# CJK Lexical Runtime Promotion Design

Status: amended after Task 0.5 tokenizer alternative spike. Approved for implementation planning
only under the active-scan-first path below.

Planning base: `main@1fdea11d70b410a0cddcf86a74af165be83daf14`.

This is an E3-F lexical-only promotion design. It is not E3-C dense retrieval.

## Context

E3-A established the Chinese retrieval baseline and proved that the current default
`numeric-grouping-v1` lexical path has a Chinese coverage failure rather than primarily a semantic
ranking failure:

| E3-A metric | Value |
|---|---:|
| Recall@5 | `0.295455` |
| nDCG@10 | `0.277279` |
| Answerable zero-hit | `0.681818` |

The dominant miss class is `compiled_query_empty`: Chinese-only queries often produce no SQLite FTS5
`MATCH` expression, so Search returns zero rows before ranking can help.

E3-B compared the bounded `cjk-trigram-overlap-v1` lexical candidate against the unchanged E3-A
protocol and fixtures. PR #31 merged that comparison as an off-default artifact. PR #32 closed the
post-merge documentation state. The canonical E3-B comparison records:

| Metric | Current | Candidate |
|---|---:|---:|
| Recall@5 | `0.295455` | `0.659091` |
| nDCG@10 | `0.277279` | `0.610619` |

All frozen development and holdout gates passed. The candidate changed only compiled-empty CJK
queries during evaluation. It did not change runtime Search/Ask, CLI, MCP, HTTP, UI, embeddings,
vector search, hybrid retrieval, RRF, reranking, or query rewrite.

The original E3-F plan required Task 0.5 to stop if a smaller approach matched the E3-B gates
without requiring a second persistent runtime projection. The execution spike found exactly that:

| Variant | Gates | Recall@5 | nDCG@10 | Second persistent projection |
|---|---:|---:|---:|---|
| `current_runtime` | failed | `0.295455` | `0.277279` | no |
| `active_fts_generated_terms` | failed | `0.295455` | `0.277279` | no |
| `unicode61_projection` | failed | `0.295455` | `0.277279` | yes |
| `trigram_projection` | passed | `0.659091` | `0.610619` | yes |
| `app_scan_no_projection` | passed | `0.659091` | `0.619152` | no |

This changes the implementation decision. E3-F should no longer start with a second persistent CJK
projection. It should first validate and harden a no-projection active Evidence scan strategy.

## Problem

MKE is positioned as a local-first, Agent-callable Evidence engine. After E3-B, the repository has a
verified Chinese lexical candidate, but normal Agent-facing Search and Ask still use
`numeric-grouping-v1`. This leaves the most visible Chinese failure mode unresolved in the product
path:

- Chinese-only questions can still return no Evidence because the default query compiler produces
  an empty FTS expression.
- CLI and MCP users cannot choose a CJK lexical runtime strategy at owner startup.
- The prior projection-first plan may be over-engineered because an active Evidence scan passes the
  same quality gates on the current corpus without adding projection lifecycle.

## Decision

Promote a smaller implementation candidate first: `cjk-active-scan-overlap-v1`.

`cjk-active-scan-overlap-v1` uses the same CJK term extraction and overlap thresholds that made
E3-B pass, but reads active text Evidence from SQLite domain truth instead of building a second
persistent runtime projection. It remains lexical-only.

The implementation must prove the active-scan path behind an explicit owner-startup selector before
changing the runtime default. It may become the default only after the Default Promotion Launch Gate
passes.

If active-scan performance, diagnostics, or MCP/Ask proof fails under the fixed gates, the
implementation must stop and return to the review window. A persistent trigram projection remains a
fallback design, not the first implementation path.

The promotion must not implement or imply dense retrieval, vector search, hybrid retrieval, RRF,
reranking, query rewrite, HTTP, UI, or broad Chinese production quality.

The strategy is owner-configured. Request-time MCP tool inputs must not expose a strategy override.

