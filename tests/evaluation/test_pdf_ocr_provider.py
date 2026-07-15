from __future__ import annotations

import copy
import json
import os
import sys
import time
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from mke.adapters.video.process import ActiveProcessController, ProcessOperationId
from mke.evaluation.pdf_ocr_paddle_vl import PdfOcrChildError as PaddleVlChildError
from mke.evaluation.pdf_ocr_paddle_vl import (
    _plain_text,  # pyright: ignore[reportPrivateUsage]
    _read_vendor_artifacts,  # pyright: ignore[reportPrivateUsage]
)
from mke.evaluation.pdf_ocr_paddle_vl import recognize as recognize_paddle_vl
from mke.evaluation.pdf_ocr_ppocrv6 import PdfOcrChildError as PpOcrChildError
from mke.evaluation.pdf_ocr_ppocrv6 import _text  # pyright: ignore[reportPrivateUsage]
from mke.evaluation.pdf_ocr_ppocrv6 import recognize as recognize_ppocrv6
from mke.evaluation.pdf_ocr_provider import (
    OcrEvalPageResult,
    PdfOcrProviderError,
    ProviderCommand,
    _normalize_line_join,  # pyright: ignore[reportPrivateUsage]
    run_provider,
)

PROVIDER = "ppocrv6-medium-cpu-spike-v1"
PROFILE = "phase0-200dpi-plain-text-v1"
FIXTURE_IMAGE = Path("tests/fixtures/pdf-ocr-phase0-v1/documents/english-scan.pdf")
ResultMutation = Callable[[dict[str, object]], object | None]
VendorWriter = Callable[[Path, str], None]


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


def _run(command: ProviderCommand, image: Path, output_root: Path) -> OcrEvalPageResult:
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


def _add_unexpected(payload: dict[str, object]) -> None:
    payload.update({"unexpected": True})


def _remove_lines(payload: dict[str, object]) -> object:
    return payload.pop("lines")


def _change_page(payload: dict[str, object]) -> None:
    payload.update({"page_number": 2})


def _change_provider(payload: dict[str, object]) -> None:
    payload.update({"provider": "wrong-provider"})


def _set_nan_confidence(payload: dict[str, object]) -> None:
    cast(list[dict[str, object]], payload["lines"])[0].update(
        {"confidence": math_nan()}
    )


def _set_invalid_box(payload: dict[str, object]) -> None:
    cast(list[dict[str, object]], payload["lines"])[0].update(
        {"box": [-0.1, 0.2, 0.4, 0.3]}
    )


def _change_normalized_text(payload: dict[str, object]) -> None:
    payload.update({"normalized_text": "different"})


