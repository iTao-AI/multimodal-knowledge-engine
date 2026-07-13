from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path


class OwnerRuntimeState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._recovered_databases: set[Path] = set()

    def recover_unfinished_runs_once(
        self,
        db_path: Path,
        recovery: Callable[[], None],
    ) -> None:
        identity = db_path.resolve()
        with self._lock:
            if identity in self._recovered_databases:
                return
            recovery()
            self._recovered_databases.add(identity)
