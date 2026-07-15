from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/pdf_ocr_phase0_consumer.py"
SCRIPTS = ROOT / "scripts"
SCORECARD = ROOT / "benchmarks/ocr/phase0-scorecard.json"


def _load_consumer() -> ModuleType:
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location("pdf_ocr_phase0_consumer", SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS))


consumer = _load_consumer()


def _wheel(path: Path, version: str = "0.1.2") -> Path:
    wheel = path / f"multimodal_knowledge_engine-{version}-py3-none-any.whl"
    dist_info = f"multimodal_knowledge_engine-{version}.dist-info"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("mke/__init__.py", f'__version__ = "{version}"\n')
        archive.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: 2.4\nName: multimodal-knowledge-engine\nVersion: {version}\n",
        )
        archive.writestr(
            f"{dist_info}/WHEEL",
            "Wheel-Version: 1.0\nTag: py3-none-any\n",
        )
        archive.writestr(f"{dist_info}/RECORD", "")
    return wheel


def _repository(tmp_path: Path) -> tuple[Path, Path, Path]:
    repository = tmp_path / "repository"
    repository.mkdir()
    scorecard = repository / "phase0-scorecard.json"
    scorecard.write_bytes(SCORECARD.read_bytes())
    protocol_root = repository / "tests/fixtures/pdf-ocr-phase0-v1"
    protocol_root.parent.mkdir(parents=True)
    source_protocol_root = ROOT / "tests/fixtures/pdf-ocr-phase0-v1"
    import shutil

    shutil.copytree(source_protocol_root, protocol_root)
    receipt_root = repository / "benchmarks/ocr"
    receipt_root.mkdir(parents=True)
    for name in ("candidate-environments.json", "model-artifacts.json", "provider-startup.json"):
        (receipt_root / name).write_bytes((ROOT / "benchmarks/ocr" / name).read_bytes())
    return repository, _wheel(repository), scorecard


def _config(consumer: ModuleType, repository: Path, wheel: Path, scorecard: Path) -> Any:
    return consumer.ConsumerProofConfig(
        repository=repository,
        wheel=wheel,
        scorecard=scorecard,
        python=sys.executable,
    )


def _successful_runner(consumer: ModuleType, calls: list[list[str]]):
    def run(command: list[str], **_: object) -> Any:
        calls.append(command)
        if command[:2] == ["uv", "venv"]:
            environment = Path(command[2])
            bin_dir = environment / "bin"
            bin_dir.mkdir(parents=True)
            (bin_dir / "python").write_bytes(b"python")
            (bin_dir / "mke").write_bytes(b"mke")
            module = environment / "lib/python3.13/site-packages/mke/__init__.py"
            module.parent.mkdir(parents=True)
            module.write_bytes(b'__version__ = "0.1.2"\n')
            return consumer.CommandResult(0, b"", b"")
        if command[:3] == ["uv", "pip", "install"]:
            return consumer.CommandResult(0, b"", b"")
        if "--internal-identity" in command:
            environment = next(
                path for path in map(Path, command) if path.name == "python"
            ).parents[1]
            payload = {
                "mke_file": str(environment / "lib/python3.13/site-packages/mke/__init__.py"),
                "mke_version": "0.1.2",
                "metadata_version": "0.1.2",
                "python_version": "3.13.12",
                "sys_executable": str(environment / "bin/python"),
            }
            return consumer.CommandResult(0, json.dumps(payload).encode(), b"")
        if "--internal-candidate" in command:
            scorecard_path = Path(command[command.index("--scorecard") + 1])
            decision = json.loads(scorecard_path.read_text())["decision"]
            if decision["status"] == "no_go":
                return consumer.CommandResult(0, b'{"status":"no_go"}', b"")
            payload = {
                "status": "passed",
                "protocol": "pdf-ocr-phase0-v1",
                "provider": "ppocrv6-medium-cpu-spike-v1",
                "profile": "phase0-200dpi-plain-text-v1",
                "publication_verified": True,
            }
            return consumer.CommandResult(0, json.dumps(payload).encode(), b"")
        if "--internal-client" in command:
            payload = {
                "status": "passed",
                "discovery_verified": True,
                "search_verified": True,
                "ask_verified": True,
                "evidence_ref_verified": True,
                "network_blocked": True,
            }
            return consumer.CommandResult(0, json.dumps(payload).encode(), b"")
        raise AssertionError(command)

    return run


def _test_sandbox(
    _runtime_root: Path,
    command: list[str],
) -> list[str]:
    return ["test-deny-network", *command]


