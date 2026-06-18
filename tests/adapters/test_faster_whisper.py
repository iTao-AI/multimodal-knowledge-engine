from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from mke.adapters.video.contracts import AdapterExitCode, VideoTranscriptionLimits
from mke.adapters.video.faster_whisper import (
    AdapterProtocolError,
    ModelResolutionError,
    doctor_transcription,
    normalize_segments,
    normalize_timestamp_ms,
    prepare_model,
    probe_media,
    resolve_model_snapshot,
    transcribe_media,
)
from mke.domain import VideoMediaInfo
from mke.runtime import FasterWhisperTranscriptionConfig, ModelPreparationConfig


def _install_fake_hub(
    monkeypatch: pytest.MonkeyPatch,
    snapshot_download: Any,
) -> None:
    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        SimpleNamespace(snapshot_download=snapshot_download),
    )


def _install_fake_whisper(
    monkeypatch: pytest.MonkeyPatch,
    model_type: type[Any] | None = None,
) -> None:
    class ReadyModel:
        supported_languages = ["en", "fr", "zh"]

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        SimpleNamespace(WhisperModel=model_type or ReadyModel, __version__="1.2.1"),
    )
    monkeypatch.setitem(sys.modules, "av", SimpleNamespace(__version__="17.1.0"))


def test_resolver_maps_small_and_passes_exact_cache_only_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, object]] = []

    def snapshot_download(**kwargs: object) -> str:
        calls.append(dict(kwargs))
        return str(tmp_path / "snapshot")

    _install_fake_hub(monkeypatch, snapshot_download)
    config = FasterWhisperTranscriptionConfig(cache_dir=tmp_path / "cache")

    resolved = resolve_model_snapshot(config, allow_download=False)

    assert resolved == tmp_path / "snapshot"
    assert calls == [
        {
            "repo_id": "Systran/faster-whisper-small",
            "revision": config.model_revision,
            "cache_dir": str(tmp_path / "cache"),
            "local_files_only": True,
        }
    ]


def test_prepare_retries_with_network_only_after_explicit_opt_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[bool] = []

    def snapshot_download(**kwargs: object) -> str:
        local_only = bool(kwargs["local_files_only"])
        calls.append(local_only)
        if local_only:
            raise FileNotFoundError("private cache path")
        return str(tmp_path / "downloaded")

    _install_fake_hub(monkeypatch, snapshot_download)
    config = ModelPreparationConfig(FasterWhisperTranscriptionConfig(), allow_model_download=True)

    result = prepare_model(config)

    assert calls == [True, False]
    assert result.status == "downloaded"
    assert not hasattr(result, "path")


def test_prepare_reports_already_cached_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[bool] = []

    def snapshot_download(**kwargs: object) -> str:
        calls.append(bool(kwargs["local_files_only"]))
        return str(tmp_path / "cached")

    _install_fake_hub(monkeypatch, snapshot_download)

    result = prepare_model(
        ModelPreparationConfig(FasterWhisperTranscriptionConfig(), allow_model_download=True)
    )

    assert calls == [True]
    assert result.status == "already_cached"


def test_prepare_without_download_permission_returns_stable_cache_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def snapshot_download(**kwargs: object) -> str:
        raise FileNotFoundError("/private/cache/model")

    _install_fake_hub(monkeypatch, snapshot_download)

    with pytest.raises(ModelResolutionError) as exc_info:
        prepare_model(ModelPreparationConfig(FasterWhisperTranscriptionConfig()))

    assert exc_info.value.cause == "configured transcription model is not cached"
    assert "/private" not in str(exc_info.value)


def test_doctor_is_cache_only_and_ready_for_supported_language(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[bool] = []

    def snapshot_download(**kwargs: object) -> str:
        calls.append(bool(kwargs["local_files_only"]))
        return str(tmp_path / "cached")

    _install_fake_hub(monkeypatch, snapshot_download)
    _install_fake_whisper(monkeypatch)

    result = doctor_transcription(FasterWhisperTranscriptionConfig(language="EN"))

    assert calls == [True]
    assert result.status == "ready"
    assert result.cause is None
    assert all("/" not in check.message for check in result.checks)


def test_doctor_rejects_language_not_supported_by_resolved_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class EnglishOnlyModel:
        supported_languages = ["en"]

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

    def snapshot_download(**kwargs: object) -> str:
        return str(tmp_path / "cached")

    _install_fake_hub(monkeypatch, snapshot_download)
    _install_fake_whisper(monkeypatch, EnglishOnlyModel)

    result = doctor_transcription(FasterWhisperTranscriptionConfig(language="fr"))

    assert result.status == "not_ready"
    assert result.cause == "configured language is not supported by the model"


def test_doctor_reports_missing_dependency_without_raw_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mke.adapters.video.faster_whisper._import_optional_runtime",
        lambda: (_ for _ in ()).throw(ImportError("secret module path")),
    )

    result = doctor_transcription(FasterWhisperTranscriptionConfig())

    assert result.status == "not_ready"
    assert result.cause == "transcription optional dependency is not installed"
    assert "secret" not in repr(result)


