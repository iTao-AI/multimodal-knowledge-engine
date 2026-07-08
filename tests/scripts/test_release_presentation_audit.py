from __future__ import annotations

from pathlib import Path

import pytest

from scripts.release_presentation_audit import audit_release_presentation


def test_audit_targets_v0_1_1_release_identity() -> None:
    from scripts import release_presentation_audit as audit

    assert audit.EXPECTED_VERSION == "0.1.1"
    assert "docs/releases/v0.1.1.md" in audit.RELEASE_FACING_FILES
    assert "docs/releases/v0.1.0.md" not in audit.RELEASE_FACING_FILES


def _write_release_tree(root: Path) -> None:
    (root / "src/mke").mkdir(parents=True)
    (root / "docs/releases").mkdir(parents=True)
    (root / "docs/how-to").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "multimodal-knowledge-engine"\nversion = "0.1.1"\n',
        encoding="utf-8",
    )
    (root / "src/mke/__init__.py").write_text('__version__ = "0.1.1"\n', encoding="utf-8")
    readme_en_text = """
# Multimodal Knowledge Engine

[English](./README.md) | [中文](./README_CN.md)

v0.1.1 ships `cjk-active-scan-overlap-v1` as the current owner-startup runtime.
E3-C dense, E3-D RRF, and E3-E reranker work are comparison-only evidence and are
not runtime strategies.

```mermaid
flowchart TB
    subgraph Interfaces["Interfaces"]
        Agent["Agent / Tool Client"]
        CLI["CLI"]
        MCP["stdio MCP Server"]
    end

    subgraph Application["Application Boundary"]
        App["MKE Application Service"]
        Contract["Shared CLI / MCP Contract"]
        Strategy["Owner-startup Retrieval Strategy"]
    end

    subgraph Lifecycle["Ingestion And Publication Lifecycle"]
        Source["Source"]
        Run["Observable Ingest Run"]
        Evidence["Evidence"]
        Publication["Active Publication"]
    end

    subgraph Authority["Domain Authority"]
        Store[("SQLite Domain Store")]
        Assets[("Immutable Assets")]
        Artifacts[("Immutable Artifacts")]
    end

    subgraph Runtime["Retrieval Runtime"]
        Projection["Rebuildable Retrieval Projections"]
        FTS["Active Evidence FTS"]
        CJK["cjk-active-scan-overlap-v1"]
        Search["Search"]
        Ask["Evidence-only Ask"]
    end

    subgraph Evaluation["Evaluation And Release Evidence"]
        Baselines["E1 / E3 baselines"]
        Dense["Dense candidate artifact"]
        RRF["RRF valid negative"]
        Reranker["Relevance gate / reranker artifact"]
        Proof["proof / demo / consumer smoke"]
        Comparison["Comparison-only Evidence"]
    end

    Agent --> Contract
    CLI --> Contract
    MCP --> Contract
    Contract --> App
    App --> Strategy
    App --> Source
    Source --> Run
    Run --> Evidence
    Evidence --> Publication
    Publication --> Projection
    Projection --> FTS
    Projection --> CJK
    FTS --> Search
    CJK --> Search
    Search --> Ask
    Store --> App
    Assets --> Run
    Artifacts --> Evidence
    Baselines -. recorded evidence .-> Comparison
    Dense -. comparison-only .-> Comparison
    RRF -. comparison-only .-> Comparison
    Reranker -. comparison-only .-> Comparison
    Proof -. release gate .-> App
```

## Verified in v0.1.1

| Capability | Evidence |
|---|---|
| Evidence lifecycle | Verified |
| text-layer PDF + short video fixture ingest | Verified |
| active-Publication Search | Verified |
| evidence-only Ask / insufficient_evidence | Verified |
| CLI + stdio MCP same application contract | Verified |
| Real stdio MCP local knowledge proof | Verified |
| cjk-active-scan-overlap-v1 default owner-startup strategy | Verified |
| proof/demo/installed-wheel consumer smoke | Verified |

## What this release proves

MKE v0.1.1 exercises the Evidence lifecycle, active Publication, CLI/MCP application
service contract, and retrieval evaluation artifacts.

| Retrieval evidence | v0.1.1 status | Boundary |
|---|---|---|
| Shipped runtime | lexical search and cjk-active-scan-overlap-v1 active scan | Active Evidence |
| Comparison-only evidence | dense, RRF, relevance gate / reranker | Runtime neutral |
| Not included | query rewrite, HyDE, OCR, HTTP/UI, API adapters | not v0.1.1 runtime behavior |

Search/Ask/MCP read active Publication Evidence.
This does not change normal Search, Ask, MCP, or the runtime default.
"""
    readme_cn_text = """
# Multimodal Knowledge Engine

[English](./README.md) | [中文](./README_CN.md)

v0.1.1 ships `cjk-active-scan-overlap-v1` as the current owner-startup runtime.
E3-C dense, E3-D RRF, and E3-E reranker work are comparison-only evidence and are
not runtime strategies.

```mermaid
flowchart TB
    subgraph Interfaces["Interfaces"]
        Agent["Agent / Tool Client"]
        CLI["CLI"]
        MCP["stdio MCP Server"]
    end

    subgraph Application["Application Boundary"]
        App["MKE Application Service"]
        Contract["Shared CLI / MCP Contract"]
        Strategy["Owner-startup Retrieval Strategy"]
    end

    subgraph Lifecycle["Ingestion And Publication Lifecycle"]
        Source["Source"]
        Run["Observable Ingest Run"]
        Evidence["Evidence"]
        Publication["Active Publication"]
    end

    subgraph Authority["Domain Authority"]
        Store[("SQLite Domain Store")]
        Assets[("Immutable Assets")]
        Artifacts[("Immutable Artifacts")]
    end

    subgraph Runtime["Retrieval Runtime"]
        Projection["Rebuildable Retrieval Projections"]
        FTS["Active Evidence FTS"]
        CJK["cjk-active-scan-overlap-v1"]
        Search["Search"]
        Ask["Evidence-only Ask"]
    end

    subgraph Evaluation["Evaluation And Release Evidence"]
        Baselines["E1 / E3 baselines"]
        Dense["Dense candidate artifact"]
        RRF["RRF valid negative"]
        Reranker["Relevance gate / reranker artifact"]
        Proof["proof / demo / consumer smoke"]
        Comparison["Comparison-only Evidence"]
    end

    Agent --> Contract
    CLI --> Contract
    MCP --> Contract
    Contract --> App
    App --> Strategy
    App --> Source
    Source --> Run
    Run --> Evidence
    Evidence --> Publication
    Publication --> Projection
    Projection --> FTS
    Projection --> CJK
    FTS --> Search
    CJK --> Search
    Search --> Ask
    Store --> App
    Assets --> Run
    Artifacts --> Evidence
    Baselines -. recorded evidence .-> Comparison
    Dense -. comparison-only .-> Comparison
    RRF -. comparison-only .-> Comparison
    Reranker -. comparison-only .-> Comparison
    Proof -. release gate .-> App
```

## v0.1.1 已验证能力

| 能力 | 验证证据 |
|---|---|
| Evidence 生命周期 | Verified |
| text-layer PDF + short video fixture ingest | Verified |
| active-Publication Search | Verified |
| evidence-only Ask / insufficient_evidence | Verified |
| CLI + stdio MCP same application contract | Verified |
| Real stdio MCP local knowledge proof | Verified |
| cjk-active-scan-overlap-v1 default owner-startup strategy | Verified |
| proof/demo/installed-wheel consumer smoke | Verified |

## v0.1.1 工程深度

MKE v0.1.1 验证 Evidence 生命周期、active Publication、CLI/MCP application
service contract，以及 retrieval evaluation artifacts。

| Retrieval evidence | v0.1.1 状态 | 边界 |
|---|---|---|
| 已发布 runtime | lexical search 和 cjk-active-scan-overlap-v1 active scan | Active Evidence |
| Comparison-only evidence | dense、RRF、relevance gate / reranker | Runtime neutral |
| 不包含 | query rewrite、HyDE、OCR、HTTP/UI、API adapters | 不是 v0.1.1 runtime behavior |

Search/Ask/MCP 读取 active Publication Evidence。
不改变 normal Search、Ask、MCP 或 runtime default。
"""
    (root / "README.md").write_text(readme_en_text, encoding="utf-8")
    (root / "README_CN.md").write_text(readme_cn_text, encoding="utf-8")
    (root / "docs/README.md").write_text(
        readme_en_text
        + "\nSee [v0.1.1](./releases/v0.1.1.md) and "
        "[Verify Release](./how-to/verify-release.md).\n",
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.1.1] - 2026-07-02\n\n"
        "Comparison-only dense/RRF/reranker evidence is not shipped runtime.\n",
        encoding="utf-8",
    )
    (root / "docs/releases/v0.1.1.md").write_text(
        "# v0.1.1\n\nProof, demo, CLI, MCP, local knowledge proof, and retrieval "
        "evaluation docs are linked.\n"
        "E3-C dense, E3-D RRF, and E3-E reranker remain comparison-only evidence.\n",
        encoding="utf-8",
    )
    (root / "docs/how-to/verify-release.md").write_text(
        "# Verify Release\n\nRun `mke proof run` and `mke demo --verify`.\n",
        encoding="utf-8",
    )


