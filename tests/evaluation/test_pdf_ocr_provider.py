from __future__ import annotations

import json
import sys
import time
from io import BytesIO
from pathlib import Path
from typing import Any, cast

import pytest

from mke.adapters.video.process import ActiveProcessController, ProcessOperationId
from mke.evaluation.pdf_ocr_paddle_vl import PdfOcrChildError as PaddleVlChildError
from mke.evaluation.pdf_ocr_paddle_vl import recognize as recognize_paddle_vl
from mke.evaluation.pdf_ocr_ppocrv6 import PdfOcrChildError as PpOcrChildError
from mke.evaluation.pdf_ocr_ppocrv6 import recognize as recognize_ppocrv6
from mke.evaluation.pdf_ocr_provider import (
    PdfOcrProviderError,
    ProviderCommand,
    run_provider,
)

PROVIDER = "ppocrv6-medium-cpu-spike-v1"
PROFILE = "phase0-200dpi-plain-text-v1"
FIXTURE_IMAGE = Path("tests/fixtures/pdf-ocr-phase0-v1/documents/english-scan.pdf")


def _result(
    *,
    provider: str = PROVIDER,
    profile: str = PROFILE,
    page_number: int = 1,
) -> dict[str, object]:
    return {
        "schema": "mke.pdf_ocr_eval_result.v1",
        "provider": provider,
        "profile": profile,
        "page_number": page_number,
        "lines": [
            {
                "text": "example",
                "confidence": 0.99,
                "box": [0.1, 0.2, 0.4, 0.3],
            }
        ],
        "normalized_text": "example",
        "duration_ms": 42,
    }


