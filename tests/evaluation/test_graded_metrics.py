import math

import pytest

from mke.evaluation.chinese_protocol import GradedQrel
from mke.evaluation.graded_metrics import (
    GradedQueryMetricInput,
    calculate_graded_metrics,
)
from mke.evaluation.manifest import StableLocator


def _page(document_id: str, page: int) -> StableLocator:
    return StableLocator(document_id, "page", page, page)


def _qrel(document_id: str, page: int, grade: int) -> GradedQrel:
    return GradedQrel(_page(document_id, page), grade)  # type: ignore[arg-type]


def _input(
    query_id: str,
    *,
    category: str = "chinese_exact_lexical",
    qrels: tuple[GradedQrel, ...] = (_qrel("doc", 1, 2),),
    retrieved: tuple[StableLocator, ...] = (_page("doc", 1),),
    ask_status: str = "evidence_found",
    compiled_query_empty: bool = False,
    ascii_token_count: int = 1,
) -> GradedQueryMetricInput:
    return GradedQueryMetricInput(
        query_id=query_id,
        category=category,  # type: ignore[arg-type]
        qrels=qrels,
        retrieved=retrieved,
        ask_status=ask_status,  # type: ignore[arg-type]
        compiled_query_empty=compiled_query_empty,
        ascii_token_count=ascii_token_count,
    )


def test_metrics_use_grade_two_for_recall_mrr_and_zero_hit() -> None:
    metrics = calculate_graded_metrics(
        (
            _input(
                "q1",
                qrels=(
                    _qrel("doc", 1, 2),
                    _qrel("doc", 2, 2),
                    _qrel("doc", 3, 1),
                ),
                retrieved=(
                    _page("doc", 3),
                    _page("other", 1),
                    _page("doc", 1),
                    _page("doc", 2),
                ),
            ),
            _input(
                "q2",
                qrels=(_qrel("doc", 4, 2),),
                retrieved=(),
                ask_status="insufficient_evidence",
            ),
            _input(
                "q3",
                category="unanswerable",
                qrels=(),
                retrieved=(),
                ask_status="invalid_question",
                compiled_query_empty=True,
                ascii_token_count=0,
            ),
        )
    )

    assert metrics.recall_at_1.value == 0.0
    assert metrics.recall_at_3.value == 0.25
    assert metrics.recall_at_5.value == 0.5
    assert metrics.mrr_at_5.value == 0.166667
    assert metrics.answerable_zero_hit_rate.value == 0.5
    assert metrics.unanswerable_no_hit_rate.value == 1.0


def test_metrics_use_graded_dcg_and_ideal_order() -> None:
    metrics = calculate_graded_metrics(
        (
            _input(
                "q1",
                qrels=(
                    _qrel("doc", 1, 2),
                    _qrel("doc", 2, 1),
                    _qrel("doc", 3, 0),
                ),
                retrieved=(
                    _page("doc", 2),
                    _page("doc", 1),
                    _page("doc", 3),
                ),
            ),
            _input(
                "q2",
                category="unanswerable",
                qrels=(),
                retrieved=(),
                ask_status="insufficient_evidence",
                ascii_token_count=0,
            ),
        )
    )

    observed = 1.0 + 3.0 / math.log2(3)
    ideal = 3.0 + 1.0 / math.log2(3)
    assert metrics.ndcg_at_5.value == round(observed / ideal, 6)
    assert metrics.ndcg_at_10.value == round(observed / ideal, 6)
    assert metrics.ndcg_at_5.count == 1


@pytest.mark.parametrize(
    ("retrieved", "expected"),
    [
        ((_page("doc", 2), _page("doc", 1)), 1.0),
        ((_page("doc", 2),), 1.0),
        ((_page("doc", 1), _page("doc", 2)), 0.0),
        ((), 0.0),
    ],
)
def test_hard_negative_failure_uses_designated_grade_zero(
    retrieved: tuple[StableLocator, ...], expected: float
) -> None:
    metrics = calculate_graded_metrics(
        (
            _input(
                "hard",
                category="ranking_hard_negative",
                qrels=(_qrel("doc", 1, 2), _qrel("doc", 2, 0)),
                retrieved=retrieved,
                ask_status="evidence_found" if retrieved else "insufficient_evidence",
            ),
            _input(
                "none",
                category="unanswerable",
                qrels=(),
                retrieved=(),
                ask_status="insufficient_evidence",
                ascii_token_count=0,
            ),
        )
    )

    assert metrics.hard_negative_failure_rate.value == expected
    assert metrics.hard_negative_failure_rate.count == 1


