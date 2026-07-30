# Diagnostic-First Deterministic Context Mechanism Separation v2 Implementation Plan

**Status:** Complete development comparison — the deterministic comparison rejected the candidate
under the frozen development protocol; holdout and runtime promotion remain `not_evaluated`.
Task 13 documentation and CI closeout is complete; independent actual-branch-diff review is
complete; publication remains pending.

> **For Codex:** Required implementation skill: use `superpowers:executing-plans` as the primary
> controller, `superpowers:test-driven-development` for every behavior change, and
> `superpowers:verification-before-completion` before each terminal handoff. Use
> `superpowers:systematic-debugging` only when a test, command, or observation behaves
> unexpectedly. Do not use another full execution controller in parallel.

**Goal:** Determine, without changing the product runtime, whether the current retrieval fallback
loses Agent-consumable context and whether any observed failure belongs to query policy, ranking,
Evidence granularity, delivery completeness, source context, or bounded adjacent-page assembly.

**Architecture:** Build a clean-main, evaluation-only v2 harness with strict direct-file authority,
typed substage diagnostics, label-blind observations, pure grading, and no-replace artifact
publication. Run one O0 current-runtime observation. Candidate modules are created only if O0
records the preregistered targeted failure. A successful development phase runs two fresh
workspaces inside one invocation, seals and compares O1/O2 portable observations before any label
access, opens the frozen grading payload exactly once in the workflow, derives residual gates,
dispatches label-blind residual candidates through typed gate decisions, seals and compares the
complete observations, and only then pure-grades and publishes one comparison-only artifact.
Holdout and runtime promotion remain outside this plan.

**Tech Stack:** Python 3.12/3.13, standard library, existing `KnowledgeEngine`, existing
`SQLiteStore` evaluation diagnostics, PyMuPDF already pinned by the repository, pytest, Ruff,
Pyright, `uv`, existing product/consumer proof commands.

**Approved design:**
`docs/superpowers/specs/2026-07-30-diagnostic-first-context-mechanism-separation-design.md`

**Planned public review record:**
`docs/superpowers/reviews/2026-07-30-diagnostic-first-context-mechanism-separation-plan-review.md`

---

## 1. Global Constraints

1. Start from the reviewed v2 spec branch based on current `main`. Do not merge or cherry-pick the
   discarded v1 prototype branch.
2. Preserve `Run`, `Publication`, `Evidence`, active-only retrieval, retrieval-order revision 2,
   cursor behavior, FTS/CJK route separation, exact-read recovery, and all existing public Python,
   CLI, MCP, installed-wheel, source-pack, and compiled-Library contracts.
3. Do not modify product retrieval, domain, application, adapter, CLI, or MCP behavior.
4. Evaluation code may call existing public application methods and existing evaluation
   diagnostics. It must not use `KnowledgeEngine._store`, `SQLiteStore._select_cjk_active_scan`, or
   another private runtime member.
5. Do not add a dependency, provider, model, cache requirement, OCR/ASR path, HTTP surface,
   GraphRAG, dense retrieval, RRF, reranker runtime, Agent loop, trace platform, or generic EvalOps
   framework.
6. Do not implement a holdout command, holdout recorder, holdout receipt, or holdout comparison
   artifact in this stage.
7. Do not change a scientific input, bound, mechanism parameter, residual gate, or verdict rule
   after the protocol is frozen.
8. Comparison results never change runtime configuration or set a promotion candidate.
   `runtime_promotion_status` is always `not_evaluated`.
9. No timing assertion or performance claim is verdict authority. Capacity must be checked before
   parsing or allocation, with exact-boundary and one-over tests.
10. Every public JSON object uses closed field sets, canonical JSON bytes, exact integer bounds,
    lowercase SHA-256, and stable machine tokens. Free-form exception text, local paths,
    credentials, environment values, opaque runtime IDs, and workspace IDs are forbidden.
11. The observer cannot access labels, qrels, required spans, expected locators, hypothesis
    strata, or verdict hints. The grader cannot call ingest, search, builders, observation,
    recorders, replay, or publication. Common metadata, observer inputs, and grading payloads use
    separate modules; the observer-side import graph cannot reach grading or holdout loaders.
12. O0 has one scientific invocation. Development has one scientific invocation. A started
    integrity failure closes v2 for this protocol. There is no attempt 2.
13. A preflight failure before observation start may be corrected only through a separately
    reviewed bounded recovery. It is not a scientific retry.
14. The public branch may contain candidate modules only after the retained O0 artifact records
    `baseline_red_observed`.
15. A complete v2 `evaluation_inconclusive` outcome is a valid falsification-first result. It does
    not become publishable mechanism evidence merely through documentation.

## 2. Result Branches

| O0 / development result | Authorized next work | Candidate code | Public artifact | Default lifecycle |
|---|---|---:|---:|---|
| Pre-observation preflight blocked | Bounded authority/environment correction | Unchanged | None | Resume only if scientific observation never started |
| O0 targeted failure absent | Docs/regression-only closeout | Absent | O0 baseline only | Reviewable |
| O0 targeted failure observed | Candidate implementation | Allowed | O0 baseline, then development if complete | Continue |
| O0 integrity/incomplete | Close v2 | Absent | None; external receipt/ledger only | No mechanism PR |
| Development scientific negative/mixed | Final comparison closeout | Present | Development | Reviewable |
| Development candidate qualified | Final comparison closeout | Present | Development | Reviewable; holdout separate |
| Development integrity/incomplete | Close v2 | Present locally | None; external receipt/ledger only | No mechanism-result PR |

The execution controller must select exactly one terminal branch. It must not run tasks from
multiple branches to manufacture a more attractive result.

## 3. Reuse And Reimplementation Matrix

| Capability | Live source | Decision | Required regression |
|---|---|---|---|
| Active retrieval and delivery | `KnowledgeEngine.search_evidence_page`, `KnowledgeEngine.read_active_evidence` | Reuse unchanged for O0 | Search/read call-spy and portable observation parity |
| Read-only Evidence and FTS diagnostics | `SQLiteStore.open_read_only_export`, `list_evaluation_evidence`, `list_fts_projection`, `observe_fts5_rank` | Reuse through existing evaluation methods | No private member access; FTS projection validation |
| CJK candidate scoring | `compile_cjk_overlap_terms`, `select_cjk_active_scan_candidates` | Reuse public pure scorer over evaluation snapshots; compare with actual runtime selection | Separate CJK parity and exact score/rank profile |
| Query compilation | `compile_fts5_query_diagnostic` | Reuse current frozen policy | Compiled query and route exactness |
| Direct file identity | `src/mke/evaluation/source_identity.py` | Extend with descriptor-bound, no-follow, mutation-detecting direct-file helpers | Symlink, alias, rename, mutation, exact boundary |
| Atomic JSON publication | `src/mke/evaluation/_atomic_json_publication.py` | Extend with descriptor-relative no-replace publication while preserving existing API | Absent/preexisting/race/durability/visible-invalid matrix |
| v1 scientific fixtures | Reviewed fixture bytes and values | Transplant only exact scientific inputs into v2; new schema and source inventory receive new identities | Canonical scientific projection equality |
| v1 segmentation ideas | Boundary discovery and byte-exact unit invariants | Reimplement after O0 RED; do not copy module wholesale | Unicode, gap-free, page-local, exact-boundary/one-over |
| v1 observation/grading/workflow | Historical test ideas only | Reject wholesale transplant | New small modules, stage-specific errors, strict Pyright |
| Historical retrieval artifacts | Checked-in artifacts and validators | Preserve bytes and interpretation | Historical/compatibility suite remains green |

## 4. File And Responsibility Map

### Common O0 files

Create:

- `src/mke/evaluation/agent_context_unit_protocol.py`
  - closed v2 protocol schemas;
  - metadata-only common DTOs;
  - frozen source-path inventories and profile validation;
  - no observer-case, label, verdict, or holdout payload loader.
- `src/mke/evaluation/agent_context_unit_observer_protocol.py`
  - label-blind development source-receipt and observer-case loader;
  - no labels, expected answers, verdicts, or holdout payload loader.
- `src/mke/evaluation/agent_context_unit_grading_protocol.py`
  - invoked only after the portable O0 observation seal;
  - baseline grading payload loader at O0;
  - development grading payload loader only after candidate authorization;
  - never imported by observation, baseline, diagnostics, segmentation, ranking, or assembly.
- `src/mke/evaluation/agent_context_unit_diagnostics.py`
  - 14-stage enum;
  - typed stage errors;
  - stage runner;
  - operator receipt builder, renderer, and pure validator.
- `src/mke/evaluation/agent_context_unit_observation.py`
  - label-blind authority and portable observation DTOs;
  - canonical sealing;
  - runtime-handle exclusion.
