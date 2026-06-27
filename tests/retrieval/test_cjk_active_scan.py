from dataclasses import replace

import pytest

from mke.retrieval.cjk_active_scan import (
    CJK_ACTIVE_SCAN_PARAMETERS,
    CjkActiveScanCandidate,
    CjkActiveScanError,
    compile_cjk_overlap_terms,
    rank_cjk_active_scan_candidates,
)


def test_active_scan_parameters_match_e3b_thresholds() -> None:
    assert CJK_ACTIVE_SCAN_PARAMETERS.strategy_id == "cjk-active-scan-overlap-v1"
    assert CJK_ACTIVE_SCAN_PARAMETERS.revision == 1
    assert CJK_ACTIVE_SCAN_PARAMETERS.minimum_overlap_count == 2
    assert CJK_ACTIVE_SCAN_PARAMETERS.minimum_overlap_ratio == 0.30
    assert CJK_ACTIVE_SCAN_PARAMETERS.max_results == 10


def test_cjk_overlap_terms_are_deterministic_and_deduplicated() -> None:
    compiled = compile_cjk_overlap_terms("发布证据检索 发布证据")

    assert compiled.terms == ("发布证", "布证据", "证据检", "据检索", "检索发", "索发布")
    assert compiled.omitted_below_minimum == ()
    assert compiled.truncated is False


def test_two_character_cjk_query_returns_stable_ineligible_error() -> None:
    try:
        compile_cjk_overlap_terms("证据", require_terms=True)
    except CjkActiveScanError as error:
        assert error.problem == "cjk_query_not_eligible"
        assert error.cause == "Query does not contain enough eligible CJK terms"
        assert error.next_step == "revise_query_or_use_rollback_strategy"
    else:  # pragma: no cover - test must fail if no error is raised
        raise AssertionError("expected CjkActiveScanError")


def test_punctuation_cjk_query_uses_longer_eligible_run() -> None:
    compiled = compile_cjk_overlap_terms("证据。生命周期")

    assert compiled.terms == ("生命周", "命周期")
    assert compiled.omitted_below_minimum == ("证据",)


def test_active_scan_overlap_ranker_applies_thresholds_and_tie_breaks() -> None:
    compiled = compile_cjk_overlap_terms("发布证据检索")
    candidates = (
        _candidate("ev_b", "doc-b", 1, "发布证据检索 完整页面"),
        _candidate("ev_a", "doc-a", 2, "发布证据检索 完整页面"),
        _candidate("ev_filtered", "doc-a", 1, "发布证"),
    )

    results = rank_cjk_active_scan_candidates(candidates, compiled.terms)

    assert [item.evidence_id for item in results] == ["ev_a", "ev_b"]
    assert results[0].overlap_count == 4
    assert results[0].overlap_ratio == 1.0


def test_runtime_query_fanout_fails_closed_instead_of_truncating() -> None:
    with pytest.raises(CjkActiveScanError) as raised:
        compile_cjk_overlap_terms("发布证据检索" * 100, require_terms=True)

    assert raised.value.problem == "cjk_scan_budget_exceeded"
    assert raised.value.cause == (
        "CJK active Evidence scan would exceed configured local budget"
    )
    assert raised.value.next_step == "narrow_query_or_use_projection_strategy"


def test_candidate_pool_cap_returns_stable_error() -> None:
    parameters = replace(CJK_ACTIVE_SCAN_PARAMETERS, max_candidate_pool=1)
    compiled = compile_cjk_overlap_terms("发布证据检索")
    candidates = (
        _candidate("ev_a", "doc-a", 1, "发布证据检索"),
        _candidate("ev_b", "doc-b", 1, "发布证据检索"),
    )

    with pytest.raises(CjkActiveScanError) as raised:
        rank_cjk_active_scan_candidates(
            candidates,
            compiled.terms,
            parameters=parameters,
        )

    assert raised.value.problem == "cjk_candidate_pool_capped"
    assert raised.value.cause == "CJK candidate pool exceeded the configured cap"
    assert raised.value.next_step == "narrow_query"


def _candidate(
    evidence_id: str,
    source_id: str,
    locator_start: int,
    text: str,
) -> CjkActiveScanCandidate:
    return CjkActiveScanCandidate(
        evidence_id=evidence_id,
        publication_id="pub",
        source_id=source_id,
        locator_kind="page",
        locator_start=locator_start,
        locator_end=locator_start,
        text=text,
        document_id=source_id,
    )
