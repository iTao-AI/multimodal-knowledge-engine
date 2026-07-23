import json
from pathlib import Path
from typing import Literal

import pytest
from pytest import CaptureFixture

from mke.cli import main
from mke.domain import TranscriptIntakeReport
from mke.proof.direct_audio import DirectAudioProofReport
from mke.proof.transcription import ProofEnvironment, TranscriptionProofReport
from mke.runtime import FasterWhisperTranscriptionConfig


def test_cli_proof_run_outputs_human_report(capsys: CaptureFixture[str]) -> None:
    assert main(["proof", "run"]) == 0

    output = capsys.readouterr().out
    assert "mke proof run" in output
    assert "proof=product status=passed cases=8 passed=8 failed=0" in output
    assert "case=cli_pdf_ingest status=passed evidence_count=2 intake_report=present" in output
    assert (
        "case=mcp_search_and_ask status=passed locator=page answer_status=evidence_found"
        in output
    )


def test_cli_proof_run_json_outputs_parseable_report(
    capsys: CaptureFixture[str],
) -> None:
    assert main(["proof", "run", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["proof"] == "product"
    assert payload["status"] == "passed"
    assert payload["cases"] == 8
    assert payload["failed"] == 0
    assert [result["case"] for result in payload["results"]] == [
        "cli_pdf_ingest",
        "cli_pdf_search",
        "cli_failed_reprocess",
        "cli_video_ingest_search",
        "cli_ask",
        "mcp_ingest_file",
        "mcp_get_run",
        "mcp_search_and_ask",
    ]


def _direct_audio_report(status: Literal["passed", "failed"]) -> DirectAudioProofReport:
    return DirectAudioProofReport(
        schema_version="mke.direct_audio_proof.v1",
        status=status,
        media_types=("audio/mpeg", "audio/wav", "audio/mp4") if status == "passed" else (),
        published_run_count=3 if status == "passed" else 0,
        evidence_count=3 if status == "passed" else 0,
        timestamp_evidence=status == "passed",
        search_ask_projection_equal=status == "passed",
        evidence_schema="mke.evidence_ref.v1",
        export_schema="mke.compiled_library_export.v2",
        markdown_format="mke.compiled_markdown.v2",
        consumer_status="passed" if status == "passed" else "failed",
        network_access="not_used",
        proof_mode="model_free",
        asr_execution="not_performed",
        cleanup=True,
        failure_code=None if status == "passed" else "consumer_failed",
        next_step=None if status == "passed" else "check_export_consumer",
    )


@pytest.mark.parametrize(("status", "exit_code"), [("passed", 0), ("failed", 1)])
def test_cli_direct_audio_proof_is_one_closed_json_object(
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
    status: Literal["passed", "failed"],
    exit_code: int,
) -> None:
    def fake_run(**_kwargs: object) -> DirectAudioProofReport:
        return _direct_audio_report(status)

    monkeypatch.setattr(
        "mke.cli.run_direct_audio_proof",
        fake_run,
    )

    assert main(["proof", "direct-audio", "--json"]) == exit_code
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert captured.err == ""
    assert payload["schema_version"] == "mke.direct_audio_proof.v1"
    assert payload["status"] == status
    assert payload["proof_mode"] == "model_free"
    assert payload["asr_execution"] == "not_performed"
    if status == "passed":
        assert "failure_code" not in payload and "next_step" not in payload
    else:
        assert payload["failure_code"] == "consumer_failed"
        assert payload["next_step"] == "check_export_consumer"


def test_cli_direct_audio_human_output_identifies_model_free_boundary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    def fake_run(**_kwargs: object) -> DirectAudioProofReport:
        return _direct_audio_report("passed")

    monkeypatch.setattr(
        "mke.cli.run_direct_audio_proof",
        fake_run,
    )

    assert main(["proof", "direct-audio"]) == 0

    captured = capsys.readouterr()
    assert "proof_mode=model_free" in captured.out
    assert "asr_execution=not_performed" in captured.out


def _transcription_report(
    status: Literal["passed", "failed"] = "passed",
) -> TranscriptionProofReport:
    report = TranscriptIntakeReport(
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
    return TranscriptionProofReport(
        status=status,
        run_state="published" if status == "passed" else "failed",
        evidence_count=2 if status == "passed" else 0,
        timestamp_evidence=status == "passed",
        search_keyword_matched=status == "passed",
        ask_status="evidence_found" if status == "passed" else "not_run",
        transcript_intake_report=report if status == "passed" else None,
        environment=ProofEnvironment(
            python_version="3.13.5",
            os="Darwin",
            architecture="arm64",
            faster_whisper_version="1.2.3",
            ctranslate2_version="4.6.0",
            pyav_version="14.4.0",
        ),
        duration_ms=12,
        reason=None if status == "passed" else "model_not_cached",
    )


def test_cli_transcription_proof_json_uses_fixed_first_party_config(
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    captured: list[tuple[Path, FasterWhisperTranscriptionConfig]] = []

    def fake_run(
        fixture: Path,
        transcription: FasterWhisperTranscriptionConfig,
    ) -> TranscriptionProofReport:
        captured.append((fixture, transcription))
        return _transcription_report()

    monkeypatch.setattr("mke.cli.run_transcription_proof", fake_run)

    assert (
        main(
            [
                "proof",
                "transcription-run",
                "--fixture",
                "tests/fixtures/video/spoken-evidence.mp4",
                "--model-revision",
                "a" * 40,
                "--model-cache",
                "/tmp/model-cache",
                "--json",
            ]
        )
        == 0
    )
    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert output.err == ""
    assert payload["status"] == "passed"
    assert payload["environment"]["os"] == "Darwin"
    assert captured[0][0] == Path("tests/fixtures/video/spoken-evidence.mp4")
    config = captured[0][1]
    assert config.provider == "faster-whisper"
    assert config.model_revision == "a" * 40
    assert config.cache_dir == Path("/tmp/model-cache")


def test_cli_transcription_proof_human_output_is_sanitized_and_failed_is_exit_one(
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    def failed_run(
        fixture: Path,
        transcription: FasterWhisperTranscriptionConfig,
    ) -> TranscriptionProofReport:
        return _transcription_report("failed")

    monkeypatch.setattr(
        "mke.cli.run_transcription_proof",
        failed_run,
    )

    assert main(["proof", "transcription-run"]) == 1
    captured = capsys.readouterr()
    assert "proof=transcription status=failed" in captured.out
    assert "next_step=run_transcription_prepare" in captured.out
    assert "Traceback" not in captured.out + captured.err
    assert "/Users/" not in captured.out + captured.err


def test_cli_transcription_proof_failed_json_is_one_object_and_exit_one(
    monkeypatch: pytest.MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    def failed_run(
        fixture: Path,
        transcription: FasterWhisperTranscriptionConfig,
    ) -> TranscriptionProofReport:
        return _transcription_report("failed")

    monkeypatch.setattr("mke.cli.run_transcription_proof", failed_run)

    assert main(["proof", "transcription-run", "--json"]) == 1
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert captured.err == ""
    assert payload["status"] == "failed"
    assert payload["reason"] == "model_not_cached"


def test_cli_transcription_proof_rejects_provider_selector_and_bad_config_as_usage(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as provider_error:
        main(
            [
                "proof",
                "transcription-run",
                "--transcript-provider",
                "sidecar",
            ]
        )
    assert provider_error.value.code == 2
    provider_output = capsys.readouterr()
    assert provider_output.out == ""
    assert "Traceback" not in provider_output.err

    with pytest.raises(SystemExit) as download_error:
        main(["proof", "transcription-run", "--allow-model-download"])
    assert download_error.value.code == 2
    download_output = capsys.readouterr()
    assert download_output.out == ""
    assert "Traceback" not in download_output.err

    with pytest.raises(SystemExit) as config_error:
        main(["proof", "transcription-run", "--model", "../private"])
    assert config_error.value.code == 2
    config_output = capsys.readouterr()
    assert config_output.out == ""
    assert "model identifier" in config_output.err
    assert "Traceback" not in config_output.err
    assert "/Users/" not in config_output.err
