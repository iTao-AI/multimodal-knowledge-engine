from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
HOW_TO = ROOT / "docs/how-to/prepare-local-embeddings.md"
REVIEW = (
    ROOT
    / "docs/superpowers/reviews/2026-06-28-local-dense-prerequisites-review.md"
)
SPEC = (
    ROOT
    / "docs/superpowers/specs/2026-06-28-local-dense-retrieval-candidate-design.md"
)
PLAN = (
    ROOT
    / "docs/superpowers/plans/2026-06-28-local-dense-retrieval-candidate-implementation.md"
)


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_dense_embedding_docs_are_discoverable_and_comparison_only() -> None:
    text = "\n".join(
        _read(relative)
        for relative in (
            "README.md",
            "docs/README.md",
            "docs/reference/cli.md",
            "docs/explanation/architecture.md",
            "docs/how-to/prepare-local-embeddings.md",
        )
    )

    assert "prepare-local-embeddings.md" in text
    assert "qwen3-embedding-0.6b-exact-v1" in text
    assert "Qwen/Qwen3-Embedding-0.6B" in text
    assert "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3" in text
    assert "comparison-only" in text
    assert "does not change normal Search, Ask, MCP, or the runtime default" in text
    assert "future API adapter" in text


def test_dense_how_to_documents_install_prepare_doctor_and_offline_proof() -> None:
    guide = HOW_TO.read_text(encoding="utf-8")

    for snippet in (
        "uv sync --locked --extra embedding",
        "uv build",
        "\"dist/multimodal_knowledge_engine-0.0.0-py3-none-any.whl[embedding]\"",
        "uv pip install --offline",
        "mke embedding prepare --allow-model-download",
        "--model qwen3-embedding-0.6b",
        "--model-revision 97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
        "--model-cache \"$HOME/Library/Caches/mke/embedding\"",
        "mke embedding doctor",
        "scripts/dense_retrieval_deployment_proof.py",
        "HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 UV_OFFLINE=1",
    ):
        assert snippet in guide

    assert "Installing packages may use a package index" in guide
    assert "Only prepare may download model files" in guide
    assert "MKE never deletes model caches" in guide
    assert "manual operator action" in guide


def test_dense_docs_match_canonical_compatibility_artifact() -> None:
    artifact = json.loads(
        (
            ROOT / "benchmarks/retrieval/qwen3-embedding-0.6b-compatibility.json"
        ).read_text(encoding="utf-8")
    )
    guide = HOW_TO.read_text(encoding="utf-8")

    resources = artifact["resources"]
    assert artifact["schema_version"] == "mke.dense_compatibility.v2"
    for value in (
        artifact["model"]["snapshot_fingerprint"],
        artifact["projection"]["selected_adapter"],
        artifact["projection"]["sqlite_vec"]["rejection_reason"],
        str(resources["snapshot_bytes"]),
        str(resources["physical_memory_bytes"]),
        str(resources["compatibility_stress_peak_rss_bytes"]),
        str(resources["single_query_smoke"]["peak_rss_bytes"]),
    ):
        assert value in guide
    assert "6 GiB" in guide
    assert "40% physical memory" in guide
    assert "single-query" in guide


def test_dense_ci_and_review_record_model_free_boundary() -> None:
    ci = _read(".github/workflows/ci.yml")
    review = REVIEW.read_text(encoding="utf-8")

    assert "test_dense_compatibility.py" in ci
    assert "qwen3-embedding-0.6b-compatibility.json" in ci
    assert "HF_HUB_OFFLINE=1" in ci
    assert "no model download" in review
    assert "No dense qrels were read or scored" in review
    assert "Python 3.12" in review
    assert "Python 3.13" in review
    assert "sqlite-vec" in review


def test_dense_durable_artifacts_record_completed_pr1_and_targeted_review_resolution() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    plan = PLAN.read_text(encoding="utf-8")
    review = REVIEW.read_text(encoding="utf-8")

    assert "implementation has not started" not in " ".join(spec.split())
    assert "Task 0.5 is being revised" not in " ".join(plan.split())
    for number, step in (
        (3, "Run the complete PR 1 verification"),
        (4, "Run `gstack-document-release` and light self-review"),
        (5, "Commit documentation and CI"),
        (6, "Handoff PR 1 for authoritative review"),
    ):
        assert f"- [x] **Step {number}: {step}**" in plan
    assert "final verification pending" not in review
    assert "Authoritative Pre-PR Review Resolution" in review
    assert "Targeted re-review remains pending" in review
