from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from mke.adapters.video import VideoExtractionError
from mke.adapters.video.providers import (
    LocalCommandTranscriptConfig,
    LocalCommandTranscriptProvider,
)


def _write_script(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "fake_transcriber.py"
    script.write_text(body)
    return script


def _valid_transcript_script() -> str:
    return (
        "import json\n"
        "print(json.dumps({"
        "'format':'mke.video_transcript.v1',"
        "'media':{'container':'mp4','video_codec':'h264','audio_codec':'aac','has_audio':True,'duration_ms':1000},"
        "'segments':[{'start_ms':0,'end_ms':1000,'text':'local command transcript'}]"
        "}))\n"
    )


def test_local_command_provider_parses_stdout_json(tmp_path: Path) -> None:
    script = _write_script(tmp_path, _valid_transcript_script())
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake mp4 bytes")
    provider = LocalCommandTranscriptProvider(
        LocalCommandTranscriptConfig(argv=(sys.executable, str(script), "{input}"))
    )

    result = provider.extract(video)

    assert result.segments[0].text == "local command transcript"
    assert result.extractor_fingerprint == "local-command-video-transcript-v1"


def test_local_command_config_accepts_list_argv() -> None:
    config = LocalCommandTranscriptConfig(argv=["cmd", "{input}"])

    assert config.argv == ("cmd", "{input}")


@pytest.mark.parametrize(
    ("argv", "error_type", "match"),
    [
        ("cmd {input}", TypeError, "argv must be a non-empty sequence of strings"),
        ((), TypeError, "argv must be a non-empty sequence of strings"),
        (("cmd", ""), TypeError, "argv must contain non-empty strings"),
        (("cmd",), ValueError, "exactly one"),
        (("cmd", "{input}", "{input}"), ValueError, "exactly one"),
    ],
)
def test_local_command_config_rejects_invalid_argv(
    argv: Any, error_type: type[Exception], match: str
) -> None:
    with pytest.raises(error_type, match=match):
        LocalCommandTranscriptConfig(argv=argv)


def test_local_command_provider_uses_argv_with_shell_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake mp4 bytes")

    def fake_run(
        command: list[str],
        *,
        shell: bool,
        capture_output: bool,
        timeout: float,
        check: bool,
    ) -> subprocess.CompletedProcess[bytes]:
        captured.update(
            {
                "command": command,
                "shell": shell,
                "capture_output": capture_output,
                "timeout": timeout,
                "check": check,
            }
        )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                b'{"format":"mke.video_transcript.v1",'
                b'"media":{"container":"mp4","video_codec":"h264","audio_codec":"aac","has_audio":true,"duration_ms":1000},'
                b'"segments":[{"start_ms":0,"end_ms":1000,"text":"ok"}]}'
            ),
            stderr=b"",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    provider = LocalCommandTranscriptProvider(
        LocalCommandTranscriptConfig(argv=("fake-transcriber", "--input", "{input}"))
    )

    provider.extract(video)

    assert captured == {
        "command": ["fake-transcriber", "--input", str(video)],
        "shell": False,
        "capture_output": True,
        "timeout": 60.0,
        "check": False,
    }


@pytest.mark.parametrize(
    ("body", "match", "max_stdout_bytes", "max_stderr_bytes"),
    [
        ("import sys\nsys.exit(7)\n", "transcript command failed", 2048, 50),
        ("import time\ntime.sleep(2)\n", "transcript command timed out", 2048, 50),
        ("print('{bad')\n", "not valid JSON", 2048, 50),
        (
            "print('x' * 100)\n",
            "transcript command produced too much stdout",
            50,
            50,
        ),
        (
            "import sys\nsys.stderr.write('x' * 100)\n"
            + _valid_transcript_script(),
            "transcript command produced too much stderr",
            2048,
            50,
        ),
        (
            "import json\n"
            "print(json.dumps({"
            "'format':'mke.video_transcript.v1',"
            "'media':{'container':'mp4','video_codec':'h264','audio_codec':'aac','has_audio':True,'duration_ms':1000},"
            "'segments':[{'start_ms':0,'end_ms':1000,'text':'first'}, {'start_ms':900,'end_ms':1100,'text':'overlap'}]"
            "}))\n",
            "stable timestamp",
            2048,
            50,
        ),
    ],
)
def test_local_command_provider_rejects_failed_outputs(
    tmp_path: Path,
    body: str,
    match: str,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
) -> None:
    script = _write_script(tmp_path, body)
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake mp4 bytes")
    provider = LocalCommandTranscriptProvider(
        LocalCommandTranscriptConfig(
            argv=(sys.executable, str(script), "{input}"),
            timeout_seconds=0.05,
            max_stdout_bytes=max_stdout_bytes,
            max_stderr_bytes=max_stderr_bytes,
        )
    )

    with pytest.raises(VideoExtractionError, match=match):
        provider.extract(video)


def test_local_command_provider_rejects_missing_executable(tmp_path: Path) -> None:
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake mp4 bytes")
    provider = LocalCommandTranscriptProvider(
        LocalCommandTranscriptConfig(argv=("mke-missing-transcriber", "{input}"))
    )

    with pytest.raises(VideoExtractionError, match="executable is missing"):
        provider.extract(video)


def test_local_command_provider_rejects_missing_input(tmp_path: Path) -> None:
    provider = LocalCommandTranscriptProvider(
        LocalCommandTranscriptConfig(argv=(sys.executable, "{input}"))
    )

    with pytest.raises(VideoExtractionError, match="input video is missing"):
        provider.extract(tmp_path / "missing.mp4")