## Runtime Strategy Semantics

The amended strategy uses this flow:

```text
Search / Ask query
  -> compile with numeric-grouping-v1
      -> non-empty compiled query: existing active_evidence_fts path
      -> empty compiled query:
           -> derive eligible CJK overlap terms
           -> bounded scan over active text Evidence
           -> deterministic overlap ranking
```

The CJK branch uses the frozen E3-B thresholds:

| Parameter | Value |
|---|---:|
| Strategy ID | `cjk-active-scan-overlap-v1` |
| Revision | `1` |
| `minimum_overlap_count` | `2` |
| `minimum_overlap_ratio` | `0.30` |
| `max_results` | `10` |

The active-scan branch ranking order is:

1. overlap count descending;
2. overlap ratio descending;
3. document ID ascending;
4. locator start ascending;
5. Evidence ID ascending.

The CJK branch does not use SQLite FTS5 rank because it does not query a CJK FTS projection.

All SQL must remain parameterized. Raw query text must never be interpolated into SQL.

## Strategy Contract

The existing `RetrievalQueryPolicy` name is too narrow for a strategy that can choose between the
existing active FTS branch and a CJK active-scan branch. Implementation should introduce a
project-owned runtime strategy concept while preserving compatibility for existing callers.

Required identifiers:

```text
current
numeric-grouping-v1
cjk-active-scan-overlap-v1
```

`cjk-trigram-overlap-v1` remains the E3-B comparison artifact candidate and the persistent
projection fallback design. It is not the default runtime strategy in this amended E3-F plan.

Required behavior:

- `cjk-active-scan-overlap-v1` is implemented behind an explicit owner-startup selector before the
  default is flipped.
- `cjk-active-scan-overlap-v1` becomes the new default runtime strategy only after the Default
  Promotion Launch Gate passes.
- `numeric-grouping-v1` remains the primary rollback strategy and requires no CJK scan-specific
  readiness.
- `current` remains the lowest-level legacy rollback strategy.
- Existing `--retrieval-query-policy` usage must continue to work as a compatibility alias.
- The preferred new owner-startup selector is `--retrieval-strategy`.
- If both selector names are provided with conflicting values, CLI and owner-started MCP startup
  must fail before engine construction with a stable usage error.

The alias exists for compatibility only. New docs should use `retrieval strategy`, not broaden the
old `query policy` vocabulary.

The runtime strategy abstraction must be descriptor-based rather than a one-off branch. Each
descriptor records strategy ID, revision, base query policy, required projections, tokenizer or
term-derivation mode, readiness checker, rollback capability, fallback semantics, and explicit
`dense=none`, `hybrid=none`, and `rerank=none` fields for this slice. Future dense or hybrid
strategies must be able to add descriptors without changing Search or Ask request DTOs.

## Active Evidence Scan Lifecycle

`cjk-active-scan-overlap-v1` does not add a second persistent retrieval projection.

Required properties:

- It reads only active text Evidence from SQLite domain truth.
- It never reads failed, partial, superseded, or inactive Publications.
- It does not copy active Evidence into a new persistent index.
- It does not require database rebuild for existing databases.
- It exposes stable diagnostics for query eligibility, fanout caps, candidate pool caps, and scan
  budget decisions.
- Rollback to `numeric-grouping-v1` or `current` requires no database migration reversal, rebuild,
  or Evidence rewrite.

The implementation should add a local readiness check:

```bash
mke --db <existing.sqlite> retrieval doctor --strategy cjk-active-scan-overlap-v1 --json
```

For the active-scan strategy, `doctor` verifies that the strategy is supported, SQLite is readable,
and an active Publication can be inspected. It must not require a CJK projection table.

`retrieval rebuild --strategy cjk-active-scan-overlap-v1` should not build anything. It must either
return a stable no-op result or a stable usage result explaining that the strategy has no projection
to rebuild. The exact behavior must be tested and documented.

## Activation And Failure Isolation