def test_controller_reuses_one_installed_wheel_for_runner_and_mcp(tmp_path: Path) -> None:
    repository, wheel, scorecard = _repository(tmp_path)
    calls: list[list[str]] = []

    result = consumer._run_consumer_proof_for_test(
        _config(consumer, repository, wheel, scorecard),
        command_runner=_successful_runner(consumer, calls),
        sandbox_command=_test_sandbox,
    )

    assert result == {
        "schema": "mke.pdf_ocr_phase0_consumer_proof.v1",
        "status": "passed",
        "protocol": "pdf-ocr-phase0-v1",
        "provider": "ppocrv6-medium-cpu-spike-v1",
        "profile": "phase0-200dpi-plain-text-v1",
        "package_version": "0.1.2",
        "python_version": "3.13.12",
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "wheel_reused": True,
        "publication_verified": True,
        "search_verified": True,
        "ask_verified": True,
        "evidence_ref_verified": True,
        "network_blocked": True,
        "cleanup": True,
    }
    assert sum(command[:3] == ["uv", "pip", "install"] for command in calls) == 1
    assert sum("--internal-candidate" in command for command in calls) == 1
    assert sum("--internal-client" in command for command in calls) == 1
    assert all("PYTHONPATH" not in command for command in calls)


@pytest.mark.parametrize(
    ("marker", "code"),
    [
        ("venv", "venv_failed"),
        ("install", "install_failed"),
        ("identity", "schema_failed"),
        ("candidate", "candidate_failed"),
    ],
)
def test_controller_maps_outer_stage_failures(tmp_path: Path, marker: str, code: str) -> None:
    repository, wheel, scorecard = _repository(tmp_path)
    calls: list[list[str]] = []
    successful = _successful_runner(consumer, calls)

    def fail(command: list[str], **kwargs: object) -> Any:
        matched = {
            "venv": command[:2] == ["uv", "venv"],
            "install": command[:3] == ["uv", "pip", "install"],
            "identity": "--internal-identity" in command,
            "candidate": "--internal-candidate" in command,
        }[marker]
        if matched:
            raise consumer.ControllerError("controlled")
        return successful(command, **kwargs)

    with pytest.raises(consumer.ConsumerProofError, match=code):
        consumer._run_consumer_proof_for_test(
            _config(consumer, repository, wheel, scorecard),
            command_runner=fail,
            sandbox_command=_test_sandbox,
        )


@pytest.mark.parametrize(
    "code",
    [
        "ingest_failed",
        "server_failed",
        "discovery_failed",
        "search_failed",
        "ask_failed",
        "locator_failed",
        "schema_failed",
    ],
)
def test_controller_preserves_closed_client_failure_codes(tmp_path: Path, code: str) -> None:
    repository, wheel, scorecard = _repository(tmp_path)
    calls: list[list[str]] = []
    successful = _successful_runner(consumer, calls)

    def fail(command: list[str], **kwargs: object) -> Any:
        if "--internal-client" in command:
            return consumer.CommandResult(
                1, json.dumps({"status": "failed", "code": code}).encode(), b""
            )
        return successful(command, **kwargs)

    with pytest.raises(consumer.ConsumerProofError, match=code):
        consumer._run_consumer_proof_for_test(
            _config(consumer, repository, wheel, scorecard),
            command_runner=fail,
            sandbox_command=_test_sandbox,
        )


def test_controller_rejects_source_checkout_import(tmp_path: Path) -> None:
    repository, wheel, scorecard = _repository(tmp_path)
    calls: list[list[str]] = []
    successful = _successful_runner(consumer, calls)

    def contaminated(command: list[str], **kwargs: object) -> Any:
        result = successful(command, **kwargs)
        if "--internal-identity" in command:
            payload = json.loads(result.stdout)
            payload["mke_file"] = str(repository / "src/mke/__init__.py")
            return consumer.CommandResult(0, json.dumps(payload).encode(), b"")
        return result

    with pytest.raises(consumer.ConsumerProofError, match="schema_failed"):
        consumer._run_consumer_proof_for_test(
            _config(consumer, repository, wheel, scorecard),
            command_runner=contaminated,
            sandbox_command=_test_sandbox,
        )


def test_installed_identity_accepts_exact_venv_python_symlink(tmp_path: Path) -> None:
    repository, wheel_path, _ = _repository(tmp_path)
    environment = tmp_path / "runtime/venv"
    module = environment / "lib/python3.13/site-packages/mke/__init__.py"
    module.parent.mkdir(parents=True)
    module.write_bytes(b'__version__ = "0.1.2"\n')
    base_python = tmp_path / "base/python3.13"
    base_python.parent.mkdir(parents=True)
    base_python.write_bytes(b"python")
    executable = environment / "bin/python"
    executable.parent.mkdir(parents=True)
    executable.symlink_to(base_python)

    version = consumer._validate_installed_identity(
        {
            "mke_file": str(module),
            "mke_version": "0.1.2",
            "metadata_version": "0.1.2",
            "python_version": "3.13.12",
            "sys_executable": str(executable),
        },
        environment=environment,
        repository=repository,
        wheel=consumer._wheel_authority(wheel_path),
    )

    assert version == "3.13.12"


