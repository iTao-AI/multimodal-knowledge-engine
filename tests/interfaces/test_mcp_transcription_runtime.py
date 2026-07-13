from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest

from mke.adapters.video.faster_whisper import ReadinessCheck, TranscriptionReadiness
from mke.adapters.video.process import ProcessOperationId
from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.interfaces.mcp_server import ingest_with_cancellation_for_test, run_mcp_server
from mke.runtime import FasterWhisperTranscriptionConfig, RuntimeConfig


def _config(tmp_path: Path) -> McpRuntimeConfig:
    return McpRuntimeConfig(
        runtime=RuntimeConfig(
            tmp_path / "mke.sqlite",
            transcription=FasterWhisperTranscriptionConfig(),
        ),
        allowed_root=tmp_path,
    )


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
        config.runtime.process_controller.register(  # type: ignore[arg-type]
            process,
            operation_id=operation_id,
        )
        config.runtime.process_controller.unregister(  # type: ignore[arg-type]
            process,
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
        controller.register(process, operation_id=operation_id)  # type: ignore[arg-type]
        started.set()
        assert release.wait(timeout=2)
        controller.unregister(process, operation_id=operation_id)  # type: ignore[arg-type]
        if path == "first.mp4":
            controller.register(  # type: ignore[arg-type]
                late_process,
                operation_id=operation_id,
            )
            controller.unregister(  # type: ignore[arg-type]
                late_process,
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
