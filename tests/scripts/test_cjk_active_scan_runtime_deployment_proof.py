import subprocess
from pathlib import Path

import pytest


def test_config_accepts_supported_python_wheel_and_explicit_only(
    tmp_path: Path,
) -> None:
    from scripts.cjk_active_scan_runtime_deployment_proof import (
        DeploymentProofConfig,
    )

    wheel = tmp_path / "mke.whl"
    wheel.write_bytes(b"wheel")

    config = DeploymentProofConfig(
        wheel=wheel,
        python_version="3.12",
        verify_default=False,
    )
    assert config.verify_default is False
    with pytest.raises(ValueError, match="python version"):
        DeploymentProofConfig(wheel=wheel, python_version="3.11")
    with pytest.raises(ValueError, match="wheel"):
        DeploymentProofConfig(
            wheel=tmp_path / "missing.whl",
            python_version="3.13",
        )


def test_isolated_environment_removes_hostile_python_import_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.cjk_active_scan_runtime_deployment_proof import (
        isolated_runtime_environment,
    )

    monkeypatch.setenv("PYTHONPATH", "/repo/src")
    monkeypatch.setenv("PYTHONHOME", "/repo/python")
    monkeypatch.setenv("VIRTUAL_ENV", "/repo/.venv")

    environment = isolated_runtime_environment()

    assert "PYTHONPATH" not in environment
    assert "PYTHONHOME" not in environment
    assert "VIRTUAL_ENV" not in environment
    assert environment["PYTHONNOUSERSITE"] == "1"
    assert environment["UV_OFFLINE"] == "1"


def test_owner_cli_command_places_strategy_before_command(tmp_path: Path) -> None:
    from scripts.cjk_active_scan_runtime_deployment_proof import owner_cli_command

    command = owner_cli_command(
        tmp_path / "mke",
        tmp_path / "mke.sqlite",
        strategy="cjk-active-scan-overlap-v1",
        command=("search", "发布证据检索"),
    )

    assert command == (
        str(tmp_path / "mke"),
        "--db",
        str(tmp_path / "mke.sqlite"),
        "--retrieval-strategy",
        "cjk-active-scan-overlap-v1",
        "search",
        "发布证据检索",
    )


def test_mcp_client_command_uses_owner_strategy_not_request_override(
    tmp_path: Path,
) -> None:
    from scripts.cjk_active_scan_runtime_deployment_proof import mcp_client_command

    command = mcp_client_command(
        python=tmp_path / "python",
        client=tmp_path / "client.py",
        mke=tmp_path / "mke",
        db=tmp_path / "mke.sqlite",
        root=tmp_path,
        fixture="adversarial.pdf",
        strategy="numeric-grouping-v1",
        mode="rollback",
        ingest=False,
    )

    assert command[-6:] == (
        "--strategy",
        "numeric-grouping-v1",
        "--mode",
        "rollback",
        "--fixture",
        "adversarial.pdf",
    )


def test_runtime_report_validation_requires_explicit_and_rollback_proof() -> None:
    from scripts.cjk_active_scan_runtime_deployment_proof import (
        validate_runtime_reports,
    )

    assert (
        validate_runtime_reports(
            explicit={"status": "passed", "strategy": "cjk-active-scan-overlap-v1"},
            rollback={"status": "passed", "strategy": "numeric-grouping-v1"},
            default=None,
            verify_default=False,
        )
        == "explicit_only"
    )
    with pytest.raises(RuntimeError, match="default retrieval strategy proof failed"):
        validate_runtime_reports(
            explicit={"status": "passed", "strategy": "cjk-active-scan-overlap-v1"},
            rollback={"status": "passed", "strategy": "numeric-grouping-v1"},
            default={"status": "passed", "strategy": "numeric-grouping-v1"},
            verify_default=True,
        )


def test_budget_error_validation_rejects_redacted_or_path_leaking_output(
    tmp_path: Path,
) -> None:
    from scripts.cjk_active_scan_runtime_deployment_proof import (
        validate_budget_error,
    )

    valid = subprocess.CompletedProcess(
        args=[],
        returncode=1,
        stdout=(
            "problem=cjk_scan_budget_exceeded "
            "cause=CJK active Evidence scan would exceed configured local budget "
            "active_publication_impact=unchanged "
            "next_step=narrow_query_or_use_projection_strategy\n"
        ),
        stderr="",
    )
    validate_budget_error(valid, forbidden_root=tmp_path)

    leaking = subprocess.CompletedProcess(
        args=[],
        returncode=1,
        stdout=valid.stdout + str(tmp_path),
        stderr="",
    )
    with pytest.raises(RuntimeError, match="budget error proof failed"):
        validate_budget_error(leaking, forbidden_root=tmp_path)
