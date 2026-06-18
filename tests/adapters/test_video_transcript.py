from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from mke.adapters.video import VideoExtractionError, extract_transcript_segments
from mke.adapters.video.contracts import VideoTranscriptionLimits
from mke.adapters.video.schema import load_transcript_json, parse_transcript_payload
from mke.domain import ParsedVideoTranscript
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


def test_parse_transcript_payload_returns_timestamp_segments() -> None:
    parsed = parse_transcript_payload(
        {
            "format": "mke.video_transcript.v1",
            "media": {
                "container": "mp4",
                "video_codec": "h264",
                "audio_codec": "aac",
                "has_audio": True,
                "duration_ms": 2200,
            },
            "segments": [
                {"start_ms": 0, "end_ms": 1200, "text": "first"},
                {"start_ms": 1200, "end_ms": 2200, "text": "second"},
            ],
        }
    )

    assert isinstance(parsed, ParsedVideoTranscript)
    assert parsed.media.duration_ms == 2200
    assert parsed.transcription_provenance is None
    assert [(segment.start_ms, segment.end_ms, segment.text) for segment in parsed.segments] == [
        (0, 1200, "first"),
        (1200, 2200, "second"),
    ]


def _first_party_payload() -> dict[str, object]:
    return {
        "format": "mke.video_transcript.v1",
        "media": {
            "container": "mp4",
            "video_codec": "h264",
            "audio_codec": "aac",
            "has_audio": True,
            "duration_ms": 2200,
        },
        "transcription": {
            "provider": "faster-whisper",
            "model": "small",
            "model_revision": "a" * 40,
            "library_version": "1.2.3",
            "device": "cpu",
            "compute_type": "int8",
            "language": "auto",
            "detected_language": "en",
            "model_source": "cache",
            "transcription_duration_ms": 500,
        },
        "segments": [
            {"start_ms": 0, "end_ms": 1200, "text": "first"},
            {"start_ms": 1200, "end_ms": 2200, "text": "second"},
        ],
    }


def test_first_party_parse_requires_and_returns_complete_provenance() -> None:
    payload = _first_party_payload()
    transcription = payload["transcription"]
    assert isinstance(transcription, dict)
    transcription["ignored_future_field"] = "ignored"

    parsed = parse_transcript_payload(payload, require_provenance=True)

    assert parsed.transcription_provenance is not None
    assert parsed.transcription_provenance.provider == "faster-whisper"
    assert not hasattr(parsed.transcription_provenance, "ignored_future_field")


@pytest.mark.parametrize("missing_field", ["transcription", "model_revision"])
def test_first_party_parse_rejects_missing_or_partial_provenance(missing_field: str) -> None:
    payload = _first_party_payload()
    if missing_field == "transcription":
        del payload[missing_field]
    else:
        transcription = payload["transcription"]
        assert isinstance(transcription, dict)
        del transcription[missing_field]

    with pytest.raises(VideoExtractionError, match="transcription provenance"):
        parse_transcript_payload(payload, require_provenance=True)


@pytest.mark.parametrize(
    ("target", "field", "value", "match"),
    [
        ("media", "duration_ms", 0, "duration"),
        ("segment", "end_ms", 2300, "media duration"),
        ("transcription", "provider", "other", "provider"),
        ("transcription", "model_revision", "abc", "revision"),
        ("transcription", "model", "x" * 257, "bounded"),
    ],
)
def test_parser_rejects_invalid_media_provenance_and_segments(
    target: str, field: str, value: object, match: str
) -> None:
    payload = _first_party_payload()
    if target == "segment":
        segments = payload["segments"]
        assert isinstance(segments, list)
        segment = cast(list[object], segments)[0]
        assert isinstance(segment, dict)
        segment[field] = value
    else:
        section = payload[target]
        assert isinstance(section, dict)
        section[field] = value

    with pytest.raises(VideoExtractionError, match=match):
        parse_transcript_payload(payload, require_provenance=True)


def test_parser_enforces_configured_segment_count_limit() -> None:
    payload = _first_party_payload()
    limits = VideoTranscriptionLimits(max_segment_count=1)

    with pytest.raises(VideoExtractionError, match="segment limit"):
        parse_transcript_payload(payload, require_provenance=True, limits=limits)


def test_shared_json_parser_uses_provider_neutral_error() -> None:
    with pytest.raises(VideoExtractionError) as exc_info:
        load_transcript_json("{bad")

    assert str(exc_info.value) == "video transcript is not valid JSON"


def test_missing_sidecar_error_remains_sidecar_specific(tmp_path: Path) -> None:
    video = tmp_path / "missing-sidecar.mp4"
    video.write_bytes(b"video")

    with pytest.raises(VideoExtractionError) as exc_info:
        extract_transcript_segments(video)

    assert str(exc_info.value) == "video transcript sidecar is missing"


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
    payload = {
        "format": "mke.video_transcript.v1",
        "media": {
            "container": "mp4",
            "video_codec": "h264",
            "audio_codec": "aac",
            "has_audio": True,
            "duration_ms": 1000,
        },
        "segments": [segment_payload],
    }

    with pytest.raises(VideoExtractionError, match=match):
        parse_transcript_payload(payload)
