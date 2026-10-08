from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import pymupdf
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/source_evidence_installed_consumer.py"


def consumer() -> Any:
    assert SCRIPT.is_file(), "installed Source consumer entry is missing"
    return importlib.import_module("scripts.source_evidence_installed_consumer")


def assets(root: Path) -> Path:
    root.mkdir()
    entries: list[dict[str, Any]] = []
    for role, count, text in [
        ("selected", 3, "needle café selected"),
        ("other", 5, "needle outsideonly"),
    ]:
        path = root / f"{role}.pdf"
        document = pymupdf.open()
        for number in range(count):
            page = document.new_page()
            page.insert_text((72, 72), f"{text} page {number + 1}")  # pyright: ignore[reportUnknownMemberType]
        document.save(path, no_new_id=True)  # pyright: ignore[reportUnknownMemberType]
        document.close()
        entries.append(
            {
                "role": role,
                "filename": path.name,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "pages": count,
            }
        )
    (root / "manifest.json").write_text(
        json.dumps(
            {"schema_version": "mke.source_evidence_installed_manifest.v1", "sources": entries}
        )
    )
    return root


def config(module: Any, root: Path, asset_root: Path) -> Any:
    return module.Config(
        root,
        asset_root,
        ROOT / "tests/fixtures/source-search-v1/mcp-tool-schemas.json",
        Path(sys.executable).with_name("mke"),
        {**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )


@pytest.mark.parametrize("mutation", ["digest", "bytes", "extra", "filename"])
def test_asset_identity_is_checked_before_creating_a_library(tmp_path: Path, mutation: str) -> None:
    module = consumer()
    source_root = assets(tmp_path / "assets")
    manifest = json.loads((source_root / "manifest.json").read_text())
    if mutation == "digest":
        manifest["sources"][0]["sha256"] = "0" * 64
    elif mutation == "bytes":
        manifest["sources"][0]["bytes"] += 1
    elif mutation == "extra":
        manifest["sources"][0]["unbound"] = True
    else:
        manifest["sources"][0]["filename"] = "../selected.pdf"
    (source_root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(module.CaseFailure, match="asset_identity_invalid"):
        asyncio.run(module.run_flow(config(module, tmp_path / "data", source_root)))
    assert not (tmp_path / "data").exists()


def test_real_flow_binds_cli_ask_to_sdk_reads_and_never_fills_from_other_source(
    tmp_path: Path,
) -> None:
    module = consumer()
    source_root = assets(tmp_path / "assets")
    result = asyncio.run(module.run_flow(config(module, tmp_path / "data", source_root)))
    assert result["schema_version"] == "mke.source_evidence_installed_consumer.v1"
    assert result["status"] == "passed" and result["tool_count"] == 15
    assert result["cases"] == {
        "first_page": "more_available",
        "complete": "complete",
        "selected_empty": "insufficient_evidence",
        "unrelated_match": True,
        "cli_sdk_equal": True,
        "utf8_digest_and_excerpt_verified": True,
    }
    assert (
        result["scope"]["content_fingerprint"]
        == "sha256:" + hashlib.sha256((source_root / "selected.pdf").read_bytes()).hexdigest()
    )
    assert result["scope"]["publication_revision"] == 1
    assert len(result["references"]) == 3
    for reference in result["references"]:
        assert reference["evidence"]["source_id"] == result["scope"]["source_id"]
        assert reference["evidence"]["publication_id"] == result["scope"]["publication_id"]
        assert reference["evidence"]["run_id"] == result["scope"]["run_id"]
        assert reference["verified_utf8_bytes"] == reference["evidence"]["original_utf8_bytes"]
        assert reference["exact_text_sha256_verified"] is True
        assert reference["excerpt_window_verified"] is True
    assert len(json.dumps(result).encode()) < 32768
    assert "next_cursor" not in json.dumps(result)
    assert result["references"][0]["verified_utf8_bytes"] == 28


@pytest.mark.parametrize(
    ("case", "code"),
    [
        ("mismatch", "identity_mismatch_detected"),
        ("stale", "stale_publication_detected"),
        ("read_failure", "read_replacement_detected"),
        ("citation_failure", "citation_corruption_detected"),
    ],
)
def test_real_negative_boundary_discards_the_entire_result(
    tmp_path: Path, case: str, code: str
) -> None:
    module = consumer()
    source_root = assets(tmp_path / "assets")
    cfg = config(module, tmp_path / "data", source_root)
    asyncio.run(module.run_flow(cfg))
    with pytest.raises(module.CaseFailure) as failure:
        asyncio.run(module.run_negative(cfg, case))
    assert failure.value.code == code
    if case in {"read_failure", "citation_failure"}:
        evidence = json.loads((cfg.work_dir / f"{case}-boundary.json").read_text())
        assert evidence["first_reference_complete"] is True
        assert evidence["native_boundary_exercised"] is True
        assert evidence["successful_receipt_emitted"] is False


def test_reused_library_is_refused_without_overwrite(tmp_path: Path) -> None:
    module = consumer()
    source_root = assets(tmp_path / "assets")
    data = tmp_path / "data"
    data.mkdir()
    retained = data / "existing.sqlite"
    retained.write_bytes(b"retained")
    with pytest.raises(module.CaseFailure, match="work_directory_exists"):
        asyncio.run(module.run_flow(config(module, data, source_root)))
    assert retained.read_bytes() == b"retained"


def test_cli_ask_packet_validation_rejects_changed_lineage(tmp_path: Path) -> None:
    module = consumer()
    source_root = assets(tmp_path / "assets")
    cfg = config(module, tmp_path / "data", source_root)
    asyncio.run(module.run_flow(cfg))
    stored = json.loads((cfg.work_dir / "cli-complete.json").read_text())
    corrupted = copy.deepcopy(stored)
    corrupted["evidence"][0]["evidence"]["run_id"] = "run_" + "0" * 32
    with pytest.raises(module.CaseFailure, match="cli_packet_invalid"):
        module.validate_ask(corrupted, stored["scope"], "needle")


def test_declared_generator_is_deterministic_and_keeps_multibyte_pdf_text(tmp_path: Path) -> None:
    script = ROOT / "scripts/generate_source_evidence_installed_fixtures.py"
    assert script.is_file(), "independently named fixture generator is missing"
    generator = importlib.import_module("scripts.generate_source_evidence_installed_fixtures")
    generator.build_assets(tmp_path / "first")
    generator.build_assets(tmp_path / "second")
    for name in ("selected.pdf", "other.pdf", "manifest.json"):
        assert (tmp_path / "first" / name).read_bytes() == (tmp_path / "second" / name).read_bytes()
    with pymupdf.open(tmp_path / "first/selected.pdf") as document:
        assert len(document) == 3
        text = document[0].get_text()  # pyright: ignore[reportUnknownMemberType]
        assert isinstance(text, str) and text.strip() == "needle café selected page 1"
    manifest = json.loads((tmp_path / "first/manifest.json").read_text())
    assert {row["filename"] for row in manifest["sources"]} == {"selected.pdf", "other.pdf"}
