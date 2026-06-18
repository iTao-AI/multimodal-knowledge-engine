"""Owner-scoped tracking for active adapter child processes."""

from __future__ import annotations

import subprocess
import threading


class ActiveProcessController:
    """Track adapter processes so cancellation and shutdown can terminate them."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._processes: set[subprocess.Popen[bytes]] = set()
        self._active_operations = 0
        self._cancel_requested = False

    def begin_operation(self) -> None:
        with self._lock:
            if self._active_operations == 0:
                self._cancel_requested = False
            self._active_operations += 1

    def end_operation(self) -> None:
        with self._lock:
            if self._active_operations <= 0:
                raise RuntimeError("process controller operation is not active")
            self._active_operations -= 1
            if self._active_operations == 0:
                self._cancel_requested = False

    def register(self, process: subprocess.Popen[bytes]) -> None:
        with self._lock:
            cancel_requested = self._cancel_requested
            if not cancel_requested:
                self._processes.add(process)
        if cancel_requested:
            self._terminate(process)

    def unregister(self, process: subprocess.Popen[bytes]) -> None:
        with self._lock:
            self._processes.discard(process)

    def cancel_active(self) -> None:
        with self._lock:
            self._cancel_requested = True
            processes = tuple(self._processes)
        for process in processes:
            self._terminate(process)

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is None:
            process.kill()
        process.wait()
