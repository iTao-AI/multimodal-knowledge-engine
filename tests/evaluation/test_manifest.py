import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from mke.evaluation.manifest import (
    FixtureValidationError,
    ManifestValidationError,
    load_retrieval_manifest,
    snapshot_retrieval_fixtures,
)

MANIFEST = Path("tests/fixtures/retrieval-eval-v1.json")


def _payload() -> dict[str, object]:
    value: dict[str, object] = json.loads(MANIFEST.read_text())
    return value


def _write_manifest(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload))
    return path


def _minimal_payload() -> dict[str, object]:
    return {
        "schema_version": "mke.retrieval_eval.v1",
        "manifest_id": "test-manifest",
        "documents": [
            {
                "document_id": "document-one",
                "media_type": "application/pdf",
                "primary_file": {
                    "path": "fixture.pdf",
                    "sha256": "0" * 64,
                    "bytes": 22,
                },
                "supporting_files": [],
            }
        ],
        "queries": [
            {
                "query_id": "answerable-one",
                "text": "searchable token",
                "category": "answerable",
                "relevant_locators": [
                    {
                        "document_id": "document-one",
                        "locator_kind": "page",
                        "locator_start": 1,
                        "locator_end": 1,
                    }
                ],
            },
            {
                "query_id": "unanswerable-one",
                "text": "absent token",
                "category": "out_of_corpus",
                "relevant_locators": [],
            },
        ],
    }


def _add_unknown_field(payload: dict[str, object]) -> None:
    payload["unexpected"] = True


def _remove_documents(payload: dict[str, object]) -> None:
    payload["documents"] = []


def _remove_queries(payload: dict[str, object]) -> None:
    payload["queries"] = []


def _remove_unanswerable_queries(payload: dict[str, object]) -> None:
    queries = cast(list[dict[str, object]], payload["queries"])
    replacement = json.loads(json.dumps(queries[0]))
    replacement["query_id"] = "answerable-two"
    queries[1] = cast(dict[str, object], replacement)


def test_load_checked_in_manifest_has_frozen_shape() -> None:
    manifest = load_retrieval_manifest(MANIFEST)

    assert manifest.schema_version == "mke.retrieval_eval.v1"
    assert manifest.manifest_id == "retrieval-eval-v1"
    assert len(manifest.documents) == 3
    assert len(manifest.queries) == 24
    assert manifest.queries[0].query_id == "volcano-answerable-01"


@pytest.mark.parametrize(
    ("mutation", "cause"),
    [
        (_add_unknown_field, "manifest contains unknown fields"),
        (
            lambda payload: payload["queries"].append(payload["queries"][0]),  # type: ignore[union-attr,index]
            "query identifiers must be unique",
        ),
        (
            lambda payload: payload["documents"][0]["primary_file"].update(  # type: ignore[index,union-attr]
                {"path": "../outside.pdf"}
            ),
            "fixture path is invalid",
        ),
        (
            lambda payload: payload["queries"][0].update({"category": "unknown"}),  # type: ignore[index,union-attr]
            "query category is invalid",
        ),
        (
            lambda payload: payload["queries"][0].update({"relevant_locators": []}),  # type: ignore[index,union-attr]
            "answerable query requires relevant locators",
        ),
        (
            lambda payload: payload["documents"][0].update({"unexpected": True}),  # type: ignore[index,union-attr]
            "document contains unknown fields",
        ),
        (
            lambda payload: payload["queries"][0].update({"unexpected": True}),  # type: ignore[index,union-attr]
            "query contains unknown fields",
        ),
        (
            lambda payload: payload["queries"][0]["relevant_locators"][0].update(  # type: ignore[index,union-attr]
                {"unexpected": True}
            ),
            "qrel contains unknown fields",
        ),
    ],
)
def test_manifest_rejects_invalid_shapes(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], None],
    cause: str,
) -> None:
    payload = _payload()
    mutation(payload)

    with pytest.raises(ManifestValidationError, match=cause):
        load_retrieval_manifest(_write_manifest(tmp_path, payload))


@pytest.mark.parametrize(
    ("field", "value", "cause"),
    [
        ("manifest_id", "UPPER", "manifest identifier is invalid"),
        ("manifest_id", "", "manifest identifier is invalid"),
        ("schema_version", "mke.retrieval_eval.v2", "manifest schema version is unsupported"),
    ],
)
def test_manifest_rejects_invalid_top_level_values(
    tmp_path: Path, field: str, value: str, cause: str
) -> None:
    payload = _payload()
    payload[field] = value

    with pytest.raises(ManifestValidationError, match=cause):
        load_retrieval_manifest(_write_manifest(tmp_path, payload))


