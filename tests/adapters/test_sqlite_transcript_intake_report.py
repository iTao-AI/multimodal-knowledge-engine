from pathlib import Path

import pytest

from mke.adapters.sqlite import InjectedStorageFailure, SQLiteStore
from mke.domain import (
    LOCAL_COMMAND_VIDEO_TRANSCRIPT_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    REQUIRED_VIDEO_STAGES,
    VIDEO_TRANSCRIPT_FINGERPRINT,
    CandidateEvidence,
    FailurePoint,
    ManifestValidationError,
    RunManifest,
    RunState,
    TranscriptIntakeReport,
)

_FASTER_WHISPER_FINGERPRINT = "faster-whisper-v1:" + ("a" * 64)


def _report() -> TranscriptIntakeReport:
    return TranscriptIntakeReport(
        provider="faster-whisper",
        model="small",
        model_revision="a" * 40,
        library_version="1.2.3",
        device="cpu",
        compute_type="int8",
        language="auto",
        detected_language="en",
        media_duration_ms=2_000,
        transcription_duration_ms=500,
        segment_count=1,
        model_source="cache",
    )


def _validated_video_run(
    store: SQLiteStore,
    *,
    source_id: str,
    fingerprint: str,
    text: str,
) -> str:
    run = store.create_run(source_id)
    store.mark_run_running(run.run_id)
    evidence = [CandidateEvidence(f"ev_{run.run_id}", "timestamp_ms", 0, 1000, text)]
    store.persist_validated_candidate(
        run.run_id,
        evidence,
        RunManifest(
            run_id=run.run_id,
            evidence_count=1,
            required_stages=tuple(sorted(REQUIRED_VIDEO_STAGES)),
            extractor_fingerprint=fingerprint,
            asset_sha256="a" * 64,
        ),
    )
    return run.run_id


def _store_with_active_video(tmp_path: Path) -> tuple[SQLiteStore, str]:
    store = SQLiteStore(tmp_path / "mke.sqlite")
    source = store.ensure_source("video.mp4", "a" * 64, "video/mp4")
    initial_run_id = _validated_video_run(
        store,
        source_id=source.source_id,
        fingerprint=VIDEO_TRANSCRIPT_FINGERPRINT,
        text="previous active timestamp evidence",
    )
    activation = store.activate_publication(initial_run_id)
    assert activation.published
    return store, source.source_id


def test_faster_whisper_activation_exposes_publication_and_report_together(
    tmp_path: Path,
) -> None:
    store, source_id = _store_with_active_video(tmp_path)
    run_id = _validated_video_run(
        store,
        source_id=source_id,
        fingerprint=_FASTER_WHISPER_FINGERPRINT,
        text="new faster whisper evidence",
    )
    report = _report()

    activation = store.activate_publication(run_id, transcript_intake_report=report)

    assert activation.published
    assert store.get_run(run_id).state == RunState.PUBLISHED
    assert store.get_transcript_intake_report(run_id) == report
    assert [result.text for result in store.search("faster whisper")] == [
        "new faster whisper evidence"
    ]


@pytest.mark.parametrize(
    "failure_point",
    [
        FailurePoint.AFTER_PUBLICATION_INSERT,
        FailurePoint.DURING_ACTIVE_FTS_REPLACEMENT,
        FailurePoint.AFTER_ACTIVE_POINTER_SWITCH,
    ],
)
def test_activation_failure_rolls_back_publication_search_and_report(
    tmp_path: Path, failure_point: FailurePoint
) -> None:
    store, source_id = _store_with_active_video(tmp_path)
    before = [result.text for result in store.search("previous active")]
    run_id = _validated_video_run(
        store,
        source_id=source_id,
        fingerprint=_FASTER_WHISPER_FINGERPRINT,
        text="uncommitted replacement evidence",
    )

    with pytest.raises(InjectedStorageFailure, match=failure_point.value):
        store.activate_publication(
            run_id,
            failure_point=failure_point,
            transcript_intake_report=_report(),
        )

    assert store.get_run(run_id).state == RunState.VALIDATED
    assert store.get_transcript_intake_report(run_id) is None
    assert [result.text for result in store.search("previous active")] == before
    assert store.search("uncommitted replacement") == []


