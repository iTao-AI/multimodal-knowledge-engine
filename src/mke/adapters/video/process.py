"""Owner-scoped tracking and bounded supervision for adapter child processes."""

from __future__ import annotations

import ctypes
import hashlib
import math
import os
import platform
import selectors
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import NewType, cast
from uuid import uuid4

ProcessOperationId = NewType("ProcessOperationId", str)
ProcessTerminator = Callable[[subprocess.Popen[bytes]], object]


@dataclass(frozen=True)
class ProcessGroupCleanup:
    sigterm_sent: bool
    sigkill_sent: bool
    waited: bool
    process_group_absent: bool


@dataclass(frozen=True)
class SupervisionReceipt:
    api: str | None
    api_version: str | None
    metric: str | None
    leader_scope: str
    leader_identity_binding: str | None
    descendants_scope: str
    budget_mode: str | None
    baseline_bytes: int
    budget_bytes: int | None
    observed_max_bytes: int
    overshoot_bytes: int
    budget_outcome: str
    transient_overshoot_possible: bool
    cleanup: ProcessGroupCleanup
    hard_kernel_enforced: bool = False

    @classmethod
    def for_unmeasured_success(cls) -> SupervisionReceipt:
        return cls(
            api=None,
            api_version=None,
            metric=None,
            leader_scope="process_group_leader",
            leader_identity_binding=None,
            descendants_scope="ordinary_cooperative_descendants",
            budget_mode=None,
            baseline_bytes=0,
            budget_bytes=None,
            observed_max_bytes=0,
            overshoot_bytes=0,
            budget_outcome="not_measured",
            transient_overshoot_possible=True,
            cleanup=ProcessGroupCleanup(False, False, True, True),
            hard_kernel_enforced=False,
        )


@dataclass(frozen=True)
class SupervisedProcessProfile:
    wall_seconds: float
    stdout_bytes: int
    stderr_bytes: int
    footprint_bytes: int | None
    footprint_budget_mode: str = "baseline_plus"
    poll_seconds: float = 0.01
    termination_grace_seconds: float = 0.25

    def __post_init__(self) -> None:
        if (
            type(self.wall_seconds) not in {int, float}
            or not math.isfinite(self.wall_seconds)
            or self.wall_seconds <= 0
            or type(self.stdout_bytes) is not int
            or self.stdout_bytes <= 0
            or type(self.stderr_bytes) is not int
            or self.stderr_bytes <= 0
            or (
                self.footprint_bytes is not None
                and (type(self.footprint_bytes) is not int or self.footprint_bytes <= 0)
            )
            or self.footprint_budget_mode not in {"absolute", "baseline_plus"}
            or type(self.poll_seconds) not in {int, float}
            or not math.isfinite(self.poll_seconds)
            or self.poll_seconds <= 0
            or type(self.termination_grace_seconds) not in {int, float}
            or not math.isfinite(self.termination_grace_seconds)
            or self.termination_grace_seconds <= 0
        ):
            raise ValueError("supervised process profile is invalid")


@dataclass(frozen=True)
class SupervisedProcessResult:
    returncode: int
    stdout: bytes
    stderr: bytes
    supervision: SupervisionReceipt


