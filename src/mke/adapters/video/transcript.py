"""Sidecar-backed transcript extraction for the deterministic local video evidence path."""

from __future__ import annotations

from pathlib import Path

from mke.adapters.video.errors import VideoExtractionError
from mke.adapters.video.schema import load_transcript_json
from mke.domain import VideoTranscriptSegment

_SIDECAR_SUFFIX = ".mke-transcript.json"


def extract_transcript_segments(path: Path) -> list[VideoTranscriptSegment]:
    """Read deterministic timestamp transcript segments for a local video."""
    if not path.exists():
        raise VideoExtractionError("input video is missing")
    sidecar = path.with_suffix(path.suffix + _SIDECAR_SUFFIX)
    if not sidecar.exists():
        raise VideoExtractionError("video transcript sidecar is missing")
    return list(load_transcript_json(sidecar.read_text()).segments)
