from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from mke.application import KnowledgeEngine
from mke.domain import RunEventType, RunState
from mke.interfaces import mcp_contract
from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.interfaces.mcp_server import ingest_with_cancellation_for_test
from mke.runtime import RuntimeConfig, build_engine
from tests.conftest import PDF_FIXTURES


def test_shared_owner_recovery_reads_cancellation_and_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "mke.sqlite"
    seed = KnowledgeEngine(db_path)
    seed.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
    old_run_id = seed.prepare_pdf_candidate(
        PDF_FIXTURES / "text-layer.pdf",
        leave_running_for_test=True,
    ).run_id
    seed.close()

    runtime = RuntimeConfig(db_path)
    config = McpRuntimeConfig(runtime=runtime, allowed_root=tmp_path)

    def first_use(_: int) -> RunState:
        engine = build_engine(runtime)
        try:
            return engine.get_run(old_run_id).state
        finally:
            engine.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        states = list(executor.map(first_use, range(2)))

    assert states == [RunState.INTERRUPTED, RunState.INTERRUPTED]
    old_run = mcp_contract.get_run(config, old_run_id)
    assert [event["event"] for event in old_run["events"]].count(
        RunEventType.RUN_INTERRUPTED
    ) == 1

    engine = build_engine(runtime)
    live_run_id = engine.prepare_pdf_candidate(
        PDF_FIXTURES / "text-layer.pdf",
        leave_running_for_test=True,
    ).run_id
    engine.close()

    assert mcp_contract.get_run(config, live_run_id)["run"]["state"] == "running"
    assert mcp_contract.search_library(config, "trustworthy")["ok"] is True
    assert (
        mcp_contract.ask_library(config, "Where is the trustworthy evidence?")["ok"]
        is True
    )
    before_events = mcp_contract.get_run(config, live_run_id)["events"]

    worker_started = threading.Event()
    worker_release = threading.Event()

    class FakeProcess:
        def __init__(self) -> None:
            self.killed = False

        def poll(self) -> int | None:
            return -9 if self.killed else None

        def kill(self) -> None:
            self.killed = True
            worker_release.set()

        def wait(self, timeout: float | None = None) -> int:
            return -9

    process = FakeProcess()

    def blocking_ingest(scoped: McpRuntimeConfig, path: str) -> dict[str, object]:
        operation_id = scoped.runtime.process_operation_id
        assert operation_id is not None
        scoped.runtime.process_controller.register(
            process,  # pyright: ignore[reportArgumentType]
            operation_id=operation_id,
        )
        worker_started.set()
        assert worker_release.wait(timeout=2)
        scoped.runtime.process_controller.unregister(
            process,  # pyright: ignore[reportArgumentType]
            operation_id=operation_id,
        )
        return {"ok": False}

    monkeypatch.setattr("mke.interfaces.mcp_server.mcp_contract.ingest_file", blocking_ingest)

    async def cancel_worker() -> None:
        task = asyncio.create_task(
            ingest_with_cancellation_for_test(config, "cancelled.mp4")
        )
        assert await asyncio.to_thread(worker_started.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)

    asyncio.run(cancel_worker())

    assert process.killed is True
    assert mcp_contract.get_run(config, live_run_id)["events"] == before_events
    assert mcp_contract.get_run(config, live_run_id)["run"]["state"] == "running"

    restart_runtime = RuntimeConfig(db_path)
    restarted = build_engine(restart_runtime)
    try:
        assert restarted.get_run(live_run_id).state is RunState.INTERRUPTED
        interrupted_events = restarted.get_run_events(live_run_id)
    finally:
        restarted.close()
    restarted_again = build_engine(restart_runtime)
    try:
        assert restarted_again.get_run_events(live_run_id) == interrupted_events
    finally:
        restarted_again.close()
