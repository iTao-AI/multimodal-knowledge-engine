from dataclasses import replace

import pytest

from mke.retrieval.mixed_cjk_fts_intent import (
    MIXED_CJK_FTS_INTENT_PARAMETERS,
    MixedCjkCandidate,
    MixedCjkFtsIntentError,
    compile_mixed_cjk_query,
    select_mixed_cjk_candidates,
)


def test_query_comparison_normalizes_compatibility_characters_and_whitespace() -> None:
    query = compile_mixed_cjk_query("anchor ⽅ 便处理")

    assert query.has_cjk is True
    assert query.comparison_query == "anchor方便处理"
    assert query.terms == ("方便处", "便处理")


def test_query_normalization_expansion_is_bounded_and_yields_trigrams() -> None:
    expanded = compile_mixed_cjk_query("anchor ㍿")

    assert expanded.comparison_query == "anchor株式会社"
    assert expanded.terms == ("株式会", "式会社")

    with pytest.raises(MixedCjkFtsIntentError) as raised:
        compile_mixed_cjk_query("anchor " + "㍿" * 130)

    assert raised.value.problem == "mixed_cjk_query_budget_exceeded"


def test_query_and_derived_term_budgets_fail_closed() -> None:
    query_characters = "".join(chr(0x4E00 + index) for index in range(131))
    with pytest.raises(MixedCjkFtsIntentError) as raised:
        compile_mixed_cjk_query("anchor " + query_characters)
    assert raised.value.problem == "mixed_cjk_query_budget_exceeded"

    short_query_parameters = replace(
        MIXED_CJK_FTS_INTENT_PARAMETERS,
        max_query_chars=3,
    )
    with pytest.raises(MixedCjkFtsIntentError):
        compile_mixed_cjk_query("账户余额", parameters=short_query_parameters)

    assert compile_mixed_cjk_query("anchor " + "ascii " * 100).has_cjk is False


def test_selector_applies_overlap_threshold_order_and_result_cap() -> None:
    terms = ("账户余", "户余额", "余额调", "额调整")
    candidates = tuple(
        MixedCjkCandidate(
            evidence_id=f"ev_{index}",
            publication_id="pub",
            source_id="source",
            content_fingerprint="sha256:" + "a" * 64,
            locator_kind="page",
            locator_start=index,
            locator_end=index,
            text=text,
            fts_order=index,
        )
        for index, text in enumerate(
            (
                "账户余额调整",
                "账户余额",
                "无关页面",
            ),
            start=1,
        )
    )
    parameters = replace(
        MIXED_CJK_FTS_INTENT_PARAMETERS,
        max_results=1,
    )

    selection = select_mixed_cjk_candidates(
        candidates,
        terms,
        parameters=parameters,
    )

    assert [result.locator_start for result in selection.results] == [1]
    assert selection.eligible_count == 2
    assert selection.discarded_by_strategy_cap is True


def test_selector_reports_candidate_pool_overflow_as_typed_failure() -> None:
    candidates = tuple(
        MixedCjkCandidate(
            evidence_id=f"ev_{index}",
            publication_id="pub",
            source_id=f"source_{index}",
            content_fingerprint="sha256:" + f"{index:064x}",
            locator_kind="page",
            locator_start=1,
            locator_end=1,
            text="账户余额调整",
            fts_order=index,
        )
        for index in range(2)
    )
    parameters = replace(
        MIXED_CJK_FTS_INTENT_PARAMETERS,
        max_candidate_pool=1,
    )

    with pytest.raises(MixedCjkFtsIntentError) as raised:
        select_mixed_cjk_candidates(
            candidates,
            ("账户余", "户余额", "余额调", "额调整"),
            parameters=parameters,
        )

    assert raised.value.problem == "mixed_cjk_candidate_pool_exceeded"
