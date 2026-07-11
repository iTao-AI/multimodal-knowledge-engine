# Versioned Evidence Provenance Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this
> plan task-by-task in an isolated worktree. Use `superpowers:test-driven-development` for every
> behavior change and `superpowers:verification-before-completion` before the final handoff.

**Goal:** Add a narrow, versioned, read-only Evidence provenance contract for generic Agent
consumers without changing MKE retrieval, ingestion, Publication, Ask refusal, or runtime defaults.

**Architecture:** New MCP snapshot methods call the unchanged retrieval path, then bulk-enrich its
`SearchResult` values from existing SQLite rows inside the same PEP 249 transaction. Three additive
v1 read-only MCP tools serialize those enriched values through strict Pydantic success/error unions;
a real stdio MCP consumer proof verifies legacy compatibility, v1 schemas, lifecycle identity,
empty states, locators, and redaction.

**Tech Stack:** Python 3.12/3.13, SQLite, Pydantic v2, FastMCP/MCP Python SDK, pytest, Ruff,
Pyright, uv.

Planning base: `main@793788f2d74a1ec072fe205e89acd13ab595bad7`.

Design: [Versioned Evidence Provenance Contract Design](../specs/2026-07-11-versioned-evidence-provenance-contract-design.md).

Planning gate: the planning window must commit the design, plan, and CLEAN plan review locally
before dispatch. The execution window must refuse to start if any of those documents is untracked,
missing from its base commit, or names a different planning base.

Implementation status: completed locally on `codex/evidence-provenance-contract`; authoritative
planning-window diff review remains pending.

Completion evidence:

- exact planning commit/parent and `main == origin/main == 793788f2...` verified before worktree
  creation;
- legacy five-tool schemas frozen and committed before MCP production changes;
- targeted contract gate: `460 passed, 5 skipped`;
- full suite: `1356 passed, 5 skipped`;
- Ruff passed; Pyright reported `0 errors, 0 warnings, 0 informations`; sdist and wheel built;
- `mke proof run`: 8/8; `mke demo --verify`: passed;
- local-knowledge and Evidence-provenance real stdio proofs: passed;
- Python 3.12.13 and 3.13.12 external installed-wheel proofs passed with lock-derived constraints,
  hostile `PYTHONPATH`, external cwd, installed-module identity checks, and `UV_OFFLINE=1`;
- E1/E2/E3-A/E3-B normalized reports matched Task 0 byte-for-byte; E1 through E3-E canonical
  validators passed after identity-only dependency closure;
- document-release audit found reference/how-to/explanation/ADR coverage with no diagram drift;
- release presentation audit returned `status=ok` with zero violations; public-boundary scan and
  `git diff --check` passed.

Plan review: [Versioned Evidence Provenance Contract Plan Review](../reviews/2026-07-11-versioned-evidence-provenance-contract-plan-review.md).

## Global Constraints

- Work in a new isolated worktree and branch from the planning commit containing this plan.
- Keep all five existing MCP tool names, input schemas, and output contracts unchanged.
- Keep existing `KnowledgeEngine.search()`, `KnowledgeEngine.ask()`, CLI output, retrieval strategy,
  Publication activation, and the eight-case `mke proof run` contract unchanged.
- Do not add a database migration, persistence table, retrieval projection, or consumer-owned join.
- Do not add business metadata, crawler/OCR/HTTP/UI/framework/runtime-promotion/release work.
- Never render paths, credentials, environment values, stderr, tracebacks, internal metadata,
  transient IDs, or Evidence text in proof reports.
- Stop if normalized E1 through E3-E semantics, corpus/qrel/query content, observations, metrics,
  gates, or verdicts drift. Validator-proven source/scope/dependency identity metadata in canonical
  artifacts and protocol-lock JSON may change only through the existing atomic refresh workflow.
- Do not push, create a PR, merge, tag, release, deploy, or publish a package.

## Target Contract