- `src/mke/evaluation/agent_context_unit_baseline.py`
  - O0 source ingestion;
  - public runtime Search/Read observation;
  - read-only FTS/CJK diagnostics and parity.
- `src/mke/evaluation/agent_context_unit_baseline_artifact.py`
  - pure O0 grading from sealed bytes plus frozen labels;
  - baseline artifact builder, renderer, and retained validator.
- `src/mke/evaluation/agent_context_unit_workflow.py`
  - thin `python -m` command parser;
  - preflight, stage orchestration, stable result, and publication;
  - lazy development dispatch only after candidate files exist.

Modify:

- `src/mke/evaluation/source_identity.py`
- `src/mke/evaluation/_atomic_json_publication.py`

Create focused tests:

- `tests/evaluation/test_agent_context_unit_protocol.py`
- `tests/evaluation/test_agent_context_unit_observer_protocol.py`
- `tests/evaluation/test_agent_context_unit_grading_protocol.py`
- `tests/evaluation/test_agent_context_unit_source_inventory.py`
- `tests/evaluation/test_agent_context_unit_diagnostics.py`
- `tests/evaluation/test_agent_context_unit_observation.py`
- `tests/evaluation/test_agent_context_unit_baseline.py`
- `tests/evaluation/test_agent_context_unit_baseline_artifact.py`
- `tests/evaluation/test_agent_context_unit_workflow.py`
- `tests/evaluation/test_source_identity.py` if absent, otherwise modify it
- `tests/evaluation/test_atomic_json_publication.py`

Create fixtures:

- `tests/fixtures/agent-context-unit-v2/README.md`
- `tests/fixtures/agent-context-unit-v2/protocol.json`
- `tests/fixtures/agent-context-unit-v2/scientific-input-lock.json`
- `tests/fixtures/agent-context-unit-v2/development/source-receipts.json`
- `tests/fixtures/agent-context-unit-v2/development/observer-cases.json`
- `tests/fixtures/agent-context-unit-v2/development/labels.json`
- `tests/fixtures/agent-context-unit-v2/development/synthetic-boundaries.pdf`
- `tests/fixtures/agent-context-unit-v2/holdout/source-receipts.json`
- `tests/fixtures/agent-context-unit-v2/holdout/observer-cases.json`
- `tests/fixtures/agent-context-unit-v2/holdout/labels.json`
- `tests/fixtures/agent-context-unit-v2/holdout/prc-data-security-law.pdf`
- `tests/fixtures/agent-context-unit-v2/holdout/usgs-national-field-manual-introduction.pdf`

Modify:

- `.gitattributes` to add
  `tests/fixtures/agent-context-unit-v2/**/*.pdf binary`.

Canonical O0 output:

- `benchmarks/retrieval/agent-context-unit-v2-baseline.json`

### Candidate-only files

Create only after O0 records `baseline_red_observed`:

- `src/mke/evaluation/agent_context_unit_segmentation.py`
- `src/mke/evaluation/agent_context_unit_ranking.py`
- `src/mke/evaluation/agent_context_unit_assembly.py`
- `src/mke/evaluation/agent_context_unit_grading.py`
- `src/mke/evaluation/agent_context_unit_artifact.py`

Create corresponding tests:

- `tests/evaluation/test_agent_context_unit_segmentation.py`
- `tests/evaluation/test_agent_context_unit_ranking.py`
- `tests/evaluation/test_agent_context_unit_assembly.py`
- `tests/evaluation/test_agent_context_unit_grading.py`
- `tests/evaluation/test_agent_context_unit_artifact.py`

Canonical development output:

- `benchmarks/retrieval/agent-context-unit-v2-development.json`

### Terminal documentation and CI

Create:

- `docs/how-to/run-agent-context-mechanism-comparison.md`

Modify:

- `docs/README.md`
- `.github/workflows/ci.yml`

Do not add an ADR unless implementation reveals a required runtime or long-lived architecture
change. Such a change is outside this plan and must stop implementation.

## 5. Direct Evaluator Source Inventories

The protocol records sorted unique repository-relative paths. Task 0 freezes these path lists;
record-time code fills byte counts and SHA-256 only for files that exist in the active branch.

### O0 direct evaluator inventory

```text
src/mke/evaluation/_atomic_json_publication.py
src/mke/evaluation/agent_context_unit_baseline.py
src/mke/evaluation/agent_context_unit_baseline_artifact.py
src/mke/evaluation/agent_context_unit_diagnostics.py
src/mke/evaluation/agent_context_unit_grading_protocol.py
src/mke/evaluation/agent_context_unit_observation.py
src/mke/evaluation/agent_context_unit_observer_protocol.py
src/mke/evaluation/agent_context_unit_protocol.py
src/mke/evaluation/agent_context_unit_workflow.py
src/mke/evaluation/diagnostic_ports.py
src/mke/evaluation/source_identity.py
```

The O0 runtime/profile seal additionally records the direct existing runtime files used by the
observation:

```text
src/mke/adapters/sqlite/__init__.py
src/mke/application/__init__.py
src/mke/application/evidence_access.py
src/mke/domain/library_export.py
src/mke/retrieval/cjk_active_scan.py
src/mke/retrieval/query_policy.py
src/mke/retrieval/strategy.py
```

These runtime files are not modified. They are direct input identity, not evaluator ownership.

### Development direct evaluator inventory

The development inventory is the O0 evaluator inventory plus:

```text
src/mke/evaluation/agent_context_unit_artifact.py
src/mke/evaluation/agent_context_unit_assembly.py
src/mke/evaluation/agent_context_unit_grading.py
src/mke/evaluation/agent_context_unit_ranking.py
src/mke/evaluation/agent_context_unit_segmentation.py
```

The implementation must fail before observation if an imported v2 evaluator module is absent from
the phase-appropriate inventory or an inventoried path is not imported by the phase. This prevents
an unrecorded helper from silently becoming scientific authority.

## 6. O0 Targeted-Failure Predicate

The frozen protocol, not the implementation, owns the candidate-target query set. It is the exact
set of observer cases that preregister at least one non-O0 contrast.

O0 records `baseline_red_observed` only when all of the following hold:

1. source ingestion, active Publication authority, route recording, provenance, exact-read, and
   deterministic observation integrity pass;
2. current-success, hard-negative, misleading-name, and exact-read controls pass their frozen
   guardrails;
3. at least one candidate-target query has a frozen required span or role that is not available in
   the top-5 delivered context under O0; and
4. the pure grader can place that miss in at least one diagnostic layer without using an observed
   cause supplied by the protocol.

Query-policy or candidate-eligibility misses remain visible classifications. They do not by
themselves claim that segmentation or contextual retrieval will help. They authorize the bounded
ablation only because O1/O2 and the residual gates can falsify that mechanism hypothesis.

If every candidate-target span and role is available under O0 and all controls pass, the result is
`docs_regression_only`. An integrity/control failure is never converted to a scientific RED.

## 7. Stable Diagnostic Contract

### Stage enum

```text
authority_preflight
runtime_baseline
source_snapshot
unit_projection
unit_rank
fixed_rank_delivery
residual_gate
adjacent_page_assembly
source_context_index
source_context_delivery
complete_observation_seal
grading
artifact_validation
publication
```

### Error type

```python
class AgentContextStageError(ValueError):
    substage: AgentContextSubstage
    error_code: str
    error_family: str
```

Component-specific subclasses may narrow construction, but the workflow catches only
`AgentContextStageError` plus an unexpected-exception boundary. Unexpected exceptions become:

```text
error_code=unexpected_stage_failure
error_family=unexpected
```

The active substage is retained.

### Public result mapping

| Substage/failure class | `problem` | `cause` | `next_step` |
|---|---|---|---|
| Pre-observation authority/path/profile | `agent_context_authority_preflight_failed` | stable component code | `correct_preflight_under_separate_authority` |
| Started O0/development substage 2–13 | `agent_context_observation_incomplete` | stable component code | `close_protocol_and_review_retained_receipt` |
| Receipt not complete-visible | `agent_context_diagnostic_receipt_unavailable` | `operator_receipt_not_complete_visible` | `repair_diagnostic_harness_before_new_protocol` |
| Publication absent after failure | `agent_context_publication_failed` | `candidate_was_not_made_visible` | `close_protocol_and_review_retained_receipt` |
| Publication visible but invalid/uncertain | `agent_context_publication_failed` | stable visible-state code | `retain_visible_bytes_and_do_not_retry` |
| Scientific negative or qualified outcome | `none` | `none` | `none` |

`first_failed_gate` is always the exact substage for integrity outcomes and `none` for scientific
outcomes.

### Receipt rules

The receipt is created only for a started integrity failure. It is published to the caller-owned
repository-external path with no replacement. A complete successful artifact has no receipt.

