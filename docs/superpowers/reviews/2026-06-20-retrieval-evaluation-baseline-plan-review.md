# Retrieval Evaluation Baseline Plan Review

## Status

- Result: approved for implementation
- Review mode: CEO scope hold, engineering review, and developer-experience polish
- Design review: skipped because E1 has no UI scope
- Implementation: not started by this review

## Premise And Scope

The next retrieval stage should establish a reproducible baseline before changing retrieval
behavior. The approved scope is intentionally limited to an offline corpus, binary locator qrels,
current Search and Ask execution, report-only quality metrics, and integrity gates.

This stage does not introduce semantic retrieval, embeddings, reranking, query rewriting, Unicode
tokenization changes, a hosted evaluator, or quality thresholds. Those decisions require the
observed E1 failure modes.

## Architecture Review

```text
manifest + checksummed fixtures
            |
            v
 strict validation before ingest
            |
      +-----+-----+
      |           |
      v           v
 workspace A   workspace B
      |           |
 normal ingest / active Evidence
      |           |
 current Search and Ask
      |           |
      +-----+-----+
            |
 deterministic stable-locator comparison
            |
 integrity verdict + baseline metrics
```

The module split is proportionate:

- `manifest.py` owns untrusted file/schema validation.
- `metrics.py` remains pure.
- `report.py` owns the bounded public contract.
- `runner.py` owns temporary-workspace orchestration and cleanup.

A new read-only active-Evidence method is justified because qrel integrity cannot be established
from top-k Search results alone. Its boundary is explicit: active Publications only, stable order,
internal diagnostics/evaluation use, and no CLI/MCP exposure. Existing Search SQL, ordering, and
Ask behavior remain unchanged.

## Findings Resolved In The Plan

| # | Finding | Resolution |
|---|---|---|
| 1 | Fixture corruption and manifest-shape failures collapsed into one problem. | Added `FixtureValidationError` and separate `retrieval_eval_fixture_invalid` handling. |
| 2 | The active-Evidence enumeration seam was present only in the plan. | Added the contract and non-exposure boundary to the approved design. |
| 3 | Evaluation failures were coupled to the global CLI/MCP `PublicError` allowlist. | Kept stable failures inside the evaluation report contract. |
| 4 | Runner and parser examples used `object`, ignored typing, and `locals()` state recovery. | Added exact callable, `pytest.MonkeyPatch`, and `RetrievalMetrics` types plus explicit `manifest_id` state. |
| 5 | The active-publication test asserted text that does not match the revised fixture. | Replaced it with the exact two revised page texts and a stale-page exclusion. |
| 6 | CLI discoverability and output naming were underspecified. | Added `--help` coverage and standardized human rows on `query_id`. |

## Verification Design

The implementation plan requires:

- exact fixture size, checksum, text-layer, and provenance checks;
- strict JSON, ID, field, path, locator, category, and qrel validation;
- active-Publication Evidence tests;
- pure Recall@1/3/5, MRR@5, zero-hit, no-hit, and Ask-refusal metric tests;
- report completeness and redaction tests;
- two fresh workspaces with ordered stable-locator equality;
- corrupt-fixture, invalid-qrel, partial-run, failed-ingest, and nondeterminism tests;
- public CLI success, JSON, help, exit `1`, and exit `2` tests;
- source-tree and isolated-wheel CI execution;
- full suite, Ruff, Pyright, build, product proof, demo, and diff checks.

CI gates integrity but does not assert exact E1 metric values. This preserves the ability to record
the current weakness without redefining weak quality as a build failure.

## Developer Experience

The evaluator is discoverable through:

```bash
mke eval retrieval --help
uv run mke eval retrieval --manifest tests/fixtures/retrieval-eval-v1.json
uv run mke eval retrieval --manifest tests/fixtures/retrieval-eval-v1.json --json
```

Exit codes are stable: `0` for a complete baseline, `1` for integrity failure, and `2` for usage
errors. Human and JSON reports exclude query text, Evidence text, random IDs, absolute paths,
temporary paths, and raw exceptions. The wheel CI case runs from outside the repository source
tree to verify installation identity and path independence.

## Remaining Risk

- The corpus is deliberately small and English-first; E1 scores do not generalize beyond
  `retrieval-eval-v1`.
- Exact qrels are binary and locator-level; they do not measure graded relevance.
- Determinism is verified on the supported CI environments, not every SQLite build or platform.
- A baseline can expose weak retrieval but cannot by itself identify the best next algorithm.

These are declared E1 boundaries, not implementation blockers.

## Verdict

The spec and plan are coherent, independently testable, and ready for a separate implementation
window. No unresolved product, architecture, test, or developer-experience decision remains.
