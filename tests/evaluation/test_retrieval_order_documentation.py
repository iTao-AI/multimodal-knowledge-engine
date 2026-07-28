from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADR = ROOT / "docs/decisions/0012-deterministic-retrieval-order.md"
ARCHITECTURE = ROOT / "docs/explanation/architecture.md"
CI = ROOT / ".github/workflows/ci.yml"
HOW_TO = (
    ROOT
    / "docs/how-to/run-deterministic-retrieval-order-proof.md"
)
NUMERIC_CI_STEP = (
    "Reject archived numeric lock and validate current retrieval-order "
    "compatibility"
)
CANONICAL_RETRIEVAL_ORDER_PATHS = (
    "benchmarks/retrieval/retrieval-order-v1-development-freeze.json",
    "benchmarks/retrieval/retrieval-order-v1-holdout-receipt.json",
    "benchmarks/retrieval/retrieval-order-v1-artifact.json",
    "benchmarks/retrieval/retrieval-order-v2-compatibility-attempt.json",
    "benchmarks/retrieval/retrieval-order-v2-compatibility.json",
)


def _numeric_ci_step() -> tuple[str, str]:
    workflow = CI.read_text(encoding="utf-8")
    marker = "      - name: "
    matches = [
        section
        for section in workflow.split(marker)[1:]
        if "uv run mke eval retrieval-numeric" in section
    ]
    assert len(matches) == 1
    name, _, body = matches[0].partition("\n")
    return name, body


def test_adr_freezes_runtime_order_cursor_and_compatibility_boundary() -> None:
    adr = ADR.read_text(encoding="utf-8")
    architecture = ARCHITECTURE.read_text(encoding="utf-8")
    combined = "\n".join((adr, architecture))

    assert "Status: Accepted" in adr
    for text in (adr, architecture):
        assert (
            "`score, locator_start, locator_kind, locator_end, "
            "source_sha256`"
        ) in text
        assert (
            "`-overlap_count, -overlap_ratio, content_fingerprint, "
            "locator_kind, locator_start, locator_end`"
        ) in text
        assert "FTS orders in SQL by" in text
        assert "CJK active scan orders in Python by" in text
        assert "The CJK key is not SQL-derived." in text
        assert (
            "`source_sha256` binds immutable Source bytes on the FTS "
            "path"
        ) in text
        assert (
            "`content_fingerprint` binds immutable Source bytes on the "
            "CJK active-scan path"
        ) in text
        assert (
            "Publication revision and Evidence text identity are not "
            "current tie-break fields."
        ) in text
        assert "identity fields, not ordering authority" in text
        assert (
            "does not promise one cross-strategy display order"
        ) in text
    for phrase in (
        "revision 2",
        "cursor revision mismatch",
        "active Publications only",
        "tie-only compatibility",
        "atomic no-replace",
        "one-shot",
    ):
        assert phrase in adr
    for non_claim in (
        "GraphRAG",
        "dense retrieval",
        "RRF",
        "reranker",
        "OCR",
        "runtime promotion",
    ):
        assert non_claim in adr
    for inaccurate_claim in (
        "stable semantic SQL key for equal-score active Evidence",
        "Source byte identity, Publication revision, locator, and "
        "Evidence text identity",
        "CJK active scan orders in SQL",
    ):
        assert inaccurate_claim not in combined


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


