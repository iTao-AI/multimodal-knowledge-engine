from __future__ import annotations

import asyncio
import sqlite3
import threading
from pathlib import Path

import pytest

import mke.application
import mke.runtime
from mke.adapters.sqlite import SQLiteStore
from mke.adapters.video.faster_whisper import ReadinessCheck, TranscriptionReadiness
from mke.adapters.video.process import ProcessOperationId
from mke.application import KnowledgeEngine
from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.interfaces.mcp_server import ingest_with_cancellation_for_test, run_mcp_server
from mke.runtime import FasterWhisperTranscriptionConfig, RuntimeConfig
from tests.application.test_audio_publication import AUDIO_FIXTURES, FakeAudioProvider


def _config(tmp_path: Path) -> McpRuntimeConfig:
    return McpRuntimeConfig(
        runtime=RuntimeConfig(
            tmp_path / "mke.sqlite",
            transcription=FasterWhisperTranscriptionConfig(),
        ),
        allowed_root=tmp_path,
    )


def _direct_audio_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> McpRuntimeConfig:
    def build_provider(_config: RuntimeConfig) -> FakeAudioProvider:
        return FakeAudioProvider()

    def build_preflight(_config: RuntimeConfig) -> object:
        return lambda: None

    monkeypatch.setattr(mke.runtime, "_build_audio_provider", build_provider)
    monkeypatch.setattr(mke.runtime, "_build_audio_preflight", build_preflight)
    return McpRuntimeConfig(
        runtime=RuntimeConfig(
            tmp_path / "mke.sqlite",
            transcription=FasterWhisperTranscriptionConfig(),
            direct_audio_footprint_bytes=1,
            direct_audio_footprint_budget_mode="baseline_plus",
        ),
        allowed_root=AUDIO_FIXTURES,
    )


def _active_publication_count(config: McpRuntimeConfig) -> int:
    engine = KnowledgeEngine(config.db_path, recover_unfinished_runs=False)
    try:
        return engine.observe_active_publications().active_publication_count
    finally:
        engine.close()


def test_mcp_preflight_stops_before_stdio_startup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _config(tmp_path)

    def not_ready(config: FasterWhisperTranscriptionConfig) -> TranscriptionReadiness:
        return TranscriptionReadiness(
            "not_ready",
            (ReadinessCheck("model", "failed", "model snapshot unavailable"),),
            "configured transcription model is not cached",
            "run_transcription_prepare",
        )

    monkeypatch.setattr("mke.interfaces.mcp_server.doctor_transcription", not_ready)

    def fail_build(config: McpRuntimeConfig) -> object:
        pytest.fail("stdio server must not start")

    monkeypatch.setattr("mke.interfaces.mcp_server.build_mcp_server", fail_build)

    assert run_mcp_server(config) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "problem=transcription_not_ready "
        "cause=configured transcription model is not cached "
        "next_step=run_transcription_prepare\n"
    )


def test_async_ingest_cancellation_waits_for_worker_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    worker_started = threading.Event()
    release_worker = threading.Event()
    worker_finished = threading.Event()
    cancelled_process = threading.Event()

    def blocking_ingest(config: McpRuntimeConfig, path: str) -> dict[str, object]:
        worker_started.set()
        release_worker.wait(timeout=2)
        worker_finished.set()
        return {"ok": False}

    def cancel_operation(operation_id: ProcessOperationId) -> None:
        assert str(operation_id).startswith("op_")
        cancelled_process.set()
        release_worker.set()

    monkeypatch.setattr("mke.interfaces.mcp_server.mcp_contract.ingest_file", blocking_ingest)
    monkeypatch.setattr(
        config.runtime.process_controller,
        "cancel_operation",
        cancel_operation,
    )

    async def exercise() -> None:
        task = asyncio.create_task(ingest_with_cancellation_for_test(config, "speech.mp4"))
        await asyncio.to_thread(worker_started.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)

    asyncio.run(exercise())

    assert cancelled_process.is_set()
    assert worker_finished.is_set()


def test_async_ingest_cancellation_wins_before_candidate_persistence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _direct_audio_config(tmp_path, monkeypatch)
    before_persist = threading.Event()
    release_worker = threading.Event()
    original_validate = mke.application.validate_manifest

    def block_before_persist(*args: object, **kwargs: object) -> None:
        original_validate(*args, **kwargs)  # type: ignore[arg-type]
        before_persist.set()
        assert release_worker.wait(timeout=2)

    monkeypatch.setattr(mke.application, "validate_manifest", block_before_persist)

    async def exercise() -> None:
        task = asyncio.create_task(
            ingest_with_cancellation_for_test(config, "direct-audio.mp3")
        )
        assert await asyncio.to_thread(before_persist.wait, 2)
        task.cancel()
        release_worker.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)

    asyncio.run(exercise())

    assert _active_publication_count(config) == 0
    with sqlite3.connect(config.db_path) as connection:
        assert connection.execute("SELECT state FROM runs").fetchall() == [("failed",)]


