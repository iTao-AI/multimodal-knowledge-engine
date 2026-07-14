from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
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
                compatibility.InterpreterIdentity(tmp_path / "first", "3.12.13", "3.12"),
                compatibility.InterpreterIdentity(tmp_path / "second", "3.12.14", "3.12"),
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


def test_all_resolver_failed_candidate_emits_mke_only_valid_receipt(
    tmp_path: Path,
) -> None:
    compatibility = _module()
    wheel = tmp_path / "multimodal_knowledge_engine-0.1.1-py3-none-any.whl"
    wheel.write_bytes(b"one built MKE wheel")
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()

    compatibility._bind_candidate_mke_wheel(wheel, wheelhouse, seed=True)

    distributions = compatibility._distribution_receipts(wheelhouse)
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    receipt = _receipt()
    receipt["mke_wheel_sha256"] = digest
    candidates = receipt["candidates"]
    assert isinstance(candidates, list)
    for candidate in candidates:
        assert isinstance(candidate, dict)
        inventory = candidate["distributions"]
        assert isinstance(inventory, list)
        mke = next(
            item
            for item in inventory
            if item["filename"] == "multimodal_knowledge_engine-0.1.1-py3-none-any.whl"
        )
        mke["sha256"] = digest
    failed = candidates[0]
    assert isinstance(failed, dict)
    failed["distributions"] = distributions
    failed["download_bytes"] = wheel.stat().st_size
    cells = failed["cells"]
    assert isinstance(cells, list)
    for cell in cells:
        assert isinstance(cell, dict)
        cell["result"] = "resolver_failed"
        cell["failure_code"] = "resolver_unavailable"
        cell["package_versions"] = {}
        cell["install_bytes"] = 0

    encoded = compatibility.canonical_receipt_bytes(receipt)

    assert distributions == [
        {
            "filename": "multimodal_knowledge_engine-0.1.1-py3-none-any.whl",
            "sha256": digest,
            "bytes": wheel.stat().st_size,
        }
    ]
    assert len(cells) == 8
    assert {cell["result"] for cell in cells} == {"resolver_failed"}
    assert json.loads(encoded) == receipt


def test_candidate_mke_seed_rejects_collision_without_overwrite(tmp_path: Path) -> None:
    compatibility = _module()
    wheel = tmp_path / "multimodal_knowledge_engine-0.1.1-py3-none-any.whl"
    wheel.write_bytes(b"expected")
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    collision = wheelhouse / wheel.name
    collision.write_bytes(b"drifted")

    with pytest.raises(compatibility.CompatibilityError) as error:
        compatibility._bind_candidate_mke_wheel(wheel, wheelhouse, seed=True)

    assert error.value.code == "distribution_identity_drift"
    assert collision.read_bytes() == b"drifted"


def test_prepared_wheelhouse_missing_mke_identity_fails_without_write(
    tmp_path: Path,
) -> None:
    compatibility = _module()
    wheel = tmp_path / "multimodal_knowledge_engine-0.1.1-py3-none-any.whl"
    wheel.write_bytes(b"expected")
    wheelhouse = tmp_path / "prepared"
    wheelhouse.mkdir()

    with pytest.raises(compatibility.CompatibilityError) as error:
        compatibility._bind_candidate_mke_wheel(wheel, wheelhouse, seed=False)

    assert error.value.code == "prepared_wheelhouses_invalid"
    assert tuple(wheelhouse.iterdir()) == ()


def _controller_inputs(tmp_path: Path):
    compatibility = _module()
    repository = tmp_path / "repository"
    repository.mkdir()
    wheel = tmp_path / "multimodal_knowledge_engine-0.1.1-py3-none-any.whl"
    wheel.write_bytes(b"one immutable MKE wheel")
    python312 = tmp_path / "python312"
    python313 = tmp_path / "python313"
    python312.write_bytes(b"python")
    python313.write_bytes(b"python")
    return compatibility, repository, wheel, python312, python313


def _fake_controller_command(compatibility, command, **_kwargs):
    if "-I" in command:
        minor = "3.12" if str(command[0]).endswith("python312") else "3.13"
        version = minor + (".13" if minor == "3.12" else ".12")
        payload = {
            "executable": str(command[0]),
            "version": version,
            "minor": minor,
        }
        return compatibility.CommandResult(0, json.dumps(payload).encode(), b"")
    if "download" in command:
        return compatibility.CommandResult(
            1,
            b"",
            b"No matching distribution found for authorized exact pins",
        )
    pytest.fail(f"unexpected controller command: {command!r}")


