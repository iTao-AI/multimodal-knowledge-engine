from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest


def _report() -> dict[str, object]:
    return {
        "provider": "faster-whisper",
        "model": "small",
        "model_revision": "a" * 40,
        "library_version": "1.2.3",
        "device": "cpu",
        "compute_type": "int8",
        "language": "auto",
        "detected_language": "en",
        "media_duration_ms": 3330,
        "transcription_duration_ms": 300,
        "segment_count": 1,
        "model_source": "cache",
    }


def test_deployment_orchestrator_runs_isolated_locked_cli_and_mcp_flow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import transcription_deployment_proof as proof

    fixture = tmp_path / "spoken-evidence.mp4"
    fixture.write_bytes(b"mp4")
    model_cache = tmp_path / "model-cache"
    model_cache.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    wheel = repo / "dist" / "multimodal_knowledge_engine-0.1.1-py3-none-any.whl"
    wheel.parent.mkdir()
    wheel.write_bytes(b"wheel")
    runtime_root: list[Path] = []
    commands: list[tuple[str, ...]] = []
    command_cwds: list[Path | None] = []
    command_envs: list[dict[str, str] | None] = []
    timeouts: list[float] = []
    limits: list[tuple[int, int]] = []
    report = _report()
    monkeypatch.setenv("PYTHONPATH", str(repo))
    monkeypatch.setenv("PYTHONHOME", str(repo / "python-home"))
    monkeypatch.setenv("VIRTUAL_ENV", str(repo / "source-venv"))

    def fake_tempdir(*, prefix: str) -> SimpleNamespace:
        path = tmp_path / "outside-runtime"
        runtime_root.append(path)

        class TempContext:
            def __enter__(self) -> str:
                path.mkdir()
                return str(path)

            def __exit__(self, *args: object) -> None:
                for child in sorted(path.rglob("*"), reverse=True):
                    if child.is_file():
                        child.unlink()
                    elif child.is_dir():
                        child.rmdir()
                path.rmdir()

        return TempContext()  # type: ignore[return-value]

    def fake_run(
        command: list[str],
        *,
        timeout_seconds: float,
        max_stdout_bytes: int,
        max_stderr_bytes: int,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        accepted_returncodes: frozenset[int] = frozenset({0}),
    ) -> SimpleNamespace:
        commands.append(tuple(command))
        command_cwds.append(cwd)
        command_envs.append(env)
        timeouts.append(timeout_seconds)
        limits.append((max_stdout_bytes, max_stderr_bytes))
        if command[:2] == ["uv", "export"]:
            output_path = Path(command[command.index("--output-file") + 1])
            output_path.write_text("mcp==1.27.2\n")
        if len(command) >= 3 and command[1] == "-c" and "mke.__file__" in command[2]:
            module_file = (
                runtime_root[0]
                / "venv"
                / "lib"
                / "python3.12"
                / "site-packages"
                / "mke"
                / "__init__.py"
            )
            module_file.parent.mkdir(parents=True)
            module_file.write_text("")
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "mke_file": str(module_file),
                        "sys_executable": str(runtime_root[0] / "venv" / "bin" / "python"),
                    }
                ).encode(),
                stderr=b"",
            )
        if "doctor" in command:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"status": "ready"}).encode(),
                stderr=b"",
            )
        if "ingest" in command:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "ok": True,
                        "run_id": "run_cli",
                        "run_state": "published",
                        "evidence_count": 1,
                        "transcript_intake_report": report,
                    }
                ).encode(),
                stderr=b"",
            )
        if "get" in command:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "ok": True,
                        "run": {"run_id": "run_cli", "state": "published"},
                        "transcript_intake_report": report,
                    }
                ).encode(),
                stderr=b"",
            )
        if "search" in command:
            return SimpleNamespace(
                returncode=0,
                stdout=b"timestamp_ms=0..3000 evidence_id=ev_1 text=Evidence remains traceable",
                stderr=b"",
            )
        if "ask" in command:
            return SimpleNamespace(
                returncode=0,
                stdout=b"answer_status=evidence_found evidence_count=1",
                stderr=b"",
            )
        if "mke.proof.mcp_deployment_client" in command:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "status": "passed",
                        "run_state": "published",
                        "evidence_count": 1,
                        "search_keyword_matched": True,
                        "ask_status": "evidence_found",
                        "transcript_intake_report": report,
                    }
                ).encode(),
                stderr=b"",
            )
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(proof.tempfile, "TemporaryDirectory", fake_tempdir)
    monkeypatch.setattr(proof, "repository_root", lambda: repo)
    def fake_select_built_wheel(root: Path) -> Path:
        return wheel

    monkeypatch.setattr(proof, "select_built_wheel", fake_select_built_wheel)
    monkeypatch.setattr(proof, "run_command", fake_run)

    result = proof.run_deployment_proof(
        proof.DeploymentProofConfig(
            fixture=fixture,
            model_cache=model_cache,
            python_version="3.12",
            allow_model_download=False,
        )
    )

    assert result["status"] == "passed"
    cli_result = cast(dict[str, object], result["cli"])
    mcp_result = cast(dict[str, object], result["mcp"])
    identity = cast(dict[str, object], result["report_identity"])
    assert cli_result["run_state"] == "published"
    assert mcp_result["ask_status"] == "evidence_found"
    assert identity["model_revision"] == "a" * 40
    assert runtime_root and not runtime_root[0].exists()
    assert all(timeout > 0 for timeout in timeouts)
    assert all(stdout > 0 and stderr > 0 for stdout, stderr in limits)
    assert commands[0][:2] == ("uv", "build")
    assert commands[1][:2] == ("uv", "export")
    assert commands[2][:2] == ("uv", "venv")
    assert "[transcription]" in " ".join(commands[3])
    assert "mke.__file__" in commands[4][2]
    assert "doctor" in commands[5]
    assert "prepare" not in " ".join(" ".join(command) for command in commands)
    assert any("ingest" in command for command in commands)
    assert any("get" in command for command in commands)
    assert any("search" in command for command in commands)
    assert any("ask" in command for command in commands)
    assert any("mke.proof.mcp_deployment_client" in command for command in commands)
    installed_command_indexes = range(4, len(commands))
    assert all(command_cwds[index] == runtime_root[0] for index in installed_command_indexes)
    for index in installed_command_indexes:
        command_env = command_envs[index]
        assert command_env is not None
        assert "PYTHONPATH" not in command_env
        assert "PYTHONHOME" not in command_env
        assert "VIRTUAL_ENV" not in command_env
    rendered = json.dumps(result)
    for forbidden in (str(tmp_path), str(repo), str(model_cache), "argv", "stderr"):
        assert forbidden not in rendered


