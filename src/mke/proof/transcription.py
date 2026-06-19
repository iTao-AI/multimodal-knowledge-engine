"""Cache-only proof for the first-party local transcription runtime."""

from __future__ import annotations

import json
import math
import platform
import re
import tempfile
import time
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Literal

from mke.application import AskResult, VideoIngestError
from mke.domain import IngestResult, SearchResult, TranscriptIntakeReport
from mke.interfaces.mcp_contract import transcript_intake_report_payload
from mke.runtime import FasterWhisperTranscriptionConfig, RuntimeConfig, build_engine

_NOT_RUN = "not_run"
_MODEL_NOT_CACHED = "model_not_cached"
_RUN_STATES = frozenset({"published", "failed"})
_ASK_STATUSES = frozenset({"evidence_found", "insufficient_evidence", _NOT_RUN})
_SAFE_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+()-]{0,255}\Z")
_SAFE_VERSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.!_+()-]{0,127}\Z")
_MODEL_PART_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}\Z")
_COMMIT_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
_NEXT_STEP_BY_REASON = {
    _MODEL_NOT_CACHED: "run_transcription_prepare",
    "fixture_unavailable": "choose_existing_fixture",
    "environment_unavailable": "check_runtime_environment",
    "runtime_initialization_failed": "check_transcription_installation",
    "proof_cleanup_failed": "retry_transcription_proof",
    "video_ingest_failed": "check_transcription_configuration",
    "proof_validation_failed": "inspect_proof_invariants",
    "unexpected_error": "check_server_logs",
}


@dataclass(frozen=True)
class ProofEnvironment:
    python_version: str
    os: str
    architecture: str
    faster_whisper_version: str
    ctranslate2_version: str
    pyav_version: str

    def __post_init__(self) -> None:
        if not all(
            _is_safe_token(value, max_length=128)
            for value in (self.os, self.architecture)
        ):
            raise ValueError("proof environment platform fields must be public-safe tokens")
        if not all(
            _is_safe_version(value)
            for value in (
                self.python_version,
                self.faster_whisper_version,
                self.ctranslate2_version,
                self.pyav_version,
            )
        ):
            raise ValueError("proof environment version fields must be public-safe tokens")


@dataclass(frozen=True)
class TranscriptionProofReport:
    status: Literal["passed", "failed"]
    run_state: str
    evidence_count: int
    timestamp_evidence: bool
    search_keyword_matched: bool
    ask_status: str
    transcript_intake_report: TranscriptIntakeReport | None
    environment: ProofEnvironment | None
    duration_ms: int
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {"passed", "failed"}:
            raise ValueError("proof status must be passed or failed")
        if self.run_state not in _RUN_STATES:
            raise ValueError("proof run state must be published or failed")
        if self.ask_status not in _ASK_STATUSES:
            raise ValueError("proof ask status is not recognized")
        if type(self.evidence_count) is not int or self.evidence_count < 0:
            raise ValueError("proof evidence count must be a non-negative integer")
        if type(self.duration_ms) is not int or self.duration_ms < 0:
            raise ValueError("proof duration must be a non-negative integer")
        if self.status == "passed":
            if self.reason is not None:
                raise ValueError("passed proof must not include a reason")
            if (
                self.run_state != "published"
                or self.evidence_count <= 0
                or not self.timestamp_evidence
                or not self.search_keyword_matched
                or self.ask_status != "evidence_found"
                or self.transcript_intake_report is None
                or self.environment is None
            ):
                raise ValueError("passed proof requires all success invariants")
            if not _is_safe_intake_report(self.transcript_intake_report):
                raise ValueError("passed proof requires a public-safe intake report")
        elif not self.reason:
            raise ValueError("failed proof requires a stable reason")
        elif self.reason not in _NEXT_STEP_BY_REASON:
            raise ValueError("failed proof reason must be allowlisted")