Because active-scan has no second projection, it must not add a new Publication activation stage.
The important invariant is that the scan reads only the already-active Publication state.

For an owner process configured with `cjk-active-scan-overlap-v1`:

- Search/Ask must never read inactive, failed, partial, or superseded Evidence;
- Search/Ask must not silently fall back to `numeric-grouping-v1` when an eligible CJK scan exceeds
  a hard budget;
- budget and eligibility failures must return stable `problem`, `cause`, and `next_step` fields;
- rollback strategies must preserve current behavior without needing any active-scan repair step.

The strategy may still use the existing `numeric-grouping-v1` branch for non-empty compiled queries.
That is part of the strategy semantics, not an error fallback.

Ask validation must become strategy-aware. Under `cjk-active-scan-overlap-v1`, eligible CJK-only
questions must not be rejected merely because ASCII token count is zero. Under `numeric-grouping-v1`
and `current`, the existing CJK-only invalid-input behavior remains the rollback behavior.

Stable active-scan errors:

| `problem` | `cause` | `next_step` |
|---|---|---|
| `cjk_query_not_eligible` | `Query does not contain enough eligible CJK terms` | `revise_query_or_use_rollback_strategy` |
| `cjk_scan_budget_exceeded` | `CJK active Evidence scan would exceed configured local budget` | `narrow_query_or_use_projection_strategy` |
| `cjk_candidate_pool_capped` | `CJK candidate pool exceeded the configured cap` | `narrow_query` |
| `retrieval_strategy_unsupported` | `Requested retrieval strategy is not supported by this runtime` | `choose_supported_retrieval_strategy` |

The implementation must bound CJK query fanout. Initial bounds are `max_cjk_query_chars=512`,
`max_overlap_terms=128`, a documented active Evidence row budget, and a documented candidate pool
cap. Truncation, cap hits, and budget failures must be visible in diagnostics and must not be hidden
in benchmark metrics.

## CLI And MCP Contract

CLI:

- Add the preferred owner selector `--retrieval-strategy`.
- Preserve `--retrieval-query-policy` as a compatibility alias.
- Reject unsupported values and conflicting selector values before engine construction.
- Update help text only after the Default Promotion Launch Gate passes. Before that, docs must show
  `cjk-active-scan-overlap-v1` as explicit opt-in.
- Once promoted, identify `cjk-active-scan-overlap-v1` as the default and `numeric-grouping-v1` as
  rollback.

MCP:

- Owner startup accepts the same runtime strategy allowlist.
- MCP tools do not accept request-time strategy overrides.
- MCP error payloads remain stable and do not expose local absolute paths or tracebacks.
- Installed-wheel stdio MCP proof must cover the default strategy, rollback startup, and actual
  `search_library`/`ask_library` tool calls over the CJK path.

HTTP and UI remain out of scope.

## Evaluation And Promotion Evidence

The implementation PR must preserve and refresh canonical artifacts as needed because source
identity will change:

- E1 retrieval baseline artifact;
- E2 numeric comparison artifact;
- E3-A Chinese baseline artifact;
- E3-B CJK lexical comparison artifact.

Refreshing source identity must not change frozen observations, metrics, gate verdicts, protocol
semantics, qrels, or fixture bytes. Any metric change requires stopping and re-reviewing the
promotion decision.

New E3-F proof should show:

- explicit `cjk-active-scan-overlap-v1` Search returns cited Evidence for the predeclared CJK
  compiled-empty class;
- default Search/Ask use `cjk-active-scan-overlap-v1` only after the launch gate passes;
- `numeric-grouping-v1` rollback preserves the previous behavior and requires no scan repair or
  projection rebuild;
- unanswerable and hard-negative gates remain bounded;
- E1 and E2 semantic payloads remain unchanged except for allowed source identity refresh;
- Product proof and demo still pass;
- installed-wheel CLI and MCP proof pass on supported Python versions.

