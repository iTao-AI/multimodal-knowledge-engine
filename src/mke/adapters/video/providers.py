"""Transcript provider adapters for local video Evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mke.adapters.video.transcript import extract_transcript_segments
from mke.domain import (
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
