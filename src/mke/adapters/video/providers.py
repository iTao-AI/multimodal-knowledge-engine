"""Transcript provider adapters for local video Evidence."""

from __future__ import annotations

import os
import select
import subprocess
import time
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from mke.adapters.video.contracts import (
    AdapterFailureSpec,
    build_transcript_intake_report,
    faster_whisper_fingerprint,
)
from mke.adapters.video.errors import VideoExtractionError
from mke.adapters.video.process import ActiveProcessController
from mke.adapters.video.schema import load_transcript_json
from mke.domain import (
    LOCAL_COMMAND_VIDEO_TRANSCRIPT_FINGERPRINT,
    VIDEO_TRANSCRIPT_FINGERPRINT,
    TranscriptExtractionResult,
)

_CAPTURE_CHUNK_BYTES = 8192
_POLL_INTERVAL_SECONDS = 0.05


def _empty_exit_code_errors() -> Mapping[int, AdapterFailureSpec]:
    return {}


@dataclass(frozen=True)
class SidecarTranscriptProvider:
    """Default deterministic provider backed by repository sidecar JSON."""

    def extract(self, path: Path) -> TranscriptExtractionResult:
        if not path.exists():
            raise VideoExtractionError("input video is missing")
        sidecar = path.with_suffix(path.suffix + ".mke-transcript.json")
        if not sidecar.exists():
            raise VideoExtractionError("video transcript sidecar is missing")
        parsed = load_transcript_json(sidecar.read_text(), require_provenance=False)
        return TranscriptExtractionResult(
            parsed_transcript=parsed,
            extractor_fingerprint=VIDEO_TRANSCRIPT_FINGERPRINT,
        )


@dataclass(frozen=True)
class LocalCommandTranscriptConfig:
    argv: Sequence[str]
    timeout_seconds: float = 60.0
    max_stdout_bytes: int = 1024 * 1024
    max_stderr_bytes: int = 64 * 1024
    extractor_fingerprint: str = LOCAL_COMMAND_VIDEO_TRANSCRIPT_FINGERPRINT
    require_provenance: bool = False
    exit_code_errors: Mapping[int, AdapterFailureSpec] = field(
        default_factory=_empty_exit_code_errors
    )
    process_controller: ActiveProcessController | None = None

    def __post_init__(self) -> None:
        if isinstance(self.argv, str) or not isinstance(self.argv, Sequence):  # pyright: ignore[reportUnnecessaryIsInstance] -- runtime guard for untyped callers
            raise TypeError("argv must be a non-empty sequence of strings")
        normalized = tuple(self.argv)
        if not normalized:
            raise TypeError("argv must be a non-empty sequence of strings")
        if any(
            not isinstance(part, str) or not part  # pyright: ignore[reportUnnecessaryIsInstance] -- runtime guard for untyped callers
            for part in normalized
        ):
            raise TypeError("argv must contain non-empty strings")
        if normalized.count("{input}") != 1:
            raise ValueError("argv must contain exactly one {input} placeholder")
        object.__setattr__(self, "argv", normalized)
        if any(type(code) is not int or code <= 0 for code in self.exit_code_errors):
            raise ValueError("adapter exit codes must be positive integers")
        object.__setattr__(
            self,
            "exit_code_errors",
            MappingProxyType(dict(self.exit_code_errors)),
        )


@dataclass(frozen=True)
class LocalCommandTranscriptProvider:
    config: LocalCommandTranscriptConfig

    def extract(self, path: Path) -> TranscriptExtractionResult:
        if not path.exists():
            raise VideoExtractionError("input video is missing")
        command = [str(path) if part == "{input}" else part for part in self.config.argv]
        completed = _run_bounded_command(
            command,
            timeout_seconds=self.config.timeout_seconds,
            max_stdout_bytes=self.config.max_stdout_bytes,
            max_stderr_bytes=self.config.max_stderr_bytes,
            process_controller=self.config.process_controller,
        )
        if completed.returncode != 0:
            failure = self.config.exit_code_errors.get(completed.returncode)
            if failure is not None:
                raise VideoExtractionError(
                    failure.cause,
                    problem=failure.problem,
                    next_step=failure.next_step,
                )
            raise VideoExtractionError("transcript command failed")
        try:
            text = completed.stdout.decode("utf-8")
        except UnicodeDecodeError as error:
            raise VideoExtractionError("transcript command stdout is not valid UTF-8") from error
        parsed = load_transcript_json(
            text,
            require_provenance=self.config.require_provenance,
        )
        if self.config.require_provenance:
            provenance = parsed.transcription_provenance
            if provenance is None:
                raise VideoExtractionError("transcript provenance is required")
            return TranscriptExtractionResult(
                parsed_transcript=parsed,
                extractor_fingerprint=faster_whisper_fingerprint(provenance),
                transcript_intake_report=build_transcript_intake_report(parsed),
            )
        return TranscriptExtractionResult(
            parsed_transcript=parsed,
            extractor_fingerprint=self.config.extractor_fingerprint,
        )


