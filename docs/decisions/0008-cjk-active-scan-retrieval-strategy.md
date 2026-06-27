# ADR-0008: CJK Active Scan Retrieval Strategy

## Status

Accepted. Default promoted after the E3-F launch gate passed.

## Evidence

E3-A recorded the current `numeric-grouping-v1` Chinese retrieval baseline with Recall@5
`0.295455`, nDCG@10 `0.277279`, and answerable zero-hit `0.681818`. The dominant failure was
`compiled_query_empty`, where Chinese-only queries produce no FTS5 expression before ranking.

E3-B recorded `cjk-trigram-overlap-v1` as an off-default comparison artifact. It raised Recall@5
to `0.659091` and nDCG@10 to `0.610619` while preserving the frozen protocol, qrels, fixture bytes,
and lexical-only scope.

Task 0.5 compared tokenizer and no-projection alternatives. `current_runtime`,
`active_fts_generated_terms`, and `unicode61_projection` failed the current gates.
`trigram_projection` passed with Recall@5 `0.659091` and nDCG@10 `0.610619`.
`app_scan_no_projection` also passed with Recall@5 `0.659091` and nDCG@10 `0.619152`, without a
second persistent runtime projection.

## Decision

Implement `cjk-active-scan-overlap-v1` as the first runtime CJK lexical strategy. It compiles each
query with `numeric-grouping-v1`; non-empty compiled queries use the existing active FTS5 Search
path, while eligible compiled-empty CJK queries scan active text Evidence from SQLite domain truth
and apply the frozen overlap thresholds.

The strategy is owner-selected through `--retrieval-strategy`. The legacy
`--retrieval-query-policy` selector remains a compatibility alias for `current` and
`numeric-grouping-v1`. Search and Ask request inputs do not accept request-time strategy overrides.

Compiled non-empty queries remain FTS-only even when FTS returns no rows. During implementation,
a broader zero-hit fallback made `应用加速 30 50 百分比` and `应用加速 99 88 百分比` return the
same Evidence, and likewise made `3T 以上超大规模虚机` and `9T 以上超大规模虚机` return the
same Evidence. The fallback discarded numeric constraints, so its apparent Recall lift was not
accepted. A future mixed/numeric fallback must preserve those constraints and be evaluated
separately.

`cjk-active-scan-overlap-v1` is the default owner-startup retrieval strategy after all launch
gates passed. `numeric-grouping-v1` remains the explicit primary rollback.

## Default Promotion Launch Gate

Default promotion requires:

- Task 0.5 active-scan lift remains material and documented.
- E1 and E2 semantic payloads remain unchanged.
- E3-A and E3-B metrics, gates, qrels, protocol semantics, and fixture bytes remain unchanged.
- Hard-negative and unanswerable controls remain within E3-B limits.
- Explicit and default CLI Search/Ask plus MCP tool-call proofs pass.
- `numeric-grouping-v1` and `current` rollback paths work without active-scan readiness.
- Active-scan high-fanout, large-row-count, and long-query gates stay within fixed budgets.
- Stale-docs and public-boundary scans pass.

Any no-go result blocks the default flip.

The implementation launch gate passed with unchanged E1/E2/E3-A/E3-B semantic payloads, E2
`14/14` gates, E3-B `11/11` gates, bounded performance tests, documentation scans, explicit and
default installed-wheel CLI/MCP proof on Python 3.12 and 3.13, and both rollback paths.

## Bounded Active Scan Contract

The CJK branch reads only active text Evidence from SQLite domain truth. It does not create a CJK
projection table, metadata table, vector index, or external cache. It must not read failed,
partial, inactive, superseded, or unpublished Evidence.

Initial bounds are `max_cjk_query_chars=512`, `max_overlap_terms=128`, a fixed active Evidence row
budget, and a fixed candidate-pool cap. Budget and eligibility failures use stable public
`problem`, `cause`, and `next_step` fields.

`retrieval doctor --strategy cjk-active-scan-overlap-v1 --json` checks local readability and active
Publication inspectability. `retrieval rebuild --strategy cjk-active-scan-overlap-v1 --json` is a
stable no-op because the strategy has no projection to rebuild.

## Rollback

`numeric-grouping-v1` remains the primary rollback strategy and requires no active-scan repair,
projection rebuild, database migration reversal, or Evidence rewrite. `current` remains the
lowest-level legacy rollback strategy.

## Rejected Alternatives

| Alternative | Decision | Reason |
|---|---|---|
| `unicode61` projection | Rejected | It did not recover the compiled-empty CJK class in Task 0.5. |
| Active FTS generated terms | Rejected | The current FTS tokenizer cannot match generated CJK overlap terms reliably. |
| Persistent trigram projection | Deferred | It passed, but active scan passed the same gates with no second persistent projection. |
| Custom SQLite tokenizer extension | Rejected | Adds non-portable extension and packaging surface without current evidence of need. |
| Wait for dense retrieval | Rejected for E3-F | E3-A/E3-B support a smaller lexical fix; dense/hybrid remains a later evidence track. |

## Non-Goals And Limitations

This ADR does not authorize embeddings, vector search, dense retrieval, hybrid retrieval, RRF,
reranking, query rewrite, HTTP, UI, OCR, ASR, or legacy RAG-OCR migration.

The evidence is bounded to a small public, text-layer, page-level corpus. The holdout is not blind.
The strategy does not claim arbitrary Chinese RAG quality. Japanese and Korean behavior is
unvalidated despite CJK terminology. Common two-character CJK words can be below the overlap
minimum unless they occur inside a longer continuous CJK run.
