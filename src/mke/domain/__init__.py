"""Domain types for the first trustworthy Evidence lifecycle."""

from __future__ import annotations

import re
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


class RunTransitionError(RuntimeError):
    def __init__(
        self,
        run_id: str,
        *,
        expected: tuple[RunState, ...],
        actual: RunState,
        target: RunState,
    ) -> None:
        super().__init__("Run state changed during processing")
        self.run_id = run_id
        self.expected = expected
        self.actual = actual
        self.target = target


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
class PdfIntakeReport:
    total_pages: int
    extracted_pages: int
    empty_pages: int
    total_extracted_chars: int
    page_char_counts: tuple[int, ...]
    suspected_scanned_pages: int
    extraction_mode: str
    failure_reason: str | None = None


@dataclass(frozen=True)
class PdfPageText:
    page_number: int
    text: str


@dataclass(frozen=True)
class PdfExtractionResult:
    report: PdfIntakeReport
    pages: tuple[PdfPageText, ...]


@dataclass(frozen=True)
class VideoTranscriptSegment:
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True)
class VideoMediaInfo:
    container: str
    video_codec: str
    audio_codec: str
    has_audio: bool
    duration_ms: int

    def __post_init__(self) -> None:
        if any(
            type(value) is not str or not value.strip()
            for value in (self.container, self.video_codec, self.audio_codec)
        ):
            raise ValueError("video media identity fields must not be blank")
        if type(self.has_audio) is not bool:
            raise ValueError("video media has_audio must be a boolean")
        if type(self.duration_ms) is not int or self.duration_ms <= 0:
            raise ValueError("video media duration must be positive integer milliseconds")


_LANGUAGE_RE = re.compile(r"(?:auto|[a-z]{2,3})\Z")


def _validate_transcription_identity(
    *,
    provider: str,
    model: str,
    model_revision: str,
    library_version: str,
    device: str,
    compute_type: str,
    language: str,
    detected_language: str,
    model_source: str,
    transcription_duration_ms: int,
) -> None:
    if any(
        type(value) is not str or not value.strip()
        for value in (
            provider,
            model,
            model_revision,
            library_version,
            device,
            compute_type,
        )
    ):
        raise ValueError("transcription identity fields must not be blank")
    if _LANGUAGE_RE.fullmatch(language) is None:
        raise ValueError("transcription language must be auto or a lowercase language code")
    if _LANGUAGE_RE.fullmatch(detected_language) is None:
        raise ValueError("detected language must be auto or a lowercase language code")
    if model_source != "cache":
        raise ValueError("transcription model source must be cache")
    if type(transcription_duration_ms) is not int or transcription_duration_ms < 0:
        raise ValueError("transcription duration must be non-negative integer milliseconds")


@dataclass(frozen=True)
class TranscriptionProvenance:
    provider: str
    model: str
    model_revision: str
    library_version: str
    device: str
    compute_type: str
    language: str
    detected_language: str
    model_source: str
    transcription_duration_ms: int

    def __post_init__(self) -> None:
        _validate_transcription_identity(**self.__dict__)


@dataclass(frozen=True)
class ParsedVideoTranscript:
    media: VideoMediaInfo
    segments: tuple[VideoTranscriptSegment, ...]
    transcription_provenance: TranscriptionProvenance | None = None


@dataclass(frozen=True)
class TranscriptIntakeReport:
    provider: str
    model: str
    model_revision: str
    library_version: str
    device: str
    compute_type: str
    language: str
    detected_language: str
    media_duration_ms: int
    transcription_duration_ms: int
    segment_count: int
    model_source: str

    def __post_init__(self) -> None:
        _validate_transcription_identity(
            provider=self.provider,
            model=self.model,
            model_revision=self.model_revision,
            library_version=self.library_version,
            device=self.device,
            compute_type=self.compute_type,
            language=self.language,
            detected_language=self.detected_language,
            model_source=self.model_source,
            transcription_duration_ms=self.transcription_duration_ms,
        )
        if type(self.media_duration_ms) is not int or self.media_duration_ms <= 0:
            raise ValueError("media duration must be positive integer milliseconds")
        if type(self.segment_count) is not int or self.segment_count <= 0:
            raise ValueError("segment count must be a positive integer")


@dataclass(frozen=True)
class TranscriptExtractionResult:
    parsed_transcript: ParsedVideoTranscript
    extractor_fingerprint: str
    transcript_intake_report: TranscriptIntakeReport | None = None

    @property
    def segments(self) -> tuple[VideoTranscriptSegment, ...]:
        return self.parsed_transcript.segments


