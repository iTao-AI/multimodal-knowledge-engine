"""Domain types for the first trustworthy Evidence lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RunState(StrEnum):
    """Authoritative Run states from ADR-0002."""

    QUEUED = "queued"
    RUNNING = "running"
    VALIDATED = "validated"
    PUBLISHED = "published"
    FAILED = "failed"
    SUPERSEDED = "superseded"
    INTERRUPTED = "interrupted"


class ManifestValidationError(ValueError):
    """Raised when candidate output cannot safely become a Publication."""


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    active_publication_id: str | None
    active_revision: int
    requested_generation: int


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    source_id: str
    state: RunState
    source_generation: int
    based_on_active_revision: int


@dataclass(frozen=True)
class CandidateEvidence:
    evidence_id: str
    locator_kind: str
    locator_start: int
    locator_end: int
    text: str


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    evidence_count: int
    required_stages: tuple[str, ...]
    extractor_fingerprint: str
    asset_sha256: str


@dataclass(frozen=True)
class ActivationResult:
    run_id: str
    run_state: RunState
    published: bool
    publication_id: str | None


@dataclass(frozen=True)
class IngestResult:
    run_id: str
    run_state: RunState
    evidence_count: int


@dataclass(frozen=True)
class SearchResult:
    evidence_id: str
    publication_id: str
    source_id: str
    page_number: int
    text: str


REQUIRED_PDF_STAGES = frozenset({"pdf_text_extraction", "candidate_evidence"})
PDF_EXTRACTOR_FINGERPRINT = "builtin-pdf-text-v1"


def validate_manifest(manifest: RunManifest, evidence: list[CandidateEvidence]) -> None:
    """Validate candidate Evidence before it can change active Search visibility."""
    if manifest.evidence_count != len(evidence):
        raise ManifestValidationError(
            "RunManifest evidence count does not match candidate Evidence"
        )
    if frozenset(manifest.required_stages) != REQUIRED_PDF_STAGES:
        raise ManifestValidationError("RunManifest required stages are incomplete")
    if manifest.extractor_fingerprint != PDF_EXTRACTOR_FINGERPRINT:
        raise ManifestValidationError("RunManifest extractor fingerprint is not recognized")
    if len(manifest.asset_sha256) != 64:
        raise ManifestValidationError("RunManifest asset sha256 must be a hex digest")
    for item in evidence:
        if item.locator_kind != "page":
            raise ManifestValidationError("Evidence locator kind must be page")
        if item.locator_start < 1 or item.locator_end < item.locator_start:
            raise ManifestValidationError("Evidence page locator must use positive page numbers")
        if not item.text.strip():
            raise ManifestValidationError("Evidence text must not be empty")