def test_async_ingest_commit_wins_at_candidate_persistence_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _direct_audio_config(tmp_path, monkeypatch)
    commit_started = threading.Event()
    release_commit = threading.Event()
    original_persist = SQLiteStore.persist_validated_candidate

    def block_commit(self: SQLiteStore, *args: object, **kwargs: object) -> None:
        commit_started.set()
        assert release_commit.wait(timeout=2)
        original_persist(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(SQLiteStore, "persist_validated_candidate", block_commit)

    async def exercise() -> dict[str, object]:
        task = asyncio.create_task(
            ingest_with_cancellation_for_test(config, "direct-audio.wav")
        )
        assert await asyncio.to_thread(commit_started.wait, 2)
        task.cancel()
        release_commit.set()
        return await asyncio.wait_for(task, timeout=2)

    result = asyncio.run(exercise())

    assert result["ok"] is True
    assert result["run_state"] == "published"
    assert _active_publication_count(config) == 1


def test_async_ingest_cancellation_kills_process_registered_after_cancel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    worker_started = threading.Event()
    cancellation_seen = threading.Event()
    process_killed = threading.Event()

    class LateProcess:
        def poll(self) -> None:
            return None

        def kill(self) -> None:
            process_killed.set()

        def wait(self, timeout: float | None = None) -> int:
            return -9

    process = LateProcess()
    original_cancel = config.runtime.process_controller.cancel_operation

    def observe_cancel(operation_id: ProcessOperationId) -> None:
        original_cancel(operation_id)
        cancellation_seen.set()

    def register_after_cancel(config: McpRuntimeConfig, path: str) -> dict[str, object]:
        worker_started.set()
        assert cancellation_seen.wait(timeout=2)
        operation_id = config.runtime.process_operation_id
        assert operation_id is not None
        config.runtime.process_controller.register(
            process,  # pyright: ignore[reportArgumentType]
            operation_id=operation_id,
        )
        config.runtime.process_controller.unregister(
            process,  # pyright: ignore[reportArgumentType]
            operation_id=operation_id,
        )
        return {"ok": False}

    monkeypatch.setattr(
        "mke.interfaces.mcp_server.mcp_contract.ingest_file",
        register_after_cancel,
    )
    monkeypatch.setattr(
        config.runtime.process_controller,
        "cancel_operation",
        observe_cancel,
    )

    async def exercise() -> None:
        task = asyncio.create_task(ingest_with_cancellation_for_test(config, "speech.mp4"))
        await asyncio.to_thread(worker_started.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)

    asyncio.run(exercise())

    assert process_killed.is_set()


def test_cancelling_one_ingest_does_not_kill_sibling_operation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    first_started = threading.Event()
    second_started = threading.Event()
    first_release = threading.Event()
    second_release = threading.Event()

    class FakeProcess:
        def __init__(self, release: threading.Event) -> None:
            self.release = release
            self.killed = False

        def poll(self) -> int | None:
            return -9 if self.killed else None

        def kill(self) -> None:
            self.killed = True
            self.release.set()

        def wait(self, timeout: float | None = None) -> int:
            return -9

    first_process = FakeProcess(first_release)
    second_process = FakeProcess(second_release)
    late_process = FakeProcess(threading.Event())

    def blocking_ingest(runtime_config: McpRuntimeConfig, path: str) -> dict[str, object]:
        operation_id = runtime_config.runtime.process_operation_id
        assert operation_id is not None
        process = first_process if path == "first.mp4" else second_process
        started = first_started if path == "first.mp4" else second_started
        release = first_release if path == "first.mp4" else second_release
        controller = runtime_config.runtime.process_controller
        controller.register(
            process,  # pyright: ignore[reportArgumentType]
            operation_id=operation_id,
        )
        started.set()
        assert release.wait(timeout=2)
        controller.unregister(
            process,  # pyright: ignore[reportArgumentType]
            operation_id=operation_id,
        )
        if path == "first.mp4":
            controller.register(
                late_process,  # pyright: ignore[reportArgumentType]
                operation_id=operation_id,
            )
            controller.unregister(
                late_process,  # pyright: ignore[reportArgumentType]
                operation_id=operation_id,
            )
        return {"ok": True, "path": path}

    monkeypatch.setattr("mke.interfaces.mcp_server.mcp_contract.ingest_file", blocking_ingest)

    async def exercise() -> None:
        first = asyncio.create_task(
            ingest_with_cancellation_for_test(config, "first.mp4")
        )
        second = asyncio.create_task(
            ingest_with_cancellation_for_test(config, "second.mp4")
        )
        await asyncio.to_thread(first_started.wait, 2)
        await asyncio.to_thread(second_started.wait, 2)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(first, timeout=2)
        assert first_process.killed is True
        assert late_process.killed is True
        assert second_process.killed is False
        second_release.set()
        assert await asyncio.wait_for(second, timeout=2) == {
            "ok": True,
            "path": "second.mp4",
        }

    asyncio.run(exercise())
