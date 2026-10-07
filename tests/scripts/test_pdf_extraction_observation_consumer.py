from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path("scripts/pdf_extraction_observation_consumer.py").resolve()


@pytest.mark.parametrize("expectation", ["source-search-v1", "pdf-extraction-observation-v1"])
def test_native_observation_consumers_share_identity_and_exact_text(
    tmp_path: Path, expectation: str,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(SCRIPT),
            "--mke-bin",
            str(Path(".venv/bin/mke").resolve()),
            "--work-dir",
            str(tmp_path / "case"),
            "--expectation",
            str(
                Path(f"tests/fixtures/{expectation}/mcp-tool-schemas.json").resolve()
            ),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if expectation == "pdf-extraction-observation-v1":
        assert result.returncode == 1
        # SDK task groups wrap inventory rejection; the existing entrypoint redacts that failure.
        assert json.loads(result.stdout) == {"status": "failed", "code": "example_failed"}
        return
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["schema_version"] == "mke.pdf_extraction_observation_consumer.v1"
    assert receipt["status"] == "passed" and receipt["tool_count"] == 15
    observation = receipt["pdf_extraction_observation"]
    assert [
        observation[key]
        for key in (
            "total_pages",
            "text_only_pages",
            "mixed_text_raster_pages",
            "raster_only_pages",
            "neither_text_nor_raster_pages",
        )
    ] == [6, 1, 2, 1, 2]
    assert [page["has_raster_images"] for page in observation["pages"]] == [
        False,
        True,
        True,
        True,
        False,
        False,
    ]
    assert receipt["evidence_pages"] == [1, 2, 3]
    assert receipt["exact_read_chunks"] > 3
    assert receipt["legacy_entries_unchanged"] is True
    assert receipt["cli_mcp_export_viewer_identity_verified"] is True
    assert receipt["exact_utf8_verified"] is True
    assert receipt["raster_only_text_absent"] is True
    assert receipt["viewer"]["evidence_count"] == 3
    assert receipt["max_canonical_model_bytes"] <= 32768
    assert receipt["max_sdk_result_bytes"] < 96 * 1024
    assert receipt["ocr_execution"] == "not_performed"
    assert receipt["original_media_semantic_coverage"] == "not_evaluated"
    assert str(tmp_path) not in result.stdout and "next_cursor" not in result.stdout
    assert "Stored mixed line" not in result.stdout


def test_observation_consumer_has_no_producer_or_storage_imports() -> None:
    tree = ast.parse(SCRIPT.read_text())
    roots = {
        node.module.split(".")[0]
        if isinstance(node, ast.ImportFrom) and node.module
        else alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert {"mke", "tests", "sqlite3"}.isdisjoint(roots)
    assert {"mcp", "compiled_library_export_consumer_v3"} <= roots
