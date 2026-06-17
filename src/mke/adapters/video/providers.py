"""Transcript provider adapters for local video Evidence."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from mke.adapters.video.errors import VideoExtractionError
from mke.adapters.video.schema import load_transcript_json
from mke.adapters.video.transcript import extract_transcript_segments
from mke.domain import (
    LOCAL_COMMAND_VIDEO_TRANSCRIPT_FINGERPRINT,
    VIDEO_TRANSCRIPT_FINGERPRINT,
    TranscriptExtractionResult,
)


@dataclass(frozen=True)
class SidecarTranscriptProvider:
    """Default deterministic provider backed by repository sidecar JSON."""

    def extract(self, path: Path) -> TranscriptExtractionResult:
        segments = extract_transcript_segments(path)
        return TranscriptExtractionResult(
            segments=tuple(segments),
            extractor_fingerprint=VIDEO_TRANSCRIPT_FINGERPRINT,
        )


@dataclass(frozen=True)
class LocalCommandTranscriptConfig:
    argv: Sequence[str]
    timeout_seconds: float = 60.0
    max_stdout_bytes: int = 1024 * 1024
    max_stderr_bytes: int = 64 * 1024
    extractor_fingerprint: str = LOCAL_COMMAND_VIDEO_TRANSCRIPT_FINGERPRINT

    def __post_init__(self) -> None:
        if isinstance(self.argv, str) or not isinstance(self.argv, Sequence):
            raise TypeError("argv must be a non-empty sequence of strings")
        normalized = tuple(self.argv)
        if not normalized:
            raise TypeError("argv must be a non-empty sequence of strings")
        if any(not isinstance(part, str) or not part for part in normalized):
            raise TypeError("argv must contain non-empty strings")
        if normalized.count("{input}") != 1:
            raise ValueError("argv must contain exactly one {input} placeholder")
        object.__setattr__(self, "argv", normalized)


@dataclass(frozen=True)
class LocalCommandTranscriptProvider:
    config: LocalCommandTranscriptConfig

    def extract(self, path: Path) -> TranscriptExtractionResult:
        if not path.exists():
            raise VideoExtractionError("input video is missing")
        command = [
            str(path) if part == "{input}" else part
            for part in self.config.argv
        ]
        try:
            completed = subprocess.run(
                command,
                shell=False,
                capture_output=True,
                timeout=self.config.timeout_seconds,
                check=False,
            )
        except FileNotFoundError as error:
            raise VideoExtractionError("transcript command executable is missing") from error
        except subprocess.TimeoutExpired as error:
            raise VideoExtractionError("transcript command timed out") from error

        stdout = _process_bytes(completed.stdout)
        stderr = _process_bytes(completed.stderr)
        if len(stdout) > self.config.max_stdout_bytes:
            raise VideoExtractionError("transcript command produced too much stdout")
        if len(stderr) > self.config.max_stderr_bytes:
            raise VideoExtractionError("transcript command produced too much stderr")
        if completed.returncode != 0:
            raise VideoExtractionError("transcript command failed")
        try:
            text = stdout.decode("utf-8")
        except UnicodeDecodeError as error:
            raise VideoExtractionError(
                "transcript command stdout is not valid UTF-8"
            ) from error
        return TranscriptExtractionResult(
            segments=load_transcript_json(text),
            extractor_fingerprint=self.config.extractor_fingerprint,
        )


def _process_bytes(value: bytes | str | None) -> bytes:
    if value is None:
        return b""
    if isinstance(value, str):
        return value.encode("utf-8", errors="replace")
    return value
