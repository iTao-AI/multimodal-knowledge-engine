from __future__ import annotations

from pathlib import Path

from mke.application import KnowledgeEngine
from mke.domain import (
    LOCAL_COMMAND_VIDEO_TRANSCRIPT_FINGERPRINT,
    RunState,
    TranscriptExtractionResult,
    VideoTranscriptSegment,
)


class FakeTranscriptProvider:
    def extract(self, path: Path) -> TranscriptExtractionResult:
        return TranscriptExtractionResult(
            segments=(VideoTranscriptSegment(0, 1000, "fake command transcript"),),
            extractor_fingerprint=LOCAL_COMMAND_VIDEO_TRANSCRIPT_FINGERPRINT,
        )


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
