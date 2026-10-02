from __future__ import annotations

import asyncio
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from tests.source_discovery_support import CLI, create_library


def test_source_discovery_native_stdio_workflow(tmp_path: Path) -> None:
    database = create_library(tmp_path)

    async def workflow() -> None:
        async with stdio_client(
            StdioServerParameters(
                command=str(CLI),
                args=["--db", str(database), "mcp", "--allowed-root", str(tmp_path)],
            )
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                inventory = await session.list_tools()
                assert {"list_sources_v1", "browse_source_evidence_v1"} <= {
                    tool.name for tool in inventory.tools
                }, "native source tools missing"
                from tests.source_discovery_client import discover_and_read

                receipt = await discover_and_read(session)
                print(receipt)
                assert receipt["status"] == "passed"
                assert receipt["catalog_pages"] == 2
                assert receipt["browse_pages"] == 2
                assert receipt["locators"] == ["page", "timestamp_ms"]
                assert receipt["exact_read_verified"] is True
                assert receipt["query_excluded_page"] is True
                assert receipt["replacement_rejected"] is True

    asyncio.run(workflow())


def test_native_unicode_escape_and_metadata_response_budgets(tmp_path: Path) -> None:
    import json

    from tests.source_discovery_client import checked_call, pages
    from tests.source_discovery_support import publish_pages

    database = tmp_path / "mke.sqlite"
    preview_text = '三🙂"\n\\' * 1000
    assert "\n" in preview_text
    assert "\\" in preview_text
    assert '"' in preview_text and "三🙂" in preview_text
    source, publication = publish_pages(
        database,
        (preview_text,) * 20,
        name="目录" * 1200 + ".pdf",
    )

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
                responses = await pages(
                    session,
                    "browse_source_evidence_v1",
                    {
                        "source_id": source,
                        "publication_id": publication,
                        "page_size": 20,
                    },
                    measurements,
                )
                entries = [entry for page in responses for entry in page["entries"]]
                assert len(responses) > 1
                assert [entry["evidence"]["locator"]["start"] for entry in entries] == list(
                    range(1, 21)
                )
                assert max(item[0] for item in measurements) > 28000
                for raw in (
                    {
                        "source_id": source,
                        "publication_id": publication,
                        "locator_range": {
                            "kind": "page",
                            "start": True,
                            "end": 2,
                        },
                    },
                    {
                        "source_id": source,
                        "publication_id": publication,
                        "locator_range": {
                            "kind": "page",
                            "start": 1,
                            "end": 2,
                            "extra": 1,
                        },
                    },
                ):
                    result = await checked_call(
                        session, "browse_source_evidence_v1", raw, measurements
                    )
                    assert result["ok"] is False and result["problem"] == "invalid_request"
                print(
                    json.dumps(
                        {
                            "native_budget_canonical_max": max(item[0] for item in measurements),
                            "native_budget_sdk_max": max(item[1] for item in measurements),
                            "pages": len(responses),
                        },
                        sort_keys=True,
                    )
                )

    asyncio.run(workflow())


def test_native_browse_large_ranges_keep_original_authenticated_filter(tmp_path: Path) -> None:
    import base64
    import json

    from mke.application import KnowledgeEngine
    from mke.application.mcp_cursor import parse_cursor_untrusted
    from tests.adapters.test_sqlite_source_discovery import publish_boundary_locators
    from tests.source_discovery_client import checked_call, pages

    database = tmp_path / "mke.sqlite"
    maximum = 2**63 - 1
    engine = KnowledgeEngine(database)
    try:
        for kind in ("page", "timestamp_ms"):
            publish_boundary_locators(engine, kind)
    finally:
        engine.close()

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
                sources = catalog[0]["sources"]
                for kind in ("page", "timestamp_ms"):
                    source = next(
                        item
                        for item in sources
                        if item["display_name"]
                        == ("boundary.pdf" if kind == "page" else "boundary.mp4")
                    )
                    base = {
                        "source_id": source["source_id"],
                        "publication_id": source["publication_id"],
                        "page_size": 1,
                    }
                    for end in (maximum, maximum + 1, 10**100):
                        start = 1 if kind == "page" else 0
                        responses = await pages(
                            session,
                            "browse_source_evidence_v1",
                            {
                                **base,
                                "locator_range": {"kind": kind, "start": start, "end": end},
                            },
                            measurements,
                        )
                        assert len(responses) == 3
                        for response in responses[:-1]:
                            cursor = response["selection"]["next_cursor"]
                            payload = parse_cursor_untrusted(cursor).raw
                            assert payload["locator_kind"] == kind
                            assert payload["locator_start"] == start
                            assert payload["locator_end"] == end
                        if end == maximum + 1:
                            token = responses[0]["selection"]["next_cursor"]
                            envelope = json.loads(
                                base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
                            )
                            payload = parse_cursor_untrusted(token).raw
                            payload["locator_end"] = 10**100
                            envelope["payload"] = (
                                base64.urlsafe_b64encode(json.dumps(payload).encode())
                                .decode()
                                .rstrip("=")
                            )
                            forged = (
                                base64.urlsafe_b64encode(json.dumps(envelope).encode())
                                .decode()
                                .rstrip("=")
                            )
                            rejected = await checked_call(
                                session,
                                "browse_source_evidence_v1",
                                {"cursor": forged},
                                measurements,
                            )
                            assert rejected["problem"] == "invalid_cursor"
                        actual = [
                            entry["evidence"]["locator"]["start"]
                            for response in responses
                            for entry in response["entries"]
                        ]
                        assert actual == (
                            [1, maximum - 1, maximum]
                            if kind == "page"
                            else [0, maximum - 2, maximum - 1]
                        )
                    for start, end, expected in (
                        (maximum + 1, maximum + 2, []),
                        (10**100, 10**100 + 1, []),
                        (
                            maximum,
                            maximum if kind == "page" else maximum + 1,
                            [maximum] if kind == "page" else [],
                        ),
                    ):
                        responses = await pages(
                            session,
                            "browse_source_evidence_v1",
                            {
                                **base,
                                "locator_range": {"kind": kind, "start": start, "end": end},
                            },
                            measurements,
                        )
                        assert len(responses) == 1
                        assert responses[0]["selection"]["status"] == "complete"
                        assert [
                            entry["evidence"]["locator"]["start"]
                            for entry in responses[0]["entries"]
                        ] == expected

    asyncio.run(workflow())