def _tree_snapshot(root: Path) -> dict[str, bytes | None]:
    return {
        str(path.relative_to(root)): None if path.is_dir() else path.read_bytes()
        for path in sorted(root.rglob("*"))
    }


def test_controller_emits_valid_negative_when_all_resolvers_fail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compatibility, repository, wheel, python312, python313 = _controller_inputs(tmp_path)
    output = repository / "benchmarks/ocr/candidate-environments.json"
    monkeypatch.setattr(
        compatibility,
        "run_bounded",
        lambda command, **kwargs: _fake_controller_command(compatibility, command, **kwargs),
    )
    monkeypatch.setattr(
        compatibility,
        "_run_offline_cell",
        lambda *_args, **_kwargs: pytest.fail("resolver-failed cells must not run offline replay"),
    )

    receipt = compatibility.run_package_matrix(
        compatibility.CompatibilityConfig(
            repository=repository,
            wheel=wheel,
            interpreters=(python312, python313),
            staging_root=tmp_path / "staging",
            cache_root=tmp_path / "cache",
            output=output,
            allow_package_download=True,
        )
    )

    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    assert receipt["mke_wheel_sha256"] == digest
    candidates = receipt["candidates"]
    assert isinstance(candidates, list) and len(candidates) == 2
    for candidate in candidates:
        assert candidate["distributions"] == [
            {
                "filename": wheel.name,
                "sha256": digest,
                "bytes": wheel.stat().st_size,
            }
        ]
        assert candidate["download_bytes"] == wheel.stat().st_size
        cells = candidate["cells"]
        assert len(cells) == 8
        assert {cell["result"] for cell in cells} == {"resolver_failed"}
        assert {cell["failure_code"] for cell in cells} == {"resolver_unavailable"}
    compatibility.validate_receipt(receipt)
    assert output.read_bytes() == compatibility.canonical_receipt_bytes(receipt)


@pytest.mark.parametrize("prepared_state", ["missing", "drifted"])
def test_controller_rejects_prepared_mke_identity_without_mutating_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prepared_state: str,
) -> None:
    compatibility, repository, wheel, python312, python313 = _controller_inputs(tmp_path)
    prepared = tmp_path / "prepared-wheelhouses"
    for candidate in compatibility.CANDIDATES:
        candidate_root = prepared / candidate
        candidate_root.mkdir(parents=True)
        (candidate_root / "inventory-sentinel.whl").write_bytes(b"preserve")
    if prepared_state == "drifted":
        first_candidate = next(iter(compatibility.CANDIDATES))
        (prepared / first_candidate / wheel.name).write_bytes(b"drifted")
    before = _tree_snapshot(prepared)
    monkeypatch.setattr(
        compatibility,
        "run_bounded",
        lambda command, **kwargs: _fake_controller_command(compatibility, command, **kwargs),
    )

    with pytest.raises(compatibility.CompatibilityError) as error:
        compatibility.run_package_matrix(
            compatibility.CompatibilityConfig(
                repository=repository,
                wheel=wheel,
                interpreters=(python312, python313),
                staging_root=tmp_path / "staging",
                cache_root=tmp_path / "cache",
                output=repository / "benchmarks/ocr/candidate-environments.json",
                allow_package_download=False,
                prepared_wheelhouses=prepared,
            )
        )

    assert error.value.code == "prepared_wheelhouses_invalid"
    assert _tree_snapshot(prepared) == before
    assert not (repository / "benchmarks/ocr/candidate-environments.json").exists()


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
        frozen_sha256="3b8014d0988b3b657fb2ada23ae78ac7d48e4f63eafd4a7074e4c6976d0896ff",
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


def test_model_acquisition_surface_requires_explicit_authority() -> None:
    source = Path("scripts/pdf_ocr_candidate_compatibility.py")
    if not source.exists():
        pytest.fail("candidate compatibility script is absent")
    text = source.read_text(encoding="utf-8").lower()
    assert "--allow-model-download" in text
    assert "model_download_not_authorized" in text
    for forbidden in ("snapshot_download", "trust_remote_code", "autodl", "modelscope"):
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


def _model_metadata(artifact, *, revision=None, license_name=None):
    return {
        "repository": artifact.repository,
        "revision": revision or artifact.revision,
        "license": license_name or artifact.license,
        "files": [
            {"path": path, "bytes": size, "sha256": digest} for path, size, digest in artifact.files
        ],
    }