```text
SQLite active snapshot
  -> ActivePublicationObservation
  -> unchanged FTS/CJK retrieval
  -> unchanged SearchResult[]
  -> one bulk provenance enrichment
  -> EvidenceRefV1
  -> strict additive v1 list/search/ask MCP response union
```

Public schema constants:

- `mke.evidence_ref.v1`
- `mke.active_publication_observation.v1`
- `mke.list_libraries_response.v1`
- `mke.search_library_response.v1`
- `mke.ask_library_response.v1`

## Task 0: Freeze the current baseline and create the isolated execution branch

**Files:**

- Read: `AGENTS.md`
- Read: this plan, its design, and the immutable plan review named above
- Record outside the repository: normalized E1/E2/E3-A/E3-B/E3-C/E3-D/E3-E reports
- Create: `tests/fixtures/mcp/legacy-tool-schemas.json`
- Create: `tests/interfaces/test_mcp_legacy_schema_snapshot.py`

- [x] **Step 1: Verify the exact base and create an isolated worktree**

Require `main == origin/main == 793788f2d74a1ec072fe205e89acd13ab595bad7` before branching from
the planning commit. Create a new worktree named for the Evidence provenance contract. Do not reuse
an older feature worktree.

- [x] **Step 2: Run baseline MCP/application tests**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/application/test_ask.py \
  tests/interfaces/test_mcp_contract.py \
  tests/interfaces/test_mcp_server.py \
  tests/proof/test_local_knowledge.py \
  tests/proof/test_mcp_deployment_client.py
```

Capture the complete input and output schemas for all five existing tools as normalized, sorted JSON
in `tests/fixtures/mcp/legacy-tool-schemas.json`, including
`baseline_commit="793788f2d74a1ec072fe205e89acd13ab595bad7"`. Add a regression test that compares the legacy
subset of `build_mcp_server(...).list_tools()` to this fixture while ignoring additive tools. Commit
the fixture and test before changing MCP code so CI and future worktrees share the same baseline.

- [x] **Step 3: Verify and commit the legacy schema fixture**

```bash
UV_OFFLINE=1 uv run pytest -q tests/interfaces/test_mcp_legacy_schema_snapshot.py
git diff --check
git add tests/fixtures/mcp/legacy-tool-schemas.json \
  tests/interfaces/test_mcp_legacy_schema_snapshot.py
