"""Transactional publication of a compiled Library export tree."""

from __future__ import annotations

import errno
import os
import stat
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PureWindowsPath
from typing import Literal

from mke.application.library_export import (
    LibraryExportResult,
    RenderedSourceEntry,
    render_compiled_markdown,
    render_evidence_jsonl,
    render_export_manifest,
)
from mke.domain import (
    CompiledLibrarySnapshot,
    CompiledLibrarySnapshotV2,
    ExportFormatVersion,
    LibraryExportDataError,
)

_MANIFEST_NAME = "export-manifest.json"
_TEMP_MANIFEST_NAME = ".export-manifest.json.tmp"
_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
_FILE_FLAGS = (
    os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
)
_FILE_READ_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
_READ_CHUNK_BYTES = 64 * 1024
_INVALID_PARENT_ERRNOS = frozenset(
    {
        errno.EACCES,
        errno.EINVAL,
        errno.ELOOP,
        errno.ENAMETOOLONG,
        errno.ENOENT,
        errno.ENOTDIR,
        errno.EPERM,
        errno.EROFS,
    }
)

OutputPublicationReason = Literal[
    "target_exists", "parent_invalid", "write_failed", "cleanup_failed"
]


class OutputPublicationError(Exception):
    """A closed failure from local output publication."""

    reason: OutputPublicationReason

    def __init__(self, reason: OutputPublicationReason) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class _Identity:
    device: int
    inode: int
    file_type: int


@dataclass(frozen=True)
class _OwnedEntry:
    parts: tuple[str, ...]
    identity: _Identity
    expected_size: int | None = None
    expected_sha256: bytes | None = None


def _identity(value: os.stat_result) -> _Identity:
    return _Identity(value.st_dev, value.st_ino, stat.S_IFMT(value.st_mode))


def _same_identity(value: os.stat_result, expected: _Identity) -> bool:
    return _identity(value) == expected


def _validate_output_name(output_name: str) -> None:
    if (
        type(output_name) is not str
        or output_name in {"", ".", ".."}
        or "\0" in output_name
        or "/" in output_name
        or "\\" in output_name
        or PureWindowsPath(output_name).is_absolute()
        or PureWindowsPath(output_name).drive != ""
    ):
        raise OutputPublicationError("parent_invalid")


def _close_fd(fd: int) -> None:
    os.close(fd)


def _safe_close(fd: int | None) -> None:
    if fd is None:
        return
    try:
        os.close(fd)
    except OSError:
        pass


def _open_parent(parent: Path) -> int:
    current_fd: int | None = None
    try:
        path = Path(parent)
        if path.is_absolute():
            current_fd = os.open("/", _DIRECTORY_FLAGS)
            parts = path.parts[1:]
        else:
            current_fd = os.open(".", _DIRECTORY_FLAGS)
            parts = path.parts
        for part in parts:
            if part in {"", "."}:
                continue
            if part == "..":
                raise OSError(errno.EINVAL, "parent traversal is not allowed")
            next_fd = os.open(part, _DIRECTORY_FLAGS, dir_fd=current_fd)
            _close_fd(current_fd)
            current_fd = next_fd
        return current_fd
    except (OSError, TypeError, ValueError) as exc:
        _safe_close(current_fd)
        raise OutputPublicationError("parent_invalid") from exc


def _lstat(name: str, directory_fd: int) -> os.stat_result:
    return os.stat(name, dir_fd=directory_fd, follow_symlinks=False)


def _create_directory(
    parent_fd: int,
    name: str,
    parts: tuple[str, ...],
    owned: list[_OwnedEntry],
) -> int:
    os.mkdir(name, mode=0o700, dir_fd=parent_fd)
    value = _lstat(name, parent_fd)
    identity = _identity(value)
    if identity.file_type != stat.S_IFDIR:
        raise OSError(errno.EINVAL, "created entry is not a directory")
    owned.append(_OwnedEntry(parts, identity))
    child_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
    if not _same_identity(os.fstat(child_fd), identity):
        _safe_close(child_fd)
        raise OSError(errno.ESTALE, "directory identity changed")
    return child_fd


