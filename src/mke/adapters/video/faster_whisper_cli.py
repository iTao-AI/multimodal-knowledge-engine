"""Package-owned subprocess entrypoint for faster-whisper transcription."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from mke.adapters.video.contracts import AdapterExitCode, VideoTranscriptionLimits
from mke.adapters.video.faster_whisper import AdapterProtocolError, transcribe_media
from mke.domain import ParsedVideoTranscript
from mke.runtime import (
    DEFAULT_MODEL_REVISION,
    FasterWhisperTranscriptionConfig,
)

logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mke-transcribe-faster-whisper")
    parser.add_argument("input", type=Path)
    parser.add_argument("--model", default="small")
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--language", default="auto")
    parser.add_argument("--model-cache", type=Path)
    parser.add_argument("--max-input-bytes", type=int, default=100 * 1024 * 1024)
    parser.add_argument("--max-media-duration-ms", type=int, default=900_000)
    parser.add_argument("--max-segment-count", type=int, default=10_000)
    args = parser.parse_args(argv)
    try:
        config = FasterWhisperTranscriptionConfig(
            model=args.model,
            model_revision=args.model_revision,
            device=args.device,
            compute_type=args.compute_type,
            language=args.language,
            cache_dir=args.model_cache,
            limits=VideoTranscriptionLimits(
                max_input_bytes=args.max_input_bytes,
                max_media_duration_ms=args.max_media_duration_ms,
                max_segment_count=args.max_segment_count,
            ),
        )
        parsed = transcribe_media(args.input, config)
    except AdapterProtocolError as error:
        logger.error("adapter_failed exit_code=%s", int(error.exit_code))
        return int(error.exit_code)
    except (TypeError, ValueError):
        logger.error("adapter_configuration_invalid")
        return int(AdapterExitCode.SCHEMA_INVALID)
    except Exception:
        logger.exception("adapter_unexpected_failure")
        return int(AdapterExitCode.TRANSCRIPTION_FAILED)
    print(json.dumps(_transcript_payload(parsed), separators=(",", ":")))
    return 0


def console_main() -> int:
    return main(sys.argv[1:])


def _transcript_payload(parsed: ParsedVideoTranscript) -> dict[str, object]:
    provenance = parsed.transcription_provenance
    if provenance is None:
        raise ValueError("first-party transcript requires provenance")
    return {
        "format": "mke.video_transcript.v1",
        "media": {
            "container": parsed.media.container,
            "video_codec": parsed.media.video_codec,
            "audio_codec": parsed.media.audio_codec,
            "has_audio": parsed.media.has_audio,
            "duration_ms": parsed.media.duration_ms,
        },
        "transcription": {
            "provider": provenance.provider,
            "model": provenance.model,
            "model_revision": provenance.model_revision,
            "library_version": provenance.library_version,
            "device": provenance.device,
            "compute_type": provenance.compute_type,
            "language": provenance.language,
            "detected_language": provenance.detected_language,
            "model_source": provenance.model_source,
            "transcription_duration_ms": provenance.transcription_duration_ms,
        },
        "segments": [
            {"start_ms": item.start_ms, "end_ms": item.end_ms, "text": item.text}
            for item in parsed.segments
        ],
    }


if __name__ == "__main__":
    raise SystemExit(console_main())
