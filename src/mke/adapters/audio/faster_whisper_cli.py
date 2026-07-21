"""Internal cache-only faster-whisper child for immutable audio snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

from mke.adapters.video.contracts import AdapterExitCode
from mke.adapters.video.faster_whisper import (
    AdapterProtocolError,
    VersionedWhisperModelFactory,
    load_whisper_runtime,
    transcribe_cached_media,
)
from mke.domain import (
    AudioMediaInfo,
    AudioTranscriptSegment,
    ParsedAudioTranscript,
    TranscriptionProvenance,
)
from mke.runtime import FasterWhisperTranscriptionConfig

_BUFFER_BYTES = 1024 * 1024


def transcribe_audio(
    *,
    path: Path,
    expected_sha256: str,
    expected_bytes: int,
    media: AudioMediaInfo,
    config: FasterWhisperTranscriptionConfig,
) -> ParsedAudioTranscript:
    try:
        raw_factory, library_version = load_whisper_runtime()
    except ImportError as error:
        raise AdapterProtocolError(AdapterExitCode.DEPENDENCY_MISSING) from error
    descriptor: int | None = None
    try:
        before = path.lstat()
        if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
            raise AdapterProtocolError(AdapterExitCode.SCHEMA_INVALID)
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        opened = os.fstat(descriptor)
        if _stat_identity(opened) != _stat_identity(before):
            raise AdapterProtocolError(AdapterExitCode.SCHEMA_INVALID)
        observed_bytes, observed_sha256 = _hash_descriptor(descriptor)
        if observed_bytes != expected_bytes or observed_sha256 != expected_sha256:
            raise AdapterProtocolError(AdapterExitCode.SCHEMA_INVALID)
        os.lseek(descriptor, 0, os.SEEK_SET)
        with os.fdopen(os.dup(descriptor), "rb", closefd=True) as stream:
            normalized, provenance = transcribe_cached_media(
                stream,
                config=config,
                model_factory=VersionedWhisperModelFactory(raw_factory, library_version),
            )
        after_bytes, after_sha256 = _hash_descriptor(descriptor)
        after = os.fstat(descriptor)
        path_after = path.lstat()
        if (
            _stat_identity(after) != _stat_identity(before)
            or _stat_identity(path_after) != _stat_identity(before)
            or after_bytes != observed_bytes
            or after_sha256 != observed_sha256
        ):
            raise AdapterProtocolError(AdapterExitCode.SCHEMA_INVALID)
        if any(segment.end_ms > media.duration_ms for segment in normalized):
            raise AdapterProtocolError(AdapterExitCode.SCHEMA_INVALID)
        return ParsedAudioTranscript(
            media=media,
            segments=tuple(
                AudioTranscriptSegment(segment.start_ms, segment.end_ms, segment.text)
                for segment in normalized
            ),
            transcription_provenance=provenance,
        )
    except AdapterProtocolError:
        raise
    except OSError as error:
        raise AdapterProtocolError(AdapterExitCode.SCHEMA_INVALID) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--path", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--expected-bytes", required=True, type=int)
    parser.add_argument("--container", required=True, choices=("mp3", "wav", "m4a"))
    parser.add_argument("--audio-codec", required=True, choices=("mp3", "pcm_s16le", "aac"))
    parser.add_argument("--channels", required=True, type=int)
    parser.add_argument("--sample-rate-hz", required=True, type=int)
    parser.add_argument("--duration-ms", required=True, type=int)
    parser.add_argument("--model", default="small")
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--language", default="auto")
    parser.add_argument("--cache-dir")
    try:
        args = parser.parse_args(argv)
        media = AudioMediaInfo(
            args.container,
            args.audio_codec,
            args.channels,
            args.sample_rate_hz,
            args.duration_ms,
        )
        config = FasterWhisperTranscriptionConfig(
            model=args.model,
            model_revision=args.model_revision,
            device=args.device,
            compute_type=args.compute_type,
            language=args.language,
            cache_dir=Path(args.cache_dir) if args.cache_dir is not None else None,
        )
        parsed = transcribe_audio(
            path=Path(args.path),
            expected_sha256=args.expected_sha256,
            expected_bytes=args.expected_bytes,
            media=media,
            config=config,
        )
        sys.stdout.write(
            json.dumps(_serialize_transcript(parsed), ensure_ascii=True, separators=(",", ":"))
            + "\n"
        )
        return 0
    except AdapterProtocolError as error:
        sys.stderr.write("audio transcription failed\n")
        return int(error.exit_code)
    except (TypeError, ValueError):
        sys.stderr.write("audio transcription failed\n")
        return int(AdapterExitCode.SCHEMA_INVALID)
    except BaseException:
        sys.stderr.write("audio transcription failed\n")
        return int(AdapterExitCode.TRANSCRIPTION_FAILED)


def _serialize_transcript(parsed: ParsedAudioTranscript) -> dict[str, object]:
    provenance = parsed.transcription_provenance
    if provenance is None:
        raise AdapterProtocolError(AdapterExitCode.SCHEMA_INVALID)
    return {
        "format": "mke.audio_transcript.v1",
        "media": {
            "container": parsed.media.container,
            "audio_codec": parsed.media.audio_codec,
            "channels": parsed.media.channels,
            "sample_rate_hz": parsed.media.sample_rate_hz,
            "duration_ms": parsed.media.duration_ms,
        },
        "segments": [
            {"start_ms": item.start_ms, "end_ms": item.end_ms, "text": item.text}
            for item in parsed.segments
        ],
        "transcription": _serialize_provenance(provenance),
    }


def _serialize_provenance(value: TranscriptionProvenance) -> dict[str, object]:
    return {
        "provider": value.provider,
        "model": value.model,
        "model_revision": value.model_revision,
        "library_version": value.library_version,
        "device": value.device,
        "compute_type": value.compute_type,
        "language": value.language,
        "detected_language": value.detected_language,
        "model_source": value.model_source,
        "transcription_duration_ms": value.transcription_duration_ms,
    }


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
