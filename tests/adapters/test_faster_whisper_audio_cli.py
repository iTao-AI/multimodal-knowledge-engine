from __future__ import annotations

# pyright: reportUnknownArgumentType=false, reportUnknownLambdaType=false
import json
import platform
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import BinaryIO, cast

import pytest

from mke.adapters.audio import (
    AUDIO_TRANSCRIPTION_COMMAND,
    AudioProviderError,
    InternalAudioProvider,
    snapshot_audio_source,
)
from mke.adapters.audio.faster_whisper_cli import main, transcribe_audio
from mke.adapters.video.faster_whisper import (
    AdapterProtocolError,
    NormalizedTranscriptSegment,
    TranscriptionReadiness,
    WhisperModelFactory,
    audio_transcription_preflight,
    transcribe_cached_media,
)
from mke.adapters.video.process import (
    SupervisedProcessProfile,
    SupervisedProcessResult,
    SupervisionReceipt,
)
from mke.domain import (
    AudioMediaInfo,
    AudioTranscriptSegment,
    ParsedAudioTranscript,
    TranscriptionProvenance,
)
from mke.runtime import FasterWhisperTranscriptionConfig


def _provenance() -> TranscriptionProvenance:
    return TranscriptionProvenance(
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
    )


def _parsed() -> ParsedAudioTranscript:
    return ParsedAudioTranscript(
        media=AudioMediaInfo("wav", "pcm_s16le", 1, 16_000, 1_000),
        segments=(AudioTranscriptSegment(0, 1_000, "speech"),),
        transcription_provenance=_provenance(),
    )


def test_shared_inference_materializes_generator_once_and_accepts_binary_media(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    consumed: list[str] = []
    model_tree = tmp_path / "model"
    model_tree.mkdir()
    monkeypatch.setattr(
        "mke.adapters.video.faster_whisper.resolve_model_snapshot",
        lambda config, allow_download: model_tree,
    )

    class Model:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.model = SimpleNamespace(device="cpu", compute_type="int8")

        def transcribe(
            self, media: str | BinaryIO, *, language: str | None
        ) -> tuple[object, object]:
            assert not isinstance(media, str)

            def values() -> object:
                consumed.append("start")
                yield SimpleNamespace(start=0.0, end=1.0, text=" speech ")
                consumed.append("finish")

            return values(), SimpleNamespace(language="EN")

    class Factory:
        library_version = "1.2.1"

        def __call__(self, *args: object, **kwargs: object) -> Model:
            assert kwargs["local_files_only"] is True
            return Model()

    media_path = tmp_path / "audio"
    media_path.write_bytes(b"audio")
    with media_path.open("rb") as stream:
        segments, provenance = transcribe_cached_media(
            stream,
            config=FasterWhisperTranscriptionConfig(),
            model_factory=cast(WhisperModelFactory, Factory()),
        )

    assert consumed == ["start", "finish"]
    assert segments == (NormalizedTranscriptSegment(0, 1_000, "speech"),)
    assert provenance.detected_language == "en"


def test_shared_inference_closes_generator_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "mke.adapters.video.faster_whisper.resolve_model_snapshot",
        lambda config, allow_download: tmp_path / "model",
    )
    class Model:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.model = SimpleNamespace(device="cpu", compute_type="int8")

        def transcribe(self, media: object, *, language: str | None) -> tuple[object, object]:
            def values() -> object:
                raise RuntimeError("SECRET_MODEL_FAILURE")
                yield

            return values(), SimpleNamespace(language="en")

    class Factory:
        library_version = "1.2.1"

        def __call__(self, *args: object, **kwargs: object) -> Model:
            return Model()

    with pytest.raises(AdapterProtocolError) as raised:
        transcribe_cached_media(
            "media",
            config=FasterWhisperTranscriptionConfig(),
            model_factory=cast(WhisperModelFactory, Factory()),
        )
    assert int(raised.value.exit_code) == 40
    assert "SECRET_MODEL_FAILURE" not in str(raised.value)


