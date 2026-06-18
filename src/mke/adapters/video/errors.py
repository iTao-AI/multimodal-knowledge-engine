"""Shared video extraction errors."""

from __future__ import annotations


class VideoExtractionError(ValueError):
    """Raised when a local video cannot produce trustworthy timestamp Evidence."""

    def __init__(
        self,
        message: str,
        *,
        problem: str = "video_ingest_failed",
        next_step: str = "fix_input_or_retry",
    ) -> None:
        super().__init__(message)
        self.problem = problem
        self.next_step = next_step