def run_transcription_proof(
    fixture: Path,
    transcription: FasterWhisperTranscriptionConfig,
) -> TranscriptionProofReport:
    """Run the first-party transcription path without preparing or downloading a model."""
    started = _safe_monotonic()
    environment: ProofEnvironment | None = None
    try:
        environment = _proof_environment()
    except Exception:
        return _failed_report(
            started,
            None,
            reason="environment_unavailable",
        )
    try:
        fixture_exists = fixture.is_file()
    except Exception:
        fixture_exists = False
    if not fixture_exists:
        return _failed_report(
            started,
            environment,
            reason="fixture_unavailable",
        )

    candidate: TranscriptionProofReport | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="mke-transcription-proof-") as temp_dir:
            runtime = RuntimeConfig(
                db_path=Path(temp_dir) / "proof.sqlite",
                transcription=transcription,
            )
            try:
                engine = build_engine(runtime)
            except Exception:
                candidate = _failed_report(
                    started,
                    environment,
                    reason="runtime_initialization_failed",
                )
            else:
                try:
                    result = engine.ingest_video(fixture)
                    run = engine.get_run(result.run_id)
                    matches = engine.search("evidence")
                    answer = engine.ask("evidence publication")
                    candidate = validate_transcription_proof(
                        result,
                        matches,
                        answer,
                        expected_source_id=run.source_id,
                        environment=environment,
                        duration_ms=_elapsed_ms(started),
                    )
                except VideoIngestError as error:
                    reason = (
                        _MODEL_NOT_CACHED
                        if error.next_step == "run_transcription_prepare"
                        else "video_ingest_failed"
                    )
                    candidate = _failed_report(
                        started,
                        environment,
                        reason=reason,
                    )
                except Exception:
                    candidate = _failed_report(
                        started,
                        environment,
                        reason="unexpected_error",
                    )
                try:
                    engine.close()
                except Exception:
                    candidate = _failed_report(
                        started,
                        environment,
                        reason="proof_cleanup_failed",
                    )
    except Exception:
        return _failed_report(
            started,
            environment,
            reason="proof_cleanup_failed",
        )
    return candidate


def validate_transcription_proof(
    result: IngestResult,
    matches: list[SearchResult],
    answer: AskResult,
    *,
    expected_source_id: str | None = None,
    environment: ProofEnvironment,
    duration_ms: int,
) -> TranscriptionProofReport:
    """Validate proof invariants without depending on an exact full transcript."""
    timestamp_evidence = bool(matches) and all(
        match.locator_kind == "timestamp_ms"
        and match.locator_start >= 0
        and match.locator_end > match.locator_start
        for match in matches
    )
    ordered_matches = sorted(
        matches,
        key=lambda match: (match.locator_start, match.locator_end, match.evidence_id),
    )
    ordered_evidence = all(
        previous.locator_end <= current.locator_start
        for previous, current in zip(
            ordered_matches,
            ordered_matches[1:],
            strict=False,
        )
    )
    search_keyword_matched = bool(matches) and all(
        "evidence" in match.text.casefold() for match in matches
    )
    intake_report = result.transcript_intake_report
    safe_intake_report = (
        intake_report
        if intake_report is not None and _is_safe_intake_report(intake_report)
        else None
    )
    source_id = expected_source_id or (matches[0].source_id if matches else None)
    publication_ids = {match.publication_id for match in matches}
    active_publication_id = next(iter(publication_ids)) if len(publication_ids) == 1 else None
    consistent_search_identity = (
        source_id is not None
        and all(match.source_id == source_id for match in matches)
        and active_publication_id is not None
        and bool(active_publication_id)
    )
    consistent_ask_identity = (
        bool(answer.evidence)
        and source_id is not None
        and active_publication_id is not None
        and all(
            item.locator_kind == "timestamp_ms"
            and item.locator_start >= 0
            and item.locator_end > item.locator_start
            and item.source_id == source_id
            and item.publication_id == active_publication_id
            for item in answer.evidence
        )
    )
    valid = (
        result.run_state.value == "published"
        and result.evidence_count > 0
        and safe_intake_report is not None
        and safe_intake_report.provider == "faster-whisper"
        and safe_intake_report.model_source == "cache"
        and safe_intake_report.segment_count == result.evidence_count
        and consistent_search_identity
        and timestamp_evidence
        and ordered_evidence
        and search_keyword_matched
        and answer.answer_status == "evidence_found"
        and consistent_ask_identity
    )
    if not valid:
        return TranscriptionProofReport(
            status="failed",
            run_state=result.run_state.value,
            evidence_count=result.evidence_count,
            timestamp_evidence=timestamp_evidence and ordered_evidence,
            search_keyword_matched=search_keyword_matched,
            ask_status=answer.answer_status,
            transcript_intake_report=safe_intake_report,
            environment=environment,
            duration_ms=duration_ms,
            reason="proof_validation_failed",
        )
    return TranscriptionProofReport(
        status="passed",
        run_state=result.run_state.value,
        evidence_count=result.evidence_count,
        timestamp_evidence=True,
        search_keyword_matched=True,
        ask_status=answer.answer_status,
        transcript_intake_report=safe_intake_report,
        environment=environment,
        duration_ms=duration_ms,
    )