def test_shared_inference_rejects_empty_transcript(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "mke.adapters.video.faster_whisper.resolve_model_snapshot",
        lambda config, allow_download: tmp_path / "model",
    )

    class Model:
        model = SimpleNamespace(device="cpu", compute_type="int8")

        def transcribe(self, media: object, *, language: str | None) -> tuple[object, object]:
            return (), SimpleNamespace(language="en")

    class Factory:
        library_version = "1.2.1"

        def __call__(self, *args: object, **kwargs: object) -> Model:
            return Model()

    with pytest.raises(AdapterProtocolError) as raised:
        transcribe_cached_media(
            "media",
            config=FasterWhisperTranscriptionConfig(),
            model_factory=cast(WhisperModelFactory, Factory()),
        )
    assert int(raised.value.exit_code) == 41


def test_transcription_child_revalidates_snapshot_after_generator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = Path(__file__).parents[1] / "fixtures" / "audio" / "direct-audio.wav"
    snapshot = snapshot_audio_source(source, tmp_path / "owned")
    monkeypatch.setattr(
        "mke.adapters.video.faster_whisper.resolve_model_snapshot",
        lambda config, allow_download: tmp_path / "model",
    )

    class Model:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.model = SimpleNamespace(device="cpu", compute_type="int8")

        def transcribe(self, media: object, *, language: str | None) -> tuple[object, object]:
            def values() -> object:
                replacement = tmp_path / "replacement"
                replacement.write_bytes(source.read_bytes())
                replacement.chmod(0o400)
                replacement.replace(snapshot.owned_path)
                yield SimpleNamespace(start=0.0, end=1.0, text="speech")

            return values(), SimpleNamespace(language="en")

    monkeypatch.setattr(
        "mke.adapters.audio.faster_whisper_cli.load_whisper_runtime",
        lambda: (Model, "1.2.1"),
    )

    with pytest.raises(AdapterProtocolError) as raised:
        transcribe_audio(
            path=snapshot.owned_path,
            expected_sha256=snapshot.owned_identity.sha256,
            expected_bytes=snapshot.owned_identity.bytes,
            media=AudioMediaInfo("wav", "pcm_s16le", 1, 16_000, 1_815),
            config=FasterWhisperTranscriptionConfig(),
        )

    assert int(raised.value.exit_code) == 50


def test_lightweight_preflight_never_constructs_whisper_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_tree = tmp_path / "model"
    model_tree.mkdir()
    for name in ("config.json", "model.bin", "tokenizer.json", "vocabulary.json"):
        (model_tree / name).write_bytes(b"x")
    constructed: list[bool] = []

    class FasterWhisper:
        __version__ = "1.2.1"

        class WhisperModel:
            def __init__(self, *args: object, **kwargs: object) -> None:
                constructed.append(True)

    def import_optional(name: str) -> object:
        if name == "faster_whisper":
            return FasterWhisper
        if name == "av":
            return object()
        raise AssertionError(name)

    monkeypatch.setattr("mke.adapters.video.faster_whisper.import_module", import_optional)
    monkeypatch.setattr(
        "mke.adapters.video.faster_whisper.resolve_model_snapshot",
        lambda config, allow_download: model_tree,
    )

    result = audio_transcription_preflight(FasterWhisperTranscriptionConfig())

    assert isinstance(result, TranscriptionReadiness)
    assert result.status == "ready"
    assert constructed == []


