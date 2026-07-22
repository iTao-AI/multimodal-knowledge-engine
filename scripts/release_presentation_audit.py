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

EXPECTED_VERSION = "0.1.3"
RUNTIME_STRATEGY = "cjk-active-scan-overlap-v1"

RELEASE_FACING_FILES = (
    "README.md",
    "README_CN.md",
    "docs/README.md",
    "CHANGELOG.md",
    "docs/releases/v0.1.3.md",
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
DIRECT_AUDIO_CLAIM_FILES = (
    "README.md",
    "README_CN.md",
    "docs/README.md",
    "docs/decisions/0011-bounded-direct-audio-intake.md",
    "docs/explanation/architecture.md",
    "docs/how-to/use-direct-audio.md",
    "docs/how-to/run-direct-audio-proof.md",
    "docs/how-to/use-local-transcription.md",
    "docs/how-to/use-mke-mcp.md",
    "docs/how-to/export-compiled-library.md",
    "docs/reference/cli.md",
    "docs/reference/contracts.md",
    "docs/reference/mcp-contract.md",
    "docs/tutorials/getting-started.md",
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
    "docs/releases/v0.1.3.md",
)
HISTORICAL_RELEASE_FILES = ("docs/releases/v0.1.2.md",)
CONSUMER_SMOKE_COMMAND_FILES = (
    "README.md",
    "README_CN.md",
    "docs/releases/v0.1.3.md",
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
        pyproject_version = (
            tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
            .get("project", {})
            .get("version")
        )
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
            "heading": "## Verified in v0.1.3",
            "header": "| Capability | Evidence |",
            "message": "English README must include the Verified in v0.1.3 capability table",
        },
        "README_CN.md": {
            "heading": "## v0.1.3 已验证能力",
            "header": "| 能力 | 验证证据 |",
            "message": "Chinese README must include localized v0.1.3 verified capability labels",
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
            "## v0.1.3 工程深度",
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
                    message="README must include the v0.1.3 Mermaid architecture diagram",
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
                    rule="verified_v013_table",
                    message=labels["message"],
                )
            )
        if not _contains_all_terms(text, engineering_depth_terms_by_file[file_name]):
            violations.append(
                Violation(
                    file=file_name,
                    rule="readme_engineering_depth",
                    message=(
                        "README must explain v0.1.3 engineering depth and retrieval "
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
        mentions_retrieval_family = all(term in lowered for term in ("dense", "rrf", "reranker"))
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
            r"\bpaddleocr-vl 1\.6\b.*\b(?:promoted|default) provider\b",
            (
                r"\bnot\b.*\bpaddleocr-vl 1\.6\b.*\b(?:promoted|default) provider\b",
                r"\bpaddleocr-vl 1\.6\b.*\bnot\b.*\b(?:promoted|default) provider\b",
            ),
        ),
        (
            r"\bpublic ocr runtime\b",
            (
                r"\b(?:no|not a) public ocr runtime\b",
                r"\bnot\b.*\bpublic ocr runtime\b",
                r"\bdoes not (?:claim|provide|ship|support)\b.*\bpublic ocr runtime\b",
            ),
        ),
        (
            r"\bgeneral ocr quality\b",
            (
                r"\b(?:no|not) general ocr quality\b",
                r"\bdoes not\b.*\bgeneral ocr quality\b",
                r"\bdoes not (?:claim|provide|validate|prove|support)\b.*\bgeneral ocr quality\b",
            ),
        ),
        (
            r"\bproduction ocr\b",
            (
                r"\b(?:is |are )?not\b.*\bproduction ocr\b",
                r"\bdoes not (?:claim|validate|provide|support)\b.*\bproduction ocr\b",
                r"\bproduction ocr remains excluded\b",
                r"\b不是 production ocr\b",
            ),
        ),
        (
            r"\b(?:reconstructs?|reconstructed|recovers?|recovered) (?:the )?(?:source )?layout\b",
            (
                r"\b(?:is |are )?not\b.*\b"
                r"(?:reconstruct(?:ed)?|recover(?:ed)?) (?:source )?layout\b",
                r"\bdoes not (?:claim|validate|provide|reconstruct|recover)\b.*\b"
                r"(?:reconstruct(?:ed)?|recover(?:ed)?) (?:source )?layout\b",
                r"\b不重建 layout\b",
            ),
        ),
        (
            r"\b(?:verified|proven|supports?) llm wiki compatibility\b",
            (
                r"\bnot (?:verified|proven) llm wiki compatibility\b",
                r"\bdoes not (?:verify|prove|support) llm wiki compatibility\b",
                r"\bllm wiki compatibility remains deferred\b",
            ),
        ),
        (
            r"\bhosted integration\b",
            (
                r"\bno hosted integration\b",
                r"\bdoes not (?:claim|validate|prove|provide|support)\b.*\bhosted integration\b",
            ),
        ),
        (
            r"\breal-user adoption\b",
            (
                r"\bno real-user adoption\b",
                r"\bdoes not (?:claim|validate|prove|provide|support)\b.*\breal-user adoption\b",
            ),
        ),
        (
            r"\bgithub release\b.*\b(?:includes?|contains?|ships?|uploads?)\b.*\bextra assets?\b",
            (
                r"\b(?:no|zero) extra assets?\b",
                r"\bdoes not (?:include|contain|ship|upload)\b.*\bextra assets?\b",
            ),
        ),
        (
            r"\bdeployed in production\b",
            (
                r"\bnot deployed in production\b",
                r"\bdoes not (?:claim|validate|prove)\b.*\bdeployed in production\b",
            ),
        ),
        (
            r"\bproduction adoption\b",
            (
                r"\bno production adoption\b",
                r"\bdoes not (?:claim|validate|prove|provide|support)\b.*\bproduction adoption\b",
                r"\bproduction adoption\b.*\b(?:claim|claims)? ?(?:remain )?excluded\b",
            ),
        ),
        (
            r"\bbusiness[- ]impact\b",
            (
                r"\bno business[- ]impact\b",
                r"\bdoes not (?:claim|validate|prove|provide|deliver|support)\b.*\b"
                r"business[- ]impact\b",
                r"\bbusiness[- ]impact claims remain excluded\b",
            ),
        ),
        (
            r"\b(?:pypi|package registr(?:y|ies))\b.*\b(?:published|available)\b",
            (
                r"\b(?:pypi|package registr(?:y|ies))\b.*\bnot (?:published|available)\b",
                r"\bno (?:pypi|package registry) publication\b",
                r"\b(?:pypi|package registry) publication remains (?:excluded|deferred)\b",
            ),
        ),
        (
            r"\b(?:published|available)\b.*\b(?:on|from) (?:pypi|the package registry)\b",
            (
                r"\bnot (?:published|available)\b.*\b(?:on|from) "
                r"(?:pypi|the package registry)\b",
            ),
        ),
        (
            r"\bv0\.1\.3\b.*\b(?:released|published|available)\b",
            (r"\bdoes not release v0\.1\.3\b", r"\bv0\.1\.3 is not released\b"),
        ),
    )
    clauses = re.split(r"(?:[;!?]+|\.\s+|,\s+but\s+)", lowered)
    return any(
        re.search(pattern, clause) is not None
        and not any(re.search(marker, clause) for marker in safe_markers)
        for clause in clauses
        for pattern, safe_markers in claims
    )


def _markdown_claim_contexts(text: str) -> list[tuple[int, str]]:
    contexts: list[tuple[int, str]] = []
    paragraph: list[str] = []
    paragraph_start = 0
    fenced = False

    def flush() -> None:
        nonlocal paragraph, paragraph_start
        if paragraph:
            contexts.append((paragraph_start, " ".join(paragraph)))
            paragraph = []
            paragraph_start = 0

    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            flush()
            fenced = not fenced
            continue
        if fenced:
            if stripped:
                contexts.append((line_number, line))
            continue
        if not stripped:
            flush()
            continue
        if re.match(r"^(?:#{1,6}\s|\||>)", stripped):
            flush()
            contexts.append((line_number, line))
            continue
        if re.match(r"^(?:[-+*]|\d+[.)])\s", stripped):
            flush()
        if not paragraph:
            paragraph_start = line_number
        paragraph.append(line)
    flush()
    return contexts


def _audit_compiled_library_claim_boundary(root: Path, files: Iterable[str]) -> list[Violation]:
    violations: list[Violation] = []
    for file_name in files:
        text = _read_text(root, file_name)
        for line_number, context in _markdown_claim_contexts(text):
            if _line_overclaims_compiled_library(context):
                violations.append(
                    Violation(
                        file=file_name,
                        rule="compiled_library_overclaim",
                        message=f"line {line_number} exceeds the compiled Library claim boundary",
                    )
                )
    return violations


def _line_overclaims_direct_audio(line: str) -> bool:
    lowered = " ".join(line.casefold().split())
    clauses = re.split(
        r"(?:[;!?；！？。]+|\.\s+|,\s+but\s+|(?:，|,)\s*(?:但|但是)\s*|"
        r"\s+(?:but|while|although|但|但是)\s+|"
        r"\s+and\s+(?=(?:mke|direct[- ]audio|terminal|has|is|offers?|provides?|supports?|"
        r"process(?:es|ing)?|downloads?|produces?|deploys?|verified|redistribut(?:e|es|ed|ing))\b|"
        r"(?:终端|已验证|重新分发)))",
        lowered,
    )
    authority_affirmatives = (
        r"\bterminal\b.*\breal\s+asr\b.*\bproof\b.*\b(?:passed|verified|completed|successful)\b",
        r"\bterminal\b.*\bproof\b.*\b(?:ran|performed|executed)\b.*\breal\s+asr\b",
        r"\b(?:verified|validated|proved)\b.*\breal\s+asr\b",
        r"\bredistribut(?:e|es|ed|ing)\b.*\bexternal\b.*\b(?:wheels?|native binaries)\b",
        r"\bmke\b.*\b(?:bundl(?:e|es|ed|ing)|packag(?:e|es|ed|ing))\b.*"
        r"\bexternal\b.*\b(?:wheels?|native binaries)\b",
        r"终端.*真实\s*asr.*(?:证明|验证).*(?:已通过|通过|完成|已验证)",
        r"终端.*证明.*(?:运行|执行|完成)(?:了)?.*真实\s*asr",
        r"已验证.*真实\s*asr",
        r"重新分发.*外部.*(?:wheels?|原生二进制)",
        r"mke.*(?:打包|捆绑).*外部.*(?:wheels?|原生二进制)",
    )
    authority_negations = (
        r"\b(?:does not|do not|did not)\s+"
        r"(?:run|perform|execute|verify|redistribute|bundle|package)\b",
        r"\b(?:has|have|was|is)\s+not\s+(?:been\s+)?"
        r"(?:run|performed|executed|verified|redistributed|bundled|packaged)\b",
        r"\bnot\s+(?:run|performed|executed|verified|redistributed|bundled|packaged)\b",
        r"(?:尚未|没有|未)(?:运行|执行|完成|验证|重新分发|打包|捆绑)",
        r"不(?:重新分发|打包|捆绑)",
    )
    if any(
        re.search(pattern, clause) is not None
        and not any(re.search(marker, clause) for marker in authority_negations)
        for clause in clauses
        for pattern in authority_affirmatives
    ):
        return True
    bounded_adverb = r"(?:currently|automatically|implicitly|explicitly|yet)"
    negated_verb_prefix = rf"(?:does not|do not|not)(?:\s+{bounded_adverb})*\s+$"
    explicit_affirmatives = (
        r"\bsupports?\s+arbitrary\b.*\b(?:audio|container|codec)s?\b",
        r"\b(?:supports?|process(?:es|ing))\s+full[- ]length\b",
        r"\b(?:supports?|process(?:es|ing))\s+long[- ]audio\b",
        r"\bautomatically downloads?\b.*\b(?:model|weights?)s?\b",
        r"\bprovides?\s+(?:a\s+)?cloud\s+asr\s+fallback\b",
        r"\bproduces?\s+accurate transcripts?\b",
    )
    for pattern in explicit_affirmatives:
        for match in re.finditer(pattern, lowered):
            prefix = lowered[max(0, match.start() - 64) : match.start()]
            if not re.search(negated_verb_prefix, prefix):
                return True
    safe_marker_patterns = (
        rf"\bdoes not(?:\s+{bounded_adverb})*\s+"
        r"(?:support|provide|offer|download|fall back|claim|authorize)\b",
        rf"\bnot(?:\s+{bounded_adverb})*\s+(?:supported|production ready|included)\b",
        r"\bare excluded\b",
        r"\bremain excluded\b",
        r"\boutside\b",
        r"\bno automatic\b",
        r"\bno implicit\b",
        r"\bclips (?:or|and) excerpts\b",
        r"并非",
        r"不提供",
        r"不声明",
        r"排除",
        r"之外",
    )
    patterns = (
        r"\barbitrary\b.*\b(?:audio|container|codec)s?\b",
        r"\bfull[- ]length\b.*\b(?:meeting|interview|lecture)s?\b",
        (
            r"\bmke\b.*\b(?:supports?|process(?:es|ing)|transcribes?|ingests?)\b.*"
            r"\b(?:meetings|interviews|lectures)\b"
        ),
        r"\b(?:supports?|process(?:es|ing))\b.*\blong[- ]audio\b",
        (
            r"\bmke\b.*\b(?:chunks?|resumes?|stream(?:s|ing)?|"
            r"diari[sz](?:e|ation)|microphone capture)\b"
        ),
        r"\bdownloads?\b.*\b(?:model|weights?)s?\b.*\bautomatically\b",
        r"\bautomatically downloads?\b.*\b(?:model|weights?)s?\b",
        r"\b(?:falls? back|fallback)\b.*\bcloud\b.*\basr\b",
        r"\bprovides?\b.*\bcloud\b.*\basr\b.*\bfallback\b",
        r"\bautomatically syncs?\b.*\bllm wiki\b",
        r"\b(?:across|on) all platforms\b",
        r"\bguarantees?\b.*\btranscript accuracy\b",
        r"\bproduces?\b.*\baccurate transcripts?\b",
        r"\b(?:audio|direct[- ]audio)\b.*\bsla\b",
        r"\bdeploys?\b.*\bdirect[- ]audio\b.*\bproduction\b",
        r"\bproduction adoption\b",
        r"\bbusiness[- ]impact\b",
        r"\b(?:published|available)\b.*\b(?:on|from) pypi\b",
        r"\bhosted\b.*\btranscription\b.*\bfallback\b",
        r"\b(?:offers?|provides?)\b.*\bcloud transcription\b.*\blocal asr fails\b",
        r"\b(?:direct[- ]audio|audio)\b.*\b(?:is|are) production[- ]ready\b",
        r"\bcross[- ]platform\b.*\b(?:coverage|support)\b",
        r"\bofficial\b.*\bopenai\b.*\b(?:integration|support)\b",
        r"\bofficial\b.*\bllm wiki\b.*\b(?:integration|support)\b",
        r"任意.*(?:音频|容器|编解码)",
        r"(?:完整|全长).*(?:会议|访谈|采访|讲座)",
        r"mke.*(?:支持|处理|转写|摄取).*(?:会议|访谈|采访|讲座)",
        r"(?:支持|处理).*长音频",
        r"mke.*(?:分块|断点续传|流式|说话人分离|麦克风)",
        r"自动下载.*模型",
        r"(?:云端|云).*(?:asr|转写|回退)",
        r"自动.*llm wiki",
        r"(?:所有平台|全平台|跨平台支持)",
        r"(?:保证.*转写|转写.*保证)",
        r"(?:direct[- ]audio|音频).*sla",
        r"(?:direct[- ]audio|音频).*(?:生产部署|部署到生产)",
        r"openai.*官方.*(?:集成|支持)",
    )
    return any(
        re.search(pattern, clause) is not None
        and not any(re.search(marker, clause) for marker in safe_marker_patterns)
        for clause in clauses
        for pattern in patterns
    )


def _audit_direct_audio_claim_boundary(root: Path, files: Iterable[str]) -> list[Violation]:
    violations: list[Violation] = []
    for file_name in files:
        text = _read_text(root, file_name)
        for line_number, context in _markdown_claim_contexts(text):
            if _line_overclaims_direct_audio(context):
                violations.append(
                    Violation(
                        file=file_name,
                        rule="direct_audio_overclaim",
                        message=f"line {line_number} exceeds the direct-audio claim boundary",
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
    release_notes = _read_text(root, "docs/releases/v0.1.3.md")
    for term in required_terms:
        if term.lower() not in release_notes.lower():
            violations.append(
                Violation(
                    file="docs/releases/v0.1.3.md",
                    rule="release_notes_links",
                    message=f"release notes must link or name {term}",
                )
            )
    return violations


def _audit_v013_contract(root: Path) -> list[Violation]:
    file_name = "docs/releases/v0.1.3.md"
    text = _read_text(root, file_name)
    required_terms = (
        "Compiled Library Export",
        "mke.compiled_library_export.v1",
        "mke.compiled_markdown.v1",
        "mke.evidence_ref.v1",
        "OCR Phase 0",
        "PP-OCRv6 medium",
        "PaddleOCR-VL 1.6",
        "not production OCR",
        "LLM Wiki compatibility is deferred",
        RUNTIME_STRATEGY,
    )
    if _contains_all_terms(text, required_terms):
        return []
    return [
        Violation(
            file=file_name,
            rule="v013_release_contract",
            message="v0.1.3 release notes must preserve the closed export and OCR boundaries",
        )
    ]


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
    exact_wheel = "dist/multimodal_knowledge_engine-0.1.3-py3-none-any.whl"
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
        if "dist/*.whl" in text or any(
            old_wheel in text
            for old_wheel in (
                "multimodal_knowledge_engine-0.1.1-py3-none-any.whl",
                "multimodal_knowledge_engine-0.1.2-py3-none-any.whl",
            )
        ):
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
            r"\b(Career|portfolio|resume|showcase|interview artifact)\b",
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
    violations.extend(_audit_compiled_library_claim_boundary(root, COMPILED_LIBRARY_CLAIM_FILES))
    violations.extend(_audit_direct_audio_claim_boundary(root, DIRECT_AUDIO_CLAIM_FILES))
    violations.extend(_audit_release_notes_links(root))
    violations.extend(_audit_v013_contract(root))
    violations.extend(_audit_stale_status(root, release_files))
    violations.extend(_audit_consumer_smoke_wheel_selection(root, CONSUMER_SMOKE_COMMAND_FILES))
    violations.extend(_audit_downstream_candidate_boundary(root))
    violations.extend(_audit_public_boundary(root, release_files))
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit v0.1.3 release presentation docs.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true", help="emit the closed JSON result")
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