def render_transcription_proof_json(report: TranscriptionProofReport) -> str:
    """Render exactly one public-safe JSON object."""
    intake_report = (
        report.transcript_intake_report
        if report.transcript_intake_report is not None
        and _is_safe_intake_report(report.transcript_intake_report)
        else None
    )
    payload: dict[str, object] = {
        "status": report.status,
        "run_state": report.run_state,
        "evidence_count": report.evidence_count,
        "timestamp_evidence": report.timestamp_evidence,
        "search_keyword_matched": report.search_keyword_matched,
        "ask_status": report.ask_status,
        "transcript_intake_report": (
            transcript_intake_report_payload(intake_report)
            if intake_report is not None
            else None
        ),
        "environment": (
            {
                "python_version": report.environment.python_version,
                "os": report.environment.os,
                "architecture": report.environment.architecture,
                "faster_whisper_version": report.environment.faster_whisper_version,
                "ctranslate2_version": report.environment.ctranslate2_version,
                "pyav_version": report.environment.pyav_version,
            }
            if report.environment is not None
            else None
        ),
        "duration_ms": report.duration_ms,
        "reason": report.reason,
    }
    return json.dumps(payload, sort_keys=True)


def render_transcription_proof_human(report: TranscriptionProofReport) -> str:
    """Render a bounded human summary containing only allowlisted report fields."""
    fields = [
        "proof=transcription",
        f"status={report.status}",
        f"run_state={report.run_state}",
        f"evidence_count={report.evidence_count}",
        f"timestamp_evidence={str(report.timestamp_evidence).lower()}",
        f"search_keyword_matched={str(report.search_keyword_matched).lower()}",
        f"ask_status={report.ask_status}",
        f"duration_ms={report.duration_ms}",
    ]
    intake_report = (
        report.transcript_intake_report
        if report.transcript_intake_report is not None
        and _is_safe_intake_report(report.transcript_intake_report)
        else None
    )
    if intake_report is not None:
        fields.extend(
            (
                f"provider={intake_report.provider}",
                f"model={intake_report.model}",
                f"model_revision={intake_report.model_revision}",
                f"library_version={intake_report.library_version}",
                f"device={intake_report.device}",
                f"compute_type={intake_report.compute_type}",
                f"language={intake_report.language}",
                f"detected_language={intake_report.detected_language}",
                f"model_source={intake_report.model_source}",
                f"segment_count={intake_report.segment_count}",
            )
        )
    if report.environment is not None:
        fields.extend(
            (
                f"python_version={report.environment.python_version}",
                f"os={report.environment.os}",
                f"architecture={report.environment.architecture}",
                f"faster_whisper_version={report.environment.faster_whisper_version}",
                f"ctranslate2_version={report.environment.ctranslate2_version}",
                f"pyav_version={report.environment.pyav_version}",
            )
        )
    if report.reason is not None:
        fields.extend(
            (
                f"reason={report.reason}",
                f"next_step={_NEXT_STEP_BY_REASON[report.reason]}",
            )
        )
    return " ".join(fields)


def _failed_report(
    started: float | None,
    environment: ProofEnvironment | None,
    *,
    reason: str,
) -> TranscriptionProofReport:
    return TranscriptionProofReport(
        status="failed",
        run_state="failed",
        evidence_count=0,
        timestamp_evidence=False,
        search_keyword_matched=False,
        ask_status=_NOT_RUN,
        transcript_intake_report=None,
        environment=environment,
        duration_ms=_elapsed_ms(started),
        reason=reason,
    )


def _proof_environment() -> ProofEnvironment:
    return ProofEnvironment(
        python_version=platform.python_version(),
        os=platform.system() or "unknown",
        architecture=platform.machine() or "unknown",
        faster_whisper_version=_package_version("faster-whisper"),
        ctranslate2_version=_package_version("ctranslate2"),
        pyav_version=_package_version("av"),
    )


def _package_version(distribution: str) -> str:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return "not-installed"


def _safe_monotonic() -> float | None:
    try:
        value = time.monotonic()
    except Exception:
        return None
    return value if math.isfinite(value) and value >= 0 else None


def _elapsed_ms(started: float | None) -> int:
    if started is None:
        return 0
    finished = _safe_monotonic()
    if finished is None or finished < started:
        return 0
    return int((finished - started) * 1000)


def _is_safe_intake_report(report: TranscriptIntakeReport) -> bool:
    return (
        _is_safe_token(report.provider)
        and _is_safe_model(report.model)
        and _COMMIT_SHA_RE.fullmatch(report.model_revision) is not None
        and _is_safe_version(report.library_version)
        and _is_safe_token(report.device)
        and _is_safe_token(report.compute_type)
        and _is_safe_token(report.language)
        and _is_safe_token(report.detected_language)
        and _is_safe_token(report.model_source)
    )


def _is_safe_model(value: str) -> bool:
    if _is_safe_token(value):
        return True
    parts = value.split("/")
    return len(parts) == 2 and all(_MODEL_PART_RE.fullmatch(part) for part in parts)


def _is_safe_token(value: object, *, max_length: int = 256) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= max_length
        and _SAFE_TOKEN_RE.fullmatch(value) is not None
    )


def _is_safe_version(value: object) -> bool:
    return isinstance(value, str) and _SAFE_VERSION_RE.fullmatch(value) is not None
