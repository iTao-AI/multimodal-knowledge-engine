# Compiled Library Export v1 Plan Engineering Review

Status: `PREFLIGHT AMENDMENT ACCEPTED / CLEARED FOR MECHANICAL AMENDMENT LANDING`

Date: 2026-07-15

Reviewed inputs:

- `2026-07-15-compiled-library-export-design-draft.md`
- `2026-07-15-compiled-library-export-implementation.md`
- `2026-07-15-compiled-library-export-llm-wiki-compatibility-implementation.md`
- MKE `main@a03c2308106ef499c6bd64b0efb1c123d5059f47`
- live SQLite, application, CLI, EvidenceRef, public-error, proof, workflow, ADR, architecture, and
  test surfaces at that baseline

Review method: `superpowers:writing-plans` plus focused `plan-eng-review`. Product direction and
written-spec decisions were already approved; this review challenged execution scope,
architecture, code organization, test paths, failure handling, and performance.

## Verdict

The plan is engineering-complete after eight amendments. The end state remains unchanged: MKE gains
a deterministic complete active-Library export, an independent installed-wheel consumer proof,
and a later isolated LLM Wiki compatibility claim. Delivery is now split into two PRs so the core
runtime contract does not share a candidate or review gate with downstream wiki evidence.

No unresolved architecture decision remains. Product authority and the isolated execution window
already exist; implementation remains paused only until the mechanical amendment landing receives
exact authority review and a resumption dispatch.

The mechanically landed documents were verified byte-for-byte at commit `10bbee5b2aea5fd0fd4c9631e31b786606a9b00a`.
Before Task 1, live-code preflight found two contract contradictions. Both are resolved below; the
three amended documents must land and receive a byte/scope review before implementation resumes.

## Step 0: Scope Challenge

The initial plan named 43 repository paths, expected roughly 30 changed paths, introduced five new
product modules plus proof/docs surfaces, and combined runtime implementation with an agent-driven
downstream compatibility workflow. That was too large for one independently reviewable PR even
though the feature itself was coherent.

Accepted reduction:

```text
PR 1: core Compiled Library Export
  domain snapshot -> read-only SQLite -> renderer -> safe files -> CLI
  -> standalone consumer -> same-wheel Python 3.12/3.13 proof -> CI/docs

merge + post-merge verification
  |
  v
PR 2: LLM Wiki compatibility evidence
  fresh retained export -> isolated local wiki -> provenance return
  -> bounded docs claim -> targeted docs/evidence verification
```

This is sequencing, not feature reduction. v0.1.3 remains a later release decision after both PRs.

## What already exists

| Existing authority | Reuse decision |
|---|---|
| `SQLiteStore._observe_active_publications()` | Extract and reuse the active graph row validator; do not create a second Publication truth model. |
| `search_provenance_snapshot()` | Reuse the existing one-transaction PEP 249 snapshot pattern. |
| `RunManifest`, `CandidateEvidence`, `validate_manifest()` | Reconstruct and validate export snapshot authority rather than duplicating manifest rules. |
| `EvidenceRefV1` | Use as the exact JSONL provenance schema and validation oracle. |
| `PublicError` and CLI rendering | Preserve the shared payload and add only command-specific closed response composition. |
| `consumer_source_pack_proof.py` | Reuse bounded command/environment/candidate helpers; do not copy process-group orchestration. |
| current pinned proof workflow | Mirror action pins and online-prewarm/offline-proof structure in one non-matrix job. |
| LLM Wiki agent workflow | Use only after core merge in a call-owned local `.wiki/`; do not add an adapter or dependency. |

## Architecture Review

### A1. One PR mixed runtime authority with downstream compatibility

Severity: P1. Confidence: 10/10.

Resolution: accepted two-PR delivery. PR 1 owns product behavior and deterministic consumer proof.
PR 2 owns only fresh downstream compatibility evidence and documentation after core merge.

### A2. Installed proof depended on private publisher `_ops`

Severity: P2. Confidence: 9/10.

Resolution: removed. Installed proof uses public installed `mke ingest`, public
`mke library export`, and the independent standard-library consumer. Cleanup fault injection stays
at the filesystem adapter unit boundary.

### A3. Filesystem plan exceeded the local product threat model

Severity: P2. Confidence: 9/10.

Resolution: keep exclusive target creation, no-follow descriptor writes, manifest-last commit,
bounded re-read, exact inventory, cleanup identity checks, and preservation of replacement operator
state. Remove the generic `DirectoryOps` interface, exhaustive micro-step inode replacement matrix,
and five-repeat race gate. The remaining coverage targets real local failures, not a hostile
same-account process at every instruction boundary.

### A4. The manifest commit point allowed ambiguous post-publication failure

Severity: P1. Confidence: 9/10.

Resolution: every file close, digest check, inventory check, temporary-manifest re-read, descriptor
close, and ownership check occurs before the final manifest rename. Publishing
`export-manifest.json` is the final production operation. A directory without that marker is
uncommitted; a directory with it has no remaining fallible producer step.

