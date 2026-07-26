# Deterministic Retrieval Order Maintenance

Status: approved design for mechanical public spec landing and implementation planning.
Runtime implementation, push, pull request, merge, release, and promotion remain pending.

Planning baseline: `main@eea3d51c36c0b3b845b8efb60eff553ddc200b88`.

## Summary

MKE's FTS5 and default CJK retrieval paths preserve relevance ordering, but their final
equal-score ordering currently depends on opaque store-local identifiers. The same active corpus
can therefore produce a different ordered Evidence projection in fresh databases that allocate
different Source and Evidence IDs.

This design makes equal-score ordering deterministic without changing candidate membership,
scores, non-tied ordering, active-Publication authority, request schemas, or Evidence addressing.
It also defines a bounded, public, nonblind development/holdout mechanism proof before any
retrieval-coverage, segmentation, or contextual-retrieval comparison resumes.

## Problem Evidence

A repository-external read-only audit probe created two fresh SQLite workspaces with the same two
source fingerprints, page locators, matching text, runtime profile, and query. Only opaque
`source_id` and `evidence_id` allocation order changed.

- Both FTS candidates received the exact score `-3e-06`.
- One workspace returned stable fingerprints `a,b`.
- The other workspace returned stable fingerprints `b,a`.
- The same inversion occurred in the CJK active-scan result.

This reproduces the mechanism: current equal-score order depends on store-local identity. It does
not establish a relevance defect, identify any unrelated observation's exact candidate pair, or
justify a retrieval candidate promotion.

## Product Decision

For a valid active-authority snapshot produced by supported ingest paths, one fixed runtime
profile, scorer, query, retrieval strategy revision, query-policy revision, and
extractor/Evidence identity:

1. Search and Ask return the same ordered stable Evidence projections across fresh databases,
   ingestion schedules, and opaque ID assignments.
2. Relevance score remains the primary order. Stable keys resolve only equal-score groups.
3. Candidate membership, score bytes, and every non-tied pair preserve current behavior.
4. Pagination is a lossless ordered projection with no duplicate, gap, or page-size-dependent
   reorder.
5. Active-only Publication authority is unchanged.
6. Opaque IDs remain store-local Evidence addresses but no longer participate in ranking
   semantics.

The stable comparison projection is:

```text
(content_fingerprint, locator_kind, locator_start, locator_end)
```

This projection is not a new Evidence identity and is not a single shared cross-strategy sort
tuple. Each scorer retains its existing secondary semantics and then reaches stable fields through
a path-specific total order. Exact Evidence authority continues to include the active
Publication/Run, locator, text digest, and opaque address required by `mke.evidence_ref.v1`.

## Goals

1. Remove opaque Source/Evidence IDs from FTS and CJK equal-score ranking semantics.
2. Preserve score, candidate membership, non-tied order, active-only authority, and public request
   schemas.
3. Make Python, CLI, Ask, MCP pagination, and evaluation diagnostics observe the same order.
4. Reject duplicate stable locator projections before new Publication and fail closed when invalid
   legacy candidates are observed.
5. Define explicit strategy revisions and cursor recovery after the ordering contract changes.
6. Preserve historical observation bytes while validating a separate revision-2 compatibility
   and differential record against current source.
7. Prove the mechanism with frozen development and disjoint public nonblind holdout partitions
   before later retrieval comparisons resume.

## Non-Goals

This work does not add or promote:

- segmentation, Passage promotion, or contextual retrieval;
- GraphRAG, dense retrieval, RRF, reranking, query rewrite, or a relevance candidate;
- OCR, table extraction, an Agent loop, HTTP, SaaS, a provider, a model, or a dependency;
- deterministic domain IDs, a schema migration, or automatic database repair;
- a new public evaluation CLI, request flag, MCP tool, or MCP request/response schema;
- relevance, recall, answer-quality, latency, production, adoption, or business-benefit claims; or
- release, deployment, or runtime promotion authority.

No incomplete retrieval-coverage work is resumed, consumed, repaired, or used as the new holdout
by this design.

## Existing Authority and Reuse

The implementation must preserve and reuse:

- SQLite as domain truth and active FTS as a rebuildable projection;
- per-Source active Publication selection and validation;
- existing Python, CLI, Ask, legacy MCP, strict-v1 MCP, and v2 MCP application paths;
- existing bounded CJK active-scan row and byte caps;
- existing metadata-first FTS page selection and response-byte accounting;
- existing public error unions and redaction policy;
- existing process-bound cursor ownership and expiry behavior;
- `SearchResultProvenance` and `mke.evidence_ref.v1`;
- installed-wheel, real-stdio, export, and standalone-consumer proof patterns.