def test_controller_cleanup_failure_overrides_success(tmp_path: Path) -> None:
    repository, wheel, scorecard = _repository(tmp_path)
    calls: list[list[str]] = []

    def fail_cleanup(_: Path) -> None:
        raise OSError("controlled")

    with pytest.raises(consumer.ConsumerProofError, match="cleanup_failed"):
        consumer._run_consumer_proof_for_test(
            _config(consumer, repository, wheel, scorecard),
            command_runner=_successful_runner(consumer, calls),
            sandbox_command=_test_sandbox,
            cleanup=fail_cleanup,
        )


def test_child_environment_keeps_existing_uv_cache_offline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    operator_home = tmp_path / "operator-home"
    cache = operator_home / ".cache/uv"
    cache.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(operator_home))
    monkeypatch.delenv("UV_CACHE_DIR", raising=False)
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "source-shadow"))

    environment = consumer._child_environment(tmp_path / "runtime")

    assert environment["UV_CACHE_DIR"] == str(cache)
    assert environment["UV_OFFLINE"] == "1"
    assert "PYTHONPATH" not in environment


def test_no_go_scorecard_emits_no_provider_claim(tmp_path: Path) -> None:
    repository, wheel, scorecard = _repository(tmp_path)
    value = json.loads(scorecard.read_text())
    for candidate in value["candidates"]:
        candidate["outcome"]["status"] = "failed"
        candidate["outcome"]["failure_codes"] = ["controlled_unavailable"]
    value["decision"] = {
        "status": "no_go",
        "selected_provider": None,
        "selected_profile": None,
    }
    scorecard.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    calls: list[list[str]] = []

    result = consumer._run_consumer_proof_for_test(
        _config(consumer, repository, wheel, scorecard),
        command_runner=_successful_runner(consumer, calls),
        sandbox_command=_test_sandbox,
        validate_scorecard=False,
    )

    assert result["status"] == "no_go"
    assert "provider" not in result and "profile" not in result
    assert not any("--internal-client" in command for command in calls)


def test_private_controller_sandbox_seam_is_host_independent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from mke.evaluation.pdf_ocr_runner import canonical_scorecard_bytes

    assert callable(canonical_scorecard_bytes)
    repository, wheel, scorecard = _repository(tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(consumer.sys, "platform", "linux")

    result = consumer._run_consumer_proof_for_test(
        _config(consumer, repository, wheel, scorecard),
        command_runner=_successful_runner(consumer, calls),
        sandbox_command=_test_sandbox,
    )

    assert result["status"] == "passed"
    sandboxed = [
        command
        for command in calls
        if "--internal-candidate" in command or "--internal-client" in command
    ]
    assert len(sandboxed) == 2
    assert all(command[0] == "test-deny-network" for command in sandboxed)


def test_public_controller_remains_fail_closed_without_darwin_sandbox(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from mke.evaluation.pdf_ocr_runner import canonical_scorecard_bytes

    assert callable(canonical_scorecard_bytes)
    repository, wheel, scorecard = _repository(tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(consumer.sys, "platform", "linux")
    monkeypatch.setattr(consumer, "run_bounded", _successful_runner(consumer, calls))

    with pytest.raises(consumer.ConsumerProofError, match="candidate_failed"):
        consumer.run_consumer_proof(_config(consumer, repository, wheel, scorecard))

    assert not any("--internal-candidate" in command for command in calls)
    assert not any("--internal-client" in command for command in calls)


def test_cli_emits_one_stable_json_object_without_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository, wheel, scorecard = _repository(tmp_path)
    expected: dict[str, object] = {
        "schema": "mke.pdf_ocr_phase0_consumer_proof.v1",
        "status": "passed",
        "protocol": "pdf-ocr-phase0-v1",
        "wheel_reused": True,
        "publication_verified": True,
        "search_verified": True,
        "ask_verified": True,
        "evidence_ref_verified": True,
        "cleanup": True,
    }

    def success(_: object) -> dict[str, object]:
        return expected

    monkeypatch.setattr(consumer, "run_consumer_proof", success)

    assert (
        consumer.main(
            [
                "--wheel",
                str(wheel),
                "--scorecard",
                str(scorecard),
                "--repository",
                str(repository),
                "--json",
            ]
        )
        == 0
    )
    output = capsys.readouterr()
    assert output.out == json.dumps(expected, sort_keys=True, separators=(",", ":")) + "\n"
    assert str(tmp_path) not in output.out


def test_failure_json_is_closed_and_redacted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository, wheel, scorecard = _repository(tmp_path)

    def fail(_: object) -> dict[str, object]:
        raise consumer.ConsumerProofError("search_failed")

    monkeypatch.setattr(consumer, "run_consumer_proof", fail)

    assert (
        consumer.main(
            [
                "--wheel",
                str(wheel),
                "--scorecard",
                str(scorecard),
                "--repository",
                str(repository),
                "--json",
            ]
        )
        == 1
    )
    assert capsys.readouterr().out == '{"code":"search_failed","status":"failed"}\n'
