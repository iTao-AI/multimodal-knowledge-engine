from __future__ import annotations

from pathlib import Path

import pytest

from scripts.release_presentation_audit import audit_release_presentation


def _write_release_tree(root: Path) -> None:
    (root / "src/mke").mkdir(parents=True)
    (root / "docs/releases").mkdir(parents=True)
    (root / "docs/how-to").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "multimodal-knowledge-engine"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    (root / "src/mke/__init__.py").write_text('__version__ = "0.1.0"\n', encoding="utf-8")
    readme_en_text = """
# Multimodal Knowledge Engine

[English](./README.md) | [中文](./README_CN.md)

v0.1.0 ships `cjk-active-scan-overlap-v1` as the current owner-startup runtime.
E3-C dense, E3-D RRF, and E3-E reranker work are comparison-only evidence and are
not runtime strategies.

```mermaid
flowchart LR
    agent[Agent / CLI / MCP Client] --> app[MKE Application Service]
    app --> run[Ingest Run]
    run --> evidence[Evidence]
    evidence --> publication[Active Publication]
    publication --> search[Search / Ask]
    app --> store[SQLite Domain Store]
    app --> projection[Rebuildable Retrieval Projections]
```

## Verified in v0.1.0

| Capability | Evidence |
|---|---|
| Evidence lifecycle | Verified |
| text-layer PDF + short video fixture ingest | Verified |
| active-Publication Search | Verified |
| evidence-only Ask / insufficient_evidence | Verified |
| CLI + stdio MCP same application contract | Verified |
| cjk-active-scan-overlap-v1 default owner-startup strategy | Verified |
| proof/demo/installed-wheel consumer smoke | Verified |
"""
    readme_cn_text = """
# Multimodal Knowledge Engine

[English](./README.md) | [中文](./README_CN.md)

v0.1.0 ships `cjk-active-scan-overlap-v1` as the current owner-startup runtime.
E3-C dense, E3-D RRF, and E3-E reranker work are comparison-only evidence and are
not runtime strategies.

```mermaid
flowchart LR
    agent[Agent / CLI / MCP Client] --> app[MKE Application Service]
    app --> run[Ingest Run]
    run --> evidence[Evidence]
    evidence --> publication[Active Publication]
    publication --> search[Search / Ask]
    app --> store[SQLite Domain Store]
    app --> projection[Rebuildable Retrieval Projections]
```

## v0.1.0 已验证能力

| 能力 | 验证证据 |
|---|---|
| Evidence 生命周期 | Verified |
| text-layer PDF + short video fixture ingest | Verified |
| active-Publication Search | Verified |
| evidence-only Ask / insufficient_evidence | Verified |
| CLI + stdio MCP same application contract | Verified |
| cjk-active-scan-overlap-v1 default owner-startup strategy | Verified |
| proof/demo/installed-wheel consumer smoke | Verified |
"""
    (root / "README.md").write_text(readme_en_text, encoding="utf-8")
    (root / "README_CN.md").write_text(readme_cn_text, encoding="utf-8")
    (root / "docs/README.md").write_text(
        readme_en_text
        + "\nSee [v0.1.0](./releases/v0.1.0.md) and "
        "[Verify Release](./how-to/verify-release.md).\n",
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.1.0] - 2026-07-02\n\n"
        "Comparison-only dense/RRF/reranker evidence is not shipped runtime.\n",
        encoding="utf-8",
    )
    (root / "docs/releases/v0.1.0.md").write_text(
        "# v0.1.0\n\nProof, demo, CLI, MCP, and retrieval evaluation docs are linked.\n"
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
def test_audit_rejects_missing_verified_v010_table(tmp_path: Path, path: str) -> None:
    _write_release_tree(tmp_path)
    heading = "## Verified in v0.1.0" if path == "README.md" else "## v0.1.0 已验证能力"
    text = (tmp_path / path).read_text(encoding="utf-8").replace(
        heading,
        "## Release Scope",
    )
    (tmp_path / path).write_text(text, encoding="utf-8")

    assert "verified_v010_table" in _rules(tmp_path)


def test_audit_rejects_english_verified_labels_in_chinese_readme(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    text = (tmp_path / "README_CN.md").read_text(encoding="utf-8")
    text = text.replace("## v0.1.0 已验证能力", "## Verified in v0.1.0")
    text = text.replace("| 能力 | 验证证据 |", "| Capability | Evidence |")
    (tmp_path / "README_CN.md").write_text(text, encoding="utf-8")

    assert "verified_v010_table" in _rules(tmp_path)


def test_audit_rejects_chinese_verified_labels_in_english_readme(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    text = (tmp_path / "README.md").read_text(encoding="utf-8")
    text = text.replace("## Verified in v0.1.0", "## v0.1.0 已验证能力")
    text = text.replace("| Capability | Evidence |", "| 能力 | 验证证据 |")
    (tmp_path / "README.md").write_text(text, encoding="utf-8")

    assert "verified_v010_table" in _rules(tmp_path)


@pytest.mark.parametrize("path", ["README.md", "README_CN.md"])
def test_audit_rejects_missing_current_runtime_default(tmp_path: Path, path: str) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / path).write_text("v0.1.0 release notes\n", encoding="utf-8")

    assert "current_runtime_default" in _rules(tmp_path)


def test_audit_rejects_dense_rrf_or_reranker_runtime_claims(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "README.md").write_text(
        "[English](./README.md) | [中文](./README_CN.md)\n\n"
        "v0.1.0 ships `cjk-active-scan-overlap-v1`.\n"
        "```mermaid\nflowchart LR\n    app[MKE Application Service] --> search[Search / Ask]\n```\n"
        "## Verified in v0.1.0\n\n| Capability | Evidence |\n|---|---|\n| Proof | Verified |\n"
        "Dense retrieval, RRF, and reranker runtime support are available.\n",
        encoding="utf-8",
    )

    assert "comparison_runtime_overclaim" in _rules(tmp_path)


def test_audit_rejects_release_docs_presenting_comparison_candidates_as_runtime(
    tmp_path: Path,
) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "docs/releases/v0.1.0.md").write_text(
        "# v0.1.0\n\nProof, demo, CLI, MCP, and retrieval evaluation docs are linked.\n"
        "Dense/RRF/reranker runtime is part of this release.\n",
        encoding="utf-8",
    )

    assert "comparison_runtime_overclaim" in _rules(tmp_path)


def test_audit_requires_comparison_only_language_for_e3_candidates(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "docs/releases/v0.1.0.md").write_text(
        "# v0.1.0\n\nE3-C dense, E3-D RRF, and E3-E reranker are documented.\n",
        encoding="utf-8",
    )

    assert "comparison_only_boundary" in _rules(tmp_path)


def test_audit_rejects_stale_release_status_phrases(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "README.md").write_text(
        "v0.1.0 uses cjk-active-scan-overlap-v1. runtime_promotion_status=not_evaluated\n",
        encoding="utf-8",
    )

    assert "stale_release_status" in _rules(tmp_path)


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
    (tmp_path / "docs/releases/v0.1.0.md").write_text(
        "# v0.1.0\n\n"
        "Proof, demo, CLI, MCP, and retrieval evaluation docs are linked.\n"
        "E3-C dense, E3-D RRF, and E3-E reranker remain comparison-only evidence.\n"
        f"{placeholder}\n",
        encoding="utf-8",
    )

    assert "stale_release_status" in _rules(tmp_path)


def test_audit_rejects_private_paths_gstack_artifacts_credentials_and_tracebacks(
    tmp_path: Path,
) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "docs/releases/v0.1.0.md").write_text(
        "# v0.1.0\n\n/Users/mac/.gstack/rollout token=secret\nTraceback (most recent call last):\n",
        encoding="utf-8",
    )

    assert "public_boundary" in _rules(tmp_path)