Receipt validation must be pure and must reject:

- unknown fields;
- absolute paths;
- private paths or home-directory fragments;
- query/source/label text;
- opaque runtime handles;
- unordered or duplicated stages;
- a completed stage after the failed stage;
- mismatched portable digests;
- invalid stderr count/digest pairs;
- tampered source or protocol seals;
- inconsistent output/publication states;
- a missing content digest.

## 8. Shared Gates

Tasks reference these gates rather than duplicating their bodies.

### Gate G0 — repository and authority preflight

```bash
git status --short --branch
git rev-parse HEAD
git rev-parse HEAD^{tree}
git diff --check
test -f AGENTS.md
test -f docs/superpowers/specs/2026-07-30-diagnostic-first-context-mechanism-separation-design.md
```

Verify:

- clean worktree and index;
- exact approved spec;
- no existing v2 canonical outputs;
- no holdout output path;
- historical retrieval artifact hashes unchanged;
- no imported discarded-prototype commit.

### Gate G1 — focused v2 tests

```bash
uv run pytest -q \
  tests/evaluation/test_agent_context_unit_protocol.py \
  tests/evaluation/test_agent_context_unit_observer_protocol.py \
  tests/evaluation/test_agent_context_unit_grading_protocol.py \
  tests/evaluation/test_agent_context_unit_source_inventory.py \
  tests/evaluation/test_agent_context_unit_diagnostics.py \
  tests/evaluation/test_agent_context_unit_observation.py \
  tests/evaluation/test_agent_context_unit_baseline.py \
  tests/evaluation/test_agent_context_unit_baseline_artifact.py \
  tests/evaluation/test_agent_context_unit_workflow.py
```

Add candidate test files to this command only on the O0-RED branch.

### Gate G2 — adjacent and historical evaluation

```bash
uv run pytest -q \
  tests/evaluation/test_source_identity.py \
  tests/evaluation/test_atomic_json_publication.py \
  tests/evaluation/test_baseline.py \
  tests/evaluation/test_retrieval_order_protocol.py \
  tests/evaluation/test_retrieval_order_artifact.py \
  tests/evaluation/test_retrieval_order_canonical_evidence.py \
  tests/evaluation/test_retrieval_order_compatibility.py \
  tests/evaluation/test_retrieval_order_historical_freeze.py \
  tests/evaluation/test_numeric_artifact.py \
  tests/evaluation/test_chinese_artifact.py \
  tests/evaluation/test_cjk_lexical_artifact.py \
  tests/evaluation/test_dense_artifact.py \
  tests/evaluation/test_hybrid_rrf_artifact.py \
  tests/evaluation/test_relevance_gate_artifact.py
```

If a named file has moved on current `main`, stop and reconcile this plan before execution. Do not
silently substitute a different gate.

### Gate G3 — static and full regression

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
```

### Gate G4 — product and consumer compatibility

```bash
uv run mke proof run
uv run mke demo --verify
```

Run the repository's existing installed-wheel, source-pack, MCP completeness, and compiled-Library
proof commands exactly as rendered by current committed workflow/tests. Do not copy stale commands
from an older plan. Record command identity and result in the retained execution ledger.

### Gate G5 — canonical-path guard

Before a scientific invocation, require `lexists == false` for:

```text
benchmarks/retrieval/agent-context-unit-v2-baseline.json
benchmarks/retrieval/agent-context-unit-v2-development.json
benchmarks/retrieval/agent-context-unit-v2-holdout-receipt.json
benchmarks/retrieval/agent-context-unit-v2-comparison.json
```

Require the caller-owned receipt path to be absent and all lexical parents to be regular,
non-symlink, exact-name, no-follow authority.

### Gate G6 — public-boundary scan

Scan changed public files for:

- private absolute paths;
- credentials or environment secrets;
- coordination identifiers;
- placeholders and unfinished markers;
- unverified quality/performance/promotion claims;
- opaque runtime IDs in canonical JSON.

### Gate G7 — final candidate identity

Record:

- HEAD and tree;
- exact changed paths;
- direct evaluator source seal;
- protocol and fixture identities;
- canonical artifact identities;
- full verification results;
- clean worktree and index;
- `git diff --check`;
- holdout output absence;
- `src/mke` non-evaluation diff absence.

## 9. Task 0 — Freeze The v2 Scientific Input And Selective-Transplant Inventory

**Files:**

- Create `src/mke/evaluation/agent_context_unit_protocol.py`.
- Create `src/mke/evaluation/agent_context_unit_observer_protocol.py`.
- Create all files under `tests/fixtures/agent-context-unit-v2/`.
- Create `tests/evaluation/test_agent_context_unit_protocol.py`.
- Create `tests/evaluation/test_agent_context_unit_observer_protocol.py`.
- Create `tests/evaluation/test_agent_context_unit_source_inventory.py`.
- Modify `.gitattributes`.

### Step 1: Record preflight and source identities

Run G0. Record the exact approved input bundle identities before writing.

The fixture import must include:

- seven development sources and eleven development queries;
- two sealed holdout sources and two holdout queries;
- the frozen 1,024/256/1,536/zero-overlap segmentation profile;
- all projection, delivery, context, candidate-pool, and byte bounds;
- all O0–O5 mechanism parameters;
- residual gates and verdict revision;
- the exact v1 scientific values, not v1 evaluator schemas.

The retained reviewed input bundle is a one-time Task 0 import source, not a live runtime or
historical-branch dependency. Before copying, generate a caller-owned import receipt containing the
exact source file identities and normalized scientific projection digest. Do not merge or import
prototype evaluator code.

Commit `scientific-input-lock.json` as the public, immutable normalized projection authority. It
contains only the frozen scientific values and source identities needed to prove equivalence; it
contains no evaluator schema, local path, branch identity, or incomplete observation.

### Step 2: Write targeted REDs

Tests must initially fail because v2 fixtures and protocol loaders do not exist. Required markers:

```text
V2_PROTOCOL_MISSING
V2_OBSERVER_PROTOCOL_MISSING
V2_SCIENTIFIC_PROJECTION_MISSING
V2_HOLDOUT_METADATA_BARRIER_MISSING
V2_SOURCE_INVENTORY_MISSING
```

The one-time import check compares the retained input bundle projection with
`scientific-input-lock.json`. The permanent regression compares the v2 protocol/fixture projection
with the lock while explicitly excluding schema version, v2 source inventories, and v2 diagnostic
fields. The public test therefore remains runnable from a clean clone without the discarded
prototype branch.

### Step 3: Run RED once

```bash
uv run pytest -q \
  tests/evaluation/test_agent_context_unit_protocol.py \
  tests/evaluation/test_agent_context_unit_observer_protocol.py \
  tests/evaluation/test_agent_context_unit_source_inventory.py
```

Require exact collection and only preregistered failures.

### Step 4: Land exact fixture bytes

- Copy PDF bytes exactly.
- Freeze JSON with canonical formatting.
- Add the v2 README with redistributable-source basis, byte counts, SHA-256, page counts, and
  scientific-equivalence statement.
- Add the O0 and development direct evaluator path inventories.
- Keep holdout metadata parseable while holdout payload loaders remain unimplemented.

### Step 5: Implement only the protocol needed for GREEN

Create `agent_context_unit_protocol.py` with:

- `load_agent_context_unit_protocol_metadata`;
- common closed typed DTOs, profiles, and source-path inventories;
- no-follow, repository-relative path validation;
- no observer-case, label, verdict, or holdout payload loader.

Create `agent_context_unit_observer_protocol.py` with:

- `load_agent_context_unit_observer_contract`;
- development source-receipt and observer-case DTOs only;
- a physical import barrier against
  `agent_context_unit_grading_protocol`;
- no labels, expected answers, verdicts, or holdout payload loader.

`agent_context_unit_grading_protocol.py` must remain absent until Task 4. A baseline grading loader
must not be declared in either common or observer protocol code.

Metadata loading may validate holdout receipt identities but cannot open holdout sources, observer
cases, or labels.

### Step 6: Run GREEN and static checks

```bash
uv run pytest -q \
  tests/evaluation/test_agent_context_unit_protocol.py \
  tests/evaluation/test_agent_context_unit_observer_protocol.py \
  tests/evaluation/test_agent_context_unit_source_inventory.py
uv run ruff check \
  src/mke/evaluation/agent_context_unit_protocol.py \
  src/mke/evaluation/agent_context_unit_observer_protocol.py \
  tests/evaluation/test_agent_context_unit_protocol.py \
  tests/evaluation/test_agent_context_unit_observer_protocol.py \
  tests/evaluation/test_agent_context_unit_source_inventory.py
