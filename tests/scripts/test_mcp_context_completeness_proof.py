from pathlib import Path


def test_proof_controller_binds_two_interpreters_to_one_wheel() -> None:
    text = Path("scripts/mcp_context_completeness_proof.py").read_text(encoding="utf-8")
    assert "mke.mcp_context_completeness_proof.v1" in text
    assert "python_versions" in text
    assert "network_access" in text
    assert "UV_OFFLINE" in text
    assert text.count('"uv", "build"') == 1
    assert "--offline" in text
    assert "--constraints" in text


def test_proof_workflow_prewarms_locked_dependencies_for_both_interpreters() -> None:
    text = Path(".github/workflows/mcp-context-completeness-proof.yml").read_text(
        encoding="utf-8"
    )

    assert "uv export --locked --no-dev --no-emit-project" in text
    assert "mke-core-requirements.txt" in text
    assert "mke-prewarm-312" in text
    assert "mke-prewarm-313" in text
    assert text.count("--requirement \"$RUNNER_TEMP/mke-core-requirements.txt\"") == 2
