"""Public-safe real stdio proof for the strict Evidence provenance contract."""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
import sqlite3
import sys
import tempfile
from collections.abc import Mapping
from datetime import timedelta
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import TypeAdapter, ValidationError

from mke.interfaces.mcp_schemas import (
    AskLibraryResponseV1,
    AskLibrarySuccessV1,
    EvidenceRefV1,
    ListLibrariesResponseV1,
    ListLibrariesSuccessV1,
    SearchLibraryErrorV1,
    SearchLibraryResponseV1,
    SearchLibrarySuccessV1,
)
from mke.proof.mcp_deployment_client import assert_public_tool_schemas, tool_payload

_TIMEOUT_SECONDS = 60.0


def run_evidence_provenance_proof(
    repo_root: Path,
    mke_executable: Path,
    *,
    server_cwd: Path | None = None,
) -> dict[str, object]:
    root = repo_root.resolve()
    executable = mke_executable.resolve()
    if not executable.is_file():
        raise ValueError("MKE executable is unavailable")
    with tempfile.TemporaryDirectory(prefix="mke-evidence-provenance-") as directory:
        temporary = Path(directory)
        cwd = (server_cwd or root).resolve()
        first_database = temporary / "first.sqlite"
        first = _server(executable, root, cwd, first_database)
        second = _server(executable, root, cwd, temporary / "second.sqlite")
        report = asyncio.run(_run(first, second, root, first_database))
    if temporary.exists():
        raise ValueError("temporary store cleanup failed")
    report["temporary_store_cleanup"] = True
    return report


def _server(executable: Path, root: Path, cwd: Path, database: Path) -> StdioServerParameters:
    return StdioServerParameters(
        command=str(executable),
        args=["--db", str(database), "mcp", "--allowed-root", str(root / "tests/fixtures")],
        cwd=cwd,
    )


async def _call(
    session: ClientSession, name: str, arguments: dict[str, object]
) -> dict[str, object]:
    result = await asyncio.wait_for(session.call_tool(name, arguments), timeout=_TIMEOUT_SECONDS)
    return tool_payload(result)


