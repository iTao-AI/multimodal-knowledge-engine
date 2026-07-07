from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import fitz  # pyright: ignore[reportMissingTypeStubs]

from scripts.generate_local_knowledge_fixtures import generate_fixture_pack

FIXTURE_ROOT = Path("tests/fixtures/local-knowledge-v1")


def _fixture_files(manifest: dict[str, object]) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], manifest["files"])


def test_local_knowledge_fixture_pack_is_reproducible(tmp_path: Path) -> None:
    generated = generate_fixture_pack(tmp_path)
    committed = json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))

    assert generated == committed
    for item in _fixture_files(generated):
        name = cast(str, item["name"])
        assert (tmp_path / name).read_bytes() == (FIXTURE_ROOT / name).read_bytes()


def test_local_knowledge_fixture_pack_contains_two_text_layer_pdfs() -> None:
    manifest = cast(
        dict[str, object],
        json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8")),
    )

    assert manifest["format"] == "mke.local_knowledge_fixture.v1"
    assert manifest["queries"] == {
        "search": "Cedar Relay maintenance window",
        "answer": "Cedar Relay telemetry amber",
        "refusal": "lunar payroll retention policy",
    }
    assert [item["name"] for item in _fixture_files(manifest)] == [
        "operations-guide.pdf",
        "incident-guide.pdf",
    ]
    for item in _fixture_files(manifest):
        path = FIXTURE_ROOT / cast(str, item["name"])
        document: Any = fitz.open(path)
        try:
            assert document.page_count == 1
            assert document[0].get_text().strip()
        finally:
            document.close()


def test_local_knowledge_fixture_readme_records_reproducible_public_provenance() -> None:
    manifest = cast(
        dict[str, object],
        json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8")),
    )
    readme = (FIXTURE_ROOT / "README.md").read_text(encoding="utf-8")

    assert "repository-authored synthetic" in readme
    assert "scripts/generate_local_knowledge_fixtures.py" in readme
    assert "UV_OFFLINE=1 uv run python" in readme
    assert fitz.VersionBind in readme
    assert "no_new_id=True" in readme
    for item in _fixture_files(manifest):
        assert f"`{item['name']}`" in readme
        assert f"{item['bytes']}" in readme
        assert f"`{item['sha256']}`" in readme