class SupervisedProcessError(RuntimeError):
    """Closed child supervision failure with no command or child diagnostics."""

    def __init__(self, code: str, receipt: SupervisionReceipt | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.receipt = receipt


class _DarwinRusageInfoV4(ctypes.Structure):
    _fields_ = [
        ("ri_uuid", ctypes.c_ubyte * 16),
        ("ri_user_time", ctypes.c_uint64),
        ("ri_system_time", ctypes.c_uint64),
        ("ri_pkg_idle_wkups", ctypes.c_uint64),
        ("ri_interrupt_wkups", ctypes.c_uint64),
        ("ri_pageins", ctypes.c_uint64),
        ("ri_wired_size", ctypes.c_uint64),
        ("ri_resident_size", ctypes.c_uint64),
        ("ri_phys_footprint", ctypes.c_uint64),
        ("ri_proc_start_abstime", ctypes.c_uint64),
        ("ri_remaining_v4_fields", ctypes.c_uint64 * 26),
    ]


if (
    ctypes.sizeof(_DarwinRusageInfoV4) != 296
    or _DarwinRusageInfoV4.ri_phys_footprint.offset != 72
    or _DarwinRusageInfoV4.ri_proc_start_abstime.offset != 80
):
    raise RuntimeError("darwin_rusage_info_v4_layout_invalid")


class DarwinFootprintSampler:
    """Bind one Darwin leader identity and sample only its physical footprint."""

    _RUSAGE_INFO_V4 = 4

    def __init__(self, pid: int) -> None:
        if platform.system() != "Darwin" or platform.machine() != "arm64":
            raise SupervisedProcessError("footprint_platform_unsupported")
        self._pid = pid
        try:
            self._libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
            self._libproc.proc_pid_rusage.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_void_p,
            ]
            self._libproc.proc_pid_rusage.restype = ctypes.c_int
        except (AttributeError, OSError) as error:
            raise SupervisedProcessError("footprint_sampling_failed") from error
        _, start_abstime = self._read_usage()
        self._identity = hashlib.sha256(
            f"{pid}:{start_abstime}".encode("ascii")
        ).hexdigest()

    @property
    def identity(self) -> str:
        _, start_abstime = self._read_usage()
        observed = hashlib.sha256(
            f"{self._pid}:{start_abstime}".encode("ascii")
        ).hexdigest()
        if observed != self._identity:
            raise SupervisedProcessError("footprint_leader_identity_drift")
        return observed

    def sample(self) -> int:
        footprint, start_abstime = self._read_usage()
        observed = hashlib.sha256(
            f"{self._pid}:{start_abstime}".encode("ascii")
        ).hexdigest()
        if observed != self._identity:
            raise SupervisedProcessError("footprint_leader_identity_drift")
        return footprint

    def _read_usage(self) -> tuple[int, int]:
        usage = _DarwinRusageInfoV4()
        if (
            self._libproc.proc_pid_rusage(
                self._pid,
                self._RUSAGE_INFO_V4,
                ctypes.byref(usage),
            )
            != 0
        ):
            raise SupervisedProcessError("footprint_sampling_failed")
        return int(usage.ri_phys_footprint), int(usage.ri_proc_start_abstime)


