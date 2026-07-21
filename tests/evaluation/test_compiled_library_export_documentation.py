import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXACT_CLAIM = (
    "MKE can deterministically export active Publications as portable Markdown with exact page or "
    "timestamp Evidence provenance, validated through an installed-wheel external consumer proof."
)
EXACT_ENGLISH_COMPATIBILITY_CLAIM = (
    "The exported Markdown was ingested and compiled in an isolated LLM Wiki workflow, "
    "preserving a return path to MKE's authoritative content fingerprint and Evidence sidecars "
    "for local-Agent use."
)
EXACT_CHINESE_COMPATIBILITY_CLAIM = (
    "导出的 Markdown 已在隔离的 LLM Wiki 工作流中完成摄取与编译，并保留了回到 MKE 权威 "
    "content fingerprint 和 Evidence sidecar 的路径，供本地 Agent 使用。"
)
EXACT_ENGLISH_RELEASE_FRAMING = (
    "v0.1.3's generic proof did not verify LLM Wiki compatibility; separate post-release "
    "acceptance evidence is recorded below."
)
EXACT_CHINESE_RELEASE_FRAMING = (
    "v0.1.3 的 generic proof 未验证 LLM Wiki compatibility；下方记录了单独的 post-release "
    "acceptance evidence。"
)
EXACT_ENGLISH_COMPATIBILITY_BOUNDARY = (
    "This evidence does not make LLM Wiki an MKE dependency or Evidence authority, and it does "
    "not provide a bundled adapter, automatic sync, hosted service, production deployment, "
    "real-user adoption, or general multimodal understanding. LLM Wiki compatibility was not "
    "shipped by v0.1.3."
)
EXACT_CHINESE_COMPATIBILITY_BOUNDARY = (
    "这项证据不会使 LLM Wiki 成为 MKE dependency 或 Evidence authority，也不提供 bundled "
    "adapter、automatic sync、hosted service 或 production deployment，也不证明真实用户采用或"
    "通用多模态理解。LLM Wiki compatibility 并非由 v0.1.3 交付。"
)
FORBIDDEN_COMPATIBILITY_CLAIMS = (
    "LLM Wiki is an MKE dependency",
    "LLM Wiki is MKE's Evidence authority",
    "MKE includes a bundled LLM Wiki adapter",
    "MKE automatically syncs exports to LLM Wiki",
    "MKE provides a hosted LLM Wiki service",
    "MKE deploys LLM Wiki in production",
    "This proves real-user adoption",
    "This proves general multimodal understanding",
    "v0.1.3 shipped LLM Wiki compatibility",
)
V013_RELEASE_SHA256 = "85aa1ba71cfc9df18ccd8655d7f3de82434c77cff0b8729a53968471fc5e22e0"


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _normalized(relative: str) -> str:
    return " ".join(_text(relative).split())


def test_readmes_and_docs_index_make_compiled_library_export_discoverable() -> None:
    assert "docs/how-to/export-compiled-library.md" in _text("README.md")
    assert "docs/how-to/export-compiled-library.md" in _text("README_CN.md")
    assert "how-to/export-compiled-library.md" in _text("docs/README.md")
    assert "how-to/run-compiled-library-export-proof.md" in _text("docs/README.md")
    assert EXACT_CLAIM in _normalized("README.md").replace("> ", "")
    assert EXACT_CLAIM in _normalized("README_CN.md").replace("> ", "")


def test_public_docs_publish_the_localized_approved_llm_wiki_compatibility_claims() -> None:
    assert EXACT_ENGLISH_COMPATIBILITY_CLAIM in _normalized("README.md").replace("> ", "")
    assert EXACT_ENGLISH_COMPATIBILITY_CLAIM in _normalized(
        "docs/how-to/export-compiled-library.md"
    ).replace("> ", "")
    assert EXACT_CHINESE_COMPATIBILITY_CLAIM in _normalized("README_CN.md").replace("> ", "")


def test_readmes_frame_compatibility_as_separate_post_release_evidence() -> None:
    assert EXACT_ENGLISH_RELEASE_FRAMING in _normalized("README.md")
    assert EXACT_CHINESE_RELEASE_FRAMING in _normalized("README_CN.md")


def test_public_docs_preserve_the_full_compatibility_claim_boundary() -> None:
    for relative in ("README.md", "docs/how-to/export-compiled-library.md"):
        assert EXACT_ENGLISH_COMPATIBILITY_BOUNDARY in _normalized(relative)
    assert EXACT_CHINESE_COMPATIBILITY_BOUNDARY in _normalized("README_CN.md")

    public_text = "\n".join(
        _text(relative)
        for relative in ("README.md", "README_CN.md", "docs/how-to/export-compiled-library.md")
    ).casefold()
    for claim in FORBIDDEN_COMPATIBILITY_CLAIMS:
        assert claim.casefold() not in public_text


def test_v013_release_history_remains_byte_identical() -> None:
    release_bytes = (ROOT / "docs/releases/v0.1.3.md").read_bytes()
    assert hashlib.sha256(release_bytes).hexdigest() == V013_RELEASE_SHA256


def test_cli_reference_documents_the_closed_export_command_and_response() -> None:
    text = _normalized("docs/reference/cli.md")
    for term in (
        "mke --db <library.sqlite3> library export --output <new-child-directory> [--json]",
        "mke.compiled_library_export_response.v1",
        "library_export=passed library_id=local source_count=<count> evidence_count=<count> "
        "manifest_sha256=<sha256>",
        "active_publication_impact",
        "unchanged",
        "--retrieval-query-policy",
        "--retrieval-strategy",
    ):
        assert term in text


def test_contract_reference_documents_exact_export_schemas_and_authority() -> None:
    text = _normalized("docs/reference/contracts.md")
    for term in (
        "mke.compiled_library_export.v1",
        "mke.compiled_markdown.v1",
        "mke.evidence_ref.v1",
        "mke.active_publication_observation.v1",
        "mke.compiled_library_export_response.v1",
        "JSONL EvidenceRef records remain the machine authority",
        "Markdown is a readable derivative",
    ):
        assert term in text


def test_export_how_to_documents_budgets_read_only_publication_and_exclusions() -> None:
    text = _normalized("docs/how-to/export-compiled-library.md")
    for term in (
        "4,096 active Publications",
        "65,536 active Evidence records",
        "128 MiB",
        "64 MiB",
        "read-only",
        "export-manifest.json",
        "final artifact operation",
        "does not read or include original Source files",
        "Markdown is a readable derivative",
        "JSONL EvidenceRef records remain the machine authority",
        "exactly two content checks",
        "The compiled article remains a downstream synthesized view",
        "content_fingerprint",
        "fixed synthetic corpus",
        "not production OCR",
    ):
        assert term in text


def test_export_proof_how_to_is_generic_installed_wheel_evidence_only() -> None:
    text = _normalized("docs/how-to/run-compiled-library-export-proof.md")
    for term in (
        "UV_OFFLINE=1 uv build",
        "scripts/compiled_library_export_proof.py",
        '--python "$PYTHON312" --python "$PYTHON313" --json',
        "installed-wheel external consumer proof",
        "does not verify LLM Wiki compatibility",
        "running the proof does not publish a release",
    ):
        assert term in text


def test_architecture_documents_snapshot_and_original_source_boundaries() -> None:
    text = _normalized("docs/explanation/architecture.md")
    for term in (
        "read-only compiled Library export",
        "one SQLite transaction",
        "manifest as the final commit marker",
        "does not read original Source files",
        "Markdown remains derivative",
        "EvidenceRef JSONL remains authoritative",
    ):
        assert term in text
