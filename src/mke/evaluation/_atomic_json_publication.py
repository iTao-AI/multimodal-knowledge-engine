from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

OutputState = Literal[
    "absent",
    "complete_preexisting",
    "complete_visible",
    "not_applicable",
]
PublicationOutcome = Literal[
    "not_attempted",
    "published",
    "failed_before_visibility",
    "durability_unconfirmed",
]


@dataclass(frozen=True)
class AtomicPublicationResult:
    output_state: OutputState
    publication_outcome: PublicationOutcome
    sha256: str | None
    problem: str | None
    cause: str | None = None
    next_step: str | None = None


@dataclass(frozen=True)
class _PublicationAuthority:
    parent_fd: int
    destination_name: str
    temporary_name: str


_ACTIVE_AUTHORITY: ContextVar[_PublicationAuthority | None] = ContextVar(
    "mke_atomic_publication_authority",
    default=None,
)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _validate_bytes(
    content: bytes,
    *,
    validate: Callable[[object], None],
) -> None:
    payload = json.loads(content)
    validate(payload)


def _write_bytes(path: Path, content: bytes) -> None:
    authority = _authority_for(path)
    if authority is not None:
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(
            path.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow,
            0o600,
            dir_fd=authority.parent_fd,
        )
        try:
            remaining = memoryview(content)
            while remaining:
                written = os.write(descriptor, remaining)
                if written < 1:
                    raise OSError("publication write did not progress")
                remaining = remaining[written:]
        finally:
            os.close(descriptor)
        return
    with path.open("wb") as stream:
        stream.write(content)
        stream.flush()


def _fsync_file(path: Path) -> None:
    authority = _authority_for(path)
    if authority is not None:
        descriptor = os.open(
            path.name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=authority.parent_fd,
        )
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return
    with path.open("rb") as stream:
        os.fsync(stream.fileno())


def _readback_bytes(path: Path) -> bytes:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise OSError("no-follow reads are unavailable")
    authority = _authority_for(path)
    descriptor = os.open(
        path.name if authority is not None else path,
        os.O_RDONLY | nofollow,
        dir_fd=authority.parent_fd if authority is not None else None,
    )
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("visible output is not a regular file")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _publish_no_replace(temporary: Path, destination: Path) -> None:
    authority = _authority_for(temporary)
    if authority is not None:
        os.link(
            temporary.name,
            destination.name,
            src_dir_fd=authority.parent_fd,
            dst_dir_fd=authority.parent_fd,
            follow_symlinks=False,
        )
        return
    os.link(temporary, destination)


def _fsync_directory(path: Path) -> None:
    authority = _ACTIVE_AUTHORITY.get()
    if authority is not None:
        os.fsync(authority.parent_fd)
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _invalid_result() -> AtomicPublicationResult:
    return AtomicPublicationResult(
        output_state="not_applicable",
        publication_outcome="not_attempted",
        sha256=None,
        problem="retrieval_order_output_invalid",
        cause="candidate_json_failed_validation",
        next_step="provide_a_valid_compatibility_record",
    )


def _invalid_visible_result() -> AtomicPublicationResult:
    return AtomicPublicationResult(
        output_state="not_applicable",
        publication_outcome="durability_unconfirmed",
        sha256=None,
        problem="retrieval_order_publication_failed",
        cause="visible_output_could_not_be_validated",
        next_step="do_not_retry_visible_output",
    )


def _invalid_parent_result() -> AtomicPublicationResult:
    return AtomicPublicationResult(
        output_state="not_applicable",
        publication_outcome="not_attempted",
        sha256=None,
        problem="retrieval_order_publication_failed",
        cause="destination_parent_authority_invalid",
        next_step="provide_a_no_follow_destination_parent",
    )


def _open_parent_chain_no_follow(
    path: Path,
    *,
    create_missing: bool,
) -> int | None:
    absolute = path.absolute()
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None:
        return None
    descriptors: list[int] = []
    retained: int | None = None
    try:
        parent_fd = os.open(absolute.anchor, os.O_RDONLY | directory | nofollow)
        descriptors.append(parent_fd)
        for component in absolute.parent.parts[1:]:
            try:
                child_fd = os.open(
                    component,
                    os.O_RDONLY | directory | nofollow,
                    dir_fd=parent_fd,
                )
            except FileNotFoundError:
                if not create_missing:
                    return None
                try:
                    os.mkdir(component, dir_fd=parent_fd)
                except FileExistsError:
                    pass
                child_fd = os.open(
                    component,
                    os.O_RDONLY | directory | nofollow,
                    dir_fd=parent_fd,
                )
            descriptors.append(child_fd)
            parent_fd = child_fd
        retained = descriptors.pop()
    except OSError:
        return None
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
    return retained


def _parent_binding_matches(path: Path, parent_fd: int) -> bool:
    current_fd = _open_parent_chain_no_follow(path, create_missing=False)
    if current_fd is None:
        return False
    try:
        current = os.fstat(current_fd)
        retained = os.fstat(parent_fd)
        return (current.st_dev, current.st_ino) == (
            retained.st_dev,
            retained.st_ino,
        )
    finally:
        os.close(current_fd)


def _authority_for(path: Path) -> _PublicationAuthority | None:
    authority = _ACTIVE_AUTHORITY.get()
    if authority is None or path.name not in {
        authority.destination_name,
        authority.temporary_name,
    }:
        return None
    return authority


