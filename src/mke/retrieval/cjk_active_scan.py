"""Bounded CJK active Evidence scan retrieval helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CjkActiveScanParameters:
    strategy_id: str
    revision: int
    minimum_overlap_count: int
    minimum_overlap_ratio: float
    max_results: int
    max_cjk_query_chars: int
    max_overlap_terms: int
    max_active_evidence_rows: int
    max_active_evidence_text_bytes: int
    max_candidate_pool: int


@dataclass(frozen=True)
class CjkOverlapTerms:
    terms: tuple[str, ...]
    omitted_below_minimum: tuple[str, ...]
    truncated: bool


@dataclass(frozen=True)
class CjkActiveScanCandidate:
    evidence_id: str
    publication_id: str
    source_id: str
    locator_kind: str
    locator_start: int
    locator_end: int
    text: str
    document_id: str | None = None


@dataclass(frozen=True)
class CjkActiveScanResult:
    evidence_id: str
    publication_id: str
    source_id: str
    locator_kind: str
    locator_start: int
    locator_end: int
    text: str
    overlap_count: int
    overlap_ratio: float
    matched_terms: tuple[str, ...]
    document_id: str | None = None


class CjkActiveScanError(ValueError):
    """Stable public-safe active-scan retrieval error."""

    def __init__(self, problem: str, cause: str, next_step: str) -> None:
        super().__init__(cause)
        self.problem = problem
        self.cause = cause
        self.next_step = next_step


CJK_ACTIVE_SCAN_PARAMETERS = CjkActiveScanParameters(
    strategy_id="cjk-active-scan-overlap-v1",
    revision=1,
    minimum_overlap_count=2,
    minimum_overlap_ratio=0.30,
    max_results=10,
    max_cjk_query_chars=512,
    max_overlap_terms=128,
    max_active_evidence_rows=10_000,
    max_active_evidence_text_bytes=16 * 1024 * 1024,
    max_candidate_pool=1_000,
)


def compile_cjk_overlap_terms(
    query: str,
    *,
    parameters: CjkActiveScanParameters = CJK_ACTIVE_SCAN_PARAMETERS,
    require_terms: bool = False,
) -> CjkOverlapTerms:
    normalized_query = query.casefold()
    if len(normalized_query) > parameters.max_cjk_query_chars:
        raise _scan_budget_exceeded()
    terms: list[str] = []
    seen_terms: set[str] = set()
    omitted: list[str] = []
    for run in _cjk_runs(normalized_query):
        if len(run) < 3:
            omitted.append(run)
            continue
        for index in range(0, len(run) - 2):
            term = run[index : index + 3]
            if term in seen_terms:
                continue
            if len(terms) >= parameters.max_overlap_terms:
                raise _scan_budget_exceeded()
            seen_terms.add(term)
            terms.append(term)
    compiled = CjkOverlapTerms(tuple(terms), tuple(omitted), False)
    if require_terms and not compiled.terms:
        raise CjkActiveScanError(
            "cjk_query_not_eligible",
            "Query does not contain enough eligible CJK terms",
            "revise_query_or_use_rollback_strategy",
        )
    return compiled


def rank_cjk_active_scan_candidates(
    candidates: tuple[CjkActiveScanCandidate, ...],
    terms: tuple[str, ...],
    *,
    parameters: CjkActiveScanParameters = CJK_ACTIVE_SCAN_PARAMETERS,
) -> tuple[CjkActiveScanResult, ...]:
    if not terms:
        return ()
    scored: list[CjkActiveScanResult] = []
    for candidate in candidates:
        normalized_text = _normalize_cjk_text(candidate.text)
        matched_terms = tuple(term for term in terms if term in normalized_text)
        overlap_count = len(matched_terms)
        overlap_ratio = overlap_count / len(terms)
        if (
            overlap_count < parameters.minimum_overlap_count
            or overlap_ratio < parameters.minimum_overlap_ratio
        ):
            continue
        if len(scored) >= parameters.max_candidate_pool:
            raise CjkActiveScanError(
                "cjk_candidate_pool_capped",
                "CJK candidate pool exceeded the configured cap",
                "narrow_query",
            )
        scored.append(
            CjkActiveScanResult(
                evidence_id=candidate.evidence_id,
                publication_id=candidate.publication_id,
                source_id=candidate.source_id,
                locator_kind=candidate.locator_kind,
                locator_start=candidate.locator_start,
                locator_end=candidate.locator_end,
                text=candidate.text,
                overlap_count=overlap_count,
                overlap_ratio=overlap_ratio,
                matched_terms=matched_terms,
                document_id=candidate.document_id,
            )
        )
    return tuple(
        sorted(
            scored,
            key=lambda item: (
                -item.overlap_count,
                -item.overlap_ratio,
                item.document_id or item.source_id,
                item.locator_start,
                item.evidence_id,
            ),
        )[: parameters.max_results]
    )


def _cjk_runs(query: str) -> tuple[str, ...]:
    runs: list[str] = []
    current: list[str] = []
    for character in query:
        if _is_cjk_character(character):
            current.append(character)
        elif character.isspace():
            continue
        elif current:
            runs.append("".join(current))
            current = []
    if current:
        runs.append("".join(current))
    return tuple(runs)


def _is_cjk_character(character: str) -> bool:
    codepoint = ord(character)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x3040 <= codepoint <= 0x30FF
        or 0x31F0 <= codepoint <= 0x31FF
        or 0xAC00 <= codepoint <= 0xD7AF
    )


def _normalize_cjk_text(text: str) -> str:
    return "".join(character for character in text.casefold() if not character.isspace())


def _scan_budget_exceeded() -> CjkActiveScanError:
    return CjkActiveScanError(
        "cjk_scan_budget_exceeded",
        "CJK active Evidence scan would exceed configured local budget",
        "narrow_query_or_use_projection_strategy",
    )
