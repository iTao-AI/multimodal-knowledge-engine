import asyncio
import json
from pathlib import Path

from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.interfaces.mcp_server import build_mcp_server
from mke.runtime import RuntimeConfig

FIXTURE = Path("tests/fixtures/consumer-source-pack-v1/mcp-tool-schemas.json")


def test_consumer_source_pack_contract_fixture_matches_producer(tmp_path: Path) -> None:
    server = build_mcp_server(McpRuntimeConfig(RuntimeConfig(tmp_path / "mke.sqlite"), tmp_path))
    tools = asyncio.run(server.list_tools())
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    release_tools = set(expected["tools"])
    actual = {
        "schema_version": "mke.consumer_mcp_tool_expectations.v1",
        "public_error_contract": expected["public_error_contract"],
        "tools": {
            tool.name: {"inputSchema": tool.inputSchema, "outputSchema": tool.outputSchema}
            for tool in tools
            if tool.name in release_tools
        },
    }
    assert actual == expected
