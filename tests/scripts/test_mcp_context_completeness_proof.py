import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

import scripts.mcp_context_completeness_proof as proof


def test_installed_case_accepts_alias_for_resolved_environment_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_root = tmp_path / "private" / "var" / "proof"
    real_root.mkdir(parents=True)
    alias_root = tmp_path / "var"
    alias_root.symlink_to(real_root, target_is_directory=True)
    case_root = alias_root / "case"
    repository = tmp_path / "repository"
    for relative in (
        "scripts/mcp_context_completeness_fixture.py",
        "scripts/mcp_context_completeness_consumer.py",
        "tests/fixtures/pdf-extraction-observation-v1/mcp-tool-schemas.json",
        "tests/fixtures/pdf/text-layer.pdf",
    ):
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")

    def fake_command(
        argv: list[str],
        *,
        cwd: Path,
        timeout: int = 180,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, timeout
        if argv[1:3] == [
            "-c",
            "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')",
        ]:
            return subprocess.CompletedProcess(argv, 0, "3.12\n", "")
        if argv[:2] == ["uv", "venv"]:
            environment = Path(argv[-1])
            (environment / "bin").mkdir(parents=True)
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[:3] == ["uv", "pip", "install"]:
            environment = Path(argv[argv.index("--python") + 1]).parents[1]
            module = environment.resolve() / "lib/python3.12/site-packages/mke/__init__.py"
            module.parent.mkdir(parents=True)
            module.write_text("", encoding="utf-8")
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[1:2] == ["-c"]:
            environment = Path(argv[0]).parents[1]
            payload = {
                "module": str(
                    environment.resolve()
                    / "lib/python3.12/site-packages/mke/__init__.py"
                ),
                "executable": str(environment.resolve() / "bin/python"),
            }
            return subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")
        if argv[1].endswith("mcp_context_completeness_fixture.py"):
            return subprocess.CompletedProcess(argv, 0, '{"status":"passed"}', "")
        if argv[1].endswith("mcp_context_completeness_consumer.py"):
            return subprocess.CompletedProcess(
                argv,
                0,
                json.dumps(
                    {
                        "status": "passed",
                        "max_canonical_model_bytes": 1,
                        "max_sdk_result_bytes": 1,
                    }
                ),
                "",
            )
        raise AssertionError(argv)

    monkeypatch.setattr(proof, "command", fake_command)

    receipt = proof.installed_case(
        interpreter=tmp_path / "python3.12",
        wheel=tmp_path / "mke.whl",
        constraints=tmp_path / "constraints.txt",
        repository=repository,
        case_root=case_root,
    )

    assert receipt["python_version"] == "3.12"


@pytest.mark.parametrize(
    ("module_location", "executable_location"),
    [
        ("repository", "environment"),
        ("external", "environment"),
        ("environment", "external"),
    ],
)
def test_installed_identity_rejects_paths_outside_the_installed_environment(
    tmp_path: Path,
    module_location: str,
    executable_location: str,
) -> None:
    environment = tmp_path / "environment"
    repository = tmp_path / "repository"
    external = tmp_path / "external"
    for root in (environment, repository, external):
        root.mkdir()
    roots = {
        "environment": environment,
        "repository": repository,
        "external": external,
    }
    module = roots[module_location] / "lib/python3.12/site-packages/mke/__init__.py"
    executable = roots[executable_location] / "bin/python"

    with pytest.raises(proof.ProofFailure, match="installed_identity_failed"):
        proof.validate_installed_identity(
            module=module,
            executable=executable,
            environment_root=environment,
            repository=repository,
        )


def test_installed_identity_rejects_wrong_executable_basename(tmp_path: Path) -> None:
    environment = tmp_path / "environment"
    repository = tmp_path / "repository"

    with pytest.raises(proof.ProofFailure, match="installed_identity_failed"):
        proof.validate_installed_identity(
            module=environment / "lib/python3.12/site-packages/mke/__init__.py",
            executable=environment / "bin/python3.12",
            environment_root=environment,
            repository=repository,
        )


def test_proof_controller_binds_two_interpreters_to_one_wheel() -> None:
    text = Path("scripts/mcp_context_completeness_proof.py").read_text(encoding="utf-8")
    assert "mke.mcp_context_completeness_proof.v1" in text
    assert "python_versions" in text
    assert "network_access" in text
    assert "UV_OFFLINE" in text
    assert text.count('"uv", "build"') == 1
    assert "--offline" in text
    assert "--constraints" in text
    assert '"dependency_constraints": "uv_lock_exact"' in text


def test_proof_controller_keeps_aggregate_receipt_v1_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constraints = tmp_path / "constraints.txt"
    constraints.write_text("locked\n", encoding="utf-8")
    candidate = tmp_path / "candidate"

    def fake_command(
        argv: list[str],
        *,
        cwd: Path,
        timeout: int = 180,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, timeout
        if argv[:2] == ["uv", "export"]:
            return subprocess.CompletedProcess(argv, 0, "locked\n", "")
        if argv[:2] == ["uv", "build"]:
            output = Path(argv[argv.index("--out-dir") + 1])
            output.mkdir(parents=True, exist_ok=True)
            (output / "mke.whl").write_bytes(b"wheel")
            return subprocess.CompletedProcess(argv, 0, "", "")
        raise AssertionError(argv)

    monkeypatch.setattr(proof, "command", fake_command)

    def fake_installed_case(**kwargs: Any) -> dict[str, Any]:
        return {
            "status": "passed",
            "python_version": "3.12"
            if kwargs["interpreter"].name.endswith("312")
            else "3.13",
            "normal_no_match": "passed",
            "inactive_evidence_recovery": "passed",
            "cjk_scan_budget_recovery": "passed",
            "max_canonical_model_bytes": 1,
            "max_sdk_result_bytes": 1,
        }

    monkeypatch.setattr(proof, "installed_case", fake_installed_case)

    args = argparse.Namespace(
        python=[tmp_path / "python312", tmp_path / "python313"],
        constraints=constraints,
        candidate_output=candidate,
    )

    receipt = proof.run(args)

    assert set(receipt) == {
        "status",
        "schema_version",
        "python_versions",
        "tool_count",
        "search_continuation",
        "exact_read",
        "cjk_cap",
        "cursor_expiry",
        "legacy_compatibility",
        "max_canonical_model_bytes",
        "max_sdk_result_bytes",
        "source_import",
        "network_access",
        "dependency_constraints",
    }


@pytest.mark.parametrize(
    ("bad_lane", "bad_field", "mutation"),
    [
        (bad_lane, bad_field, mutation)
        for bad_lane in (0, 1)
        for bad_field in (
            "normal_no_match",
            "inactive_evidence_recovery",
            "cjk_scan_budget_recovery",
        )
        for mutation in ("missing", "drifted")
    ],
)
def test_proof_controller_rejects_lane_without_required_consumer_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bad_lane: int,
    bad_field: str,
    mutation: str,
) -> None:
    constraints = tmp_path / "constraints.txt"
    constraints.write_text("locked\n", encoding="utf-8")
    candidate = tmp_path / "candidate"

    def fake_command(
        argv: list[str],
        *,
        cwd: Path,
        timeout: int = 180,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, timeout
        if argv[:2] == ["uv", "export"]:
            return subprocess.CompletedProcess(argv, 0, "locked\n", "")
        if argv[:2] == ["uv", "build"]:
            output = Path(argv[argv.index("--out-dir") + 1])
            output.mkdir(parents=True, exist_ok=True)
            (output / "mke.whl").write_bytes(b"wheel")
            return subprocess.CompletedProcess(argv, 0, "", "")
        raise AssertionError(argv)

    monkeypatch.setattr(proof, "command", fake_command)

    def fake_installed_case(**kwargs: Any) -> dict[str, Any]:
        receipt: dict[str, Any] = {
            "status": "passed",
            "python_version": "3.12"
            if kwargs["interpreter"].name.endswith("312")
            else "3.13",
            "normal_no_match": "passed",
            "inactive_evidence_recovery": "passed",
            "cjk_scan_budget_recovery": "passed",
            "max_canonical_model_bytes": 1,
            "max_sdk_result_bytes": 1,
        }
        if kwargs["case_root"].name == f"case-{bad_lane}":
            if mutation == "missing":
                del receipt[bad_field]
            else:
                receipt[bad_field] = "failed"
        return receipt

    monkeypatch.setattr(
        proof,
        "installed_case",
        fake_installed_case,
    )

    args = argparse.Namespace(
        python=[tmp_path / "python312", tmp_path / "python313"],
        constraints=constraints,
        candidate_output=candidate,
    )

    with pytest.raises(proof.ProofFailure) as raised:
        proof.run(args)

    assert raised.value.code == "consumer_proof_failed"


def test_proof_workflow_prewarms_locked_dependencies_for_both_interpreters() -> None:
    text = Path(".github/workflows/mcp-context-completeness-proof.yml").read_text(
        encoding="utf-8"
    )

    assert "uv export --locked --no-dev --no-emit-project --no-header" in text
    assert "mke-core-requirements.txt" in text
    assert "mke-prewarm-312" in text
    assert "mke-prewarm-313" in text
    assert text.count("--requirement \"$RUNNER_TEMP/mke-core-requirements.txt\"") == 2


def test_proof_controller_rejects_constraints_not_equal_to_locked_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constraints = tmp_path / "arbitrary-constraints.txt"
    constraints.write_text("", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_command(
        argv: list[str],
        *,
        cwd: Path,
        timeout: int = 180,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, timeout
        calls.append(argv)
        if argv[:2] == ["uv", "export"]:
            return subprocess.CompletedProcess(
                argv,
                0,
                "mcp==1.28.1 --hash=sha256:" + "a" * 64 + "\n",
                "",
            )
        raise AssertionError("arbitrary constraints must fail before build")

    monkeypatch.setattr(proof, "command", fake_command)
    args = argparse.Namespace(
        python=[tmp_path / "python3.12", tmp_path / "python3.13"],
        constraints=constraints,
        candidate_output=tmp_path / "candidate",
    )

    with pytest.raises(proof.ProofFailure) as raised:
        proof.run(args)

    assert raised.value.code == "locked_constraints_mismatch"
    assert calls == [
        [
            "uv",
            "export",
            "--locked",
            "--no-dev",
            "--no-emit-project",
            "--no-header",
        ]
    ]
