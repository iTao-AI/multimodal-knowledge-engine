from __future__ import annotations

from pathlib import Path

import pytest

from mke.adapters.video import VideoExtractionError
from mke.adapters.video.contracts import faster_whisper_fingerprint
from mke.application import KnowledgeEngine, VideoIngestError
from mke.domain import (
    LOCAL_COMMAND_VIDEO_TRANSCRIPT_FINGERPRINT,
    ParsedVideoTranscript,
    RunState,
    TranscriptExtractionResult,
    TranscriptIntakeReport,
    TranscriptionProvenance,
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


def _faster_whisper_provenance() -> TranscriptionProvenance:
    return TranscriptionProvenance(
        provider="faster-whisper",
        model="small",
        model_revision="a" * 40,
        library_version="1.2.3",
        device="cpu",
        compute_type="int8",
        language="auto",
        detected_language="en",
        model_source="cache",
        transcription_duration_ms=250,
    )


class FakeFasterWhisperProvider:
    def extract(self, path: Path) -> TranscriptExtractionResult:
        provenance = _faster_whisper_provenance()
        parsed = ParsedVideoTranscript(
            media=VideoMediaInfo("mp4", "h264", "aac", True, 1000),
            segments=(VideoTranscriptSegment(0, 1000, "faster whisper transcript"),),
            transcription_provenance=provenance,
        )
        report = TranscriptIntakeReport(
            provider=provenance.provider,
            model=provenance.model,
            model_revision=provenance.model_revision,
            library_version=provenance.library_version,
            device=provenance.device,
            compute_type=provenance.compute_type,
            language=provenance.language,
            detected_language=provenance.detected_language,
            media_duration_ms=parsed.media.duration_ms,
            transcription_duration_ms=provenance.transcription_duration_ms,
            segment_count=len(parsed.segments),
            model_source=provenance.model_source,
        )
        return TranscriptExtractionResult(
            parsed_transcript=parsed,
            extractor_fingerprint=faster_whisper_fingerprint(provenance),
            transcript_intake_report=report,
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


def test_faster_whisper_ingest_returns_and_persists_successful_report(tmp_path: Path) -> None:
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake mp4 bytes")
    engine = KnowledgeEngine(
        tmp_path / "mke.sqlite",
        transcript_provider=FakeFasterWhisperProvider(),
    )

    result = engine.ingest_video(video)

    assert result.run_state == RunState.PUBLISHED
    assert result.transcript_intake_report is not None
    assert result.transcript_intake_report.provider == "faster-whisper"
    assert engine.get_transcript_intake_report(result.run_id) == (
        result.transcript_intake_report
    )


@pytest.mark.parametrize("input_kind", ["missing", "empty", "non_mp4", "oversized"])
def test_video_preflight_rejects_before_hash_provider_or_run_creation(
    tmp_path: Path,
    input_kind: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / ("sample.txt" if input_kind == "non_mp4" else "sample.mp4")
    if input_kind == "empty" or input_kind == "non_mp4":
        path.write_bytes(b"" if input_kind == "empty" else b"content")
    elif input_kind == "oversized":
        with path.open("wb") as handle:
            handle.truncate((100 * 1024 * 1024) + 1)
    provider = FakeFasterWhisperProvider()
    engine = KnowledgeEngine(tmp_path / "mke.sqlite", transcript_provider=provider)

    def fail_if_called(*args: object, **kwargs: object) -> object:
        raise AssertionError("preflight must run before hashing, provider, or Run creation")

    monkeypatch.setattr("mke.application._sha256_file", fail_if_called)
    monkeypatch.setattr(provider, "extract", fail_if_called)
    monkeypatch.setattr(engine, "create_run", fail_if_called)

    with pytest.raises(VideoIngestError):
        engine.ingest_video(path)
