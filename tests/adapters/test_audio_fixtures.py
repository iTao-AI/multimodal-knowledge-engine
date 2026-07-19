from __future__ import annotations

import hashlib
import importlib
import importlib.util
import io
import os
from dataclasses import dataclass
from pathlib import Path

import pytest

AUDIO_FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "audio"
README_PATH = AUDIO_FIXTURE_ROOT / "README.md"


@dataclass(frozen=True)
class FixtureReceipt:
    media_type: str
    bytes: int
    sha256: str
    format_tokens: frozenset[str]
    codec: str
    duration_us: int
    layout: str
    container_metadata: tuple[tuple[str, str], ...]
    stream_metadata: tuple[tuple[str, str], ...]
    aac_profile: str | None = None
    major_brand: str | None = None
    compatible_brands: str | None = None


FIXTURE_RECEIPTS = {
    "direct-audio.mp3": FixtureReceipt(
        media_type="audio/mpeg",
        bytes=22_509,
        sha256="cc10ce7b07ae0ea8434b690383bb7ef0a43f7af66aec474d410e5a9612158631",
        format_tokens=frozenset({"mp3"}),
        codec="mp3float",
        duration_us=3_630_000,
        layout="mono",
        container_metadata=(("encoder", "Lavf62.12.101"),),
        stream_metadata=(),
    ),
    "direct-audio.wav": FixtureReceipt(
        media_type="audio/wav",
        bytes=116_238,
        sha256="ec82eefefc5a6ccbbfc757864fc94bffd250bf185b03fc0404568063c8f993ac",
        format_tokens=frozenset({"wav"}),
        codec="pcm_s16le",
        duration_us=3_630_000,
        layout="1 channels",
        container_metadata=(("encoder", "Lavf62.12.101"),),
        stream_metadata=(),
    ),
    "direct-audio.m4a": FixtureReceipt(
        media_type="audio/mp4",
        bytes=24_880,
        sha256="cd7307b22b74de4fef8bda87582be791528c65d6546e4abdf42128070980e260",
        format_tokens=frozenset({"mov", "mp4", "m4a", "3gp", "3g2", "mj2"}),
        codec="aac",
        duration_us=3_630_000,
        layout="mono",
        container_metadata=(
            ("major_brand", "M4A "),
            ("minor_version", "512"),
            ("compatible_brands", "M4A isomiso2"),
            ("encoder", "Lavf62.12.101"),
        ),
        stream_metadata=(("language", "und"), ("handler_name", "SoundHandler")),
        aac_profile="LC",
        major_brand="M4A ",
        compatible_brands="M4A isomiso2",
    ),
}


@pytest.mark.parametrize(
    ("name", "expected_media_type"),
    [
        ("direct-audio.mp3", "audio/mpeg"),
        ("direct-audio.wav", "audio/wav"),
        ("direct-audio.m4a", "audio/mp4"),
    ],
)
def test_direct_audio_fixture_inventory(name: str, expected_media_type: str) -> None:
    path = AUDIO_FIXTURE_ROOT / name

    assert path.is_file()
    assert not path.is_symlink()
    receipt = FIXTURE_RECEIPTS[name]
    assert receipt.media_type == expected_media_type
    assert path.stat().st_size == receipt.bytes
    assert hashlib.sha256(path.read_bytes()).hexdigest() == receipt.sha256
    assert not Path(f"{path}.mke-transcript.json").exists()


def test_direct_audio_fixture_readme_is_the_provenance_authority() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    assert "Direct audio remains traceable after publication." in readme
    assert "Mimic 1.3.0.1" in readme
    assert "built-in `slt` / `cmu_us_slt`" in readme
    assert "2e62303fbc08223d326b6faa3699bbbfdf0e0fca335101bdb7265b4988d11cb4" in readme
    assert "Flite notice retained" in readme
    assert "License: flite" in readme
    assert "9041f5c7d3720899c90c890ada179c92c3b542b90bb655c247e4a4835df79249" in readme
    assert "996e1812de0adcf8a58e0a0977d04dbf03d9f04097562eb8a57b7487fafbb943" in readme
    assert "1688519d7e403129c3e984188fca1c0416409b53952088e986d811463827f036" in readme
    assert "32baf028277764bd1d9aff05b36b106b7149f6bcefcce698b842b863fd81cc6d" in readme
    assert "ffmpeg` 8.1.1" in readme
    assert "GPL-3.0-or-later" in readme
    assert "b6863adde98898f42602017462871b5f6333e65aec803fdd7a6308639c52edf3" in readme
    assert "00d01197255300c02122c783dd0126a9e7f47d6c6a19faafae2e6610efd071d3" in readme
    assert "No personal recording" in readme
    assert "No private source audio" in readme
    assert "not a transcription-quality benchmark" in readme
    assert "mimic -t" in readme
    assert readme.count("ffmpeg -nostdin -y -i") == 3
    assert 'rm -rf -- "$tmp_dir"' in readme
    for name, receipt in FIXTURE_RECEIPTS.items():
        assert name in readme
        assert receipt.media_type in readme
        assert f"{receipt.bytes:,} bytes" in readme
        assert receipt.sha256 in readme


@pytest.mark.parametrize("name", sorted(FIXTURE_RECEIPTS))
def test_direct_audio_fixture_matches_frozen_pyav_profile(name: str) -> None:
    if importlib.util.find_spec("av") is None:
        if os.environ.get("MKE_REQUIRE_TRANSCRIPTION_EXTRA") == "1":
            pytest.fail("PyAV is required when MKE_REQUIRE_TRANSCRIPTION_EXTRA=1")
        pytest.skip("transcription extra is not installed")

    av = importlib.import_module("av")
    path = AUDIO_FIXTURE_ROOT / name
    receipt = FIXTURE_RECEIPTS[name]
    committed_bytes = path.read_bytes()

    with av.open(io.BytesIO(committed_bytes)) as container:
        assert frozenset(container.format.name.split(",")) == receipt.format_tokens
        assert container.duration == receipt.duration_us
        assert container.duration > 0
        assert len(container.streams.audio) == 1
        assert len(container.streams.video) == 0
        assert len(container.streams.subtitles) == 0
        assert len(container.streams.data) == 0
        assert len(container.streams.attachments) == 0
        assert {stream.type for stream in container.streams} == {"audio"}
        assert dict(container.metadata) == dict(receipt.container_metadata)

        audio = container.streams.audio[0]
        assert dict(audio.metadata) == dict(receipt.stream_metadata)
        assert audio.codec_context.name == receipt.codec
        assert audio.codec_context.channels == 1
        assert audio.codec_context.layout.name == receipt.layout
        assert audio.codec_context.sample_rate == 16_000
        assert audio.duration is not None
        assert audio.duration > 0
        if receipt.aac_profile is not None:
            assert audio.codec_context.profile == receipt.aac_profile
        if receipt.major_brand is not None:
            assert container.metadata["major_brand"] == receipt.major_brand
        if receipt.compatible_brands is not None:
            assert container.metadata["compatible_brands"] == receipt.compatible_brands

        decoded_samples = sum(frame.samples for frame in container.decode(audio=0))
        assert decoded_samples > 0


def test_direct_audio_fixture_directory_contains_no_source_or_sidecar_material() -> None:
    expected_names = {"README.md", *FIXTURE_RECEIPTS}

    assert {path.name for path in AUDIO_FIXTURE_ROOT.iterdir()} == expected_names
