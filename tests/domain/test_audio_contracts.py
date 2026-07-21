from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from mke.adapters.audio.contracts import (
    AudioTranscriptionLimits,
    audio_extractor_fingerprint,
)
from mke.adapters.audio.schema import AudioTranscriptValidationError, parse_audio_transcript_payload
from mke.domain import (
    AudioMediaInfo,
    AudioTranscriptExtractionResult,
    AudioTranscriptSegment,
    ParsedAudioTranscript,
    TranscriptionProvenance,
)


def _provenance(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "provider": "faster-whisper",
        "model": "small",
        "model_revision": "a" * 40,
        "library_version": "1.2.1",
        "device": "cpu",
        "compute_type": "int8",
        "language": "auto",
        "detected_language": "en",
        "model_source": "cache",
        "transcription_duration_ms": 321,
    }
    values.update(overrides)
    return values


def _payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "format": "mke.audio_transcript.v1",
        "media": {
            "audio_codec": "aac",
            "channels": 1,
            "container": "m4a",
            "duration_ms": 1_234,
            "sample_rate_hz": 16_000,
        },
        "segments": [{"end_ms": 1_200, "start_ms": 0, "text": "cafe\u0301"}],
        "transcription": _provenance(),
    }
    values.update(overrides)
    return values


def test_audio_contract_is_typed_frozen_and_normalizes_unicode() -> None:
    parsed = parse_audio_transcript_payload(_payload())
    provenance = parsed.transcription_provenance
    assert parsed == ParsedAudioTranscript(
        media=AudioMediaInfo("m4a", "aac", 1, 16_000, 1_234),
        segments=(AudioTranscriptSegment(0, 1_200, "café"),),
        transcription_provenance=provenance,
    )
    assert provenance is not None
    result = AudioTranscriptExtractionResult(
        parsed_transcript=parsed,
        extractor_fingerprint=audio_extractor_fingerprint(provenance),
    )
    assert result.segments == parsed.segments
    with pytest.raises(FrozenInstanceError):
        result.parsed_transcript = parsed  # type: ignore[misc]


@pytest.mark.parametrize("missing", ["format", "media", "segments", "transcription"])
def test_audio_parser_rejects_missing_top_level_field(missing: str) -> None:
    payload = _payload()
    del payload[missing]
    with pytest.raises(AudioTranscriptValidationError, match="fields"):
        parse_audio_transcript_payload(payload)


def test_audio_parser_rejects_unknown_fields_at_every_level() -> None:
    payloads: list[dict[str, object]] = []
    top = _payload(extra=True)
    payloads.append(top)
    media = _payload()
    media_section = cast(dict[str, object], media["media"])
    media_section["extra"] = True
    payloads.append(media)
    segment = _payload()
    segment_section = cast(list[dict[str, object]], segment["segments"])
    segment_section[0]["extra"] = True
    payloads.append(segment)
    provenance = _payload()
    provenance_section = cast(dict[str, object], provenance["transcription"])
    provenance_section["extra"] = True
    payloads.append(provenance)

    for payload in payloads:
        with pytest.raises(AudioTranscriptValidationError, match="fields"):
            parse_audio_transcript_payload(payload)


@pytest.mark.parametrize(
    ("section", "field", "value", "match"),
    [
        ("media", "channels", True, "channels"),
        ("media", "sample_rate_hz", True, "sample rate"),
        ("media", "duration_ms", True, "duration"),
        ("segment", "start_ms", True, "integer"),
        ("segment", "end_ms", True, "integer"),
        ("transcription", "transcription_duration_ms", True, "duration"),
    ],
)
def test_audio_parser_rejects_bool_as_int(
    section: str, field: str, value: object, match: str
) -> None:
    payload = _payload()
    if section == "segment":
        segments = payload["segments"]
        assert isinstance(segments, list) and isinstance(segments[0], dict)
        segments[0][field] = value
    else:
        target = payload[section]
        assert isinstance(target, dict)
        target[field] = value
    with pytest.raises(AudioTranscriptValidationError, match=match):
        parse_audio_transcript_payload(payload)