@pytest.mark.parametrize(
    ("device", "compute_type"),
    [("metal", "int8"), ("cpu", "not-a-type")],
)
def test_doctor_rejects_unsupported_profile_stably(device: str, compute_type: str) -> None:
    result = doctor_transcription(
        FasterWhisperTranscriptionConfig(device=device, compute_type=compute_type)
    )

    assert result.status == "not_ready"
    assert result.cause == "transcription device or compute profile is unsupported"


def test_resolution_permission_error_is_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    def snapshot_download(**kwargs: object) -> str:
        raise PermissionError("/private/cache denied")

    _install_fake_hub(monkeypatch, snapshot_download)

    with pytest.raises(ModelResolutionError) as exc_info:
        resolve_model_snapshot(FasterWhisperTranscriptionConfig(), allow_download=False)

    assert exc_info.value.cause == "transcription model cache is not readable"
    assert "/private" not in str(exc_info.value)


class _FakeCodec:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeStream:
    def __init__(self, codec: str) -> None:
        self.codec_context = _FakeCodec(codec)


class _FakeContainer:
    def __init__(
        self,
        *,
        container: str = "mov,mp4,m4a,3gp,3g2,mj2",
        video_codec: str = "h264",
        audio_codec: str = "aac",
        duration: int = 1_000_000,
        audio: bool = True,
    ) -> None:
        self.format = SimpleNamespace(name=container)
        self.streams = SimpleNamespace(
            video=[_FakeStream(video_codec)],
            audio=[_FakeStream(audio_codec)] if audio else [],
        )
        self.duration = duration
        self.closed = False

    def close(self) -> None:
        self.closed = True


@dataclass
class _RawSegment:
    start: float
    end: float
    text: str


def test_probe_accepts_short_mp4_and_closes_container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = tmp_path / "speech.mp4"
    video.write_bytes(b"x")
    container = _FakeContainer()

    def open_container(path: Path) -> _FakeContainer:
        return container

    monkeypatch.setattr("mke.adapters.video.faster_whisper._open_media_container", open_container)

    media = probe_media(video, VideoTranscriptionLimits())

    assert media == VideoMediaInfo("mp4", "h264", "aac", True, 1000)
    assert container.closed is True


@pytest.mark.parametrize(
    ("container", "video_codec", "audio_codec", "audio", "duration", "code"),
    [
        ("matroska", "h264", "aac", True, 1_000_000, AdapterExitCode.MEDIA_UNSUPPORTED),
        ("mp4", "hevc", "aac", True, 1_000_000, AdapterExitCode.MEDIA_UNSUPPORTED),
        ("mp4", "h264", "opus", True, 1_000_000, AdapterExitCode.MEDIA_UNSUPPORTED),
        ("mp4", "h264", "aac", False, 1_000_000, AdapterExitCode.MEDIA_NO_AUDIO),
        ("mp4", "h264", "aac", True, 0, AdapterExitCode.MEDIA_UNSUPPORTED),
        ("mp4", "h264", "aac", True, 901_000_000, AdapterExitCode.MEDIA_LIMIT_EXCEEDED),
    ],
)
def test_probe_rejects_media_before_model_construction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    container: str,
    video_codec: str,
    audio_codec: str,
    audio: bool,
    duration: int,
    code: AdapterExitCode,
) -> None:
    video = tmp_path / "speech.mp4"
    video.write_bytes(b"x")

    def open_container(path: Path) -> _FakeContainer:
        return _FakeContainer(
            container=container,
            video_codec=video_codec,
            audio_codec=audio_codec,
            audio=audio,
            duration=duration,
        )

    monkeypatch.setattr("mke.adapters.video.faster_whisper._open_media_container", open_container)

    with pytest.raises(AdapterProtocolError) as exc_info:
        probe_media(video, VideoTranscriptionLimits())

    assert exc_info.value.exit_code == code


def test_probe_enforces_input_size_before_opening_pyav(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = tmp_path / "speech.mp4"
    video.write_bytes(b"xx")
    limits = VideoTranscriptionLimits(max_input_bytes=1)

    def fail_open(path: Path) -> _FakeContainer:
        pytest.fail("PyAV must not open oversized input")

    monkeypatch.setattr("mke.adapters.video.faster_whisper._open_media_container", fail_open)

    with pytest.raises(AdapterProtocolError) as exc_info:
        probe_media(video, limits)

    assert exc_info.value.exit_code == AdapterExitCode.MEDIA_LIMIT_EXCEEDED


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0.0, 0), (0.0005, 1), (1.2345, 1235)],
)
def test_timestamp_normalization_rounds_half_millisecond_up(seconds: float, expected: int) -> None:
    assert normalize_timestamp_ms(seconds) == expected


@pytest.mark.parametrize("seconds", [-0.1, float("inf"), float("nan")])
def test_timestamp_normalization_rejects_negative_or_non_finite(seconds: float) -> None:
    with pytest.raises(AdapterProtocolError) as exc_info:
        normalize_timestamp_ms(seconds)
    assert exc_info.value.exit_code == AdapterExitCode.SCHEMA_INVALID


