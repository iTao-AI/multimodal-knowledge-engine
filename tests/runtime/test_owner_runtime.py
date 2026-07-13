import math
import threading
import time
from pathlib import Path
from typing import Any, cast

import pytest

from mke.adapters.sqlite import SQLiteStore
from mke.application import KnowledgeEngine
from mke.domain import RunState
from mke.runtime import RuntimeConfig, build_engine
from mke.runtime_owner import (
    AdmissionOverloadedError,
    AdmissionSnapshot,
    BoundedAdmissionController,
)
from tests.conftest import PDF_FIXTURES


def _leave_running(db_path: Path) -> str:
    engine = KnowledgeEngine(db_path)
    try:
        return engine.prepare_pdf_candidate(
            PDF_FIXTURES / "text-layer.pdf",
            leave_running_for_test=True,
        ).run_id
    finally:
        engine.close()


def test_sqlite_store_construction_does_not_recover_runs(tmp_path: Path) -> None:
    db_path = tmp_path / "mke.sqlite"
    run_id = _leave_running(db_path)
    store = SQLiteStore(db_path)
    try:
        assert store.get_run(run_id).state is RunState.RUNNING
    finally:
        store.close()


def test_shared_runtime_recovers_only_on_first_engine_build(tmp_path: Path) -> None:
    db_path = tmp_path / "mke.sqlite"
    old_run_id = _leave_running(db_path)
    runtime = RuntimeConfig(db_path)
    first = build_engine(runtime)
    assert first.get_run(old_run_id).state is RunState.INTERRUPTED
    live_run_id = first.prepare_pdf_candidate(
        PDF_FIXTURES / "text-layer.pdf",
        leave_running_for_test=True,
    ).run_id
    first.close()
    second = build_engine(runtime)
    try:
        assert second.get_run(live_run_id).state is RunState.RUNNING
    finally:
        second.close()


def _wait_for_waiter(controller: BoundedAdmissionController) -> None:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if controller.snapshot().waiting == 1:
            return
        time.sleep(0.005)
    pytest.fail("admission waiter did not enter the bounded queue")


def test_bounded_admission_allows_one_waiter_and_rejects_eight_more() -> None:
    controller = BoundedAdmissionController(capacity=1, max_waiters=1)
    first = controller.acquire()
    assert controller.snapshot() == AdmissionSnapshot(
        capacity=1,
        active=1,
        waiting=0,
        state="busy",
    )
    waiter_acquired = threading.Event()
    release_waiter = threading.Event()

    def wait_for_lease() -> None:
        with controller.acquire(timeout_seconds=1):
            waiter_acquired.set()
            assert release_waiter.wait(timeout=2)

    waiter = threading.Thread(target=wait_for_lease)
    waiter.start()
    _wait_for_waiter(controller)
    assert controller.snapshot() == AdmissionSnapshot(
        capacity=1,
        active=1,
        waiting=1,
        state="overloaded",
    )

    for _ in range(8):
        with pytest.raises(AdmissionOverloadedError, match="^owner capacity is busy$"):
            controller.acquire(timeout_seconds=1)

    first.release()
    assert waiter_acquired.wait(timeout=2)
    release_waiter.set()
    waiter.join(timeout=2)
    assert not waiter.is_alive()
    assert controller.snapshot() == AdmissionSnapshot(
        capacity=1,
        active=0,
        waiting=0,
        state="available",
    )


def test_admission_timeout_decrements_waiter_count() -> None:
    controller = BoundedAdmissionController(capacity=1, max_waiters=1)
    lease = controller.acquire()

    with pytest.raises(AdmissionOverloadedError, match="^owner capacity is busy$"):
        controller.acquire(timeout_seconds=0.01)

    assert controller.snapshot() == AdmissionSnapshot(1, 1, 0, "busy")
    lease.release()


def test_admission_lease_cannot_be_released_twice() -> None:
    controller = BoundedAdmissionController(capacity=1, max_waiters=0)
    lease = controller.acquire()
    lease.release()

    with pytest.raises(RuntimeError, match="already released"):
        lease.release()
    with pytest.raises(RuntimeError, match="already released"):
        lease.__exit__(None, None, None)

    assert controller.snapshot() == AdmissionSnapshot(1, 0, 0, "available")


@pytest.mark.parametrize("timeout_seconds", [-1.0, math.nan, math.inf, -math.inf])
def test_admission_rejects_negative_or_non_finite_timeout(timeout_seconds: float) -> None:
    controller = BoundedAdmissionController(capacity=1, max_waiters=1)
    with pytest.raises(ValueError, match="finite non-negative"):
        controller.acquire(timeout_seconds=timeout_seconds)


@pytest.mark.parametrize(
    ("capacity", "max_waiters"),
    [(0, 0), (-1, 0), (1, -1)],
)
def test_admission_rejects_invalid_bounds(capacity: int, max_waiters: int) -> None:
    with pytest.raises(ValueError):
        BoundedAdmissionController(capacity=capacity, max_waiters=max_waiters)


def test_runtime_owns_typed_admission_controller(tmp_path: Path) -> None:
    runtime = RuntimeConfig(tmp_path / "mke.sqlite")
    assert runtime.admission_controller.snapshot() == AdmissionSnapshot(
        capacity=1,
        active=0,
        waiting=0,
        state="available",
    )

    with pytest.raises(TypeError, match="admission controller"):
        RuntimeConfig(
            tmp_path / "invalid.sqlite",
            admission_controller=cast(Any, object()),
        )