def _rules(root: Path) -> set[str]:
    return {violation.rule for violation in audit_release_presentation(root)}


def test_audit_accepts_complete_release_presentation(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)

    assert audit_release_presentation(tmp_path) == []


def test_audit_rejects_version_mismatch(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "src/mke/__init__.py").write_text('__version__ = "0.0.0"\n', encoding="utf-8")

    assert "version_identity" in _rules(tmp_path)


@pytest.mark.parametrize("path", ["README.md", "README_CN.md"])
def test_audit_rejects_missing_top_language_switch(tmp_path: Path, path: str) -> None:
    _write_release_tree(tmp_path)
    text = (tmp_path / path).read_text(encoding="utf-8").replace(
        "[English](./README.md) | [中文](./README_CN.md)\n\n",
        "",
    )
    (tmp_path / path).write_text(text, encoding="utf-8")

    assert "readme_language_switch" in _rules(tmp_path)


@pytest.mark.parametrize("path", ["README.md", "README_CN.md"])
def test_audit_rejects_missing_readme_mermaid_architecture_diagram(
    tmp_path: Path,
    path: str,
) -> None:
    _write_release_tree(tmp_path)
    text = (tmp_path / path).read_text(encoding="utf-8")
    text = text.replace("```mermaid", "```text")
    (tmp_path / path).write_text(text, encoding="utf-8")

    assert "readme_architecture_diagram" in _rules(tmp_path)


