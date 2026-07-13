from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


def _module():
    from scripts import pdf_ocr_candidate_compatibility

    return pdf_ocr_candidate_compatibility


def _interpreters(tmp_path: Path):
    compatibility = _module()
    first = tmp_path / "python312"
    second = tmp_path / "python313"
    first.write_bytes(b"python")
    second.write_bytes(b"python")
    return (
        compatibility.InterpreterIdentity(first, "3.12.13", "3.12"),
        compatibility.InterpreterIdentity(second, "3.13.12", "3.13"),
    )


def test_matrix_uses_one_wheel_both_interpreters_and_exact_sixteen_cells(
    tmp_path: Path,
) -> None:
    compatibility = _module()
    wheel = tmp_path / "multimodal_knowledge_engine-0.1.1-py3-none-any.whl"
    wheel.write_bytes(b"one immutable wheel")

    plan = compatibility.build_matrix_plan(wheel, _interpreters(tmp_path))

    expected_digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    assert {cell.mke_wheel_sha256 for cell in plan.cells} == {expected_digest}
    assert {cell.python_minor for cell in plan.cells} == {"3.12", "3.13"}
    assert {cell.surface for cell in plan.cells} == {
        "base",
        "embedding",
        "transcription",
        "embedding+transcription",
    }
    assert {cell.candidate for cell in plan.cells} == {
        "paddleocr-vl-1.6-cpu-spike-v1",
        "ppocrv6-medium-cpu-spike-v1",
    }
    assert len(plan.cells) == 16


def test_matrix_rejects_interpreter_aliasing_and_wrong_minors(tmp_path: Path) -> None:
    compatibility = _module()
    wheel = tmp_path / "package.whl"
    wheel.write_bytes(b"wheel")
    python = tmp_path / "python"
    python.write_bytes(b"python")

    with pytest.raises(ValueError, match="alias"):
        compatibility.build_matrix_plan(
            wheel,
            (
                compatibility.InterpreterIdentity(python, "3.12.13", "3.12"),
                compatibility.InterpreterIdentity(python, "3.13.12", "3.13"),
            ),
        )
    with pytest.raises(ValueError, match="3.12 and 3.13"):
        compatibility.build_matrix_plan(
            wheel,
            (
                compatibility.InterpreterIdentity(
                    tmp_path / "first", "3.12.13", "3.12"
                ),
                compatibility.InterpreterIdentity(
                    tmp_path / "second", "3.12.14", "3.12"
                ),
            ),
        )


def test_candidate_pins_and_commands_are_exact_and_model_free(tmp_path: Path) -> None:
    compatibility = _module()
    wheel = tmp_path / "package.whl"
    wheel.write_bytes(b"wheel")
    destination = tmp_path / "wheelhouse"
    cache = tmp_path / "cache"
    python = tmp_path / "python"
    python.write_bytes(b"python")

    pp = compatibility.CANDIDATES["ppocrv6-medium-cpu-spike-v1"]
    vl = compatibility.CANDIDATES["paddleocr-vl-1.6-cpu-spike-v1"]
    assert pp.requirements == ("paddleocr==3.7.0", "paddlepaddle==3.3.1")
    assert vl.requirements == (
        "paddleocr[doc-parser]==3.7.0",
        "paddlepaddle==3.3.1",
    )

    online = compatibility.candidate_download_command(
        python=python,
        wheel=wheel,
        candidate=vl,
        destination=destination,
        cache=cache,
    )
    offline = compatibility.offline_install_command(
        python=python,
        wheel=wheel,
        candidate=pp,
        surface="embedding+transcription",
        wheelhouse=destination,
    )

    assert online[:4] == (str(python), "-m", "pip", "download")
    assert "--only-binary=:all:" in online
    assert "[embedding,transcription]" in " ".join(online)
    assert "doc-parser" in " ".join(online)
    assert offline[:4] == (str(python), "-m", "pip", "install")
    assert "--no-index" in offline
    assert "--find-links" in offline
    assert "uv.lock" not in " ".join((*online, *offline))
    forbidden = ("model", "huggingface.co", "autodl", "http://", "https://")
    assert not any(token in " ".join((*online, *offline)).lower() for token in forbidden)