def test_model_prepare_without_authority_is_stable_noop(tmp_path: Path) -> None:
    compatibility = _module()
    staging = tmp_path / "staging"
    final = tmp_path / "models"
    output = tmp_path / "model-receipt.json"

    with pytest.raises(compatibility.CompatibilityError) as error:
        compatibility.prepare_model_artifacts(
            compatibility.ModelPreparationConfig(
                staging_root=staging,
                final_root=final,
                output=output,
                allow_model_download=False,
            )
        )

    assert error.value.code == "model_download_not_authorized"
    assert not staging.exists()
    assert not final.exists()
    assert not output.exists()


def test_model_prepare_cli_without_authority_is_stable_noop(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    compatibility = _module()
    staging = tmp_path / "staging"
    final = tmp_path / "models"
    output = tmp_path / "receipt.json"

    result = compatibility.main(
        [
            "--prepare-models",
            "--model-staging-root",
            str(staging),
            "--model-final-root",
            str(final),
            "--model-output",
            str(output),
            "--json",
        ]
    )

    assert result == 1
    assert json.loads(capsys.readouterr().out) == {
        "status": "failed",
        "code": "model_download_not_authorized",
    }
    assert not staging.exists() and not final.exists() and not output.exists()


@pytest.mark.parametrize("mutation", ["revision", "license", "inventory", "bytes", "digest"])
def test_model_metadata_drift_fails_closed(mutation: str) -> None:
    compatibility = _module()
    artifact = compatibility.MODEL_ARTIFACTS[0]
    metadata = _model_metadata(artifact)
    if mutation == "revision":
        metadata["revision"] = "0" * 40
    elif mutation == "license":
        metadata["license"] = "unknown"
    elif mutation == "inventory":
        metadata["files"].append({"path": "unexpected.bin", "bytes": 1, "sha256": "f" * 64})
    elif mutation == "bytes":
        metadata["files"][0]["bytes"] += 1
    else:
        metadata["files"][0]["sha256"] = "f" * 64

    with pytest.raises(compatibility.CompatibilityError) as error:
        compatibility.validate_model_metadata(artifact, metadata)

    assert error.value.code == "model_metadata_drift"


def test_model_metadata_accepts_exact_git_blob_and_lfs_identities() -> None:
    compatibility = _module()
    artifact = compatibility.MODEL_ARTIFACTS[0]

    compatibility.validate_model_metadata(artifact, _model_metadata(artifact))


@pytest.mark.parametrize(
    "failure", ["partial", "symlink", "directory", "traversal", "collision", "oversize"]
)
def test_model_prepare_rejects_unsafe_or_incomplete_downloads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    compatibility = _module()
    artifact = compatibility.ModelArtifact(
        candidate="ppocrv6-medium-cpu-spike-v1",
        component="test-model",
        repository="PaddlePaddle/test-model",
        revision="1" * 40,
        license="Apache-2.0",
        files=(("model.bin", 4, hashlib.sha256(b"xxxx").hexdigest()),),
    )

    def downloader(_artifact, file_receipt, destination):
        if failure == "traversal":
            raise compatibility.CompatibilityError("model_inventory_invalid")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if failure == "symlink":
            destination.symlink_to(tmp_path / "outside")
            return
        if failure == "directory":
            destination.mkdir()
            return
        if failure == "collision":
            destination.write_bytes(b"first")
            raise compatibility.CompatibilityError("model_file_collision")
        size = file_receipt[1]
        if failure == "partial":
            size = max(0, size - 1)
        elif failure == "oversize":
            size += 1
        destination.write_bytes(b"x" * size)

    monkeypatch.setattr(compatibility, "MODEL_ARTIFACTS", (artifact,))
    with pytest.raises(compatibility.CompatibilityError) as error:
        compatibility.prepare_model_artifacts(
            compatibility.ModelPreparationConfig(
                staging_root=tmp_path / "staging",
                final_root=tmp_path / "models",
                output=tmp_path / "receipt.json",
                allow_model_download=True,
            ),
            metadata_loader=lambda value: _model_metadata(value),
            downloader=downloader,
        )

    if failure == "directory":
        assert error.value.code == "model_inventory_invalid"

    assert not (tmp_path / "models").exists()
    assert not (tmp_path / "receipt.json").exists()
    assert not (tmp_path / "staging").exists()


def test_model_prepare_publishes_content_addressed_public_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compatibility = _module()
    digest = hashlib.sha256(b"model-bytes").hexdigest()
    artifact = compatibility.ModelArtifact(
        candidate="ppocrv6-medium-cpu-spike-v1",
        component="test-model",
        repository="PaddlePaddle/test-model",
        revision="1" * 40,
        license="Apache-2.0",
        files=(("model.bin", 11, digest),),
    )
    monkeypatch.setattr(compatibility, "MODEL_ARTIFACTS", (artifact,))

    def downloader(_artifact, _file_receipt, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"model-bytes")

    final = tmp_path / "models"
    output = tmp_path / "receipt.json"
    receipt = compatibility.prepare_model_artifacts(
        compatibility.ModelPreparationConfig(
            staging_root=tmp_path / "staging",
            final_root=final,
            output=output,
            allow_model_download=True,
        ),
        metadata_loader=lambda value: _model_metadata(value),
        downloader=downloader,
    )

    compatibility.validate_model_receipt(receipt)
    assert receipt["schema"] == "mke.pdf_ocr_model_artifacts.v1"
    assert receipt["total_bytes"] == 11
    assert output.read_bytes() == compatibility.canonical_model_receipt_bytes(receipt)
    assert final.is_dir()
    assert not (tmp_path / "staging").exists()
    serialized = output.read_text(encoding="utf-8")
    assert str(tmp_path) not in serialized
    assert not any(
        marker in serialized.lower()
        for marker in ("token", "command", "cache", "traceback", "http://", "https://")
    )


def test_model_prepare_rejects_replacement_after_validation_before_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compatibility = _module()
    original = b"original-model"
    replacement = b"changed-model!"
    assert len(original) == len(replacement)
    digest = hashlib.sha256(original).hexdigest()
    artifact = compatibility.ModelArtifact(
        candidate="ppocrv6-medium-cpu-spike-v1",
        component="test-model",
        repository="PaddlePaddle/test-model",
        revision="1" * 40,
        license="Apache-2.0",
        files=(("model.bin", len(original), digest),),
    )
    monkeypatch.setattr(compatibility, "MODEL_ARTIFACTS", (artifact,))
    real_seal = compatibility._make_model_tree_read_only
    replaced = False

    def replace_before_seal(root: Path) -> None:
        nonlocal replaced
        target = next(root.rglob("model.bin"))
        replacement_path = target.with_name("replacement.bin")
        replacement_path.write_bytes(replacement)
        os.replace(replacement_path, target)
        replaced = True
        real_seal(root)

    monkeypatch.setattr(compatibility, "_make_model_tree_read_only", replace_before_seal)

    def downloader(_artifact, _file_receipt, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(original)

    final = tmp_path / "models"
    output = tmp_path / "receipt.json"
    with pytest.raises(compatibility.CompatibilityError, match="model_artifact_invalid"):
        compatibility.prepare_model_artifacts(
            compatibility.ModelPreparationConfig(
                staging_root=tmp_path / "staging",
                final_root=final,
                output=output,
                allow_model_download=True,
            ),
            metadata_loader=lambda value: _model_metadata(value),
            downloader=downloader,
        )

    assert replaced is True
    assert not final.exists()
    assert not output.exists()
    assert not (tmp_path / "staging").exists()


def test_model_tree_rejects_same_size_replacement_between_identity_and_receipt_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compatibility = _module()
    original = b"original-model"
    replacement = b"changed-model!"
    assert len(original) == len(replacement)
    path = tmp_path / "model.bin"
    path.write_bytes(original)
    expected = (("model.bin", len(original), hashlib.sha256(original).hexdigest()),)
    real_sha256 = compatibility.hashlib.sha256
    replaced = False

    class RacingDigest:
        def __init__(self, *args, **kwargs) -> None:
            self._digest = real_sha256(*args, **kwargs)

        def update(self, value: bytes) -> None:
            self._digest.update(value)

        def hexdigest(self) -> str:
            nonlocal replaced
            result = self._digest.hexdigest()
            if not replaced:
                replacement_path = tmp_path / "replacement.bin"
                replacement_path.write_bytes(replacement)
                os.replace(replacement_path, path)
                replaced = True
            return result

    monkeypatch.setattr(compatibility.hashlib, "sha256", RacingDigest)

    with pytest.raises(compatibility.CompatibilityError, match="model_artifact_invalid"):
        compatibility._validated_model_tree(tmp_path, expected)

    assert replaced is True
    assert path.read_bytes() == replacement


def _provider_startup_receipt() -> dict[str, object]:
    return {
        "schema": "mke.pdf_ocr_provider_startup.v1",
        "profile": "phase0-200dpi-plain-text-v1",
        "platform": {"os": "Darwin", "architecture": "arm64"},
        "package_receipt_sha256": "a" * 64,
        "model_receipt_sha256": "b" * 64,
        "network_isolation": {
            "mechanism": "darwin-sandbox-deny-network",
            "canary": "blocked",
        },
        "fixture": {
            "protocol": "pdf-ocr-phase0-v1",
            "document": "english-scan",
            "page": 1,
            "source_sha256": "e" * 64,
        },
        "runtime": {
            "python": "3.13.12",
            "mke_version": "0.1.1",
            "mke_wheel_sha256": "a" * 64,
            "module_origin": "installed-environment",
            "isolated": True,
            "pythonpath": "absent",
            "vendor_fixture_sha256": "f" * 64,
        },
        "providers": [
            {
                "provider": "apple-vision-local-v1",
                "status": "passed",
                "failure_code": None,
                "duration_ms": 547,
                "normalized_text_sha256": "c" * 64,
                "vendor_artifacts": None,
            },
            {
                "provider": "paddleocr-vl-1.6-cpu-spike-v1",
                "status": "failed",
                "failure_code": "vendor_artifact_schema_mismatch",
                "duration_ms": None,
                "normalized_text_sha256": None,
                "vendor_artifacts": {
                    "files": [
                        {"name": "english-scan-page-1.md", "bytes": 51, "sha256": "d" * 64},
                        {
                            "name": "english-scan-page-1_res.json",
                            "bytes": 2458,
                            "sha256": "e" * 64,
                        },
                    ],
                    "json_top_level_keys": ["height", "parsing_res_list"],
                    "parsing_block_keys": ["block_content", "block_label"],
                    "markdown_class": "prose_only",
                    "adapter_result": "rejected_fail_closed",
                },
            },
            {
                "provider": "ppocrv6-medium-cpu-spike-v1",
                "status": "passed",
                "failure_code": None,
                "duration_ms": 14365,
                "normalized_text_sha256": "c" * 64,
                "vendor_artifacts": None,
            },
        ],
    }


def test_provider_startup_receipt_is_closed_and_public_neutral() -> None:
    compatibility = _module()
    receipt = _provider_startup_receipt()

    encoded = compatibility.canonical_provider_startup_bytes(receipt)

    assert json.loads(encoded) == receipt
    private = copy.deepcopy(receipt)
    private["runtime_path"] = "/Users/example/private"
    with pytest.raises(ValueError, match="startup receipt"):
        compatibility.validate_provider_startup_receipt(private)


@pytest.mark.parametrize(
    ("field", "provider_index", "value"),
    [
        ("package_receipt_sha256", None, "a" * 64),
        ("model_receipt_sha256", None, "b" * 64),
        ("normalized_text_sha256", 0, "c" * 64),
        ("normalized_text_sha256", 1, "c" * 64),
        ("normalized_text_sha256", 2, "c" * 64),
    ],
)
def test_provider_startup_authority_rejects_cross_artifact_hash_drift(
    field: str,
    provider_index: int | None,
    value: str,
) -> None:
    compatibility = _module()
    repository = Path(__file__).resolve().parents[2]
    receipt = json.loads((repository / "benchmarks/ocr/provider-startup.json").read_bytes())
    if provider_index is not None:
        receipt["providers"][provider_index][field] = value
    else:
        receipt[field] = value

    compatibility.validate_provider_startup_receipt(receipt)
    with pytest.raises(ValueError, match="startup authority"):
        compatibility.validate_provider_startup_authority(repository, receipt)


def test_committed_provider_startup_receipt_passes_repository_authority() -> None:
    compatibility = _module()
    repository = Path(__file__).resolve().parents[2]
    path = repository / "benchmarks/ocr/provider-startup.json"
    receipt = json.loads(path.read_bytes())

    compatibility.validate_provider_startup_authority(repository, receipt)
    assert path.read_bytes() == compatibility.canonical_provider_startup_bytes(receipt)


def test_provider_startup_authority_rejects_missing_installed_wheel_identity() -> None:
    compatibility = _module()
    repository = Path(__file__).resolve().parents[2]
    receipt = json.loads((repository / "benchmarks/ocr/provider-startup.json").read_bytes())
    receipt.pop("runtime", None)

    with pytest.raises(ValueError, match="startup authority"):
        compatibility.validate_provider_startup_authority(repository, receipt)


@pytest.mark.parametrize("drift", ["repository-shadow", "pythonpath-shadow"])
def test_provider_runtime_identity_rejects_source_shadow(
    tmp_path: Path,
    drift: str,
) -> None:
    compatibility = _module()
    repository = tmp_path / "repository"
    runtime = tmp_path / "runtime"
    repository_module = repository / "src/mke/__init__.py"
    runtime_module = runtime / "lib/python3.13/site-packages/mke/__init__.py"
    module = repository_module if drift == "repository-shadow" else runtime_module
    fixture = Path(
        "src/mke/evaluation/fixtures/paddleocr-vl-1.6-observed.json"
    ).read_text(encoding="utf-8")
    identity = {
        "python": "3.13.12",
        "mke_version": "0.1.1",
        "mke_file": str(module),
        "sys_executable": str(runtime / "bin/python"),
        "sys_prefix": str(runtime),
        "isolated": True,
        "pythonpath_present": drift == "pythonpath-shadow",
        "vendor_fixture_sha256": hashlib.sha256(fixture.encode("utf-8")).hexdigest(),
        "vendor_fixture_text": fixture,
    }

    with pytest.raises(compatibility.CompatibilityError, match="provider_runtime_invalid"):
        compatibility.validate_provider_runtime_identity(
            identity,
            runtime=runtime,
            repository=repository,
            expected_python="3.13.12",
            expected_wheel_sha256="b" * 64,
        )


def test_observed_vendor_fixture_is_packaged_with_mke() -> None:
    repository = Path(__file__).resolve().parents[2]
    fixture = repository / "src/mke/evaluation/fixtures/paddleocr-vl-1.6-observed.json"

    assert fixture.is_file()
    value = json.loads(fixture.read_bytes())
    assert value["markdown"] == "Aurora station uses amber seals for verified cargo."


def test_provider_runtime_identity_returns_public_installed_wheel_binding(
    tmp_path: Path,
) -> None:
    compatibility = _module()
    repository = tmp_path / "repository"
    runtime = tmp_path / "runtime"
    module = runtime / "lib/python3.13/site-packages/mke/__init__.py"
    executable = runtime / "bin/python"
    module.parent.mkdir(parents=True)
    executable.parent.mkdir(parents=True)
    module.write_text("", encoding="utf-8")
    executable.write_text("", encoding="utf-8")
    fixture = Path(
        "src/mke/evaluation/fixtures/paddleocr-vl-1.6-observed.json"
    ).read_text(encoding="utf-8")
    fixture_digest = hashlib.sha256(fixture.encode("utf-8")).hexdigest()
    wheel_digest = "b" * 64
    identity = {
        "python": "3.13.12",
        "mke_version": "0.1.1",
        "mke_file": str(module),
        "sys_executable": str(executable),
        "sys_prefix": str(runtime),
        "isolated": True,
        "pythonpath_present": False,
        "vendor_fixture_sha256": fixture_digest,
        "vendor_fixture_text": fixture,
    }

    public = compatibility.validate_provider_runtime_identity(
        identity,
        runtime=runtime,
        repository=repository,
        expected_python="3.13.12",
        expected_wheel_sha256=wheel_digest,
    )

    assert public == {
        "python": "3.13.12",
        "mke_version": "0.1.1",
        "mke_wheel_sha256": wheel_digest,
        "module_origin": "installed-environment",
        "isolated": True,
        "pythonpath": "absent",
        "vendor_fixture_sha256": fixture_digest,
    }


def test_provider_runtime_identity_accepts_standard_venv_python_symlink(
    tmp_path: Path,
) -> None:
    compatibility = _module()
    repository = tmp_path / "repository"
    runtime = tmp_path / "runtime"
    module = runtime / "lib/python3.13/site-packages/mke/__init__.py"
    base_python = tmp_path / "base/python3.13"
    executable = runtime / "bin/python"
    module.parent.mkdir(parents=True)
    base_python.parent.mkdir(parents=True)
    executable.parent.mkdir(parents=True)
    module.write_text("", encoding="utf-8")
    base_python.write_text("", encoding="utf-8")
    executable.symlink_to(base_python)
    fixture = Path(
        "src/mke/evaluation/fixtures/paddleocr-vl-1.6-observed.json"
    ).read_text(encoding="utf-8")
    identity = {
        "python": "3.13.12",
        "mke_version": "0.1.1",
        "mke_file": str(module),
        "sys_executable": str(executable),
        "sys_prefix": str(runtime),
        "isolated": True,
        "pythonpath_present": False,
        "vendor_fixture_sha256": hashlib.sha256(fixture.encode()).hexdigest(),
        "vendor_fixture_text": fixture,
    }

    public = compatibility.validate_provider_runtime_identity(
        identity,
        runtime=runtime,
        repository=repository,
        expected_python="3.13.12",
        expected_wheel_sha256="b" * 64,
    )

    assert public["module_origin"] == "installed-environment"


def test_provider_startup_controller_runs_from_exact_installed_wheel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compatibility = _module()
    source = Path(__file__).resolve().parents[2]
    repository = tmp_path / "repository"
    benchmark_root = repository / "benchmarks/ocr"
    fixture_root = repository / "tests/fixtures/pdf-ocr-phase0-v1"
    observed_root = repository / "src/mke/evaluation/fixtures"
    benchmark_root.mkdir(parents=True)
    (fixture_root / "documents").mkdir(parents=True)
    observed_root.mkdir(parents=True)
    shutil.copyfile(
        source / "benchmarks/ocr/model-artifacts.json",
        benchmark_root / "model-artifacts.json",
    )
    shutil.copyfile(
        source / "tests/fixtures/pdf-ocr-phase0-v1/protocol.json",
        fixture_root / "protocol.json",
    )
    shutil.copyfile(
        source / "tests/fixtures/pdf-ocr-phase0-v1/documents/english-scan.pdf",
        fixture_root / "documents/english-scan.pdf",
    )
    observed_source = source / "src/mke/evaluation/fixtures/paddleocr-vl-1.6-observed.json"
    observed = observed_source.read_text(encoding="utf-8")
    (observed_root / observed_source.name).write_text(observed, encoding="utf-8")
    wheel = tmp_path / "multimodal_knowledge_engine-0.1.1-py3-none-any.whl"
    wheel.write_bytes(b"current reviewed MKE wheel")
    wheel_digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    package = json.loads((source / "benchmarks/ocr/candidate-environments.json").read_bytes())
    package["mke_wheel_sha256"] = wheel_digest
    for candidate in package["candidates"]:
        for distribution in candidate["distributions"]:
            if distribution["filename"] == wheel.name:
                candidate["download_bytes"] += len(wheel.read_bytes()) - distribution["bytes"]
                distribution["bytes"] = len(wheel.read_bytes())
                distribution["sha256"] = wheel_digest
    (benchmark_root / "candidate-environments.json").write_bytes(
        compatibility.canonical_receipt_bytes(package)
    )
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    shutil.copyfile(wheel, wheelhouse / wheel.name)
    model_root = tmp_path / "models"
    model_root.mkdir()
    apple = tmp_path / "apple-vision"
    apple.write_text("binary", encoding="utf-8")
    python = tmp_path / "python3.13"
    python.write_text("binary", encoding="utf-8")
    monkeypatch.setattr(compatibility, "_revalidate_sealed_model_tree", lambda *_args: None)
    calls: list[tuple[tuple[str, ...], dict[str, str]]] = []

    def fake_run(command, *, env, **_kwargs):
        command = tuple(command)
        calls.append((command, dict(env)))
        if command[1:3] == ("-m", "venv"):
            runtime = Path(command[3])
            module = runtime / "lib/python3.13/site-packages/mke/__init__.py"
            executable = runtime / "bin/python"
            module.parent.mkdir(parents=True)
            executable.parent.mkdir(parents=True)
            module.write_text("", encoding="utf-8")
            executable.write_text("", encoding="utf-8")
            return compatibility.CommandResult(0, b"", b"")
        if "pip" in command and "install" in command:
            return compatibility.CommandResult(0, b"", b"")
        if "importlib.resources" in command[-1]:
            runtime = tmp_path / "startup/venv"
            payload = {
                "python": "3.13.12",
                "mke_version": "0.1.1",
                "mke_file": str(runtime / "lib/python3.13/site-packages/mke/__init__.py"),
                "sys_executable": str(runtime / "bin/python"),
                "sys_prefix": str(runtime),
                "isolated": True,
                "pythonpath_present": False,
                "vendor_fixture_sha256": hashlib.sha256(observed.encode()).hexdigest(),
                "vendor_fixture_text": observed,
            }
            return compatibility.CommandResult(0, json.dumps(payload).encode(), b"")
        if "platform.python_version" in command[-1]:
            payload = {"executable": str(python), "version": "3.13.12", "minor": "3.13"}
            return compatibility.CommandResult(0, json.dumps(payload).encode(), b"")
        if command[-8] == compatibility._INSTALLED_PROVIDER_STARTUP_PROOF:
            text_digest = hashlib.sha256(
                b"Aurora station uses amber seals for verified cargo."
            ).hexdigest()
            providers = [
                {
                    "provider": provider,
                    "status": "passed",
                    "failure_code": None,
                    "duration_ms": index + 1,
                    "normalized_text_sha256": text_digest,
                    "vendor_artifacts": None,
                }
                for index, provider in enumerate(
                    [
                        "apple-vision-local-v1",
                        "paddleocr-vl-1.6-cpu-spike-v1",
                        "ppocrv6-medium-cpu-spike-v1",
                    ]
                )
            ]
            payload = {
                "network_isolation": {
                    "mechanism": "darwin-sandbox-deny-network",
                    "canary": "blocked",
                },
                "providers": providers,
            }
            return compatibility.CommandResult(0, json.dumps(payload).encode(), b"")
        pytest.fail(f"unexpected command: {command!r}")

    monkeypatch.setattr(compatibility, "run_bounded", fake_run)
    receipt = compatibility.run_provider_startup(
        compatibility.ProviderStartupConfig(
            repository=repository,
            wheel=wheel,
            python=python,
            wheelhouse=wheelhouse,
            model_root=model_root,
            apple_executable=apple,
            staging_root=tmp_path / "startup",
            output=benchmark_root / "provider-startup.json",
        )
    )

    compatibility.validate_provider_startup_authority(repository, receipt)
    assert receipt["runtime"]["mke_wheel_sha256"] == wheel_digest
    assert receipt["runtime"]["module_origin"] == "installed-environment"
    assert (benchmark_root / "provider-startup.json").read_bytes() == (
        compatibility.canonical_provider_startup_bytes(receipt)
    )
    assert not (tmp_path / "startup").exists()
    assert all("PYTHONPATH" not in environment for _, environment in calls)
    proof_commands = [
        command
        for command, _ in calls
        if compatibility._INSTALLED_PROVIDER_STARTUP_PROOF in command
    ]
    assert len(proof_commands) == 1
    assert proof_commands[0][0].endswith("/venv/bin/python")
    assert proof_commands[0][1:3] == ("-I", "-c")


def test_provider_startup_authority_writer_is_atomic_and_rejects_drift(
    tmp_path: Path,
) -> None:
    compatibility = _module()
    repository = Path(__file__).resolve().parents[2]
    receipt = json.loads((repository / "benchmarks/ocr/provider-startup.json").read_bytes())
    expected_text = b"Aurora station uses amber seals for verified cargo."
    text_digest = hashlib.sha256(expected_text).hexdigest()
    paddle = receipt["providers"][1]
    paddle.update(
        {
            "status": "passed",
            "failure_code": None,
            "duration_ms": 1,
            "normalized_text_sha256": text_digest,
        }
    )
    paddle["vendor_artifacts"]["adapter_result"] = "accepted_strict_observed_schema"
    output = tmp_path / "provider-startup.json"

    compatibility.write_provider_startup_receipt(repository, receipt, output)
    assert output.read_bytes() == compatibility.canonical_provider_startup_bytes(receipt)

    drifted = copy.deepcopy(receipt)
    drifted["model_receipt_sha256"] = "f" * 64
    rejected = tmp_path / "rejected.json"
    with pytest.raises(ValueError, match="startup authority"):
        compatibility.write_provider_startup_receipt(repository, drifted, rejected)
    assert not rejected.exists()


def test_committed_model_and_startup_receipts_are_canonical_and_frozen() -> None:
    compatibility = _module()
    root = Path(__file__).resolve().parents[2] / "benchmarks/ocr"
    cases = (
        (
            "model-artifacts.json",
            "3d1e8c45b7ed0c817acaeda3f51954b463016763690e09ca1f23162042219d6e",
            compatibility.canonical_model_receipt_bytes,
        ),
    )
    for name, expected_sha256, canonical in cases:
        encoded = (root / name).read_bytes()
        assert hashlib.sha256(encoded).hexdigest() == expected_sha256
        assert encoded == canonical(json.loads(encoded))
