"""MCP stdio server for local Agent access to MKE Evidence."""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from mke.interfaces import mcp_contract
from mke.interfaces.mcp_contract import (
    DEFAULT_ASK_LIMIT,
    McpRuntimeConfig,
)
from mke.interfaces.public_errors import public_error_from_exception

logger = logging.getLogger(__name__)

def build_mcp_server(config: McpRuntimeConfig) -> FastMCP:
    mcp = FastMCP("Multimodal Knowledge Engine", json_response=True, log_level="WARNING")

    @mcp.tool()
    @_safe_tool
    def list_libraries() -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        """List available MKE Libraries."""
        return mcp_contract.list_libraries()

    @mcp.tool()
    @_safe_tool
    def ingest_file(path: str) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        """Ingest a PDF or short MP4 under the configured allowed root."""
        return mcp_contract.ingest_file(config, path)

    @mcp.tool()
    @_safe_tool
    def get_run(run_id: str) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        """Inspect a Run and its append-only events."""
        return mcp_contract.get_run(config, run_id)

    @mcp.tool()
    @_safe_tool
    def search_library(  # pyright: ignore[reportUnusedFunction]
        query: str, limit: int = DEFAULT_ASK_LIMIT
    ) -> dict[str, Any]:
        """Search active Publication Evidence."""
        return mcp_contract.search_library(config, query, limit)

    @mcp.tool()
    @_safe_tool
    def ask_library(  # pyright: ignore[reportUnusedFunction]
        question: str, limit: int = DEFAULT_ASK_LIMIT
    ) -> dict[str, Any]:
        """Return deterministic cited Evidence or insufficient-Evidence state."""
        return mcp_contract.ask_library(config, question, limit)

    return mcp


def run_mcp_server(*, db_path: Path, allowed_root: Path) -> int:
    config = McpRuntimeConfig(db_path=db_path, allowed_root=allowed_root)
    build_mcp_server(config).run()
    return 0


def _safe_tool(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    @functools.wraps(fn)
    def wrapper(*args: object, **kwargs: object) -> dict[str, Any]:
        try:
            return fn(*args, **kwargs)
        except Exception as error:
            logger.exception("mcp_tool_failed")
            return public_error_from_exception(
                error,
                problem="internal_error",
                next_step="check_server_logs",
            ).payload()

    return wrapper


safe_tool_for_test = _safe_tool
