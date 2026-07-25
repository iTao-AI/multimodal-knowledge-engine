#!/usr/bin/env python3
"""Standalone official-SDK consumer for the installed MCP completeness proof."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROOF_SCHEMA = "mke.mcp_context_completeness_consumer.v1"
CANONICAL_LIMIT = 32768
SDK_LIMIT = 96 * 1024


class ProofFailure(RuntimeError):
    pass


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def require(condition: bool) -> None:
    if not condition:
        raise ProofFailure


def structured(result: Any, measurements: list[tuple[int, int]]) -> dict[str, Any]:
    value = result.structuredContent
    require(isinstance(value, dict))
    require(len(result.content) == 1)
    require(result.content[0].type == "text")
    require(json.loads(result.content[0].text) == value)
    canonical_bytes = len(canonical_json(value))
    sdk_bytes = len(result.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8"))
    require(canonical_bytes <= CANONICAL_LIMIT)
    require(sdk_bytes < SDK_LIMIT)
    measurements.append((canonical_bytes, sdk_bytes))
    return value


@asynccontextmanager
async def session_for(
    server_command: Path, database: Path, allowed_root: Path
) -> AsyncIterator[ClientSession]:
    parameters = StdioServerParameters(
        command=str(server_command),
        args=[
            "--db",
            str(database),
            "mcp",
            "--allowed-root",
            str(allowed_root),
        ],
    )
    async with stdio_client(parameters) as streams:
        async with ClientSession(*streams) as session:
            await asyncio.wait_for(session.initialize(), timeout=15)
            yield session


def tool_snapshot(tool: Any) -> dict[str, Any]:
    dumped = tool.model_dump(by_alias=True, exclude_none=True)
    return {
        "inputSchema": dumped["inputSchema"],
        "outputSchema": dumped.get("outputSchema"),
        "description": dumped.get("description"),
        "annotations": dumped.get("annotations"),
    }


async def call(
    session: ClientSession,
    name: str,
    arguments: dict[str, Any],
    measurements: list[tuple[int, int]],
) -> dict[str, Any]:
    result = await asyncio.wait_for(
        session.call_tool(name, arguments),
        timeout=30,
    )
    return structured(result, measurements)


async def run(args: argparse.Namespace) -> dict[str, object]:
    expectation = json.loads(args.expectation.read_text(encoding="utf-8"))
    measurements: list[tuple[int, int]] = []
    expired_cursor = ""

    async with session_for(args.server_command, args.database, args.allowed_root) as session:
        discovered = await asyncio.wait_for(session.list_tools(), timeout=15)
        actual = {
            tool.name: tool_snapshot(tool)
            for tool in sorted(discovered.tools, key=lambda item: item.name)
        }
        require(actual == expectation["tools"])

        first = await call(
            session,
            "search_library_v2",
            {"request": {"query": "publication authority continuation", "limit": 1}},
            measurements,
        )
        require(first["ok"] is True)
        require(first["selection"]["status"] == "more_available")
        require(len(first["matches"]) == 1)
        cursor = first["selection"]["next_cursor"]
        continued = await call(
            session,
            "search_library_v2",
            {"request": {"cursor": cursor}},
            measurements,
        )
        require(continued["ok"] is True)
        require(continued["selection"]["status"] == "complete")
        require(
            first["matches"][0]["evidence"]["evidence_id"]
            != continued["matches"][0]["evidence"]["evidence_id"]
        )

        tampered = cursor[:-1] + ("A" if cursor[-1] != "A" else "B")
        bad = await call(
            session,
            "search_library_v2",
            {"request": {"cursor": tampered}},
            measurements,
        )
        require(bad["ok"] is False and bad["problem"] == "invalid_cursor")

        large = await call(
            session,
            "search_library_v2",
            {"request": {"query": "late completeness marker", "limit": 1}},
            measurements,
        )
        match = large["matches"][0]
        require(match["excerpt"]["complete"] is False)
        require(match["excerpt"]["kind"] == "query_window")
        require("late completeness marker" in match["excerpt"]["text"])
        evidence_id = match["evidence"]["evidence_id"]
        expected_digest = match["evidence"]["evidence_text_sha256"]
        chunks: list[bytes] = []
        read_request: dict[str, Any] = {"evidence_id": evidence_id, "max_bytes": 16384}
        expected_offset = 0
        while True:
            read = await call(
                session,
                "read_evidence_v1",
                {"request": read_request},
                measurements,
            )
            require(read["ok"] is True)
            content = read["content"]
            encoded = content["text"].encode("utf-8")
            require(content["offset_bytes"] == expected_offset)
            require(content["returned_utf8_bytes"] == len(encoded))
            expected_offset += len(encoded)
            chunks.append(encoded)
            if read["complete"]:
                require(read.get("next_cursor") is None)
                break
            read_request = {"cursor": read["next_cursor"]}
        reconstructed = b"".join(chunks)
        require("sha256:" + hashlib.sha256(reconstructed).hexdigest() == expected_digest)

        cjk_request: dict[str, Any] = {"query": "知识完整性证据", "limit": 5}
        cjk_status = ""
        cjk_count = 0
        while True:
            page = await call(
                session,
                "search_library_v2",
                {"request": cjk_request},
                measurements,
            )
            require(page["ok"] is True)
            cjk_count += len(page["matches"])
            cjk_status = page["selection"]["status"]
            if cjk_status != "more_available":
                break
            cjk_request = {"cursor": page["selection"]["next_cursor"]}
        require(cjk_status == "capped")
        require(cjk_count == 10)

        bounded = await call(
            session,
            "search_library_v1",
            {"query": "publication authority continuation", "limit": 1},
            measurements,
        )
        require(bounded["ok"] is True)
        oversized = await call(
            session,
            "search_library_v1",
            {"query": "late completeness marker", "limit": 1},
            measurements,
        )
        require(oversized["ok"] is False)
        require(oversized["problem"] == "response_too_large")

        expiring = await call(
            session,
            "search_library_v2",
            {"request": {"query": "publication authority continuation", "limit": 1}},
            measurements,
        )
        expired_cursor = expiring["selection"]["next_cursor"]
        ingest = await call(
            session,
            "ingest_file",
            {"path": args.ingest_fixture.name},
            measurements,
        )
        require(ingest["ok"] is True)
        changed = await call(
            session,
            "search_library_v2",
            {"request": {"cursor": expired_cursor}},
            measurements,
        )
        require(changed["ok"] is False and changed["problem"] == "cursor_expired")

    async with session_for(args.server_command, args.database, args.allowed_root) as restarted:
        after_restart = await call(
            restarted,
            "search_library_v2",
            {"request": {"cursor": expired_cursor}},
            measurements,
        )
        require(
            after_restart["ok"] is False
            and after_restart["problem"] == "cursor_expired"
        )
        reconnect = await call(
            restarted,
            "list_libraries_v1",
            {},
            measurements,
        )
        require(reconnect["ok"] is True)

    return {
        "status": "passed",
        "schema_version": PROOF_SCHEMA,
        "tool_count": len(expectation["tools"]),
        "search_continuation": "passed",
        "exact_read": "passed",
        "cjk_cap": "passed",
        "cursor_expiry": "passed",
        "legacy_compatibility": "passed",
        "max_canonical_model_bytes": max(item[0] for item in measurements),
        "max_sdk_result_bytes": max(item[1] for item in measurements),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-command", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--allowed-root", type=Path, required=True)
    parser.add_argument("--expectation", type=Path, required=True)
    parser.add_argument("--ingest-fixture", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    try:
        receipt = asyncio.run(run(parse_args()))
    except Exception:
        print(json.dumps({"status": "failed", "code": "consumer_proof_failed"}))
        return 1
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
