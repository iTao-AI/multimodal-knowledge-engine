"""Shared video extraction errors."""

from __future__ import annotations


class VideoExtractionError(ValueError):
    """Raised when a local video cannot produce trustworthy timestamp Evidence."""
