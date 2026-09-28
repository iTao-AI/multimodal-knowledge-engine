"""Provider-free guards for the static Evidence showcase projection."""

from __future__ import annotations

import json
import re
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
    assert {
        name: {"route": entry["route"], "state": entry["state"]}
        for name, entry in manifest["assets"].items()
    } == {
        "evidence-workspace-overview.png": {
            "route": "evidence-workspace-overview.html",
            "state": "overview",
        },
        "evidence-publication-search.png": {
            "route": "evidence-publication-search.html",
            "state": "publication_search",
        },
        "evidence-insufficient-recovery.png": {
            "route": "evidence-insufficient-recovery.html",
            "state": "failed_or_insufficient_recovery",
        },
    }
    for entry in manifest["assets"].values():
        assert entry["source_commit"] == manifest["source_commit"]
        assert entry["viewport"] == {"width": 1600, "height": 1000}
        assert entry["locale"] == "en-US"
        assert entry["synthetic_demo_disclosure"] == manifest["synthetic_demo_disclosure"]
        assert (SHOWCASE / entry["route"]).is_file()

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


def test_search_frame_has_one_visible_result_and_matching_provenance() -> None:
    markup = (SHOWCASE / "evidence-publication-search.html").read_text(encoding="utf-8")
    surface = markup.split('<section class="surface-card evidence-surface"', 1)[1].split(
        "</section>", 1
    )[0]
    cards = surface.count('<article class="evidence-card')
    provenance = markup.split('<section class="side-card provenance-card"', 1)[1].split(
        "</section>", 1
    )[0]

    assert cards == 1
    assert '<strong>1</strong>' in surface
    assert "short-audio.mp4" in surface
    assert "Timestamp 1,200–2,200 ms" in surface
    assert "returned=1 · active_evidence_count=4" in markup
    assert "sha256:4e3c9feffa503e193165ddf27c40c0e0edf9f256c2e8e1e2d863bd7ba3e1fe49" in provenance
    assert "timestamp_ms:1200-2200" in provenance
    assert "page:1-1" not in provenance
    assert "0ac3e96efc89ee91e48bb3efc8611de88b2698e5aa26c1f8e0e8f78ad2d60ddd" not in provenance


def test_recovery_frame_distinguishes_agent_consumer_branches() -> None:
    markup = (SHOWCASE / "evidence-insufficient-recovery.html").read_text(encoding="utf-8")

    for marker in (
        "selection.status=complete",
        "matches=[]",
        "Normal no-match",
        "selection.status=capped",
        "non-exhaustive",
        "problem=evidence_not_found",
        "next_step=search_current_active_evidence",
        "active_publication_impact=unchanged",
        "run_state=failed",
    ):
        assert marker in markup
    assert "normal_no_match" not in markup


def test_readmes_surface_mcp_consumer_branch_decisions() -> None:
    proof_link = "./docs/how-to/run-mcp-context-completeness-proof.md"
    for name, detail_heading in (
        ("README.md", "## Detailed contracts and history"),
        ("README_CN.md", "## Detailed contracts and history / 详细契约与历史"),
    ):
        text = (ROOT / name).read_text(encoding="utf-8")
        first_layer = text[: text.index(detail_heading)]
        assert len(re.findall(rf"\[[^\]]+\]\({re.escape(proof_link)}\)", first_layer)) == 1
        for literal in (
            "selection.status=complete",
            "selection.status=capped",
            "evidence_not_found",
            "search_current_active_evidence",
        ):
            assert literal in first_layer
        if name == "README_CN.md":
            assert "正常无匹配" in first_layer
            assert "非穷尽" in first_layer


def test_readmes_disclose_current_default_branch_release_boundary() -> None:
    requirements = (
        (
            "README.md",
            "### Current default branch status",
            "### Five-layer relation",
            "available from the current source checkout",
            "not included in `v0.1.7`",
        ),
        (
            "README_CN.md",
            "### 当前默认分支状态",
            "### 五层关系",
            "可从当前源码仓库使用",
            "尚未包含在 `v0.1.7` 中",
        ),
    )
    internal_nonclaims = (
        "package publication",
        "hosted deployment",
        "model/provider",
        "retrieval-quality",
    )
    for name, status_heading, following_heading, source_checkout, release_boundary in requirements:
        text = (ROOT / name).read_text(encoding="utf-8")
        status_start = text.index(status_heading)
        status = text[status_start : text.index(following_heading, status_start)]
        normalized_status = " ".join(status.split())
        assert "v0.1.7" in status
        assert "MCP consumer failure-branch/recovery proof" in status
        assert source_checkout in normalized_status
        assert release_boundary in normalized_status

        first_layer = text[: text.index(
            "## Detailed contracts and history"
            if name == "README.md"
            else "## Detailed contracts and history / 详细契约与历史"
        )]
        for nonclaim in internal_nonclaims:
            assert nonclaim not in first_layer, (name, nonclaim)


def test_readmes_embed_canonical_frames_once_in_approved_order() -> None:
    expected_order = (
        "./docs/evidence-workspace/evidence-workspace-overview.png",
        "./docs/evidence-workspace/evidence-publication-search.png",
        "./docs/evidence-workspace/evidence-insufficient-recovery.png",
    )
    for name, detail_heading, judgment_heading, quick_heading in (
        (
            "README.md",
            "## Detailed contracts and history",
            "### Four engineering judgments",
            "## Quick Verify",
        ),
        (
            "README_CN.md",
            "## Detailed contracts and history / 详细契约与历史",
            "### 四条工程判断",
            "## 快速验证",
        ),
    ):
        text = (ROOT / name).read_text(encoding="utf-8")
        first_layer = text[: text.index(detail_heading)]
        positions: list[int] = []
        for path in expected_order:
            matches = re.findall(rf"!\[[^\]]+\]\({re.escape(path)}\)", first_layer)
            assert len(matches) == 1, (name, path)
            positions.append(first_layer.index(matches[0]))
        assert positions == sorted(positions), name
        assert max(positions) < first_layer.index(judgment_heading), name
        assert max(positions) < first_layer.index(quick_heading), name
        assert first_layer.lower().count("synthetic") == 1, name


def test_readme_cn_first_layer_is_naturalized_without_changing_contract_terms() -> None:
    text = (ROOT / "README_CN.md").read_text(encoding="utf-8")
    first_layer = text[: text.index("## Detailed contracts and history / 详细契约与历史")]
    for phrase in (
        "本地原始资料",
        "来源处理",
        "当前产品切片",
        "示意值",
        "生命周期边界",
        "原始资料不是答案",
        "候选输出",
        "安全收口",
    ):
        assert phrase in first_layer
    for phrase in (
        "source material",
        "source processing",
        "product slice",
        "illustrative",
        "contract fields",
        "lifecycle boundaries",
        "Raw material",
        "candidate output",
        "fail closed",
    ):
        assert phrase not in first_layer
    for literal in (
        "`Source`",
        "`Run`",
        "`active Publication`",
        "`Evidence`",
        "`Search`",
        "`Ask`",
        "`stdio MCP`",
        "`mke.evidence_ref.v1`",
        "`active_publication_impact=unchanged`",
    ):
        assert literal in first_layer


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
