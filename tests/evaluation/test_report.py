import json

from mke.evaluation.manifest import StableLocator
from mke.evaluation.metrics import MetricValue, RetrievalMetrics
from mke.evaluation.report import (
    IntegrityFailure,
    QueryEvaluationResult,
    RetrievalEvaluationReport,
    render_retrieval_human_report,
    render_retrieval_json_report,
)


def _metrics() -> RetrievalMetrics:
    value = MetricValue(value=0.5, sum=1.0, count=2)
    return RetrievalMetrics(value, value, value, value, value, value, value)


def _passed_report() -> RetrievalEvaluationReport:
    return RetrievalEvaluationReport(
        manifest_id="retrieval-eval-v1",
        benchmark_scope="small_english_page_timestamp_corpus",
        quality_gate="none",
        status="passed",
        quality_status="baseline_recorded",
        document_count=3,
        results=(
            QueryEvaluationResult(
                query_id="volcano-answerable-01",
                category="answerable",
                relevant_locator_count=1,
                retrieved_locators=(
                    StableLocator("usgs-volcano-hazards", "page", 1, 1),
                ),
                relevant_retrieved_at_1=1,
                relevant_retrieved_at_3=1,
                relevant_retrieved_at_5=1,
                first_relevant_rank=1,
                ask_status="evidence_found",
            ),
            QueryEvaluationResult(
                query_id="out-of-corpus-01",
                category="out_of_corpus",
                relevant_locator_count=0,
                retrieved_locators=(),
                relevant_retrieved_at_1=0,
                relevant_retrieved_at_3=0,
                relevant_retrieved_at_5=0,
                first_relevant_rank=None,
                ask_status="insufficient_evidence",
            ),
        ),
        metrics=_metrics(),
        integrity_failures=(),
        duration_ms=10,
    )


def test_json_report_is_public_safe_and_complete() -> None:
    rendered = render_retrieval_json_report(_passed_report())
    payload = json.loads(rendered)

    assert payload["evaluation"] == "retrieval"
    assert payload["schema_version"] == "mke.retrieval_eval_report.v1"
    assert payload["quality_status"] == "baseline_recorded"
    assert payload["documents"] == 3
    assert payload["queries"] == 2
    assert payload["answerable"] == 1
    assert payload["unanswerable"] == 1
    assert payload["category_counts"] == {
        "answerable": 1,
        "lexical_confuser": 0,
        "out_of_corpus": 1,
    }
    assert payload["metrics"]["locator_recall_at_1"] == {
        "value": 0.5,
        "sum": 1.0,
        "count": 2,
    }
    assert payload["results"][0]["query_id"] == "volcano-answerable-01"
    assert payload["results"][0]["retrieved_locator_count"] == 1
    assert "query" not in payload["results"][0]
    assert "/Users/" not in rendered
    assert "eruption clouds aviation" not in rendered
    assert "evidence_id" not in rendered
    assert "Traceback" not in rendered


def test_human_report_contains_scope_aggregate_and_bounded_query_lines() -> None:
    rendered = render_retrieval_human_report(_passed_report())

    lines = rendered.splitlines()
    assert lines[0] == "mke eval retrieval"
    assert lines[1] == (
        "scope=small_english_page_timestamp_corpus quality_gate=none"
    )
    aggregate = lines[2]
    for field in (
        "evaluation=retrieval",
        "manifest=retrieval-eval-v1",
        "status=passed",
        "quality_status=baseline_recorded",
        "documents=3",
        "queries=2",
        "answerable=1",
        "unanswerable=1",
        "locator_recall_at_1=0.500000",
        "locator_recall_at_3=0.500000",
        "locator_recall_at_5=0.500000",
        "mrr_at_5=0.500000",
        "answerable_zero_hit_rate=0.500000",
        "unanswerable_no_hit_rate=0.500000",
        "ask_refusal_rate=0.500000",
    ):
        assert field in aggregate
    assert (
        "query_id=volcano-answerable-01 category=answerable "
        "relevant_locator_count=1 retrieved_locator_count=1 "
        "relevant_retrieved_at_1=1 relevant_retrieved_at_3=1 "
        "relevant_retrieved_at_5=1 first_relevant_rank=1 "
        "ask_status=evidence_found "
        "retrieved_locators=usgs-volcano-hazards:page:1..1"
    ) in lines
    assert "eruption clouds aviation" not in rendered


def test_failed_report_includes_only_stable_failure_fields() -> None:
    report = RetrievalEvaluationReport(
        manifest_id="unknown",
        benchmark_scope="small_english_page_timestamp_corpus",
        quality_gate="none",
        status="failed",
        quality_status="not_recorded",
        document_count=0,
        results=(),
        metrics=None,
        integrity_failures=(
            IntegrityFailure(
                problem="retrieval_eval_manifest_invalid",
                cause="manifest file is missing",
                next_step="fix_retrieval_eval_manifest",
                subject_id="manifest-one",
            ),
        ),
        duration_ms=2,
    )

    human = render_retrieval_human_report(report)
    payload = json.loads(render_retrieval_json_report(report))

    assert "locator_recall_at_1" not in human
    assert payload["metrics"] is None
    assert payload["integrity_failures"] == [
        {
            "problem": "retrieval_eval_manifest_invalid",
            "cause": "manifest file is missing",
            "next_step": "fix_retrieval_eval_manifest",
            "subject_id": "manifest-one",
        }
    ]
    assert (
        "problem=retrieval_eval_manifest_invalid cause=manifest_file_is_missing "
        "next_step=fix_retrieval_eval_manifest subject_id=manifest-one"
    ) in human
