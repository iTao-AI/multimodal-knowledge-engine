from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXACT_CLAIM = (
    "MKE can deterministically export active Publications as portable Markdown with exact page or "
    "timestamp Evidence provenance, validated through an installed-wheel external consumer proof."
)


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
        "LLM Wiki compatibility is deferred",
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
