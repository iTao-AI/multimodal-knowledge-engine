"""MCP stdio server for local Agent access to MKE Evidence."""

from __future__ import annotations

import asyncio
import functools
import logging
import sys
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from typing import Any

from mcp.server.fastmcp import FastMCP

from mke.adapters.video.faster_whisper import doctor_transcription
from mke.interfaces import mcp_contract
from mke.interfaces.mcp_contract import (
    DEFAULT_ASK_LIMIT,
    McpRuntimeConfig,
)
from mke.interfaces.public_errors import public_error_from_exception
from mke.runtime import FasterWhisperTranscriptionConfig

logger = logging.getLogger(__name__)


def build_mcp_server(config: McpRuntimeConfig) -> FastMCP:
    @asynccontextmanager
    async def lifespan(app: FastMCP[Any]) -> AsyncGenerator[None]:
        try:
            yield
        finally:
            config.runtime.process_controller.cancel_active()

    mcp = FastMCP(
        "Multimodal Knowledge Engine",
        json_response=True,
        log_level="WARNING",
        lifespan=lifespan,
    )

    @mcp.tool()
    @_safe_tool
    def list_libraries() -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        """List available MKE Libraries."""
        return mcp_contract.list_libraries()

    @mcp.tool()
    @_safe_async_tool
    async def ingest_file(path: str) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        """Ingest a PDF or short MP4 under the configured allowed root."""
        return await _ingest_with_cancellation(config, path)

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


def run_mcp_server(config: McpRuntimeConfig) -> int:
    transcription = config.runtime.transcription
    if isinstance(transcription, FasterWhisperTranscriptionConfig):
        readiness = doctor_transcription(transcription)
        if readiness.status != "ready":
            print(
                "problem=transcription_not_ready "
                f"cause={readiness.cause} next_step={readiness.next_step}",
                file=sys.stderr,
            )
            return 1
    build_mcp_server(config).run()
    return 0


async def _ingest_with_cancellation(
    config: McpRuntimeConfig,
    path: str,
) -> dict[str, Any]:
    worker = asyncio.create_task(asyncio.to_thread(mcp_contract.ingest_file, config, path))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        config.runtime.process_controller.cancel_active()
        with suppress(Exception):
            await asyncio.shield(worker)
        raise


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


def _safe_async_tool(
    fn: Callable[..., Awaitable[dict[str, Any]]],
) -> Callable[..., Awaitable[dict[str, Any]]]:
    @functools.wraps(fn)
    async def wrapper(*args: object, **kwargs: object) -> dict[str, Any]:
        try:
            return await fn(*args, **kwargs)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.exception("mcp_tool_failed")
            return public_error_from_exception(
                error,
                problem="internal_error",
                next_step="check_server_logs",
            ).payload()

    return wrapper


safe_tool_for_test = _safe_tool
ingest_with_cancellation_for_test = _ingest_with_cancellation