## Code Quality Review

### Q1. A regression-only MCP schema file was included in commit scope

Severity: P3. Confidence: 10/10.

Resolution: `tests/interfaces/test_mcp_v1_schemas.py` remains a required regression command but is
no longer listed as a planned modification or staged Task 4 file.

### Q2. Docs-only compatibility closure repeated unrelated full gates

Severity: P2. Confidence: 9/10.

Resolution: PR 2 reruns documentation contract tests, presentation audit, standalone consumer/proof
tests, fresh same-wheel generic proof, and the isolated wiki proof. It relies on normal PR CI for
repository-wide regressions and does not locally repeat unrelated OCR, retrieval, build, Ruff,
Pyright, demo, and product proofs. PR 1 still runs the complete repository gate.

No DRY-motivated refactor of the existing source-pack proof is added. Importing its reviewed helper
surface is a smaller and safer change than restructuring an already-shipped proof in this feature.

## Pre-Implementation Live-Code Authority Review

### P1. Planned export causes expanded the frozen MCP/consumer contract

Severity: P1. Confidence: 10/10.

Live code confirms `_ALLOWLISTED_CAUSES` is consumed by MCP response validation and copied in full
into the exact consumer source-pack fixture. None of the six planned export causes exists in that
fixture. Adding them would contradict both the no-MCP-change boundary and byte-identical consumer
contract requirement.

Resolution: the six non-redacted export causes move to a closed command-local set in
`mke.interfaces.library_export`. `LibraryExportErrorV1` accepts only those six plus the exact
redacted literal. Typed export failures may reuse the `PublicError` value/payload shape without
changing the shared factory or allowlist. Shared `public_errors.py`, MCP schemas, and the consumer
fixture are regression-only and must remain unchanged.

### P2. Global retrieval options leaked into the closed export parser surface

Severity: P2. Confidence: 10/10.

The current parser defines `--retrieval-query-policy` and `--retrieval-strategy` globally, so both
would be accepted before `library export` unless explicitly guarded. That conflicts with the
closed command contract and the rule that export does not consult retrieval runtime configuration.

Resolution: preserve global `--db`, but reject both retrieval options, including equals forms,
for `library export` before runtime construction. RED/GREEN parser tests bind both options and the
consumer source-pack contract test proves the shared MCP surface remains unchanged.

## Test Review

Test framework: Pytest with strict Pyright and Ruff; installed proof uses explicit Python 3.12 and
3.13 interpreters plus one built wheel.

```text
CODE PATHS                                             USER / CONSUMER FLOWS
[+] read-only startup                                  [+] export active Library
  |-- missing/incompatible DB       [TESTED]              |-- JSON success       [TESTED]
  |-- query_only/migration bypass   [TESTED]              |-- human success      [TESTED]
  `-- normal owner path unchanged   [TESTED]              `-- stable failures    [TESTED]

[+] bounded SQLite snapshot                            [+] consume portable copy
  |-- empty/no active               [TESTED]              |-- exact inventory    [TESTED]
  |-- valid page + timestamp        [TESTED]              |-- canonical bytes    [TESTED]
  |-- corrupt provenance graph      [TESTED]              |-- fingerprint map    [TESTED]
  |-- count/byte limits             [TESTED]              `-- every drift field  [TESTED]
  `-- concurrent writer snapshot    [TESTED]

[+] renderer + publisher                              [+] installed distribution
  |-- canonical JSONL/Markdown       [TESTED]              |-- Python 3.12         [E2E]
  |-- untrusted text serialization  [TESTED]              |-- Python 3.13         [E2E]
  |-- short write/digest drift      [TESTED]              |-- repeated export    [E2E]
  |-- collision/symlink/cleanup     [TESTED]              `-- public negatives   [E2E]
  `-- manifest final commit         [TESTED]

[+] follow-up compatibility                           [+] local-Agent workflow
  |-- immutable raw ingest          [MANUAL PROOF]         |-- page query          [MANUAL]
  |-- sourced article/index         [MANUAL PROOF]         |-- timestamp query     [MANUAL]
  |-- EvidenceRef return path       [MANUAL PROOF]         `-- configured hub safe[MANUAL]
  `-- lint/rehash/cleanup           [MANUAL PROOF]
```

Coverage result: all planned branches and user flows have unit, integration, installed-wheel E2E,
or explicitly bounded operator-local proof coverage. No prompt/LLM output quality evaluation is
required because the wiki phase checks deterministic source linkage and provenance return, not
generated prose quality.

## Failure Modes

