from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class AdmissionSnapshot:
    capacity: int
    active: int
    waiting: int
    state: Literal["available", "busy", "overloaded"]


@dataclass(frozen=True)
class _AdmissionState:
    active: int = 0
    waiting: int = 0


class AdmissionOverloadedError(RuntimeError):
    """Raised when bounded owner capacity cannot admit an operation."""

    def __init__(self) -> None:
        super().__init__("owner capacity is busy")


class AdmissionLease:
    def __init__(self, release: Callable[[], None]) -> None:
        self._release = release
        self._lock = threading.Lock()
        self._released = False

    def release(self) -> None:
        with self._lock:
            if self._released:
                raise RuntimeError("admission lease is already released")
            self._released = True
        self._release()

    def __enter__(self) -> AdmissionLease:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()


class BoundedAdmissionController:
    def __init__(self, *, capacity: int, max_waiters: int) -> None:
        if type(capacity) is not int or capacity < 1:
            raise ValueError("capacity must be an integer of at least one")
        if type(max_waiters) is not int or max_waiters < 0:
            raise ValueError("max_waiters must be a non-negative integer")
        self._capacity = capacity
        self._max_waiters = max_waiters
        self._condition = threading.Condition()
        self._state = _AdmissionState()

    def acquire(self, *, timeout_seconds: float = 0.0) -> AdmissionLease:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))  # pyright: ignore[reportUnnecessaryIsInstance] -- runtime guard for untyped callers
            or not math.isfinite(timeout_seconds)
            or timeout_seconds < 0
        ):
            raise ValueError("timeout_seconds must be finite non-negative")
        deadline = time.monotonic() + timeout_seconds
        with self._condition:
            if self._state.active < self._capacity:
                self._state = _AdmissionState(
                    active=self._state.active + 1,
                    waiting=self._state.waiting,
                )
                return AdmissionLease(self._release)
            if self._max_waiters == 0 or self._state.waiting >= self._max_waiters:
                raise AdmissionOverloadedError
            self._state = _AdmissionState(
                active=self._state.active,
                waiting=self._state.waiting + 1,
            )
            admitted = False
            try:
                while self._state.active >= self._capacity:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise AdmissionOverloadedError
                    self._condition.wait(timeout=remaining)
                self._state = _AdmissionState(
                    active=self._state.active + 1,
                    waiting=self._state.waiting - 1,
                )
                admitted = True
                return AdmissionLease(self._release)
            finally:
                if not admitted:
                    self._state = _AdmissionState(
                        active=self._state.active,
                        waiting=self._state.waiting - 1,
                    )

    def snapshot(self) -> AdmissionSnapshot:
        with self._condition:
            if self._state.active < self._capacity:
                state: Literal["available", "busy", "overloaded"] = "available"
            elif (
                self._max_waiters == 0
                or self._state.waiting >= self._max_waiters
            ):
                state = "overloaded"
            else:
                state = "busy"
            return AdmissionSnapshot(
                capacity=self._capacity,
                active=self._state.active,
                waiting=self._state.waiting,
                state=state,
            )

    def _release(self) -> None:
        with self._condition:
            if self._state.active <= 0:
                raise RuntimeError("admission controller has no active lease")
            self._state = _AdmissionState(
                active=self._state.active - 1,
                waiting=self._state.waiting,
            )
            self._condition.notify(1)


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
