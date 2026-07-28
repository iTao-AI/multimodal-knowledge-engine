from __future__ import annotations

from pathlib import Path

import pytest

from scripts.release_presentation_audit import audit_release_presentation

ROOT = Path(__file__).resolve().parents[2]

COMPLETE_PUBLICATION_VERIFICATION = """
## Publication verification

- Tag: `v0.1.5`
- Merge commit: `1234567890abcdef1234567890abcdef12345678`
- Merge tree: `234567890abcdef1234567890abcdef123456789`
- GitHub Release URL: https://github.com/iTao-AI/multimodal-knowledge-engine/releases/tag/v0.1.5
- Published timestamp: `2026-07-28T12:34:56Z`
- Assets: zero
- Hosted checks: all required checks passed on the merge commit
- Archive descriptor SHA-256: `34567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12`
- Archive manifest SHA-256: `4567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef123`
- Archive wheel: `multimodal_knowledge_engine-0.1.5-py3-none-any.whl`
- Git-less allowlist: passed
- Exact-main proof: passed
- Canonical evidence hashes: unchanged
- Temporary compatibility: seven families with all six delta classes zero
- Limitations and non-claims: no retrieval-quality, performance, deployment, or adoption claim
"""


def test_audit_targets_v0_1_5_release_identity() -> None:
    from scripts import release_presentation_audit as audit

    assert audit.EXPECTED_VERSION == "0.1.5"
    assert "docs/releases/v0.1.5.md" in audit.RELEASE_FACING_FILES
    assert "docs/releases/v0.1.4.md" in audit.HISTORICAL_RELEASE_FILES
    assert callable(audit.__dict__["_audit_v014_contract"])
    assert callable(audit.__dict__["_audit_v015_contract"])
    assert "docs/releases/v0.1.3.md" in audit.HISTORICAL_RELEASE_FILES
    assert "docs/releases/v0.1.2.md" in audit.HISTORICAL_RELEASE_FILES
    assert "docs/releases/v0.1.0.md" not in audit.RELEASE_FACING_FILES
    assert "docs/releases/v0.1.1.md" not in audit.RELEASE_FACING_FILES


def test_audit_targets_current_build_wheel_command_docs() -> None:
    from scripts import release_presentation_audit as audit

    assert audit.CURRENT_BUILD_WHEEL_COMMAND_FILES == (
        "docs/how-to/prepare-local-embeddings.md",
        "docs/how-to/evaluate-dense-retrieval.md",
        "docs/how-to/enable-cjk-retrieval.md",
        "docs/how-to/evaluate-numeric-retrieval.md",
        "docs/how-to/run-chinese-retrieval-evaluation.md",
    )


def test_current_build_wheel_command_docs_use_v0_1_5() -> None:
    current_wheel = "multimodal_knowledge_engine-0.1.5-py3-none-any.whl"
    stale_wheel = "multimodal_knowledge_engine-0.1.3-py3-none-any.whl"
    paths = (
        "docs/how-to/prepare-local-embeddings.md",
        "docs/how-to/evaluate-dense-retrieval.md",
        "docs/how-to/enable-cjk-retrieval.md",
        "docs/how-to/evaluate-numeric-retrieval.md",
        "docs/how-to/run-chinese-retrieval-evaluation.md",
    )

    for relative in paths:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert current_wheel in text
        assert stale_wheel not in text


