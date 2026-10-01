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
    source, publication = publish_pages(
        database,
        (
            '三🙂"\
'
            * 1000,
        )
        * 20,
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
