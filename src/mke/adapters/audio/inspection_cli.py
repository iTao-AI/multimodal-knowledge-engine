"""Internal closed PyAV inspection child for immutable audio snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import BinaryIO, Protocol, cast

from mke.adapters.audio.inspection import (
    AudioInspectionError,
    AudioInspectionObservation,
    AudioInspectionRequest,
    AudioInspectionResult,
    _normalize_audio_profile,  # pyright: ignore[reportPrivateUsage]
    validate_audio_inspection_request,
)

_BUFFER_BYTES = 1024 * 1024


class _CodecContext(Protocol):
    name: str
    profile: str | None
    channels: int
    sample_rate: int


class _AudioStream(Protocol):
    codec_context: _CodecContext


class _Packet(Protocol):
    def decode(self) -> Iterable[object]: ...


class _ContainerFormat(Protocol):
    name: str


class _Streams(Protocol):
    audio: list[_AudioStream]
    video: list[object]
    subtitles: list[object]
    data: list[object]
    attachments: list[object]


class _Container(Protocol):
    format: _ContainerFormat
    streams: _Streams
    duration: int | None

    def demux(self, stream: _AudioStream) -> Iterable[_Packet]: ...

    def close(self) -> None: ...


def inspect_audio(request: AudioInspectionRequest) -> AudioInspectionResult:
    validated = validate_audio_inspection_request(request)
    path = Path(validated["path"])
    descriptor: int | None = None
    try:
        before = path.lstat()
        if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
            raise AudioInspectionError("inspection_identity_mismatch")
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        opened = os.fstat(descriptor)
        if _stat_identity(opened) != _stat_identity(before):
            raise AudioInspectionError("inspection_identity_mismatch")
        observed_bytes, observed_sha256 = _hash_descriptor(descriptor)
        _require_expected(validated, observed_bytes, observed_sha256)
        os.lseek(descriptor, 0, os.SEEK_SET)
        with os.fdopen(os.dup(descriptor), "rb", closefd=True) as stream:
            observation = _inspect_audio_stream(stream)
        after_bytes, after_sha256 = _hash_descriptor(descriptor)
        after = os.fstat(descriptor)
        path_after = path.lstat()
        if (
            _stat_identity(after) != _stat_identity(before)
            or _stat_identity(path_after) != _stat_identity(before)
            or after_bytes != observed_bytes
            or after_sha256 != observed_sha256
        ):
            raise AudioInspectionError("inspection_identity_mismatch")
        media = _normalize_audio_profile(
            observation,
            expected_suffix=validated["expected_suffix"],
        )
        return AudioInspectionResult(
            schema_version="mke.audio_inspection.v1",
            media={
                "container": media.container,
                "audio_codec": media.audio_codec,
                "channels": media.channels,
                "sample_rate_hz": media.sample_rate_hz,
                "duration_ms": media.duration_ms,
            },
            observed_sha256=observed_sha256,
            observed_bytes=observed_bytes,
        )
    except AudioInspectionError:
        raise
    except (OSError, ValueError) as error:
        raise AudioInspectionError("inspection_identity_mismatch") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _inspect_audio_stream(stream: BinaryIO) -> AudioInspectionObservation:
    return _inspect_container(stream)


def _inspect_container(stream: BinaryIO) -> AudioInspectionObservation:
    try:
        from importlib import import_module

        av = import_module("av")
        container = cast(_Container, av.open(stream, mode="r"))
    except ImportError as error:
        raise AudioInspectionError("inspection_dependency_missing") from error
    except Exception as error:
        raise AudioInspectionError("audio_profile_unsupported") from error
    try:
        audio_streams = tuple(container.streams.audio)
        if len(audio_streams) != 1:
            raise AudioInspectionError("audio_stream_count_invalid")
        audio_stream = audio_streams[0]
        try:
            for packet in container.demux(audio_stream):
                for _frame in packet.decode():
                    pass
        except Exception as error:
            raise AudioInspectionError("audio_profile_unsupported") from error
        codec = audio_stream.codec_context
        if container.duration is None:
            duration_seconds = float("nan")
        else:
            duration_seconds = container.duration / 1_000_000
        return AudioInspectionObservation(
            format_tokens=tuple(sorted(container.format.name.split(","))),
            audio_stream_count=len(audio_streams),
            video_stream_count=len(container.streams.video),
            subtitle_stream_count=len(container.streams.subtitles),
            data_stream_count=len(container.streams.data),
            attachment_stream_count=len(container.streams.attachments),
            audio_codec=codec.name,
            audio_profile=codec.profile,
            channels=codec.channels,
            sample_rate_hz=codec.sample_rate,
            duration_seconds=duration_seconds,
        )
    finally:
        container.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--path", required=True)
    parser.add_argument("--expected-suffix", required=True, choices=(".mp3", ".wav", ".m4a"))
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--expected-bytes", required=True, type=int)
    try:
        args = parser.parse_args(argv)
        request = validate_audio_inspection_request(
            {
                "path": args.path,
                "expected_suffix": args.expected_suffix,
                "expected_sha256": args.expected_sha256,
                "expected_bytes": args.expected_bytes,
            }
        )
        result = inspect_audio(request)
        sys.stdout.write(json.dumps(result, ensure_ascii=True, separators=(",", ":")) + "\n")
        return 0
    except AudioInspectionError as error:
        code = {
            "inspection_dependency_missing": 20,
            "audio_stream_count_invalid": 31,
            "audio_profile_unsupported": 30,
            "inspection_identity_mismatch": 50,
        }.get(str(error), 50)
        sys.stderr.write("audio inspection failed\n")
        return code
    except BaseException:
        sys.stderr.write("audio inspection failed\n")
        return 40


def _hash_descriptor(descriptor: int) -> tuple[int, str]:
    os.lseek(descriptor, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    total = 0
    while True:
        block = os.read(descriptor, _BUFFER_BYTES)
        if not block:
            break
        total += len(block)
        digest.update(block)
    return total, digest.hexdigest()


def _require_expected(request: AudioInspectionRequest, byte_count: int, digest: str) -> None:
    if byte_count != request["expected_bytes"] or digest != request["expected_sha256"]:
        raise AudioInspectionError("inspection_identity_mismatch")


def _stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


if __name__ == "__main__":
    raise SystemExit(main())
