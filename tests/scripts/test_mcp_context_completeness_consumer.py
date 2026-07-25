import ast
from pathlib import Path


def test_consumer_uses_only_official_sdk_and_standard_library() -> None:
    path = Path("scripts/mcp_context_completeness_consumer.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots = {
        (
            node.module.split(".", 1)[0]
            if isinstance(node, ast.ImportFrom) and node.module
            else alias.name.split(".", 1)[0]
        )
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert {"mke", "pydantic", "sqlite3", "tests"}.isdisjoint(roots)
    assert "mcp" in roots
    text = path.read_text(encoding="utf-8")
    for proof_point in (
        "search_library_v2",
        "read_evidence_v1",
        "invalid_cursor",
        "cursor_expired",
        "response_too_large",
        "max_canonical_model_bytes",
        "max_sdk_result_bytes",
    ):
        assert proof_point in text
