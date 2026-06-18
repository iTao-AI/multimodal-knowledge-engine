"""Deterministic local video transcript adapter."""

from mke.adapters.video.errors import VideoExtractionError
from mke.adapters.video.providers import (
    LocalCommandTranscriptConfig,
    LocalCommandTranscriptProvider,
    SidecarTranscriptProvider,
)
from mke.adapters.video.transcript import extract_transcript_segments
from mke.domain import ParsedVideoTranscript, TranscriptExtractionResult, VideoTranscriptSegment

__all__ = [
    "SidecarTranscriptProvider",
    "LocalCommandTranscriptConfig",
    "LocalCommandTranscriptProvider",
    "TranscriptExtractionResult",
    "ParsedVideoTranscript",
    "VideoExtractionError",
    "VideoTranscriptSegment",
    "extract_transcript_segments",
]
