from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPT = Path("scripts/source_discovery_consumer.py")


def consumer() -> Any:
    spec = importlib.util.spec_from_file_location("source_discovery_consumer", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    descriptor = {
        "evidence_id": "ev_fixture",
        "source_id": "src_fixture",
        "content_fingerprint": "sha256:" + "a" * 64,
        "publication_id": "pub_fixture",
        "publication_revision": 1,
        "run_id": "run_fixture",
        "locator": {"kind": "page", "start": 2, "end": 2},
        "evidence_text_sha256": "sha256:" + hashlib.sha256("Café🙂".encode()).hexdigest(),
        "original_utf8_bytes": 9,
    }
    chunks = [
        {
            "ok": True,
            "evidence": copy.deepcopy(descriptor),
            "content": {"text": "Ca", "offset_bytes": 0, "returned_utf8_bytes": 2},
            "complete": False,
            "next_cursor": "opaque",
        },
        {
            "ok": True,
            "evidence": copy.deepcopy(descriptor),
            "content": {"text": "fé🙂", "offset_bytes": 2, "returned_utf8_bytes": 7},
            "complete": True,
            "next_cursor": None,
        },
    ]
    return descriptor, chunks


def test_consumer_reconstructs_exact_utf8_text() -> None:
    descriptor, chunks = sample()
    assert consumer().verify_exact_read(descriptor, chunks) == "Café🙂"


@pytest.mark.parametrize(
    "field",
    [
        "source_id",
        "publication_id",
        "publication_revision",
        "run_id",
        "content_fingerprint",
        "locator",
        "evidence_text_sha256",
        "original_utf8_bytes",
    ],
)
def test_consumer_rejects_changed_citation_provenance(field: str) -> None:
    module = consumer()
    descriptor, chunks = sample()
    chunks[1]["evidence"][field] = "mutated"
    with pytest.raises(module.ConsumerFailure):
        module.verify_exact_read(descriptor, chunks)


def test_consumer_rejects_digest_mismatch_after_matching_lineage() -> None:
    module = consumer()
    descriptor, chunks = sample()
    descriptor["evidence_text_sha256"] = "sha256:" + "b" * 64
    for chunk in chunks:
        chunk["evidence"] = copy.deepcopy(descriptor)
    with pytest.raises(module.ConsumerFailure):
        module.verify_exact_read(descriptor, chunks)


@pytest.mark.parametrize("field,value", [("offset_bytes", 3), ("returned_utf8_bytes", 6)])
def test_consumer_rejects_chunk_gaps_and_wrong_byte_count(field: str, value: int) -> None:
    module = consumer()
    descriptor, chunks = sample()
    chunks[1]["content"][field] = value
    with pytest.raises(module.ConsumerFailure):
        module.verify_exact_read(descriptor, chunks)


def test_consumer_has_no_project_or_storage_imports() -> None:
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
    assert "mcp" in roots


def test_independent_native_consumer_reports_honest_coverage(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(SCRIPT),
            "--mke-bin",
            str(Path(".venv/bin/mke").resolve()),
            "--work-dir",
            str(tmp_path / "example"),
            "--expectation",
            "tests/fixtures/source-discovery-v1/mcp-tool-schemas.json",
        ],
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["status"] == "passed"
    assert receipt["tool_count"] == 12
    assert receipt["pdf"]["coverage"]["total_pages"] == 4
    assert receipt["pdf"]["coverage"]["extracted_pages"] == 3
    assert receipt["pdf"]["coverage"]["empty_pages"] == 1
    assert receipt["pdf"]["coverage"]["suspected_scanned_pages"] == 1
    assert receipt["pdf"]["catalog_counts_omitted"] is True
    assert receipt["pdf"]["coverage"]["page_char_counts_omitted"] is False
    assert receipt["pdf"]["coverage"]["page_char_counts"][2] == 0
    assert receipt["pdf"]["browse_pages"] == 2
    assert receipt["pdf"]["locators"] == [2, 4]
    assert receipt["pdf"]["query_excluded_page"] is True
    assert receipt["pdf"]["preview_complete"] is False
    assert receipt["pdf"]["read_chunks"] > 1
    assert receipt["transcript"]["report_status"] == "not_observed"
    assert receipt["transcript"]["locators"] == [[0, 1000], [1000, 2000]]
    assert receipt["catalog_pages"] == 2
    assert receipt["exact_utf8_and_citation_verified"] is True
    assert receipt["max_canonical_model_bytes"] <= 32768
    assert receipt["max_sdk_result_bytes"] < 96 * 1024
    assert receipt["asr_execution"] == "not_performed"
    assert receipt["ocr_execution"] == "not_performed"
    assert str(tmp_path) not in result.stdout
    assert "next_cursor" not in result.stdout
    assert "lexicalneedle" not in result.stdout