git commit -m "test(mcp): freeze legacy tool schemas"
```

- [x] **Step 4: Record and validate historical evaluation reports**

Run the canonical E1 through E3-E evaluation commands and validators already documented by the
repository. Normalize volatile duration fields and retain the reports outside the repository for
the final semantic-equality comparison. Stop if any current artifact is invalid before changes.

## Task 1: Define provenance and active-observation domain contracts

**Files:**

- Modify: `src/mke/domain/__init__.py`
- Modify: `tests/domain/test_manifest.py`
- Create or modify: focused domain tests matching existing conventions

**Interfaces:**

- Keep `SearchResult` unchanged.
- Add immutable `SearchResultProvenance`, `ActivePublicationObservation`, `SearchSnapshot`, and
  `AskSnapshot` values.
- Preserve the existing Search and Ask result semantics.

- [x] **Step 1: Write RED domain validation tests**

Cover:

- valid `sha256:<64-lowercase-hex>` source-content fingerprints;
- invalid fingerprint algorithms, casing, length, and characters;
- positive Publication revision;
- page locator invariants and timestamp locator invariants;
- observation state/count invariants, including rejection of active Publication with zero Evidence;
- immutable Search/Ask snapshot composition.

Run:

```bash
UV_OFFLINE=1 uv run pytest -q tests/domain
```

- [x] **Step 2: Implement the minimal immutable domain values**

Do not introduce product metadata or modify `SearchResult`. `SearchResultProvenance` wraps one
unchanged Search result with `content_fingerprint`, `publication_revision`, and `run_id`; the MCP
model in Task 4 is the versioned transport projection.

- [x] **Step 3: Verify GREEN and commit**

```bash
UV_OFFLINE=1 uv run pytest -q tests/domain
git diff --check
git add src/mke/domain tests/domain
git commit -m "feat(domain): define Evidence provenance snapshots"
```

## Task 2: Read provenance and active state from SQLite in one snapshot

**Files:**

- Modify: `src/mke/adapters/sqlite/__init__.py`
- Create: `tests/adapters/test_sqlite_provenance.py`
- Modify: `tests/adapters/test_sqlite_fts.py`
- Modify: `tests/adapters/test_sqlite_cjk_active_scan.py`
- Modify: retrieval tests only where enriched `SearchResult` construction requires it

**Interfaces:**

- Add `observe_active_publications() -> ActivePublicationObservation`.
- Add `search_provenance_snapshot(query, limit) -> SearchSnapshot`.
- After unchanged FTS/CJK retrieval, bulk-load `publications.revision`, `publications.run_id`, and
  `run_manifests.asset_sha256` for the returned Evidence IDs in one query.

- [x] **Step 1: Write RED SQLite provenance tests**

Cover PDF and video Evidence, page/timestamp locators, Publication revision, Run identity, and
`sha256:` source-content fingerprint. Require only active Publication Evidence after reprocessing.
Require the original FTS and CJK SQL/result shapes and `SearchResult` fields to remain unchanged.

- [x] **Step 2: Write RED observation-state tests**

Cover:

- fresh database -> `empty`;
- failed Run with a Source but no Publication -> `no_active_publication`;
- published Source -> `active` with exact counts;
- multiple Sources with a mixture of published and failed Runs;
- corrupted active Publication with zero active Evidence -> fail closed;
- active pointer to a different Source's Publication -> fail closed;
- Publication/Run/Source mismatch -> fail closed;
- Evidence/Run/Source mismatch -> fail closed;
- Run-manifest fingerprint that differs from the Source asset SHA-256 -> fail closed;
- Source active revision that differs from Publication revision -> fail closed;
- active Run state other than `published` -> fail closed;
- Run-manifest Evidence count that differs from active Evidence rows -> fail closed;
- any joined row outside the implicit `local` Library -> fail closed.

- [x] **Step 3: Write RED consistency and query-shape regressions**

Inject Publication activation from a second connection between hypothetical separate reads and
require `search_provenance_snapshot` to return one consistent SQLite snapshot. Use SQL trace evidence to
require a fixed number of observation/integrity queries, the unchanged bounded retrieval queries,
and one bulk provenance query, with no per-result lookup.

- [x] **Step 4: Implement joined retrieval and snapshot reads**

Use the transaction already maintained by `sqlite3` with `autocommit=False`; do not issue a nested
`BEGIN`. Execute observation, unchanged retrieval, and bulk enrichment before closing the read
snapshot with `commit()` on success or `rollback()` on error. Compare raw active pointers and base
Search result IDs to the fully joined provenance graph so a missing/mismatched relation fails closed
instead of becoming a false no-match. Do not mutate or rebuild `active_evidence_fts`, and do not
change ranking, ordering, limits, CJK eligibility, or scan budgets.

- [x] **Step 5: Verify both retrieval paths and commit**

```bash
UV_OFFLINE=1 uv run pytest -q tests/adapters tests/retrieval tests/application/test_cjk_active_scan_runtime.py
git diff --check
git add src/mke/adapters/sqlite tests/adapters tests/retrieval \
  tests/application/test_cjk_active_scan_runtime.py