def test_deployment_orchestrator_only_prepares_with_explicit_authorization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import transcription_deployment_proof as proof

    fixture = tmp_path / "spoken-evidence.mp4"
    fixture.write_bytes(b"mp4")
    model_cache = tmp_path / "cache"
    model_cache.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    wheel = repo / "dist" / "package.whl"
    wheel.parent.mkdir()
    wheel.write_bytes(b"wheel")
    commands: list[tuple[str, ...]] = []
    report = _report()

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        commands.append(tuple(command))
        if command[:2] == ["uv", "export"]:
            Path(command[command.index("--output-file") + 1]).write_text("mcp==1.27.2\n")
        if len(command) >= 3 and command[1] == "-c" and "mke.__file__" in command[2]:
            runtime_root = cast(Path, kwargs["cwd"])
            environment = runtime_root / "venv"
            module_file = (
                environment / "lib" / "python3.13" / "site-packages" / "mke" / "__init__.py"
            )
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "mke_file": str(module_file),
                        "sys_executable": str(environment / "bin" / "python"),
                    }
                ).encode(),
                stderr=b"",
            )
        if "doctor" in command:
            status = "not_ready" if len([c for c in commands if "doctor" in c]) == 1 else "ready"
            return SimpleNamespace(
                returncode=1 if status == "not_ready" else 0,
                stdout=json.dumps({"status": status}).encode(),
                stderr=b"",
            )
        if "prepare" in command:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"status": "downloaded"}).encode(),
                stderr=b"",
            )
        if "ingest" in command:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "ok": True,
                        "run_id": "run_1",
                        "run_state": "published",
                        "evidence_count": 1,
                        "transcript_intake_report": report,
                    }
                ).encode(),
                stderr=b"",
            )
        if "get" in command:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "ok": True,
                        "run": {"run_id": "run_1", "state": "published"},
                        "transcript_intake_report": report,
                    }
                ).encode(),
                stderr=b"",
            )
        if "search" in command:
            return SimpleNamespace(
                returncode=0,
                stdout=b"timestamp_ms=0..3000 evidence_id=ev_1 text=Evidence",
                stderr=b"",
            )
        if "ask" in command:
            return SimpleNamespace(
                returncode=0,
                stdout=b"answer_status=evidence_found",
                stderr=b"",
            )
        if "mcp_deployment_client" in " ".join(command):
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "status": "passed",
                        "run_state": "published",
                        "evidence_count": 1,
                        "search_keyword_matched": True,
                        "ask_status": "evidence_found",
                        "transcript_intake_report": report,
                    }
                ).encode(),
                stderr=b"",
            )
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(proof, "repository_root", lambda: repo)
    def fake_select_built_wheel(root: Path) -> Path:
        return wheel

    monkeypatch.setattr(proof, "select_built_wheel", fake_select_built_wheel)
    monkeypatch.setattr(proof, "run_command", fake_run)

    result = proof.run_deployment_proof(
        proof.DeploymentProofConfig(
            fixture=fixture,
            model_cache=model_cache,
            python_version="3.13",
            allow_model_download=True,
        )
    )

    assert result["status"] == "passed"
    prepare_commands = [command for command in commands if "prepare" in command]
    assert len(prepare_commands) == 1
    assert "--allow-model-download" in prepare_commands[0]
    doctor_indexes = [index for index, command in enumerate(commands) if "doctor" in command]
    prepare_index = next(index for index, command in enumerate(commands) if "prepare" in command)
    assert doctor_indexes[0] < prepare_index < doctor_indexes[1]