@pytest.mark.parametrize(
    ("mutation", "problem"),
    [
        (_add_unexpected, "pdf_ocr_result_invalid"),
        (_remove_lines, "pdf_ocr_result_invalid"),
        (_change_page, "pdf_ocr_result_invalid"),
        (_change_provider, "pdf_ocr_result_invalid"),
        (_set_nan_confidence, "pdf_ocr_result_invalid"),
        (_set_invalid_box, "pdf_ocr_result_invalid"),
        (_change_normalized_text, "pdf_ocr_result_invalid"),
    ],
)
def test_result_rejects_closed_schema_violations(
    tmp_path: Path,
    mutation: ResultMutation,
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


def test_successful_parent_exit_kills_descendant_process_group(tmp_path: Path) -> None:
    image = tmp_path / "page.png"
    image.write_bytes(b"bounded image")
    marker = tmp_path / "descendant-finished"
    output_root = tmp_path / "output"
    descendant = (
        "import time,pathlib;time.sleep(.3);"
        f"pathlib.Path({str(marker)!r}).write_text('bad')"
    )
    payload = json.dumps(_result())
    script = f"""
import argparse, pathlib, subprocess, sys
p=argparse.ArgumentParser();p.add_argument('--input');p.add_argument('--output');p.add_argument('--page-number');a=p.parse_args()
subprocess.Popen(
    [sys.executable, '-c', {descendant!r}],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
pathlib.Path(a.output).write_text({payload!r}, encoding='utf-8')
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
    )

    result = _run(command, image, output_root)
    time.sleep(0.4)

    assert result.normalized_text == "example"
    assert not marker.exists()


def test_child_environment_is_allowlisted_and_uses_private_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = tmp_path / "page.png"
    image.write_bytes(b"bounded image")
    output_root = tmp_path / "output"
    marker = tmp_path / "environment.json"
    monkeypatch.setenv("MKE_PHASE0_ENV_CANARY", "secret-value")
    monkeypatch.setenv("HTTPS_PROXY", "https://proxy-secret.invalid")
    payload = json.dumps(_result())
    script = f"""
import argparse, json, os, pathlib
p=argparse.ArgumentParser();p.add_argument('--input');p.add_argument('--output');p.add_argument('--page-number');a=p.parse_args()
pathlib.Path({str(marker)!r}).write_text(json.dumps({{
    'canary': os.environ.get('MKE_PHASE0_ENV_CANARY'),
    'proxy': os.environ.get('HTTPS_PROXY'),
    'home': os.environ.get('HOME'),
    'tmpdir': os.environ.get('TMPDIR'),
    'cache': os.environ.get('XDG_CACHE_HOME'),
    'path': os.environ.get('PATH'),
    'lang': os.environ.get('LANG'),
}}), encoding='utf-8')
pathlib.Path(a.output).write_text({payload!r}, encoding='utf-8')
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
    )

    _run(command, image, output_root)
    observed = cast(dict[str, object], json.loads(marker.read_text(encoding="utf-8")))

    assert observed["canary"] is None
    assert observed["proxy"] is None
    for key in ("home", "tmpdir", "cache"):
        assert Path(cast(str, observed[key])).is_relative_to(output_root)
    assert observed["path"]
    assert observed["lang"]
    assert not (output_root / "child-runtime").exists()


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
    def start_process(_argv: tuple[str, ...], _environment: dict[str, str]) -> _FakeProcess:
        return process

    monkeypatch.setattr(pdf_ocr_provider, "_start_process", start_process)
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


