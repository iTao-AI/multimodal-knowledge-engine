from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol


@dataclass(frozen=True)
class EvaluationEvidenceSnapshot:
    evidence_id: str
    publication_id: str
    source_id: str
    locator_kind: str
    locator_start: int
    locator_end: int
    text: str


@dataclass(frozen=True)
class FtsProjectionSnapshot:
    evidence_id: str
    publication_id: str
    source_id: str
    locator_label: str
    text_sha256: str


@dataclass(frozen=True)
class FtsRankObservation:
    evidence_id: str
    locator_start: int
    rank_score: float
    bm25_score: float


@dataclass(frozen=True)
class FtsRankProfile:
    rank_order: tuple[FtsRankObservation, ...]
    bm25_order: tuple[FtsRankObservation, ...]
    rank_override_present: bool


class FtsProjectionIntegrityError(ValueError):
    """The rebuildable FTS projection differs from active domain Evidence."""


class EvaluationRetrievalDiagnostics(Protocol):
    def list_evaluation_evidence(self) -> tuple[EvaluationEvidenceSnapshot, ...]:
        raise NotImplementedError

    def list_fts_projection(self) -> tuple[FtsProjectionSnapshot, ...]:
        raise NotImplementedError

    def observe_fts5_rank(self, compiled_query: str) -> FtsRankProfile:
        raise NotImplementedError


def validate_fts_projection(
    evidence: tuple[EvaluationEvidenceSnapshot, ...],
    projection: tuple[FtsProjectionSnapshot, ...],
) -> None:
    expected = Counter(
        FtsProjectionSnapshot(
            evidence_id=item.evidence_id,
            publication_id=item.publication_id,
            source_id=item.source_id,
            locator_label=_locator_label(
                item.locator_kind, item.locator_start, item.locator_end
            ),
            text_sha256=sha256(item.text.encode("utf-8")).hexdigest(),
        )
        for item in evidence
    )
    observed = Counter(projection)
    if expected != observed:
        raise FtsProjectionIntegrityError(
            "active Evidence and FTS projection are inconsistent"
        )


def _locator_label(locator_kind: str, locator_start: int, locator_end: int) -> str:
    if locator_kind == "page":
        return f"page:{locator_start}"
    if locator_kind == "timestamp_ms":
        return f"timestamp_ms:{locator_start}..{locator_end}"
    return f"{locator_kind}:{locator_start}..{locator_end}"
