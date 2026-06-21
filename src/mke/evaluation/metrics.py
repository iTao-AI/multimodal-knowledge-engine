from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mke.evaluation.manifest import QueryCategory, StableLocator

AskStatus = Literal["evidence_found", "insufficient_evidence"]


@dataclass(frozen=True)
class QueryMetricInput:
    category: QueryCategory
    relevant: tuple[StableLocator, ...]
    retrieved: tuple[StableLocator, ...]
    ask_status: AskStatus


@dataclass(frozen=True)
class MetricValue:
    value: float
    sum: float
    count: int


@dataclass(frozen=True)
class RetrievalMetrics:
    locator_recall_at_1: MetricValue
    locator_recall_at_3: MetricValue
    locator_recall_at_5: MetricValue
    mrr_at_5: MetricValue
    answerable_zero_hit_rate: MetricValue
    unanswerable_no_hit_rate: MetricValue
    ask_refusal_rate: MetricValue


def calculate_metrics(inputs: tuple[QueryMetricInput, ...]) -> RetrievalMetrics:
    answerable = tuple(item for item in inputs if item.category == "answerable")
    unanswerable = tuple(item for item in inputs if item.category != "answerable")
    if not answerable or not unanswerable:
        raise ValueError("metrics require answerable and unanswerable queries")
    for item in inputs:
        search_found = bool(item.retrieved)
        ask_found = item.ask_status == "evidence_found"
        if search_found != ask_found:
            raise ValueError("Search and Ask results disagree")
    if any(not item.relevant for item in answerable):
        raise ValueError("answerable metrics require relevant locators")

    return RetrievalMetrics(
        locator_recall_at_1=_mean(tuple(_recall(item, 1) for item in answerable)),
        locator_recall_at_3=_mean(tuple(_recall(item, 3) for item in answerable)),
        locator_recall_at_5=_mean(tuple(_recall(item, 5) for item in answerable)),
        mrr_at_5=_mean(tuple(_reciprocal_rank(item) for item in answerable)),
        answerable_zero_hit_rate=_mean(
            tuple(float(not item.retrieved) for item in answerable)
        ),
        unanswerable_no_hit_rate=_mean(
            tuple(float(not item.retrieved) for item in unanswerable)
        ),
        ask_refusal_rate=_mean(
            tuple(
                float(item.ask_status == "insufficient_evidence")
                for item in unanswerable
            )
        ),
    )


def _recall(item: QueryMetricInput, limit: int) -> float:
    relevant = set(item.relevant)
    return len(relevant.intersection(item.retrieved[:limit])) / len(relevant)


def _reciprocal_rank(item: QueryMetricInput) -> float:
    relevant = set(item.relevant)
    for index, locator in enumerate(item.retrieved[:5], start=1):
        if locator in relevant:
            return 1.0 / index
    return 0.0


def _mean(values: tuple[float, ...]) -> MetricValue:
    total = sum(values)
    return MetricValue(value=round(total / len(values), 6), sum=total, count=len(values))