def test_audio_cli_writes_exactly_one_closed_protocol_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "sealed"
    path.write_bytes(b"x")
    monkeypatch.setattr(
        "mke.adapters.audio.faster_whisper_cli.transcribe_audio",
        lambda **kwargs: _parsed(),
    )

    exit_code = main(
        [
            "--path",
            str(path),
            "--expected-sha256",
            "a" * 64,
            "--expected-bytes",
            "1",
            "--container",
            "wav",
            "--audio-codec",
            "pcm_s16le",
            "--channels",
            "1",
            "--sample-rate-hz",
            "16000",
            "--duration-ms",
            "1000",
            "--model-revision",
            "a" * 40,
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert captured.out.count("\n") == 1
    payload = json.loads(captured.out)
    assert payload["format"] == "mke.audio_transcript.v1"
    assert payload["segments"] == [{"start_ms": 0, "end_ms": 1000, "text": "speech"}]


def test_internal_provider_uses_exact_argv_offline_environment_and_closed_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = Path(__file__).parents[1] / "fixtures" / "audio" / "direct-audio.wav"
    snapshot = snapshot_audio_source(source, tmp_path / "owned")
    captured: dict[str, object] = {}

    def run(command: tuple[str, ...], **kwargs: object) -> SupervisedProcessResult:
        captured["command"] = command
        captured.update(kwargs)
        return SupervisedProcessResult(
            returncode=0,
            stdout=json.dumps(
                {
                    "format": "mke.audio_transcript.v1",
                    "media": {
                        "container": "wav",
                        "audio_codec": "pcm_s16le",
                        "channels": 1,
                        "sample_rate_hz": 16000,
                        "duration_ms": 1000,
                    },
                    "segments": [{"start_ms": 0, "end_ms": 1000, "text": "speech"}],
                    "transcription": {
                        "provider": "faster-whisper",
                        "model": "small",
                        "model_revision": "a" * 40,
                        "library_version": "1.2.1",
                        "device": "cpu",
                        "compute_type": "int8",
                        "language": "auto",
                        "detected_language": "en",
                        "model_source": "cache",
                        "transcription_duration_ms": 5,
                    },
                },
                separators=(",", ":"),
            ).encode()
            + b"\n",
            stderr=b"",
            supervision=SupervisionReceipt.for_unmeasured_success(),
        )

    monkeypatch.setattr("mke.adapters.audio.run_supervised_process", run)
    provider = InternalAudioProvider(
        profile=SupervisedProcessProfile(
            wall_seconds=5,
            stdout_bytes=8192,
            stderr_bytes=1024,
            footprint_bytes=64 * 1024 * 1024,
        )
    )

    result = provider.transcribe(
        snapshot,
        AudioMediaInfo("wav", "pcm_s16le", 1, 16_000, 1_000),
        FasterWhisperTranscriptionConfig(model_revision="a" * 40),
    )

    command = captured["command"]
    assert isinstance(command, tuple)
    assert command[:5] == AUDIO_TRANSCRIPTION_COMMAND
    assert command[5:7] == ("--path", str(snapshot.owned_path))
    environment = cast(dict[str, object], captured["environment"])
    assert environment["HF_HUB_OFFLINE"] == "1"
    assert environment["TRANSFORMERS_OFFLINE"] == "1"
    assert "PYTHONPATH" not in environment
    assert not any("PROXY" in str(key) or "TOKEN" in str(key) for key in environment)
    assert result.parsed_transcript.segments[0].text == "speech"


def test_internal_provider_maps_known_and_unknown_exit_without_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = Path(__file__).parents[1] / "fixtures" / "audio" / "direct-audio.wav"
    snapshot = snapshot_audio_source(source, tmp_path / "owned")
    provider = InternalAudioProvider(
        profile=SupervisedProcessProfile(5, 8192, 1024, footprint_bytes=64 * 1024 * 1024)
    )

    cases = (
        (21, "configured transcription model is not cached"),
        (99, "audio ingest failed"),
    )
    for code, expected in cases:
        monkeypatch.setattr(
            "mke.adapters.audio.run_supervised_process",
            lambda *args, _code=code, **kwargs: SupervisedProcessResult(
                _code,
                b"",
                f"SECRET {tmp_path}".encode(),
                SupervisionReceipt.for_unmeasured_success(),
            ),
        )
        with pytest.raises(AudioProviderError) as raised:
            provider.transcribe(
                snapshot,
                AudioMediaInfo("wav", "pcm_s16le", 1, 16_000, 1_000),
                FasterWhisperTranscriptionConfig(),
            )
        assert str(raised.value) == expected
        assert "SECRET" not in str(raised.value)
        assert str(tmp_path) not in str(raised.value)


@pytest.mark.skipif(
    platform.system() != "Darwin" or platform.machine() != "arm64",
    reason="Darwin arm64 provider authority",
)
def test_internal_provider_requires_footprint_polling_on_supported_cell() -> None:
    with pytest.raises(ValueError, match="footprint supervision is required"):
        InternalAudioProvider(
            profile=SupervisedProcessProfile(5, 8192, 1024, footprint_bytes=None)
        )


def test_audio_module_uses_isolated_package_child_argv() -> None:
    assert AUDIO_TRANSCRIPTION_COMMAND == (
        sys.executable,
        "-I",
        "-B",
        "-m",
        "mke.adapters.audio.faster_whisper_cli",
    )
