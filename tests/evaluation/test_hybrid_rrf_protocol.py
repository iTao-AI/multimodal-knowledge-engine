from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from mke.evaluation.hybrid_rrf_protocol import (
    HybridRrfProtocolError,
    build_hybrid_rrf_protocol_lock,
    render_hybrid_rrf_protocol_lock_json,
    validate_hybrid_rrf_protocol_lock,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def repository_root() -> Path:
    return ROOT


def test_protocol_lock_is_byte_stable(repository_root: Path) -> None:
    protocol = build_hybrid_rrf_protocol_lock(repository_root=repository_root)
    rendered = render_hybrid_rrf_protocol_lock_json(protocol)
    reparsed = json.loads(rendered)

    assert rendered.endswith("\n")
    assert reparsed == protocol
    validate_hybrid_rrf_protocol_lock(protocol, repository_root=repository_root)


def test_protocol_freezes_candidate_rrf_arms_and_inputs(repository_root: Path) -> None:
    protocol = build_hybrid_rrf_protocol_lock(repository_root=repository_root)
    candidate = cast(dict[str, object], protocol["candidate"])
    rrf = cast(dict[str, object], protocol["rrf"])
    arms = cast(dict[str, object], protocol["arms"])
    inputs = cast(dict[str, dict[str, object]], protocol["inputs"])

    assert protocol["schema_version"] == "mke.hybrid_rrf_protocol.v1"
    assert candidate == {
        "candidate_id": "cjk-active-scan-qwen3-rrf-v1",
        "candidate_revision": 1,
    }
    assert rrf == {
        "k": 60,
        "lexical_weight": 1.0,
        "dense_weight": 1.0,
        "input_depth": 10,
        "output_depth": 10,
        "score_decimals": 12,
        "rank_base": 1,
        "tie_break_order": [
            "fused_score_desc",
            "arm_hit_count_desc",
            "best_individual_rank_asc",
            "lexical_rank_asc",
            "dense_rank_asc",
            "stable_locator_id_asc",
        ],
    }
    assert arms == {
        "lexical": "cjk-active-scan-overlap-v1",
        "dense": "qwen3-embedding-0.6b-exact-v1",
    }
    assert set(inputs) == {
        "chinese_protocol",
        "qrel_adjudication",
        "dense_artifact",
        "runtime_strategy_source",
        "rrf_source",
        "workflow_source",
        "artifact_source",
        "metrics_source",
        "cli_source",
    }
    assert all(cast(int, item["bytes"]) >= 0 for item in inputs.values())
    assert all(
        isinstance(item["sha256"], str) and len(cast(str, item["sha256"])) == 64
        for item in inputs.values()
    )


def test_protocol_rejects_bool_revision(repository_root: Path) -> None:
    protocol = build_hybrid_rrf_protocol_lock(repository_root=repository_root)
    cast(dict[str, object], protocol["candidate"])["candidate_revision"] = True

    with pytest.raises(HybridRrfProtocolError, match="candidate"):
        validate_hybrid_rrf_protocol_lock(protocol, repository_root=repository_root)


def test_protocol_rejects_path_and_identity_tampering(repository_root: Path) -> None:
    protocol = build_hybrid_rrf_protocol_lock(repository_root=repository_root)

    changed = _copy(protocol)
    inputs = cast(dict[str, dict[str, object]], changed["inputs"])
    inputs["dense_artifact"]["path"] = str(
        repository_root / "benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json"
    )
    with pytest.raises(HybridRrfProtocolError, match="path"):
        validate_hybrid_rrf_protocol_lock(changed, repository_root=repository_root)

    changed = _copy(protocol)
    inputs = cast(dict[str, dict[str, object]], changed["inputs"])
    inputs["dense_artifact"]["sha256"] = "0" * 64
    with pytest.raises(HybridRrfProtocolError, match="identity"):
        validate_hybrid_rrf_protocol_lock(changed, repository_root=repository_root)


def test_protocol_rejects_bad_candidate_and_locator_contract(
    repository_root: Path,
) -> None:
    protocol = build_hybrid_rrf_protocol_lock(repository_root=repository_root)

    changed = _copy(protocol)
    cast(dict[str, object], changed["candidate"])["candidate_id"] = "other"
    with pytest.raises(HybridRrfProtocolError, match="candidate"):
        validate_hybrid_rrf_protocol_lock(changed, repository_root=repository_root)

    changed = _copy(protocol)
    cast(dict[str, object], changed["dedupe"])["key"] = ["stable_locator_id"]
    with pytest.raises(HybridRrfProtocolError, match="locator"):
        validate_hybrid_rrf_protocol_lock(changed, repository_root=repository_root)


def _copy(payload: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], json.loads(json.dumps(payload)))
