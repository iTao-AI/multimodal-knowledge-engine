"""Public-safe local knowledge proof over the real stdio MCP transport."""

from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
from collections.abc import Mapping
from datetime import timedelta
from pathlib import Path
from typing import cast

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mke.proof.mcp_deployment_client import assert_public_tool_schemas, tool_payload

_FIXTURE_PACK = Path("tests/fixtures/local-knowledge-v1")
_TIMEOUT_SECONDS = 60.0


def render_local_knowledge_report(report: Mapping[str, object]) -> str:
    return json.dumps(dict(report), sort_keys=True)


def run_local_knowledge_proof(
    *,
    repo_root: Path,
    mke_executable: Path,
) -> dict[str, object]:
    root = repo_root.resolve()
    executable = mke_executable.resolve()
    fixture_root = root / _FIXTURE_PACK
    manifest = _load_manifest(fixture_root)
    if not executable.is_file():
        raise ValueError("MKE executable is unavailable")

    with tempfile.TemporaryDirectory(prefix="mke-local-knowledge-") as directory:
        database = Path(directory) / "mke.sqlite"
        server = StdioServerParameters(
            command=str(executable),
            args=[
                "--db",
                str(database),
                "mcp",
                "--allowed-root",
                str(fixture_root),
            ],
            cwd=root,
        )
        return asyncio.run(_run_mcp_proof(server, manifest))


async def _run_mcp_proof(
    server: StdioServerParameters,
    manifest: Mapping[str, object],
) -> dict[str, object]:
    files = _manifest_files(manifest)
    queries = _manifest_queries(manifest)
    published_runs = 0
    published_evidence = 0
    timeout = timedelta(seconds=_TIMEOUT_SECONDS)

    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as errlog:
        async with stdio_client(server, errlog=errlog) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timeout) as session:
                await session.initialize()
                listed = await session.list_tools()
                assert_public_tool_schemas(listed.tools)

                for item in files:
                    name = _required_string(item, "name")
                    ingest = tool_payload(
                        await session.call_tool("ingest_file", {"path": name})
                    )
                    if ingest.get("ok") is not True or ingest.get("run_state") != "published":
                        raise ValueError("MCP ingest did not publish")
                    evidence_count = ingest.get("evidence_count")
                    if type(evidence_count) is not int or evidence_count <= 0:
                        raise ValueError("MCP ingest Evidence count is invalid")
                    run_id = _required_string(ingest, "run_id")
                    inspected = tool_payload(
                        await session.call_tool("get_run", {"run_id": run_id})
                    )
                    _validate_run(inspected, run_id)
                    published_runs += 1
                    published_evidence += evidence_count

                searched = tool_payload(
                    await session.call_tool(
                        "search_library",
                        {"query": queries["search"], "limit": 5},
                    )
                )
                search_results = _page_evidence(searched, field="results")
                if len(search_results) != 1:
                    raise ValueError("MCP Search result count mismatch")

                asked = tool_payload(
                    await session.call_tool(
                        "ask_library",
                        {"question": queries["answer"], "limit": 5},
                    )
                )
                answer_evidence = _answer_evidence(asked, expected_status="evidence_found")
                if len(answer_evidence) != 1:
                    raise ValueError("MCP Ask citation count mismatch")

                refused = tool_payload(
                    await session.call_tool(
                        "ask_library",
                        {"question": queries["refusal"], "limit": 5},
                    )
                )
                refusal_evidence = _answer_evidence(
                    refused,
                    expected_status="insufficient_evidence",
                )
                if refusal_evidence:
                    raise ValueError("MCP refusal returned Evidence")

    return {
        "proof": "local_knowledge",
        "status": "passed",
        "fixtures": len(files),
        "runs": {"published": published_runs},
        "evidence": {"published": published_evidence, "locator": "page"},
        "search": {"status": "evidence_found", "results": len(search_results)},
        "ask": {"status": "evidence_found", "citations": len(answer_evidence)},
        "refusal": {
            "status": "insufficient_evidence",
            "citations": len(refusal_evidence),
        },
    }


