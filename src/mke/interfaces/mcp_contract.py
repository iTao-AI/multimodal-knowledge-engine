"""Pure MCP tool contracts backed by the project-owned KnowledgeEngine."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mke.application import (
    DEFAULT_ASK_LIMIT,
    MAX_ASK_LIMIT,
    MIN_ASK_LIMIT,
    AskValidationError,
    KnowledgeEngine,
    PdfIngestError,
    VideoIngestError,
)
from mke.domain import PdfIntakeReport, SearchResult

logger = logging.getLogger(__name__)

_MAX_PDF_INPUT_BYTES = 100 * 1024 * 1024

_SUPPORTED_SUFFIX_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".mp4": "video/mp4",
}


@dataclass(frozen=True)
class McpRuntimeConfig:
    db_path: Path
    allowed_root: Path


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
        input_path = _resolve_allowed_file(config, path)
    except ValueError as error:
        return _failure(
            "input_path_rejected",
            str(error),
            "choose_file_under_allowed_root",
        )
    except OSError:
        logger.exception("path resolution failed")
        return _failure(
            "input_path_rejected",
            "file path cannot be resolved",
            "choose_file_under_allowed_root",
        )

    suffix = input_path.suffix.lower()
    media_type = _SUPPORTED_SUFFIX_MEDIA_TYPES.get(suffix)
    if media_type is None:
        return _failure(
            "unsupported_media_type",
            "supported suffixes are .pdf and .mp4",
            "choose_supported_file",
        )
    if suffix == ".pdf" and input_path.stat().st_size > _MAX_PDF_INPUT_BYTES:
        return _failure(
            "input_file_too_large",
            "PDF input exceeds 100 MB limit",
            "choose_smaller_file",
        )

    engine: KnowledgeEngine | None = None
    try:
        engine = KnowledgeEngine(config.db_path)
        try:
            if suffix == ".mp4":
                result = engine.ingest_video(input_path)
            elif suffix == ".pdf":
                result = engine.ingest_pdf(input_path)
            else:
                return _failure(
                    "unsupported_media_type",
                    "supported suffixes are .pdf and .mp4",
                    "choose_supported_file",
                )
        except PdfIngestError as error:
            return _failure(
                "pdf_ingest_failed",
                str(error),
                "fix_input_or_retry",
                run_id=error.run_id,
            )
        except VideoIngestError as error:
            return _failure(
                "video_ingest_failed",
                str(error),
                "fix_input_or_retry",
                run_id=error.run_id,
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
        return payload
    finally:
        if engine is not None:
            engine.close()


def get_run(config: McpRuntimeConfig, run_id: str) -> dict[str, Any]:
    engine: KnowledgeEngine | None = None
    try:
        engine = KnowledgeEngine(config.db_path)
        try:
            run = engine.get_run(run_id)
        except KeyError:
            return _failure("run_not_found", f"unknown run: {run_id}", "check_run_id")
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
        engine = KnowledgeEngine(config.db_path)
        results = [
            _evidence_from_search_result(match)
            for match in engine.search(normalized_query, limit=limit)
        ]
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
        engine = KnowledgeEngine(config.db_path)
        try:
            result = engine.ask(question, limit=limit)
        except AskValidationError as error:
            return _failure(error.problem, error.cause, error.next_step)
        return {
            "ok": True,
            "ask_id": result.ask_id,
            "question": result.question,
            "answer_status": result.answer_status,
            "summary": result.summary,
            "evidence": [
                _evidence_from_search_result(match) for match in result.evidence
            ],
            "limitations": list(result.limitations),
        }
    finally:
        if engine is not None:
            engine.close()


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


def _resolve_allowed_file(config: McpRuntimeConfig, path: str) -> Path:
    stripped_path = path.strip()
    if not stripped_path:
        raise ValueError("input path must not be empty")

    allowed_root = config.allowed_root.resolve()
    requested = Path(stripped_path)
    candidate = requested if requested.is_absolute() else allowed_root / requested
    resolved = candidate.resolve()
    try:
        resolved.relative_to(allowed_root)
    except ValueError as error:
        raise ValueError("input path must be under allowed root") from error
    if not resolved.exists():
        raise ValueError("input file does not exist")
    if not resolved.is_file():
        raise ValueError("input path must be a file")
    return resolved


def _failure(
    problem: str,
    cause: str,
    next_step: str,
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "problem": problem,
        "cause": cause,
        "active_publication_impact": "unchanged",
        "next_step": next_step,
    }
    if run_id is not None:
        payload["run_id"] = run_id
    return payload
