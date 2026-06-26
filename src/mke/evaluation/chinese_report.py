from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from mke.evaluation.chinese_diagnostics import MissClassification
from mke.evaluation.chinese_protocol import (
    ChineseQueryCategory,
    ChineseSplit,
    QrelAdjudication,
)
from mke.evaluation.graded_metrics import (
    AskObservationStatus,
    GradedRetrievalMetrics,
    MetricBreakdown,
)
from mke.evaluation.manifest import StableLocator
from mke.evaluation.metrics import MetricValue

E3BReason = Literal[
    "development_compiled_query_empty_miss_observed",
    "no_development_compiled_query_empty_miss",
    "qrel_review_incomplete",
    "evaluation_integrity_failed",
]

CHINESE_RETRIEVAL_LIMITATIONS = (
    "public_holdout_not_blind",
    "small_engineering_corpus",
    "text_layer_pdf_only",
    "page_level_evidence_only",
    "current_ascii_oriented_query_compilation",
    "development_and_holdout_real_documents_cover_different_domains",
    "no_general_chinese_quality_claim",
    "no_dense_hybrid_or_reranker_claim",
)


@dataclass(frozen=True)
class IntegrityFailure:
    problem: str
    cause: str
    next_step: str
    subject_id: str | None = None


@dataclass(frozen=True)
class FtsRankScoreEvidence:
    locator: StableLocator
    rank_score_hex: str
    bm25_score_hex: str


@dataclass(frozen=True)
class FtsRankEvidence:
    query_id: str
    split: ChineseSplit
    result_count: int
    ordered_evidence_ids_sha256: str
    score_pairs_sha256: str
    rank_override_present: bool
    ordered_evidence: tuple[StableLocator, ...]
    score_pairs: tuple[FtsRankScoreEvidence, ...]


@dataclass(frozen=True)
class ChineseQueryResult:
    query_id: str
    split: ChineseSplit
    category: ChineseQueryCategory
    qrel_counts: tuple[int, int, int]
    retrieved_locators: tuple[StableLocator, ...]
    retrieved_grades: tuple[int | None, ...]
    direct_ranks: tuple[int, ...]
    hard_negative_failure: bool
    ask_status: AskObservationStatus
    compiled_query: str
    ascii_token_count: int
    compiled_query_empty: bool
    miss: MissClassification | None


@dataclass(frozen=True)
class E3BDecisionEvidence:
    development_answerable_compiled_query_empty_misses: int
    qrel_review_status: Literal["complete"]
    query_page_judgment_count: int


@dataclass(frozen=True)
class ChineseRetrievalReport:
    protocol_id: str
    benchmark_scope: Literal["small_public_chinese_page_corpus"]
    quality_gate: Literal["none"]
    integrity_status: Literal["passed", "failed"]
    quality_status: Literal["baseline_recorded", "not_recorded"]
    documents: int
    queries: int
    split_counts: Mapping[ChineseSplit, int]
    results: tuple[ChineseQueryResult, ...]
    metrics: GradedRetrievalMetrics | None
    qrel_adjudication: QrelAdjudication
    e3b_decision: Literal["eligible", "not_justified"]
    e3b_evidence: E3BDecisionEvidence
    e3b_reason: E3BReason
    fts5_rank_profile: str | None
    fts5_rank_observations: tuple[FtsRankEvidence, ...]
    integrity_failures: tuple[IntegrityFailure, ...]
    duration_ms: int
    limitations: tuple[str, ...]


def render_chinese_retrieval_human(report: ChineseRetrievalReport) -> str:
    lines = [
        "mke eval retrieval-chinese",
        (
            f"integrity_status={report.integrity_status} "
            f"quality_status={report.quality_status} "
            f"quality_gate={report.quality_gate}"
        ),
        f"e3b_decision={report.e3b_decision} reason={report.e3b_reason}",
        (
            f"documents={report.documents} queries={report.queries} "
            f"development={report.split_counts.get('development', 0)} "
            f"holdout={report.split_counts.get('holdout', 0)} "
            f"duration_ms={report.duration_ms}"
        ),
        (
            f"qrel_review_status={report.qrel_adjudication.review_status} "
            f"reviewed_queries={report.qrel_adjudication.reviewed_query_count} "
            "query_page_judgment_count="
            f"{report.qrel_adjudication.query_page_judgment_count}"
        ),
        f"fts5_rank_profile={report.fts5_rank_profile or 'unavailable'}",
    ]
    if report.metrics is not None:
        lines.append(_human_metric_line("metrics", report.metrics))
        for breakdown in report.metrics.category_metrics:
            lines.append(
                _human_breakdown_line("category", breakdown)
            )
        for breakdown in report.metrics.compiled_query_empty_metrics:
            lines.append(
                _human_breakdown_line("compiled_query_empty", breakdown)
            )
        for breakdown in report.metrics.ascii_token_count_metrics:
            lines.append(
                _human_breakdown_line("ascii_token_count", breakdown)
            )
    for result in report.results:
        lines.append(
            f"query={result.query_id} split={result.split} category={result.category} "
            f"compiled_query_empty={str(result.compiled_query_empty).lower()} "
            f"ascii_token_count={result.ascii_token_count} "
            f"retrieved={len(result.retrieved_locators)} "
            f"ask_status={result.ask_status} "
            f"miss={result.miss.symptom if result.miss is not None else 'none'}"
        )
    for failure in report.integrity_failures:
        subject = (
            f" subject_id={failure.subject_id}" if failure.subject_id is not None else ""
        )
        lines.append(
            f"failure problem={failure.problem} cause={failure.cause} "
            f"next_step={failure.next_step}{subject}"
        )
    lines.extend(f"limitation={item}" for item in report.limitations)
    return "\n".join(lines) + "\n"