uv run pyright
git diff --check
```

### Step 7: Commit

```bash
git add .gitattributes \
  src/mke/evaluation/agent_context_unit_protocol.py \
  src/mke/evaluation/agent_context_unit_observer_protocol.py \
  tests/evaluation/test_agent_context_unit_protocol.py \
  tests/evaluation/test_agent_context_unit_observer_protocol.py \
  tests/evaluation/test_agent_context_unit_source_inventory.py \
  tests/fixtures/agent-context-unit-v2
git commit -m "test(eval): freeze diagnostic context protocol"
```

## 10. Task 1 — Seal Direct Source And No-Replace Publication Authority

**Files:**

- Modify `src/mke/evaluation/source_identity.py`.
- Modify `src/mke/evaluation/_atomic_json_publication.py`.
- Create or modify `tests/evaluation/test_source_identity.py`.
- Modify `tests/evaluation/test_atomic_json_publication.py`.

### Step 1: Write targeted REDs

Source identity REDs:

- component-wise parent symlink;
- final symlink and nonregular file;
- two logical paths resolving to one inode;
- rename/replacement between preflight and read;
- size or metadata mutation during read;
- sorted unique path requirement;
- exact bytes/SHA-256;
- aggregate digest;
- empty and over-cap inventory rejected before any file content read.

Publication REDs:

- descriptor-relative parent and exact basename;
- destination absent/preexisting regular/symlink/nonregular;
- race winner;
- partial write/readback mismatch;
- validation failure before visibility;
- directory durability failure after visibility;
- invalid visible output;
- cleanup failure cannot erase visible authority;
- no replacement and no retry after visibility.

### Step 2: Run RED once

```bash
uv run pytest -q \
  tests/evaluation/test_source_identity.py \
  tests/evaluation/test_atomic_json_publication.py
```

### Step 3: Implement minimal generic primitives

Add project-generic helpers, keeping existing public functions and result fields compatible:

- descriptor-bound no-follow regular-file read;
- physical identity tuple captured before and after read;
- aggregate direct-file identity builder;
- descriptor-relative no-replace JSON publication;
- visible-state readback and canonical validation.

Do not add v2-specific tokens to the generic helper. The v2 workflow maps generic publication
results to v2 public result tokens.

### Step 4: Run focused and adjacent GREEN

```bash
uv run pytest -q \
  tests/evaluation/test_source_identity.py \
  tests/evaluation/test_atomic_json_publication.py \
  tests/evaluation/test_retrieval_order_compatibility.py \
  tests/evaluation/test_retrieval_order_workflow.py
uv run ruff check \
  src/mke/evaluation/source_identity.py \
  src/mke/evaluation/_atomic_json_publication.py \
  tests/evaluation/test_source_identity.py \
  tests/evaluation/test_atomic_json_publication.py
uv run pyright
git diff --check
```

### Step 5: Commit

```bash
git add \
  src/mke/evaluation/source_identity.py \
  src/mke/evaluation/_atomic_json_publication.py \
  tests/evaluation/test_source_identity.py \
  tests/evaluation/test_atomic_json_publication.py
git commit -m "fix(eval): seal direct evaluator authority"
```

## 11. Task 2 — Implement Typed Diagnostics And Pure Operator Receipts

**Files:**

- Create `src/mke/evaluation/agent_context_unit_diagnostics.py`.
- Create `tests/evaluation/test_agent_context_unit_diagnostics.py`.

### Step 1: Write the 14-stage fault matrix RED

Use synthetic stage callables. For each stage:

- all earlier stages complete in order;
- the active stage raises a typed error;
- all later callables remain uncalled;
- result retains exact `first_failed_gate`;
- receipt contains ordered completed stages and exact failed stage;
- artifact builder, grader, labels, holdout, and publication remain uncalled unless the failure is
  at their authorized stage.

Add same-exception-type tests proving base and extension failures remain distinguishable.

### Step 2: Add receipt authority REDs

Cover:

- closed field sets;
- canonical bytes and content digest;
- absent/preexisting/symlink/nonregular destination;
- no local path or payload leak;
- stderr count/digest only;
- tamper detection;
- unexpected exception normalization;
- receipt visibility required before normal failed-result return;
- complete successful path emits no receipt.

### Step 3: Run exact RED

```bash
uv run pytest -q tests/evaluation/test_agent_context_unit_diagnostics.py
```

### Step 4: Implement diagnostics

Implement:

- `AgentContextSubstage`;
- `AgentContextStageError`;
- immutable stage success records;
- `run_diagnostic_stage`;
- receipt builder and canonical renderer;
- `validate_agent_context_diagnostic_receipt`;
- stable mapping described in section 6.

All validators are pure. Use dependency injection for synthetic stage calls; do not implement a
general plugin system.

### Step 5: Run GREEN

```bash
uv run pytest -q \
  tests/evaluation/test_agent_context_unit_diagnostics.py \
  tests/evaluation/test_atomic_json_publication.py
uv run ruff check \
  src/mke/evaluation/agent_context_unit_diagnostics.py \
  tests/evaluation/test_agent_context_unit_diagnostics.py
uv run pyright
git diff --check
```

### Step 6: Commit

```bash
git add \
  src/mke/evaluation/agent_context_unit_diagnostics.py \
  tests/evaluation/test_agent_context_unit_diagnostics.py
git commit -m "feat(eval): expose diagnostic context stages"
```

## 12. Task 3 — Build Label-Blind O0 Observation

**Files:**

- Create `src/mke/evaluation/agent_context_unit_observation.py`.
- Create `src/mke/evaluation/agent_context_unit_baseline.py`.
- Create `tests/evaluation/test_agent_context_unit_observation.py`.
- Create `tests/evaluation/test_agent_context_unit_baseline.py`.

### Step 1: Write label-blind observation REDs

Require:

- observer contract contains query text, source receipt, expected route, and profile identity only;
- no label/qrel/span/expected-locator/hypothesis/verdict field;
- module import graph cannot import the grading loader or holdout loader;
- canonical portable observation excludes source ID, Publication ID, Run ID, Evidence ID, database
  path, workspace ID, and duration;
- authority observation may retain runtime handles for internal parity only;
- portable equality uses provenance-stable source fingerprint, locator, exact text digest, route,
  rank, arm-local score token, hints, excerpt, exact-read digest, and bounded byte accounting.

### Step 2: Write O0 route and parity REDs

Use the real current runtime over small synthetic fixtures:

- public `search_evidence_page` and `read_active_evidence` are called;
- an independent `SQLiteStore.open_read_only_export` validates active Evidence and FTS projection;
- FTS rank comes from `observe_fts5_rank`;
- CJK rank comes from public `select_cjk_active_scan_candidates` over
  `list_evaluation_evidence`;
- the public compiled-Library v2 snapshot supplies the source-ID-to-content-fingerprint map used to
  build stable CJK scorer candidates;
- actual selected stable locators equal the corresponding scorer projection;
- FTS and CJK score schemas remain separate;
- query policy miss, candidate miss, rank miss, delivery miss, output completeness, exact-read,
  and provenance are observable but not graded.

Add spies that fail on `KnowledgeEngine._store` or another private member access.

### Step 3: Add boundedness REDs

Test:

- max source/evidence/page/text/candidate/rank/result budgets;
- exact boundary passes;
- one-over fails before per-row text parsing or allocation;
- no N+1 Evidence reads;
- all selected exact reads use one bounded call per selected item;
- misleading filenames do not enter retrieval or delivery text.

### Step 4: Run RED once

```bash
uv run pytest -q \
  tests/evaluation/test_agent_context_unit_observation.py \
  tests/evaluation/test_agent_context_unit_baseline.py
```

### Step 5: Implement observation and O0

`agent_context_unit_observation.py` owns closed DTOs and canonical sealing only.

`agent_context_unit_baseline.py`:

1. receives the label-blind observer contract;
2. ingests frozen development sources into a caller-owned fresh workspace;
3. queries only the current public Search/Read methods;
4. opens the committed database read-only for evaluation diagnostics;
5. validates FTS/CJK parity;
6. returns authority and portable observations;
7. does not grade, publish, or know the canonical output path.

### Step 6: Run GREEN

```bash
uv run pytest -q \
  tests/evaluation/test_agent_context_unit_observation.py \
  tests/evaluation/test_agent_context_unit_baseline.py \
  tests/evaluation/test_agent_context_unit_protocol.py \
  tests/evaluation/test_agent_context_unit_observer_protocol.py \
  tests/evaluation/test_agent_context_unit_diagnostics.py
uv run ruff check \
  src/mke/evaluation/agent_context_unit_observation.py \
  src/mke/evaluation/agent_context_unit_baseline.py \
  tests/evaluation/test_agent_context_unit_observation.py \
  tests/evaluation/test_agent_context_unit_baseline.py
