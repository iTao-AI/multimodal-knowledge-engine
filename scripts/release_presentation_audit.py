from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

EXPECTED_VERSION = "0.1.2"
RUNTIME_STRATEGY = "cjk-active-scan-overlap-v1"

RELEASE_FACING_FILES = (
    "README.md",
    "README_CN.md",
    "docs/README.md",
    "CHANGELOG.md",
    "docs/releases/v0.1.2.md",
    "docs/how-to/verify-release.md",
)
COMPILED_LIBRARY_CLAIM_FILES = (
    *RELEASE_FACING_FILES,
    "docs/explanation/architecture.md",
    "docs/how-to/export-compiled-library.md",
    "docs/how-to/run-compiled-library-export-proof.md",
    "docs/reference/cli.md",
    "docs/reference/contracts.md",
)
ENTRY_POINT_FILES = (
    "README.md",
    "README_CN.md",
    "docs/README.md",
)
README_FILES = (
    "README.md",
    "README_CN.md",
)
RELEASE_NOTE_FILES = (
    "CHANGELOG.md",
    "docs/releases/v0.1.2.md",
)
CONSUMER_SMOKE_COMMAND_FILES = (
    "README.md",
    "README_CN.md",
    "docs/releases/v0.1.2.md",
    "docs/how-to/verify-release.md",
)


@dataclass(frozen=True)
class Violation:
    file: str
    rule: str
    message: str