@dataclass(frozen=True)
class IngestResult:
    run_id: str
    run_state: RunState
    evidence_count: int
    retry_of_run_id: str | None = None
    intake_report: PdfIntakeReport | None = None
    transcript_intake_report: TranscriptIntakeReport | None = None


@dataclass(frozen=True)
class ActiveEvidenceRef:
    source_id: str
    locator_kind: str
    locator_start: int
    locator_end: int


@dataclass(frozen=True)
class SearchResult:
    evidence_id: str
    publication_id: str
    source_id: str
    locator_kind: str
    locator_start: int
    locator_end: int
    text: str

    @property
    def page_number(self) -> int:
        if self.locator_kind != "page":
            raise ValueError("SearchResult does not contain page Evidence")
        return self.locator_start


@dataclass(frozen=True)
class AskResult:
    ask_id: str
    question: str
    answer_status: str
    summary: str
    evidence: tuple[SearchResult, ...]
    limitations: tuple[str, ...]


_CONTENT_FINGERPRINT_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class SearchResultProvenance:
    result: SearchResult
    content_fingerprint: str
    publication_revision: int
    run_id: str

    def __post_init__(self) -> None:
        if _CONTENT_FINGERPRINT_RE.fullmatch(self.content_fingerprint) is None:
            raise ValueError("content fingerprint must be a lowercase sha256 digest")
        if type(self.publication_revision) is not int or self.publication_revision <= 0:
            raise ValueError("Publication revision must be a positive integer")
        if type(self.run_id) is not str or not self.run_id:
            raise ValueError("Run identity must not be blank")
        result = self.result
        if result.locator_kind == "page":
            valid_locator = (
                type(result.locator_start) is int
                and result.locator_start > 0
                and result.locator_end == result.locator_start
            )
        elif result.locator_kind == "timestamp_ms":
            valid_locator = (
                type(result.locator_start) is int
                and type(result.locator_end) is int
                and result.locator_start >= 0
                and result.locator_end > result.locator_start
            )
        else:
            valid_locator = False
        if not valid_locator:
            raise ValueError("Evidence locator is invalid")


@dataclass(frozen=True)
class ActivePublicationObservation:
    library_id: str
    state: str
    source_count: int
    active_publication_count: int
    active_evidence_count: int

    def __post_init__(self) -> None:
        counts = (
            self.source_count,
            self.active_publication_count,
            self.active_evidence_count,
        )
        if self.library_id != "local" or any(
            type(value) is not int or value < 0 for value in counts
        ):
            raise ValueError("active Publication observation is invalid")
        valid = (
            self.state == "empty"
            and counts == (0, 0, 0)
            or self.state == "no_active_publication"
            and self.source_count > 0
            and self.active_publication_count == 0
            and self.active_evidence_count == 0
            or self.state == "active"
            and self.source_count > 0
            and self.active_publication_count > 0
            and self.active_evidence_count > 0
            and self.active_publication_count <= self.source_count
            and self.active_publication_count <= self.active_evidence_count
        )
        if not valid:
            raise ValueError("active Publication state does not match its counts")


@dataclass(frozen=True)
class SearchSnapshot:
    observation: ActivePublicationObservation
    results: tuple[SearchResultProvenance, ...]

    def __post_init__(self) -> None:
        if len(self.results) > 20:
            raise ValueError("Search snapshot exceeds the public result limit")
        if self.observation.state != "active" and self.results:
            raise ValueError("Search results require an active Publication observation")
        if len(self.results) > self.observation.active_evidence_count:
            raise ValueError("Search results exceed observed active Evidence")


@dataclass(frozen=True)
class AskSnapshot:
    observation: ActivePublicationObservation
    result: AskResult
    evidence: tuple[SearchResultProvenance, ...]

    def __post_init__(self) -> None:
        if len(self.evidence) > 20:
            raise ValueError("Ask snapshot exceeds the public Evidence limit")
        projected = tuple(item.result for item in self.evidence)
        if projected != self.result.evidence:
            raise ValueError("Ask Evidence provenance projection is inconsistent")
        has_evidence = bool(self.evidence)
        if self.result.answer_status == "evidence_found":
            valid_status = has_evidence
        elif self.result.answer_status == "insufficient_evidence":
            valid_status = not has_evidence
        else:
            valid_status = False
        if not valid_status:
            raise ValueError("Ask answer status does not match Evidence")
        if self.observation.state != "active" and has_evidence:
            raise ValueError("Ask Evidence requires an active Publication observation")
        if len(self.evidence) > self.observation.active_evidence_count:
            raise ValueError("Ask Evidence exceeds observed active Evidence")