uv run pyright
git diff --check
```

### Step 7: Commit

```bash
git add \
  src/mke/evaluation/agent_context_unit_observation.py \
  src/mke/evaluation/agent_context_unit_baseline.py \
  tests/evaluation/test_agent_context_unit_observation.py \
  tests/evaluation/test_agent_context_unit_baseline.py
git commit -m "feat(eval): observe current context delivery"
```

## 13. Task 4 — Build Pure Baseline Grading, Artifact, And Thin Workflow

**Files:**

- Create `src/mke/evaluation/agent_context_unit_grading_protocol.py`.
- Create `src/mke/evaluation/agent_context_unit_baseline_artifact.py`.
- Create `src/mke/evaluation/agent_context_unit_workflow.py`.
- Create `tests/evaluation/test_agent_context_unit_grading_protocol.py`.
- Create `tests/evaluation/test_agent_context_unit_baseline_artifact.py`.
- Create `tests/evaluation/test_agent_context_unit_workflow.py`.

### Step 1: Write pure baseline artifact REDs

Require `agent_context_unit_grading_protocol.py` to:

- own `load_agent_context_unit_baseline_grading_payload`;
- open the baseline grading payload only when the O0 workflow calls it after the O0
  `complete_observation_seal`;
- reserve development grading-payload access for a later workflow call made exactly once after both
  fresh development workspaces have byte-identical O1/O2 intermediate portable seals; O3/O4/O5
  receive only typed gate decisions and label-blind frozen inputs;
- expose no holdout payload loader;
- reject label, expected-answer, verdict, or grading access through the common or observer
  protocol modules;
- remain physically absent from the import graph of observation, baseline, diagnostics,
  segmentation, ranking, and assembly.

Require the pure builder/validator to:

- receive sealed portable observation bytes;
- receive labels only through an explicit baseline grading payload passed after the O0
  `complete_observation_seal`;
- recompute required-span and role coverage;
- classify only `baseline_red_observed` or `docs_regression_only`;
- recompute the targeted-failure predicate from frozen spans and controls;
- bind protocol, O0 evaluator source, runtime/profile, fixture, and observation digests;
- set all candidate mechanisms `not_evaluated`;
- set holdout `not_evaluated`;
- set runtime promotion `not_evaluated`;
- exclude duration and opaque IDs;
- validate retained recorded authority without reading current evaluator files;
- offer a separate strict-live validator.

Add a replay barrier that fails if pure validation invokes source observation, ingest, Search,
Read, grading loaders, builders, recorders, or publication.

### Step 2: Write workflow REDs

Commands:

```text
diagnose
baseline
validate-baseline
validate-receipt
```

There is no `development` or `holdout` command yet.

Cover:

- exact public result fields;
- argparse exit 2;
- scientific result exit 0;
- integrity result exit 1;
- preflight happens before source open;
- observation start is first real development source open;
- one fresh workspace per O0;
- receipt only on started failure;
- artifact absent on integrity failure;
- no-replace canonical publication;
- manual stable result never includes receipt path;
- candidate module imports fail if attempted before O0 RED.

Add a physical import-graph regression that proves observation, baseline, and diagnostics cannot
import `agent_context_unit_grading_protocol`, directly or through
`agent_context_unit_protocol` / `agent_context_unit_observer_protocol`. Workflow is the only O0
orchestrator permitted to import the grading protocol, and it must do so only after the portable
observation seal.

### Step 3: Run RED

```bash
uv run pytest -q \
  tests/evaluation/test_agent_context_unit_grading_protocol.py \
  tests/evaluation/test_agent_context_unit_baseline_artifact.py \
  tests/evaluation/test_agent_context_unit_workflow.py
```

### Step 4: Implement pure artifact and workflow

The grading protocol is the sole label-loading authority. Its baseline loader returns immutable
grading DTOs and has no dependency on observation, baseline, diagnostics, or publication.

The workflow is orchestration only. It may:

- preflight direct source seals and output paths;
- call typed stages;
- open the baseline grading payload after the O0 portable observation seal;
- call the pure baseline artifact builder;
- publish canonical bytes;
- publish a failure receipt;
- render the stable result.

It may not implement retrieval, segmentation, scoring, delivery, grading rules, or artifact field
validation inline.

### Step 5: Controller self-test

Before any real source observation, run a synthetic subprocess matrix that proves:

- exact argv and exit code;
- bounded stdout/stderr;
- receipt visibility before exit 1;
- no artifact on every injected substage failure;
- success artifact publication to a temporary noncanonical path;
- pure validate does not observe;
- cwd, env, umask, and signal state are restored.

This is a provider-free harness test, not O0.

### Step 6: Run GREEN and shared gates

Run G1, then G2, Ruff, Pyright, and `git diff --check`.

### Step 7: Commit

```bash
git add \
  src/mke/evaluation/agent_context_unit_grading_protocol.py \
  src/mke/evaluation/agent_context_unit_baseline_artifact.py \
  src/mke/evaluation/agent_context_unit_workflow.py \
  tests/evaluation/test_agent_context_unit_grading_protocol.py \
  tests/evaluation/test_agent_context_unit_baseline_artifact.py \
  tests/evaluation/test_agent_context_unit_workflow.py
git commit -m "feat(eval): bind diagnostic context workflow"
```

## 14. Task 5 — Seal And Invoke O0 Exactly Once

This task has two authority parts. Pre-observation verification may run autonomously. Approval of
this complete plan authorizes the one O0 invocation after the independent review authority accepts
the exact candidate seal. No additional approval round is required unless the spec, scientific
input, command, acceptance gate, environment premise, or external-action scope changes.

### Step 1: Freeze the pre-O0 candidate

Run G0–G6, including:

- G1 and G2;
- full suite, Ruff, Pyright, build;
- product and consumer compatibility;
- synthetic 14-stage fault matrix;
- temporary noncanonical baseline record and pure validate;
- exact O0 direct evaluator and runtime source seals;
- canonical and receipt path absence.

Commit any required test/code repair before this seal. Then require clean HEAD and index.

### Step 2: Independent actual-diff review

Review the complete implementation range against:

- approved spec and this plan;
- source inventories;
- no private runtime access;
- no candidate code;
- observer label blindness;
- pure validator barriers;
- path/publication authority;
- stable result/receipt privacy;
- historical compatibility;
- one-shot semantics.

Any spec/plan/handoff/acceptance/environment defect returns to the plan authority and becomes a new
approved-input revision. It is not counted as an implementation failure.

### Step 3: Record final candidate seal

After review fixes and targeted re-review:

- rerun G1–G6;
- record exact HEAD/tree/status;
- record source/protocol/fixture identities;
- record canonical path absence;
- create a fresh caller-owned external process ledger whose lexical component chain is no-follow,
  whose physical directory is empty before use, and whose identity is retained for readback;
- run no command that can mutate or observe after the final seal.

### Step 4: Invoke O0 once

Exact command:

```bash
CALLER_OWNED_RECEIPT="$CALLER_OWNED_LEDGER_ROOT/o0-receipt.json"
uv run python -m mke.evaluation.agent_context_unit_workflow baseline \
  --protocol tests/fixtures/agent-context-unit-v2/protocol.json \
  --record benchmarks/retrieval/agent-context-unit-v2-baseline.json \
  --diagnostic-receipt "$CALLER_OWNED_RECEIPT" \
  --json
```

The controller records exact argv, start/end state, exit code, stdout/stderr byte counts and
digests, and canonical/receipt visibility. It must not retry.

### Step 5: Classify the terminal branch

Read stdout and visible files manually without calling production validators.

#### Branch A — `docs_regression_only`

- O0 exit 0;
- baseline artifact complete-visible and canonical;
- receipt absent;
- targeted failure absent;
- candidate modules absent.

Complete Step 6, then proceed only to Task 6A.

#### Branch B — `baseline_red_observed`

- O0 exit 0;
- baseline artifact complete-visible and canonical;
- receipt absent;
- targeted failure present.

Commit the exact baseline artifact, run pure retained validation, and proceed to Task 6B.

#### Branch C — `pre_observation_blocked`

- exit 1 before `runtime_baseline` starts;
- no baseline artifact and no started-failure receipt;
- controller ledger proves source observation did not start;
- candidate modules absent.

Stop for bounded root-cause attribution. A separately reviewed authority, gate, or environment
correction may resume the same protocol only when the retained ledger proves that no scientific
observation began. Reapproval is required only if a scientific input, acceptance gate, command,
environment premise, or external-action scope changes materially.

#### Branch D — `evaluation_inconclusive`

- O0 exit 1 or hard process failure;
- `runtime_baseline` or a later scientific substage started;
- no complete baseline artifact;
- complete receipt or process ledger retained externally;
- candidate modules absent;
- no retry.

Stop this plan. Do not create a mechanism-result PR.

### Step 6: Commit successful O0 artifact

For Branch A or B only:

```bash
git add benchmarks/retrieval/agent-context-unit-v2-baseline.json
git commit -m "test(eval): record current context baseline"
uv run python -m mke.evaluation.agent_context_unit_workflow validate-baseline \
  --protocol tests/fixtures/agent-context-unit-v2/protocol.json \
  --artifact benchmarks/retrieval/agent-context-unit-v2-baseline.json \
  --json
