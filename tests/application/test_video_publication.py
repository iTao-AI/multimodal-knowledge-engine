import json
from dataclasses import replace
from pathlib import Path

import pytest

from mke.application import KnowledgeEngine, VideoIngestError
from mke.domain import (
    ActivationResult,
    CandidateEvidence,
    FailurePoint,
    RunEventType,
    RunManifest,
    RunState,
    RunTransitionError,
    TranscriptExtractionResult,
    TranscriptIntakeReport,
)
from tests.application.test_video_provider_injection import (
    FailingTranscriptProvider,
    FakeFasterWhisperProvider,
)
from tests.conftest import PDF_FIXTURES, VIDEO_FIXTURES


def test_video_ingest_publishes_timestamp_evidence_to_active_search(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    result = engine.ingest_video(VIDEO_FIXTURES / "short-audio.mp4")

    assert result.run_state == RunState.PUBLISHED
    assert result.evidence_count == 2
    matches = engine.search("introduces")
    assert [
        (match.locator_kind, match.locator_start, match.locator_end, match.text)
        for match in matches
    ] == [
        (
            "timestamp_ms",
            0,
            1200,
            "Video evidence introduces timestamp search.",
        )
    ]


def test_normal_video_ingest_keeps_recognized_video_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    observed: list[RunManifest] = []
    persist = engine._store.persist_validated_candidate  # pyright: ignore[reportPrivateUsage]

    def capture_manifest(
        run_id: str,
        evidence: list[CandidateEvidence],
        manifest: RunManifest,
        *,
        failure_point: FailurePoint | None = None,
    ) -> None:
        observed.append(manifest)
        persist(run_id, evidence, manifest, failure_point=failure_point)

    monkeypatch.setattr(
        engine._store,  # pyright: ignore[reportPrivateUsage]
        "persist_validated_candidate",
        capture_manifest,
    )

    engine.ingest_video(VIDEO_FIXTURES / "short-audio.mp4")

    assert len(observed) == 1
    assert observed[0].extractor_fingerprint == "builtin-video-transcript-v1"
    assert observed[0].required_stages == ("candidate_evidence", "video_transcription")


def test_pdf_and_video_share_active_search_projection(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
    engine.ingest_video(VIDEO_FIXTURES / "short-audio.mp4")

    assert [match.page_number for match in engine.search("trustworthy")] == [1]
    video_matches = engine.search("spoken timestamp proof")
    assert [
        (match.locator_kind, match.locator_start, match.locator_end)
        for match in video_matches
    ] == [
        ("timestamp_ms", 1200, 2200)
    ]


@pytest.mark.parametrize(
    ("sidecar_payload", "match"),
    [
        (
            {
                "format": "mke.video_transcript.v1",
                "media": {
                    "container": "mp4",
                    "video_codec": "h264",
                    "audio_codec": "aac",
                    "has_audio": False,
                    "duration_ms": 1000,
                },
                "segments": [{"start_ms": 0, "end_ms": 1000, "text": "missing audio"}],
            },
            "audio",
        ),
        (
            {
                "format": "mke.video_transcript.v1",
                "media": {
                    "container": "webm",
                    "video_codec": "vp9",
                    "audio_codec": "opus",
                    "has_audio": True,
                    "duration_ms": 1000,
                },
                "segments": [{"start_ms": 0, "end_ms": 1000, "text": "unsupported"}],
            },
            "unsupported codec",
        ),
        (
            {
                "format": "mke.video_transcript.v1",
                "media": {
                    "container": "mp4",
                    "video_codec": "h264",
                    "audio_codec": "aac",
                    "has_audio": True,
                    "duration_ms": 1000,
                },
                "transcription_error": "provider failed",
                "segments": [],
            },
            "transcription failed",
        ),
        (
            {
                "format": "mke.video_transcript.v1",
                "media": {
                    "container": "mp4",
                    "video_codec": "h264",
                    "audio_codec": "aac",
                    "has_audio": True,
                    "duration_ms": 1000,
                },
                "segments": [
                    {"start_ms": 0, "end_ms": 800, "text": "first"},
                    {"start_ms": 700, "end_ms": 1000, "text": "overlap"},
                ],
            },
            "stable timestamp",
        ),
    ],
)
def test_video_failures_do_not_change_active_pdf_search(
    tmp_path: Path, sidecar_payload: dict[str, object], match: str
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
    before = [match.text for match in engine.search("trustworthy")]

    video = tmp_path / "bad.mp4"
    video.write_bytes(b"fake mp4 bytes")
    video.with_suffix(video.suffix + ".mke-transcript.json").write_text(json.dumps(sidecar_payload))

    with pytest.raises(VideoIngestError, match=match):
        engine.ingest_video(video)

    assert [match.text for match in engine.search("trustworthy")] == before


@pytest.mark.parametrize(
    "failure_stage",
    [
        "run_start",
        "provider",
        "schema",
        "report_mismatch",
        "fingerprint_mismatch",
        "candidate",
        "activation",
        "report_insert",
    ],
)
def test_video_lifecycle_failure_marks_run_failed_and_preserves_active_search(
    tmp_path: Path,
    failure_stage: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    engine.ingest_video(VIDEO_FIXTURES / "short-audio.mp4")
    before = [match.text for match in engine.search("timestamp proof")]
    provider = FakeFasterWhisperProvider()
    monkeypatch.setattr(engine, "_transcript_provider", provider)

    if failure_stage == "run_start":
        def fail_run_start(*args: object, **kwargs: object) -> None:
            raise RuntimeError("run start failed")

        monkeypatch.setattr(
            engine._store,  # pyright: ignore[reportPrivateUsage]
            "mark_run_running",
            fail_run_start,
        )
    elif failure_stage == "provider":
        monkeypatch.setattr(engine, "_transcript_provider", FailingTranscriptProvider())
    elif failure_stage == "schema":
        original_extract = provider.extract

        def invalid_schema(path: Path) -> object:
            result = original_extract(path)
            return type(result)(
                parsed_transcript=result.parsed_transcript,
                extractor_fingerprint="unrecognized-provider",
                transcript_intake_report=result.transcript_intake_report,
            )

        monkeypatch.setattr(provider, "extract", invalid_schema)
    elif failure_stage == "report_mismatch":
        original_extract = provider.extract

        def mismatched_report(path: Path) -> TranscriptExtractionResult:
            result = original_extract(path)
            assert result.transcript_intake_report is not None
            return replace(
                result,
                transcript_intake_report=replace(
                    result.transcript_intake_report,
                    segment_count=2,
                ),
            )

        monkeypatch.setattr(provider, "extract", mismatched_report)
    elif failure_stage == "fingerprint_mismatch":
        original_extract = provider.extract

        def mismatched_fingerprint(path: Path) -> TranscriptExtractionResult:
            return replace(
                original_extract(path),
                extractor_fingerprint="faster-whisper-v1:" + ("b" * 64),
            )

        monkeypatch.setattr(provider, "extract", mismatched_fingerprint)
    elif failure_stage == "candidate":
        def fail_candidate(*args: object, **kwargs: object) -> None:
            raise RuntimeError("candidate persistence failed")

        monkeypatch.setattr(
            engine._store,  # pyright: ignore[reportPrivateUsage]
            "persist_validated_candidate",
            fail_candidate,
        )
    elif failure_stage == "activation":
        def fail_activation(*args: object, **kwargs: object) -> None:
            raise RuntimeError("activation failed")

        monkeypatch.setattr(
            engine._store,  # pyright: ignore[reportPrivateUsage]
            "activate_publication",
            fail_activation,
        )
    elif failure_stage == "report_insert":
        def fail_report_insert(*args: object, **kwargs: object) -> None:
            raise RuntimeError("report insert failed")

        monkeypatch.setattr(
            engine._store,  # pyright: ignore[reportPrivateUsage]
            "_insert_transcript_intake_report",
            fail_report_insert,
        )

    with pytest.raises(VideoIngestError) as exc_info:
        engine.ingest_video(VIDEO_FIXTURES / "short-audio.mp4")

    assert exc_info.value.run_id is not None
    expected_state = (
        RunState.VALIDATED
        if failure_stage in {"activation", "report_insert"}
        else RunState.FAILED
    )
    assert engine.get_run(exc_info.value.run_id).state == expected_state
    assert engine.get_transcript_intake_report(exc_info.value.run_id) is None
    assert [match.text for match in engine.search("timestamp proof")] == before
    assert engine.search("faster whisper") == []


def test_superseded_video_ingest_does_not_expose_successful_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    engine.ingest_video(VIDEO_FIXTURES / "short-audio.mp4")
    before = [match.text for match in engine.search("timestamp proof")]
    monkeypatch.setattr(engine, "_transcript_provider", FakeFasterWhisperProvider())
    original_activate = engine._store.activate_publication  # pyright: ignore[reportPrivateUsage]

    def supersede_before_activation(
        run_id: str,
        failure_point: FailurePoint | None = None,
        *,
        transcript_intake_report: TranscriptIntakeReport | None = None,
    ) -> ActivationResult:
        run = engine.get_run(run_id)
        engine.create_run(run.source_id)
        return original_activate(
            run_id,
            failure_point,
            transcript_intake_report=transcript_intake_report,
        )

    monkeypatch.setattr(
        engine._store,  # pyright: ignore[reportPrivateUsage]
        "activate_publication",
        supersede_before_activation,
    )

    result = engine.ingest_video(VIDEO_FIXTURES / "short-audio.mp4")

    assert result.run_state == RunState.SUPERSEDED
    assert result.transcript_intake_report is None
    assert engine.get_transcript_intake_report(result.run_id) is None
    assert [match.text for match in engine.search("timestamp proof")] == before


def test_video_final_activation_cas_failure_preserves_active_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    engine.ingest_video(VIDEO_FIXTURES / "short-audio.mp4")
    before_search = engine.search("timestamp proof")
    before_ask = engine.ask("What does the timestamp proof say?")
    monkeypatch.setattr(engine, "_transcript_provider", FakeFasterWhisperProvider())
    original_transition = engine._store._transition_run  # pyright: ignore[reportPrivateUsage]

    def interrupt_before_final_cas(
        run_id: str,
        *,
        expected: tuple[RunState, ...],
        target: RunState,
        event_type: str,
    ) -> None:
        if target is RunState.PUBLISHED:
            raise RunTransitionError(
                run_id,
                expected=expected,
                actual=RunState.INTERRUPTED,
                target=target,
            )
        original_transition(
            run_id,
            expected=expected,
            target=target,
            event_type=event_type,
        )

    monkeypatch.setattr(
        engine._store,  # pyright: ignore[reportPrivateUsage]
        "_transition_run",
        interrupt_before_final_cas,
    )

    with pytest.raises(VideoIngestError) as error:
        engine.ingest_video(VIDEO_FIXTURES / "short-audio.mp4")

    run_id = error.value.run_id
    assert run_id is not None
    assert error.value.problem == "video_ingest_failed"
    assert error.value.next_step == "retry_when_owner_ready"
    assert engine.get_run(run_id).state is RunState.VALIDATED
    assert RunEventType.PUBLICATION_ACTIVATED not in [
        event.event_type for event in engine.get_run_events(run_id)
    ]
    assert engine.search("timestamp proof") == before_search
    after_ask = engine.ask("What does the timestamp proof say?")
    assert (
        after_ask.answer_status,
        after_ask.summary,
        after_ask.evidence,
        after_ask.limitations,
    ) == (
        before_ask.answer_status,
        before_ask.summary,
        before_ask.evidence,
        before_ask.limitations,
    )