The maintenance must not introduce a second retrieval authority, alternate Publication selection,
parallel SQLite truth, or adapter-owned Evidence identity.

## Stable Locator Admissibility

For every newly admitted Run, the Publication manifest rejects duplicate locator tuples within
that Run:

```text
(locator_kind, locator_start, locator_end)
```

This formalizes an invariant already produced by supported extractors: PDF/OCR produces one
Evidence item per page, while video/audio validation requires sorted, non-overlapping timestamp
ranges.

Before candidate observation, a read-only compatibility audit must prove that checked-in fixtures
and replayed supported-ingest snapshots contain no duplicate locator tuples.

An externally mutated or otherwise invalid legacy database is not repaired, deduplicated, or
migrated automatically. New writes fail before Publication. Because direct Search callers do not
all pass through manifest validation, each affected candidate path also detects duplicate stable
projections inside the candidate set it already evaluates:

```text
(content_fingerprint, locator_kind, locator_start, locator_end)
```

- FTS detection is part of the existing matched-candidate statement and occurs before pagination.
- CJK detection runs over the already bounded active-scan candidates before sorting.

This request-time check is not a full-corpus corruption scan. No database uniqueness constraint or
schema migration is added.

## Runtime Design

### FTS5

Retain the current primary and secondary semantics and replace the random final key with:

```text
rank, locator_start, locator_kind, locator_end, assets.sha256
```

The query joins `assets` through the already joined `sources` table. `evidence_id` is not an order
key. The page query remains metadata-only: it does not select or order by full Evidence text, and
it keeps existing bounded byte-length accounting before admitted text is loaded.

Duplicate stable-projection detection is computed in the same matched-candidate statement. The
change must not add a second full scan or N+1 access.

Use the identical order in:

- unpaged Python/CLI/Ask Search;
- bounded MCP Search page selection; and
- the FTS5 rank diagnostic used by evaluation.

### CJK active scan

Load the source asset SHA-256 with each active Evidence candidate and use it as stable document
identity. Preserve current score and document-grouping semantics:

```text
-overlap_count,
-overlap_ratio,
content_fingerprint,
locator_kind,
locator_start,
locator_end
```

The pure ranking helper requires stable document identity instead of falling back to `source_id`.
`evidence_id` is not an order key. The active-scan path rejects duplicate stable projections within
its existing bounded candidate set before sorting.

Do not change the separate evaluation-only `CJK_LEXICAL_CANDIDATE` scorer, its revision, or
historical observation payload. It already receives an evaluation-stable `document_id`.
Source-bound validation for that historical observation is handled by the compatibility closure
below, not by claiming revision 2 generated revision-1 bytes.

## Version and Cursor Contract

- Keep public strategy IDs and CLI/MCP request schemas unchanged.
- Bump the runtime descriptor revision for `current`, `numeric-grouping-v1`, and
  `cjk-active-scan-overlap-v1` from 1 to 2.
- Bump `CJK_ACTIVE_SCAN_PARAMETERS.revision` from 1 to 2.
- Keep query-policy revision 1 because token compilation is unchanged.
- Existing Search cursors expire on strategy-revision mismatch.
- After Search cursor expiry, the consumer discards the complete partial traversal and repeats the
  initial query under revision 2. It never appends revision-2 pages to a revision-1 prefix.
- Exact-read cursors do not bind ranking strategy revision. They survive a strategy-only change
  under the same owner and active authority.
- A real owner restart continues to expire both Search and Read cursors through the existing
  `owner_restarted` contract.

Record the exact evaluation runtime profile:

- Python major/minor;
- SQLite library version;
- `sqlite_source_id()`;
- sorted SQLite compile options;
- FTS5 rank configuration;
- strategy revision; and
- query-policy revision.

Exact score-byte equality is a before/after gate inside that fixed profile. The supported Python CI
matrix proves compatibility and deterministic order, not floating-point identity across arbitrary
SQLite builds.

## Public Failure and Recovery

Add one path-neutral typed Python exception, `RetrievalAuthorityError`, for duplicate stable
Evidence locator projections observed by FTS or CJK candidates. It does not create a new response
schema.

Python Search/Ask, CLI Search/Ask, legacy MCP, strict v1, and v2 Search map it into the existing
public error shape:

