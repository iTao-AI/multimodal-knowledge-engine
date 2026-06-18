import asyncio
from pathlib import Path

from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.interfaces.mcp_server import build_mcp_server
from mke.interfaces.mcp_server import safe_tool_for_test as safe_tool


def test_build_mcp_server_returns_named_server(tmp_path: Path) -> None:
    server = build_mcp_server(
        McpRuntimeConfig(db_path=tmp_path / "mke.sqlite", allowed_root=tmp_path)
    )

    assert server.name == "Multimodal Knowledge Engine"


def test_build_mcp_server_exposes_ask_library_tool(tmp_path: Path) -> None:
    server = build_mcp_server(
        McpRuntimeConfig(db_path=tmp_path / "mke.sqlite", allowed_root=tmp_path)
    )

    tools = asyncio.run(server.list_tools())

    assert "ask_library" in {tool.name for tool in tools}


def test_safe_tool_returns_stable_error_without_exception_details() -> None:
    @safe_tool
    def exploding_tool() -> dict[str, object]:
        raise RuntimeError("/private/path/to/database.sqlite exploded")

    result = exploding_tool()

    assert result == {
        "ok": False,
        "problem": "internal_error",
        "cause": "operation failed; details were redacted",
        "active_publication_impact": "unchanged",
        "next_step": "check_server_logs",
    }


def test_safe_tool_passes_through_success_result() -> None:
    @safe_tool
    def ok_tool() -> dict[str, object]:
        return {"ok": True, "data": "result"}

    result = ok_tool()

    assert result == {"ok": True, "data": "result"}


def test_safe_tool_preserves_arguments() -> None:
    @safe_tool
    def arg_tool(a: str, b: int) -> dict[str, object]:
        return {"ok": True, "a": a, "b": b}

    result = arg_tool("hello", b=42)

    assert result == {"ok": True, "a": "hello", "b": 42}
