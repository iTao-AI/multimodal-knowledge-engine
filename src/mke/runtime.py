"""Typed owner configuration and shared runtime composition."""

from __future__ import annotations

import platform
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, cast

from mke.adapters.video.contracts import (
    AdapterExitCode,
    AdapterFailureSpec,
    VideoTranscriptionLimits,
)
from mke.adapters.video.process import (
    ActiveProcessController,
    ProcessOperationId,
    SupervisedProcessProfile,
)
from mke.adapters.video.providers import (
    LocalCommandTranscriptConfig,
    LocalCommandTranscriptProvider,
    SidecarTranscriptProvider,
)
from mke.application import AudioIngestError, AudioProvider, KnowledgeEngine, TranscriptProvider
from mke.retrieval import (
    DEFAULT_RETRIEVAL_STRATEGY,
    RetrievalQueryPolicy,
    RetrievalStrategy,
)
from mke.retrieval.query_policy import require_retrieval_query_policy
from mke.retrieval.strategy import (
    get_retrieval_strategy_descriptor,
    require_retrieval_strategy,
)
from mke.runtime_owner import BoundedAdmissionController, OwnerRuntimeState

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
    retrieval_query_policy: RetrievalQueryPolicy | None = None
    retrieval_strategy: RetrievalStrategy | None = None
    transcription: TranscriptionConfig = SidecarTranscriptionConfig()
    process_controller: ActiveProcessController = field(
        default_factory=ActiveProcessController,
        compare=False,
    )
    owner_state: OwnerRuntimeState = field(
        default_factory=OwnerRuntimeState,
        compare=False,
    )
    admission_controller: BoundedAdmissionController = field(
        default_factory=lambda: BoundedAdmissionController(capacity=1, max_waiters=1),
        compare=False,
    )
    process_operation_id: ProcessOperationId | None = field(
        default=None,
        compare=False,
    )
    direct_audio_footprint_bytes: int | None = None
    direct_audio_footprint_budget_mode: Literal["baseline_plus"] | None = None

    def __post_init__(self) -> None:
        query_policy = (
            require_retrieval_query_policy(self.retrieval_query_policy)
            if self.retrieval_query_policy is not None
            else None
        )
        if self.retrieval_strategy is None:
            strategy = require_retrieval_strategy(
                query_policy if query_policy is not None else DEFAULT_RETRIEVAL_STRATEGY
            )
        else:
            strategy = require_retrieval_strategy(self.retrieval_strategy)
        query_policy = get_retrieval_strategy_descriptor(strategy).base_query_policy
        object.__setattr__(self, "retrieval_query_policy", query_policy)
        object.__setattr__(self, "retrieval_strategy", strategy)
        if type(self.transcription) not in {
            SidecarTranscriptionConfig,
            FasterWhisperTranscriptionConfig,
        }:
            raise TypeError("transcription config must be a typed configuration")
        footprint_bytes = self.direct_audio_footprint_bytes
        footprint_mode = self.direct_audio_footprint_budget_mode
        if (footprint_bytes is None) != (footprint_mode is None):
            raise ValueError(
                "direct audio supervision fields must be configured together"
            )
        if footprint_bytes is not None:
            if type(footprint_bytes) is not int:
                raise TypeError("direct audio footprint bytes must be a positive integer")
            if footprint_bytes <= 0:
                raise ValueError("direct audio footprint bytes must be a positive integer")
            if footprint_mode != "baseline_plus":
                raise ValueError("direct audio footprint budget mode must be baseline_plus")
        if type(self.process_controller) is not ActiveProcessController:
            raise TypeError("process controller must be ActiveProcessController")
        if type(self.owner_state) is not OwnerRuntimeState:
            raise TypeError("owner state must be OwnerRuntimeState")
        if type(self.admission_controller) is not BoundedAdmissionController:
            raise TypeError("admission controller must be BoundedAdmissionController")
        if self.process_operation_id is not None:
            if not isinstance(self.process_operation_id, str):  # pyright: ignore[reportUnnecessaryIsInstance] -- runtime guard for untyped callers
                raise TypeError("process operation ID must be a string")
            if not self.process_operation_id.startswith("op_"):
                raise ValueError("process operation ID must begin with op_")


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
            process_operation_id=config.process_operation_id,
        )
    )