def _prepare_vl_call(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    image = tmp_path / "page.png"
    output = tmp_path / "result.json"
    layout = tmp_path / "layout"
    model = tmp_path / "vl"
    image.write_bytes(b"image")
    output.write_bytes(b"")
    layout.mkdir()
    model.mkdir()
    return image, output, layout, model


def _run_fake_vl(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    writer: VendorWriter,
) -> tuple[Path, Path]:
    from mke.evaluation import pdf_ocr_paddle_vl

    image, output, layout, model = _prepare_vl_call(tmp_path)
    private_roots: list[Path] = []

    class FakeResult:
        def save_to_json(self, *, save_path: Path) -> None:
            private_roots.append(Path(save_path))
            writer(Path(save_path), "json")

        def save_to_markdown(self, *, save_path: Path) -> None:
            writer(Path(save_path), "markdown")

    class FakePipeline:
        def predict(self, _input: str) -> list[FakeResult]:
            return [FakeResult()]

    def paddle_ocr_vl(**_kwargs: object) -> FakePipeline:
        return FakePipeline()

    def import_module(_name: str) -> SimpleNamespace:
        return SimpleNamespace(PaddleOCRVL=paddle_ocr_vl)

    monkeypatch.setattr(pdf_ocr_paddle_vl.importlib, "import_module", import_module)
    try:
        recognize_paddle_vl(
            input_image=image,
            output_path=output,
            page_number=1,
            layout_model_dir=layout,
            vl_model_dir=model,
        )
    finally:
        assert private_roots
        assert not private_roots[0].exists()
    return output, private_roots[0]


def _valid_vl_writer(root: Path, kind: str) -> None:
    fixture = _observed_vl_fixture()
    if kind == "json":
        value = copy.deepcopy(fixture["vendor_json"])
        value["parsing_res_list"][0]["block_content"] = "alpha beta"
        (root / "result.json").write_text(json.dumps(value), encoding="utf-8")
    else:
        (root / "result.md").write_text("alpha beta", encoding="utf-8")


def _observed_vl_fixture() -> dict[str, Any]:
    path = Path("src/mke/evaluation/fixtures/paddleocr-vl-1.6-observed.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_paddle_vl_accepts_only_observed_direct_top_level_prose_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _observed_vl_fixture()

    def writer(root: Path, kind: str) -> None:
        if kind == "json":
            (root / "result.json").write_text(
                json.dumps(fixture["vendor_json"]), encoding="utf-8"
            )
        else:
            (root / "result.md").write_text(fixture["markdown"], encoding="utf-8")

    output, _private_root = _run_fake_vl(tmp_path, monkeypatch, writer)
    result = json.loads(output.read_text(encoding="utf-8"))

    assert result["normalized_text"] == fixture["markdown"]
    serialized = output.read_text(encoding="utf-8")
    assert "input_path" not in serialized
    assert "model_settings" not in serialized


def test_paddle_vl_rejects_the_unobserved_nested_result_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def writer(root: Path, kind: str) -> None:
        if kind == "json":
            (root / "result.json").write_text(
                json.dumps(
                    {"res": {"parsing_res_list": [{"block_label": "text", "block_content": "x"}]}}
                ),
                encoding="utf-8",
            )
        else:
            (root / "result.md").write_text("x", encoding="utf-8")

    with pytest.raises(PaddleVlChildError, match="provider result schema is invalid"):
        _run_fake_vl(tmp_path, monkeypatch, writer)


@pytest.mark.parametrize(
    "mutation",
    [
        "extra-top-level-key",
        "boolean-width",
        "page-index",
        "extra-block-key",
        "unsupported-label",
        "non-finite-coordinate",
        "model-setting-drift",
        "layout-label-drift",
        "extra-layout-box",
        "excessive-blocks",
    ],
)
def test_paddle_vl_rejects_observed_schema_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    fixture = _observed_vl_fixture()
    vendor = copy.deepcopy(fixture["vendor_json"])
    if mutation == "extra-top-level-key":
        vendor["unexpected"] = True
    elif mutation == "boolean-width":
        vendor["width"] = True
    elif mutation == "page-index":
        vendor["page_index"] = 0
    elif mutation == "extra-block-key":
        vendor["parsing_res_list"][0]["unexpected"] = 1
    elif mutation == "unsupported-label":
        vendor["parsing_res_list"][0]["block_label"] = "table"
    elif mutation == "non-finite-coordinate":
        vendor["parsing_res_list"][0]["block_polygon_points"][0][0] = float("inf")
    elif mutation == "model-setting-drift":
        vendor["model_settings"]["use_chart_recognition"] = True
    elif mutation == "layout-label-drift":
        vendor["layout_det_res"]["boxes"][0]["label"] = "image"
    elif mutation == "extra-layout-box":
        vendor["layout_det_res"]["boxes"].append(
            copy.deepcopy(vendor["layout_det_res"]["boxes"][0])
        )
    else:
        vendor["parsing_res_list"] = vendor["parsing_res_list"] * 1001

    def writer(root: Path, kind: str) -> None:
        if kind == "json":
            (root / "result.json").write_text(json.dumps(vendor), encoding="utf-8")
        else:
            (root / "result.md").write_text(fixture["markdown"], encoding="utf-8")

    with pytest.raises(PaddleVlChildError, match="provider result schema is invalid"):
        _run_fake_vl(tmp_path, monkeypatch, writer)


def test_paddle_vl_requires_markdown_to_equal_validated_block_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _observed_vl_fixture()

    def writer(root: Path, kind: str) -> None:
        if kind == "json":
            (root / "result.json").write_text(
                json.dumps(fixture["vendor_json"]), encoding="utf-8"
            )
        else:
            (root / "result.md").write_text("different prose", encoding="utf-8")

    with pytest.raises(PaddleVlChildError, match="provider result schema is invalid"):
        _run_fake_vl(tmp_path, monkeypatch, writer)


def test_paddle_vl_fails_closed_on_excessive_json_nesting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def writer(root: Path, kind: str) -> None:
        if kind == "json":
            (root / "result.json").write_text(
                '{"nested":' + "[" * 2000 + "0" + "]" * 2000 + "}",
                encoding="utf-8",
            )
        else:
            (root / "result.md").write_text("plain prose", encoding="utf-8")

    with pytest.raises(PaddleVlChildError, match="provider result schema is invalid"):
        _run_fake_vl(tmp_path, monkeypatch, writer)


@pytest.mark.parametrize("mutation", ["unexpected", "nested", "symlink"])
def test_paddle_vl_rejects_non_exact_regular_file_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    def writer(root: Path, kind: str) -> None:
        _valid_vl_writer(root, kind)
        if kind != "markdown":
            return
        if mutation == "unexpected":
            (root / "unexpected.txt").write_text("bad", encoding="utf-8")
        elif mutation == "nested":
            (root / "nested").mkdir()
            (root / "nested" / "bad.txt").write_text("bad", encoding="utf-8")
        else:
            (root / "result.md").unlink()
            (root / "target.md").write_text("bad", encoding="utf-8")
            (root / "result.md").symlink_to(root / "target.md")

    with pytest.raises(PaddleVlChildError, match="provider result inventory is invalid"):
        _run_fake_vl(tmp_path, monkeypatch, writer)


def test_paddle_vl_rejects_oversized_artifacts_before_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.evaluation import pdf_ocr_paddle_vl

    monkeypatch.setattr(pdf_ocr_paddle_vl, "_MAX_VENDOR_FILE_BYTES", 16)

    with pytest.raises(PaddleVlChildError, match="provider result bytes exceeded"):
        _run_fake_vl(tmp_path, monkeypatch, _valid_vl_writer)


def test_paddle_vl_rejects_aggregate_artifact_bytes_before_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.evaluation import pdf_ocr_paddle_vl

    monkeypatch.setattr(pdf_ocr_paddle_vl, "_MAX_VENDOR_FILE_BYTES", 1024)
    monkeypatch.setattr(pdf_ocr_paddle_vl, "_MAX_VENDOR_TOTAL_BYTES", 32)

    with pytest.raises(PaddleVlChildError, match="provider result bytes exceeded"):
        _run_fake_vl(tmp_path, monkeypatch, _valid_vl_writer)


@pytest.mark.parametrize(
    ("per_file_limit", "aggregate_limit", "grown_bytes"),
    [(16, 4096, 1024), (16, 16, 12)],
    ids=["per-file", "aggregate"],
)
def test_paddle_vl_bounds_actual_descriptor_reads_after_metadata_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    per_file_limit: int,
    aggregate_limit: int,
    grown_bytes: int,
) -> None:
    from mke.evaluation import pdf_ocr_paddle_vl

    root = tmp_path / "vendor"
    root.mkdir()
    json_path = root / "result.json"
    markdown_path = root / "result.md"
    json_path.write_bytes(b"j")
    markdown_path.write_bytes(b"m")
    original_lstat = Path.lstat
    artifact_lstat_calls = 0

    def racing_lstat(path: Path) -> os.stat_result:
        nonlocal artifact_lstat_calls
        metadata = original_lstat(path)
        if path.parent == root:
            artifact_lstat_calls += 1
            if artifact_lstat_calls == 4:
                json_path.write_bytes(b"j" * grown_bytes)
                markdown_path.write_bytes(b"m" * grown_bytes)
        return metadata

    monkeypatch.setattr(Path, "lstat", racing_lstat)
    monkeypatch.setattr(
        pdf_ocr_paddle_vl,
        "_MAX_VENDOR_FILE_BYTES",
        per_file_limit,
    )
    monkeypatch.setattr(
        pdf_ocr_paddle_vl,
        "_MAX_VENDOR_TOTAL_BYTES",
        aggregate_limit,
    )

    with pytest.raises(PaddleVlChildError, match="provider result bytes exceeded"):
        _read_vendor_artifacts(root)

    assert artifact_lstat_calls >= 4
    assert json_path.stat().st_size == grown_bytes
    assert markdown_path.stat().st_size == grown_bytes


def test_paddle_vl_rejects_artifact_replacement_after_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "vendor"
    root.mkdir()
    json_path = root / "result.json"
    markdown_path = root / "result.md"
    json_path.write_bytes(b"j")
    markdown_path.write_bytes(b"m")
    original_identity = json_path.stat().st_ino
    original_lstat = Path.lstat
    artifact_lstat_calls = 0

    def racing_lstat(path: Path) -> os.stat_result:
        nonlocal artifact_lstat_calls
        metadata = original_lstat(path)
        if path.parent == root:
            artifact_lstat_calls += 1
            if artifact_lstat_calls == 4:
                replacement = root / "replacement"
                replacement.write_bytes(b"x" * 1024)
                os.replace(replacement, json_path)
        return metadata

    monkeypatch.setattr(Path, "lstat", racing_lstat)

    with pytest.raises(PaddleVlChildError, match="provider result inventory is invalid"):
        _read_vendor_artifacts(root)

    assert artifact_lstat_calls >= 4
    assert json_path.stat().st_ino != original_identity
    assert json_path.stat().st_size == 1024


def test_paddle_vl_rejects_non_utf8_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def writer(root: Path, kind: str) -> None:
        _valid_vl_writer(root, kind)
        if kind == "markdown":
            (root / "result.md").write_bytes(b"\xff")

    with pytest.raises(PaddleVlChildError, match="provider result schema is invalid"):
        _run_fake_vl(tmp_path, monkeypatch, writer)


@pytest.mark.parametrize(
    "json_payload",
    [
        [],
        {},
        {"res": {"parsing_res_list": "not-a-list"}},
        {"res": {"parsing_res_list": [{"block_label": "table", "block_content": "x"}]}},
    ],
)
def test_paddle_vl_rejects_malformed_or_unsupported_json_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    json_payload: object,
) -> None:
    def writer(root: Path, kind: str) -> None:
        if kind == "json":
            (root / "result.json").write_text(json.dumps(json_payload), encoding="utf-8")
        else:
            (root / "result.md").write_text("plain prose", encoding="utf-8")

    with pytest.raises(PaddleVlChildError, match="provider result schema is invalid"):
        _run_fake_vl(tmp_path, monkeypatch, writer)


@pytest.mark.parametrize(
    "markdown",
    [
        "| A | B |\n| --- | --- |\n| 1 | 2 |",
        "$$ x + y $$",
        "![diagram](image.png)",
        "# layout heading",
    ],
)
def test_paddle_vl_rejects_non_prose_markdown(markdown: str) -> None:
    with pytest.raises(PaddleVlChildError, match="unsupported layout content"):
        _plain_text(markdown)


def test_provider_normalization_contract_is_shared_by_python_children() -> None:
    raw = "  alpha\t beta  \r\ncafe\u0301  "
    expected = "alpha beta\ncafé"

    assert _normalize_line_join((raw,)) == expected
    assert _text(raw) == expected
    assert _plain_text(raw) == expected


def test_swift_child_uses_the_shared_normalization_contract() -> None:
    source = Path("scripts/pdf_ocr_apple_vision.swift").read_text(encoding="utf-8")

    assert "func canonicalText" in source
    assert 'replacingOccurrences(of: "\\r\\n", with: "\\n")' in source
    assert 'replacingOccurrences(of: "\\r", with: "\\n")' in source
    assert "precomposedStringWithCanonicalMapping" in source
    assert "regularExpression" in source


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
