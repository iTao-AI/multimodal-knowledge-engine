"""Immutable, active-only Source discovery snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mke.domain import TranscriptIntakeReport
from mke.domain.evidence_access import ActiveAuthoritySnapshot, EvidenceDescriptor, EvidenceExcerpt
from mke.domain.pdf_observation import PdfExtractionObservation


@dataclass(frozen=True)
class SourceLocatorRange:
    kind: Literal["page", "timestamp_ms"]
    start: int
    end: int

    def __post_init__(self) -> None:
        if type(self.start) is not int or type(self.end) is not int:
            raise ValueError("locator boundaries must be integers")
        if not (
            self.kind == "page"
            and 0 < self.start <= self.end
            or self.kind == "timestamp_ms"
            and 0 <= self.start < self.end
        ):
            raise ValueError("invalid Source locator range")


@dataclass(frozen=True)
class PdfSourceCoverage:
    report_status: Literal["observed", "not_observed"]
    extraction_mode: str | None = None
    total_pages: int | None = None
    extracted_pages: int | None = None
    empty_pages: int | None = None
    suspected_scanned_pages: int | None = None
    total_extracted_chars: int | None = None
    page_char_counts: tuple[int, ...] = ()
    page_char_counts_total: int | None = None
    page_char_counts_omitted: bool = False
    kind: Literal["pdf"] = "pdf"


@dataclass(frozen=True)
class TranscriptSourceCoverage:
    report_status: Literal["observed", "not_observed"]
    provenance: TranscriptIntakeReport | None = None
    evidence_kind: Literal["stored_transcript"] = "stored_transcript"
    kind: Literal["transcript"] = "transcript"


type SourceCoverage = PdfSourceCoverage | TranscriptSourceCoverage


@dataclass(frozen=True)
class SourceMetadata:
    source_id: str
    display_name: str
    media_type: str
    content_fingerprint: str
    publication_id: str
    publication_revision: int
    run_id: str
    extractor_fingerprint: str
    required_stages: tuple[str, ...]
    evidence_count: int
    coverage: SourceCoverage
    pdf_extraction_observation: PdfExtractionObservation | None = None


@dataclass(frozen=True)
class SourceBrowseEntry:
    descriptor: EvidenceDescriptor
    preview: EvidenceExcerpt


@dataclass(frozen=True)
class SourceCatalogPage:
    authority: ActiveAuthoritySnapshot
    position: int
    sources: tuple[SourceMetadata, ...]
    more_available: bool


@dataclass(frozen=True)
class SourceBrowsePage:
    authority: ActiveAuthoritySnapshot
    position: int
    source: SourceMetadata
    entries: tuple[SourceBrowseEntry, ...]
    more_available: bool
