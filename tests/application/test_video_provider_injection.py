from __future__ import annotations

from pathlib import Path

import pytest

from mke.adapters.video import VideoExtractionError
from mke.application import KnowledgeEngine, VideoIngestError
from mke.domain import (
    LOCAL_COMMAND_VIDEO_TRANSCRIPT_FINGERPRINT,
    ParsedVideoTranscript,
    RunState,
    TranscriptExtractionResult,
    VideoMediaInfo,
    VideoTranscriptSegment,
)
from tests.conftest import VIDEO_FIXTURES


class FakeTranscriptProvider:
    def extract(self, path: Path) -> TranscriptExtractionResult:
        return TranscriptExtractionResult(
            parsed_transcript=ParsedVideoTranscript(
                media=VideoMediaInfo("mp4", "h264", "aac", True, 1000),
                segments=(VideoTranscriptSegment(0, 1000, "fake command transcript"),),
            ),
            extractor_fingerprint=LOCAL_COMMAND_VIDEO_TRANSCRIPT_FINGERPRINT,
        )


class FailingTranscriptProvider:
    def extract(self, path: Path) -> TranscriptExtractionResult:
        raise VideoExtractionError("transcript command failed")


def test_knowledge_engine_accepts_injected_transcript_provider(tmp_path: Path) -> None:
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake mp4 bytes")
    engine = KnowledgeEngine(tmp_path / "mke.sqlite", transcript_provider=FakeTranscriptProvider())

    result = engine.ingest_video(video)

    assert result.run_state == RunState.PUBLISHED
    assert result.evidence_count == 1
    assert [match.text for match in engine.search("fake command")] == [
        "fake command transcript"
    ]


def test_failed_transcript_provider_leaves_active_search_unchanged(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    engine.ingest_video(VIDEO_FIXTURES / "short-audio.mp4")
    before = [match.text for match in engine.search("timestamp proof")]
    failed_video = tmp_path / "failed.mp4"
    failed_video.write_bytes(b"fake mp4 bytes")
    failing = KnowledgeEngine(
        tmp_path / "mke.sqlite",
        transcript_provider=FailingTranscriptProvider(),
    )

    with pytest.raises(VideoIngestError, match="transcript command failed"):
        failing.ingest_video(failed_video)

    assert [match.text for match in engine.search("timestamp proof")] == before
