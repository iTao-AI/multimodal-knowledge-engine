from pathlib import Path


def test_fixture_script_exists_and_is_public_neutral() -> None:
    path = Path("scripts/mcp_context_completeness_fixture.py")
    text = path.read_text(encoding="utf-8")
    assert "mke.mcp_context_fixture.v1" in text
    assert "/Users/" not in text
    assert "late completeness marker" in text
    assert "range(1, 12)" in text
