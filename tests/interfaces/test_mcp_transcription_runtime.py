from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest

from mke.adapters.video.faster_whisper import ReadinessCheck, TranscriptionReadiness
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

    def cancel_active() -> None:
        cancelled_process.set()
        release_worker.set()

    monkeypatch.setattr("mke.interfaces.mcp_server.mcp_contract.ingest_file", blocking_ingest)
    monkeypatch.setattr(config.runtime.process_controller, "cancel_active", cancel_active)

    async def exercise() -> None:
        task = asyncio.create_task(ingest_with_cancellation_for_test(config, "speech.mp4"))
        await asyncio.to_thread(worker_started.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)

    asyncio.run(exercise())

    assert cancelled_process.is_set()
    assert worker_finished.is_set()
