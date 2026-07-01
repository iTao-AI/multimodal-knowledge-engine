"""Deterministic E3-E relevance gate profiles and reranking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mke.evaluation.relevance_gate_features import RelevanceFeatures

ProfileId = Literal["lexical-floor", "balanced-constraint", "strict-constraint"]
ReasonCode = Literal[
    "allowed",
    "missing_date_constraint",
    "missing_mixed_constraint",
    "missing_numeric_constraint",
    "missing_unit_constraint",
    "weak_dense_overlap",
    "weak_lexical_floor_overlap",
]

PROFILE_CATALOG: tuple[ProfileId, ...] = (
    "lexical-floor",
    "balanced-constraint",
    "strict-constraint",
)


class RelevanceGateCandidateError(ValueError):
    """Raised when candidate gating input is invalid."""


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason_code: ReasonCode
    rerank_score: float


@dataclass(frozen=True)
class RankedRelevanceRow:
    features: RelevanceFeatures
    decision: GateDecision


def gate_feature_row(
    features: RelevanceFeatures,
    *,
    profile_id: str,
) -> GateDecision:
    profile = _profile(profile_id)
    _validate_features(features)
    constraint_reason = _constraint_rejection(features)
    if constraint_reason is not None:
        return GateDecision(
            allowed=False,
            reason_code=constraint_reason,
            rerank_score=0.0,
        )
    if profile == "lexical-floor" and "lexical" not in features.arm_contributions:
        if not _has_explicit_constraint(features) or _overlap_strength(features) < 1:
            return GateDecision(
                allowed=False,
                reason_code="weak_lexical_floor_overlap",
                rerank_score=0.0,
            )
    if profile == "strict-constraint" and "dense" in features.arm_contributions:
        if "lexical" not in features.arm_contributions and _overlap_strength(features) < 2:
            return GateDecision(
                allowed=False,
                reason_code="weak_dense_overlap",
                rerank_score=0.0,
            )
    return GateDecision(
        allowed=True,
        reason_code="allowed",
        rerank_score=_score(features, profile=profile),
    )


def rerank_allowed_rows(
    rows: tuple[RelevanceFeatures, ...],
    *,
    profile_id: str,
) -> tuple[RankedRelevanceRow, ...]:
    profile = _profile(profile_id)
    ranked = tuple(
        RankedRelevanceRow(features=row, decision=decision)
        for row in rows
        if (decision := gate_feature_row(row, profile_id=profile)).allowed
    )
    return tuple(sorted(ranked, key=_sort_key))


def _profile(profile_id: str) -> ProfileId:
    if profile_id not in PROFILE_CATALOG:
        raise RelevanceGateCandidateError("profile is invalid")
    return profile_id  # type: ignore[return-value]


def _validate_features(features: RelevanceFeatures) -> None:
    for subject, rank in (
        ("lexical_rank", features.lexical_rank),
        ("dense_rank", features.dense_rank),
        ("rrf_rank", features.rrf_rank),
    ):
        if rank is not None and (type(rank) is not int or rank < 1):
            raise RelevanceGateCandidateError(f"{subject} rank is invalid")
    if not features.arm_contributions:
        raise RelevanceGateCandidateError("arm provenance is invalid")
    if set(features.arm_contributions) - {"lexical", "dense"}:
        raise RelevanceGateCandidateError("arm provenance is invalid")


def _constraint_rejection(features: RelevanceFeatures) -> ReasonCode | None:
    coverage = features.coverage
    if coverage.missing_dates:
        return "missing_date_constraint"
    if coverage.missing_mixed:
        return "missing_mixed_constraint"
    if coverage.missing_numbers:
        return "missing_numeric_constraint"
    if coverage.missing_units:
        return "missing_unit_constraint"
    return None


def _score(features: RelevanceFeatures, *, profile: ProfileId) -> float:
    del profile
    arm_bonus = 10.0 * len(set(features.arm_contributions))
    overlap_bonus = (
        features.coverage.cjk_overlap_count
        + features.coverage.ascii_overlap_count
        + (2 * features.coverage.mixed_overlap_count)
    )
    rank_penalty = 0.01 * _best_rank(features)
    return round(arm_bonus + overlap_bonus - rank_penalty, 6)


def _sort_key(row: RankedRelevanceRow) -> tuple[float, int, int, int, int, int, str]:
    features = row.features
    return (
        -row.decision.rerank_score,
        -len(set(features.arm_contributions)),
        _best_rank(features),
        _rank_or_large(features.lexical_rank),
        _rank_or_large(features.dense_rank),
        _rank_or_large(features.rrf_rank),
        features.stable_locator_id,
    )


def _has_explicit_constraint(features: RelevanceFeatures) -> bool:
    constraints = features.required_constraints
    return bool(
        constraints.numbers
        or constraints.dates
        or constraints.units
        or constraints.mixed
    )


def _overlap_strength(features: RelevanceFeatures) -> int:
    return (
        features.coverage.cjk_overlap_count
        + features.coverage.ascii_overlap_count
        + features.coverage.mixed_overlap_count
    )


def _best_rank(features: RelevanceFeatures) -> int:
    return min(
        _rank_or_large(features.lexical_rank),
        _rank_or_large(features.dense_rank),
        _rank_or_large(features.rrf_rank),
    )


def _rank_or_large(rank: int | None) -> int:
    return rank if rank is not None else 1_000_000