```

The validation command must not observe, rebuild, or publish.

## 15. Task 6A — Close The Docs/Regression-Only Branch

Run only when O0 recorded `docs_regression_only`.

**Files:**

- Create `docs/how-to/run-agent-context-mechanism-comparison.md`.
- Modify `docs/README.md`.
- Modify `.github/workflows/ci.yml`.
- Modify documentation tests or create
  `tests/evaluation/test_agent_context_unit_documentation.py`.
- Modify
  `docs/superpowers/plans/2026-07-30-diagnostic-first-context-mechanism-separation-implementation.md`
  to close the applicable checklist and status.

### Step 1: Write documentation and CI REDs

Require:

- current baseline failure not observed;
- no candidate implementation;
- exact baseline artifact identity;
- pure validation command;
- compiled-Library fast path versus retrieval fallback;
- exact-read recovery boundary;
- holdout not evaluated;
- no runtime promotion;
- no quality, performance, or generalization claim;
- CI cannot record O0/development/holdout.

### Step 2: Implement bounded docs and CI

CI adds:

- fixture/protocol identity tests;
- synthetic diagnostics;
- pure baseline validation;
- canonical path state guard;
- no candidate artifact expectation.

It does not run a recorder.

### Step 3: Verify and commit

Run G1–G7, documentation tests, and the exact committed CI block locally.

```bash
git add \
  .github/workflows/ci.yml \
  docs/README.md \
  docs/how-to/run-agent-context-mechanism-comparison.md \
  tests/evaluation/test_agent_context_unit_documentation.py \
  docs/superpowers/plans/2026-07-30-diagnostic-first-context-mechanism-separation-implementation.md
git commit -m "docs(retrieval): record context baseline negative"
```

Stop. Tasks 6B–13 are not applicable.

## 16. Task 6B — Implement Deterministic Page-Local Segmentation

Run only when the retained O0 artifact records `baseline_red_observed`.

**Files:**

- Create `src/mke/evaluation/agent_context_unit_segmentation.py`.
- Create `tests/evaluation/test_agent_context_unit_segmentation.py`.

### Step 1: Write segmentation REDs

Cover:

- 1,024 target, 256 minimum except final, 1,536 maximum, zero overlap;
- heading, paragraph, sentence, hard-split, final-merge precedence;
- Unicode/NFKC discovery without authoritative byte rewrite;
- combining marks, emoji, CRLF, CJK punctuation, long unbroken text;
- exact parent-byte concatenation;
- ordered, gap-free, non-overlapping page-local units;
- stable projection ID independent of opaque runtime IDs;
- Publication/Evidence/source provenance;
- exact-boundary pass and one-over failure before allocation;
- no cross-page unit.

### Step 2: Run RED, implement, run GREEN

```bash
uv run pytest -q tests/evaluation/test_agent_context_unit_segmentation.py
uv run ruff check \
  src/mke/evaluation/agent_context_unit_segmentation.py \
  tests/evaluation/test_agent_context_unit_segmentation.py
uv run pyright
git diff --check
```

### Step 3: Commit

```bash
git add \
  src/mke/evaluation/agent_context_unit_segmentation.py \
  tests/evaluation/test_agent_context_unit_segmentation.py
git commit -m "feat(eval): segment exact page context units"
```

## 17. Task 7 — Implement O1 Unit Ranking

**Files:**

- Create `src/mke/evaluation/agent_context_unit_ranking.py`.
- Create `tests/evaluation/test_agent_context_unit_ranking.py`.

### Step 1: Write O1 REDs

Cover:

- projection rows use exact unit bytes and stable provenance;
- capacity count/bytes checked before encoding or per-row parsing;
- FTS and CJK ranking families remain separate;
- FTS score is canonical finite `float.hex()`;
- CJK score records exact overlap count/ratio and matched terms;
- stable tie key never uses opaque Evidence ID or workspace order;
- top 10 diagnostic and top 5 primary;
- max candidate pool 1,000;
- parent-collapsed rank and unique parent counts;
- candidate expansion;
- no labels or filename text;
- arm-local score comparison only;
- fresh workspace portable equality.

### Step 2: Implement O1 only

Use a temporary evaluation projection owned by the evaluation workspace. Do not modify the product
SQLite schema or product retrieval path.

The module exposes pure projection-row construction and route-specific rank functions. It does not
deliver content, derive residual gates, grade, or publish.

### Step 3: Verify and commit

```bash
uv run pytest -q \
  tests/evaluation/test_agent_context_unit_ranking.py \
  tests/evaluation/test_agent_context_unit_segmentation.py
uv run ruff check \
  src/mke/evaluation/agent_context_unit_ranking.py \
  tests/evaluation/test_agent_context_unit_ranking.py
uv run pyright
git diff --check
git add \
  src/mke/evaluation/agent_context_unit_ranking.py \
  tests/evaluation/test_agent_context_unit_ranking.py
git commit -m "feat(eval): rank deterministic context units"
```

## 18. Task 8 — Implement O2, O4, And O5 Delivery/Assembly

**Files:**

- Create `src/mke/evaluation/agent_context_unit_assembly.py`.
- Create `tests/evaluation/test_agent_context_unit_assembly.py`.

O3 indexing remains in Task 9 because its source-context projection and attribution share the
residual-gate grading boundary. This task owns delivery only.

### Step 1: Write fixed-selection REDs

For O2/O4/O5:

- selected stable identities are input and cannot change;
- no rerank, label selection, or qrel access;
- provenance remains exact;
- output bytes and useful-span density are observable;
- canonical content/item/envelope budgets are enforced;
- separator bytes count;
- exact requested/returned/omitted/truncated accounting;
- no duplicate context bytes.

### Step 2: Write O2 REDs

- complete authoritative unit text delivered;
- unit text never truncated;
- item budget enforced before render;
- selection digest unchanged.

### Step 3: Write O4 REDs

- 512-byte source-context cap;
- allocation order heading, previous unit, next unit;
- context component origin and byte range;
- context-only match attribution;
- filename/display name excluded;
- missing/ambiguous/inactive context explicit.

### Step 4: Write O5 REDs

- previous tail and next head each at most 256 bytes;
- same source, active Publication, exact adjacent page only;
- no cross-source or inactive page;
- fixed selected excerpt authority;
- frozen excerpt reduction rule;
- explicit no-context record.

### Step 5: Implement, verify, commit

```bash
uv run pytest -q \
  tests/evaluation/test_agent_context_unit_assembly.py \
  tests/evaluation/test_agent_context_unit_segmentation.py \
  tests/evaluation/test_agent_context_unit_ranking.py
uv run ruff check \
  src/mke/evaluation/agent_context_unit_assembly.py \
  tests/evaluation/test_agent_context_unit_assembly.py
uv run pyright
git diff --check
git add \
  src/mke/evaluation/agent_context_unit_assembly.py \
  tests/evaluation/test_agent_context_unit_assembly.py
