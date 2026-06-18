from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

import pytest

from mke.adapters.video.contracts import VideoTranscriptionLimits
from mke.adapters.video.providers import LocalCommandTranscriptProvider, SidecarTranscriptProvider
from mke.runtime import (
    DEFAULT_MODEL_REVISION,
    FasterWhisperTranscriptionConfig,
    ModelPreparationConfig,
    RuntimeConfig,
    SidecarTranscriptionConfig,
    build_engine,
    build_transcript_provider,
    first_party_adapter_argv,
)


def test_runtime_defaults_to_sidecar_and_owns_one_process_controller(tmp_path: Path) -> None:
    runtime = RuntimeConfig(db_path=tmp_path / "mke.sqlite")

    assert runtime.transcription == SidecarTranscriptionConfig()
    assert runtime.process_controller is runtime.process_controller


def test_faster_whisper_defaults_match_the_approved_profile() -> None:
    config = FasterWhisperTranscriptionConfig()

    assert config.model == "small"
    assert config.model_revision == DEFAULT_MODEL_REVISION
    assert config.device == "cpu"
    assert config.compute_type == "int8"
    assert config.language == "auto"


@pytest.mark.parametrize(
    "model",
    ["", " ", "/tmp/model", "./model", "../model", "owner/../model", "owner/", "/owner/model"],
)
def test_model_identifier_rejects_paths_and_malformed_repo_ids(model: str) -> None:
    with pytest.raises(ValueError, match="model identifier"):
        FasterWhisperTranscriptionConfig(model=model)


@pytest.mark.parametrize("revision", ["a" * 39, "a" * 41, "A" * 40, "g" * 40])
def test_model_revision_requires_full_lowercase_commit_sha(revision: str) -> None:
    with pytest.raises(ValueError, match="model revision"):
        FasterWhisperTranscriptionConfig(model_revision=revision)


@pytest.mark.parametrize(("language", "expected"), [("AUTO", "auto"), ("EN", "en"), ("zho", "zho")])
def test_language_is_normalized(language: str, expected: str) -> None:
    assert FasterWhisperTranscriptionConfig(language=language).language == expected


@pytest.mark.parametrize("language", ["", "e", "english", "en-US", "123"])
def test_language_rejects_unsupported_syntax(language: str) -> None:
    with pytest.raises(ValueError, match="language"):
        FasterWhisperTranscriptionConfig(language=language)


def test_runtime_limits_remain_within_the_approved_short_video_envelope() -> None:
    with pytest.raises(ValueError, match="approved bounds"):
        FasterWhisperTranscriptionConfig(
            limits=VideoTranscriptionLimits(max_input_bytes=100 * 1024 * 1024 + 1)
        )


def test_download_permission_exists_only_on_preparation_config() -> None:
    transcription = FasterWhisperTranscriptionConfig()

    assert not hasattr(transcription, "allow_model_download")
    assert ModelPreparationConfig(transcription=transcription).allow_model_download is False
    assert (
        ModelPreparationConfig(
            transcription=transcription, allow_model_download=True
        ).allow_model_download
        is True
    )


def test_runtime_rejects_non_typed_transcription_config(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="transcription config"):
        RuntimeConfig(  # type: ignore[arg-type]
            db_path=tmp_path / "mke.sqlite",
            transcription=cast(Any, {"provider": "faster-whisper"}),
        )


def test_first_party_argv_uses_current_interpreter_module_and_one_placeholder() -> None:
    argv = first_party_adapter_argv(FasterWhisperTranscriptionConfig())

    assert argv[:3] == (sys.executable, "-m", "mke.adapters.video.faster_whisper_cli")
    assert argv.count("{input}") == 1


def test_runtime_builds_sidecar_or_first_party_provider_with_shared_controller(
    tmp_path: Path,
) -> None:
    sidecar = build_transcript_provider(RuntimeConfig(tmp_path / "sidecar.sqlite"))
    runtime = RuntimeConfig(
        tmp_path / "asr.sqlite",
        transcription=FasterWhisperTranscriptionConfig(),
    )
    first_party = build_transcript_provider(runtime)

    assert isinstance(sidecar, SidecarTranscriptProvider)
    assert isinstance(first_party, LocalCommandTranscriptProvider)
    assert first_party.config.process_controller is runtime.process_controller
    assert first_party.config.require_provenance is True


def test_build_engine_uses_shared_provider_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = RuntimeConfig(tmp_path / "mke.sqlite")
    sentinel = SidecarTranscriptProvider()

    def fake_build(config: RuntimeConfig) -> SidecarTranscriptProvider:
        return sentinel

    monkeypatch.setattr("mke.runtime.build_transcript_provider", fake_build)

    engine = build_engine(runtime)
    try:
        assert engine._transcript_provider is sentinel  # pyright: ignore[reportPrivateUsage]
    finally:
        engine.close()
