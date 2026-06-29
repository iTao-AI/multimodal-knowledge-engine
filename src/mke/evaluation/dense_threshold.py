"""Deterministic development-only threshold selection for E3-C."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, cast

from mke.evaluation.chinese_protocol import EXPECTED_CATEGORY_COUNTS

_SCHEMA = "mke.dense_threshold_selection.v1"
_TARGET_CLASSES = frozenset(
    {"semantic_paraphrase", "multi_condition", "ranking_hard_negative"}
)
_SELECTION_RULE = [
    "reject_unanswerable_no_hit_below_0.500000",
    "reject_hard_negative_failure_above_0.300000",
    "maximize_target_grade_2_recovery",
    "tie_break_dense_ndcg_at_10_desc",
    "tie_break_higher_threshold",
]
_INPUT_KEYS = {
    "query_id",
    "category",
    "current_runtime_missed",
    "recovery_score",
    "dense_ndcg_at_10",
    "unanswerable_top_score",
    "hard_negative_failure_score",
    "ranked_scores_and_grades",
    "ideal_grades",
}


class DenseThresholdValidationError(ValueError):
    """Raised when threshold inputs or a selection report are invalid."""


@dataclass(frozen=True)
class DenseThresholdInput:
    query_id: str
    category: str
    current_runtime_missed: bool
    recovery_score: float | None
    dense_ndcg_at_10: float
    unanswerable_top_score: float | None
    hard_negative_failure_score: float | None
    ranked_scores_and_grades: tuple[tuple[float, int], ...] = ()
    ideal_grades: tuple[int, ...] = ()


def dense_threshold_grid() -> list[float]:
    """Return the frozen integer-basis threshold grid without float stepping."""
    return [index / 100 for index in range(101)]


def select_dense_threshold(
    inputs: tuple[DenseThresholdInput, ...],
) -> dict[str, Any]:
    """Select the frozen development threshold without accessing holdout."""
    _validate_inputs(inputs)
    return _build_report(inputs, include_sensitivity=True)


def validate_threshold_report(report: dict[str, Any]) -> None:
    """Fail closed unless the report exactly recomputes from its recorded inputs."""
    if report.get("schema_version") != _SCHEMA:
        raise DenseThresholdValidationError("threshold report schema is invalid")
    raw_inputs: object = report.get("inputs")
    if not isinstance(raw_inputs, list) or not raw_inputs:
        raise DenseThresholdValidationError("threshold report inputs are invalid")
    inputs: list[DenseThresholdInput] = []
    for raw_value in cast(list[object], raw_inputs):
        if not isinstance(raw_value, dict):
            raise DenseThresholdValidationError("threshold report inputs are invalid")
        raw = cast(dict[str, object], raw_value)
        if set(raw) != _INPUT_KEYS:
            raise DenseThresholdValidationError("threshold report inputs are invalid")
        inputs.append(
            DenseThresholdInput(
                query_id=_required_str(raw["query_id"]),
                category=_required_str(raw["category"]),
                current_runtime_missed=_required_bool(
                    raw["current_runtime_missed"]
                ),
                recovery_score=_optional_float(raw["recovery_score"]),
                dense_ndcg_at_10=_required_float(raw["dense_ndcg_at_10"]),
                unanswerable_top_score=_optional_float(
                    raw["unanswerable_top_score"]
                ),
                hard_negative_failure_score=_optional_float(
                    raw["hard_negative_failure_score"]
                ),
                ranked_scores_and_grades=_ranked_scores(
                    raw["ranked_scores_and_grades"]
                ),
                ideal_grades=_ideal_grades(raw["ideal_grades"]),
            )
        )
    frozen_inputs = tuple(inputs)
    _validate_inputs(frozen_inputs)
    expected = _build_report(frozen_inputs, include_sensitivity=True)
    if report != expected:
        raise DenseThresholdValidationError("threshold report content drift")


def _build_report(
    inputs: tuple[DenseThresholdInput, ...],
    *,
    include_sensitivity: bool,
) -> dict[str, Any]:
    trace = [_evaluate_threshold(inputs, threshold) for threshold in dense_threshold_grid()]
    eligible = [item for item in trace if not item["rejection_reasons"]]
    ranked = sorted(
        eligible,
        key=lambda item: (
            -cast(int, item["recovered_target_grade2_count"]),
            -cast(float, item["dense_ndcg_at_10"]),
            -cast(float, item["threshold"]),
        ),
    )
    rank_by_threshold = {
        cast(float, item["threshold"]): rank
        for rank, item in enumerate(ranked, start=1)
    }
    for item in trace:
        item["selection_rank"] = rank_by_threshold.get(
            cast(float, item["threshold"])
        )

    best = ranked[0] if ranked else None
    threshold_selected = (
        best is not None
        and cast(int, best["recovered_target_grade2_count"]) > 0
    )
    development_passed = (
        threshold_selected
        and best is not None
        and cast(int, best["recovered_target_grade2_count"]) >= 2
    )
    selected = dict(best) if threshold_selected and best is not None else None
    intervals = _optimal_intervals(trace, selected)
    report: dict[str, Any] = {
        "schema_version": _SCHEMA,
        "inputs": [_input_payload(item) for item in inputs],
        "selection_rule": list(_SELECTION_RULE),
        "gates": {
            "target_recovery_minimum": 2,
            "unanswerable_no_hit_minimum": 0.5,
            "hard_negative_failure_maximum": 0.3,
        },
        "development_status": "passed" if development_passed else "valid_negative",
        "selected_threshold": selected["threshold"] if selected is not None else None,
        "selected": selected,
        "optimal_threshold_intervals": intervals,
        "threshold_trace": trace,
        "holdout_status": "not_observed",
        "candidate_status": "not_evaluated" if development_passed else "completed",
        "e3d_status": "not_evaluated" if development_passed else "not_eligible",
        "runtime_promotion_status": "not_evaluated",
        "development_leave_one_query_out": [],
    }
    if include_sensitivity:
        report["development_leave_one_query_out"] = [
            _leave_one_out(inputs, omitted_index)
            for omitted_index in range(len(inputs))
        ]
    return report


def _evaluate_threshold(
    inputs: tuple[DenseThresholdInput, ...], threshold: float
) -> dict[str, object]:
    unanswerable = tuple(
        item.unanswerable_top_score
        for item in inputs
        if item.unanswerable_top_score is not None
    )
    hard_negative = tuple(
        item.hard_negative_failure_score
        for item in inputs
        if item.hard_negative_failure_score is not None
    )
    no_hit = _ratio(
        sum(score < threshold for score in unanswerable),
        len(unanswerable),
        1.0,
    )
    hard_failure = _ratio(
        sum(score >= threshold for score in hard_negative),
        len(hard_negative),
        0.0,
    )
    recovered = sorted(
        item.query_id
        for item in inputs
        if item.category in _TARGET_CLASSES
        and item.current_runtime_missed
        and item.recovery_score is not None
        and item.recovery_score >= threshold
    )
    report_only = sorted(
        item.query_id
        for item in inputs
        if item.category == "number_date_unit"
        and item.recovery_score is not None
        and item.recovery_score >= threshold
    )
    answerable = tuple(
        item
        for item in inputs
        if item.recovery_score is not None or item.ranked_scores_and_grades
    )
    dense_ndcg = _ratio(
        sum(
            _threshold_ndcg(item, threshold)
            for item in answerable
        ),
        len(answerable),
        0.0,
    )
    rejection_reasons: list[str] = []
    if no_hit < 0.5:
        rejection_reasons.append("unanswerable_no_hit_below_0.500000")
    if hard_failure > 0.3:
        rejection_reasons.append("hard_negative_failure_above_0.300000")
    return {
        "threshold": threshold,
        "unanswerable_no_hit": no_hit,
        "hard_negative_failure": hard_failure,
        "recovered_target_grade2_count": len(recovered),
        "recovery_ids": recovered,
        "report_only_number_date_recovery_ids": report_only,
        "dense_ndcg_at_10": dense_ndcg,
        "rejection_reasons": rejection_reasons,
        "selection_rank": None,
    }


def _optimal_intervals(
    trace: list[dict[str, object]],
    selected: dict[str, object] | None,
) -> list[dict[str, object]]:
    if selected is None:
        return []
    target_count = selected["recovered_target_grade2_count"]
    target_ndcg = selected["dense_ndcg_at_10"]
    optimal = [
        item
        for item in trace
        if not item["rejection_reasons"]
        and item["recovered_target_grade2_count"] == target_count
        and item["dense_ndcg_at_10"] == target_ndcg
    ]
    intervals: list[dict[str, object]] = []
    start = cast(float, optimal[0]["threshold"])
    previous = start
    for item in optimal[1:]:
        current = cast(float, item["threshold"])
        if round(current - previous, 2) != 0.01:
            intervals.append(_interval(start, previous, target_count, target_ndcg))
            start = current
        previous = current
    intervals.append(_interval(start, previous, target_count, target_ndcg))
    return intervals


def _interval(
    start: float,
    end: float,
    recovered_count: object,
    dense_ndcg: object,
) -> dict[str, object]:
    return {
        "start": start,
        "end": end,
        "recovered_target_grade2_count": recovered_count,
        "dense_ndcg_at_10": dense_ndcg,
    }


def _leave_one_out(
    inputs: tuple[DenseThresholdInput, ...], omitted_index: int
) -> dict[str, object]:
    reduced = inputs[:omitted_index] + inputs[omitted_index + 1 :]
    if not reduced:
        return {
            "query_id": inputs[omitted_index].query_id,
            "development_status": "valid_negative",
            "selected_threshold": None,
            "recovered_target_grade2_count": 0,
        }
    result = _build_report(reduced, include_sensitivity=False)
    selected = result["selected"]
    return {
        "query_id": inputs[omitted_index].query_id,
        "development_status": result["development_status"],
        "selected_threshold": result["selected_threshold"],
        "recovered_target_grade2_count": (
            cast(dict[str, object], selected)["recovered_target_grade2_count"]
            if selected is not None
            else 0
        ),
    }


def _validate_inputs(inputs: tuple[DenseThresholdInput, ...]) -> None:
    if not inputs:
        raise DenseThresholdValidationError("threshold inputs are empty")
    seen: set[str] = set()
    for item in inputs:
        if not item.query_id or item.query_id in seen:
            raise DenseThresholdValidationError("threshold query identity is invalid")
        seen.add(item.query_id)
        if item.category not in EXPECTED_CATEGORY_COUNTS:
            raise DenseThresholdValidationError("threshold category is invalid")
        if type(item.current_runtime_missed) is not bool:
            raise DenseThresholdValidationError("runtime miss flag is invalid")
        _validate_score(item.recovery_score, "recovery score", optional=True)
        _validate_score(
            item.dense_ndcg_at_10,
            "dense nDCG@10",
            optional=False,
            minimum=0.0,
        )
        _validate_score(
            item.unanswerable_top_score, "unanswerable top score", optional=True
        )
        _validate_score(
            item.hard_negative_failure_score,
            "hard-negative failure score",
            optional=True,
        )
        _validate_ranked_evidence(item)
        if (
            item.category in _TARGET_CLASSES
            and item.recovery_score is not None
            and item.current_runtime_missed is not True
        ):
            raise DenseThresholdValidationError(
                "target recovery must be a current-runtime miss"
            )
        if item.category == "unanswerable" and (
            item.unanswerable_top_score is None
            or item.recovery_score is not None
            or item.current_runtime_missed
        ):
            raise DenseThresholdValidationError("unanswerable input is invalid")


def _validate_score(
    value: object,
    label: str,
    *,
    optional: bool,
    minimum: float = -1.0,
) -> None:
    if value is None and optional:
        return
    if (
        type(value) is not float
        or not math.isfinite(value)
        or not minimum <= value <= 1.0
    ):
        raise DenseThresholdValidationError(f"{label} is invalid")


def _ratio(numerator: int | float, denominator: int, empty: float) -> float:
    if denominator == 0:
        return empty
    return round(numerator / denominator, 6)


def _required_str(value: object) -> str:
    if not isinstance(value, str):
        raise DenseThresholdValidationError("threshold report inputs are invalid")
    return value


def _required_bool(value: object) -> bool:
    if type(value) is not bool:
        raise DenseThresholdValidationError("threshold report inputs are invalid")
    return value


def _required_float(value: object) -> float:
    if type(value) is not float:
        raise DenseThresholdValidationError("threshold report inputs are invalid")
    return value


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if type(value) is not float or not math.isfinite(value) or not -1.0 <= value <= 1.0:
        raise DenseThresholdValidationError("threshold report inputs are invalid")
    return value


def _ranked_scores(value: object) -> tuple[tuple[float, int], ...]:
    if not isinstance(value, list):
        raise DenseThresholdValidationError("ranked score evidence is invalid")
    result: list[tuple[float, int]] = []
    for raw in cast(list[object], value):
        if not isinstance(raw, list):
            raise DenseThresholdValidationError("ranked score evidence is invalid")
        pair = cast(list[object], raw)
        if len(pair) != 2:
            raise DenseThresholdValidationError("ranked score evidence is invalid")
        score, grade = pair
        if type(score) is not float or type(grade) is not int:
            raise DenseThresholdValidationError("ranked score evidence is invalid")
        result.append((score, grade))
    return tuple(result)


def _ideal_grades(value: object) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise DenseThresholdValidationError("ideal grade evidence is invalid")
    grades = cast(list[object], value)
    if any(type(item) is not int for item in grades):
        raise DenseThresholdValidationError("ideal grade evidence is invalid")
    return tuple(cast(list[int], grades))


def _input_payload(item: DenseThresholdInput) -> dict[str, object]:
    return {
        "query_id": item.query_id,
        "category": item.category,
        "current_runtime_missed": item.current_runtime_missed,
        "recovery_score": item.recovery_score,
        "dense_ndcg_at_10": item.dense_ndcg_at_10,
        "unanswerable_top_score": item.unanswerable_top_score,
        "hard_negative_failure_score": item.hard_negative_failure_score,
        "ranked_scores_and_grades": [
            [score, grade] for score, grade in item.ranked_scores_and_grades
        ],
        "ideal_grades": list(item.ideal_grades),
    }


def _validate_ranked_evidence(item: DenseThresholdInput) -> None:
    if len(item.ranked_scores_and_grades) > 10:
        raise DenseThresholdValidationError("ranked score evidence is invalid")
    previous = 1.0
    for score, grade in item.ranked_scores_and_grades:
        _validate_score(score, "ranked score", optional=False)
        if type(grade) is not int or grade not in {0, 1, 2} or score > previous:
            raise DenseThresholdValidationError("ranked score evidence is invalid")
        previous = score
    if any(type(grade) is not int or grade not in {0, 1, 2} for grade in item.ideal_grades):
        raise DenseThresholdValidationError("ideal grade evidence is invalid")
    if item.ranked_scores_and_grades and not item.ideal_grades:
        raise DenseThresholdValidationError("ideal grade evidence is invalid")
    if item.ranked_scores_and_grades:
        grade_two_scores = [
            score for score, grade in item.ranked_scores_and_grades if grade == 2
        ]
        expected_recovery = max(grade_two_scores, default=None)
        if item.recovery_score != expected_recovery:
            raise DenseThresholdValidationError(
                "recovery score evidence is inconsistent"
            )


def _threshold_ndcg(item: DenseThresholdInput, threshold: float) -> float:
    if not item.ranked_scores_and_grades:
        return (
            item.dense_ndcg_at_10
            if item.recovery_score is not None and item.recovery_score >= threshold
            else 0.0
        )
    observed = tuple(
        grade
        for score, grade in item.ranked_scores_and_grades
        if score >= threshold
    )
    ideal = tuple(sorted(item.ideal_grades, reverse=True)[:10])
    ideal_dcg = _dcg(ideal)
    if ideal_dcg == 0.0:
        return 0.0
    return _dcg(observed) / ideal_dcg


def _dcg(grades: tuple[int, ...]) -> float:
    return sum(
        (2**grade - 1) / math.log2(rank + 1)
        for rank, grade in enumerate(grades, start=1)
    )
