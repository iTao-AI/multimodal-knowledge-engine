"""Owner-scoped tracking for active adapter child processes."""

from __future__ import annotations

import subprocess
import threading
from typing import NewType
from uuid import uuid4

ProcessOperationId = NewType("ProcessOperationId", str)


class ActiveProcessController:
    """Track adapter processes so cancellation and shutdown can terminate them."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._processes: dict[
            ProcessOperationId | None, set[subprocess.Popen[bytes]]
        ] = {}
        self._cancelled_operations: set[ProcessOperationId] = set()
        self._shutdown_requested = False

    def begin_operation(self) -> ProcessOperationId:
        operation_id = ProcessOperationId(f"op_{uuid4().hex}")
        with self._lock:
            if self._shutdown_requested:
                raise RuntimeError("process controller is shutting down")
            self._processes[operation_id] = set()
        return operation_id

    def end_operation(self, operation_id: ProcessOperationId) -> None:
        with self._lock:
            processes = self._processes.get(operation_id)
            if processes is None:
                raise RuntimeError("process controller operation is not active")
            if processes:
                raise RuntimeError("process controller operation still has active children")
            del self._processes[operation_id]
            self._cancelled_operations.discard(operation_id)

    def register(
        self,
        process: subprocess.Popen[bytes],
        *,
        operation_id: ProcessOperationId | None = None,
    ) -> None:
        with self._lock:
            if operation_id is not None and operation_id not in self._processes:
                raise RuntimeError("process controller operation is not active")
            terminate = self._shutdown_requested or (
                operation_id is not None
                and operation_id in self._cancelled_operations
            )
            if not terminate:
                self._processes.setdefault(operation_id, set()).add(process)
        if terminate:
            self._terminate(process)

    def unregister(
        self,
        process: subprocess.Popen[bytes],
        *,
        operation_id: ProcessOperationId | None = None,
    ) -> None:
        with self._lock:
            processes = self._processes.get(operation_id)
            if processes is not None:
                processes.discard(process)

    def cancel_operation(self, operation_id: ProcessOperationId) -> None:
        with self._lock:
            processes = self._processes.get(operation_id)
            if processes is None:
                raise RuntimeError("process controller operation is not active")
            self._cancelled_operations.add(operation_id)
            active = tuple(processes)
        for process in active:
            self._terminate(process)

    def shutdown(self) -> None:
        with self._lock:
            self._shutdown_requested = True
            processes = tuple(
                process
                for operation_processes in self._processes.values()
                for process in operation_processes
            )
        for process in processes:
            self._terminate(process)

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        try:
            if process.poll() is None:
                process.kill()
        finally:
            process.wait()
