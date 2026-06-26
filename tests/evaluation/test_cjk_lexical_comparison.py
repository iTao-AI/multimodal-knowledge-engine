from dataclasses import replace
from pathlib import Path

import pytest

from mke.evaluation.chinese_runner import run_chinese_retrieval_evaluation
from mke.evaluation.cjk_lexical_comparison import (
    CJK_LEXICAL_GATE_THRESHOLDS,
    CjkLexicalComparisonReport,
    run_cjk_lexical_comparison,
)

PROTOCOL = Path("tests/fixtures/retrieval-chinese-v1/protocol.json")


@pytest.fixture(scope="module")
def comparison_report() -> CjkLexicalComparisonReport:
    return run_cjk_lexical_comparison(PROTOCOL)


def test_runner_preserves_current_chinese_baseline_payload(
    comparison_report: CjkLexicalComparisonReport,
) -> None:
    baseline = run_chinese_retrieval_evaluation(PROTOCOL)

    assert comparison_report.integrity_status == "passed"
    assert comparison_report.current_results == baseline.results
    assert comparison_report.current_metrics == baseline.metrics


def test_candidate_is_not_used_when_current_compiled_query_is_non_empty(
    comparison_report: CjkLexicalComparisonReport,
) -> None:
    non_empty = tuple(
        item
        for item in comparison_report.query_observations
        if not item.current_compiled_query_empty
    )

    assert non_empty
    assert all(not item.candidate_used for item in non_empty)
    assert all(
        item.candidate_retrieved_locators == item.current_retrieved_locators
        for item in non_empty
    )


def test_compiled_empty_query_uses_trigram_overlap_projection(
    comparison_report: CjkLexicalComparisonReport,
) -> None:
    fallback = tuple(
        item for item in comparison_report.query_observations if item.candidate_used
    )

    assert fallback
    assert all(item.current_compiled_query_empty for item in fallback)
    assert all(item.generated_terms for item in fallback)
    assert all(
        item.projection_pool_row_count >= len(item.candidate_retrieved_locators)
        for item in fallback
    )
    assert comparison_report.projection.tokenizer == "trigram"
    assert comparison_report.projection.row_count == 70


def test_development_gate_failure_records_failed_candidate_status() -> None:
    impossible = replace(
        CJK_LEXICAL_GATE_THRESHOLDS,
        development_recall_at_5_minimum=1.1,
    )

    report = run_cjk_lexical_comparison(
        PROTOCOL,
        gate_thresholds=impossible,
    )

    assert report.integrity_status == "passed"
    assert report.candidate_status == "failed"
    assert any(
        gate.gate_id == "development_answerable_recall_at_5"
        and gate.status == "failed"
        for gate in report.development_gates
    )
    assert report.holdout_gates == ()


def test_holdout_cannot_be_observed_before_development_gates_are_frozen() -> None:
    report = run_cjk_lexical_comparison(
        PROTOCOL,
        freeze_development_gates=False,
    )

    assert report.integrity_status == "failed"
    assert report.candidate_status == "failed"
    assert report.integrity_failures[0].problem == "cjk_lexical_holdout_not_frozen"
