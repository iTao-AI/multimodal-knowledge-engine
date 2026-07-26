# Run The Deterministic Retrieval Order Proof

This maintainer workflow verifies deterministic retrieval order from cheap read-only checks to
expensive installed proof. Canonical development, holdout, compatibility, candidate, and installed
steps require their separate approval gates. This guide does not predict an unobserved result or
authorize a one-shot command.

The four authority boundaries are exact:

```text
archive validation -> historical bytes are self-consistent only
current replay -> current runtime compatibility only
differential validation -> revision-2 comparison only
temporary output -> never canonical authority
```

## Command Authority

| Command | Authority and expected boundary |
|---|---|
| `mke eval retrieval-numeric` | strict live authority; a stale checked-in lock exits 1 with the existing `retrieval_numeric_fixture_invalid` contract |
| `retrieval_order_compatibility record` | archive self-consistency + current replay + differential; temporary/noncanonical only |
| `retrieval_order_compatibility validate` | pure read-only validation of an existing artifact's archive/current/differential/canonical states |
| `retrieval_order_compatibility record-canonical` | one-shot publication only after successful holdout and candidate seal |

The compatibility commands return independent schemas:
`mke.retrieval_order_compatibility_record_result.v1`,
`mke.retrieval_order_compatibility_validate_result.v1`, and
`mke.retrieval_order_compatibility_record_canonical_result.v1`. Exit `0` is success, exit `1` is a
stable failed gate, and invalid CLI usage exits `2`.

## 1. Run Fast Preflight

Run focused tests and the strict live numeric command before any one-shot output:

```bash
uv run pytest -q \
  tests/evaluation/test_retrieval_order_protocol.py \
  tests/evaluation/test_retrieval_order_workflow.py \
  tests/evaluation/test_retrieval_order_artifact.py
uv run mke eval retrieval-numeric
```

A stale numeric source lock is a strict-live failure, not a compatibility-closure failure.

## 2. Record Temporary Compatibility

Use a new temporary path outside canonical benchmark paths:

```bash
uv run python -m mke.evaluation.retrieval_order_compatibility record \
  --protocol tests/fixtures/retrieval-order-v1/protocol.json \
  --artifact "$TEMPORARY_COMPATIBILITY_JSON" \
  --repository . --json
uv run python -m mke.evaluation.retrieval_order_compatibility validate \
  --protocol tests/fixtures/retrieval-order-v1/protocol.json \
  --artifact "$TEMPORARY_COMPATIBILITY_JSON" \
  --repository . --json
```

`validate` reads and cross-binds existing bytes only. It does not replay retrieval.

## 3. Run The Full Candidate Gate

Run the historical matrix, full suite, Ruff, Pyright, build, and the repository CI-parity commands.
The candidate is not sealed until all required gates pass at one clean HEAD.

## 4. Record Development Once

Only after explicit development authorization:

```bash
uv run python -m mke.evaluation.retrieval_order_workflow development \
  --protocol tests/fixtures/retrieval-order-v1/protocol.json \
  --record-development-freeze \
  benchmarks/retrieval/retrieval-order-v1-development-freeze.json --json
```

The no-replace freeze is bound to the exact candidate seal.

## 5. Observe Holdout Once

Only after the development freeze and a separate one-shot holdout authorization:

```bash
uv run python -m mke.evaluation.retrieval_order_workflow holdout \
  --protocol tests/fixtures/retrieval-order-v1/protocol.json \
  --development-freeze \
  benchmarks/retrieval/retrieval-order-v1-development-freeze.json \
  --record-holdout-receipt \
  benchmarks/retrieval/retrieval-order-v1-holdout-receipt.json \
  --record benchmarks/retrieval/retrieval-order-v1-artifact.json --json
```

The typed capability is issued only after the complete receipt is visible and is consumed once.

## 6. Record Canonical Compatibility Once

Only after a successful holdout artifact and candidate seal:

```bash
uv run python -m mke.evaluation.retrieval_order_compatibility record-canonical \
  --protocol tests/fixtures/retrieval-order-v1/protocol.json \
  --development-freeze benchmarks/retrieval/retrieval-order-v1-development-freeze.json \
  --holdout-receipt benchmarks/retrieval/retrieval-order-v1-holdout-receipt.json \
  --retrieval-artifact benchmarks/retrieval/retrieval-order-v1-artifact.json \
  --candidate-head "$CANDIDATE_SEAL_SHA" \
  --attempt-receipt benchmarks/retrieval/retrieval-order-v2-compatibility-attempt.json \
  --artifact benchmarks/retrieval/retrieval-order-v2-compatibility.json \
  --repository . --json
```

The attempt receipt is published before replay. Any later failure retains it and closes retry.

## 7. Publish The Task 8R Attempt Claim

Task 8R alone may run the real two-interpreter source-pack proof with all three qualifying inputs:

```bash
UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py \
  --python "$PYTHON_312" --python "$PYTHON_313" \
  --candidate-output "$CANDIDATE_OUTPUT" \
  --attempt-claim "$EXTERNAL_ATTEMPT_CLAIM" --json
```

The external no-replace claim is complete before build or child execution. It is retained on any
later failure.

## 8. Prove The Exact Installed Wheel

Use only the prebuilt wheel named and hashed by the candidate receipt:

```bash
uv run python scripts/retrieval_order_installed_proof.py \
  --python "$PYTHON_312" --python "$PYTHON_313" \
  --mke-wheel "$EXACT_CANDIDATE_WHEEL" \
  --candidate-receipt "$CANDIDATE_RECEIPT" \
  --protocol "$COPIED_PROTOCOL" \
  --development-freeze "$COPIED_DEVELOPMENT_FREEZE" \
  --holdout-receipt "$COPIED_HOLDOUT_RECEIPT" \
  --artifact "$COPIED_RETRIEVAL_ARTIFACT" \
  --compatibility "$COPIED_COMPATIBILITY_ARTIFACT" --json
```

The installed proof never discovers, chooses, or rebuilds a wheel.

## Recovery And Non-claims

No-replace failure leaves the destination absent or complete. Complete visible bytes with
unconfirmed directory durability are terminal; retain them and stop. Never delete or overwrite an
attempt to manufacture a retry.

Passing evidence would establish deterministic revision-2 order under the frozen corpus and
specified runtimes only. It does not establish retrieval quality improvement, runtime promotion,
GraphRAG, dense retrieval, RRF, reranking, OCR, hosted delivery, or broad multilingual support.