git commit -m "feat(eval): assemble fixed context delivery"
```

## 19. Task 9 — Implement O3, Residual Gates, Pure Grading, And Development Artifact

**Files:**

- Create `src/mke/evaluation/agent_context_unit_grading.py`.
- Create `src/mke/evaluation/agent_context_unit_artifact.py`.
- Create `tests/evaluation/test_agent_context_unit_grading.py`.
- Create `tests/evaluation/test_agent_context_unit_artifact.py`.
- Extend `src/mke/evaluation/agent_context_unit_ranking.py`.
- Extend `tests/evaluation/test_agent_context_unit_ranking.py`.
- Extend `src/mke/evaluation/agent_context_unit_grading_protocol.py`.
- Extend `tests/evaluation/test_agent_context_unit_grading_protocol.py`.

### Step 1: Write residual-gate REDs

From sealed O0/O1/O2 bytes plus the frozen development grading payload opened by the workflow only
after the O1/O2 intermediate seal:

- O3 runs only for residual indexing/ranking failure;
- O4 runs only for residual delivery failure;
- O5 runs only for preregistered cross-page cases;
- gate schema, inputs, reason, and digest are closed;
- a false gate makes the mechanism `not_evaluated`;
- dispatch cannot accept a forged gate;
- no label or expected answer reaches candidate ranking or selection.

### Step 2: Write O3 REDs

- O3 reuses exact O1 units;
- frozen source-context treatment only;
- every O1 unit is an independent O3 retrieval document, so the same provenance-bound heading or
  neighboring unit may be reused across documents;
- duplicate kinds, ranges, or payloads remain invalid within one O3 document, while O4/O5 retain
  their existing cross-selected-output delivery deduplication;
- unit origin and context origin separate;
- context-only component attribution exact;
- unit text delivered unchanged;
- FTS/CJK route separation;
- no filename/display-name text;
- 512-byte context bound and global projection bounds;
- selected origin Evidence remains recoverable.

Dependency direction remains one-way: workflow asks assembly for frozen source-context components,
then passes those immutable components to the ranking projection. Ranking never imports assembly,
and neither module imports grading.

### Step 3: Write pure grading REDs

Require the grader to recompute:

- token presence;
- selection recall;
- delivery recall;
- output completeness;
- provenance exactness;
- deterministic equality;
- required-span/role coverage;
- rank 1/3/5/10;
- parent-collapsed rank;
- candidate expansion;
- useful-span density;
- context-only matches and component attribution;
- hard negatives and current-success controls;
- all scientific classifications and mechanism statuses.

The grader must reject:

- cross-arm raw score comparison;
- missing or duplicate cases;
- forged classifications;
- selected-identity drift;
- portable digest drift;
- guardrail regression;
- ambiguous attribution presented as qualified;
- any call to observation, ingest, search, builders, recorder, replay, publication, or holdout.

Extend only `agent_context_unit_grading_protocol.py` with the development grading payload loader
after candidate authorization. Keep `agent_context_unit_protocol.py` and
`agent_context_unit_observer_protocol.py` frozen and label-blind.

### Step 4: Write development artifact REDs

The artifact binds:

- protocol and direct candidate source seals;
- O0 baseline artifact identity;
- two fresh portable observations and equality;
- sealed base and complete observations;
- residual gates;
- metrics/classifications;
- mechanism status and selection policy;
- limitations and non-claims;
- `holdout_status=not_evaluated`;
- `runtime_promotion_status=not_evaluated`.

Retained validation uses recorded authority. Strict-live validation is separate.

### Step 5: Implement, verify, commit

```bash
uv run pytest -q \
  tests/evaluation/test_agent_context_unit_grading_protocol.py \
  tests/evaluation/test_agent_context_unit_ranking.py \
  tests/evaluation/test_agent_context_unit_grading.py \
  tests/evaluation/test_agent_context_unit_artifact.py
uv run ruff check \
  src/mke/evaluation/agent_context_unit_grading_protocol.py \
  src/mke/evaluation/agent_context_unit_ranking.py \
  src/mke/evaluation/agent_context_unit_grading.py \
  src/mke/evaluation/agent_context_unit_artifact.py \
  tests/evaluation/test_agent_context_unit_grading_protocol.py \
  tests/evaluation/test_agent_context_unit_ranking.py \
  tests/evaluation/test_agent_context_unit_grading.py \
  tests/evaluation/test_agent_context_unit_artifact.py
uv run pyright
git diff --check
git add \
  src/mke/evaluation/agent_context_unit_grading_protocol.py \
  src/mke/evaluation/agent_context_unit_ranking.py \
  src/mke/evaluation/agent_context_unit_grading.py \
  src/mke/evaluation/agent_context_unit_artifact.py \
  tests/evaluation/test_agent_context_unit_grading_protocol.py \
  tests/evaluation/test_agent_context_unit_ranking.py \
  tests/evaluation/test_agent_context_unit_grading.py \
  tests/evaluation/test_agent_context_unit_artifact.py
git commit -m "feat(eval): grade context mechanism contrasts"
```

## 20. Task 10 — Add The One-Shot Development Workflow

**Files:**

- Modify `src/mke/evaluation/agent_context_unit_workflow.py`.
- Modify `tests/evaluation/test_agent_context_unit_workflow.py`.
- Modify `src/mke/evaluation/agent_context_unit_baseline_artifact.py` only if a retained O0
  validator needs an additive public helper; do not change O0 artifact semantics.

### Step 1: Write development workflow REDs

Add commands:

```text
development
validate-development
```

There is still no holdout command.

Cover:

- retained baseline must be complete and `baseline_red_observed`;
- direct candidate source preflight;
- canonical output/receipt absence;
- observation starts at first candidate workspace ingestion;
- exactly two fresh workspaces inside one process invocation;
- workspace A/B authority handles may differ;
- both workspaces complete O1/O2 and form byte-identical intermediate portable seals before any
  development label access; this internal seal adds no public substage token;
- the workflow opens the frozen development grading payload exactly once at `residual_gate`, only
  after O1/O2 intermediate equality;
- residual gates derive only from that frozen payload plus sealed O0/O1/O2 observations;
- typed gate dispatch is validated and `residual_gate` completes before any O3/O4/O5 candidate
  entry; label-load, derivation, and injected gate failures retain
  `first_failed_gate=residual_gate`;
- O3/O4/O5 receive only typed gate decisions, the label-blind observer contract, and existing
  frozen candidate inputs; they cannot receive the grading payload, required spans, labels, qrels,
  expected locators, or hypothesis and verdict hints;
- O3/O4/O5 dispatch only through the same frozen gate set in both workspaces;
- `complete_observation_seal` occurs only after every dispatched residual mechanism completes, and
  complete workspace A/B portable observation bytes must be byte-identical;
- the pure grader and artifact validator run only after `complete_observation_seal`;
- success publishes artifact and no receipt;
- started failure publishes receipt and no artifact;
- scientific outcomes exit 0;
- integrity outcomes exit 1;
- no retry or attempt counter.

### Step 2: Add stage-specific integration faults

Inject real-shaped failures at every candidate stage and prove exact diagnosis. Include the
historical failure classes:

- capacity preallocation exceeded before parse/allocation;
- candidate observation integrity failure;
- workspace portable mismatch;
- source-context attribution mismatch;
- output/publication visible-state failure.

Each must map to a distinct substage/code, not a shared generic candidate-invalid result.

### Step 3: Implement thin orchestration

The workflow imports candidate modules only inside the `development` and `validate-development`
paths after the baseline artifact has authorized Phase C.

The workflow does not contain segmentation, ranking, assembly, residual-gate, grading, or artifact
rules.

### Step 4: Controller self-test

Use noncanonical temporary outputs and synthetic source fixtures. Prove exact process behavior and
environment restoration before any real development observation.

### Step 5: Verify and commit

Run all candidate-focused tests, G2, Ruff, Pyright, and `git diff --check`.

```bash
git add \
  src/mke/evaluation/agent_context_unit_workflow.py \
  tests/evaluation/test_agent_context_unit_workflow.py
git commit -m "feat(eval): orchestrate one-shot context comparison"
```

## 21. Task 11 — Seal The Development Candidate

### Step 1: Run complete pre-observation verification

Run:

- all v2 focused tests;
- exact 14-stage fault matrix;
- all historical artifact and compatibility tests;
- runtime/interface/schema/consumer tests;
- full suite;
- Ruff;
- Pyright;
- build;
- product proof and demo;
- existing installed/source-pack/MCP/compiled-Library proofs;
- temporary noncanonical development record and pure validate using synthetic inputs only;
- candidate source/protocol seal readback;
- canonical and receipt path absence;
- holdout loader/open barriers;
- public scan.

### Step 2: Independent actual-diff review

Review the complete post-O0 candidate range. Required risk surfaces:

- candidate modules exist only because O0 retained RED;
- exact profile and bounds;
- capacity before parsing/allocation;
- FTS/CJK route and score separation;
- fixed-selection delivery;
- O3/O4 residual-gate authority;
- O5 page adjacency;
- label-blind observations;
- O1/O2 intermediate seal and byte equality before label access;
- exactly one workflow-owned development grading-payload open;
- typed gate-only dataflow into residual candidate modules;
- candidate import and label/grading-access barriers;
- complete observation seal after all dispatched residual observations;
- pure grading/validation;
- two-workspace equality;
- no holdout command/import/open;
- no runtime/public contract/dependency change.

### Step 3: Apply bounded review fixes

Each finding must first be verified. Add a focused RED before code repair. After each repair batch,
run targeted GREEN and the affected adjacent matrix. Then perform targeted re-review.

If the finding exposes a spec/plan/handoff/acceptance/environment defect, stop for plan-authority
revision and reapproval when substantive. Do not compensate for unstable authority by changing
implementation tactics.

### Step 4: Freeze final candidate

Run G1–G7 and record exact clean HEAD/tree/source seals. No test, formatter, validator, generator,
or proof runs after this seal and before Task 12.

## 22. Task 12 — Invoke Development Exactly Once

Approval of this complete plan authorizes the one development invocation only on the O0-RED
branch, after the independent review authority accepts the exact Task 11 seal. No additional
approval round is required unless an approved input, residual gate, command, environment premise,
or external-action scope changes.

### Step 1: Invoke once

```bash
CALLER_OWNED_RECEIPT="$CALLER_OWNED_LEDGER_ROOT/development-receipt.json"
uv run python -m mke.evaluation.agent_context_unit_workflow development \
  --protocol tests/fixtures/agent-context-unit-v2/protocol.json \
  --baseline benchmarks/retrieval/agent-context-unit-v2-baseline.json \
  --record benchmarks/retrieval/agent-context-unit-v2-development.json \
  --diagnostic-receipt "$CALLER_OWNED_RECEIPT" \
  --json