| Code path | Realistic failure | Test/proof | Error visible to operator |
|---|---|---|---|
| read-only startup | DB missing, stale, or permissions invalid | startup matrix | stable unavailable/incompatible cause |
| snapshot | active pointer or manifest graph drift | corruption matrix | stable provenance-invalid cause |
| snapshot | Library exceeds count or byte budget | exact-boundary tests | stable too-large cause |
| renderer | untrusted text attempts Markdown/frontmatter injection | golden/adversarial tests | serialized as data or typed failure |
| publisher | short write, digest mismatch, collision, cleanup failure | adapter failure matrix | stable write/cleanup failure |
| CLI | unknown exception contains a path or Source text | redaction tests | redacted public error |
| consumer | copied export is truncated, non-canonical, or cross-file inconsistent | mutation matrix | allowlisted consumer failure code |
| installed proof | interpreter/cache/build/process cleanup unavailable | controller tests and real run | stable proof failure code |
| wiki compatibility | ingest rewrites identity or compiled article loses source link | isolated proof | compatibility claim withheld; generic export unaffected |

Critical silent gaps: 0.

## Performance Review

No issue found after amendment.

- SQLite data access is set-oriented and constant-query: five data `SELECT`s regardless of Source
  count; PRAGMA/schema checks are startup-only.
- Preflight count and UTF-8 byte totals run before Evidence materialization.
- Closed limits are 4,096 active Publications, 65,536 Evidence records, 128 MiB aggregate text,
  and 64 MiB per rendered source file.
- Snapshot memory is bounded by aggregate text; renderer and publisher retain one Source's emitted
  bytes at a time plus small manifest metadata.
- The workflow adds no model call, network requirement, background process, cache, or watcher.

## NOT in scope

- Production OCR or Phase 0 provider promotion: separate product phase with representative inputs.
- Rich block/document IR, table/formula/chart/layout reconstruction, and asset graph: no current
  consumer evidence justifies a schema.
- MCP Resource, HTTP service, watcher, plugin, or bidirectional sync: no second consumer has shown
  integration friction that warrants another adapter.
- Direct Obsidian or configured LLM Wiki hub write: export remains product-neutral and local.
- Windows support claim: current proof covers the repository's verified POSIX CI/local surfaces;
  unsupported platforms must fail normally and remain unclaimed.
- v0.1.3 version bump, tag, Release, registry publication, and deployment: separate authorization
  after both PRs.

## TODOS.md Review

No `TODOS.md` exists, and this review creates no new deferred blocker that needs a public TODO.
The separate compatibility plan captures the only ordered follow-up. Longer-term OCR, rich IR, and
MCP Resource possibilities remain explicitly documented future phases, not current commitments.

## Parallelization Strategy

| Lane | Modules | Depends on |
|---|---|---|
| A: core Tasks 1-8 | domain, SQLite adapter, application, filesystem adapter, interfaces, proof, docs | sequential contract flow |
| B: compatibility Tasks 1-4 | retained proof, operator-local wiki, docs/evidence | core PR merged and post-merge verified |

Execution is sequential. Core tasks share contract and fixture authority, so parallel worktrees
would increase drift and merge conflicts. Lane B starts only after Lane A lands; no useful
same-baseline parallelization remains.

## Implementation Tasks

All review-derived amendments are already folded into the written plans:

- [x] **T1 (P1)** — delivery — split runtime and downstream compatibility into two PRs.
- [x] **T2 (P2)** — proof — remove installed private `_ops` fault injection.
- [x] **T3 (P2)** — filesystem — bound the threat model and remove exhaustive race gates.
- [x] **T4 (P1)** — publication — make manifest rename the final production operation.
- [x] **T5 (P3)** — test scope — remove unchanged MCP schema test from staged files.
- [x] **T6 (P2)** — verification — right-size the docs/evidence follow-up gates.
- [x] **T7 (P1)** — public errors — keep export causes command-local and preserve the frozen
  MCP/consumer cause contract.
- [x] **T8 (P2)** — CLI — reject global retrieval runtime overrides on the closed export command.

## Completion Summary

- Step 0 Scope Challenge: scope reduced to two sequential PRs without reducing the end state.
- Architecture Review: 4 issues found, all folded into the plans.
- Code Quality Review: 2 issues found, all folded into the plans.
- Live-Code Authority Review: 2 contradictions found, both folded into the design and core plan.
- Test Review: diagram produced, 0 remaining gaps.
- Performance Review: 0 issues found.
- NOT in scope: written.
- What already exists: written.
- TODOS.md updates: 0 proposed.
- Failure modes: 0 critical gaps.
- Outside voice: skipped; the written spec already completed product-direction review and no
  unresolved architecture disagreement remains.
- Parallelization: 2 sequential lanes, 0 concurrent lanes.
- Lake Score: 3/3 complete, right-sized recommendations accepted or authority-selected.

## Final Gate

Explicit product and plan approval was received on 2026-07-15, and the initial mechanical landing
was accepted at `10bbee5b2aea5fd0fd4c9631e31b786606a9b00a`. The 2026-07-16 preflight amendment is now
authority-approved. Mechanically replace only the public design, core plan, and plan review with
the amended bytes, commit them, and stop. Core implementation resumes only after that exact diff
receives authority review and a separate resumption dispatch.
