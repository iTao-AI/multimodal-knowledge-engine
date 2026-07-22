from __future__ import annotations

import json
from pathlib import Path

import pytest

from mke.application import AudioIngestError
from mke.cli import main
from mke.domain import IngestResult, RunState, TranscriptIntakeReport
from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.runtime import RuntimeConfig

AUDIO_FIXTURES = Path(__file__).parents[1] / "fixtures" / "audio"
_OWNER_TEST_FOOTPRINT_BYTES = 12_345_679


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
        media_duration_ms=1_200,
        transcription_duration_ms=25,
        segment_count=1,
        model_source="cache",
    )


@pytest.mark.parametrize("suffix", [".mp3", ".wav", ".m4a", ".MP3", ".WAV", ".M4A"])
def test_cli_audio_uses_canonical_dispatcher_and_owner_startup_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    suffix: str,
) -> None:
    calls: list[Path] = []
    runtimes: list[RuntimeConfig] = []
    result = IngestResult(
        "run_audio",
        RunState.PUBLISHED,
        1,
        transcript_intake_report=_report(),
    )

    class EngineSpy:
        def ingest_file(self, path: Path) -> IngestResult:
            calls.append(path)
            return result

        def close(self) -> None:
            return None

    def build(config: RuntimeConfig) -> EngineSpy:
        runtimes.append(config)
        return EngineSpy()

    monkeypatch.setattr("mke.cli.build_engine", build)
    input_path = tmp_path / f"voice{suffix}"

    assert (
        main(
            [
                "--db",
                str(tmp_path / "mke.sqlite"),
                "ingest",
                str(input_path),
                "--transcript-provider",
                "faster-whisper",
                "--direct-audio-footprint-bytes",
                str(_OWNER_TEST_FOOTPRINT_BYTES),
                "--direct-audio-footprint-budget-mode",
                "baseline_plus",
                "--json",
            ]
        )
        == 0
    )

    assert calls == [input_path]
    assert runtimes[0].direct_audio_footprint_bytes == _OWNER_TEST_FOOTPRINT_BYTES
    assert runtimes[0].direct_audio_footprint_budget_mode == "baseline_plus"
    payload = json.loads(capsys.readouterr().out)
    assert set(payload) == {
        "ok",
        "run_id",
        "run_state",
        "evidence_count",
        "transcript_intake_report",
    }


@pytest.mark.parametrize(
    "owner_args",
    [
        ["--direct-audio-footprint-bytes", str(_OWNER_TEST_FOOTPRINT_BYTES)],
        ["--direct-audio-footprint-budget-mode", "baseline_plus"],
    ],
)
def test_cli_rejects_incomplete_owner_supervision_pair(
    capsys: pytest.CaptureFixture[str],
    owner_args: list[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["ingest", "voice.mp3", *owner_args])

    assert raised.value.code == 2
    assert "direct audio supervision fields must be configured together" in capsys.readouterr().err


def test_mcp_owner_startup_pair_reaches_runtime_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[McpRuntimeConfig] = []

    def run(config: McpRuntimeConfig) -> int:
        observed.append(config)
        return 0

    monkeypatch.setattr("mke.cli.run_mcp_server", run)

    assert (
        main(
            [
                "--db",
                str(tmp_path / "mke.sqlite"),
                "mcp",
                "--allowed-root",
                str(tmp_path),
                "--transcript-provider",
                "faster-whisper",
                "--direct-audio-footprint-bytes",
                str(_OWNER_TEST_FOOTPRINT_BYTES),
                "--direct-audio-footprint-budget-mode",
                "baseline_plus",
            ]
        )
        == 0
    )
    assert observed[0].runtime.direct_audio_footprint_bytes == _OWNER_TEST_FOOTPRINT_BYTES
    assert observed[0].runtime.direct_audio_footprint_budget_mode == "baseline_plus"


@pytest.mark.parametrize("value", ["0", "-1"])
def test_cli_rejects_nonpositive_owner_footprint(
    capsys: pytest.CaptureFixture[str],
    value: str,
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(
            [
                "ingest",
                "voice.mp3",
                "--direct-audio-footprint-bytes",
                value,
                "--direct-audio-footprint-budget-mode",
                "baseline_plus",
            ]
        )

    assert raised.value.code == 2
    assert "positive integer" in capsys.readouterr().err


def test_cli_rejects_absolute_direct_audio_mode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(
            [
                "ingest",
                "voice.mp3",
                "--direct-audio-footprint-bytes",
                str(_OWNER_TEST_FOOTPRINT_BYTES),
                "--direct-audio-footprint-budget-mode",
                "absolute",
            ]
        )

    assert raised.value.code == 2
    assert "invalid choice: 'absolute'" in capsys.readouterr().err


def test_cli_missing_supervision_is_closed_pre_run_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "--db",
                str(tmp_path / "mke.sqlite"),
                "ingest",
                str(AUDIO_FIXTURES / "direct-audio.mp3"),
                "--transcript-provider",
                "faster-whisper",
                "--json",
            ]
        )
        == 1
    )

    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "problem": "transcription_not_ready",
        "cause": "direct audio supervision is not configured",
        "active_publication_impact": "unchanged",
        "next_step": "configure_direct_audio_supervision",
    }


