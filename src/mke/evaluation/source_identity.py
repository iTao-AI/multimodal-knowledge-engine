from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import cast

FILE_FIELDS = {"path", "bytes", "sha256"}
SOURCE_FIELDS = {"sha256", "files"}
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_MAX_SOURCE_IDENTITY_FILES = 1024


@dataclass(frozen=True)
class DirectFileRead:
    content: bytes
    identity: dict[str, object]
    physical_identity: tuple[int, int]


def read_no_follow_regular_file(
    repository_root: Path,
    relative_path: str,
    *,
    on_open: Callable[[], None] | None = None,
) -> DirectFileRead:
    validate_recorded_file_identity(
        {"path": relative_path, "bytes": 0, "sha256": "0" * 64},
        expected_path=relative_path,
    )
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory_flag = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory_flag is None:
        raise OSError("no-follow reads are unavailable")
    root_fd = os.open(repository_root, os.O_RDONLY | directory_flag | nofollow)
    descriptors = [root_fd]
    try:
        parts = PurePosixPath(relative_path).parts
        parent_fd = root_fd
        for part in parts[:-1]:
            parent_fd = os.open(
                part,
                os.O_RDONLY | directory_flag | nofollow,
                dir_fd=parent_fd,
            )
            descriptors.append(parent_fd)
        file_fd = os.open(parts[-1], os.O_RDONLY | nofollow, dir_fd=parent_fd)
        descriptors.append(file_fd)
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("source identity path is invalid")
        if on_open is not None:
            on_open()
        chunks: list[bytes] = []
        while chunk := os.read(file_fd, 1024 * 1024):
            chunks.append(chunk)
        after = os.fstat(file_fd)
        lexical = os.stat(parts[-1], dir_fd=parent_fd, follow_symlinks=False)
        stable_fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns")
        if any(getattr(before, field) != getattr(after, field) for field in stable_fields):
            raise ValueError("source identity changed during read")
        if (lexical.st_dev, lexical.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError("source identity changed during read")
        content = b"".join(chunks)
        if len(content) != before.st_size:
            raise ValueError("source identity changed during read")
        return DirectFileRead(
            content=content,
            identity={
                "path": relative_path,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            },
            physical_identity=(before.st_dev, before.st_ino),
        )
    except (FileNotFoundError, NotADirectoryError, OSError) as error:
        raise ValueError("source identity path is invalid") from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def build_file_identity(
    repository_root: Path, relative_path: str
) -> dict[str, object]:
    return read_no_follow_regular_file(repository_root, relative_path).identity


def build_source_identity(
    repository_root: Path, relative_paths: Sequence[str]
) -> dict[str, object]:
    paths = list(relative_paths)
    if (
        not paths
        or len(paths) > _MAX_SOURCE_IDENTITY_FILES
        or len(paths) != len(set(paths))
    ):
        suffix = " capacity" if len(paths) > _MAX_SOURCE_IDENTITY_FILES else ""
        raise ValueError(f"source identity{suffix} paths are invalid")
    reads = [
        read_no_follow_regular_file(repository_root, path) for path in sorted(paths)
    ]
    physical = [item.physical_identity for item in reads]
    if len(physical) != len(set(physical)):
        raise ValueError("source identity physical aliases are invalid")
    files = [item.identity for item in reads]
    if not files:
        raise ValueError("source identity paths are invalid")
    return {
        "sha256": _source_digest(files),
        "files": files,
    }


def validate_recorded_file_identity(
    value: object, *, expected_path: str | None = None
) -> None:
    if not isinstance(value, dict):
        raise ValueError("recorded file identity fields are invalid")
    record = cast(dict[str, object], value)
    if set(record) != FILE_FIELDS:
        raise ValueError("recorded file identity fields are invalid")
    path = record["path"]
    if not isinstance(path, str) or not path:
        raise ValueError("recorded file identity path is invalid")
    parsed = PurePosixPath(path)
    if (
        parsed.is_absolute()
        or ".." in parsed.parts
        or path != parsed.as_posix()
        or (expected_path is not None and path != expected_path)
    ):
        raise ValueError("recorded file identity path is invalid")
    byte_count = record["bytes"]
    if isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count < 0:
        raise ValueError("recorded file identity byte count is invalid")
    sha256 = record["sha256"]
    if not isinstance(sha256, str) or _SHA256_RE.fullmatch(sha256) is None:
        raise ValueError("recorded file identity digest is invalid")


def validate_recorded_source_identity(value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError("recorded source identity fields are invalid")
    source = cast(dict[str, object], value)
    if set(source) != SOURCE_FIELDS:
        raise ValueError("recorded source identity fields are invalid")
    files_value = source["files"]
    if not isinstance(files_value, list) or not files_value:
        raise ValueError("recorded source identity files are invalid")
    files = cast(list[object], files_value)
    for item in files:
        validate_recorded_file_identity(item)
    paths = [cast(str, cast(dict[str, object], item)["path"]) for item in files]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise ValueError("recorded source identity paths are invalid")
    sha256 = source["sha256"]
    if (
        not isinstance(sha256, str)
        or _SHA256_RE.fullmatch(sha256) is None
        or sha256 != _source_digest(cast(list[dict[str, object]], files))
    ):
        raise ValueError("recorded source identity digest is invalid")


def _source_digest(files: list[dict[str, object]]) -> str:
    encoded = json.dumps(
        files, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(encoded).hexdigest()