def _write_chunk(fd: int, data: memoryview) -> int:
    return os.write(fd, data)


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        written = _write_chunk(fd, view[offset:])
        if written <= 0 or written > len(view) - offset:
            raise OSError(errno.EIO, "short write made no progress")
        offset += written


def _read_bounded(fd: int, maximum: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(fd, min(_READ_CHUNK_BYTES, maximum + 1 - total))
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > maximum:
            raise OSError(errno.EIO, "file exceeds expected byte count")
        chunks.append(chunk)


def _revalidate_file(fd: int, expected: bytes, identity: _Identity) -> None:
    current = os.fstat(fd)
    if not _same_identity(current, identity) or identity.file_type != stat.S_IFREG:
        raise OSError(errno.ESTALE, "file identity changed")
    os.lseek(fd, 0, os.SEEK_SET)
    actual = _read_bounded(fd, len(expected))
    if len(actual) != len(expected) or sha256(actual).digest() != sha256(expected).digest():
        raise OSError(errno.EIO, "file digest mismatch")


def _create_write_file(
    directory_fd: int,
    name: str,
    data: bytes,
    parts: tuple[str, ...],
    owned: list[_OwnedEntry],
) -> _OwnedEntry:
    fd = os.open(name, _FILE_FLAGS, 0o600, dir_fd=directory_fd)
    identity = _identity(os.fstat(fd))
    if identity.file_type != stat.S_IFREG:
        _safe_close(fd)
        raise OSError(errno.EINVAL, "created entry is not a regular file")
    entry = _OwnedEntry(parts, identity, len(data), sha256(data).digest())
    owned.append(entry)
    try:
        _write_all(fd, data)
        _revalidate_file(fd, data, identity)
    finally:
        _close_fd(fd)
    return entry


def _revalidate_file_at(
    directory_fd: int,
    name: str,
    entry: _OwnedEntry,
) -> None:
    if (
        entry.identity.file_type != stat.S_IFREG
        or entry.expected_size is None
        or entry.expected_sha256 is None
    ):
        raise OSError(errno.EINVAL, "owned file metadata is incomplete")
    path_before = _lstat(name, directory_fd)
    if not _same_identity(path_before, entry.identity):
        raise OSError(errno.ESTALE, "owned file path identity changed")
    fd: int | None = None
    try:
        fd = os.open(name, _FILE_READ_FLAGS, dir_fd=directory_fd)
        descriptor_before = os.fstat(fd)
        path_bound = _lstat(name, directory_fd)
        if (
            not _same_identity(descriptor_before, entry.identity)
            or not _same_identity(path_bound, entry.identity)
            or stat.S_IFMT(descriptor_before.st_mode) != stat.S_IFREG
            or descriptor_before.st_size != entry.expected_size
            or path_bound.st_size != entry.expected_size
        ):
            raise OSError(errno.ESTALE, "owned file identity or size changed")
        actual = _read_bounded(fd, entry.expected_size)
        descriptor_after = os.fstat(fd)
        path_after = _lstat(name, directory_fd)
        if (
            len(actual) != entry.expected_size
            or sha256(actual).digest() != entry.expected_sha256
            or not _same_identity(descriptor_after, entry.identity)
            or not _same_identity(path_after, entry.identity)
            or descriptor_after.st_size != entry.expected_size
            or path_after.st_size != entry.expected_size
        ):
            raise OSError(errno.EIO, "owned file content changed")
    finally:
        if fd is not None:
            _close_fd(fd)


def _revalidate_owned_file(target_fd: int, entry: _OwnedEntry) -> None:
    directory_fd, close_directory = _open_relative_parent(target_fd, entry.parts)
    try:
        _revalidate_file_at(directory_fd, entry.parts[-1], entry)
    finally:
        if close_directory:
            _close_fd(directory_fd)


def _revalidate_owned_files(target_fd: int, owned: list[_OwnedEntry]) -> None:
    for entry in owned:
        if entry.identity.file_type == stat.S_IFREG:
            _revalidate_owned_file(target_fd, entry)


def _write_content_file(
    directory_fd: int,
    name: str,
    data: bytes,
    parts: tuple[str, ...],
    owned: list[_OwnedEntry],
) -> None:
    entry = _create_write_file(directory_fd, name, data, parts, owned)
    _revalidate_file_at(directory_fd, name, entry)


def _inventory(directory_fd: int) -> set[str]:
    inventory: set[str] = set()
    for name in os.listdir(directory_fd):
        value = _lstat(name, directory_fd)
        file_type = stat.S_IFMT(value.st_mode)
        inventory.add(name)
        if file_type == stat.S_IFDIR:
            child_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=directory_fd)
            try:
                for child in os.listdir(child_fd):
                    child_value = _lstat(child, child_fd)
                    if stat.S_IFMT(child_value.st_mode) != stat.S_IFREG:
                        inventory.add(f"{name}/{child}/")
                    else:
                        inventory.add(f"{name}/{child}")
            finally:
                _close_fd(child_fd)
    return inventory