```text
problem=retrieval_authority_invalid
cause=active retrieval candidates contain duplicate stable Evidence locators
active_publication_impact=unchanged
next_step=restore_valid_database_or_reingest_into_new_database
```

The cause enters the existing public-safe allowlist. CLI exits 1 without a traceback. MCP retains
its existing strict success/error unions, field sets, tool inventory, and request/output schemas.
The response never exposes Source/Evidence IDs, query text, paths, duplicate counts, or internal
exceptions.

Extend existing read-only `mke retrieval doctor --strategy ...` output with a
`stable_locator_identity` check over the complete active authority. This explicit operator command
may perform the full read-only audit that request-time Search intentionally avoids. Failure returns
the same problem/cause/next-step recovery contract.

Recovery is limited to restoring a valid backup or re-ingesting original Sources into a new
database path. No in-place deletion, migration, or automatic deduplication is permitted.

## Strategy Alternatives

| Approach | Benefit | Cost or risk | Decision |
|---|---|---|---|
| Query-boundary stable key plus locator uniqueness | Preserves IDs, scores, pagination, and schemas | Adds one stable join/key and a manifest invariant | Selected |
| Deterministic content-derived IDs | Makes IDs reproducible | Changes addressing, migration, collision, and consumer contracts | Rejected |
| Fetch then Python post-sort | Avoids SQL edits | `LIMIT/OFFSET` can omit tied rows; safe repair harms bounds | Rejected |
| Normalize only in evaluation | Makes a test stable | Hides actual Search/MCP behavior | Rejected |

## Stage Alternatives

| Direction | Result | Decision |
|---|---|---|
| Maintenance | Removes the reproduced Agent-visible ordering defect | Do now |
| Docs/regression-only | Records the issue but leaves runtime order unstable | Not sufficient |
| Segmentation comparison | Changes Evidence granularity while the baseline order is unstable | Defer |
| Contextual retrieval comparison | Adds the largest interpretation surface before baseline closure | Defer |

## Evaluation Protocol

Create one bounded public `retrieval-order-v1` mechanism-regression asset with two disjoint
partitions. It is not a reusable retrieval-quality benchmark framework.

### Development

- constructed equal-score FTS page cases;
- constructed equal-overlap CJK page cases;
- constructed timestamp cases;
- two fresh workspaces using inverse ingestion and opaque-ID schedules; and
- pagination at page sizes 1, 2, and the full result count.

### Holdout

- one FTS equal-score group and one CJK equal-overlap group under inverse ID/ingest schedules;
- source fingerprints, Evidence text, locators, and query text disjoint from development;
- bytes and hashes frozen before candidate implementation; and
- one execution only after development passes and candidate commit SHA/runtime profile are frozen.

The holdout is public and nonblind. The protocol makes no secrecy or human-unopened claim.
Independence comes from disjoint bytes, frozen hashes, enforced execution order, frozen candidate
SHA/profile, and one recorded observation. It is a minimal one-shot mechanism challenge set, not
evidence of general retrieval quality.

After first publication, both partitions become development material and cannot serve as a future
segmentation, contextual-retrieval, relevance, or promotion holdout.

### Exact gates

- stable-order rate: `1.0` in development and holdout;
- candidate membership delta: `0`;
- FTS rank-score byte/hex delta: `0`;
- non-tied pair order delta: `0`;
- duplicate/gap pagination count: `0`;
- Search/Ask stable-locator identity: exact;
- Python Search, CLI, MCP v1 compatibility, MCP v2 pagination, and exact read: passed;
- active-only, supersession, Publication, and Evidence provenance: passed;
- historical E1/E2/E3 observation JSON bytes and hashes: unchanged;
- revision-2 replay changes only preidentified equal-score permutations;
- revision-2 metrics, gates, and verdicts: unchanged;
- full tests, Ruff, Pyright, CI, compiled-library export proof, and consumer source-pack proof:
  passed.

Any membership, score, non-tied order, metric, gate, or verdict drift stops the phase. It is not
resolved by choosing a different stable key or widening refresh allowances.

### Historical compatibility closure

Before candidate RED or implementation, Task 0 inventories every source-bound historical
protocol, freeze, receipt, artifact, canonical pointer, and validator that includes an affected
runtime file. The inventory covers numeric/Chinese/CJK, dense, hybrid RRF, relevance-gate, and any
other matched family. Validator disposition must be complete before runtime work begins.

Historical observation JSON bytes and hashes remain immutable. For each affected current-source
validator, add or revise a separate revision-2 compatibility/differential record that binds:

