from __future__ import annotations

from concurrent.futures import CancelledError
from hashlib import sha256
from pathlib import Path

import pytest

from mke.adapters.audio import AudioProviderError, AudioSourceSnapshot, audio_extractor_fingerprint
from mke.adapters.audio import cleanup_audio_snapshot as real_cleanup_audio_snapshot
from mke.application import (
    AudioIngestError,
    IngestDispatchError,
    KnowledgeEngine,
)
from mke.domain import (
    AudioMediaInfo,
    AudioTranscriptExtractionResult,
    AudioTranscriptSegment,
    IngestResult,
    ParsedAudioTranscript,
    RunState,
    TranscriptIntakeReport,
    TranscriptionProvenance,
)
from mke.runtime_owner import BoundedAdmissionController

AUDIO_FIXTURES = Path(__file__).parents[1] / "fixtures" / "audio"


def _media(suffix: str) -> AudioMediaInfo:
    return {
        ".mp3": AudioMediaInfo("mp3", "mp3", 1, 16_000, 1_200),
        ".wav": AudioMediaInfo("wav", "pcm_s16le", 1, 16_000, 1_200),
        ".m4a": AudioMediaInfo("m4a", "aac", 1, 16_000, 1_200),
    }[suffix.lower()]


def _extraction(media: AudioMediaInfo) -> AudioTranscriptExtractionResult:
    provenance = TranscriptionProvenance(
        provider="faster-whisper",
        model="small",
        model_revision="a" * 40,
        library_version="1.2.3",
        device="cpu",
        compute_type="int8",
        language="auto",
        detected_language="en",
        model_source="cache",
        transcription_duration_ms=25,
    )
    return AudioTranscriptExtractionResult(
        ParsedAudioTranscript(
            media,
            (AudioTranscriptSegment(0, 1_000, "bounded synthetic speech"),),
            provenance,
        ),
        audio_extractor_fingerprint(provenance),
        TranscriptIntakeReport(
            provider="faster-whisper",
            model="small",
            model_revision="a" * 40,
            library_version="1.2.3",
            device="cpu",
            compute_type="int8",
            language="auto",
            detected_language="en",
            media_duration_ms=media.duration_ms,
            transcription_duration_ms=25,
            segment_count=1,
            model_source="cache",
        ),
    )


class FakeAudioProvider:
    def __init__(self) -> None:
        self.inspected: list[AudioSourceSnapshot] = []
        self.transcribed: list[AudioSourceSnapshot] = []

    def inspect(self, snapshot: AudioSourceSnapshot, *, suffix: str) -> AudioMediaInfo:
        snapshot.verify_owned_path()
        self.inspected.append(snapshot)
        return _media(suffix)

    def transcribe(
        self,
        snapshot: AudioSourceSnapshot,
        media: AudioMediaInfo,
        config: object,
    ) -> AudioTranscriptExtractionResult:
        snapshot.verify_owned_path()
        self.transcribed.append(snapshot)
        return _extraction(media)


def _engine(
    tmp_path: Path,
    provider: FakeAudioProvider | None = None,
    *,
    admission: BoundedAdmissionController | None = None,
) -> tuple[KnowledgeEngine, FakeAudioProvider]:
    selected = provider or FakeAudioProvider()
    return (
        KnowledgeEngine(
            tmp_path / "mke.sqlite",
            audio_provider=selected,
            audio_transcription_config=object(),
            audio_preflight=lambda: None,
            admission_controller=admission,
        ),
        selected,
    )


