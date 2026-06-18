from dataclasses import FrozenInstanceError, asdict

import pytest

from mke.adapters.video.contracts import (
    AdapterExitCode,
    VideoTranscriptionLimits,
    faster_whisper_fingerprint,
)
from mke.domain import (
    ParsedVideoTranscript,
    TranscriptExtractionResult,
    TranscriptIntakeReport,
    TranscriptionProvenance,
    VideoMediaInfo,
    VideoTranscriptSegment,
    is_recognized_video_fingerprint,
)


def _provenance(**overrides: object) -> TranscriptionProvenance:
    values: dict[str, object] = {
        "provider": "faster-whisper",
        "model": "small",
        "model_revision": "a" * 40,
        "library_version": "1.2.3",
        "device": "cpu",
        "compute_type": "int8",
        "language": "auto",
        "detected_language": "en",
        "model_source": "cache",
        "transcription_duration_ms": 250,
    }
    values.update(overrides)
    return TranscriptionProvenance(**values)  # pyright: ignore[reportArgumentType]


def _report(**overrides: object) -> TranscriptIntakeReport:
    values = asdict(_provenance())
    values["media_duration_ms"] = 1_500
    values["segment_count"] = 1
    values.update(overrides)
    return TranscriptIntakeReport(**values)  # pyright: ignore[reportArgumentType]


def test_complete_transcript_contract_is_typed_and_frozen() -> None:
    provenance = _provenance()
    parsed = ParsedVideoTranscript(
        media=VideoMediaInfo("mp4", "h264", "aac", True, 1_500),
        segments=(VideoTranscriptSegment(0, 1_000, "spoken evidence"),),
        transcription_provenance=provenance,
    )
    result = TranscriptExtractionResult(
        parsed_transcript=parsed,
        extractor_fingerprint=faster_whisper_fingerprint(provenance),
        transcript_intake_report=_report(),
    )

    assert result.segments == parsed.segments
    assert result.transcript_intake_report is not None
    assert "path" not in asdict(result.transcript_intake_report)
    assert "argv" not in asdict(result.transcript_intake_report)
    with pytest.raises(FrozenInstanceError):
        result.transcript_intake_report.model = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider", ""),
        ("model", "  "),
        ("model_revision", ""),
        ("library_version", ""),
        ("device", ""),
        ("compute_type", ""),
        ("language", "english"),
        ("detected_language", "e"),
        ("media_duration_ms", 0),
        ("transcription_duration_ms", -1),
        ("segment_count", 0),
        ("model_source", "download"),
    ],
)
def test_transcript_intake_report_rejects_invalid_values(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        _report(**{field: value})


def test_faster_whisper_fingerprint_requires_version_and_lowercase_sha256() -> None:
    valid = "faster-whisper-v1:" + ("a" * 64)
    assert is_recognized_video_fingerprint(valid)
    assert not is_recognized_video_fingerprint("faster-whisper-v1:abc")
    assert not is_recognized_video_fingerprint("faster-whisper-v1:" + ("A" * 64))
    assert not is_recognized_video_fingerprint("faster-whisper-v2:" + ("a" * 64))


def test_requested_language_changes_faster_whisper_fingerprint() -> None:
    automatic = faster_whisper_fingerprint(_provenance(language="auto"))
    english = faster_whisper_fingerprint(_provenance(language="en"))

    assert automatic != english
    assert is_recognized_video_fingerprint(automatic)
    assert is_recognized_video_fingerprint(english)


@pytest.mark.parametrize(
    "field",
    [
        "max_input_bytes",
        "max_media_duration_ms",
        "max_segment_count",
        "timeout_seconds",
        "max_stdout_bytes",
        "max_stderr_bytes",
    ],
)
def test_video_transcription_limits_must_be_positive(field: str) -> None:
    with pytest.raises(ValueError):
        VideoTranscriptionLimits(**{field: 0})  # pyright: ignore[reportArgumentType]


def test_adapter_exit_codes_are_stable() -> None:
    assert AdapterExitCode.DEPENDENCY_MISSING == 20
    assert AdapterExitCode.SCHEMA_INVALID == 50
