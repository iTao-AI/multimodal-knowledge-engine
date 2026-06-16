from __future__ import annotations

import json
from pathlib import Path

import pytest

from mke.adapters.video import VideoExtractionError, extract_transcript_segments
from mke.adapters.video.transcript import (
    _segment_from_payload,  # pyright: ignore[reportPrivateUsage]
)
from tests.conftest import VIDEO_FIXTURES


def _write_fixture(
    tmp_path: Path, *, media: dict[str, object], segments: list[dict[str, object]]
) -> Path:
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake mp4 bytes")
    sidecar = video.with_suffix(video.suffix + ".mke-transcript.json")
    sidecar.write_text(
        json.dumps(
            {
                "format": "mke.video_transcript.v1",
                "license": "test",
                "media": media,
                "segments": segments,
            }
        )
    )
    return video


def test_extracts_deterministic_timestamp_segments() -> None:
    segments = extract_transcript_segments(VIDEO_FIXTURES / "short-audio.mp4")

    assert [(segment.start_ms, segment.end_ms, segment.text) for segment in segments] == [
        (0, 1200, "Video evidence introduces timestamp search."),
        (1200, 2200, "Active publication search finds spoken timestamp proof."),
    ]


@pytest.mark.parametrize(
    ("media", "match"),
    [
        (
            {
                "container": "mp4",
                "video_codec": "h264",
                "audio_codec": "aac",
                "has_audio": False,
                "duration_ms": 1000,
            },
            "audio",
        ),
        (
            {
                "container": "webm",
                "video_codec": "vp9",
                "audio_codec": "opus",
                "has_audio": True,
                "duration_ms": 1000,
            },
            "unsupported codec",
        ),
    ],
)
def test_rejects_missing_audio_and_unsupported_codecs(
    tmp_path: Path, media: dict[str, object], match: str
) -> None:
    video = _write_fixture(
        tmp_path,
        media=media,
        segments=[{"start_ms": 0, "end_ms": 1000, "text": "hello"}],
    )

    with pytest.raises(VideoExtractionError, match=match):
        extract_transcript_segments(video)


def test_rejects_transcription_failure_sidecar(tmp_path: Path) -> None:
    video = tmp_path / "failed.mp4"
    video.write_bytes(b"fake mp4 bytes")
    video.with_suffix(video.suffix + ".mke-transcript.json").write_text(
        json.dumps(
            {
                "format": "mke.video_transcript.v1",
                "license": "test",
                "media": {
                    "container": "mp4",
                    "video_codec": "h264",
                    "audio_codec": "aac",
                    "has_audio": True,
                    "duration_ms": 1000,
                },
                "transcription_error": "fixture transcription failed",
                "segments": [],
            }
        )
    )

    with pytest.raises(VideoExtractionError, match="transcription failed"):
        extract_transcript_segments(video)


def test_rejects_unstable_timestamp_locator_generation(tmp_path: Path) -> None:
    video = _write_fixture(
        tmp_path,
        media={
            "container": "mp4",
            "video_codec": "h264",
            "audio_codec": "aac",
            "has_audio": True,
            "duration_ms": 1000,
        },
        segments=[
            {"start_ms": 0, "end_ms": 800, "text": "first"},
            {"start_ms": 700, "end_ms": 1000, "text": "overlap"},
        ],
    )

    with pytest.raises(VideoExtractionError, match="stable timestamp"):
        extract_transcript_segments(video)


def test_rejects_malformed_json_sidecar(tmp_path: Path) -> None:
    video = tmp_path / "bad.mp4"
    video.write_bytes(b"fake mp4 bytes")
    video.with_suffix(video.suffix + ".mke-transcript.json").write_text("{bad")

    with pytest.raises(VideoExtractionError, match="not valid JSON"):
        extract_transcript_segments(video)


@pytest.mark.parametrize(
    ("content", "match"),
    [
        ("[]", "must be a JSON object"),
        (
            '{"format":"mke.video_transcript.v1","media":{"container":"mp4",'
            '"video_codec":"h264","audio_codec":"aac","has_audio":true,"duration_ms":1000},'
            '"segments":["not_a_dict"]}',
            "must be an object",
        ),
    ],
)
def test_rejects_invalid_json_structure(
    tmp_path: Path, content: str, match: str
) -> None:
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake mp4 bytes")
    video.with_suffix(video.suffix + ".mke-transcript.json").write_text(content)

    with pytest.raises(VideoExtractionError, match=match):
        extract_transcript_segments(video)


@pytest.mark.parametrize(
    ("segment_payload", "match"),
    [
        ({"start_ms": -1, "end_ms": 1000, "text": "neg"}, "increasing ranges"),
        ({"start_ms": 0, "end_ms": 0, "text": "zero"}, "increasing ranges"),
        ({"start_ms": 0.5, "end_ms": 1000, "text": "float"}, "integer milliseconds"),
        ({"start_ms": 0, "end_ms": 1000, "text": "  "}, "must not be empty"),
        ({"start_ms": 0, "end_ms": 1000, "text": 123}, "must not be empty"),
    ],
)
def test_segment_from_payload_rejects_invalid_inputs(
    segment_payload: dict[str, object], match: str
) -> None:
    with pytest.raises(VideoExtractionError, match=match):
        _segment_from_payload(segment_payload)