@pytest.mark.parametrize(
    ("name", "method"),
    [
        ("document.pdf", "ingest_pdf"),
        ("clip.mp4", "ingest_video"),
        ("voice.mp3", "ingest_audio"),
        ("voice.WAV", "ingest_audio"),
        ("voice.M4A", "ingest_audio"),
    ],
)
def test_ingest_file_uses_one_closed_suffix_dispatcher(
    tmp_path: Path,
    name: str,
    method: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    expected = IngestResult("run_test", RunState.PUBLISHED, 1)
    calls: list[tuple[str, Path]] = []

    def dispatch(path: Path) -> IngestResult:
        calls.append((method, path))
        return expected

    monkeypatch.setattr(
        engine,
        method,
        dispatch,
    )

    assert engine.ingest_file(Path(name)) == expected
    assert calls == [(method, Path(name))]


def test_ingest_file_rejects_unknown_suffix_without_source_or_run(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    with pytest.raises(IngestDispatchError) as raised:
        engine.ingest_file(Path("notes.txt"))

    assert raised.value.problem == "unsupported_media_type"
    assert raised.value.cause == "supported suffixes are .pdf, .mp4, .mp3, .wav, and .m4a"
    assert raised.value.next_step == "choose_supported_file"
    assert engine.observe_active_publications().source_count == 0


def test_sidecar_owner_rejects_audio_before_source_or_run(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    with pytest.raises(AudioIngestError) as raised:
        engine.ingest_file(AUDIO_FIXTURES / "direct-audio.mp3")

    assert raised.value.problem == "transcription_not_ready"
    assert raised.value.cause == "direct audio requires faster-whisper owner"
    assert raised.value.next_step == "configure_faster_whisper_owner"
    assert raised.value.run_id is None
    assert engine.observe_active_publications().source_count == 0


@pytest.mark.parametrize(
    ("fixture", "media_type"),
    [
        ("direct-audio.mp3", "audio/mpeg"),
        ("direct-audio.wav", "audio/wav"),
        ("direct-audio.m4a", "audio/mp4"),
    ],
)
def test_audio_ingest_publishes_timestamp_evidence_from_owned_bytes(
    tmp_path: Path,
    fixture: str,
    media_type: str,
) -> None:
    engine, provider = _engine(tmp_path)
    source_path = AUDIO_FIXTURES / fixture

    result = engine.ingest_file(source_path)

    assert result.run_state is RunState.PUBLISHED
    assert result.evidence_count == 1
    assert result.transcript_intake_report == _extraction(
        _media(source_path.suffix)
    ).transcript_intake_report
    assert [item.text for item in engine.search("bounded synthetic")] == [
        "bounded synthetic speech"
    ]
    ask = engine.ask("bounded synthetic")
    assert [item.text for item in ask.evidence] == ["bounded synthetic speech"]
    assert provider.inspected == provider.transcribed
    snapshot = provider.inspected[0]
    assert snapshot.original_path == source_path.resolve()
    assert snapshot.owned_identity.sha256 == sha256(source_path.read_bytes()).hexdigest()
    assert not snapshot.owned_root.exists()
    stored = engine._store._connection.execute(  # pyright: ignore[reportPrivateUsage]
        """
        SELECT assets.media_type, assets.sha256
        FROM sources JOIN assets ON assets.asset_id = sources.asset_id
        """
    ).fetchone()
    assert stored is not None
    assert (stored["media_type"], stored["sha256"]) == (
        media_type,
        snapshot.owned_identity.sha256,
    )


def test_admission_rejection_precedes_snapshot_and_provider_calls(tmp_path: Path) -> None:
    admission = BoundedAdmissionController(capacity=1, max_waiters=0)
    held = admission.acquire()
    engine, provider = _engine(tmp_path, admission=admission)

    try:
        with pytest.raises(AudioIngestError) as raised:
            engine.ingest_audio(AUDIO_FIXTURES / "direct-audio.wav")
    finally:
        held.release()

    assert raised.value.problem == "transcription_busy"
    assert raised.value.cause == "direct audio owner capacity is busy"
    assert raised.value.next_step == "retry_when_owner_ready"
    assert raised.value.run_id is None
    assert provider.inspected == []
    assert provider.transcribed == []
    assert engine.observe_active_publications().source_count == 0


def test_preflight_failure_precedes_admission_and_snapshot(tmp_path: Path) -> None:
    admission = BoundedAdmissionController(capacity=1, max_waiters=0)

    def reject() -> None:
        raise AudioIngestError(
            "configured transcription model is not cached",
            problem="transcription_not_ready",
            next_step="run_transcription_prepare",
        )

    provider = FakeAudioProvider()
    engine = KnowledgeEngine(
        tmp_path / "mke.sqlite",
        audio_provider=provider,
        audio_transcription_config=object(),
        audio_preflight=reject,
        admission_controller=admission,
    )

    with pytest.raises(AudioIngestError, match="configured transcription model is not cached"):
        engine.ingest_audio(AUDIO_FIXTURES / "direct-audio.m4a")

    assert admission.snapshot().active == 0
    assert provider.inspected == []
    assert engine.observe_active_publications().source_count == 0


@pytest.mark.parametrize("kind", ["missing", "directory", "symlink"])
def test_input_identity_rejection_precedes_preflight_and_provider(
    tmp_path: Path,
    kind: str,
) -> None:
    target = tmp_path / "voice.mp3"
    if kind == "directory":
        target.mkdir()
    elif kind == "symlink":
        target.symlink_to(AUDIO_FIXTURES / "direct-audio.mp3")
    preflight_calls = 0
    provider = FakeAudioProvider()

    def observe_preflight() -> None:
        nonlocal preflight_calls
        preflight_calls += 1

    engine = KnowledgeEngine(
        tmp_path / "mke.sqlite",
        audio_provider=provider,
        audio_transcription_config=object(),
        audio_preflight=observe_preflight,
    )

    with pytest.raises(AudioIngestError) as raised:
        engine.ingest_audio(target)

    assert raised.value.problem == "input_path_rejected"
    assert raised.value.next_step == "choose_file_under_allowed_root"
    assert raised.value.run_id is None
    assert preflight_calls == 0
    assert provider.inspected == []
    assert engine.observe_active_publications().source_count == 0


def test_provider_failure_releases_lease_and_preserves_prior_publication(tmp_path: Path) -> None:
    engine, provider = _engine(tmp_path)
    first = engine.ingest_audio(AUDIO_FIXTURES / "direct-audio.mp3")

    def fail(
        snapshot: AudioSourceSnapshot,
        media: AudioMediaInfo,
        config: object,
    ) -> AudioTranscriptExtractionResult:
        raise RuntimeError("provider detail must not publish")

    provider.transcribe = fail  # type: ignore[method-assign]
    with pytest.raises(AudioIngestError) as raised:
        engine.ingest_audio(AUDIO_FIXTURES / "direct-audio.mp3")

    assert raised.value.run_id is not None
    assert engine.get_run(raised.value.run_id).state is RunState.FAILED
    assert engine.get_run(first.run_id).state is RunState.PUBLISHED
    assert [item.text for item in engine.search("bounded synthetic")] == [
        "bounded synthetic speech"
    ]
    assert engine._admission_controller.snapshot().active == 0  # pyright: ignore[reportPrivateUsage]


def test_snapshot_precedes_source_and_run_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import mke.application as application

    engine, _provider = _engine(tmp_path)
    original = application.snapshot_audio_source
    observations: list[tuple[int, int]] = []

    def observe(path: Path, owned_root: Path) -> AudioSourceSnapshot:
        source_count = engine.observe_active_publications().source_count
        run_count = engine._store._connection.execute(  # pyright: ignore[reportPrivateUsage]
            "SELECT COUNT(*) FROM runs"
        ).fetchone()[0]
        observations.append((source_count, run_count))
        return original(path, owned_root)

    monkeypatch.setattr(application, "snapshot_audio_source", observe)

    engine.ingest_audio(AUDIO_FIXTURES / "direct-audio.mp3")

    assert observations == [(0, 0)]


def test_cleanup_failure_marks_run_failed_and_preserves_prior_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import mke.application as application

    engine, provider = _engine(tmp_path)
    first = engine.ingest_audio(AUDIO_FIXTURES / "direct-audio.wav")
    def fail_cleanup(_snapshot: AudioSourceSnapshot) -> None:
        raise RuntimeError("cleanup failed")

    monkeypatch.setattr(application, "cleanup_audio_snapshot", fail_cleanup)

    with pytest.raises(AudioIngestError) as raised:
        engine.ingest_audio(AUDIO_FIXTURES / "direct-audio.wav")

    assert raised.value.cause == "audio intake cleanup failed"
    assert raised.value.next_step == "check_server_logs"
    assert raised.value.run_id is not None
    assert engine.get_run(raised.value.run_id).state is RunState.FAILED
    assert engine.get_run(first.run_id).state is RunState.PUBLISHED
    assert engine._admission_controller.snapshot().active == 0  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(application, "cleanup_audio_snapshot", real_cleanup_audio_snapshot)
    real_cleanup_audio_snapshot(provider.inspected[-1])


def test_cancellation_cleans_snapshot_marks_run_failed_and_releases_lease(
    tmp_path: Path,
) -> None:
    engine, provider = _engine(tmp_path)

    def cancel(
        snapshot: AudioSourceSnapshot,
        media: AudioMediaInfo,
        config: object,
    ) -> AudioTranscriptExtractionResult:
        raise CancelledError

    provider.transcribe = cancel  # type: ignore[method-assign]

    with pytest.raises(AudioIngestError) as raised:
        engine.ingest_audio(AUDIO_FIXTURES / "direct-audio.m4a")

    assert raised.value.run_id is not None
    assert engine.get_run(raised.value.run_id).state is RunState.FAILED
    assert not provider.inspected[0].owned_root.exists()
    assert engine._admission_controller.snapshot().active == 0  # pyright: ignore[reportPrivateUsage]


def test_superseded_run_does_not_publish_report_or_evidence(tmp_path: Path) -> None:
    engine, provider = _engine(tmp_path)
    original = provider.transcribe

    def supersede(
        snapshot: AudioSourceSnapshot,
        media: AudioMediaInfo,
        config: object,
    ) -> AudioTranscriptExtractionResult:
        source = engine._store.get_first_source()  # pyright: ignore[reportPrivateUsage]
        assert source is not None
        engine.create_run(source.source_id)
        return original(snapshot, media, config)

    provider.transcribe = supersede  # type: ignore[method-assign]

    result = engine.ingest_audio(AUDIO_FIXTURES / "direct-audio.mp3")

    assert result.run_state is RunState.SUPERSEDED
    assert result.evidence_count == 0
    assert result.transcript_intake_report is None
    assert engine.get_transcript_intake_report(result.run_id) is None
    assert engine.search("bounded synthetic") == []


def test_report_insertion_failure_rolls_back_publication_and_preserves_prior(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, _provider = _engine(tmp_path)
    first = engine.ingest_audio(AUDIO_FIXTURES / "direct-audio.mp3")

    def fail_report(run_id: str, report: TranscriptIntakeReport) -> None:
        raise RuntimeError("report insertion failed")

    monkeypatch.setattr(engine._store, "_insert_transcript_intake_report", fail_report)  # pyright: ignore[reportPrivateUsage]

    with pytest.raises(AudioIngestError) as raised:
        engine.ingest_audio(AUDIO_FIXTURES / "direct-audio.mp3")

    assert raised.value.run_id is not None
    assert raised.value.cause == "audio publication failed"
    assert raised.value.next_step == "retry_when_owner_ready"
    assert engine.get_run(raised.value.run_id).state is RunState.FAILED
    assert engine.get_run(first.run_id).state is RunState.PUBLISHED
    assert [item.text for item in engine.search("bounded synthetic")] == [
        "bounded synthetic speech"
    ]


def test_source_identity_drift_uses_closed_post_run_error(tmp_path: Path) -> None:
    source_path = tmp_path / "voice.mp3"
    source_path.write_bytes((AUDIO_FIXTURES / "direct-audio.mp3").read_bytes())
    engine, provider = _engine(tmp_path)
    original = provider.transcribe

    def drift(
        snapshot: AudioSourceSnapshot,
        media: AudioMediaInfo,
        config: object,
    ) -> AudioTranscriptExtractionResult:
        result = original(snapshot, media, config)
        source_path.write_bytes(b"x" * source_path.stat().st_size)
        return result

    provider.transcribe = drift  # type: ignore[method-assign]

    with pytest.raises(AudioIngestError) as raised:
        engine.ingest_audio(source_path)

    assert raised.value.problem == "audio_ingest_failed"
    assert raised.value.cause == "audio source identity changed during intake"
    assert raised.value.next_step == "retry_with_stable_file"
    assert raised.value.run_id is not None
    assert engine.get_run(raised.value.run_id).state is RunState.FAILED


def test_post_run_manifest_validation_uses_publication_failure(tmp_path: Path) -> None:
    engine, provider = _engine(tmp_path)
    original = provider.transcribe

    def invalid_manifest(
        snapshot: AudioSourceSnapshot,
        media: AudioMediaInfo,
        config: object,
    ) -> AudioTranscriptExtractionResult:
        result = original(snapshot, media, config)
        return AudioTranscriptExtractionResult(
            parsed_transcript=result.parsed_transcript,
            extractor_fingerprint="faster-whisper-audio-v1:" + ("f" * 64),
            transcript_intake_report=result.transcript_intake_report,
        )

    provider.transcribe = invalid_manifest  # type: ignore[method-assign]

    with pytest.raises(AudioIngestError) as raised:
        engine.ingest_audio(AUDIO_FIXTURES / "direct-audio.mp3")

    assert raised.value.problem == "audio_ingest_failed"
    assert raised.value.cause == "audio publication failed"
    assert raised.value.next_step == "retry_when_owner_ready"
    assert raised.value.run_id is not None
    assert engine.get_run(raised.value.run_id).state is RunState.FAILED


@pytest.mark.parametrize(
    ("cause", "next_step"),
    [
        ("audio inspection timed out", "retry_with_supported_file"),
        ("audio inspection failed", "choose_supported_file"),
    ],
)
def test_inspection_failure_preserves_closed_pre_run_error(
    tmp_path: Path,
    cause: str,
    next_step: str,
) -> None:
    engine, provider = _engine(tmp_path)

    def fail(_snapshot: AudioSourceSnapshot, *, suffix: str) -> AudioMediaInfo:
        raise AudioProviderError(cause, next_step=next_step)

    provider.inspect = fail  # type: ignore[method-assign]

    with pytest.raises(AudioIngestError) as raised:
        engine.ingest_audio(AUDIO_FIXTURES / "direct-audio.mp3")

    assert raised.value.problem == "audio_ingest_failed"
    assert raised.value.cause == cause
    assert raised.value.next_step == next_step
    assert raised.value.run_id is None


def test_admission_lease_is_released_before_candidate_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admission = BoundedAdmissionController(capacity=1, max_waiters=0)
    engine, _provider = _engine(tmp_path, admission=admission)
    original = engine._store.persist_validated_candidate  # pyright: ignore[reportPrivateUsage]

    def observe_release(run_id: str, evidence: object, manifest: object) -> None:
        assert admission.snapshot().active == 0
        original(run_id, evidence, manifest)  # type: ignore[arg-type]

    monkeypatch.setattr(engine._store, "persist_validated_candidate", observe_release)  # pyright: ignore[reportPrivateUsage]

    result = engine.ingest_audio(AUDIO_FIXTURES / "direct-audio.wav")

    assert result.run_state is RunState.PUBLISHED


def test_concurrent_admission_rejection_keeps_active_publication_unchanged(
    tmp_path: Path,
) -> None:
    admission = BoundedAdmissionController(capacity=1, max_waiters=0)
    engine, _provider = _engine(tmp_path, admission=admission)
    first = engine.ingest_audio(AUDIO_FIXTURES / "direct-audio.wav")
    held = admission.acquire()
    try:
        with pytest.raises(AudioIngestError) as raised:
            engine.ingest_audio(AUDIO_FIXTURES / "direct-audio.wav")
    finally:
        held.release()

    assert raised.value.problem == "transcription_busy"
    assert engine.get_run(first.run_id).state is RunState.PUBLISHED