REQUIRED_PDF_STAGES = frozenset({"pdf_text_extraction", "candidate_evidence"})
PDF_EXTRACTOR_FINGERPRINT = "builtin-pdf-text-v1"
PYMUPDF_TEXT_FINGERPRINT = "pymupdf-text-v1"
REQUIRED_VIDEO_STAGES = frozenset({"video_transcription", "candidate_evidence"})
VIDEO_TRANSCRIPT_FINGERPRINT = "builtin-video-transcript-v1"
LOCAL_COMMAND_VIDEO_TRANSCRIPT_FINGERPRINT = "local-command-video-transcript-v1"
_FASTER_WHISPER_FINGERPRINT_RE = re.compile(r"faster-whisper-v1:[0-9a-f]{64}\Z")
_PDF_OCR_EVALUATION_FINGERPRINT_RE = re.compile(r"pdf-ocr-eval-v1:[0-9a-f]{64}\Z")
_REQUIRED_PDF_OCR_EVALUATION_STAGES = frozenset(
    {"pdf_ocr_extraction", "candidate_evidence"}
)


def is_recognized_video_fingerprint(value: str) -> bool:
    return (
        value
        in {
            VIDEO_TRANSCRIPT_FINGERPRINT,
            LOCAL_COMMAND_VIDEO_TRANSCRIPT_FINGERPRINT,
        }
        or _FASTER_WHISPER_FINGERPRINT_RE.fullmatch(value) is not None
    )


def validate_manifest(manifest: RunManifest, evidence: list[CandidateEvidence]) -> None:
    """Validate candidate Evidence before it can change active Search visibility."""
    if manifest.evidence_count != len(evidence):
        raise ManifestValidationError(
            "RunManifest evidence count does not match candidate Evidence"
        )
    if manifest.extractor_fingerprint in {
        PDF_EXTRACTOR_FINGERPRINT,
        PYMUPDF_TEXT_FINGERPRINT,
    }:
        expected_stages = REQUIRED_PDF_STAGES
        expected_locator_kind = "page"
    elif is_recognized_video_fingerprint(manifest.extractor_fingerprint):
        expected_stages = REQUIRED_VIDEO_STAGES
        expected_locator_kind = "timestamp_ms"
    elif _PDF_OCR_EVALUATION_FINGERPRINT_RE.fullmatch(manifest.extractor_fingerprint):
        expected_stages = _REQUIRED_PDF_OCR_EVALUATION_STAGES
        expected_locator_kind = "page"
    else:
        raise ManifestValidationError("RunManifest extractor fingerprint is not recognized")
    if (
        len(manifest.required_stages) != len(set(manifest.required_stages))
        or frozenset(manifest.required_stages) != expected_stages
    ):
        raise ManifestValidationError("RunManifest required stages are incomplete")
    if len(manifest.asset_sha256) != 64:
        raise ManifestValidationError("RunManifest asset sha256 must be a hex digest")
    for item in evidence:
        if item.locator_kind != expected_locator_kind:
            raise ManifestValidationError(f"Evidence locator kind must be {expected_locator_kind}")
        if item.locator_kind == "page" and (
            item.locator_start < 1 or item.locator_end < item.locator_start
        ):
            raise ManifestValidationError("Evidence page locator must use positive page numbers")
        if item.locator_kind == "timestamp_ms" and (
            item.locator_start < 0 or item.locator_end <= item.locator_start
        ):
            raise ManifestValidationError(
                "Evidence timestamp locator must use non-negative increasing millisecond ranges"
            )
        if not item.text.strip():
            raise ManifestValidationError("Evidence text must not be empty")


from .library_export import (  # noqa: E402
    DEFAULT_EXPORT_LIMITS,
    CompiledEvidenceSnapshot,
    CompiledLibrarySnapshot,
    CompiledSourceSnapshot,
    ExportLimits,
    LibraryExportDataError,
)

_LIBRARY_EXPORT_CONTRACTS = (
    DEFAULT_EXPORT_LIMITS,
    CompiledEvidenceSnapshot,
    CompiledLibrarySnapshot,
    CompiledSourceSnapshot,
    ExportLimits,
    LibraryExportDataError,
)
