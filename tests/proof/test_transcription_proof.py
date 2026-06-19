from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from mke.adapters.video.contracts import AdapterExitCode
from mke.runtime import FasterWhisperTranscriptionConfig
from tests.conftest import VIDEO_FIXTURES


def _first_party_transcript() -> bytes:
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
            "transcription": {
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
            },
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
