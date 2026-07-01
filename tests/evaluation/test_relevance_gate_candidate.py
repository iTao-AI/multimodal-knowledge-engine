from __future__ import annotations

import dataclasses

import pytest

from mke.evaluation.relevance_gate_candidate import (
    GateDecision,
    RelevanceGateCandidateError,
    gate_feature_row,
    rerank_allowed_rows,
)
from mke.evaluation.relevance_gate_features import (
    EvidenceCandidateInput,
    build_relevance_features,
)


def test_lexical_floor_preserves_high_confidence_lexical_rows() -> None:
    decision = gate_feature_row(
        _features(
            stable_locator_id="doc|page|1|1|a",
            query="服务限额是多少？",
            evidence="服务限额是30GB。",
            arms=("lexical",),
            lexical_rank=1,
            dense_rank=None,
            rrf_rank=2,
        ),
        profile_id="lexical-floor",
    )

    assert decision.allowed is True
    assert decision.reason_code == "allowed"
    assert decision.rerank_score > 0


def test_balanced_constraint_allows_dense_only_when_constraints_are_preserved() -> None:
    decision = gate_feature_row(
        _features(
            stable_locator_id="doc|page|2|2|a",
            query="API-7 在 2025 年需要 30GB 吗？",
            evidence="API-7 在 2025 年需要 30GB。",
            arms=("dense",),
            lexical_rank=None,
            dense_rank=2,
            rrf_rank=2,
        ),
        profile_id="balanced-constraint",
    )

    assert decision.allowed is True
    assert decision.reason_code == "allowed"


def test_strict_constraint_rejects_weak_overlap_dense_only_rows() -> None:
    decision = gate_feature_row(
        _features(
            stable_locator_id="doc|page|3|3|a",
            query="服务限额是多少？",
            evidence="平台支持上传文件。",
            arms=("dense",),
            lexical_rank=None,
            dense_rank=1,
            rrf_rank=1,
        ),
        profile_id="strict-constraint",
    )

    assert decision == GateDecision(
        allowed=False,
        reason_code="weak_dense_overlap",
        rerank_score=0.0,
    )


def test_missing_constraints_reject_with_stable_reason_codes() -> None:
    cases = (
        (
            "API-7 在 2025 年需要 30GB 吗？",
            "API-7 在 2024 年需要 30GB。",
            "missing_date_constraint",
        ),
        ("API-7 需要 30GB 吗？", "API-7 需要 20GB。", "missing_numeric_constraint"),
        ("API-7 需要 30GB 吗？", "API-7 需要 30MB。", "missing_unit_constraint"),
        ("API-7 需要吗？", "API-8 需要。", "missing_mixed_constraint"),
    )
    for query, evidence, reason_code in cases:
        decision = gate_feature_row(
            _features(
                stable_locator_id=f"doc|page|{reason_code}|{reason_code}|a",
                query=query,
                evidence=evidence,
                arms=("dense",),
                lexical_rank=None,
                dense_rank=1,
                rrf_rank=1,
            ),
            profile_id="balanced-constraint",
        )

        assert decision.allowed is False
        assert decision.reason_code == reason_code
        assert decision.rerank_score == 0.0


def test_allowed_rows_sort_by_score_and_stable_tie_breaks() -> None:
    rows = (
        _features(
            stable_locator_id="doc|page|3|3|c",
            query="服务限额",
            evidence="服务限额",
            arms=("dense",),
            lexical_rank=None,
            dense_rank=1,
            rrf_rank=1,
        ),
        _features(
            stable_locator_id="doc|page|2|2|b",
            query="服务限额",
            evidence="服务限额",
            arms=("lexical", "dense"),
            lexical_rank=2,
            dense_rank=2,
            rrf_rank=2,
        ),
        _features(
            stable_locator_id="doc|page|1|1|a",
            query="服务限额",
            evidence="服务限额",
            arms=("lexical", "dense"),
            lexical_rank=2,
            dense_rank=2,
            rrf_rank=2,
        ),
    )

    ranked = rerank_allowed_rows(rows, profile_id="balanced-constraint")

    assert [row.features.stable_locator_id for row in ranked] == [
        "doc|page|1|1|a",
        "doc|page|2|2|b",
        "doc|page|3|3|c",
    ]
    assert all(row.decision.allowed for row in ranked)


def test_rejected_rows_have_exactly_one_reason_code() -> None:
    ranked = rerank_allowed_rows(
        (
            _features(
                stable_locator_id="doc|page|1|1|a",
                query="API-7",
                evidence="API-8",
                arms=("dense",),
                lexical_rank=None,
                dense_rank=1,
                rrf_rank=1,
            ),
        ),
        profile_id="balanced-constraint",
    )

    assert ranked == ()


def test_rejects_unknown_profiles_and_bool_ranks() -> None:
    row = _features(
        stable_locator_id="doc|page|1|1|a",
        query="服务限额",
        evidence="服务限额",
        arms=("lexical",),
        lexical_rank=1,
        dense_rank=None,
        rrf_rank=1,
    )
    with pytest.raises(RelevanceGateCandidateError, match="profile"):
        gate_feature_row(row, profile_id="shortcut")

    bool_rank = dataclasses.replace(row, lexical_rank=True)  # type: ignore[arg-type]
    with pytest.raises(RelevanceGateCandidateError, match="rank"):
        gate_feature_row(bool_rank, profile_id="lexical-floor")


def _features(
    *,
    stable_locator_id: str,
    query: str,
    evidence: str,
    arms: tuple[str, ...],
    lexical_rank: int | None,
    dense_rank: int | None,
    rrf_rank: int | None,
):
    return build_relevance_features(
        EvidenceCandidateInput(
            query_id="q",
            query_text=query,
            stable_locator_id=stable_locator_id,
            document_id="doc",
            locator_kind="page",
            locator_start=1,
            locator_end=1,
            evidence_text=evidence,
            arm_contributions=arms,  # type: ignore[arg-type]
            lexical_rank=lexical_rank,
            dense_rank=dense_rank,
            rrf_rank=rrf_rank,
        )
    )