- old artifact hash;
- new source identity;
- recorded runtime profile;
- preidentified tied groups;
- before/after stable projections;
- exact score hex;
- membership and non-tied pair order; and
- recomputed metrics, gates, and verdict.

Canonical self-consistency validates the archived artifact against its historical identity and the
separate revision-2 record against current source. It never implies that revision 2 generated the
historical observation.

### Targeted RED and execution sequence

1. Complete the source-bound historical inventory and validator disposition.
2. Freeze protocol, corpus receipts, partition rules, canonical key order, runtime-profile fields,
   and current-runtime observation.
3. Add tests proving current FTS and CJK flip stable order under inverse opaque-ID schedules.
4. Add pagination/output-budget RED and page/timestamp duplicate-locator
   manifest/candidate-path RED.
5. Confirm failures are limited to the intended stable-order and admissibility contracts.
6. Implement the smallest runtime change.
7. Run development once and exclusive-create its freeze only when every gate passes.
8. Freeze candidate commit SHA/profile; execute the public nonblind holdout exactly once, record
   its receipt, and stop on any failure.
9. Run compatibility, historical differential, full verification, and consumer proof.

The development challenge matrix covers FTS/CJK page and timestamp Evidence, different sources
with the same locator, one source with different locators, `locator_kind`/`locator_end` ties, page
sizes 1/2/full, forced MCP excerpt/envelope-budget fragmentation, continuation across
budget-shortened pages, active-set change, revision-1 Search cursor expiry, exact-read continuity
under a strategy-only same-owner change, Search/Read expiry after owner restart, CJK row/byte caps,
and inverse ingestion/opaque-ID schedules. The holdout stays minimal.

Performance acceptance is structural: one FTS `MATCH`, no N+1, no full text in ordering, bounded
statement count, unchanged CJK row/byte caps, and a recorded fixed-profile query plan.
Wall-clock timing is informational unless a stable threshold is separately preregistered.

This maintenance adds no public `mke eval` subcommand or request flag. Freeze these internal
maintainer entry points:

```bash
uv run python -m mke.evaluation.retrieval_order_workflow development \
  --protocol tests/fixtures/retrieval-order-v1/protocol.json \
  --record-development-freeze \
    benchmarks/retrieval/retrieval-order-v1-development-freeze.json \
  --json

uv run python -m mke.evaluation.retrieval_order_workflow holdout \
  --protocol tests/fixtures/retrieval-order-v1/protocol.json \
  --development-freeze \
    benchmarks/retrieval/retrieval-order-v1-development-freeze.json \
  --record-holdout-receipt \
    benchmarks/retrieval/retrieval-order-v1-holdout-receipt.json \
  --record benchmarks/retrieval/retrieval-order-v1-artifact.json \
  --json

uv run python -m mke.evaluation.retrieval_order_artifact validate \
  --artifact benchmarks/retrieval/retrieval-order-v1-artifact.json \
  --protocol tests/fixtures/retrieval-order-v1/protocol.json \
  --repository .
```

The development command rejects a dirty candidate and records current HEAD plus the runtime
profile. The holdout command requires a passing exclusive development freeze bound to the same
candidate HEAD/profile, exclusive-creates its receipt before observation, and refuses overwrite or
canonical retry.

Valid `--json` execution emits one JSON object with empty stderr. Success is exit 0 and
integrity/proof failure is exit 1. Invalid flag/subcommand combinations use standard `argparse`
stderr and exit 2. Outputs expose no absolute path, opaque ID/cursor, raw query/Evidence, or
traceback.

## Architecture

```text
asset sha256 + validated locator uniqueness
                    |
                    v
Publication -> active Evidence authority
                    |
          +---------+---------+
          |                   |
          v                   v
 FTS5 score order       CJK overlap order
          |                   |
          +---------+---------+
                    |
          stable tie-order key
                    |
       Search / Ask / MCP page cursor
                    |
              Agent context
```

The stable key is retrieval projection semantics, not a domain identifier.

## Test and Proof Matrix

| Surface | Required proof |
|---|---|
| Manifest | Duplicate Run-local locator rejected atomically |
| FTS Search/page | Equal scores stable across ID schedules; page sizes are lossless |
| FTS diagnostic | Runtime and evaluation order agree |
| CJK active scan | Asset fingerprint resolves ties; caps remain unchanged |
| Strategy descriptors | All affected runtime revisions are 2 |
| Cursor behavior | Old Search traversal discarded; exact Read survives same-owner strategy-only change |
| Active authority | Unpublished and superseded Evidence remains absent |
| Historical evaluation | Old bytes retained; revision-2 differential changes only preregistered ties |
| Public recovery | FTS/CJK invalid candidates produce one redacted typed error; doctor checks full active authority |
| Consumer delivery | One installed wheel gives equal projections in inverse fresh stores with no schema drift |

