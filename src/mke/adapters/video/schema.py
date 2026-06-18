"""Parser and validator for project-owned video transcript JSON."""

from __future__ import annotations

import json
from typing import Any, cast

from mke.adapters.video.errors import VideoExtractionError
from mke.domain import VideoTranscriptSegment

_TRANSCRIPT_FORMAT = "mke.video_transcript.v1"
_SUPPORTED_CONTAINER = "mp4"
_SUPPORTED_VIDEO_CODEC = "h264"
_SUPPORTED_AUDIO_CODEC = "aac"


def parse_transcript_payload(payload: object) -> tuple[VideoTranscriptSegment, ...]:
    """Parse provider-neutral transcript payload into timestamp segments."""
    if not isinstance(payload, dict):
        raise VideoExtractionError("video transcript sidecar must be a JSON object")
    transcript = cast(dict[str, object], payload)
    if transcript.get("format") != _TRANSCRIPT_FORMAT:
        raise VideoExtractionError("video transcript sidecar format is unsupported")
    if transcript.get("transcription_error"):
        raise VideoExtractionError("transcription failed")

    media = _require_object(transcript, "media")
    _validate_media(media)

    raw_segments = transcript.get("segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        raise VideoExtractionError("video transcript must contain at least one segment")
    return _parse_segments(cast(list[object], raw_segments))


def load_transcript_json(text: str) -> tuple[VideoTranscriptSegment, ...]:
    """Parse transcript JSON text from a sidecar file or provider stdout."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise VideoExtractionError("video transcript sidecar is not valid JSON") from error
    return parse_transcript_payload(payload)


def _require_object(payload: dict[str, object], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise VideoExtractionError(f"video transcript sidecar missing {key}")
    return cast(dict[str, Any], value)


def _validate_media(media: dict[str, Any]) -> None:
    if media.get("has_audio") is not True:
        raise VideoExtractionError("video must contain an audio track")
    if (
        media.get("container") != _SUPPORTED_CONTAINER
        or media.get("video_codec") != _SUPPORTED_VIDEO_CODEC
        or media.get("audio_codec") != _SUPPORTED_AUDIO_CODEC
    ):
        raise VideoExtractionError("unsupported codec for local video proof")


def _parse_segments(raw_segments: list[object]) -> tuple[VideoTranscriptSegment, ...]:
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