def _write_release_tree(root: Path) -> None:
    (root / "src/mke").mkdir(parents=True)
    (root / "docs/releases").mkdir(parents=True)
    (root / "docs/how-to").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "multimodal-knowledge-engine"\nversion = "0.1.2"\n',
        encoding="utf-8",
    )
    (root / "src/mke/__init__.py").write_text('__version__ = "0.1.2"\n', encoding="utf-8")
    readme_en_text = """
# Multimodal Knowledge Engine

[English](./README.md) | [中文](./README_CN.md)

v0.1.2 ships `cjk-active-scan-overlap-v1` as the current owner-startup runtime.
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

## Verified in v0.1.2

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
| Evidence provenance with strict `mke.evidence_ref.v1` | Verified |
| external source-pack proof with the same wheel on Python 3.12/3.13 | Verified |
| owner lifecycle and runtime hardening | Verified |

## What this release proves

MKE v0.1.2 exercises the Evidence lifecycle, active Publication, CLI/MCP application
service contract, and retrieval evaluation artifacts.

Evidence provenance, the external source-pack proof, same-wheel Python 3.12/3.13
validation, and owner lifecycle and runtime hardening are release evidence.
OCR remains excluded.

| Retrieval evidence | v0.1.2 status | Boundary |
|---|---|---|
| Shipped runtime | lexical search and cjk-active-scan-overlap-v1 active scan | Active Evidence |
| Comparison-only evidence | dense, RRF, relevance gate / reranker | Runtime neutral |
| Not included | query rewrite, HyDE, OCR, HTTP/UI, API adapters | not v0.1.2 runtime behavior |

Search/Ask/MCP read active Publication Evidence.
This does not change normal Search, Ask, MCP, or the runtime default.

`uv run python scripts/release_consumer_smoke.py \
  --wheel dist/multimodal_knowledge_engine-0.1.2-py3-none-any.whl --json`
"""
    readme_cn_text = """
# Multimodal Knowledge Engine

[English](./README.md) | [中文](./README_CN.md)

v0.1.2 ships `cjk-active-scan-overlap-v1` as the current owner-startup runtime.
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

## v0.1.2 已验证能力

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
| Evidence provenance with strict `mke.evidence_ref.v1` | Verified |
| external source-pack proof with the same wheel on Python 3.12/3.13 | Verified |
| owner lifecycle and runtime hardening | Verified |

## v0.1.2 工程深度

MKE v0.1.2 验证 Evidence 生命周期、active Publication、CLI/MCP application
service contract，以及 retrieval evaluation artifacts。

Evidence provenance、external source-pack proof、same-wheel Python 3.12/3.13
validation，以及 owner lifecycle and runtime hardening 都是 release evidence。OCR 仍排除。

| Retrieval evidence | v0.1.2 状态 | 边界 |
|---|---|---|
| 已发布 runtime | lexical search 和 cjk-active-scan-overlap-v1 active scan | Active Evidence |
| Comparison-only evidence | dense、RRF、relevance gate / reranker | Runtime neutral |
| 不包含 | query rewrite、HyDE、OCR、HTTP/UI、API adapters | 不是 v0.1.2 runtime behavior |

Search/Ask/MCP 读取 active Publication Evidence。
不改变 normal Search、Ask、MCP 或 runtime default。

`uv run python scripts/release_consumer_smoke.py \
  --wheel dist/multimodal_knowledge_engine-0.1.2-py3-none-any.whl --json`
"""
    (root / "README.md").write_text(readme_en_text, encoding="utf-8")
    (root / "README_CN.md").write_text(readme_cn_text, encoding="utf-8")
    (root / "docs/README.md").write_text(
        readme_en_text + "\nSee [v0.1.2](./releases/v0.1.2.md) and "
        "`dist/multimodal_knowledge_engine-0.1.2-py3-none-any.whl` and "
        "[Verify Release](./how-to/verify-release.md).\n",
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.1.2] - 2026-07-14\n\n"
        "Evidence provenance and external source-pack proof ship with owner/runtime "
        "hardening. Same-wheel Python 3.12/3.13 evidence uses mke.evidence_ref.v1. "
        "OCR is excluded; dense/RRF/reranker evidence remains comparison-only.\n",
        encoding="utf-8",
    )
    (root / "docs/releases/v0.1.2.md").write_text(
        "# v0.1.2\n\nProof, demo, CLI, MCP, local knowledge proof, and retrieval "
        "evaluation docs are linked. Evidence provenance uses strict mke.evidence_ref.v1. "
        "The external source-pack proof validates the same wheel on Python 3.12/3.13, "
        "with owner lifecycle and runtime hardening. OCR remains excluded.\n"
        "E3-C dense, E3-D RRF, and E3-E reranker remain comparison-only evidence.\n\n"
        "An independent consumer validated a pre-release candidate from synthetic fixtures "
        "and a strict receipt at https://github.com/iTao-AI/night-voyager/pull/21, bound "
        "to source commit 16fae017ced5fe67da3fae4a01f26e9e9f1084aa. This did not "
        "validate the final v0.1.2 wheel and does not prove production adoption, hosted "
        "deployment, or real-user outcomes. Night Voyager remains an independent consumer "
        "and is not an MKE CI dependency. An identity-only release does not require a "
        "downstream lock update.\n\n"
        "`uv run python scripts/release_consumer_smoke.py --wheel "
        "dist/multimodal_knowledge_engine-0.1.2-py3-none-any.whl --json`\n",
        encoding="utf-8",
    )
    (root / "docs/how-to/verify-release.md").write_text(
        "# Verify Release\n\nRun `mke proof run` and `mke demo --verify`.\n"
        "`uv run python scripts/release_consumer_smoke.py --wheel "
        "dist/multimodal_knowledge_engine-0.1.2-py3-none-any.whl --json`\n",
        encoding="utf-8",
    )
    for relative in (
        "pyproject.toml",
        "src/mke/__init__.py",
        "README.md",
        "README_CN.md",
        "docs/README.md",
        "CHANGELOG.md",
        "docs/how-to/verify-release.md",
    ):
        path = root / relative
        path.write_text(
            path.read_text(encoding="utf-8").replace("0.1.2", "0.1.3"),
            encoding="utf-8",
        )
    historical = root / "docs/releases/v0.1.2.md"
    (root / "docs/releases/v0.1.3.md").write_text(
        historical.read_text(encoding="utf-8").replace("0.1.2", "0.1.3")
        + "\n## Compiled Library Export\n\n"
        "`mke.compiled_library_export.v1`, `mke.compiled_markdown.v1`, and "
        "`mke.evidence_ref.v1` are portable boundaries.\n\n"
        "## OCR Phase 0\n\nPP-OCRv6 medium is the selected planning baseline; "
        "PaddleOCR-VL 1.6 is a comparison candidate. This is not production OCR. "
        "LLM Wiki compatibility is deferred. `cjk-active-scan-overlap-v1` remains default.\n",
        encoding="utf-8",
    )
    for relative in (
        "pyproject.toml",
        "src/mke/__init__.py",
        "README.md",
        "README_CN.md",
        "docs/README.md",
        "CHANGELOG.md",
        "docs/how-to/verify-release.md",
    ):
        path = root / relative
        path.write_text(
            path.read_text(encoding="utf-8").replace("0.1.3", "0.1.4"),
            encoding="utf-8",
        )
    (root / "docs/releases/v0.1.4.md").write_text(
        "# v0.1.4\n\n"
        "Proof, demo, CLI, MCP, local knowledge proof, and retrieval evaluation docs are linked.\n"
        "Bounded direct audio releases MP3, WAV/PCM, and M4A/AAC intake for clips up to "
        "15 minutes and 100 MiB on Darwin arm64 through an explicitly prepared cache-only "
        "faster-whisper owner.\n\n"
        "Python, CLI, and stdio MCP publish timestamp Evidence to an active Publication for "
        "Search/Ask and explicit Compiled Library Export v2 consumption.\n\n"
        "Export v1 remains compatible for PDF/video-only Libraries; LLM Wiki compatibility is "
        "isolated downstream evidence and MKE does not bundle or automatically integrate LLM "
        "Wiki.\n\n"
        "MKE does not redistribute external wheels or native binaries.\n\n"
        "The GitHub Release has zero extra assets. There is no PyPI or package registry "
        "publication.\n\n"
        "MKE has no hosted deployment and is not deployed in production. MKE does not claim "
        "production adoption or business impact.\n\n"
        "MKE does not claim transcript accuracy, a production SLA, or cross-platform support, "
        "and does not download a model implicitly or fall back to cloud ASR.\n\n"
        "`cjk-active-scan-overlap-v1` remains the runtime default and retrieval candidates remain "
        "comparison-only.\n\n"
        "`uv run python scripts/release_consumer_smoke.py --wheel "
        "dist/multimodal_knowledge_engine-0.1.4-py3-none-any.whl --json`\n",
        encoding="utf-8",
    )
    current_release = (
        (root / "docs/releases/v0.1.4.md")
        .read_text(encoding="utf-8")
        .replace("v0.1.4", "v0.1.5")
        .replace("0.1.4-py3", "0.1.5-py3")
    )
    current_release += (
        "\nsearch_library_v2 complete more_available capped read_evidence_v1 "
        "evidence_text_sha256 active Publication ten tools deterministic "
        "Source-byte-bound revision 2 legacy v1 no runtime promotion "
        "source archive or checkout zero assets no PyPI cache-warmed\n"
    )
    (root / "docs/releases/v0.1.5.md").write_text(current_release, encoding="utf-8")
    for relative in (
        "pyproject.toml",
        "src/mke/__init__.py",
        "README.md",
        "README_CN.md",
        "docs/README.md",
        "CHANGELOG.md",
        "docs/how-to/verify-release.md",
    ):
        path = root / relative
        text = path.read_text(encoding="utf-8")
        if relative in {"pyproject.toml", "src/mke/__init__.py"}:
            text = text.replace("0.1.4", "0.1.5")
        else:
            text = text.replace("0.1.4-py3", "0.1.5-py3")
            text += "\nCurrent release: v0.1.5.\n"
            if relative == "CHANGELOG.md":
                text = text.replace(
                    "# Changelog\n\n",
                    "# Changelog\n\n## [0.1.5] - 2026-07-28\n\n"
                    "Current release: v0.1.5.\n\n",
                    1,
                )
            elif relative == "docs/how-to/verify-release.md":
                text += (
                    "\n## Completed v0.1.4 Release Record\n\n"
                    "Immutable historical v0.1.4 facts.\n"
                )
        path.write_text(text, encoding="utf-8")


def _rules(root: Path) -> set[str]:
    return {violation.rule for violation in audit_release_presentation(root)}


def _append_current_surface_text(target: Path, addition: str) -> None:
    text = target.read_text(encoding="utf-8").rstrip()
    marker = None
    if target.name == "CHANGELOG.md":
        marker = "## [0.1.4]"
    elif target.name == "verify-release.md":
        marker = "## Completed v0.1.4 Release Record"
    if marker is None:
        updated = f"{text}\n\n{addition}\n"
    else:
        current, historical = text.split(marker, maxsplit=1)
        updated = f"{current.rstrip()}\n\n{addition}\n\n{marker}{historical}\n"
    target.write_text(updated, encoding="utf-8")


