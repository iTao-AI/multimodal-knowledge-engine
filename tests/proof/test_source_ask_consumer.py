from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pymupdf
import pytest
from mcp import ClientSession
from mcp.types import CallToolResult

from mke.retrieval.strategy import RetrievalStrategy
from scripts.mcp_context_completeness_consumer import tool_snapshot
from tests.proof.test_source_search_stdio import ingest_transcript
from tests.source_discovery_support import cli_payloads, native_cli

SCRIPT = Path("scripts/source_evidence_consumer.py").resolve()
CASES: tuple[tuple[RetrievalStrategy, str, str], ...] = (
    ("current", "needle", "needle"),
    ("numeric-grouping-v1", "needle 410000", "needle 410,000"),
    ("cjk-active-scan-overlap-v1", "needle", "needle"),
    ("mixed-cjk-fts-intent-v1", "needle", "needle"),
)


def ingest_pdf(root: Path, database: Path, name: str, texts: tuple[str, ...]) -> Path:
    path = root / name
    document = pymupdf.open()
    for text in texts:
        page = document.new_page()
        page.insert_text((72, 72), text)  # pyright: ignore[reportUnknownMemberType]
    document.save(path)  # pyright: ignore[reportUnknownMemberType]
    document.close()
    cli_payloads(native_cli(database, "ingest", str(path), "--json"))
    return path


def catalog(database: Path) -> list[dict[str, Any]]:
    return cli_payloads(native_cli(database, "sources", "list", "--json"))[0]["sources"]


