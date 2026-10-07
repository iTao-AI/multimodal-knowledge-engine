from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mke.interfaces.source_search_schemas import SearchSourceEvidenceResponseV1
from mke.retrieval.strategy import RetrievalStrategy
from scripts.mcp_context_completeness_consumer import tool_snapshot
from tests.source_discovery_client import checked_call, pages
from tests.source_discovery_support import CLI, cli_payloads, native_cli

CASES: tuple[tuple[RetrievalStrategy, str, str], ...] = (
    ("current", "needle", "needle"),
    ("numeric-grouping-v1", "needle 1000", "needle 1000"),
    ("cjk-active-scan-overlap-v1", "needle", "needle"),
    ("cjk-active-scan-overlap-v1", "知识检索范围", "知识检索范围"),
    ("mixed-cjk-fts-intent-v1", "知识检索范围", "知识检索范围"),
    ("mixed-cjk-fts-intent-v1", "needle 知识检索范围", "needle 知识检索范围"),
)


def ingest_transcript(root: Path, database: Path, name: str, texts: tuple[str, ...]) -> Path:
    """Declared synthetic MP4 identity and sidecar; no encoded-media or ASR claim."""
    path = root / name
    path.write_bytes(("public synthetic identity: " + name).encode())
    path.with_suffix(".mp4.mke-transcript.json").write_text(
        json.dumps(
            {
                "format": "mke.video_transcript.v1",
                "media": {
                    "container": "mp4",
                    "video_codec": "h264",
                    "audio_codec": "aac",
                    "has_audio": True,
                    "duration_ms": len(texts) * 100,
                },
                "segments": [
                    {"start_ms": i * 100, "end_ms": (i + 1) * 100, "text": text}
                    for i, text in enumerate(texts)
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    cli_payloads(native_cli(database, "ingest", str(path), "--json"))
    return path


async def verify_matches(
    session: ClientSession,
    responses: list[dict[str, Any]],
    active: dict[str, dict[str, Any]],
    expected: tuple[str, ...],
    measurements: list[tuple[int, int]],
    *,
    start: int = 0,
    step: int = 100,
) -> None:
    citations: list[dict[str, Any]] = []
    for response in responses:
        SearchSourceEvidenceResponseV1.model_validate(response)
        assert response["scope"] == responses[0]["scope"]
        assert response["authority_snapshot"] == responses[0]["authority_snapshot"]
        for match in response["matches"]:
            descriptor = match["evidence"]
            assert descriptor == active[descriptor["evidence_id"]]
            read = await checked_call(
                session,
                "read_evidence_v1",
                {
                    "evidence_id": descriptor["evidence_id"],
                    "max_bytes": 16384,
                },
                measurements,
            )
            assert read["ok"] is True and read["complete"] is True
            assert read["evidence"] == descriptor and read["content"]["offset_bytes"] == 0
            text = read["content"]["text"]
            assert text == expected[(descriptor["locator"]["start"] - start) // step]
            assert len(text.encode()) == descriptor["original_utf8_bytes"]
            assert descriptor["evidence_text_sha256"] == (
                "sha256:" + hashlib.sha256(text.encode()).hexdigest()
            )
            citations.append(descriptor)
    assert [d["locator"]["start"] for d in citations] == list(range(start, start + 13 * step, step))
    assert len({d["evidence_id"] for d in citations}) == 13


@pytest.mark.parametrize("strategy,query,text", CASES)
def test_actual_cli_ingest_search_and_native_scoped_search_all_strategies(
    tmp_path: Path,
    strategy: RetrievalStrategy,
    query: str,
    text: str,
) -> None:
    database = tmp_path / "library.sqlite"
    # The distractor has strictly higher CJK overlap; FTS sees shorter distractor documents.
    selected_text = text.replace("知识检索范围", "知识检索")
    texts = (selected_text + " padding" * 30,) * 13
    target = ingest_transcript(tmp_path, database, "target.mp4", texts)
    ingest_transcript(tmp_path, database, "distractor.mp4", (text + " outsideonly",) * 20)

    async def workflow() -> None:
        measurements: list[tuple[int, int]] = []
        async with stdio_client(
            StdioServerParameters(
                command=str(CLI),
                args=[
                    "--db",
                    str(database),
                    "--retrieval-strategy",
                    strategy,
                    "mcp",
                    "--allowed-root",
                    str(tmp_path),
                ],
            )
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                current = json.loads(
                    Path("tests/fixtures/source-search-v1/mcp-tool-schemas.json").read_text()
                )
                assert {tool.name: tool_snapshot(tool) for tool in listed.tools} == current["tools"]
                catalog = await pages(session, "list_sources_v1", {"page_size": 1}, measurements)
                sources = [s for page in catalog for s in page["sources"]]
                assert len(sources) == 2
                selected = next(s for s in sources if s["display_name"] == target.name)
                other = next(s for s in sources if s["display_name"] != target.name)
                initial = {
                    "source_id": selected["source_id"],
                    "publication_id": selected["publication_id"],
                    "query": query,
                    "limit": 3,
                }
                global_search = await checked_call(
                    session,
                    "search_library_v2",
                    {"query": query, "limit": 3},
                    measurements,
                )
                assert len(global_search["matches"]) == 3
                assert all(
                    m["evidence"]["source_id"] == other["source_id"]
                    for m in global_search["matches"]
                )
                responses = await pages(session, "search_source_evidence_v1", initial, measurements)
                assert len(responses) == 5 and responses[-1]["selection"]["status"] == "complete"
                browse = await pages(
                    session,
                    "browse_source_evidence_v1",
                    {
                        "source_id": selected["source_id"],
                        "publication_id": selected["publication_id"],
                        "page_size": 20,
                    },
                    measurements,
                )
                active = {
                    entry["evidence"]["evidence_id"]: entry["evidence"]
                    for page in browse
                    for entry in page["entries"]
                }
                await verify_matches(session, responses, active, texts, measurements)
                cli = cli_payloads(
                    native_cli(
                        database,
                        "--retrieval-strategy",
                        strategy,
                        "search",
                        query,
                        "--source-id",
                        selected["source_id"],
                        "--publication-id",
                        selected["publication_id"],
                        "--limit",
                        "3",
                        "--json",
                    )
                )
                assert len(cli) == 5
                assert [m["evidence"] for p in cli for m in p["matches"]] == [
                    m["evidence"] for p in responses for m in p["matches"]
                ]
                empty = await checked_call(
                    session,
                    "search_source_evidence_v1",
                    {
                        **initial,
                        "query": "outsideonly",
                    },
                    measurements,
                )
                assert empty["ok"] is True and empty["matches"] == []
                assert empty["scope"] == responses[0]["scope"]
                cursor = responses[0]["selection"]["next_cursor"]
                for request, problem in (
                    ({"cursor": cursor, "query": query}, "invalid_request"),
                    ({"cursor": global_search["selection"]["next_cursor"]}, "invalid_cursor"),
                    ({**initial, "publication_id": other["publication_id"]}, "evidence_not_found"),
                    ({**initial, "source_id": "src_unknown"}, "evidence_not_found"),
                ):
                    error = await checked_call(
                        session,
                        "search_source_evidence_v1",
                        request,
                        measurements,
                    )
                    SearchSourceEvidenceResponseV1.model_validate(error)
                    assert error["ok"] is False and error["problem"] == problem
                ingested = await session.call_tool("ingest_file", {"path": target.name})
                assert not ingested.isError and ingested.structuredContent is not None
                expired = await checked_call(
                    session,
                    "search_source_evidence_v1",
                    {"cursor": cursor},
                    measurements,
                )
                assert expired["problem"] == "cursor_expired"
                assert expired["next_step"] == "repeat_search_on_current_publications"
                stale = await checked_call(
                    session, "search_source_evidence_v1", initial, measurements
                )
                assert stale["problem"] == "evidence_not_found"
                updated = await pages(session, "list_sources_v1", {}, measurements)
                reselected = next(
                    s
                    for p in updated
                    for s in p["sources"]
                    if s["source_id"] == selected["source_id"]
                )
                assert reselected["publication_id"] != selected["publication_id"]
                renewed = await pages(
                    session,
                    "search_source_evidence_v1",
                    {
                        **initial,
                        "publication_id": reselected["publication_id"],
                    },
                    measurements,
                )
                active_pages = await pages(
                    session,
                    "browse_source_evidence_v1",
                    {
                        "source_id": reselected["source_id"],
                        "publication_id": reselected["publication_id"],
                        "page_size": 20,
                    },
                    measurements,
                )
                active = {
                    entry["evidence"]["evidence_id"]: entry["evidence"]
                    for p in active_pages
                    for entry in p["entries"]
                }
                await verify_matches(session, renewed, active, texts, measurements)
                print(
                    json.dumps(
                        {
                            "strategy": strategy,
                            "query_branch": "CJK" if "知识" in query else "FTS",
                            "source_matches": 13,
                            "pages": 5,
                            "native_exact_read": "passed",
                            "replacement_reselection": "passed",
                            "max_canonical_model_bytes": max(m[0] for m in measurements),
                            "max_sdk_result_bytes": max(m[1] for m in measurements),
                            "asr_execution": "not_performed",
                        },
                        sort_keys=True,
                    )
                )

    asyncio.run(workflow())
