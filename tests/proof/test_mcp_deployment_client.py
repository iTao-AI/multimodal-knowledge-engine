from __future__ import annotations

import hashlib
import json
import os
import sys
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TextIO

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


def test_mcp_sdk_flow_supports_direct_audio_keyword_without_request_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.proof import mcp_deployment_client as client

    calls: list[tuple[str, dict[str, object]]] = []
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
    evidence = {
        "schema_version": "mke.evidence_ref.v1",
        "evidence_id": "ev_" + "1" * 32,
        "publication_id": "pub_" + "2" * 32,
        "source_id": "src_" + "3" * 32,
        "content_fingerprint": "sha256:" + "b" * 64,
        "publication_revision": 1,
        "run_id": "run_" + "4" * 32,
        "locator": {"kind": "timestamp_ms", "start": 0, "end": 3000},
        "text": "Direct audio remains traceable after publication.",
    }
    responses: dict[str, dict[str, object]] = {
        "ingest_file": {
            "ok": True,
            "run_id": "run_" + "4" * 32,
            "run_state": "published",
            "evidence_count": 1,
            "transcript_intake_report": report,
        },
        "get_run": {
            "ok": True,
            "run": {"run_id": "run_" + "4" * 32, "state": "published"},
            "transcript_intake_report": report,
        },
        "search_library": {"ok": True, "results": [evidence]},
        "ask_library": {
            "ok": True,
            "answer_status": "evidence_found",
            "evidence": [evidence],
        },
        "search_library_v1": {
            "schema_version": "mke.search_library_response.v1",
            "ok": True,
            "query": "traceable",
            "observation": {
                "schema_version": "mke.active_publication_observation.v1",
                "library_id": "local",
                "state": "active",
                "source_count": 1,
                "active_publication_count": 1,
                "active_evidence_count": 1,
            },
            "results": [evidence],
        },
        "ask_library_v1": {
            "schema_version": "mke.ask_library_response.v1",
            "ok": True,
            "question": "traceable publication",
            "answer_status": "evidence_found",
            "summary": "Matched 1 active Evidence item.",
            "observation": {
                "schema_version": "mke.active_publication_observation.v1",
                "library_id": "local",
                "state": "active",
                "source_count": 1,
                "active_publication_count": 1,
                "active_evidence_count": 1,
            },
            "evidence": [evidence],
            "limitations": ["No model-generated answer is produced in this slice."],
        },
    }

    @asynccontextmanager
    async def fake_stdio(
        server: StdioServerParameters,
        errlog: object = None,
    ) -> AsyncGenerator[tuple[object, object]]:
        yield object(), object()

    class FakeSession:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

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
                    _tool("search_library", {"query": {}, "limit": {}}),
                    _tool("ask_library", {"question": {}, "limit": {}}),
                    _tool("search_library_v1", {"query": {}, "limit": {}}),
                    _tool("ask_library_v1", {"question": {}, "limit": {}}),
                ]
            )

        async def call_tool(
            self, name: str, arguments: dict[str, object]
        ) -> SimpleNamespace:
            calls.append((name, arguments))
            return _tool_result(responses[name])

    monkeypatch.setattr(client, "stdio_client", fake_stdio)
    monkeypatch.setattr(client, "ClientSession", FakeSession)

    result = client.run_mcp_flow_sync(
        StdioServerParameters(command="/tmp/installed-mke"),
        "direct-audio.m4a",
        provider_timeout_seconds=120.0,
        search_query="traceable",
        ask_question="traceable publication",
        expected_keyword="traceable",
        expected_content_fingerprint="sha256:" + "b" * 64,
        portable_evidence=True,
    )

    assert calls == [
        ("ingest_file", {"path": "direct-audio.m4a"}),
        ("get_run", {"run_id": "run_" + "4" * 32}),
        ("search_library", {"query": "traceable", "limit": 5}),
        ("ask_library", {"question": "traceable publication", "limit": 5}),
        ("search_library_v1", {"query": "traceable", "limit": 5}),
        ("ask_library_v1", {"question": "traceable publication", "limit": 5}),
    ]
    assert result["status"] == "passed"
    assert result["evidence_ref"] == evidence
    assert result["source_sha256"] == "b" * 64


