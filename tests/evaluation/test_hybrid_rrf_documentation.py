from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
GUIDE = ROOT / "docs/how-to/evaluate-hybrid-rrf-retrieval.md"
ARTIFACT = (
    ROOT / "benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json"
)
FREEZE = (
    ROOT
    / "benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-development-freeze.json"
)
REVIEW = (
    ROOT
    / "docs/superpowers/reviews/2026-06-30-cjk-lexical-dense-rrf-fusion-review.md"
)


def test_hybrid_rrf_guide_matches_canonical_valid_negative() -> None:
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    guide = GUIDE.read_text(encoding="utf-8")
    metrics = artifact["development"]["metrics"]
    diagnostics = artifact["development"]["diagnostics"]

    for snippet in (
        "cjk-active-scan-qwen3-rrf-v1",
        "comparison-only",
        "rank-only RRF",
        "development_status=valid_negative",
        "holdout_status=not_observed",
        "runtime_promotion_status=not_evaluated",
        "selected threshold `0.58`",
        "retrieved_locators",
        "recorded dense rank",
        "mke eval retrieval-hybrid-rrf",
        "--record-development-freeze",
        "--record-holdout-receipt",
        "python -m mke.evaluation.hybrid_rrf_artifact validate",
        "python -m mke.evaluation.dense_replay validate",
        "optional corroborating check",
        "--model-cache <model-cache>",
        "Search, Ask, MCP, owner startup, Publication, ingestion",
        "API adapter, reranker, query rewrite, segmentation, HTTP/UI",
        "Milvus, Redis, or pgvector",
    ):
        assert snippet in guide

    for arm in ("fused", "lexical", "dense"):
        for key in ("recall_at_5", "ndcg_at_10", "mrr_at_5"):
            assert f"`{metrics[arm][key]['value']:.6f}`" in guide
    for key in (
        "union_grade2_coverage_at_10",
        "fused_lost_union_grade2_count",
        "ranking_headroom_count",
        "lexical_only_recovery_count",
        "dense_only_recovery_count",
        "both_arm_recovery_count",
        "neither_arm_miss_count",
    ):
        assert f"`{key}={diagnostics[key]}`" in guide

    assert hashlib.sha256(ARTIFACT.read_bytes()).hexdigest() in guide
    assert hashlib.sha256(FREEZE.read_bytes()).hexdigest() in guide


def test_hybrid_rrf_docs_are_discoverable_and_reviewed_without_promotion() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    review = REVIEW.read_text(encoding="utf-8")
    public_docs = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8")
        for relative in (
            "docs/README.md",
            "docs/explanation/architecture.md",
        )
    )

    assert "evaluate-hybrid-rrf-retrieval.md" in public_docs
    assert "cjk-active-scan-qwen3-rrf-v1" in public_docs
    assert "does not combine raw lexical and dense scores" in public_docs
    assert "does not change Search, Ask, MCP, owner startup" in public_docs
    assert "holdout was not observed" in review
    assert "valid negative" in review
    assert "pre-PR review" in review
    assert "targeted re-review" in review
    assert "pending" not in review
    assert "holdout_status=not_observed" in guide
