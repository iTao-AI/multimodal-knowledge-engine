"""Typed owner configuration and shared runtime composition."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from mke.adapters.video.contracts import (
    AdapterExitCode,
    AdapterFailureSpec,
    VideoTranscriptionLimits,
)
from mke.adapters.video.process import ActiveProcessController
from mke.adapters.video.providers import (
    LocalCommandTranscriptConfig,
    LocalCommandTranscriptProvider,
    SidecarTranscriptProvider,
)
from mke.application import KnowledgeEngine, TranscriptProvider

DEFAULT_MODEL_REVISION = "536b0662742c02347bc0e980a01041f333bce120"

_COMMIT_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
_LANGUAGE_RE = re.compile(r"(?:auto|[a-z]{2,3})\Z")
_REPOSITORY_ID_RE = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,95})/"
    r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,95})\Z"
)
_MAX_LIMITS = VideoTranscriptionLimits()

FIRST_PARTY_EXIT_ERRORS = {
    int(AdapterExitCode.DEPENDENCY_MISSING): AdapterFailureSpec(
        "video_ingest_failed",
        "transcription optional dependency is not installed",
        "install_transcription_extra",
    ),
    int(AdapterExitCode.MODEL_UNAVAILABLE): AdapterFailureSpec(
        "video_ingest_failed",
        "configured transcription model is not cached",
        "run_transcription_prepare",
    ),
    int(AdapterExitCode.MODEL_RESOLUTION_FAILED): AdapterFailureSpec(
        "video_ingest_failed",
        "transcription model resolution failed",
        "check_model_configuration",
    ),
    int(AdapterExitCode.MEDIA_UNSUPPORTED): AdapterFailureSpec(
        "video_ingest_failed", "unsupported codec for local video proof", "choose_supported_file"
    ),
    int(AdapterExitCode.MEDIA_NO_AUDIO): AdapterFailureSpec(
        "video_ingest_failed", "video must contain an audio track", "choose_supported_file"
    ),
    int(AdapterExitCode.MEDIA_LIMIT_EXCEEDED): AdapterFailureSpec(
        "video_ingest_failed", "video media exceeds duration limit", "choose_smaller_file"
    ),
    int(AdapterExitCode.TRANSCRIPTION_FAILED): AdapterFailureSpec(
        "video_ingest_failed", "transcription failed", "check_server_logs"
    ),
    int(AdapterExitCode.EMPTY_TRANSCRIPT): AdapterFailureSpec(
        "video_ingest_failed", "video transcript must contain at least one segment", "check_audio"
    ),
    int(AdapterExitCode.SCHEMA_INVALID): AdapterFailureSpec(
        "video_ingest_failed", "transcript schema validation failed", "check_server_logs"
    ),
}


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


def first_party_adapter_argv(
    config: FasterWhisperTranscriptionConfig,
) -> tuple[str, ...]:
    argv = [
        sys.executable,
        "-m",
        "mke.adapters.video.faster_whisper_cli",
        "{input}",
        "--model",
        config.model,
        "--model-revision",
        config.model_revision,
        "--device",
        config.device,
        "--compute-type",
        config.compute_type,
        "--language",
        config.language,
        "--max-input-bytes",
        str(config.limits.max_input_bytes),
        "--max-media-duration-ms",
        str(config.limits.max_media_duration_ms),
        "--max-segment-count",
        str(config.limits.max_segment_count),
    ]
    if config.cache_dir is not None:
        argv.extend(("--model-cache", str(config.cache_dir)))
    return tuple(argv)


def build_transcript_provider(config: RuntimeConfig) -> TranscriptProvider:
    if isinstance(config.transcription, SidecarTranscriptionConfig):
        return SidecarTranscriptProvider()
    transcription = config.transcription
    return LocalCommandTranscriptProvider(
        LocalCommandTranscriptConfig(
            argv=first_party_adapter_argv(transcription),
            timeout_seconds=transcription.limits.timeout_seconds,
            max_stdout_bytes=transcription.limits.max_stdout_bytes,
            max_stderr_bytes=transcription.limits.max_stderr_bytes,
            require_provenance=True,
            exit_code_errors=FIRST_PARTY_EXIT_ERRORS,
            process_controller=config.process_controller,
        )
    )


def build_engine(config: RuntimeConfig) -> KnowledgeEngine:
    return KnowledgeEngine(
        config.db_path,
        transcript_provider=build_transcript_provider(config),
    )
