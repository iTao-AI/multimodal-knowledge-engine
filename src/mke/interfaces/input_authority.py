"""Descriptor-bound input authority for the path-only MCP ingest boundary."""

from __future__ import annotations

import os
import stat
import sys
import tempfile
from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from mke.application import IngestFileAuthorityError

_COPY_BUFFER_BYTES = 1024 * 1024
_MAX_BOUND_INPUT_BYTES = 100 * 1024 * 1024
_CHANGED_CAUSE = "input path changed during validation"


@dataclass
class BoundInputFile:
    """An opened regular file whose content can be materialized without path reopen."""

    path: Path
    byte_count: int
    _descriptor: int
    _identity: tuple[int, int, int, int, int, int]
    _companions: tuple[BoundInputFile, ...] = ()
    _closed: bool = False

    def close(self) -> None:
        if not self._closed:
            try:
                os.close(self._descriptor)
            finally:
                try:
                    for companion in self._companions:
                        companion.close()
                finally:
                    self._closed = True

    def add_companion(self, companion: BoundInputFile) -> None:
        if self._closed:
            companion.close()
            raise IngestFileAuthorityError(_CHANGED_CAUSE)
        self._companions = (*self._companions, companion)

    def materialize(self) -> AbstractContextManager[Path]:
        return _materialize_bound_input(self)


