from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from mke.evaluation.manifest import QueryCategory, StableLocator
from mke.evaluation.metrics import AskStatus, MetricValue, RetrievalMetrics

EvaluationStatus = Literal["passed", "failed"]
QualityStatus = Literal["baseline_recorded", "not_recorded"]


@dataclass(frozen=True)
class IntegrityFailure:
    problem: str
    cause: str
    next_step: str
    subject_id: str | None = None


@dataclass(frozen=True)
class QueryEvaluationResult:
    query_id: str
    category: QueryCategory
    relevant_locator_count: int
    retrieved_locators: tuple[StableLocator, ...]
    relevant_retrieved_at_1: int
    relevant_retrieved_at_3: int
    relevant_retrieved_at_5: int
    first_relevant_rank: int | None
    ask_status: AskStatus

    @property
    def retrieved_locator_count(self) -> int:
        return len(self.retrieved_locators)


@dataclass(frozen=True)
class RetrievalEvaluationReport:
    manifest_id: str
    benchmark_scope: str
    quality_gate: Literal["none"]
    status: EvaluationStatus
    quality_status: QualityStatus
    document_count: int
    results: tuple[QueryEvaluationResult, ...]
    metrics: RetrievalMetrics | None
    integrity_failures: tuple[IntegrityFailure, ...]
    duration_ms: int

    @property
    def query_count(self) -> int:
        return len(self.results)

    @property
    def answerable_count(self) -> int:
        return sum(item.category == "answerable" for item in self.results)

    @property
    def unanswerable_count(self) -> int:
        return self.query_count - self.answerable_count


def render_retrieval_json_report(report: RetrievalEvaluationReport) -> str:
    return json.dumps(_payload(report), indent=2, sort_keys=False)


def render_retrieval_human_report(report: RetrievalEvaluationReport) -> str:
    lines = [
        "mke eval retrieval",
        f"scope={report.benchmark_scope} quality_gate={report.quality_gate}",
    ]
    aggregate = (
        f"evaluation=retrieval manifest={report.manifest_id} status={report.status} "
        f"quality_status={report.quality_status} documents={report.document_count} "
        f"queries={report.query_count} answerable={report.answerable_count} "
        f"unanswerable={report.unanswerable_count}"
    )
    if report.metrics is not None:
        metrics = report.metrics
        aggregate += (
            f" locator_recall_at_1={metrics.locator_recall_at_1.value:.6f}"
            f" locator_recall_at_3={metrics.locator_recall_at_3.value:.6f}"
            f" locator_recall_at_5={metrics.locator_recall_at_5.value:.6f}"
            f" mrr_at_5={metrics.mrr_at_5.value:.6f}"
            f" answerable_zero_hit_rate={metrics.answerable_zero_hit_rate.value:.6f}"
            f" unanswerable_no_hit_rate={metrics.unanswerable_no_hit_rate.value:.6f}"
            f" ask_refusal_rate={metrics.ask_refusal_rate.value:.6f}"
        )
    lines.append(aggregate)
    for result in report.results:
        rank = "none" if result.first_relevant_rank is None else str(result.first_relevant_rank)
        locators = ",".join(_human_locator(item) for item in result.retrieved_locators)
        lines.append(
            f"query_id={result.query_id} category={result.category} "
            f"relevant_locator_count={result.relevant_locator_count} "
            f"retrieved_locator_count={result.retrieved_locator_count} "
            f"relevant_retrieved_at_1={result.relevant_retrieved_at_1} "
            f"relevant_retrieved_at_3={result.relevant_retrieved_at_3} "
            f"relevant_retrieved_at_5={result.relevant_retrieved_at_5} "
            f"first_relevant_rank={rank} ask_status={result.ask_status} "
            f"retrieved_locators={locators or 'none'}"
        )
    for failure in report.integrity_failures:
        subject = (
            f" subject_id={failure.subject_id}" if failure.subject_id is not None else ""
        )
        lines.append(
            f"problem={failure.problem} cause={_human_token(failure.cause)} "
            f"next_step={failure.next_step}{subject}"
        )
    return "\n".join(lines)


def _payload(report: RetrievalEvaluationReport) -> dict[str, object]:
    category_counts = {
        category: sum(item.category == category for item in report.results)
        for category in ("answerable", "lexical_confuser", "out_of_corpus")
    }
    return {
        "evaluation": "retrieval",
        "schema_version": "mke.retrieval_eval_report.v1",
        "manifest_id": report.manifest_id,
        "benchmark_scope": report.benchmark_scope,
        "quality_gate": report.quality_gate,
        "status": report.status,
        "quality_status": report.quality_status,
        "documents": report.document_count,
        "queries": report.query_count,
        "answerable": report.answerable_count,
        "unanswerable": report.unanswerable_count,
        "metrics": _metrics_payload(report.metrics),
        "category_counts": category_counts,
        "results": [_result_payload(item) for item in report.results],
        "integrity_failures": [
            {
                "problem": item.problem,
                "cause": item.cause,
                "next_step": item.next_step,
                "subject_id": item.subject_id,
            }
            for item in report.integrity_failures
        ],
        "duration_ms": report.duration_ms,
    }


def _metrics_payload(metrics: RetrievalMetrics | None) -> dict[str, object] | None:
    if metrics is None:
        return None
    return {
        "locator_recall_at_1": _metric_payload(metrics.locator_recall_at_1),
        "locator_recall_at_3": _metric_payload(metrics.locator_recall_at_3),
        "locator_recall_at_5": _metric_payload(metrics.locator_recall_at_5),
        "mrr_at_5": _metric_payload(metrics.mrr_at_5),
        "answerable_zero_hit_rate": _metric_payload(
            metrics.answerable_zero_hit_rate
        ),
        "unanswerable_no_hit_rate": _metric_payload(
            metrics.unanswerable_no_hit_rate
        ),
        "ask_refusal_rate": _metric_payload(metrics.ask_refusal_rate),
    }


def _metric_payload(metric: MetricValue) -> dict[str, object]:
    return {"value": metric.value, "sum": metric.sum, "count": metric.count}


def _result_payload(result: QueryEvaluationResult) -> dict[str, object]:
    return {
        "query_id": result.query_id,
        "category": result.category,
        "relevant_locator_count": result.relevant_locator_count,
        "retrieved_locator_count": result.retrieved_locator_count,
        "relevant_retrieved_at_1": result.relevant_retrieved_at_1,
        "relevant_retrieved_at_3": result.relevant_retrieved_at_3,
        "relevant_retrieved_at_5": result.relevant_retrieved_at_5,
        "first_relevant_rank": result.first_relevant_rank,
        "ask_status": result.ask_status,
        "retrieved_locators": [
            {
                "document_id": item.document_id,
                "locator_kind": item.locator_kind,
                "locator_start": item.locator_start,
                "locator_end": item.locator_end,
            }
            for item in result.retrieved_locators
        ],
    }


def _human_locator(locator: StableLocator) -> str:
    return (
        f"{locator.document_id}:{locator.locator_kind}:"
        f"{locator.locator_start}..{locator.locator_end}"
    )


def _human_token(value: str) -> str:
    return value.replace(" ", "_")
