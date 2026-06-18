"""Typed owner configuration and shared runtime composition."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from mke.adapters.video.contracts import VideoTranscriptionLimits
from mke.adapters.video.process import ActiveProcessController

DEFAULT_MODEL_REVISION = "536b0662742c02347bc0e980a01041f333bce120"

_COMMIT_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
_LANGUAGE_RE = re.compile(r"(?:auto|[a-z]{2,3})\Z")
_REPOSITORY_ID_RE = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,95})/"
    r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,95})\Z"
)
_MAX_LIMITS = VideoTranscriptionLimits()


@dataclass(frozen=True)
class SidecarTranscriptionConfig:
    provider: Literal["sidecar"] = "sidecar"


@dataclass(frozen=True)
class FasterWhisperTranscriptionConfig:
    provider: Literal["faster-whisper"] = "faster-whisper"
    model: str = "small"
    model_revision: str = DEFAULT_MODEL_REVISION
    device: str = "cpu"
    compute_type: str = "int8"
    language: str = "auto"
    cache_dir: Path | None = None
    limits: VideoTranscriptionLimits = VideoTranscriptionLimits()

    def __post_init__(self) -> None:
        if self.model != "small" and _REPOSITORY_ID_RE.fullmatch(self.model) is None:
            raise ValueError("model identifier must be 'small' or an owner/repository ID")
        if self.model in {".", ".."} or ".." in self.model.split("/"):
            raise ValueError("model identifier must not be a filesystem path")
        if _COMMIT_SHA_RE.fullmatch(self.model_revision) is None:
            raise ValueError("model revision must be a 40-character lowercase commit SHA")
        language = self.language.lower()
        if _LANGUAGE_RE.fullmatch(language) is None:
            raise ValueError("language must be auto or a two- or three-letter code")
        object.__setattr__(self, "language", language)
        if not self.device.strip() or len(self.device) > 64:
            raise ValueError("device must be a bounded non-empty value")
        if not self.compute_type.strip() or len(self.compute_type) > 64:
            raise ValueError("compute type must be a bounded non-empty value")
        _validate_approved_limits(self.limits)


@dataclass(frozen=True)
class ModelPreparationConfig:
    transcription: FasterWhisperTranscriptionConfig
    allow_model_download: bool = False

    def __post_init__(self) -> None:
        if type(self.allow_model_download) is not bool:
            raise TypeError("allow_model_download must be a boolean")


TranscriptionConfig = SidecarTranscriptionConfig | FasterWhisperTranscriptionConfig


@dataclass(frozen=True)
class RuntimeConfig:
    db_path: Path
    transcription: TranscriptionConfig = SidecarTranscriptionConfig()
    process_controller: ActiveProcessController = field(
        default_factory=ActiveProcessController,
        compare=False,
    )

    def __post_init__(self) -> None:
        if type(self.transcription) not in {
            SidecarTranscriptionConfig,
            FasterWhisperTranscriptionConfig,
        }:
            raise TypeError("transcription config must be a typed configuration")
        if type(self.process_controller) is not ActiveProcessController:
            raise TypeError("process controller must be ActiveProcessController")


def _validate_approved_limits(limits: VideoTranscriptionLimits) -> None:
    values = (
        (limits.max_input_bytes, _MAX_LIMITS.max_input_bytes),
        (limits.max_media_duration_ms, _MAX_LIMITS.max_media_duration_ms),
        (limits.max_segment_count, _MAX_LIMITS.max_segment_count),
        (limits.timeout_seconds, _MAX_LIMITS.timeout_seconds),
        (limits.max_stdout_bytes, _MAX_LIMITS.max_stdout_bytes),
        (limits.max_stderr_bytes, _MAX_LIMITS.max_stderr_bytes),
    )
    if any(actual > maximum for actual, maximum in values):
        raise ValueError("video transcription limits exceed approved bounds")
