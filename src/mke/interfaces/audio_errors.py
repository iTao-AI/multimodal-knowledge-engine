"""Operation-local safe causes for direct-audio ingest interfaces."""

DIRECT_AUDIO_SAFE_CAUSES = frozenset(
    {
        "input path must exist and be readable",
        "input path must be a regular file and not a symlink",
        "input path changed during validation",
        "audio input is empty",
        "direct audio requires faster-whisper owner",
        "direct audio supervision is not configured",
        "direct audio runtime is supported only on Darwin arm64",
        "direct audio owner capacity is busy",
        "audio profile is unsupported",
        "audio input exceeds supported limits",
        "audio source identity changed during intake",
        "audio inspection timed out",
        "audio inspection failed",
        "audio intake cleanup failed",
        "audio file must contain one audio stream",
        "audio transcript must contain at least one segment",
        "audio transcript schema validation failed",
        "audio publication failed",
        "supported suffixes are .pdf, .mp4, .mp3, .wav, and .m4a",
    }
)

__all__ = ["DIRECT_AUDIO_SAFE_CAUSES"]
