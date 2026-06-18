"""Owner-scoped tracking for active adapter child processes."""

from __future__ import annotations

import subprocess
import threading


class ActiveProcessController:
    """Track adapter processes so cancellation and shutdown can terminate them."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._processes: set[subprocess.Popen[bytes]] = set()

    def register(self, process: subprocess.Popen[bytes]) -> None:
        with self._lock:
            self._processes.add(process)

    def unregister(self, process: subprocess.Popen[bytes]) -> None:
        with self._lock:
            self._processes.discard(process)

    def cancel_active(self) -> None:
        with self._lock:
            processes = tuple(self._processes)
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.wait()