async def _run(
    first: StdioServerParameters,
    second: StdioServerParameters,
    root: Path,
    first_database: Path,
) -> dict[str, object]:
    legacy_fixture = json.loads(
        (root / "tests/fixtures/mcp/legacy-tool-schemas.json").read_text(encoding="utf-8")
    )["tools"]
    timeout = timedelta(seconds=_TIMEOUT_SECONDS)
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as errlog:
        async with stdio_client(first, errlog=errlog) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timeout) as session:
                await asyncio.wait_for(session.initialize(), timeout=_TIMEOUT_SECONDS)
                listed = await asyncio.wait_for(session.list_tools(), timeout=_TIMEOUT_SECONDS)
                assert_public_tool_schemas(listed.tools)
                tools = {tool.name: tool for tool in listed.tools}
                for name, schemas in legacy_fixture.items():
                    assert tools[name].inputSchema == schemas["inputSchema"]
                    assert tools[name].outputSchema == schemas["outputSchema"]
                _validate_v1_tool_schemas(tools)

                empty = _list(await _call(session, "list_libraries_v1", {}))
                if empty.observation.state != "empty":
                    raise ValueError("fresh store observation mismatch")
                failed = await _call(session, "ingest_file", {"path": "pdf/invalid.pdf"})
                if failed.get("ok") is not False:
                    raise ValueError("invalid PDF did not fail")
                no_active = _list(await _call(session, "list_libraries_v1", {}))
                if no_active.observation.state != "no_active_publication":
                    raise ValueError("failed ingest observation mismatch")

                await _call(session, "ingest_file", {"path": "pdf/text-layer.pdf"})
                page_search = _search(
                    await _call(
                        session, "search_library_v1", {"query": "publication active", "limit": 5}
                    )
                )
                page_ask = _ask(
                    await _call(
                        session, "ask_library_v1", {"question": "publication active", "limit": 5}
                    )
                )
                page = _matching_projection(page_search, page_ask, "page")
                no_match = _search(
                    await _call(session, "search_library_v1", {"query": "absenttoken", "limit": 5})
                )
                if no_match.observation.state != "active" or no_match.results:
                    raise ValueError("active no-match observation mismatch")

                await _call(session, "ingest_file", {"path": "pdf/text-layer.pdf"})
                reingested = _search(
                    await _call(
                        session, "search_library_v1", {"query": "publication active", "limit": 5}
                    )
                ).results[0]
                if not (
                    reingested.source_id == page.source_id
                    and reingested.content_fingerprint == page.content_fingerprint
                    and reingested.run_id != page.run_id
                    and reingested.publication_id != page.publication_id
                    and reingested.publication_revision > page.publication_revision
                    and reingested.evidence_id != page.evidence_id
                ):
                    raise ValueError("same-store identity contract mismatch")

                await _call(session, "ingest_file", {"path": "video/short-audio.mp4"})
                video_search = _search(
                    await _call(
                        session, "search_library_v1", {"query": "timestamp proof", "limit": 5}
                    )
                )
                video_ask = _ask(
                    await _call(
                        session, "ask_library_v1", {"question": "timestamp proof", "limit": 5}
                    )
                )
                _matching_projection(video_search, video_ask, "timestamp_ms")

                _verify_malformed_payload_rejection(page_search)
                with sqlite3.connect(first_database) as connection:
                    connection.execute("UPDATE run_manifests SET evidence_count = 999")
                failed_search = (
                    TypeAdapter(SearchLibraryResponseV1)
                    .validate_python(
                        await _call(
                            session,
                            "search_library_v1",
                            {"query": "publication active", "limit": 5},
                        )
                    )
                    .root
                )
                if not isinstance(failed_search, SearchLibraryErrorV1) or failed_search != (
                    SearchLibraryErrorV1(
                        ok=False,
                        problem="internal_error",
                        cause="operation failed; details were redacted",
                        next_step="check_server_logs",
                    )
                ):
                    raise ValueError("unexpected exception was not redacted")

    fresh = await _fresh_fingerprint(second)
    if fresh != page.content_fingerprint:
        raise ValueError("fresh-store fingerprint identity mismatch")
    transport_failure_bounded = await _verify_bounded_stdio_failure(
        StdioServerParameters(command=sys.executable, args=["-c", "raise SystemExit(1)"])
    )
    timeout_pid_path = first_database.parent / "timeout-child.pid"
    timeout_bounded = await _verify_bounded_stdio_failure(
        StdioServerParameters(
            command=sys.executable,
            args=[
                "-c",
                (
                    "import os,sys,time; from pathlib import Path; "
                    "Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(10)"
                ),
                str(timeout_pid_path),
            ],
        ),
        timeout_seconds=0.1,
        child_pid_path=timeout_pid_path,
    )
    return {
        "proof": "evidence_provenance",
        "status": "passed",
        "schema_versions": [
            "mke.evidence_ref.v1",
            "mke.active_publication_observation.v1",
            "mke.list_libraries_response.v1",
            "mke.search_library_response.v1",
            "mke.ask_library_response.v1",
        ],
        "legacy_tools": 5,
        "strict_tools": 3,
        "states": ["empty", "no_active_publication", "active"],
        "locators": ["page", "timestamp_ms"],
        "search_ask_projection_equal": True,
        "same_store_identity": True,
        "fresh_store_fingerprint_identity": True,
        "malformed_payloads_rejected": True,
        "unexpected_exception_redacted": True,
        "transport_failure_bounded": transport_failure_bounded,
        "timeout_bounded": timeout_bounded,
        "timeout_child_terminated": timeout_bounded,
    }


def _verify_malformed_payload_rejection(value: SearchLibrarySuccessV1) -> None:
    payload = value.model_dump(mode="json")
    malformed: list[dict[str, object]] = []
    extra = copy.deepcopy(payload)
    extra["path"] = "/not-public"
    malformed.append(extra)
    version = copy.deepcopy(payload)
    version["schema_version"] = "mke.search_library_response.v2"
    malformed.append(version)
    locator = copy.deepcopy(payload)
    locator["results"][0]["locator"] = {"kind": "page", "start": 1, "end": 2}
    malformed.append(locator)
    for candidate in malformed:
        try:
            TypeAdapter(SearchLibraryResponseV1).validate_python(candidate)
        except ValidationError:
            continue
        raise ValueError("malformed v1 payload was accepted")


