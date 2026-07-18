#!/usr/bin/env python3
"""Validate offline inputs for the direct-audio external dependency receipt.

The ``--check-inputs`` path is deliberately stdlib-only and read-only. It runs
only a fixed, bounded identity probe for each declared interpreter. Receipt
generation remains gated on independently acquired and authorized inputs.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import re
import selectors
import signal
import stat
import subprocess
import sys
import sysconfig
import time
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_DIST = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*\Z")
_VERSION = re.compile(r"[0-9][a-z0-9]*(?:[._+][a-z0-9]+)*\Z")
_TAG = re.compile(r"[a-z0-9_]+(?:\.[a-z0-9_]+)*\Z")
_PUBLIC_REFERENCE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*\Z")
_FIXTURES = ("direct-audio.m4a", "direct-audio.mp3", "direct-audio.wav")
_FIXTURE_AUTHORITY_DOCUMENT_SHA256 = (
    "533bc8a47ba89aeb86de0e7b944da2f1a3f1de8a5ba062b861a3aef854a87ccb"
)
_FIXTURE_SOURCE_SHA256 = "2e62303fbc08223d326b6faa3699bbbfdf0e0fca335101bdb7265b4988d11cb4"


def _canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


_FIXTURE_AUTHORITY = {
    "direct-audio.m4a": {
        "bytes": 24_880,
        "sha256": "cd7307b22b74de4fef8bda87582be791528c65d6546e4abdf42128070980e260",
        "profile_sha256": "70d2c652b5dd0317bda6d718b17ea8b205c557f79d9f923fd130a29a03626014",
    },
    "direct-audio.mp3": {
        "bytes": 22_509,
        "sha256": "cc10ce7b07ae0ea8434b690383bb7ef0a43f7af66aec474d410e5a9612158631",
        "profile_sha256": "75193a2111794a0d0c2b35d2dbf69498eed959161a48c2434812564cbc4dc3b1",
    },
    "direct-audio.wav": {
        "bytes": 116_238,
        "sha256": "ec82eefefc5a6ccbbfc757864fc94bffd250bf185b03fc0404568063c8f993ac",
        "profile_sha256": "49e792c43526bb7ef609de4ca013aea070fb882a643cc1a20b4a9bb77d0e073d",
    },
}


class ReceiptError(ValueError):
    """Closed validation error whose message is a stable public-safe code."""

    def __init__(self, code: str, *, details: Mapping[str, object] | None = None) -> None:
        super().__init__(code)
        self.details = dict(details) if details is not None else None


@dataclass(frozen=True)
class Cell:
    python: str
    version: str
    python_tag: str
    platform_tag: str


@dataclass(frozen=True, order=True)
class Requirement:
    name: str
    version: str


@dataclass(frozen=True)
class WheelEntry:
    filename: str
    distribution: str
    version: str
    build: str | None
    python_tags: tuple[str, ...]
    abi_tags: tuple[str, ...]
    platform_tags: tuple[str, ...]
    bytes: int
    sha256: str


@dataclass(frozen=True)
class LockProjection:
    requirements: tuple[Requirement, ...]
    requirements_by_cell: tuple[tuple[str, tuple[Requirement, ...]], ...]
    constraints: bytes
    root_requirements: bytes
    root_requirements_by_cell: tuple[tuple[str, bytes], ...]
    cells: tuple[Cell, ...]


@dataclass(frozen=True)
class ExecutableSnapshot:
    resolved: Path
    identity: tuple[int, ...]
    target_file_identity: tuple[int, int]
    sha256: str


@dataclass(frozen=True)
class BoundedProfile:
    wall_seconds: float
    stdout_bytes: int
    stderr_bytes: int
    footprint_bytes: int | None = None
    footprint_budget_mode: str = "absolute"
    poll_seconds: float = 0.01
    term_grace_seconds: float = 0.2
    controlled_allocator: str = "none"
    input_bytes: int = 0
    temp_bytes: int = 0
    output_bytes: int | None = None


@dataclass(frozen=True)
class BoundedRunResult:
    returncode: int
    stdout: bytes
    stderr: bytes
    supervision: dict[str, object] | None


_TARGET_PROFILE = BoundedProfile(5.0, 4096, 4096, output_bytes=4096)
_PIP_PROFILE = BoundedProfile(300.0, 64 * 1024, 64 * 1024, output_bytes=64 * 1024)
_INTERPRETER_PROBE_SOURCE = (
    "import json,platform,struct,sys,sysconfig;"
    "print(json.dumps({"
    "'schema':'mke.target_interpreter_identity.v1',"
    "'implementation':sys.implementation.name,"
    "'python_version':list(sys.version_info[:3]),"
    "'system':platform.system(),"
    "'machine':platform.machine(),"
    "'sysconfig_platform':sysconfig.get_platform(),"
    "'soabi':sysconfig.get_config_var('SOABI'),"
    "'ext_suffix':sysconfig.get_config_var('EXT_SUFFIX'),"
    "'cache_tag':sys.implementation.cache_tag,"
    "'abiflags':sys.abiflags,"
    "'pointer_bits':struct.calcsize('P')*8,"
    "'byteorder':sys.byteorder"
    "},sort_keys=True,separators=(',',':')))"
)


def _normal_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _read_regular(path: Path) -> bytes:
    """Descriptor-read a regular non-symlink and reject in-read identity drift."""
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode):
            raise ReceiptError("input_invalid")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise ReceiptError("input_identity_drift")
            chunks: list[bytes] = []
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            after = os.fstat(descriptor)
            path_after = path.lstat()
        finally:
            os.close(descriptor)
    except ReceiptError:
        raise
    except OSError as error:
        raise ReceiptError("input_invalid") from error
    identity = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
    )
    observed = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
    )
    path_observed = (
        path_after.st_dev,
        path_after.st_ino,
        path_after.st_mode,
        path_after.st_size,
        path_after.st_mtime_ns,
    )
    if identity != observed or identity != path_observed:
        raise ReceiptError("input_identity_drift")
    return b"".join(chunks)


def _parse_wheel_filename(
    filename: str,
) -> tuple[str, str, str | None, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    if not filename.endswith(".whl") or filename != filename.lower():
        raise ReceiptError("wheel_input_invalid")
    stem = filename[:-4]
    parts = stem.split("-")
    if len(parts) not in {5, 6} or any(not part for part in parts):
        raise ReceiptError("wheel_input_invalid")
    distribution, version = parts[:2]
    build = parts[2] if len(parts) == 6 else None
    python_tag, abi_tag, platform_tag = parts[-3:]
    if (
        _DIST.fullmatch(distribution) is None
        or _VERSION.fullmatch(version) is None
        or (build is not None and re.fullmatch(r"[0-9][a-z0-9_]*", build) is None)
        or _TAG.fullmatch(python_tag) is None
        or _TAG.fullmatch(abi_tag) is None
        or _TAG.fullmatch(platform_tag) is None
    ):
        raise ReceiptError("wheel_input_invalid")
    return (
        _normal_name(distribution),
        version,
        build,
        tuple(python_tag.split(".")),
        tuple(abi_tag.split(".")),
        tuple(platform_tag.split(".")),
    )


def build_manifest_from_paths(paths: tuple[Path, ...]) -> tuple[WheelEntry, ...]:
    seen: set[str] = set()
    result: list[WheelEntry] = []
    for path in paths:
        if path.name in seen:
            raise ReceiptError("wheel_duplicate")
        seen.add(path.name)
        try:
            parsed = _parse_wheel_filename(path.name)
            value = _read_regular(path)
        except ReceiptError as error:
            if str(error) in {"input_invalid", "input_identity_drift"}:
                raise ReceiptError("wheel_input_invalid") from error
            raise
        result.append(
            WheelEntry(
                path.name,
                *parsed,
                len(value),
                hashlib.sha256(value).hexdigest(),
            )
        )
    return tuple(sorted(result, key=lambda item: item.filename))


def build_wheelhouse_manifest(wheelhouse: Path) -> tuple[WheelEntry, ...]:
    try:
        root = wheelhouse.lstat()
        if not stat.S_ISDIR(root.st_mode) or wheelhouse.is_symlink():
            raise ReceiptError("wheel_input_invalid")
        paths: list[Path] = []
        with os.scandir(wheelhouse) as entries:
            for entry in entries:
                if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                    raise ReceiptError("wheel_input_invalid")
                paths.append(wheelhouse / entry.name)
    except ReceiptError:
        raise
    except OSError as error:
        raise ReceiptError("wheel_input_invalid") from error
    return build_manifest_from_paths(tuple(paths))


def validate_manifest_identity(wheelhouse: Path, expected: tuple[WheelEntry, ...]) -> None:
    try:
        observed = build_wheelhouse_manifest(wheelhouse)
    except ReceiptError as error:
        raise ReceiptError("wheel_identity_drift") from error
    if observed != expected:
        raise ReceiptError("wheel_identity_drift")


def _wheel_compatible(entry: WheelEntry, cell: Cell) -> bool:
    python_ok = (
        "py3" in entry.python_tags
        or cell.python_tag in entry.python_tags
        or any(
            tag.startswith("cp")
            and tag[2:].isdigit()
            and int(tag[2:]) <= int(cell.python_tag[2:])
            and "abi3" in entry.abi_tags
            for tag in entry.python_tags
        )
    )
    abi_ok = (
        "none" in entry.abi_tags or "abi3" in entry.abi_tags or cell.python_tag in entry.abi_tags
    )
    platform_ok = "any" in entry.platform_tags or any(
        _platform_tag_compatible(tag, cell.platform_tag) for tag in entry.platform_tags
    )
    return python_ok and abi_ok and platform_ok


def _platform_tag_compatible(wheel_tag: str, cell_tag: str) -> bool:
    if wheel_tag == cell_tag:
        return True
    wheel_match = re.fullmatch(r"macosx_(\d+)_(\d+)_(arm64|x86_64|universal2)", wheel_tag)
    cell_match = re.fullmatch(r"macosx_(\d+)_(\d+)_(arm64|x86_64)", cell_tag)
    if wheel_match is None or cell_match is None:
        return False
    if wheel_match[3] not in {cell_match[3], "universal2"}:
        return False
    return (int(wheel_match[1]), int(wheel_match[2])) <= (
        int(cell_match[1]),
        int(cell_match[2]),
    )


def resolve_wheels(
    manifest: tuple[WheelEntry, ...],
    requirements: tuple[Requirement, ...],
    cells: tuple[Cell, ...],
) -> dict[str, dict[str, WheelEntry]]:
    requirements_by_cell = tuple((cell.version, requirements) for cell in cells)
    return resolve_wheels_by_cell(manifest, requirements_by_cell, cells)


def resolve_wheels_by_cell(
    manifest: tuple[WheelEntry, ...],
    requirements_by_cell: tuple[tuple[str, tuple[Requirement, ...]], ...],
    cells: tuple[Cell, ...],
) -> dict[str, dict[str, WheelEntry]]:
    cell_authority = dict(requirements_by_cell)
    if set(cell_authority) != {cell.version for cell in cells}:
        raise ReceiptError("cell_authority_invalid")
    resolved: dict[str, dict[str, WheelEntry]] = {}
    used: set[str] = set()
    for cell in cells:
        cell_result: dict[str, WheelEntry] = {}
        for requirement in cell_authority[cell.version]:
            candidates = [
                entry
                for entry in manifest
                if entry.distribution == requirement.name
                and entry.version == requirement.version
                and _wheel_compatible(entry, cell)
            ]
            if not candidates:
                raise ReceiptError("wheel_missing")
            if len(candidates) != 1:
                raise ReceiptError("wheel_ambiguous")
            cell_result[requirement.name] = candidates[0]
            used.add(candidates[0].filename)
        resolved[cell.version] = cell_result
    if used != {entry.filename for entry in manifest}:
        raise ReceiptError("wheel_surplus")
    return resolved


def resolve_projected_wheels(
    manifest: tuple[WheelEntry, ...], projection: LockProjection
) -> dict[str, dict[str, WheelEntry]]:
    return resolve_wheels_by_cell(manifest, projection.requirements_by_cell, projection.cells)


def _marker_applies(marker: object, cells: tuple[Cell, ...]) -> bool:
    if marker is None:
        return True
    if not isinstance(marker, str):
        raise ReceiptError("lock_projection_invalid")
    # uv's platform dependency markers are closed comparisons joined by and/or.
    # This evaluator supports that authority without importing packaging.
    for cell in cells:
        values = {
            "python_version": cell.version,
            "python_full_version": cell.version + ".0",
            "implementation_name": "cpython",
            "platform_machine": "arm64",
            "sys_platform": "darwin",
        }
        expression = marker
        for name, value in values.items():
            expression = re.sub(rf"\b{name}\b", repr(value), expression)
        if re.fullmatch(r"[A-Za-z0-9_ .'<>=!()\"-]+", expression) is None:
            raise ReceiptError("lock_projection_invalid")
        try:
            applies = eval(expression, {"__builtins__": {}}, {})  # noqa: S307
        except (SyntaxError, TypeError) as error:
            raise ReceiptError("lock_projection_invalid") from error
        if applies is True:
            return True
    return False


def derive_transcription_projection(lock_path: Path, cells: tuple[Cell, ...]) -> LockProjection:
    return _derive_transcription_projection(_read_regular(lock_path), cells)


def _derive_transcription_projection(lock_value: bytes, cells: tuple[Cell, ...]) -> LockProjection:
    try:
        lock = tomllib.loads(lock_value.decode("utf-8", errors="strict"))
        packages = cast(list[dict[str, object]], lock["package"])
        project = next(
            package for package in packages if package.get("name") == "multimodal-knowledge-engine"
        )
        optional = cast(dict[str, list[dict[str, object]]], project["optional-dependencies"])
        roots = optional["transcription"]
    except (
        KeyError,
        StopIteration,
        UnicodeDecodeError,
        tomllib.TOMLDecodeError,
        TypeError,
    ) as error:
        raise ReceiptError("lock_projection_invalid") from error
    by_name = {cast(str, package["name"]): package for package in packages}
    selected_by_cell: dict[str, set[str]] = {}
    root_names_by_cell: dict[str, set[str]] = {}
    for cell in cells:
        root_names = {
            cast(str, item["name"])
            for item in roots
            if _marker_applies(item.get("marker"), (cell,))
        }
        root_names_by_cell[cell.version] = root_names
        pending = list(root_names)
        selected: set[str] = set()
        while pending:
            name = pending.pop()
            if name in selected:
                continue
            package = by_name.get(name)
            if package is None or "registry" not in cast(
                dict[str, object], package.get("source", {})
            ):
                raise ReceiptError("lock_projection_invalid")
            selected.add(name)
            for dependency in cast(list[dict[str, object]], package.get("dependencies", [])):
                if _marker_applies(dependency.get("marker"), (cell,)):
                    pending.append(cast(str, dependency["name"]))
        selected_by_cell[cell.version] = selected
    selected_union: set[str] = set()
    for selected in selected_by_cell.values():
        selected_union.update(selected)

    requirements: list[Requirement] = []
    lines_by_name: dict[str, str] = {}
    requirement_by_name: dict[str, Requirement] = {}
    for name in sorted(selected_union):
        package = by_name[name]
        version = package.get("version")
        wheels_value = package.get("wheels")
        if not isinstance(version, str) or not isinstance(wheels_value, list) or not wheels_value:
            raise ReceiptError("lock_projection_invalid")
        wheels = cast(list[object], wheels_value)
        hashes: set[str] = set()
        for wheel_value in wheels:
            if not isinstance(wheel_value, dict):
                raise ReceiptError("lock_projection_invalid")
            wheel = cast(dict[str, object], wheel_value)
            digest_value = wheel.get("hash")
            if not isinstance(digest_value, str) or not digest_value.startswith("sha256:"):
                raise ReceiptError("lock_projection_invalid")
            digest = digest_value.removeprefix("sha256:")
            if _DIGEST.fullmatch(digest) is None:
                raise ReceiptError("lock_projection_invalid")
            hashes.add(digest)
        normal = _normal_name(name)
        requirement = Requirement(normal, version)
        requirements.append(requirement)
        requirement_by_name[name] = requirement
        line = f"{normal}=={version} " + " ".join(
            f"--hash=sha256:{digest}" for digest in sorted(hashes)
        )
        lines_by_name[name] = line
    lines = [lines_by_name[name] for name in sorted(selected_union)]
    root_union: set[str] = set()
    for root_names in root_names_by_cell.values():
        root_union.update(root_names)
    root_lines = [lines_by_name[name] for name in sorted(root_union)]
    root_encoded = ("\n".join(sorted(root_lines)) + "\n").encode("ascii")
    requirements_by_cell = tuple(
        (
            cell.version,
            tuple(requirement_by_name[name] for name in sorted(selected_by_cell[cell.version])),
        )
        for cell in cells
    )
    constraint_headers = [
        f"# mke-cell {cell_version}:"
        + ",".join(f"{item.name}=={item.version}" for item in cell_requirements)
        for cell_version, cell_requirements in requirements_by_cell
    ]
    encoded = ("\n".join([*constraint_headers, *lines]) + "\n").encode("ascii")
    roots_by_cell = tuple(
        (
            cell.version,
            (
                "\n".join(lines_by_name[name] for name in sorted(root_names_by_cell[cell.version]))
                + "\n"
            ).encode("ascii"),
        )
        for cell in cells
    )
    return LockProjection(
        tuple(requirements),
        requirements_by_cell,
        encoded,
        root_encoded,
        roots_by_cell,
        cells,
    )


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


class _DarwinFootprintSampler:
    """Bind a Darwin process identity and sample its physical footprint."""

    _RUSAGE_INFO_V4 = 4

    def __init__(self, pid: int) -> None:
        if platform.system() != "Darwin":
            raise ReceiptError("footprint_platform_unsupported")
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
            raise ReceiptError("footprint_sampling_failed") from error
        _, start_abstime = self._read_usage()
        self._bound_identity = hashlib.sha256(f"{pid}:{start_abstime}".encode("ascii")).hexdigest()

    @property
    def identity(self) -> str:
        _, start_abstime = self._read_usage()
        observed = hashlib.sha256(f"{self._pid}:{start_abstime}".encode("ascii")).hexdigest()
        if observed != self._bound_identity:
            raise ReceiptError("footprint_leader_identity_drift")
        return observed

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
            raise ReceiptError("footprint_sampling_failed")
        # Public rusage_info_v4 is 296 bytes; footprint/start offsets are 72/80.
        return int(usage.ri_phys_footprint), int(usage.ri_proc_start_abstime)

    def sample(self) -> int:
        footprint, start_abstime = self._read_usage()
        observed_identity = hashlib.sha256(
            f"{self._pid}:{start_abstime}".encode("ascii")
        ).hexdigest()
        if observed_identity != self._bound_identity:
            raise ReceiptError("footprint_leader_identity_drift")
        return footprint


def _process_group_absent(pid: int) -> bool:
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return True
    except OSError as error:
        raise ReceiptError("bounded_cleanup_incomplete") from error
    return False


def _signal_process_group(pid: int, sig: signal.Signals) -> bool:
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        return False
    except OSError as error:
        raise ReceiptError("bounded_cleanup_incomplete") from error
    return True


def _cleanup_process_group(
    process: subprocess.Popen[bytes], *, grace_seconds: float, terminate: bool
) -> dict[str, bool]:
    sigterm_sent = False
    sigkill_sent = False
    group_absent = _process_group_absent(process.pid)
    if terminate and not group_absent:
        sigterm_sent = _signal_process_group(process.pid, signal.SIGTERM)
    deadline = time.monotonic() + grace_seconds
    while not group_absent:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            process_running = process.poll() is None
        except OSError as error:
            raise ReceiptError("bounded_cleanup_incomplete") from error
        if process_running:
            try:
                process.wait(timeout=min(0.01, remaining))
            except subprocess.TimeoutExpired:
                pass
            except OSError as error:
                raise ReceiptError("bounded_cleanup_incomplete") from error
        else:
            time.sleep(min(0.01, remaining))
        group_absent = _process_group_absent(process.pid)
    if not group_absent:
        if terminate:
            sigkill_sent = _signal_process_group(process.pid, signal.SIGKILL)
        else:
            raise ReceiptError("bounded_cleanup_incomplete")
    try:
        process.wait(timeout=max(grace_seconds, 0.1))
    except (subprocess.TimeoutExpired, OSError) as error:
        raise ReceiptError("bounded_cleanup_incomplete") from error
    deadline = time.monotonic() + max(grace_seconds, 0.1)
    group_absent = _process_group_absent(process.pid)
    while not group_absent and time.monotonic() < deadline:
        time.sleep(min(0.01, grace_seconds))
        group_absent = _process_group_absent(process.pid)
    if not group_absent:
        raise ReceiptError("bounded_cleanup_incomplete")
    return {
        "sigterm_sent": sigterm_sent,
        "sigkill_sent": sigkill_sent,
        "waited": True,
        "process_group_absent": True,
    }


def _supervision_receipt(
    *,
    profile: BoundedProfile,
    baseline: int,
    budget: int,
    observed_max: int,
    outcome: str,
    cleanup: dict[str, bool],
) -> dict[str, object]:
    return {
        "api": "proc_pid_rusage",
        "api_version": "RUSAGE_INFO_V4",
        "tool": "stdlib-ctypes",
        "metric": "ri_phys_footprint",
        "leader_scope": "process_group_leader",
        "leader_identity_binding": "pid+ri_proc_start_abstime",
        "descendants_scope": "ordinary_cooperative_descendants",
        "budget_mode": profile.footprint_budget_mode,
        "baseline_bytes": baseline,
        "budget_bytes": budget,
        "poll_seconds": profile.poll_seconds,
        "controlled_allocator": profile.controlled_allocator,
        "observed_max_bytes": observed_max,
        "overshoot_bytes": max(0, observed_max - budget),
        "budget_outcome": outcome,
        "transient_overshoot_possible": True,
        "cleanup": cleanup,
        "hard_kernel_enforced": False,
        "bounds": {
            "wall_seconds": profile.wall_seconds,
            "stdout_bytes": profile.stdout_bytes,
            "stderr_bytes": profile.stderr_bytes,
            "input_bytes": profile.input_bytes,
            "temp_bytes": profile.temp_bytes,
            "output_bytes": (
                profile.stdout_bytes if profile.output_bytes is None else profile.output_bytes
            ),
        },
    }


def _cleanup_after_supervision_failure(
    process: subprocess.Popen[bytes], *, grace_seconds: float
) -> dict[str, bool]:
    for _ in range(2):
        try:
            return _cleanup_process_group(
                process,
                grace_seconds=grace_seconds,
                terminate=True,
            )
        except ReceiptError:
            pass
    return {
        "sigterm_sent": False,
        "sigkill_sent": False,
        "waited": False,
        "process_group_absent": False,
    }


def _run_bounded(
    argv: list[str],
    *,
    env: dict[str, str],
    cwd: Path | None,
    profile: BoundedProfile,
) -> BoundedRunResult:
    if (
        not argv
        or profile.wall_seconds <= 0
        or profile.stdout_bytes < 0
        or profile.stderr_bytes < 0
        or profile.poll_seconds <= 0
        or profile.term_grace_seconds <= 0
        or profile.input_bytes != 0
        or profile.footprint_budget_mode not in {"absolute", "baseline_plus"}
    ):
        raise ReceiptError("bounded_profile_invalid")
    process = subprocess.Popen(
        argv,
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=cwd,
        close_fds=True,
        start_new_session=True,
    )
    if process.stdout is None or process.stderr is None:
        _cleanup_process_group(process, grace_seconds=profile.term_grace_seconds, terminate=True)
        raise ReceiptError("bounded_capture_invalid")
    selector: selectors.BaseSelector | None = None
    sampler: _DarwinFootprintSampler | None = None
    baseline = 0
    budget = profile.footprint_bytes or 0
    observed_max = 0
    try:
        try:
            process_group = os.getpgid(process.pid)
        except OSError as error:
            raise ReceiptError("bounded_supervision_failed") from error
        if process_group != process.pid:
            raise ReceiptError("bounded_leader_identity_invalid")
        sampler = (
            _DarwinFootprintSampler(process.pid) if profile.footprint_bytes is not None else None
        )
        bound_leader = sampler.identity if sampler is not None else None
        if sampler is not None:
            baseline = sampler.sample()
            observed_max = baseline
            if profile.footprint_budget_mode == "baseline_plus":
                budget = baseline + cast(int, profile.footprint_bytes)
        selector = selectors.DefaultSelector()
        streams = {
            process.stdout.fileno(): (process.stdout, profile.stdout_bytes),
            process.stderr.fileno(): (process.stderr, profile.stderr_bytes),
        }
        captured: dict[int, bytearray] = {descriptor: bytearray() for descriptor in streams}
        try:
            for descriptor, (stream, _) in streams.items():
                os.set_blocking(descriptor, False)
                selector.register(stream, selectors.EVENT_READ, descriptor)
        except OSError as error:
            raise ReceiptError("bounded_supervision_failed") from error
        started = time.monotonic()
        while selector.get_map() or process.poll() is None:
            if time.monotonic() - started > profile.wall_seconds:
                raise ReceiptError("bounded_timeout")
            if sampler is not None and process.poll() is None:
                if sampler.identity != bound_leader:
                    raise ReceiptError("footprint_leader_identity_drift")
                observed = sampler.sample()
                observed_max = max(observed_max, observed)
                if observed > budget:
                    cleanup = _cleanup_process_group(
                        process,
                        grace_seconds=profile.term_grace_seconds,
                        terminate=True,
                    )
                    supervision = _supervision_receipt(
                        profile=profile,
                        baseline=baseline,
                        budget=budget,
                        observed_max=observed_max,
                        outcome="exceeded_terminated",
                        cleanup=cleanup,
                    )
                    result = BoundedRunResult(
                        cast(int, process.returncode),
                        bytes(captured[process.stdout.fileno()]),
                        bytes(captured[process.stderr.fileno()]),
                        supervision,
                    )
                    if profile.controlled_allocator != "none":
                        return result
                    raise ReceiptError("footprint_budget_exceeded", details=supervision)
            for key, _ in selector.select(profile.poll_seconds):
                descriptor = cast(int, key.data)
                try:
                    chunk = os.read(descriptor, 8192)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                captured[descriptor].extend(chunk)
                limit = streams[descriptor][1]
                if len(captured[descriptor]) > limit:
                    code = (
                        "bounded_stdout_exceeded"
                        if descriptor == process.stdout.fileno()
                        else "bounded_stderr_exceeded"
                    )
                    raise ReceiptError(code)
        try:
            returncode = process.wait(timeout=profile.term_grace_seconds)
        except (subprocess.TimeoutExpired, OSError) as error:
            raise ReceiptError("bounded_supervision_failed") from error
        cleanup = _cleanup_process_group(
            process, grace_seconds=profile.term_grace_seconds, terminate=False
        )
        stdout = bytes(captured[process.stdout.fileno()])
        stderr = bytes(captured[process.stderr.fileno()])
        supervision: dict[str, object] | None = None
        if sampler is not None:
            supervision = _supervision_receipt(
                profile=profile,
                baseline=baseline,
                budget=budget,
                observed_max=observed_max,
                outcome="within_budget",
                cleanup=cleanup,
            )
        return BoundedRunResult(returncode, stdout, stderr, supervision)
    except OSError as cause:
        error = ReceiptError("bounded_supervision_failed")
        cleanup = _cleanup_after_supervision_failure(
            process,
            grace_seconds=profile.term_grace_seconds,
        )
        if profile.footprint_bytes is not None:
            error.details = _supervision_receipt(
                profile=profile,
                baseline=baseline,
                budget=budget,
                observed_max=observed_max,
                outcome="supervision_failed",
                cleanup=cleanup,
            )
        raise error from cause
    except ReceiptError as error:
        cleanup = _cleanup_after_supervision_failure(
            process,
            grace_seconds=profile.term_grace_seconds,
        )
        if profile.footprint_bytes is not None and error.details is None:
            error.details = _supervision_receipt(
                profile=profile,
                baseline=baseline,
                budget=budget,
                observed_max=observed_max,
                outcome="supervision_failed",
                cleanup=cleanup,
            )
        raise
    finally:
        if selector is not None:
            selector.close()
        process.stdout.close()
        process.stderr.close()


def run_nested_pip_install(
    *,
    python: Path,
    wheelhouse: Path,
    constraints: Path,
    root_requirements: Path,
    expected_manifest: tuple[WheelEntry, ...],
    constraints_sha256: str,
    root_requirements_sha256: str,
    runtime_root: Path,
    home: Path,
    temp: Path,
    cwd: Path,
    cell: Cell,
    preflight_interpreter: Mapping[str, object],
    preflight_file_identity: tuple[int, ...],
) -> None:
    constraints_value = _read_regular(constraints)
    requirements_value = _read_regular(root_requirements)
    if (
        _DIGEST.fullmatch(constraints_sha256) is None
        or hashlib.sha256(constraints_value).hexdigest() != constraints_sha256
        or _DIGEST.fullmatch(root_requirements_sha256) is None
        or hashlib.sha256(requirements_value).hexdigest() != root_requirements_sha256
    ):
        raise ReceiptError("pip_input_identity_drift")
    observed_manifest = build_wheelhouse_manifest(wheelhouse)
    if observed_manifest != expected_manifest:
        raise ReceiptError("wheel_identity_drift")
    validated_wheelhouse = wheelhouse.resolve(strict=True)
    validated_runtime = _validated_directory(runtime_root, code="runtime_path_invalid")
    validated_home = _validated_owned_directory(home, validated_runtime)
    validated_temp = _validated_owned_directory(temp, validated_runtime)
    validated_cwd = _validated_owned_directory(cwd, validated_runtime)
    generation_interpreter, generation_file_identity, generation_executable = (
        _probe_target_interpreter(python, cell)
    )
    if (
        generation_interpreter != dict(preflight_interpreter)
        or generation_file_identity != preflight_file_identity
    ):
        raise ReceiptError("pip_interpreter_identity_drift")
    argv = [
        str(generation_executable),
        "-I",
        "-m",
        "pip",
        "--isolated",
        "--disable-pip-version-check",
        "--no-input",
        "install",
        "--no-index",
        "--find-links",
        validated_wheelhouse.as_uri(),
        "--only-binary=:all:",
        "--no-cache-dir",
        "--require-hashes",
        "--constraint",
        str(constraints.resolve()),
        "--requirement",
        str(root_requirements.resolve()),
    ]
    environment = {
        "HOME": str(validated_home),
        "TMPDIR": str(validated_temp),
        "PIP_CONFIG_FILE": os.devnull,
    }
    result = _run_bounded(
        argv,
        env=environment,
        cwd=validated_cwd,
        profile=_PIP_PROFILE,
    )
    if result.returncode != 0:
        raise ReceiptError("pip_install_failed")


def _validated_directory(path: Path, *, code: str) -> Path:
    try:
        observed = path.lstat()
        if not stat.S_ISDIR(observed.st_mode) or path.is_symlink():
            raise ReceiptError(code)
        return path.resolve(strict=True)
    except ReceiptError:
        raise
    except OSError as error:
        raise ReceiptError(code) from error


def _validated_owned_directory(path: Path, runtime_root: Path) -> Path:
    resolved = _validated_directory(path, code="runtime_path_invalid")
    try:
        relative = resolved.relative_to(runtime_root)
    except ValueError as error:
        raise ReceiptError("runtime_path_invalid") from error
    if not relative.parts:
        raise ReceiptError("runtime_path_invalid")
    return resolved


def _issue(code: str, subject: str) -> dict[str, str]:
    return {"code": code, "subject": subject}


def _parse_constraints(
    value: bytes,
) -> tuple[
    tuple[Requirement, ...],
    dict[tuple[str, str], frozenset[str]],
    tuple[tuple[str, tuple[Requirement, ...]], ...],
]:
    try:
        text = value.decode("ascii", errors="strict")
    except UnicodeDecodeError as error:
        raise ReceiptError("constraints_invalid") from error
    lines = text.splitlines()
    if not lines or not text.endswith("\n"):
        raise ReceiptError("constraints_invalid")
    header_lines = [line for line in lines if line.startswith("# mke-cell ")]
    requirement_lines = [line for line in lines if not line.startswith("#")]
    if (
        len(header_lines) + len(requirement_lines) != len(lines)
        or header_lines != sorted(header_lines)
        or requirement_lines != sorted(requirement_lines)
        or lines != [*header_lines, *requirement_lines]
    ):
        raise ReceiptError("constraints_invalid")
    requirements: list[Requirement] = []
    authorities: dict[tuple[str, str], frozenset[str]] = {}
    for line in requirement_lines:
        parts = line.split(" ")
        if len(parts) < 2 or "==" not in parts[0]:
            raise ReceiptError("constraints_invalid")
        name, version = parts[0].split("==", 1)
        if name != _normal_name(name) or _VERSION.fullmatch(version) is None:
            raise ReceiptError("constraints_invalid")
        hashes: list[str] = []
        for part in parts[1:]:
            if not part.startswith("--hash=sha256:"):
                raise ReceiptError("constraints_invalid")
            digest = part.removeprefix("--hash=sha256:")
            if _DIGEST.fullmatch(digest) is None:
                raise ReceiptError("constraints_invalid")
            hashes.append(digest)
        key = (name, version)
        if key in authorities or hashes != sorted(set(hashes)):
            raise ReceiptError("constraints_invalid")
        requirements.append(Requirement(name, version))
        authorities[key] = frozenset(hashes)
    union = {(item.name, item.version): item for item in requirements}
    by_cell: list[tuple[str, tuple[Requirement, ...]]] = []
    for line in header_lines:
        match = re.fullmatch(r"# mke-cell (3\.12|3\.13):(.*)", line)
        if match is None:
            raise ReceiptError("constraints_invalid")
        cell_requirements: list[Requirement] = []
        raw_items = match[2].split(",") if match[2] else []
        if raw_items != sorted(set(raw_items)):
            raise ReceiptError("constraints_invalid")
        for raw_item in raw_items:
            if raw_item.count("==") != 1:
                raise ReceiptError("constraints_invalid")
            name, version = raw_item.split("==")
            requirement = union.get((name, version))
            if requirement is None:
                raise ReceiptError("constraints_invalid")
            cell_requirements.append(requirement)
        by_cell.append((match[1], tuple(cell_requirements)))
    if not by_cell:
        by_cell = [(cell.version, tuple(requirements)) for cell in _supported_cells()]
    if {version for version, _ in by_cell} != {"3.12", "3.13"}:
        raise ReceiptError("constraints_invalid")
    return tuple(requirements), authorities, tuple(by_cell)


def _supported_cells() -> tuple[Cell, ...]:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        tag = "unsupported"
    else:
        version = platform.mac_ver()[0].split(".")
        if len(version) < 2 or not all(part.isdigit() for part in version[:2]):
            tag = "unsupported"
        else:
            tag = f"macosx_{version[0]}_{version[1]}_arm64"
    return (
        Cell("python3.12", "3.12", "cp312", tag),
        Cell("python3.13", "3.13", "cp313", tag),
    )


def _snapshot_interpreter_executable(path: Path) -> ExecutableSnapshot:
    try:
        declared_before = path.lstat()
        resolved = path.resolve(strict=True)
        target = resolved.lstat()
        if (
            not stat.S_ISREG(target.st_mode)
            or target.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH) == 0
        ):
            raise ReceiptError("interpreter_invalid")
        value = _read_regular(resolved)
        declared_after = path.lstat()
        target_after = resolved.lstat()
    except ReceiptError:
        raise
    except OSError as error:
        raise ReceiptError("interpreter_invalid") from error
    declared_identity = (
        declared_before.st_dev,
        declared_before.st_ino,
        declared_before.st_mode,
        declared_before.st_size,
        declared_before.st_mtime_ns,
        declared_before.st_ctime_ns,
    )
    if declared_identity != (
        declared_after.st_dev,
        declared_after.st_ino,
        declared_after.st_mode,
        declared_after.st_size,
        declared_after.st_mtime_ns,
        declared_after.st_ctime_ns,
    ):
        raise ReceiptError("interpreter_identity_drift")
    target_identity = (
        target.st_dev,
        target.st_ino,
        target.st_mode,
        target.st_size,
        target.st_mtime_ns,
        target.st_ctime_ns,
    )
    if target_identity != (
        target_after.st_dev,
        target_after.st_ino,
        target_after.st_mode,
        target_after.st_size,
        target_after.st_mtime_ns,
        target_after.st_ctime_ns,
    ):
        raise ReceiptError("interpreter_identity_drift")
    return ExecutableSnapshot(
        resolved,
        (*declared_identity, *target_identity),
        (target.st_dev, target.st_ino),
        hashlib.sha256(value).hexdigest(),
    )


def _snapshot_executable(path: Path) -> ExecutableSnapshot:
    return _snapshot_interpreter_executable(path)


def _probe_target_interpreter(
    path: Path, cell: Cell
) -> tuple[dict[str, object], tuple[int, ...], Path]:
    before = _snapshot_executable(path)
    result = _run_bounded(
        [str(before.resolved), "-I", "-B", "-c", _INTERPRETER_PROBE_SOURCE],
        env={},
        cwd=None,
        profile=_TARGET_PROFILE,
    )
    if result.returncode != 0 or result.stderr:
        raise ReceiptError("interpreter_probe_failed")
    try:
        decoded = cast(object, json.loads(result.stdout.decode("ascii", errors="strict")))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReceiptError("interpreter_output_invalid") from error
    expected_keys = {
        "implementation",
        "schema",
        "python_version",
        "system",
        "machine",
        "sysconfig_platform",
        "soabi",
        "ext_suffix",
        "cache_tag",
        "abiflags",
        "pointer_bits",
        "byteorder",
    }
    if not isinstance(decoded, dict):
        raise ReceiptError("interpreter_output_invalid")
    unknown_payload = cast(dict[object, object], decoded)
    if set(unknown_payload) != expected_keys:
        raise ReceiptError("interpreter_output_invalid")
    payload = cast(dict[str, object], unknown_payload)
    version_value = payload["python_version"]
    if not isinstance(version_value, list):
        raise ReceiptError("interpreter_output_invalid")
    version_items = cast(list[object], version_value)
    if len(version_items) != 3 or any(
        not isinstance(item, int) or isinstance(item, bool) for item in version_items
    ):
        raise ReceiptError("interpreter_output_invalid")
    version = cast(list[int], version_items)
    compact = cell.version.replace(".", "")
    identity_values: dict[str, object] = {
        "schema": "mke.target_interpreter_identity.v1",
        "implementation": "cpython",
        "system": "Darwin",
        "machine": "arm64",
        "soabi": f"cpython-{compact}-darwin",
        "ext_suffix": f".cpython-{compact}-darwin.so",
        "cache_tag": f"cpython-{compact}",
        "abiflags": "",
        "pointer_bits": 64,
        "byteorder": "little",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
    sysconfig_platform = payload["sysconfig_platform"]
    if (
        result.stdout != canonical
        or version[:2] != [int(part) for part in cell.version.split(".")]
        or not isinstance(sysconfig_platform, str)
        or re.fullmatch(r"macosx-\d+\.\d+-(?:arm64|universal2)", sysconfig_platform) is None
        or any(payload[key] != value for key, value in identity_values.items())
    ):
        raise ReceiptError("interpreter_identity_mismatch")
    after = _snapshot_executable(path)
    if before != after:
        raise ReceiptError("interpreter_identity_drift")
    label = f"python-{cell.version}"
    return (
        {
            "label": label,
            "implementation": "cpython",
            "python_version": ".".join(str(item) for item in version),
            "system": "Darwin",
            "machine": "arm64",
            "sysconfig_platform": cast(str, payload["sysconfig_platform"]),
            "soabi": cast(str, payload["soabi"]),
            "ext_suffix": cast(str, payload["ext_suffix"]),
            "cache_tag": cast(str, payload["cache_tag"]),
            "abiflags": cast(str, payload["abiflags"]),
            "pointer_bits": cast(int, payload["pointer_bits"]),
            "byteorder": cast(str, payload["byteorder"]),
            "executable_sha256": before.sha256,
        },
        before.identity,
        before.resolved,
    )


def _declared_path_failure(path: Path, *, missing: str, invalid: str) -> str:
    try:
        path.lstat()
    except FileNotFoundError:
        return missing
    except OSError:
        return invalid
    return invalid


def _public_controller_identity(executable: Path) -> dict[str, str]:
    try:
        resolved = executable.resolve(strict=True)
        actual = Path(sys.executable).resolve(strict=True)
        observed = resolved.lstat()
        if (
            resolved != actual
            or not stat.S_ISREG(observed.st_mode)
            or observed.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH) == 0
            or sys.implementation.name != "cpython"
        ):
            raise ReceiptError("controller_executable_invalid")
        value = _read_regular(resolved)
    except ReceiptError:
        raise
    except OSError as error:
        raise ReceiptError("controller_executable_invalid") from error
    return {
        "implementation": "cpython",
        "python_version": platform.python_version(),
        "platform": sysconfig.get_platform(),
        "executable_type": "regular",
        "executable_mode": f"{stat.S_IMODE(observed.st_mode):04o}",
        "executable_sha256": hashlib.sha256(value).hexdigest(),
    }


def _wheel_resolution_issues(
    manifest: tuple[WheelEntry, ...],
    projection: LockProjection,
    hash_authority: dict[tuple[str, str], frozenset[str]],
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    used: set[str] = set()
    requirements_by_cell = dict(projection.requirements_by_cell)
    for cell in projection.cells:
        for requirement in requirements_by_cell[cell.version]:
            subject = f"{cell.version}:{requirement.name}=={requirement.version}"
            same_distribution = [
                entry for entry in manifest if entry.distribution == requirement.name
            ]
            exact_version = [
                entry for entry in same_distribution if entry.version == requirement.version
            ]
            candidates = [entry for entry in exact_version if _wheel_compatible(entry, cell)]
            if not candidates:
                if exact_version:
                    issues.append(_issue("wheel_wrong_tag", subject))
                elif same_distribution:
                    issues.append(_issue("wheel_wrong_version", subject))
                else:
                    issues.append(_issue("wheel_missing", subject))
                continue
            if len(candidates) > 1:
                issues.append(_issue("wheel_ambiguous", subject))
                continue
            candidate = candidates[0]
            used.add(candidate.filename)
            if candidate.sha256 not in hash_authority[(requirement.name, requirement.version)]:
                issues.append(_issue("wheel_substituted", subject))
    for entry in manifest:
        if entry.filename not in used:
            issues.append(
                _issue(
                    "wheel_surplus",
                    f"all:{entry.distribution}=={entry.version}:{entry.filename}",
                )
            )
    return issues


def check_inputs(
    *,
    pythons: tuple[Path, ...],
    wheelhouse: Path,
    constraints: Path,
    fixture_root: Path,
    lock_path: Path | None = None,
    controller_executable: Path | None = None,
) -> dict[str, object]:
    issues: list[dict[str, str]] = []
    interpreters: list[dict[str, object]] = []
    interpreter_identities: dict[tuple[int, ...], str] = {}
    cells = _supported_cells()
    if len(pythons) != 2:
        issues.append(_issue("interpreter_count_invalid", "python-cells"))
    for index, python in enumerate(pythons):
        label = ("python-3.12", "python-3.13")[index] if index < 2 else f"python-extra-{index + 1}"
        try:
            snapshot = _snapshot_executable(python)
        except ReceiptError as error:
            issues.append(_issue(str(error), label))
            continue
        previous = interpreter_identities.get(snapshot.target_file_identity)
        if previous is not None:
            issues.append(_issue("interpreter_identity_duplicate", f"{previous},{label}"))
        else:
            interpreter_identities[snapshot.target_file_identity] = label
        if index >= len(cells):
            continue
        try:
            identity, observed_file_identity, _ = _probe_target_interpreter(
                python, cells[index]
            )
        except ReceiptError as error:
            issues.append(_issue(str(error), label))
        else:
            if observed_file_identity != snapshot.identity:
                issues.append(_issue("interpreter_identity_drift", label))
            else:
                interpreters.append(identity)
    lock_sha: str | None = None
    projection_hash_authority: dict[tuple[str, str], frozenset[str]] = {}
    try:
        if lock_path is None:
            raise ReceiptError("lock_missing")
        lock_value = _read_regular(lock_path)
        projection = _derive_transcription_projection(lock_value, cells)
        lock_sha = hashlib.sha256(lock_value).hexdigest()
        _, projection_hash_authority, _ = _parse_constraints(projection.constraints)
    except ReceiptError as error:
        projection = None
        code = (
            str(error)
            if str(error) == "lock_missing"
            else _declared_path_failure(
                lock_path if lock_path is not None else Path("."),
                missing="lock_missing",
                invalid="lock_invalid",
            )
        )
        issues.append(_issue(code, "uv-lock"))
    constraints_sha: str | None = None
    try:
        constraints_value = _read_regular(constraints)
        constraints_sha = hashlib.sha256(constraints_value).hexdigest()
        if projection is None or constraints_value != projection.constraints:
            raise ReceiptError("constraints_projection_drift")
        _, _, parsed_by_cell = _parse_constraints(constraints_value)
        if parsed_by_cell != projection.requirements_by_cell:
            raise ReceiptError("constraints_projection_drift")
    except ReceiptError as error:
        code = str(error)
        if code in {"input_invalid", "input_identity_drift"}:
            code = _declared_path_failure(
                constraints,
                missing="constraints_missing",
                invalid="constraints_invalid",
            )
        issues.append(_issue(code, "external-constraints"))
    try:
        manifest = build_wheelhouse_manifest(wheelhouse)
        if not manifest:
            issues.append(_issue("wheelhouse_empty", "external-wheelhouse"))
        if projection is None:
            for entry in manifest:
                issues.append(
                    _issue(
                        "wheel_surplus",
                        f"all:{entry.distribution}=={entry.version}:{entry.filename}",
                    )
                )
        else:
            issues.extend(_wheel_resolution_issues(manifest, projection, projection_hash_authority))
    except ReceiptError as error:
        manifest = ()
        code = str(error)
        if code in {"wheel_input_invalid", "input_invalid", "input_identity_drift"}:
            code = _declared_path_failure(
                wheelhouse,
                missing="wheelhouse_missing",
                invalid="wheelhouse_invalid",
            )
        issues.append(_issue(code, "external-wheelhouse"))
        if projection is not None:
            issues.extend(_wheel_resolution_issues((), projection, projection_hash_authority))
    fixture_receipts: list[dict[str, object]] = []
    for name in _FIXTURES:
        try:
            value = _read_regular(fixture_root / name)
        except ReceiptError:
            issues.append(_issue("fixture_missing", name))
        else:
            fixture_receipts.append(
                {"filename": name, "bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
            )
    try:
        controller = _public_controller_identity(
            Path(sys.executable) if controller_executable is None else controller_executable
        )
    except ReceiptError as error:
        controller = None
        issues.append(_issue(str(error), "controller-executable"))
    issues.sort(key=lambda item: json.dumps(item, sort_keys=True))
    script_value = _read_regular(Path(__file__).resolve())
    result: dict[str, object] = {
        "schema": "mke.direct_audio_dependency_input_check.v1",
        "status": "failed" if issues else "passed",
        "gate": "input_validation_failed" if issues else "inputs_valid",
        "distribution": {
            "external_binary_redistribution": "not_performed",
            "redistribution_authority": "not_claimed",
        },
        "controller": controller,
        "script": {"sha256": hashlib.sha256(script_value).hexdigest()},
        "interpreters": sorted(interpreters, key=lambda item: cast(str, item["label"])),
        "lock_sha256": lock_sha,
        "constraints_sha256": constraints_sha,
        "wheelhouse": [
            {
                "filename": entry.filename,
                "bytes": entry.bytes,
                "sha256": entry.sha256,
                "distribution": entry.distribution,
                "version": entry.version,
                "build": entry.build,
                "python_tags": list(entry.python_tags),
                "abi_tags": list(entry.abi_tags),
                "platform_tags": list(entry.platform_tags),
                "artifact_scope": "local_runtime_only",
            }
            for entry in manifest
        ],
        "fixtures": [
            {**item, "artifact_scope": "repository_distributed"} for item in fixture_receipts
        ],
        "issues": issues,
    }
    observed = {
        key: value for key, value in result.items() if key not in {"issues", "status", "gate"}
    }
    result["observed_digest"] = hashlib.sha256(
        json.dumps(observed, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    return result


def _digest_value(value: object) -> bool:
    return isinstance(value, str) and _DIGEST.fullmatch(value) is not None


def _resolved_text(value: object) -> bool:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > 4096:
        return False
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        return False
    return (
        re.search(r"(?:^|\W)(?:unknown|unresolved|unobservable|tbd)(?:$|\W)", value, re.I) is None
    )


def _public_reference(value: object) -> bool:
    return (
        _resolved_text(value)
        and isinstance(value, str)
        and _PUBLIC_REFERENCE.fullmatch(value) is not None
    )


def _generation_preflight_digest(
    wheels: list[dict[str, object]], fixtures: list[dict[str, object]]
) -> str | None:
    if any(not isinstance(item.get("filename"), str) for item in [*wheels, *fixtures]):
        return None
    projection = {
        "fixtures": sorted(fixtures, key=lambda item: cast(str, item["filename"])),
        "wheel_inventory": sorted(wheels, key=lambda item: cast(str, item["filename"])),
    }
    try:
        return _canonical_digest(projection)
    except (TypeError, ValueError, UnicodeEncodeError):
        return None


def _exact_mapping(value: object, keys: set[str]) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    unknown = cast(dict[object, object], value)
    if set(unknown) != keys:
        return None
    return cast(dict[str, object], unknown)


def _inventory_rows(value: object, keys: set[str]) -> list[dict[str, object]] | None:
    if not isinstance(value, list) or not value:
        return None
    rows: list[dict[str, object]] = []
    for item in cast(list[object], value):
        row = _exact_mapping(item, keys)
        if row is None:
            return None
        rows.append(row)
    return rows


def _string_items(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    items = cast(list[object], value)
    if any(not isinstance(item, str) or not item for item in items):
        return None
    return cast(list[str], items)


def validate_generation_evidence(evidence: Mapping[str, object]) -> dict[str, str]:
    """Validate local-use evidence without claiming binary redistribution authority."""
    required = {
        "preflight_observed_digest",
        "generation_preflight_observed_digest",
        "external_binary_redistribution",
        "redistribution_authority",
        "wheel_inventory",
        "installed_distributions",
        "pyav",
        "ffmpeg_runtime",
        "direct_components",
        "fixtures",
        "unresolved_transitive_binary_items",
    }
    if not required.issubset(evidence):
        return {"failure": "generation_evidence_incomplete", "status": "failed"}
    if set(evidence) != required:
        return {"failure": "generation_evidence_invalid", "status": "failed"}
    valid = (
        evidence["external_binary_redistribution"] == "not_performed"
        and evidence["redistribution_authority"] == "not_claimed"
    )
    wheels = _inventory_rows(
        evidence["wheel_inventory"],
        {"filename", "distribution", "version", "sha256", "artifact_scope"},
    )
    installed = _inventory_rows(
        evidence["installed_distributions"],
        {"distribution", "version", "source_wheel_sha256", "cell", "artifact_scope"},
    )
    if wheels is None or installed is None:
        valid = False
    else:
        wheel_authority = {
            (item["distribution"], item["version"], item["sha256"]) for item in wheels
        }
        installed_authority = {
            (
                item["cell"],
                item["distribution"],
                item["version"],
                item["source_wheel_sha256"],
            )
            for item in installed
        }
        valid = (
            valid
            and all(
                (
                    item["distribution"],
                    item["version"],
                    item["source_wheel_sha256"],
                )
                in wheel_authority
                for item in installed
            )
            and {item["sha256"] for item in wheels}
            == {item["source_wheel_sha256"] for item in installed}
            and all(
                isinstance(item["filename"], str)
                and _digest_value(item["sha256"])
                and item["artifact_scope"] == "local_runtime_only"
                for item in wheels
            )
            and all(
                item["cell"] in {"3.12", "3.13"} and item["artifact_scope"] == "local_runtime_only"
                for item in installed
            )
        )
        valid = valid and {item["cell"] for item in installed} == {"3.12", "3.13"}
        valid = (
            valid
            and len(wheel_authority) == len(wheels)
            and len(installed_authority) == len(installed)
        )
    pyav = _exact_mapping(
        evidence["pyav"],
        {
            "distribution",
            "version",
            "artifact_scope",
            "extensions",
            "linked_components",
            "bundled_components",
        },
    )
    linked: set[str] = set()
    bundled: set[str] = set()
    if pyav is None:
        valid = False
    else:
        pyav_row = pyav
        extensions = _inventory_rows(pyav_row["extensions"], {"filename", "sha256"})
        linked_value = _string_items(pyav_row["linked_components"])
        bundled_value = _string_items(pyav_row["bundled_components"])
        if (
            extensions is None
            or linked_value is None
            or bundled_value is None
            or not [*linked_value, *bundled_value]
            or any(
                not isinstance(item["filename"], str) or not _digest_value(item["sha256"])
                for item in extensions
            )
            or len({item["filename"] for item in extensions}) != len(extensions)
            or len(set(linked_value)) != len(linked_value)
            or len(set(bundled_value)) != len(bundled_value)
            or not set(linked_value).isdisjoint(bundled_value)
        ):
            valid = False
        else:
            linked = set(linked_value)
            bundled = set(bundled_value)
            valid = (
                valid
                and pyav_row["artifact_scope"] == "local_runtime_only"
                and installed is not None
                and (pyav_row["distribution"], pyav_row["version"])
                in {(item["distribution"], item["version"]) for item in installed}
            )
    ffmpeg = _exact_mapping(
        evidence["ffmpeg_runtime"],
        {
            "license",
            "configuration",
            "sha256",
            "source_reference",
            "license_text_sha256",
            "artifact_scope",
        },
    )
    if ffmpeg is None:
        valid = False
    else:
        ffmpeg_row = ffmpeg
        valid = (
            valid
            and ffmpeg_row["artifact_scope"] == "local_runtime_only"
            and all(
                _resolved_text(ffmpeg_row[key]) for key in ("license", "configuration")
            )
            and _public_reference(ffmpeg_row["source_reference"])
            and _digest_value(ffmpeg_row["sha256"])
            and _digest_value(ffmpeg_row["license_text_sha256"])
        )
    direct = _inventory_rows(
        evidence["direct_components"],
        {
            "name",
            "version",
            "license",
            "evidence_sha256",
            "source_reference",
            "license_text_sha256",
            "artifact_scope",
            "local_use_restriction",
        },
    )
    if direct is None:
        valid = False
    else:
        direct_names = {item["name"] for item in direct}
        valid = (
            valid
            and direct_names == linked | bundled
            and len(direct_names) == len(direct)
            and all(
                all(_resolved_text(item[key]) for key in ("name", "version", "license"))
                and _public_reference(item["source_reference"])
                and _digest_value(item["evidence_sha256"])
                and _digest_value(item["license_text_sha256"])
                and item["artifact_scope"] == "local_runtime_only"
                and item["local_use_restriction"] == "none_observed"
                for item in direct
            )
        )
    fixtures = _inventory_rows(
        evidence["fixtures"],
        {
            "filename",
            "sha256",
            "redistribution",
            "artifact_scope",
            "bytes",
            "source",
            "recipe_sha256",
            "license",
            "license_evidence_sha256",
            "source_sha256",
            "required_notice",
            "notice_evidence_sha256",
            "redistribution_basis",
            "redistribution_evidence_sha256",
            "profile_sha256",
            "authority_document_sha256",
        },
    )
    if fixtures is None:
        valid = False
    else:
        valid = (
            valid
            and {item["filename"] for item in fixtures} == set(_FIXTURES)
            and len(fixtures) == len(_FIXTURES)
            and all(
                item["redistribution"] == "permitted"
                and item["artifact_scope"] == "repository_distributed"
                and item["bytes"]
                == _FIXTURE_AUTHORITY[cast(str, item["filename"])]["bytes"]
                and item["sha256"]
                == _FIXTURE_AUTHORITY[cast(str, item["filename"])]["sha256"]
                and item["profile_sha256"]
                == _FIXTURE_AUTHORITY[cast(str, item["filename"])]["profile_sha256"]
                and _public_reference(item["source"])
                and item["source"] == "repository-authored-synthetic-speech"
                and item["recipe_sha256"] == _FIXTURE_AUTHORITY_DOCUMENT_SHA256
                and item["license"] == "Flite"
                and item["license_evidence_sha256"] == _FIXTURE_AUTHORITY_DOCUMENT_SHA256
                and item["source_sha256"] == _FIXTURE_SOURCE_SHA256
                and item["required_notice"] == "included"
                and item["notice_evidence_sha256"] == _FIXTURE_AUTHORITY_DOCUMENT_SHA256
                and item["redistribution_basis"] == "documented_source_license_and_recipe"
                and item["redistribution_evidence_sha256"]
                == _FIXTURE_AUTHORITY_DOCUMENT_SHA256
                and item["authority_document_sha256"]
                == _FIXTURE_AUTHORITY_DOCUMENT_SHA256
                for item in fixtures
            )
        )
    if wheels is None or fixtures is None:
        valid = False
    else:
        expected_preflight_digest = _generation_preflight_digest(wheels, fixtures)
        valid = (
            valid
            and expected_preflight_digest is not None
            and evidence["preflight_observed_digest"] == expected_preflight_digest
            and evidence["generation_preflight_observed_digest"] == expected_preflight_digest
        )
    unresolved = evidence["unresolved_transitive_binary_items"]
    unresolved_keys = {
        "name",
        "version",
        "identity_sha256",
        "redistribution_clearance",
        "local_use_restriction",
        "artifact_scope",
    }
    unresolved_rows: list[dict[str, object]] | None = None
    if isinstance(unresolved, list):
        unresolved_rows = []
        for value in cast(list[object], unresolved):
            row = _exact_mapping(value, unresolved_keys)
            if row is None:
                unresolved_rows = None
                break
            unresolved_rows.append(row)
    if unresolved_rows is None or any(
        not _resolved_text(item["name"])
        or not _resolved_text(item["version"])
        or not _digest_value(item["identity_sha256"])
        or item["redistribution_clearance"] != "unresolved"
        or item["local_use_restriction"] != "none_observed"
        or item["artifact_scope"] != "local_runtime_only"
        for item in unresolved_rows
    ):
        valid = False
    elif len({item["name"] for item in unresolved_rows}) != len(unresolved_rows):
        valid = False
    if not valid:
        return {"failure": "generation_evidence_invalid", "status": "failed"}
    return {
        "external_binary_redistribution": "not_performed",
        "redistribution_authority": "not_claimed",
        "status": "passed",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="direct_audio_dependency_receipt.py")
    parser.add_argument("--check-inputs", action="store_true")
    parser.add_argument("--python", action="append", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--constraints", type=Path, required=True)
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.check_inputs:
        payload: dict[str, object] = {
            "failure": "acquisition_authorization_required",
            "status": "failed",
        }
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 1
    if (
        sys.implementation.name != "cpython"
        or not sys.flags.isolated
        or not sys.flags.dont_write_bytecode
    ):
        print(
            json.dumps(
                {"failure": "controller_not_isolated", "status": "failed"},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    payload = check_inputs(
        pythons=tuple(args.python),
        wheelhouse=args.wheelhouse,
        lock_path=args.lock,
        constraints=args.constraints,
        fixture_root=args.fixture_root,
    )
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
