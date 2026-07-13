#!/usr/bin/env python3
"""Prepare and replay the PDF OCR Phase 0 package compatibility matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, NoReturn, cast

_SCHEMA = "mke.pdf_ocr_candidate_environments.v1"
_RECEIPT_PROFILE = "phase0-package-only-v1"
_CANDIDATE_PROFILE = "phase0-200dpi-plain-text-v1"
_MKE_WHEEL_FILENAME = "multimodal_knowledge_engine-0.1.1-py3-none-any.whl"
_SURFACES = ("base", "embedding", "transcription", "embedding+transcription")
_PYTHON_MINORS = ("3.12", "3.13")
_RESULTS = frozenset({"passed", "resolver_failed", "offline_replay_failed", "validation_failed"})
_FAILURE_CODES = frozenset(
    {
        "resolver_unavailable",
        "offline_install_failed",
        "pip_check_failed",
        "import_doctor_failed",
        "mke_identity_failed",
        "fake_child_failed",
    }
)
_READ_CHUNK_BYTES = 8192
_POLL_SECONDS = 0.02
_TERMINATION_GRACE_SECONDS = 0.5
_DEFAULT_TIMEOUT_SECONDS = 600.0
_DEFAULT_STDOUT_BYTES = 2 * 1024 * 1024
_DEFAULT_STDERR_BYTES = 2 * 1024 * 1024
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_VERSION_RE = re.compile(r"[0-9]+(?:\.[0-9A-Za-z]+)+(?:[-+._][0-9A-Za-z]+)*\Z")
_SAFE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+()-]{0,255}\Z")
_PRIVATE_RE = re.compile(
    r"(?:/Users/|/private/|[A-Za-z]:\\|https?://|Traceback|API[_-]?KEY|TOKEN=|"
    r"SECRET=|PASSWORD=|BEGIN [A-Z ]*PRIVATE KEY)",
    re.IGNORECASE,
)
_RESOLVER_MARKERS = (
    b"no matching distribution found",
    b"could not find a version that satisfies the requirement",
    b"resolutionimpossible",
)


class CompatibilityError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Candidate:
    candidate: str
    profile: str
    requirements: tuple[str, str]
    required_symbol: str


CANDIDATES: dict[str, Candidate] = {
    "ppocrv6-medium-cpu-spike-v1": Candidate(
        candidate="ppocrv6-medium-cpu-spike-v1",
        profile=_CANDIDATE_PROFILE,
        requirements=("paddleocr==3.7.0", "paddlepaddle==3.3.1"),
        required_symbol="PaddleOCR",
    ),
    "paddleocr-vl-1.6-cpu-spike-v1": Candidate(
        candidate="paddleocr-vl-1.6-cpu-spike-v1",
        profile=_CANDIDATE_PROFILE,
        requirements=("paddleocr[doc-parser]==3.7.0", "paddlepaddle==3.3.1"),
        required_symbol="PaddleOCRVL",
    ),
}


@dataclass(frozen=True)
class InterpreterIdentity:
    python: Path
    version: str
    minor: str

    def __post_init__(self) -> None:
        if self.minor not in _PYTHON_MINORS or not self.version.startswith(self.minor + "."):
            raise ValueError("interpreter version is invalid")


@dataclass(frozen=True)
class MatrixCell:
    candidate: str
    profile: str
    surface: str
    python: Path
    python_version: str
    python_minor: str
    mke_wheel_sha256: str


@dataclass(frozen=True)
class MatrixPlan:
    cells: tuple[MatrixCell, ...]
    mke_wheel_sha256: str


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: bytes
    stderr: bytes


@dataclass(frozen=True)
class CompatibilityConfig:
    repository: Path
    wheel: Path
    interpreters: tuple[Path, Path]
    staging_root: Path
    cache_root: Path
    output: Path
    allow_package_download: bool
    prepared_wheelhouses: Path | None = None
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS
    max_stdout_bytes: int = _DEFAULT_STDOUT_BYTES
    max_stderr_bytes: int = _DEFAULT_STDERR_BYTES


@dataclass
class _Capture:
    limit: int
    data: bytearray
    exceeded: threading.Event


def build_matrix_plan(
    wheel: Path,
    interpreters: tuple[InterpreterIdentity, InterpreterIdentity],
) -> MatrixPlan:
    if not wheel.is_file() or wheel.suffix != ".whl":
        raise ValueError("MKE wheel is invalid")
    resolved = tuple(item.python.resolve() for item in interpreters)
    if resolved[0] == resolved[1]:
        raise ValueError("interpreter aliasing is forbidden")
    if {item.minor for item in interpreters} != set(_PYTHON_MINORS):
        raise ValueError("interpreters must cover exact Python 3.12 and 3.13")
    digest = _sha256_file(wheel)
    cells = tuple(
        MatrixCell(
            candidate=candidate.candidate,
            profile=candidate.profile,
            surface=surface,
            python=interpreter.python,
            python_version=interpreter.version,
            python_minor=interpreter.minor,
            mke_wheel_sha256=digest,
        )
        for candidate in CANDIDATES.values()
        for interpreter in sorted(interpreters, key=lambda item: item.minor)
        for surface in _SURFACES
    )
    return MatrixPlan(cells=cells, mke_wheel_sha256=digest)


def candidate_download_command(
    *,
    python: Path,
    wheel: Path,
    candidate: Candidate,
    destination: Path,
    cache: Path,
) -> tuple[str, ...]:
    return (
        str(python),
        "-m",
        "pip",
        "download",
        "--disable-pip-version-check",
        "--only-binary=:all:",
        "--dest",
        str(destination),
        "--cache-dir",
        str(cache),
        f"{wheel}[embedding,transcription]",
        *candidate.requirements,
    )


def offline_install_command(
    *,
    python: Path,
    wheel: Path,
    candidate: Candidate,
    surface: str,
    wheelhouse: Path,
) -> tuple[str, ...]:
    if surface not in _SURFACES:
        raise ValueError("matrix surface is invalid")
    extras = {
        "base": "",
        "embedding": "[embedding]",
        "transcription": "[transcription]",
        "embedding+transcription": "[embedding,transcription]",
    }[surface]
    return (
        str(python),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-index",
        "--find-links",
        str(wheelhouse),
        f"{wheel}{extras}",
        *candidate.requirements,
    )


def classify_prepare_failure(stderr: bytes) -> str:
    normalized = stderr.lower()
    if any(marker in normalized for marker in _RESOLVER_MARKERS):
        return "resolver_failed"
    return "infrastructure_failed"


def validate_acquisition_mode(
    allow_package_download: bool,
    prepared_wheelhouses: Path | None,
) -> Path | None:
    if allow_package_download and prepared_wheelhouses is not None:
        raise CompatibilityError("acquisition_mode_invalid")
    if allow_package_download:
        return None
    if prepared_wheelhouses is None:
        raise CompatibilityError("package_download_not_authorized")
    resolved = prepared_wheelhouses.resolve()
    if not resolved.is_dir():
        raise CompatibilityError("prepared_wheelhouses_invalid")
    return resolved


def run_bounded(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    timeout_seconds: float,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
) -> CommandResult:
    if timeout_seconds <= 0 or max_stdout_bytes <= 0 or max_stderr_bytes <= 0:
        raise CompatibilityError("command_contract_invalid")
    try:
        process = subprocess.Popen(
            list(command),
            shell=False,
            cwd=cwd,
            env=dict(env),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=os.name == "posix",
        )
    except OSError as error:
        raise CompatibilityError("command_could_not_start") from error
    pgid: int | None = process.pid if os.name == "posix" else None
    if process.stdout is None or process.stderr is None:
        _terminate(process, pgid)
        raise CompatibilityError("command_capture_failed")
    stdout = _Capture(max_stdout_bytes, bytearray(), threading.Event())
    stderr = _Capture(max_stderr_bytes, bytearray(), threading.Event())
    readers = (
        threading.Thread(target=_drain, args=(process.stdout, stdout), daemon=True),
        threading.Thread(target=_drain, args=(process.stderr, stderr), daemon=True),
    )
    for reader in readers:
        reader.start()
    deadline = time.monotonic() + timeout_seconds
    try:
        while process.poll() is None:
            if stdout.exceeded.is_set() or stderr.exceeded.is_set():
                raise CompatibilityError("command_output_exceeded")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise CompatibilityError("command_timed_out")
            try:
                process.wait(timeout=min(_POLL_SECONDS, remaining))
            except subprocess.TimeoutExpired:
                continue
        _terminate(process, pgid)
        for reader in readers:
            reader.join(timeout=1)
        if any(reader.is_alive() for reader in readers):
            raise CompatibilityError("command_capture_failed")
        if stdout.exceeded.is_set() or stderr.exceeded.is_set():
            raise CompatibilityError("command_output_exceeded")
        return CommandResult(process.returncode, bytes(stdout.data), bytes(stderr.data))
    except BaseException:
        _terminate(process, pgid)
        for reader in readers:
            reader.join(timeout=1)
        raise
    finally:
        for stream in (process.stdout, process.stderr):
            try:
                stream.close()
            except OSError:
                pass


def validate_receipt(value: object) -> None:
    receipt = _mapping(value)
    _exact(receipt, {"schema", "profile", "platform", "mke_wheel_sha256", "candidates"})
    if receipt["schema"] != _SCHEMA or receipt["profile"] != _RECEIPT_PROFILE:
        _receipt_error()
    mke_wheel_sha256 = _digest(receipt["mke_wheel_sha256"])
    runtime = _mapping(receipt["platform"])
    _exact(runtime, {"os", "architecture"})
    _safe(runtime["os"])
    _safe(runtime["architecture"])
    raw_candidates = receipt["candidates"]
    if not isinstance(raw_candidates, list):
        _receipt_error()
    candidate_items = cast(list[object], raw_candidates)
    if len(candidate_items) != 2:
        _receipt_error()
    observed_candidates: set[str] = set()
    observed_cells: set[tuple[str, str, str]] = set()
    for raw_candidate in candidate_items:
        candidate = _mapping(raw_candidate)
        _exact(
            candidate,
            {"candidate", "profile", "pins", "distributions", "download_bytes", "cells"},
        )
        candidate_id = _safe(candidate["candidate"])
        expected = CANDIDATES.get(candidate_id)
        if expected is None or candidate["profile"] != expected.profile:
            _receipt_error()
        observed_candidates.add(candidate_id)
        pins = candidate["pins"]
        if not isinstance(pins, list) or pins != list(expected.requirements):
            _receipt_error()
        download_bytes = _nonnegative_integer(candidate["download_bytes"])
        distributions = _validate_distributions(candidate["distributions"])
        if not distributions or download_bytes != sum(
            _nonnegative_integer(item["bytes"]) for item in distributions
        ):
            _receipt_error()
        mke_distributions = [
            item for item in distributions if item["filename"] == _MKE_WHEEL_FILENAME
        ]
        if (
            len(mke_distributions) != 1
            or mke_distributions[0]["sha256"] != mke_wheel_sha256
        ):
            _receipt_error()
        cells = candidate["cells"]
        if not isinstance(cells, list):
            _receipt_error()
        cell_items = cast(list[object], cells)
        if len(cell_items) != 8:
            _receipt_error()
        for raw_cell in cell_items:
            cell = _mapping(raw_cell)
            _exact(
                cell,
                {
                    "python",
                    "python_minor",
                    "surface",
                    "result",
                    "failure_code",
                    "package_versions",
                    "install_bytes",
                },
            )
            python = _version(cell["python"])
            minor = cell["python_minor"]
            surface = cell["surface"]
            result = cell["result"]
            if (
                minor not in _PYTHON_MINORS
                or not python.startswith(cast(str, minor) + ".")
                or surface not in _SURFACES
                or result not in _RESULTS
            ):
                _receipt_error()
            key = (candidate_id, cast(str, minor), cast(str, surface))
            if key in observed_cells:
                _receipt_error()
            observed_cells.add(key)
            failure_code = cell["failure_code"]
            versions = _mapping(cell["package_versions"])
            if result == "passed":
                if failure_code is not None or not versions:
                    _receipt_error()
                if (
                    versions.get("multimodal-knowledge-engine") != "0.1.1"
                    or versions.get("paddleocr") != "3.7.0"
                    or versions.get("paddlepaddle") != "3.3.1"
                ):
                    _receipt_error()
            elif failure_code not in _FAILURE_CODES or versions:
                _receipt_error()
            for name, version in versions.items():
                _safe(name)
                _version(version)
            _nonnegative_integer(cell["install_bytes"])
    expected_cells = {
        (candidate, minor, surface)
        for candidate in CANDIDATES
        for minor in _PYTHON_MINORS
        for surface in _SURFACES
    }
    if observed_candidates != set(CANDIDATES) or observed_cells != expected_cells:
        _receipt_error()
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    if _PRIVATE_RE.search(encoded):
        _receipt_error()


def canonical_receipt_bytes(receipt: object) -> bytes:
    validate_receipt(receipt)
    return (json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def validate_committed_receipt_bytes(
    encoded: bytes,
    *,
    frozen_sha256: str,
) -> dict[str, object]:
    _digest(frozen_sha256)
    if hashlib.sha256(encoded).hexdigest() != frozen_sha256:
        _receipt_error()
    try:
        receipt = json.loads(encoded.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("candidate compatibility receipt is invalid") from error
    validate_receipt(receipt)
    if canonical_receipt_bytes(receipt) != encoded:
        _receipt_error()
    return _mapping(receipt)


def probe_interpreter(
    python: Path,
    *,
    cwd: Path,
    env: Mapping[str, str],
    timeout_seconds: float,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
) -> InterpreterIdentity:
    result = run_bounded(
        (
            str(python),
            "-I",
            "-c",
            (
                "import json,platform,sys;"
                "print(json.dumps({'executable':sys.executable,'version':platform.python_version(),"
                "'minor':f'{sys.version_info.major}.{sys.version_info.minor}'}))"
            ),
        ),
        cwd=cwd,
        env=env,
        timeout_seconds=timeout_seconds,
        max_stdout_bytes=max_stdout_bytes,
        max_stderr_bytes=max_stderr_bytes,
    )
    if result.returncode != 0:
        raise CompatibilityError("interpreter_probe_failed")
    try:
        payload = json.loads(result.stdout)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise CompatibilityError("interpreter_probe_failed") from error
    data = _mapping(payload)
    _exact(data, {"executable", "version", "minor"})
    executable = data["executable"]
    version = data["version"]
    minor = data["minor"]
    if (
        not isinstance(executable, str)
        or not isinstance(version, str)
        or not isinstance(minor, str)
    ):
        raise CompatibilityError("interpreter_probe_failed")
    return InterpreterIdentity(Path(executable), version, minor)


def run_package_matrix(config: CompatibilityConfig) -> dict[str, object]:
    repository = config.repository.resolve()
    wheel = config.wheel.resolve()
    staging = config.staging_root.resolve()
    cache = config.cache_root.resolve()
    output = config.output.resolve()
    prepared_wheelhouses = validate_acquisition_mode(
        config.allow_package_download,
        config.prepared_wheelhouses,
    )
    if not repository.is_dir() or not wheel.is_file():
        raise CompatibilityError("input_invalid")
    external_paths = (staging, cache) + (
        (prepared_wheelhouses,) if prepared_wheelhouses is not None else ()
    )
    if any(_within(path, repository) for path in external_paths):
        raise CompatibilityError("external_isolation_failed")
    if output != repository / "benchmarks/ocr/candidate-environments.json":
        raise CompatibilityError("output_invalid")
    if staging.exists() or cache.exists():
        raise CompatibilityError("call_owned_root_exists")
    staging.mkdir(mode=0o700, parents=True)
    cache.mkdir(mode=0o700, parents=True)
    runtime_root = staging / "runtime"
    wheelhouse_root = prepared_wheelhouses or staging / "wheelhouses"
    prepare_root = staging / "prepare"
    directories = [runtime_root]
    if prepared_wheelhouses is None:
        directories.extend((wheelhouse_root, prepare_root))
    for directory in directories:
        directory.mkdir(mode=0o700)
    online_env = _package_environment(staging / "home", cache, offline=False)
    offline_env = _package_environment(staging / "home", cache, offline=True)
    identities = tuple(
        probe_interpreter(
            path,
            cwd=staging,
            env=offline_env,
            timeout_seconds=config.timeout_seconds,
            max_stdout_bytes=config.max_stdout_bytes,
            max_stderr_bytes=config.max_stderr_bytes,
        )
        for path in config.interpreters
    )
    plan = build_matrix_plan(
        wheel,
        cast(tuple[InterpreterIdentity, InterpreterIdentity], identities),
    )
    candidate_receipts: list[dict[str, object]] = []
    for candidate in CANDIDATES.values():
        wheelhouse = wheelhouse_root / candidate.candidate
        if prepared_wheelhouses is None:
            wheelhouse.mkdir(mode=0o700)
        elif not wheelhouse.is_dir():
            raise CompatibilityError("prepared_wheelhouses_invalid")
        preparation_failures: dict[str, str] = {}
        if prepared_wheelhouses is None:
            for identity in sorted(identities, key=lambda item: item.minor):
                destination = prepare_root / f"{candidate.candidate}-{identity.minor}"
                destination.mkdir(mode=0o700)
                result = run_bounded(
                    candidate_download_command(
                        python=identity.python,
                        wheel=wheel,
                        candidate=candidate,
                        destination=destination,
                        cache=cache,
                    ),
                    cwd=staging,
                    env=online_env,
                    timeout_seconds=config.timeout_seconds,
                    max_stdout_bytes=config.max_stdout_bytes,
                    max_stderr_bytes=config.max_stderr_bytes,
                )
                if result.returncode != 0:
                    classification = classify_prepare_failure(result.stderr)
                    shutil.rmtree(destination)
                    if classification != "resolver_failed":
                        raise CompatibilityError("package_prepare_infrastructure_failed")
                    preparation_failures[identity.minor] = "resolver_unavailable"
                    continue
                _merge_wheels(destination, wheelhouse)
                shutil.rmtree(destination)
        distributions = _distribution_receipts(wheelhouse)
        cells: list[dict[str, object]] = []
        for cell in (item for item in plan.cells if item.candidate == candidate.candidate):
            if cell.python_minor in preparation_failures:
                cells.append(
                    _failed_cell(cell, "resolver_failed", preparation_failures[cell.python_minor])
                )
                continue
            cells.append(
                _run_offline_cell(
                    cell,
                    candidate=candidate,
                    wheel=wheel,
                    wheelhouse=wheelhouse,
                    runtime_root=runtime_root,
                    repository=repository,
                    environment=offline_env,
                    config=config,
                )
            )
        candidate_receipts.append(
            {
                "candidate": candidate.candidate,
                "profile": candidate.profile,
                "pins": list(candidate.requirements),
                "distributions": distributions,
                "download_bytes": sum(cast(int, item["bytes"]) for item in distributions),
                "cells": cells,
            }
        )
    receipt: dict[str, object] = {
        "schema": _SCHEMA,
        "profile": _RECEIPT_PROFILE,
        "platform": {"os": platform.system(), "architecture": platform.machine()},
        "mke_wheel_sha256": plan.mke_wheel_sha256,
        "candidates": candidate_receipts,
    }
    encoded = canonical_receipt_bytes(receipt)
    output.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    temporary = output.with_suffix(".json.tmp")
    temporary.write_bytes(encoded)
    os.replace(temporary, output)
    if any(runtime_root.iterdir()):
        raise CompatibilityError("cleanup_failed")
    return receipt


def _run_offline_cell(
    cell: MatrixCell,
    *,
    candidate: Candidate,
    wheel: Path,
    wheelhouse: Path,
    runtime_root: Path,
    repository: Path,
    environment: Mapping[str, str],
    config: CompatibilityConfig,
) -> dict[str, object]:
    cell_root = Path(tempfile.mkdtemp(prefix="cell-", dir=runtime_root))
    runtime = cell_root / "venv"
    try:
        create = run_bounded(
            (str(cell.python), "-m", "venv", str(runtime)),
            cwd=cell_root,
            env=environment,
            timeout_seconds=config.timeout_seconds,
            max_stdout_bytes=config.max_stdout_bytes,
            max_stderr_bytes=config.max_stderr_bytes,
        )
        if create.returncode != 0:
            raise CompatibilityError("environment_create_failed")
        python = runtime / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        install = run_bounded(
            offline_install_command(
                python=python,
                wheel=wheel,
                candidate=candidate,
                surface=cell.surface,
                wheelhouse=wheelhouse,
            ),
            cwd=cell_root,
            env=environment,
            timeout_seconds=config.timeout_seconds,
            max_stdout_bytes=config.max_stdout_bytes,
            max_stderr_bytes=config.max_stderr_bytes,
        )
        if install.returncode != 0:
            return _failed_cell(
                cell,
                "offline_replay_failed",
                "offline_install_failed",
                install_bytes=_tree_bytes(runtime),
            )
        checked = run_bounded(
            (str(python), "-m", "pip", "check"),
            cwd=cell_root,
            env=environment,
            timeout_seconds=config.timeout_seconds,
            max_stdout_bytes=config.max_stdout_bytes,
            max_stderr_bytes=config.max_stderr_bytes,
        )
        if checked.returncode != 0:
            return _failed_cell(
                cell,
                "validation_failed",
                "pip_check_failed",
                install_bytes=_tree_bytes(runtime),
            )
        identity = _run_import_doctor(
            python,
            cell=cell,
            candidate=candidate,
            cwd=cell_root,
            environment=environment,
            config=config,
        )
        if identity is None:
            return _failed_cell(
                cell,
                "validation_failed",
                "import_doctor_failed",
                install_bytes=_tree_bytes(runtime),
            )
        if not _valid_installed_identity(
            identity,
            runtime=runtime,
            repository=repository,
            expected_python=cell.python_version,
        ):
            return _failed_cell(
                cell,
                "validation_failed",
                "mke_identity_failed",
                install_bytes=_tree_bytes(runtime),
            )
        fake = run_bounded(
            (str(python), "-I", "-c", _FAKE_CHILD_PROOF),
            cwd=cell_root,
            env=environment,
            timeout_seconds=config.timeout_seconds,
            max_stdout_bytes=config.max_stdout_bytes,
            max_stderr_bytes=config.max_stderr_bytes,
        )
        if fake.returncode != 0 or fake.stdout.strip() != b'{"status": "passed"}':
            return _failed_cell(
                cell,
                "validation_failed",
                "fake_child_failed",
                install_bytes=_tree_bytes(runtime),
            )
        versions = identity.get("package_versions")
        if not isinstance(versions, dict):
            raise CompatibilityError("identity_contract_failed")
        return {
            "python": cell.python_version,
            "python_minor": cell.python_minor,
            "surface": cell.surface,
            "result": "passed",
            "failure_code": None,
            "package_versions": dict(sorted(cast(dict[str, str], versions).items())),
            "install_bytes": _tree_bytes(runtime),
        }
    finally:
        shutil.rmtree(cell_root, ignore_errors=True)
        if cell_root.exists():
            raise CompatibilityError("cleanup_failed")


def _run_import_doctor(
    python: Path,
    *,
    cell: MatrixCell,
    candidate: Candidate,
    cwd: Path,
    environment: Mapping[str, str],
    config: CompatibilityConfig,
) -> dict[str, object] | None:
    modules = ["mke", "paddle", "paddleocr"]
    if "embedding" in cell.surface:
        modules.extend(["sentence_transformers", "sqlite_vec", "huggingface_hub"])
    if "transcription" in cell.surface:
        modules.extend(["faster_whisper", "av", "huggingface_hub"])
    program = (
        "import importlib,importlib.metadata as md,json,platform,sys;"
        f"mods={modules!r};"
        "[importlib.import_module(name) for name in mods];"
        "p=importlib.import_module('paddleocr');"
        f"assert hasattr(p,{candidate.required_symbol!r});"
        "versions={};"
        "[(versions.setdefault((d.metadata.get('Name') or '').lower().replace('_','-'),d.version)) "
        "for d in md.distributions() if d.metadata.get('Name')];"
        "import mke;"
        "print(json.dumps({'mke_file':mke.__file__,'sys_executable':sys.executable,"
        "'sys_prefix':sys.prefix,'sys_base_prefix':sys.base_prefix,"
        "'python':platform.python_version(),'package_versions':versions},sort_keys=True))"
    )
    result = run_bounded(
        (str(python), "-I", "-c", program),
        cwd=cwd,
        env=environment,
        timeout_seconds=config.timeout_seconds,
        max_stdout_bytes=config.max_stdout_bytes,
        max_stderr_bytes=config.max_stderr_bytes,
    )
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except (UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return cast(dict[str, object], payload)


def _valid_installed_identity(
    value: Mapping[str, object],
    *,
    runtime: Path,
    repository: Path,
    expected_python: str,
) -> bool:
    if set(value) != {
        "mke_file",
        "sys_executable",
        "sys_prefix",
        "sys_base_prefix",
        "python",
        "package_versions",
    }:
        return False
    module = value["mke_file"]
    executable = value["sys_executable"]
    prefix = value["sys_prefix"]
    base_prefix = value["sys_base_prefix"]
    version = value["python"]
    versions = value["package_versions"]
    if (
        not isinstance(module, str)
        or not isinstance(executable, str)
        or not isinstance(prefix, str)
        or not isinstance(base_prefix, str)
        or version != expected_python
        or not isinstance(versions, dict)
    ):
        return False
    try:
        module_path = Path(module).resolve()
        prefix_path = Path(prefix).resolve()
        base_prefix_path = Path(base_prefix).resolve()
    except OSError:
        return False
    return (
        _within(module_path, runtime)
        and not _within(module_path, repository)
        and _lexically_within(Path(executable), runtime)
        and _within(prefix_path, runtime)
        and not _within(prefix_path, repository)
        and not _within(base_prefix_path, runtime)
        and "site-packages" in module_path.parts
    )


def _failed_cell(
    cell: MatrixCell,
    result: str,
    failure_code: str,
    *,
    install_bytes: int = 0,
) -> dict[str, object]:
    return {
        "python": cell.python_version,
        "python_minor": cell.python_minor,
        "surface": cell.surface,
        "result": result,
        "failure_code": failure_code,
        "package_versions": {},
        "install_bytes": install_bytes,
    }


def _merge_wheels(source: Path, destination: Path) -> None:
    entries = tuple(source.iterdir())
    if not entries:
        raise CompatibilityError("package_prepare_failed")
    for entry in entries:
        metadata = entry.lstat()
        if entry.is_symlink() or not stat.S_ISREG(metadata.st_mode) or entry.suffix != ".whl":
            raise CompatibilityError("package_prepare_failed")
        target = destination / entry.name
        if target.exists():
            if _sha256_file(target) != _sha256_file(entry):
                raise CompatibilityError("distribution_identity_drift")
            continue
        shutil.copyfile(entry, target)


def _distribution_receipts(wheelhouse: Path) -> list[dict[str, object]]:
    receipts: list[dict[str, object]] = []
    for path in sorted(wheelhouse.iterdir(), key=lambda item: item.name):
        metadata = path.lstat()
        if path.is_symlink() or not stat.S_ISREG(metadata.st_mode) or path.suffix != ".whl":
            raise CompatibilityError("distribution_inventory_invalid")
        receipts.append(
            {"filename": path.name, "sha256": _sha256_file(path), "bytes": metadata.st_size}
        )
    return receipts


def _package_environment(home: Path, cache: Path, *, offline: bool) -> dict[str, str]:
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = home.parent / "tmp"
    temporary.mkdir(mode=0o700, exist_ok=True)
    environment = {
        "HOME": str(home),
        "TMPDIR": str(temporary),
        "TMP": str(temporary),
        "TEMP": str(temporary),
        "PIP_CACHE_DIR": str(cache),
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "PATH": os.defpath,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    if offline:
        environment["PIP_NO_INDEX"] = "1"
    if os.name == "nt":
        for key in ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT"):
            value = os.environ.get(key)
            if value is not None:
                environment[key] = value
    return environment


def _drain(stream: BinaryIO, capture: _Capture) -> None:
    try:
        while chunk := stream.read(_READ_CHUNK_BYTES):
            remaining = capture.limit - len(capture.data)
            if remaining > 0:
                capture.data.extend(chunk[:remaining])
            if len(chunk) > remaining:
                capture.exceeded.set()
    except (OSError, ValueError):
        capture.exceeded.set()


def _group_exists(pgid: int) -> bool:
    if os.name != "posix":
        return False
    try:
        os.killpg(pgid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _terminate(process: subprocess.Popen[bytes], pgid: int | None) -> None:
    if pgid is not None:
        try:
            os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        deadline = time.monotonic() + _TERMINATION_GRACE_SECONDS
        while time.monotonic() < deadline:
            if process.poll() is not None and not _group_exists(pgid):
                break
            time.sleep(_POLL_SECONDS)
        if _group_exists(pgid):
            try:
                os.killpg(pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
    elif process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
    try:
        process.wait(timeout=_TERMINATION_GRACE_SECONDS)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _tree_bytes(root: Path) -> int:
    total = 0
    for path in root.rglob("*"):
        metadata = path.lstat()
        if stat.S_ISREG(metadata.st_mode):
            total += metadata.st_size
    return total


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _lexically_within(path: Path, parent: Path) -> bool:
    try:
        Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(parent)))
    except ValueError:
        return False
    return True


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        _receipt_error()
    unknown = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in unknown):
        _receipt_error()
    return cast(dict[str, object], value)


def _exact(value: Mapping[str, object], keys: set[str]) -> None:
    if set(value) != keys:
        _receipt_error()


def _safe(value: object) -> str:
    if not isinstance(value, str) or _SAFE_RE.fullmatch(value) is None:
        _receipt_error()
    return value


def _version(value: object) -> str:
    if not isinstance(value, str) or _VERSION_RE.fullmatch(value) is None:
        _receipt_error()
    return value


def _digest(value: object) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        _receipt_error()
    return value


def _nonnegative_integer(value: object) -> int:
    if type(value) is not int or value < 0:
        _receipt_error()
    return value


def _validate_distributions(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        _receipt_error()
    distributions: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in cast(list[object], value):
        distribution = _mapping(raw)
        _exact(distribution, {"filename", "sha256", "bytes"})
        filename = _safe(distribution["filename"])
        if filename in seen or Path(filename).name != filename or not filename.endswith(".whl"):
            _receipt_error()
        seen.add(filename)
        _digest(distribution["sha256"])
        _nonnegative_integer(distribution["bytes"])
        distributions.append(distribution)
    return distributions


def _receipt_error() -> NoReturn:
    raise ValueError("candidate compatibility receipt is invalid")


_FAKE_CHILD_PROOF = r'''
import json
import pathlib
import sys
import tempfile
from mke.evaluation.pdf_ocr_provider import ProviderCommand, run_provider
with tempfile.TemporaryDirectory(prefix="mke-ocr-fake-child-") as raw:
    root = pathlib.Path(raw)
    image = root / "page.png"
    image.write_bytes(b"image")
    payload = {
        "schema": "mke.pdf_ocr_eval_result.v1",
        "provider": "ppocrv6-medium-cpu-spike-v1",
        "profile": "phase0-200dpi-plain-text-v1",
        "page_number": 1,
        "lines": [
            {"text": "package proof", "confidence": 0.9, "box": [0, 0, 1, 1]}
        ],
        "normalized_text": "package proof",
        "duration_ms": 1,
    }
    child = (
        "import argparse,json,pathlib;"
        "p=argparse.ArgumentParser();"
        "p.add_argument('--input');p.add_argument('--output');"
        "p.add_argument('--page-number');a=p.parse_args();"
        "pathlib.Path(a.output).write_text(json.dumps(" + repr(payload) + "),"
        "encoding='utf-8')"
    )
    command = ProviderCommand(
        argv=(
            sys.executable,
            "-c",
            child,
            "--input",
            "{input}",
            "--output",
            "{output}",
            "--page-number",
            "{page_number}",
        ),
        provider="ppocrv6-medium-cpu-spike-v1",
        profile="phase0-200dpi-plain-text-v1",
        timeout_seconds=30,
    )
    result = run_provider(command,image_path=image,page_number=1,output_root=root / "output")
    assert result.normalized_text == "package proof"
print(json.dumps({"status":"passed"},sort_keys=True))
'''


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--python", required=True, action="append", type=Path)
    parser.add_argument("--staging-root", required=True, type=Path)
    parser.add_argument("--cache-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--allow-package-download", action="store_true")
    parser.add_argument("--prepared-wheelhouses", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=_DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if len(args.python) != 2:
        parser.error("--python must be supplied exactly twice")
    try:
        receipt = run_package_matrix(
            CompatibilityConfig(
                repository=args.repository,
                wheel=args.wheel,
                interpreters=(args.python[0], args.python[1]),
                staging_root=args.staging_root,
                cache_root=args.cache_root,
                output=args.output,
                allow_package_download=args.allow_package_download,
                prepared_wheelhouses=args.prepared_wheelhouses,
                timeout_seconds=args.timeout_seconds,
            )
        )
    except (CompatibilityError, ValueError) as error:
        failure = error.code if isinstance(error, CompatibilityError) else "receipt_invalid"
        if args.json:
            print(json.dumps({"status": "failed", "code": failure}, sort_keys=True))
        return 1
    if args.json:
        print(canonical_receipt_bytes(receipt).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
