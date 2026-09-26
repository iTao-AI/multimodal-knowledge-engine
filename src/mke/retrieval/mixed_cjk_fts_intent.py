"""Bounded CJK intent selection over an exact active FTS match set."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from mke.retrieval.cjk_active_scan import (
    CjkActiveScanError,
    cjk_runs,
    is_cjk_character,
)
from mke.retrieval.errors import RetrievalAuthorityError


@dataclass(frozen=True)
class MixedCjkFtsIntentParameters:
    strategy_id: str = "mixed-cjk-fts-intent-v1"
    revision: int = 1
    minimum_overlap_count: int = 2
    minimum_overlap_ratio: float = 0.30
    max_results: int = 10
    max_query_chars: int = 512
    max_overlap_terms: int = 128
    max_matched_rows: int = 10_000
    max_matched_text_bytes: int = 16 * 1024 * 1024
    max_candidate_pool: int = 1_000


MIXED_CJK_FTS_INTENT_PARAMETERS = MixedCjkFtsIntentParameters()


@dataclass(frozen=True)
class MixedCjkQuery:
    comparison_query: str
    has_cjk: bool
    terms: tuple[str, ...]


@dataclass(frozen=True)
class MixedCjkCandidate:
    evidence_id: str
    publication_id: str
    source_id: str
    content_fingerprint: str
    locator_kind: str
    locator_start: int
    locator_end: int
    text: str
    fts_order: int


@dataclass(frozen=True)
class MixedCjkResult(MixedCjkCandidate):
    overlap_count: int
    overlap_ratio: float
    matched_terms: tuple[str, ...]


@dataclass(frozen=True)
class MixedCjkSelection:
    results: tuple[MixedCjkResult, ...]
    eligible_count: int
    discarded_by_strategy_cap: bool


class MixedCjkFtsIntentError(CjkActiveScanError):
    """Stable public-safe failure for bounded mixed-query selection."""

    def __init__(self, problem: str, cause: str, next_step: str) -> None:
        super().__init__(problem, cause, next_step)


def compile_mixed_cjk_query(
    query: str,
    *,
    parameters: MixedCjkFtsIntentParameters = MIXED_CJK_FTS_INTENT_PARAMETERS,
) -> MixedCjkQuery:
    normalized = unicodedata.normalize("NFKC", query).casefold()
    has_cjk = any(is_cjk_character(character) for character in normalized)
    comparison_query = "".join(
        character for character in normalized if not character.isspace()
    )
    if not has_cjk:
        return MixedCjkQuery(comparison_query, False, ())
    if len(query) > parameters.max_query_chars or len(normalized) > parameters.max_query_chars:
        raise MixedCjkFtsIntentError(
            "mixed_cjk_query_budget_exceeded",
            "Mixed CJK query exceeds the configured local character budget",
            "shorten_query",
        )
    terms: list[str] = []
    seen: set[str] = set()
    if has_cjk:
        for run in cjk_runs(normalized):
            if len(run) < 3:
                continue
            for index in range(len(run) - 2):
                term = run[index : index + 3]
                if term in seen:
                    continue
                if len(terms) >= parameters.max_overlap_terms:
                    raise MixedCjkFtsIntentError(
                        "mixed_cjk_query_budget_exceeded",
                        "Mixed CJK query exceeds the configured local term budget",
                        "shorten_query",
                    )
                seen.add(term)
                terms.append(term)
    return MixedCjkQuery(comparison_query, has_cjk, tuple(terms))


def normalize_mixed_cjk_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return "".join(character for character in normalized if not character.isspace())


def select_mixed_cjk_candidates(
    candidates: tuple[MixedCjkCandidate, ...],
    terms: tuple[str, ...],
    *,
    parameters: MixedCjkFtsIntentParameters = MIXED_CJK_FTS_INTENT_PARAMETERS,
) -> MixedCjkSelection:
    if not terms:
        return MixedCjkSelection((), 0, False)
    seen: set[tuple[str, str, int, int]] = set()
    for candidate in candidates:
        locator = (
            candidate.content_fingerprint,
            candidate.locator_kind,
            candidate.locator_start,
            candidate.locator_end,
        )
        if locator in seen:
            raise RetrievalAuthorityError
        seen.add(locator)

    eligible: list[MixedCjkResult] = []
    for candidate in candidates:
        normalized_text = normalize_mixed_cjk_text(candidate.text)
        matched_terms = tuple(term for term in terms if term in normalized_text)
        overlap_count = len(matched_terms)
        overlap_ratio = overlap_count / len(terms)
        if (
            overlap_count < parameters.minimum_overlap_count
            or overlap_ratio < parameters.minimum_overlap_ratio
        ):
            continue
        if len(eligible) >= parameters.max_candidate_pool:
            raise MixedCjkFtsIntentError(
                "mixed_cjk_candidate_pool_exceeded",
                "Mixed CJK eligible candidate pool exceeded the configured cap",
                "narrow_query",
            )
        eligible.append(
            MixedCjkResult(
                evidence_id=candidate.evidence_id,
                publication_id=candidate.publication_id,
                source_id=candidate.source_id,
                content_fingerprint=candidate.content_fingerprint,
                locator_kind=candidate.locator_kind,
                locator_start=candidate.locator_start,
                locator_end=candidate.locator_end,
                text=candidate.text,
                fts_order=candidate.fts_order,
                overlap_count=overlap_count,
                overlap_ratio=overlap_ratio,
                matched_terms=matched_terms,
            )
        )
    ranked = tuple(
        sorted(
            eligible,
            key=lambda item: (
                -item.overlap_count,
                -item.overlap_ratio,
                item.fts_order,
            ),
        )
    )
    return MixedCjkSelection(
        results=ranked[: parameters.max_results],
        eligible_count=len(ranked),
        discarded_by_strategy_cap=len(ranked) > parameters.max_results,
    )


def matched_set_budget_error() -> MixedCjkFtsIntentError:
    return MixedCjkFtsIntentError(
        "mixed_cjk_match_budget_exceeded",
        "Mixed CJK FTS match set exceeds the configured local row or text budget",
        "narrow_query",
    )
