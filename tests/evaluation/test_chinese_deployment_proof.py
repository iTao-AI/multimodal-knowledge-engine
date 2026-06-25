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