git commit -m "feat(sqlite): snapshot active Evidence provenance"
```

## Task 3: Expose snapshot methods through the application boundary

**Files:**

- Modify: `src/mke/application/__init__.py`
- Modify: `tests/application/test_ask.py`
- Create: `tests/application/test_evidence_provenance.py`

**Interfaces:**

- Add `KnowledgeEngine.observe_active_publications()`.
- Add `KnowledgeEngine.search_provenance_snapshot()` for v1 MCP consumers.
- Add `KnowledgeEngine.ask_provenance_snapshot()` that constructs the existing `AskResult` from the snapshot
  Evidence and returns the same observation.
- Keep `search()` and `ask()` behavior and signatures unchanged.

- [x] **Step 1: Write RED Search/Ask projection-consistency tests**

For one matching query, require v1 Search and Ask snapshots to return equal
`SearchResultProvenance` values for each shared Evidence. Cover evidence-found and
insufficient-evidence branches.

- [x] **Step 2: Write RED empty/no-active/no-match tests**

Require:

- empty and no-active observations remain distinguishable even though both return no Evidence;
- active no-match returns `active` plus no Evidence;
- Ask still returns `insufficient_evidence` and its existing limitations in all no-Evidence cases.

- [x] **Step 3: Implement snapshot application methods without changing normal runtime paths**

Extract only the minimal private helper needed to avoid duplicating Ask result construction. Do not
route CLI/evaluation calls through the new MCP-specific snapshot methods.

- [x] **Step 4: Verify and commit**

```bash
UV_OFFLINE=1 uv run pytest -q tests/application \
  tests/interfaces/test_cli_retrieval.py tests/interfaces/test_cli_ask.py
