"""Cache-only first-party faster-whisper runtime support."""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Iterable
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import BinaryIO, Literal, Protocol, cast

from mke.adapters.video.contracts import AdapterExitCode, VideoTranscriptionLimits
from mke.domain import (
    ParsedVideoTranscript,
    TranscriptionProvenance,
    VideoMediaInfo,
    VideoTranscriptSegment,
)
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


class _ResolvedRuntimeModel(Protocol):
    device: str
    compute_type: str


class _WhisperModelFactory(Protocol):
    def __call__(
        self,
        model_size_or_path: str,
        *,
        device: str,
        compute_type: str,
        local_files_only: bool,
    ) -> _ReadyModel: ...


class _CodecContext(Protocol):
    name: str


class _Stream(Protocol):
    codec_context: _CodecContext


class _Streams(Protocol):
    video: list[_Stream]
    audio: list[_Stream]


class _ContainerFormat(Protocol):
    name: str


class _MediaContainer(Protocol):
    format: _ContainerFormat
    streams: _Streams
    duration: int | None

    def close(self) -> None: ...


class _TranscriptionSegment(Protocol):
    start: float
    end: float
    text: str


class _TranscriptionInfo(Protocol):
    language: str


class _TranscribingModel(_ReadyModel, Protocol):
    model: _ResolvedRuntimeModel

    def transcribe(
        self, media: str | BinaryIO, *, language: str | None
    ) -> tuple[Iterable[_TranscriptionSegment], _TranscriptionInfo]: ...


class _TranscribingModelFactory(Protocol):
    def __call__(
        self,
        model_size_or_path: str,
        *,
        device: str,
        compute_type: str,
        local_files_only: bool,
    ) -> _TranscribingModel: ...


class WhisperModelFactory(Protocol):
    @property
    def library_version(self) -> str: ...

    def __call__(
        self,
        model_size_or_path: str,
        *,
        device: str,
        compute_type: str,
        local_files_only: bool,
    ) -> _TranscribingModel: ...


class ModelResolutionError(RuntimeError):
    """Stable setup failure that never includes SDK exception text or local paths."""

    def __init__(self, cause: str, next_step: str) -> None:
        super().__init__(cause)
        self.cause = cause
        self.next_step = next_step


class AdapterProtocolError(RuntimeError):
    """Versioned adapter failure with an optional internal-only diagnostic."""

    def __init__(
        self,
        exit_code: AdapterExitCode,
        diagnostic: str = "adapter operation failed",
    ) -> None:
        super().__init__(diagnostic)
        self.exit_code = exit_code


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


@dataclass(frozen=True)
class NormalizedTranscriptSegment:
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True)
class VersionedWhisperModelFactory:
    factory: _TranscribingModelFactory
    library_version: str

    def __call__(
        self,
        model_size_or_path: str,
        *,
        device: str,
        compute_type: str,
        local_files_only: bool,
    ) -> _TranscribingModel:
        return self.factory(
            model_size_or_path,
            device=device,
            compute_type=compute_type,
            local_files_only=local_files_only,
        )


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
        snapshot = resolve_model_snapshot(config.transcription, allow_download=False)
        _require_complete_model_snapshot(snapshot)
    except ModelResolutionError as error:
        if not config.allow_model_download or error.cause != (
            "configured transcription model is not cached"
        ):
            raise
        snapshot = resolve_model_snapshot(config.transcription, allow_download=True)
        try:
            _require_complete_model_snapshot(snapshot)
        except ModelResolutionError as incomplete_error:
            raise ModelResolutionError(
                "transcription model download failed",
                "check_network_and_model_configuration",
            ) from incomplete_error
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
        _require_complete_model_snapshot(snapshot)
    except ModelResolutionError as error:
        checks.append(ReadinessCheck("model", "failed", "model snapshot incomplete"))
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


def audio_transcription_preflight(
    config: object,
) -> TranscriptionReadiness:
    """Check audio readiness without importing or constructing ``WhisperModel``."""

    if not isinstance(config, FasterWhisperTranscriptionConfig):
        return _not_ready(
            (ReadinessCheck("config", "failed", "configuration invalid"),),
            "transcription configuration is invalid",
            "check_model_configuration",
        )
    profile_failure = _validate_runtime_profile(config)
    if profile_failure is not None:
        return _not_ready(
            (ReadinessCheck("profile", "failed", "unsupported profile"),),
            profile_failure,
            "choose_supported_transcription_profile",
        )
    try:
        import_module("av")
        import_module("faster_whisper")
    except ImportError:
        return _not_ready(
            (ReadinessCheck("dependencies", "failed", "optional dependencies missing"),),
            "transcription optional dependency is not installed",
            "install_transcription_extra",
        )
    checks = (
        ReadinessCheck("dependencies", "passed", "optional dependencies available"),
        ReadinessCheck("profile", "passed", "runtime profile supported"),
    )
    try:
        snapshot = resolve_model_snapshot(config, allow_download=False)
        _require_complete_model_snapshot(snapshot)
    except ModelResolutionError as error:
        return _not_ready(
            checks + (ReadinessCheck("model", "failed", "model snapshot unavailable"),),
            error.cause,
            error.next_step,
        )
    return TranscriptionReadiness(
        status="ready",
        checks=checks + (ReadinessCheck("model", "passed", "exact model revision cached"),),
        cause=None,
        next_step=None,
    )


