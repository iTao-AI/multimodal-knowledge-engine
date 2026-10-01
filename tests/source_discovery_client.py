"""Native SDK consumer helpers; no project response construction or fabricated transport."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp import ClientSession


async def checked_call(
    session: ClientSession,
    tool: str,
    request: dict[str, Any],
    measurements: list[tuple[int, int]],
) -> dict[str, Any]:
    result = await session.call_tool(tool, {"request": request})
    assert not result.isError
    payload = result.structuredContent
    assert isinstance(payload, dict)
    canonical = len(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    )
    transport = len(result.model_dump_json(by_alias=True, exclude_none=True).encode())
    assert canonical <= 32768
    assert transport < 96 * 1024
    measurements.append((canonical, transport))
    text = next(item.text for item in result.content if item.type == "text")
    assert json.loads(text) == payload
    return payload


async def pages(
    session: ClientSession,
    tool: str,
    initial: dict[str, Any],
    measurements: list[tuple[int, int]],
) -> list[dict[str, Any]]:
    responses: list[dict[str, Any]] = []
    request = initial
    while True:
        response = await checked_call(session, tool, request, measurements)
        assert response["ok"] is True, response
        responses.append(response)
        selection = response["selection"]
        if selection["status"] == "complete":
            return responses
        assert selection["returned"] > 0
        request = {"cursor": selection["next_cursor"]}


async def exact_read(
    session: ClientSession,
    descriptor: dict[str, Any],
    measurements: list[tuple[int, int]],
) -> str:
    request = {"evidence_id": descriptor["evidence_id"], "max_bytes": 8}
    chunks: list[str] = []
    while True:
        response = await checked_call(session, "read_evidence_v1", request, measurements)
        assert response["ok"] is True, response
        assert response["evidence"] == descriptor
        assert response["content"]["offset_bytes"] == len("".join(chunks).encode())
        chunks.append(response["content"]["text"])
        if response["complete"]:
            break
        request = {"cursor": response["next_cursor"]}
    text = "".join(chunks)
    assert len(text.encode()) == descriptor["original_utf8_bytes"]
    assert (
        "sha256:" + hashlib.sha256(text.encode()).hexdigest() == descriptor["evidence_text_sha256"]
    )
    return text


async def discover_and_read(session: ClientSession) -> dict[str, Any]:
    measurements: list[tuple[int, int]] = []
    catalog = await pages(session, "list_sources_v1", {"page_size": 1}, measurements)
    sources = [source for response in catalog for source in response["sources"]]
    assert len({source["source_id"] for source in sources}) == len(sources)
    pdf = next(source for source in sources if source["display_name"] == "navigation.pdf")
    transcript = next(source for source in sources if source["display_name"] == "transcript.mp4")
    query = await checked_call(
        session,
        "search_library_v2",
        {"query": "lexicalneedle"},
        measurements,
    )
    assert query["ok"] is True and len(query["matches"]) == 1
    assert query["matches"][0]["evidence"]["locator"]["start"] == 1
    browse = await pages(
        session,
        "browse_source_evidence_v1",
        {
            "source_id": pdf["source_id"],
            "publication_id": pdf["publication_id"],
            "page_size": 1,
            "locator_range": {"kind": "page", "start": 2, "end": 3},
        },
        measurements,
    )
    entries = [entry for response in browse for entry in response["entries"]]
    assert [entry["evidence"]["locator"]["start"] for entry in entries] == [2, 3]
    assert browse[0]["source"]["coverage"]["extraction_mode"] == "pymupdf-text"
    assert await exact_read(session, entries[0]["evidence"], measurements) == (
        "navigation target page two"
    )
    times = await pages(
        session,
        "browse_source_evidence_v1",
        {
            "source_id": transcript["source_id"],
            "publication_id": transcript["publication_id"],
            "page_size": 1,
            "locator_range": {"kind": "timestamp_ms", "start": 500, "end": 1500},
        },
        measurements,
    )
    timestamp_entries = [entry for response in times for entry in response["entries"]]
    assert [entry["evidence"]["locator"] for entry in timestamp_entries] == [
        {"kind": "timestamp_ms", "start": 0, "end": 1000},
        {"kind": "timestamp_ms", "start": 1000, "end": 2000},
    ]
    assert await exact_read(session, timestamp_entries[0]["evidence"], measurements) == (
        "First stored transcript."
    )
    assert times[0]["source"]["coverage"]["report_status"] == "not_observed"
    # Real ingest of the same declared input replaces its active Publication.
    replacement = await session.call_tool("ingest_file", {"path": "navigation.pdf"})
    assert not replacement.isError
    catalog_token = catalog[0]["selection"]["next_cursor"]
    browse_token = browse[0]["selection"]["next_cursor"]
    for tool, cursor in (
        ("list_sources_v1", catalog_token),
        ("browse_source_evidence_v1", browse_token),
    ):
        stale = await checked_call(session, tool, {"cursor": cursor}, measurements)
        assert stale["ok"] is False and stale["problem"] == "cursor_expired"
    return {
        "status": "passed",
        "catalog_pages": len(catalog),
        "browse_pages": len(browse),
        "locators": ["page", "timestamp_ms"],
        "exact_read_verified": True,
        "query_excluded_page": True,
        "replacement_rejected": True,
        "max_canonical_model_bytes": max(size[0] for size in measurements),
        "max_sdk_result_bytes": max(size[1] for size in measurements),
    }
