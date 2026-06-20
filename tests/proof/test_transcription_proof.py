from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from mke.adapters.video.contracts import AdapterExitCode
from mke.application import AskResult
from mke.domain import IngestResult, RunState, SearchResult, TranscriptIntakeReport
from mke.proof.transcription import (
    ProofEnvironment,
    TranscriptionProofReport,
    validate_transcription_proof,
)
from mke.runtime import FasterWhisperTranscriptionConfig
from tests.conftest import VIDEO_FIXTURES


def _first_party_transcript(**transcription_overrides: object) -> bytes:
    transcription: dict[str, object] = {
        "provider": "faster-whisper",
        "model": "small",
        "model_revision": "a" * 40,
        "library_version": "1.2.3",
        "device": "cpu",
        "compute_type": "int8",
        "language": "auto",
        "detected_language": "en",
        "model_source": "cache",
        "transcription_duration_ms": 321,
    }
    transcription.update(transcription_overrides)
    return json.dumps(
        {
            "format": "mke.video_transcript.v1",
            "media": {
                "container": "mp4",
                "video_codec": "h264",
                "audio_codec": "aac",
                "has_audio": True,
                "duration_ms": 4000,
            },
            "transcription": transcription,
            "segments": [
                {
                    "start_ms": 0,
                    "end_ms": 1800,
                    "text": "Evidence publication remains traceable",
                },
                {
                    "start_ms": 1800,
                    "end_ms": 4000,
                    "text": "Evidence stays linked after publication",
                },
            ],
        }
    ).encode()


def _patch_successful_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, ...]]:
    commands: list[tuple[str, ...]] = []

    def fake_run(command: list[str], **_: object) -> SimpleNamespace:
        commands.append(tuple(command))
        return SimpleNamespace(returncode=0, stdout=_first_party_transcript(), stderr=b"")

    def forbidden(*_: object, **__: object) -> object:
        pytest.fail("proof must not prepare or resolve/download a model in-process")

    monkeypatch.setattr("mke.adapters.video.providers._run_bounded_command", fake_run)
    monkeypatch.setattr("mke.adapters.video.faster_whisper.prepare_model", forbidden)
    monkeypatch.setattr("mke.adapters.video.faster_whisper.resolve_model_snapshot", forbidden)
    return commands


def test_transcription_proof_runs_first_party_cache_only_path_and_cleans_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.proof.transcription import run_transcription_proof

    commands = _patch_successful_provider(monkeypatch)
    from mke.proof import transcription as proof_module

    monkeypatch.setattr(proof_module.tempfile, "tempdir", str(tmp_path))
    repo_cache_files_before = set(Path.cwd().rglob("proof.sqlite"))

    report = run_transcription_proof(
        VIDEO_FIXTURES / "spoken-evidence.mp4",
        FasterWhisperTranscriptionConfig(model_revision="a" * 40),
    )

    assert report.status == "passed"
    assert report.run_state == "published"
    assert report.evidence_count == 2
    assert report.timestamp_evidence is True
    assert report.search_keyword_matched is True
    assert report.ask_status == "evidence_found"
    assert report.transcript_intake_report is not None
    assert report.transcript_intake_report.model_source == "cache"
    assert report.reason is None
    assert len(commands) == 1
    assert "mke.adapters.video.faster_whisper_cli" in commands[0]
    assert "--allow-model-download" not in commands[0]
    assert list(tmp_path.iterdir()) == []
    assert set(Path.cwd().rglob("proof.sqlite")) == repo_cache_files_before


