"""MCP stdio server for local Agent access to MKE Evidence."""

from __future__ import annotations

import asyncio
import functools
import logging
import sys
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Any

from mcp.server.fastmcp import FastMCP

from mke.adapters.video.faster_whisper import doctor_transcription
from mke.interfaces import mcp_contract
from mke.interfaces.mcp_contract import (
    DEFAULT_ASK_LIMIT,
    McpRuntimeConfig,
)
from mke.interfaces.mcp_schemas import (
    AskLibraryErrorV1,
    AskLibraryResponseV1,
    ListLibrariesErrorV1,
    ListLibrariesResponseV1,
    SearchLibraryErrorV1,
    SearchLibraryResponseV1,
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
            config.runtime.process_controller.shutdown()

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
        """Ingest a PDF, short MP4, MP3, WAV, or M4A under the configured allowed root."""
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

    @mcp.tool()
    def list_libraries_v1() -> ListLibrariesResponseV1:  # pyright: ignore[reportUnusedFunction]
        """Observe the implicit local Library through the strict v1 contract."""
        try:
            return mcp_contract.list_libraries_v1(config)
        except Exception:
            logger.exception("mcp_v1_tool_failed")
            return ListLibrariesResponseV1(
                root=ListLibrariesErrorV1(
                    ok=False,
                    problem="internal_error",
                    cause="operation failed; details were redacted",
                    next_step="check_server_logs",
                )
            )

    @mcp.tool()
    def search_library_v1(  # pyright: ignore[reportUnusedFunction]
        query: str, limit: int = DEFAULT_ASK_LIMIT
    ) -> SearchLibraryResponseV1:
        """Search active Evidence with strict v1 provenance."""
        try:
            return mcp_contract.search_library_v1(config, query, limit)
        except Exception:
            logger.exception("mcp_v1_tool_failed")
            return SearchLibraryResponseV1(
                root=SearchLibraryErrorV1(
                    ok=False,
                    problem="internal_error",
                    cause="operation failed; details were redacted",
                    next_step="check_server_logs",
                )
            )

    @mcp.tool()
    def ask_library_v1(  # pyright: ignore[reportUnusedFunction]
        question: str, limit: int = DEFAULT_ASK_LIMIT
    ) -> AskLibraryResponseV1:
        """Return deterministic cited Evidence with strict v1 provenance."""
        try:
            return mcp_contract.ask_library_v1(config, question, limit)
        except Exception:
            logger.exception("mcp_v1_tool_failed")
            return AskLibraryResponseV1(
                root=AskLibraryErrorV1(
                    ok=False,
                    problem="internal_error",
                    cause="operation failed; details were redacted",
                    next_step="check_server_logs",
                )
            )

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
    controller = config.runtime.process_controller
    operation_id = controller.begin_operation()
    scoped = replace(
        config,
        runtime=replace(config.runtime, process_operation_id=operation_id),
    )
    try:
        worker = asyncio.create_task(
            asyncio.to_thread(mcp_contract.ingest_file, scoped, path)
        )
        try:
            return await asyncio.shield(worker)
        except asyncio.CancelledError as cancellation:
            cancellation_won = controller.cancel_operation(operation_id) is not False
            try:
                result = await _wait_for_worker_cleanup(worker)
            except Exception:
                if cancellation_won:
                    raise cancellation
                raise
            if not cancellation_won:
                return result
            raise cancellation
    finally:
        controller.end_operation(operation_id)


async def _wait_for_worker_cleanup(
    worker: asyncio.Task[dict[str, Any]],
) -> dict[str, Any]:
    while True:
        try:
            return await asyncio.shield(worker)
        except asyncio.CancelledError:
            if worker.done():
                return worker.result()


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
