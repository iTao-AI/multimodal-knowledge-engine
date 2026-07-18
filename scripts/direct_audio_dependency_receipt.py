#!/usr/bin/env python3
"""Validate offline inputs for the direct-audio external dependency receipt.

The ``--check-inputs`` path is deliberately stdlib-only and read-only. It runs
only a fixed, bounded identity probe for each declared interpreter. Receipt
generation remains gated on independently acquired and authorized inputs.
"""

from __future__ import annotations

import argparse
import ast
import ctypes
import hashlib
import json
import os
import platform
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import sysconfig
import tempfile
import time
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, cast
from urllib.parse import urlsplit

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_DIST = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*\Z")
_VERSION = re.compile(r"[0-9][a-z0-9]*(?:[._+][a-z0-9]+)*\Z")
_TAG = re.compile(r"[a-z0-9_]+(?:\.[a-z0-9_]+)*\Z")
_PUBLIC_REFERENCE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*\Z")
_SPDX_LICENSE = re.compile(r"(?:MIT|[A-Za-z][A-Za-z0-9]*-[0-9]+(?:\.[0-9]+)*(?:-[A-Za-z0-9]+)*)\Z")
_EXTENSION_PART = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\Z")
_FFMPEG_FLAG = re.compile(
    r"(?:--(?:enable|disable)-[a-z0-9]+(?:-[a-z0-9]+)*|"
    r"--[a-z0-9]+(?:-[a-z0-9]+)*=[a-z0-9_+,-]+)\Z"
)
_FFMPEG_LICENSE = re.compile(r"(?:LGPL|GPL) version [0-9]+(?:\.[0-9]+)*(?: or later)?\Z")
_FIXTURES = ("direct-audio.m4a", "direct-audio.mp3", "direct-audio.wav")
_FIXTURE_FILES = ("README.md", *_FIXTURES)
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
    "README.md": {
        "bytes": 7_256,
        "sha256": _FIXTURE_AUTHORITY_DOCUMENT_SHA256,
    },
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
    locked_wheels: tuple[WheelEntry, ...]
    cells: tuple[Cell, ...]


@dataclass(frozen=True)
class ExecutableSnapshot:
    resolved: Path
    identity: tuple[int, ...]
    target_file_identity: tuple[int, int]
    sha256: str


@dataclass(frozen=True)
class FileAuthority:
    identity: tuple[int, ...]
    bytes: int
    sha256: str


@dataclass(frozen=True)
class PipInputAuthority:
    constraints: FileAuthority
    root_requirements: FileAuthority
    wheelhouse_identity: tuple[int, ...]
    wheels: tuple[tuple[str, FileAuthority], ...]


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
_PIP_ARGV_AUTHORITY = [
    "call-owned-venv-python",
    "-I",
    "-m",
    "pip",
    "--isolated",
    "--disable-pip-version-check",
    "--no-input",
    "install",
    "--no-index",
    "--find-links",
    "call-owned-wheelhouse-uri",
    "--only-binary=:all:",
    "--no-cache-dir",
    "--require-hashes",
    "--constraint",
    "call-owned-constraints",
    "--requirement",
    "call-owned-root-requirements",
]
_PIP_ENVIRONMENT_AUTHORITY = {
    "HOME": "call-owned-home",
    "PIP_CONFIG_FILE": "platform-null",
    "TMPDIR": "call-owned-temp",
}
_REQUIRED_IMPORTS = {
    "av": "av",
    "faster-whisper": "faster_whisper",
    "huggingface-hub": "huggingface_hub",
}
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
        before.st_ctime_ns,
    )
    observed = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    path_observed = (
        path_after.st_dev,
        path_after.st_ino,
        path_after.st_mode,
        path_after.st_size,
        path_after.st_mtime_ns,
        path_after.st_ctime_ns,
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


def _wheel_manifest_sha256(entries: tuple[WheelEntry, ...]) -> str:
    return _canonical_digest(
        [
            {
                "filename": entry.filename,
                "distribution": entry.distribution,
                "version": entry.version,
                "build": entry.build,
                "python_tags": list(entry.python_tags),
                "abi_tags": list(entry.abi_tags),
                "platform_tags": list(entry.platform_tags),
                "bytes": entry.bytes,
                "sha256": entry.sha256,
            }
            for entry in entries
        ]
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


def _evaluate_marker_node(node: ast.AST, values: Mapping[str, str]) -> str | bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, bool)):
        return node.value
    if isinstance(node, ast.Name):
        try:
            return values[node.id]
        except KeyError as error:
            raise ReceiptError("lock_projection_invalid") from error
    if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
        items = [_evaluate_marker_node(item, values) for item in node.values]
        if any(not isinstance(item, bool) for item in items):
            raise ReceiptError("lock_projection_invalid")
        return all(items) if isinstance(node.op, ast.And) else any(items)
    if isinstance(node, ast.Compare):
        left = _evaluate_marker_node(node.left, values)
        comparisons: list[bool] = []
        for operator, comparator in zip(node.ops, node.comparators, strict=True):
            right = _evaluate_marker_node(comparator, values)
            if not isinstance(left, str) or not isinstance(right, str):
                raise ReceiptError("lock_projection_invalid")
            if isinstance(operator, ast.Eq):
                comparison = left == right
            elif isinstance(operator, ast.NotEq):
                comparison = left != right
            elif isinstance(operator, ast.Lt):
                comparison = left < right
            elif isinstance(operator, ast.LtE):
                comparison = left <= right
            elif isinstance(operator, ast.Gt):
                comparison = left > right
            elif isinstance(operator, ast.GtE):
                comparison = left >= right
            elif isinstance(operator, ast.In):
                comparison = left in right
            elif isinstance(operator, ast.NotIn):
                comparison = left not in right
            else:
                raise ReceiptError("lock_projection_invalid")
            comparisons.append(comparison)
            left = right
        return all(comparisons)
    raise ReceiptError("lock_projection_invalid")


def _marker_applies(marker: object, cells: tuple[Cell, ...]) -> bool:
    if marker is None:
        return True
    if not isinstance(marker, str) or not marker or len(marker) > 4096:
        raise ReceiptError("lock_projection_invalid")
    try:
        expression = ast.parse(marker, mode="eval")
    except (SyntaxError, ValueError) as error:
        raise ReceiptError("lock_projection_invalid") from error
    for cell in cells:
        values = {
            "python_version": cell.version,
            "python_full_version": cell.version + ".0",
            "implementation_name": "cpython",
            "platform_python_implementation": "CPython",
            "platform_machine": "arm64",
            "sys_platform": "darwin",
        }
        applies = _evaluate_marker_node(expression.body, values)
        if not isinstance(applies, bool):
            raise ReceiptError("lock_projection_invalid")
        if applies:
            return True
    return False


