# CJK Lexical Runtime Promotion Design

Status: approved for implementation planning. This is an E3-F lexical-only promotion design, not
E3-C dense retrieval.

Planning base: `main@ee1eca081dffb9350f1fb9d20a3d32a06efa1785`.

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

The program-level E3 design explicitly permits E3-F to promote a CJK lexical strategy without
waiting for dense retrieval when prior artifacts support that smaller strategy.

## Problem

MKE is positioned as a local-first, Agent-callable Evidence engine. After E3-B, the repository has a
verified Chinese lexical candidate, but normal Agent-facing Search and Ask still use
`numeric-grouping-v1`. This leaves the most visible Chinese failure mode unresolved in the product
path:

- Chinese-only questions can still return no Evidence because the default query compiler produces
  an empty FTS expression.
- CLI and MCP users cannot choose the approved CJK lexical strategy at owner startup.
- There is no runtime projection lifecycle, readiness check, rebuild command, or rollback proof for
  the CJK lexical candidate.

## Decision

Promote the smallest verified strategy: `cjk-trigram-overlap-v1`.

This E3-F slice should make `cjk-trigram-overlap-v1` the normal runtime retrieval strategy for
Search, Ask, CLI, and owner-started MCP composition, while preserving direct rollback to
`numeric-grouping-v1` and `current`.

The promotion must remain lexical-only. It must not implement or imply dense retrieval, vector
search, hybrid retrieval, RRF, reranking, query rewrite, HTTP, UI, or broad Chinese production
quality.

The strategy is owner-configured. Request-time MCP tool inputs must not expose a strategy override.

## Runtime Strategy Semantics

The promoted strategy keeps the E3-B behavior:

1. Compile the query with `numeric-grouping-v1`.
2. If the compiled query is non-empty, use the existing active FTS5 Search path.
3. If the compiled query is empty and eligible CJK trigram terms exist, search the CJK lexical
   projection.
4. If no eligible terms exist, return the same no-hit or insufficient-input behavior as the current
   runtime path.

The CJK branch uses the frozen E3-B parameters:

| Parameter | Value |
|---|---:|
| Candidate ID | `cjk-trigram-overlap-v1` |
| Revision | `1` |
| `minimum_overlap_count` | `2` |
| `minimum_overlap_ratio` | `0.30` |
| `max_results` | `10` |

Ranking order remains:

1. overlap count descending;
2. overlap ratio descending;
3. SQLite FTS5 rank ascending;
4. document ID ascending;
5. locator start ascending;
6. Evidence ID ascending.

All SQL must remain parameterized. Raw query text must never be interpolated into SQL.

## Strategy Contract

The existing `RetrievalQueryPolicy` name is too narrow for a strategy that can choose between two
projections. Implementation should introduce a project-owned runtime strategy concept while
preserving compatibility for existing callers.

Required identifiers:

```text
current
numeric-grouping-v1
cjk-trigram-overlap-v1
```

Required behavior:

- `cjk-trigram-overlap-v1` is the new default runtime strategy.
- `numeric-grouping-v1` remains the primary rollback strategy and requires no CJK projection.
- `current` remains the lowest-level legacy rollback strategy.
- Existing `--retrieval-query-policy` usage must continue to work as a compatibility alias.
- The preferred new owner-startup selector is `--retrieval-strategy`.
- If both selector names are provided with conflicting values, CLI and owner-started MCP startup
  must fail before engine construction with a stable usage error.

The alias exists for compatibility only. New docs should use `retrieval strategy`, not broaden the
old `query policy` vocabulary.

## CJK Projection Lifecycle

The CJK lexical projection is a rebuildable SQLite projection, not domain truth.

Required properties:

- It is separate from `active_evidence_fts`.
- It mirrors active text Evidence rows only.
- It stores enough metadata to verify projection readiness against active Evidence identity, row
  count, tokenizer identity, strategy revision, and aggregate text digest.
- It is rebuilt from SQLite domain truth, not from previous projection contents.
- Rollback to `numeric-grouping-v1` or `current` must not require projection rebuild, database
  migration reversal, or Evidence rewrite.

The implementation must add cache-only local commands for readiness and rebuild. Required command
shape:

```bash
mke retrieval doctor --strategy cjk-trigram-overlap-v1 --json
mke retrieval rebuild --strategy cjk-trigram-overlap-v1 --json
```

These command names are part of this promotion contract. Changing them requires updating this
design, the implementation plan, docs, tests, MCP startup contract, and ADR in the same PR.

