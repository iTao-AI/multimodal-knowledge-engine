from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import pymupdf
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mke.interfaces.source_search_schemas import SearchSourceEvidenceResponseV1
from tests.proof.test_source_search_stdio import ingest_transcript, verify_matches
from tests.source_discovery_client import checked_call, pages
from tests.source_discovery_support import CLI, cli_payloads, native_cli


def test_real_pdf_source_search_matches_active_pages_and_cli(tmp_path: Path) -> None:
    database = tmp_path / "library.sqlite"
    pdf = tmp_path / "target.pdf"
    text = "needle padding padding padding"
    with pymupdf.open() as document:
        for _ in range(13):
            document.new_page().insert_text((72, 72), text)  # pyright: ignore[reportUnknownMemberType]
        document.save(pdf)  # pyright: ignore[reportUnknownMemberType]
    cli_payloads(native_cli(database, "ingest", str(pdf), "--json"))
    ingest_transcript(tmp_path, database, "distractor.mp4", ("needle outsideonly",) * 20)

    async def workflow() -> None:
        measurements: list[tuple[int, int]] = []
        async with stdio_client(
            StdioServerParameters(
                command=str(CLI),
                args=["--db", str(database), "mcp", "--allowed-root", str(tmp_path)],
            )
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                catalog = await pages(session, "list_sources_v1", {}, measurements)
                source = next(
                    s for p in catalog for s in p["sources"] if s["display_name"] == pdf.name
                )
                ids = {"source_id": source["source_id"], "publication_id": source["publication_id"]}
                responses = await pages(
                    session,
                    "search_source_evidence_v1",
                    {
                        **ids,
                        "query": "needle",
                        "limit": 3,
                    },
                    measurements,
                )
                browse = await pages(
                    session,
                    "browse_source_evidence_v1",
                    {
                        **ids,
                        "page_size": 20,
                    },
                    measurements,
                )
                active = {
                    e["evidence"]["evidence_id"]: e["evidence"]
                    for p in browse
                    for e in p["entries"]
                }
                await verify_matches(
                    session, responses, active, (text,) * 13, measurements, start=1, step=1
                )
                assert len(responses) == 5
                cli = cli_payloads(
                    native_cli(
                        database,
                        "search",
                        "needle",
                        "--source-id",
                        ids["source_id"],
                        "--publication-id",
                        ids["publication_id"],
                        "--limit",
                        "3",
                        "--json",
                    )
                )
                assert [m["evidence"] for p in cli for m in p["matches"]] == [
                    m["evidence"] for p in responses for m in p["matches"]
                ]
                print(
                    json.dumps(
                        {
                            "native_pdf_pages": 13,
                            "search_pages": 5,
                            "active_citations_and_exact_reads": "passed",
                        }
                    )
                )

    asyncio.run(workflow())


def test_ingested_unicode_scope_measures_full_envelope_and_makes_progress(tmp_path: Path) -> None:
    database = tmp_path / "library.sqlite"
    text = 'needle 三🙂"\n\\' * 1000
    ingest_transcript(tmp_path, database, "unicode.mp4", (text,) * 20)

    async def workflow() -> None:
        measurements: list[tuple[int, int]] = []
        async with stdio_client(
            StdioServerParameters(
                command=str(CLI),
                args=["--db", str(database), "mcp", "--allowed-root", str(tmp_path)],
            )
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                catalog = await pages(session, "list_sources_v1", {}, measurements)
                source = catalog[0]["sources"][0]
                ids = {"source_id": source["source_id"], "publication_id": source["publication_id"]}
                responses = await pages(
                    session,
                    "search_source_evidence_v1",
                    {
                        **ids,
                        "query": "needle",
                        "limit": 20,
                    },
                    measurements,
                )
                assert len(responses) > 1
                matches: list[dict[str, Any]] = []
                for page in responses:
                    SearchSourceEvidenceResponseV1.model_validate(page)
                    assert page["scope"] == responses[0]["scope"]
                    assert (
                        sum(m["excerpt"]["returned_utf8_bytes"] for m in page["matches"]) <= 16384
                    )
                    assert all(not m["excerpt"]["complete"] for m in page["matches"])
                    matches.extend(page["matches"])
                assert len(matches) == 20
                assert len({m["evidence"]["evidence_id"] for m in matches}) == 20
                for match in matches:
                    descriptor = match["evidence"]
                    request = {"evidence_id": descriptor["evidence_id"], "max_bytes": 16384}
                    chunks: list[str] = []
                    while True:
                        response = await checked_call(
                            session, "read_evidence_v1", request, measurements
                        )
                        assert response["ok"] is True and response["evidence"] == descriptor
                        assert response["content"]["offset_bytes"] == len("".join(chunks).encode())
                        chunks.append(response["content"]["text"])
                        if response["complete"]:
                            break
                        request = {"cursor": response["next_cursor"]}
                    restored = "".join(chunks)
                    assert restored == text
                    assert len(restored.encode()) == descriptor["original_utf8_bytes"]
                    assert descriptor["evidence_text_sha256"] == (
                        "sha256:" + hashlib.sha256(restored.encode()).hexdigest()
                    )
                print(
                    json.dumps(
                        {
                            "unicode_matches": 20,
                            "search_pages": len(responses),
                            "positive_progress": True,
                            "max_search_canonical_bytes": max(
                                len(
                                    json.dumps(
                                        p,
                                        ensure_ascii=False,
                                        separators=(",", ":"),
                                        sort_keys=True,
                                    ).encode()
                                )
                                for p in responses
                            ),
                            "max_canonical_model_bytes": max(m[0] for m in measurements),
                            "max_sdk_result_bytes": max(m[1] for m in measurements),
                        },
                        sort_keys=True,
                    )
                )

    asyncio.run(workflow())