```

Record exact process and visibility state. Do not retry.

### Step 2: Manual readback

Without calling a production validator, inspect:

- process exit;
- stable public result field set;
- artifact/receipt visibility;
- source/protocol seal identity;
- workspace equality digest;
- mechanism statuses;
- holdout `not_evaluated`;
- runtime promotion `not_evaluated`.

### Step 3: Terminal classification

#### Complete scientific result

- exit 0;
- development artifact complete-visible;
- receipt absent;
- valid scientific outcome token.

Commit the artifact:

```bash
git add benchmarks/retrieval/agent-context-unit-v2-development.json
git commit -m "test(eval): record context mechanism comparison"
```

Then pure-validate:

```bash
uv run python -m mke.evaluation.agent_context_unit_workflow validate-development \
  --protocol tests/fixtures/agent-context-unit-v2/protocol.json \
  --baseline benchmarks/retrieval/agent-context-unit-v2-baseline.json \
  --artifact benchmarks/retrieval/agent-context-unit-v2-development.json \
  --json
```

#### Pre-observation blocked

- exit 1 before the first candidate workspace ingestion;
- no complete development artifact and no started-failure receipt;
- process ledger proves observation did not start.

Stop for bounded root-cause attribution. Resume is allowed only through separately reviewed
authority, gate, or environment correction under the unchanged protocol and exact candidate seal.
Reapproval is required only when an approved input, residual gate, command, environment premise,
or external-action scope changes materially.

#### Evaluation inconclusive

- exit 1 or hard process failure;
- first candidate workspace ingestion or a later scientific substage started;
- no complete development artifact;
- receipt or process ledger retained externally;
- no retry;
- no mechanism-result PR by default.

Stop before Task 13 unless the plan authority separately authorizes a
diagnostic-maintenance-only closeout.

## 23. Task 13 — Close Documentation, CI, And Final Review

Run only for a complete development artifact. The O0 docs-only branch is closed by Task 6A and
must not enter this task.

Task 13 implementation status: complete; independent actual-branch-diff review complete;
publication pending.

- [x] Document the exact development result and non-claims
- [x] Add pure, model-free CI validation and canonical absence guards
- [x] Run final verification and the exact committed CI block locally
- [x] Commit the five-path documentation and CI closeout

**Files:**

- Create `docs/how-to/run-agent-context-mechanism-comparison.md`.
- Create `tests/evaluation/test_agent_context_unit_documentation.py`.
- Modify `docs/README.md`.
- Modify `.github/workflows/ci.yml`.
- Update plan checkboxes and status.

### Step 1: Write documentation RED

Require exact statements for:

- MKE as local-first Agent-callable Evidence/Context compiler;
- compiled-Library fast path;
- retrieval fallback;
- exact-read recovery;
- O0–O5 ablation meanings;
- exact protocol and source identity;
- diagnostic receipt/privacy;
- observed terminal result;
- artifact identities;
- holdout not evaluated;
- runtime promotion not evaluated;
- constructed-corpus/public-nonblind limitations;
- no quality/performance/generalization claim.

### Step 2: Add pure CI validation

CI may:

- validate protocol/fixtures;
- run synthetic diagnostics;
- run model-free mechanism unit tests;
- pure-validate checked baseline/development artifacts that exist;
- assert absent non-authorized holdout paths;
- preserve historical compatibility;
- run supported Python and existing consumer proofs.

CI must not record O0, development, or holdout.

### Step 3: Run final verification

Run G1–G7 on the final artifact-bearing HEAD. Also run:

```bash
uv run pytest -q tests/evaluation/test_agent_context_unit_documentation.py
```

Execute the exact committed CI block locally. Confirm no non-evaluation `src/mke` diff.

### Step 4: Final authority review

The independent review authority reviews:

- actual branch diff;
- spec and plan conformance;
- protocol/artifact bytes;
- one-shot process ledger;
- test and proof evidence;
- public docs and claims;
- holdout and promotion absence.

Fix verified findings through focused TDD, rerun the affected gates, then targeted re-review.

### Step 5: Commit

```bash
git add \
  .github/workflows/ci.yml \
  docs/README.md \
  docs/how-to/run-agent-context-mechanism-comparison.md \
  tests/evaluation/test_agent_context_unit_documentation.py \
  docs/superpowers/plans/2026-07-30-diagnostic-first-context-mechanism-separation-implementation.md
git commit -m "docs(retrieval): close context mechanism comparison"
```

Push, PR, merge, release, cleanup, holdout, and runtime promotion remain separately authorized.

## 24. Review And Repair Policy

1. Each code task gets one task-scoped actual-diff review when its risk warrants it; ordinary
   low-risk tasks use execution self-review plus focused verification.
2. The complete pre-O0 and pre-development candidates each receive one independent full-diff
   review.
3. Verified findings receive the smallest TDD repair and targeted re-review.
4. The design repair budget remains the spec authority: original plus at most two evidence-backed
   bounded repair rounds for one stable terminal gate.
5. Repair count never replaces root-cause attribution.
6. The plan/review authority first attributes a failure to:
   - spec/plan/handoff;
   - acceptance/test/gate;
   - environment/packaging/process state; or
   - execution against stable approved inputs.
7. Authority or environment defects are corrected by their owner under a new bounded task.
   Failures under different authority revisions do not accumulate.
8. Implementation repair proceeds only after inputs, gates, and environment premises are stable.
9. A scientific started failure receives no repair. It closes the protocol.
10. No v3 follows an inconclusive v2 under this direction.

## 25. Parallelism And Ownership

This plan is dependency-heavy and defaults to serial execution.

Potential read-only parallel lanes are limited to:

- historical artifact/hash verification;
- documentation/public-boundary review;
- independent test-log analysis.

Do not parallelize writes to protocol, workflow, diagnostics, artifacts, or fixtures. They share
authority contracts and one-shot semantics. The primary execution controller owns integration,
full verification, and the terminal report.

## 26. Expected Public Claims

Before an observed result, the repository may claim only:

- a diagnostic-first comparison is implemented;
- the protocol separates query policy, ranking, granularity, delivery, source context, and
  adjacent-page assembly;
- the harness is provider-free, bounded, and deterministic under its frozen profile;
- runtime and public contracts are unchanged.

After a complete O0 or development artifact, documentation may report only the exact observed
classification and mechanism statuses.

It must not claim:

- production retrieval improvement;
- generalized RAG quality;
- lower latency, cost, or storage;
- enterprise/user adoption;
- statistical significance;
- holdout success;
- runtime promotion;
- a generic Agent memory platform.

## 27. Completion Definition

The plan completes in exactly one of three states:

1. `docs_regression_only` with a retained O0 artifact and no candidate code;
2. complete development comparison with retained O0/development artifacts and no holdout or
   promotion; or
3. `evaluation_inconclusive` with no comparison artifact, a retained external receipt/process
   ledger, and no retry.

Any other state is incomplete.

## 28. Amendment E — Residual-Gate Diagnostics And O3 Context Reuse

This amendment closes two Task 10 pre-observation authority mismatches without changing the
scientific protocol.

The stable public substage vocabulary remains 14 tokens, but `residual_gate` now follows
`fixed_rank_delivery` and precedes all O3/O4/O5 mechanism stages. After byte-identical O1/O2
intermediate seals, the workflow opens the development grading payload once, derives and validates
one typed gate set, completes `residual_gate`, and only then enters residual candidate modules.
Gate-load, gate-derivation, and injected gate failures stop before candidate side effects and are
reported at `residual_gate`; later mechanism failures retain their own exact stage.

O3 builds an independent retrieval document for each exact O1 unit. Source-derived context is
validated per document, so the same provenance range may be reused by different unit documents
without row-order-dependent ambiguity. Duplicate context kinds, ranges, or payloads within one O3
document remain invalid. O4/O5 delivery continues to enforce its existing cross-selected-output
deduplication and no-duplicate delivery contract.

The amendment authorizes only the corresponding design, plan, review, diagnostics, workflow, and
focused-test repair. It changes no protocol or scientific-input bytes, mechanism parameters,
context order, residual or verdict rules, artifact schema, runtime product path, dependency,
holdout boundary, or observation count. O0 remains retained and development remains uninvoked.
