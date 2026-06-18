from __future__ import annotations

import json
from pathlib import Path

import pytest

from mke.adapters.video.faster_whisper import (
    ModelPreparationResult,
    ReadinessCheck,
    TranscriptionReadiness,
)
from mke.application import KnowledgeEngine
from mke.cli import main
from mke.runtime import (
    FasterWhisperTranscriptionConfig,
    ModelPreparationConfig,
    RuntimeConfig,
)
from tests.conftest import VIDEO_FIXTURES


def test_prepare_requires_explicit_download_permission() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["transcription", "prepare"])

    assert exc_info.value.code == 2


def test_prepare_json_never_builds_engine(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail_build(config: RuntimeConfig) -> KnowledgeEngine:
        pytest.fail("prepare must not open SQLite")

    def fake_prepare(config: ModelPreparationConfig) -> ModelPreparationResult:
        return ModelPreparationResult("already_cached", "faster-whisper", "small", "a" * 40)

    monkeypatch.setattr("mke.cli.build_engine", fail_build)
    monkeypatch.setattr("mke.cli.prepare_model", fake_prepare)

    assert (
        main(
            [
                "transcription",
                "prepare",
                "--allow-model-download",
                "--model-revision",
                "a" * 40,
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "status": "already_cached",
        "provider": "faster-whisper",
        "model": "small",
        "model_revision": "a" * 40,
    }


def test_doctor_json_is_read_only_and_uses_documented_exit_codes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail_build(config: RuntimeConfig) -> KnowledgeEngine:
        pytest.fail("doctor must not open SQLite")

    def fake_doctor(
        config: FasterWhisperTranscriptionConfig,
    ) -> TranscriptionReadiness:
        return TranscriptionReadiness(
            "not_ready",
            (ReadinessCheck("model", "failed", "model snapshot unavailable"),),
            "configured transcription model is not cached",
            "run_transcription_prepare",
        )

    monkeypatch.setattr("mke.cli.build_engine", fail_build)
    monkeypatch.setattr("mke.cli.doctor_transcription", fake_doctor)

    assert main(["transcription", "doctor", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "not_ready"
    assert payload["cause"] == "configured transcription model is not cached"
    assert "path" not in payload


def test_doctor_rejects_invalid_owner_config_as_usage_without_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["transcription", "doctor", "--model", "../bad", "--json"])

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "model identifier" in captured.err
    assert "Traceback" not in captured.err
    assert "/Users/" not in captured.err


def test_ingest_preflights_explicit_language_before_building_engine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db = tmp_path / "mke.sqlite"

    def unsupported_language(
        config: FasterWhisperTranscriptionConfig,
    ) -> TranscriptionReadiness:
        assert config.language == "fr"
        return TranscriptionReadiness(
            "not_ready",
            (ReadinessCheck("language", "failed", "language unsupported"),),
            "configured language is not supported by the model",
            "choose_supported_language",
        )

    def fail_build(config: RuntimeConfig) -> KnowledgeEngine:
        pytest.fail("readiness must be checked before engine and Run creation")

    monkeypatch.setattr("mke.cli.doctor_transcription", unsupported_language)
    monkeypatch.setattr("mke.cli.build_engine", fail_build)

    assert (
        main(
            [
                "--db",
                str(db),
                "ingest",
                str(VIDEO_FIXTURES / "short-audio.mp4"),
                "--transcript-provider",
                "faster-whisper",
                "--language",
                "fr",
                "--json",
            ]
        )
        == 1
    )

    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "problem": "transcription_not_ready",
        "cause": "configured language is not supported by the model",
        "active_publication_impact": "unchanged",
        "next_step": "choose_supported_language",
    }
    assert not db.exists()


def test_ingest_faster_whisper_uses_shared_runtime_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[RuntimeConfig] = []

    def fake_build(config: RuntimeConfig) -> KnowledgeEngine:
        captured.append(config)
        return KnowledgeEngine(tmp_path / "mke.sqlite")

    def ready(
        config: FasterWhisperTranscriptionConfig,
    ) -> TranscriptionReadiness:
        return TranscriptionReadiness("ready", (), None, None)

    monkeypatch.setattr("mke.cli.build_engine", fake_build)
    monkeypatch.setattr("mke.cli.doctor_transcription", ready)

    assert (
        main(
            [
                "ingest",
                str(VIDEO_FIXTURES / "short-audio.mp4"),
                "--transcript-provider",
                "faster-whisper",
            ]
        )
        == 0
    )
    assert isinstance(captured[0].transcription, FasterWhisperTranscriptionConfig)


def test_default_ingest_runtime_remains_sidecar_backed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[RuntimeConfig] = []

    def fake_build(config: RuntimeConfig) -> KnowledgeEngine:
        captured.append(config)
        return KnowledgeEngine(tmp_path / "mke.sqlite")

    monkeypatch.setattr("mke.cli.build_engine", fake_build)

    assert main(["ingest", str(VIDEO_FIXTURES / "short-audio.mp4")]) == 0
    assert captured[0].transcription.provider == "sidecar"


def test_ingest_and_run_get_json_emit_one_object(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "mke.sqlite"

    assert (
        main(
            [
                "--db",
                str(db),
                "ingest",
                str(VIDEO_FIXTURES / "short-audio.mp4"),
                "--json",
            ]
        )
        == 0
    )
    ingest_output = capsys.readouterr().out
    ingest_payload = json.loads(ingest_output)
    assert ingest_output.count("\n") == 1

    assert main(["--db", str(db), "run", "get", ingest_payload["run_id"], "--json"]) == 0
    run_output = capsys.readouterr().out
    assert run_output.count("\n") == 1
    assert json.loads(run_output)["run"]["run_id"] == ingest_payload["run_id"]