def test_metrics_count_three_ask_outcomes_separately() -> None:
    metrics = calculate_graded_metrics(
        (
            _input("found"),
            _input(
                "insufficient",
                retrieved=(),
                ask_status="insufficient_evidence",
            ),
            _input(
                "invalid",
                category="unanswerable",
                qrels=(),
                retrieved=(),
                ask_status="invalid_question",
                compiled_query_empty=True,
                ascii_token_count=0,
            ),
        )
    )

    assert metrics.ask_evidence_found_rate.value == pytest.approx(1 / 3)
    assert metrics.ask_insufficient_evidence_rate.value == pytest.approx(1 / 3)
    assert metrics.ask_input_rejection_rate.value == pytest.approx(1 / 3)


def test_metrics_include_all_categories_and_fixed_query_strata() -> None:
    metrics = calculate_graded_metrics(
        (
            _input("one", ascii_token_count=1),
            _input(
                "two",
                category="semantic_paraphrase",
                ascii_token_count=3,
            ),
            _input(
                "zero",
                category="unanswerable",
                qrels=(),
                retrieved=(),
                ask_status="invalid_question",
                compiled_query_empty=True,
                ascii_token_count=0,
            ),
        )
    )

    assert [item.label for item in metrics.category_metrics] == [
        "chinese_exact_lexical",
        "chinese_word_boundary",
        "proper_noun_mixed",
        "number_date_unit",
        "semantic_paraphrase",
        "multi_condition",
        "ranking_hard_negative",
        "unanswerable",
    ]
    assert [item.query_count for item in metrics.category_metrics] == [
        1,
        0,
        0,
        0,
        1,
        0,
        0,
        1,
    ]
    assert [
        (item.label, item.query_count)
        for item in metrics.compiled_query_empty_metrics
    ] == [("false", 2), ("true", 1)]
    assert [
        (item.label, item.query_count) for item in metrics.ascii_token_count_metrics
    ] == [("0", 1), ("1", 1), ("2_plus", 1)]


def test_metric_values_round_only_the_public_value() -> None:
    metrics = calculate_graded_metrics(
        (
            _input(
                "fraction",
                qrels=(
                    _qrel("doc", 1, 2),
                    _qrel("doc", 2, 2),
                    _qrel("doc", 3, 2),
                ),
                retrieved=(_page("doc", 1),),
            ),
            _input(
                "none",
                category="unanswerable",
                qrels=(),
                retrieved=(),
                ask_status="insufficient_evidence",
                ascii_token_count=0,
            ),
        )
    )

    assert metrics.recall_at_1.value == 0.333333
    assert metrics.recall_at_1.sum == 1 / 3
    assert metrics.recall_at_1.count == 1


@pytest.mark.parametrize(
    ("item", "cause"),
    [
        (
            _input(
                "duplicate",
                retrieved=(_page("doc", 1), _page("doc", 1)),
            ),
            "retrieved locators must be unique",
        ),
        (
            _input("status", ask_status="other"),
            "Ask status is invalid",
        ),
        (
            _input("no-direct", qrels=(_qrel("doc", 1, 1),)),
            "answerable metric input requires grade 2",
        ),
        (
            _input("flag", compiled_query_empty=1),  # type: ignore[arg-type]
            "compiled-query flag is invalid",
        ),
        (
            _input("ascii-bool", ascii_token_count=True),  # type: ignore[arg-type]
            "ASCII token count is invalid",
        ),
        (
            _input("ascii-negative", ascii_token_count=-1),
            "ASCII token count is invalid",
        ),
    ],
)
def test_metrics_reject_invalid_inputs(
    item: GradedQueryMetricInput, cause: str
) -> None:
    with pytest.raises(ValueError, match=cause):
        calculate_graded_metrics((item,))
