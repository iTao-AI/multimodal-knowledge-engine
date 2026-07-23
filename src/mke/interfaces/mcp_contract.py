"""Pure MCP tool contracts backed by the project-owned KnowledgeEngine."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from mke.application import (
    DEFAULT_ASK_LIMIT,
    MAX_ASK_LIMIT,
    MIN_ASK_LIMIT,
    AskValidationError,
    AudioIngestError,
    IngestDispatchError,
    IngestFileAuthorityError,
    KnowledgeEngine,
    PdfIngestError,
    VideoIngestError,
)
from mke.domain import (
    ActivePublicationObservation,
    PdfIntakeReport,
    SearchResult,
    SearchResultProvenance,
    TranscriptIntakeReport,
)
from mke.interfaces.audio_errors import DIRECT_AUDIO_SAFE_CAUSES
from mke.interfaces.input_authority import (
    BoundInputFile,
    bind_allowed_file,
    bind_optional_allowed_file,
)
from mke.interfaces.mcp_schemas import (
    ActivePublicationObservationV1,
    AskLibraryErrorV1,
    AskLibraryResponseV1,
    AskLibrarySuccessV1,
    EvidenceRefV1,
    ListLibrariesResponseV1,
    ListLibrariesSuccessV1,
    PageLocatorV1,
    SearchLibraryErrorV1,
    SearchLibraryResponseV1,
    SearchLibrarySuccessV1,
    TimestampLocatorV1,
)
from mke.interfaces.public_errors import public_error_from_cause
from mke.retrieval.cjk_active_scan import CjkActiveScanError
from mke.runtime import RuntimeConfig, SidecarTranscriptionConfig, build_engine

logger = logging.getLogger(__name__)

_MAX_PDF_INPUT_BYTES = 100 * 1024 * 1024

_SUPPORTED_SUFFIX_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".mp4": "video/mp4",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
}
_INGEST_LOCAL_SAFE_CAUSES = DIRECT_AUDIO_SAFE_CAUSES | frozenset(
    {"input path must not be a symlink"}
)


@dataclass(frozen=True)
class McpRuntimeConfig:
    runtime: RuntimeConfig
    allowed_root: Path

    @property
    def db_path(self) -> Path:
        return self.runtime.db_path


def list_libraries() -> dict[str, Any]:
    return {
        "libraries": [
            {
                "library_id": "local",
                "name": "Local Library",
                "status": "implicit",
                "active_publication_scope": "source",
            }
        ]
    }


def ingest_file(config: McpRuntimeConfig, path: str) -> dict[str, Any]:
    try:
        bound_input = _resolve_allowed_file(config, path)
    except ValueError as error:
        return _ingest_failure(
            "input_path_rejected",
            str(error),
            "choose_file_under_allowed_root",
        )
    except OSError:
        logger.exception("path resolution failed")
        return _ingest_failure(
            "input_path_rejected",
            "file path cannot be resolved",
            "choose_file_under_allowed_root",
        )

    engine: KnowledgeEngine | None = None
    try:
        suffix = bound_input.path.suffix.lower()
        if suffix == ".pdf" and bound_input.byte_count > _MAX_PDF_INPUT_BYTES:
            return _ingest_failure(
                "input_file_too_large",
                "PDF input exceeds 100 MB limit",
                "choose_smaller_file",
            )
        engine = build_engine(config.runtime)
        try:
            result = engine.ingest_file(
                bound_input.path,
                input_authority=bound_input,
            )
        except IngestFileAuthorityError:
            return _ingest_failure(
                "input_path_rejected",
                "input path changed during validation",
                "choose_file_under_allowed_root",
            )
        except PdfIngestError as error:
            return _failure(
                "pdf_ingest_failed",
                str(error),
                "fix_input_or_retry",
                run_id=error.run_id,
            )
        except VideoIngestError as error:
            return _ingest_failure(
                error.problem,
                str(error),
                error.next_step,
                run_id=error.run_id,
            )
        except AudioIngestError as error:
            return _ingest_failure(
                error.problem,
                error.cause,
                error.next_step,
                run_id=error.run_id,
            )
        except IngestDispatchError as error:
            return _ingest_failure(
                error.problem,
                error.cause,
                error.next_step,
            )
        media_type = _SUPPORTED_SUFFIX_MEDIA_TYPES.get(suffix)
        if media_type is None:
            return _ingest_failure(
                "unsupported_media_type",
                "supported suffixes are .pdf, .mp4, .mp3, .wav, and .m4a",
                "choose_supported_file",
            )
        payload: dict[str, Any] = {
            "ok": True,
            "run_id": result.run_id,
            "run_state": result.run_state.value,
            "evidence_count": result.evidence_count,
            "media_type": media_type,
            "active_publication_impact": (
                "changed" if result.run_state.value == "published" else "unchanged"
            ),
        }
        if result.intake_report is not None:
            payload["intake_report"] = _pdf_intake_report_payload(result.intake_report)
        if result.transcript_intake_report is not None:
            payload["transcript_intake_report"] = transcript_intake_report_payload(
                result.transcript_intake_report
            )
        return payload
    finally:
        try:
            if engine is not None:
                engine.close()
        finally:
            bound_input.close()


def get_run(config: McpRuntimeConfig, run_id: str) -> dict[str, Any]:
    engine: KnowledgeEngine | None = None
    try:
        engine = build_engine(config.runtime)
        try:
            run = engine.get_run(run_id)
        except KeyError:
            return _failure(
                "run_not_found",
                "unknown run",
                "check_run_id",
                run_id=run_id,
            )
        events = [
            {"event_index": event.event_index, "event": event.event_type}
            for event in engine.get_run_events(run_id)
        ]
        payload: dict[str, Any] = {
            "ok": True,
            "run": {
                "run_id": run.run_id,
                "state": run.state.value,
                "source_generation": run.source_generation,
                "retry_of_run_id": run.retry_of_run_id,
            },
            "events": events,
        }
        report = engine.get_pdf_intake_report(run_id)
        if report is not None:
            payload["intake_report"] = _pdf_intake_report_payload(report)
        transcript_report = engine.get_transcript_intake_report(run_id)
        if transcript_report is not None:
            payload["transcript_intake_report"] = transcript_intake_report_payload(
                transcript_report
            )
        return payload
    finally:
        if engine is not None:
            engine.close()


def search_library(
    config: McpRuntimeConfig, query: str, limit: int = DEFAULT_ASK_LIMIT
) -> dict[str, Any]:
    normalized_query = query.strip()
    if not normalized_query:
        return _failure("invalid_query", "query must not be empty", "provide_non_empty_query")
    if type(limit) is not int or limit < MIN_ASK_LIMIT or limit > MAX_ASK_LIMIT:
        return _failure(
            "invalid_query",
            f"limit must be between {MIN_ASK_LIMIT} and {MAX_ASK_LIMIT}",
            "choose_limit_between_1_and_20",
        )

    engine: KnowledgeEngine | None = None
    try:
        engine = build_engine(config.runtime)
        try:
            matches = engine.search(normalized_query, limit=limit)
        except CjkActiveScanError as error:
            return _failure(error.problem, error.cause, error.next_step)
        results = [_evidence_from_search_result(match) for match in matches]
        return {"ok": True, "query": normalized_query, "results": results}
    finally:
        if engine is not None:
            engine.close()


def ask_library(
    config: McpRuntimeConfig, question: str, limit: int = DEFAULT_ASK_LIMIT
) -> dict[str, Any]:
    normalized_question = question.strip()
    if not normalized_question:
        return _failure(
            "invalid_question",
            "question must not be empty",
            "provide_non_empty_question",
        )
    if type(limit) is not int or limit < MIN_ASK_LIMIT or limit > MAX_ASK_LIMIT:
        return _failure(
            "invalid_query",
            f"limit must be between {MIN_ASK_LIMIT} and {MAX_ASK_LIMIT}",
            "choose_limit_between_1_and_20",
        )
    engine: KnowledgeEngine | None = None
    try:
        engine = build_engine(config.runtime)
        try:
            result = engine.ask(question, limit=limit)
        except (AskValidationError, CjkActiveScanError) as error:
            return _failure(error.problem, error.cause, error.next_step)
        return {
            "ok": True,
            "ask_id": result.ask_id,
            "question": result.question,
            "answer_status": result.answer_status,
            "summary": result.summary,
            "evidence": [_evidence_from_search_result(match) for match in result.evidence],
            "limitations": list(result.limitations),
        }
    finally:
        if engine is not None:
            engine.close()


def list_libraries_v1(config: McpRuntimeConfig) -> ListLibrariesResponseV1:
    engine: KnowledgeEngine | None = None
    try:
        engine = build_engine(config.runtime)
        return ListLibrariesResponseV1(
            root=ListLibrariesSuccessV1(
                observation=_observation_v1(engine.observe_active_publications())
            )
        )
    finally:
        if engine is not None:
            engine.close()


def search_library_v1(
    config: McpRuntimeConfig, query: str, limit: int = DEFAULT_ASK_LIMIT
) -> SearchLibraryResponseV1:
    normalized_query = query.strip()
    if not normalized_query:
        return SearchLibraryResponseV1(
            root=SearchLibraryErrorV1(
                ok=False,
                problem="invalid_query",
                cause="query must not be empty",
                next_step="provide_non_empty_query",
            )
        )
    if type(limit) is not int or not MIN_ASK_LIMIT <= limit <= MAX_ASK_LIMIT:
        return SearchLibraryResponseV1(
            root=SearchLibraryErrorV1(
                ok=False,
                problem="invalid_query",
                cause=f"limit must be between {MIN_ASK_LIMIT} and {MAX_ASK_LIMIT}",
                next_step="choose_limit_between_1_and_20",
            )
        )
    engine: KnowledgeEngine | None = None
    try:
        engine = build_engine(config.runtime)
        snapshot = engine.search_provenance_snapshot(normalized_query, limit=limit)
        return SearchLibraryResponseV1(
            root=SearchLibrarySuccessV1(
                query=normalized_query,
                observation=_observation_v1(snapshot.observation),
                results=[_evidence_ref_v1(item) for item in snapshot.results],
            )
        )
    except (AskValidationError, CjkActiveScanError) as error:
        return SearchLibraryResponseV1(
            root=SearchLibraryErrorV1(
                ok=False, problem=error.problem, cause=error.cause, next_step=error.next_step
            )
        )
    finally:
        if engine is not None:
            engine.close()


def ask_library_v1(
    config: McpRuntimeConfig, question: str, limit: int = DEFAULT_ASK_LIMIT
) -> AskLibraryResponseV1:
    normalized_question = question.strip()
    if not normalized_question:
        return AskLibraryResponseV1(
            root=AskLibraryErrorV1(
                ok=False,
                problem="invalid_question",
                cause="question must not be empty",
                next_step="provide_non_empty_question",
            )
        )
    engine: KnowledgeEngine | None = None
    try:
        engine = build_engine(config.runtime)
        snapshot = engine.ask_provenance_snapshot(normalized_question, limit=limit)
        return AskLibraryResponseV1(
            root=AskLibrarySuccessV1(
                question=snapshot.result.question,
                answer_status=cast(
                    Literal["evidence_found", "insufficient_evidence"],
                    snapshot.result.answer_status,
                ),
                summary=snapshot.result.summary,
                observation=_observation_v1(snapshot.observation),
                evidence=[_evidence_ref_v1(item) for item in snapshot.evidence],
                limitations=list(snapshot.result.limitations),
            )
        )
    except (AskValidationError, CjkActiveScanError) as error:
        return AskLibraryResponseV1(
            root=AskLibraryErrorV1(
                ok=False, problem=error.problem, cause=error.cause, next_step=error.next_step
            )
        )
    finally:
        if engine is not None:
            engine.close()


def _observation_v1(value: ActivePublicationObservation) -> ActivePublicationObservationV1:
    return ActivePublicationObservationV1(
        state=cast(Literal["empty", "no_active_publication", "active"], value.state),
        source_count=value.source_count,
        active_publication_count=value.active_publication_count,
        active_evidence_count=value.active_evidence_count,
    )


def _evidence_ref_v1(value: SearchResultProvenance) -> EvidenceRefV1:
    result = value.result
    locator = (
        PageLocatorV1(kind="page", start=result.locator_start, end=result.locator_end)
        if result.locator_kind == "page"
        else TimestampLocatorV1(
            kind="timestamp_ms", start=result.locator_start, end=result.locator_end
        )
    )
    return EvidenceRefV1(
        evidence_id=result.evidence_id,
        source_id=result.source_id,
        content_fingerprint=value.content_fingerprint,
        publication_id=result.publication_id,
        publication_revision=value.publication_revision,
        run_id=value.run_id,
        locator=locator,
        text=result.text,
    )


def _evidence_from_search_result(match: SearchResult) -> dict[str, Any]:
    return {
        "evidence_id": match.evidence_id,
        "publication_id": match.publication_id,
        "source_id": match.source_id,
        "locator": {
            "kind": match.locator_kind,
            "start": match.locator_start,
            "end": match.locator_end,
        },
        "text": match.text,
    }


def _pdf_intake_report_payload(report: PdfIntakeReport) -> dict[str, Any]:
    return {
        "total_pages": report.total_pages,
        "extracted_pages": report.extracted_pages,
        "empty_pages": report.empty_pages,
        "total_extracted_chars": report.total_extracted_chars,
        "page_char_counts": list(report.page_char_counts),
        "suspected_scanned_pages": report.suspected_scanned_pages,
        "extraction_mode": report.extraction_mode,
        "failure_reason": report.failure_reason,
    }


def transcript_intake_report_payload(
    report: TranscriptIntakeReport,
) -> dict[str, object]:
    return {
        "provider": report.provider,
        "model": report.model,
        "model_revision": report.model_revision,
        "library_version": report.library_version,
        "device": report.device,
        "compute_type": report.compute_type,
        "language": report.language,
        "detected_language": report.detected_language,
        "media_duration_ms": report.media_duration_ms,
        "transcription_duration_ms": report.transcription_duration_ms,
        "segment_count": report.segment_count,
        "model_source": report.model_source,
    }


def _resolve_allowed_file(config: McpRuntimeConfig, path: str) -> BoundInputFile:
    bound = bind_allowed_file(config.allowed_root, path)
    try:
        if (
            bound.path.suffix.lower() == ".mp4"
            and isinstance(config.runtime.transcription, SidecarTranscriptionConfig)
        ):
            companion = bind_optional_allowed_file(
                config.allowed_root,
                f"{path.strip()}.mke-transcript.json",
            )
            if companion is not None:
                bound.add_companion(companion)
        return bound
    except Exception:
        bound.close()
        raise


def _ingest_failure(
    problem: str,
    cause: str,
    next_step: str,
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    return _failure(
        problem,
        cause,
        next_step,
        run_id=run_id,
        safe_causes=_INGEST_LOCAL_SAFE_CAUSES,
    )


def _failure(
    problem: str,
    cause: str,
    next_step: str,
    *,
    run_id: str | None = None,
    safe_causes: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    return public_error_from_cause(
        cause,
        problem=problem,
        next_step=next_step,
        run_id=run_id,
        safe_causes=safe_causes,
    ).payload()