git diff --check
git add src/mke/application tests/application
git commit -m "feat(application): expose active Evidence snapshots"
```

## Task 4: Add strict parallel v1 read-only MCP schemas and tools

**Files:**

- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `src/mke/interfaces/mcp_schemas.py`
- Modify: `src/mke/interfaces/mcp_contract.py`
- Modify: `src/mke/interfaces/mcp_server.py`
- Modify: `tests/interfaces/test_mcp_contract.py`
- Modify: `tests/interfaces/test_mcp_server.py`
- Modify: MCP schema snapshot/contract tests discovered during implementation

**Interfaces:**

- Pydantic strict models with `extra="forbid"`, immutable values, literal schema versions, bounded
  strings/counts, discriminated locators, and top-level success/error unions.
- `list_libraries_v1(config)`, `search_library_v1(...)`, and `ask_library_v1(...)` return typed v1
  models.
- FastMCP exposes top-level `oneOf` output schemas discriminated by `ok`.
- All five existing tool contracts remain unchanged.

- [x] **Step 1: Declare the existing direct Pydantic dependency**

Add `pydantic>=2.13.4,<3`, matching the currently locked MCP runtime dependency. Regenerate
`uv.lock` without upgrading unrelated packages, and assert the package set/version remains
otherwise stable.

- [x] **Step 2: Write RED model tests**

Reject unknown schema version, missing field, extra field, bool-as-int, invalid ID, invalid
fingerprint, invalid revision, invalid locator, invalid observation state/count, and mixed success/
error branch fields. Require `model_dump(mode="json")` to produce only public fields.

- [x] **Step 3: Write RED FastMCP output-schema tests**

For all three additive v1 read tools require:

- exact response version constant;
- top-level success/error `oneOf` discriminated by `ok`;
- `additionalProperties: false` for every object definition;
- exact shared `mke.evidence_ref.v1` fields for Search and Ask;
- no path, credential, provider, model, cache, stderr, traceback, environment, or runtime selector
  terms.

Also require all five legacy input and output schemas to remain byte-for-byte equivalent to the
Task 0 snapshot.
Keep input-schema owner-control terms separate from output-schema disclosure terms: output
validation must allow public `publication_revision` while still rejecting provider/model/cache/
credential/path/environment/stderr/traceback metadata.

- [x] **Step 4: Implement typed contract mapping and response-specific safe errors**

Map domain values once through a shared `EvidenceRefV1.from_provenance_result()` path. Add a typed
v1 safe-tool decorator/error factory rather than reusing the legacy dict-returning `_safe_tool`.
Adapt unexpected
exceptions to response-specific strict error models while preserving redacted `problem/cause/
next_step` and `active_publication_impact="unchanged"`.

- [x] **Step 5: Write RED/green MCP behavior tests**

Cover v1 list observation, Search results, Ask citations, empty/no-active/active-no-match, invalid
query/limit, storage failure, CJK budget failure, unknown exception redaction, and response
serialization through FastMCP.

- [x] **Step 6: Verify interfaces and commit**

```bash
UV_OFFLINE=1 uv run pytest -q tests/interfaces tests/application/test_evidence_provenance.py
UV_OFFLINE=1 uv run ruff check src/mke/interfaces tests/interfaces
UV_OFFLINE=1 uv run pyright src/mke/interfaces tests/interfaces
git diff --check
git add pyproject.toml uv.lock src/mke/interfaces tests/interfaces
git commit -m "feat(mcp): version Evidence provenance responses"
```

## Task 5: Update existing MCP consumers and add a real provenance proof

**Files:**

- Modify: `src/mke/proof/mcp_deployment_client.py`
- Modify: `src/mke/proof/local_knowledge.py`
- Create: `src/mke/proof/evidence_provenance.py`
- Modify: `src/mke/proof/__init__.py`
- Create: `scripts/evidence_provenance_proof.py`
- Modify: `tests/proof/test_mcp_deployment_client.py`
- Modify: `tests/proof/test_local_knowledge.py`
- Create: `tests/proof/test_evidence_provenance.py`
- Create: `tests/scripts/test_evidence_provenance_proof.py`

**Interfaces:**

- Consumer validation reads the three v1 tool `outputSchema` values and response payloads fail
  closed.
- New proof prints one redacted aggregate JSON object and leaves the five legacy tool contracts and
  existing proof output contracts unchanged.

- [x] **Step 1: Write RED stale-consumer regressions**

The new v1 consumer helper must reject legacy/open shapes when parsing a v1 result, unknown versions,
extra fields, mixed success/error payloads, invalid observation counts, invalid provenance, and v1
Search/Ask projection drift. Legacy consumers continue to accept only their unchanged legacy tools.

- [x] **Step 2: Preserve legacy consumers and add v1 schema discovery**

Keep legacy flow assertions unchanged. Extend tool discovery to require the additive v1 tools and
their strict output schemas without routing legacy proofs through the new payloads.

- [x] **Step 3: Write RED real stdio lifecycle proof tests**

Use repository-owned `tests/fixtures/local-knowledge-v1`, `tests/fixtures/pdf/invalid.pdf`, and
`tests/fixtures/video/short-audio.mp4` plus its sidecar. Verify the eleven proof cases from the design,
including same-store reingest and fresh-store fingerprint stability.

- [x] **Step 4: Implement the proof and fail-closed script**

Create independent temporary stores and real stdio MCP sessions. Retain IDs/text only in memory.
The rendered report may include schema names, state names, counts, and booleans; it must not include
any source text, identifier, path, command, environment, stderr, or exception detail. Bound server
startup, session initialization, and every tool call with explicit timeouts; on timeout,
cancellation, or failure terminate the child and remove temporary stores in `finally` cleanup.

- [x] **Step 5: Verify proof outputs and commit**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/proof/test_mcp_deployment_client.py \
  tests/proof/test_local_knowledge.py \
  tests/proof/test_evidence_provenance.py \
  tests/scripts/test_evidence_provenance_proof.py
UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py
UV_OFFLINE=1 uv run python scripts/evidence_provenance_proof.py
git diff --check
git add src/mke/proof scripts/evidence_provenance_proof.py tests/proof \
  tests/scripts/test_evidence_provenance_proof.py
git commit -m "test(proof): prove Evidence provenance contract"
```

## Task 6: Document the public contract and architecture decision

**Files:**

