"""Application service for the narrow local Evidence ingest and Search path."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from mke.adapters.pdf import PdfExtractionError, extract_text_pages
from mke.adapters.sqlite import InjectedStorageFailure, SQLiteStore
from mke.adapters.video import VideoExtractionError, extract_transcript_segments
from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    REQUIRED_VIDEO_STAGES,
    VIDEO_TRANSCRIPT_FINGERPRINT,
    ActivationResult,
    CandidateEvidence,
    FailurePoint,
    IngestResult,
    ManifestValidationError,
    RunEvent,
    RunManifest,
    RunRecord,
    RunState,
    SearchResult,
    SourceRecord,
)

_SHA256_CHUNK_BYTES = 1024 * 1024


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


class KnowledgeEngine:
    """Project-owned application facade shared by CLI and future interfaces."""

    def __init__(self, db_path: Path) -> None:
        self._store = SQLiteStore(db_path)

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

    def persist_validated_candidate(
        self, run_id: str, evidence: list[CandidateEvidence], manifest: RunManifest
    ) -> None:
        self._store.persist_validated_candidate(run_id, evidence, manifest)

    def activate_publication(
        self, run_id: str, failure_point: FailurePoint | None = None
    ) -> ActivationResult:
        return self._store.activate_publication(run_id, failure_point=failure_point)

    def search(self, query: str) -> list[SearchResult]:
        return self._store.search(query)

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
            pages = extract_text_pages(path)
            evidence = [
                CandidateEvidence(
                    evidence_id=f"ev_{uuid4().hex}",
                    locator_kind="page",
                    locator_start=page.page_number,
                    locator_end=page.page_number,
                    text=page.text,
                )
                for page in pages
            ]
            manifest = RunManifest(
                run_id=run.run_id,
                evidence_count=len(evidence),
                required_stages=tuple(sorted(REQUIRED_PDF_STAGES)),
                extractor_fingerprint=PDF_EXTRACTOR_FINGERPRINT,
                asset_sha256=asset_sha256,
            )
            self._store.persist_validated_candidate(
                run.run_id,
                evidence,
                manifest,
                failure_point=failure_point,
            )
            if not activate:
                return IngestResult(run.run_id, RunState.VALIDATED, len(evidence), retry_of_run_id)
            activation = self.activate_publication(run.run_id, failure_point=failure_point)
            return IngestResult(
                run_id=run.run_id,
                run_state=activation.run_state,
                evidence_count=len(evidence) if activation.published else 0,
                retry_of_run_id=retry_of_run_id,
            )
        except (PdfExtractionError, ManifestValidationError, InjectedStorageFailure) as error:
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
            segments = extract_transcript_segments(path)
            evidence = [
                CandidateEvidence(
                    evidence_id=f"ev_{uuid4().hex}",
                    locator_kind="timestamp_ms",
                    locator_start=segment.start_ms,
                    locator_end=segment.end_ms,
                    text=segment.text,
                )
                for segment in segments
            ]
            manifest = RunManifest(
                run_id=run.run_id,
                evidence_count=len(evidence),
                required_stages=tuple(sorted(REQUIRED_VIDEO_STAGES)),
                extractor_fingerprint=VIDEO_TRANSCRIPT_FINGERPRINT,
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


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_SHA256_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()
