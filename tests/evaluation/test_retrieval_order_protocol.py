from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

import pytest

from mke.evaluation.retrieval_order_protocol import (
    RetrievalOrderProtocolError,
    load_retrieval_order_protocol,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/fixtures/retrieval-order-v1/protocol.json"


def test_protocol_freezes_stable_keys_partitions_and_runtime_profile() -> None:
    protocol = load_retrieval_order_protocol(
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
    elif mutation == "hash_mismatch":
        development["sha256"] = "0" * 64
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
        load_retrieval_order_protocol(
            _write(tmp_path, payload), repository_root=ROOT
        )


def test_protocol_partition_hashes_bind_exact_fixture_bytes() -> None:
    protocol = load_retrieval_order_protocol(
        PROTOCOL, repository_root=ROOT
    )
    for partition in (protocol.development, protocol.holdout):
        assert hashlib.sha256(partition.path.read_bytes()).hexdigest() == (
            partition.sha256
        )