def load_whisper_runtime() -> tuple[_TranscribingModelFactory, str]:
    """Load the existing optional runtime for another package-owned media child."""

    return _load_whisper_runtime()


def _import_optional_runtime() -> _WhisperModelFactory:
    import_module("av")
    faster_whisper = import_module("faster_whisper")
    return cast(_WhisperModelFactory, faster_whisper.WhisperModel)


def _require_complete_model_snapshot(snapshot: Path) -> None:
    required = ("config.json", "model.bin", "tokenizer.json")
    if not all((snapshot / name).is_file() for name in required):
        raise ModelResolutionError(
            "configured transcription model is not cached",
            "run_transcription_prepare",
        )
    if not any(path.is_file() for path in snapshot.glob("vocabulary.*")):
        raise ModelResolutionError(
            "configured transcription model is not cached",
            "run_transcription_prepare",
        )


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


def probe_media(path: Path, limits: VideoTranscriptionLimits) -> VideoMediaInfo:
    try:
        input_size = path.stat().st_size
    except OSError as error:
        raise AdapterProtocolError(AdapterExitCode.MEDIA_UNSUPPORTED) from error
    if input_size <= 0:
        raise AdapterProtocolError(AdapterExitCode.MEDIA_UNSUPPORTED)
    if input_size > limits.max_input_bytes:
        raise AdapterProtocolError(AdapterExitCode.MEDIA_LIMIT_EXCEEDED)

    try:
        container = _open_media_container(path)
    except Exception as error:
        raise AdapterProtocolError(AdapterExitCode.MEDIA_UNSUPPORTED) from error
    try:
        if "mp4" not in container.format.name.split(","):
            raise AdapterProtocolError(AdapterExitCode.MEDIA_UNSUPPORTED)
        if not container.streams.audio:
            raise AdapterProtocolError(AdapterExitCode.MEDIA_NO_AUDIO)
        if not container.streams.video:
            raise AdapterProtocolError(AdapterExitCode.MEDIA_UNSUPPORTED)
        video_codec = container.streams.video[0].codec_context.name
        audio_codec = container.streams.audio[0].codec_context.name
        if video_codec != "h264" or audio_codec != "aac":
            raise AdapterProtocolError(AdapterExitCode.MEDIA_UNSUPPORTED)
        if container.duration is None or container.duration <= 0:
            raise AdapterProtocolError(AdapterExitCode.MEDIA_UNSUPPORTED)
        duration_ms = math.floor(container.duration / 1000 + 0.5)
        if duration_ms > limits.max_media_duration_ms:
            raise AdapterProtocolError(AdapterExitCode.MEDIA_LIMIT_EXCEEDED)
        return VideoMediaInfo(
            container="mp4",
            video_codec=video_codec,
            audio_codec=audio_codec,
            has_audio=True,
            duration_ms=duration_ms,
        )
    finally:
        container.close()


def _open_media_container(path: Path) -> _MediaContainer:
    av = import_module("av")
    return cast(_MediaContainer, av.open(str(path)))


def normalize_timestamp_ms(seconds: float) -> int:
    if not math.isfinite(seconds) or seconds < 0:
        raise AdapterProtocolError(AdapterExitCode.SCHEMA_INVALID)
    return math.floor(seconds * 1000 + 0.5)


def normalize_segments(
    raw_segments: Iterable[_TranscriptionSegment],
    media: VideoMediaInfo,
    limits: VideoTranscriptionLimits,
) -> tuple[VideoTranscriptSegment, ...]:
    normalized: list[VideoTranscriptSegment] = []
    previous_end = 0
    for raw in raw_segments:
        if len(normalized) >= limits.max_segment_count:
            raise AdapterProtocolError(AdapterExitCode.SCHEMA_INVALID)
        start_ms = normalize_timestamp_ms(raw.start)
        end_ms = normalize_timestamp_ms(raw.end)
        if start_ms < previous_end:
            if previous_end - start_ms > 1:
                raise AdapterProtocolError(AdapterExitCode.SCHEMA_INVALID)
            start_ms = previous_end
        text = raw.text.strip()
        if not text or end_ms <= start_ms or end_ms > media.duration_ms:
            raise AdapterProtocolError(AdapterExitCode.SCHEMA_INVALID)
        normalized.append(VideoTranscriptSegment(start_ms, end_ms, text))
        previous_end = end_ms
    if not normalized:
        raise AdapterProtocolError(AdapterExitCode.EMPTY_TRANSCRIPT)
    return tuple(normalized)


