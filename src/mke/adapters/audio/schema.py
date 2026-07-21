"""Closed parser for the project-owned direct-audio transcript protocol."""

from __future__ import annotations

import re
from typing import Literal, cast

from mke.adapters.audio.contracts import AudioTranscriptionLimits
from mke.domain import (
    AudioMediaInfo,
    AudioTranscriptSegment,
    ParsedAudioTranscript,
    TranscriptionProvenance,
)

_TRANSCRIPT_FIELDS = frozenset({"format", "media", "segments", "transcription"})
_MEDIA_FIELDS = frozenset({"audio_codec", "channels", "container", "duration_ms", "sample_rate_hz"})
_SEGMENT_FIELDS = frozenset({"end_ms", "start_ms", "text"})
_PROVENANCE_FIELDS = frozenset(
    {
        "compute_type",
        "detected_language",
        "device",
        "language",
        "library_version",
        "model",
        "model_revision",
        "model_source",
        "provider",
        "transcription_duration_ms",
    }
)
_COMMIT_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
_MAX_IDENTITY_LENGTH = 256
_DEFAULT_LIMITS = AudioTranscriptionLimits()


class AudioTranscriptValidationError(ValueError):
    """Raised when the internal audio transcript protocol fails closed validation."""


def parse_audio_transcript_payload(
    payload: object,
    *,
    limits: AudioTranscriptionLimits = _DEFAULT_LIMITS,
) -> ParsedAudioTranscript:
    if not isinstance(payload, dict):
        raise AudioTranscriptValidationError("audio transcript must be a JSON object")
    transcript = cast(dict[str, object], payload)
    _require_exact_fields(transcript, _TRANSCRIPT_FIELDS, "audio transcript")
    if transcript["format"] != "mke.audio_transcript.v1":
        raise AudioTranscriptValidationError("audio transcript format is unsupported")
    media_payload = _require_object(transcript["media"], "audio transcript media")
    media = _parse_media(media_payload, limits)
    segments_payload = transcript["segments"]
    if not isinstance(segments_payload, list) or not segments_payload:
        raise AudioTranscriptValidationError("audio transcript must contain at least one segment")
    typed_segments = cast(list[object], segments_payload)
    if len(typed_segments) > limits.max_segment_count:
        raise AudioTranscriptValidationError("audio transcript exceeds segment limit")
    segments = _parse_segments(typed_segments, media.duration_ms)
    provenance = _parse_provenance(transcript["transcription"])
    try:
        return ParsedAudioTranscript(
            media=media,
            segments=segments,
            transcription_provenance=provenance,
        )
    except ValueError as error:
        raise AudioTranscriptValidationError(str(error)) from error


def _parse_media(payload: dict[str, object], limits: AudioTranscriptionLimits) -> AudioMediaInfo:
    _require_exact_fields(payload, _MEDIA_FIELDS, "audio media")
    channels = payload["channels"]
    sample_rate_hz = payload["sample_rate_hz"]
    duration_ms = payload["duration_ms"]
    if type(channels) is not int or channels not in {1, 2}:
        raise AudioTranscriptValidationError("audio media channels must be one or two")
    if type(sample_rate_hz) is not int or not 8_000 <= sample_rate_hz <= 48_000:
        raise AudioTranscriptValidationError("audio media sample rate is unsupported")
    if (
        type(duration_ms) is not int
        or duration_ms <= 0
        or duration_ms > limits.max_media_duration_ms
    ):
        raise AudioTranscriptValidationError("audio media duration is unsupported")
    container = payload["container"]
    codec = payload["audio_codec"]
    if type(container) is not str or type(codec) is not str or (container, codec) not in {
        ("mp3", "mp3"),
        ("wav", "pcm_s16le"),
        ("m4a", "aac"),
    }:
        raise AudioTranscriptValidationError("audio media profile is unsupported")
    return AudioMediaInfo(
        container=cast(Literal["mp3", "wav", "m4a"], container),
        audio_codec=cast(Literal["mp3", "pcm_s16le", "aac"], codec),
        channels=channels,
        sample_rate_hz=sample_rate_hz,
        duration_ms=duration_ms,
    )


def _parse_segments(
    payloads: list[object], media_duration_ms: int
) -> tuple[AudioTranscriptSegment, ...]:
    parsed: list[AudioTranscriptSegment] = []
    previous_end = 0
    for value in payloads:
        segment_payload = _require_object(value, "audio transcript segment")
        _require_exact_fields(segment_payload, _SEGMENT_FIELDS, "audio transcript segment")
        start_ms = segment_payload["start_ms"]
        end_ms = segment_payload["end_ms"]
        if type(start_ms) is not int or type(end_ms) is not int:
            raise AudioTranscriptValidationError("audio timestamps must be integer milliseconds")
        if start_ms < 0 or end_ms <= start_ms:
            raise AudioTranscriptValidationError("audio timestamps must use increasing ranges")
        if start_ms < previous_end:
            raise AudioTranscriptValidationError(
                "audio transcript ranges must be sorted and non-overlapping"
            )
        if end_ms > media_duration_ms:
            raise AudioTranscriptValidationError("audio transcript segment exceeds media duration")
        try:
            segment = AudioTranscriptSegment(
                start_ms=start_ms,
                end_ms=end_ms,
                text=cast("str", segment_payload["text"]),
            )
        except (TypeError, ValueError) as error:
            raise AudioTranscriptValidationError(str(error)) from error
        parsed.append(segment)
        previous_end = segment.end_ms
    return tuple(parsed)


def _parse_provenance(value: object) -> TranscriptionProvenance | None:
    if value is None:
        return None
    provenance = _require_object(value, "audio transcript transcription")
    _require_exact_fields(provenance, _PROVENANCE_FIELDS, "audio transcription")
    provider = _bounded_string(provenance["provider"], "transcription provider")
    if provider != "faster-whisper":
        raise AudioTranscriptValidationError("transcription provider is unsupported")
    revision = _bounded_string(provenance["model_revision"], "transcription model revision")
    if _COMMIT_SHA_RE.fullmatch(revision) is None:
        raise AudioTranscriptValidationError("transcription model revision must be a commit SHA")
    duration_ms = provenance["transcription_duration_ms"]
    if type(duration_ms) is not int or duration_ms < 0:
        raise AudioTranscriptValidationError(
            "transcription duration must be non-negative integer milliseconds"
        )
    try:
        return TranscriptionProvenance(
            provider=provider,
            model=_bounded_string(provenance["model"], "transcription model"),
            model_revision=revision,
            library_version=_bounded_string(
                provenance["library_version"], "transcription library version"
            ),
            device=_bounded_string(provenance["device"], "transcription device"),
            compute_type=_bounded_string(provenance["compute_type"], "transcription compute type"),
            language=_bounded_string(provenance["language"], "transcription language"),
            detected_language=_bounded_string(provenance["detected_language"], "detected language"),
            model_source=_bounded_string(provenance["model_source"], "transcription model source"),
            transcription_duration_ms=duration_ms,
        )
    except ValueError as error:
        raise AudioTranscriptValidationError(
            "audio transcript transcription provenance is invalid"
        ) from error


def _bounded_string(value: object, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise AudioTranscriptValidationError(f"{label} must not be blank")
    if len(value) > _MAX_IDENTITY_LENGTH:
        raise AudioTranscriptValidationError(f"{label} exceeds bounded length")
    return value


def _require_object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise AudioTranscriptValidationError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _require_exact_fields(value: dict[str, object], expected: frozenset[str], label: str) -> None:
    if frozenset(value) != expected:
        raise AudioTranscriptValidationError(f"{label} fields are invalid")