async def _verify_bounded_stdio_failure(
    server: StdioServerParameters,
    *,
    timeout_seconds: float = 1.0,
    child_pid_path: Path | None = None,
) -> bool:
    process_logger = logging.getLogger("mcp.os.posix.utilities")
    previous_disabled = process_logger.disabled
    process_logger.disabled = True
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as errlog:
        try:
            async with stdio_client(server, errlog=errlog) as (read, write):
                async with ClientSession(
                    read,
                    write,
                    read_timeout_seconds=timedelta(seconds=timeout_seconds),
                ) as session:
                    await asyncio.wait_for(session.initialize(), timeout=timeout_seconds)
        except Exception:
            if child_pid_path is not None:
                child_pid = await _read_child_pid(child_pid_path)
                await _require_process_terminated(child_pid)
            return True
        finally:
            process_logger.disabled = previous_disabled
    raise ValueError("stdio failure did not fail closed")


async def _read_child_pid(path: Path) -> int:
    deadline = asyncio.get_running_loop().time() + 1.0
    while asyncio.get_running_loop().time() < deadline:
        try:
            value = int(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            await asyncio.sleep(0.01)
            continue
        if value > 0:
            return value
        break
    raise ValueError("timeout child did not publish a valid PID")


async def _require_process_terminated(pid: int) -> None:
    deadline = asyncio.get_running_loop().time() + 2.0
    while asyncio.get_running_loop().time() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        await asyncio.sleep(0.01)
    raise ValueError("timeout child process remained alive")


async def _fresh_fingerprint(server: StdioServerParameters) -> str:
    timeout = timedelta(seconds=_TIMEOUT_SECONDS)
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as errlog:
        async with stdio_client(server, errlog=errlog) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timeout) as session:
                await asyncio.wait_for(session.initialize(), timeout=_TIMEOUT_SECONDS)
                await _call(session, "ingest_file", {"path": "pdf/text-layer.pdf"})
                result = _search(
                    await _call(
                        session, "search_library_v1", {"query": "publication active", "limit": 5}
                    )
                )
                return result.results[0].content_fingerprint


def _validate_v1_tool_schemas(tools: Mapping[str, object]) -> None:
    versions = {
        "list_libraries_v1": "mke.list_libraries_response.v1",
        "search_library_v1": "mke.search_library_response.v1",
        "ask_library_v1": "mke.ask_library_response.v1",
    }
    for name, version in versions.items():
        schema = getattr(tools.get(name), "outputSchema", None)
        rendered = json.dumps(schema, sort_keys=True)
        if not isinstance(schema, dict) or "oneOf" not in schema:
            raise ValueError("v1 output schema is not discriminated")
        if version not in rendered or '"additionalProperties": false' not in rendered:
            raise ValueError("v1 output schema is not strict")


def _list(payload: dict[str, object]) -> ListLibrariesSuccessV1:
    root = TypeAdapter(ListLibrariesResponseV1).validate_python(payload).root
    if not isinstance(root, ListLibrariesSuccessV1):
        raise ValueError("list observation failed")
    return root


def _search(payload: dict[str, object]) -> SearchLibrarySuccessV1:
    root = TypeAdapter(SearchLibraryResponseV1).validate_python(payload).root
    if not isinstance(root, SearchLibrarySuccessV1):
        raise ValueError("v1 Search failed")
    return root


def _ask(payload: dict[str, object]) -> AskLibrarySuccessV1:
    root = TypeAdapter(AskLibraryResponseV1).validate_python(payload).root
    if not isinstance(root, AskLibrarySuccessV1):
        raise ValueError("v1 Ask failed")
    return root


def _matching_projection(
    searched: SearchLibrarySuccessV1,
    asked: AskLibrarySuccessV1,
    locator_kind: str,
) -> EvidenceRefV1:
    if not searched.results or tuple(searched.results) != tuple(asked.evidence):
        raise ValueError("Search and Ask Evidence projection mismatch")
    result = searched.results[0]
    if result.locator.kind != locator_kind:
        raise ValueError("Evidence locator mismatch")
    return result