def test_deployment_orchestrator_fails_closed_on_cli_mcp_identity_mismatch(
    tmp_path: Path,
) -> None:
    from scripts.transcription_deployment_proof import compare_report_identity

    cli_report = _report()
    mcp_report = {**_report(), "compute_type": "float16"}

    with pytest.raises(ValueError, match="identity mismatch"):
        compare_report_identity(cli_report, mcp_report)


def test_deployment_orchestrator_rejects_unsafe_report_identity() -> None:
    from scripts.transcription_deployment_proof import compare_report_identity

    unsafe = {**_report(), "library_version": "/Users/private/secret"}

    with pytest.raises(ValueError, match="identity mismatch"):
        compare_report_identity(unsafe, unsafe)


def test_installed_identity_probe_rejects_source_tree_module(
    tmp_path: Path,
) -> None:
    from scripts.transcription_deployment_proof import validate_installed_identity

    repo = tmp_path / "repo"
    repo.mkdir()
    environment = tmp_path / "runtime" / "venv"
    installed_python = environment / "bin" / "python"
    installed_python.parent.mkdir(parents=True)
    source_module = repo / "src" / "mke" / "__init__.py"
    source_module.parent.mkdir(parents=True)
    source_module.write_text("")

    with pytest.raises(
        ValueError,
        match="installed package identity verification failed",
    ):
        validate_installed_identity(
            {
                "mke_file": str(source_module),
                "sys_executable": str(installed_python),
            },
            environment=environment,
            repository=repo,
        )


def test_bounded_command_enforces_output_limit_and_timeout() -> None:
    from scripts.transcription_deployment_proof import (
        DeploymentProofError,
        run_command,
    )

    with pytest.raises(DeploymentProofError, match="output exceeded"):
        run_command(
            [sys.executable, "-c", "print('x' * 100)"],
            timeout_seconds=2,
            max_stdout_bytes=16,
            max_stderr_bytes=16,
        )

    with pytest.raises(DeploymentProofError, match="timed out"):
        run_command(
            [sys.executable, "-c", "import time; time.sleep(2)"],
            timeout_seconds=0.05,
            max_stdout_bytes=16,
            max_stderr_bytes=16,
        )