def test_audit_accepts_complete_release_presentation(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)

    assert audit_release_presentation(tmp_path) == []


@pytest.mark.parametrize(
    "claim",
    [
        "This release improves relevance, recall, and precision.",
        "This release improves recall.",
        "This release improves precision.",
        "This release improves latency.",
        "This release improves throughput.",
        "Agents get faster retrieval with lower latency and higher throughput.",
        "Search is exhaustive across the corpus and returns total counts.",
        "Search returns total counts.",
        "Segmentation and contextual-retrieval quality are improved.",
        "Segmentation quality is improved.",
        "Contextual-retrieval quality is improved.",
        "Offline installation works from an empty machine with a cold cache.",
        "Offline installation works with a cold cache.",
        "Offline installation works on an empty machine.",
        "Dense retrieval is promoted into the runtime.",
        "RRF is promoted into the runtime.",
        "The reranker is promoted into the runtime.",
        "MKE is deployed in production with user adoption and business value.",
        "MKE has production adoption.",
        "MKE delivers business value.",
        "GraphRAG ships in this release.",
        "OCR runtime ships in this release.",
        "An Agent loop ships in this release.",
        "HTTP/SaaS ships in this release.",
        "A new provider ships in this release.",
        "MKE is published on PyPI.",
        "Uploaded Release assets are included.",
        "We verified that this release delivers faster Agent retrieval.",
    ],
)
def test_audit_rejects_v015_affirmative_or_wrapped_overclaims(
    tmp_path: Path,
    claim: str,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "docs/releases/v0.1.5.md"
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n{claim}\n",
        encoding="utf-8",
    )

    assert "v015_release_overclaim" in _rules(tmp_path)


@pytest.mark.parametrize(
    "safe_boundary",
    [
        "MKE does not improve relevance, recall, or precision.",
        "Search is not exhaustive and does not return total counts.",
        "Dense, RRF, and reranker are not runtime features.",
        "Cold-cache and empty-machine offline installation are not claimed.",
        "MKE does not provide production deployment, real-user adoption, or business value.",
        "GraphRAG, OCR runtime, an Agent loop, HTTP/SaaS, providers, PyPI, and uploaded assets "
        "remain excluded.",
    ],
)
def test_audit_preserves_v015_negated_non_claims(
    tmp_path: Path,
    safe_boundary: str,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "docs/releases/v0.1.5.md"
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n{safe_boundary}\n",
        encoding="utf-8",
    )

    assert "v015_release_overclaim" not in _rules(tmp_path)


def test_audit_accepts_absent_publication_verification(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)

    assert "v015_publication_verification" not in _rules(tmp_path)


def test_audit_accepts_shape_valid_complete_publication_verification(
    tmp_path: Path,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "docs/releases/v0.1.5.md"
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n"
        f"{COMPLETE_PUBLICATION_VERIFICATION.strip()}\n",
        encoding="utf-8",
    )

    assert "v015_publication_verification" not in _rules(tmp_path)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("- Tag: `v0.1.5`", "- Tag: `v0.1.4`"),
        (
            "- Merge commit: `1234567890abcdef1234567890abcdef12345678`",
            "- Merge commit: `not-a-commit`",
        ),
        (
            "- Merge commit: `1234567890abcdef1234567890abcdef12345678`",
            "- Merge commit: `1234567890ABCDEF1234567890ABCDEF12345678`",
        ),
        (
            "- Merge tree: `234567890abcdef1234567890abcdef123456789`",
            "- Merge tree: `234567890abcdef1234567890abcdef12345678`",
        ),
        (
            "- GitHub Release URL: "
            "https://github.com/iTao-AI/multimodal-knowledge-engine/releases/tag/v0.1.5",
            "- GitHub Release URL: "
            "https://github.com/iTao-AI/multimodal-knowledge-engine/releases/tag/v0.1.4",
        ),
        (
            "- Published timestamp: `2026-07-28T12:34:56Z`",
            "- Published timestamp: `2026-07-28 12:34:56+00:00`",
        ),
        ("- Assets: zero", "- Assets: one"),
        (
            "- Archive descriptor SHA-256: "
            "`34567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12`",
            "- Archive descriptor SHA-256: `x`",
        ),
        (
            "- Archive manifest SHA-256: "
            "`4567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef123`",
            "- Archive manifest SHA-256: "
            "`4567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF123`",
        ),
        (
            "- Archive wheel: `multimodal_knowledge_engine-0.1.5-py3-none-any.whl`",
            "- Archive wheel: `multimodal_knowledge_engine-0.1.4-py3-none-any.whl`",
        ),
        (
            "- Hosted checks: all required checks passed on the merge commit",
            "- Hosted checks:",
        ),
        ("- Git-less allowlist: passed", "- Git-less allowlist:"),
        ("- Exact-main proof: passed", "- Exact-main proof:"),
        ("- Canonical evidence hashes: unchanged", "- Canonical evidence hashes:"),
        (
            "- Temporary compatibility: seven families with all six delta classes zero",
            "- Temporary compatibility:",
        ),
        (
            "- Limitations and non-claims: "
            "no retrieval-quality, performance, deployment, or adoption claim",
            "- Limitations and non-claims:",
        ),
    ],
)
def test_audit_rejects_malformed_or_empty_publication_facts(
    tmp_path: Path,
    old: str,
    new: str,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "docs/releases/v0.1.5.md"
    malformed = COMPLETE_PUBLICATION_VERIFICATION.replace(old, new, 1)
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n{malformed.strip()}\n",
        encoding="utf-8",
    )

    assert "v015_publication_verification" in _rules(tmp_path)


@pytest.mark.parametrize(
    "label",
    [
        "Tag",
        "Merge commit",
        "Merge tree",
        "GitHub Release URL",
        "Published timestamp",
        "Assets",
        "Hosted checks",
        "Archive descriptor SHA-256",
        "Archive manifest SHA-256",
        "Archive wheel",
        "Git-less allowlist",
        "Exact-main proof",
        "Canonical evidence hashes",
        "Temporary compatibility",
        "Limitations and non-claims",
    ],
)
def test_audit_rejects_duplicate_publication_labels(
    tmp_path: Path,
    label: str,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "docs/releases/v0.1.5.md"
    duplicate = next(
        line
        for line in COMPLETE_PUBLICATION_VERIFICATION.splitlines()
        if line.startswith(f"- {label}:")
    )
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n"
        f"{COMPLETE_PUBLICATION_VERIFICATION.strip()}\n{duplicate}\n",
        encoding="utf-8",
    )

    assert "v015_publication_verification" in _rules(tmp_path)


@pytest.mark.parametrize(
    "label",
    [
        "Tag",
        "Merge commit",
        "Merge tree",
        "GitHub Release URL",
        "Published timestamp",
        "Assets",
        "Hosted checks",
        "Archive descriptor SHA-256",
        "Archive manifest SHA-256",
        "Archive wheel",
        "Git-less allowlist",
        "Exact-main proof",
        "Canonical evidence hashes",
        "Temporary compatibility",
        "Limitations and non-claims",
    ],
)
def test_audit_rejects_missing_publication_labels(
    tmp_path: Path,
    label: str,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "docs/releases/v0.1.5.md"
    incomplete = "\n".join(
        line
        for line in COMPLETE_PUBLICATION_VERIFICATION.splitlines()
        if not line.startswith(f"- {label}:")
    )
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n{incomplete.strip()}\n",
        encoding="utf-8",
    )

    assert "v015_publication_verification" in _rules(tmp_path)


