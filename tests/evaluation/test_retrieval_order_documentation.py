from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADR = ROOT / "docs/decisions/0012-deterministic-retrieval-order.md"
HOW_TO = (
    ROOT
    / "docs/how-to/run-deterministic-retrieval-order-proof.md"
)


def test_adr_freezes_runtime_order_cursor_and_compatibility_boundary() -> None:
    text = ADR.read_text(encoding="utf-8")

    assert "Status: Accepted" in text
    for phrase in (
        "stable semantic SQL key",
        "revision 2",
        "cursor revision mismatch",
        "active Publications only",
        "tie-only compatibility",
        "atomic no-replace",
        "one-shot",
    ):
        assert phrase in text
    for non_claim in (
        "GraphRAG",
        "dense retrieval",
        "RRF",
        "reranker",
        "OCR",
        "runtime promotion",
    ):
        assert non_claim in text


def test_how_to_freezes_authority_mapping_and_fast_to_expensive_order() -> None:
    text = HOW_TO.read_text(encoding="utf-8")

    expected_order = (
        "## 1. Run Fast Preflight",
        "## 2. Record Temporary Compatibility",
        "## 3. Run The Full Candidate Gate",
        "## 4. Record Development Once",
        "## 5. Observe Holdout Once",
        "## 6. Record Canonical Compatibility Once",
        "## 7. Publish The Task 8R Attempt Claim",
        "## 8. Prove The Exact Installed Wheel",
    )
    offsets = [text.index(heading) for heading in expected_order]
    assert offsets == sorted(offsets)
    for boundary in (
        "archive validation -> historical bytes are self-consistent only",
        "current replay -> current runtime compatibility only",
        "differential validation -> revision-2 comparison only",
        "temporary output -> never canonical authority",
    ):
        assert boundary in text
    for command in (
        "`mke eval retrieval-numeric`",
        "`retrieval_order_compatibility record`",
        "`retrieval_order_compatibility validate`",
        "`retrieval_order_compatibility record-canonical`",
    ):
        assert command in text
    for schema in (
        "mke.retrieval_order_compatibility_record_result.v1",
        "mke.retrieval_order_compatibility_validate_result.v1",
        "mke.retrieval_order_compatibility_record_canonical_result.v1",
    ):
        assert schema in text
    assert "does not predict" in text
    assert "holdout will pass" not in text


def test_retrieval_order_docs_are_linked_and_public_neutral() -> None:
    linked_paths = (
        ROOT / "docs/explanation/architecture.md",
        ROOT / "docs/reference/contracts.md",
        ROOT / "docs/reference/mcp-contract.md",
        ROOT / "docs/reference/cli.md",
        ROOT / "docs/how-to/use-mke-mcp.md",
        ROOT / "docs/how-to/enable-cjk-retrieval.md",
        ROOT / "docs/README.md",
    )
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in linked_paths
    )

    assert combined.count("deterministic retrieval order") >= 7
    assert "run-deterministic-retrieval-order-proof.md" in combined
    assert "0012-deterministic-retrieval-order.md" in combined
    for private_marker in (
        "/Users/" + "mac",
        ".g" + "stack",
        "Car" + "eer",
    ):
        assert private_marker not in combined