def audio_transcription_preflight(config: FasterWhisperTranscriptionConfig) -> object:
    from mke.adapters.video.faster_whisper import (
        audio_transcription_preflight as run_preflight,
    )

    return run_preflight(config)


def _build_audio_provider(config: RuntimeConfig) -> AudioProvider | None:
    if isinstance(config.transcription, SidecarTranscriptionConfig):
        return None
    if (
        config.direct_audio_footprint_bytes is None
        or config.direct_audio_footprint_budget_mode is None
        or platform.system() != "Darwin"
        or platform.machine() != "arm64"
    ):
        return None
    from mke.adapters.audio import InternalAudioProvider

    profile = SupervisedProcessProfile(
        wall_seconds=config.transcription.limits.timeout_seconds,
        stdout_bytes=config.transcription.limits.max_stdout_bytes,
        stderr_bytes=config.transcription.limits.max_stderr_bytes,
        footprint_bytes=config.direct_audio_footprint_bytes,
        footprint_budget_mode=config.direct_audio_footprint_budget_mode,
    )
    return cast(
        AudioProvider,
        InternalAudioProvider(
            profile=profile,
            process_controller=config.process_controller,
            process_operation_id=config.process_operation_id,
        ),
    )


def _build_audio_preflight(
    config: RuntimeConfig,
) -> Callable[[], None] | None:
    if isinstance(config.transcription, SidecarTranscriptionConfig):
        return None
    transcription = config.transcription

    def preflight() -> None:
        if (
            config.direct_audio_footprint_bytes is None
            or config.direct_audio_footprint_budget_mode is None
        ):
            raise AudioIngestError(
                "direct audio supervision is not configured",
                problem="transcription_not_ready",
                next_step="configure_direct_audio_supervision",
            )
        if platform.system() != "Darwin" or platform.machine() != "arm64":
            raise AudioIngestError(
                "direct audio runtime is supported only on Darwin arm64",
                problem="transcription_not_ready",
                next_step="run_on_supported_darwin_arm64",
            )
        readiness = audio_transcription_preflight(transcription)
        if getattr(readiness, "status", None) == "ready":
            return
        cause = getattr(readiness, "cause", None)
        next_step = getattr(readiness, "next_step", None)
        raise AudioIngestError(
            cause if isinstance(cause, str) else "transcription is not ready",
            problem="transcription_not_ready",
            next_step=(
                next_step if isinstance(next_step, str) else "run_transcription_doctor"
            ),
        )

    return preflight


def build_engine(config: RuntimeConfig) -> KnowledgeEngine:
    publication_commit: Callable[[], bool] | None = None
    operation_id = config.process_operation_id
    if operation_id is not None:

        def begin_publication_commit() -> bool:
            return config.process_controller.begin_publication_commit(operation_id)

        publication_commit = begin_publication_commit
    engine = KnowledgeEngine(
        config.db_path,
        transcript_provider=build_transcript_provider(config),
        audio_provider=_build_audio_provider(config),
        audio_transcription_config=(
            config.transcription
            if isinstance(config.transcription, FasterWhisperTranscriptionConfig)
            else None
        ),
        audio_preflight=_build_audio_preflight(config),
        publication_commit=publication_commit,
        admission_controller=config.admission_controller,
        query_policy=config.retrieval_query_policy,
        retrieval_strategy=cast(RetrievalStrategy, config.retrieval_strategy),
        recover_unfinished_runs=False,
    )
    try:
        config.owner_state.recover_unfinished_runs_once(
            config.db_path,
            engine.recover_unfinished_runs,
        )
    except Exception:
        engine.close()
        raise
    return engine
