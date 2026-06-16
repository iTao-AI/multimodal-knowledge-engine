from pathlib import Path

from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.interfaces.mcp_server import build_mcp_server
from mke.interfaces.mcp_server import safe_tool_for_test as safe_tool


def test_build_mcp_server_returns_named_server(tmp_path: Path) -> None:
    server = build_mcp_server(
        McpRuntimeConfig(db_path=tmp_path / "mke.sqlite", allowed_root=tmp_path)
    )

    assert server.name == "Multimodal Knowledge Engine"


def test_safe_tool_returns_stable_error_without_exception_details() -> None:
    @safe_tool
    def exploding_tool() -> dict[str, object]:
        raise RuntimeError("/private/path/to/database.sqlite exploded")

    result = exploding_tool()

    assert result == {
        "ok": False,
        "problem": "mcp_tool_failed",
        "cause": "internal error",
        "active_publication_impact": "unchanged",
        "next_step": "check_server_logs",
    }