class ActiveProcessController:
    """Track adapter processes so cancellation and shutdown can terminate them."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._processes: dict[
            ProcessOperationId | None,
            dict[subprocess.Popen[bytes], ProcessTerminator],
        ] = {}
        self._cancelled_operations: set[ProcessOperationId] = set()
        self._shutdown_requested = False

    def begin_operation(self) -> ProcessOperationId:
        operation_id = ProcessOperationId(f"op_{uuid4().hex}")
        with self._lock:
            if self._shutdown_requested:
                raise RuntimeError("process controller is shutting down")
            self._processes[operation_id] = {}
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
        terminator: ProcessTerminator | None = None,
    ) -> None:
        selected_terminator = terminator or self._terminate
        with self._lock:
            if operation_id is not None and operation_id not in self._processes:
                raise RuntimeError("process controller operation is not active")
            terminate = self._shutdown_requested or (
                operation_id is not None and operation_id in self._cancelled_operations
            )
            if not terminate:
                self._processes.setdefault(operation_id, {})[process] = selected_terminator
        if terminate:
            selected_terminator(process)

    def unregister(
        self,
        process: subprocess.Popen[bytes],
        *,
        operation_id: ProcessOperationId | None = None,
    ) -> None:
        with self._lock:
            processes = self._processes.get(operation_id)
            if processes is not None:
                processes.pop(process, None)

    def cancel_operation(self, operation_id: ProcessOperationId) -> None:
        with self._lock:
            processes = self._processes.get(operation_id)
            if processes is None:
                raise RuntimeError("process controller operation is not active")
            self._cancelled_operations.add(operation_id)
            active = tuple(processes.items())
        for process, terminator in active:
            terminator(process)

    def shutdown(self) -> None:
        with self._lock:
            self._shutdown_requested = True
            processes = tuple(
                item
                for operation_processes in self._processes.values()
                for item in operation_processes.items()
            )
        for process, terminator in processes:
            terminator(process)

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        try:
            if process.poll() is None:
                process.kill()
        finally:
            process.wait()


def run_supervised_process(
    command: Sequence[str],
    *,
    environment: Mapping[str, str],
    profile: SupervisedProcessProfile,
    process_controller: ActiveProcessController | None = None,
    process_operation_id: ProcessOperationId | None = None,
) -> SupervisedProcessResult:
    """Run one internal child in a dedicated, bounded process group."""

    if not command or any(type(part) is not str or not part for part in command):
        raise SupervisedProcessError("command_invalid")
    try:
        process = subprocess.Popen(
            list(command),
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=dict(environment),
            close_fds=True,
            start_new_session=True,
        )
    except (OSError, TypeError, ValueError) as error:
        raise SupervisedProcessError("process_start_failed") from error

    registered = False
    selector: selectors.BaseSelector | None = None
    sampler: DarwinFootprintSampler | None = None
    baseline = 0
    budget = profile.footprint_bytes
    observed_max = 0
    controller_cleanup: ProcessGroupCleanup | None = None

    def terminate_group(child: subprocess.Popen[bytes]) -> ProcessGroupCleanup:
        nonlocal controller_cleanup
        controller_cleanup = terminate_process_group(
            child,
            grace_seconds=profile.termination_grace_seconds,
        )
        return controller_cleanup

    try:
        if process.stdout is None or process.stderr is None:
            raise SupervisedProcessError("capture_invalid")
        try:
            if os.getpgid(process.pid) != process.pid:
                raise SupervisedProcessError("process_group_identity_invalid")
        except OSError as error:
            raise SupervisedProcessError("process_group_identity_invalid") from error

        if profile.footprint_bytes is not None:
            sampler = DarwinFootprintSampler(process.pid)
            bound_identity = sampler.identity
            baseline = sampler.sample()
            observed_max = baseline
            if profile.footprint_budget_mode == "baseline_plus":
                budget = baseline + profile.footprint_bytes
        else:
            bound_identity = None

        if process_controller is not None:
            process_controller.register(
                process,
                operation_id=process_operation_id,
                terminator=terminate_group,
            )
            registered = True

        selector = selectors.DefaultSelector()
        streams = {
            process.stdout.fileno(): (process.stdout, profile.stdout_bytes, "stdout"),
            process.stderr.fileno(): (process.stderr, profile.stderr_bytes, "stderr"),
        }
        captured = {descriptor: bytearray() for descriptor in streams}
        for descriptor, (stream, _, _) in streams.items():
            os.set_blocking(descriptor, False)
            selector.register(stream, selectors.EVENT_READ, descriptor)

        started = time.monotonic()
        while selector.get_map() or process.poll() is None:
            if time.monotonic() - started > profile.wall_seconds:
                raise SupervisedProcessError("process_timeout")
            if sampler is not None and process.poll() is None:
                if sampler.identity != bound_identity:
                    raise SupervisedProcessError("footprint_leader_identity_drift")
                observed = sampler.sample()
                observed_max = max(observed_max, observed)
                if budget is not None and observed > budget:
                    raise SupervisedProcessError("footprint_budget_exceeded")
            for key, _ in selector.select(profile.poll_seconds):
                descriptor = cast(int, key.data)
                stream, limit, name = streams[descriptor]
                try:
                    chunk = os.read(descriptor, min(8192, limit - len(captured[descriptor]) + 1))
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(stream)
                    continue
                captured[descriptor].extend(chunk)
                if len(captured[descriptor]) > limit:
                    raise SupervisedProcessError(f"{name}_limit_exceeded")

        returncode = process.wait(timeout=profile.termination_grace_seconds)
        cleanup = controller_cleanup or _cleanup_completed_process_group(
            process, grace_seconds=profile.termination_grace_seconds
        )
        receipt = _supervision_receipt(
            profile=profile,
            baseline=baseline,
            budget=budget,
            observed_max=observed_max,
            outcome="within_budget" if sampler is not None else "not_measured",
            cleanup=cleanup,
        )
        return SupervisedProcessResult(
            returncode=returncode,
            stdout=bytes(captured[process.stdout.fileno()]),
            stderr=bytes(captured[process.stderr.fileno()]),
            supervision=receipt,
        )
    except BaseException as error:
        cleanup = _cleanup_after_failure(
            process,
            grace_seconds=profile.termination_grace_seconds,
        )
        outcome = (
            "exceeded_terminated"
            if isinstance(error, SupervisedProcessError)
            and error.code == "footprint_budget_exceeded"
            else "supervision_failed"
        )
        receipt = _supervision_receipt(
            profile=profile,
            baseline=baseline,
            budget=budget,
            observed_max=observed_max,
            outcome=outcome if cleanup.process_group_absent else "cleanup_incomplete",
            cleanup=cleanup,
        )
        if not cleanup.process_group_absent:
            raise SupervisedProcessError("process_group_cleanup_incomplete", receipt) from error
        if isinstance(error, SupervisedProcessError):
            error.receipt = receipt
            raise
        raise SupervisedProcessError("supervision_failed", receipt) from error
    finally:
        if process_controller is not None and registered:
            process_controller.unregister(process, operation_id=process_operation_id)
        if selector is not None:
            selector.close()
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()


def process_group_absent(pid: int) -> bool:
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return True
    except OSError as error:
        raise SupervisedProcessError("process_group_cleanup_incomplete") from error
    return False


def _signal_process_group(pid: int, sig: signal.Signals) -> bool:
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        return False
    except OSError as error:
        raise SupervisedProcessError("process_group_cleanup_incomplete") from error
    return True


def terminate_process_group(
    process: subprocess.Popen[bytes], *, grace_seconds: float
) -> ProcessGroupCleanup:
    sigterm_sent = False
    sigkill_sent = False
    absent = process_group_absent(process.pid)
    if not absent:
        sigterm_sent = _signal_process_group(process.pid, signal.SIGTERM)
    deadline = time.monotonic() + grace_seconds
    while not absent and time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        try:
            process_running = process.poll() is None
        except OSError as error:
            raise SupervisedProcessError("process_group_cleanup_incomplete") from error
        if process_running:
            try:
                process.wait(timeout=min(0.01, max(remaining, 0.001)))
            except subprocess.TimeoutExpired:
                pass
            except OSError as error:
                raise SupervisedProcessError("process_group_cleanup_incomplete") from error
        else:
            time.sleep(min(0.01, max(remaining, 0.001)))
        absent = process_group_absent(process.pid)
    if not absent:
        sigkill_sent = _signal_process_group(process.pid, signal.SIGKILL)
    try:
        process.wait(timeout=max(grace_seconds, 0.1))
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SupervisedProcessError("process_group_cleanup_incomplete") from error
    deadline = time.monotonic() + max(grace_seconds, 0.1)
    absent = process_group_absent(process.pid)
    while not absent and time.monotonic() < deadline:
        time.sleep(min(0.01, grace_seconds))
        absent = process_group_absent(process.pid)
    if not absent:
        raise SupervisedProcessError("process_group_cleanup_incomplete")
    return ProcessGroupCleanup(sigterm_sent, sigkill_sent, True, True)


def _cleanup_completed_process_group(
    process: subprocess.Popen[bytes], *, grace_seconds: float
) -> ProcessGroupCleanup:
    deadline = time.monotonic() + max(grace_seconds, 0.1)
    absent = process_group_absent(process.pid)
    while not absent and time.monotonic() < deadline:
        time.sleep(min(0.01, grace_seconds))
        absent = process_group_absent(process.pid)
    if not absent:
        raise SupervisedProcessError("process_group_cleanup_incomplete")
    return ProcessGroupCleanup(False, False, True, True)


def _cleanup_after_failure(
    process: subprocess.Popen[bytes], *, grace_seconds: float
) -> ProcessGroupCleanup:
    for _ in range(2):
        try:
            return terminate_process_group(process, grace_seconds=grace_seconds)
        except SupervisedProcessError:
            pass
    return ProcessGroupCleanup(False, False, False, False)


def _supervision_receipt(
    *,
    profile: SupervisedProcessProfile,
    baseline: int,
    budget: int | None,
    observed_max: int,
    outcome: str,
    cleanup: ProcessGroupCleanup,
) -> SupervisionReceipt:
    measured = profile.footprint_bytes is not None
    return SupervisionReceipt(
        api="proc_pid_rusage" if measured else None,
        api_version="RUSAGE_INFO_V4" if measured else None,
        metric="ri_phys_footprint" if measured else None,
        leader_scope="process_group_leader",
        leader_identity_binding="pid+ri_proc_start_abstime" if measured else None,
        descendants_scope="ordinary_cooperative_descendants",
        budget_mode=profile.footprint_budget_mode if measured else None,
        baseline_bytes=baseline,
        budget_bytes=budget,
        observed_max_bytes=observed_max,
        overshoot_bytes=max(0, observed_max - budget) if budget is not None else 0,
        budget_outcome=outcome,
        transient_overshoot_possible=True,
        cleanup=cleanup,
        hard_kernel_enforced=False,
    )