## Activation And Failure Isolation

Any required-stage or projection failure must not make partial results searchable.

For an owner process configured with `cjk-trigram-overlap-v1`:

- new Publication activation must build or refresh the normal active FTS projection and the CJK
  lexical projection before Search/Ask observes the new active Publication;
- if CJK projection build fails, the Run or activation path must fail closed and preserve the
  previous active Publication;
- Search/Ask must not silently fall back to `numeric-grouping-v1` when the owner selected
  `cjk-trigram-overlap-v1` and the CJK projection is stale or missing;
- `retrieval doctor` must report `not_ready` with stable `problem`, `cause`, and `next_step` fields
  when projection readiness is incomplete;
- `retrieval rebuild` must be idempotent and must not change domain truth or Publication identity.

The strategy may still use the existing `numeric-grouping-v1` branch for non-empty compiled queries.
That is part of the strategy semantics, not an error fallback.

## CLI And MCP Contract

CLI:

- Add the preferred owner selector `--retrieval-strategy`.
- Preserve `--retrieval-query-policy` as a compatibility alias.
- Reject unsupported values and conflicting selector values before engine construction.
- Update help text to identify `cjk-trigram-overlap-v1` as the default and
  `numeric-grouping-v1` as rollback.

MCP:

- Owner startup accepts the same runtime strategy allowlist.
- MCP tools do not accept request-time strategy overrides.
- MCP error payloads remain stable and do not expose local absolute paths or tracebacks.
- Installed-wheel stdio MCP proof must cover the default strategy and rollback startup.

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

- default `cjk-trigram-overlap-v1` Search returns cited Evidence for the predeclared CJK
  compiled-empty class;
- `numeric-grouping-v1` rollback preserves the previous behavior and requires no projection rebuild;
- unanswerable and hard-negative gates remain bounded;
- E1 and E2 semantic payloads remain unchanged except for allowed source identity refresh;
- Product proof and demo still pass;
- installed-wheel CLI and MCP proof pass on supported Python versions.

## ADR Requirement

The implementation PR must add ADR-0008 before or with the runtime change.

ADR-0008 must record:

- evidence basis from E3-A and E3-B;
- selected runtime default strategy;
- projection lifecycle and readiness contract;
- owner-startup selector and compatibility alias;
- rollback paths;
- explicit non-goals for dense/vector/hybrid/RRF/reranker/query rewrite;
- limitations of public holdout evidence and CJK trigram lexical matching.

## Public Demonstration Deliverables

The implementation should update repository-visible demonstration assets without publishing an
external recording:

- an architecture diagram showing domain truth, active FTS projection, CJK lexical projection, and
  owner-startup strategy selection;
- a strategy comparison table generated from canonical artifacts;
- one direct offline proof command;
- a short demo script covering ingest, Chinese Search/Ask Evidence, refusal, and rollback.

External video publication remains out of scope unless separately authorized.

## Non-Goals

- No embeddings, vector search, dense retrieval, hybrid retrieval, RRF, reranker, or query rewrite.
- No LangChain, LlamaIndex, LangGraph, retrieval SDK, or hosted retrieval service.
- No HTTP API or UI behavior change.
- No OCR, ASR, PDF parser, chunking, or segmentation expansion.
- No broad claim that MKE solves arbitrary Chinese RAG.
- No request-time retrieval strategy override through MCP tool inputs.
- No migration from legacy `multimodal-rag-ocr` architecture or services.

## Acceptance Criteria

E3-F lexical-only promotion is complete when:

1. ADR-0008 is accepted in the same PR as the runtime change.
2. `cjk-trigram-overlap-v1` is the default owner-startup retrieval strategy.
3. `numeric-grouping-v1` and `current` remain direct rollback strategies.
4. The CJK lexical projection is persistent, rebuildable, readiness-checked, and separate from
   domain truth.
5. Projection failure cannot publish or activate partial searchable state.
6. CLI and owner-started MCP support the allowlisted strategy contract without request-time tool
   overrides.
7. E1, E2, E3-A, and E3-B canonical validators pass after source identity refresh, with unchanged
   metrics and verdicts unless a reviewer explicitly approves a new promotion decision.
8. Runtime Search/Ask tests prove the default CJK strategy, rollback behavior, hard-negative
   preservation, and stable errors.
9. Python 3.12 and Python 3.13 installed-wheel CLI/MCP proof pass.
10. Product proof, demo, tests, lint, type checking, build, documentation checks, and diff checks
    pass.