def test_transcription_proof_reports_actual_non_sensitive_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.proof import transcription as proof_module
    from mke.proof.transcription import run_transcription_proof

    _patch_successful_provider(monkeypatch)
    versions = {
        "faster-whisper": "1.2.3",
        "ctranslate2": "4.6.0",
        "av": "14.4.0",
    }
    monkeypatch.setattr(proof_module.metadata, "version", versions.__getitem__)

    report = run_transcription_proof(
        VIDEO_FIXTURES / "spoken-evidence.mp4",
        FasterWhisperTranscriptionConfig(model_revision="a" * 40),
    )

    assert report.environment is not None
    payload = proof_module.render_transcription_proof_json(report)
    environment = json.loads(payload)["environment"]
    assert environment["faster_whisper_version"] == "1.2.3"
    assert environment["ctranslate2_version"] == "4.6.0"
    assert environment["pyav_version"] == "14.4.0"
    assert set(environment) == {
        "python_version",
        "os",
        "architecture",
        "faster_whisper_version",
        "ctranslate2_version",
        "pyav_version",
    }
    forbidden = (
        str(Path.home()),
        str(Path.cwd()),
        "hostname",
        "username",
        "model-cache",
        "argv",
        "endpoint",
        "secret",
    )
    assert all(value not in payload for value in forbidden)


def test_transcription_proof_human_output_contains_complete_safe_runtime_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.proof.transcription import (
        render_transcription_proof_human,
        run_transcription_proof,
    )

    _patch_successful_provider(monkeypatch)
    report = run_transcription_proof(
        VIDEO_FIXTURES / "spoken-evidence.mp4",
        FasterWhisperTranscriptionConfig(model_revision="a" * 40),
    )

    human = render_transcription_proof_human(report)
    assert "model=small" in human
    assert f"model_revision={'a' * 40}" in human
    assert "library_version=1.2.3" in human
    assert "device=cpu" in human
    assert "compute_type=int8" in human
    assert "language=auto" in human
    assert "detected_language=en" in human
    assert "python_version=" in human
    assert "os=" in human
    assert "architecture=" in human
    assert "faster_whisper_version=" in human
    assert "ctranslate2_version=" in human
    assert "pyav_version=" in human
    assert str(Path.home()) not in human
    assert str(Path.cwd()) not in human
    assert "argv=" not in human
    assert "secret" not in human


def test_transcription_proof_cache_miss_is_stable_failed_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.proof.transcription import (
        render_transcription_proof_human,
        render_transcription_proof_json,
        run_transcription_proof,
    )

    def cache_miss(command: list[str], **_: object) -> SimpleNamespace:
        assert "--allow-model-download" not in command
        return SimpleNamespace(
            returncode=int(AdapterExitCode.MODEL_UNAVAILABLE),
            stdout=b"",
            stderr=b"/Users/private/model-cache secret-token",
        )

    monkeypatch.setattr("mke.adapters.video.providers._run_bounded_command", cache_miss)
    report = run_transcription_proof(
        VIDEO_FIXTURES / "spoken-evidence.mp4",
        FasterWhisperTranscriptionConfig(model_revision="a" * 40),
    )

    assert report.status == "failed"
    assert report.reason == "model_not_cached"
    assert report.run_state == "failed"
    assert report.evidence_count == 0
    rendered = render_transcription_proof_json(report)
    human = render_transcription_proof_human(report)
    assert json.loads(rendered)["reason"] == "model_not_cached"
    assert "run_transcription_prepare" in human
    assert "/Users/private" not in rendered + human
    assert "secret-token" not in rendered + human
    assert "Traceback" not in rendered + human


def test_transcription_proof_build_failure_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.proof.transcription import (
        render_transcription_proof_json,
        run_transcription_proof,
    )

    def fail_build(config: object) -> object:
        raise RuntimeError("/Users/private/database.sqlite secret-token")

    monkeypatch.setattr("mke.proof.transcription.build_engine", fail_build)

    report = run_transcription_proof(
        VIDEO_FIXTURES / "spoken-evidence.mp4",
        FasterWhisperTranscriptionConfig(model_revision="a" * 40),
    )

    rendered = render_transcription_proof_json(report)
    assert report.status == "failed"
    assert report.reason == "runtime_initialization_failed"
    assert "/Users/private" not in rendered
    assert "secret-token" not in rendered
    assert "Traceback" not in rendered