- Create: `docs/decisions/0009-versioned-evidence-provenance-contract.md`
- Modify: `docs/explanation/architecture.md`
- Modify: `docs/reference/mcp-contract.md`
- Modify: `docs/how-to/use-mke-mcp.md`
- Create: `docs/how-to/run-evidence-provenance-proof.md`
- Modify: `docs/README.md`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: documentation tests matching current conventions
- Create: `docs/superpowers/reviews/2026-07-11-versioned-evidence-provenance-contract-implementation-review.md`

- [x] **Step 1: Write RED documentation assertions**

Require public docs to contain exact schema names, evidence fields, observation states, compatibility
boundary, proof command, active-only semantics, and explicit non-goals. Reject stale open-schema
examples, private paths, credentials, stderr/traceback examples, and claims that dense/RRF/reranker
are runtime behavior.

- [x] **Step 2: Write ADR-0009 and update Diataxis surfaces**

Explain why the contract adds parallel v1 read tools, why observation/results share a SQLite
snapshot, why fingerprints identify source bytes, why opaque IDs are not cross-store stable, and
why legacy/write-tool versioning is deferred.

- [x] **Step 3: Add the durable implementation review skeleton**

Record scope, verification commands, artifact closure, remaining risks, and authoritative
implementation-review status as pending. Do not modify or downgrade the separate CLEAN plan review,
and do not claim implementation review CLEAN before the planning/review window completes it.

- [x] **Step 4: Run document-release audit and commit**

Use `gstack-document-release` as a pre-merge documentation audit. Apply only findings relevant to
this contract. Then run focused documentation tests and relative-link checks.

```bash
UV_OFFLINE=1 uv run pytest -q tests/evaluation/test_*documentation.py \
  tests/scripts/test_release_presentation_audit.py
git diff --check
git add README.md README_CN.md docs tests
git commit -m "docs(mcp): document Evidence provenance contract"
```

## Task 7: Close the evaluation artifact identity dependency chain

**Files:**

- Modify only the canonical E1 through E3-E artifacts and protocol-lock identity metadata required
  by the existing repository refresh workflow
- Modify identity-reference tests/docs only when a validator proves they are stale

- [x] **Step 1: Run every validator before writing**

Record the exact invalid chain. Do not assume that only E1 or E2 needs refresh. Do not redesign the
historical identity boundary in this feature: that would alter evaluation provenance policy and is
outside the approved MCP contract scope.

- [x] **Step 2: Perform repository-supported identity-only refresh**

Use the atomic refresh tooling where supported, then rebind downstream E3-C/E3-D/E3-E historical
arm identities in dependency order. Before each write, compare normalized semantic payloads to Task
0 and abort on any change outside approved source/scope/provenance identities.

- [x] **Step 3: Run all artifact tests and validators**

Require E1 through E3-E canonical validators and artifact regression suites to pass. Require qrels,
corpus fixture bytes, query definitions, observations, metrics, gates, selected candidates/profiles,
and verdicts to be byte- or semantic-equivalent as appropriate. Allow only validator-proven
source/scope/dependency identity fields in canonical artifacts and protocol-lock JSON to change.

- [x] **Step 4: Commit identity closure separately**

```bash
git diff --check
git diff --name-only -- benchmarks/retrieval tests/fixtures tests/evaluation docs/how-to
# Inspect the list, then run git add -- with only validator-proven artifacts, protocol-lock identity
# metadata, identity-reference tests, and identity-reference docs.
# Do not stage corpus fixture bytes, qrels, query definitions, observations, metrics, gates, or verdicts.
git commit -m "test(eval): refresh provenance contract identities"
```

Do not stage any qrel or fixture byte change.

## Task 8: Full verification and clean local handoff

**Files:**

- Review: all branch changes against the planning base
- Modify: only files required by verified review or verification findings

- [x] **Step 1: Run targeted contract gates**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/domain \
  tests/adapters \
  tests/application/test_ask.py \
  tests/application/test_evidence_provenance.py \
  tests/interfaces \
  tests/proof/test_mcp_deployment_client.py \
  tests/proof/test_local_knowledge.py \
  tests/proof/test_evidence_provenance.py \
  tests/scripts/test_evidence_provenance_proof.py
UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py
UV_OFFLINE=1 uv run python scripts/evidence_provenance_proof.py
```

- [x] **Step 2: Run complete repository gates**

```bash
UV_OFFLINE=1 uv run pytest -q
UV_OFFLINE=1 uv run ruff check .
UV_OFFLINE=1 uv run pyright
UV_OFFLINE=1 uv build
UV_OFFLINE=1 uv run mke proof run
UV_OFFLINE=1 uv run mke demo --verify
UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py
UV_OFFLINE=1 uv run python scripts/evidence_provenance_proof.py
uv run python scripts/release_presentation_audit.py --root .
git diff --check
```

Also run every E1 through E3-E evaluator/validator and compare normalized reports to Task 0.

- [x] **Step 3: Run installed-wheel consumer proof on Python 3.12 and 3.13**

Build one wheel, install it into fresh external temporary environments with the existing lock/cache,
run MCP schema and provenance consumer smoke from an external working directory under hostile
`PYTHONPATH`, and require imports/executables to resolve outside the repository. Do not download a
model or fixture. Run strictly offline; if the package cache is incomplete, stop and report the
missing locked wheel instead of authorizing network access or weakening the proof.

- [x] **Step 4: Run final self-review and public-boundary scan**

Review the actual diff for active-only leakage, inconsistent Search/Ask projection, schema drift,
extra-field acceptance, transaction consistency, N+1 queries, path/credential/stderr disclosure,
private planning terms, artifact semantic drift, and unrelated dependency/version changes.

- [x] **Step 5: Update durable review evidence and commit**

Record actual commands/results and remaining risks. Keep authoritative scheme-window review pending.

```bash
git add docs/superpowers/plans/2026-07-11-versioned-evidence-provenance-contract-implementation.md \
  docs/superpowers/reviews/2026-07-11-versioned-evidence-provenance-contract-implementation-review.md
git commit -m "docs(mcp): record provenance contract verification"
git status --short --branch
```

Expected handoff: clean local branch, no upstream, no push/PR/tag/release/deploy.

## Test Coverage Map

```text
CODE PATHS                                           CONSUMER FLOWS
[ ] domain provenance validation                    [ ] fresh store -> empty
    +-- valid source fingerprint/revision                +-- strict list response
    +-- invalid fingerprint/revision [fail closed]       +-- no identifiers or paths
    +-- page locator                                 [ ] failed ingest -> no active Publication
    +-- timestamp locator                                +-- source exists, active counts zero
    +-- invalid locator [fail closed]                [ ] PDF publish -> Search -> Ask
[ ] SQLite active snapshot                              +-- same EvidenceRef projection
    +-- observation aggregate                            +-- page locator
    +-- FTS result + provenance join                  [ ] video publish -> Search -> Ask
    +-- CJK result + provenance join                     +-- timestamp locator
    +-- corrupt active state [fail closed]            [ ] same-store reingest
    +-- concurrent activation consistency                +-- stable source/fingerprint
[ ] application snapshot                                +-- changed run/publication/revision/evidence
    +-- evidence found                               [ ] fresh-store ingest
    +-- empty / no-active / active no-match              +-- stable fingerprint, opaque IDs may change
    +-- Ask insufficient_evidence                    [ ] malformed output or transport failure
[ ] strict MCP model                                    +-- consumer rejects and reports stable failure
    +-- success branch                               [ ] installed wheel, Python 3.12/3.13
    +-- public error branch                              +-- external cwd and hostile environment
    +-- outputSchema oneOf/const/no extras
    +-- unexpected exception redaction
