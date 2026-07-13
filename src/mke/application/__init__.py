"""Application service for the narrow local Evidence ingest and Search path."""

from __future__ import annotations

import re
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from mke.adapters.pdf import PdfExtractionError, PyMuPDFPdfExtractor
from mke.adapters.sqlite import InjectedStorageFailure, SQLiteStore
from mke.adapters.video import SidecarTranscriptProvider
from mke.adapters.video.contracts import (
    VideoTranscriptionLimits,
    build_transcript_intake_report,
    faster_whisper_fingerprint,
)
from mke.domain import (
    PYMUPDF_TEXT_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    REQUIRED_VIDEO_STAGES,
    ActivationResult,
    ActiveEvidenceRef,
    ActivePublicationObservation,
    AskResult,
    AskSnapshot,
    CandidateEvidence,
    FailurePoint,
    IngestResult,
    ManifestValidationError,
    PdfExtractionResult,
    PdfIntakeReport,
    RunEvent,
    RunManifest,
    RunRecord,
    RunState,
    RunTransitionError,
    SearchResult,
    SearchSnapshot,
    SourceRecord,
    TranscriptExtractionResult,
    TranscriptIntakeReport,
)
from mke.retrieval import (
    DEFAULT_RETRIEVAL_STRATEGY,
    RetrievalQueryPolicy,
    RetrievalStrategy,
)
from mke.retrieval.cjk_active_scan import CjkActiveScanError, compile_cjk_overlap_terms
from mke.retrieval.query_policy import require_retrieval_query_policy
from mke.retrieval.strategy import require_retrieval_strategy

_SHA256_CHUNK_BYTES = 1024 * 1024
DEFAULT_ASK_LIMIT = 5
MIN_ASK_LIMIT = 1
MAX_ASK_LIMIT = 20
_MAX_ASK_QUESTION_CHARS = 1000
_SEARCHABLE_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
_MODEL_FREE_LIMITATION = "No model-generated answer is produced in this slice."
_COUNT_ONLY_LIMITATION = (
    "The summary is deterministic and only reports matched Evidence count."
)
_VIDEO_TRANSCRIPTION_LIMITS = VideoTranscriptionLimits()


class PdfExtractor(Protocol):
    def extract(self, path: Path) -> PdfExtractionResult:
        raise NotImplementedError


class TranscriptProvider(Protocol):
    def extract(self, path: Path) -> TranscriptExtractionResult:
        raise NotImplementedError


class PdfIngestError(ValueError):
    """Raised when the PDF happy path cannot produce publishable Evidence."""

    def __init__(self, message: str, run_id: str | None = None) -> None:
        super().__init__(message)
        self.run_id = run_id


class VideoIngestError(ValueError):
    """Raised when the video path cannot produce publishable Evidence."""

    def __init__(
        self,
        message: str,
        run_id: str | None = None,
        *,
        problem: str = "video_ingest_failed",
        next_step: str = "fix_input_or_retry",
    ) -> None:
        super().__init__(message)
        self.run_id = run_id
        self.problem = problem
        self.next_step = next_step


class AskValidationError(ValueError):
    """Raised when an Ask request cannot be evaluated safely."""

    def __init__(self, problem: str, cause: str, next_step: str) -> None:
        super().__init__(cause)
        self.problem = problem
        self.cause = cause
        self.next_step = next_step


