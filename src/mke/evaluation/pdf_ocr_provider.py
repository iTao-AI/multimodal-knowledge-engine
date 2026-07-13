"""Strict isolated provider child protocol for PDF OCR Phase 0."""

from __future__ import annotations

import json
import math
import os
import re
import signal
import stat
import subprocess
import threading
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn, cast

from mke.adapters.video.process import ActiveProcessController, ProcessOperationId

_READ_CHUNK_BYTES = 8192
_POLL_SECONDS = 0.01
_FIXED_PLACEHOLDERS = ("{input}", "{output}", "{page_number}")
_PROVIDERS = frozenset(
    {
        "apple-vision-local-v1",
        "paddleocr-vl-1.6-cpu-spike-v1",
        "ppocrv6-medium-cpu-spike-v1",
    }
)
_PROFILE_RE = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*\Z")


@dataclass(frozen=True)
class ProviderCommand:
    argv: tuple[str, ...]
    provider: str
    profile: str
    max_stdout_bytes: int = 64 * 1024
    max_stderr_bytes: int = 256 * 1024
    max_result_bytes: int = 8 * 1024 * 1024
    timeout_seconds: float = 180.0

    def __post_init__(self) -> None:
        if not self.argv or any(type(item) is not str or not item for item in self.argv):
            raise ValueError("provider argv must contain non-empty strings")
        if any(self.argv.count(placeholder) != 1 for placeholder in _FIXED_PLACEHOLDERS):
            raise ValueError("provider argv must contain the fixed placeholders exactly once")
        if self.provider not in _PROVIDERS:
            raise ValueError("provider identifier is invalid")
        if _PROFILE_RE.fullmatch(self.profile) is None:
            raise ValueError("provider profile is invalid")
        limits = (self.max_stdout_bytes, self.max_stderr_bytes, self.max_result_bytes)
        if any(type(value) is not int or value <= 0 for value in limits):
            raise ValueError("provider output limits must be positive integers")
        if (
            isinstance(self.timeout_seconds, bool)
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("provider timeout must be finite and positive")


class PdfOcrProviderError(RuntimeError):
    def __init__(
        self,
        *,
        problem: str,
        cause: str,
        next_step: str,
        provider: str,
    ) -> None:
        super().__init__(f"{problem}: {cause}")
        self.problem = problem
        self.cause = cause
        self.next_step = next_step
        self.provider = provider


@dataclass(frozen=True)
class OcrEvalLine:
    text: str
    confidence: float | None
    box: tuple[float, float, float, float]


@dataclass(frozen=True)
class OcrEvalPageResult:
    schema: str
    provider: str
    profile: str
    page_number: int
    lines: tuple[OcrEvalLine, ...]
    normalized_text: str
    duration_ms: int


class _ProcessGroupPopen(subprocess.Popen[bytes]):
    def kill(self) -> None:
        if os.name == "posix" and self.poll() is None:
            try:
                os.killpg(os.getpgid(self.pid), signal.SIGKILL)
                return
            except (OSError, ProcessLookupError):
                pass
        super().kill()


@dataclass
class _PipeCapture:
    limit: int
    data: bytearray
    exceeded: threading.Event


def run_provider(
    command: ProviderCommand,
    *,
    image_path: Path,
    page_number: int,
    output_root: Path,
    process_controller: ActiveProcessController | None = None,
    operation_id: ProcessOperationId | None = None,
) -> OcrEvalPageResult:
    if image_path.is_symlink() or not image_path.is_file():
        _error(command, "pdf_ocr_input_invalid", "OCR page input is invalid", "inspect_pdf_page")
    if type(page_number) is not int or page_number <= 0:
        _error(
            command,
            "pdf_ocr_result_invalid",
            "OCR page identity is invalid",
            "inspect_pdf_page",
        )
    try:
        output_root.mkdir(mode=0o700, parents=True, exist_ok=False)
        output_path = output_root / "result.json"
        descriptor = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        output_identity = output_path.stat()
    except OSError as error:
        raise PdfOcrProviderError(
            problem="pdf_ocr_process_failed",
            cause="OCR child output is unavailable",
            next_step="inspect_pdf_ocr_run",
            provider=command.provider,
        ) from error
    substitutions = {
        "{input}": str(image_path),
        "{output}": str(output_path),
        "{page_number}": str(page_number),
    }
    argv = tuple(substitutions.get(item, item) for item in command.argv)
    try:
        process = _start_process(argv)
    except (OSError, ValueError) as error:
        raise PdfOcrProviderError(
            problem="pdf_ocr_process_failed",
            cause="PDF OCR process failed",
            next_step="inspect_pdf_ocr_run",
            provider=command.provider,
        ) from error
    registered = False
    try:
        if process_controller is not None:
            try:
                process_controller.register(process, operation_id=operation_id)
                registered = True
            except Exception as error:
                _terminate(process)
                _close_streams(process)
                raise PdfOcrProviderError(
                    problem="pdf_ocr_process_failed",
                    cause="PDF OCR process failed",
                    next_step="inspect_pdf_ocr_run",
                    provider=command.provider,
                ) from error
        returncode, stdout_exceeded, stderr_exceeded = _wait_bounded(
            process,
            timeout_seconds=float(command.timeout_seconds),
            max_stdout_bytes=command.max_stdout_bytes,
            max_stderr_bytes=command.max_stderr_bytes,
            command=command,
        )
        if stdout_exceeded or stderr_exceeded:
            _error(
                command,
                "pdf_ocr_output_limit_exceeded",
                "PDF OCR process output exceeded the configured limit",
                "reduce_pdf_ocr_input",
            )
        if returncode != 0:
            _error(
                command,
                "pdf_ocr_process_failed",
                "PDF OCR process failed",
                "inspect_pdf_ocr_run",
            )
        return _load_result(
            command,
            output_path=output_path,
            output_identity=output_identity,
            page_number=page_number,
        )
    finally:
        if registered and process_controller is not None:
            process_controller.unregister(process, operation_id=operation_id)
        _close_streams(process)


def _start_process(argv: tuple[str, ...]) -> subprocess.Popen[bytes]:
    if os.name == "posix":
        return _ProcessGroupPopen(
            list(argv),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=True,
        )
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return _ProcessGroupPopen(
        list(argv),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        creationflags=creationflags,
    )


def _wait_bounded(
    process: subprocess.Popen[bytes],
    *,
    timeout_seconds: float,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
    command: ProviderCommand,
) -> tuple[int, bool, bool]:
    if process.stdout is None or process.stderr is None:
        _terminate(process)
        _error(
            command,
            "pdf_ocr_process_failed",
            "PDF OCR process failed",
            "inspect_pdf_ocr_run",
        )
    stdout = _PipeCapture(max_stdout_bytes, bytearray(), threading.Event())
    stderr = _PipeCapture(max_stderr_bytes, bytearray(), threading.Event())
    threads = (
        threading.Thread(target=_read_pipe, args=(process.stdout, stdout), daemon=True),
        threading.Thread(target=_read_pipe, args=(process.stderr, stderr), daemon=True),
    )
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + timeout_seconds
    returncode: int | None = None
    while returncode is None:
        if stdout.exceeded.is_set() or stderr.exceeded.is_set():
            _terminate(process)
            returncode = process.poll()
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _terminate(process)
            for thread in threads:
                thread.join(timeout=1)
            _error(
                command,
                "pdf_ocr_timeout",
                "PDF OCR operation timed out",
                "retry_smaller_pdf",
            )
        try:
            returncode = process.wait(timeout=min(_POLL_SECONDS, remaining))
        except subprocess.TimeoutExpired:
            continue
    for thread in threads:
        thread.join(timeout=1)
    if any(thread.is_alive() for thread in threads):
        _terminate(process)
        _error(
            command,
            "pdf_ocr_process_failed",
            "PDF OCR process failed",
            "inspect_pdf_ocr_run",
        )
    return int(returncode if returncode is not None else process.wait()), (
        stdout.exceeded.is_set()
    ), stderr.exceeded.is_set()


def _read_pipe(stream: Any, capture: _PipeCapture) -> None:
    try:
        while chunk := stream.read(_READ_CHUNK_BYTES):
            remaining = capture.limit - len(capture.data)
            if remaining > 0:
                capture.data.extend(chunk[:remaining])
            if len(chunk) > remaining:
                capture.exceeded.set()
    except (OSError, ValueError):
        capture.exceeded.set()


def _terminate(process: subprocess.Popen[bytes]) -> None:
    try:
        if process.poll() is None:
            process.kill()
    except OSError:
        pass
    try:
        process.wait(timeout=1)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _close_streams(process: subprocess.Popen[bytes]) -> None:
    for stream in (process.stdout, process.stderr):
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass


def _load_result(
    command: ProviderCommand,
    *,
    output_path: Path,
    output_identity: os.stat_result,
    page_number: int,
) -> OcrEvalPageResult:
    try:
        if output_path.is_symlink():
            _invalid(command)
        current = output_path.stat()
        if not stat.S_ISREG(current.st_mode) or (
            current.st_dev,
            current.st_ino,
        ) != (output_identity.st_dev, output_identity.st_ino):
            _invalid(command)
        if current.st_size > command.max_result_bytes:
            _error(
                command,
                "pdf_ocr_output_limit_exceeded",
                "PDF OCR result exceeded the configured limit",
                "reduce_pdf_ocr_input",
            )
        raw = output_path.read_bytes()
    except PdfOcrProviderError:
        raise
    except OSError as error:
        raise PdfOcrProviderError(
            problem="pdf_ocr_result_invalid",
            cause="PDF OCR result schema is invalid",
            next_step="report_pdf_ocr_runtime_issue",
            provider=command.provider,
        ) from error
    if not raw:
        _invalid(command)
    try:
        value: object = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise PdfOcrProviderError(
            problem="pdf_ocr_result_invalid",
            cause="PDF OCR result schema is invalid",
            next_step="report_pdf_ocr_runtime_issue",
            provider=command.provider,
        ) from error
    if not isinstance(value, dict):
        _invalid(command)
    payload = cast(dict[str, object], value)
    _exact_keys(
        command,
        payload,
        {"schema", "provider", "profile", "page_number", "lines", "normalized_text", "duration_ms"},
    )
    if (
        payload["schema"] != "mke.pdf_ocr_eval_result.v1"
        or payload["provider"] != command.provider
        or payload["profile"] != command.profile
        or payload["page_number"] != page_number
    ):
        _invalid(command)
    raw_lines = payload["lines"]
    if not isinstance(raw_lines, list) or not raw_lines:
        _invalid(command)
    lines = tuple(_line(command, item) for item in cast(list[object], raw_lines))
    normalized = _normalize_line_join(tuple(item.text for item in lines))
    if payload["normalized_text"] != normalized:
        _invalid(command)
    duration = payload["duration_ms"]
    if isinstance(duration, bool) or not isinstance(duration, int) or duration < 0:
        _invalid(command)
    return OcrEvalPageResult(
        schema="mke.pdf_ocr_eval_result.v1",
        provider=command.provider,
        profile=command.profile,
        page_number=page_number,
        lines=lines,
        normalized_text=normalized,
        duration_ms=duration,
    )


def _line(command: ProviderCommand, value: object) -> OcrEvalLine:
    if not isinstance(value, dict):
        _invalid(command)
    payload = cast(dict[str, object], value)
    _exact_keys(command, payload, {"text", "confidence", "box"})
    text = payload["text"]
    if not isinstance(text, str) or not text.strip() or len(text) > 100_000:
        _invalid(command)
    normalized_text = unicodedata.normalize("NFC", text.strip())
    confidence = payload["confidence"]
    if confidence is None:
        if command.provider != "apple-vision-local-v1":
            _invalid(command)
        normalized_confidence = None
    elif (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not math.isfinite(confidence)
        or not 0 <= confidence <= 1
    ):
        _invalid(command)
    else:
        normalized_confidence = float(confidence)
    raw_box = payload["box"]
    if not isinstance(raw_box, list):
        _invalid(command)
    box_items = cast(list[object], raw_box)
    if len(box_items) != 4:
        _invalid(command)
    box_values: list[float] = []
    for item in box_items:
        if (
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not math.isfinite(item)
            or not 0 <= item <= 1
        ):
            _invalid(command)
        box_values.append(float(item))
    box = (box_values[0], box_values[1], box_values[2], box_values[3])
    if box[2] < box[0] or box[3] < box[1]:
        _invalid(command)
    return OcrEvalLine(normalized_text, normalized_confidence, box)


def _normalize_line_join(lines: tuple[str, ...]) -> str:
    return "\n".join(
        re.sub(r"[^\S\n]+", " ", unicodedata.normalize("NFC", line)).strip()
        for line in lines
    )


def _exact_keys(
    command: ProviderCommand,
    payload: dict[str, object],
    expected: set[str],
) -> None:
    if set(payload) != expected:
        _invalid(command)


def _invalid(command: ProviderCommand) -> NoReturn:
    _error(
        command,
        "pdf_ocr_result_invalid",
        "PDF OCR result schema is invalid",
        "report_pdf_ocr_runtime_issue",
    )


def _error(
    command: ProviderCommand,
    problem: str,
    cause: str,
    next_step: str,
) -> NoReturn:
    raise PdfOcrProviderError(
        problem=problem,
        cause=cause,
        next_step=next_step,
        provider=command.provider,
    )