def _validate_exact_inventory(target_fd: int, expected: set[str]) -> None:
    if _inventory(target_fd) != expected:
        raise OSError(errno.EINVAL, "unexpected export inventory")


def _write_manifest_temp(
    target_fd: int, manifest: bytes, owned: list[_OwnedEntry]
) -> _OwnedEntry:
    entry = _create_write_file(
        target_fd,
        _TEMP_MANIFEST_NAME,
        manifest,
        (_TEMP_MANIFEST_NAME,),
        owned,
    )
    _revalidate_file_at(target_fd, _TEMP_MANIFEST_NAME, entry)
    return entry


def _publish_manifest(target_fd: int) -> None:
    os.rename(
        _TEMP_MANIFEST_NAME,
        _MANIFEST_NAME,
        src_dir_fd=target_fd,
        dst_dir_fd=target_fd,
    )


def _rebind_published_manifest(
    owned: list[_OwnedEntry], manifest_entry: _OwnedEntry
) -> _OwnedEntry:
    published = _OwnedEntry(
        (_MANIFEST_NAME,),
        manifest_entry.identity,
        manifest_entry.expected_size,
        manifest_entry.expected_sha256,
    )
    for index, entry in enumerate(owned):
        if entry is manifest_entry:
            owned[index] = published
            return published
    raise OSError(errno.ESTALE, "temporary manifest ownership was lost")


def _revalidate_target(
    parent_fd: int,
    output_name: str,
    target_fd: int,
    expected: _Identity,
) -> None:
    path_value = _lstat(output_name, parent_fd)
    descriptor_value = os.fstat(target_fd)
    if (
        expected.file_type != stat.S_IFDIR
        or not _same_identity(path_value, expected)
        or not _same_identity(descriptor_value, expected)
        or _identity(path_value) != _identity(descriptor_value)
    ):
        raise OSError(errno.ESTALE, "target identity changed before publication")


def _open_relative_parent(target_fd: int, parts: tuple[str, ...]) -> tuple[int, bool]:
    if len(parts) == 1:
        return target_fd, False
    current_fd = os.open(parts[0], _DIRECTORY_FLAGS, dir_fd=target_fd)
    try:
        for part in parts[1:-1]:
            next_fd = os.open(part, _DIRECTORY_FLAGS, dir_fd=current_fd)
            _close_fd(current_fd)
            current_fd = next_fd
        return current_fd, True
    except Exception:
        _safe_close(current_fd)
        raise


def _unlink_owned(target_fd: int, entry: _OwnedEntry) -> None:
    directory_fd, close_directory = _open_relative_parent(target_fd, entry.parts)
    try:
        current = _lstat(entry.parts[-1], directory_fd)
        if not _same_identity(current, entry.identity):
            raise OSError(errno.ESTALE, "owned file identity changed")
        os.unlink(entry.parts[-1], dir_fd=directory_fd)
    finally:
        if close_directory:
            _safe_close(directory_fd)


