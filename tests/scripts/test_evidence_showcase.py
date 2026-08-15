"""Provider-free guards for the static Evidence showcase projection."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHOWCASE = ROOT / "docs/evidence-workspace"
PNG_NAMES = {
    "evidence-workspace-overview.png",
    "evidence-publication-search.png",
    "evidence-insufficient-recovery.png",
}


def test_showcase_projection_is_closed_and_contract_bound() -> None:
    assert SHOWCASE.is_dir(), "generate docs/evidence-workspace before verifying its projection"

    from scripts.generate_evidence_workspace import verify_showcase

    report = verify_showcase(ROOT)
    assert report["png_names"] == sorted(PNG_NAMES)
    assert report["viewport"] == {"width": 1600, "height": 1000}
    assert report["locale"] == "en-US"

    manifest = json.loads((SHOWCASE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "mke.evidence_showcase_manifest.v1"
    assert manifest["fixture_state"] == {
        "compiled_export": "mke.compiled_library_export.v2",
        "local_knowledge": "local-knowledge-v1",
        "product_proof": "mke proof run",
        "video_fixture": "short-audio.mp4.mke-transcript.json",
    }
    assert manifest["synthetic_demo_disclosure"]
    assert set(manifest["assets"]) == PNG_NAMES

    all_markup = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(SHOWCASE.glob("*.html"))
    )
    for marker in (
        "mke.active_publication_observation.v1",
        "mke.evidence_ref.v1",
        "selection.status",
        "publication_revision",
        "timestamp_ms",
        "CLI",
        "stdio MCP",
        "Compiled Library Export",
        "pdf_ingest_failed",
        "PDF cannot be opened",
        "active_publication_impact",
        "fix_input_or_retry",
        "insufficient_evidence",
    ):
        assert marker in all_markup


def test_readmes_put_showcase_lifecycle_before_detail() -> None:
    headings = {
        "README.md": (
            "## Evidence workspace",
            "## Quick Verify",
            "## Detailed contracts and history",
        ),
        "README_CN.md": (
            "## Evidence workspace / 证据工作台",
            "## 快速验证",
            "## Detailed contracts and history / 详细契约与历史",
        ),
    }
    for name, expected_headings in headings.items():
        text = (ROOT / name).read_text(encoding="utf-8")
        positions = [text.find(heading) for heading in expected_headings]
        assert all(position >= 0 for position in positions), name
        assert positions == sorted(positions), name
