"""Application service for the narrow local Evidence ingest and Search path."""

from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from mke.adapters.pdf import PdfExtractionError, PyMuPDFPdfExtractor
from mke.adapters.sqlite import InjectedStorageFailure, SQLiteStore
from mke.adapters.video import SidecarTranscriptProvider, VideoExtractionError
from mke.domain import (
    PYMUPDF_TEXT_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    REQUIRED_VIDEO_STAGES,
    ActivationResult,
    AskResult,
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
    SearchResult,
    SourceRecord,
    TranscriptExtractionResult,
)

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

    def __init__(self, message: str, run_id: str | None = None) -> None:
        super().__init__(message)
        self.run_id = run_id


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
    ) -> None:
        self._store = SQLiteStore(db_path)
        self._pdf_extractor = pdf_extractor or PyMuPDFPdfExtractor()
        self._transcript_provider = transcript_provider or SidecarTranscriptProvider()

    def close(self) -> None:
        self._store.close()

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

    def persist_validated_candidate(
        self, run_id: str, evidence: list[CandidateEvidence], manifest: RunManifest
    ) -> None:
        self._store.persist_validated_candidate(run_id, evidence, manifest)

    def activate_publication(
        self, run_id: str, failure_point: FailurePoint | None = None
    ) -> ActivationResult:
        return self._store.activate_publication(run_id, failure_point=failure_point)

    def search(self, query: str, limit: int | None = None) -> list[SearchResult]:
        return self._store.search(query, limit=limit)

    def ask(self, question: str, limit: int = DEFAULT_ASK_LIMIT) -> AskResult:
        normalized_question = _normalize_ask_question(question)
        if type(limit) is not int or limit < MIN_ASK_LIMIT or limit > MAX_ASK_LIMIT:
            raise AskValidationError(
                "invalid_query",
                f"limit must be between {MIN_ASK_LIMIT} and {MAX_ASK_LIMIT}",
                "choose_limit_between_1_and_20",
            )
        evidence = self.search(normalized_question, limit=limit)
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
        if not path.exists():
            raise VideoIngestError("input video is missing")
        asset_sha256 = _sha256_file(path)
        source = self.ensure_source(
            display_name=path.name,
            asset_sha256=asset_sha256,
            media_type="video/mp4",
        )
        run = self.create_run(source.source_id)
        self._store.mark_run_running(run.run_id)
        try:
            transcript = self._transcript_provider.extract(path)
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
            activation = self.activate_publication(run.run_id)
            return IngestResult(
                run_id=run.run_id,
                run_state=activation.run_state,
                evidence_count=len(evidence) if activation.published else 0,
            )
        except (VideoExtractionError, ManifestValidationError, InjectedStorageFailure) as error:
            self._store.mark_run_failed(run.run_id)
            raise VideoIngestError(str(error), run.run_id) from error


def _normalize_ask_question(question: str) -> str:
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