def _rmdir_owned(target_fd: int, entry: _OwnedEntry) -> None:
    directory_fd, close_directory = _open_relative_parent(target_fd, entry.parts)
    try:
        current = _lstat(entry.parts[-1], directory_fd)
        if not _same_identity(current, entry.identity):
            raise OSError(errno.ESTALE, "owned directory identity changed")
        os.rmdir(entry.parts[-1], dir_fd=directory_fd)
    finally:
        if close_directory:
            _safe_close(directory_fd)


def _cleanup(
    parent_fd: int,
    target_fd: int,
    output_name: str,
    target_identity: _Identity,
    owned: list[_OwnedEntry],
) -> bool:
    complete = True
    for entry in reversed(owned):
        try:
            if entry.identity.file_type == stat.S_IFDIR:
                _rmdir_owned(target_fd, entry)
            elif entry.identity.file_type == stat.S_IFREG:
                _unlink_owned(target_fd, entry)
            else:
                complete = False
        except OSError:
            complete = False
    try:
        current = _lstat(output_name, parent_fd)
        if not _same_identity(current, target_identity):
            return False
        os.rmdir(output_name, dir_fd=parent_fd)
    except OSError:
        complete = False
    return complete


def _cleanup_target_only(
    parent_fd: int, output_name: str, target_identity: _Identity
) -> bool:
    try:
        current = _lstat(output_name, parent_fd)
        if not _same_identity(current, target_identity):
            return False
        os.rmdir(output_name, dir_fd=parent_fd)
    except OSError:
        return False
    return True