def _fake_command(
    tmp_path: Path,
    *,
    payload: dict[str, object] | str | None = None,
    stdout_bytes: int = 0,
    stderr_bytes: int = 0,
    exit_code: int = 0,
    sleep_seconds: float = 0.0,
    symlink_output: bool = False,
    timeout_seconds: float = 2.0,
    max_stdout_bytes: int = 64 * 1024,
    max_stderr_bytes: int = 256 * 1024,
    max_result_bytes: int = 8 * 1024 * 1024,
) -> tuple[ProviderCommand, Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    image = tmp_path / "page.png"
    image.write_bytes(b"bounded image")
    output_root = tmp_path / "output"
    serialized = "" if payload is None else (
        payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    )
    script = f"""
import argparse, os, pathlib, sys, time
parser = argparse.ArgumentParser()
parser.add_argument('--input', required=True)
parser.add_argument('--output', required=True)
parser.add_argument('--page-number', required=True)
args = parser.parse_args()
sys.stdout.buffer.write(b'x' * {stdout_bytes})
sys.stdout.buffer.flush()
sys.stderr.buffer.write(b'y' * {stderr_bytes})
sys.stderr.buffer.flush()
time.sleep({sleep_seconds!r})
output = pathlib.Path(args.output)
if {symlink_output!r}:
    output.unlink()
    output.symlink_to(pathlib.Path(args.input))
else:
    output.write_text({serialized!r}, encoding='utf-8')
raise SystemExit({exit_code})
"""
    command = ProviderCommand(
        argv=(
            sys.executable,
            "-c",
            script,
            "--input",
            "{input}",
            "--output",
            "{output}",
            "--page-number",
            "{page_number}",
        ),
        provider=PROVIDER,
        profile=PROFILE,
        timeout_seconds=timeout_seconds,
        max_stdout_bytes=max_stdout_bytes,
        max_stderr_bytes=max_stderr_bytes,
        max_result_bytes=max_result_bytes,
    )
    return command, image, output_root


def _run(command: ProviderCommand, image: Path, output_root: Path) -> object:
    return run_provider(command, image_path=image, page_number=1, output_root=output_root)


def test_provider_modules_are_lazy() -> None:
    assert "paddleocr" not in sys.modules
    assert "paddle" not in sys.modules


def test_fake_child_success_has_closed_project_owned_result(tmp_path: Path) -> None:
    command, image, output_root = _fake_command(tmp_path, payload=_result())

    result = _run(command, image, output_root)

    assert result.schema == "mke.pdf_ocr_eval_result.v1"
    assert result.provider == PROVIDER
    assert result.profile == PROFILE
    assert result.page_number == 1
    assert result.normalized_text == "example"
    assert result.lines[0].box == (0.1, 0.2, 0.4, 0.3)


@pytest.mark.parametrize(
    ("mutation", "problem"),
    [
        (lambda payload: payload.update({"unexpected": True}), "pdf_ocr_result_invalid"),
        (lambda payload: payload.pop("lines"), "pdf_ocr_result_invalid"),
        (lambda payload: payload.update({"page_number": 2}), "pdf_ocr_result_invalid"),
        (
            lambda payload: payload.update({"provider": "wrong-provider"}),
            "pdf_ocr_result_invalid",
        ),
        (
            lambda payload: cast(list[dict[str, object]], payload["lines"])[0].update(
                {"confidence": math_nan()}
            ),
            "pdf_ocr_result_invalid",
        ),
        (
            lambda payload: cast(list[dict[str, object]], payload["lines"])[0].update(
                {"box": [-0.1, 0.2, 0.4, 0.3]}
            ),
            "pdf_ocr_result_invalid",
        ),
        (
            lambda payload: payload.update({"normalized_text": "different"}),
            "pdf_ocr_result_invalid",
        ),
    ],
)
def test_result_rejects_closed_schema_violations(
    tmp_path: Path,
    mutation: Any,
    problem: str,
) -> None:
    payload = _result()
    mutation(payload)
    command, image, output_root = _fake_command(tmp_path, payload=payload)

    with pytest.raises(PdfOcrProviderError) as error:
        _run(command, image, output_root)
    assert error.value.problem == problem
    assert error.value.provider == PROVIDER
    assert str(tmp_path) not in str(error.value)


def math_nan() -> float:
    return float("nan")


@pytest.mark.parametrize("payload", [None, "{} trailing", "\xff"])
def test_result_rejects_empty_malformed_and_non_utf8(
    tmp_path: Path,
    payload: str | None,
) -> None:
    command, image, output_root = _fake_command(tmp_path, payload=payload)

    with pytest.raises(PdfOcrProviderError, match="pdf_ocr_result_invalid"):
        _run(command, image, output_root)


def test_result_rejects_symlink_and_oversized_file(tmp_path: Path) -> None:
    command, image, output_root = _fake_command(
        tmp_path / "symlink", payload=_result(), symlink_output=True
    )
    with pytest.raises(PdfOcrProviderError, match="pdf_ocr_result_invalid"):
        _run(command, image, output_root)

    command, image, output_root = _fake_command(
        tmp_path / "large",
        payload=_result() | {"padding": "x" * 1000},
        max_result_bytes=100,
    )
    with pytest.raises(PdfOcrProviderError, match="pdf_ocr_output_limit_exceeded"):
        _run(command, image, output_root)


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_parent_bounds_child_stdout_and_stderr(tmp_path: Path, stream: str) -> None:
    command, image, output_root = _fake_command(
        tmp_path,
        payload=_result(),
        stdout_bytes=1024 if stream == "stdout" else 0,
        stderr_bytes=1024 if stream == "stderr" else 0,
        max_stdout_bytes=32,
        max_stderr_bytes=32,
    )

    with pytest.raises(PdfOcrProviderError, match="pdf_ocr_output_limit_exceeded"):
        _run(command, image, output_root)


def test_timeout_and_negative_exit_are_stable(tmp_path: Path) -> None:
    command, image, output_root = _fake_command(
        tmp_path / "timeout",
        payload=_result(),
        sleep_seconds=2,
        timeout_seconds=0.05,
    )
    with pytest.raises(PdfOcrProviderError) as timeout:
        _run(command, image, output_root)
    assert timeout.value.problem == "pdf_ocr_timeout"

    command, image, output_root = _fake_command(
        tmp_path / "exit", payload=_result(), exit_code=7
    )
    with pytest.raises(PdfOcrProviderError) as failed:
        _run(command, image, output_root)
    assert failed.value.problem == "pdf_ocr_process_failed"


def test_timeout_kills_descendant_process_group(tmp_path: Path) -> None:
    image = tmp_path / "page.png"
    image.write_bytes(b"bounded image")
    marker = tmp_path / "descendant-finished"
    output_root = tmp_path / "output"
    descendant = (
        "import time,pathlib;time.sleep(.3);"
        f"pathlib.Path({str(marker)!r}).write_text('bad')"
    )
    script = f"""
import argparse, subprocess, sys, time
p=argparse.ArgumentParser();p.add_argument('--input');p.add_argument('--output');p.add_argument('--page-number');p.parse_args()
subprocess.Popen([sys.executable, '-c', {descendant!r}])
time.sleep(5)
"""
    command = ProviderCommand(
        argv=(
            sys.executable,
            "-c",
            script,
            "--input",
            "{input}",
            "--output",
            "{output}",
            "--page-number",
            "{page_number}",
        ),
        provider=PROVIDER,
        profile=PROFILE,
        timeout_seconds=0.05,
    )

    with pytest.raises(PdfOcrProviderError, match="pdf_ocr_timeout"):
        _run(command, image, output_root)
    time.sleep(0.4)
    assert not marker.exists()


class _FakeProcess:
    def __init__(self) -> None:
        self.stdout = BytesIO()
        self.stderr = BytesIO()
        self.killed = False
        self.waited = False

    def poll(self) -> int | None:
        return -9 if self.killed else None

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: float | None = None) -> int:
        self.waited = True
        return -9


