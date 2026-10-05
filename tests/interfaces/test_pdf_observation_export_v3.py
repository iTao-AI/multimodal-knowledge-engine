from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.interfaces.test_pdf_observation_source_v2 import browse, library, selected
from tests.source_discovery_support import (
    CLI,
    cli_payloads,
    create_library,
    native_cli,
    publish_pages,
)

ROOT = Path.cwd()


def export(database: Path, parent: Path, name: str, version: str) -> Path:
    result = subprocess.run(
        [
            str(CLI),
            "--db",
            str(database),
            "library",
            "export",
            "--output",
            name,
            "--format-version",
            version,
            "--json",
        ],
        cwd=parent,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == f"mke.compiled_library_export_response.{version}"
    assert payload["ok"]
    return parent / name


def consumer(directory: Path, version: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(ROOT / f"scripts/compiled_library_export_consumer_{version}.py"),
            "--export",
            str(directory),
            "--json",
        ],
        cwd=directory.parent,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def test_real_v3_export_matches_browse_and_keeps_v2_evidence_bytes(tmp_path: Path) -> None:
    config = library(tmp_path)
    source = selected(config)
    detail = browse(config, source)["source"]["pdf_extraction_observation"]
    v2 = export(config.db_path, tmp_path, "export-v2", "v2")
    v3 = export(config.db_path, tmp_path, "export-v3", "v3")
    manifest = json.loads((v3 / "export-manifest.json").read_text())
    assert manifest["schema_version"] == "mke.compiled_library_export.v3"
    entry = manifest["sources"][0]
    assert entry["pdf_extraction_observation"] == detail
    for field in (
        "source_id",
        "publication_id",
        "publication_revision",
        "run_id",
        "content_fingerprint",
        "extractor_fingerprint",
    ):
        assert entry[field] == source[field]
    assert (v3 / entry["evidence_path"]).read_bytes() == (v2 / entry["evidence_path"]).read_bytes()
    assert consumer(v3, "v3").returncode == 0
    assert consumer(v2, "v2").returncode == 0
    assert consumer(v3, "v2").returncode == 1


def test_read_only_v3_export_from_pre_migration_library_is_unknown(tmp_path: Path) -> None:
    database = tmp_path / "mke.sqlite"
    publish_pages(database, ("ordinary old text",))
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE pdf_extraction_observations")
    directory = export(database, tmp_path, "old-v3", "v3")
    manifest = json.loads((directory / "export-manifest.json").read_text())
    observation = manifest["sources"][0]["pdf_extraction_observation"]
    assert observation["status"] == "not_observed"
    assert observation["mixed_text_raster_pages"] is None
    assert consumer(directory, "v3").returncode == 0
    with sqlite3.connect(database) as connection:
        assert not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='pdf_extraction_observations'",
        ).fetchall()


def test_non_pdf_v2_source_and_v3_viewer_keep_timestamp_identity(tmp_path: Path) -> None:
    database = create_library(tmp_path)
    catalog = cli_payloads(
        native_cli(
            database,
            "sources",
            "list",
            "--contract-version",
            "v2",
            "--json",
        )
    )
    source = next(
        item
        for response in catalog
        for item in response["sources"]
        if item["media_type"] == "video/mp4"
    )
    assert source["pdf_extraction_observation"] is None
    selected = cli_payloads(
        native_cli(
            database,
            "source",
            "browse",
            source["source_id"],
            "--publication-id",
            source["publication_id"],
            "--contract-version",
            "v2",
            "--json",
        )
    )[0]
    assert selected["source"]["pdf_extraction_observation"] is None
    directory = export(database, tmp_path, "mixed-v3", "v3")
    assert consumer(directory, "v3").returncode == 0
    output = tmp_path / "mixed-viewer.html"
    built = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(ROOT / "scripts/build_compiled_library_viewer.py"),
            "--export",
            str(directory),
            "--output",
            str(output),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    marker = '<script type="application/json" id="viewer-data">'
    data = json.loads(output.read_text().split(marker, 1)[1].split("</script>", 1)[0])
    viewed = next(item for item in data["sources"] if item["source_id"] == source["source_id"])
    assert viewed["pdf_extraction_observation"] is None
    for row, entry in zip(viewed["evidence"], selected["entries"], strict=True):
        assert row["text"] == entry["excerpt"]["text"]
        for key in ("evidence_id", "publication_id", "run_id", "content_fingerprint", "locator"):
            assert row[key] == entry["evidence"][key]
        assert row["locator"]["kind"] == "timestamp_ms"


def test_v3_large_pdf_discloses_bounded_details_and_full_counts(tmp_path: Path) -> None:
    config = library(tmp_path, pages=300)
    directory = export(config.db_path, tmp_path, "large-v3", "v3")
    manifest = json.loads((directory / "export-manifest.json").read_text())
    observation = manifest["sources"][0]["pdf_extraction_observation"]
    assert observation["total_pages"] == 300
    assert observation["mixed_text_raster_pages"] == 1
    assert observation["returned_page_range"] == {"start": 1, "end": 256}
    assert observation["omitted_page_ranges"] == [{"start": 257, "end": 300}]
    assert len(observation["pages"]) == 256
    assert not any(page["has_raster_images"] for page in observation["pages"])
    result = consumer(directory, "v3")
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("mutation", ["boolean", "omission", "unknown_zero", "identity", "chars"])
def test_independent_v3_consumer_rejects_forged_observation(tmp_path: Path, mutation: str) -> None:
    config = library(tmp_path)
    directory = export(config.db_path, tmp_path, "export-v3", "v3")
    path = directory / "export-manifest.json"
    manifest: dict[str, Any] = json.loads(path.read_text())
    source = manifest["sources"][0]
    observation = source["pdf_extraction_observation"]
    if mutation == "boolean":
        observation["pages"][0]["has_raster_images"] = 0
    elif mutation == "omission":
        observation["omitted_page_ranges"] = [{"start": 1, "end": 6}]
    elif mutation == "unknown_zero":
        observation["status"] = "not_observed"
    elif mutation == "identity":
        source["run_id"] = "run_" + "f" * 32
    else:
        observation["pages"][0]["text_layer_chars"] = 13
    # Keep Markdown consistent with the forged declaration so its hash alone cannot catch it.
    markdown = directory / source["markdown_path"]
    original = markdown.read_text()
    begin = original.index("```json\n") + len("```json\n")
    end = original.index("```", begin)
    changed = (
        original[:begin]
        + json.dumps(
            observation,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
        + original[end:]
    )
    markdown.write_text(changed)
    source["markdown_sha256"] = hashlib.sha256(markdown.read_bytes()).hexdigest()
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    )
    assert consumer(directory, "v3").returncode == 1
