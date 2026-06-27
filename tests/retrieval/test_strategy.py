from inspect import signature
from pathlib import Path

import pytest

from mke.application import KnowledgeEngine
from mke.retrieval.query_policy import compile_fts5_query


def test_supported_runtime_strategies_are_exact() -> None:
    from mke.retrieval.strategy import SUPPORTED_RETRIEVAL_STRATEGIES

    assert SUPPORTED_RETRIEVAL_STRATEGIES == (
        "current",
        "numeric-grouping-v1",
        "cjk-active-scan-overlap-v1",
    )


def test_cjk_trigram_candidate_is_not_runtime_strategy() -> None:
    from mke.retrieval.strategy import require_retrieval_strategy

    with pytest.raises(ValueError, match="retrieval strategy is unsupported"):
        require_retrieval_strategy("cjk-trigram-overlap-v1")


def test_active_scan_strategy_is_the_promoted_default() -> None:
    from mke.retrieval.strategy import (
        DEFAULT_RETRIEVAL_STRATEGY,
        get_retrieval_strategy_descriptor,
        require_retrieval_strategy,
    )

    assert require_retrieval_strategy("cjk-active-scan-overlap-v1") == (
        "cjk-active-scan-overlap-v1"
    )
    assert DEFAULT_RETRIEVAL_STRATEGY == "cjk-active-scan-overlap-v1"
    descriptor = get_retrieval_strategy_descriptor("cjk-active-scan-overlap-v1")
    assert descriptor.strategy_id == "cjk-active-scan-overlap-v1"
    assert descriptor.base_query_policy == "numeric-grouping-v1"
    assert descriptor.required_projections == ("active_evidence_fts",)
    assert descriptor.additional_projections == ()
    assert descriptor.term_derivation_mode == "cjk-overlap-trigrams"
    assert descriptor.dense == "none"
    assert descriptor.hybrid == "none"
    assert descriptor.rerank == "none"


@pytest.mark.parametrize("value", ["unknown", "", "true"])
def test_invalid_strategy_fails_with_stable_error(value: str) -> None:
    from mke.retrieval.strategy import require_retrieval_strategy

    with pytest.raises(ValueError, match="retrieval strategy is unsupported"):
        require_retrieval_strategy(value)


@pytest.mark.parametrize("value", [True, False, 1, None])
def test_non_string_strategy_values_are_rejected_before_engine_construction(
    value: object,
) -> None:
    from mke.retrieval.strategy import require_retrieval_strategy

    with pytest.raises(TypeError, match="retrieval strategy must be a string"):
        require_retrieval_strategy(value)  # type: ignore[arg-type]


def test_legacy_query_policy_helpers_remain_available() -> None:
    assert compile_fts5_query("410000 withdrawals") == (
        '("410000" OR "410 000") AND "withdrawals"'
    )


def test_strategy_descriptor_is_extensible_without_request_dto_changes() -> None:
    from mke.retrieval.strategy import (
        RetrievalStrategyDescriptor,
        get_retrieval_strategy_descriptor,
    )

    active_scan = get_retrieval_strategy_descriptor("cjk-active-scan-overlap-v1")
    future = RetrievalStrategyDescriptor(
        strategy_id="future-dense-v1",
        revision=1,
        base_query_policy="numeric-grouping-v1",
        required_projections=("vector",),
        additional_projections=("vector",),
        term_derivation_mode="embedding-query",
        readiness_checker="vector-projection",
        rollback_capability=("numeric-grouping-v1", "current"),
        fallback_semantics="owner-selected descriptor only",
        dense="configured",
        hybrid="none",
        rerank="none",
    )

    assert future.strategy_id != active_scan.strategy_id
    assert "retrieval_strategy" not in signature(KnowledgeEngine.search).parameters
    assert "retrieval_strategy" not in signature(KnowledgeEngine.ask).parameters


def test_adr_0008_records_active_scan_strategy() -> None:
    path = Path("docs/decisions/0008-cjk-active-scan-retrieval-strategy.md")
    text = path.read_text(encoding="utf-8")

    assert "cjk-active-scan-overlap-v1" in text
    assert "Default Promotion Launch Gate" in text
    assert "app_scan_no_projection" in text


def test_adr_0007_and_0008_cross_reference_default_supersession() -> None:
    numeric = Path("docs/decisions/0007-numeric-grouping-query-policy.md").read_text(
        encoding="utf-8"
    )
    active_scan = Path(
        "docs/decisions/0008-cjk-active-scan-retrieval-strategy.md"
    ).read_text(encoding="utf-8")

    assert "Default selection superseded by ADR-0008" in numeric
    assert "supersedes only ADR-0007's default selection" in active_scan