def test_acquisition_mode_requires_exactly_one_online_or_replay_authority(
    tmp_path: Path,
) -> None:
    compatibility = _module()
    prepared = tmp_path / "prepared"
    prepared.mkdir()

    assert compatibility.validate_acquisition_mode(True, None) is None
    assert compatibility.validate_acquisition_mode(False, prepared) == prepared.resolve()
    with pytest.raises(compatibility.CompatibilityError) as absent:
        compatibility.validate_acquisition_mode(False, None)
    assert absent.value.code == "package_download_not_authorized"
    with pytest.raises(compatibility.CompatibilityError) as ambiguous:
        compatibility.validate_acquisition_mode(True, prepared)
    assert ambiguous.value.code == "acquisition_mode_invalid"


def _receipt() -> dict[str, object]:
    candidates: list[dict[str, object]] = []
    for candidate, pins in (
        (
            "ppocrv6-medium-cpu-spike-v1",
            ["paddleocr==3.7.0", "paddlepaddle==3.3.1"],
        ),
        (
            "paddleocr-vl-1.6-cpu-spike-v1",
            ["paddleocr[doc-parser]==3.7.0", "paddlepaddle==3.3.1"],
        ),
    ):
        cells: list[dict[str, object]] = []
        for python, minor in (("3.12.13", "3.12"), ("3.13.12", "3.13")):
            for surface in (
                "base",
                "embedding",
                "transcription",
                "embedding+transcription",
            ):
                cells.append(
                    {
                        "python": python,
                        "python_minor": minor,
                        "surface": surface,
                        "result": "passed",
                        "failure_code": None,
                        "package_versions": {
                            "multimodal-knowledge-engine": "0.1.1",
                            "paddleocr": "3.7.0",
                            "paddlepaddle": "3.3.1",
                        },
                        "install_bytes": 123,
                    }
                )
        candidates.append(
            {
                "candidate": candidate,
                "profile": "phase0-200dpi-plain-text-v1",
                "pins": pins,
                "distributions": [
                    {
                        "filename": "multimodal_knowledge_engine-0.1.1-py3-none-any.whl",
                        "sha256": "a" * 64,
                        "bytes": 11,
                    },
                    {
                        "filename": "package-1.0-py3-none-any.whl",
                        "sha256": "b" * 64,
                        "bytes": 7,
                    },
                ],
                "download_bytes": 18,
                "cells": cells,
            }
        )
    return {
        "schema": "mke.pdf_ocr_candidate_environments.v1",
        "profile": "phase0-package-only-v1",
        "platform": {"os": "macOS", "architecture": "arm64"},
        "mke_wheel_sha256": "a" * 64,
        "candidates": candidates,
    }


def test_receipt_validator_requires_closed_public_sixteen_cell_evidence() -> None:
    compatibility = _module()
    receipt = _receipt()

    compatibility.validate_receipt(receipt)

    private = copy.deepcopy(receipt)
    private["profile"] = "/Users/example/private"
    with pytest.raises(ValueError, match="receipt"):
        compatibility.validate_receipt(private)
    extra = copy.deepcopy(receipt)
    extra["command"] = ["pip", "install"]
    with pytest.raises(ValueError, match="receipt"):
        compatibility.validate_receipt(extra)
    missing = copy.deepcopy(receipt)
    candidates = missing["candidates"]
    assert isinstance(candidates, list)
    candidate = candidates[0]
    assert isinstance(candidate, dict)
    cells = candidate["cells"]
    assert isinstance(cells, list)
    cells.pop()
    with pytest.raises(ValueError, match="receipt"):
        compatibility.validate_receipt(missing)


