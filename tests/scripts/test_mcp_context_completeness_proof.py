from pathlib import Path


def test_proof_controller_binds_two_interpreters_to_one_wheel() -> None:
    text = Path("scripts/mcp_context_completeness_proof.py").read_text(encoding="utf-8")
    assert "mke.mcp_context_completeness_proof.v1" in text
    assert "python_versions" in text
    assert "network_access" in text
    assert "UV_OFFLINE" in text
    assert text.count('"uv", "build"') == 1
    assert "--offline" in text
