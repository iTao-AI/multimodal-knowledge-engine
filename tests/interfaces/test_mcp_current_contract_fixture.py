from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import cast

from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.interfaces.mcp_server import build_mcp_server
from mke.interfaces.public_errors import (
    _ALLOWLISTED_CAUSES,  # pyright: ignore[reportPrivateUsage]
)
from mke.runtime import RuntimeConfig
from scripts.mcp_context_completeness_consumer import tool_snapshot

FIXTURE = Path(
    "tests/fixtures/mcp-context-completeness-v1/mcp-tool-schemas.json"
)
EXPECTED_TOOL_NAMES = (
    "ask_library",
    "ask_library_v1",
    "get_run",
    "ingest_file",
    "list_libraries",
    "list_libraries_v1",
    "read_evidence_v1",
    "search_library",
    "search_library_v1",
    "search_library_v2",
)
STABLE_LOCATOR_CAUSE = (
    "active retrieval candidates contain duplicate stable Evidence locators"
)


def test_current_mcp_contract_fixture_matches_exact_producer_snapshot(
    tmp_path: Path,
) -> None:
    fixture = cast(
        dict[str, object],
        json.loads(FIXTURE.read_text(encoding="utf-8")),
    )
    server = build_mcp_server(
        McpRuntimeConfig(
            RuntimeConfig(tmp_path / "mke.sqlite"),
            tmp_path,
        )
    )
    listed = asyncio.run(server.list_tools())
    actual_tools = {
        tool.name: tool_snapshot(tool)
        for tool in sorted(listed, key=lambda item: item.name)
    }
    safe_causes = cast(list[str], fixture["safe_causes"])

    assert fixture["schema_version"] == "mke.mcp_tool_expectation.v1"
    assert tuple(actual_tools) == EXPECTED_TOOL_NAMES
    assert tuple(cast(dict[str, object], fixture["tools"])) == (
        EXPECTED_TOOL_NAMES
    )
    assert fixture["tools"] == actual_tools
    assert safe_causes == sorted(safe_causes)
    assert len(safe_causes) == len(set(safe_causes))

    expected = {
        "schema_version": "mke.mcp_tool_expectation.v1",
        "safe_causes": sorted(_ALLOWLISTED_CAUSES),
        "tools": actual_tools,
    }
    assert fixture == expected
    assert STABLE_LOCATOR_CAUSE in safe_causes
