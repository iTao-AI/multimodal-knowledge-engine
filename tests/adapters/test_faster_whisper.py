from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from mke.adapters.video.faster_whisper import (
    ModelResolutionError,
    doctor_transcription,
    prepare_model,
    resolve_model_snapshot,
)
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
    config = ModelPreparationConfig(
        FasterWhisperTranscriptionConfig(), allow_model_download=True
    )

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
        ModelPreparationConfig(
            FasterWhisperTranscriptionConfig(), allow_model_download=True
        )
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
def test_doctor_rejects_unsupported_profile_stably(
    device: str, compute_type: str
) -> None:
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
