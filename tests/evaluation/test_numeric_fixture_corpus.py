import hashlib
import json
import re
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

import fitz  # pyright: ignore[reportMissingTypeStubs]
import pytest

from mke.evaluation.manifest import (
    RetrievalEvaluationManifest,
    load_retrieval_manifest,
)

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "retrieval-numeric-v1"
E1_MANIFEST = FIXTURE_ROOT.parent / "retrieval-eval-v1.json"
README = FIXTURE_ROOT / "README.md"
PROTOCOL = FIXTURE_ROOT / "protocol-lock.json"
PROTOCOL_CLAIM = "compact_query_adjacent_right_grouped_tokens_without_unrelated_change"

EXPECTED_PAGES = {
    "development.pdf": (
        "Grouped daily withdrawal total: 410,000 million gallons.",
        "Compact inventory total: 730000 storage units.",
        (
            "Non-adjacent ledger values: 410 units were accepted; "
            "after review, 000 units were rejected."
        ),
        "Identifiers: postal district 02139; equipment model ZX410000; reporting year 2005.",
    ),
    "holdout.pdf": (
        "Grouped reserve capacity: 57,600 cubic meters.",
        "Compact shipment count: 880000 sealed packages.",
        "Non-adjacent audit values: 57 samples passed; later, 600 samples failed.",
        "Identifiers: postal district 00701; sensor model AB57600; reporting year 1997.",
    ),
}

EXPECTED_QUERY_IDS = {
    "development": (
        "numeric-dev-grouped-01",
        "numeric-dev-compact-01",
        "numeric-dev-non-adjacent-01",
        "numeric-dev-leading-zero-01",
        "numeric-dev-identifier-01",
        "numeric-dev-short-01",
        "numeric-dev-outside-01",
    ),
    "holdout": (
        "numeric-holdout-grouped-01",
        "numeric-holdout-compact-01",
        "numeric-holdout-non-adjacent-01",
        "numeric-holdout-leading-zero-01",
        "numeric-holdout-identifier-01",
        "numeric-holdout-short-01",
        "numeric-holdout-outside-01",
    ),
}


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _readme_identity(name: str) -> tuple[int, str]:
    readme = README.read_text(encoding="utf-8")
    match = re.search(
        rf"^\| `{re.escape(name)}` \| (?P<bytes>[0-9]+) \| "
        rf"`(?P<sha256>[0-9a-f]{{64}})` \|$",
        readme,
        flags=re.MULTILINE,
    )
    assert match is not None
    return int(match.group("bytes")), match.group("sha256")


def test_numeric_retrieval_pdfs_match_frozen_text_and_identity() -> None:
    observed_bytes: list[bytes] = []
    observed_pages: list[set[str]] = []

    for name, expected_pages in EXPECTED_PAGES.items():
        path = FIXTURE_ROOT / name
        data = path.read_bytes()
        expected_bytes, expected_sha256 = _readme_identity(name)
        assert len(data) == expected_bytes
        assert hashlib.sha256(data).hexdigest() == expected_sha256

        with fitz.open(path) as document:
            assert len(document) == 4
            pages = tuple(
                _normalize(
                    cast(
                        str,
                        page.get_text(  # pyright: ignore[reportUnknownMemberType]
                            "text", sort=True
                        ),
                    )
                )
                for page in document
            )
        assert pages == expected_pages
        observed_bytes.append(data)
        observed_pages.append(set(pages))

    assert observed_bytes[0] != observed_bytes[1]
    assert observed_pages[0].isdisjoint(observed_pages[1])


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_exact_keys(payload: Mapping[str, object], expected: set[str]) -> None:
    if set(payload) != expected:
        raise ValueError("protocol validation failed")


