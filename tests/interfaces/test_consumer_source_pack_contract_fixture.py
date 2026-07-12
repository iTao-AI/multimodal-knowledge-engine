import asyncio
import json
from pathlib import Path

from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.interfaces.mcp_server import build_mcp_server
from mke.interfaces.public_errors import _ALLOWLISTED_CAUSES, _REDACTED_CAUSE
from mke.runtime import RuntimeConfig

FIXTURE = Path("tests/fixtures/consumer-source-pack-v1/mcp-tool-schemas.json")


def test_consumer_source_pack_contract_fixture_matches_producer(tmp_path: Path) -> None:
    server = build_mcp_server(McpRuntimeConfig(RuntimeConfig(tmp_path / "mke.sqlite"), tmp_path))
    tools = asyncio.run(server.list_tools())
    actual = {
        "schema_version": "mke.consumer_mcp_tool_expectations.v1",
        "public_error_contract": {
            "machine_token_pattern": "^[a-z][a-z0-9_]{0,127}$",
            "active_publication_impact": "unchanged",
            "safe_causes": sorted({*_ALLOWLISTED_CAUSES, _REDACTED_CAUSE}),
        },
        "tools": {
            tool.name: {"inputSchema": tool.inputSchema, "outputSchema": tool.outputSchema}
            for tool in tools
        },
    }
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert actual == expected
