from __future__ import annotations

import json
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace

import pytest
from mcp import StdioServerParameters


def _tool(name: str, properties: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        inputSchema={
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
        },
    )


def _tool_result(payload: Mapping[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        structuredContent=dict(payload),
        content=[],
        isError=False,
    )


def test_mcp_sdk_flow_uses_public_tools_in_order_and_validates_reports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.proof import mcp_deployment_client as client

    calls: list[tuple[str, dict[str, object]]] = []
    session_timeout: list[timedelta | None] = []
    report = {
        "provider": "faster-whisper",
        "model": "small",
        "model_revision": "a" * 40,
        "library_version": "1.2.3",
        "device": "cpu",
        "compute_type": "int8",
        "language": "auto",
        "detected_language": "en",
        "media_duration_ms": 3330,
        "transcription_duration_ms": 300,
        "segment_count": 1,
        "model_source": "cache",
    }
    responses: dict[str, dict[str, object]] = {
        "ingest_file": {
            "ok": True,
            "run_id": "run_1",
            "run_state": "published",
            "evidence_count": 1,
            "transcript_intake_report": report,
        },
        "get_run": {
            "ok": True,
            "run": {"run_id": "run_1", "state": "published"},
            "transcript_intake_report": report,
        },
        "search_library": {
            "ok": True,
            "results": [
                {
                    "evidence_id": "ev_1",
                    "publication_id": "pub_1",
                    "source_id": "src_1",
                    "locator": {"kind": "timestamp_ms", "start": 0, "end": 3000},
                    "text": "Evidence remains traceable after publication.",
                }
            ],
        },
        "ask_library": {
            "ok": True,
            "answer_status": "evidence_found",
            "evidence": [
                {
                    "evidence_id": "ev_1",
                    "publication_id": "pub_1",
                    "source_id": "src_1",
                    "locator": {"kind": "timestamp_ms", "start": 0, "end": 3000},
                    "text": "Evidence remains traceable after publication.",
                }
            ],
        },
    }

    @asynccontextmanager
    async def fake_stdio(
        server: StdioServerParameters,
        errlog: object = None,
    ) -> AsyncGenerator[tuple[object, object]]:
        assert server.command == "/tmp/installed-mke"
        yield object(), object()

    class FakeSession:
        def __init__(
            self,
            read: object,
            write: object,
            read_timeout_seconds: timedelta | None = None,
        ) -> None:
            session_timeout.append(read_timeout_seconds)

        async def __aenter__(self) -> FakeSession:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def initialize(self) -> None:
            return None

        async def list_tools(self) -> SimpleNamespace:
            return SimpleNamespace(
                tools=[
                    _tool("list_libraries", {}),
                    _tool("ingest_file", {"path": {"type": "string"}}),
                    _tool("get_run", {"run_id": {"type": "string"}}),
                    _tool(
                        "search_library",
                        {"query": {"type": "string"}, "limit": {"type": "integer"}},
                    ),
                    _tool(
                        "ask_library",
                        {"question": {"type": "string"}, "limit": {"type": "integer"}},
                    ),
                ]
            )

        async def call_tool(
            self,
            name: str,
            arguments: dict[str, object],
        ) -> SimpleNamespace:
            calls.append((name, arguments))
            return _tool_result(responses[name])

    monkeypatch.setattr(client, "stdio_client", fake_stdio)
    monkeypatch.setattr(client, "ClientSession", FakeSession)

    result = client.run_mcp_flow_sync(
        StdioServerParameters(command="/tmp/installed-mke"),
        "spoken-evidence.mp4",
        provider_timeout_seconds=120.0,
    )

    assert session_timeout == [timedelta(seconds=120)]
    assert calls == [
        ("ingest_file", {"path": "spoken-evidence.mp4"}),
        ("get_run", {"run_id": "run_1"}),
        ("search_library", {"query": "evidence", "limit": 5}),
        ("ask_library", {"question": "evidence publication", "limit": 5}),
    ]
    assert result["status"] == "passed"
    assert result["run_state"] == "published"
    assert result["search_keyword_matched"] is True
    assert result["ask_status"] == "evidence_found"
    assert result["transcript_intake_report"] == report


def test_mcp_sdk_client_rejects_provider_controls_in_tool_schema() -> None:
    from mke.proof.mcp_deployment_client import assert_public_tool_schemas

    tools = [
        _tool(
            "ingest_file",
            {
                "path": {"type": "string"},
                "model_cache": {"type": "string"},
            },
        )
    ]

    with pytest.raises(ValueError, match="tool schema"):
        assert_public_tool_schemas(tools)


def test_mcp_tool_result_parser_accepts_text_json_and_rejects_errors() -> None:
    from mcp import types

    from mke.proof.mcp_deployment_client import tool_payload

    payload = {"ok": True, "run_id": "run_1"}
    text_result = SimpleNamespace(
        structuredContent=None,
        content=[types.TextContent(type="text", text=json.dumps(payload))],
        isError=False,
    )
    assert tool_payload(text_result) == payload

    error_result = SimpleNamespace(
        structuredContent=None,
        content=[types.TextContent(type="text", text="private failure")],
        isError=True,
    )
    with pytest.raises(ValueError, match="MCP tool call failed"):
        tool_payload(error_result)


def test_mcp_sdk_flow_rejects_unsafe_transcript_report() -> None:
    from mke.proof.mcp_deployment_client import validate_mcp_flow

    report = {
        "provider": "faster-whisper",
        "model": "small",
        "model_revision": "a" * 40,
        "library_version": "/Users/private/secret",
        "device": "cpu",
        "compute_type": "int8",
        "language": "auto",
        "detected_language": "en",
        "media_duration_ms": 3330,
        "transcription_duration_ms": 300,
        "segment_count": 1,
        "model_source": "cache",
    }
    ingest: dict[str, object] = {
        "ok": True,
        "run_id": "run_1",
        "run_state": "published",
        "evidence_count": 1,
        "transcript_intake_report": report,
    }
    inspected: dict[str, object] = {
        "ok": True,
        "run": {"run_id": "run_1", "state": "published"},
        "transcript_intake_report": report,
    }

    with pytest.raises(ValueError, match="report mismatch"):
        validate_mcp_flow(
            ingest,
            inspected,
            {
                "ok": True,
                "results": [
                    {
                        "locator": {"kind": "timestamp_ms", "start": 0, "end": 1},
                        "text": "evidence",
                    }
                ],
            },
            {
                "ok": True,
                "answer_status": "evidence_found",
                "evidence": [
                    {
                        "locator": {"kind": "timestamp_ms", "start": 0, "end": 1},
                        "text": "evidence",
                    }
                ],
            },
        )
