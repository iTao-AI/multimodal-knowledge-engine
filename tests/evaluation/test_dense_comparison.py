from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from mke.evaluation.dense_comparison import (
    DenseArmEvidence,
    DenseComparisonError,
    DenseComparisonIdentity,
    DenseComparisonState,
    DenseDevelopmentFreeze,
    DenseHoldoutEvidence,
    DensePartitionObservation,
    freeze_dense_development,
)
from mke.evaluation.dense_threshold import (
    DenseThresholdInput,
    select_dense_threshold,
)


def test_development_freeze_keeps_four_arms_separate_and_historical() -> None:
    e3a = DenseArmEvidence("e3a-historical-fts5-baseline", "e3a-frozen")
    e3b = DenseArmEvidence("cjk-trigram-overlap-v1", "e3b-frozen")

    freeze = freeze_dense_development(
        e3a=e3a,
        e3b=e3b,
        current_runtime_expected_digest="runtime-frozen",
        current_runtime_observed_digest="runtime-frozen",
        threshold_report=_passing_threshold_report(),
        identity=_identity(),
        snapshot_id="development-snapshot",
        projection_id="development-projection",
    )

    assert freeze.development_status == "passed"
    assert freeze.selected_threshold == 0.7
    assert freeze.arms == (
        e3a,
        e3b,
        DenseArmEvidence("cjk-active-scan-overlap-v1", "runtime-frozen"),
        DenseArmEvidence("qwen3-embedding-0.6b-exact-v1", "development-projection"),
    )
    assert not hasattr(freeze, "fused_score")


def test_development_freeze_rejects_current_runtime_semantic_drift() -> None:
    with pytest.raises(DenseComparisonError, match="current runtime semantics drift"):
        freeze_dense_development(
            e3a=DenseArmEvidence("e3a-historical-fts5-baseline", "e3a-frozen"),
            e3b=DenseArmEvidence("cjk-trigram-overlap-v1", "e3b-frozen"),
            current_runtime_expected_digest="runtime-frozen",
            current_runtime_observed_digest="runtime-changed",
            threshold_report=_passing_threshold_report(),
            identity=_identity(),
            snapshot_id="development-snapshot",
            projection_id="development-projection",
        )


def test_valid_negative_development_never_observes_holdout() -> None:
    state = DenseComparisonState()
    freeze = _freeze(_valid_negative_threshold_report())
    calls = 0

    def forbidden_holdout() -> DenseHoldoutEvidence:
        nonlocal calls
        calls += 1
        raise AssertionError("holdout must not be observed")

    result = state.complete(freeze, holdout_loader=forbidden_holdout)

    assert calls == 0
    assert result["candidate_status"] == "completed"
    assert result["e3d_status"] == "not_eligible"
    assert result["holdout_status"] == "not_observed"
    assert result["runtime_promotion_status"] == "not_evaluated"


def test_holdout_passes_once_after_frozen_development() -> None:
    state = DenseComparisonState()
    freeze = _freeze(_passing_threshold_report())
    holdout = _holdout(
        (
            _recovery("semantic-holdout"),
            _recovery("multi-holdout", category="multi_condition"),
            _unanswerable("unanswerable-a", no_hit=True),
            _unanswerable("unanswerable-b", no_hit=False),
            _hard_negative("hard-a", failed=False),
            _hard_negative("hard-b", failed=False),
            _hard_negative("hard-c", failed=False),
            _hard_negative("hard-d", failed=False),
            _hard_negative("hard-e", failed=False),
            _hard_negative("hard-f", failed=False),
            _hard_negative("hard-g", failed=True),
        )
    )

    result = state.complete(freeze, holdout_loader=lambda: holdout)

    assert result["candidate_status"] == "completed"
    assert result["e3d_status"] == "eligible"
    assert result["holdout_status"] == "observed"
    assert result["holdout"]["recovered_target_grade2_count"] == 2
    assert result["holdout"]["unanswerable_no_hit"] == 0.5
    assert result["holdout"]["hard_negative_failure"] == 0.142857
    assert result["runtime_promotion_status"] == "not_evaluated"

    with pytest.raises(DenseComparisonError, match="holdout already observed"):
        state.complete(freeze, holdout_loader=lambda: holdout)


def test_existing_completion_record_and_identity_drift_fail_closed() -> None:
    freeze = _freeze(_passing_threshold_report())
    holdout = _holdout((_recovery("a"), _recovery("b")))

    with pytest.raises(DenseComparisonError, match="completion record already exists"):
        DenseComparisonState(completion_record_exists=True).complete(
            freeze, holdout_loader=lambda: holdout
        )

    changed = replace(
        holdout,
        identity=replace(holdout.identity, model_revision="changed"),
    )
    with pytest.raises(DenseComparisonError, match="holdout identity drift"):
        DenseComparisonState().complete(freeze, holdout_loader=lambda: changed)


