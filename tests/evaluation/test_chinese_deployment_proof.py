import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_proof_config_accepts_only_supported_python_and_wheel(
    tmp_path: Path,
) -> None:
    from scripts.chinese_retrieval_deployment_proof import DeploymentProofConfig

    wheel = tmp_path / "mke.whl"
    protocol = tmp_path / "protocol.json"
    wheel.write_bytes(b"wheel")
    protocol.write_text("{}")

    assert (
        DeploymentProofConfig(
            wheel=wheel,
            protocol=protocol,
            python_version="3.12",
        ).python_version
        == "3.12"
    )
    with pytest.raises(ValueError, match="python version"):
        DeploymentProofConfig(
            wheel=wheel,
            protocol=protocol,
            python_version="3.11",
        )
    with pytest.raises(ValueError, match="protocol"):
        DeploymentProofConfig(
            wheel=wheel,
            protocol=tmp_path / "missing.json",
            python_version="3.13",
        )


def test_proof_environment_is_offline_and_hostile_source_state_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.chinese_retrieval_deployment_proof import (
        isolated_runtime_environment,
    )

    monkeypatch.setenv("PYTHONPATH", "/repo/src")
    monkeypatch.setenv("PYTHONHOME", "/repo/python")
    monkeypatch.setenv("VIRTUAL_ENV", "/repo/.venv")

    environment = isolated_runtime_environment()

    assert environment["UV_OFFLINE"] == "1"
    assert "PYTHONPATH" not in environment
    assert "PYTHONHOME" not in environment
    assert "VIRTUAL_ENV" not in environment


def test_proof_install_uses_offline_constraints_and_isolated_python(
    tmp_path: Path,
) -> None:
    from scripts.chinese_retrieval_deployment_proof import wheel_install_command

    command = wheel_install_command(
        tmp_path / "venv" / "bin" / "python",
        tmp_path / "mke.whl",
        tmp_path / "constraints.txt",
    )

    assert command == (
        "uv",
        "pip",
        "install",
        "--offline",
        "--python",
        str(tmp_path / "venv" / "bin" / "python"),
        "--constraint",
        str(tmp_path / "constraints.txt"),
        str(tmp_path / "mke.whl"),
    )


def test_proof_rejects_source_tree_import(tmp_path: Path) -> None:
    from scripts.chinese_retrieval_deployment_proof import (
        validate_installed_identity,
    )

    repository = tmp_path / "repo"
    source = repository / "src" / "mke" / "__init__.py"
    source.parent.mkdir(parents=True)
    source.write_text("")
    environment = tmp_path / "runtime" / "venv"

    with pytest.raises(ValueError, match="installed package identity"):
        validate_installed_identity(
            {
                "mke_file": str(source),
                "sys_executable": str(environment / "bin" / "python"),
            },
            environment=environment,
            repository=repository,
        )


def test_proof_rejects_venv_python_with_non_site_packages_import(
    tmp_path: Path,
) -> None:
    from scripts.chinese_retrieval_deployment_proof import (
        validate_installed_identity,
    )

    repository = tmp_path / "repo"
    repository.mkdir()
    environment = tmp_path / "runtime" / "venv"
    module = environment / "src" / "mke" / "__init__.py"
    module.parent.mkdir(parents=True)
    module.write_text("")

    with pytest.raises(ValueError, match="installed package identity"):
        validate_installed_identity(
            {
                "mke_file": str(module),
                "sys_executable": str(environment / "bin" / "python"),
            },
            environment=environment,
            repository=repository,
        )


