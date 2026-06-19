"""Cache-only proof for the first-party local transcription runtime."""

from __future__ import annotations

import json
import platform
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
_NEXT_STEP_BY_REASON = {
    _MODEL_NOT_CACHED: "run_transcription_prepare",
    "fixture_unavailable": "choose_existing_fixture",
    "runtime_initialization_failed": "check_transcription_installation",
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
        for value in self.__dict__.values():
            if not isinstance(value, str) or not value or len(value) > 128:
                raise ValueError("proof environment fields must be bounded non-empty strings")
            if any(character in value for character in ("\n", "\r", "\x00")):
                raise ValueError("proof environment fields must be single-line strings")


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
        if type(self.evidence_count) is not int or self.evidence_count < 0:
            raise ValueError("proof evidence count must be a non-negative integer")
        if type(self.duration_ms) is not int or self.duration_ms < 0:
            raise ValueError("proof duration must be a non-negative integer")
        if self.status == "passed":
            if self.reason is not None:
                raise ValueError("passed proof must not include a reason")
            if self.transcript_intake_report is None or self.environment is None:
                raise ValueError("passed proof requires intake and environment reports")
        elif not self.reason:
            raise ValueError("failed proof requires a stable reason")
        elif self.reason not in _NEXT_STEP_BY_REASON:
            raise ValueError("failed proof reason must be allowlisted")


def run_transcription_proof(
    fixture: Path,
    transcription: FasterWhisperTranscriptionConfig,
) -> TranscriptionProofReport:
    """Run the first-party transcription path without preparing or downloading a model."""
    started = time.monotonic()
    environment = _proof_environment()
    try:
        fixture_exists = fixture.is_file()
    except OSError:
        fixture_exists = False
    if not fixture_exists:
        return _failed_report(
            started,
            environment,
            reason="fixture_unavailable",
        )

    with tempfile.TemporaryDirectory(prefix="mke-transcription-proof-") as temp_dir:
        runtime = RuntimeConfig(
            db_path=Path(temp_dir) / "proof.sqlite",
            transcription=transcription,
        )
        try:
            engine = build_engine(runtime)
        except Exception:
            return _failed_report(
                started,
                environment,
                reason="runtime_initialization_failed",
            )
        try:
            try:
                result = engine.ingest_video(fixture)
                matches = engine.search("evidence")
                answer = engine.ask("evidence publication")
                return validate_transcription_proof(
                    result,
                    matches,
                    answer,
                    environment=environment,
                    duration_ms=_elapsed_ms(started),
                )
            except VideoIngestError as error:
                reason = (
                    _MODEL_NOT_CACHED
                    if error.next_step == "run_transcription_prepare"
                    else "video_ingest_failed"
                )
                return _failed_report(
                    started,
                    environment,
                    reason=reason,
                )
            except Exception:
                return _failed_report(
                    started,
                    environment,
                    reason="unexpected_error",
                )
        finally:
            try:
                engine.close()
            except Exception:
                pass


def validate_transcription_proof(
    result: IngestResult,
    matches: list[SearchResult],
    answer: AskResult,
    *,
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
    ordered_evidence = all(
        previous.locator_end <= current.locator_start
        for previous, current in zip(matches, matches[1:], strict=False)
    )
    search_keyword_matched = bool(matches) and all(
        "evidence" in match.text.casefold() for match in matches
    )
    intake_report = result.transcript_intake_report
    valid = (
        result.run_state.value == "published"
        and result.evidence_count > 0
        and intake_report is not None
        and intake_report.provider == "faster-whisper"
        and intake_report.model_source == "cache"
        and intake_report.segment_count == result.evidence_count
        and timestamp_evidence
        and ordered_evidence
        and search_keyword_matched
        and answer.answer_status == "evidence_found"
        and bool(answer.evidence)
        and all(item.locator_kind == "timestamp_ms" for item in answer.evidence)
    )
    if not valid:
        return TranscriptionProofReport(
            status="failed",
            run_state=result.run_state.value,
            evidence_count=result.evidence_count,
            timestamp_evidence=timestamp_evidence and ordered_evidence,
            search_keyword_matched=search_keyword_matched,
            ask_status=answer.answer_status,
            transcript_intake_report=intake_report,
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
        transcript_intake_report=intake_report,
        environment=environment,
        duration_ms=duration_ms,
    )


def render_transcription_proof_json(report: TranscriptionProofReport) -> str:
    """Render exactly one public-safe JSON object."""
    payload: dict[str, object] = {
        "status": report.status,
        "run_state": report.run_state,
        "evidence_count": report.evidence_count,
        "timestamp_evidence": report.timestamp_evidence,
        "search_keyword_matched": report.search_keyword_matched,
        "ask_status": report.ask_status,
        "transcript_intake_report": (
            transcript_intake_report_payload(report.transcript_intake_report)
            if report.transcript_intake_report is not None
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
    if report.transcript_intake_report is not None:
        fields.extend(
            (
                f"provider={report.transcript_intake_report.provider}",
                f"model_source={report.transcript_intake_report.model_source}",
                f"segment_count={report.transcript_intake_report.segment_count}",
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
    started: float,
    environment: ProofEnvironment,
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


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