def test_normalize_segments_clamps_one_millisecond_overlap_and_trims_text() -> None:
    raw = [
        _RawSegment(start=0.0, end=1.001, text=" first "),
        _RawSegment(start=1.0, end=2.0, text=" second "),
    ]
    media = VideoMediaInfo("mp4", "h264", "aac", True, 2000)

    segments = normalize_segments(raw, media, VideoTranscriptionLimits())

    assert [(item.start_ms, item.end_ms, item.text) for item in segments] == [
        (0, 1001, "first"),
        (1001, 2000, "second"),
    ]


@pytest.mark.parametrize(
    "raw",
    [
        [
            _RawSegment(start=0.0, end=1.1, text="one"),
            _RawSegment(start=1.0, end=2.0, text="two"),
        ],
        [_RawSegment(start=1.0, end=1.0, text="zero")],
        [_RawSegment(start=0.0, end=1.0, text="   ")],
    ],
)
def test_normalize_segments_rejects_invalid_ranges_or_empty_text(
    raw: list[_RawSegment],
) -> None:
    with pytest.raises(AdapterProtocolError):
        normalize_segments(
            raw,
            VideoMediaInfo("mp4", "h264", "aac", True, 2000),
            VideoTranscriptionLimits(),
        )


def test_transcribe_materializes_generator_before_returning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = tmp_path / "speech.mp4"
    video.write_bytes(b"x")
    consumed: list[str] = []

    class FakeModel:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.model = SimpleNamespace(device="cpu", compute_type="int8")

        def transcribe(self, path: str, *, language: str | None) -> tuple[object, object]:
            def segments() -> object:
                consumed.append("started")
                yield _RawSegment(start=0.0, end=1.0, text="speech")
                consumed.append("finished")

            return segments(), SimpleNamespace(language="en")

    def fake_probe(path: Path, limits: VideoTranscriptionLimits) -> VideoMediaInfo:
        return VideoMediaInfo("mp4", "h264", "aac", True, 1000)

    def fake_resolve(config: FasterWhisperTranscriptionConfig, *, allow_download: bool) -> Path:
        return tmp_path / "snapshot"

    monkeypatch.setattr("mke.adapters.video.faster_whisper.probe_media", fake_probe)
    monkeypatch.setattr("mke.adapters.video.faster_whisper.resolve_model_snapshot", fake_resolve)
    monkeypatch.setattr(
        "mke.adapters.video.faster_whisper._load_whisper_runtime",
        lambda: (FakeModel, "1.2.1"),
    )

    parsed = transcribe_media(video, FasterWhisperTranscriptionConfig())

    assert consumed == ["started", "finished"]
    assert parsed.segments[0].text == "speech"
    assert parsed.transcription_provenance is not None
    assert parsed.transcription_provenance.language == "auto"


def test_transcribe_reports_missing_optional_runtime_before_media_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = tmp_path / "speech.mp4"
    video.write_bytes(b"x")

    def missing_runtime() -> tuple[object, str]:
        raise ImportError("No module named 'av'")

    def fail_probe(path: Path, limits: VideoTranscriptionLimits) -> VideoMediaInfo:
        pytest.fail("media probing must not classify a missing optional runtime as a codec error")

    monkeypatch.setattr(
        "mke.adapters.video.faster_whisper._load_whisper_runtime",
        missing_runtime,
    )
    monkeypatch.setattr("mke.adapters.video.faster_whisper.probe_media", fail_probe)

    with pytest.raises(AdapterProtocolError) as exc_info:
        transcribe_media(video, FasterWhisperTranscriptionConfig())

    assert exc_info.value.exit_code == AdapterExitCode.DEPENDENCY_MISSING


def test_transcribe_records_resolved_runtime_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = tmp_path / "speech.mp4"
    video.write_bytes(b"x")

    class FakeModel:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.model = SimpleNamespace(device="cpu", compute_type="int8_float32")

        def transcribe(self, path: str, *, language: str | None) -> tuple[object, object]:
            return (
                [_RawSegment(start=0.0, end=1.0, text="speech")],
                SimpleNamespace(language="en"),
            )

    def fake_probe(path: Path, limits: VideoTranscriptionLimits) -> VideoMediaInfo:
        return VideoMediaInfo("mp4", "h264", "aac", True, 1000)

    def fake_resolve(
        config: FasterWhisperTranscriptionConfig, *, allow_download: bool
    ) -> Path:
        return tmp_path / "snapshot"

    monkeypatch.setattr(
        "mke.adapters.video.faster_whisper.probe_media",
        fake_probe,
    )
    monkeypatch.setattr(
        "mke.adapters.video.faster_whisper.resolve_model_snapshot",
        fake_resolve,
    )
    monkeypatch.setattr(
        "mke.adapters.video.faster_whisper._load_whisper_runtime",
        lambda: (FakeModel, "1.2.1"),
    )

    parsed = transcribe_media(
        video,
        FasterWhisperTranscriptionConfig(device="auto", compute_type="default"),
    )

    assert parsed.transcription_provenance is not None
    assert parsed.transcription_provenance.device == "cpu"
    assert parsed.transcription_provenance.compute_type == "int8_float32"