def publish_compiled_library(
    snapshot: CompiledLibrarySnapshot | CompiledLibrarySnapshotV2,
    *,
    format_version: ExportFormatVersion = "v1",
    output_name: str,
    parent: Path = Path("."),
) -> LibraryExportResult:
    """Publish a new compiled Library directory with the manifest as commit marker."""

    if format_version not in ("v1", "v2"):
        raise ValueError("unsupported export format version")
    expected_type = (
        CompiledLibrarySnapshot
        if format_version == "v1"
        else CompiledLibrarySnapshotV2
    )
    if type(snapshot) is not expected_type:
        raise LibraryExportDataError("provenance")
    _validate_output_name(output_name)
    snapshot.__post_init__()
    parent_fd = _open_parent(parent)
    target_fd: int | None = None
    sources_fd: int | None = None
    evidence_fd: int | None = None
    target_identity: _Identity | None = None
    target_created = False
    owned: list[_OwnedEntry] = []
    try:
        try:
            _lstat(output_name, parent_fd)
        except FileNotFoundError:
            pass
        else:
            raise OutputPublicationError("target_exists")
        try:
            os.mkdir(output_name, mode=0o700, dir_fd=parent_fd)
        except FileExistsError as exc:
            raise OutputPublicationError("target_exists") from exc
        except OSError as exc:
            reason: OutputPublicationReason = (
                "parent_invalid"
                if exc.errno in _INVALID_PARENT_ERRNOS
                else "write_failed"
            )
            raise OutputPublicationError(reason) from exc
        target_created = True
        target_value = _lstat(output_name, parent_fd)
        target_identity = _identity(target_value)
        if target_identity.file_type != stat.S_IFDIR:
            raise OutputPublicationError("parent_invalid")
        target_fd = os.open(output_name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
        if not _same_identity(os.fstat(target_fd), target_identity):
            raise OutputPublicationError("parent_invalid")

        sources_fd = _create_directory(
            target_fd, "sources", ("sources",), owned
        )
        evidence_fd = _create_directory(
            target_fd, "evidence", ("evidence",), owned
        )
        directory_fds = {"sources": sources_fd, "evidence": evidence_fd}
        expected = {"sources", "evidence"}
        entries: list[RenderedSourceEntry] = []
        evidence_count = 0
        for source in snapshot.sources:
            digest = source.content_fingerprint.removeprefix("sha256:")
            evidence = render_evidence_jsonl(source, format_version=format_version)
            markdown = render_compiled_markdown(source, format_version=format_version)
            evidence_name = f"{digest}.jsonl"
            markdown_name = f"{digest}.md"
            _write_content_file(
                directory_fds["evidence"],
                evidence_name,
                evidence,
                ("evidence", evidence_name),
                owned,
            )
            _write_content_file(
                directory_fds["sources"],
                markdown_name,
                markdown,
                ("sources", markdown_name),
                owned,
            )
            expected.update(
                {f"evidence/{evidence_name}", f"sources/{markdown_name}"}
            )
            evidence_count += len(source.evidence)
            entries.append(
                RenderedSourceEntry(
                    source_id=source.source_id,
                    display_name=source.display_name,
                    content_fingerprint=source.content_fingerprint,
                    media_type=source.media_type,
                    publication_id=source.publication_id,
                    publication_revision=source.publication_revision,
                    run_id=source.run_id,
                    extractor_fingerprint=source.extractor_fingerprint,
                    required_stages=source.required_stages,
                    evidence_count=len(source.evidence),
                    evidence_path=f"evidence/{evidence_name}",
                    evidence_sha256=sha256(evidence).hexdigest(),
                    markdown_path=f"sources/{markdown_name}",
                    markdown_sha256=sha256(markdown).hexdigest(),
                )
            )
            del evidence, markdown

        _close_fd(sources_fd)
        sources_fd = None
        _close_fd(evidence_fd)
        evidence_fd = None
        _validate_exact_inventory(target_fd, expected)
        _revalidate_owned_files(target_fd, owned)
        manifest = render_export_manifest(
            snapshot, entries, format_version=format_version
        )
        result = LibraryExportResult(
            library_id=snapshot.observation.library_id,
            source_count=len(snapshot.sources),
            evidence_count=evidence_count,
            manifest_sha256=sha256(manifest).hexdigest(),
        )
        manifest_entry = _write_manifest_temp(target_fd, manifest, owned)
        _revalidate_target(parent_fd, output_name, target_fd, target_identity)
        _publish_manifest(target_fd)
        _rebind_published_manifest(owned, manifest_entry)
        _validate_exact_inventory(target_fd, expected | {_MANIFEST_NAME})
        _revalidate_owned_files(target_fd, owned)
        _revalidate_target(parent_fd, output_name, target_fd, target_identity)
        return result
    except LibraryExportDataError as exc:
        if not target_created:
            raise
        if target_identity is None:
            raise OutputPublicationError("cleanup_failed") from exc
        cleaned = (
            _cleanup(parent_fd, target_fd, output_name, target_identity, owned)
            if target_fd is not None
            else _cleanup_target_only(parent_fd, output_name, target_identity)
        )
        if not cleaned:
            raise OutputPublicationError("cleanup_failed") from exc
        raise
    except OutputPublicationError as exc:
        if not target_created:
            raise
        if target_identity is None:
            raise OutputPublicationError("cleanup_failed") from exc
        cleaned = (
            _cleanup(parent_fd, target_fd, output_name, target_identity, owned)
            if target_fd is not None
            else _cleanup_target_only(parent_fd, output_name, target_identity)
        )
        if not cleaned:
            raise OutputPublicationError("cleanup_failed") from exc
        raise
    except (OSError, ValueError) as exc:
        if not target_created:
            raise OutputPublicationError("parent_invalid") from exc
        if target_identity is None:
            raise OutputPublicationError("cleanup_failed") from exc
        cleaned = (
            _cleanup(parent_fd, target_fd, output_name, target_identity, owned)
            if target_fd is not None
            else _cleanup_target_only(parent_fd, output_name, target_identity)
        )
        if not cleaned:
            raise OutputPublicationError("cleanup_failed") from exc
        raise OutputPublicationError("write_failed") from exc
    finally:
        _safe_close(sources_fd)
        _safe_close(evidence_fd)
        _safe_close(target_fd)
        _safe_close(parent_fd)