def consume(
    database: Path,
    selected: dict[str, Any],
    question: str,
    strategy: RetrievalStrategy = "cjk-active-scan-overlap-v1",
    limit: int = 3,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--db",
            str(database),
            "--source-id",
            selected["source_id"],
            "--publication-id",
            selected["publication_id"],
            "--question",
            question,
            "--limit",
            str(limit),
            "--retrieval-strategy",
            strategy,
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


@pytest.mark.parametrize("strategy,question,text", CASES)
@pytest.mark.parametrize("kind", ["pdf", "timestamp"])
def test_actual_cli_ask_and_sdk_consumer_exclude_stronger_source(
    tmp_path: Path,
    strategy: RetrievalStrategy,
    question: str,
    text: str,
    kind: str,
) -> None:
    from scripts.source_evidence_consumer import RECEIPT_SCHEMA

    database = tmp_path / "library.sqlite"
    ingest = ingest_pdf if kind == "pdf" else ingest_transcript
    suffix = ".pdf" if kind == "pdf" else ".mp4"
    ingest(tmp_path, database, "target" + suffix, (text + " padding" * 30,) * 13)
    ingest(tmp_path, database, "other" + suffix, (text + " outsideonly",) * 20)
    sources = catalog(database)
    selected = next(source for source in sources if source["display_name"] == "target" + suffix)
    legacy = native_cli(database, "--retrieval-strategy", strategy, "ask", question)
    assert legacy.returncode == 0 and "outsideonly" in legacy.stdout
    cli = cli_payloads(
        native_cli(
            database,
            "--retrieval-strategy",
            strategy,
            "ask",
            question,
            "--source-id",
            selected["source_id"],
            "--publication-id",
            selected["publication_id"],
            "--limit",
            "3",
            "--json",
        )
    )[0]
    result = consume(database, selected, question, strategy)
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["schema_version"] == RECEIPT_SCHEMA and receipt["ok"] is True
    assert receipt["question"] == question and receipt["answer_status"] == "evidence_found"
    assert receipt["scope"] == cli["scope"]
    assert receipt["selection"] == cli["selection"]
    assert receipt["selection"]["status"] == "more_available"
    assert [entry["evidence"] for entry in receipt["references"]] == [
        entry["evidence"] for entry in cli["evidence"]
    ]
    for reference in receipt["references"]:
        assert reference["evidence"]["source_id"] == selected["source_id"]
        assert reference["evidence"]["locator"]["kind"] == (
            "page" if kind == "pdf" else "timestamp_ms"
        )
        assert reference["verified_utf8_bytes"] == reference["evidence"]["original_utf8_bytes"]
        assert reference["exact_text_sha256_verified"] is True
        assert reference["excerpt_window_verified"] is True
    assert "outsideonly" not in result.stdout and "next_cursor" not in result.stdout
    assert len(result.stdout.encode()) <= 32768
    assert receipt["limitations"] == cli["limitations"]


def test_actual_consumer_complete_and_zero_match_never_fall_back(tmp_path: Path) -> None:
    database = tmp_path / "library.sqlite"
    ingest_pdf(tmp_path, database, "target.pdf", ("needle selected",) * 2)
    ingest_pdf(tmp_path, database, "other.pdf", ("outsideonly needle",))
    selected = next(
        source for source in catalog(database) if source["display_name"] == "target.pdf"
    )
    complete = consume(database, selected, "needle")
    assert complete.returncode == 0, complete.stdout + complete.stderr
    receipt = json.loads(complete.stdout)
    assert len(receipt["references"]) == 2 and receipt["selection"]["status"] == "complete"
    empty = consume(database, selected, "outsideonly")
    assert empty.returncode == 0, empty.stdout + empty.stderr
    zero = json.loads(empty.stdout)
    assert zero["scope"] == receipt["scope"]
    assert zero["references"] == [] and zero["answer_status"] == "insufficient_evidence"
    assert zero["selection"]["next_step"] == "refine_question_in_selected_source"


def test_actual_consumer_rejects_mismatched_and_replaced_publication(tmp_path: Path) -> None:
    database = tmp_path / "library.sqlite"
    target = ingest_pdf(tmp_path, database, "target.pdf", ("needle selected",))
    ingest_pdf(tmp_path, database, "other.pdf", ("needle other",))
    sources = catalog(database)
    selected = next(source for source in sources if source["display_name"] == "target.pdf")
    other = next(source for source in sources if source["display_name"] == "other.pdf")
    mismatch = consume(database, {**selected, "publication_id": other["publication_id"]}, "needle")
    cli_payloads(native_cli(database, "ingest", str(target), "--json"))
    stale = consume(database, selected, "needle")
    for result in (mismatch, stale):
        assert result.returncode == 1, result.stdout + result.stderr
        assert json.loads(result.stdout)["ok"] is False
        assert "references" not in result.stdout and "Traceback" not in result.stderr


@pytest.mark.parametrize(
    "strategy,question",
    [
        ("cjk-active-scan-overlap-v1", "知识检索"),
        ("mixed-cjk-fts-intent-v1", "needle 知识检索"),
    ],
)
def test_actual_sdk_unicode_chunk_reads_and_fifteen_tool_inventory(
    tmp_path: Path,
    strategy: RetrievalStrategy,
    question: str,
) -> None:
    from scripts.source_evidence_consumer import consume_source_evidence, session_for

    database = tmp_path / "library.sqlite"
    ingest_transcript(tmp_path, database, "target.mp4", ('前🙂 知识检索 "needle" 尾',))
    selected = catalog(database)[0]

    async def workflow() -> None:
        async with session_for(database, strategy=strategy) as session:
            inventory = await session.list_tools()
            frozen = json.loads(
                Path("tests/fixtures/source-search-v1/mcp-tool-schemas.json").read_text()
            )
            assert len(inventory.tools) == 15
            assert {tool.name: tool_snapshot(tool) for tool in inventory.tools} == frozen["tools"]
            receipt = await consume_source_evidence(
                session,
                selected["source_id"],
                selected["publication_id"],
                question,
                max_read_bytes=4,
            )
            assert receipt["selection"]["status"] == "complete"
            assert receipt["references"][0]["excerpt_window_verified"] is True
            assert receipt["references"][0]["exact_text_sha256_verified"] is True

    asyncio.run(workflow())


@pytest.mark.parametrize("change_before", ["search_source_evidence_v1", "read_evidence_v1"])
def test_actual_sdk_publication_change_during_consumer_fails_closed(
    tmp_path: Path,
    change_before: str,
) -> None:
    from scripts.source_evidence_consumer import (
        ConsumerFailure,
        consume_source_evidence,
        session_for,
    )

    database = tmp_path / "library.sqlite"
    target = ingest_pdf(tmp_path, database, "target.pdf", ("needle selected",))
    selected = catalog(database)[0]

    async def workflow() -> None:
        async with session_for(database) as session:

            class ChangingSession:
                def __init__(self, native: ClientSession) -> None:
                    self.native = native
                    self.changed = False

                async def call_tool(
                    self,
                    name: str,
                    arguments: dict[str, Any] | None = None,
                ) -> CallToolResult:
                    if name == change_before and not self.changed:
                        self.changed = True
                        result = await self.native.call_tool("ingest_file", {"path": target.name})
                        assert result.structuredContent is not None
                        assert result.structuredContent["ok"] is True
                    return await self.native.call_tool(name, arguments)

            with pytest.raises(ConsumerFailure):
                await consume_source_evidence(
                    ChangingSession(session),
                    selected["source_id"],
                    selected["publication_id"],
                    "needle",
                )

    asyncio.run(workflow())
