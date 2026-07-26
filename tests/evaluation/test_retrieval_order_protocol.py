from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest

from mke.evaluation.retrieval_order_protocol import (
    RetrievalOrderProtocolError,
    load_retrieval_order_protocol,
    load_retrieval_order_protocol_metadata,
    load_retrieval_order_protocol_partition,
)
from tests.evaluation.test_retrieval_order_workflow import (
    synthetic_fixture_payload,
    synthetic_partition_metadata,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/fixtures/retrieval-order-v1/protocol.json"
CANONICAL_HOLDOUT_FIXTURE = (
    ROOT / "tests/fixtures/retrieval-order-v1/holdout/cases.json"
)


@pytest.fixture(autouse=True)
def forbid_canonical_holdout_fixture_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = Path.read_bytes

    def guarded(path: Path) -> bytes:
        if path.resolve() == CANONICAL_HOLDOUT_FIXTURE.resolve():
            raise AssertionError("canonical holdout fixture must stay unopened")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", guarded)


def test_protocol_freezes_stable_keys_partitions_and_runtime_profile() -> None:
    protocol = load_retrieval_order_protocol_metadata(
        PROTOCOL, repository_root=ROOT
    )

    assert protocol.protocol_id == "retrieval-order-v1"
    assert protocol.key_contract.fts == (
        "rank",
        "locator_start",
        "locator_kind",
        "locator_end",
        "assets.sha256",
    )
    assert protocol.key_contract.cjk == (
        "-overlap_count",
        "-overlap_ratio",
        "content_fingerprint",
        "locator_kind",
        "locator_start",
        "locator_end",
    )
    assert protocol.development.sha256 != protocol.holdout.sha256
    assert protocol.development.source_ids.isdisjoint(
        protocol.holdout.source_ids
    )
    assert protocol.development.query_ids.isdisjoint(
        protocol.holdout.query_ids
    )
    assert protocol.runtime_profile_fields == (
        "python",
        "sqlite",
        "sqlite_source_id",
        "sqlite_compile_options",
        "fts5_rank_configuration",
        "strategy_revision",
        "query_policy_revision",
    )


def _payload() -> dict[str, object]:
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))


def _write(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "mutation",
    [
        "absolute_path",
        "parent_path",
        "hash_mismatch",
        "duplicate_case_id",
        "shared_source_id",
        "shared_query_id",
        "missing_timestamp",
        "opaque_projection_id",
    ],
)
def test_protocol_rejects_identity_partition_or_projection_tampering(
    tmp_path: Path,
    mutation: str,
) -> None:
    if mutation == "hash_mismatch":
        root, protocol_path, _, _ = _synthetic_protocol(tmp_path)
        payload = json.loads(protocol_path.read_text(encoding="utf-8"))
        partitions = cast(dict[str, object], payload["partitions"])
        development = cast(
            dict[str, object],
            partitions["development"],
        )
        development["sha256"] = "0" * 64
        protocol_path.write_text(json.dumps(payload), encoding="utf-8")
        metadata = load_retrieval_order_protocol_metadata(
            protocol_path,
            repository_root=root,
        )
        with pytest.raises(RetrievalOrderProtocolError):
            load_retrieval_order_protocol_partition(
                metadata,
                "development",
            )
        return
    payload = _payload()
    partitions = payload["partitions"]
    assert isinstance(partitions, dict)
    development = cast(dict[str, object], partitions["development"])
    holdout = cast(dict[str, object], partitions["holdout"])
    assert isinstance(development, dict)
    assert isinstance(holdout, dict)
    development_cases = cast(dict[str, object], development["cases"])
    holdout_cases = cast(dict[str, object], holdout["cases"])
    assert isinstance(development_cases, dict)
    assert isinstance(holdout_cases, dict)
    if mutation == "absolute_path":
        development["path"] = "/tmp/cases.json"
    elif mutation == "parent_path":
        development["path"] = "../cases.json"
    elif mutation == "duplicate_case_id":
        case_ids = cast(list[object], development_cases["case_ids"])
        assert isinstance(case_ids, list)
        case_ids.append(case_ids[0])
    elif mutation == "shared_source_id":
        source_ids = cast(list[object], holdout_cases["source_ids"])
        development_source_ids = cast(
            list[object], development_cases["source_ids"]
        )
        assert isinstance(source_ids, list)
        assert isinstance(development_source_ids, list)
        source_ids[0] = development_source_ids[0]
    elif mutation == "shared_query_id":
        query_ids = cast(list[object], holdout_cases["query_ids"])
        development_query_ids = cast(
            list[object], development_cases["query_ids"]
        )
        assert isinstance(query_ids, list)
        assert isinstance(development_query_ids, list)
        query_ids[0] = development_query_ids[0]
    elif mutation == "missing_timestamp":
        coverage = cast(list[object], development_cases["coverage"])
        assert isinstance(coverage, list)
        coverage.remove("timestamp")
    else:
        projections = cast(
            list[object],
            development_cases["expected_stable_projections"],
        )
        assert isinstance(projections, list)
        projection = cast(list[object], projections[0])
        assert isinstance(projection, list)
        projection[0] = "evidence_opaque"

    with pytest.raises(RetrievalOrderProtocolError):
        load_retrieval_order_protocol_metadata(
            _write(tmp_path, payload), repository_root=ROOT
        )