def test_receipt_validator_rejects_drifted_pins_and_failed_cell_contract() -> None:
    compatibility = _module()
    drifted = _receipt()
    candidates = drifted["candidates"]
    assert isinstance(candidates, list) and isinstance(candidates[0], dict)
    candidates[0]["pins"] = ["paddleocr==3.7.1", "paddlepaddle==3.3.1"]
    with pytest.raises(ValueError, match="receipt"):
        compatibility.validate_receipt(drifted)

    failed = _receipt()
    failed_candidates = failed["candidates"]
    assert isinstance(failed_candidates, list) and isinstance(failed_candidates[0], dict)
    cells = failed_candidates[0]["cells"]
    assert isinstance(cells, list) and isinstance(cells[0], dict)
    cells[0]["result"] = "resolver_failed"
    cells[0]["failure_code"] = None
    cells[0]["package_versions"] = {}
    with pytest.raises(ValueError, match="receipt"):
        compatibility.validate_receipt(failed)


def test_receipt_validator_rejects_download_byte_drift() -> None:
    compatibility = _module()
    receipt = _receipt()
    candidates = receipt["candidates"]
    assert isinstance(candidates, list) and isinstance(candidates[0], dict)
    candidates[0]["download_bytes"] = 19

    with pytest.raises(ValueError, match="receipt"):
        compatibility.validate_receipt(receipt)


def test_receipt_validator_rejects_empty_successful_inventory() -> None:
    compatibility = _module()
    receipt = _receipt()
    candidates = receipt["candidates"]
    assert isinstance(candidates, list) and isinstance(candidates[0], dict)
    candidates[0]["distributions"] = []
    candidates[0]["download_bytes"] = 0

    with pytest.raises(ValueError, match="receipt"):
        compatibility.validate_receipt(receipt)


def test_receipt_validator_binds_mke_digest_to_candidate_inventories() -> None:
    compatibility = _module()
    receipt = _receipt()
    receipt["mke_wheel_sha256"] = "f" * 64

    with pytest.raises(ValueError, match="receipt"):
        compatibility.validate_receipt(receipt)


def test_bounded_subprocess_rejects_output_and_timeout(tmp_path: Path) -> None:
    compatibility = _module()

    with pytest.raises(compatibility.CompatibilityError) as output:
        compatibility.run_bounded(
            (sys.executable, "-c", "print('x' * 1000)"),
            cwd=tmp_path,
            env={},
            timeout_seconds=2,
            max_stdout_bytes=32,
            max_stderr_bytes=32,
        )
    assert output.value.code == "command_output_exceeded"

    with pytest.raises(compatibility.CompatibilityError) as timeout:
        compatibility.run_bounded(
            (sys.executable, "-c", "import time; time.sleep(2)"),
            cwd=tmp_path,
            env={},
            timeout_seconds=0.05,
            max_stdout_bytes=32,
            max_stderr_bytes=32,
        )
    assert timeout.value.code == "command_timed_out"


@pytest.mark.skipif(os.name != "posix", reason="process-group regression is POSIX-only")
def test_bounded_subprocess_cleans_descendant_after_successful_parent(
    tmp_path: Path,
) -> None:
    compatibility = _module()
    marker = tmp_path / "descendant-marker"
    child = (
        "import pathlib,sys,time;"
        "time.sleep(0.35);"
        "pathlib.Path(sys.argv[1]).write_text('survived',encoding='utf-8')"
    )
    parent = (
        "import subprocess,sys;"
        f"subprocess.Popen([sys.executable,'-c',{child!r},sys.argv[1]],"
        "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,"
        "stderr=subprocess.DEVNULL,close_fds=True)"
    )

    result = compatibility.run_bounded(
        (sys.executable, "-c", parent, str(marker)),
        cwd=tmp_path,
        env=os.environ,
        timeout_seconds=2,
        max_stdout_bytes=1024,
        max_stderr_bytes=1024,
    )
    time.sleep(0.7)

    assert result.returncode == 0
    assert not marker.exists()