def derive_transcription_projection(lock_path: Path, cells: tuple[Cell, ...]) -> LockProjection:
    return _derive_transcription_projection(_read_regular(lock_path), cells)


def _derive_transcription_projection(lock_value: bytes, cells: tuple[Cell, ...]) -> LockProjection:
    try:
        lock = tomllib.loads(lock_value.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise ReceiptError("lock_projection_invalid") from error
    packages_value = cast(dict[str, object], lock).get("package")
    if not isinstance(packages_value, list) or not packages_value:
        raise ReceiptError("lock_projection_invalid")
    packages: list[dict[str, object]] = []
    by_name: dict[str, dict[str, object]] = {}
    for package_value in cast(list[object], packages_value):
        if not isinstance(package_value, dict):
            raise ReceiptError("lock_projection_invalid")
        package = cast(dict[str, object], package_value)
        name = package.get("name")
        if not isinstance(name, str) or not name or _normal_name(name) != name or name in by_name:
            raise ReceiptError("lock_projection_invalid")
        packages.append(package)
        by_name[name] = package
    project = by_name.get("multimodal-knowledge-engine")
    if project is None:
        raise ReceiptError("lock_projection_invalid")
    optional_value = project.get("optional-dependencies")
    if not isinstance(optional_value, dict):
        raise ReceiptError("lock_projection_invalid")
    roots_value = cast(dict[str, object], optional_value).get("transcription")
    if not isinstance(roots_value, list) or not roots_value:
        raise ReceiptError("lock_projection_invalid")
    roots: list[dict[str, object]] = []
    for root_value in cast(list[object], roots_value):
        if not isinstance(root_value, dict):
            raise ReceiptError("lock_projection_invalid")
        root = cast(dict[str, object], root_value)
        name = root.get("name")
        if not isinstance(name, str) or name not in by_name:
            raise ReceiptError("lock_projection_invalid")
        roots.append(root)
    selected_by_cell: dict[str, set[str]] = {}
    root_names_by_cell: dict[str, set[str]] = {}
    for cell in cells:
        root_names = {
            cast(str, item.get("name"))
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
            if package is None:
                raise ReceiptError("lock_projection_invalid")
            source = package.get("source")
            if not isinstance(source, dict) or not isinstance(
                cast(dict[str, object], source).get("registry"), str
            ):
                raise ReceiptError("lock_projection_invalid")
            selected.add(name)
            dependencies_value = package.get("dependencies", [])
            if not isinstance(dependencies_value, list):
                raise ReceiptError("lock_projection_invalid")
            for dependency_value in cast(list[object], dependencies_value):
                if not isinstance(dependency_value, dict):
                    raise ReceiptError("lock_projection_invalid")
                dependency = cast(dict[str, object], dependency_value)
                dependency_name = dependency.get("name")
                if not isinstance(dependency_name, str) or dependency_name not in by_name:
                    raise ReceiptError("lock_projection_invalid")
                if _marker_applies(dependency.get("marker"), (cell,)):
                    pending.append(dependency_name)
        selected_by_cell[cell.version] = selected
    selected_union: set[str] = set()
    for selected in selected_by_cell.values():
        selected_union.update(selected)

    requirements: list[Requirement] = []
    locked_wheels: list[WheelEntry] = []
    locked_filenames: set[str] = set()
    lines_by_name: dict[str, str] = {}
    requirement_by_name: dict[str, Requirement] = {}
    for name in sorted(selected_union):
        package = by_name[name]
        version = package.get("version")
        wheels_value = package.get("wheels")
        if (
            not isinstance(version, str)
            or _VERSION.fullmatch(version) is None
            or not isinstance(wheels_value, list)
            or not wheels_value
        ):
            raise ReceiptError("lock_projection_invalid")
        wheels = cast(list[object], wheels_value)
        hashes: set[str] = set()
        for wheel_value in wheels:
            if not isinstance(wheel_value, dict):
                raise ReceiptError("lock_projection_invalid")
            wheel = cast(dict[str, object], wheel_value)
            url = wheel.get("url")
            digest_value = wheel.get("hash")
            size = wheel.get("size")
            if (
                not isinstance(url, str)
                or not url
                or not isinstance(digest_value, str)
                or not digest_value.startswith("sha256:")
                or not isinstance(size, int)
                or isinstance(size, bool)
                or size <= 0
            ):
                raise ReceiptError("lock_projection_invalid")
            digest = digest_value.removeprefix("sha256:")
            if _DIGEST.fullmatch(digest) is None:
                raise ReceiptError("lock_projection_invalid")
            parsed_url = urlsplit(url)
            filename = parsed_url.path.rsplit("/", 1)[-1]
            if (
                parsed_url.scheme != "https"
                or not parsed_url.netloc
                or parsed_url.query
                or parsed_url.fragment
                or not filename
                or "%" in filename
                or filename in locked_filenames
            ):
                raise ReceiptError("lock_projection_invalid")
            try:
                parsed_wheel = _parse_wheel_filename(filename)
            except ReceiptError as error:
                raise ReceiptError("lock_projection_invalid") from error
            if parsed_wheel[0] != _normal_name(name) or parsed_wheel[1] != version:
                raise ReceiptError("lock_projection_invalid")
            locked_filenames.add(filename)
            locked_wheels.append(WheelEntry(filename, *parsed_wheel, size, digest))
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
        tuple(sorted(locked_wheels, key=lambda item: item.filename)),
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
    try:
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
    except (OSError, TypeError, ValueError) as error:
        raise ReceiptError("bounded_supervision_failed") from error
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


def _file_authority(path: Path) -> tuple[FileAuthority, bytes]:
    try:
        before = path.lstat()
        value = _read_regular(path)
        after = path.lstat()
    except ReceiptError:
        raise
    except OSError as error:
        raise ReceiptError("pip_input_identity_drift") from error
    identity = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    if identity != (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        raise ReceiptError("pip_input_identity_drift")
    return FileAuthority(identity, len(value), hashlib.sha256(value).hexdigest()), value


def _directory_authority(path: Path, *, code: str) -> tuple[int, ...]:
    try:
        observed = path.lstat()
    except OSError as error:
        raise ReceiptError(code) from error
    if not stat.S_ISDIR(observed.st_mode) or path.is_symlink():
        raise ReceiptError(code)
    return (
        observed.st_dev,
        observed.st_ino,
        observed.st_mode,
        observed.st_size,
        observed.st_mtime_ns,
        observed.st_ctime_ns,
    )


def _owned_directory_identity(path: Path) -> tuple[int, ...]:
    try:
        observed = path.lstat()
    except OSError as error:
        raise ReceiptError("pip_cleanup_failed") from error
    if not stat.S_ISDIR(observed.st_mode) or path.is_symlink():
        raise ReceiptError("pip_cleanup_failed")
    return (observed.st_dev, observed.st_ino, observed.st_mode)


def _write_exclusive_file(path: Path, value: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
        try:
            offset = 0
            while offset < len(value):
                offset += os.write(descriptor, value[offset:])
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as error:
        raise ReceiptError("pip_staging_invalid") from error


def _snapshot_pip_inputs(
    *,
    constraints: Path,
    root_requirements: Path,
    wheelhouse: Path,
    expected_manifest: tuple[WheelEntry, ...],
    constraints_sha256: str,
    root_requirements_sha256: str,
    stage: Path | None = None,
) -> PipInputAuthority:
    try:
        constraints_authority, constraints_value = _file_authority(constraints)
        requirements_authority, requirements_value = _file_authority(root_requirements)
    except ReceiptError as error:
        raise ReceiptError("pip_input_identity_drift") from error
    if (
        _DIGEST.fullmatch(constraints_sha256) is None
        or constraints_authority.sha256 != constraints_sha256
        or _DIGEST.fullmatch(root_requirements_sha256) is None
        or requirements_authority.sha256 != root_requirements_sha256
    ):
        raise ReceiptError("pip_input_identity_drift")
    try:
        wheelhouse_before = _directory_authority(wheelhouse, code="wheel_input_invalid")
        with os.scandir(wheelhouse) as entries:
            names = sorted(entry.name for entry in entries)
    except ReceiptError:
        raise
    except OSError as error:
        raise ReceiptError("wheel_input_invalid") from error
    expected_names = [entry.filename for entry in expected_manifest]
    if names != expected_names:
        raise ReceiptError("wheel_identity_drift")
    wheel_authorities: list[tuple[str, FileAuthority]] = []
    observed_manifest: list[WheelEntry] = []
    if stage is not None:
        _write_exclusive_file(stage / "constraints.txt", constraints_value)
        _write_exclusive_file(stage / "root-requirements.txt", requirements_value)
        staged_wheelhouse = stage / "wheelhouse"
        try:
            staged_wheelhouse.mkdir(mode=0o700)
        except OSError as error:
            raise ReceiptError("pip_staging_invalid") from error
    else:
        staged_wheelhouse = None
    for name in names:
        path = wheelhouse / name
        try:
            authority, value = _file_authority(path)
            parsed = _parse_wheel_filename(name)
        except ReceiptError as error:
            raise ReceiptError("wheel_identity_drift") from error
        wheel_authorities.append((name, authority))
        observed_manifest.append(WheelEntry(name, *parsed, authority.bytes, authority.sha256))
        if staged_wheelhouse is not None:
            _write_exclusive_file(staged_wheelhouse / name, value)
    wheelhouse_after = _directory_authority(wheelhouse, code="wheel_identity_drift")
    if wheelhouse_before != wheelhouse_after or tuple(observed_manifest) != expected_manifest:
        raise ReceiptError("wheel_identity_drift")
    return PipInputAuthority(
        constraints_authority,
        requirements_authority,
        wheelhouse_before,
        tuple(wheel_authorities),
    )


def _validate_pip_inputs(
    expected: PipInputAuthority,
    *,
    constraints: Path,
    root_requirements: Path,
    wheelhouse: Path,
    expected_manifest: tuple[WheelEntry, ...],
    constraints_sha256: str,
    root_requirements_sha256: str,
    code: str,
) -> None:
    try:
        observed = _snapshot_pip_inputs(
            constraints=constraints,
            root_requirements=root_requirements,
            wheelhouse=wheelhouse,
            expected_manifest=expected_manifest,
            constraints_sha256=constraints_sha256,
            root_requirements_sha256=root_requirements_sha256,
        )
    except ReceiptError as error:
        raise ReceiptError(code) from error
    if observed != expected:
        raise ReceiptError(code)


def _cleanup_owned_tree(path: Path, identity: tuple[int, ...]) -> None:
    if _owned_directory_identity(path) != identity:
        raise ReceiptError("pip_cleanup_failed")
    try:
        shutil.rmtree(path)
        path.lstat()
    except FileNotFoundError:
        return
    except OSError as error:
        raise ReceiptError("pip_cleanup_failed") from error
    raise ReceiptError("pip_cleanup_failed")


def _venv_python(path: Path, runtime_root: Path) -> ExecutableSnapshot:
    try:
        observed = path.lstat()
        if (
            path.is_symlink()
            or not stat.S_ISREG(observed.st_mode)
            or observed.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH) == 0
        ):
            raise ReceiptError("pip_venv_invalid")
        resolved = path.resolve(strict=True)
        resolved.relative_to(runtime_root)
    except ReceiptError:
        raise
    except (OSError, ValueError) as error:
        raise ReceiptError("pip_venv_invalid") from error
    return _snapshot_executable(path)


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
    cell: Cell,
    preflight_interpreter: Mapping[str, object],
    preflight_file_identity: tuple[int, ...],
) -> dict[str, object]:
    validated_runtime = _validated_directory(runtime_root, code="runtime_path_invalid")
    generation_interpreter, generation_file_identity, generation_executable = (
        _probe_target_interpreter(python, cell)
    )
    if (
        generation_interpreter != dict(preflight_interpreter)
        or generation_file_identity != preflight_file_identity
    ):
        raise ReceiptError("pip_interpreter_identity_drift")
    try:
        call_root = Path(tempfile.mkdtemp(prefix="direct-audio-pip-", dir=validated_runtime))
        call_root.chmod(0o700)
        call_identity = _owned_directory_identity(call_root)
    except (OSError, ReceiptError) as error:
        raise ReceiptError("runtime_path_invalid") from error
    failure: ReceiptError | None = None
    public_result: dict[str, object] | None = None
    try:
        home = call_root / "home"
        temp = call_root / "tmp"
        cwd = call_root / "cwd"
        stage = call_root / "stage"
        for directory in (home, temp, cwd, stage):
            directory.mkdir(mode=0o700)
        source_authority = _snapshot_pip_inputs(
            constraints=constraints,
            root_requirements=root_requirements,
            wheelhouse=wheelhouse,
            expected_manifest=expected_manifest,
            constraints_sha256=constraints_sha256,
            root_requirements_sha256=root_requirements_sha256,
            stage=stage,
        )
        _validate_pip_inputs(
            source_authority,
            constraints=constraints,
            root_requirements=root_requirements,
            wheelhouse=wheelhouse,
            expected_manifest=expected_manifest,
            constraints_sha256=constraints_sha256,
            root_requirements_sha256=root_requirements_sha256,
            code="pip_input_identity_drift",
        )
        staged_constraints = stage / "constraints.txt"
        staged_requirements = stage / "root-requirements.txt"
        staged_wheelhouse = stage / "wheelhouse"
        staging_authority = _snapshot_pip_inputs(
            constraints=staged_constraints,
            root_requirements=staged_requirements,
            wheelhouse=staged_wheelhouse,
            expected_manifest=expected_manifest,
            constraints_sha256=constraints_sha256,
            root_requirements_sha256=root_requirements_sha256,
        )
        venv = call_root / "venv"
        creation = _run_bounded(
            [
                str(generation_executable),
                "-I",
                "-B",
                "-m",
                "venv",
                "--copies",
                str(venv),
            ],
            env={"HOME": str(home), "TMPDIR": str(temp)},
            cwd=cwd,
            profile=_PIP_PROFILE,
        )
        if creation.returncode != 0 or creation.stderr:
            raise ReceiptError("pip_venv_creation_failed")
        venv_executable = venv / "bin" / f"python{cell.version}"
        venv_before = _venv_python(venv_executable, validated_runtime)
        venv_interpreter, _, pip_executable = _probe_target_interpreter(venv_executable, cell)
        if (
            venv_interpreter != dict(preflight_interpreter)
            or pip_executable != venv_before.resolved
        ):
            raise ReceiptError("pip_venv_identity_drift")
        environment = {
            "HOME": str(home),
            "TMPDIR": str(temp),
            "PIP_CONFIG_FILE": os.devnull,
        }
        argv = [
            str(venv_executable),
            "-I",
            "-m",
            "pip",
            "--isolated",
            "--disable-pip-version-check",
            "--no-input",
            "install",
            "--no-index",
            "--find-links",
            staged_wheelhouse.as_uri(),
            "--only-binary=:all:",
            "--no-cache-dir",
            "--require-hashes",
            "--constraint",
            str(staged_constraints),
            "--requirement",
            str(staged_requirements),
        ]
        install = _run_bounded(argv, env=environment, cwd=cwd, profile=_PIP_PROFILE)
        if install.returncode != 0:
            raise ReceiptError("pip_install_failed")
        _validate_pip_inputs(
            source_authority,
            constraints=constraints,
            root_requirements=root_requirements,
            wheelhouse=wheelhouse,
            expected_manifest=expected_manifest,
            constraints_sha256=constraints_sha256,
            root_requirements_sha256=root_requirements_sha256,
            code="pip_input_identity_drift",
        )
        _validate_pip_inputs(
            staging_authority,
            constraints=staged_constraints,
            root_requirements=staged_requirements,
            wheelhouse=staged_wheelhouse,
            expected_manifest=expected_manifest,
            constraints_sha256=constraints_sha256,
            root_requirements_sha256=root_requirements_sha256,
            code="pip_staging_identity_drift",
        )
        if _venv_python(venv_executable, validated_runtime) != venv_before:
            raise ReceiptError("pip_venv_identity_drift")
        pip_check = _run_bounded(
            [
                str(venv_executable),
                "-I",
                "-m",
                "pip",
                "--isolated",
                "--disable-pip-version-check",
                "--no-input",
                "check",
            ],
            env=environment,
            cwd=cwd,
            profile=_PIP_PROFILE,
        )
        if pip_check.returncode != 0:
            raise ReceiptError("pip_check_failed")
        _validate_pip_inputs(
            source_authority,
            constraints=constraints,
            root_requirements=root_requirements,
            wheelhouse=wheelhouse,
            expected_manifest=expected_manifest,
            constraints_sha256=constraints_sha256,
            root_requirements_sha256=root_requirements_sha256,
            code="pip_input_identity_drift",
        )
        _validate_pip_inputs(
            staging_authority,
            constraints=staged_constraints,
            root_requirements=staged_requirements,
            wheelhouse=staged_wheelhouse,
            expected_manifest=expected_manifest,
            constraints_sha256=constraints_sha256,
            root_requirements_sha256=root_requirements_sha256,
            code="pip_staging_identity_drift",
        )
        if _venv_python(venv_executable, validated_runtime) != venv_before:
            raise ReceiptError("pip_venv_identity_drift")
        final_interpreter = _snapshot_executable(python)
        if (
            final_interpreter.identity != preflight_file_identity
            or final_interpreter.sha256 != preflight_interpreter.get("executable_sha256")
        ):
            raise ReceiptError("pip_interpreter_identity_drift")
        manifest_digest = _wheel_manifest_sha256(expected_manifest)
        public_result = {
            "cell": cell.version,
            "pip_install": "passed",
            "pip_check": "passed",
            "argv": list(_PIP_ARGV_AUTHORITY),
            "environment": dict(_PIP_ENVIRONMENT_AUTHORITY),
            "staging": {
                "constraints_sha256": constraints_sha256,
                "root_requirements_sha256": root_requirements_sha256,
                "wheelhouse_manifest_sha256": manifest_digest,
            },
        }
    except ReceiptError as error:
        failure = error
    except Exception as error:
        failure = ReceiptError("pip_execution_failed")
        failure.__cause__ = error
    try:
        _cleanup_owned_tree(call_root, call_identity)
    except ReceiptError as cleanup_error:
        raise cleanup_error from failure
    if failure is not None:
        raise failure
    if public_result is None:
        raise ReceiptError("pip_execution_failed")
    public_result["cleanup"] = "passed"
    return public_result


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
    locked_by_filename = {entry.filename: entry for entry in projection.locked_wheels}
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
            if (
                candidate.sha256
                not in hash_authority.get((requirement.name, requirement.version), frozenset())
                or locked_by_filename.get(candidate.filename) != candidate
            ):
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


def _wheel_resolution_rows(
    manifest: tuple[WheelEntry, ...], projection: LockProjection
) -> list[dict[str, object]]:
    try:
        resolved = resolve_projected_wheels(manifest, projection)
    except ReceiptError:
        return []
    rows: list[dict[str, object]] = []
    for cell in projection.cells:
        for distribution, entry in sorted(resolved[cell.version].items()):
            rows.append(
                {
                    "cell": cell.version,
                    "distribution": distribution,
                    "version": entry.version,
                    "filename": entry.filename,
                    "sha256": entry.sha256,
                }
            )
    return rows


def build_fixture_manifest(fixture_root: Path) -> tuple[dict[str, object], ...]:
    try:
        root_identity = _directory_authority(fixture_root, code="fixture_inventory_invalid")
        names: list[str] = []
        with os.scandir(fixture_root) as entries:
            for entry in entries:
                if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                    raise ReceiptError("fixture_inventory_invalid")
                names.append(entry.name)
    except ReceiptError:
        raise
    except OSError as error:
        raise ReceiptError("fixture_inventory_invalid") from error
    if set(names) != set(_FIXTURE_FILES) or len(names) != len(_FIXTURE_FILES):
        raise ReceiptError("fixture_inventory_invalid")
    result: list[dict[str, object]] = []
    for name in _FIXTURE_FILES:
        try:
            value = _read_regular(fixture_root / name)
        except ReceiptError as error:
            raise ReceiptError("fixture_identity_invalid") from error
        observed = {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
        expected = _FIXTURE_AUTHORITY[name]
        if observed != {"bytes": expected["bytes"], "sha256": expected["sha256"]}:
            raise ReceiptError("fixture_identity_invalid")
        result.append(
            {
                "filename": name,
                **observed,
                "artifact_scope": "repository_distributed",
            }
        )
    try:
        final_root_identity = _directory_authority(fixture_root, code="fixture_identity_invalid")
        with os.scandir(fixture_root) as entries:
            final_names = sorted(entry.name for entry in entries)
    except ReceiptError:
        raise
    except OSError as error:
        raise ReceiptError("fixture_identity_invalid") from error
    if final_root_identity != root_identity or final_names != sorted(_FIXTURE_FILES):
        raise ReceiptError("fixture_identity_invalid")
    return tuple(result)


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
            identity, observed_file_identity, _ = _probe_target_interpreter(python, cells[index])
        except ReceiptError as error:
            issues.append(_issue(str(error), label))
        else:
            if observed_file_identity != snapshot.identity:
                issues.append(_issue("interpreter_identity_drift", label))
            else:
                interpreters.append(identity)
    lock_sha: str | None = None
    root_requirements_sha: str | None = None
    projection_hash_authority: dict[tuple[str, str], frozenset[str]] = {}
    try:
        if lock_path is None:
            raise ReceiptError("lock_missing")
        lock_value = _read_regular(lock_path)
        projection = _derive_transcription_projection(lock_value, cells)
        lock_sha = hashlib.sha256(lock_value).hexdigest()
        root_requirements_sha = hashlib.sha256(projection.root_requirements).hexdigest()
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
    wheel_resolution = (
        _wheel_resolution_rows(manifest, projection) if projection is not None else []
    )
    try:
        fixture_receipts = list(build_fixture_manifest(fixture_root))
    except ReceiptError as error:
        fixture_receipts = []
        issues.append(_issue(str(error), "audio-fixtures"))
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
        "root_requirements_sha256": root_requirements_sha,
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
        "wheel_resolution": wheel_resolution,
        "fixtures": fixture_receipts,
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


def _closed_version(value: object) -> bool:
    return isinstance(value, str) and _VERSION.fullmatch(value) is not None


def _spdx_license(value: object) -> bool:
    return isinstance(value, str) and _SPDX_LICENSE.fullmatch(value) is not None


def _relative_extension_filename(value: object) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or value.startswith("/")
        or "\\" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        return False
    parts = value.split("/")
    return all(
        part not in {"", ".", ".."} and _EXTENSION_PART.fullmatch(part) is not None
        for part in parts
    )


def _ffmpeg_configuration(value: object) -> bool:
    if not isinstance(value, str) or not value or value != value.strip():
        return False
    flags = value.split(" ")
    return flags == sorted(set(flags)) and all(
        flag and _FFMPEG_FLAG.fullmatch(flag) is not None for flag in flags
    )


def _ffmpeg_license(value: object) -> bool:
    return isinstance(value, str) and _FFMPEG_LICENSE.fullmatch(value) is not None


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


def _interpreter_authority(
    row: dict[str, object],
) -> tuple[Cell, dict[str, object]] | None:
    label = row["label"]
    if label not in {"python-3.12", "python-3.13"}:
        return None
    cell_version = cast(str, label).removeprefix("python-")
    compact = cell_version.replace(".", "")
    python_version = row["python_version"]
    sysconfig_platform = row["sysconfig_platform"]
    platform_match = (
        re.fullmatch(r"macosx-(\d+)\.(\d+)-(?:arm64|universal2)", sysconfig_platform)
        if isinstance(sysconfig_platform, str)
        else None
    )
    if (
        row["implementation"] != "cpython"
        or not isinstance(python_version, str)
        or re.fullmatch(rf"{re.escape(cell_version)}\.\d+", python_version) is None
        or row["system"] != "Darwin"
        or row["machine"] != "arm64"
        or platform_match is None
        or row["soabi"] != f"cpython-{compact}-darwin"
        or row["ext_suffix"] != f".cpython-{compact}-darwin.so"
        or row["cache_tag"] != f"cpython-{compact}"
        or row["abiflags"] != ""
        or row["pointer_bits"] != 64
        or row["byteorder"] != "little"
        or not _digest_value(row["executable_sha256"])
    ):
        return None
    cell = Cell(
        cast(str, label),
        cell_version,
        f"cp{compact}",
        f"macosx_{platform_match[1]}_{platform_match[2]}_arm64",
    )
    return cell, row


def _wheel_evidence_entry(row: dict[str, object]) -> WheelEntry | None:
    filename = row["filename"]
    if not isinstance(filename, str):
        return None
    try:
        parsed = _parse_wheel_filename(filename)
    except ReceiptError:
        return None
    python_tags = _string_items(row["python_tags"])
    abi_tags = _string_items(row["abi_tags"])
    platform_tags = _string_items(row["platform_tags"])
    size = row["bytes"]
    if (
        row["distribution"] != parsed[0]
        or row["version"] != parsed[1]
        or row["build"] != parsed[2]
        or python_tags != list(parsed[3])
        or abi_tags != list(parsed[4])
        or platform_tags != list(parsed[5])
        or not isinstance(size, int)
        or isinstance(size, bool)
        or size <= 0
        or not _digest_value(row["sha256"])
        or row["artifact_scope"] != "local_runtime_only"
    ):
        return None
    return WheelEntry(filename, *parsed, size, cast(str, row["sha256"]))


def _passed_preflight_authority(
    value: Mapping[str, object] | None,
) -> dict[str, object] | None:
    keys = {
        "schema",
        "status",
        "gate",
        "distribution",
        "controller",
        "script",
        "interpreters",
        "lock_sha256",
        "constraints_sha256",
        "root_requirements_sha256",
        "wheelhouse",
        "wheel_resolution",
        "fixtures",
        "issues",
        "observed_digest",
    }
    payload = _exact_mapping(value, keys)
    if payload is None:
        return None
    distribution = _exact_mapping(
        payload["distribution"],
        {"external_binary_redistribution", "redistribution_authority"},
    )
    controller = _exact_mapping(
        payload["controller"],
        {
            "implementation",
            "python_version",
            "platform",
            "executable_type",
            "executable_mode",
            "executable_sha256",
        },
    )
    script = _exact_mapping(payload["script"], {"sha256"})
    interpreters = _inventory_rows(
        payload["interpreters"],
        {
            "label",
            "implementation",
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
            "executable_sha256",
        },
    )
    wheelhouse = _inventory_rows(
        payload["wheelhouse"],
        {
            "filename",
            "bytes",
            "sha256",
            "distribution",
            "version",
            "build",
            "python_tags",
            "abi_tags",
            "platform_tags",
            "artifact_scope",
        },
    )
    resolution = _inventory_rows(
        payload["wheel_resolution"],
        {"cell", "distribution", "version", "filename", "sha256"},
    )
    fixtures = _inventory_rows(
        payload["fixtures"], {"filename", "bytes", "sha256", "artifact_scope"}
    )
    if (
        payload["schema"] != "mke.direct_audio_dependency_input_check.v1"
        or payload["status"] != "passed"
        or payload["gate"] != "inputs_valid"
        or payload["issues"] != []
        or distribution
        != {
            "external_binary_redistribution": "not_performed",
            "redistribution_authority": "not_claimed",
        }
        or controller is None
        or controller["implementation"] != "cpython"
        or not _resolved_text(controller["python_version"])
        or not _resolved_text(controller["platform"])
        or controller["executable_type"] != "regular"
        or not isinstance(controller["executable_mode"], str)
        or re.fullmatch(r"0[0-7]{3}", controller["executable_mode"]) is None
        or not _digest_value(controller["executable_sha256"])
        or script is None
        or not _digest_value(script["sha256"])
        or interpreters is None
        or len(interpreters) != 2
        or {item["label"] for item in interpreters} != {"python-3.12", "python-3.13"}
        or wheelhouse is None
        or resolution is None
        or fixtures is None
        or not _digest_value(payload["lock_sha256"])
        or not _digest_value(payload["constraints_sha256"])
        or not _digest_value(payload["root_requirements_sha256"])
        or not _digest_value(payload["observed_digest"])
    ):
        return None
    interpreter_authorities = [_interpreter_authority(item) for item in interpreters]
    if any(item is None for item in interpreter_authorities):
        return None
    interpreter_map = {
        authority[0].version: authority
        for authority in cast(list[tuple[Cell, dict[str, object]]], interpreter_authorities)
    }
    if (
        set(interpreter_map) != {"3.12", "3.13"}
        or len({item[1]["executable_sha256"] for item in interpreter_map.values()}) != 2
    ):
        return None
    try:
        live_script_sha256 = hashlib.sha256(_read_regular(Path(__file__).resolve())).hexdigest()
    except ReceiptError:
        return None
    if script["sha256"] != live_script_sha256:
        return None
    wheel_entries = [_wheel_evidence_entry(item) for item in wheelhouse]
    if any(item is None for item in wheel_entries):
        return None
    if len({item["filename"] for item in wheelhouse}) != len(wheelhouse):
        return None
    entries_by_filename = {entry.filename: entry for entry in cast(list[WheelEntry], wheel_entries)}
    resolution_keys: set[tuple[object, object]] = set()
    used_filenames: set[str] = set()
    for row in resolution:
        cell = row["cell"]
        filename = row["filename"]
        if not isinstance(cell, str) or not isinstance(filename, str):
            return None
        interpreter = interpreter_map.get(cell)
        entry = entries_by_filename.get(filename)
        key = (cell, row["distribution"])
        if (
            interpreter is None
            or entry is None
            or key in resolution_keys
            or row["distribution"] != entry.distribution
            or row["version"] != entry.version
            or row["sha256"] != entry.sha256
            or not _wheel_compatible(entry, interpreter[0])
        ):
            return None
        resolution_keys.add(key)
        used_filenames.add(filename)
    if {row["cell"] for row in resolution} != {"3.12", "3.13"} or used_filenames != set(
        entries_by_filename
    ):
        return None
    if (
        {item["filename"] for item in fixtures} != set(_FIXTURE_FILES)
        or len(fixtures) != len(_FIXTURE_FILES)
        or any(
            not isinstance(item["bytes"], int)
            or isinstance(item["bytes"], bool)
            or item["bytes"] <= 0
            or not _digest_value(item["sha256"])
            or item["artifact_scope"] != "repository_distributed"
            or item["bytes"] != _FIXTURE_AUTHORITY[cast(str, item["filename"])]["bytes"]
            or item["sha256"] != _FIXTURE_AUTHORITY[cast(str, item["filename"])]["sha256"]
            for item in fixtures
        )
    ):
        return None
    observed = {
        key: item
        for key, item in payload.items()
        if key not in {"issues", "status", "gate", "observed_digest"}
    }
    try:
        expected_digest = _canonical_digest(observed)
    except (TypeError, ValueError, UnicodeEncodeError):
        return None
    if payload["observed_digest"] != expected_digest:
        return None
    return {
        "observed_digest": expected_digest,
        "script_sha256": live_script_sha256,
        "constraints_sha256": payload["constraints_sha256"],
        "root_requirements_sha256": payload["root_requirements_sha256"],
        "interpreters": {f"python-{version}": row for version, (_, row) in interpreter_map.items()},
        "wheelhouse": sorted(wheelhouse, key=lambda item: cast(str, item["filename"])),
        "wheel_resolution": sorted(
            resolution,
            key=lambda item: (
                cast(str, item["cell"]),
                cast(str, item["distribution"]),
            ),
        ),
        "fixtures": sorted(fixtures, key=lambda item: cast(str, item["filename"])),
    }


def _valid_supervisor_authority(value: object) -> bool:
    supervisor = _exact_mapping(
        value,
        {
            "api",
            "api_version",
            "tool",
            "metric",
            "leader_scope",
            "leader_identity_binding",
            "descendants_scope",
            "budget_mode",
            "baseline_bytes",
            "budget_bytes",
            "poll_seconds",
            "controlled_allocator",
            "observed_max_bytes",
            "overshoot_bytes",
            "budget_outcome",
            "transient_overshoot_possible",
            "cleanup",
            "hard_kernel_enforced",
            "bounds",
        },
    )
    if supervisor is None:
        return False
    cleanup = _exact_mapping(
        supervisor["cleanup"],
        {"sigterm_sent", "sigkill_sent", "waited", "process_group_absent"},
    )
    bounds = _exact_mapping(
        supervisor["bounds"],
        {
            "wall_seconds",
            "stdout_bytes",
            "stderr_bytes",
            "input_bytes",
            "temp_bytes",
            "output_bytes",
        },
    )
    integers = (
        supervisor["baseline_bytes"],
        supervisor["budget_bytes"],
        supervisor["observed_max_bytes"],
        supervisor["overshoot_bytes"],
    )
    if (
        cleanup is None
        or bounds is None
        or any(not isinstance(item, int) or isinstance(item, bool) for item in integers)
        or not isinstance(supervisor["poll_seconds"], (int, float))
        or isinstance(supervisor["poll_seconds"], bool)
    ):
        return False
    baseline, budget, observed, overshoot = cast(tuple[int, int, int, int], integers)
    numeric_bounds = tuple(bounds.values())
    return (
        supervisor["api"] == "proc_pid_rusage"
        and supervisor["api_version"] == "RUSAGE_INFO_V4"
        and supervisor["tool"] == "stdlib-ctypes"
        and supervisor["metric"] == "ri_phys_footprint"
        and supervisor["leader_scope"] == "process_group_leader"
        and supervisor["leader_identity_binding"] == "pid+ri_proc_start_abstime"
        and supervisor["descendants_scope"] == "ordinary_cooperative_descendants"
        and supervisor["budget_mode"] in {"absolute", "baseline_plus"}
        and baseline >= 0
        and budget > 0
        and observed > budget
        and overshoot == observed - budget
        and cast(float, supervisor["poll_seconds"]) > 0
        and _public_reference(supervisor["controlled_allocator"])
        and supervisor["controlled_allocator"] != "none"
        and supervisor["budget_outcome"] == "exceeded_terminated"
        and supervisor["transient_overshoot_possible"] is True
        and cleanup["sigterm_sent"] is True
        and isinstance(cleanup["sigkill_sent"], bool)
        and cleanup["waited"] is True
        and cleanup["process_group_absent"] is True
        and supervisor["hard_kernel_enforced"] is False
        and all(
            isinstance(item, (int, float)) and not isinstance(item, bool) and item >= 0
            for item in numeric_bounds
        )
        and cast(float, bounds["wall_seconds"]) > 0
        and cast(int, bounds["stdout_bytes"]) > 0
        and cast(int, bounds["stderr_bytes"]) > 0
        and bounds["input_bytes"] == 0
        and cast(int, bounds["output_bytes"]) > 0
    )


def _valid_pip_authority(
    value: object,
    *,
    constraints_sha256: object,
    root_requirements_sha256: object,
    wheelhouse_manifest_sha256: str,
) -> bool:
    pip = _exact_mapping(
        value,
        {"argv", "environment", "pip_install", "pip_check", "cleanup", "staging"},
    )
    if pip is None:
        return False
    staging = _exact_mapping(
        pip["staging"],
        {
            "constraints_sha256",
            "root_requirements_sha256",
            "wheelhouse_manifest_sha256",
        },
    )
    return (
        pip["argv"] == _PIP_ARGV_AUTHORITY
        and pip["environment"] == _PIP_ENVIRONMENT_AUTHORITY
        and pip["pip_install"] == "passed"
        and pip["pip_check"] == "passed"
        and pip["cleanup"] == "passed"
        and staging is not None
        and staging["constraints_sha256"] == constraints_sha256
        and staging["root_requirements_sha256"] == root_requirements_sha256
        and staging["wheelhouse_manifest_sha256"] == wheelhouse_manifest_sha256
    )


def validate_generation_evidence(
    evidence: Mapping[str, object],
    *,
    preflight: Mapping[str, object] | None = None,
    generation_preflight: Mapping[str, object] | None = None,
) -> dict[str, str]:
    """Validate local-use evidence without claiming binary redistribution authority."""
    required = {
        "receipt_sha256",
        "script_sha256",
        "preflight_observed_digest",
        "generation_preflight_observed_digest",
        "external_binary_redistribution",
        "redistribution_authority",
        "wheel_inventory",
        "installed_distributions",
        "cells",
        "darwin_supervisor",
        "pyav",
        "ffmpeg_runtime",
        "direct_components",
        "fixture_authority_document",
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
    preflight_authority = _passed_preflight_authority(preflight)
    generation_preflight_authority = _passed_preflight_authority(generation_preflight)
    valid = (
        valid
        and preflight_authority is not None
        and generation_preflight_authority is not None
        and preflight_authority == generation_preflight_authority
    )
    if preflight_authority is not None:
        valid = (
            valid
            and evidence["preflight_observed_digest"] == preflight_authority["observed_digest"]
            and evidence["generation_preflight_observed_digest"]
            == preflight_authority["observed_digest"]
            and evidence["script_sha256"] == preflight_authority["script_sha256"]
        )
    try:
        receipt_digest = _canonical_digest(
            {key: value for key, value in evidence.items() if key != "receipt_sha256"}
        )
    except (TypeError, ValueError, UnicodeEncodeError):
        receipt_digest = None
    valid = valid and evidence["receipt_sha256"] == receipt_digest
    wheels = _inventory_rows(
        evidence["wheel_inventory"],
        {
            "filename",
            "distribution",
            "version",
            "build",
            "python_tags",
            "abi_tags",
            "platform_tags",
            "bytes",
            "sha256",
            "artifact_scope",
        },
    )
    installed = _inventory_rows(
        evidence["installed_distributions"],
        {
            "distribution",
            "version",
            "source_wheel_filename",
            "source_wheel_sha256",
            "cell",
            "artifact_scope",
        },
    )
    wheel_authority: dict[str, WheelEntry] = {}
    wheelhouse_manifest_sha256: str | None = None
    if wheels is None or installed is None:
        valid = False
    else:
        wheel_entries = [_wheel_evidence_entry(item) for item in wheels]
        if any(item is None for item in wheel_entries):
            valid = False
        else:
            wheel_authority = {
                entry.filename: entry for entry in cast(list[WheelEntry], wheel_entries)
            }
            wheelhouse_manifest_sha256 = _wheel_manifest_sha256(
                tuple(sorted(wheel_authority.values(), key=lambda item: item.filename))
            )
        installed_authority = {
            (
                item["cell"],
                item["distribution"],
                item["version"],
                item["source_wheel_filename"],
                item["source_wheel_sha256"],
            )
            for item in installed
        }
        if preflight_authority is None:
            expected_installed: set[tuple[object, ...]] = set()
        else:
            expected_installed = {
                (
                    item["cell"],
                    item["distribution"],
                    item["version"],
                    item["filename"],
                    item["sha256"],
                )
                for item in cast(list[dict[str, object]], preflight_authority["wheel_resolution"])
            }
        valid = (
            valid
            and preflight_authority is not None
            and sorted(wheels, key=lambda item: cast(str, item["filename"]))
            == preflight_authority["wheelhouse"]
            and installed_authority == expected_installed
            and all(
                isinstance(item["source_wheel_filename"], str)
                and (entry := wheel_authority.get(item["source_wheel_filename"])) is not None
                and item["distribution"] == entry.distribution
                and item["version"] == entry.version
                and item["source_wheel_sha256"] == entry.sha256
                and item["cell"] in {"3.12", "3.13"}
                and item["artifact_scope"] == "local_runtime_only"
                for item in installed
            )
            and len(wheel_authority) == len(wheels)
            and len(installed_authority) == len(installed)
        )
    cell_rows = _inventory_rows(
        evidence["cells"],
        {"cell", "interpreter", "pip", "installed_distributions", "imports", "fixture_decodes"},
    )
    if (
        cell_rows is None
        or len(cell_rows) != 2
        or {item["cell"] for item in cell_rows} != {"3.12", "3.13"}
        or preflight_authority is None
        or installed is None
        or wheelhouse_manifest_sha256 is None
    ):
        valid = False
    else:
        preflight_interpreters = cast(
            dict[str, dict[str, object]], preflight_authority["interpreters"]
        )
        installed_keys = {
            "distribution",
            "version",
            "source_wheel_filename",
            "source_wheel_sha256",
            "cell",
            "artifact_scope",
        }
        for cell_row in cell_rows:
            cell = cell_row["cell"]
            if not isinstance(cell, str):
                valid = False
                continue
            interpreter = _exact_mapping(
                cell_row["interpreter"],
                {
                    "label",
                    "implementation",
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
                    "executable_sha256",
                },
            )
            cell_installed = _inventory_rows(cell_row["installed_distributions"], installed_keys)
            imports = _inventory_rows(
                cell_row["imports"],
                {"distribution", "module", "status", "version", "evidence_sha256"},
            )
            decodes = _inventory_rows(
                cell_row["fixture_decodes"],
                {"filename", "sha256", "decoder", "status", "stream_count"},
            )
            expected_cell_installed = [item for item in installed if item["cell"] == cell]
            if (
                interpreter is None
                or _interpreter_authority(interpreter) is None
                or interpreter != preflight_interpreters.get(f"python-{cell}")
                or not _valid_pip_authority(
                    cell_row["pip"],
                    constraints_sha256=preflight_authority["constraints_sha256"],
                    root_requirements_sha256=preflight_authority["root_requirements_sha256"],
                    wheelhouse_manifest_sha256=wheelhouse_manifest_sha256,
                )
                or cell_installed is None
                or sorted(
                    cell_installed,
                    key=lambda item: cast(str, item["distribution"]),
                )
                != sorted(
                    expected_cell_installed,
                    key=lambda item: cast(str, item["distribution"]),
                )
                or imports is None
                or decodes is None
            ):
                valid = False
                continue
            installed_by_distribution = {
                cast(str, item["distribution"]): item for item in cell_installed
            }
            if (
                {item["distribution"] for item in imports} != set(_REQUIRED_IMPORTS)
                or len(imports) != len(_REQUIRED_IMPORTS)
                or any(
                    item["module"] != _REQUIRED_IMPORTS.get(cast(str, item["distribution"]))
                    or item["status"] != "passed"
                    or (
                        installed_item := installed_by_distribution.get(
                            cast(str, item["distribution"])
                        )
                    )
                    is None
                    or item["version"] != installed_item["version"]
                    or item["evidence_sha256"] != installed_item["source_wheel_sha256"]
                    for item in imports
                )
            ):
                valid = False
            if (
                {item["filename"] for item in decodes} != set(_FIXTURES)
                or len(decodes) != len(_FIXTURES)
                or any(
                    item["sha256"] != _FIXTURE_AUTHORITY[cast(str, item["filename"])]["sha256"]
                    or item["decoder"] != "pyav"
                    or item["status"] != "passed"
                    or item["stream_count"] != 1
                    for item in decodes
                )
            ):
                valid = False
    valid = valid and _valid_supervisor_authority(evidence["darwin_supervisor"])
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
                not _relative_extension_filename(item["filename"])
                or not _digest_value(item["sha256"])
                for item in extensions
            )
            or any(not _public_reference(item) for item in [*linked_value, *bundled_value])
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
            "configuration_sha256",
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
            and _ffmpeg_license(ffmpeg_row["license"])
            and _ffmpeg_configuration(ffmpeg_row["configuration"])
            and _digest_value(ffmpeg_row["configuration_sha256"])
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
                _public_reference(item["name"])
                and _closed_version(item["version"])
                and _spdx_license(item["license"])
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
                and item["bytes"] == _FIXTURE_AUTHORITY[cast(str, item["filename"])]["bytes"]
                and item["sha256"] == _FIXTURE_AUTHORITY[cast(str, item["filename"])]["sha256"]
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
                and item["redistribution_evidence_sha256"] == _FIXTURE_AUTHORITY_DOCUMENT_SHA256
                and item["authority_document_sha256"] == _FIXTURE_AUTHORITY_DOCUMENT_SHA256
                for item in fixtures
            )
        )
    fixture_document = _exact_mapping(
        evidence["fixture_authority_document"],
        {"filename", "bytes", "sha256", "artifact_scope"},
    )
    valid = valid and fixture_document == {
        "filename": "README.md",
        "bytes": _FIXTURE_AUTHORITY["README.md"]["bytes"],
        "sha256": _FIXTURE_AUTHORITY["README.md"]["sha256"],
        "artifact_scope": "repository_distributed",
    }
    if wheels is None or fixtures is None or fixture_document is None:
        valid = False
    else:
        generation_fixture_projection = sorted(
            [
                fixture_document,
                *(
                    {
                        "filename": item["filename"],
                        "bytes": item["bytes"],
                        "sha256": item["sha256"],
                        "artifact_scope": item["artifact_scope"],
                    }
                    for item in fixtures
                ),
            ],
            key=lambda item: cast(str, item["filename"]),
        )
        valid = (
            valid
            and preflight_authority is not None
            and generation_fixture_projection == preflight_authority["fixtures"]
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
        not _public_reference(item["name"])
        or not _closed_version(item["version"])
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


class _ClosedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        del message
        raise ReceiptError("cli_arguments_invalid")


def _parser() -> argparse.ArgumentParser:
    parser = _ClosedArgumentParser(prog="direct_audio_dependency_receipt.py")
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
    try:
        args = _parser().parse_args(argv)
    except Exception:
        print(
            json.dumps(
                {"failure": "cli_arguments_invalid", "status": "failed"},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
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
    try:
        payload = check_inputs(
            pythons=tuple(args.python),
            wheelhouse=args.wheelhouse,
            lock_path=args.lock,
            constraints=args.constraints,
            fixture_root=args.fixture_root,
        )
    except ReceiptError as error:
        code = str(error)
        if _PUBLIC_REFERENCE.fullmatch(code) is None:
            code = "receipt_controller_failed"
        payload = {"failure": code, "status": "failed"}
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 2
    except Exception:
        payload = {"failure": "receipt_controller_failed", "status": "failed"}
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 2
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