def _unlink_temporary(path: Path) -> None:
    authority = _authority_for(path)
    if authority is not None:
        os.unlink(path.name, dir_fd=authority.parent_fd)
        return
    path.unlink()


def _lexical_state(path: Path) -> Literal["absent", "regular", "invalid"]:
    try:
        authority = _authority_for(path)
        metadata = (
            os.stat(
                path.name,
                dir_fd=authority.parent_fd,
                follow_symlinks=False,
            )
            if authority is not None
            else path.lstat()
        )
    except FileNotFoundError:
        return "absent"
    except OSError:
        return "invalid"
    return "regular" if stat.S_ISREG(metadata.st_mode) else "invalid"


def _existing_result(
    destination: Path,
    *,
    validate: Callable[[object], None],
) -> AtomicPublicationResult:
    if _lexical_state(destination) != "regular":
        return _invalid_visible_result()
    try:
        existing = _readback_bytes(destination)
        _validate_bytes(existing, validate=validate)
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        return _invalid_visible_result()
    return AtomicPublicationResult(
        output_state="complete_preexisting",
        publication_outcome="not_attempted",
        sha256=sha256_bytes(existing),
        problem="retrieval_order_output_exists",
        cause="destination_already_contains_a_complete_record",
        next_step="validate_or_choose_a_new_temporary_output",
    )


def _result_after_publish_exception(
    destination: Path,
    candidate: bytes,
    *,
    validate: Callable[[object], None],
    different_visible_is_invalid: bool = False,
) -> AtomicPublicationResult:
    state = _lexical_state(destination)
    if state == "absent":
        return AtomicPublicationResult(
            output_state="absent",
            publication_outcome="failed_before_visibility",
            sha256=None,
            problem="retrieval_order_publication_failed",
            cause="candidate_was_not_made_visible",
            next_step="retry_with_a_new_temporary_output",
        )
    if state == "invalid":
        return _invalid_visible_result()
    try:
        visible = _readback_bytes(destination)
    except OSError:
        return _invalid_visible_result()
    try:
        _validate_bytes(visible, validate=validate)
    except (UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        return _invalid_visible_result()
    if visible != candidate:
        if different_visible_is_invalid:
            return _invalid_visible_result()
        return AtomicPublicationResult(
            output_state="complete_preexisting",
            publication_outcome="not_attempted",
            sha256=sha256_bytes(visible),
            problem="retrieval_order_output_exists",
            cause="destination_contains_a_different_complete_record",
            next_step="do_not_retry_visible_output",
        )
    return AtomicPublicationResult(
        output_state="complete_visible",
        publication_outcome="durability_unconfirmed",
        sha256=sha256_bytes(visible),
        problem="retrieval_order_publication_durability_unconfirmed",
        cause="publication_failed_after_visibility",
        next_step="do_not_retry_visible_output",
    )


def publish_json_no_replace(
    destination: Path,
    content: bytes,
    *,
    validate: Callable[[object], None],
) -> AtomicPublicationResult:
    try:
        _validate_bytes(content, validate=validate)
    except (UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        return _invalid_result()

    parent_fd = _open_parent_chain_no_follow(destination, create_missing=True)
    if parent_fd is None:
        return _invalid_parent_result()
    temporary = destination.parent / (
        f".{destination.name}.{secrets.token_hex(16)}.tmp"
    )
    authority = _PublicationAuthority(
        parent_fd=parent_fd,
        destination_name=destination.name,
        temporary_name=temporary.name,
    )
    token = _ACTIVE_AUTHORITY.set(authority)
    cleanup_failed = False
    try:
        if not _parent_binding_matches(destination, parent_fd):
            return _invalid_parent_result()
        if _lexical_state(destination) != "absent":
            return _existing_result(destination, validate=validate)
        try:
            _write_bytes(temporary, content)
            _fsync_file(temporary)
            readback = _readback_bytes(temporary)
            if readback != content:
                raise ValueError
            _validate_bytes(readback, validate=validate)
            if not _parent_binding_matches(destination, parent_fd):
                raise OSError("destination parent authority changed")
            _publish_no_replace(temporary, destination)
        except FileExistsError:
            result = _result_after_publish_exception(
                destination,
                content,
                validate=validate,
            )
        except (
            OSError,
            UnicodeError,
            ValueError,
            TypeError,
            json.JSONDecodeError,
        ):
            result = _result_after_publish_exception(
                destination,
                content,
                validate=validate,
            )
        else:
            if not _parent_binding_matches(destination, parent_fd):
                result = _invalid_visible_result()
                return result
            try:
                _fsync_directory(destination.parent)
            except OSError:
                result = AtomicPublicationResult(
                    output_state="complete_visible",
                    publication_outcome="durability_unconfirmed",
                    sha256=sha256_bytes(content),
                    problem=(
                        "retrieval_order_publication_durability_unconfirmed"
                    ),
                    cause="directory_sync_failed_after_visibility",
                    next_step="do_not_retry_visible_output",
                )
            else:
                result = AtomicPublicationResult(
                    output_state="complete_visible",
                    publication_outcome="published",
                    sha256=sha256_bytes(content),
                    problem=None,
                )
    finally:
        try:
            _unlink_temporary(temporary)
        except FileNotFoundError:
            pass
        except OSError:
            cleanup_failed = True
        if cleanup_failed:
            result = _result_after_publish_exception(
                destination,
                content,
                validate=validate,
                different_visible_is_invalid=True,
            )
        _ACTIVE_AUTHORITY.reset(token)
        os.close(parent_fd)
    return result