def test_how_to_states_exact_proof_and_claim_recovery_boundaries() -> None:
    text = HOW_TO.read_text(encoding="utf-8")
    prose = " ".join(text.replace("`", "").split())

    assert (
        "uv run mke eval retrieval-numeric --protocol "
        "tests/fixtures/retrieval-numeric-v1/protocol-lock.json --json"
        in text
    )
    for expected in (
        "strict-live exit `1`",
        "`problem=retrieval_numeric_fixture_invalid`",
        "`cause=protocol-bound input identity mismatch`",
        "`next_step=restore_numeric_protocol_inputs`",
    ):
        assert expected in text
    for expected in (
        "explicit wheel/receipt/input identity preflight",
        "installed module, distribution, strategy revision, and "
        "query-policy revision",
        "validator function availability under Python 3.12 and "
        "Python 3.13",
        "This proof checks validator availability only; it does not "
        "execute either validator. Canonical checkout content is "
        "validated separately by "
        "tests/evaluation/test_retrieval_order_canonical_evidence.py.",
        "real nonsymlink lexical ancestor chain",
        "symlink-alias preclaim rejection is not a durable attempt",
        "complete claim is visible, the durable attempt is terminal",
    ):
        assert expected in prose


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


def test_numeric_ci_step_is_exact_strict_live_negative_control() -> None:
    name, step = _numeric_ci_step()

    assert name == NUMERIC_CI_STEP
    assert 'test "$comparison_status" -eq 1' in step
    assert '0|1)' not in step
    for expected in (
        'p["integrity_status"] == "failed"',
        'p["candidate_status"] == "not_recorded"',
        "len(p[\"integrity_failures\"]) == 1",
        'f["problem"] == "retrieval_numeric_fixture_invalid"',
        'f["cause"] == "protocol-bound input identity mismatch"',
        'f["next_step"] == "restore_numeric_protocol_inputs"',
        'f["subject_id"] is None',
    ):
        assert expected in step
    assert "mke.evaluation.numeric_artifact validate" not in step


def test_numeric_ci_step_has_exact_temporary_compatibility_lane() -> None:
    _, step = _numeric_ci_step()

    assert (
        'TEMPORARY_COMPATIBILITY_JSON="$RUNNER_TEMP/'
        'retrieval-order-v2-compatibility-${{ matrix.python-version }}.json"'
    ) in step
    assert 'test ! -e "$TEMPORARY_COMPATIBILITY_JSON"' in step
    for command in (
        "mke.evaluation.retrieval_order_compatibility record",
        "mke.evaluation.retrieval_order_compatibility validate",
        "--protocol tests/fixtures/retrieval-order-v1/protocol.json",
        '--artifact "$TEMPORARY_COMPATIBILITY_JSON"',
        "--repository . --json",
    ):
        assert command in step
    assert (
        "--artifact benchmarks/retrieval/"
        "retrieval-order-v2-compatibility.json"
        not in step
    )


def test_numeric_ci_step_preserves_all_canonical_paths() -> None:
    _, step = _numeric_ci_step()

    assert "canonical_state_before" in step
    assert "canonical_state_after" in step
    assert "assert canonical_state_before == canonical_state_after" in step
    assert "assert all(value is None for value in canonical_state_before.values())" not in step
    assert "assert all(value is None for value in canonical_state_after.values())" not in step
    for path in CANONICAL_RETRIEVAL_ORDER_PATHS:
        assert step.count(path) == 1


def test_numeric_ci_step_freezes_compatibility_results_and_differential() -> None:
    _, step = _numeric_ci_step()

    for expected in (
        "mke.retrieval_order_compatibility_record_result.v1",
        "mke.retrieval_order_compatibility_validate_result.v1",
        '"mode": "record"',
        '"mode": "validate"',
        '"authority_layer": "archive_current_differential"',
        '"authority_layer": "artifact_validation"',
        '"output_state": "complete_visible"',
        '"output_state": "complete_preexisting"',
        '"publication_outcome": "published"',
        '"publication_outcome": "not_attempted"',
        'artifact["integrity_status"] == "passed"',
        'artifact["compatibility_status"] == "passed"',
        "len(families) == 7",
        "membership_delta",
        "score_hex_delta",
        "non_tied_pair_delta",
        "metric_delta",
        "gate_delta",
        "verdict_delta",
        "no_ordered_delta_authority",
        "deterministic_historical_subprocess_replay",
    ):
        assert expected in step