Default promotion is a launch-gated step. The implementation must first prove the explicit selector
path. Only after all validators, proofs, performance gates, stale-docs checks, and rollback checks
pass may it change the default strategy constant.

## ADR Requirement

The implementation PR must add ADR-0008 before or with the runtime change.

ADR-0008 must record:

- evidence basis from E3-A and E3-B;
- Task 0.5 spike outcome, including why `app_scan_no_projection` became the first runtime candidate;
- why `unicode61`, active FTS generated terms, custom tokenizer extensions, wait-for-dense, and
  persistent trigram projection were rejected or deferred;
- selected runtime default strategy after launch gate;
- the Default Promotion Launch Gate;
- no-projection active-scan lifecycle and bounded scan contract;
- owner-startup selector and compatibility alias;
- rollback paths;
- explicit non-goals for dense/vector/hybrid/RRF/reranker/query rewrite;
- limitations of public holdout evidence and CJK trigram lexical matching;
- Japanese and Korean behavior is unvalidated despite CJK terminology;
- common two-character CJK words can be below the overlap minimum unless they occur inside a longer
  continuous CJK run.

## Public Demonstration Deliverables

The implementation should update repository-visible demonstration assets without publishing an
external recording:

- an architecture diagram showing SQLite domain truth, active FTS, active-scan fallback, and
  owner-startup strategy selection;
- a strategy comparison table generated from canonical artifacts and the Task 0.5 spike;
- one direct offline proof command;
- a short demo script covering ingest, Chinese Search/Ask Evidence, refusal, and rollback.

External video publication remains out of scope unless separately authorized.

## Non-Goals

- No embeddings, vector search, dense retrieval, hybrid retrieval, RRF, reranker, or query rewrite.
- No LangChain, LlamaIndex, LangGraph, retrieval SDK, or hosted retrieval service.
- No HTTP API or UI behavior change.
- No OCR, ASR, PDF parser, chunking, or segmentation expansion.
- No broad claim that MKE solves arbitrary Chinese RAG.
- No claim that Japanese or Korean retrieval quality has been validated.
- No request-time retrieval strategy override through MCP tool inputs.
- No migration from legacy `multimodal-rag-ocr` architecture or services.

## Acceptance Criteria

E3-F lexical-only promotion is complete when:

1. ADR-0008 is accepted in the same PR as the runtime change.
2. Tokenizer alternatives have been evaluated and recorded, including the active-scan result.
3. `cjk-active-scan-overlap-v1` is implemented behind an explicit owner-startup selector.
4. The Default Promotion Launch Gate passes before `cjk-active-scan-overlap-v1` becomes the default
   owner-startup retrieval strategy.
5. `numeric-grouping-v1` and `current` remain direct rollback strategies.
6. The active scan reads only active text Evidence from SQLite domain truth and adds no persistent
   CJK projection.
7. Failed, partial, inactive, superseded, or unpublished Evidence cannot be scanned.
8. Ask validation is strategy-aware and does not reject eligible CJK-only questions under the CJK
   strategy.
9. CLI and owner-started MCP support the allowlisted strategy contract without request-time tool
   overrides.
10. Installed-wheel MCP proof covers actual `search_library` and `ask_library` tool calls.
11. Existing databases need no CJK projection rebuild for the active-scan strategy, and doctor/no-op
    rebuild behavior is documented and tested.
12. E1, E2, E3-A, and E3-B canonical validators pass after source identity refresh, with unchanged
    metrics and verdicts unless a reviewer explicitly approves a new promotion decision.
13. Runtime Search/Ask tests prove the explicit and default CJK strategy, rollback behavior,
    hard-negative preservation, and stable errors.
14. Active-scan high-fanout, long-query, large-row-count, and candidate-pool performance gates pass
    under fixed local budgets.
15. Python 3.12 and Python 3.13 installed-wheel CLI/MCP proof pass.
16. Product proof, demo, tests, lint, type checking, build, documentation checks, and diff checks
    pass.
