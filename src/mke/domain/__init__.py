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


class FailurePoint(StrEnum):
    """Deterministic failure injection points for the PR 3 reliability proof."""

    BEFORE_VALIDATION = "before_validation"
    DURING_CANDIDATE_WRITES = "during_candidate_writes"
    DURING_ACTIVE_FTS_REPLACEMENT = "during_active_fts_replacement"
    AFTER_PUBLICATION_INSERT = "after_publication_insert"
    AFTER_ACTIVE_POINTER_SWITCH = "after_active_pointer_switch"


class RunEventType(StrEnum):
    """Append-only Run event types recorded during the Evidence lifecycle."""

    RUN_CREATED = "run_created"
    RUN_STARTED = "run_started"
    RUN_FAILED = "run_failed"
    RUN_INTERRUPTED = "run_interrupted"
    CANDIDATE_VALIDATED = "candidate_validated"
    PUBLICATION_ACTIVATED = "publication_activated"
    RUN_SUPERSEDED = "run_superseded"


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
    retry_of_run_id: str | None = None


@dataclass(frozen=True)
class RunEvent:
    run_id: str
    event_index: int
    event_type: str


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
    retry_of_run_id: str | None = None


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
