from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
GUIDE = ROOT / "docs/how-to/evaluate-relevance-gate-reranker.md"
ARTIFACT = (
    ROOT / "benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json"
)
FREEZE = (
    ROOT
    / "benchmarks/retrieval/cjk-relevance-gate-reranker-v1-development-freeze.json"
)
RECEIPT = (
    ROOT
    / "benchmarks/retrieval/cjk-relevance-gate-reranker-v1-holdout-receipt.json"
)
REVIEW = (
    ROOT
    / "docs/superpowers/reviews/2026-06-30-cjk-relevance-gate-reranker-review.md"
)
SPEC = (
    ROOT
    / "docs/superpowers/specs/2026-06-30-cjk-relevance-gate-reranker-design.md"
)
PLAN = (
    ROOT
    / "docs/superpowers/plans/2026-06-30-cjk-relevance-gate-reranker-implementation.md"
)


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_relevance_gate_guide_matches_canonical_holdout_result() -> None:
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    guide = GUIDE.read_text(encoding="utf-8")
    development = artifact["development"]
    holdout = artifact["holdout"]
    forbidden_scoring_boundary = (
        "does not read qrels, grades, query category labels, split labels, "
        "or expected locators as candidate scoring input"
    )

    for snippet in (
        "cjk-relevance-gate-reranker-v1",
        "comparison-only",
        "deterministic relevance gate",
        "selected_profile=strict-constraint",
        "development_status=passed",
        "holdout_status=observed",
        "holdout_gate_status=failed",
        "runtime_promotion_status=not_evaluated",
        "not a runtime strategy",
        forbidden_scoring_boundary,
        "mke eval retrieval-relevance-gate",
        "--development-only",
        "--record-development-freeze",
        "--record-holdout-receipt",
        "python -m mke.evaluation.relevance_gate_artifact validate",
        "Search, Ask, MCP, owner startup, Publication, ingestion",
        "API reranker, LLM judge, local cross-encoder, query rewrite, HyDE, segmentation",
        "Milvus, Redis, pgvector, LangChain, LlamaIndex, or LangGraph",
        "valid negative",
        "runtime promotion",
    ):
        assert snippet in guide

    for section in (development, holdout):
        for key in (
            "recall_at_5",
            "ndcg_at_10",
            "mrr_at_5",
            "unanswerable_no_hit_rate",
            "hard_negative_failure_rate",
        ):
            assert f"`{section['metrics'][key]['value']:.6f}`" in guide

    for key in (
        "input_union_count",
        "allowed_count",
        "dropped_grade2_count",
        "dense_only_recovery_retained_count",
        "lexical_only_recovery_retained_count",
        "union_only_recovery_retained_count",
        "empty_result_no_hit_count",
    ):
        assert f"`{key}={development['diagnostics'][key]}`" in guide

    assert hashlib.sha256(ARTIFACT.read_bytes()).hexdigest() in guide
    assert hashlib.sha256(FREEZE.read_bytes()).hexdigest() in guide
    assert hashlib.sha256(RECEIPT.read_bytes()).hexdigest() in guide


def test_relevance_gate_docs_are_discoverable_reviewed_and_runtime_neutral() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    review = REVIEW.read_text(encoding="utf-8")
    spec = SPEC.read_text(encoding="utf-8")
    plan = PLAN.read_text(encoding="utf-8")
    public_docs = "\n".join(
        _read(relative)
        for relative in (
            "README.md",
            "docs/README.md",
            "docs/reference/cli.md",
            "docs/explanation/architecture.md",
        )
    )

    assert "evaluate-relevance-gate-reranker.md" in public_docs
    assert "cjk-relevance-gate-reranker-v1" in public_docs
    assert "comparison-only deterministic relevance gate" in public_docs
    assert "holdout_gate_status=failed" in public_docs
    assert "runtime_promotion_status=not_evaluated" in public_docs
    assert "does not change Search, Ask, MCP, owner startup" in public_docs
    assert "not a runtime strategy" in public_docs
    for phrase in (
        "No API reranker",
        "LLM judge",
        "local cross-encoder",
        "query rewrite",
        "HyDE",
        "segmentation",
    ):
        assert phrase in public_docs

    assert "development_status=passed" in guide
    assert "holdout_gate_status=failed" in guide
    assert "pre-PR review" in review
    assert "local branch only" in review
    assert "no runtime promotion" in review
    assert "no unresolved implementation findings" in review
    assert "pending" not in review
    assert "No PR has been created" not in review
    for durable_doc in (spec, plan, review):
        assert "main@03a7583fd7161585bc039832b517cc3be97ddca9" in durable_doc
