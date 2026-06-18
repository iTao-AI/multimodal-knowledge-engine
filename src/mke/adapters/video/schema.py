"""Parser and validator for project-owned video transcript JSON."""

from __future__ import annotations

import json
import re
from typing import Any, cast

from mke.adapters.video.contracts import VideoTranscriptionLimits
from mke.adapters.video.errors import VideoExtractionError
from mke.domain import (
    ParsedVideoTranscript,
    TranscriptionProvenance,
    VideoMediaInfo,
    VideoTranscriptSegment,
)

_TRANSCRIPT_FORMAT = "mke.video_transcript.v1"
_SUPPORTED_CONTAINER = "mp4"
_SUPPORTED_VIDEO_CODEC = "h264"
_SUPPORTED_AUDIO_CODEC = "aac"
_MAX_IDENTITY_LENGTH = 256
_COMMIT_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
_DEFAULT_LIMITS = VideoTranscriptionLimits()
_PROVENANCE_FIELDS = (
    "provider",
    "model",
    "model_revision",
    "library_version",
    "device",
    "compute_type",
    "language",
    "detected_language",
    "model_source",
    "transcription_duration_ms",
)


def parse_transcript_payload(
    payload: object,
    *,
    require_provenance: bool = False,
    limits: VideoTranscriptionLimits = _DEFAULT_LIMITS,
) -> ParsedVideoTranscript:
    """Parse provider-neutral transcript payload into validated timestamp Evidence inputs."""
    if not isinstance(payload, dict):
        raise VideoExtractionError("video transcript must be a JSON object")
    transcript = cast(dict[str, object], payload)
    if transcript.get("format") != _TRANSCRIPT_FORMAT:
        raise VideoExtractionError("video transcript format is unsupported")
    if transcript.get("transcription_error"):
        raise VideoExtractionError("transcription failed")

    media = _parse_media(_require_object(transcript, "media"), limits)
    raw_segments = transcript.get("segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        raise VideoExtractionError("video transcript must contain at least one segment")
    segment_payloads = cast(list[object], raw_segments)
    if len(segment_payloads) > limits.max_segment_count:
        raise VideoExtractionError("video transcript exceeds segment limit")
    segments = _parse_segments(segment_payloads, media.duration_ms)
    provenance = _parse_provenance(transcript.get("transcription"), require_provenance)
    return ParsedVideoTranscript(
        media=media,
        segments=segments,
        transcription_provenance=provenance,
    )


def load_transcript_json(
    text: str,
    *,
    require_provenance: bool = False,
    limits: VideoTranscriptionLimits = _DEFAULT_LIMITS,
) -> ParsedVideoTranscript:
    """Parse transcript JSON text from a sidecar file or provider stdout."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise VideoExtractionError("video transcript is not valid JSON") from error
    return parse_transcript_payload(
        payload,
        require_provenance=require_provenance,
        limits=limits,
    )


def _require_object(payload: dict[str, object], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise VideoExtractionError(f"video transcript missing {key}")
    return cast(dict[str, Any], value)


def _parse_media(
    media: dict[str, Any], limits: VideoTranscriptionLimits
) -> VideoMediaInfo:
    if media.get("has_audio") is not True:
        raise VideoExtractionError("video must contain an audio track")
    if (
        media.get("container") != _SUPPORTED_CONTAINER
        or media.get("video_codec") != _SUPPORTED_VIDEO_CODEC
        or media.get("audio_codec") != _SUPPORTED_AUDIO_CODEC
    ):
        raise VideoExtractionError("unsupported codec for local video proof")
    duration_ms = media.get("duration_ms")
    if type(duration_ms) is not int or duration_ms <= 0:
        raise VideoExtractionError("video media duration must be positive integer milliseconds")
    if duration_ms > limits.max_media_duration_ms:
        raise VideoExtractionError("video media exceeds duration limit")
    return VideoMediaInfo(
        container=_bounded_string(media.get("container"), "media container"),
        video_codec=_bounded_string(media.get("video_codec"), "video codec"),
        audio_codec=_bounded_string(media.get("audio_codec"), "audio codec"),
        has_audio=True,
        duration_ms=duration_ms,
    )


def _parse_provenance(
    value: object, require_provenance: bool
) -> TranscriptionProvenance | None:
    if value is None and not require_provenance:
        return None
    if not isinstance(value, dict):
        raise VideoExtractionError("video transcript transcription provenance is incomplete")
    provenance = cast(dict[str, object], value)
    if any(field not in provenance for field in _PROVENANCE_FIELDS):
        raise VideoExtractionError("video transcript transcription provenance is incomplete")
    provider = _bounded_string(provenance["provider"], "transcription provider")
    if provider != "faster-whisper":
        raise VideoExtractionError("transcription provider is unsupported")
    model_revision = _bounded_string(
        provenance["model_revision"], "transcription model revision"
    )
    if _COMMIT_SHA_RE.fullmatch(model_revision) is None:
        raise VideoExtractionError("transcription model revision must be a commit SHA")
    duration_ms = provenance["transcription_duration_ms"]
    if type(duration_ms) is not int or duration_ms < 0:
        raise VideoExtractionError(
            "transcription duration must be non-negative integer milliseconds"
        )
    try:
        return TranscriptionProvenance(
            provider=provider,
            model=_bounded_string(provenance["model"], "transcription model"),
            model_revision=model_revision,
            library_version=_bounded_string(
                provenance["library_version"], "transcription library version"
            ),
            device=_bounded_string(provenance["device"], "transcription device"),
            compute_type=_bounded_string(
                provenance["compute_type"], "transcription compute type"
            ),
            language=_bounded_string(provenance["language"], "transcription language"),
            detected_language=_bounded_string(
                provenance["detected_language"], "detected language"
            ),
            model_source=_bounded_string(
                provenance["model_source"], "transcription model source"
            ),
            transcription_duration_ms=duration_ms,
        )
    except VideoExtractionError:
        raise
    except ValueError as error:
        raise VideoExtractionError(
            "video transcript transcription provenance is invalid"
        ) from error


def _bounded_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VideoExtractionError(f"{label} must not be blank")
    if len(value) > _MAX_IDENTITY_LENGTH:
        raise VideoExtractionError(f"{label} exceeds bounded length")
    return value


def _parse_segments(
    raw_segments: list[object], media_duration_ms: int
) -> tuple[VideoTranscriptSegment, ...]:
    segments: list[VideoTranscriptSegment] = []
    previous_end = 0
    for raw_segment in raw_segments:
        if not isinstance(raw_segment, dict):
            raise VideoExtractionError("video transcript segment must be an object")
        segment = _segment_from_payload(cast(dict[str, object], raw_segment))
        if segment.start_ms < previous_end:
            raise VideoExtractionError(
                "stable timestamp locator generation requires sorted ranges"
            )
        if segment.end_ms > media_duration_ms:
            raise VideoExtractionError("video transcript segment exceeds media duration")
        segments.append(segment)
        previous_end = segment.end_ms
    return tuple(segments)


def _segment_from_payload(payload: dict[str, object]) -> VideoTranscriptSegment:
    start_ms = payload.get("start_ms")
    end_ms = payload.get("end_ms")
    text = payload.get("text")
    if type(start_ms) is not int or type(end_ms) is not int:
        raise VideoExtractionError("timestamp locators must be integer milliseconds")
    if start_ms < 0 or end_ms <= start_ms:
        raise VideoExtractionError(
            "stable timestamp locator generation requires increasing ranges"
        )
    if not isinstance(text, str) or not text.strip():
        raise VideoExtractionError("video transcript text must not be empty")
    return VideoTranscriptSegment(start_ms=start_ms, end_ms=end_ms, text=text)
