import argparse
import subprocess
from pathlib import Path

import pytest

import scripts.mcp_context_completeness_proof as proof


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