## Documentation Contract

Implementation must update in the same PR:

- new ADR `0012` for stable equal-score order, locator admissibility, revision/cursor effects;
- `docs/explanation/architecture.md`;
- `docs/reference/contracts.md`;
- `docs/reference/mcp-contract.md`;
- `docs/how-to/use-mke-mcp.md`;
- `docs/reference/cli.md`;
- `docs/how-to/enable-cjk-retrieval.md`;
- one maintainer how-to for targeted RED, the internal workflow commands, artifact replay, runtime
  profile, and nonblind/non-quality boundaries; and
- documentation indexes and documentation contract tests.

Release notes change only in a later release phase.

## Operator and Agent Journeys

Agent consumer:

1. Call existing Python/CLI/MCP Search without a tie-break parameter.
2. Continue only while the existing result says more results are available.
3. On Search cursor expiry, discard the complete partial traversal and repeat the initial query.
4. On `retrieval_authority_invalid`, stop consuming that database and route it to the operator.
5. Continue using opaque Evidence IDs for exact reads; stable projection fields are not addresses.

Operator:

1. Run existing `retrieval doctor`.
2. If `stable_locator_identity` fails, restore a valid backup or re-ingest original Sources into a
   new database.
3. Never delete duplicates in place or treat candidate-path checks as a full corruption audit.

Maintainer:

1. Complete Task 0 historical inventory and validator disposition.
2. Reproduce the targeted FTS/CJK RED.
3. Freeze development only after every exact gate passes.
4. Freeze candidate HEAD/profile and execute holdout once.
5. Validate the artifact and revision-2 historical differential.
6. Prove the installed wheel in two external fresh stores through Python/CLI/MCP.
7. Stop on any unauthorized drift.

## Failure Modes and Required Response

| Failure | Required response |
|---|---|
| Score or membership changes | Stop; maintenance exceeded tie-only scope |
| Non-tied order changes | Stop; stable key is placed incorrectly |
| Pagination duplicate or gap | Stop; SQL and cursor order disagree |
| Duplicate locators remain admissible | Stop; stable projection is not total |
| Internal error or traceback escapes | Stop; recovery is not Agent-callable |
| Extra full scan, N+1, text ordering, or cap regression | Stop; structural performance contract failed |
| Historical semantic drift | Stop; never refresh away the difference |
| Holdout runs before freeze or more than once | Fail closed; require a newly approved holdout |
| Public schema changes | Stop; new surface is outside scope |
| Completion requires incomplete retrieval-coverage material | Stop; preserve ownership boundary |

## Stop Points

Stop this phase if:

1. canonical targeted RED does not reproduce both FTS and CJK instability;
2. source-bound validator disposition or corpus/partition/receipt identity cannot be frozen before
   candidate observation;
3. candidate changes score, membership, non-tied order, active-only authority, public schemas, or
   historical metrics/gates/verdicts;
4. holdout is observed before candidate/profile freeze or more than once;
5. one-`MATCH`, bounded-statement, CJK-cap, query-plan, or metadata-only gates regress; or
6. completion would require consuming or modifying incomplete retrieval-coverage work.

Comparison-only results never promote segmentation or contextual retrieval. Maintenance success
only permits a separately approved restart of retrieval-coverage evaluation.

## Implementation Order After Spec Approval

1. Review and approve the actual public spec diff.
2. Produce and review the implementation plan.
3. Start a separate maintenance implementation worktree from current `main`.
4. Execute Task 0 inventory, targeted RED, runtime maintenance, development freeze, one holdout,
   compatibility closure, full verification, authoritative review, and merge preparation.
5. Preserve incomplete retrieval-coverage work without copying its dirty fixture/query choices.
6. Only after maintenance is merged and proof is clean, separately approve any retrieval-coverage
   restart. Segmentation and contextual retrieval remain deferred until that evaluation has frozen
   development and holdout evidence.

## Non-Claims

- Stable tie order is not better relevance.
- A constructed mechanism challenge set is not arbitrary-corpus quality evidence.
- Passing local or CI proof is not production deployment or external adoption.
- This design does not identify any unrelated stopped observation's exact differing pair.
- No segmentation or contextual-retrieval candidate is approved or promoted.
- No implementation, release, or runtime outcome exists yet.
