import json
from pathlib import Path

import pytest

from mke.application import KnowledgeEngine, VideoIngestError
from mke.domain import RunState
from tests.conftest import PDF_FIXTURES, VIDEO_FIXTURES


def test_video_ingest_publishes_timestamp_evidence_to_active_search(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    result = engine.ingest_video(VIDEO_FIXTURES / "short-audio.mp4")

    assert result.run_state == RunState.PUBLISHED
    assert result.evidence_count == 2
    matches = engine.search("introduces")
    assert [
        (match.locator_kind, match.locator_start, match.locator_end, match.text)
        for match in matches
    ] == [
        (
            "timestamp_ms",
            0,
            1200,
            "Video evidence introduces timestamp search.",
        )
    ]


def test_pdf_and_video_share_active_search_projection(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
    engine.ingest_video(VIDEO_FIXTURES / "short-audio.mp4")

    assert [match.page_number for match in engine.search("trustworthy")] == [1]
    video_matches = engine.search("spoken timestamp proof")
    assert [
        (match.locator_kind, match.locator_start, match.locator_end)
        for match in video_matches
    ] == [
        ("timestamp_ms", 1200, 2200)
    ]


@pytest.mark.parametrize(
    ("sidecar_payload", "match"),
    [
        (
            {
                "format": "mke.video_transcript.v1",
                "media": {
                    "container": "mp4",
                    "video_codec": "h264",
                    "audio_codec": "aac",
                    "has_audio": False,
                    "duration_ms": 1000,
                },
                "segments": [{"start_ms": 0, "end_ms": 1000, "text": "missing audio"}],
            },
            "audio",
        ),
        (
            {
                "format": "mke.video_transcript.v1",
                "media": {
                    "container": "webm",
                    "video_codec": "vp9",
                    "audio_codec": "opus",
                    "has_audio": True,
                    "duration_ms": 1000,
                },
                "segments": [{"start_ms": 0, "end_ms": 1000, "text": "unsupported"}],
            },
            "unsupported codec",
        ),
        (
            {
                "format": "mke.video_transcript.v1",
                "media": {
                    "container": "mp4",
                    "video_codec": "h264",
                    "audio_codec": "aac",
                    "has_audio": True,
                    "duration_ms": 1000,
                },
                "transcription_error": "provider failed",
                "segments": [],
            },
            "transcription failed",
        ),
        (
            {
                "format": "mke.video_transcript.v1",
                "media": {
                    "container": "mp4",
                    "video_codec": "h264",
                    "audio_codec": "aac",
                    "has_audio": True,
                    "duration_ms": 1000,
                },
                "segments": [
                    {"start_ms": 0, "end_ms": 800, "text": "first"},
                    {"start_ms": 700, "end_ms": 1000, "text": "overlap"},
                ],
            },
            "stable timestamp",
        ),
    ],
)
def test_video_failures_do_not_change_active_pdf_search(
    tmp_path: Path, sidecar_payload: dict[str, object], match: str
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
    before = [match.text for match in engine.search("trustworthy")]

    video = tmp_path / "bad.mp4"
    video.write_bytes(b"fake mp4 bytes")
    video.with_suffix(video.suffix + ".mke-transcript.json").write_text(json.dumps(sidecar_payload))

    with pytest.raises(VideoIngestError, match=match):
        engine.ingest_video(video)

    assert [match.text for match in engine.search("trustworthy")] == before
