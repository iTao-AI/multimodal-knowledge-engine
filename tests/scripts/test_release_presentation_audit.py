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
    readme_text = """
# Multimodal Knowledge Engine

v0.1.0 ships `cjk-active-scan-overlap-v1` as the current owner-startup runtime.
E3-C dense, E3-D RRF, and E3-E reranker work are comparison-only evidence and are
not runtime strategies.
"""
    (root / "README.md").write_text(readme_text, encoding="utf-8")
    (root / "README_CN.md").write_text(readme_text, encoding="utf-8")
    (root / "docs/README.md").write_text(
        readme_text
        + "\nSee [v0.1.0](./releases/v0.1.0.md) and [Verify Release](./how-to/verify-release.md).\n",
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.1.0] - 2026-07-02\n\nComparison-only dense/RRF/reranker evidence is not shipped runtime.\n",
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
def test_audit_rejects_missing_current_runtime_default(tmp_path: Path, path: str) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / path).write_text("v0.1.0 release notes\n", encoding="utf-8")

    assert "current_runtime_default" in _rules(tmp_path)


def test_audit_rejects_dense_rrf_or_reranker_runtime_claims(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "README.md").write_text(
        "v0.1.0 ships `cjk-active-scan-overlap-v1`.\n"
        "Dense retrieval, RRF, and reranker runtime support are available.\n",
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


def test_audit_rejects_private_paths_gstack_artifacts_credentials_and_tracebacks(
    tmp_path: Path,
) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "docs/releases/v0.1.0.md").write_text(
        "# v0.1.0\n\n/Users/mac/.gstack/rollout token=secret\nTraceback (most recent call last):\n",
        encoding="utf-8",
    )

    assert "public_boundary" in _rules(tmp_path)
