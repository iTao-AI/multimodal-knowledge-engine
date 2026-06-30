from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from mke.evaluation.hybrid_rrf_workflow import (
    HybridRrfWorkflowError,
    load_hybrid_rrf_inputs,
)

ROOT = Path(__file__).resolve().parents[2]
DENSE_ARTIFACT = ROOT / "benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json"
PROTOCOL = ROOT / "tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json"


@pytest.fixture
def repository_root() -> Path:
    return ROOT


def test_load_hybrid_inputs_binds_development_and_holdout(
    repository_root: Path,
) -> None:
    inputs = load_hybrid_rrf_inputs(
        dense_artifact_path=DENSE_ARTIFACT,
        protocol_path=PROTOCOL,
        repository_root=repository_root,
    )

    assert len(inputs.development.queries) == 24
    assert len(inputs.holdout.queries) == 24
    assert inputs.state.runtime_promotion_status == "not_evaluated"
    assert inputs.state.e3d_status == "eligible"
    assert inputs.state.selected_threshold == 0.58


def test_lexical_rank_comes_from_retrieved_locator_order(
    repository_root: Path,
) -> None:
    inputs = load_hybrid_rrf_inputs(
        dense_artifact_path=DENSE_ARTIFACT,
        protocol_path=PROTOCOL,
        repository_root=repository_root,
    )
    query = next(
        item
        for item in inputs.development.queries
        if item.query_id == "zh-dev-exact-01"
    )

    assert [row.rank for row in query.lexical] == [1, 2]
    assert [row.locator_start for row in query.lexical] == [14, 13]


def test_dense_threshold_filter_preserves_recorded_rank(
    repository_root: Path,
) -> None:
    inputs = load_hybrid_rrf_inputs(
        dense_artifact_path=DENSE_ARTIFACT,
        protocol_path=PROTOCOL,
        repository_root=repository_root,
    )
    query = next(
        item
        for item in inputs.development.queries
        if item.query_id == "zh-dev-exact-01"
    )

    assert [row.rank for row in query.dense] == [1]
    assert query.dense[0].stable_locator_id.startswith("ub-service-core|page|14|14|")


def test_loader_rejects_bad_state_or_threshold(repository_root: Path, tmp_path: Path) -> None:
    payload = _artifact_copy()
    cast(dict[str, object], payload["comparison"])["e3d_status"] = "not_eligible"
    path = tmp_path / "bad-e3d.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(HybridRrfWorkflowError, match="e3d_status"):
        load_hybrid_rrf_inputs(
            dense_artifact_path=path,
            protocol_path=PROTOCOL,
            repository_root=repository_root,
        )

    payload = _artifact_copy()
    cast(dict[str, object], payload["threshold_report"])["selected_threshold"] = 0.59
    path = tmp_path / "bad-threshold.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(HybridRrfWorkflowError, match="threshold"):
        load_hybrid_rrf_inputs(
            dense_artifact_path=path,
            protocol_path=PROTOCOL,
            repository_root=repository_root,
        )


def test_loader_rejects_malformed_or_duplicate_arm_rows(
    repository_root: Path,
    tmp_path: Path,
) -> None:
    payload = _artifact_copy()
    runtime = cast(dict[str, object], payload["current_runtime"])
    semantics = cast(dict[str, object], runtime["semantics"])
    runtime_results = cast(list[dict[str, object]], semantics["results"])
    runtime_results[0]["retrieved_locators"] = "bad"
    path = tmp_path / "bad-lexical.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(HybridRrfWorkflowError, match="retrieved_locators"):
        load_hybrid_rrf_inputs(
            dense_artifact_path=path,
            protocol_path=PROTOCOL,
            repository_root=repository_root,
        )

    payload = _artifact_copy()
    development = cast(dict[str, object], payload["development_candidate"])
    observations = cast(list[dict[str, object]], development["observations"])
    results = cast(list[dict[str, object]], observations[0]["results"])
    results[1]["stable_locator_id"] = results[0]["stable_locator_id"]
    path = tmp_path / "duplicate-dense.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(HybridRrfWorkflowError, match="duplicate"):
        load_hybrid_rrf_inputs(
            dense_artifact_path=path,
            protocol_path=PROTOCOL,
            repository_root=repository_root,
        )


def test_loader_rejects_unbound_lexical_locator(
    repository_root: Path,
    tmp_path: Path,
) -> None:
    payload = _artifact_copy()
    runtime = cast(dict[str, object], payload["current_runtime"])
    semantics = cast(dict[str, object], runtime["semantics"])
    runtime_results = cast(list[dict[str, object]], semantics["results"])
    locators = cast(list[dict[str, object]], runtime_results[0]["retrieved_locators"])
    locators[0]["locator_start"] = 999
    locators[0]["locator_end"] = 999
    path = tmp_path / "unbound-lexical.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(HybridRrfWorkflowError, match="lexical locator"):
        load_hybrid_rrf_inputs(
            dense_artifact_path=path,
            protocol_path=PROTOCOL,
            repository_root=repository_root,
        )


def _artifact_copy() -> dict[str, object]:
    return cast(dict[str, object], json.loads(DENSE_ARTIFACT.read_text(encoding="utf-8")))
