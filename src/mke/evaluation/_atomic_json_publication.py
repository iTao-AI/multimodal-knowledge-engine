from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable
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
    with path.open("wb") as stream:
        stream.write(content)
        stream.flush()


def _fsync_file(path: Path) -> None:
    with path.open("rb") as stream:
        os.fsync(stream.fileno())


def _readback_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _publish_no_replace(temporary: Path, destination: Path) -> None:
    os.link(temporary, destination)


def _fsync_directory(path: Path) -> None:
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


def _existing_result(
    destination: Path,
    *,
    validate: Callable[[object], None],
) -> AtomicPublicationResult:
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
) -> AtomicPublicationResult:
    try:
        visible = destination.read_bytes()
    except FileNotFoundError:
        return AtomicPublicationResult(
            output_state="absent",
            publication_outcome="failed_before_visibility",
            sha256=None,
            problem="retrieval_order_publication_failed",
            cause="candidate_was_not_made_visible",
            next_step="retry_with_a_new_temporary_output",
        )
    except OSError:
        return _invalid_visible_result()
    try:
        _validate_bytes(visible, validate=validate)
    except (UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        return _invalid_visible_result()
    if visible != candidate:
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

    if destination.exists():
        return _existing_result(destination, validate=validate)

    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        try:
            _write_bytes(temporary, content)
            _fsync_file(temporary)
            readback = _readback_bytes(temporary)
            if readback != content:
                raise ValueError
            _validate_bytes(readback, validate=validate)
            _publish_no_replace(temporary, destination)
        except FileExistsError:
            return _result_after_publish_exception(
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
            return _result_after_publish_exception(
                destination,
                content,
                validate=validate,
            )

        try:
            _fsync_directory(destination.parent)
        except OSError:
            return AtomicPublicationResult(
                output_state="complete_visible",
                publication_outcome="durability_unconfirmed",
                sha256=sha256_bytes(content),
                problem=(
                    "retrieval_order_publication_durability_unconfirmed"
                ),
                cause="directory_sync_failed_after_visibility",
                next_step="do_not_retry_visible_output",
            )
        return AtomicPublicationResult(
            output_state="complete_visible",
            publication_outcome="published",
            sha256=sha256_bytes(content),
            problem=None,
        )
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
