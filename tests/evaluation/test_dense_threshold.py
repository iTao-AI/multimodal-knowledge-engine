from __future__ import annotations

import math
from collections.abc import Callable
from copy import deepcopy
from dataclasses import replace
from typing import Any

import pytest

from mke.evaluation.dense_threshold import (
    DenseThresholdInput,
    DenseThresholdValidationError,
    dense_threshold_grid,
    select_dense_threshold,
    validate_threshold_report,
)

ThresholdMutation = Callable[[dict[str, Any]], None]
_TAMPER_MUTATIONS: tuple[ThresholdMutation, ...] = (
    lambda report: report["threshold_trace"].reverse(),
    lambda report: report["threshold_trace"][0].__setitem__("threshold", True),
    lambda report: report["threshold_trace"][0].__setitem__(
        "unanswerable_no_hit", math.nan
    ),
    lambda report: report["threshold_trace"][0].__setitem__(
        "recovered_target_grade2_count", -1
    ),
    lambda report: report["selected"].__setitem__("recovery_ids", []),
    lambda report: report.__setitem__("candidate_status", "completed"),
)


def test_threshold_grid_is_exact_101_decimal_values() -> None:
    grid = dense_threshold_grid()

    assert len(grid) == 101
    assert grid[0] == 0.0
    assert grid[-1] == 1.0
    assert grid[1] == 0.01
    assert grid[99] == 0.99


def test_threshold_selection_applies_safety_then_recovery_then_tie_breaks() -> None:
    report = select_dense_threshold(
        (
            _target("semantic-a", 0.61, ndcg=0.30),
            _target("multi-b", 0.59, ndcg=0.20),
            _target("hard-c", 0.72, ndcg=0.10),
            _unanswerable("unanswerable-a", top_score=0.59),
            _unanswerable("unanswerable-b", top_score=0.20),
            _hard_negative("hard-negative-a", failure_score=0.61),
            _hard_negative("hard-negative-b", failure_score=0.40),
            _hard_negative("hard-negative-c", failure_score=0.30),
            _hard_negative("hard-negative-d", failure_score=0.20),
        )
    )

    validate_threshold_report(report)
    assert report["development_status"] == "passed"
    assert report["selected_threshold"] == 0.59
    assert report["selected"]["recovered_target_grade2_count"] == 3
    assert report["selected"]["unanswerable_no_hit"] == 0.5
    assert report["selected"]["hard_negative_failure"] == 0.25
    assert report["selected"]["recovery_ids"] == [
        "hard-c",
        "multi-b",
        "semantic-a",
    ]
    assert any(
        "hard_negative_failure_above_0.300000" in item["rejection_reasons"]
        for item in report["threshold_trace"]
        if item["threshold"] == 0.4
    )
    assert any(
        "unanswerable_no_hit_below_0.500000" in item["rejection_reasons"]
        for item in report["threshold_trace"]
        if item["threshold"] == 0.2
    )


def test_threshold_selection_breaks_remaining_ties_with_higher_threshold() -> None:
    report = select_dense_threshold(
        (
            _target("semantic-a", 0.80, ndcg=0.40),
            _target("multi-b", 0.70, ndcg=0.30),
            _unanswerable("unanswerable-a", top_score=0.10),
            _unanswerable("unanswerable-b", top_score=0.20),
            _hard_negative("hard-negative-a", failure_score=0.10),
        )
    )

    assert report["selected_threshold"] == 0.7
    assert report["optimal_threshold_intervals"] == [
        {
            "start": 0.11,
            "end": 0.7,
            "recovered_target_grade2_count": 2,
            "dense_ndcg_at_10": 0.35,
        }
    ]


