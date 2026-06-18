from __future__ import annotations

import json
from pathlib import Path

import pytest

from mke.adapters.video.contracts import AdapterExitCode
from mke.adapters.video.faster_whisper import AdapterProtocolError
from mke.adapters.video.faster_whisper_cli import main
from mke.domain import (
    ParsedVideoTranscript,
    TranscriptionProvenance,
    VideoMediaInfo,
    VideoTranscriptSegment,
)
from mke.runtime import FasterWhisperTranscriptionConfig


def _parsed() -> ParsedVideoTranscript:
    return ParsedVideoTranscript(
        media=VideoMediaInfo("mp4", "h264", "aac", True, 1000),
        segments=(VideoTranscriptSegment(0, 1000, "speech"),),
        transcription_provenance=TranscriptionProvenance(
            provider="faster-whisper",
            model="small",
            model_revision="a" * 40,
            library_version="1.2.1",
            device="cpu",
            compute_type="int8",
            language="auto",
            detected_language="en",
            model_source="cache",
            transcription_duration_ms=5,
        ),
    )


def test_adapter_cli_writes_exactly_one_compact_protocol_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    video = tmp_path / "speech.mp4"
    video.write_bytes(b"x")

    def fake_transcribe(
        path: Path, config: FasterWhisperTranscriptionConfig
    ) -> ParsedVideoTranscript:
        return _parsed()

    monkeypatch.setattr("mke.adapters.video.faster_whisper_cli.transcribe_media", fake_transcribe)

    exit_code = main([str(video), "--model-revision", "a" * 40])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert captured.out.count("\n") == 1
    payload = json.loads(captured.out)
    assert payload["format"] == "mke.video_transcript.v1"
    assert payload["segments"] == [{"start_ms": 0, "end_ms": 1000, "text": "speech"}]


def test_adapter_cli_maps_known_failure_without_serializing_raw_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    video = tmp_path / "speech.mp4"
    video.write_bytes(b"x")

    def fail(path: Path, config: object) -> object:
        raise AdapterProtocolError(AdapterExitCode.MEDIA_NO_AUDIO, "private path")

    monkeypatch.setattr("mke.adapters.video.faster_whisper_cli.transcribe_media", fail)

    exit_code = main([str(video), "--model-revision", "a" * 40])

    captured = capsys.readouterr()
    assert exit_code == AdapterExitCode.MEDIA_NO_AUDIO
    assert captured.out == ""
    assert "private path" not in captured.err
