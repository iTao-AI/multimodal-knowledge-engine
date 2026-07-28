from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import cast

FILE_FIELDS = {"path", "bytes", "sha256"}
SOURCE_FIELDS = {"sha256", "files"}
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


def build_file_identity(
    repository_root: Path, relative_path: str
) -> dict[str, object]:
    root = repository_root.resolve()
    validate_recorded_file_identity(
        {"path": relative_path, "bytes": 0, "sha256": "0" * 64},
        expected_path=relative_path,
    )
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("source identity path is invalid")
    data = path.read_bytes()
    return {
        "path": relative_path,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def build_source_identity(
    repository_root: Path, relative_paths: Sequence[str]
) -> dict[str, object]:
    paths = sorted(relative_paths)
    if not paths or len(paths) != len(set(paths)):
        raise ValueError("source identity paths are invalid")
    files = [build_file_identity(repository_root, path) for path in paths]
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
