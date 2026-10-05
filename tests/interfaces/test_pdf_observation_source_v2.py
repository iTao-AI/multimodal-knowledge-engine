from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pymupdf
import pytest
from pydantic import ValidationError

from mke.application import KnowledgeEngine
from mke.interfaces import source_discovery, source_schemas
from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.runtime import RuntimeConfig
from tests.source_discovery_support import cli_payloads, native_cli, publish_pages


def observed_pdf(path: Path, *, pages: int = 6) -> None:
    doc: Any = pymupdf.open()
    for number in range(1, pages + 1):
        page: Any = doc.new_page()
        if pages != 6 or number <= 3:
            page.insert_text((72, 72), f"text on page {number}")
        if number in ((2, 3, 4) if pages == 6 else (290,)):
            side = 2 if number == 3 else 40
            page.insert_image(pymupdf.Rect(72, 100, 72 + side, 100 + side),
                              stream=b"P6\n1 1\n255\n\x00\x00\x00")
        if pages == 6 and number == 6:
            page.draw_rect(pymupdf.Rect(72, 72, 120, 120))
    doc.save(path)
    doc.close()


def library(root: Path, pages: int = 6) -> McpRuntimeConfig:
    pdf = root / "observed.pdf"
    observed_pdf(pdf, pages=pages)
    database = root / "mke.sqlite"
    engine = KnowledgeEngine(database)
    try:
        engine.ingest_pdf(pdf)
    finally:
        engine.close()
    return McpRuntimeConfig(RuntimeConfig(database), root)


def call(config: McpRuntimeConfig, tool: str, raw: object) -> dict[str, Any]:
    request = (source_schemas.ListSourcesV1Request if tool.startswith("list")
               else source_schemas.BrowseSourceEvidenceV1Request)(root=raw)
    return getattr(source_discovery, tool)(config, request).model_dump(mode="json")


def selected(config: McpRuntimeConfig) -> dict[str, Any]:
    result = call(config, "list_sources_v2", {})
    assert result["ok"], result
    return result["sources"][0]


def browse(config: McpRuntimeConfig, source: dict[str, Any], **extra: Any) -> dict[str, Any]:
    result = call(config, "browse_source_evidence_v2", {
        "source_id": source["source_id"], "publication_id": source["publication_id"], **extra,
    })
    assert result["ok"], result
    return result


def test_v2_catalog_and_browse_disclose_local_signals_without_changing_v1(tmp_path: Path) -> None:
    config = library(tmp_path)
    source = selected(config)
    observation = source["pdf_extraction_observation"]
    assert observation["status"] == "observed"
    assert [observation[key] for key in (
        "total_pages", "text_only_pages", "mixed_text_raster_pages", "raster_only_pages",
        "neither_text_nor_raster_pages",
    )] == [6, 1, 2, 1, 2]
    assert observation["pages"] == [] and observation["returned_page_range"] is None
    assert observation["omitted_page_ranges"] == [{"start": 1, "end": 6}]
    result = browse(config, source)
    detail = result["source"]["pdf_extraction_observation"]
    assert [item["has_raster_images"] for item in detail["pages"]] == [
        False, True, True, True, False, False,
    ]
    assert detail["returned_page_range"] == {"start": 1, "end": 6}
    assert detail["omitted_page_ranges"] == []
    old = call(config, "list_sources_v1", {})["sources"][0]
    assert "pdf_extraction_observation" not in old
    source_schemas.SourceMetadataV1.model_validate(old)
    assert old["coverage"]["suspected_scanned_pages"] == 1
    old_browse = call(config, "browse_source_evidence_v1", {
        "source_id": source["source_id"], "publication_id": source["publication_id"],
    })
    assert result["entries"] == old_browse["entries"]


def test_old_publication_is_not_observed_not_zero(tmp_path: Path) -> None:
    database = tmp_path / "mke.sqlite"
    publish_pages(database, ("ordinary stored text",))
    source = selected(McpRuntimeConfig(RuntimeConfig(database), tmp_path))
    observation = source["pdf_extraction_observation"]
    assert observation["status"] == "not_observed"
    assert observation["total_pages"] is None and observation["mixed_text_raster_pages"] is None
    assert observation["pages"] == [] and observation["omitted_page_ranges"] == []