def _resolve_protocol_path(root: Path, raw_path: object, expected: str) -> Path:
    if not isinstance(raw_path, str) or raw_path != expected:
        raise ValueError("protocol validation failed")
    relative = Path(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("protocol validation failed")
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("protocol validation failed")
    return resolved


def _validate_protocol(path: Path) -> None:
    payload = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    _require_exact_keys(
        payload,
        {
            "schema_version",
            "protocol_id",
            "candidate",
            "claim",
            "manifests",
            "fixtures",
            "required_query_ids",
        },
    )
    if payload["schema_version"] != "mke.retrieval_numeric_protocol.v1":
        raise ValueError("protocol validation failed")
    if payload["protocol_id"] != "retrieval-numeric-v1":
        raise ValueError("protocol validation failed")
    candidate = cast(dict[str, object], payload["candidate"])
    _require_exact_keys(candidate, {"id", "revision"})
    if candidate != {"id": "numeric-grouping-v1", "revision": 1}:
        raise ValueError("protocol validation failed")
    if payload["claim"] != PROTOCOL_CLAIM:
        raise ValueError("protocol validation failed")

    root = path.parent.parent
    manifests = cast(dict[str, dict[str, object]], payload["manifests"])
    _require_exact_keys(manifests, {"development", "holdout", "e1"})
    manifest_paths: dict[str, Path] = {}
    for partition, expected_path in {
        "development": "retrieval-numeric-v1/development.json",
        "holdout": "retrieval-numeric-v1/holdout.json",
        "e1": "retrieval-eval-v1.json",
    }.items():
        record = manifests[partition]
        _require_exact_keys(record, {"path", "sha256"})
        manifest_path = _resolve_protocol_path(root, record["path"], expected_path)
        if record["sha256"] != _sha256(manifest_path):
            raise ValueError("protocol-bound input identity mismatch")
        manifest_paths[partition] = manifest_path

    fixtures = cast(list[dict[str, object]], payload["fixtures"])
    if len(fixtures) != 2:
        raise ValueError("protocol validation failed")
    for fixture, partition in zip(fixtures, ("development", "holdout"), strict=True):
        _require_exact_keys(fixture, {"partition", "path", "bytes", "sha256"})
        if fixture["partition"] != partition:
            raise ValueError("protocol validation failed")
        fixture_path = _resolve_protocol_path(
            root,
            fixture["path"],
            f"retrieval-numeric-v1/{partition}.pdf",
        )
        if fixture["bytes"] != fixture_path.stat().st_size:
            raise ValueError("protocol-bound input identity mismatch")
        if fixture["sha256"] != _sha256(fixture_path):
            raise ValueError("protocol-bound input identity mismatch")

    required_query_ids = cast(dict[str, list[str]], payload["required_query_ids"])
    _require_exact_keys(required_query_ids, {"development", "holdout", "e1"})
    loaded_manifests: dict[str, RetrievalEvaluationManifest] = {}
    for partition in ("development", "holdout"):
        manifest = load_retrieval_manifest(manifest_paths[partition])
        loaded_manifests[partition] = manifest
        if tuple(required_query_ids[partition]) != EXPECTED_QUERY_IDS[partition]:
            raise ValueError("protocol validation failed")
        if tuple(query.query_id for query in manifest.queries) != EXPECTED_QUERY_IDS[partition]:
            raise ValueError("protocol validation failed")
    if {
        query.query_id for query in loaded_manifests["development"].queries
    } & {query.query_id for query in loaded_manifests["holdout"].queries}:
        raise ValueError("protocol validation failed")
    if {
        query.text for query in loaded_manifests["development"].queries
    } & {query.text for query in loaded_manifests["holdout"].queries}:
        raise ValueError("protocol validation failed")
    e1 = load_retrieval_manifest(manifest_paths["e1"])
    if tuple(required_query_ids["e1"]) != tuple(query.query_id for query in e1.queries):
        raise ValueError("protocol validation failed")


def test_numeric_manifests_freeze_inventory_and_disjoint_holdout() -> None:
    development = cast(
        dict[str, object],
        json.loads((FIXTURE_ROOT / "development.json").read_text(encoding="utf-8")),
    )
    holdout = cast(
        dict[str, object],
        json.loads((FIXTURE_ROOT / "holdout.json").read_text(encoding="utf-8")),
    )
    development_queries = cast(list[dict[str, object]], development["queries"])
    holdout_queries = cast(list[dict[str, object]], holdout["queries"])

    assert development["manifest_id"] == "retrieval-numeric-v1-development"
    assert holdout["manifest_id"] == "retrieval-numeric-v1-holdout"
    assert tuple(query["query_id"] for query in development_queries) == EXPECTED_QUERY_IDS[
        "development"
    ]
    assert tuple(query["query_id"] for query in holdout_queries) == EXPECTED_QUERY_IDS[
        "holdout"
    ]
    assert {query["query_id"] for query in development_queries}.isdisjoint(
        query["query_id"] for query in holdout_queries
    )
    assert {query["text"] for query in development_queries}.isdisjoint(
        query["text"] for query in holdout_queries
    )
    assert sum(query["category"] == "answerable" for query in development_queries) == 5
    assert sum(query["category"] == "answerable" for query in holdout_queries) == 5
    assert all(
        len(cast(list[object], query["relevant_locators"])) == 1
        for queries in (development_queries, holdout_queries)
        for query in queries
        if query["category"] == "answerable"
    )


def test_protocol_lock_binds_all_inputs() -> None:
    _validate_protocol(PROTOCOL)


def _copy_protocol(tmp_path: Path) -> Path:
    root = tmp_path / "fixtures"
    shutil.copytree(FIXTURE_ROOT, root / "retrieval-numeric-v1")
    shutil.copy2(E1_MANIFEST, root / E1_MANIFEST.name)
    for manifest_name in ("development.json", "holdout.json"):
        payload = json.loads((FIXTURE_ROOT / manifest_name).read_text(encoding="utf-8"))
        for document in payload["documents"]:
            fixture_name = Path(document["primary_file"]["path"]).name
            document["primary_file"]["path"] = fixture_name
        (root / "retrieval-numeric-v1" / manifest_name).write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
    protocol = root / "retrieval-numeric-v1" / "protocol-lock.json"
    payload = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    for partition, manifest_name in {
        "development": "development.json",
        "holdout": "holdout.json",
    }.items():
        payload["manifests"][partition]["sha256"] = _sha256(
            root / "retrieval-numeric-v1" / manifest_name
        )
    protocol.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return protocol


def _add_unknown(payload: dict[str, object]) -> None:
    payload["unexpected"] = True


def _change_candidate_id(payload: dict[str, object]) -> None:
    cast(dict[str, object], payload["candidate"])["id"] = "unknown"


def _change_candidate_revision(payload: dict[str, object]) -> None:
    cast(dict[str, object], payload["candidate"])["revision"] = 2


def _change_claim(payload: dict[str, object]) -> None:
    payload["claim"] = "broader_claim"


def _change_development_path(payload: dict[str, object], path: str) -> None:
    manifests = cast(dict[str, dict[str, object]], payload["manifests"])
    manifests["development"]["path"] = path


def _absolute_development_path(payload: dict[str, object]) -> None:
    _change_development_path(payload, "/tmp/development.json")


def _parent_development_path(payload: dict[str, object]) -> None:
    _change_development_path(payload, "../development.json")


def _alternate_development_path(payload: dict[str, object]) -> None:
    _change_development_path(payload, "retrieval-numeric-v1/alternate.json")


def _change_e1_checksum(payload: dict[str, object]) -> None:
    manifests = cast(dict[str, dict[str, object]], payload["manifests"])
    manifests["e1"]["sha256"] = "0" * 64


def _change_fixture_bytes(payload: dict[str, object]) -> None:
    fixtures = cast(list[dict[str, object]], payload["fixtures"])
    fixtures[0]["bytes"] = 1


@pytest.mark.parametrize(
    ("mutation", "cause"),
    [
        (_add_unknown, "protocol validation failed"),
        (_change_candidate_id, "protocol validation failed"),
        (_change_candidate_revision, "protocol validation failed"),
        (_change_claim, "protocol validation failed"),
        (_absolute_development_path, "protocol validation failed"),
        (_parent_development_path, "protocol validation failed"),
        (_alternate_development_path, "protocol validation failed"),
        (_change_e1_checksum, "protocol-bound input identity mismatch"),
        (_change_fixture_bytes, "protocol-bound input identity mismatch"),
    ],
)
def test_protocol_lock_rejects_mutations(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], None],
    cause: str,
) -> None:
    protocol = _copy_protocol(tmp_path)
    payload = cast(
        dict[str, object],
        json.loads(protocol.read_text(encoding="utf-8")),
    )
    mutation(payload)
    protocol.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=cause):
        _validate_protocol(protocol)


def test_protocol_lock_rejects_symlink_escape(tmp_path: Path) -> None:
    protocol = _copy_protocol(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_bytes((protocol.parent / "development.json").read_bytes())
    (protocol.parent / "development.json").unlink()
    (protocol.parent / "development.json").symlink_to(outside)
    payload = json.loads(protocol.read_text(encoding="utf-8"))
    payload["manifests"]["development"]["sha256"] = _sha256(outside)
    protocol.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="protocol validation failed"):
        _validate_protocol(protocol)


@pytest.mark.parametrize(
    "relative_path",
    [
        "retrieval-numeric-v1/development.json",
        "retrieval-numeric-v1/holdout.json",
        "retrieval-numeric-v1/development.pdf",
        "retrieval-numeric-v1/holdout.pdf",
    ],
)
def test_protocol_lock_rejects_bound_file_mutation(
    tmp_path: Path,
    relative_path: str,
) -> None:
    protocol = _copy_protocol(tmp_path)
    target = protocol.parent.parent / relative_path
    target.write_bytes(target.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="protocol-bound input identity mismatch"):
        _validate_protocol(protocol)