def transcribe_cached_media(
    media: str | BinaryIO,
    *,
    config: FasterWhisperTranscriptionConfig,
    model_factory: WhisperModelFactory,
) -> tuple[tuple[NormalizedTranscriptSegment, ...], TranscriptionProvenance]:
    """Materialize one cache-only inference into media-neutral private values."""

    try:
        snapshot = resolve_model_snapshot(config, allow_download=False)
    except ModelResolutionError as error:
        exit_code = (
            AdapterExitCode.MODEL_UNAVAILABLE
            if error.cause == "configured transcription model is not cached"
            else AdapterExitCode.MODEL_RESOLUTION_FAILED
        )
        raise AdapterProtocolError(exit_code) from error
    started = time.monotonic()
    try:
        model = model_factory(
            str(snapshot),
            device=config.device,
            compute_type=config.compute_type,
            local_files_only=True,
        )
        raw_segments, info = model.transcribe(
            media,
            language=None if config.language == "auto" else config.language,
        )
        materialized = tuple(raw_segments)
    except AdapterProtocolError:
        raise
    except Exception as error:
        logger.exception("faster_whisper_transcription_failed")
        raise AdapterProtocolError(AdapterExitCode.TRANSCRIPTION_FAILED) from error
    segments = _normalize_cached_segments(materialized, config.limits)
    duration_ms = math.floor((time.monotonic() - started) * 1000 + 0.5)
    provenance = TranscriptionProvenance(
        provider="faster-whisper",
        model=config.model,
        model_revision=config.model_revision,
        library_version=model_factory.library_version,
        device=model.model.device,
        compute_type=model.model.compute_type,
        language=config.language,
        detected_language=info.language.lower(),
        model_source="cache",
        transcription_duration_ms=duration_ms,
    )
    return segments, provenance


def _normalize_cached_segments(
    raw_segments: Iterable[_TranscriptionSegment],
    limits: VideoTranscriptionLimits,
) -> tuple[NormalizedTranscriptSegment, ...]:
    normalized: list[NormalizedTranscriptSegment] = []
    previous_end = 0
    for raw in raw_segments:
        if len(normalized) >= limits.max_segment_count:
            raise AdapterProtocolError(AdapterExitCode.SCHEMA_INVALID)
        start_ms = normalize_timestamp_ms(raw.start)
        end_ms = normalize_timestamp_ms(raw.end)
        if start_ms < previous_end:
            if previous_end - start_ms > 1:
                raise AdapterProtocolError(AdapterExitCode.SCHEMA_INVALID)
            start_ms = previous_end
        text = raw.text.strip()
        if (
            not text
            or end_ms <= start_ms
            or end_ms > limits.max_media_duration_ms
        ):
            raise AdapterProtocolError(AdapterExitCode.SCHEMA_INVALID)
        normalized.append(NormalizedTranscriptSegment(start_ms, end_ms, text))
        previous_end = end_ms
    if not normalized:
        raise AdapterProtocolError(AdapterExitCode.EMPTY_TRANSCRIPT)
    return tuple(normalized)


def transcribe_media(
    path: Path,
    config: FasterWhisperTranscriptionConfig,
) -> ParsedVideoTranscript:
    try:
        model_factory, library_version = _load_whisper_runtime()
    except ImportError as error:
        raise AdapterProtocolError(AdapterExitCode.DEPENDENCY_MISSING) from error
    media = probe_media(path, config.limits)
    normalized, provenance = transcribe_cached_media(
        str(path),
        config=config,
        model_factory=VersionedWhisperModelFactory(model_factory, library_version),
    )
    if any(segment.end_ms > media.duration_ms for segment in normalized):
        raise AdapterProtocolError(AdapterExitCode.SCHEMA_INVALID)
    segments = tuple(
        VideoTranscriptSegment(segment.start_ms, segment.end_ms, segment.text)
        for segment in normalized
    )
    return ParsedVideoTranscript(
        media=media,
        segments=segments,
        transcription_provenance=provenance,
    )


def _load_whisper_runtime() -> tuple[_TranscribingModelFactory, str]:
    import_module("av")
    faster_whisper = import_module("faster_whisper")
    return (
        cast(_TranscribingModelFactory, faster_whisper.WhisperModel),
        cast(str, faster_whisper.__version__),
    )