def test_browse_observation_bounds_and_page_filter_are_explicit(tmp_path: Path) -> None:
    config = library(tmp_path, pages=300)
    source = selected(config)
    result = browse(config, source, page_size=1)
    observation = result["source"]["pdf_extraction_observation"]
    assert len(observation["pages"]) == 256
    assert observation["returned_page_range"] == {"start": 1, "end": 256}
    assert observation["omitted_page_ranges"] == [{"start": 257, "end": 300}]
    assert observation["mixed_text_raster_pages"] == 1
    filtered = browse(config, source, locator_range={"kind": "page", "start": 290, "end": 300})
    observation = filtered["source"]["pdf_extraction_observation"]
    assert len(observation["pages"]) == 11 and observation["pages"][0]["has_raster_images"]
    assert observation["omitted_page_ranges"] == [{"start": 1, "end": 289}]
    outside = browse(config, source, locator_range={"kind": "page", "start": 301, "end": 999})
    assert outside["entries"] == []
    assert outside["source"]["pdf_extraction_observation"]["omitted_page_ranges"] == [
        {"start": 1, "end": 300},
    ]


def test_v2_cursor_cannot_be_used_by_v1(tmp_path: Path) -> None:
    config = library(tmp_path)
    publish_pages(config.db_path, ("second",), fingerprint="b")
    initial = call(config, "list_sources_v2", {"page_size": 1})
    token = initial["selection"]["next_cursor"]
    assert call(config, "list_sources_v1", {"cursor": token})["problem"] == "invalid_cursor"
    assert call(config, "list_sources_v2", {"cursor": token})["ok"]
    source = selected(config)
    initial = browse(config, source, page_size=1)
    token = initial["selection"]["next_cursor"]
    assert call(config, "browse_source_evidence_v1", {"cursor": token})["problem"] == (
        "invalid_cursor"
    )


def test_bad_observation_fails_v2_closed_while_v1_shape_stays_usable(tmp_path: Path) -> None:
    config = library(tmp_path)
    with sqlite3.connect(config.db_path) as connection:
        connection.execute("UPDATE pdf_extraction_observations SET page_has_raster_images='[1]' ")
    assert call(config, "list_sources_v2", {})["problem"] == "internal_error"
    assert call(config, "list_sources_v1", {})["ok"]


def test_console_cli_explicitly_opts_into_observations(tmp_path: Path) -> None:
    config = library(tmp_path)
    catalog = cli_payloads(native_cli(
        config.db_path, "sources", "list", "--contract-version", "v2", "--json",
    ))
    assert catalog[0]["schema_version"] == "mke.list_sources_response.v2"
    source = catalog[0]["sources"][0]
    output = cli_payloads(native_cli(
        config.db_path, "source", "browse", source["source_id"], "--publication-id",
        source["publication_id"], "--contract-version", "v2", "--page-start", "2",
        "--page-end", "2", "--json",
    ))
    assert output[0]["source"]["pdf_extraction_observation"]["pages"] == [
        {"page_number": 2, "text_layer_chars": 14, "has_raster_images": True},
    ]
    assert output[0]["entries"][0]["excerpt"]["text"] == "text on page 2"
    default = cli_payloads(native_cli(config.db_path, "sources", "list", "--json"))[0]
    assert default["schema_version"] == "mke.list_sources_response.v1"
    assert "pdf_extraction_observation" not in default["sources"][0]


@pytest.mark.parametrize("mutation", ["boolean", "omission", "partition", "extra"])
def test_v2_observation_schema_rejects_forged_scope(tmp_path: Path, mutation: str) -> None:
    config = library(tmp_path)
    source = browse(config, selected(config))["source"]
    observation = source["pdf_extraction_observation"]
    if mutation == "boolean":
        observation["pages"][0]["has_raster_images"] = 0
    elif mutation == "omission":
        observation["omitted_page_ranges"] = [{"start": 1, "end": 6}]
    elif mutation == "partition":
        observation["text_only_pages"] = 2
    else:
        observation["confidence"] = 1.0
    with pytest.raises(ValidationError):
        source_schemas.SourceMetadataV2.model_validate(source)
