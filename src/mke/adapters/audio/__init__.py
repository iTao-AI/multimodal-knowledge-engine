"""Internal direct-audio contracts and adapters."""

from mke.adapters.audio.contracts import AudioTranscriptionLimits, audio_extractor_fingerprint
from mke.adapters.audio.inspection import (
    AudioInspectionError,
    AudioSnapshotError,
    AudioSourceSnapshot,
    cleanup_audio_snapshot,
    parse_audio_inspection_result,
    snapshot_audio_source,
    validate_audio_inspection_request,
    verify_owned_path,
    verify_source_path,
)
from mke.adapters.audio.schema import (
    AudioTranscriptValidationError,
    parse_audio_transcript_payload,
)

__all__ = [
    "AudioInspectionError",
    "AudioSnapshotError",
    "AudioSourceSnapshot",
    "AudioTranscriptValidationError",
    "AudioTranscriptionLimits",
    "audio_extractor_fingerprint",
    "cleanup_audio_snapshot",
    "parse_audio_inspection_result",
    "parse_audio_transcript_payload",
    "snapshot_audio_source",
    "validate_audio_inspection_request",
    "verify_owned_path",
    "verify_source_path",
]
