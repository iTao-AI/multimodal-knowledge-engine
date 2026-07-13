from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest

from mke.adapters.video.process import ProcessOperationId
from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.interfaces.mcp_server import ingest_with_cancellation_for_test
from mke.runtime import RuntimeConfig


def test_repeated_cancellation_waits_for_worker_and_preserves_cancelled_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = McpRuntimeConfig(
        runtime=RuntimeConfig(tmp_path / "mke.sqlite"),
        allowed_root=tmp_path,
    )
    worker_started = threading.Event()
    process_killed = threading.Event()
    allow_unregister = threading.Event()
    worker_unregistered = threading.Event()
    operation_ids: list[ProcessOperationId] = []

    class FakeProcess:
        def poll(self) -> int | None:
            return -9 if process_killed.is_set() else None

        def kill(self) -> None:
            process_killed.set()

        def wait(self, timeout: float | None = None) -> int:
            return -9

    process = FakeProcess()

    def blocking_ingest(scoped: McpRuntimeConfig, path: str) -> dict[str, object]:
        operation_id = scoped.runtime.process_operation_id
        assert operation_id is not None
        operation_ids.append(operation_id)
        controller = scoped.runtime.process_controller
        controller.register(
            process,  # pyright: ignore[reportArgumentType]
            operation_id=operation_id,
        )
        worker_started.set()
        assert process_killed.wait(timeout=2)
        assert allow_unregister.wait(timeout=2)
        controller.unregister(
            process,  # pyright: ignore[reportArgumentType]
            operation_id=operation_id,
        )
        worker_unregistered.set()
        return {"ok": False}

    monkeypatch.setattr("mke.interfaces.mcp_server.mcp_contract.ingest_file", blocking_ingest)

    async def exercise() -> None:
        task = asyncio.create_task(
            ingest_with_cancellation_for_test(config, "speech.mp4")
        )
        assert await asyncio.to_thread(worker_started.wait, 2)
        task.cancel()
        assert await asyncio.to_thread(process_killed.wait, 2)
        task.cancel()
        await asyncio.sleep(0)
        assert not worker_unregistered.is_set()
        allow_unregister.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)
        assert worker_unregistered.is_set()

    try:
        asyncio.run(exercise())
    finally:
        allow_unregister.set()

    assert len(operation_ids) == 1
    with pytest.raises(RuntimeError, match="operation is not active"):
        config.runtime.process_controller.end_operation(operation_ids[0])
