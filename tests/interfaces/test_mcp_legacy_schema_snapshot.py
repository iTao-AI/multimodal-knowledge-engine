import asyncio
import json
from pathlib import Path
from typing import Any

from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.interfaces.mcp_server import build_mcp_server
from mke.runtime import RuntimeConfig

LEGACY_TOOLS = {
    "list_libraries",
    "ingest_file",
    "get_run",
    "search_library",
    "ask_library",
}
FIXTURE = Path("tests/fixtures/mcp/legacy-tool-schemas.json")


def _legacy_schemas(tmp_path: Path) -> dict[str, Any]:
    server = build_mcp_server(
        McpRuntimeConfig(
            runtime=RuntimeConfig(tmp_path / "mke.sqlite"),
            allowed_root=tmp_path,
        )
    )
    tools = asyncio.run(server.list_tools())
    return {
        tool.name: {
            "inputSchema": tool.inputSchema,
            "outputSchema": tool.outputSchema,
        }
        for tool in tools
        if tool.name in LEGACY_TOOLS
    }


def test_legacy_tool_schemas_match_frozen_baseline(tmp_path: Path) -> None:
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert expected["baseline_commit"] == "793788f2d74a1ec072fe205e89acd13ab595bad7"
    assert _legacy_schemas(tmp_path) == expected["tools"]