class KnowledgeEngine:
    """Project-owned application facade shared by CLI and future interfaces."""

    def __init__(
        self,
        db_path: Path,
        pdf_extractor: PdfExtractor | None = None,
        transcript_provider: TranscriptProvider | None = None,
        *,
        query_policy: RetrievalQueryPolicy | None = None,
        retrieval_strategy: RetrievalStrategy | None = None,
        search_observer: Callable[[int], None] | None = None,
        recover_unfinished_runs: bool = True,
    ) -> None:
        selected_strategy = _normalize_retrieval_strategy(
            retrieval_strategy,
            query_policy=query_policy,
        )
        self._store = SQLiteStore(
            db_path,
            query_policy=query_policy,
            retrieval_strategy=selected_strategy,
            search_observer=search_observer,
        )
        self._retrieval_strategy: RetrievalStrategy = selected_strategy
        self._pdf_extractor = pdf_extractor or PyMuPDFPdfExtractor()
        self._transcript_provider = transcript_provider or SidecarTranscriptProvider()
        if recover_unfinished_runs:
            self.recover_unfinished_runs()

    def close(self) -> None:
        self._store.close()

    def recover_unfinished_runs(self) -> None:
        self._store.interrupt_unfinished_runs()

    def ensure_source(
        self, display_name: str, asset_sha256: str, media_type: str = "application/pdf"
    ) -> SourceRecord:
        return self._store.ensure_source(display_name, asset_sha256, media_type=media_type)

    def create_run(self, source_id: str, retry_of_run_id: str | None = None) -> RunRecord:
        return self._store.create_run(source_id, retry_of_run_id=retry_of_run_id)

    def get_run(self, run_id: str) -> RunRecord:
        return self._store.get_run(run_id)

    def get_run_events(self, run_id: str) -> list[RunEvent]:
        return self._store.get_run_events(run_id)

    def get_pdf_intake_report(self, run_id: str) -> PdfIntakeReport | None:
        return self._store.get_pdf_intake_report(run_id)

    def get_transcript_intake_report(
        self, run_id: str
    ) -> TranscriptIntakeReport | None:
        return self._store.get_transcript_intake_report(run_id)

    def persist_validated_candidate(
        self, run_id: str, evidence: list[CandidateEvidence], manifest: RunManifest
    ) -> None:
        if self.get_run(run_id).state is RunState.QUEUED:
            self._store.mark_run_running(run_id)
        self._store.persist_validated_candidate(run_id, evidence, manifest)

    def activate_publication(
        self, run_id: str, failure_point: FailurePoint | None = None
    ) -> ActivationResult:
        return self._store.activate_publication(run_id, failure_point=failure_point)

    def list_active_evidence(self) -> list[ActiveEvidenceRef]:
        """Return active Evidence for internal diagnostics and evaluation."""
        return self._store.list_active_evidence()

    def search(self, query: str, limit: int | None = None) -> list[SearchResult]:
        return self._store.search(query, limit=limit)

    def observe_active_publications(self) -> ActivePublicationObservation:
        return self._store.observe_active_publications()

    def search_provenance_snapshot(
        self, query: str, limit: int | None = None
    ) -> SearchSnapshot:
        return self._store.search_provenance_snapshot(query, limit=limit)

    def ask(self, question: str, limit: int = DEFAULT_ASK_LIMIT) -> AskResult:
        normalized_question = _normalize_ask_question(
            question,
            retrieval_strategy=self._retrieval_strategy,
        )
        if type(limit) is not int or limit < MIN_ASK_LIMIT or limit > MAX_ASK_LIMIT:
            raise AskValidationError(
                "invalid_query",
                f"limit must be between {MIN_ASK_LIMIT} and {MAX_ASK_LIMIT}",
                "choose_limit_between_1_and_20",
            )
        evidence = self.search(normalized_question, limit=limit)
        return _ask_result(normalized_question, evidence)

    def ask_provenance_snapshot(
        self, question: str, limit: int = DEFAULT_ASK_LIMIT
    ) -> AskSnapshot:
        normalized_question = _normalize_ask_question(
            question,
            retrieval_strategy=self._retrieval_strategy,
        )
        if type(limit) is not int or limit < MIN_ASK_LIMIT or limit > MAX_ASK_LIMIT:
            raise AskValidationError(
                "invalid_query",
                f"limit must be between {MIN_ASK_LIMIT} and {MAX_ASK_LIMIT}",
                "choose_limit_between_1_and_20",
            )
        snapshot = self.search_provenance_snapshot(normalized_question, limit=limit)
        result = _ask_result(
            normalized_question, [item.result for item in snapshot.results]
        )
        return AskSnapshot(snapshot.observation, result, snapshot.results)

    def ingest_pdf(self, path: Path) -> IngestResult:
        return self._process_pdf(path, retry_of_run_id=None, failure_point=None)

    def ingest_video(self, path: Path) -> IngestResult:
        return self._process_video(path)

    def reprocess_pdf(
        self, path: Path, failure_point: FailurePoint | None = None
    ) -> IngestResult:
        return self._process_pdf(
            path,
            retry_of_run_id=None,
            failure_point=failure_point,
            reuse_existing_source=True,
        )

    def retry_pdf(self, failed_run_id: str, path: Path) -> IngestResult:
        failed = self.get_run(failed_run_id)
        return self._process_pdf(
            path,
            retry_of_run_id=failed.run_id,
            source_id=failed.source_id,
            failure_point=None,
        )

    def prepare_pdf_candidate(
        self,
        path: Path,
        *,
        leave_running_for_test: bool = False,
        reuse_existing_source: bool = True,
    ) -> IngestResult:
        return self._process_pdf(
            path,
            retry_of_run_id=None,
            failure_point=None,
            activate=False,
            leave_running_for_test=leave_running_for_test,
            reuse_existing_source=reuse_existing_source,
        )

    def _process_pdf(
        self,
        path: Path,
        *,
        retry_of_run_id: str | None,
        failure_point: FailurePoint | None,
        source_id: str | None = None,
        activate: bool = True,
        leave_running_for_test: bool = False,
        reuse_existing_source: bool = False,
    ) -> IngestResult:
        asset_sha256 = _sha256_file(path)
        source = self._select_source(path, asset_sha256, source_id, reuse_existing_source)
        run = self.create_run(source.source_id, retry_of_run_id=retry_of_run_id)
        self._store.mark_run_running(run.run_id)
        if leave_running_for_test:
            return IngestResult(run.run_id, RunState.RUNNING, 0, retry_of_run_id)
        try:
            if failure_point == FailurePoint.BEFORE_VALIDATION:
                raise InjectedStorageFailure(failure_point.value)
            extraction = self._pdf_extractor.extract(path)
            evidence = [
                CandidateEvidence(
                    evidence_id=f"ev_{uuid4().hex}",
                    locator_kind="page",
                    locator_start=page.page_number,
                    locator_end=page.page_number,
                    text=page.text,
                )
                for page in extraction.pages
            ]
            manifest = RunManifest(
                run_id=run.run_id,
                evidence_count=len(evidence),
                required_stages=tuple(sorted(REQUIRED_PDF_STAGES)),
                extractor_fingerprint=PYMUPDF_TEXT_FINGERPRINT,
                asset_sha256=asset_sha256,
            )
            self._store.persist_validated_candidate(
                run.run_id,
                evidence,
                manifest,
                failure_point=failure_point,
            )
            if not activate:
                self._store.persist_pdf_intake_report(run.run_id, extraction.report)
                return IngestResult(
                    run.run_id,
                    RunState.VALIDATED,
                    len(evidence),
                    retry_of_run_id,
                    extraction.report,
                )
            activation = self.activate_publication(run.run_id, failure_point=failure_point)
            if activation.published:
                self._store.persist_pdf_intake_report(run.run_id, extraction.report)
            return IngestResult(
                run_id=run.run_id,
                run_state=activation.run_state,
                evidence_count=len(evidence) if activation.published else 0,
                retry_of_run_id=retry_of_run_id,
                intake_report=extraction.report,
            )
        except RunTransitionError as error:
            raise PdfIngestError(str(error), run.run_id) from error
        except (PdfExtractionError, ManifestValidationError, InjectedStorageFailure) as error:
            if isinstance(error, PdfExtractionError) and error.report is not None:
                self._store.persist_pdf_intake_report(run.run_id, error.report)
            if failure_point in {
                FailurePoint.AFTER_PUBLICATION_INSERT,
                FailurePoint.DURING_ACTIVE_FTS_REPLACEMENT,
                FailurePoint.AFTER_ACTIVE_POINTER_SWITCH,
            }:
                raise PdfIngestError(str(error), run.run_id) from error
            self._store.mark_run_failed(run.run_id)
            raise PdfIngestError(str(error), run.run_id) from error

    def _select_source(
        self,
        path: Path,
        asset_sha256: str,
        source_id: str | None,
        reuse_existing_source: bool,
    ) -> SourceRecord:
        if source_id is not None:
            return self._store.get_source(source_id)
        if reuse_existing_source:
            existing = self._store.get_first_source()
            if existing is not None:
                return existing
        return self.ensure_source(display_name=path.name, asset_sha256=asset_sha256)

    def _process_video(self, path: Path) -> IngestResult:
        run: RunRecord | None = None
        try:
            try:
                _validate_video_input(path, _VIDEO_TRANSCRIPTION_LIMITS)
                asset_sha256 = _sha256_file(path)
            except VideoIngestError:
                raise
            except OSError as error:
                raise VideoIngestError("input video could not be read") from error
            source = self.ensure_source(
                display_name=path.name,
                asset_sha256=asset_sha256,
                media_type="video/mp4",
            )
            run = self.create_run(source.source_id)
            self._store.mark_run_running(run.run_id)
            transcript = self._transcript_provider.extract(path)
            _validate_transcript_extraction_result(transcript)
            evidence = [
                CandidateEvidence(
                    evidence_id=f"ev_{uuid4().hex}",
                    locator_kind="timestamp_ms",
                    locator_start=segment.start_ms,
                    locator_end=segment.end_ms,
                    text=segment.text,
                )
                for segment in transcript.segments
            ]
            manifest = RunManifest(
                run_id=run.run_id,
                evidence_count=len(evidence),
                required_stages=tuple(sorted(REQUIRED_VIDEO_STAGES)),
                extractor_fingerprint=transcript.extractor_fingerprint,
                asset_sha256=asset_sha256,
            )
            self._store.persist_validated_candidate(run.run_id, evidence, manifest)
            activation = self._store.activate_publication(
                run.run_id,
                transcript_intake_report=transcript.transcript_intake_report,
            )
            return IngestResult(
                run_id=run.run_id,
                run_state=activation.run_state,
                evidence_count=len(evidence) if activation.published else 0,
                transcript_intake_report=(
                    transcript.transcript_intake_report if activation.published else None
                ),
            )
        except RunTransitionError as error:
            assert run is not None
            raise VideoIngestError(
                str(error),
                run.run_id,
                problem="video_ingest_failed",
                next_step="retry_when_owner_ready",
            ) from error
        except Exception as error:
            if run is None:
                if isinstance(error, VideoIngestError):
                    raise
                raise VideoIngestError("video ingest initialization failed") from error
            try:
                self._store.mark_run_failed(run.run_id)
            except Exception:
                pass
            raise VideoIngestError(
                str(error),
                run.run_id,
                problem=getattr(error, "problem", "video_ingest_failed"),
                next_step=getattr(error, "next_step", "fix_input_or_retry"),
            ) from error


