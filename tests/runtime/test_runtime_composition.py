from __future__ import annotations

import math
import sqlite3
import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from mke.adapters.video.contracts import VideoTranscriptionLimits
from mke.adapters.video.process import ActiveProcessController
from mke.adapters.video.providers import LocalCommandTranscriptProvider, SidecarTranscriptProvider
from mke.application import AudioIngestError, KnowledgeEngine
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
from mke.runtime_owner import BoundedAdmissionController, OwnerRuntimeState
from tests.conftest import PDF_FIXTURES

_OWNER_TEST_FOOTPRINT_BYTES = 12_345_679


def test_runtime_defaults_to_sidecar_and_owns_one_process_controller(tmp_path: Path) -> None:
    runtime = RuntimeConfig(db_path=tmp_path / "mke.sqlite")

    assert runtime.transcription == SidecarTranscriptionConfig()
    assert runtime.retrieval_query_policy == "numeric-grouping-v1"
    assert runtime.process_controller is runtime.process_controller
    assert runtime.direct_audio_footprint_bytes is None
    assert runtime.direct_audio_footprint_budget_mode is None


def test_runtime_accepts_explicit_direct_audio_supervision_pair(tmp_path: Path) -> None:
    runtime = RuntimeConfig(
        tmp_path / "mke.sqlite",
        direct_audio_footprint_bytes=_OWNER_TEST_FOOTPRINT_BYTES,
        direct_audio_footprint_budget_mode="baseline_plus",
    )

    assert runtime.direct_audio_footprint_bytes == _OWNER_TEST_FOOTPRINT_BYTES
    assert runtime.direct_audio_footprint_budget_mode == "baseline_plus"


