import asyncio
import json
from pathlib import Path

from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.interfaces.mcp_schemas import SearchLibraryErrorV1
from mke.interfaces.mcp_server import build_mcp_server
from mke.interfaces.public_errors import is_public_error_cause
from mke.runtime import RuntimeConfig

FIXTURE = Path("tests/fixtures/consumer-source-pack-v1/mcp-tool-schemas.json")


def test_consumer_source_pack_contract_fixture_matches_producer(tmp_path: Path) -> None:
    server = build_mcp_server(McpRuntimeConfig(RuntimeConfig(tmp_path / "mke.sqlite"), tmp_path))
    tools = asyncio.run(server.list_tools())
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    release_tools = set(expected["tools"])
    release_error_contract = expected["public_error_contract"]
    error_schema = SearchLibraryErrorV1.model_json_schema()
    assert error_schema["properties"]["problem"]["pattern"] == release_error_contract[
        "machine_token_pattern"
    ]
    assert error_schema["properties"]["next_step"]["pattern"] == release_error_contract[
        "machine_token_pattern"
    ]
    assert error_schema["properties"]["active_publication_impact"]["const"] == (
        release_error_contract["active_publication_impact"]
    )
    assert all(
        is_public_error_cause(cause) for cause in release_error_contract["safe_causes"]
    )
    actual = {
        "schema_version": "mke.consumer_mcp_tool_expectations.v1",
        "public_error_contract": release_error_contract,
        "tools": {
            tool.name: {"inputSchema": tool.inputSchema, "outputSchema": tool.outputSchema}
            for tool in tools
            if tool.name in release_tools
        },
    }
    assert actual == expected
