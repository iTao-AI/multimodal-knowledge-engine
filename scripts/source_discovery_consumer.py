#!/usr/bin/env python3
"""Standalone public synthetic Source discovery example over CLI and official MCP SDK.

No MKE implementation/storage imports: native results are the only Evidence authority.
The generated image-only PDF page and declared video sidecar are synthetic inputs.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import struct
import subprocess
import zlib
from pathlib import Path
from typing import Any

import pymupdf
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult

CANONICAL_LIMIT = 32768
SDK_LIMIT = 96 * 1024


class ConsumerFailure(RuntimeError):
    """Bounded example failure; native/private details must not enter the receipt."""


def require(condition: bool, code: str = "consumer_verification_failed") -> None:
    if not condition:
        raise ConsumerFailure(code)


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def verify_exact_read(descriptor: dict[str, Any], chunks: list[dict[str, Any]]) -> str:
    """Independently check every chunk's full lineage, UTF-8 offsets and final digest."""
    require(bool(chunks))
    parts: list[str] = []
    offset = 0
    for index, response in enumerate(chunks):
        require(
            response["ok"] is True and response["evidence"] == descriptor,
            "citation_provenance_mismatch",
        )
        content = response["content"]
        data = content["text"].encode("utf-8")
        require(
            content["offset_bytes"] == offset
            and content["returned_utf8_bytes"] == len(data)
            and len(data) > 0,
            "utf8_chunk_mismatch",
        )
        terminal = index == len(chunks) - 1
        require(response["complete"] is terminal, "read_terminality_mismatch")
        require(
            (response.get("next_cursor") is None)
            if terminal
            else isinstance(response.get("next_cursor"), str) and bool(response["next_cursor"]),
            "read_terminality_mismatch",
        )
        parts.append(content["text"])
        offset += len(data)
    text = "".join(parts)
    require(offset == descriptor["original_utf8_bytes"], "utf8_size_mismatch")
    require(
        "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
        == descriptor["evidence_text_sha256"],
        "evidence_digest_mismatch",
    )
    return text