def test_registration_rejection_kills_waits_and_closes_streams(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.evaluation import pdf_ocr_provider

    command, image, output_root = _fake_command(tmp_path, payload=_result())
    process = _FakeProcess()
    monkeypatch.setattr(pdf_ocr_provider, "_start_process", lambda argv: process)
    controller = ActiveProcessController()

    with pytest.raises(PdfOcrProviderError, match="pdf_ocr_process_failed"):
        run_provider(
            command,
            image_path=image,
            page_number=1,
            output_root=output_root,
            process_controller=controller,
            operation_id=ProcessOperationId("op_unknown"),
        )
    assert process.killed is True
    assert process.waited is True
    assert process.stdout.closed is True
    assert process.stderr.closed is True


def test_missing_model_roots_fail_before_lazy_provider_import(tmp_path: Path) -> None:
    image = tmp_path / "page.png"
    output = tmp_path / "result.json"
    image.write_bytes(b"image")
    output.write_bytes(b"")

    with pytest.raises(PpOcrChildError, match="model directory is unavailable"):
        recognize_ppocrv6(
            input_image=image,
            output_path=output,
            page_number=1,
            detection_model_dir=tmp_path / "missing-det",
            recognition_model_dir=tmp_path / "missing-rec",
        )
    with pytest.raises(PaddleVlChildError, match="model directory is unavailable"):
        recognize_paddle_vl(
            input_image=image,
            output_path=output,
            page_number=1,
            layout_model_dir=tmp_path / "missing-layout",
            vl_model_dir=tmp_path / "missing-vl",
        )
    assert "paddleocr" not in sys.modules


def test_missing_provider_package_is_stable_and_path_free(tmp_path: Path) -> None:
    image = tmp_path / "page.png"
    output = tmp_path / "result.json"
    image.write_bytes(b"image")
    output.write_bytes(b"")
    detection = tmp_path / "det"
    recognition = tmp_path / "rec"
    detection.mkdir()
    recognition.mkdir()

    with pytest.raises(PpOcrChildError) as error:
        recognize_ppocrv6(
            input_image=image,
            output_path=output,
            page_number=1,
            detection_model_dir=detection,
            recognition_model_dir=recognition,
        )
    assert error.value.cause == "PDF OCR optional dependency is not installed"
    assert str(tmp_path) not in str(error.value)


def test_provider_command_rejects_non_fixed_placeholders() -> None:
    with pytest.raises(ValueError, match="fixed placeholders"):
        ProviderCommand(
            argv=("child", "{input}", "{output}"),
            provider=PROVIDER,
            profile=PROFILE,
        )
