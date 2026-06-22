from pathlib import Path

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


def test_wheel_install_uses_isolated_interpreter_without_claiming_offline_cache(
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
        "--python",
        str(python),
        str(wheel),
    )
    assert "--offline" not in command