@pytest.mark.parametrize(
    "invalid_value",
    ["TBD", "TODO", "<placeholder>", "to be filled", "x" * 501],
)
def test_audit_rejects_placeholder_or_unbounded_publication_values(
    tmp_path: Path,
    invalid_value: str,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "docs/releases/v0.1.5.md"
    malformed = COMPLETE_PUBLICATION_VERIFICATION.replace(
        "all required checks passed on the merge commit",
        invalid_value,
    )
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n{malformed.strip()}\n",
        encoding="utf-8",
    )

    assert "v015_publication_verification" in _rules(tmp_path)


@pytest.mark.parametrize(
    ("old", "label"),
    [
        (
            "- Hosted checks: all required checks passed on the merge commit",
            "Hosted checks",
        ),
        ("- Git-less allowlist: passed", "Git-less allowlist"),
        ("- Exact-main proof: passed", "Exact-main proof"),
        ("- Canonical evidence hashes: unchanged", "Canonical evidence hashes"),
        (
            "- Temporary compatibility: seven families with all six delta classes zero",
            "Temporary compatibility",
        ),
        (
            "- Limitations and non-claims: "
            "no retrieval-quality, performance, deployment, or adoption claim",
            "Limitations and non-claims",
        ),
    ],
)
def test_audit_rejects_semantically_empty_markdown_publication_values(
    tmp_path: Path,
    old: str,
    label: str,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "docs/releases/v0.1.5.md"
    malformed = COMPLETE_PUBLICATION_VERIFICATION.replace(
        old,
        f"- {label}:   ``  ",
        1,
    )
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n{malformed.strip()}\n",
        encoding="utf-8",
    )

    assert "v015_publication_verification" in _rules(tmp_path)


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-99-99T99:99:99Z",
        "2026-02-30T12:34:56Z",
        "2026-07-28T24:00:00Z",
    ],
)
def test_audit_rejects_impossible_utc_publication_timestamp(
    tmp_path: Path,
    timestamp: str,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "docs/releases/v0.1.5.md"
    malformed = COMPLETE_PUBLICATION_VERIFICATION.replace(
        "`2026-07-28T12:34:56Z`",
        f"`{timestamp}`",
        1,
    )
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n{malformed.strip()}\n",
        encoding="utf-8",
    )

    assert "v015_publication_verification" in _rules(tmp_path)


@pytest.mark.parametrize(
    ("old", "zero_identity"),
    [
        ("`1234567890abcdef1234567890abcdef12345678`", "`" + "0" * 40 + "`"),
        ("`234567890abcdef1234567890abcdef123456789`", "`" + "0" * 40 + "`"),
        (
            "`34567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12`",
            "`" + "0" * 64 + "`",
        ),
        (
            "`4567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef123`",
            "`" + "0" * 64 + "`",
        ),
    ],
)
def test_audit_rejects_all_zero_publication_identities(
    tmp_path: Path,
    old: str,
    zero_identity: str,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "docs/releases/v0.1.5.md"
    malformed = COMPLETE_PUBLICATION_VERIFICATION.replace(old, zero_identity, 1)
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n{malformed.strip()}\n",
        encoding="utf-8",
    )

    assert "v015_publication_verification" in _rules(tmp_path)