def test_holdout_gate_failure_is_completed_negative_and_report_only_stays_separate() -> None:
    freeze = _freeze(_passing_threshold_report())
    holdout = _holdout(
        (
            _recovery("semantic-holdout"),
            _recovery("number-holdout", category="number_date_unit"),
            _recovery("proper-holdout", category="proper_noun_mixed"),
            _unanswerable("unanswerable-a", no_hit=True),
            _hard_negative("hard-a", failed=True),
        )
    )

    result = DenseComparisonState().complete(
        freeze, holdout_loader=lambda: holdout
    )

    assert result["candidate_status"] == "completed"
    assert result["e3d_status"] == "not_eligible"
    assert result["holdout"]["recovered_target_grade2_count"] == 1
    assert result["holdout"]["report_only_recovery_ids"] == [
        "number-holdout",
        "proper-holdout",
    ]


def _freeze(threshold_report: dict[str, Any]) -> DenseDevelopmentFreeze:
    return freeze_dense_development(
        e3a=DenseArmEvidence("e3a-historical-fts5-baseline", "e3a-frozen"),
        e3b=DenseArmEvidence("cjk-trigram-overlap-v1", "e3b-frozen"),
        current_runtime_expected_digest="runtime-frozen",
        current_runtime_observed_digest="runtime-frozen",
        threshold_report=threshold_report,
        identity=_identity(),
        snapshot_id="development-snapshot",
        projection_id="development-projection",
    )


def _identity() -> DenseComparisonIdentity:
    return DenseComparisonIdentity(
        candidate_id="qwen3-embedding-0.6b-exact-v1",
        model_id="Qwen/Qwen3-Embedding-0.6B",
        model_revision="97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
        adapter_id="exact-cosine-v1",
    )


def _passing_threshold_report():
    return select_dense_threshold(
        (
            _threshold_target("semantic-dev", 0.8, 0.4),
            _threshold_target("multi-dev", 0.7, 0.3),
            _threshold_unanswerable("unanswerable-dev", 0.1),
            _threshold_hard_negative("hard-dev", 0.1),
        )
    )


def _valid_negative_threshold_report():
    return select_dense_threshold(
        (
            _threshold_target("semantic-dev", 0.8, 0.4),
            _threshold_unanswerable("unanswerable-dev", 0.1),
            _threshold_hard_negative("hard-dev", 0.1),
        )
    )


def _threshold_target(query_id: str, score: float, ndcg: float) -> DenseThresholdInput:
    return DenseThresholdInput(
        query_id=query_id,
        category="semantic_paraphrase",
        current_runtime_missed=True,
        recovery_score=score,
        dense_ndcg_at_10=ndcg,
        unanswerable_top_score=None,
        hard_negative_failure_score=None,
    )


def _threshold_unanswerable(query_id: str, score: float) -> DenseThresholdInput:
    return DenseThresholdInput(
        query_id=query_id,
        category="unanswerable",
        current_runtime_missed=False,
        recovery_score=None,
        dense_ndcg_at_10=0.0,
        unanswerable_top_score=score,
        hard_negative_failure_score=None,
    )


def _threshold_hard_negative(query_id: str, score: float) -> DenseThresholdInput:
    return DenseThresholdInput(
        query_id=query_id,
        category="ranking_hard_negative",
        current_runtime_missed=False,
        recovery_score=None,
        dense_ndcg_at_10=0.0,
        unanswerable_top_score=None,
        hard_negative_failure_score=score,
    )


def _holdout(
    observations: tuple[DensePartitionObservation, ...],
) -> DenseHoldoutEvidence:
    return DenseHoldoutEvidence(
        identity=_identity(),
        snapshot_id="holdout-snapshot",
        projection_id="holdout-projection",
        selected_threshold=0.7,
        observations=observations,
    )


def _recovery(
    query_id: str,
    *,
    category: str = "semantic_paraphrase",
) -> DensePartitionObservation:
    return DensePartitionObservation(
        query_id=query_id,
        category=category,
        current_runtime_missed=True,
        recovered_grade2=True,
        unanswerable_no_hit=None,
        hard_negative_failure=None,
    )


def _unanswerable(query_id: str, *, no_hit: bool) -> DensePartitionObservation:
    return DensePartitionObservation(
        query_id=query_id,
        category="unanswerable",
        current_runtime_missed=False,
        recovered_grade2=False,
        unanswerable_no_hit=no_hit,
        hard_negative_failure=None,
    )


def _hard_negative(query_id: str, *, failed: bool) -> DensePartitionObservation:
    return DensePartitionObservation(
        query_id=query_id,
        category="ranking_hard_negative",
        current_runtime_missed=False,
        recovered_grade2=False,
        unanswerable_no_hit=None,
        hard_negative_failure=failed,
    )
