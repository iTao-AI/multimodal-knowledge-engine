"""Provider-neutral contracts for bounded local video transcription."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import IntEnum
from hashlib import sha256

from mke.domain import TranscriptionProvenance


@dataclass(frozen=True)
class VideoTranscriptionLimits:
    max_input_bytes: int = 100 * 1024 * 1024
    max_media_duration_ms: int = 900_000
    max_segment_count: int = 10_000
    timeout_seconds: float = 900.0
    max_stdout_bytes: int = 2 * 1024 * 1024
    max_stderr_bytes: int = 512 * 1024

    def __post_init__(self) -> None:
        values = (
            self.max_input_bytes,
            self.max_media_duration_ms,
            self.max_segment_count,
            self.timeout_seconds,
            self.max_stdout_bytes,
            self.max_stderr_bytes,
        )
        if any(type(value) not in {int, float} or value <= 0 for value in values):
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