```

Every branch above requires behavior, edge, and error-path coverage. The real stdio proof is the
integration test for the cross-layer flows; pure validators and state derivation remain unit tests.

## Failure Modes

| Failure | Required handling | Test |
|---|---|---|
| Run manifest fingerprint is missing or malformed | Fail closed as redacted internal error. | SQLite and MCP error tests. |
| Publication changes between observation and Search | One read transaction returns one snapshot. | Deterministic concurrency injection test. |
| FastMCP emits an open schema or wraps the union unexpectedly | Schema test rejects before consumer proof. | Tool-list schema regression. |
| v1 Search and Ask mapping drift | Shared converter plus exact projection equality test. | Application/MCP/proof tests. |
| Failed Run creates Source without Publication | Report `no_active_publication`, never expose candidate Evidence. | SQLite and real MCP proof. |
| Active Publication has zero Evidence | Integrity failure; do not report `active`. | Corruption regression. |
| Extra/unknown response fields or schema version | Consumer validation rejects. | Model and proof helper tests. |
| Unexpected exception contains path/credential/stderr | Response and proof emit allowlisted redacted error only. | Adversarial sanitization tests. |
| Evidence text itself contains user-authored sensitive content | Return it as selected Evidence; do not inject process/config secrets. Consumer DLP is outside this contract. | Mapping test separates Evidence text from system metadata. |
| Provenance joins add per-result queries | Reject N+1; bounded statement-count regression. | SQL trace test. |
| Artifact refresh changes evaluation semantics or corpus/qrel/query content | Stop before commit; only protocol-lock identity metadata may change. | Normalized Task 0 comparison. |

## NOT in Scope

- Consumer-specific business fields or freshness policy: consumer manifest responsibility.
- HTML crawler, OCR, HTTP, or UI: separate ingestion/interface features.
- LangChain/LangGraph or another orchestration layer: MKE remains an Agent-callable Evidence tool.
- Dense/hybrid/RRF/reranker/query-rewrite runtime: comparison evidence remains non-runtime.
- Replacing or versioning the five legacy tool outputs: current consumers retain their exact
  contracts; only additive v1 read tools are introduced.
- Redesigning E1–E3 source-identity scope: separate evaluation-governance change, not a prerequisite
  for this contract.
- Release/version/CHANGELOG/PyPI/tag/deployment work: no shipped release action in this task.

## What Already Exists

- SQLite already owns asset SHA-256, Source, Run manifest, Publication revision, Evidence, and
  active-Publication joins; the plan adds reads, not storage.
- `KnowledgeEngine.search()` and `ask()` already enforce active-only retrieval and refusal; the plan
  calls the unchanged retrieval path and bulk-enriches only the v1 MCP snapshot.
- `PublicError` already supplies allowlisted redaction vocabulary; strict MCP errors reuse it.
- `mcp_deployment_client` and the local-knowledge proof already drive real stdio MCP with the
  official SDK; the new proof extends consumer validation without changing their stable reports.
- Existing artifact refresh/validator chains already protect E1 through E3-E semantics; the plan
  uses that dependency closure.

## Parallelization

Sequential implementation, no parallelization opportunity. Domain, SQLite, application, MCP,
consumer proof, documentation, and artifact identities form one dependency chain and touch shared
contracts; parallel worktrees would create avoidable merge conflicts and contract drift.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|---|---|---|---:|---|---|
| CEO Review | `/plan-ceo-review` | Scope and strategy | 0 | Not required | Product direction was already approved and remained narrow. |
| Codex Review | outside voice | Independent plan challenge | 5 | CLEAN | 15 iterative P1/P2 findings surfaced; 13 folded, 2 explicitly rejected as scope expansion. |
| Eng Review | `/plan-eng-review` | Architecture and tests | 1 | CLEAN | 15 issues reviewed, 0 critical gaps, 0 unresolved. |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | Not required | No UI or visual interaction change. |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | Not required | MCP consumer proof and docs are covered by the engineering plan. |

**CODEX:** Final targeted re-review returned exactly `CLEAN` after compatibility, transaction,
integrity, schema-baseline, review-file, and artifact-closure amendments.

**VERDICT:** ENG + OUTSIDE VOICE CLEARED — ready for isolated local implementation.

NO UNRESOLVED DECISIONS
