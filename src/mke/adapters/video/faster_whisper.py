"""Cache-only first-party faster-whisper runtime support."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Literal, Protocol, cast

from mke.runtime import FasterWhisperTranscriptionConfig, ModelPreparationConfig

logger = logging.getLogger(__name__)

_MODEL_ALIASES = {"small": "Systran/faster-whisper-small"}
_SUPPORTED_DEVICES = frozenset({"auto", "cpu", "cuda"})
_SUPPORTED_COMPUTE_TYPES = frozenset(
    {
        "auto",
        "default",
        "int8",
        "int8_float16",
        "int8_float32",
        "int8_bfloat16",
        "int16",
        "float16",
        "bfloat16",
        "float32",
    }
)


class _SnapshotDownload(Protocol):
    def __call__(
        self,
        *,
        repo_id: str,
        revision: str,
        cache_dir: str | None,
        local_files_only: bool,
    ) -> str: ...


class _ReadyModel(Protocol):
    supported_languages: list[str]


class _WhisperModelFactory(Protocol):
    def __call__(
        self,
        model_size_or_path: str,
        *,
        device: str,
        compute_type: str,
        local_files_only: bool,
    ) -> _ReadyModel: ...


class ModelResolutionError(RuntimeError):
    """Stable setup failure that never includes SDK exception text or local paths."""

    def __init__(self, cause: str, next_step: str) -> None:
        super().__init__(cause)
        self.cause = cause
        self.next_step = next_step


@dataclass(frozen=True)
class ModelPreparationResult:
    status: Literal["already_cached", "downloaded"]
    provider: str
    model: str
    model_revision: str


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    status: Literal["passed", "failed"]
    message: str


@dataclass(frozen=True)
class TranscriptionReadiness:
    status: Literal["ready", "not_ready"]
    checks: tuple[ReadinessCheck, ...]
    cause: str | None
    next_step: str | None


def normalize_model_identifier(model: str) -> str:
    return _MODEL_ALIASES.get(model, model)


def resolve_model_snapshot(
    config: FasterWhisperTranscriptionConfig,
    *,
    allow_download: bool,
) -> Path:
    try:
        hub = import_module("huggingface_hub")
        snapshot_download = cast(_SnapshotDownload, hub.snapshot_download)
    except ImportError as error:
        raise ModelResolutionError(
            "transcription optional dependency is not installed",
            "install_transcription_extra",
        ) from error

    try:
        resolved = snapshot_download(
            repo_id=normalize_model_identifier(config.model),
            revision=config.model_revision,
            cache_dir=str(config.cache_dir) if config.cache_dir is not None else None,
            local_files_only=not allow_download,
        )
    except Exception as error:
        logger.exception("transcription_model_resolution_failed")
        raise classify_model_resolution_error(
            error,
            allow_download=allow_download,
        ) from error
    return Path(resolved)


def classify_model_resolution_error(
    error: Exception,
    *,
    allow_download: bool,
) -> ModelResolutionError:
    error_name = type(error).__name__
    if isinstance(error, PermissionError):
        return ModelResolutionError(
            "transcription model cache is not readable",
            "check_model_cache_permissions",
        )
    if error_name in {"RevisionNotFoundError", "RepositoryNotFoundError"}:
        return ModelResolutionError(
            "configured transcription model revision is unavailable",
            "check_model_and_revision",
        )
    if not allow_download and (
        isinstance(error, FileNotFoundError)
        or error_name in {"LocalEntryNotFoundError", "CacheNotFound"}
    ):
        return ModelResolutionError(
            "configured transcription model is not cached",
            "run_transcription_prepare",
        )
    if allow_download:
        return ModelResolutionError(
            "transcription model download failed",
            "check_network_and_model_configuration",
        )
    return ModelResolutionError(
        "transcription model resolution failed",
        "check_model_configuration",
    )


def prepare_model(config: ModelPreparationConfig) -> ModelPreparationResult:
    try:
        resolve_model_snapshot(config.transcription, allow_download=False)
    except ModelResolutionError as error:
        if not config.allow_model_download or error.cause != (
            "configured transcription model is not cached"
        ):
            raise
        resolve_model_snapshot(config.transcription, allow_download=True)
        status: Literal["already_cached", "downloaded"] = "downloaded"
    else:
        status = "already_cached"
    return ModelPreparationResult(
        status=status,
        provider=config.transcription.provider,
        model=config.transcription.model,
        model_revision=config.transcription.model_revision,
    )


def doctor_transcription(
    config: FasterWhisperTranscriptionConfig,
) -> TranscriptionReadiness:
    profile_failure = _validate_runtime_profile(config)
    if profile_failure is not None:
        return _not_ready(
            checks=(ReadinessCheck("profile", "failed", "unsupported profile"),),
            cause=profile_failure,
            next_step="choose_supported_transcription_profile",
        )

    try:
        whisper_model = _import_optional_runtime()
    except ImportError:
        return _not_ready(
            checks=(ReadinessCheck("dependencies", "failed", "optional dependencies missing"),),
            cause="transcription optional dependency is not installed",
            next_step="install_transcription_extra",
        )

    checks = [
        ReadinessCheck("dependencies", "passed", "optional dependencies available"),
        ReadinessCheck("profile", "passed", "runtime profile supported"),
    ]
    try:
        snapshot = resolve_model_snapshot(config, allow_download=False)
    except ModelResolutionError as error:
        checks.append(ReadinessCheck("model", "failed", "model snapshot unavailable"))
        return _not_ready(tuple(checks), error.cause, error.next_step)

    try:
        model = whisper_model(
            str(snapshot),
            device=config.device,
            compute_type=config.compute_type,
            local_files_only=True,
        )
    except Exception:
        logger.exception("transcription_profile_initialization_failed")
        checks.append(ReadinessCheck("model", "failed", "model profile unavailable"))
        return _not_ready(
            tuple(checks),
            "transcription device or compute profile is unsupported",
            "choose_supported_transcription_profile",
        )

    if config.language != "auto" and config.language not in model.supported_languages:
        checks.append(ReadinessCheck("language", "failed", "language unsupported"))
        return _not_ready(
            tuple(checks),
            "configured language is not supported by the model",
            "choose_supported_language",
        )
    checks.extend(
        (
            ReadinessCheck("model", "passed", "exact model revision cached"),
            ReadinessCheck("language", "passed", "language mode supported"),
        )
    )
    return TranscriptionReadiness(
        status="ready",
        checks=tuple(checks),
        cause=None,
        next_step=None,
    )


def _import_optional_runtime() -> _WhisperModelFactory:
    import_module("av")
    faster_whisper = import_module("faster_whisper")
    return cast(_WhisperModelFactory, faster_whisper.WhisperModel)


def _validate_runtime_profile(config: FasterWhisperTranscriptionConfig) -> str | None:
    if (
        config.device not in _SUPPORTED_DEVICES
        or config.compute_type not in _SUPPORTED_COMPUTE_TYPES
    ):
        return "transcription device or compute profile is unsupported"
    return None


def _not_ready(
    checks: tuple[ReadinessCheck, ...],
    cause: str,
    next_step: str,
) -> TranscriptionReadiness:
    return TranscriptionReadiness(
        status="not_ready",
        checks=checks,
        cause=cause,
        next_step=next_step,
    )