def test_audit_rejects_retained_malformed_publication_diagnostic(
    tmp_path: Path,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "docs/releases/v0.1.5.md"
    malformed = (
        COMPLETE_PUBLICATION_VERIFICATION.replace(
            "`1234567890abcdef1234567890abcdef12345678`",
            "`not-a-commit`",
        )
        .replace(
            "`34567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12`",
            "`x`",
        )
        .replace(
            "- Hosted checks: all required checks passed on the merge commit",
            "- Hosted checks:",
        )
    )
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n{malformed.strip()}\n",
        encoding="utf-8",
    )

    assert "v015_publication_verification" in _rules(tmp_path)


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "README_CN.md",
        "docs/README.md",
        "CHANGELOG.md",
        "docs/releases/v0.1.5.md",
        "docs/how-to/verify-release.md",
    ],
)
def test_audit_rejects_current_overclaim_on_every_release_facing_surface(
    tmp_path: Path,
    path: str,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / path
    _append_current_surface_text(
        target,
        "This release improves recall and throughput.",
    )

    violations = audit_release_presentation(tmp_path)
    assert any(
        violation.rule == "v015_release_overclaim" and violation.file == path
        for violation in violations
    )


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "README_CN.md",
        "docs/README.md",
        "CHANGELOG.md",
        "docs/releases/v0.1.5.md",
        "docs/how-to/verify-release.md",
    ],
)
def test_audit_accepts_matched_negated_control_on_every_current_surface(
    tmp_path: Path,
    path: str,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / path
    _append_current_surface_text(
        target,
        "This release does not improve recall or throughput.",
    )

    assert not any(
        violation.rule == "v015_release_overclaim" and violation.file == path
        for violation in audit_release_presentation(tmp_path)
    )


@pytest.mark.parametrize("path", ["CHANGELOG.md", "docs/how-to/verify-release.md"])
def test_audit_does_not_treat_historical_v014_record_as_current_overclaim(
    tmp_path: Path,
    path: str,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / path
    text = target.read_text(encoding="utf-8")
    if path == "CHANGELOG.md":
        text = text.replace(
            "## [0.1.4]",
            "## [0.1.4]\n\nThis release improves recall and throughput.",
            1,
        )
    else:
        text += "\nThis release improves recall and throughput.\n"
    target.write_text(text, encoding="utf-8")

    assert not any(
        violation.rule == "v015_release_overclaim" and violation.file == path
        for violation in audit_release_presentation(tmp_path)
    )


def test_audit_rejects_version_mismatch(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "src/mke/__init__.py").write_text('__version__ = "0.0.0"\n', encoding="utf-8")

    assert "version_identity" in _rules(tmp_path)


@pytest.mark.parametrize("path", ["README.md", "README_CN.md"])
def test_audit_rejects_missing_top_language_switch(tmp_path: Path, path: str) -> None:
    _write_release_tree(tmp_path)
    text = (
        (tmp_path / path)
        .read_text(encoding="utf-8")
        .replace(
            "[English](./README.md) | [中文](./README_CN.md)\n\n",
            "",
        )
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
def test_audit_rejects_missing_verified_v014_table(tmp_path: Path, path: str) -> None:
    _write_release_tree(tmp_path)
    heading = "## Verified in v0.1.4" if path == "README.md" else "## v0.1.4 已验证能力"
    text = (
        (tmp_path / path)
        .read_text(encoding="utf-8")
        .replace(
            heading,
            "## Release Scope",
        )
    )
    (tmp_path / path).write_text(text, encoding="utf-8")

    assert "verified_v014_table" in _rules(tmp_path)


@pytest.mark.parametrize("path", ["README.md", "README_CN.md"])
def test_audit_rejects_shallow_readme_engineering_depth(tmp_path: Path, path: str) -> None:
    _write_release_tree(tmp_path)
    marker = "## What this release proves" if path == "README.md" else "## v0.1.4 工程深度"
    text = (
        (tmp_path / path)
        .read_text(encoding="utf-8")
        .replace(
            marker,
            "## Notes",
        )
    )
    (tmp_path / path).write_text(text, encoding="utf-8")

    assert "readme_engineering_depth" in _rules(tmp_path)


@pytest.mark.parametrize("path", ["README.md", "README_CN.md"])
def test_audit_rejects_missing_retrieval_evidence_table(tmp_path: Path, path: str) -> None:
    _write_release_tree(tmp_path)
    text = (
        (tmp_path / path)
        .read_text(encoding="utf-8")
        .replace(
            "Comparison-only evidence",
            "Candidate observations",
        )
    )
    (tmp_path / path).write_text(text, encoding="utf-8")

    assert "readme_engineering_depth" in _rules(tmp_path)


@pytest.mark.parametrize(
    "term",
    [
        "Evidence provenance",
        "mke.evidence_ref.v1",
        "external source-pack proof",
        "same-wheel Python 3.12/3.13",
        "owner lifecycle and runtime hardening",
        "OCR remains excluded",
    ],
)
def test_audit_rejects_missing_v014_capability_term(tmp_path: Path, term: str) -> None:
    _write_release_tree(tmp_path)
    for path in ("README.md", "README_CN.md"):
        target = tmp_path / path
        target.write_text(
            target.read_text(encoding="utf-8").replace(term, "removed release term"),
            encoding="utf-8",
        )

    assert "readme_engineering_depth" in _rules(tmp_path)


def test_audit_rejects_english_verified_labels_in_chinese_readme(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    text = (tmp_path / "README_CN.md").read_text(encoding="utf-8")
    text = text.replace("## v0.1.4 已验证能力", "## Verified in v0.1.4")
    text = text.replace("| 能力 | 验证证据 |", "| Capability | Evidence |")
    (tmp_path / "README_CN.md").write_text(text, encoding="utf-8")

    assert "verified_v014_table" in _rules(tmp_path)


def test_audit_rejects_chinese_verified_labels_in_english_readme(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    text = (tmp_path / "README.md").read_text(encoding="utf-8")
    text = text.replace("## Verified in v0.1.4", "## v0.1.4 已验证能力")
    text = text.replace("| Capability | Evidence |", "| 能力 | 验证证据 |")
    (tmp_path / "README.md").write_text(text, encoding="utf-8")

    assert "verified_v014_table" in _rules(tmp_path)


@pytest.mark.parametrize("path", ["README.md", "README_CN.md"])
def test_audit_rejects_missing_current_runtime_default(tmp_path: Path, path: str) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / path).write_text("v0.1.4 release notes\n", encoding="utf-8")

    assert "current_runtime_default" in _rules(tmp_path)


def test_audit_rejects_dense_rrf_or_reranker_runtime_claims(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "README.md").write_text(
        "[English](./README.md) | [中文](./README_CN.md)\n\n"
        "v0.1.4 ships `cjk-active-scan-overlap-v1`.\n"
        "```mermaid\nflowchart LR\n    app[MKE Application Service] --> search[Search / Ask]\n```\n"
        "## Verified in v0.1.4\n\n| Capability | Evidence |\n|---|---|\n| Proof | Verified |\n"
        "Dense retrieval, RRF, and reranker runtime support are available.\n",
        encoding="utf-8",
    )

    assert "comparison_runtime_overclaim" in _rules(tmp_path)


def test_audit_rejects_release_docs_presenting_comparison_candidates_as_runtime(
    tmp_path: Path,
) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "docs/releases/v0.1.5.md").write_text(
        "# v0.1.5\n\nProof, demo, CLI, MCP, and retrieval evaluation docs are linked.\n"
        "Dense/RRF/reranker runtime is part of this release.\n",
        encoding="utf-8",
    )

    assert "comparison_runtime_overclaim" in _rules(tmp_path)


def test_audit_requires_comparison_only_language_for_e3_candidates(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "docs/releases/v0.1.5.md").write_text(
        "# v0.1.5\n\nE3-C dense, E3-D RRF, and E3-E reranker are documented.\n",
        encoding="utf-8",
    )

    assert "comparison_only_boundary" in _rules(tmp_path)


def test_audit_rejects_stale_release_status_phrases(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "README.md").write_text(
        "v0.1.4 uses cjk-active-scan-overlap-v1. runtime_promotion_status=not_evaluated\n",
        encoding="utf-8",
    )

    assert "stale_release_status" in _rules(tmp_path)


def test_audit_rejects_stale_stage2_changelog_gate(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.1.2] - 2026-07-14\n\n"
        "Stage 2 installed-package consumer smoke, tag creation, and GitHub Release "
        "publication are separate gates after this presentation-readiness work merges.\n",
        encoding="utf-8",
    )

    assert "stale_release_status" in _rules(tmp_path)


def test_audit_rejects_separate_branch_stage2_wording(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "docs/how-to/verify-release.md").write_text(
        "# Verify Release\n\nStage 2 must run from a separate branch after Stage 1 merges.\n",
        encoding="utf-8",
    )

    assert "stale_release_status" in _rules(tmp_path)


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "README_CN.md",
        "docs/releases/v0.1.5.md",
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


def test_audit_rejects_old_exact_consumer_smoke_wheel(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "docs/how-to/verify-release.md"
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            "dist/multimodal_knowledge_engine-0.1.5-py3-none-any.whl",
            "dist/multimodal_knowledge_engine-0.1.2-py3-none-any.whl",
        ),
        encoding="utf-8",
    )

    assert "consumer_smoke_wheel_selection" in _rules(tmp_path)


def test_audit_rejects_old_current_build_wheel(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "docs/how-to/prepare-local-embeddings.md"
    target.write_text(
        "uv pip install "
        "\"dist/multimodal_knowledge_engine-0.1.3-py3-none-any.whl[embedding]\"\n",
        encoding="utf-8",
    )

    assert "current_build_wheel_selection" in _rules(tmp_path)


def test_audit_does_not_apply_current_wheel_rule_to_v0_1_0_history(
    tmp_path: Path,
) -> None:
    _write_release_tree(tmp_path)
    historical = tmp_path / "docs/releases/v0.1.0.md"
    historical.write_text(
        "# v0.1.0\n\nuv run python scripts/release_consumer_smoke.py --wheel dist/*.whl --json\n",
        encoding="utf-8",
    )

    assert audit_release_presentation(tmp_path) == []


def test_audit_does_not_apply_current_wheel_rule_to_v0_1_1_history(
    tmp_path: Path,
) -> None:
    _write_release_tree(tmp_path)
    historical = tmp_path / "docs/releases/v0.1.1.md"
    historical.write_text(
        "# v0.1.1\n\nuv run python scripts/release_consumer_smoke.py --wheel dist/*.whl --json\n",
        encoding="utf-8",
    )

    assert audit_release_presentation(tmp_path) == []


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("16fae017ced5fe67da3fae4a01f26e9e9f1084aa", "0" * 40),
        ("https://github.com/iTao-AI/night-voyager/pull/21", "https://example.com/pr/21"),
        ("did not validate the final v0.1.2 wheel", "validated the final v0.1.2 wheel"),
        ("does not prove production adoption", "proves production adoption"),
        ("hosted deployment", "hosted service"),
        ("real-user outcomes", "customer outcomes"),
        ("is not an MKE CI dependency", "is an MKE CI dependency"),
        (
            "does not require a downstream lock update",
            "requires a downstream lock update",
        ),
    ],
)
def test_audit_rejects_invalid_downstream_candidate_boundary(
    tmp_path: Path,
    old: str,
    new: str,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "docs/releases/v0.1.2.md"
    text = target.read_text(encoding="utf-8")
    assert old in text
    target.write_text(text.replace(old, new), encoding="utf-8")

    assert "downstream_candidate_boundary" in _rules(tmp_path)


@pytest.mark.parametrize(
    "contradictory_claim",
    [
        "The final v0.1.2 wheel was validated by the downstream consumer.",
        "The downstream integration proves production adoption.",
        "The downstream integration proves hosted deployment.",
        "The downstream integration proves real-user outcomes.",
        "Night Voyager is an MKE CI dependency.",
        "A downstream lock update is required for this release.",
    ],
)
def test_audit_rejects_contradictory_affirmative_downstream_claims(
    tmp_path: Path,
    contradictory_claim: str,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "docs/releases/v0.1.2.md"
    original = target.read_text(encoding="utf-8")
    target.write_text(
        f"{original.rstrip()}\n\n{contradictory_claim}\n",
        encoding="utf-8",
    )

    assert "downstream_candidate_boundary" in _rules(tmp_path)


@pytest.mark.parametrize(
    "overclaim",
    [
        "MKE provides production OCR.",
        "PaddleOCR-VL 1.6 is the promoted default provider.",
        "MKE ships a public OCR runtime.",
        "MKE provides general OCR quality.",
        "MKE reconstructs source layout.",
        "MKE has verified LLM Wiki compatibility.",
        "MKE bundles LLM Wiki as an automatic integration.",
        "MKE provides hosted integration.",
        "MKE has real-user adoption.",
        "The GitHub Release includes extra assets.",
        "MKE is deployed in production.",
        "MKE has production adoption.",
        "MKE delivers business impact.",
        "MKE is published on PyPI.",
        "MKE is available from the package registry.",
        "MKE v0.1.4 has been published.",
    ],
)
def test_audit_rejects_compiled_library_release_overclaims(
    tmp_path: Path,
    overclaim: str,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "README.md"
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n{overclaim}\n",
        encoding="utf-8",
    )

    assert "compiled_library_overclaim" in _rules(tmp_path)


@pytest.mark.parametrize(
    "wrapped_overclaim",
    [
        "PaddleOCR-VL 1.6 is the promoted\ndefault provider.",
        "MKE ships a public\nOCR runtime.",
        "The GitHub Release includes\nextra assets.",
        "MKE is available from\nPyPI.",
        "MKE is deployed in\nproduction.",
        "MKE has production\nadoption.",
        "MKE delivers business\nimpact.",
    ],
)
def test_audit_rejects_wrapped_release_overclaims_once(
    tmp_path: Path,
    wrapped_overclaim: str,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "README.md"
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n{wrapped_overclaim}\n",
        encoding="utf-8",
    )

    violations = [
        violation
        for violation in audit_release_presentation(tmp_path)
        if violation.rule == "compiled_library_overclaim"
    ]
    assert len(violations) == 1


@pytest.mark.parametrize(
    "wrapped_negative",
    [
        "PaddleOCR-VL 1.6 is not the promoted\ndefault provider.",
        "MKE does not ship a public\nOCR runtime.",
        "The GitHub Release does not include\nextra assets.",
        "MKE is not available from\nPyPI.",
        "MKE is not deployed in\nproduction and does not claim production adoption or "
        "business impact.",
    ],
)
def test_audit_accepts_wrapped_release_negations(
    tmp_path: Path,
    wrapped_negative: str,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "README.md"
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n{wrapped_negative}\n",
        encoding="utf-8",
    )

    assert "compiled_library_overclaim" not in _rules(tmp_path)


@pytest.mark.parametrize(
    "separated_text",
    [
        "MKE ships a public\n\nOCR runtime.",
        "PaddleOCR-VL 1.6 is the promoted\n\n> default provider.",
        "- The GitHub Release includes\n- extra assets.",
    ],
)
def test_audit_does_not_join_distinct_markdown_blocks(
    tmp_path: Path,
    separated_text: str,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "README.md"
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n{separated_text}\n",
        encoding="utf-8",
    )

    assert "compiled_library_overclaim" not in _rules(tmp_path)


def test_verify_release_does_not_mix_four_stage_workflow_with_stale_three_check_claim() -> None:
    text = Path("docs/how-to/verify-release.md").read_text(encoding="utf-8")

    assert "This guide separates four ordered stages" in text
    assert "completed all three checks" not in text
    assert "earlier three-check workflow" in text


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
            "docs/releases/v0.1.5.md",
            "GitHub Release metadata records the final tag and target commit when Stage 3 "
            "creates the release from the verified commit.",
        ),
        (
            "docs/releases/v0.1.5.md",
            "This document describes release scope and verification before publication.",
        ),
        (
            "docs/releases/v0.1.5.md",
            "This document does not predeclare a future tag target.",
        ),
        (
            "docs/releases/v0.1.5.md",
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
        "# v0.1.4\n\n"
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
        "directory.\n"
        "`uv run python scripts/release_consumer_smoke.py --wheel "
        "dist/multimodal_knowledge_engine-0.1.5-py3-none-any.whl --json`\n",
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
    (tmp_path / "docs/releases/v0.1.5.md").write_text(
        "# v0.1.5\n\n"
        "Proof, demo, CLI, MCP, and retrieval evaluation docs are linked.\n"
        "E3-C dense, E3-D RRF, and E3-E reranker remain comparison-only evidence.\n"
        f"{placeholder}\n",
        encoding="utf-8",
    )

    assert "stale_release_status" in _rules(tmp_path)


@pytest.mark.parametrize(
    "positioning_word",
    ["Career", "portfolio", "resume", "interview artifact", "showcase"],
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


@pytest.mark.parametrize(
    "claim",
    [
        "verified LLM Wiki compatibility, but does not bundle LLM Wiki",
        "production OCR; LLM Wiki compatibility remains deferred",
    ],
)
def test_compiled_library_safe_marker_does_not_mask_another_overclaim(
    tmp_path: Path, claim: str
) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "README.md").write_text(
        (tmp_path / "README.md").read_text(encoding="utf-8") + f"\n{claim}\n",
        encoding="utf-8",
    )

    assert "compiled_library_overclaim" in _rules(tmp_path)


@pytest.mark.parametrize(
    "claim",
    [
        "does not claim reconstructed layout, hosted integration, real-user adoption",
        "does not validate production OCR, reconstructed layout, hosted integration, adoption",
    ],
)
def test_compiled_library_shared_negative_scope_is_not_an_overclaim(
    tmp_path: Path, claim: str
) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "README.md").write_text(
        (tmp_path / "README.md").read_text(encoding="utf-8") + f"\n{claim}\n",
        encoding="utf-8",
    )

    assert "compiled_library_overclaim" not in _rules(tmp_path)


@pytest.mark.parametrize(
    "claim",
    [
        "PaddleOCR-VL 1.6 is not the promoted default provider.",
        "MKE does not ship a public OCR runtime or claim general OCR quality.",
        "The GitHub Release has zero extra assets.",
        "MKE is not deployed in production and does not claim production adoption or "
        "business impact.",
        "PyPI and other package registries are not published.",
    ],
)
def test_release_boundary_negations_are_not_overclaims(tmp_path: Path, claim: str) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "README.md").write_text(
        (tmp_path / "README.md").read_text(encoding="utf-8") + f"\n{claim}\n",
        encoding="utf-8",
    )

    assert "compiled_library_overclaim" not in _rules(tmp_path)