@pytest.mark.parametrize("path", ["README.md", "README_CN.md"])
def test_audit_rejects_linear_readme_architecture_diagram(
    tmp_path: Path,
    path: str,
) -> None:
    _write_release_tree(tmp_path)
    text = (tmp_path / path).read_text(encoding="utf-8")
    text = text.replace("subgraph Interfaces", "section Interfaces")
    (tmp_path / path).write_text(text, encoding="utf-8")

    assert "readme_architecture_diagram" in _rules(tmp_path)


@pytest.mark.parametrize("path", ["README.md", "README_CN.md"])
def test_audit_rejects_diagram_without_comparison_only_evidence_boundary(
    tmp_path: Path,
    path: str,
) -> None:
    _write_release_tree(tmp_path)
    text = (tmp_path / path).read_text(encoding="utf-8")
    text = text.replace("Comparison-only Evidence", "Runtime Evidence")
    text = text.replace("comparison-only", "runtime")
    (tmp_path / path).write_text(text, encoding="utf-8")

    assert "readme_architecture_diagram" in _rules(tmp_path)


@pytest.mark.parametrize("path", ["README.md", "README_CN.md"])
def test_audit_rejects_missing_verified_v011_table(tmp_path: Path, path: str) -> None:
    _write_release_tree(tmp_path)
    heading = "## Verified in v0.1.1" if path == "README.md" else "## v0.1.1 已验证能力"
    text = (tmp_path / path).read_text(encoding="utf-8").replace(
        heading,
        "## Release Scope",
    )
    (tmp_path / path).write_text(text, encoding="utf-8")

    assert "verified_v011_table" in _rules(tmp_path)


@pytest.mark.parametrize("path", ["README.md", "README_CN.md"])
def test_audit_rejects_shallow_readme_engineering_depth(tmp_path: Path, path: str) -> None:
    _write_release_tree(tmp_path)
    marker = "## What this release proves" if path == "README.md" else "## v0.1.1 工程深度"
    text = (tmp_path / path).read_text(encoding="utf-8").replace(
        marker,
        "## Notes",
    )
    (tmp_path / path).write_text(text, encoding="utf-8")

    assert "readme_engineering_depth" in _rules(tmp_path)


@pytest.mark.parametrize("path", ["README.md", "README_CN.md"])
def test_audit_rejects_missing_retrieval_evidence_table(tmp_path: Path, path: str) -> None:
    _write_release_tree(tmp_path)
    text = (tmp_path / path).read_text(encoding="utf-8").replace(
        "Comparison-only evidence",
        "Candidate observations",
    )
    (tmp_path / path).write_text(text, encoding="utf-8")

    assert "readme_engineering_depth" in _rules(tmp_path)