def test_protocol_metadata_records_exact_canonical_partition_identities() -> None:
    protocol = load_retrieval_order_protocol_metadata(
        PROTOCOL, repository_root=ROOT
    )

    assert protocol.development.bytes == 6196
    assert protocol.development.sha256 == (
        "e37e9519d899fc934c1758860f1b40d3605ed065a11b1921fdac914746f733f5"
    )
    assert protocol.holdout.bytes == 2896
    assert protocol.holdout.sha256 == (
        "e95c5253d0284f8127754591b9da9aa71b30a8ceae2670ca4751456cf7d4a080"
    )


def test_metadata_preflight_does_not_open_partition_fixtures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, protocol_path, development_path, holdout_path = (
        _synthetic_protocol(tmp_path)
    )
    opened: list[Path] = []
    original = Path.read_bytes

    def read_bytes(path: Path) -> bytes:
        if path.resolve() in {development_path, holdout_path}:
            opened.append(path.resolve())
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)

    metadata = load_retrieval_order_protocol_metadata(
        protocol_path,
        repository_root=root,
    )

    assert opened == []
    development = load_retrieval_order_protocol_partition(
        metadata,
        "development",
    )
    assert development.path == development_path
    assert opened == [development_path]
    holdout = load_retrieval_order_protocol_partition(metadata, "holdout")
    assert holdout.path == holdout_path
    assert opened == [development_path, holdout_path]
    complete = load_retrieval_order_protocol(
        protocol_path,
        repository_root=root,
    )
    assert complete.development.fixture["partition"] == "development"
    assert complete.holdout.fixture["partition"] == "holdout"


def _synthetic_protocol(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path]:
    root = tmp_path / "synthetic-repository"
    fixture_root = root / "fixtures"
    fixture_root.mkdir(parents=True)
    payload = deepcopy(_payload())
    partitions = cast(dict[str, object], payload["partitions"])
    paths: dict[str, Path] = {}
    for name in ("development", "holdout"):
        record = cast(dict[str, object], partitions[name])
        fixture = synthetic_fixture_payload(name)
        data = (
            json.dumps(
                fixture,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode()
        destination = fixture_root / f"{name}.json"
        destination.write_bytes(data)
        record["path"] = destination.relative_to(root).as_posix()
        record["bytes"] = len(data)
        record["sha256"] = hashlib.sha256(data).hexdigest()
        record["cases"] = synthetic_partition_metadata(fixture)
        paths[name] = destination.resolve()
    protocol_path = root / "protocol.json"
    protocol_path.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True),
        encoding="utf-8",
    )
    return (
        root.resolve(),
        protocol_path.resolve(),
        paths["development"],
        paths["holdout"],
    )
