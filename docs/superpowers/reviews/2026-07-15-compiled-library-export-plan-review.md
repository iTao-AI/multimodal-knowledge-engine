# Compiled Library Export v1 Plan Engineering Review

Status: `TASK 8 COLLECTION AMENDMENT ACCEPTED / CLEARED FOR STEP 5-6`

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

The plan is engineering-complete after ten amendments. The end state remains unchanged: MKE gains
a deterministic complete active-Library export, an independent installed-wheel consumer proof,
and a later isolated LLM Wiki compatibility claim. Delivery is now split into two PRs so the core
runtime contract does not share a candidate or review gate with downstream wiki evidence.

No unresolved architecture decision remains. Product authority and the isolated execution window
already exist. Tasks 1-3 passed their task-scoped reviews. The public plan/review bytes must be
mechanically synchronized first; exact byte/scope verification then clears the same execution turn
to continue Tasks 4-8 without an intermediate authority round trip.

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
- [x] **T9 (P1)** — persistence compatibility — preserve the established comma-joined
  `required_stages` writer and make export strictly validate that representation without migration,
  JSON fallback, or dual-format persistence.
- [x] **T10 (P2)** — concurrency proof — mutate both metadata and Evidence in one WAL transaction
  and require the raced result to equal one complete independently captured before/after DTO.
- [x] **T11 (P1)** — snapshot completeness — retain every active-pointer Source through metadata
  lookup, bind an independent active-pointer count to graph-row count, and fail closed on a missing
  asset edge instead of silently omitting a Publication.
- [x] **T12 (P1)** — SQLite type authority — validate exact runtime storage classes before DTO
  construction; never use Python `str()`/`int()` coercion to fabricate valid text or numeric fields
  from BLOB/TEXT/REAL drift.
- [x] **T13 (P1)** — pytest collection identity — keep both approved `test_library_export.py`
  paths and add only empty `tests/application/__init__.py` and `tests/domain/__init__.py` package
  markers; do not rename tests or change repository-wide import mode.

## Task 3 Targeted Authority Re-review

Reviewed amended commit: `6ed93852951ea80564df002aca8a5c6e992df2dd` on parent `81278b2`.

- The normal manifest writer is again exactly `",".join(manifest.required_stages)`.
- Export accepts only the strict current comma-joined representation; JSON, empty-token,
  whitespace, duplicate, and unsorted drift fail closed without migration or dual-format reads.
- The WAL test changes valid Source metadata and Evidence in one transaction, independently
  captures complete before/after DTOs, and rejects every mixed result by exact DTO equality.
- Task 3 remains one commit and changes only its four approved implementation/test paths.
- Fresh local gates passed, but executable adversarial probes independently reproduced two P1s:
  deleting an active Source's referenced asset silently reduced the export, and BLOB display/text
  values were converted to printable Python representations and accepted as content.

Second repaired commit: `652e5360f27dacd27140cda438e374e226ccd304`, still one Task 3
commit on parent `81278b2`.

- Missing active asset edges now remain visible to the graph validator and fail closed; an
  independent active-pointer count is bound to metadata-row count.
- Every selected SQLite authority field is exact-type checked before DTO construction; BLOB text,
  locator, and revision drift no longer survives Python coercion.
- Independent authority probes for the two original P1s passed; the final combined focused and
  adjacent slice reported 55 passing tests, Ruff clean, and Pyright at 0 errors.

Verdict: `ACCEPTED`. No Critical, Important, or Minor Task 3 finding remains. The exact public docs
sync may be followed immediately by batched Tasks 4-8; no separate docs hard stop is required.

## Task 8 Collection Amendment

At `03a8393ab2d0fefb126ae6c4ebdd7d96a4e21770`, the first bare full-suite command stopped during
collection because `tests/application/test_library_export.py` and
`tests/domain/test_library_export.py` were both imported as top-level `test_library_export`.
This is a real acceptance blocker because no full-suite result exists, but it does not change the
Compiled Library Export contract.

The repository already uses empty package markers to isolate same-basename tests under other test
subdirectories. The bounded resolution is therefore accepted:

- add only zero-byte `tests/application/__init__.py` and `tests/domain/__init__.py`;
- preserve both plan-approved test filenames and their existing references;
- do not change `pyproject.toml`, pytest import mode, production packages, or runtime behavior;
- commit the marker correction before rerunning collection and the complete Step 5 gates;
- rebuild the installed-wheel proof on the resulting committed HEAD rather than reusing the Task 7
  candidate digest;
- hard stop after Step 5 evidence so the planning/review authority can perform Step 6.

An independent repository-external archive simulation added both empty markers and collected the
73 focused tests successfully. The modules resolved as `tests.application.test_library_export` and
`tests.domain.test_library_export`; wheel packaging remains limited to `src/mke`.

Verdict: `ACCEPTED / CLEARED FOR TASK 8 STEP 5-6`.

## Completion Summary

- Step 0 Scope Challenge: scope reduced to two sequential PRs without reducing the end state.
- Architecture Review: 4 issues found, all folded into the plans.
- Code Quality Review: 2 issues found, all folded into the plans.
- Live-Code Authority Review: 6 contradictions found across preflight and Task 3, all folded into
  the design and core plan; one later pytest collection identity gap was folded into the core plan.
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
was accepted at `10bbee5b2aea5fd0fd4c9631e31b786606a9b00a`. The preflight amendment landed at
`3bb2cfb1b3c71547156b0d564a5b3ad8a28cdeda`. Task 3 is accepted at
`652e5360f27dacd27140cda438e374e226ccd304`. Tasks 4-7 and Task 8 documentation are now implemented
through `03a8393ab2d0fefb126ae6c4ebdd7d96a4e21770`. Mechanically replace only the public core plan and
plan review with these exact bytes, verify byte equality and scope, and commit that docs-only sync.
Then add and commit the two empty test package markers, rerun Task 8 Step 5 on that committed HEAD,
and stop at Step 6 for the single authoritative pre-PR review. Earlier stops remain mandatory only
for a concrete architecture conflict, scope expansion, external side effect, or a same-finding
repair that has failed twice.