def test_threshold_report_records_complete_trace_rank_and_sensitivity() -> None:
    inputs = (
        _target("semantic-a", 0.80, ndcg=0.40),
        _target("multi-b", 0.70, ndcg=0.30),
        _unanswerable("unanswerable-a", top_score=0.10),
        _hard_negative("hard-negative-a", failure_score=0.10),
    )

    report = select_dense_threshold(inputs)

    assert len(report["threshold_trace"]) == 101
    assert report["threshold_trace"][0]["threshold"] == 0.0
    assert report["threshold_trace"][-1]["threshold"] == 1.0
    assert all("selection_rank" in item for item in report["threshold_trace"])
    assert all("rejection_reasons" in item for item in report["threshold_trace"])
    assert [item["query_id"] for item in report["development_leave_one_query_out"]] == [
        item.query_id for item in inputs
    ]
    validate_threshold_report(report)


def test_no_eligible_threshold_returns_valid_negative_without_holdout() -> None:
    report = select_dense_threshold(
        (
            _target("semantic-a", 0.90, ndcg=0.30),
            _unanswerable("unanswerable-a", top_score=0.95),
            _hard_negative("hard-negative-a", failure_score=0.95),
        )
    )

    assert report["development_status"] == "valid_negative"
    assert report["selected_threshold"] is None
    assert report["holdout_status"] == "not_observed"
    assert report["candidate_status"] == "completed"
    assert report["e3d_status"] == "not_eligible"
    assert report["runtime_promotion_status"] == "not_evaluated"


def test_number_date_recovery_is_report_only_and_input_tampering_is_rejected() -> None:
    report = select_dense_threshold(
        (
            _target("semantic-a", 0.80, ndcg=0.30),
            replace(_target("number-a", 0.80, ndcg=0.90), category="number_date_unit"),
            _unanswerable("unanswerable-a", top_score=0.10),
            _hard_negative("hard-negative-a", failure_score=0.10),
        )
    )

    assert report["selected"]["recovered_target_grade2_count"] == 1
    assert report["selected"]["report_only_number_date_recovery_ids"] == ["number-a"]

    with pytest.raises(DenseThresholdValidationError):
        select_dense_threshold((replace(_target("bad", 0.5), recovery_score=math.nan),))
    with pytest.raises(DenseThresholdValidationError):
        select_dense_threshold((replace(_target("bad", 0.5), current_runtime_missed=False),))


@pytest.mark.parametrize(
    "mutation",
    _TAMPER_MUTATIONS,
)
def test_threshold_validator_rejects_trace_and_verdict_tampering(
    mutation: ThresholdMutation,
) -> None:
    report = select_dense_threshold(
        (
            _target("semantic-a", 0.80, ndcg=0.40),
            _target("multi-b", 0.70, ndcg=0.30),
            _unanswerable("unanswerable-a", top_score=0.10),
            _hard_negative("hard-negative-a", failure_score=0.10),
        )
    )
    tampered = deepcopy(report)
    mutation(tampered)

    with pytest.raises(DenseThresholdValidationError):
        validate_threshold_report(tampered)


def _target(
    query_id: str,
    score: float,
    *,
    ndcg: float = 0.0,
) -> DenseThresholdInput:
    return DenseThresholdInput(
        query_id=query_id,
        category="semantic_paraphrase",
        current_runtime_missed=True,
        recovery_score=score,
        dense_ndcg_at_10=ndcg,
        unanswerable_top_score=None,
        hard_negative_failure_score=None,
    )


def _unanswerable(query_id: str, *, top_score: float) -> DenseThresholdInput:
    return DenseThresholdInput(
        query_id=query_id,
        category="unanswerable",
        current_runtime_missed=False,
        recovery_score=None,
        dense_ndcg_at_10=0.0,
        unanswerable_top_score=top_score,
        hard_negative_failure_score=None,
    )


def _hard_negative(query_id: str, *, failure_score: float) -> DenseThresholdInput:
    return DenseThresholdInput(
        query_id=query_id,
        category="ranking_hard_negative",
        current_runtime_missed=False,
        recovery_score=None,
        dense_ndcg_at_10=0.0,
        unanswerable_top_score=None,
        hard_negative_failure_score=failure_score,
    )