def render_chinese_retrieval_json(report: ChineseRetrievalReport) -> str:
    payload = {
        "schema_version": "mke.retrieval_chinese_report.v1",
        "protocol_id": report.protocol_id,
        "benchmark_scope": report.benchmark_scope,
        "quality_gate": report.quality_gate,
        "integrity_status": report.integrity_status,
        "quality_status": report.quality_status,
        "documents": report.documents,
        "queries": report.queries,
        "split_counts": {
            "development": report.split_counts.get("development", 0),
            "holdout": report.split_counts.get("holdout", 0),
        },
        "results": [_query_payload(item) for item in report.results],
        "metrics": _metrics_payload(report.metrics),
        "qrel_adjudication": {
            "sha256": report.qrel_adjudication.sha256,
            "review_status": report.qrel_adjudication.review_status,
            "reviewed_query_count": report.qrel_adjudication.reviewed_query_count,
            "query_page_judgment_count": (
                report.qrel_adjudication.query_page_judgment_count
            ),
        },
        "e3b_decision": report.e3b_decision,
        "e3b_evidence": {
            "development_answerable_compiled_query_empty_misses": (
                report.e3b_evidence.development_answerable_compiled_query_empty_misses
            ),
            "qrel_review_status": report.e3b_evidence.qrel_review_status,
            "query_page_judgment_count": (
                report.e3b_evidence.query_page_judgment_count
            ),
        },
        "e3b_reason": report.e3b_reason,
        "fts5_rank_profile": report.fts5_rank_profile,
        "fts5_rank_observations": [
            {
                "query_id": item.query_id,
                "split": item.split,
                "result_count": item.result_count,
                "ordered_evidence_ids_sha256": item.ordered_evidence_ids_sha256,
                "score_pairs_sha256": item.score_pairs_sha256,
                "rank_override_present": item.rank_override_present,
                "ordered_evidence": [
                    _locator_payload(locator)
                    for locator in item.ordered_evidence
                ],
                "score_pairs": [
                    {
                        "locator": _locator_payload(pair.locator),
                        "rank_score_hex": pair.rank_score_hex,
                        "bm25_score_hex": pair.bm25_score_hex,
                    }
                    for pair in item.score_pairs
                ],
            }
            for item in report.fts5_rank_observations
        ],
        "integrity_failures": [
            _failure_payload(item) for item in report.integrity_failures
        ],
        "duration_ms": report.duration_ms,
        "limitations": list(report.limitations),
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ) + "\n"


def _failure_payload(failure: IntegrityFailure) -> dict[str, object]:
    payload: dict[str, object] = {
        "problem": failure.problem,
        "cause": failure.cause,
        "next_step": failure.next_step,
    }
    if failure.subject_id is not None:
        payload["subject_id"] = failure.subject_id
    return payload


def _query_payload(result: ChineseQueryResult) -> dict[str, object]:
    return {
        "query_id": result.query_id,
        "split": result.split,
        "category": result.category,
        "qrel_counts": {
            "grade_0": result.qrel_counts[0],
            "grade_1": result.qrel_counts[1],
            "grade_2": result.qrel_counts[2],
        },
        "retrieved": [
            {
                "locator": _locator_payload(locator),
                "grade": grade,
            }
            for locator, grade in zip(
                result.retrieved_locators, result.retrieved_grades, strict=True
            )
        ],
        "direct_ranks": list(result.direct_ranks),
        "hard_negative_failure": result.hard_negative_failure,
        "ask_status": result.ask_status,
        "compiled_query": result.compiled_query,
        "ascii_token_count": result.ascii_token_count,
        "compiled_query_empty": result.compiled_query_empty,
        "miss": _miss_payload(result.miss),
    }