def test_runtime_keeps_existing_positional_construction_compatible(tmp_path: Path) -> None:
    controller = ActiveProcessController()
    owner_state = OwnerRuntimeState()
    admission = BoundedAdmissionController(capacity=2, max_waiters=3)
    operation_id = controller.begin_operation()

    runtime = RuntimeConfig(
        tmp_path / "mke.sqlite",
        None,
        None,
        SidecarTranscriptionConfig(),
        controller,
        owner_state,
        admission,
        operation_id,
    )

    assert runtime.process_controller is controller
    assert runtime.owner_state is owner_state
    assert runtime.admission_controller is admission
    assert runtime.process_operation_id == operation_id
    assert runtime.direct_audio_footprint_bytes is None
    assert runtime.direct_audio_footprint_budget_mode is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"direct_audio_footprint_bytes": _OWNER_TEST_FOOTPRINT_BYTES},
        {"direct_audio_footprint_budget_mode": "baseline_plus"},
    ],
)
def test_runtime_requires_direct_audio_supervision_pair(
    tmp_path: Path,
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(
        ValueError,
        match="direct audio supervision fields must be configured together",
    ):
        RuntimeConfig(tmp_path / "mke.sqlite", **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [True, 0, -1])
def test_runtime_requires_positive_non_boolean_direct_audio_footprint(
    tmp_path: Path,
    value: object,
) -> None:
    with pytest.raises((TypeError, ValueError), match="positive integer"):
        RuntimeConfig(
            tmp_path / "mke.sqlite",
            direct_audio_footprint_bytes=value,  # type: ignore[arg-type]
            direct_audio_footprint_budget_mode="baseline_plus",
        )


def test_runtime_rejects_absolute_direct_audio_budget_mode(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must be baseline_plus"):
        RuntimeConfig(
            tmp_path / "mke.sqlite",
            direct_audio_footprint_bytes=_OWNER_TEST_FOOTPRINT_BYTES,
            direct_audio_footprint_budget_mode="absolute",  # type: ignore[arg-type]
        )


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


def test_build_engine_leaves_direct_audio_uncomposed_for_sidecar_owner(
    tmp_path: Path,
) -> None:
    runtime = RuntimeConfig(tmp_path / "mke.sqlite")

    engine = build_engine(runtime)
    try:
        assert engine._audio_provider is None  # pyright: ignore[reportPrivateUsage]
        assert engine._audio_preflight is None  # pyright: ignore[reportPrivateUsage]
        assert engine._admission_controller is runtime.admission_controller  # pyright: ignore[reportPrivateUsage]
    finally:
        engine.close()


def test_build_engine_composes_direct_audio_only_for_faster_whisper_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.adapters.audio import InternalAudioProvider

    monkeypatch.setattr("mke.runtime.platform.system", lambda: "Darwin")
    monkeypatch.setattr("mke.runtime.platform.machine", lambda: "arm64")
    runtime = RuntimeConfig(
        tmp_path / "mke.sqlite",
        transcription=FasterWhisperTranscriptionConfig(),
        direct_audio_footprint_bytes=_OWNER_TEST_FOOTPRINT_BYTES,
        direct_audio_footprint_budget_mode="baseline_plus",
    )

    engine = build_engine(runtime)
    try:
        assert isinstance(
            engine._audio_provider,  # pyright: ignore[reportPrivateUsage]
            InternalAudioProvider,
        )
        assert engine._audio_transcription_config is runtime.transcription  # pyright: ignore[reportPrivateUsage]
        assert engine._admission_controller is runtime.admission_controller  # pyright: ignore[reportPrivateUsage]
    finally:
        engine.close()


def test_darwin_audio_runtime_uses_exact_owner_supervision_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.adapters.audio import InternalAudioProvider

    monkeypatch.setattr("mke.runtime.platform.system", lambda: "Darwin")
    monkeypatch.setattr("mke.runtime.platform.machine", lambda: "arm64")
    runtime = RuntimeConfig(
        tmp_path / "mke.sqlite",
        transcription=FasterWhisperTranscriptionConfig(),
        direct_audio_footprint_bytes=_OWNER_TEST_FOOTPRINT_BYTES,
        direct_audio_footprint_budget_mode="baseline_plus",
    )

    engine = build_engine(runtime)
    try:
        provider = engine._audio_provider  # pyright: ignore[reportPrivateUsage]
        assert isinstance(provider, InternalAudioProvider)
        assert provider.profile.footprint_bytes == _OWNER_TEST_FOOTPRINT_BYTES
        assert provider.profile.footprint_budget_mode == "baseline_plus"
    finally:
        engine.close()


def test_missing_audio_supervision_fails_before_preflight_snapshot_or_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_preflight(_config: FasterWhisperTranscriptionConfig) -> object:
        pytest.fail("owner readiness preflight must not run")

    def unexpected_snapshot(_path: Path, _root: Path) -> object:
        pytest.fail("snapshot must not be created")

    monkeypatch.setattr("mke.runtime.platform.system", lambda: "Darwin")
    monkeypatch.setattr("mke.runtime.platform.machine", lambda: "arm64")
    monkeypatch.setattr(
        "mke.runtime.audio_transcription_preflight",
        unexpected_preflight,
    )
    monkeypatch.setattr(
        "mke.application.snapshot_audio_source",
        unexpected_snapshot,
    )
    runtime = RuntimeConfig(
        tmp_path / "mke.sqlite",
        transcription=FasterWhisperTranscriptionConfig(),
    )
    engine = build_engine(runtime)
    try:
        with pytest.raises(AudioIngestError) as raised:
            engine.ingest_audio(Path(__file__).parents[1] / "fixtures/audio/direct-audio.mp3")
        assert raised.value.problem == "transcription_not_ready"
        assert raised.value.cause == "direct audio supervision is not configured"
        assert raised.value.next_step == "configure_direct_audio_supervision"
        assert raised.value.run_id is None
        assert engine.observe_active_publications().source_count == 0
    finally:
        engine.close()


def test_unsupported_audio_platform_fails_before_preflight_snapshot_or_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_preflight(_config: FasterWhisperTranscriptionConfig) -> object:
        pytest.fail("owner readiness preflight must not run")

    def unexpected_snapshot(_path: Path, _root: Path) -> object:
        pytest.fail("snapshot must not be created")

    monkeypatch.setattr("mke.runtime.platform.system", lambda: "Linux")
    monkeypatch.setattr("mke.runtime.platform.machine", lambda: "x86_64")
    monkeypatch.setattr(
        "mke.runtime.audio_transcription_preflight",
        unexpected_preflight,
    )
    monkeypatch.setattr(
        "mke.application.snapshot_audio_source",
        unexpected_snapshot,
    )
    runtime = RuntimeConfig(
        tmp_path / "mke.sqlite",
        transcription=FasterWhisperTranscriptionConfig(),
        direct_audio_footprint_bytes=_OWNER_TEST_FOOTPRINT_BYTES,
        direct_audio_footprint_budget_mode="baseline_plus",
    )
    engine = build_engine(runtime)
    try:
        with pytest.raises(AudioIngestError) as raised:
            engine.ingest_audio(Path(__file__).parents[1] / "fixtures/audio/direct-audio.wav")
        assert raised.value.problem == "transcription_not_ready"
        assert raised.value.cause == "direct audio runtime is supported only on Darwin arm64"
        assert raised.value.next_step == "run_on_supported_darwin_arm64"
        assert raised.value.run_id is None
        assert engine.observe_active_publications().source_count == 0
    finally:
        engine.close()


def test_missing_audio_supervision_keeps_pdf_and_video_owner_compatible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("mke.runtime.platform.system", lambda: "Darwin")
    monkeypatch.setattr("mke.runtime.platform.machine", lambda: "arm64")
    runtime = RuntimeConfig(
        tmp_path / "mke.sqlite",
        transcription=FasterWhisperTranscriptionConfig(),
    )

    engine = build_engine(runtime)
    try:
        assert isinstance(engine._transcript_provider, LocalCommandTranscriptProvider)  # pyright: ignore[reportPrivateUsage]
        assert engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf").run_state.value == "published"
    finally:
        engine.close()


def test_audio_runtime_preflight_failure_is_pre_run_and_model_free(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[FasterWhisperTranscriptionConfig] = []

    def not_ready(config: FasterWhisperTranscriptionConfig) -> object:
        calls.append(config)
        return SimpleNamespace(
            status="not_ready",
            cause="configured transcription model is not cached",
            next_step="run_transcription_prepare",
        )

    monkeypatch.setattr("mke.runtime.audio_transcription_preflight", not_ready)
    monkeypatch.setattr("mke.runtime.platform.system", lambda: "Darwin")
    monkeypatch.setattr("mke.runtime.platform.machine", lambda: "arm64")
    runtime = RuntimeConfig(
        tmp_path / "mke.sqlite",
        transcription=FasterWhisperTranscriptionConfig(),
        direct_audio_footprint_bytes=_OWNER_TEST_FOOTPRINT_BYTES,
        direct_audio_footprint_budget_mode="baseline_plus",
    )
    engine = build_engine(runtime)
    try:
        with pytest.raises(AudioIngestError) as raised:
            engine.ingest_audio(Path(__file__).parents[1] / "fixtures/audio/direct-audio.mp3")
        assert raised.value.problem == "transcription_not_ready"
        assert raised.value.cause == "configured transcription model is not cached"
        assert raised.value.next_step == "run_transcription_prepare"
        assert raised.value.run_id is None
        assert calls == [runtime.transcription]
        assert engine.observe_active_publications().source_count == 0
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


def test_normal_engine_and_runtime_owner_startup_remain_compatible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "mke.sqlite"
    direct = KnowledgeEngine(db_path)
    direct.close()

    assert db_path.exists()
    connection = sqlite3.connect(db_path)
    try:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'publications'"
        ).fetchone() == ("publications",)
    finally:
        connection.close()

    recovery_calls = 0
    original_recovery = KnowledgeEngine.recover_unfinished_runs

    def observe_recovery(engine: KnowledgeEngine) -> None:
        nonlocal recovery_calls
        recovery_calls += 1
        original_recovery(engine)

    monkeypatch.setattr(KnowledgeEngine, "recover_unfinished_runs", observe_recovery)
    runtime = RuntimeConfig(db_path, owner_state=OwnerRuntimeState())
    first = build_engine(runtime)
    first.close()
    second = build_engine(runtime)
    second.close()

    assert recovery_calls == 1


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
