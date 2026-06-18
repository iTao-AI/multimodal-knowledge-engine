from __future__ import annotations

import sys
from pathlib import Path

from pytest import CaptureFixture

from mke.cli import main


def _write_fake_transcriber(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "fake_transcriber.py"
    script.write_text(body)
    return script


def _write_video(tmp_path: Path) -> Path:
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake mp4 bytes")
    return video


def _valid_transcriber_body(text: str = "smoke command transcript") -> str:
    return (
        "import json\n"
        "print(json.dumps({"
        "'format':'mke.video_transcript.v1',"
        "'media':{'container':'mp4','video_codec':'h264','audio_codec':'aac','has_audio':True,'duration_ms':1000},"
        f"'segments':[{{'start_ms':0,'end_ms':1000,'text':'{text}'}}]"
        "}))\n"
    )


def test_cli_proof_transcript_smoke_uses_local_command(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    video = _write_video(tmp_path)
    script = _write_fake_transcriber(tmp_path, _valid_transcriber_body())

    assert (
        main(
            [
                "proof",
                "transcript-smoke",
                "--fixture",
                str(video),
                "--",
                sys.executable,
                str(script),
                "{input}",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "mke proof transcript-smoke" in output
    assert "proof=transcript_smoke status=passed" in output
    assert "provider=local_command" in output
    assert "evidence_count=1" in output
    assert str(tmp_path) not in output


def test_cli_proof_transcript_smoke_requires_command(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    video = _write_video(tmp_path)

    assert main(["proof", "transcript-smoke", "--fixture", str(video)]) == 1

    output = capsys.readouterr().out
    assert "problem=video_ingest_failed" in output
    assert "cause=transcript command is required" in output
    assert str(tmp_path) not in output


def test_cli_proof_transcript_smoke_rejects_command_without_input_placeholder(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    video = _write_video(tmp_path)
    script = _write_fake_transcriber(tmp_path, _valid_transcriber_body())

    assert (
        main(
            [
                "proof",
                "transcript-smoke",
                "--fixture",
                str(video),
                "--",
                sys.executable,
                str(script),
            ]
        )
        == 1
    )

    output = capsys.readouterr().out
    assert "problem=video_ingest_failed" in output
    assert "cause=argv must contain exactly one {input} placeholder" in output
    assert str(tmp_path) not in output


def test_cli_proof_transcript_smoke_rejects_invalid_json(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    video = _write_video(tmp_path)
    script = _write_fake_transcriber(tmp_path, "print('{bad')\n")

    assert (
        main(
            [
                "proof",
                "transcript-smoke",
                "--fixture",
                str(video),
                "--",
                sys.executable,
                str(script),
                "{input}",
            ]
        )
        == 1
    )

    output = capsys.readouterr().out
    assert "problem=video_ingest_failed" in output
    assert "cause=video transcript is not valid JSON" in output
    assert str(tmp_path) not in output


def test_cli_proof_transcript_smoke_sanitizes_command_failure(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    video = _write_video(tmp_path)
    secret = "SECRET_STDERR_TOKEN"
    argv_secret = "SECRET_ARGV_TOKEN"
    script = _write_fake_transcriber(
        tmp_path,
        "import sys\n"
        f"sys.stderr.write('{secret} Traceback {tmp_path}')\n"
        "sys.exit(7)\n",
    )

    assert (
        main(
            [
                "proof",
                "transcript-smoke",
                "--fixture",
                str(video),
                "--",
                sys.executable,
                str(script),
                "{input}",
                argv_secret,
            ]
        )
        == 1
    )

    output = capsys.readouterr().out
    assert "problem=video_ingest_failed" in output
    assert "cause=transcript command failed" in output
    assert str(tmp_path) not in output
    assert str(script) not in output
    assert argv_secret not in output
    assert secret not in output
    assert "Traceback" not in output
    assert "mke-transcript-smoke-" not in output