def _read_text(root: Path, relative: str) -> str:
    path = root / relative
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _tracked_release_files(root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ("git", "ls-files", *RELEASE_FACING_FILES),
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return [path for path in RELEASE_FACING_FILES if (root / path).exists()]
    tracked = [line for line in result.stdout.splitlines() if line in RELEASE_FACING_FILES]
    existing_untracked = [path for path in RELEASE_FACING_FILES if (root / path).exists()]
    return sorted(set(tracked + existing_untracked), key=RELEASE_FACING_FILES.index)


def _version_from_init(text: str) -> str | None:
    match = re.search(r"__version__\s*=\s*[\"']([^\"']+)[\"']", text)
    return match.group(1) if match else None


def _contains_all_terms(text: str, terms: Iterable[str]) -> bool:
    normalized_text = " ".join(text.split())
    return all(" ".join(term.split()) in normalized_text for term in terms)


def _audit_version_identity(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    pyproject_path = root / "pyproject.toml"
    init_path = root / "src/mke/__init__.py"
    pyproject_version = None
    init_version = None
    if pyproject_path.exists():
        pyproject_version = tomllib.loads(pyproject_path.read_text(encoding="utf-8")).get(
            "project", {}
        ).get("version")
    if init_path.exists():
        init_version = _version_from_init(init_path.read_text(encoding="utf-8"))
    versions = {
        "pyproject.toml": pyproject_version,
        "src/mke/__init__.py": init_version,
    }
    for file_name, version in versions.items():
        if version != EXPECTED_VERSION:
            violations.append(
                Violation(
                    file=file_name,
                    rule="version_identity",
                    message=f"expected version {EXPECTED_VERSION}, found {version!r}",
                )
            )
    if pyproject_version != init_version:
        violations.append(
            Violation(
                file="pyproject.toml",
                rule="version_identity",
                message="pyproject version and mke.__version__ differ",
            )
        )
    for file_name in RELEASE_NOTE_FILES:
        if (root / file_name).exists() and EXPECTED_VERSION not in _read_text(root, file_name):
            violations.append(
                Violation(
                    file=file_name,
                    rule="version_identity",
                    message=f"release notes must mention {EXPECTED_VERSION}",
                )
            )
    return violations


def _audit_runtime_default(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for file_name in ENTRY_POINT_FILES:
        text = _read_text(root, file_name)
        if not text:
            continue
        if EXPECTED_VERSION not in text and f"v{EXPECTED_VERSION}" not in text:
            violations.append(
                Violation(
                    file=file_name,
                    rule="version_identity",
                    message=f"entry point must mention v{EXPECTED_VERSION}",
                )
            )
        if RUNTIME_STRATEGY not in text:
            violations.append(
                Violation(
                    file=file_name,
                    rule="current_runtime_default",
                    message=f"entry point must mention {RUNTIME_STRATEGY}",
                )
            )
    return violations


def _audit_readme_presentation(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    language_switch = "[English](./README.md) | [中文](./README_CN.md)"
    verified_table_labels = {
        "README.md": {
            "heading": "## Verified in v0.1.2",
            "header": "| Capability | Evidence |",
            "message": "English README must include the Verified in v0.1.2 capability table",
        },
        "README_CN.md": {
            "heading": "## v0.1.2 已验证能力",
            "header": "| 能力 | 验证证据 |",
            "message": "Chinese README must include localized v0.1.2 verified capability labels",
        },
    }
    diagram_terms = (
        "flowchart TB",
        "subgraph Interfaces",
        "Agent / Tool Client",
        "CLI",
        "stdio MCP Server",
        "subgraph Application",
        "Application Boundary",
        "MKE Application Service",
        "Shared CLI / MCP Contract",
        "Owner-startup Retrieval Strategy",
        "subgraph Lifecycle",
        "Ingestion And Publication Lifecycle",
        "Source",
        "Observable Ingest Run",
        "Evidence",
        "Active Publication",
        "subgraph Authority",
        "Domain Authority",
        "SQLite Domain Store",
        "Immutable Assets",
        "Immutable Artifacts",
        "subgraph Runtime",
        "Retrieval Runtime",
        "Rebuildable Retrieval Projections",
        "Active Evidence FTS",
        RUNTIME_STRATEGY,
        "Search",
        "Evidence-only Ask",
        "subgraph Evaluation",
        "Evaluation And Release Evidence",
        "E1 / E3 baselines",
        "Dense candidate artifact",
        "RRF valid negative",
        "Relevance gate / reranker artifact",
        "proof / demo / consumer smoke",
        "Comparison-only Evidence",
        "comparison-only",
        "release gate",
    )
    engineering_depth_terms_by_file = {
        "README.md": (
            "## What this release proves",
            "Evidence lifecycle",
            "active Publication",
            "CLI/MCP application service contract",
            "retrieval evaluation artifacts",
            "Retrieval evidence",
            "Shipped runtime",
            "Comparison-only evidence",
            "Not included",
            "lexical search",
            "dense",
            "RRF",
            "relevance gate",
            "reranker",
            "does not change normal Search, Ask, MCP, or the runtime default",
            "query rewrite",
            "HyDE",
            "OCR",
            "HTTP/UI",
            "API adapters",
            "Evidence provenance",
            "mke.evidence_ref.v1",
            "external source-pack proof",
            "same-wheel Python 3.12/3.13",
            "owner lifecycle and runtime hardening",
            "OCR remains excluded",
        ),
        "README_CN.md": (
            "## v0.1.2 工程深度",
            "Evidence 生命周期",
            "active Publication",
            "CLI/MCP application service contract",
            "retrieval evaluation artifacts",
            "Retrieval evidence",
            "已发布 runtime",
            "Comparison-only evidence",
            "不包含",
            "lexical search",
            "dense",
            "RRF",
            "relevance gate",
            "reranker",
            "不改变 normal Search、Ask、MCP 或 runtime default",
            "query rewrite",
            "HyDE",
            "OCR",
            "HTTP/UI",
            "API adapters",
            "Evidence provenance",
            "mke.evidence_ref.v1",
            "external source-pack proof",
            "same-wheel Python 3.12/3.13",
            "owner lifecycle and runtime hardening",
            "OCR 仍排除",
        ),
    }
    verified_terms_by_file = {
        "README.md": (
            "Evidence lifecycle",
            "text-layer PDF",
            "short video fixture",
            "active-Publication Search",
            "evidence-only Ask",
            "insufficient_evidence",
            "CLI + stdio MCP",
            "Real stdio MCP local knowledge proof",
            RUNTIME_STRATEGY,
            "consumer smoke",
            "Evidence provenance",
            "mke.evidence_ref.v1",
            "external source-pack proof",
            "same wheel on Python 3.12/3.13",
            "owner lifecycle and runtime hardening",
        ),
        "README_CN.md": (
            "Evidence 生命周期",
            "text-layer PDF",
            "short video fixture",
            "active-Publication Search",
            "evidence-only Ask",
            "insufficient_evidence",
            "CLI + stdio MCP",
            "Real stdio MCP local knowledge proof",
            RUNTIME_STRATEGY,
            "consumer smoke",
            "Evidence provenance",
            "mke.evidence_ref.v1",
            "external source-pack proof",
            "same wheel on Python 3.12/3.13",
            "owner lifecycle and runtime hardening",
        ),
    }
    for file_name in README_FILES:
        text = _read_text(root, file_name)
        if not text:
            continue
        top_lines = "\n".join(text.splitlines()[:8])
        if language_switch not in top_lines:
            violations.append(
                Violation(
                    file=file_name,
                    rule="readme_language_switch",
                    message="README must start with the shared English/Chinese language switch",
                )
            )
        if "```mermaid" not in text or not _contains_all_terms(text, diagram_terms):
            violations.append(
                Violation(
                    file=file_name,
                    rule="readme_architecture_diagram",
                    message="README must include the v0.1.2 Mermaid architecture diagram",
                )
            )
        labels = verified_table_labels[file_name]
        if (
            labels["heading"] not in text
            or labels["header"] not in text
            or not _contains_all_terms(text, verified_terms_by_file[file_name])
        ):
            violations.append(
                Violation(
                    file=file_name,
                    rule="verified_v012_table",
                    message=labels["message"],
                )
            )
        if not _contains_all_terms(text, engineering_depth_terms_by_file[file_name]):
            violations.append(
                Violation(
                    file=file_name,
                    rule="readme_engineering_depth",
                    message=(
                        "README must explain v0.1.2 engineering depth and retrieval "
                        "evidence boundaries"
                    ),
                )
            )
    return violations


def _line_overclaims_runtime(line: str) -> bool:
    lowered = line.lower()
    if not re.search(r"\b(dense|rrf|reranker|reranking)\b", lowered):
        return False
    if "runtime" not in lowered and "strategy" not in lowered and "support" not in lowered:
        return False
    safe_markers = (
        "comparison-only",
        "not runtime",
        "not a runtime",
        "does not change",
        "out of scope",
        "not included",
        "remain separate",
        "仍不在范围",
        "不改变",
        "不是 runtime",
        "非 runtime",
        "comparison evidence",
    )
    return not any(marker in lowered for marker in safe_markers)


def _audit_comparison_boundary(root: Path, files: Iterable[str]) -> list[Violation]:
    violations: list[Violation] = []
    for file_name in files:
        text = _read_text(root, file_name)
        if not text:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if _line_overclaims_runtime(line):
                violations.append(
                    Violation(
                        file=file_name,
                        rule="comparison_runtime_overclaim",
                        message=f"line {line_number} may present dense/RRF/reranker as runtime",
                    )
                )
        lowered = text.lower()
        mentions_candidate = all(term in lowered for term in ("e3-c", "e3-d", "e3-e"))
        mentions_retrieval_family = all(
            term in lowered for term in ("dense", "rrf", "reranker")
        )
        if (mentions_candidate or mentions_retrieval_family) and "comparison-only" not in lowered:
            violations.append(
                Violation(
                    file=file_name,
                    rule="comparison_only_boundary",
                    message="E3-C/D/E release text must say comparison-only",
                )
            )
    return violations


def _line_overclaims_compiled_library(line: str) -> bool:
    lowered = " ".join(line.lower().split())
    claims = (
        (
            r"\bproduction ocr\b",
            (
                "not production ocr",
                "production ocr remains excluded",
                "不是 production ocr",
            ),
        ),
        (
            r"\b(?:reconstructs?|reconstructed|recovers?|recovered) (?:the )?(?:source )?layout\b",
            (
                "does not reconstruct",
                "not reconstruct",
                "not reconstructed",
                "does not claim reconstructed",
                "不重建 layout",
            ),
        ),
        (
            r"\b(?:verified|proven|supports?) llm wiki compatibility\b",
            (
                "not verified llm wiki",
                "llm wiki compatibility remains deferred",
                "does not verify llm wiki compatibility",
            ),
        ),
        (
            r"\bhosted integration\b",
            (
                "no hosted integration",
                "does not claim hosted integration",
                "does not prove hosted integration",
            ),
        ),
        (
            r"\breal-user adoption\b",
            (
                "no real-user adoption",
                "does not claim real-user adoption",
                "does not prove real-user adoption",
            ),
        ),
        (
            r"\bv0\.1\.3\b.*\b(?:released|published|available)\b",
            ("does not release v0.1.3", "v0.1.3 is not released"),
        ),
    )
    return any(
        re.search(pattern, lowered) is not None
        and not any(marker in lowered for marker in safe_markers)
        for pattern, safe_markers in claims
    )


def _audit_compiled_library_claim_boundary(
    root: Path, files: Iterable[str]
) -> list[Violation]:
    violations: list[Violation] = []
    for file_name in files:
        text = _read_text(root, file_name)
        for line_number, line in enumerate(text.splitlines(), start=1):
            if _line_overclaims_compiled_library(line):
                violations.append(
                    Violation(
                        file=file_name,
                        rule="compiled_library_overclaim",
                        message=f"line {line_number} exceeds the compiled Library claim boundary",
                    )
                )
    return violations


def _audit_release_notes_links(root: Path) -> list[Violation]:
    required_terms = (
        "proof",
        "demo",
        "CLI",
        "MCP",
        "retrieval evaluation",
        "local knowledge proof",
    )
    violations: list[Violation] = []
    release_notes = _read_text(root, "docs/releases/v0.1.2.md")
    for term in required_terms:
        if term.lower() not in release_notes.lower():
            violations.append(
                Violation(
                    file="docs/releases/v0.1.2.md",
                    rule="release_notes_links",
                    message=f"release notes must link or name {term}",
                )
            )
    return violations


def _audit_stale_status(root: Path, files: Iterable[str]) -> list[Violation]:
    stale_patterns = (
        "not merged",
        "pending implementation",
        "placeholder-marker",
        "placeholder for",
        "tbd",
        "todo fill",
        "to be created",
        "to be filled",
        "to be determined",
        "stage 2 installed-package consumer smoke, tag creation, and github release publication "
        "are separate gates after this presentation-readiness work merges",
        "stage 2 must run from a separate branch after stage 1 merges",
        "runtime_promotion_status=not_evaluated",
        "0.0.0",
    )
    post_release_stale_patterns = (
        "github release metadata records the final tag and target commit when stage 3 creates "
        "the release",
        "describes release scope and verification before publication",
        "does not predeclare a future tag target",
        "tag and github release publication remain a separate authorized stage 3 action",
        "tag creation, github release publication, and pypi publication remain separate stage 3 "
        "authorization actions",
    )
    violations: list[Violation] = []
    for file_name in files:
        text = _read_text(root, file_name)
        lowered = text.lower()
        patterns = stale_patterns
        if file_name in RELEASE_NOTE_FILES:
            patterns = stale_patterns + post_release_stale_patterns
        for pattern in patterns:
            if pattern in lowered:
                violations.append(
                    Violation(
                        file=file_name,
                        rule="stale_release_status",
                        message=f"release-facing file contains stale phrase {pattern!r}",
                    )
                )
    return violations


def _audit_consumer_smoke_wheel_selection(
    root: Path,
    files: Iterable[str],
) -> list[Violation]:
    violations: list[Violation] = []
    exact_wheel = "dist/multimodal_knowledge_engine-0.1.2-py3-none-any.whl"
    for file_name in files:
        text = _read_text(root, file_name)
        if exact_wheel not in text:
            violations.append(
                Violation(
                    file=file_name,
                    rule="consumer_smoke_wheel_selection",
                    message=f"consumer smoke must name {exact_wheel}",
                )
            )
        if "dist/*.whl" in text or "multimodal_knowledge_engine-0.1.1-py3-none-any.whl" in text:
            violations.append(
                Violation(
                    file=file_name,
                    rule="consumer_smoke_wheel_selection",
                    message="consumer smoke must name the single current release wheel",
                )
            )
    return violations


def _audit_downstream_candidate_boundary(root: Path) -> list[Violation]:
    file_name = "docs/releases/v0.1.2.md"
    text = _read_text(root, file_name)
    required_terms = (
        "https://github.com/iTao-AI/night-voyager/pull/21",
        "16fae017ced5fe67da3fae4a01f26e9e9f1084aa",
        "independent consumer",
        "pre-release candidate",
        "synthetic fixtures",
        "strict receipt",
        "did not validate the final v0.1.2 wheel",
        "does not prove production adoption",
        "hosted deployment",
        "real-user outcomes",
        "is not an MKE CI dependency",
        "does not require a downstream lock update",
    )
    if not _contains_all_terms(text, required_terms):
        return [
            Violation(
                file=file_name,
                rule="downstream_candidate_boundary",
                message=(
                    "release notes must preserve the exact downstream pre-release "
                    "candidate and non-production boundary"
                ),
            )
        ]
    normalized = " ".join(text.split())
    affirmative_overclaims = (
        re.compile(
            r"\bfinal v0\.1\.2 wheel (?:was|is|has been) validated\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:proves|proved|demonstrates|demonstrated|confirms|confirmed) "
            r"(?:production adoption|hosted deployment|real-user outcomes)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:is|was|has been) an? MKE CI dependency\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:a )?downstream lock update (?:is|was|remains) required\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\brequires a downstream lock update\b",
            re.IGNORECASE,
        ),
    )
    if any(pattern.search(normalized) for pattern in affirmative_overclaims):
        return [
            Violation(
                file=file_name,
                rule="downstream_candidate_boundary",
                message="release notes must not add affirmative downstream overclaims",
            )
        ]
    return []


def _audit_public_boundary(root: Path, files: Iterable[str]) -> list[Violation]:
    patterns = {
        "absolute local path": re.compile(r"/Users/[^\s)`]+"),
        "raw gstack artifact": re.compile(r"(\.gstack|rollout-|raw GStack)", re.IGNORECASE),
        "model cache path": re.compile(r"(Library/Caches|\.cache/huggingface|model-cache)"),
        "credential": re.compile(r"(token|secret|password|cookie|api[_-]?key)\s*=", re.IGNORECASE),
        "stack trace": re.compile(r"Traceback \(most recent call last\):"),
        "non-neutral public positioning": re.compile(
            r"\b(Career|portfolio|resume|interview|showcase)\b",
            re.IGNORECASE,
        ),
    }
    violations: list[Violation] = []
    for file_name in files:
        text = _read_text(root, file_name)
        for label, pattern in patterns.items():
            if pattern.search(text):
                violations.append(
                    Violation(
                        file=file_name,
                        rule="public_boundary",
                        message=f"release-facing file contains {label}",
                    )
                )
    return violations


def audit_release_presentation(root: Path) -> list[Violation]:
    root = root.resolve()
    release_files = _tracked_release_files(root)
    violations: list[Violation] = []
    violations.extend(_audit_version_identity(root))
    violations.extend(_audit_runtime_default(root))
    violations.extend(_audit_readme_presentation(root))
    violations.extend(_audit_comparison_boundary(root, release_files))
    violations.extend(
        _audit_compiled_library_claim_boundary(root, COMPILED_LIBRARY_CLAIM_FILES)
    )
    violations.extend(_audit_release_notes_links(root))
    violations.extend(_audit_stale_status(root, release_files))
    violations.extend(
        _audit_consumer_smoke_wheel_selection(root, CONSUMER_SMOKE_COMMAND_FILES)
    )
    violations.extend(_audit_downstream_candidate_boundary(root))
    violations.extend(_audit_public_boundary(root, release_files))
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit v0.1.2 release presentation docs.")
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    violations = audit_release_presentation(args.root)
    payload = {
        "status": "ok" if not violations else "failed",
        "violations": [asdict(violation) for violation in violations],
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if not violations else 1


if __name__ == "__main__":
    sys.exit(main())