def test_transcription_proof_environment_failure_is_stable_and_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.proof import transcription as proof_module
    from mke.proof.transcription import (
        render_transcription_proof_human,
        render_transcription_proof_json,
        run_transcription_proof,
    )

    def fail_version(distribution: str) -> str:
        raise RuntimeError("/Users/private/site-packages secret-token")

    monkeypatch.setattr(proof_module.metadata, "version", fail_version)

    report = run_transcription_proof(
        VIDEO_FIXTURES / "spoken-evidence.mp4",
        FasterWhisperTranscriptionConfig(model_revision="a" * 40),
    )

    rendered = render_transcription_proof_json(report)
    human = render_transcription_proof_human(report)
    assert report.status == "failed"
    assert report.reason == "environment_unavailable"
    assert report.environment is None
    assert "/Users/private" not in rendered + human
    assert "secret-token" not in rendered + human
    assert "Traceback" not in rendered + human


@pytest.mark.parametrize(
    "unsafe_version",
    (
        "/Users/private/secret",
        r"C:\private\secret",
        "token=secret",
    ),
)
def test_transcription_proof_rejects_unsafe_environment_versions(
    unsafe_version: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.proof import transcription as proof_module
    from mke.proof.transcription import (
        render_transcription_proof_human,
        render_transcription_proof_json,
        run_transcription_proof,
    )

    def unsafe_package_version(distribution: str) -> str:
        return unsafe_version

    monkeypatch.setattr(proof_module.metadata, "version", unsafe_package_version)

    report = run_transcription_proof(
        VIDEO_FIXTURES / "spoken-evidence.mp4",
        FasterWhisperTranscriptionConfig(model_revision="a" * 40),
    )

    rendered = render_transcription_proof_json(report)
    human = render_transcription_proof_human(report)
    assert report.status == "failed"
    assert report.reason == "environment_unavailable"
    assert report.environment is None
    assert unsafe_version not in rendered + human


def test_transcription_proof_initial_clock_failure_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.proof import transcription as proof_module
    from mke.proof.transcription import (
        render_transcription_proof_json,
        run_transcription_proof,
    )

    _patch_successful_provider(monkeypatch)

    def fail_clock() -> float:
        raise RuntimeError("/Users/private/clock secret")

    monkeypatch.setattr(proof_module.time, "monotonic", fail_clock)

    report = run_transcription_proof(
        VIDEO_FIXTURES / "spoken-evidence.mp4",
        FasterWhisperTranscriptionConfig(model_revision="a" * 40),
    )

    rendered = render_transcription_proof_json(report)
    assert report.status == "passed"
    assert report.duration_ms == 0
    assert "/Users/private" not in rendered
    assert "secret" not in rendered
    assert "Traceback" not in rendered


def test_transcription_proof_later_clock_failure_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.proof import transcription as proof_module
    from mke.proof.transcription import (
        render_transcription_proof_json,
        run_transcription_proof,
    )

    _patch_successful_provider(monkeypatch)
    calls = 0

    def fail_later_clock() -> float:
        nonlocal calls
        calls += 1
        if calls == 1:
            return 10.0
        raise RuntimeError("/Users/private/clock secret")

    monkeypatch.setattr(proof_module.time, "monotonic", fail_later_clock)

    report = run_transcription_proof(
        VIDEO_FIXTURES / "spoken-evidence.mp4",
        FasterWhisperTranscriptionConfig(model_revision="a" * 40),
    )

    rendered = render_transcription_proof_json(report)
    assert report.status == "passed"
    assert report.duration_ms == 0
    assert "/Users/private" not in rendered
    assert "secret" not in rendered
    assert "Traceback" not in rendered


@pytest.mark.parametrize("clock_value", (math.nan, math.inf, -math.inf, -1.0))
def test_transcription_proof_initial_invalid_clock_is_unavailable(
    clock_value: float,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.proof import transcription as proof_module
    from mke.proof.transcription import (
        render_transcription_proof_json,
        run_transcription_proof,
    )

    _patch_successful_provider(monkeypatch)
    monkeypatch.setattr(proof_module.time, "monotonic", lambda: clock_value)

    report = run_transcription_proof(
        VIDEO_FIXTURES / "spoken-evidence.mp4",
        FasterWhisperTranscriptionConfig(model_revision="a" * 40),
    )

    rendered = render_transcription_proof_json(report)
    assert report.status == "passed"
    assert report.duration_ms == 0
    assert "NaN" not in rendered
    assert "Infinity" not in rendered


@pytest.mark.parametrize(
    "later_value",
    (math.nan, math.inf, -math.inf, -1.0, 5.0),
)
def test_transcription_proof_later_invalid_or_reversed_clock_returns_zero_duration(
    later_value: float,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.proof import transcription as proof_module
    from mke.proof.transcription import run_transcription_proof

    _patch_successful_provider(monkeypatch)
    values = iter((10.0, later_value))
    monkeypatch.setattr(proof_module.time, "monotonic", lambda: next(values))

    report = run_transcription_proof(
        VIDEO_FIXTURES / "spoken-evidence.mp4",
        FasterWhisperTranscriptionConfig(model_revision="a" * 40),
    )

    assert report.status == "passed"
    assert report.duration_ms == 0


@pytest.mark.parametrize(
    ("field", "unsafe_value"),
    (
        ("run_state", "/Users/private/run"),
        ("run_state", "token=secret"),
        ("run_state", "not_run"),
        ("ask_status", "/Users/private/ask"),
        ("ask_status", "token=secret"),
        ("ask_status", "unexpected_status"),
    ),
)
def test_transcription_proof_report_rejects_invalid_semantic_status_fields(
    field: str,
    unsafe_value: str,
) -> None:
    values: dict[str, object] = {
        "status": "failed",
        "run_state": "failed",
        "evidence_count": 0,
        "timestamp_evidence": False,
        "search_keyword_matched": False,
        "ask_status": "not_run",
        "transcript_intake_report": None,
        "environment": None,
        "duration_ms": 0,
        "reason": "unexpected_error",
    }
    values[field] = unsafe_value

    with pytest.raises(ValueError, match=field.replace("_", " ")):
        TranscriptionProofReport(**values)  # pyright: ignore[reportArgumentType]


def test_transcription_proof_fixture_preflight_failure_is_stable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.proof.transcription import run_transcription_proof

    def fail_is_file(self: Path) -> bool:
        raise RuntimeError("/Users/private/fixture secret-token")

    monkeypatch.setattr(Path, "is_file", fail_is_file)

    report = run_transcription_proof(
        VIDEO_FIXTURES / "spoken-evidence.mp4",
        FasterWhisperTranscriptionConfig(model_revision="a" * 40),
    )

    assert report.status == "failed"
    assert report.reason == "fixture_unavailable"
    assert report.run_state == "failed"


def test_transcription_proof_temporary_workspace_cleanup_failure_is_stable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.proof import transcription as proof_module
    from mke.proof.transcription import (
        render_transcription_proof_json,
        run_transcription_proof,
    )

    _patch_successful_provider(monkeypatch)

    class CleanupFailure:
        def __enter__(self) -> str:
            return str(tmp_path)

        def __exit__(self, *args: Any) -> None:
            raise RuntimeError("/Users/private/cleanup secret-token")

    def cleanup_failure_directory(**kwargs: object) -> CleanupFailure:
        return CleanupFailure()

    monkeypatch.setattr(
        proof_module.tempfile,
        "TemporaryDirectory",
        cleanup_failure_directory,
    )

    report = run_transcription_proof(
        VIDEO_FIXTURES / "spoken-evidence.mp4",
        FasterWhisperTranscriptionConfig(model_revision="a" * 40),
    )

    rendered = render_transcription_proof_json(report)
    assert report.status == "failed"
    assert report.reason == "proof_cleanup_failed"
    assert "/Users/private" not in rendered
    assert "secret-token" not in rendered
    assert "Traceback" not in rendered


def test_transcription_proof_engine_close_failure_cannot_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.application import KnowledgeEngine
    from mke.proof.transcription import run_transcription_proof

    _patch_successful_provider(monkeypatch)

    def fail_close(self: KnowledgeEngine) -> None:
        raise RuntimeError("/Users/private/database.sqlite secret-token")

    monkeypatch.setattr(KnowledgeEngine, "close", fail_close)

    report = run_transcription_proof(
        VIDEO_FIXTURES / "spoken-evidence.mp4",
        FasterWhisperTranscriptionConfig(model_revision="a" * 40),
    )

    assert report.status == "failed"
    assert report.reason == "proof_cleanup_failed"
    assert report.run_state == "failed"


def test_transcription_proof_allows_search_subset_of_reported_evidence() -> None:
    intake_report = TranscriptIntakeReport(
        provider="faster-whisper",
        model="small",
        model_revision="a" * 40,
        library_version="1.2.3",
        device="cpu",
        compute_type="int8",
        language="auto",
        detected_language="en",
        media_duration_ms=4000,
        transcription_duration_ms=321,
        segment_count=3,
        model_source="cache",
    )
    first_match = SearchResult(
        evidence_id="ev_1",
        publication_id="pub_1",
        source_id="src_1",
        locator_kind="timestamp_ms",
        locator_start=0,
        locator_end=1800,
        text="Evidence publication remains traceable",
    )
    result = IngestResult(
        run_id="run_1",
        run_state=RunState.PUBLISHED,
        evidence_count=3,
        transcript_intake_report=intake_report,
    )
    answer = AskResult(
        ask_id="ask_1",
        question="evidence publication",
        answer_status="evidence_found",
        summary="Evidence found.",
        evidence=(first_match,),
        limitations=("Evidence only.",),
    )

    report = validate_transcription_proof(
        result,
        [first_match],
        answer,
        environment=ProofEnvironment(
            python_version="3.13.5",
            os="Darwin",
            architecture="arm64",
            faster_whisper_version="1.2.3",
            ctranslate2_version="4.6.0",
            pyav_version="14.4.0",
        ),
        duration_ms=12,
    )

    assert report.status == "passed"


def _proof_validation_inputs() -> tuple[
    IngestResult,
    list[SearchResult],
    AskResult,
    ProofEnvironment,
]:
    intake_report = TranscriptIntakeReport(
        provider="faster-whisper",
        model="small",
        model_revision="a" * 40,
        library_version="1.2.3",
        device="cpu",
        compute_type="int8",
        language="auto",
        detected_language="en",
        media_duration_ms=4000,
        transcription_duration_ms=321,
        segment_count=2,
        model_source="cache",
    )
    matches = [
        SearchResult(
            evidence_id="ev_1",
            publication_id="pub_1",
            source_id="src_1",
            locator_kind="timestamp_ms",
            locator_start=0,
            locator_end=1800,
            text="Evidence publication remains traceable",
        ),
        SearchResult(
            evidence_id="ev_2",
            publication_id="pub_1",
            source_id="src_1",
            locator_kind="timestamp_ms",
            locator_start=1800,
            locator_end=4000,
            text="Evidence stays linked after publication",
        ),
    ]
    return (
        IngestResult(
            run_id="run_1",
            run_state=RunState.PUBLISHED,
            evidence_count=2,
            transcript_intake_report=intake_report,
        ),
        matches,
        AskResult(
            ask_id="ask_1",
            question="evidence publication",
            answer_status="evidence_found",
            summary="Evidence found.",
            evidence=(matches[0],),
            limitations=("Evidence only.",),
        ),
        ProofEnvironment(
            python_version="3.13.5",
            os="Darwin",
            architecture="arm64",
            faster_whisper_version="1.2.3",
            ctranslate2_version="4.6.0",
            pyav_version="14.4.0",
        ),
    )


@pytest.mark.parametrize("identity_field", ("source_id", "publication_id"))
def test_transcription_proof_rejects_mixed_search_identity(identity_field: str) -> None:
    result, matches, answer, environment = _proof_validation_inputs()
    matches[1] = replace(matches[1], **{identity_field: f"other_{identity_field}"})

    report = validate_transcription_proof(
        result,
        matches,
        answer,
        expected_source_id="src_1",
        environment=environment,
        duration_ms=12,
    )

    assert report.status == "failed"
    assert report.reason == "proof_validation_failed"


def test_transcription_proof_rejects_search_source_unrelated_to_ingest_run() -> None:
    result, matches, answer, environment = _proof_validation_inputs()

    report = validate_transcription_proof(
        result,
        matches,
        answer,
        expected_source_id="src_from_ingest_run",
        environment=environment,
        duration_ms=12,
    )

    assert report.status == "failed"
    assert report.reason == "proof_validation_failed"


def test_transcription_proof_rejects_empty_search_publication_identity() -> None:
    result, matches, answer, environment = _proof_validation_inputs()
    matches = [replace(match, publication_id="") for match in matches]

    report = validate_transcription_proof(
        result,
        matches,
        answer,
        expected_source_id="src_1",
        environment=environment,
        duration_ms=12,
    )

    assert report.status == "failed"
    assert report.reason == "proof_validation_failed"


def test_transcription_proof_allows_ask_evidence_outside_search_subset() -> None:
    result, matches, answer, environment = _proof_validation_inputs()
    same_publication = replace(
        matches[0],
        evidence_id="ev_ask_only",
        locator_start=500,
        locator_end=1200,
    )
    answer = replace(answer, evidence=(same_publication,))

    report = validate_transcription_proof(
        result,
        matches,
        answer,
        expected_source_id="src_1",
        environment=environment,
        duration_ms=12,
    )

    assert report.status == "passed"


def test_transcription_proof_allows_rank_order_different_from_timestamp_order() -> None:
    result, matches, answer, environment = _proof_validation_inputs()
    ranked_matches = [matches[1], matches[0]]

    report = validate_transcription_proof(
        result,
        ranked_matches,
        answer,
        expected_source_id="src_1",
        environment=environment,
        duration_ms=12,
    )

    assert report.status == "passed"
    assert report.timestamp_evidence is True


@pytest.mark.parametrize(
    "invalid_match",
    (
        SearchResult(
            evidence_id="ev_overlap",
            publication_id="pub_1",
            source_id="src_1",
            locator_kind="timestamp_ms",
            locator_start=1700,
            locator_end=3000,
            text="Evidence overlaps",
        ),
        SearchResult(
            evidence_id="ev_invalid",
            publication_id="pub_1",
            source_id="src_1",
            locator_kind="timestamp_ms",
            locator_start=3000,
            locator_end=3000,
            text="Evidence invalid",
        ),
    ),
)
def test_transcription_proof_rejects_overlapping_or_invalid_timestamp_evidence(
    invalid_match: SearchResult,
) -> None:
    result, matches, answer, environment = _proof_validation_inputs()
    matches[1] = invalid_match

    report = validate_transcription_proof(
        result,
        matches,
        answer,
        expected_source_id="src_1",
        environment=environment,
        duration_ms=12,
    )

    assert report.status == "failed"
    assert report.reason == "proof_validation_failed"


@pytest.mark.parametrize("identity_field", ("source_id", "publication_id"))
def test_transcription_proof_rejects_mixed_ask_identity(identity_field: str) -> None:
    result, matches, answer, environment = _proof_validation_inputs()
    unrelated = replace(
        matches[0],
        evidence_id="ev_ask_only",
        **{identity_field: f"other_{identity_field}"},
    )
    answer = replace(answer, evidence=(unrelated,))

    report = validate_transcription_proof(
        result,
        matches,
        answer,
        expected_source_id="src_1",
        environment=environment,
        duration_ms=12,
    )

    assert report.status == "failed"
    assert report.reason == "proof_validation_failed"


def test_transcription_proof_insufficient_evidence_is_validation_failure() -> None:
    result, matches, answer, environment = _proof_validation_inputs()
    answer = replace(
        answer,
        answer_status="insufficient_evidence",
        evidence=(),
    )

    report = validate_transcription_proof(
        result,
        matches,
        answer,
        expected_source_id="src_1",
        environment=environment,
        duration_ms=12,
    )

    assert report.status == "failed"
    assert report.reason == "proof_validation_failed"
    assert report.ask_status == "insufficient_evidence"


def test_transcription_proof_runner_preserves_insufficient_evidence_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.application import KnowledgeEngine
    from mke.proof.transcription import run_transcription_proof

    _patch_successful_provider(monkeypatch)

    def insufficient_answer(
        self: KnowledgeEngine,
        question: str,
        limit: int = 5,
    ) -> AskResult:
        return AskResult(
            ask_id="ask_none",
            question=question,
            answer_status="insufficient_evidence",
            summary="No active Evidence matched.",
            evidence=(),
            limitations=("Evidence only.",),
        )

    monkeypatch.setattr(KnowledgeEngine, "ask", insufficient_answer)

    report = run_transcription_proof(
        VIDEO_FIXTURES / "spoken-evidence.mp4",
        FasterWhisperTranscriptionConfig(model_revision="a" * 40),
    )

    assert report.status == "failed"
    assert report.reason == "proof_validation_failed"
    assert report.ask_status == "insufficient_evidence"


@pytest.mark.parametrize(
    ("field", "unsafe_value"),
    (
        ("library_version", "/Users/private/secret"),
        ("library_version", r"C:\private\secret"),
        ("device", "token=secret"),
    ),
)
def test_transcription_proof_rejects_unsafe_intake_profile(
    field: str,
    unsafe_value: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.proof.transcription import (
        render_transcription_proof_human,
        render_transcription_proof_json,
        run_transcription_proof,
    )

    def unsafe_provider(command: list[str], **_: object) -> SimpleNamespace:
        return SimpleNamespace(
            returncode=0,
            stdout=_first_party_transcript(**{field: unsafe_value}),
            stderr=b"",
        )

    monkeypatch.setattr("mke.adapters.video.providers._run_bounded_command", unsafe_provider)

    report = run_transcription_proof(
        VIDEO_FIXTURES / "spoken-evidence.mp4",
        FasterWhisperTranscriptionConfig(model_revision="a" * 40),
    )

    rendered = render_transcription_proof_json(report)
    human = render_transcription_proof_human(report)
    assert report.status == "failed"
    assert report.reason == "proof_validation_failed"
    assert report.transcript_intake_report is None
    assert unsafe_value not in rendered + human


def test_transcription_proof_allows_single_hugging_face_model_identifier() -> None:
    result, matches, answer, environment = _proof_validation_inputs()
    assert result.transcript_intake_report is not None
    result = replace(
        result,
        transcript_intake_report=replace(
            result.transcript_intake_report,
            model="Systran/faster-whisper-small",
        ),
    )

    report = validate_transcription_proof(
        result,
        matches,
        answer,
        expected_source_id="src_1",
        environment=environment,
        duration_ms=12,
    )

    assert report.status == "passed"


def test_transcription_proof_environment_allows_pep440_epoch_version() -> None:
    environment = ProofEnvironment(
        python_version="3.13.5",
        os="Darwin",
        architecture="arm64",
        faster_whisper_version="1!2.0",
        ctranslate2_version="4.6.0",
        pyav_version="14.4.0",
    )

    assert environment.faster_whisper_version == "1!2.0"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("run_state", "failed"),
        ("evidence_count", 0),
        ("timestamp_evidence", False),
        ("search_keyword_matched", False),
        ("ask_status", "not_run"),
        ("transcript_intake_report", None),
        ("environment", None),
    ),
)
def test_transcription_proof_passed_report_requires_success_invariants(
    field: str,
    value: object,
) -> None:
    result, _, _, environment = _proof_validation_inputs()
    values: dict[str, object] = {
        "status": "passed",
        "run_state": "published",
        "evidence_count": 2,
        "timestamp_evidence": True,
        "search_keyword_matched": True,
        "ask_status": "evidence_found",
        "transcript_intake_report": result.transcript_intake_report,
        "environment": environment,
        "duration_ms": 12,
    }
    values[field] = value

    with pytest.raises(ValueError, match="passed proof"):
        TranscriptionProofReport(**values)  # pyright: ignore[reportArgumentType]


def test_transcription_proof_validates_timestamp_order_without_exact_transcript(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.proof.transcription import run_transcription_proof

    _patch_successful_provider(monkeypatch)
    report = run_transcription_proof(
        VIDEO_FIXTURES / "spoken-evidence.mp4",
        FasterWhisperTranscriptionConfig(model_revision="a" * 40),
    )

    assert report.timestamp_evidence is True
    assert report.search_keyword_matched is True
    assert not hasattr(report, "transcript")
