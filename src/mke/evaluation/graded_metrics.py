from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from mke.evaluation.chinese_protocol import (
    EXPECTED_CATEGORY_COUNTS,
    ChineseQueryCategory,
    GradedQrel,
)
from mke.evaluation.manifest import StableLocator
from mke.evaluation.metrics import MetricValue

AskObservationStatus = Literal[
    "evidence_found",
    "insufficient_evidence",
    "invalid_question",
]


@dataclass(frozen=True)
class GradedQueryMetricInput:
    query_id: str
    category: ChineseQueryCategory
    qrels: tuple[GradedQrel, ...]
    retrieved: tuple[StableLocator, ...]
    ask_status: AskObservationStatus
    compiled_query_empty: bool
    ascii_token_count: int


@dataclass(frozen=True)
class MetricBreakdown:
    label: str
    query_count: int
    recall_at_1: MetricValue
    recall_at_3: MetricValue
    recall_at_5: MetricValue
    mrr_at_5: MetricValue
    ndcg_at_5: MetricValue
    ndcg_at_10: MetricValue
    answerable_zero_hit_rate: MetricValue
    hard_negative_failure_rate: MetricValue
    unanswerable_no_hit_rate: MetricValue
    ask_input_rejection_rate: MetricValue
    ask_insufficient_evidence_rate: MetricValue
    ask_evidence_found_rate: MetricValue


@dataclass(frozen=True)
class GradedRetrievalMetrics:
    recall_at_1: MetricValue
    recall_at_3: MetricValue
    recall_at_5: MetricValue
    mrr_at_5: MetricValue
    ndcg_at_5: MetricValue
    ndcg_at_10: MetricValue
    answerable_zero_hit_rate: MetricValue
    hard_negative_failure_rate: MetricValue
    unanswerable_no_hit_rate: MetricValue
    ask_input_rejection_rate: MetricValue
    ask_insufficient_evidence_rate: MetricValue
    ask_evidence_found_rate: MetricValue
    category_metrics: tuple[MetricBreakdown, ...]
    compiled_query_empty_metrics: tuple[MetricBreakdown, ...]
    ascii_token_count_metrics: tuple[MetricBreakdown, ...]


def calculate_graded_metrics(
    inputs: tuple[GradedQueryMetricInput, ...],
) -> GradedRetrievalMetrics:
    for item in inputs:
        _validate_input(item)
    overall = _breakdown("all", inputs)
    return GradedRetrievalMetrics(
        recall_at_1=overall.recall_at_1,
        recall_at_3=overall.recall_at_3,
        recall_at_5=overall.recall_at_5,
        mrr_at_5=overall.mrr_at_5,
        ndcg_at_5=overall.ndcg_at_5,
        ndcg_at_10=overall.ndcg_at_10,
        answerable_zero_hit_rate=overall.answerable_zero_hit_rate,
        hard_negative_failure_rate=overall.hard_negative_failure_rate,
        unanswerable_no_hit_rate=overall.unanswerable_no_hit_rate,
        ask_input_rejection_rate=overall.ask_input_rejection_rate,
        ask_insufficient_evidence_rate=overall.ask_insufficient_evidence_rate,
        ask_evidence_found_rate=overall.ask_evidence_found_rate,
        category_metrics=tuple(
            _breakdown(
                category,
                tuple(item for item in inputs if item.category == category),
            )
            for category in EXPECTED_CATEGORY_COUNTS
        ),
        compiled_query_empty_metrics=(
            _breakdown(
                "false",
                tuple(item for item in inputs if not item.compiled_query_empty),
            ),
            _breakdown(
                "true",
                tuple(item for item in inputs if item.compiled_query_empty),
            ),
        ),
        ascii_token_count_metrics=(
            _breakdown(
                "0",
                tuple(item for item in inputs if item.ascii_token_count == 0),
            ),
            _breakdown(
                "1",
                tuple(item for item in inputs if item.ascii_token_count == 1),
            ),
            _breakdown(
                "2_plus",
                tuple(item for item in inputs if item.ascii_token_count >= 2),
            ),
        ),
    )


def _validate_input(item: GradedQueryMetricInput) -> None:
    if len(set(item.retrieved)) != len(item.retrieved):
        raise ValueError("retrieved locators must be unique")
    if item.ask_status not in {
        "evidence_found",
        "insufficient_evidence",
        "invalid_question",
    }:
        raise ValueError("Ask status is invalid")
    if type(item.compiled_query_empty) is not bool:
        raise ValueError("compiled-query flag is invalid")
    if (
        type(item.ascii_token_count) is not int
        or item.ascii_token_count < 0
    ):
        raise ValueError("ASCII token count is invalid")
    if item.category == "unanswerable":
        if item.qrels:
            raise ValueError("unanswerable metric input must not have qrels")
    elif not any(qrel.grade == 2 for qrel in item.qrels):
        raise ValueError("answerable metric input requires grade 2")
    if len({qrel.locator for qrel in item.qrels}) != len(item.qrels):
        raise ValueError("qrel locators must be unique")