def synthetic_image() -> bytes:
    """Small declared raster checkerboard; contains no hidden/extracted text."""
    size = 64
    raw = b"".join(
        b"\0" + bytes(0 if (x // 8 + y // 8) % 2 else 255 for x in range(size)) for y in range(size)
    )

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack("!IIBBBBB", size, size, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def create_inputs(root: Path) -> tuple[Path, Path, str]:
    pdf = root / "mixed-navigation.pdf"
    document: Any = pymupdf.open()
    document.new_page().insert_text((40, 40), "lexicalneedle only on page one")
    page = document.new_page()
    lines = [f"Café résumé stored evidence line {index:03d}." for index in range(60)]
    for index, line in enumerate(lines):
        page.insert_text((40, 40 + 12 * index), line, fontsize=11, fontname="helv")
    document.new_page().insert_image(pymupdf.Rect(40, 40, 240, 240), stream=synthetic_image())
    document.new_page().insert_text((40, 40), "Final stored Evidence on page four.")
    document.save(pdf)
    document.close()
    video = root / "declared-transcript.mp4"
    video.write_bytes(b"public synthetic sidecar identity fixture; no encoded media or ASR")
    video.with_suffix(".mp4.mke-transcript.json").write_bytes(
        canonical(
            {
                "format": "mke.video_transcript.v1",
                "media": {
                    "container": "mp4",
                    "video_codec": "h264",
                    "audio_codec": "aac",
                    "has_audio": True,
                    "duration_ms": 3000,
                },
                "segments": [
                    {
                        "start_ms": index * 1000,
                        "end_ms": (index + 1) * 1000,
                        "text": f"Stored synthetic transcript {index + 1}.",
                    }
                    for index in range(3)
                ],
            }
        )
    )
    return pdf, video, "\n".join(lines)


def ingest(command: Path, database: Path, source: Path) -> None:
    result = subprocess.run(
        [str(command), "--db", str(database), "ingest", str(source), "--json"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    require(result.returncode == 0, "cli_ingest_failed")
    payload = json.loads(result.stdout)
    require(payload.get("ok") is True, "cli_ingest_failed")


def checked_result(result: CallToolResult, measurements: list[tuple[int, int]]) -> dict[str, Any]:
    require(not result.isError, "mcp_tool_failed")
    value = result.structuredContent
    require(isinstance(value, dict), "structured_result_missing")
    assert isinstance(value, dict)
    require(
        len(result.content) == 1 and result.content[0].type == "text", "compatibility_text_missing"
    )
    text = result.content[0]
    assert text.type == "text"
    require(json.loads(text.text) == value, "structured_text_mismatch")
    sizes = (
        len(canonical(value)),
        len(result.model_dump_json(by_alias=True, exclude_none=True).encode()),
    )
    require(sizes[0] <= CANONICAL_LIMIT and sizes[1] < SDK_LIMIT, "response_budget_exceeded")
    measurements.append(sizes)
    return value


async def call(
    session: ClientSession, tool: str, request: dict[str, Any], measurements: list[tuple[int, int]]
) -> dict[str, Any]:
    result = await asyncio.wait_for(session.call_tool(tool, {"request": request}), timeout=20)
    response = checked_result(result, measurements)
    require(response.get("ok") is True, "native_public_error")
    return response


async def pages(
    session: ClientSession, tool: str, request: dict[str, Any], measurements: list[tuple[int, int]]
) -> list[dict[str, Any]]:
    responses: list[dict[str, Any]] = []
    fingerprint = None
    cursors: set[str] = set()
    for _ in range(100):
        response = await call(session, tool, request, measurements)
        authority = response["authority_snapshot"]["active_set_fingerprint"]
        require(fingerprint is None or fingerprint == authority, "active_authority_changed")
        fingerprint = authority
        responses.append(response)
        selection = response["selection"]
        if selection["status"] == "complete":
            return responses
        require(selection["status"] == "more_available" and selection["returned"] > 0)
        cursor = selection["next_cursor"]
        require(cursor not in cursors, "continuation_did_not_progress")
        cursors.add(cursor)
        request = {"cursor": cursor}
    raise ConsumerFailure("continuation_limit_exceeded")


async def read(
    session: ClientSession, descriptor: dict[str, Any], measurements: list[tuple[int, int]]
) -> tuple[str, int]:
    request = {"evidence_id": descriptor["evidence_id"], "max_bytes": 97}
    chunks: list[dict[str, Any]] = []
    for _ in range(100):
        response = await call(session, "read_evidence_v1", request, measurements)
        chunks.append(response)
        if response["complete"]:
            return verify_exact_read(descriptor, chunks), len(chunks)
        request = {"cursor": response["next_cursor"]}
    raise ConsumerFailure("read_limit_exceeded")


def check_entries(source: dict[str, Any], entries: list[dict[str, Any]]) -> None:
    identities = [entry["evidence"]["evidence_id"] for entry in entries]
    require(len(identities) == len(set(identities)), "duplicate_evidence")
    ordering = [
        (
            entry["evidence"]["locator"]["start"],
            entry["evidence"]["locator"]["end"],
            entry["evidence"]["evidence_id"],
        )
        for entry in entries
    ]
    require(ordering == sorted(ordering), "locator_order_mismatch")
    for entry in entries:
        descriptor = entry["evidence"]
        for field in (
            "source_id",
            "publication_id",
            "publication_revision",
            "run_id",
            "content_fingerprint",
        ):
            require(descriptor[field] == source[field], "citation_provenance_mismatch")
        require(
            entry["read"]["evidence_id"] == descriptor["evidence_id"], "read_affordance_mismatch"
        )
        require(entry["excerpt"]["content_trust"] == "untrusted_evidence")


async def discover(
    session: ClientSession, expected_tools: dict[str, Any], expected_pdf_text: str
) -> dict[str, object]:
    inventory = await session.list_tools()
    actual: dict[str, dict[str, Any]] = {}
    for tool in inventory.tools:
        dumped = tool.model_dump(by_alias=True, exclude_none=True)
        actual[tool.name] = {
            key: dumped.get(key)
            for key in ("inputSchema", "outputSchema", "description", "annotations")
        }
    require(actual == expected_tools and len(actual) == 14, "tool_inventory_mismatch")
    measurements: list[tuple[int, int]] = []
    catalog = await pages(session, "list_sources_v1", {"page_size": 1}, measurements)
    sources = [source for response in catalog for source in response["sources"]]
    require(len(sources) == 2 and len({source["source_id"] for source in sources}) == 2)
    pdf = next(source for source in sources if source["display_name"] == "mixed-navigation.pdf")
    transcript = next(
        source for source in sources if source["display_name"] == "declared-transcript.mp4"
    )
    summary = pdf["coverage"]
    require(
        summary["report_status"] == "observed"
        and summary["page_char_counts"] == []
        and summary["page_char_counts_omitted"] is True
        and summary["page_char_counts_total"] == 4
    )
    query = await call(session, "search_library_v2", {"query": "lexicalneedle"}, measurements)
    require(
        len(query["matches"]) == 1
        and query["matches"][0]["evidence"]["source_id"] == pdf["source_id"]
        and query["matches"][0]["evidence"]["locator"] == {"kind": "page", "start": 1, "end": 1},
        "declared_query_boundary_mismatch",
    )
    browsed = await pages(
        session,
        "browse_source_evidence_v1",
        {
            "source_id": pdf["source_id"],
            "publication_id": pdf["publication_id"],
            "page_size": 1,
            "locator_range": {"kind": "page", "start": 2, "end": 4},
        },
        measurements,
    )
    entries = [entry for response in browsed for entry in response["entries"]]
    check_entries(pdf, entries)
    require([entry["evidence"]["locator"]["start"] for entry in entries] == [2, 4])
    coverage = browsed[0]["source"]["coverage"]
    require(
        coverage["extraction_mode"] == "pymupdf-text"
        and coverage["total_pages"] == 4
        and coverage["extracted_pages"] == 3
        and coverage["empty_pages"] == 1
        and coverage["suspected_scanned_pages"] == 1
        and coverage["page_char_counts"][2] == 0
        and coverage["page_char_counts_omitted"] is False
        and len(coverage["page_char_counts"]) == 4
    )
    for field in (
        "extraction_mode",
        "total_pages",
        "extracted_pages",
        "empty_pages",
        "suspected_scanned_pages",
        "total_extracted_chars",
        "page_char_counts_total",
    ):
        require(coverage[field] == summary[field], "producing_report_mismatch")
    require(
        entries[0]["excerpt"]["complete"] is False
        and entries[0]["excerpt"]["suffix_omitted"] is True,
        "preview_boundary_mismatch",
    )
    pdf_text, read_chunks = await read(session, entries[0]["evidence"], measurements)
    require(pdf_text == expected_pdf_text, "declared_pdf_text_mismatch")
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
    time_entries = [entry for response in times for entry in response["entries"]]
    check_entries(transcript, time_entries)
    require(
        [entry["evidence"]["locator"] for entry in time_entries]
        == [
            {"kind": "timestamp_ms", "start": 0, "end": 1000},
            {"kind": "timestamp_ms", "start": 1000, "end": 2000},
        ]
    )
    report = times[0]["source"]["coverage"]
    require(
        report["evidence_kind"] == "stored_transcript"
        and report["report_status"] == "not_observed"
        and report["provenance"] is None
    )
    for index, entry in enumerate(time_entries):
        text, _ = await read(session, entry["evidence"], measurements)
        require(text == f"Stored synthetic transcript {index + 1}.")
    return {
        "schema_version": "mke.source_discovery_consumer.v1",
        "status": "passed",
        "tool_count": len(actual),
        "catalog_pages": len(catalog),
        "pdf": {
            "coverage": coverage,
            "catalog_counts_omitted": summary["page_char_counts_omitted"],
            "browse_pages": len(browsed),
            "locators": [2, 4],
            "query_excluded_page": True,
            "preview_complete": entries[0]["excerpt"]["complete"],
            "read_chunks": read_chunks,
            "citation": entries[0]["evidence"],
        },
        "transcript": {
            "report_status": report["report_status"],
            "browse_pages": len(times),
            "locators": [[0, 1000], [1000, 2000]],
            "citations": [entry["evidence"] for entry in time_entries],
        },
        "exact_utf8_and_citation_verified": True,
        "structured_text_equal": True,
        "max_canonical_model_bytes": max(item[0] for item in measurements),
        "max_sdk_result_bytes": max(item[1] for item in measurements),
        "asr_execution": "not_performed",
        "ocr_execution": "not_performed",
        "original_media_semantic_coverage": "not_evaluated",
    }


async def run(args: argparse.Namespace) -> dict[str, object]:
    root: Path = args.work_dir.resolve()
    root.mkdir(parents=True, exist_ok=False)
    command: Path = args.mke_bin.resolve()
    pdf, video, expected_pdf_text = create_inputs(root)
    database = root / "library.sqlite"
    for source in (pdf, video):
        ingest(command, database, source)
    expectation = json.loads(args.expectation.read_text(encoding="utf-8"))
    parameters = StdioServerParameters(
        command=str(command), args=["--db", str(database), "mcp", "--allowed-root", str(root)]
    )
    async with stdio_client(parameters) as streams:
        async with ClientSession(*streams) as session:
            await asyncio.wait_for(session.initialize(), timeout=15)
            return await discover(session, expectation["tools"], expected_pdf_text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mke-bin", type=Path, required=True)
    parser.add_argument(
        "--work-dir", type=Path, required=True, help="new directory for synthetic inputs"
    )
    parser.add_argument(
        "--expectation",
        type=Path,
        default=Path("tests/fixtures/pdf-extraction-observation-v1/mcp-tool-schemas.json"),
    )
    args = parser.parse_args()
    try:
        receipt = asyncio.run(run(args))
    except ConsumerFailure as error:
        print(json.dumps({"status": "failed", "code": str(error)}))
        return 1
    except Exception:
        print(json.dumps({"status": "failed", "code": "example_failed"}))
        return 1
    print(canonical(receipt).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
