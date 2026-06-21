import pytest

from mke.evaluation.manifest import StableLocator
from mke.evaluation.metrics import QueryMetricInput, calculate_metrics


def _page(document_id: str, page: int) -> StableLocator:
    return StableLocator(document_id, "page", page, page)


def test_metrics_use_macro_recall_and_first_relevant_rank() -> None:
    metrics = calculate_metrics(
        (
            QueryMetricInput(
                category="answerable",
                relevant=(_page("doc", 1), _page("doc", 2)),
                retrieved=(_page("doc", 1), _page("other", 1), _page("doc", 2)),
                ask_status="evidence_found",
            ),
            QueryMetricInput(
                category="answerable",
                relevant=(_page("doc", 3),),
                retrieved=(),
                ask_status="insufficient_evidence",
            ),
            QueryMetricInput(
                category="out_of_corpus",
                relevant=(),
                retrieved=(),
                ask_status="insufficient_evidence",
            ),
        )
    )

    assert metrics.locator_recall_at_1.value == 0.25
    assert metrics.locator_recall_at_3.value == 0.5
    assert metrics.locator_recall_at_5.value == 0.5
    assert metrics.mrr_at_5.value == 0.5
    assert metrics.answerable_zero_hit_rate.value == 0.5
    assert metrics.unanswerable_no_hit_rate.value == 1.0
    assert metrics.ask_refusal_rate.value == 1.0


def test_metrics_round_values_to_six_decimal_places() -> None:
    metrics = calculate_metrics(
        (
            QueryMetricInput(
                category="answerable",
                relevant=(_page("doc", 1), _page("doc", 2), _page("doc", 3)),
                retrieved=(_page("doc", 1),),
                ask_status="evidence_found",
            ),
            QueryMetricInput(
                category="lexical_confuser",
                relevant=(),
                retrieved=(),
                ask_status="insufficient_evidence",
            ),
        )
    )

    assert metrics.locator_recall_at_1.value == 0.333333
    assert metrics.locator_recall_at_1.sum == 0.3333333333333333
    assert metrics.locator_recall_at_1.count == 1


def test_metrics_use_first_relevant_rank_after_non_relevant_result() -> None:
    metrics = calculate_metrics(
        (
            QueryMetricInput(
                category="answerable",
                relevant=(_page("doc", 2),),
                retrieved=(_page("other", 1), _page("doc", 2)),
                ask_status="evidence_found",
            ),
            QueryMetricInput(
                category="out_of_corpus",
                relevant=(),
                retrieved=(),
                ask_status="insufficient_evidence",
            ),
        )
    )

    assert metrics.mrr_at_5.value == 0.5


def test_metrics_group_both_unanswerable_categories() -> None:
    metrics = calculate_metrics(
        (
            QueryMetricInput(
                category="answerable",
                relevant=(_page("doc", 1),),
                retrieved=(_page("doc", 1),),
                ask_status="evidence_found",
            ),
            QueryMetricInput(
                category="lexical_confuser",
                relevant=(),
                retrieved=(_page("doc", 1),),
                ask_status="evidence_found",
            ),
            QueryMetricInput(
                category="out_of_corpus",
                relevant=(),
                retrieved=(),
                ask_status="insufficient_evidence",
            ),
        )
    )

    assert metrics.unanswerable_no_hit_rate.value == 0.5
    assert metrics.ask_refusal_rate.value == 0.5
    assert metrics.unanswerable_no_hit_rate.count == 2


@pytest.mark.parametrize(
    "item",
    [
        QueryMetricInput(
            category="out_of_corpus",
            relevant=(),
            retrieved=(_page("doc", 1),),
            ask_status="insufficient_evidence",
        ),
        QueryMetricInput(
            category="out_of_corpus",
            relevant=(),
            retrieved=(),
            ask_status="evidence_found",
        ),
    ],
)
def test_metrics_reject_search_ask_disagreement(item: QueryMetricInput) -> None:
    with pytest.raises(ValueError, match="Search and Ask results disagree"):
        calculate_metrics(
            (
                QueryMetricInput(
                    category="answerable",
                    relevant=(_page("doc", 1),),
                    retrieved=(_page("doc", 1),),
                    ask_status="evidence_found",
                ),
                item,
            )
        )


@pytest.mark.parametrize(
    "inputs",
    [
        (
            QueryMetricInput(
                category="answerable",
                relevant=(_page("doc", 1),),
                retrieved=(),
                ask_status="insufficient_evidence",
            ),
        ),
        (
            QueryMetricInput(
                category="out_of_corpus",
                relevant=(),
                retrieved=(),
                ask_status="insufficient_evidence",
            ),
        ),
    ],
)
def test_metrics_require_answerable_and_unanswerable_groups(
    inputs: tuple[QueryMetricInput, ...],
) -> None:
    with pytest.raises(ValueError, match="metrics require answerable and unanswerable queries"):
        calculate_metrics(inputs)