def test_mcp_client_owner_supervision_pair_is_startup_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from mke.proof import mcp_deployment_client as client

    observed: list[tuple[StdioServerParameters, str, dict[str, object]]] = []

    def fake_run(
        server: StdioServerParameters,
        fixture_name: str,
        **kwargs: object,
    ) -> dict[str, object]:
        observed.append((server, fixture_name, kwargs))
        return {"status": "passed"}

    monkeypatch.setattr(client, "run_mcp_flow_sync", fake_run)
    monkeypatch.chdir(tmp_path)
    for name in ("home", "tmp", "cache"):
        (tmp_path / name).mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("TMPDIR", str(tmp_path / "tmp"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("PIP_CONFIG_FILE", os.devnull)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.setenv("UV_OFFLINE", "1")
    monkeypatch.setenv("PYTHONPATH", "/private/forbidden")
    monkeypatch.setenv("HTTPS_PROXY", "https://credential.invalid")
    diagnostic = tmp_path / "mcp-diagnostic.json"
    result = client.main(
        [
            "--mke-command",
            "/tmp/installed-mke",
            "--fixture-name",
            "direct-audio.wav",
            "--db",
            str(tmp_path / "mcp.sqlite"),
            "--allowed-root",
            str(tmp_path),
            "--child-cwd",
            str(tmp_path),
            "--diagnostic",
            str(diagnostic),
            "--model-revision",
            "a" * 40,
            "--direct-audio-footprint-bytes",
            "123456",
            "--direct-audio-footprint-budget-mode",
            "baseline_plus",
            "--search-query",
            "traceable",
            "--ask-question",
            "traceable publication",
            "--expected-keyword",
            "traceable",
        ]
    )

    assert result == 0
    server, fixture, kwargs = observed[0]
    assert fixture == "direct-audio.wav"
    assert server.args is not None
    assert server.args[-4:] == [
        "--direct-audio-footprint-bytes",
        "123456",
        "--direct-audio-footprint-budget-mode",
        "baseline_plus",
    ]
    assert kwargs["expected_keyword"] == "traceable"
    assert server.cwd == tmp_path
    assert server.env == {
        "HOME": str(tmp_path / "home"),
        "TMPDIR": str(tmp_path / "tmp"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "PIP_CONFIG_FILE": os.devnull,
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "UV_OFFLINE": "1",
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "C",
        "LC_ALL": "C",
        "LOGNAME": "",
        "SHELL": "",
        "TERM": "dumb",
        "USER": "",
    }
    assert server.env is not None
    assert "PYTHONPATH" not in server.env
    assert "HTTPS_PROXY" not in server.env
    assert not diagnostic.exists()


@pytest.mark.parametrize(
    "flags",
    [
        ["--direct-audio-footprint-bytes", "123456"],
        ["--direct-audio-footprint-budget-mode", "baseline_plus"],
    ],
)
def test_mcp_client_rejects_incomplete_owner_supervision_pair(
    flags: list[str], tmp_path: Path
) -> None:
    from mke.proof import mcp_deployment_client as client

    with pytest.raises(SystemExit):
        client.main(
            [
                "--mke-command",
                "/tmp/installed-mke",
                "--fixture-name",
                "direct-audio.wav",
                "--db",
                str(tmp_path / "mcp.sqlite"),
                "--allowed-root",
                str(tmp_path),
                "--model-revision",
                "a" * 40,
                *flags,
            ]
        )


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


def test_portable_mcp_evidence_rejects_search_ask_or_source_drift() -> None:
    from mke.proof.mcp_deployment_client import validate_portable_evidence

    run_id = "run_" + "4" * 32
    evidence = {
        "schema_version": "mke.evidence_ref.v1",
        "evidence_id": "ev_" + "1" * 32,
        "source_id": "src_" + "2" * 32,
        "content_fingerprint": "sha256:" + "b" * 64,
        "publication_id": "pub_" + "3" * 32,
        "publication_revision": 1,
        "run_id": run_id,
        "locator": {"kind": "timestamp_ms", "start": 0, "end": 1000},
        "text": "Direct audio remains traceable after publication.",
    }
    observation = {
        "schema_version": "mke.active_publication_observation.v1",
        "library_id": "local",
        "state": "active",
        "source_count": 1,
        "active_publication_count": 1,
        "active_evidence_count": 1,
    }
    searched: dict[str, object] = {
        "schema_version": "mke.search_library_response.v1",
        "ok": True,
        "query": "traceable",
        "observation": observation,
        "results": [evidence],
    }
    drifted = {**evidence, "source_id": "src_" + "9" * 32}
    asked: dict[str, object] = {
        "schema_version": "mke.ask_library_response.v1",
        "ok": True,
        "question": "traceable publication",
        "answer_status": "evidence_found",
        "summary": "Matched 1 active Evidence item.",
        "observation": observation,
        "evidence": [drifted],
        "limitations": ["No model-generated answer is produced in this slice."],
    }

    with pytest.raises(ValueError, match="Search and Ask Evidence mismatch"):
        validate_portable_evidence(
            searched,
            asked,
            run_id=run_id,
            content_fingerprint="sha256:" + "b" * 64,
            keyword="traceable",
            media_duration_ms=3000,
        )

    asked["evidence"] = [evidence]
    with pytest.raises(ValueError, match="Source or Run identity mismatch"):
        validate_portable_evidence(
            searched,
            asked,
            run_id=run_id,
            content_fingerprint="sha256:" + "f" * 64,
            keyword="traceable",
            media_duration_ms=3000,
        )


def _stage_flow_responses() -> dict[str, dict[str, object]]:
    run_id = "run_" + "4" * 32
    evidence = {
        "schema_version": "mke.evidence_ref.v1",
        "evidence_id": "ev_" + "1" * 32,
        "source_id": "src_" + "2" * 32,
        "content_fingerprint": "sha256:" + "b" * 64,
        "publication_id": "pub_" + "3" * 32,
        "publication_revision": 1,
        "run_id": run_id,
        "locator": {"kind": "timestamp_ms", "start": 0, "end": 1000},
        "text": "Direct audio remains traceable after publication.",
    }
    report = {
        "provider": "faster-whisper",
        "model": "small",
        "model_revision": "a" * 40,
        "library_version": "1.2.3",
        "device": "cpu",
        "compute_type": "int8",
        "language": "auto",
        "detected_language": "en",
        "media_duration_ms": 3000,
        "transcription_duration_ms": 300,
        "segment_count": 1,
        "model_source": "cache",
    }
    observation = {
        "schema_version": "mke.active_publication_observation.v1",
        "library_id": "local",
        "state": "active",
        "source_count": 1,
        "active_publication_count": 1,
        "active_evidence_count": 1,
    }
    return {
        "ingest_file": {
            "ok": True,
            "run_id": run_id,
            "run_state": "published",
            "evidence_count": 1,
            "transcript_intake_report": report,
        },
        "get_run": {
            "ok": True,
            "run": {"run_id": run_id, "state": "published"},
            "transcript_intake_report": report,
        },
        "search_library": {"ok": True, "results": [evidence]},
        "ask_library": {
            "ok": True,
            "answer_status": "evidence_found",
            "evidence": [evidence],
        },
        "search_library_v1": {
            "schema_version": "mke.search_library_response.v1",
            "ok": True,
            "query": "traceable",
            "observation": observation,
            "results": [evidence],
        },
        "ask_library_v1": {
            "schema_version": "mke.ask_library_response.v1",
            "ok": True,
            "question": "traceable publication",
            "answer_status": "evidence_found",
            "summary": "Matched 1 active Evidence item.",
            "observation": observation,
            "evidence": [evidence],
            "limitations": ["No model-generated answer is produced in this slice."],
        },
    }


@pytest.mark.parametrize(
    "failing_stage",
    (
        "startup",
        "schema",
        "ingest",
        "get_run",
        "search",
        "ask",
        "portable_search",
        "portable_ask",
        "shutdown",
        "flow_validation",
        "portable_validation",
    ),
)
def test_mcp_failures_preserve_closed_stable_stage(
    monkeypatch: pytest.MonkeyPatch,
    failing_stage: str,
) -> None:
    from mke.proof import mcp_deployment_client as client

    responses = _stage_flow_responses()

    @asynccontextmanager
    async def fake_stdio(
        server: StdioServerParameters,
        errlog: object,
    ) -> AsyncGenerator[tuple[object, object]]:
        del server, errlog
        if failing_stage == "startup":
            raise OSError("/private/raw-startup-secret")
        yield object(), object()

    class StageSession:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> StageSession:
            return self

        async def __aexit__(self, *args: object) -> None:
            if failing_stage == "shutdown":
                raise ValueError("/private/raw-shutdown-secret")
            return None

        async def initialize(self) -> None:
            return None

        async def list_tools(self) -> SimpleNamespace:
            if failing_stage == "schema":
                raise ValueError("/private/raw-schema-secret")
            return SimpleNamespace(
                tools=[
                    _tool("list_libraries", {}),
                    _tool("ingest_file", {"path": {}}),
                    _tool("get_run", {"run_id": {}}),
                    _tool("search_library", {"query": {}, "limit": {}}),
                    _tool("ask_library", {"question": {}, "limit": {}}),
                    _tool("search_library_v1", {"query": {}, "limit": {}}),
                    _tool("ask_library_v1", {"question": {}, "limit": {}}),
                ]
            )

        async def call_tool(
            self,
            name: str,
            arguments: dict[str, object],
        ) -> SimpleNamespace:
            del arguments
            mapped = {
                "ingest_file": "ingest",
                "get_run": "get_run",
                "search_library": "search",
                "ask_library": "ask",
                "search_library_v1": "portable_search",
                "ask_library_v1": "portable_ask",
            }[name]
            if mapped == failing_stage:
                raise ValueError("/private/raw-tool-secret")
            return _tool_result(responses[name])

    monkeypatch.setattr(client, "stdio_client", fake_stdio)
    monkeypatch.setattr(client, "ClientSession", StageSession)
    if failing_stage == "flow_validation":
        def fail_flow(*args: object, **kwargs: object) -> dict[str, object]:
            del args, kwargs
            raise ValueError("/private/raw-flow-secret")

        monkeypatch.setattr(
            client,
            "validate_mcp_flow",
            fail_flow,
        )
    if failing_stage == "portable_validation":
        def fail_portable(*args: object, **kwargs: object) -> dict[str, object]:
            del args, kwargs
            raise ValueError("/private/raw-portable-secret")

        monkeypatch.setattr(
            client,
            "validate_portable_evidence",
            fail_portable,
        )

    with pytest.raises(client.McpDeploymentFailure) as captured:
        client.run_mcp_flow_sync(
            StdioServerParameters(command="/tmp/installed-mke"),
            "direct-audio.m4a",
            provider_timeout_seconds=120.0,
            search_query="traceable",
            ask_question="traceable publication",
            expected_keyword="traceable",
            expected_content_fingerprint="sha256:" + "b" * 64,
            portable_evidence=True,
        )

    assert captured.value.stage == failing_stage
    assert "/private" not in str(captured.value)


def test_bounded_nonempty_server_stderr_does_not_fail_validated_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.proof import mcp_deployment_client as client

    responses = _stage_flow_responses()

    @asynccontextmanager
    async def warning_stdio(
        server: StdioServerParameters,
        errlog: TextIO,
    ) -> AsyncGenerator[tuple[object, object]]:
        del server
        errlog.write("ordinary bounded warning\n")
        errlog.flush()
        yield object(), object()

    class SuccessfulSession:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> SuccessfulSession:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def initialize(self) -> None:
            return None

        async def list_tools(self) -> SimpleNamespace:
            return SimpleNamespace(
                tools=[
                    _tool("list_libraries", {}),
                    _tool("ingest_file", {"path": {}}),
                    _tool("get_run", {"run_id": {}}),
                    _tool("search_library", {"query": {}, "limit": {}}),
                    _tool("ask_library", {"question": {}, "limit": {}}),
                ]
            )

        async def call_tool(
            self, name: str, arguments: dict[str, object]
        ) -> SimpleNamespace:
            del arguments
            return _tool_result(responses[name])

    monkeypatch.setattr(client, "stdio_client", warning_stdio)
    monkeypatch.setattr(client, "ClientSession", SuccessfulSession)

    result = client.run_mcp_flow_sync(
        StdioServerParameters(command="/tmp/installed-mke"),
        "direct-audio.m4a",
        provider_timeout_seconds=120.0,
        expected_keyword="traceable",
    )

    assert result["status"] == "passed"


def test_stderr_overflow_fails_closed_without_raw_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.proof import mcp_deployment_client as client

    @asynccontextmanager
    async def overflowing_stdio(
        server: StdioServerParameters,
        errlog: TextIO,
    ) -> AsyncGenerator[tuple[object, object]]:
        del server
        errlog.write(
            "s" * (client._MAX_SERVER_STDERR_BYTES + 1)  # pyright: ignore[reportPrivateUsage]
        )
        errlog.flush()
        raise OSError("/private/raw-overflow-secret")
        yield object(), object()

    monkeypatch.setattr(client, "stdio_client", overflowing_stdio)

    with pytest.raises(client.McpDeploymentFailure) as captured:
        client.run_mcp_flow_sync(
            StdioServerParameters(command="/tmp/installed-mke"),
            "direct-audio.m4a",
            provider_timeout_seconds=120.0,
        )

    assert captured.value.stage == "stderr"
    assert captured.value.stderr["overflow"] is True
    assert "/private" not in str(captured.value)


def test_stderr_capture_failure_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    from mke.proof import mcp_deployment_client as client

    real_finish = client._BoundedStderrCapture.finish  # pyright: ignore[reportPrivateUsage]

    def failed_finish(self: Any) -> dict[str, object]:
        metadata = real_finish(self)
        return {**metadata, "capture_failed": True}

    monkeypatch.setattr(
        client._BoundedStderrCapture,  # pyright: ignore[reportPrivateUsage]
        "finish",
        failed_finish,
    )

    with pytest.raises(client.McpDeploymentFailure) as captured:
        client.run_mcp_flow_sync(
            StdioServerParameters(
                command=sys.executable,
                args=["-I", "-B", "-c", "pass"],
            ),
            "direct-audio.m4a",
            provider_timeout_seconds=5.0,
        )

    assert captured.value.stage == "stderr"
    assert captured.value.stderr["capture_failed"] is True


@pytest.mark.parametrize(
    ("stage", "stderr_bytes", "overflow", "capture_failed"),
    (
        ("search", 256 * 1024 + 1, True, False),
        ("search", 0, False, True),
        ("stderr", 0, False, False),
        ("stderr", 256 * 1024, True, False),
    ),
)
def test_mcp_failure_normalizes_generator_impossible_stderr_semantics(
    stage: str,
    stderr_bytes: int,
    overflow: bool,
    capture_failed: bool,
) -> None:
    from mke.proof import mcp_deployment_client as client

    failure = client.McpDeploymentFailure(
        stage,  # pyright: ignore[reportArgumentType]
        {
            "bytes": stderr_bytes,
            "sha256": hashlib.sha256(b"stderr").hexdigest(),
            "overflow": overflow,
            "capture_failed": capture_failed,
        },
    )

    assert failure.stage == "stderr"
    assert failure.stderr == {
        "bytes": 0,
        "sha256": hashlib.sha256(b"").hexdigest(),
        "overflow": False,
        "capture_failed": True,
    }


@pytest.mark.parametrize(
    ("stage", "stderr_bytes", "overflow", "capture_failed"),
    (
        ("search", len(b"stderr"), False, False),
        ("search", 256 * 1024, False, False),
        ("stderr", 256 * 1024 + 1, True, False),
        ("stderr", 0, False, True),
    ),
)
def test_mcp_failure_preserves_exact_valid_stderr_semantics(
    stage: str,
    stderr_bytes: int,
    overflow: bool,
    capture_failed: bool,
) -> None:
    from mke.proof import mcp_deployment_client as client

    metadata = {
        "bytes": stderr_bytes,
        "sha256": hashlib.sha256(b"stderr").hexdigest(),
        "overflow": overflow,
        "capture_failed": capture_failed,
    }
    failure = client.McpDeploymentFailure(
        stage,  # pyright: ignore[reportArgumentType]
        metadata,
    )

    assert failure.stage == stage
    assert failure.stderr == metadata


def test_real_stdio_boundary_captures_stderr_without_parent_sink() -> None:
    from mke.proof import mcp_deployment_client as client

    warning = b"bounded-real-stdio-warning\n"
    with pytest.raises(client.McpDeploymentFailure) as captured:
        client.run_mcp_flow_sync(
            StdioServerParameters(
                command=sys.executable,
                args=[
                    "-I",
                    "-B",
                    "-c",
                    "import sys; sys.stderr.write('bounded-real-stdio-warning\\n')",
                ],
                env={"PATH": "/usr/bin:/bin"},
                cwd=Path.cwd(),
            ),
            "direct-audio.m4a",
            provider_timeout_seconds=5.0,
        )

    assert captured.value.stage == "startup"
    assert captured.value.stderr == {
        "bytes": len(warning),
        "sha256": hashlib.sha256(warning).hexdigest(),
        "overflow": False,
        "capture_failed": False,
    }


def test_client_failure_writes_closed_operator_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from mke.proof import mcp_deployment_client as client

    monkeypatch.chdir(tmp_path)
    for name in ("home", "tmp", "cache"):
        (tmp_path / name).mkdir()
    for key, value in {
        "HOME": str(tmp_path / "home"),
        "TMPDIR": str(tmp_path / "tmp"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "PIP_CONFIG_FILE": os.devnull,
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "UV_OFFLINE": "1",
    }.items():
        monkeypatch.setenv(key, value)
    diagnostic = tmp_path / "mcp-diagnostic.json"
    stderr = b"private server warning"

    def fail(*args: object, **kwargs: object) -> dict[str, object]:
        del args, kwargs
        raise client.McpDeploymentFailure(
            "search",
            {
                "bytes": len(stderr),
                "sha256": hashlib.sha256(stderr).hexdigest(),
                "overflow": False,
                "capture_failed": False,
            },
        )

    monkeypatch.setattr(client, "run_mcp_flow_sync", fail)

    result = client.main(
        [
            "--mke-command",
            "/tmp/installed-mke",
            "--fixture-name",
            "direct-audio.wav",
            "--db",
            str(tmp_path / "mcp.sqlite"),
            "--allowed-root",
            str(tmp_path),
            "--child-cwd",
            str(tmp_path),
            "--diagnostic",
            str(diagnostic),
            "--model-revision",
            "a" * 40,
        ]
    )

    assert result == 1
    assert json.loads(capsys.readouterr().out) == {
        "status": "failed",
        "reason": "mcp_deployment_failed",
    }
    assert json.loads(diagnostic.read_text(encoding="ascii")) == {
        "schema_version": "mke.mcp_deployment_diagnostic.v1",
        "status": "failed",
        "failure": "mcp_deployment_failed",
        "stage": "search",
        "stderr": {
            "bytes": len(stderr),
            "sha256": hashlib.sha256(stderr).hexdigest(),
            "overflow": False,
            "capture_failed": False,
        },
    }
    assert diagnostic.stat().st_mode & 0o777 == 0o600
    assert "private server warning" not in diagnostic.read_text(encoding="ascii")


def test_client_diagnostic_rejects_symlink_parent_without_operator_write(
    tmp_path: Path,
) -> None:
    from mke.proof import mcp_deployment_client as client

    operator = tmp_path / "operator"
    operator.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(operator, target_is_directory=True)

    with pytest.raises(client.McpDiagnosticWriteError):
        client.write_mcp_diagnostic(
            alias / "mcp-diagnostic.json",
            client.McpDeploymentFailure(
                "startup",
                {
                    "bytes": 0,
                    "sha256": hashlib.sha256(b"").hexdigest(),
                    "overflow": False,
                    "capture_failed": False,
                },
            ),
        )

    assert not (operator / "mcp-diagnostic.json").exists()


def test_client_diagnostic_rejects_existing_destination_without_clobber(
    tmp_path: Path,
) -> None:
    from mke.proof import mcp_deployment_client as client

    diagnostic = tmp_path / "mcp-diagnostic.json"
    diagnostic.write_bytes(b"operator-state")

    with pytest.raises(client.McpDiagnosticWriteError):
        client.write_mcp_diagnostic(
            diagnostic,
            client.McpDeploymentFailure("startup"),
        )

    assert diagnostic.read_bytes() == b"operator-state"
