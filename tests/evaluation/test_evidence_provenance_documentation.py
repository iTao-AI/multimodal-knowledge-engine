from pathlib import Path


def test_public_docs_cover_versioned_evidence_provenance_contract() -> None:
    paths = [
        Path("README.md"),
        Path("README_CN.md"),
        Path("docs/reference/mcp-contract.md"),
        Path("docs/how-to/use-mke-mcp.md"),
        Path("docs/how-to/run-evidence-provenance-proof.md"),
        Path("docs/explanation/architecture.md"),
        Path("docs/decisions/0009-versioned-evidence-provenance-contract.md"),
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for required in (
        "mke.evidence_ref.v1",
        "mke.active_publication_observation.v1",
        "mke.list_libraries_response.v1",
        "mke.search_library_response.v1",
        "mke.ask_library_response.v1",
        "list_libraries_v1",
        "search_library_v1",
        "ask_library_v1",
        "no_active_publication",
        "content_fingerprint",
        "publication_revision",
        "scripts/evidence_provenance_proof.py",
    ):
        assert required in text


def test_durable_provenance_docs_record_post_merge_closeout() -> None:
    spec = Path(
        "docs/superpowers/specs/2026-07-11-versioned-evidence-provenance-contract-design.md"
    ).read_text(encoding="utf-8")
    plan = Path(
        "docs/superpowers/plans/2026-07-11-versioned-evidence-provenance-contract-implementation.md"
    ).read_text(encoding="utf-8")
    review = Path(
        "docs/superpowers/reviews/2026-07-11-versioned-evidence-provenance-contract-implementation-review.md"
    ).read_text(encoding="utf-8")
    durable_docs = "\n".join((spec, plan, review))

    assert "PR #63" in durable_docs
    assert "0ccc82874e2a4a01e01badcf959ba5a5e0dcbc13" in durable_docs
    assert "Post-merge checks: passed" in durable_docs
    assert "authoritative targeted re-review: `CLEAN / 0 findings`" in durable_docs
    assert "approved for local implementation" not in spec
    assert (
        "**VERDICT:** ENG + OUTSIDE VOICE CLEARED — ready for isolated local implementation."
        not in plan
    )