def _miss_payload(miss: MissClassification | None) -> dict[str, object] | None:
    if miss is None:
        return None
    return {
        "symptom": miss.symptom,
        "compiled_query": miss.compiled_query,
        "ascii_token_count": miss.ascii_token_count,
        "compiled_query_empty": miss.compiled_query_empty,
        "direct_locators": [
            _locator_payload(locator) for locator in miss.direct_locators
        ],
        "returned_direct_ranks": list(miss.returned_direct_ranks),
        "returned_distractor_ranks": list(miss.returned_distractor_ranks),
        "direct_page_clause_coverage": [
            list(page) for page in miss.direct_page_clause_coverage
        ],
        "observation": miss.observation,
    }


def _locator_payload(locator: StableLocator) -> dict[str, object]:
    return {
        "document_id": locator.document_id,
        "locator_kind": locator.locator_kind,
        "locator_start": locator.locator_start,
        "locator_end": locator.locator_end,
    }


def _metrics_payload(
    metrics: GradedRetrievalMetrics | None,
) -> dict[str, object] | None:
    if metrics is None:
        return None
    return {
        "recall_at_1": _metric_payload(metrics.recall_at_1),
        "recall_at_3": _metric_payload(metrics.recall_at_3),
        "recall_at_5": _metric_payload(metrics.recall_at_5),
        "mrr_at_5": _metric_payload(metrics.mrr_at_5),
        "ndcg_at_5": _metric_payload(metrics.ndcg_at_5),
        "ndcg_at_10": _metric_payload(metrics.ndcg_at_10),
        "answerable_zero_hit_rate": _metric_payload(
            metrics.answerable_zero_hit_rate
        ),
        "hard_negative_failure_rate": _metric_payload(
            metrics.hard_negative_failure_rate
        ),
        "unanswerable_no_hit_rate": _metric_payload(
            metrics.unanswerable_no_hit_rate
        ),
        "ask_input_rejection_rate": _metric_payload(
            metrics.ask_input_rejection_rate
        ),
        "ask_insufficient_evidence_rate": _metric_payload(
            metrics.ask_insufficient_evidence_rate
        ),
        "ask_evidence_found_rate": _metric_payload(
            metrics.ask_evidence_found_rate
        ),
        "category_metrics": [
            _breakdown_payload(item) for item in metrics.category_metrics
        ],
        "compiled_query_empty_metrics": [
            _breakdown_payload(item)
            for item in metrics.compiled_query_empty_metrics
        ],
        "ascii_token_count_metrics": [
            _breakdown_payload(item) for item in metrics.ascii_token_count_metrics
        ],
    }


def _breakdown_payload(item: MetricBreakdown) -> dict[str, object]:
    return {
        "label": item.label,
        "query_count": item.query_count,
        "recall_at_1": _metric_payload(item.recall_at_1),
        "recall_at_3": _metric_payload(item.recall_at_3),
        "recall_at_5": _metric_payload(item.recall_at_5),
        "mrr_at_5": _metric_payload(item.mrr_at_5),
        "ndcg_at_5": _metric_payload(item.ndcg_at_5),
        "ndcg_at_10": _metric_payload(item.ndcg_at_10),
        "answerable_zero_hit_rate": _metric_payload(
            item.answerable_zero_hit_rate
        ),
        "hard_negative_failure_rate": _metric_payload(
            item.hard_negative_failure_rate
        ),
        "unanswerable_no_hit_rate": _metric_payload(
            item.unanswerable_no_hit_rate
        ),
        "ask_input_rejection_rate": _metric_payload(
            item.ask_input_rejection_rate
        ),
        "ask_insufficient_evidence_rate": _metric_payload(
            item.ask_insufficient_evidence_rate
        ),
        "ask_evidence_found_rate": _metric_payload(item.ask_evidence_found_rate),
    }


def _metric_payload(metric: MetricValue) -> dict[str, object]:
    return {
        "value": metric.value,
        "sum": metric.sum,
        "count": metric.count,
    }


def _human_metric_line(
    prefix: str, metrics: GradedRetrievalMetrics
) -> str:
    return (
        f"{prefix} recall_at_1={metrics.recall_at_1.value:.6f} "
        f"recall_at_3={metrics.recall_at_3.value:.6f} "
        f"recall_at_5={metrics.recall_at_5.value:.6f} "
        f"mrr_at_5={metrics.mrr_at_5.value:.6f} "
        f"ndcg_at_5={metrics.ndcg_at_5.value:.6f} "
        f"ndcg_at_10={metrics.ndcg_at_10.value:.6f}"
    )


def _human_breakdown_line(kind: str, item: MetricBreakdown) -> str:
    return (
        f"{kind}={item.label} queries={item.query_count} "
        f"recall_at_5={item.recall_at_5.value:.6f} "
        f"ndcg_at_10={item.ndcg_at_10.value:.6f} "
        f"answerable_zero_hit_rate={item.answerable_zero_hit_rate.value:.6f}"
    )
