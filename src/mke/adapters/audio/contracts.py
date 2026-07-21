"""Project-owned direct-audio adapter contracts."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from hashlib import sha256

from mke.domain import TranscriptionProvenance


@dataclass(frozen=True)
class AudioTranscriptionLimits:
    max_input_bytes: int = 100 * 1024 * 1024
    max_media_duration_ms: int = 900_000
    max_segment_count: int = 10_000
    timeout_seconds: float = 120.0
    max_stdout_bytes: int = 8 * 1024 * 1024
    max_stderr_bytes: int = 64 * 1024

    def __post_init__(self) -> None:
        integer_limits = (
            self.max_input_bytes,
            self.max_media_duration_ms,
            self.max_segment_count,
            self.max_stdout_bytes,
            self.max_stderr_bytes,
        )
        if any(type(value) is not int or value <= 0 for value in integer_limits):
            raise ValueError("audio transcription limits must be positive integers")
        if (
            type(self.timeout_seconds) not in {int, float}
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("audio transcription timeout must be positive and finite")


def audio_extractor_fingerprint(provenance: TranscriptionProvenance) -> str:
    identity = {
        "compute_type": provenance.compute_type,
        "device": provenance.device,
        "language": provenance.language,
        "library_version": provenance.library_version,
        "model": provenance.model,
        "model_revision": provenance.model_revision,
        "provider": provenance.provider,
    }
    canonical = json.dumps(identity, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return "faster-whisper-audio-v1:" + sha256(canonical.encode("utf-8")).hexdigest()
