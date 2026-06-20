from __future__ import annotations

import hashlib
import importlib
import importlib.util
import os
from pathlib import Path

import pytest

from mke.adapters.video.contracts import VideoTranscriptionLimits

EXPECTED_SHA256 = "6c2a57a73ee01976bccfcfe73f3334d8d1675a891ccc5868d68fa2caadf27e3e"
EXPECTED_SIZE_BYTES = 33_171


def _spoken_fixture(video_fixtures: Path) -> Path:
    return video_fixtures / "spoken-evidence.mp4"


def test_spoken_fixture_has_stable_identity_and_no_sidecar(video_fixtures: Path) -> None:
    fixture = _spoken_fixture(video_fixtures)

    assert fixture.is_file()
    assert fixture.stat().st_size == EXPECTED_SIZE_BYTES
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == EXPECTED_SHA256
    assert not Path(f"{fixture}.mke-transcript.json").exists()


def test_spoken_fixture_matches_the_bounded_mp4_profile(video_fixtures: Path) -> None:
    fixture = _spoken_fixture(video_fixtures)
    if importlib.util.find_spec("av") is None:
        if os.environ.get("MKE_REQUIRE_TRANSCRIPTION_EXTRA") == "1":
            pytest.fail("PyAV is required when MKE_REQUIRE_TRANSCRIPTION_EXTRA=1")
        pytest.skip("transcription extra is not installed")

    av = importlib.import_module("av")
    limits = VideoTranscriptionLimits()

    with av.open(str(fixture)) as container:
        assert "mp4" in container.format.name.split(",")
        assert container.streams.video
        assert container.streams.audio
        assert container.streams.video[0].codec_context.name == "h264"
        assert container.streams.audio[0].codec_context.name == "aac"
        assert container.duration is not None
        assert 0 < container.duration <= limits.max_media_duration_ms * 1000

    assert 0 < fixture.stat().st_size <= limits.max_input_bytes
