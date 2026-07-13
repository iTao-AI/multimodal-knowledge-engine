from __future__ import annotations

import math
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from mke.adapters.video.contracts import VideoTranscriptionLimits
from mke.adapters.video.process import ActiveProcessController
from mke.adapters.video.providers import LocalCommandTranscriptProvider, SidecarTranscriptProvider
from mke.application import KnowledgeEngine
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
from mke.runtime_owner import OwnerRuntimeState


def test_runtime_defaults_to_sidecar_and_owns_one_process_controller(tmp_path: Path) -> None:
    runtime = RuntimeConfig(db_path=tmp_path / "mke.sqlite")

    assert runtime.transcription == SidecarTranscriptionConfig()
    assert runtime.retrieval_query_policy == "numeric-grouping-v1"
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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_input_bytes", 1.5),
        ("max_media_duration_ms", 1.5),
        ("max_segment_count", 1.5),
        ("max_stdout_bytes", 1.5),
        ("max_stderr_bytes", 1.5),
        ("timeout_seconds", math.nan),
        ("timeout_seconds", math.inf),
    ],
)
def test_runtime_limits_reject_fractional_integer_slots_and_non_finite_timeout(
    field: str, value: float
) -> None:
    with pytest.raises(ValueError, match="video transcription limits"):
        VideoTranscriptionLimits(**{field: value})  # type: ignore[arg-type]


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


def test_runtime_rejects_non_owner_runtime_state(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="owner state"):
        RuntimeConfig(  # type: ignore[call-arg]
            db_path=tmp_path / "mke.sqlite",
            owner_state=cast(Any, object()),
        )


@pytest.mark.parametrize("operation_id", ["invalid", "", 7])
def test_runtime_rejects_invalid_process_operation_id(
    tmp_path: Path, operation_id: object
) -> None:
    with pytest.raises((TypeError, ValueError), match="operation ID"):
        RuntimeConfig(
            db_path=tmp_path / "mke.sqlite",
            process_operation_id=cast(Any, operation_id),
        )


def test_runtime_rejects_unknown_retrieval_query_policy(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="retrieval query policy is unsupported"):
        RuntimeConfig(
            db_path=tmp_path / "mke.sqlite",
            retrieval_query_policy="unknown",  # type: ignore[arg-type]
        )


def test_first_party_argv_uses_current_interpreter_module_and_one_placeholder() -> None:
    argv = first_party_adapter_argv(FasterWhisperTranscriptionConfig())

    assert argv[:3] == (sys.executable, "-m", "mke.adapters.video.faster_whisper_cli")
    assert argv.count("{input}") == 1


def test_runtime_builds_sidecar_or_first_party_provider_with_shared_controller(
    tmp_path: Path,
) -> None:
    sidecar = build_transcript_provider(RuntimeConfig(tmp_path / "sidecar.sqlite"))
    controller = ActiveProcessController()
    operation_id = controller.begin_operation()
    runtime = RuntimeConfig(
        tmp_path / "asr.sqlite",
        transcription=FasterWhisperTranscriptionConfig(),
        process_controller=controller,
        process_operation_id=operation_id,
    )
    first_party = build_transcript_provider(runtime)

    assert isinstance(sidecar, SidecarTranscriptProvider)
    assert isinstance(first_party, LocalCommandTranscriptProvider)
    assert first_party.config.process_controller is runtime.process_controller
    assert first_party.config.process_operation_id == operation_id
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
        assert engine._store._query_policy == (  # pyright: ignore[reportPrivateUsage]
            "numeric-grouping-v1"
        )
    finally:
        engine.close()


def test_build_engine_closes_engine_when_owner_recovery_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = RuntimeConfig(tmp_path / "mke.sqlite", owner_state=OwnerRuntimeState())
    closed: list[KnowledgeEngine] = []
    original_close = KnowledgeEngine.close

    def fail_recovery(
        db_path: Path, recovery: Callable[[], None]
    ) -> None:
        raise RuntimeError("recovery failed")

    def observe_close(engine: KnowledgeEngine) -> None:
        closed.append(engine)
        original_close(engine)

    monkeypatch.setattr(
        runtime.owner_state,
        "recover_unfinished_runs_once",
        fail_recovery,
    )
    monkeypatch.setattr(KnowledgeEngine, "close", observe_close)

    with pytest.raises(RuntimeError, match="recovery failed"):
        build_engine(runtime)

    assert len(closed) == 1


def test_build_engine_accepts_current_policy_for_rollback(tmp_path: Path) -> None:
    engine = build_engine(
        RuntimeConfig(
            tmp_path / "mke.sqlite",
            retrieval_query_policy="current",
        )
    )
    try:
        assert engine._store._query_policy == "current"  # pyright: ignore[reportPrivateUsage]
    finally:
        engine.close()


def test_explicit_legacy_query_policy_overrides_future_default_strategy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mke.runtime.DEFAULT_RETRIEVAL_STRATEGY",
        "cjk-active-scan-overlap-v1",
    )

    default = RuntimeConfig(tmp_path / "default.sqlite")
    rollback = RuntimeConfig(
        tmp_path / "rollback.sqlite",
        retrieval_query_policy="numeric-grouping-v1",
    )

    assert default.retrieval_strategy == "cjk-active-scan-overlap-v1"
    assert rollback.retrieval_strategy == "numeric-grouping-v1"


def test_knowledge_engine_explicit_query_policy_stays_protocol_owned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mke.application.DEFAULT_RETRIEVAL_STRATEGY",
        "cjk-active-scan-overlap-v1",
    )

    default = KnowledgeEngine(tmp_path / "default.sqlite")
    rollback = KnowledgeEngine(
        tmp_path / "rollback.sqlite",
        query_policy="numeric-grouping-v1",
    )
    try:
        assert default._retrieval_strategy == (  # pyright: ignore[reportPrivateUsage]
            "cjk-active-scan-overlap-v1"
        )
        assert rollback._retrieval_strategy == (  # pyright: ignore[reportPrivateUsage]
            "numeric-grouping-v1"
        )
    finally:
        default.close()
        rollback.close()