@pytest.mark.parametrize(
    "claim",
    [
        "provides production OCR; it is not production OCR",
        "provides production OCR. It is not production OCR.",
        "provides production OCR, but it is not production OCR",
        "verified LLM Wiki compatibility. It does not verify LLM Wiki compatibility.",
    ],
)
def test_compiled_library_same_claim_contradiction_remains_an_overclaim(
    tmp_path: Path, claim: str
) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "README.md").write_text(
        (tmp_path / "README.md").read_text(encoding="utf-8") + f"\n{claim}\n",
        encoding="utf-8",
    )

    assert "compiled_library_overclaim" in _rules(tmp_path)


def test_release_presentation_audit_reports_missing_current_release_note(
    tmp_path: Path,
) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "docs/releases/v0.1.4.md").unlink()

    assert "v014_release_contract" in _rules(tmp_path)


def test_release_presentation_audit_accepts_current_repository() -> None:
    assert audit_release_presentation(ROOT) == []


@pytest.mark.parametrize(
    ("readme", "stale"),
    (
        ("README.md", "this release does not claim that terminal real ASR has run"),
        ("README_CN.md", "当前 release 不声明 terminal real ASR 已运行"),
    ),
)
def test_audit_rejects_exact_stale_terminal_asr_denial_only_in_current_readmes(
    tmp_path: Path, readme: str, stale: str
) -> None:
    _write_release_tree(tmp_path)
    current = tmp_path / readme
    current.write_text(
        f"{current.read_text(encoding='utf-8').rstrip()}\n\n{stale}\n",
        encoding="utf-8",
    )
    historical = tmp_path / "docs/releases/v0.1.3.md"
    historical.parent.mkdir(parents=True, exist_ok=True)
    historical.write_text(f"# v0.1.3\n\n{stale}\n", encoding="utf-8")

    violations = audit_release_presentation(tmp_path)

    assert any(
        violation.file == readme and violation.rule == "stale_terminal_asr_denial"
        for violation in violations
    )
    assert not any(
        violation.file == "docs/releases/v0.1.3.md"
        and violation.rule == "stale_terminal_asr_denial"
        for violation in violations
    )