def test_proof_can_reuse_preinstalled_wheel_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import chinese_retrieval_deployment_proof as proof

    wheel = tmp_path / "mke.whl"
    protocol = tmp_path / "protocol.json"
    wheel.write_bytes(b"wheel")
    protocol.write_text("{}")
    installed_environment = tmp_path / "wheel-env"
    (installed_environment / "bin").mkdir(parents=True)
    (installed_environment / "bin" / "python").write_text("")
    (installed_environment / "bin" / "mke").write_text("")
    site_package = (
        installed_environment
        / "lib"
        / "python3.13"
        / "site-packages"
        / "mke"
        / "__init__.py"
    )
    site_package.parent.mkdir(parents=True)
    site_package.write_text("")
    commands: list[tuple[str, ...]] = []

    def fake_json_command(
        command: tuple[str, ...],
        *,
        cwd: Path,
        environment: dict[str, str],
        timeout: float,
    ) -> dict[str, object]:
        del timeout
        commands.append(command)
        assert cwd != Path(__file__).resolve().parents[2]
        assert environment["UV_OFFLINE"] == "1"
        assert "PYTHONPATH" not in environment
        assert "PYTHONHOME" not in environment
        assert "VIRTUAL_ENV" not in environment
        if command[0] == str(installed_environment / "bin" / "python"):
            return {
                "mke_file": str(site_package),
                "sys_executable": str(installed_environment / "bin" / "python"),
            }
        return {
            "integrity_status": "passed",
            "quality_status": "baseline_recorded",
            "documents": 5,
            "queries": 48,
            "split_counts": {"development": 24, "holdout": 24},
            "integrity_failures": [],
            "fts5_rank_profile": "sqlite_fts5_default_bm25",
        }

    def unexpected_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError("preinstalled environment proof must not install")

    monkeypatch.setattr(proof, "_json_command", fake_json_command)
    monkeypatch.setattr(proof.subprocess, "run", unexpected_run)

    report = proof.run_deployment_proof(
        proof.DeploymentProofConfig(
            wheel=wheel,
            protocol=protocol,
            python_version="3.13",
            installed_environment=installed_environment,
        )
    )

    assert report["status"] == "passed"
    assert report["installed_identity"] == "passed"
    assert commands[0][0] == str(installed_environment / "bin" / "python")
    assert commands[1][0] == str(installed_environment / "bin" / "mke")


def test_proof_subprocess_timeout_and_output_are_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import chinese_retrieval_deployment_proof as proof

    def oversized(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout="x" * 100_000, stderr=""
        )

    monkeypatch.setattr(proof.subprocess, "run", oversized)
    with pytest.raises(RuntimeError, match="output limit"):
        proof._run(  # pyright: ignore[reportPrivateUsage]
            ("true",),
            cwd=tmp_path,
            environment={"UV_OFFLINE": "1"},
        )


def test_empty_offline_cache_failure_is_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import chinese_retrieval_deployment_proof as proof

    def unavailable(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=1, stdout="", stderr="offline cache empty")

    monkeypatch.setattr(proof.subprocess, "run", unavailable)
    with pytest.raises(RuntimeError, match="deployment proof command failed"):
        proof._run(  # pyright: ignore[reportPrivateUsage]
            ("uv", "pip", "install", "--offline"),
            cwd=tmp_path,
            environment={"UV_OFFLINE": "1"},
        )


def test_evaluation_payload_requires_partition_and_rank_evidence() -> None:
    from scripts.chinese_retrieval_deployment_proof import validate_evaluation

    validate_evaluation(
        {
            "integrity_status": "passed",
            "quality_status": "baseline_recorded",
            "documents": 5,
            "queries": 48,
            "split_counts": {"development": 24, "holdout": 24},
            "integrity_failures": [],
            "fts5_rank_profile": "sqlite_fts5_default_bm25",
        }
    )
    with pytest.raises(RuntimeError, match="evaluation proof failed"):
        validate_evaluation(
            {
                "integrity_status": "passed",
                "quality_status": "baseline_recorded",
                "documents": 5,
                "queries": 48,
                "split_counts": {"development": 48, "holdout": 0},
                "integrity_failures": [],
                "fts5_rank_profile": "sqlite_fts5_default_bm25",
            }
        )
