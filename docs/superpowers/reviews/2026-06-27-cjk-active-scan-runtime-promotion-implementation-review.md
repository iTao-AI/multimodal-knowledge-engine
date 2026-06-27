# CJK Active Scan Runtime Promotion Implementation Review

Status: completed. Ready for independent pre-PR review.

## Scope

This record covers E3-F `cjk-active-scan-overlap-v1`, owner-startup CLI/MCP selection, readiness,
no-op rebuild, installed-wheel proof, artifact identity maintenance, documentation, rollback, and
default-promotion gating. It adds no persistent CJK projection, HTTP, UI, embedding/vector or
hybrid retrieval, RRF, reranking, query rewrite, or legacy RAG-OCR migration.

## Fail-Closed Stops And Decisions

### Task 0.5

The tokenizer spike stopped projection-first execution because the no-projection application scan
passed the frozen quality gates. The amendment selected active-scan-first and retained trigram
projection only as a reviewed fallback.

### E2 Scope Identity

E2 validation stopped fail closed after runtime work changed the scope-bound
`src/mke/adapters/sqlite/__init__.py` and `src/mke/application/__init__.py` hashes. A supported
same-directory protocol copy was refreshed and rerun before any checked-in update. Only those file
hashes and the resulting scope identity changed. Candidate identity, claim, manifests, fixtures,
query inventory, observations, metrics, 14 gates, and verdict remained canonical. The checked-in
protocol and E1/E2/E3-A set then used recoverable artifact refresh; E3-B used its supported
recorder.

### Compiled-Empty-Only Routing

An intermediate FTS-zero-hit fallback produced Recall@5 `0.704545`, but the lift came from two
compiled non-empty numeric queries. Counterexamples showed that correct and incorrect numbers
returned the same Evidence:

- `应用加速 30 50 百分比` versus `应用加速 99 88 百分比`;
- `3T 以上超大规模虚机` versus `9T 以上超大规模虚机`.

Execution stopped and restored ADR-0008 routing: compile once; compiled non-empty queries are
FTS-only even after zero hits; only eligible compiled-empty CJK queries use active scan. The
48-query runtime result returned to Recall@5 `0.659091`, nDCG@10 `0.619152`, unanswerable no-hit
rate `0.500000`, and hard-negative failure rate `0.235294`.

## Implemented Contract

- Active scan reads bounded text Evidence through active Publication joins in SQLite domain truth.
- No CJK projection table, metadata table, external cache, or schema migration is added.
- Search and Ask share one owner-selected strategy; MCP requests cannot override it.
- Doctor is read-only; active-scan rebuild is a stable `noop` with `projection=none`.
- `numeric-grouping-v1` is primary rollback and `current` remains legacy rollback.
- Omitted strategy and explicit legacy query-policy selection remain distinguishable.

## Gate Evidence

| Gate | Result | Evidence |
|---|---|---|
| G1 Task 0.5 | passed | Recall@5 `0.659091`, nDCG@10 `0.619152`. |
| G2 E1/E2 | passed | Semantic payloads unchanged; E2 `14/14` gates. |
| G3 E3-A/E3-B | passed | Metrics, gates, qrels, protocol semantics, and fixture bytes unchanged. |
| G4 hard negatives | passed | Unanswerable no-hit `0.500000`; hard-negative failure `0.235294`. |
| G5 runtime | passed | Explicit/default installed-wheel CLI and MCP on Python 3.12 and 3.13. |
| G6 rollback | passed | `numeric-grouping-v1` and `current` require no active-scan readiness. |
| G7 performance | passed | High-fanout, row-budget, and long-query tests passed. |
| G8 docs | passed | Documentation tests, stale scan, and public-boundary scan passed. |

## Review Boundary

The default changed only after every gate passed. Post-promotion Python 3.12 and 3.13 installed-wheel
proofs confirmed default, explicit, rollback, doctor/rebuild, budget errors, MCP calls, offline
execution, and installed package identity. Document-release found complete reference, how-to,
tutorial, and explanation coverage; its only command drift finding was corrected before handoff.

The final branch remains local for independent review; no push, PR, or final full GStack review
belongs to this execution window.

## Final Verification

- `uv run pytest -q`: `936 passed, 1 skipped`.
- `uv run pytest tests/performance -q`: `3 passed`.
- `uv run ruff check .`: passed.
- `uv run pyright`: `0 errors, 0 warnings`.
- `uv build`: sdist and wheel built.
- `uv run mke proof run`: `8/8` cases passed.
- `uv run mke demo --verify`: passed.
- `uv run python scripts/cjk_active_scan_demo.py`: ingest, CJK Search/Ask, refusal, and rollback passed.
- E1, E2, E3-A, and E3-B final observations completed; all four artifact validators passed.
- Python 3.12 and 3.13 installed-wheel proofs passed with `network=offline` and
  `installed_identity=wheel`.
- Documentation tests, stale-docs scan, public-boundary scan, and `git diff --check` passed.