@pytest.mark.parametrize(
    "media",
    [
        {
            "container": "mp3",
            "audio_codec": "mp3",
            "channels": 1,
            "sample_rate_hz": 8_000,
            "duration_ms": 1,
        },
        {
            "container": "wav",
            "audio_codec": "pcm_s16le",
            "channels": 2,
            "sample_rate_hz": 48_000,
            "duration_ms": 900_000,
        },
        {
            "container": "m4a",
            "audio_codec": "aac",
            "channels": 1,
            "sample_rate_hz": 16_000,
            "duration_ms": 1_234,
        },
    ],
)
def test_audio_parser_accepts_exact_supported_media_profiles(media: dict[str, object]) -> None:
    duration_ms = media["duration_ms"]
    assert isinstance(duration_ms, int)
    parsed = parse_audio_transcript_payload(
        _payload(
            media=media,
            segments=[{"start_ms": 0, "end_ms": duration_ms, "text": "bounded"}],
        )
    )
    assert parsed.media.container == media["container"]


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("container", "mp4", "profile"),
        ("audio_codec", "opus", "profile"),
        ("channels", 0, "channels"),
        ("channels", 3, "channels"),
        ("sample_rate_hz", 7_999, "sample rate"),
        ("sample_rate_hz", 48_001, "sample rate"),
        ("duration_ms", 0, "duration"),
        ("duration_ms", 900_001, "duration"),
    ],
)
def test_audio_parser_rejects_unsupported_media(field: str, value: object, match: str) -> None:
    payload = _payload()
    media = payload["media"]
    assert isinstance(media, dict)
    media[field] = value
    with pytest.raises(AudioTranscriptValidationError, match=match):
        parse_audio_transcript_payload(payload)


@pytest.mark.parametrize("field", ["container", "audio_codec"])
@pytest.mark.parametrize("value", [[], {}, None, True], ids=["list", "dict", "null", "bool"])
def test_audio_parser_rejects_non_string_media_profile_with_typed_error(
    field: str, value: object
) -> None:
    payload = _payload()
    media = payload["media"]
    assert isinstance(media, dict)
    media[field] = value

    with pytest.raises(AudioTranscriptValidationError, match="profile"):
        parse_audio_transcript_payload(payload)


@pytest.mark.parametrize(
    ("segments", "match"),
    [
        ([], "at least one"),
        ([{"start_ms": 0, "end_ms": 10, "text": " "}], "text"),
        ([{"start_ms": -1, "end_ms": 10, "text": "bad"}], "increasing"),
        ([{"start_ms": 10, "end_ms": 10, "text": "bad"}], "increasing"),
        ([{"start_ms": 0.5, "end_ms": 10, "text": "bad"}], "integer"),
        ([{"start_ms": 0, "end_ms": float("inf"), "text": "bad"}], "integer"),
        ([{"start_ms": 0, "end_ms": 1_235, "text": "bad"}], "media duration"),
        (
            [
                {"start_ms": 0, "end_ms": 800, "text": "first"},
                {"start_ms": 700, "end_ms": 1_000, "text": "overlap"},
            ],
            "sorted",
        ),
        (
            [
                {"start_ms": 500, "end_ms": 1_000, "text": "first"},
                {"start_ms": 0, "end_ms": 400, "text": "duplicate order"},
            ],
            "sorted",
        ),
    ],
)
def test_audio_parser_rejects_invalid_segments(
    segments: list[dict[str, object]], match: str
) -> None:
    with pytest.raises(AudioTranscriptValidationError, match=match):
        parse_audio_transcript_payload(_payload(segments=segments))


def test_audio_parser_enforces_segment_limit() -> None:
    payload = _payload(
        media={
            "audio_codec": "aac",
            "channels": 1,
            "container": "m4a",
            "duration_ms": 20,
            "sample_rate_hz": 16_000,
        },
        segments=[
            {"start_ms": 0, "end_ms": 10, "text": "first"},
            {"start_ms": 10, "end_ms": 20, "text": "second"},
        ],
    )
    with pytest.raises(AudioTranscriptValidationError, match="segment limit"):
        parse_audio_transcript_payload(
            payload, limits=AudioTranscriptionLimits(max_segment_count=1)
        )


def test_audio_parser_accepts_explicit_null_provenance() -> None:
    parsed = parse_audio_transcript_payload(_payload(transcription=None))
    assert parsed.transcription_provenance is None


def test_audio_fingerprint_is_canonical_and_audio_specific() -> None:
    provenance = TranscriptionProvenance(**_provenance())  # pyright: ignore[reportArgumentType]
    fingerprint = audio_extractor_fingerprint(provenance)
    assert (
        fingerprint
        == "faster-whisper-audio-v1:"
        "604a22cb2adc43ea170047b7d92c2fa672afd4e47c7b06e4f6c4ddf217098ff5"
    )