def test_installed_identity_accepts_venv_interpreter_symlink(tmp_path: Path) -> None:
    compatibility = _module()
    repository = tmp_path / "repository"
    runtime = tmp_path / "runtime" / "venv"
    module = runtime / "lib/python3.12/site-packages/mke/__init__.py"
    executable = runtime / "bin/python"
    base_executable = tmp_path / "python-base/bin/python3.12"
    module.parent.mkdir(parents=True)
    executable.parent.mkdir(parents=True)
    base_executable.parent.mkdir(parents=True)
    module.write_text("", encoding="utf-8")
    base_executable.write_text("", encoding="utf-8")
    executable.symlink_to(base_executable)

    assert compatibility._valid_installed_identity(
        {
            "mke_file": str(module),
            "sys_executable": str(executable),
            "sys_prefix": str(runtime),
            "sys_base_prefix": str(base_executable.parent.parent),
            "python": "3.12.13",
            "package_versions": {"multimodal-knowledge-engine": "0.1.1"},
        },
        runtime=runtime,
        repository=repository,
        expected_python="3.12.13",
    )


@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        (b"No matching distribution found for paddlepaddle==3.3.1", "resolver_failed"),
        (b"Could not find a version that satisfies the requirement", "resolver_failed"),
        (b"Temporary failure in name resolution", "infrastructure_failed"),
        (b"No space left on device", "infrastructure_failed"),
    ],
)
def test_prepare_failure_classification_separates_resolver_and_infrastructure(
    stderr: bytes,
    expected: str,
) -> None:
    compatibility = _module()

    assert compatibility.classify_prepare_failure(stderr) == expected


def test_receipt_json_is_canonical_and_round_trips() -> None:
    compatibility = _module()
    receipt = _receipt()

    encoded = compatibility.canonical_receipt_bytes(receipt)

    assert encoded.endswith(b"\n")
    assert json.loads(encoded) == receipt
    assert b"/Users/" not in encoded
    compatibility.validate_receipt(json.loads(encoded))


def test_committed_receipt_is_canonical_closed_and_frozen() -> None:
    compatibility = _module()
    root = Path(__file__).resolve().parents[2]
    path = root / "benchmarks/ocr/candidate-environments.json"
    encoded = path.read_bytes()

    receipt = compatibility.validate_committed_receipt_bytes(
        encoded,
        frozen_sha256="df04fff10a7f170b7dbf51ccafba3e189d15f64719a4e172c165bb0a15ee360e",
    )

    candidates = receipt["candidates"]
    assert isinstance(candidates, list)
    assert {candidate["candidate"] for candidate in candidates} == {
        "paddleocr-vl-1.6-cpu-spike-v1",
        "ppocrv6-medium-cpu-spike-v1",
    }
    cells = [cell for candidate in candidates for cell in candidate["cells"]]
    assert len(cells) == 16
    assert {cell["result"] for cell in cells} == {"passed"}
    assert {cell["python"] for cell in cells} == {"3.12.13", "3.13.12"}
    assert {cell["surface"] for cell in cells} == {
        "base",
        "embedding",
        "transcription",
        "embedding+transcription",
    }


def test_script_source_has_no_model_acquisition_surface() -> None:
    source = Path("scripts/pdf_ocr_candidate_compatibility.py")
    if not source.exists():
        pytest.fail("candidate compatibility script is absent")
    text = source.read_text(encoding="utf-8").lower()
    for forbidden in (
        "allow-model-download",
        "snapshot_download",
        "pp-doclayoutv3",
        "pp-ocrv6_medium_det",
        "vl_rec_model_dir",
    ):
        assert forbidden not in text


def test_no_dependency_files_are_modified() -> None:
    root = Path(__file__).resolve().parents[2]
    for relative in ("pyproject.toml", "uv.lock"):
        committed = subprocess.run(
            ["git", "show", f"HEAD:{relative}"],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
        assert (root / relative).read_bytes() == committed