def bind_allowed_file(allowed_root: Path, path: str) -> BoundInputFile:
    stripped_path = path.strip()
    if not stripped_path:
        raise ValueError("input path must not be empty")

    resolved_root = allowed_root.resolve(strict=True)
    requested = Path(stripped_path)
    candidate = requested if requested.is_absolute() else resolved_root / requested
    try:
        unresolved_stat = candidate.lstat()
    except FileNotFoundError as error:
        raise ValueError("input file does not exist") from error
    if stat.S_ISLNK(unresolved_stat.st_mode):
        raise ValueError("input path must not be a symlink")
    if not stat.S_ISREG(unresolved_stat.st_mode):
        raise ValueError("input path must be a file")

    resolved = candidate.resolve(strict=True)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as error:
        raise ValueError("input path must be under allowed root") from error
    resolved_stat = resolved.stat()
    if not stat.S_ISREG(resolved_stat.st_mode):
        raise ValueError("input path must be a file")
    if _file_identity(unresolved_stat) != _file_identity(resolved_stat):
        raise ValueError(_CHANGED_CAUSE)

    descriptor = -1
    try:
        descriptor = os.open(
            resolved,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        opened_stat = os.fstat(descriptor)
        identity = _file_identity(opened_stat)
        if not stat.S_ISREG(opened_stat.st_mode) or identity != _file_identity(resolved_stat):
            raise ValueError(_CHANGED_CAUSE)
        return BoundInputFile(resolved, opened_stat.st_size, descriptor, identity)
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        raise


def bind_optional_allowed_file(allowed_root: Path, path: str) -> BoundInputFile | None:
    stripped_path = path.strip()
    if not stripped_path:
        return None
    resolved_root = allowed_root.resolve(strict=True)
    requested = Path(stripped_path)
    candidate = requested if requested.is_absolute() else resolved_root / requested
    if not os.path.lexists(candidate):
        return None
    return bind_allowed_file(allowed_root, path)


@contextmanager
def _materialize_bound_input(bound: BoundInputFile) -> Generator[Path, None, None]:
    if bound._closed:  # pyright: ignore[reportPrivateUsage]
        raise IngestFileAuthorityError(_CHANGED_CAUSE)
    allocated_root = Path(tempfile.mkdtemp(prefix="mke-bound-ingest-"))
    root = allocated_root.parent.resolve(strict=True) / allocated_root.name
    root_stat = root.lstat()
    root_identity = _directory_identity(root_stat)
    entries: list[tuple[Path, tuple[int, int, int, int, int, int]]] = []
    target = root / bound.path.name
    try:
        _materialize_one(bound, root, entries)
        for companion in bound._companions:  # pyright: ignore[reportPrivateUsage]
            _materialize_one(companion, root, entries)
        yield target
    except IngestFileAuthorityError:
        raise
    except OSError as error:
        raise IngestFileAuthorityError(_CHANGED_CAUSE) from error
    finally:
        _cleanup_materialized_input(
            root,
            root_identity=root_identity,
            entries=entries,
        )


def _materialize_one(
    bound: BoundInputFile,
    root: Path,
    entries: list[tuple[Path, tuple[int, int, int, int, int, int]]],
) -> None:
    target = root / bound.path.name
    descriptor = -1
    try:
        descriptor = os.open(
            target,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        created_stat = os.fstat(descriptor)
        entries.append((target, _file_identity(created_stat)))
        _copy_stable_descriptor(bound, descriptor)
        os.fchmod(descriptor, 0o400)
        os.fsync(descriptor)
        entries[-1] = target, _file_identity(os.fstat(descriptor))
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _copy_stable_descriptor(bound: BoundInputFile, target_descriptor: int) -> None:
    before = os.fstat(bound._descriptor)  # pyright: ignore[reportPrivateUsage]
    if _file_identity(before) != bound._identity:  # pyright: ignore[reportPrivateUsage]
        raise IngestFileAuthorityError(_CHANGED_CAUSE)

    first_digest = sha256()
    copied = 0
    os.lseek(bound._descriptor, 0, os.SEEK_SET)  # pyright: ignore[reportPrivateUsage]
    while chunk := os.read(
        bound._descriptor,  # pyright: ignore[reportPrivateUsage]
        _COPY_BUFFER_BYTES,
    ):
        copied += len(chunk)
        if copied > _MAX_BOUND_INPUT_BYTES:
            raise IngestFileAuthorityError(_CHANGED_CAUSE)
        first_digest.update(chunk)
        _write_all(target_descriptor, chunk)

    second_digest = sha256()
    observed = 0
    os.lseek(bound._descriptor, 0, os.SEEK_SET)  # pyright: ignore[reportPrivateUsage]
    while chunk := os.read(
        bound._descriptor,  # pyright: ignore[reportPrivateUsage]
        _COPY_BUFFER_BYTES,
    ):
        observed += len(chunk)
        if observed > _MAX_BOUND_INPUT_BYTES:
            raise IngestFileAuthorityError(_CHANGED_CAUSE)
        second_digest.update(chunk)

    after = os.fstat(bound._descriptor)  # pyright: ignore[reportPrivateUsage]
    if (
        _file_identity(after) != bound._identity  # pyright: ignore[reportPrivateUsage]
        or copied != bound.byte_count
        or observed != bound.byte_count
        or first_digest.digest() != second_digest.digest()
    ):
        raise IngestFileAuthorityError(_CHANGED_CAUSE)


def _write_all(descriptor: int, data: bytes) -> None:
    written = 0
    while written < len(data):
        count = os.write(descriptor, data[written:])
        if count <= 0:
            raise IngestFileAuthorityError(_CHANGED_CAUSE)
        written += count


def _cleanup_materialized_input(
    root: Path,
    *,
    root_identity: tuple[int, int, int],
    entries: list[tuple[Path, tuple[int, int, int, int, int, int]]],
) -> None:
    root_descriptor = -1
    try:
        root_descriptor = os.open(
            root,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        if _directory_identity(os.fstat(root_descriptor)) != root_identity:
            raise IngestFileAuthorityError(_CHANGED_CAUSE)
        for target, target_identity in reversed(entries):
            if target.parent != root:
                raise IngestFileAuthorityError(_CHANGED_CAUSE)
            observed = os.stat(
                target.name,
                dir_fd=root_descriptor,
                follow_symlinks=False,
            )
            if _file_identity(observed) != target_identity:
                raise IngestFileAuthorityError(_CHANGED_CAUSE)
            os.unlink(target.name, dir_fd=root_descriptor)
        if os.listdir(root_descriptor):
            raise IngestFileAuthorityError(_CHANGED_CAUSE)
        if not _remove_owned_root_entry(root, root_identity, root_descriptor):
            raise IngestFileAuthorityError(_CHANGED_CAUSE)
        if os.path.lexists(root):
            raise IngestFileAuthorityError(_CHANGED_CAUSE)
    except FileNotFoundError as error:
        raise IngestFileAuthorityError(_CHANGED_CAUSE) from error
    except OSError as error:
        raise IngestFileAuthorityError(_CHANGED_CAUSE) from error
    finally:
        if root_descriptor >= 0:
            os.close(root_descriptor)


def _remove_owned_root_entry(
    root: Path,
    root_identity: tuple[int, int, int],
    root_descriptor: int,
) -> bool:
    if (
        _directory_identity(os.fstat(root_descriptor)) != root_identity
        or os.listdir(root_descriptor)
    ):
        raise IngestFileAuthorityError(_CHANGED_CAUSE)
    if sys.platform == "darwin":
        identity_path = Path("/.vol") / str(root_identity[0]) / str(root_identity[1])
        if _directory_identity(identity_path.lstat()) != root_identity:
            raise IngestFileAuthorityError(_CHANGED_CAUSE)
        try:
            root_path_unchanged = _directory_identity(root.lstat()) == root_identity
        except OSError:
            root_path_unchanged = False
        os.rmdir(identity_path)
        return root_path_unchanged

    parent_descriptor = os.open(
        root.parent,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        owned_name: str | None = None
        for name in os.listdir(parent_descriptor):
            observed = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
            if not stat.S_ISDIR(observed.st_mode):
                continue
            if _directory_identity(observed) == root_identity:
                if owned_name is not None:
                    raise IngestFileAuthorityError(_CHANGED_CAUSE)
                owned_name = name
        if owned_name is None:
            raise IngestFileAuthorityError(_CHANGED_CAUSE)
        os.rmdir(owned_name, dir_fd=parent_descriptor)
        return owned_name == root.name
    finally:
        os.close(parent_descriptor)


def _file_identity(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _directory_identity(value: os.stat_result) -> tuple[int, int, int]:
    if not stat.S_ISDIR(value.st_mode):
        raise IngestFileAuthorityError(_CHANGED_CAUSE)
    return value.st_dev, value.st_ino, value.st_mode


__all__ = ["BoundInputFile", "bind_allowed_file", "bind_optional_allowed_file"]