def _breakdown(
    label: str, inputs: tuple[GradedQueryMetricInput, ...]
) -> MetricBreakdown:
    answerable = tuple(item for item in inputs if item.category != "unanswerable")
    unanswerable = tuple(item for item in inputs if item.category == "unanswerable")
    hard_negative = tuple(
        item for item in answerable if any(qrel.grade == 0 for qrel in item.qrels)
    )
    return MetricBreakdown(
        label=label,
        query_count=len(inputs),
        recall_at_1=_mean(tuple(_recall(item, 1) for item in answerable)),
        recall_at_3=_mean(tuple(_recall(item, 3) for item in answerable)),
        recall_at_5=_mean(tuple(_recall(item, 5) for item in answerable)),
        mrr_at_5=_mean(tuple(_reciprocal_rank(item) for item in answerable)),
        ndcg_at_5=_mean(tuple(_ndcg(item, 5) for item in answerable)),
        ndcg_at_10=_mean(tuple(_ndcg(item, 10) for item in answerable)),
        answerable_zero_hit_rate=_mean(
            tuple(float(not _returned_grade_two(item, 10)) for item in answerable)
        ),
        hard_negative_failure_rate=_mean(
            tuple(float(_hard_negative_failure(item)) for item in hard_negative)
        ),
        unanswerable_no_hit_rate=_mean(
            tuple(float(not item.retrieved) for item in unanswerable)
        ),
        ask_input_rejection_rate=_mean(
            tuple(float(item.ask_status == "invalid_question") for item in inputs)
        ),
        ask_insufficient_evidence_rate=_mean(
            tuple(float(item.ask_status == "insufficient_evidence") for item in inputs)
        ),
        ask_evidence_found_rate=_mean(
            tuple(float(item.ask_status == "evidence_found") for item in inputs)
        ),
    )


def _grade_map(item: GradedQueryMetricInput) -> dict[StableLocator, int]:
    return {qrel.locator: qrel.grade for qrel in item.qrels}


def _recall(item: GradedQueryMetricInput, limit: int) -> float:
    direct = {qrel.locator for qrel in item.qrels if qrel.grade == 2}
    returned = set(item.retrieved[:limit])
    return len(direct & returned) / len(direct)


def _reciprocal_rank(item: GradedQueryMetricInput) -> float:
    direct = {qrel.locator for qrel in item.qrels if qrel.grade == 2}
    for rank, locator in enumerate(item.retrieved[:5], start=1):
        if locator in direct:
            return 1.0 / rank
    return 0.0


def _dcg(grades: tuple[int, ...]) -> float:
    return sum(
        (2**grade - 1) / math.log2(rank + 1)
        for rank, grade in enumerate(grades, start=1)
    )


def _ndcg(item: GradedQueryMetricInput, limit: int) -> float:
    grade_by_locator = _grade_map(item)
    observed = tuple(
        grade_by_locator.get(locator, 0) for locator in item.retrieved[:limit]
    )
    ideal = tuple(
        sorted((qrel.grade for qrel in item.qrels), reverse=True)[:limit]
    )
    ideal_dcg = _dcg(ideal)
    return _dcg(observed) / ideal_dcg


def _returned_grade_two(item: GradedQueryMetricInput, limit: int) -> bool:
    direct = {qrel.locator for qrel in item.qrels if qrel.grade == 2}
    return any(locator in direct for locator in item.retrieved[:limit])


def _hard_negative_failure(item: GradedQueryMetricInput) -> bool:
    direct = {qrel.locator for qrel in item.qrels if qrel.grade == 2}
    distractors = {qrel.locator for qrel in item.qrels if qrel.grade == 0}
    direct_ranks = tuple(
        rank
        for rank, locator in enumerate(item.retrieved, start=1)
        if locator in direct
    )
    distractor_ranks = tuple(
        rank
        for rank, locator in enumerate(item.retrieved, start=1)
        if locator in distractors
    )
    if not distractor_ranks:
        return False
    return not direct_ranks or min(distractor_ranks) < min(direct_ranks)


def _mean(values: tuple[float, ...]) -> MetricValue:
    if not values:
        return MetricValue(value=0.0, sum=0.0, count=0)
    total = sum(values)
    return MetricValue(
        value=round(total / len(values), 6),
        sum=total,
        count=len(values),
    )