def test_audit_rejects_english_verified_labels_in_chinese_readme(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    text = (tmp_path / "README_CN.md").read_text(encoding="utf-8")
    text = text.replace("## v0.1.1 已验证能力", "## Verified in v0.1.1")
    text = text.replace("| 能力 | 验证证据 |", "| Capability | Evidence |")
    (tmp_path / "README_CN.md").write_text(text, encoding="utf-8")

    assert "verified_v011_table" in _rules(tmp_path)


def test_audit_rejects_chinese_verified_labels_in_english_readme(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    text = (tmp_path / "README.md").read_text(encoding="utf-8")
    text = text.replace("## Verified in v0.1.1", "## v0.1.1 已验证能力")
    text = text.replace("| Capability | Evidence |", "| 能力 | 验证证据 |")
    (tmp_path / "README.md").write_text(text, encoding="utf-8")

    assert "verified_v011_table" in _rules(tmp_path)


@pytest.mark.parametrize("path", ["README.md", "README_CN.md"])
def test_audit_rejects_missing_current_runtime_default(tmp_path: Path, path: str) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / path).write_text("v0.1.1 release notes\n", encoding="utf-8")

    assert "current_runtime_default" in _rules(tmp_path)


def test_audit_rejects_dense_rrf_or_reranker_runtime_claims(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "README.md").write_text(
        "[English](./README.md) | [中文](./README_CN.md)\n\n"
        "v0.1.1 ships `cjk-active-scan-overlap-v1`.\n"
        "```mermaid\nflowchart LR\n    app[MKE Application Service] --> search[Search / Ask]\n```\n"
        "## Verified in v0.1.1\n\n| Capability | Evidence |\n|---|---|\n| Proof | Verified |\n"
        "Dense retrieval, RRF, and reranker runtime support are available.\n",
        encoding="utf-8",
    )

    assert "comparison_runtime_overclaim" in _rules(tmp_path)


def test_audit_rejects_release_docs_presenting_comparison_candidates_as_runtime(
    tmp_path: Path,
) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "docs/releases/v0.1.1.md").write_text(
        "# v0.1.1\n\nProof, demo, CLI, MCP, and retrieval evaluation docs are linked.\n"
        "Dense/RRF/reranker runtime is part of this release.\n",
        encoding="utf-8",
    )

    assert "comparison_runtime_overclaim" in _rules(tmp_path)


def test_audit_requires_comparison_only_language_for_e3_candidates(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "docs/releases/v0.1.1.md").write_text(
        "# v0.1.1\n\nE3-C dense, E3-D RRF, and E3-E reranker are documented.\n",
        encoding="utf-8",
    )

    assert "comparison_only_boundary" in _rules(tmp_path)


def test_audit_rejects_stale_release_status_phrases(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "README.md").write_text(
        "v0.1.1 uses cjk-active-scan-overlap-v1. runtime_promotion_status=not_evaluated\n",
        encoding="utf-8",
    )

    assert "stale_release_status" in _rules(tmp_path)


def test_audit_rejects_stale_stage2_changelog_gate(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.1.1] - 2026-07-02\n\n"
        "Stage 2 installed-package consumer smoke, tag creation, and GitHub Release "
        "publication are separate gates after this presentation-readiness work merges.\n",
        encoding="utf-8",
    )

    assert "stale_release_status" in _rules(tmp_path)


