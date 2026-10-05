#!/usr/bin/env python3
"""Provider-free CLI/MCP/export/Viewer proof over a declared six-page PDF.

Native public results own identity and content. No producer or storage imports.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pymupdf
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(_SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIRECTORY))

from compiled_library_export_consumer_v3 import load_validated_export  # noqa: E402
from source_discovery_consumer import (  # noqa: E402
    ConsumerFailure,
    call,
    canonical,
    check_entries,
    ingest,
    pages,
    read,
    require,
    verify_exact_read,
)

IDENTITY_FIELDS = (
    "source_id",
    "publication_id",
    "publication_revision",
    "run_id",
    "content_fingerprint",
)


def create_pdf(root: Path) -> tuple[Path, dict[int, str]]:
    """Raster value is deliberately absent from the PDF text layer; no OCR is run."""
    figure: Any = pymupdf.open()
    image_page = figure.new_page(width=240, height=70)
    image_page.insert_text((8, 24), "RASTER ONLY: value = 37", fontsize=13)
    image_page.draw_rect(pymupdf.Rect(8, 40, 180, 55), color=(0.1, 0.3, 0.7), fill=(0.1, 0.3, 0.7))
    raster = image_page.get_pixmap().tobytes("png")
    figure.close()
    expected = {
        1: "Ordinary text on page one.",
        2: "\n".join(f"Café Stored mixed line {i:03d}; consult the figure." for i in range(60)),
        3: "Text with a decorative raster on page three.",
    }
    document: Any = pymupdf.open()
    document.new_page().insert_text((40, 40), expected[1])
    page = document.new_page()
    for index, line in enumerate(expected[2].splitlines()):
        page.insert_text((40, 40 + 12 * index), line, fontsize=11)
    page.insert_image(pymupdf.Rect(400, 90, 580, 143), stream=raster)
    page = document.new_page()
    page.insert_text((40, 40), expected[3])
    page.insert_image(pymupdf.Rect(40, 60, 42, 62), stream=b"P6\n1 1\n255\n\x00\x00\x00")
    document.new_page().insert_image(pymupdf.Rect(40, 80, 280, 150), stream=raster)
    document.new_page()
    document.new_page().draw_rect(pymupdf.Rect(40, 40, 140, 140))
    path = root / "declared-mixed.pdf"
    document.save(path)
    document.close()
    return path, expected


def command(argv: list[str], root: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=30, check=False)
    require(result.returncode == 0, "native_command_failed")
    require(len(result.stdout.encode()) < 1024 * 1024, "command_output_exceeded")
    return result


def cli(command_path: Path, database: Path, root: Path, *args: str) -> list[dict[str, Any]]:
    result = command([str(command_path), "--db", str(database), *args, "--json"], root)
    payloads = [json.loads(line) for line in result.stdout.splitlines()]
    require(bool(payloads) and all(item.get("ok") is True for item in payloads), "cli_public_error")
    return payloads


async def discover(
    session: ClientSession,
    expected_tools: dict[str, Any],
    expected_text: dict[int, str],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, object]]:
    inventory = await asyncio.wait_for(session.list_tools(), timeout=15)
    actual = {}
    for tool in inventory.tools:
        dumped = tool.model_dump(by_alias=True, exclude_none=True)
        actual[tool.name] = {
            key: dumped.get(key)
            for key in ("inputSchema", "outputSchema", "description", "annotations")
        }
    require(actual == expected_tools and len(actual) == 14, "tool_inventory_mismatch")
    measurements: list[tuple[int, int]] = []
    catalog = await call(session, "list_sources_v2", {}, measurements)
    require(len(catalog["sources"]) == 1)
    source = catalog["sources"][0]
    summary = source["pdf_extraction_observation"]
    require(summary["pages"] == [] and summary["omitted_page_ranges"] == [{"start": 1, "end": 6}])
    request = {
        "source_id": source["source_id"],
        "publication_id": source["publication_id"],
        "page_size": 1,
    }
    browsed = await pages(session, "browse_source_evidence_v2", request, measurements)
    entries = [entry for response in browsed for entry in response["entries"]]
    check_entries(source, entries)
    require([entry["evidence"]["locator"]["start"] for entry in entries] == [1, 2, 3])
    detail = browsed[0]["source"]
    observation = detail["pdf_extraction_observation"]
    for response in browsed:
        require(response["source"] == detail, "producing_report_mismatch")
    for field, value in (
        ("total_pages", 6),
        ("text_only_pages", 1),
        ("mixed_text_raster_pages", 2),
        ("raster_only_pages", 1),
        ("neither_text_nor_raster_pages", 2),
    ):
        require(observation[field] == summary[field] == value, "declared_observation_mismatch")
    require(
        [page["has_raster_images"] for page in observation["pages"]]
        == [
            False,
            True,
            True,
            True,
            False,
            False,
        ]
    )
    require(detail["coverage"]["suspected_scanned_pages"] == 1)
    require(entries[1]["excerpt"]["complete"] is False, "preview_boundary_mismatch")
    chunks = 0
    for entry in entries:
        text, count = await read(session, entry["evidence"], measurements)
        require(
            text == expected_text[entry["evidence"]["locator"]["start"]], "declared_text_mismatch"
        )
        require("RASTER ONLY" not in text, "raster_text_was_inferred")
        chunks += count
    old = await pages(session, "browse_source_evidence_v1", request, measurements)
    require(
        entries == [entry for response in old for entry in response["entries"]], "legacy_changed"
    )
    require("pdf_extraction_observation" not in old[0]["source"], "legacy_shape_changed")
    return (
        detail,
        entries,
        {
            "tool_count": len(actual),
            "exact_read_chunks": chunks,
            "max_canonical_model_bytes": max(item[0] for item in measurements),
            "max_sdk_result_bytes": max(item[1] for item in measurements),
        },
    )


async def run(args: argparse.Namespace) -> dict[str, object]:
    root = args.work_dir.resolve()
    root.mkdir(parents=True, exist_ok=False)
    executable = args.mke_bin.resolve()
    database = root / "library.sqlite"
    pdf, expected = create_pdf(root)
    ingest(executable, database, pdf)
    catalog = cli(executable, database, root, "sources", "list", "--contract-version", "v2")
    selected = catalog[0]["sources"][0]
    browse_args = (
        "source",
        "browse",
        selected["source_id"],
        "--publication-id",
        selected["publication_id"],
        "--contract-version",
        "v2",
        "--page-size",
        "1",
    )
    cli_browse = cli(executable, database, root, *browse_args)
    parameters = StdioServerParameters(
        command=str(executable),
        args=["--db", str(database), "mcp", "--allowed-root", str(root)],
    )
    expectation = json.loads(args.expectation.read_text())
    async with stdio_client(parameters) as streams:
        async with ClientSession(*streams) as session:
            await asyncio.wait_for(session.initialize(), timeout=15)
            source, entries, measurements = await discover(session, expectation["tools"], expected)
    require(cli_browse[0]["source"] == source, "cli_mcp_source_mismatch")
    require([entry for response in cli_browse for entry in response["entries"]] == entries)
    cli_read = cli(
        executable,
        database,
        root,
        "evidence",
        "read",
        entries[1]["evidence"]["evidence_id"],
        "--max-bytes",
        "97",
    )
    require(verify_exact_read(entries[1]["evidence"], cli_read) == expected[2])
    exported = cli(
        executable,
        database,
        root,
        "library",
        "export",
        "--output",
        "compiled-v3",
        "--format-version",
        "v3",
    )
    require(exported[0]["schema_version"] == "mke.compiled_library_export_response.v3")
    directory = root / "compiled-v3"
    snapshot = load_validated_export(directory)
    require(len(snapshot.sources) == 1)
    exported_source = snapshot.sources[0]
    for field in (*IDENTITY_FIELDS, "extractor_fingerprint"):
        require(exported_source.descriptor[field] == source[field], "export_identity_mismatch")
    require(
        exported_source.descriptor["pdf_extraction_observation"]
        == source["pdf_extraction_observation"]
    )
    for row, entry in zip(exported_source.evidence, entries, strict=True):
        descriptor = entry["evidence"]
        for field in (*IDENTITY_FIELDS, "evidence_id", "locator"):
            require(row[field] == descriptor[field], "export_citation_mismatch")
        data = str(row["text"]).encode("utf-8")
        require(row["text"] == expected[descriptor["locator"]["start"]])
        require(len(data) == descriptor["original_utf8_bytes"])
        require("sha256:" + hashlib.sha256(data).hexdigest() == descriptor["evidence_text_sha256"])
    viewer = root / "viewer.html"
    command(
        [
            sys.executable,
            "-I",
            "-B",
            str(_SCRIPT_DIRECTORY / "build_compiled_library_viewer.py"),
            "--export",
            str(directory),
            "--output",
            str(viewer),
        ],
        root,
    )
    html = viewer.read_text()
    marker = '<script type="application/json" id="viewer-data">'
    data = json.loads(html.split(marker, 1)[1].split("</script>", 1)[0])
    require(data["export_schema"] == "mke.compiled_library_export.v3")
    viewed = data["sources"][0]
    for field in IDENTITY_FIELDS:
        require(viewed[field] == source[field], "viewer_identity_mismatch")
    require(viewed["pdf_extraction_observation"] == source["pdf_extraction_observation"])
    require(viewed["evidence"] == list(exported_source.evidence), "viewer_text_mismatch")
    return {
        "schema_version": "mke.pdf_extraction_observation_consumer.v1",
        "status": "passed",
        **measurements,
        "identity": {field: source[field] for field in IDENTITY_FIELDS},
        "pdf_extraction_observation": source["pdf_extraction_observation"],
        "evidence_pages": [1, 2, 3],
        "legacy_entries_unchanged": True,
        "cli_mcp_export_viewer_identity_verified": True,
        "exact_utf8_verified": True,
        "raster_only_text_absent": True,
        "viewer": {"source_count": data["source_count"], "evidence_count": data["evidence_count"]},
        "ocr_execution": "not_performed",
        "original_media_semantic_coverage": "not_evaluated",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mke-bin", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--expectation", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = asyncio.run(run(args))
    except ConsumerFailure as error:
        receipt = {"status": "failed", "code": str(error)}
    except Exception:
        receipt = {"status": "failed", "code": "example_failed"}
    print(canonical(receipt).decode("utf-8"))
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
