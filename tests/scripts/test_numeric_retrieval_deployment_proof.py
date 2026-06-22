import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_config_accepts_only_supported_python_and_wheel(tmp_path: Path) -> None:
    from scripts.numeric_retrieval_deployment_proof import DeploymentProofConfig

    wheel = tmp_path / "mke.whl"
    wheel.write_bytes(b"wheel")

    assert DeploymentProofConfig(wheel=wheel, python_version="3.12").python_version == "3.12"
    with pytest.raises(ValueError, match="python version"):
        DeploymentProofConfig(wheel=wheel, python_version="3.11")
    with pytest.raises(ValueError, match="wheel"):
        DeploymentProofConfig(wheel=tmp_path / "missing.whl", python_version="3.13")


def test_isolated_runtime_environment_removes_source_import_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.numeric_retrieval_deployment_proof import isolated_runtime_environment

    monkeypatch.setenv("PYTHONPATH", "/repo/src")
    monkeypatch.setenv("PYTHONHOME", "/repo/python")
    monkeypatch.setenv("VIRTUAL_ENV", "/repo/.venv")

    environment = isolated_runtime_environment()

    assert "PYTHONPATH" not in environment
    assert "PYTHONHOME" not in environment
    assert "VIRTUAL_ENV" not in environment


def test_installed_identity_rejects_source_tree_import(tmp_path: Path) -> None:
    from scripts.numeric_retrieval_deployment_proof import validate_installed_identity

    repository = tmp_path / "repo"
    source_module = repository / "src" / "mke" / "__init__.py"
    source_module.parent.mkdir(parents=True)
    source_module.write_text("")
    environment = tmp_path / "runtime" / "venv"
    installed_python = environment / "bin" / "python"

    with pytest.raises(ValueError, match="installed package identity"):
        validate_installed_identity(
            {
                "mke_file": str(source_module),
                "sys_executable": str(installed_python),
            },
            environment=environment,
            repository=repository,
        )


def test_wheel_install_is_offline_and_uses_isolated_interpreter(
    tmp_path: Path,
) -> None:
    from scripts.numeric_retrieval_deployment_proof import wheel_install_command

    python = tmp_path / "venv" / "bin" / "python"
    wheel = tmp_path / "mke.whl"

    command = wheel_install_command(python, wheel)

    assert command == (
        "uv",
        "pip",
        "install",
        "--offline",
        "--python",
        str(python),
        str(wheel),
    )
    assert "--offline" in command


def test_isolated_runtime_environment_forces_uv_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.numeric_retrieval_deployment_proof import isolated_runtime_environment

    monkeypatch.delenv("UV_OFFLINE", raising=False)

    environment = isolated_runtime_environment()

    assert environment["UV_OFFLINE"] == "1"


def test_offline_install_failure_is_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import numeric_retrieval_deployment_proof as proof

    def unavailable_dependency(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=1, stdout="", stderr="package unavailable offline")

    monkeypatch.setattr(proof.subprocess, "run", unavailable_dependency)

    with pytest.raises(RuntimeError, match="deployment proof command failed"):
        proof._run(  # pyright: ignore[reportPrivateUsage]
            proof.wheel_install_command(
                tmp_path / "venv" / "bin" / "python",
                tmp_path / "package.whl",
            ),
            cwd=tmp_path,
            environment={"UV_OFFLINE": "1"},
        )


def test_default_cli_command_omits_policy_and_rollback_is_explicit(
    tmp_path: Path,
) -> None:
    from scripts.numeric_retrieval_deployment_proof import cli_search_command

    default = cli_search_command(
        tmp_path / "mke",
        tmp_path / "mke.sqlite",
        "410000 grouped comma control",
        policy=None,
    )
    rollback = cli_search_command(
        tmp_path / "mke",
        tmp_path / "mke.sqlite",
        "410000 grouped comma control",
        policy="current",
    )

    assert "--retrieval-query-policy" not in default
    assert rollback[-4:-2] == ("--retrieval-query-policy", "current")


def test_default_mcp_command_omits_policy_and_rollback_is_explicit(
    tmp_path: Path,
) -> None:
    from scripts.numeric_retrieval_deployment_proof import mcp_client_command

    default = mcp_client_command(
        python=tmp_path / "python",
        client=tmp_path / "client.py",
        mke=tmp_path / "mke",
        db=tmp_path / "mke.sqlite",
        root=tmp_path,
        fixture="fixture.pdf",
        policy=None,
        ingest=True,
    )
    rollback = mcp_client_command(
        python=tmp_path / "python",
        client=tmp_path / "client.py",
        mke=tmp_path / "mke",
        db=tmp_path / "mke.sqlite",
        root=tmp_path,
        fixture="fixture.pdf",
        policy="current",
        ingest=False,
    )

    assert "--policy" not in default
    assert rollback[-2:] == ("--policy", "current")


def test_wrong_default_policy_results_are_rejected() -> None:
    from scripts.numeric_retrieval_deployment_proof import validate_policy_reports

    with pytest.raises(RuntimeError, match="default retrieval policy proof failed"):
        validate_policy_reports(
            promoted={"status": "passed", "policy": "current"},
            rollback={"status": "passed", "policy": "current"},
        )


def test_default_cli_check_rejects_current_behavior(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import numeric_retrieval_deployment_proof as proof

    def no_grouped_match(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(proof, "_run", no_grouped_match)

    with pytest.raises(RuntimeError, match="installed CLI retrieval proof failed"):
        proof._assert_cli_page(  # pyright: ignore[reportPrivateUsage]
            tmp_path / "mke",
            tmp_path / "mke.sqlite",
            None,
            "410000 grouped comma control",
            1,
            cwd=tmp_path,
            environment={"UV_OFFLINE": "1"},
        )
