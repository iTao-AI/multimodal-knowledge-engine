from __future__ import annotations

from pathlib import Path

import pytest

import scripts.dense_retrieval_deployment_proof as proof
from scripts.dense_retrieval_deployment_proof import (
    DeploymentProofConfig,
    isolated_runtime_environment,
    validate_installed_identity,
    wheel_install_command,
)


def _config(tmp_path: Path, python_version: str = "3.12") -> DeploymentProofConfig:
    tmp_path.mkdir(parents=True, exist_ok=True)
    wheel = tmp_path / "mke.whl"
    wheel.write_bytes(b"wheel")
    lock = tmp_path / "corpus-lock.json"
    lock.write_text("{}", encoding="utf-8")
    cache = tmp_path / "model-cache"
    cache.mkdir()
    return DeploymentProofConfig(wheel, lock, cache, python_version)


def test_config_requires_supported_python_existing_wheel_lock_and_external_cache(
    tmp_path: Path,
) -> None:
    assert _config(tmp_path).python_version == "3.12"
    with pytest.raises(ValueError, match="python"):
        _config(tmp_path / "invalid", "3.11")


def test_config_rejects_model_cache_or_installed_environment_inside_repository(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    wheel = repository / "mke.whl"
    wheel.write_bytes(b"wheel")
    lock = repository / "corpus-lock.json"
    lock.write_text("{}", encoding="utf-8")
    cache = repository / "model-cache"
    cache.mkdir()

    with pytest.raises(ValueError, match="cache"):
        DeploymentProofConfig(
            wheel,
            lock,
            cache,
            "3.12",
            repository=repository,
        )

    external_cache = tmp_path / "external-cache"
    external_cache.mkdir()
    with pytest.raises(ValueError, match="environment"):
        DeploymentProofConfig(
            wheel,
            lock,
            external_cache,
            "3.12",
            repository=repository,
            installed_environment=repository / "venv",
        )


def test_environment_is_offline_cache_only_and_clears_hostile_python_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTHONPATH", "/repo/src")
    monkeypatch.setenv("PYTHONHOME", "/repo/python")
    monkeypatch.setenv("VIRTUAL_ENV", "/repo/.venv")

    environment = isolated_runtime_environment()

    assert environment["UV_OFFLINE"] == "1"
    assert environment["PIP_NO_INDEX"] == "1"
    assert environment["HF_HUB_OFFLINE"] == "1"
    assert environment["HF_HUB_DISABLE_TELEMETRY"] == "1"
    assert environment["TRANSFORMERS_OFFLINE"] == "1"
    assert all(name not in environment for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"))


def test_wheel_install_command_uses_embedding_extra_and_offline_constraints(tmp_path: Path) -> None:
    command = wheel_install_command(
        tmp_path / "venv/bin/python",
        tmp_path / "mke.whl",
        tmp_path / "constraints.txt",
    )

    assert command == (
        "uv",
        "pip",
        "install",
        "--offline",
        "--python",
        str(tmp_path / "venv/bin/python"),
        "--constraint",
        str(tmp_path / "constraints.txt"),
        str(tmp_path / "mke.whl") + "[embedding]",
    )


def test_installed_identity_must_be_external_site_packages_and_selected_interpreter(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    environment = tmp_path / "runtime"
    module = environment / "lib/python3.13/site-packages/mke/__init__.py"
    module.parent.mkdir(parents=True)
    module.write_text("", encoding="utf-8")
    executable = environment / "bin/python"
    executable.parent.mkdir()
    executable.write_text("", encoding="utf-8")

    validate_installed_identity(
        {"mke_file": str(module), "sys_executable": str(executable)},
        environment=environment,
        repository=repository,
    )

    with pytest.raises(ValueError, match="installed"):
        validate_installed_identity(
            {
                "mke_file": str(repository / "src/mke/__init__.py"),
                "sys_executable": str(executable),
            },
            environment=environment,
            repository=repository,
        )
    with pytest.raises(ValueError, match="installed"):
        validate_installed_identity(
            {
                "mke_file": str(module),
                "sys_executable": str(tmp_path / "other/python"),
            },
            environment=environment,
            repository=repository,
        )


def test_proof_source_contains_no_download_flag_or_runtime_network_fallback() -> None:
    source = (Path(__file__).parents[2] / "scripts/dense_retrieval_deployment_proof.py").read_text(
        encoding="utf-8"
    )
    assert "allow-model-download" not in source
    assert "local_files_only=False" not in source
    assert "--no-python-downloads" in source


def test_query_smoke_command_is_separate_cache_only_installed_process(tmp_path: Path) -> None:
    assert hasattr(proof, "query_smoke_command")

    command = proof.query_smoke_command(
        tmp_path / "venv/bin/python",
        tmp_path / "corpus-lock.json",
        tmp_path / "model-cache",
        tmp_path / "repo",
    )

    assert command[:3] == (
        str(tmp_path / "venv/bin/python"),
        "-m",
        "mke.evaluation.dense_compatibility",
    )
    assert "--single-query-smoke" in command
    assert "--json" in command
    assert "--allow-model-download" not in command


def test_query_smoke_evidence_is_fail_closed_for_missing_or_networked_measurements() -> None:
    assert hasattr(proof, "validate_query_smoke_evidence")
    valid: dict[str, object] = {
        "status": "passed",
        "python": "3.13.12",
        "interpreter": "installed",
        "cache_only": True,
        "network": False,
        "source_tree_import": False,
        "model_fingerprint": "sha256:" + "1" * 64,
        "query_vector_digest": "sha256:" + "2" * 64,
        "peak_rss_bytes": 3_400_000_000,
        "model_load_ms": 1,
        "query_embedding_ms": 1,
    }

    proof.validate_query_smoke_evidence(
        valid,
        expected_model_fingerprint="sha256:" + "1" * 64,
    )
    for field, value in (
        ("network", True),
        ("cache_only", False),
        ("source_tree_import", True),
        ("model_fingerprint", "sha256:" + "0" * 64),
        ("peak_rss_bytes", float("nan")),
    ):
        changed = dict(valid)
        changed[field] = value
        with pytest.raises(ValueError):
            proof.validate_query_smoke_evidence(
                changed,
                expected_model_fingerprint="sha256:" + "1" * 64,
            )
