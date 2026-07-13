from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from mke.adapters.video import VideoExtractionError
from mke.adapters.video.contracts import AdapterFailureSpec
from mke.adapters.video.process import ActiveProcessController
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

    assert result.parsed_transcript is not None
    assert result.parsed_transcript.media.duration_ms == 1000
    assert result.parsed_transcript.transcription_provenance is None
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
    script = _write_script(tmp_path, _valid_transcript_script())
    original_popen: Any = subprocess.Popen

    def fail_on_run(*args: object, **kwargs: object) -> object:
        raise AssertionError("capture_output=True is not bounded capture")

    def spy_popen(*args: Any, **kwargs: Any) -> Any:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return original_popen(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", fail_on_run)
    monkeypatch.setattr(subprocess, "Popen", spy_popen)
    provider = LocalCommandTranscriptProvider(
        LocalCommandTranscriptConfig(argv=(sys.executable, str(script), "{input}"))
    )

    provider.extract(video)

    popen_args = captured["args"]
    assert isinstance(popen_args, tuple)
    assert popen_args[0] == [sys.executable, str(script), str(video)]
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["shell"] is False
    assert kwargs["stdout"] == subprocess.PIPE
    assert kwargs["stderr"] == subprocess.PIPE


def test_local_command_provider_rejects_oversized_stdout_before_json_parser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _write_script(
        tmp_path,
        'import sys\nsys.stdout.write(\'{"format":"mke.video_transcript.v1"}\' * 100)\n',
    )
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake mp4 bytes")

    def fail_if_parsed(text: str) -> object:
        raise AssertionError(f"JSON parser should not receive oversized stdout: {text[:8]}")

    monkeypatch.setattr("mke.adapters.video.providers.load_transcript_json", fail_if_parsed)
    provider = LocalCommandTranscriptProvider(
        LocalCommandTranscriptConfig(
            argv=(sys.executable, str(script), "{input}"),
            max_stdout_bytes=50,
        )
    )

    with pytest.raises(
        VideoExtractionError,
        match="transcript command produced too much stdout",
    ):
        provider.extract(video)


def test_local_command_provider_rejects_oversized_stderr_without_leaking_content(
    tmp_path: Path,
) -> None:
    secret = "SECRET_STDERR_VALUE"
    script = _write_script(
        tmp_path,
        f"import sys\nsys.stderr.write('{secret}' * 100)\n" + _valid_transcript_script(),
    )
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake mp4 bytes")
    provider = LocalCommandTranscriptProvider(
        LocalCommandTranscriptConfig(
            argv=(sys.executable, str(script), "{input}"),
            max_stderr_bytes=50,
        )
    )

    with pytest.raises(VideoExtractionError) as exc_info:
        provider.extract(video)

    message = str(exc_info.value)
    assert message == "transcript command produced too much stderr"
    assert secret not in message
    assert str(tmp_path) not in message


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
            "import sys\nsys.stderr.write('x' * 100)\n" + _valid_transcript_script(),
            "transcript command produced too much stderr",
            2048,
            50,
        ),
        (
            "import json\n"
            "print(json.dumps({"
            "'format':'mke.video_transcript.v1',"
            "'media':{'container':'mp4','video_codec':'h264','audio_codec':'aac','has_audio':True,'duration_ms':1000},"
            "'segments':["
            "{'start_ms':0,'end_ms':1000,'text':'first'}, "
            "{'start_ms':900,'end_ms':1100,'text':'overlap'}"
            "]"
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


def test_local_command_provider_sanitizes_process_start_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake mp4 bytes")
    secret = "SECRET_EXECUTION_DETAIL"

    def fail_to_start(*args: object, **kwargs: object) -> object:
        raise PermissionError(f"{secret} {tmp_path}")

    monkeypatch.setattr(subprocess, "Popen", fail_to_start)
    provider = LocalCommandTranscriptProvider(
        LocalCommandTranscriptConfig(argv=("transcribe-wrapper", "{input}"))
    )

    with pytest.raises(VideoExtractionError) as exc_info:
        provider.extract(video)

    assert str(exc_info.value) == "transcript command failed"
    assert secret not in str(exc_info.value)
    assert str(tmp_path) not in str(exc_info.value)


def test_local_command_provider_rejects_missing_input(tmp_path: Path) -> None:
    provider = LocalCommandTranscriptProvider(
        LocalCommandTranscriptConfig(argv=(sys.executable, "{input}"))
    )

    with pytest.raises(VideoExtractionError, match="input video is missing"):
        provider.extract(tmp_path / "missing.mp4")


def test_local_command_provider_maps_configured_exit_code_without_leaking_stderr(
    tmp_path: Path,
) -> None:
    secret = "SECRET_STDERR"
    script = _write_script(
        tmp_path,
        f"import sys\nsys.stderr.write('{secret}')\nsys.exit(21)\n",
    )
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake mp4 bytes")
    provider = LocalCommandTranscriptProvider(
        LocalCommandTranscriptConfig(
            argv=(sys.executable, str(script), "{input}"),
            exit_code_errors={
                21: AdapterFailureSpec(
                    "video_ingest_failed",
                    "configured transcription model is not cached",
                    "run_transcription_prepare",
                )
            },
        )
    )

    with pytest.raises(VideoExtractionError) as exc_info:
        provider.extract(video)

    assert str(exc_info.value) == "configured transcription model is not cached"
    assert exc_info.value.problem == "video_ingest_failed"
    assert exc_info.value.next_step == "run_transcription_prepare"
    assert secret not in str(exc_info.value)


def test_local_command_provider_requires_provenance_when_configured(tmp_path: Path) -> None:
    script = _write_script(tmp_path, _valid_transcript_script())
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake mp4 bytes")
    provider = LocalCommandTranscriptProvider(
        LocalCommandTranscriptConfig(
            argv=(sys.executable, str(script), "{input}"),
            require_provenance=True,
        )
    )

    with pytest.raises(VideoExtractionError, match="provenance"):
        provider.extract(video)


def test_run_bounded_command_cleans_up_on_base_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    killed: list[bool] = []
    waited: list[bool] = []

    class FakePipe:
        def close(self) -> None:
            pass

    class FakeProcess:
        stdout = FakePipe()
        stderr = FakePipe()

        def poll(self) -> None:
            return None

        def kill(self) -> None:
            killed.append(True)

        def wait(self, timeout: float | None = None) -> int:
            waited.append(True)
            return -9

    process = FakeProcess()
    controller = ActiveProcessController()
    operation_id = controller.begin_operation()

    def fake_popen(*args: Any, **kwargs: Any) -> Any:
        return process

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    def interrupt(*args: object, **kwargs: object) -> object:
        raise KeyboardInterrupt

    monkeypatch.setattr("mke.adapters.video.providers._read_bounded_process_output", interrupt)
    provider = LocalCommandTranscriptProvider(
        LocalCommandTranscriptConfig(
            argv=("owned", "{input}"),
            process_controller=controller,
            process_operation_id=operation_id,
        )
    )
    video = Path("sample.mp4")
    video.write_bytes(b"video")

    try:
        with pytest.raises(KeyboardInterrupt):
            provider.extract(video)
    finally:
        video.unlink()

    assert killed == [True]
    assert waited
    controller.end_operation(operation_id)