def test_report_insert_failure_rolls_back_publication_search_and_report(tmp_path: Path) -> None:
    store, source_id = _store_with_active_video(tmp_path)
    before = [result.text for result in store.search("previous active")]
    run_id = _validated_video_run(
        store,
        source_id=source_id,
        fingerprint=_FASTER_WHISPER_FINGERPRINT,
        text="report failure replacement",
    )
    store._connection.executescript(  # pyright: ignore[reportPrivateUsage]
        """
        CREATE TRIGGER fail_transcript_report
        BEFORE INSERT ON transcript_intake_reports
        BEGIN
          SELECT RAISE(ABORT, 'injected report insert failure');
        END;
        """
    )
    store._connection.commit()  # pyright: ignore[reportPrivateUsage]

    with pytest.raises(Exception, match="injected report insert failure"):
        store.activate_publication(run_id, transcript_intake_report=_report())

    assert store.get_run(run_id).state == RunState.VALIDATED
    assert store.get_transcript_intake_report(run_id) is None
    assert [result.text for result in store.search("previous active")] == before
    assert store.search("report failure replacement") == []


def test_faster_whisper_manifest_cannot_publish_without_report(tmp_path: Path) -> None:
    store, source_id = _store_with_active_video(tmp_path)
    run_id = _validated_video_run(
        store,
        source_id=source_id,
        fingerprint=_FASTER_WHISPER_FINGERPRINT,
        text="missing report evidence",
    )

    with pytest.raises(ManifestValidationError, match="intake report"):
        store.activate_publication(run_id)

    assert store.get_run(run_id).state == RunState.VALIDATED
    assert store.get_transcript_intake_report(run_id) is None
    assert store.search("missing report") == []


def test_superseded_faster_whisper_run_exposes_no_report(tmp_path: Path) -> None:
    store, source_id = _store_with_active_video(tmp_path)
    stale_run_id = _validated_video_run(
        store,
        source_id=source_id,
        fingerprint=_FASTER_WHISPER_FINGERPRINT,
        text="stale evidence",
    )
    _validated_video_run(
        store,
        source_id=source_id,
        fingerprint=LOCAL_COMMAND_VIDEO_TRANSCRIPT_FINGERPRINT,
        text="newer candidate",
    )

    activation = store.activate_publication(
        stale_run_id,
        transcript_intake_report=_report(),
    )

    assert activation.run_state == RunState.SUPERSEDED
    assert not activation.published
    assert store.get_transcript_intake_report(stale_run_id) is None


def test_legacy_video_and_pdf_activation_allow_no_transcript_report(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "mke.sqlite")
    video_source = store.ensure_source("video.mp4", "a" * 64, "video/mp4")
    video_run_id = _validated_video_run(
        store,
        source_id=video_source.source_id,
        fingerprint=VIDEO_TRANSCRIPT_FINGERPRINT,
        text="legacy video evidence",
    )
    assert store.activate_publication(video_run_id).published
    assert store.get_transcript_intake_report(video_run_id) is None

    pdf_source = store.ensure_source("document.pdf", "b" * 64)
    pdf_run = store.create_run(pdf_source.source_id)
    store.mark_run_running(pdf_run.run_id)
    evidence = [CandidateEvidence("ev_pdf", "page", 1, 1, "legacy pdf evidence")]
    store.persist_validated_candidate(
        pdf_run.run_id,
        evidence,
        RunManifest(
            run_id=pdf_run.run_id,
            evidence_count=1,
            required_stages=tuple(sorted(REQUIRED_PDF_STAGES)),
            extractor_fingerprint="builtin-pdf-text-v1",
            asset_sha256="b" * 64,
        ),
    )
    assert store.activate_publication(pdf_run.run_id).published
    assert store.get_transcript_intake_report(pdf_run.run_id) is None