def test_audit_accepts_fully_bounded_terminal_asr_observation(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    claim = (
        "A separately authorized terminal observation used fixed MP3, WAV, and M4A fixtures on "
        "Darwin arm64 with a prepared cache-only faster-whisper model and bounded supervision. "
        "It returned status=passed and canonical=true across Python, CLI, stdio MCP, published "
        "Runs, timestamp Evidence, Search/Ask, Export v2, network denial, and cleanup. This does "
        "not prove transcript accuracy, a production SLA, hosted production, cross-platform "
        "support, arbitrary media support, hostile-media sandboxing, business adoption, or "
        "real-user outcomes."
    )
    target = tmp_path / "README.md"
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n{claim}\n",
        encoding="utf-8",
    )

    assert "direct_audio_overclaim" not in _rules(tmp_path)


@pytest.mark.parametrize(
    "claim",
    (
        "A terminal observation returned status=passed.",
        "A separately authorized terminal observation returned status=passed and canonical=true.",
        "The terminal proof returned status=passed and canonical=true.",
        "一次 terminal observation 返回 status=passed。",
    ),
)
def test_audit_rejects_incomplete_affirmative_terminal_observation(
    tmp_path: Path, claim: str
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "README.md"
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n{claim}\n",
        encoding="utf-8",
    )

    assert "direct_audio_overclaim" in _rules(tmp_path)


@pytest.mark.parametrize(
    "contradiction",
    (
        "MKE verified real ASR in the terminal proof.",
        "The terminal real ASR proof passed.",
    ),
)
def test_audit_rejects_unbounded_real_asr_affirmative_after_bounded_observation(
    tmp_path: Path, contradiction: str
) -> None:
    _write_release_tree(tmp_path)
    bounded = (
        "A separately authorized terminal observation used fixed MP3, WAV, and M4A fixtures on "
        "Darwin arm64 with a prepared cache-only faster-whisper model and bounded supervision. "
        "It returned status=passed and canonical=true across Python, CLI, stdio MCP, published "
        "Runs, timestamp Evidence, Search/Ask, Export v2, network denial, and cleanup. This does "
        "not prove transcript accuracy, a production SLA, hosted production, cross-platform "
        "support, arbitrary media support, hostile-media sandboxing, business adoption, or "
        "real-user outcomes."
    )
    target = tmp_path / "README.md"
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n{bounded} {contradiction}\n",
        encoding="utf-8",
    )

    assert "direct_audio_overclaim" in _rules(tmp_path)


def test_verify_release_co_binds_compiled_export_proof_to_validated_candidate() -> None:
    text = Path("docs/how-to/verify-release.md").read_text(encoding="utf-8")

    assert "candidate_validation=" in text
    assert "scripts/compiled_library_export_proof.py" in text
    assert "compiled-export-proof.json" in text
    assert 'proof["proof_input_wheel_sha256"] == validated["wheel_sha256"]' in text
    assert "The independent candidate validator" in text


def test_verify_release_archive_smoke_covers_provenance_and_compiled_export() -> None:
    text = Path("docs/how-to/verify-release.md").read_text(encoding="utf-8")

    for command in (
        "scripts/evidence_provenance_proof.py",
        "mke --db library.sqlite ingest operations-guide.pdf --json",
        "mke --db library.sqlite ingest spoken-evidence.mp4 --json",
        "mke --db library.sqlite library export",
        "scripts/compiled_library_export_consumer.py",
    ):
        assert command in text
    expected_result = (
        'Require `status="passed"`, exact portable schemas, two sources, and three '
        "Evidence records."
    )
    assert expected_result in text


@pytest.mark.parametrize(
    "relative",
    [
        "docs/how-to/export-compiled-library.md",
        "docs/how-to/run-compiled-library-export-proof.md",
        "docs/reference/cli.md",
        "docs/reference/contracts.md",
    ],
)
def test_compiled_library_claim_audit_covers_feature_public_docs(
    tmp_path: Path, relative: str
) -> None:
    _write_release_tree(tmp_path)
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Feature\n\nverified LLM Wiki compatibility\n", encoding="utf-8")

    assert "compiled_library_overclaim" in _rules(tmp_path)


APPROVED_DIRECT_AUDIO_CLAIM = (
    "Bounded local voice notes and clips or excerpts from meetings, interviews, lectures, and "
    "other downloaded spoken material, when encoded as the supported MP3, WAV/PCM, or M4A/AAC "
    "profiles, can be transcribed through an explicitly prepared, cache-only faster-whisper "
    "runtime into timestamped active Evidence, then consumed through Python, CLI, stdio MCP, "
    "Search/Ask, and a versioned deterministic Compiled Library Export."
)