@dataclass(frozen=True)
class _BoundedCommandResult:
    returncode: int
    stdout: bytes
    stderr: bytes


def _run_bounded_command(
    command: Sequence[str],
    *,
    timeout_seconds: float,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
    process_controller: ActiveProcessController | None = None,
) -> _BoundedCommandResult:
    try:
        process = subprocess.Popen(
            list(command),
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as error:
        raise VideoExtractionError("transcript command executable is missing") from error
    except OSError as error:
        raise VideoExtractionError("transcript command failed") from error

    if process_controller is not None:
        process_controller.register(process)
    stdout = bytearray()
    stderr = bytearray()
    try:
        return _read_bounded_process_output(
            process,
            stdout=stdout,
            stderr=stderr,
            timeout_seconds=timeout_seconds,
            max_stdout_bytes=max_stdout_bytes,
            max_stderr_bytes=max_stderr_bytes,
        )
    except OSError as error:
        _kill_process(process)
        raise VideoExtractionError("transcript command failed") from error
    except BaseException:
        _kill_process(process)
        raise
    finally:
        if process_controller is not None:
            process_controller.unregister(process)
        if process.stdout is not None:
            with suppress(OSError):
                process.stdout.close()
        if process.stderr is not None:
            with suppress(OSError):
                process.stderr.close()


def _read_bounded_process_output(
    process: subprocess.Popen[bytes],
    *,
    stdout: bytearray,
    stderr: bytearray,
    timeout_seconds: float,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
) -> _BoundedCommandResult:
    if process.stdout is None or process.stderr is None:
        _kill_process(process)
        raise VideoExtractionError("transcript command failed")

    stdout_fd = process.stdout.fileno()
    stderr_fd = process.stderr.fileno()
    os.set_blocking(stdout_fd, False)
    os.set_blocking(stderr_fd, False)
    streams: dict[int, tuple[str, bytearray, int]] = {
        stdout_fd: ("stdout", stdout, max_stdout_bytes),
        stderr_fd: ("stderr", stderr, max_stderr_bytes),
    }
    deadline = time.monotonic() + timeout_seconds

    while streams:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _kill_process(process)
            raise VideoExtractionError("transcript command timed out")
        ready, _, _ = select.select(
            list(streams),
            [],
            [],
            min(remaining, _POLL_INTERVAL_SECONDS),
        )
        if not ready:
            continue
        for fd in ready:
            stream_name, buffer, limit = streams[fd]
            read_size = min(_CAPTURE_CHUNK_BYTES, limit - len(buffer) + 1)
            if read_size <= 0:
                _kill_process(process)
                raise _oversized_output_error(stream_name)
            try:
                chunk = os.read(fd, read_size)
            except BlockingIOError:
                continue
            if not chunk:
                del streams[fd]
                continue
            buffer.extend(chunk)
            if len(buffer) > limit:
                _kill_process(process)
                raise _oversized_output_error(stream_name)

    return _BoundedCommandResult(
        returncode=process.wait(),
        stdout=bytes(stdout),
        stderr=bytes(stderr),
    )


def _kill_process(process: subprocess.Popen[bytes]) -> None:
    with suppress(OSError):
        if process.poll() is None:
            process.kill()
    try:
        process.wait(timeout=1)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _oversized_output_error(stream_name: str) -> VideoExtractionError:
    return VideoExtractionError(f"transcript command produced too much {stream_name}")