def test_audit_rejects_separate_branch_stage2_wording(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "docs/how-to/verify-release.md").write_text(
        "# Verify Release\n\n"
        "Stage 2 must run from a separate branch after Stage 1 merges.\n",
        encoding="utf-8",
    )

    assert "stale_release_status" in _rules(tmp_path)


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "README_CN.md",
        "docs/releases/v0.1.1.md",
        "docs/how-to/verify-release.md",
    ],
)
def test_audit_rejects_consumer_smoke_wheel_wildcard(
    tmp_path: Path,
    path: str,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / path
    target.write_text(
        target.read_text(encoding="utf-8")
        + "\nuv run python scripts/release_consumer_smoke.py --wheel dist/*.whl --json\n",
        encoding="utf-8",
    )

    assert "consumer_smoke_wheel_selection" in _rules(tmp_path)


def test_audit_rejects_multiline_consumer_smoke_wheel_wildcard(
    tmp_path: Path,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "docs/how-to/verify-release.md"
    target.write_text(
        target.read_text(encoding="utf-8")
        + "\nuv run python scripts/release_consumer_smoke.py \\\n"
        "  --wheel dist/*.whl --json\n",
        encoding="utf-8",
    )

    assert "consumer_smoke_wheel_selection" in _rules(tmp_path)


def test_audit_does_not_apply_current_wheel_rule_to_v0_1_0_history(
    tmp_path: Path,
) -> None:
    _write_release_tree(tmp_path)
    historical = tmp_path / "docs/releases/v0.1.0.md"
    historical.write_text(
        "# v0.1.0\n\n"
        "uv run python scripts/release_consumer_smoke.py --wheel dist/*.whl --json\n",
        encoding="utf-8",
    )

    assert audit_release_presentation(tmp_path) == []


def test_audit_limits_current_wheel_rule_to_command_docs(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        changelog.read_text(encoding="utf-8")
        + "\nuv run python scripts/release_consumer_smoke.py --wheel dist/*.whl --json\n",
        encoding="utf-8",
    )

    assert audit_release_presentation(tmp_path) == []


@pytest.mark.parametrize(
    ("path", "stale_text"),
    [
        (
            "docs/releases/v0.1.1.md",
            "GitHub Release metadata records the final tag and target commit when Stage 3 "
            "creates the release from the verified commit.",
        ),
        (
            "docs/releases/v0.1.1.md",
            "This document describes release scope and verification before publication.",
        ),
        (
            "docs/releases/v0.1.1.md",
            "This document does not predeclare a future tag target.",
        ),
        (
            "docs/releases/v0.1.1.md",
            "Tag and GitHub Release publication remain a separate authorized Stage 3 action.",
        ),
        (
            "CHANGELOG.md",
            "Tag creation, GitHub Release publication, and PyPI publication remain separate "
            "Stage 3 authorization actions.",
        ),
    ],
)
def test_audit_rejects_post_release_stale_publication_status(
    tmp_path: Path,
    path: str,
    stale_text: str,
) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / path).write_text(
        "# v0.1.1\n\n"
        "Proof, demo, CLI, MCP, and retrieval evaluation docs are linked.\n"
        "E3-C dense, E3-D RRF, and E3-E reranker remain comparison-only evidence.\n"
        f"{stale_text}\n",
        encoding="utf-8",
    )

    assert "stale_release_status" in _rules(tmp_path)


def test_audit_allows_verify_release_generic_stage3_instructions(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "docs/how-to/verify-release.md").write_text(
        "# Verify Release\n\n"
        "After Stage 1 and Stage 2 merge, create the annotated tag and GitHub Release only "
        "with explicit authorization. Then verify the public archive from a clean temporary "
        "directory.\n",
        encoding="utf-8",
    )

    assert audit_release_presentation(tmp_path) == []


@pytest.mark.parametrize(
    "placeholder",
    [
        "Tag: to be created after smoke testing",
        "Release commit: to be filled from the tag",
        "TBD after release",
        "TODO fill release metadata",
        "placeholder for final release metadata",
    ],
)
def test_audit_rejects_unresolved_release_placeholders(
    tmp_path: Path,
    placeholder: str,
) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "docs/releases/v0.1.1.md").write_text(
        "# v0.1.1\n\n"
        "Proof, demo, CLI, MCP, and retrieval evaluation docs are linked.\n"
        "E3-C dense, E3-D RRF, and E3-E reranker remain comparison-only evidence.\n"
        f"{placeholder}\n",
        encoding="utf-8",
    )

    assert "stale_release_status" in _rules(tmp_path)


@pytest.mark.parametrize(
    "positioning_word",
    ["Career", "portfolio", "resume", "interview", "showcase"],
)
def test_audit_rejects_non_neutral_public_positioning(
    tmp_path: Path,
    positioning_word: str,
) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "README.md").write_text(
        (tmp_path / "README.md").read_text(encoding="utf-8")
        + f"\nThis release is a {positioning_word} artifact.\n",
        encoding="utf-8",
    )

    assert "public_boundary" in _rules(tmp_path)


def test_audit_rejects_private_paths_gstack_artifacts_credentials_and_tracebacks(
    tmp_path: Path,
) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "docs/releases/v0.1.1.md").write_text(
        "# v0.1.1\n\n/Users/mac/.gstack/rollout token=secret\nTraceback (most recent call last):\n",
        encoding="utf-8",
    )

    assert "public_boundary" in _rules(tmp_path)
