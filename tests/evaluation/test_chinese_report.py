import json
from dataclasses import replace
from pathlib import Path

from mke.evaluation.chinese_diagnostics import MissClassification
from mke.evaluation.chinese_protocol import GradedQrel, QrelAdjudication
from mke.evaluation.chinese_report import (
    ChineseQueryResult,
    ChineseRetrievalReport,
    E3BDecisionEvidence,
    FtsRankEvidence,
    IntegrityFailure,
    render_chinese_retrieval_human,
    render_chinese_retrieval_json,
)
from mke.evaluation.graded_metrics import (
    GradedQueryMetricInput,
    calculate_graded_metrics,
)
from mke.evaluation.manifest import StableLocator


def _page(document_id: str, page: int) -> StableLocator:
    return StableLocator(document_id, "page", page, page)


def _report() -> ChineseRetrievalReport:
    direct = _page("document", 1)
    metrics = calculate_graded_metrics(
        (
            GradedQueryMetricInput(
                query_id="zh-dev-exact-01",
                category="chinese_exact_lexical",
                qrels=(GradedQrel(direct, 2),),
                retrieved=(),
                ask_status="invalid_question",
                compiled_query_empty=True,
                ascii_token_count=0,
            ),
            GradedQueryMetricInput(
                query_id="zh-hold-unanswerable-01",
                category="unanswerable",
                qrels=(),
                retrieved=(),
                ask_status="invalid_question",
                compiled_query_empty=True,
                ascii_token_count=0,
            ),
        )
    )
    miss = MissClassification(
        symptom="compiled_query_empty",
        compiled_query="",
        ascii_token_count=0,
        compiled_query_empty=True,
        direct_locators=(direct,),
        returned_direct_ranks=(),
        returned_distractor_ranks=(),
        direct_page_clause_coverage=((),),
        observation="The current query compiler produced no FTS5 MATCH expression.",
    )
    result = ChineseQueryResult(
        query_id="zh-dev-exact-01",
        split="development",
        category="chinese_exact_lexical",
        qrel_counts=(0, 0, 1),
        retrieved_locators=(),
        retrieved_grades=(),
        direct_ranks=(),
        hard_negative_failure=False,
        ask_status="invalid_question",
        compiled_query="",
        ascii_token_count=0,
        compiled_query_empty=True,
        miss=miss,
    )
    return ChineseRetrievalReport(
        protocol_id="retrieval-chinese-v1",
        benchmark_scope="small_public_chinese_page_corpus",
        quality_gate="none",
        integrity_status="passed",
        quality_status="baseline_recorded",
        documents=5,
        queries=48,
        split_counts={"development": 24, "holdout": 24},
        results=(result,),
        metrics=metrics,
        qrel_adjudication=QrelAdjudication(
            path=Path("/private/qrel-adjudication.json"),
            sha256="a" * 64,
            review_status="complete",
            reviewed_query_count=48,
            query_page_judgment_count=1680,
        ),
        e3b_decision="eligible",
        e3b_evidence=E3BDecisionEvidence(
            development_answerable_compiled_query_empty_misses=1,
            qrel_review_status="complete",
            query_page_judgment_count=1680,
        ),
        e3b_reason="development_compiled_query_empty_miss_observed",
        fts5_rank_profile="sqlite_fts5_default_bm25",
        fts5_rank_observations=(
            FtsRankEvidence(
                query_id="zh-dev-exact-02",
                split="development",
                result_count=2,
                ordered_evidence_ids_sha256="b" * 64,
                score_pairs_sha256="c" * 64,
                rank_override_present=False,
            ),
        ),
        integrity_failures=(),
        duration_ms=123,
        limitations=(
            "public_holdout_not_blind",
            "small_engineering_corpus",
            "text_layer_pdf_only",
            "page_level_evidence_only",
            "current_ascii_oriented_query_compilation",
            "development_and_holdout_real_documents_cover_different_domains",
            "no_general_chinese_quality_claim",
            "no_dense_hybrid_or_reranker_claim",
        ),
    )


def test_human_report_locks_decision_first_four_lines() -> None:
    lines = render_chinese_retrieval_human(_report()).splitlines()

    assert lines[:4] == [
        "mke eval retrieval-chinese",
        "integrity_status=passed quality_status=baseline_recorded quality_gate=none",
        (
            "e3b_decision=eligible "
            "reason=development_compiled_query_empty_miss_observed"
        ),
        "documents=5 queries=48 development=24 holdout=24 duration_ms=123",
    ]
    assert any("fts5_rank_profile=sqlite_fts5_default_bm25" in line for line in lines)
    assert any("query_page_judgment_count=1680" in line for line in lines)
    assert any("category=chinese_exact_lexical" in line for line in lines)
    assert "/private/" not in "\n".join(lines)


def test_json_report_has_exact_schema_and_public_safe_payload() -> None:
    rendered = render_chinese_retrieval_json(_report())
    payload = json.loads(rendered)

    assert set(payload) == {
        "schema_version",
        "protocol_id",
        "benchmark_scope",
        "quality_gate",
        "integrity_status",
        "quality_status",
        "documents",
        "queries",
        "split_counts",
        "results",
        "metrics",
        "qrel_adjudication",
        "e3b_decision",
        "e3b_evidence",
        "e3b_reason",
        "fts5_rank_profile",
        "fts5_rank_observations",
        "integrity_failures",
        "duration_ms",
        "limitations",
    }
    assert payload["schema_version"] == "mke.retrieval_chinese_report.v1"
    assert payload["qrel_adjudication"] == {
        "sha256": "a" * 64,
        "review_status": "complete",
        "reviewed_query_count": 48,
        "query_page_judgment_count": 1680,
    }
    assert payload["e3b_evidence"][
        "development_answerable_compiled_query_empty_misses"
    ] == 1
    assert payload["fts5_rank_observations"][0]["result_count"] == 2
    assert payload["results"][0]["miss"]["symptom"] == "compiled_query_empty"
    assert "/private/" not in rendered
    assert "raw Evidence" not in rendered
    assert "which page answers" not in rendered


def test_failed_report_renders_stable_integrity_failure_without_metrics() -> None:
    report = _report()
    failed = replace(
        report,
        integrity_status="failed",
        quality_status="not_recorded",
        metrics=None,
        e3b_decision="not_justified",
        e3b_reason="evaluation_integrity_failed",
        fts5_rank_profile=None,
        fts5_rank_observations=(),
        integrity_failures=(
            IntegrityFailure(
                problem="retrieval_chinese_fixture_invalid",
                cause="Chinese retrieval fixture identity is invalid",
                next_step="verify_fixture_identity",
                subject_id="ub-service-core",
            ),
        ),
    )

    payload = json.loads(render_chinese_retrieval_json(failed))
    human = render_chinese_retrieval_human(failed)

    assert payload["metrics"] is None
    assert payload["integrity_failures"] == [
        {
            "problem": "retrieval_chinese_fixture_invalid",
            "cause": "Chinese retrieval fixture identity is invalid",
            "next_step": "verify_fixture_identity",
            "subject_id": "ub-service-core",
        }
    ]
    assert "Traceback" not in human
    assert "/private/" not in human