def _load_manifest(fixture_root: Path) -> dict[str, object]:
    raw = json.loads((fixture_root / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("fixture manifest is invalid")
    manifest = cast(dict[str, object], raw)
    if manifest.get("format") != "mke.local_knowledge_fixture.v1":
        raise ValueError("fixture manifest format is invalid")
    for item in _manifest_files(manifest):
        name = _required_string(item, "name")
        expected_bytes = item.get("bytes")
        expected_sha256 = item.get("sha256")
        path = fixture_root / name
        content = path.read_bytes()
        if (
            type(expected_bytes) is not int
            or len(content) != expected_bytes
            or not isinstance(expected_sha256, str)
            or hashlib.sha256(content).hexdigest() != expected_sha256
        ):
            raise ValueError("fixture identity mismatch")
    _manifest_queries(manifest)
    return manifest


def _manifest_files(manifest: Mapping[str, object]) -> list[dict[str, object]]:
    raw_files = manifest.get("files")
    if not isinstance(raw_files, list):
        raise ValueError("fixture manifest files are invalid")
    files = cast(list[object], raw_files)
    if len(files) != 2:
        raise ValueError("fixture manifest files are invalid")
    if not all(isinstance(item, dict) for item in files):
        raise ValueError("fixture manifest file entry is invalid")
    return cast(list[dict[str, object]], files)


def _manifest_queries(manifest: Mapping[str, object]) -> dict[str, str]:
    raw_queries = manifest.get("queries")
    if not isinstance(raw_queries, dict):
        raise ValueError("fixture manifest queries are invalid")
    queries = cast(dict[str, object], raw_queries)
    if set(queries) != {"search", "answer", "refusal"}:
        raise ValueError("fixture manifest queries are invalid")
    if not all(isinstance(value, str) and value for value in queries.values()):
        raise ValueError("fixture manifest query is invalid")
    return cast(dict[str, str], queries)


def _validate_run(payload: Mapping[str, object], expected_run_id: str) -> None:
    raw_run = payload.get("run")
    raw_events = payload.get("events")
    if payload.get("ok") is not True or not isinstance(raw_run, dict):
        raise ValueError("MCP Run inspection failed")
    run = cast(Mapping[str, object], raw_run)
    if run.get("run_id") != expected_run_id or run.get("state") != "published":
        raise ValueError("MCP Run state mismatch")
    if not isinstance(raw_events, list) or not raw_events:
        raise ValueError("MCP Run events are missing")


def _page_evidence(
    payload: Mapping[str, object],
    *,
    field: str,
) -> list[dict[str, object]]:
    raw_evidence = payload.get(field)
    if payload.get("ok") is not True or not isinstance(raw_evidence, list):
        raise ValueError("MCP Evidence payload is invalid")
    evidence = cast(list[object], raw_evidence)
    if not all(_is_page_evidence(item) for item in evidence):
        raise ValueError("MCP page Evidence is invalid")
    return cast(list[dict[str, object]], evidence)


def _answer_evidence(
    payload: Mapping[str, object],
    *,
    expected_status: str,
) -> list[dict[str, object]]:
    if payload.get("answer_status") != expected_status:
        raise ValueError("MCP Ask status mismatch")
    return _page_evidence(payload, field="evidence")


def _is_page_evidence(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    evidence = cast(Mapping[str, object], value)
    raw_locator = evidence.get("locator")
    if not isinstance(raw_locator, dict):
        return False
    locator = cast(Mapping[str, object], raw_locator)
    return (
        all(
            isinstance(evidence.get(field), str) and evidence.get(field)
            for field in ("evidence_id", "publication_id", "source_id", "text")
        )
        and locator.get("kind") == "page"
        and type(locator.get("start")) is int
        and type(locator.get("end")) is int
    )


def _required_string(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError("required identifier is missing")
    return value