def test_cli_sidecar_owner_is_closed_pre_run_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "--db",
                str(tmp_path / "mke.sqlite"),
                "ingest",
                str(AUDIO_FIXTURES / "direct-audio.mp3"),
                "--json",
            ]
        )
        == 1
    )

    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "problem": "transcription_not_ready",
        "cause": "direct audio requires faster-whisper owner",
        "active_publication_impact": "unchanged",
        "next_step": "configure_faster_whisper_owner",
    }


def test_cli_missing_audio_path_uses_operation_local_safe_cause(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "missing.mp3"

    assert main(["ingest", str(missing), "--json"]) == 1

    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "problem": "input_path_rejected",
        "cause": "input path must exist and be readable",
        "active_publication_impact": "unchanged",
        "next_step": "choose_file_under_allowed_root",
    }


def test_cli_empty_audio_uses_operation_local_safe_cause(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    empty = tmp_path / "empty.wav"
    empty.touch()

    assert main(["ingest", str(empty), "--json"]) == 1

    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "problem": "audio_ingest_failed",
        "cause": "audio input is empty",
        "active_publication_impact": "unchanged",
        "next_step": "choose_supported_file",
    }


def test_cli_unsupported_platform_is_closed_pre_run_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("mke.runtime.platform.system", lambda: "Linux")
    monkeypatch.setattr("mke.runtime.platform.machine", lambda: "x86_64")

    assert (
        main(
            [
                "--db",
                str(tmp_path / "mke.sqlite"),
                "ingest",
                str(AUDIO_FIXTURES / "direct-audio.wav"),
                "--transcript-provider",
                "faster-whisper",
                "--direct-audio-footprint-bytes",
                str(_OWNER_TEST_FOOTPRINT_BYTES),
                "--direct-audio-footprint-budget-mode",
                "baseline_plus",
                "--json",
            ]
        )
        == 1
    )

    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "problem": "transcription_not_ready",
        "cause": "direct audio runtime is supported only on Darwin arm64",
        "active_publication_impact": "unchanged",
        "next_step": "run_on_supported_darwin_arm64",
    }


def test_cli_post_run_audio_error_includes_run_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class EngineSpy:
        def ingest_file(self, path: Path) -> IngestResult:
            raise AudioIngestError(
                "audio publication failed",
                "run_failed",
                next_step="retry_when_owner_ready",
            )

        def close(self) -> None:
            return None

    def build(_config: RuntimeConfig) -> EngineSpy:
        return EngineSpy()

    monkeypatch.setattr("mke.cli.build_engine", build)

    assert main(["ingest", str(tmp_path / "voice.mp3"), "--json"]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "problem": "audio_ingest_failed",
        "cause": "audio publication failed",
        "active_publication_impact": "unchanged",
        "next_step": "retry_when_owner_ready",
        "run_id": "run_failed",
    }


def test_cli_unknown_audio_diagnostic_remains_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class EngineSpy:
        def ingest_file(self, path: Path) -> IngestResult:
            raise AudioIngestError("SECRET_TOKEN /private/provider/stderr")

        def close(self) -> None:
            return None

    def build(_config: RuntimeConfig) -> EngineSpy:
        return EngineSpy()

    monkeypatch.setattr("mke.cli.build_engine", build)

    assert main(["ingest", str(tmp_path / "voice.mp3"), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["cause"] == "operation failed; details were redacted"
    assert "SECRET_TOKEN" not in json.dumps(payload)
    assert "/private/provider/stderr" not in json.dumps(payload)