@pytest.mark.parametrize(
    "claim",
    [
        "MKE supports arbitrary audio codecs.",
        "MKE supports arbitrary audio codecs and long audio are excluded.",
        (
            "MKE does not support arbitrary codecs and supports full-length meetings, "
            "interviews, and lectures."
        ),
        "MKE supports meetings, interviews, and lectures.",
        "MKE processes full-length meetings, interviews, and lectures.",
        "MKE supports long audio.",
        "MKE chunks and resumes streaming audio.",
        "MKE provides speaker diarization and microphone capture.",
        "MKE downloads transcription models automatically.",
        "MKE automatically downloads transcription models.",
        "MKE falls back to cloud ASR.",
        "MKE provides a cloud ASR fallback.",
        "MKE automatically syncs audio to LLM Wiki.",
        "MKE supports direct audio across all platforms.",
        "MKE guarantees transcript accuracy and an audio SLA.",
        "MKE produces accurate transcripts.",
        "MKE deploys direct audio in production.",
        "MKE has production adoption.",
        "MKE delivers business impact.",
        "MKE is published on PyPI.",
        "MKE provides a hosted transcription fallback.",
        "MKE offers cloud transcription when local ASR fails.",
        "MKE direct audio is production ready.",
        "MKE does not claim cross-platform support and MKE is available on PyPI.",
        "MKE does not support full-length meetings and has production adoption.",
        "MKE does not download models and offers cloud transcription when local ASR fails.",
        "MKE does not claim an SLA and direct audio is production ready.",
        "MKE provides cross-platform direct-audio coverage.",
        "MKE has official OpenAI direct-audio integration.",
        "MKE has official LLM Wiki direct-audio integration.",
        "The terminal real ASR proof passed.",
        "MKE verified real ASR in the terminal proof.",
        "The terminal proof ran real ASR.",
        (
            "The terminal real ASR proof passed with production verified transcript accuracy, "
            "an SLA, and cross-platform support."
        ),
        "MKE redistributes external wheels and native binaries.",
        "MKE redistributes external wheels/native binaries.",
        "MKE bundles external wheels and native binaries.",
        "MKE 支持任意音频编解码器。",
        "MKE 支持完整会议、访谈和讲座处理。",
        "MKE 会自动下载转写模型。",
        "Direct audio 支持所有平台。",
        "终端真实 ASR 证明已通过。",
        "MKE 已验证真实 ASR。",
        "终端证明执行了真实 ASR。",
        "MKE 重新分发外部 wheels 和原生二进制文件。",
        "MKE 打包外部 wheels 和原生二进制文件。",
    ],
)
def test_audit_rejects_direct_audio_overclaims(tmp_path: Path, claim: str) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "README.md"
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n{claim}\n",
        encoding="utf-8",
    )

    assert "direct_audio_overclaim" in _rules(tmp_path)


def test_audit_rejects_wrapped_direct_audio_overclaim_once(tmp_path: Path) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "README.md"
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n"
        "MKE processes full-length meetings,\ninterviews, and lectures.\n",
        encoding="utf-8",
    )

    violations = [
        violation
        for violation in audit_release_presentation(tmp_path)
        if violation.rule == "direct_audio_overclaim"
    ]
    assert len(violations) == 1


@pytest.mark.parametrize(
    "wrapped_claim",
    [
        "The terminal real ASR proof\npassed and was verified.",
        "The terminal proof ran\nreal ASR.",
        "MKE redistributes external wheels\nand native binaries.",
        "MKE bundles external wheels\nand native binaries.",
        "终端真实 ASR 证明\n已通过并完成验证。",
        "终端证明执行了\n真实 ASR。",
        "MKE 重新分发外部 wheels\n和原生二进制文件。",
        "MKE 打包外部 wheels\n和原生二进制文件。",
    ],
)
def test_audit_rejects_wrapped_audio_authority_overclaim_once(
    tmp_path: Path, wrapped_claim: str
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "README.md"
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n{wrapped_claim}\n",
        encoding="utf-8",
    )

    violations = [
        violation
        for violation in audit_release_presentation(tmp_path)
        if violation.rule == "direct_audio_overclaim"
    ]
    assert len(violations) == 1


@pytest.mark.parametrize(
    "claim",
    [
        APPROVED_DIRECT_AUDIO_CLAIM,
        "MKE does not support arbitrary codecs or full-length meetings, interviews, or lectures.",
        (
            "Long audio, chunking, resume, streaming, diarization, and microphone capture "
            "are excluded."
        ),
        "MKE does not download models implicitly or fall back to cloud ASR.",
        "MKE does not currently support arbitrary audio codecs.",
        "MKE does not automatically download transcription models.",
        "MKE does not currently offer cloud transcription when local ASR fails.",
        "Direct audio does not currently provide cross-platform support.",
        (
            "This candidate does not claim cross-platform support, transcript accuracy, an SLA, "
            "or production deployment."
        ),
        "The terminal real ASR proof has not been performed.",
        "MKE has not verified real ASR.",
        "The terminal proof did not run real ASR.",
        "MKE does not redistribute external wheels or native binaries.",
        "MKE does not bundle external wheels or native binaries.",
        "尚未运行终端真实 ASR 证明。",
        "MKE 未验证真实 ASR。",
        "终端证明未执行真实 ASR。",
        "MKE 不重新分发外部 wheels 或原生二进制文件。",
        "MKE 不打包外部 wheels 或原生二进制文件。",
    ],
)
def test_audit_accepts_approved_or_negated_direct_audio_boundaries(
    tmp_path: Path,
    claim: str,
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "README.md"
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n{claim}\n",
        encoding="utf-8",
    )

    assert "direct_audio_overclaim" not in _rules(tmp_path)


@pytest.mark.parametrize(
    "claim",
    [
        (
            "MKE does not redistribute external wheels or native binaries and "
            "MKE redistributes external wheels/native binaries."
        ),
        "MKE has not verified real ASR and MKE verified real ASR in the terminal proof.",
        "The terminal proof did not run real ASR, but the terminal proof ran real ASR.",
        (
            "MKE does not bundle external wheels or native binaries, but "
            "MKE bundles external wheels and native binaries."
        ),
        "MKE 不重新分发外部 wheels，但 MKE 重新分发外部 wheels 和原生二进制文件。",
        "MKE 未验证真实 ASR，但 MKE 已验证真实 ASR。",
        "终端证明未执行真实 ASR，但终端证明执行了真实 ASR。",
        "MKE 不打包外部 wheels，但 MKE 打包外部 wheels 和原生二进制文件。",
    ],
)
def test_audio_authority_negation_does_not_mask_contradictory_overclaim(
    tmp_path: Path, claim: str
) -> None:
    _write_release_tree(tmp_path)
    target = tmp_path / "README.md"
    target.write_text(
        f"{target.read_text(encoding='utf-8').rstrip()}\n\n{claim}\n",
        encoding="utf-8",
    )

    assert "direct_audio_overclaim" in _rules(tmp_path)


def test_audit_rejects_private_paths_gstack_artifacts_credentials_and_tracebacks(
    tmp_path: Path,
) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "docs/releases/v0.1.5.md").write_text(
        "# v0.1.5\n\n/Users/mac/.gstack/rollout token=secret\nTraceback (most recent call last):\n",
        encoding="utf-8",
    )

    assert "public_boundary" in _rules(tmp_path)