def _ask_result(normalized_question: str, evidence: list[SearchResult]) -> AskResult:
    if evidence:
        return AskResult(
            ask_id=f"ask_{uuid4().hex}",
            question=normalized_question,
            answer_status="evidence_found",
            summary=_matched_summary(len(evidence)),
            evidence=tuple(evidence),
            limitations=(_MODEL_FREE_LIMITATION, _COUNT_ONLY_LIMITATION),
        )
    return AskResult(
        ask_id=f"ask_{uuid4().hex}",
        question=normalized_question,
        answer_status="insufficient_evidence",
        summary="No active Evidence matched the search terms.",
        evidence=(),
        limitations=(
            "No answer is produced because no active Evidence matched the search terms.",
            _MODEL_FREE_LIMITATION,
        ),
    )


def _validate_video_input(path: Path, limits: VideoTranscriptionLimits) -> None:
    if not path.exists():
        raise VideoIngestError("input video is missing")
    if not path.is_file() or path.suffix.lower() != ".mp4":
        raise VideoIngestError("input video must be an MP4 file")
    size = path.stat().st_size
    if size == 0:
        raise VideoIngestError("input video is empty")
    if size > limits.max_input_bytes:
        raise VideoIngestError("video input exceeds 100 MiB limit")


def _validate_transcript_extraction_result(
    result: TranscriptExtractionResult,
) -> None:
    report = result.transcript_intake_report
    if report is None:
        return
    try:
        expected_report = build_transcript_intake_report(result.parsed_transcript)
    except ValueError as error:
        raise ManifestValidationError(
            "successful transcript report requires validated provenance"
        ) from error
    if report != expected_report:
        raise ManifestValidationError(
            "transcript intake report does not match parsed transcript"
        )
    provenance = result.parsed_transcript.transcription_provenance
    assert provenance is not None
    if result.extractor_fingerprint != faster_whisper_fingerprint(provenance):
        raise ManifestValidationError(
            "transcript extractor fingerprint does not match provenance"
        )


