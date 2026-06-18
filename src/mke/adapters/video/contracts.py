"""Provider-neutral contracts for bounded local video transcription."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import IntEnum
from hashlib import sha256

from mke.domain import (
    ParsedVideoTranscript,
    TranscriptIntakeReport,
    TranscriptionProvenance,
)


@dataclass(frozen=True)
class VideoTranscriptionLimits:
    max_input_bytes: int = 100 * 1024 * 1024
    max_media_duration_ms: int = 900_000
    max_segment_count: int = 10_000
    timeout_seconds: float = 900.0
    max_stdout_bytes: int = 2 * 1024 * 1024
    max_stderr_bytes: int = 512 * 1024

    def __post_init__(self) -> None:
        integer_values = (
            self.max_input_bytes,
            self.max_media_duration_ms,
            self.max_segment_count,
            self.max_stdout_bytes,
            self.max_stderr_bytes,
        )
        timeout = self.timeout_seconds
        if (
            any(type(value) is not int or value <= 0 for value in integer_values)
            or type(timeout) not in {int, float}
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError("video transcription limits must be positive")


class AdapterExitCode(IntEnum):
    DEPENDENCY_MISSING = 20
    MODEL_UNAVAILABLE = 21
    MODEL_RESOLUTION_FAILED = 22
    MEDIA_UNSUPPORTED = 30
    MEDIA_NO_AUDIO = 31
    MEDIA_LIMIT_EXCEEDED = 32
    TRANSCRIPTION_FAILED = 40
    EMPTY_TRANSCRIPT = 41
    SCHEMA_INVALID = 50


@dataclass(frozen=True)
class AdapterFailureSpec:
    problem: str
    cause: str
    next_step: str

    def __post_init__(self) -> None:
        if any(not value.strip() for value in (self.problem, self.cause, self.next_step)):
            raise ValueError("adapter failure fields must not be blank")


def faster_whisper_fingerprint(provenance: TranscriptionProvenance) -> str:
    identity = {
        "compute_type": provenance.compute_type,
        "device": provenance.device,
        "language": provenance.language,
        "library_version": provenance.library_version,
        "model": provenance.model,
        "model_revision": provenance.model_revision,
        "provider": provenance.provider,
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "faster-whisper-v1:" + sha256(canonical.encode("utf-8")).hexdigest()


def build_transcript_intake_report(
    parsed: ParsedVideoTranscript,
) -> TranscriptIntakeReport:
    provenance = parsed.transcription_provenance
    if provenance is None:
        raise ValueError("transcription provenance is required for a successful report")
    return TranscriptIntakeReport(
        provider=provenance.provider,
        model=provenance.model,
        model_revision=provenance.model_revision,
        library_version=provenance.library_version,
        device=provenance.device,
        compute_type=provenance.compute_type,
        language=provenance.language,
        detected_language=provenance.detected_language,
        media_duration_ms=parsed.media.duration_ms,
        transcription_duration_ms=provenance.transcription_duration_ms,
        segment_count=len(parsed.segments),
        model_source=provenance.model_source,
    )
