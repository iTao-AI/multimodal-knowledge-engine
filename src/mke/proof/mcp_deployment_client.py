"""Installed-package stdio MCP SDK deployment proof client."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import timedelta
from pathlib import Path
from typing import cast

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

_EXPECTED_TOOL_FIELDS: dict[str, frozenset[str]] = {
    "list_libraries": frozenset(),
    "ingest_file": frozenset({"path"}),
    "get_run": frozenset({"run_id"}),
    "search_library": frozenset({"query", "limit"}),
    "ask_library": frozenset({"question", "limit"}),
}
_FORBIDDEN_SCHEMA_TERMS = (
    "provider",
    "model",
    "revision",
    "cache",
    "argv",
    "endpoint",
    "credential",
    "download",
)
_SAFE_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.!_+()-]{0,255}\Z")
_MODEL_PART_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}\Z")
_COMMIT_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
_REPORT_IDENTITY_FIELDS = (
    "provider",
    "model",
    "model_revision",
    "library_version",
    "device",
    "compute_type",
    "language",
    "detected_language",
    "model_source",
)


async def run_mcp_flow(
    server: StdioServerParameters,
    fixture_name: str,
    *,
    provider_timeout_seconds: float,
) -> dict[str, object]:
    """Run the installed stdio MCP flow through the official Python SDK."""
    if provider_timeout_seconds <= 0:
        raise ValueError("provider timeout must be positive")
    timeout = timedelta(seconds=provider_timeout_seconds)
    async with stdio_client(server) as (read, write):
        async with ClientSession(
            read,
            write,
            read_timeout_seconds=timeout,
        ) as session:
            await session.initialize()
            listed = await session.list_tools()
            assert_public_tool_schemas(listed.tools)

            ingest = tool_payload(
                await session.call_tool("ingest_file", {"path": fixture_name})
            )
            run_id = _required_string(ingest, "run_id")
            inspected = tool_payload(
                await session.call_tool("get_run", {"run_id": run_id})
            )
            searched = tool_payload(
                await session.call_tool(
                    "search_library",
                    {"query": "evidence", "limit": 5},
                )
            )
            asked = tool_payload(
                await session.call_tool(
                    "ask_library",
                    {"question": "evidence publication", "limit": 5},
                )
            )
    return validate_mcp_flow(ingest, inspected, searched, asked)


def run_mcp_flow_sync(
    server: StdioServerParameters,
    fixture_name: str,
    *,
    provider_timeout_seconds: float,
) -> dict[str, object]:
    return asyncio.run(
        run_mcp_flow(
            server,
            fixture_name,
            provider_timeout_seconds=provider_timeout_seconds,
        )
    )


def assert_public_tool_schemas(tools: Iterable[object]) -> None:
    """Require the stable public tool fields and reject owner runtime controls."""
    observed: dict[str, frozenset[str]] = {}
    for tool in tools:
        name = getattr(tool, "name", None)
        raw_schema = getattr(tool, "inputSchema", None)
        if not isinstance(name, str) or not isinstance(raw_schema, dict):
            raise ValueError("MCP tool schema is invalid")
        schema = cast(Mapping[str, object], raw_schema)
        rendered = json.dumps(schema, sort_keys=True).casefold()
        if any(term in rendered for term in _FORBIDDEN_SCHEMA_TERMS):
            raise ValueError("MCP tool schema exposes owner runtime controls")
        raw_properties = schema.get("properties", {})
        if not isinstance(raw_properties, dict):
            raise ValueError("MCP tool schema properties are invalid")
        properties = cast(Mapping[str, object], raw_properties)
        observed[name] = frozenset(str(field) for field in properties)

    for name, expected in _EXPECTED_TOOL_FIELDS.items():
        if observed.get(name) != expected:
            raise ValueError("MCP public tool schema mismatch")


def tool_payload(result: object) -> dict[str, object]:
    """Extract one object from structuredContent or a TextContent JSON fallback."""
    if bool(getattr(result, "isError", False)):
        raise ValueError("MCP tool call failed")
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return cast(dict[str, object], structured)

    raw_content = getattr(result, "content", None)
    if not isinstance(raw_content, list):
        raise ValueError("MCP tool result is missing content")
    content = cast(list[object], raw_content)
    for item in content:
        if isinstance(item, types.TextContent):
            try:
                payload = json.loads(item.text)
            except json.JSONDecodeError as error:
                raise ValueError("MCP tool result is not valid JSON") from error
            if isinstance(payload, dict):
                return cast(dict[str, object], payload)
    raise ValueError("MCP tool result is missing an object payload")


def validate_mcp_flow(
    ingest: dict[str, object],
    inspected: dict[str, object],
    searched: dict[str, object],
    asked: dict[str, object],
) -> dict[str, object]:
    if ingest.get("ok") is not True or ingest.get("run_state") != "published":
        raise ValueError("MCP ingest did not publish")
    run_id = _required_string(ingest, "run_id")
    raw_run = inspected.get("run")
    if (
        inspected.get("ok") is not True
        or not isinstance(raw_run, dict)
    ):
        raise ValueError("MCP Run inspection mismatch")
    run = cast(Mapping[str, object], raw_run)
    if run.get("run_id") != run_id or run.get("state") != "published":
        raise ValueError("MCP Run inspection mismatch")

    ingest_report = _required_report(ingest)
    inspected_report = _required_report(inspected)
    if ingest_report != inspected_report or not _is_public_transcript_report(ingest_report):
        raise ValueError("MCP transcript report mismatch")

    raw_results = searched.get("results")
    if (
        searched.get("ok") is not True
        or not isinstance(raw_results, list)
        or not raw_results
    ):
        raise ValueError("MCP Search returned no Evidence")
    results = cast(list[object], raw_results)
    if not all(_is_timestamp_evidence(item, keyword="evidence") for item in results):
        raise ValueError("MCP Search Evidence is invalid")

    raw_answer_evidence = asked.get("evidence")
    if (
        asked.get("ok") is not True
        or asked.get("answer_status") != "evidence_found"
        or not isinstance(raw_answer_evidence, list)
        or not raw_answer_evidence
    ):
        raise ValueError("MCP Ask did not return timestamp Evidence")
    answer_evidence = cast(list[object], raw_answer_evidence)
    if not all(_is_timestamp_evidence(item) for item in answer_evidence):
        raise ValueError("MCP Ask did not return timestamp Evidence")

    evidence_count = ingest.get("evidence_count")
    if type(evidence_count) is not int or evidence_count <= 0:
        raise ValueError("MCP ingest Evidence count is invalid")
    return {
        "status": "passed",
        "run_state": "published",
        "evidence_count": evidence_count,
        "search_keyword_matched": True,
        "ask_status": "evidence_found",
        "transcript_intake_report": ingest_report,
    }


def _is_timestamp_evidence(value: object, *, keyword: str | None = None) -> bool:
    if not isinstance(value, dict):
        return False
    evidence = cast(Mapping[str, object], value)
    raw_locator = evidence.get("locator")
    text = evidence.get("text")
    if not isinstance(raw_locator, dict) or not isinstance(text, str):
        return False
    locator = cast(Mapping[str, object], raw_locator)
    start = locator.get("start")
    end = locator.get("end")
    return (
        locator.get("kind") == "timestamp_ms"
        and type(start) is int
        and type(end) is int
        and start >= 0
        and end > start
        and (keyword is None or keyword in text.casefold())
    )


def _required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError("MCP result is missing a required identifier")
    return value


def _required_report(payload: dict[str, object]) -> dict[str, object]:
    report = payload.get("transcript_intake_report")
    if not isinstance(report, dict):
        raise ValueError("MCP result is missing the transcript report")
    return cast(dict[str, object], report)


def _is_public_transcript_report(report: Mapping[str, object]) -> bool:
    if report.get("provider") != "faster-whisper" or report.get("model_source") != "cache":
        return False
    if not _is_safe_model(report.get("model")):
        return False
    revision = report.get("model_revision")
    if not isinstance(revision, str) or _COMMIT_SHA_RE.fullmatch(revision) is None:
        return False
    for field in _REPORT_IDENTITY_FIELDS:
        if field in {"model", "model_revision"}:
            continue
        value = report.get(field)
        if not isinstance(value, str) or _SAFE_TOKEN_RE.fullmatch(value) is None:
            return False
    for field in ("media_duration_ms", "segment_count"):
        value = report.get(field)
        if type(value) is not int or value <= 0:
            return False
    duration = report.get("transcription_duration_ms")
    return type(duration) is int and duration >= 0


def _is_safe_model(value: object) -> bool:
    if not isinstance(value, str):
        return False
    if _SAFE_TOKEN_RE.fullmatch(value) is not None:
        return True
    parts = value.split("/")
    return len(parts) == 2 and all(_MODEL_PART_RE.fullmatch(part) for part in parts)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m mke.proof.mcp_deployment_client")
    parser.add_argument("--mke-command", required=True)
    parser.add_argument("--fixture-name", required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--allowed-root", type=Path, required=True)
    parser.add_argument("--model", default="small")
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--language", default="auto")
    parser.add_argument("--model-cache", type=Path)
    parser.add_argument("--transcription-timeout-seconds", type=float, default=900.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    server_args = [
        "--db",
        str(args.db),
        "mcp",
        "--allowed-root",
        str(args.allowed_root),
        "--transcript-provider",
        "faster-whisper",
        "--model",
        args.model,
        "--model-revision",
        args.model_revision,
        "--device",
        args.device,
        "--compute-type",
        args.compute_type,
        "--language",
        args.language,
        "--transcription-timeout-seconds",
        str(args.transcription_timeout_seconds),
    ]
    if args.model_cache is not None:
        server_args.extend(("--model-cache", str(args.model_cache)))
    try:
        report = run_mcp_flow_sync(
            StdioServerParameters(
                command=args.mke_command,
                args=server_args,
            ),
            args.fixture_name,
            provider_timeout_seconds=args.transcription_timeout_seconds,
        )
    except Exception:
        print(json.dumps({"status": "failed", "reason": "mcp_deployment_failed"}))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