def _normalize_retrieval_strategy(
    retrieval_strategy: RetrievalStrategy | None,
    *,
    query_policy: RetrievalQueryPolicy | None,
) -> RetrievalStrategy:
    if retrieval_strategy is not None:
        return require_retrieval_strategy(retrieval_strategy)
    if query_policy is not None:
        return require_retrieval_strategy(
            require_retrieval_query_policy(query_policy)
        )
    return DEFAULT_RETRIEVAL_STRATEGY


def _normalize_ask_question(
    question: str,
    *,
    retrieval_strategy: RetrievalStrategy = DEFAULT_RETRIEVAL_STRATEGY,
) -> str:
    if not isinstance(question, str):  # pyright: ignore[reportUnnecessaryIsInstance] -- runtime guard
        raise AskValidationError(
            "invalid_question",
            "question must be a string",
            "provide_string_question",
        )
    normalized_question = question.strip()
    if not normalized_question:
        raise AskValidationError(
            "invalid_question",
            "question must not be empty",
            "provide_non_empty_question",
        )
    if len(normalized_question) > _MAX_ASK_QUESTION_CHARS:
        raise AskValidationError(
            "invalid_question",
            f"question must be {_MAX_ASK_QUESTION_CHARS} characters or fewer",
            "shorten_question",
        )
    if _SEARCHABLE_TOKEN_RE.search(normalized_question) is None:
        if retrieval_strategy == "cjk-active-scan-overlap-v1":
            try:
                compile_cjk_overlap_terms(normalized_question, require_terms=True)
            except CjkActiveScanError:
                pass
            else:
                return normalized_question
        raise AskValidationError(
            "invalid_question",
            "question must contain at least one searchable ASCII token",
            "provide_searchable_question",
        )
    return normalized_question


def _matched_summary(evidence_count: int) -> str:
    noun = "item" if evidence_count == 1 else "items"
    return f"{evidence_count} active Evidence {noun} matched the search terms."


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_SHA256_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()