def test_manifest_rejects_checksum_mismatch_before_ingest(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.pdf"
    fixture.write_bytes(b"not the approved bytes")

    with pytest.raises(FixtureValidationError, match="fixture checksum does not match"):
        load_retrieval_manifest(_write_manifest(tmp_path, _minimal_payload()))


def test_manifest_rejects_byte_size_mismatch_before_ingest(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.pdf"
    fixture.write_bytes(b"x" * 21)
    payload = _minimal_payload()
    primary = payload["documents"][0]["primary_file"]  # type: ignore[index]
    primary["sha256"] = hashlib.sha256(fixture.read_bytes()).hexdigest()

    with pytest.raises(FixtureValidationError, match="fixture byte size does not match"):
        load_retrieval_manifest(_write_manifest(tmp_path, payload))


@pytest.mark.parametrize(
    ("path", "cause"),
    [
        ("/absolute.pdf", "fixture path is invalid"),
        ("dir/../outside.pdf", "fixture path is invalid"),
        ("", "fixture path is invalid"),
    ],
)
def test_manifest_rejects_unsafe_fixture_paths(
    tmp_path: Path, path: str, cause: str
) -> None:
    payload = _minimal_payload()
    payload["documents"][0]["primary_file"]["path"] = path  # type: ignore[index]

    with pytest.raises(ManifestValidationError, match=cause):
        load_retrieval_manifest(_write_manifest(tmp_path, payload))


def test_manifest_rejects_non_lowercase_checksum(tmp_path: Path) -> None:
    payload = _minimal_payload()
    payload["documents"][0]["primary_file"]["sha256"] = "A" * 64  # type: ignore[index]

    with pytest.raises(ManifestValidationError, match="fixture checksum is invalid"):
        load_retrieval_manifest(_write_manifest(tmp_path, payload))


@pytest.mark.parametrize(
    ("mutation", "cause"),
    [
        (
            lambda payload: payload["documents"].append(payload["documents"][0]),  # type: ignore[union-attr,index]
            "document identifiers must be unique",
        ),
        (
            lambda payload: payload["documents"].append(  # type: ignore[union-attr]
                {
                    **payload["documents"][0],  # type: ignore[index]
                    "document_id": "document-two",
                }
            ),
            "primary fixture paths must be unique",
        ),
        (
            lambda payload: payload["documents"].append(  # type: ignore[union-attr]
                {
                    **payload["documents"][0],  # type: ignore[index]
                    "document_id": "document-two",
                    "primary_file": {
                        **payload["documents"][0]["primary_file"],  # type: ignore[index]
                        "path": "fixture-two.pdf",
                    },
                }
            ),
            "primary fixture checksums must be unique",
        ),
    ],
)
def test_manifest_rejects_duplicate_document_identity(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], None],
    cause: str,
) -> None:
    payload = _minimal_payload()
    mutation(payload)

    with pytest.raises(ManifestValidationError, match=cause):
        load_retrieval_manifest(_write_manifest(tmp_path, payload))


def test_manifest_requires_exact_video_sidecar_adjacency(tmp_path: Path) -> None:
    payload = _minimal_payload()
    document = payload["documents"][0]  # type: ignore[index]
    document["media_type"] = "video/mp4"
    document["primary_file"]["path"] = "clip.mp4"
    document["supporting_files"] = [
        {
            "role": "transcript_sidecar",
            "path": "other.json",
            "sha256": "1" * 64,
            "bytes": 10,
        }
    ]

    with pytest.raises(ManifestValidationError, match="video transcript sidecar path is invalid"):
        load_retrieval_manifest(_write_manifest(tmp_path, payload))


@pytest.mark.parametrize(
    ("kind", "start", "end", "cause"),
    [
        ("page", 0, 0, "page locator is invalid"),
        ("page", 1, 2, "page locator is invalid"),
        ("timestamp_ms", -1, 2, "timestamp locator is invalid"),
        ("timestamp_ms", 2, 1, "timestamp locator is invalid"),
        ("other", 1, 1, "locator kind is invalid"),
    ],
)
def test_manifest_rejects_invalid_locator_ranges(
    tmp_path: Path, kind: str, start: int, end: int, cause: str
) -> None:
    payload = _minimal_payload()
    locator = cast(
        dict[str, object],
        payload["queries"][0]["relevant_locators"][0],  # type: ignore[index]
    )
    locator.update(
        {"locator_kind": kind, "locator_start": start, "locator_end": end}
    )

    with pytest.raises(ManifestValidationError, match=cause):
        load_retrieval_manifest(_write_manifest(tmp_path, payload))


def test_manifest_rejects_unanswerable_query_with_qrels(tmp_path: Path) -> None:
    payload = _minimal_payload()
    payload["queries"][1]["relevant_locators"] = [  # type: ignore[index]
        payload["queries"][0]["relevant_locators"][0]  # type: ignore[index]
    ]

    with pytest.raises(
        ManifestValidationError, match="unanswerable query must not have relevant locators"
    ):
        load_retrieval_manifest(_write_manifest(tmp_path, payload))


@pytest.mark.parametrize(
    ("mutation", "cause"),
    [
        (_remove_documents, "manifest document count is invalid"),
        (_remove_queries, "manifest query count is invalid"),
        (_remove_unanswerable_queries, "manifest requires answerable and unanswerable queries"),
    ],
)
def test_manifest_rejects_invalid_group_bounds(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], object],
    cause: str,
) -> None:
    payload = _minimal_payload()
    mutation(payload)

    with pytest.raises(ManifestValidationError, match=cause):
        load_retrieval_manifest(_write_manifest(tmp_path, payload))


def test_manifest_distinguishes_missing_file_from_invalid_json(tmp_path: Path) -> None:
    with pytest.raises(ManifestValidationError, match="manifest file is missing"):
        load_retrieval_manifest(tmp_path / "missing.json")

    invalid = tmp_path / "invalid.json"
    invalid.write_text("{")
    with pytest.raises(ManifestValidationError, match="manifest is not valid JSON"):
        load_retrieval_manifest(invalid)


def test_snapshot_preserves_relative_paths_and_verified_bytes(tmp_path: Path) -> None:
    manifest = load_retrieval_manifest(MANIFEST)
    snapshot = snapshot_retrieval_fixtures(manifest, tmp_path / "snapshot")

    assert snapshot.root == (tmp_path / "snapshot").resolve()
    for document in snapshot.documents:
        files = (document.primary_file, *document.supporting_files)
        for fixture in files:
            copied = snapshot.resolve(fixture)
            assert copied.is_file()
            assert hashlib.sha256(copied.read_bytes()).hexdigest() == fixture.sha256
