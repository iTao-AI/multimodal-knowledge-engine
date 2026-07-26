# Deterministic Retrieval Order Maintenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this
> plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make FTS5 and CJK equal-score Evidence order deterministic across fresh stores while
preserving scores, candidate membership, non-tied order, active-Publication authority, public
schemas, and historical observation bytes.

**Architecture:** Keep each scorer's relevance order and replace only opaque-ID tie semantics with
path-specific stable source/locator keys. Reject duplicate stable locator projections before new
Publication and at affected read paths, map one typed authority failure through current Python,
CLI, and MCP contracts, and prove the change through a frozen `retrieval-order-v1` mechanism
protocol plus a separate revision-2 historical compatibility record.

**Tech Stack:** Python 3.12/3.13, SQLite/FTS5, Pydantic 2.13.4, MCP Python SDK/FastMCP 1.28.1,
pytest, Ruff, Pyright, uv, GitHub Actions.

## Global Constraints

- Planning baseline is `main@eea3d51c36c0b3b845b8efb60eff553ddc200b88`.
- Reviewed spec commit is `04bbc24562d24e3666472b38ed39c59db2f5acf2` on
  `codex/deterministic-retrieval-order-spec`.
- Relevance score remains the primary order; stable keys resolve equal-score groups only.
- FTS order is exactly
  `rank, locator_start, locator_kind, locator_end, assets.sha256`.
- CJK order is exactly
  `-overlap_count, -overlap_ratio, content_fingerprint, locator_kind, locator_start, locator_end`.
- Opaque `source_id` and `evidence_id` remain addresses and never rank results.
- Public strategy IDs, query-policy revision 1, CLI/MCP request schemas, MCP tool inventory, and
  response field sets remain unchanged.
- Runtime descriptor revisions for `current`, `numeric-grouping-v1`, and
  `cjk-active-scan-overlap-v1` become 2; `CJK_ACTIVE_SCAN_PARAMETERS.revision` becomes 2.
- Search cursors from revision 1 expire; consumers discard the full partial traversal and repeat
  the initial query. Read cursors survive a same-owner strategy-only change. Owner restart expires
  both cursor kinds.
- Historical observation JSON bytes and SHA-256 values are immutable.
- Development and holdout are public, nonblind, mechanism-only fixtures. After first publication,
  both are development material.
- Holdout is executed once, only after a clean candidate commit, a passing development freeze, and
  a frozen runtime profile.
- No GraphRAG, dense/RRF/reranker runtime, segmentation, contextual retrieval, OCR, Agent loop,
  HTTP/SaaS, provider, model, dependency, schema migration, or deterministic domain ID.
- No push, PR, merge, tag, release, deployment, promotion, or worktree cleanup without later
  explicit authorization.
- Do not access or modify any unrelated retained retrieval-coverage worktree or dirty evidence.

---

Execution branch for spec and plan:
`codex/deterministic-retrieval-order-spec`.

Design:
[Deterministic Retrieval Order Maintenance](../specs/2026-07-26-deterministic-retrieval-order-maintenance-design.md).

## Execution Mode and Gates

- After this plan is reviewed and approved, start a separate isolated implementation worktree at
  the reviewed plan commit. Its merge base must remain the current `main` baseline above.
- Execute sequentially with `superpowers:executing-plans`. Historical authority, protocol,
  runtime SQL, CJK ranking, public errors, observation state, and one-shot holdout form one ordered
  dependency chain.
- Use `superpowers:test-driven-development` for every behavior change and
  `superpowers:verification-before-completion` before READY.
- Task 0 is read-only except for its public inventory record. No runtime test or production file
  changes before the inventory and validator disposition are review-clean.
- Task 1 separates archived source identity from current-source compatibility so additive
  evaluation modules and later runtime edits do not invalidate historical observation bytes.
- Task 2 freezes all development/holdout bytes and the current-runtime observation before runtime
  implementation.
- The pre-implementation RED gate must fail only on stable ordering, duplicate-locator
  admissibility, strategy revision, and public authority-error mapping.
- Stop if a proposed SQL shape requires more than one FTS `MATCH`, selects full Evidence text for
  page ordering, adds N+1 access, or changes CJK row/byte/candidate/result caps.
- Stop if any historical replay changes candidate membership, score hex, a non-tied pair,
  recomputed metric, gate, or verdict.
- Stop if the development command does not pass on its first canonical observation. Do not run the
  holdout command after a failed development gate.
- The holdout command exclusive-creates its receipt before observation. Any second canonical
  attempt or overwrite is an authority failure requiring a newly approved holdout.

## Fixed Contracts

```python
STABLE_LOCATOR_CAUSE = (
    "active retrieval candidates contain duplicate stable Evidence locators"
)
STABLE_LOCATOR_PROBLEM = "retrieval_authority_invalid"
STABLE_LOCATOR_NEXT_STEP = "restore_valid_database_or_reingest_into_new_database"

FTS_ORDER = (
    "rank",
    "locator_start",
    "locator_kind",
    "locator_end",
    "assets.sha256",
)
CJK_ORDER = (
    "-overlap_count",
    "-overlap_ratio",
    "content_fingerprint",
    "locator_kind",
    "locator_start",
    "locator_end",
)

RUNTIME_STRATEGY_REVISION = 2
CJK_ACTIVE_SCAN_REVISION = 2
QUERY_POLICY_REVISION = 1
```

The public error payload remains:

```json
{
  "ok": false,
  "problem": "retrieval_authority_invalid",
  "cause": "active retrieval candidates contain duplicate stable Evidence locators",
  "active_publication_impact": "unchanged",
  "next_step": "restore_valid_database_or_reingest_into_new_database"
}
```

Stable result comparison uses:

```python
StableProjection = tuple[str, str, int, int]
# (content_fingerprint, locator_kind, locator_start, locator_end)
```

The projection is not a domain ID or exact-read address.

## Exact File Map

### Create

- `src/mke/retrieval/errors.py`: path-neutral `RetrievalAuthorityError`.
- `src/mke/evaluation/source_identity.py`: strict recorded file/source identity validation shared
  by historical artifact and protocol validators.
- `src/mke/evaluation/retrieval_order_protocol.py`: strict protocol, fixture hashes, partition
  separation, runtime-profile schema, and frozen key contract.
- `src/mke/evaluation/retrieval_order_workflow.py`: deterministic ID schedules, fresh-workspace
  observation, development freeze, and one-shot holdout workflow.
- `src/mke/evaluation/retrieval_order_artifact.py`: canonical artifact and validator.
- `src/mke/evaluation/retrieval_order_compatibility.py`: archived-source self-consistency and
  revision-2 historical differential.
- `tests/fixtures/retrieval-order-v1/protocol.json`: canonical public protocol.
- `tests/fixtures/retrieval-order-v1/development/cases.json`: constructed FTS/CJK page/timestamp
  mechanism cases.
- `tests/fixtures/retrieval-order-v1/holdout/cases.json`: disjoint public nonblind holdout cases.
- `benchmarks/retrieval/retrieval-order-v1-current-runtime-observation.json`: immutable
  pre-maintenance failure observation.
- `benchmarks/retrieval/retrieval-order-v1-development-freeze.json`: passing candidate-bound
  development freeze.
- `benchmarks/retrieval/retrieval-order-v1-holdout-receipt.json`: one-shot receipt created before
  holdout observation.
- `benchmarks/retrieval/retrieval-order-v1-artifact.json`: final mechanism artifact.
- `benchmarks/retrieval/retrieval-order-v2-compatibility.json`: old-artifact/revision-2
  compatibility and differential.
- `docs/decisions/0012-deterministic-retrieval-order.md`: stable equal-score order, locator
  admissibility, strategy revision, and cursor decision.
- `docs/how-to/run-deterministic-retrieval-order-proof.md`: maintainer workflow and recovery.
- `docs/superpowers/reviews/2026-07-26-deterministic-retrieval-order-source-inventory.md`:
  Task 0 source-bound artifact/validator disposition.
- `tests/evaluation/test_retrieval_order_protocol.py`
- `tests/evaluation/test_retrieval_order_workflow.py`
- `tests/evaluation/test_retrieval_order_artifact.py`
- `tests/evaluation/test_retrieval_order_compatibility.py`
- `tests/evaluation/test_retrieval_order_historical_freeze.py`
- `tests/evaluation/test_retrieval_order_documentation.py`
- `tests/adapters/test_sqlite_fts_order.py`
- `tests/adapters/test_sqlite_cjk_order.py`
- `tests/scripts/test_retrieval_order_installed_proof.py`
- `scripts/retrieval_order_installed_proof.py`

### Modify

- `src/mke/domain/__init__.py`: Run-local locator uniqueness.
- `src/mke/retrieval/__init__.py`: export `RetrievalAuthorityError`.
- `src/mke/retrieval/cjk_active_scan.py`: required content fingerprint, stable order, duplicate
  detection, revision 2.
- `src/mke/retrieval/strategy.py`: three runtime descriptor revisions.
- `src/mke/retrieval/readiness.py`: complete-active-authority `stable_locator_identity` doctor
  check.
- `src/mke/adapters/sqlite/__init__.py`: FTS stable order, same-`MATCH` duplicate detection, CJK
  asset fingerprint loading, and FTS diagnostic parity.
- `src/mke/interfaces/public_errors.py`: allowlist the one stable duplicate-locator cause.
- `src/mke/interfaces/mcp_contract.py`: map authority error in legacy/v1 Search and Ask.
- `src/mke/interfaces/mcp_completeness_contract.py`: map authority error in v2 Search before the
  generic internal error.
- `src/mke/cli.py`: map authority error in Search/Ask and render doctor status.
- `src/mke/evaluation/baseline.py`
- `src/mke/evaluation/numeric_artifact.py`
- `src/mke/evaluation/chinese_artifact.py`
- `src/mke/evaluation/cjk_lexical_artifact.py`: preserve archived source identity and delegate
  current-source claims to revision-2 compatibility.
- `src/mke/evaluation/dense_protocol.py`
- `src/mke/evaluation/dense_artifact.py`
- `src/mke/evaluation/dense_workflow.py`
- `src/mke/evaluation/hybrid_rrf_protocol.py`
- `src/mke/evaluation/relevance_gate_protocol.py`: validate frozen recorded input identities
  without claiming current-source generation.
- `tests/domain/test_manifest.py`
- `tests/retrieval/test_cjk_active_scan.py`
- `tests/retrieval/test_strategy.py`
- `tests/adapters/test_sqlite_fts.py`
- `tests/adapters/test_sqlite_cjk_active_scan.py`
- `tests/adapters/test_sqlite_evidence_access.py`
- `tests/application/test_mcp_cursor.py`
- `tests/interfaces/test_cli_retrieval.py`
- `tests/interfaces/test_mcp_contract.py`
- `tests/interfaces/test_mcp_context_completeness.py`
- `tests/interfaces/test_mcp_legacy_schema_snapshot.py`
- `tests/interfaces/test_mcp_v1_schemas.py`
- `tests/performance/test_cjk_active_scan_performance.py`
- `tests/evaluation/test_baseline.py`
- `tests/evaluation/test_numeric_artifact.py`
- `tests/evaluation/test_chinese_artifact.py`
- `tests/evaluation/test_cjk_lexical_artifact.py`
- `tests/evaluation/test_dense_protocol.py`
- `tests/evaluation/test_dense_artifact.py`
- `tests/evaluation/test_hybrid_rrf_protocol.py`
- `tests/evaluation/test_relevance_gate_protocol.py`
- `docs/explanation/architecture.md`
- `docs/reference/contracts.md`
- `docs/reference/mcp-contract.md`
- `docs/reference/cli.md`
- `docs/how-to/use-mke-mcp.md`
- `docs/how-to/enable-cjk-retrieval.md`
- `docs/README.md`

## Historical Hash Freeze

Task 0 records and later tests preserve these exact baseline bytes:

| Path | SHA-256 |
|---|---|
| `benchmarks/retrieval/retrieval-eval-v1-baseline.json` | `c2518b2f95a91eb91f2f83953965e186711e2b3d93725e9d83617d0fde530a88` |
| `benchmarks/retrieval/numeric-grouping-v1-comparison.json` | `98fb1f61d824d7b307d3a2745b49ed972fc6d4af292833098a15b13b860ddae9` |
| `benchmarks/retrieval/retrieval-chinese-v1-baseline.json` | `7187d999fc98f2ed0f405756f0a4b02ab4dcbb14fdb8d49d8bfd1ad205295828` |
| `benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json` | `5cb54cc7baea939b439c617ee917badff64bface2f2fe5a85b128185fdf3ed3c` |
| `benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json` | `a992059a24b5afbd26c22f71916d7266ada9c3e9ed1fe1354447c7f5f2c40d26` |
| `benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json` | `6b77d29fa3b8badd7400e53fa96cd544ecf84d51563170bfc44d56975ff470c3` |
| `benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json` | `e22e561618726c339bd955d1c7cfcf573080c251549e6a89c8187251d6011e36` |

Protocol bytes also remain unchanged:

| Path | SHA-256 |
|---|---|
| `tests/fixtures/retrieval-eval-v1.json` | `a65b33e011c7a39245a2202fa741e57a268b42da9f68d8da0725955834dd4761` |
| `tests/fixtures/retrieval-numeric-v1/protocol-lock.json` | `17c424e49237deba600fef70d47da803fb73f72d2ee65995fc155dc96e22da60` |
| `tests/fixtures/retrieval-chinese-v1/protocol.json` | `00f72934018a52b5b5f5591fba119050882aee9b782e5dac199702b0cf995944` |
| `tests/fixtures/retrieval-dense-v1/protocol-lock.json` | `afca992a7115fdb06e620168d14f8d09055f231c061b59f82c69f0be2a6e4251` |
| `tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json` | `2407fb3d9abfe1a1127c5d9a600dea529c32c308a42cbd3622c52211d314a716` |
| `tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json` | `6983eb5243493176d6cf97a5e7b5ae888aac9885c25e945583bc291aacf253b1` |

## Task 0: Inventory historical source authority and freeze disposition

**Files:**
- Create:
  `docs/superpowers/reviews/2026-07-26-deterministic-retrieval-order-source-inventory.md`
- Test: existing canonical artifact validators only.

**Interfaces:**
- Consumes: the exact historical hashes above and current validator implementations.
- Produces: one reviewed disposition table used by Tasks 1 and 6; no runtime code.

- [ ] **Step 1: Verify the clean implementation base**

Run:

```bash
git status --short --branch
git merge-base HEAD main
git rev-parse HEAD
```

Expected: clean branch, merge base
`eea3d51c36c0b3b845b8efb60eff553ddc200b88`, and the reviewed plan commit.

- [ ] **Step 2: Recompute the historical byte freeze**

Run the exact `shasum -a 256` command over every path in `Historical Hash Freeze`.

Expected: every digest equals the table. Any mismatch stops Task 0.

- [ ] **Step 3: Run the seven canonical validators before any change**

```bash
uv run pytest -q \
  tests/evaluation/test_baseline.py::test_checked_in_canonical_baseline_is_self_consistent \
  tests/evaluation/test_numeric_artifact.py::test_recorded_artifact_validates_against_fresh_observation \
  tests/evaluation/test_chinese_artifact.py::test_recorded_chinese_artifact_validates_without_reingest \
  tests/evaluation/test_cjk_lexical_artifact.py::test_recorded_cjk_lexical_artifact_validates_by_recomputing_candidate \
  tests/evaluation/test_dense_artifact.py::test_dense_artifact_recomputes_threshold_metrics_and_verdict \
  tests/evaluation/test_hybrid_rrf_artifact.py::test_artifact_validator_recomputes_from_inputs \
  tests/evaluation/test_relevance_gate_artifact.py::test_validator_accepts_canonical_artifact
```

Expected: `7 passed`.

- [ ] **Step 4: Write the exact disposition**

The review must record:

```text
E1 baseline:
  current binding = every src/mke/**/*.py file
  disposition = archived list/digest self-consistency + rev2 current-source differential
E2 numeric:
  current binding = baseline whole-source identity
  disposition = archived source field immutable + rev2 differential
E3-A Chinese:
  current binding = every src/mke/**/*.py file
  disposition = archived source field immutable + rev2 differential
E3-B CJK trigram:
  current binding includes src/mke/adapters/sqlite/__init__.py
  disposition = evaluation-only scorer/revision unchanged; archived bytes immutable; rev2 source differential
E3-C dense:
  explicit source list does not authorize runtime-order refresh
  disposition = artifact bytes immutable; validate consumed E3-A/E3-B identities and current runtime replay
E3-D RRF:
  protocol binds src/mke/retrieval/strategy.py
  disposition = artifact bytes immutable; rev2 replay and verdict equality
E3-E relevance gate:
  recomputes from dense/RRF/current locators
  disposition = artifact bytes immutable; rev2 replay and verdict equality
```

It must also state that no historical observation file will be rewritten and that the separate
revision-2 record owns current-source claims.

- [ ] **Step 5: Review and commit Task 0**

```bash
git diff --check
git diff -- docs/superpowers/reviews/2026-07-26-deterministic-retrieval-order-source-inventory.md
git add docs/superpowers/reviews/2026-07-26-deterministic-retrieval-order-source-inventory.md
git commit -m "docs(eval): inventory retrieval order authority"
```

## Task 1: Separate archived source identity from current-source compatibility

**Files:**
- Create: `src/mke/evaluation/source_identity.py`
- Modify:
  - `src/mke/evaluation/baseline.py`
  - `src/mke/evaluation/numeric_artifact.py`
  - `src/mke/evaluation/chinese_artifact.py`
  - `src/mke/evaluation/cjk_lexical_artifact.py`
  - `src/mke/evaluation/dense_protocol.py`
  - `src/mke/evaluation/dense_artifact.py`
  - `src/mke/evaluation/dense_workflow.py`
  - `src/mke/evaluation/hybrid_rrf_protocol.py`
  - `src/mke/evaluation/relevance_gate_protocol.py`
- Create: `tests/evaluation/test_retrieval_order_historical_freeze.py`
- Modify the matched tests listed in the exact file map.

**Interfaces:**
- Consumes: Task 0's artifact/protocol hashes and disposition.
- Produces:

```python
def build_file_identity(repository_root: Path, relative_path: str) -> dict[str, object]

def build_source_identity(
    repository_root: Path, relative_paths: Sequence[str]
) -> dict[str, object]

def validate_recorded_file_identity(
    value: object, *, expected_path: str | None = None
) -> None

def validate_recorded_source_identity(value: object) -> None
```

Current-source builders remain available only for recording a new artifact or building the
separate revision-2 compatibility record. Historical validators call the recorded-identity
validators.

- [ ] **Step 1: Write source-identity authority REDs**

Add tests that copy each checked-in historical artifact/protocol, mutate one recorded identity
field, and require rejection for:

```text
absolute or parent-traversing path
unsorted or duplicate path list
negative or bool byte count
non-lowercase or malformed SHA-256
top-level source digest inconsistent with canonical recorded file list
missing or extra identity field
changed historical artifact/protocol byte
```

Add a fresh temporary repository file not present in the recorded lists. Historical validation
must still pass; `build_*_identity` must include the new file only when explicitly asked to build a
new current-source record.

`test_retrieval_order_historical_freeze.py` contains the exact artifact/protocol digest maps from
`Historical Hash Freeze` and hashes the checked-in bytes directly. This test, rather than a
current-source comparison, prevents coordinated rewriting of recorded identities.

- [ ] **Step 2: Run the authority REDs**

```bash
uv run pytest -q \
  tests/evaluation/test_retrieval_order_historical_freeze.py \
  tests/evaluation/test_baseline.py -k source \
  tests/evaluation/test_numeric_artifact.py -k source \
  tests/evaluation/test_chinese_artifact.py -k source \
  tests/evaluation/test_cjk_lexical_artifact.py -k source \
  tests/evaluation/test_dense_protocol.py -k identity \
  tests/evaluation/test_dense_artifact.py -k identity \
  tests/evaluation/test_hybrid_rrf_protocol.py -k identity \
  tests/evaluation/test_relevance_gate_protocol.py -k identity
```

Expected: the new "recorded identity survives unrelated current-source change" assertions fail
under current validators. Existing tamper-rejection assertions continue to pass.

- [ ] **Step 3: Implement strict recorded-identity validation**

Canonical source digest:

```python
encoded = json.dumps(
    files, ensure_ascii=True, separators=(",", ":"), sort_keys=True
).encode()
expected = hashlib.sha256(encoded).hexdigest()
```

Require exact fields:

```python
FILE_FIELDS = {"path", "bytes", "sha256"}
SOURCE_FIELDS = {"sha256", "files"}
```

Paths are non-empty `PurePosixPath` values, are not absolute, contain no `..`, and use the exact
expected repository-relative path where the protocol defines one. File lists are sorted by path
and unique.

- [ ] **Step 4: Refactor historical validators narrowly**

Keep every schema, fixture, manifest, score, metric, state, gate, and verdict assertion.

For artifact validators that rebuild an expected payload, validate the recorded source/input
identity first, then compare the rebuilt payload after replacing only its current-source/input
identity field with the validated recorded field. Do not normalize any other field.

For dense development freezes, validate the recorded `source` identity rather than requiring
`dense_source_identity(current_root)`. Protocol and compatibility artifact path/hash fields remain
exact and immutable.

For dense, hybrid-RRF, and relevance-gate protocol locks, validate each recorded input path,
bytes, and SHA rather than comparing it to current checkout bytes. Their current-source replay is
owned by `retrieval-order-v2-compatibility.json` in Task 7.

- [ ] **Step 5: Prove historical bytes and validators**

Run the seven canonical tests from Task 0 plus:

```bash
uv run pytest -q \
  tests/evaluation/test_dense_protocol.py \
  tests/evaluation/test_hybrid_rrf_protocol.py \
  tests/evaluation/test_relevance_gate_protocol.py
```

Expected: pass. Re-run every Task 0 `shasum`; all values remain exact.

- [ ] **Step 6: Commit Task 1**

```bash
git add \
  src/mke/evaluation/source_identity.py \
  src/mke/evaluation/baseline.py \
  src/mke/evaluation/numeric_artifact.py \
  src/mke/evaluation/chinese_artifact.py \
  src/mke/evaluation/cjk_lexical_artifact.py \
  src/mke/evaluation/dense_protocol.py \
  src/mke/evaluation/dense_artifact.py \
  src/mke/evaluation/dense_workflow.py \
  src/mke/evaluation/hybrid_rrf_protocol.py \
  src/mke/evaluation/relevance_gate_protocol.py \
  tests/evaluation/test_retrieval_order_historical_freeze.py \
  tests/evaluation/test_baseline.py \
  tests/evaluation/test_numeric_artifact.py \
  tests/evaluation/test_chinese_artifact.py \
  tests/evaluation/test_cjk_lexical_artifact.py \
  tests/evaluation/test_dense_protocol.py \
  tests/evaluation/test_dense_artifact.py \
  tests/evaluation/test_hybrid_rrf_protocol.py \
  tests/evaluation/test_relevance_gate_protocol.py
git diff --cached --check
git commit -m "fix(eval): separate archived source identity"
```

## Task 2: Freeze `retrieval-order-v1` and record the current failure

**Files:**
- Create: `src/mke/evaluation/retrieval_order_protocol.py`
- Create: `src/mke/evaluation/retrieval_order_workflow.py`
- Create: `tests/fixtures/retrieval-order-v1/protocol.json`
- Create: `tests/fixtures/retrieval-order-v1/development/cases.json`
- Create: `tests/fixtures/retrieval-order-v1/holdout/cases.json`
- Create: `benchmarks/retrieval/retrieval-order-v1-current-runtime-observation.json`
- Create: `tests/evaluation/test_retrieval_order_protocol.py`
- Create: `tests/evaluation/test_retrieval_order_workflow.py`

**Interfaces:**
- Consumes: current `KnowledgeEngine`, `SQLiteStore`, strategy descriptors, query-policy revision,
  and fixed historical hashes.
- Produces:

```python
@dataclass(frozen=True)
class RetrievalOrderProtocol:
    schema_version: Literal["mke.retrieval_order_protocol.v1"]
    protocol_id: Literal["retrieval-order-v1"]
    key_contract: RetrievalOrderKeyContract
    development: PartitionContract
    holdout: PartitionContract
    runtime_profile_fields: tuple[str, ...]

def load_retrieval_order_protocol(path: Path, *, repository_root: Path) -> RetrievalOrderProtocol

def observe_retrieval_order_partition(
    *, protocol_path: Path, partition: Literal["development", "holdout"],
    repository_root: Path
) -> dict[str, object]

def retrieval_runtime_profile(connection: sqlite3.Connection) -> dict[str, object]
```

- [ ] **Step 1: Write strict protocol tests**

Add tests that require:

```python
assert protocol.protocol_id == "retrieval-order-v1"
assert protocol.key_contract.fts == (
    "rank", "locator_start", "locator_kind", "locator_end", "assets.sha256"
)
assert protocol.key_contract.cjk == (
    "-overlap_count", "-overlap_ratio", "content_fingerprint",
    "locator_kind", "locator_start", "locator_end"
)
assert protocol.development.sha256 != protocol.holdout.sha256
assert development_source_ids.isdisjoint(holdout_source_ids)
assert development_query_ids.isdisjoint(holdout_query_ids)
assert protocol.runtime_profile_fields == (
    "python", "sqlite", "sqlite_source_id", "sqlite_compile_options",
    "fts5_rank_configuration", "strategy_revision", "query_policy_revision"
)
```

Mutation tests reject absolute paths, `..`, hash mismatch, duplicate case/query identity, shared
development/holdout bytes, missing page/timestamp coverage, and any opaque ID in expected stable
projections.

- [ ] **Step 2: Run protocol tests to verify RED**

```bash
uv run pytest -q tests/evaluation/test_retrieval_order_protocol.py
```

Expected: import failure for `mke.evaluation.retrieval_order_protocol`.

- [ ] **Step 3: Implement the protocol loader and exact fixture cases**

Development must contain:

```text
FTS page equal-score group
FTS timestamp equal-score group
CJK page equal-overlap group
CJK timestamp equal-overlap group
different Sources with the same locator
one Source with distinct locators
locator_kind and locator_end tie coverage
workspace schedules forward_ids and reverse_ids
page sizes 1, 2, and full result count
```

Holdout contains exactly one disjoint FTS equal-score group and one disjoint CJK equal-overlap
group. Its source bytes, source digests, Evidence text, locators, query text, and IDs do not appear
in development.

Both fixture files contain only constructed text and stable digests. They contain no private path,
opaque runtime cursor, or externally sourced document.

- [ ] **Step 4: Implement deterministic fresh-workspace observation**

Use an evaluation-only ID schedule context:

```python
@contextmanager
def _controlled_sqlite_ids(schedule: Mapping[str, tuple[str, ...]]) -> Iterator[None]:
    original = mke.adapters.sqlite._new_id
    queues = {prefix: iter(values) for prefix, values in schedule.items()}
    mke.adapters.sqlite._new_id = lambda prefix: next(queues[prefix])
    try:
        yield
    finally:
        mke.adapters.sqlite._new_id = original
```

The workflow still creates Sources, Runs, candidate Evidence, and Publications through the
application/store lifecycle. A test raises inside the context and proves `_new_id` is restored.
Every workspace is a new temporary database and is closed before comparison.

The observation records stable projections, score hex for FTS, non-tied pairs, candidate
membership, page concatenation, strategy/query-policy revisions, and the fixed runtime profile. It
does not record raw query/Evidence text, opaque IDs, cursors, absolute paths, or tracebacks.

- [ ] **Step 5: Freeze the pre-maintenance observation**

Run the current observation once:

```bash
uv run python -m mke.evaluation.retrieval_order_workflow current \
  --protocol tests/fixtures/retrieval-order-v1/protocol.json \
  --record benchmarks/retrieval/retrieval-order-v1-current-runtime-observation.json \
  --json
```

Expected exit: `1`.

Expected public fields:

```json
{
  "schema_version": "mke.retrieval_order_observation.v1",
  "phase": "current",
  "integrity_status": "passed",
  "observation_status": "failed",
  "problem": "retrieval_order_nondeterministic",
  "cause": "fresh workspace stable projections differ",
  "next_step": "apply_tie_only_stable_order_maintenance"
}
```

The command emits one JSON object, empty stderr, no raw text/IDs/path, and leaves no database.

- [ ] **Step 6: Run Task 2 tests and commit**

```bash
uv run pytest -q \
  tests/evaluation/test_retrieval_order_protocol.py \
  tests/evaluation/test_retrieval_order_workflow.py
git diff --check
git add \
  src/mke/evaluation/retrieval_order_protocol.py \
  src/mke/evaluation/retrieval_order_workflow.py \
  tests/fixtures/retrieval-order-v1/protocol.json \
  tests/fixtures/retrieval-order-v1/development/cases.json \
  tests/fixtures/retrieval-order-v1/holdout/cases.json \
  benchmarks/retrieval/retrieval-order-v1-current-runtime-observation.json \
  tests/evaluation/test_retrieval_order_protocol.py \
  tests/evaluation/test_retrieval_order_workflow.py
git commit -m "test(eval): freeze deterministic retrieval order protocol"
```

## Pre-implementation RED gate

Create the first failing tests in these separate files without staging them together:

- `tests/domain/test_manifest.py`: duplicate page and timestamp locator tuples fail.
- `tests/adapters/test_sqlite_fts_order.py`: inverse ID schedules return the same stable projection;
  duplicate matched legacy candidates raise `RetrievalAuthorityError`.
- `tests/adapters/test_sqlite_cjk_order.py`: inverse Source/Evidence IDs return the same stable
  projection; duplicate bounded candidates raise `RetrievalAuthorityError`.
- `tests/retrieval/test_strategy.py`: three descriptor revisions are 2.
- `tests/interfaces/test_cli_retrieval.py`: mocked authority error is redacted and exits 1.
- `tests/interfaces/test_mcp_contract.py`: legacy/v1 Search and Ask return the frozen authority
  error.
- `tests/interfaces/test_mcp_context_completeness.py`: v2 Search returns the frozen authority error.

Run:

```bash
uv run pytest -q \
  tests/domain/test_manifest.py::test_manifest_rejects_duplicate_page_locator \
  tests/domain/test_manifest.py::test_manifest_rejects_duplicate_timestamp_locator \
  tests/adapters/test_sqlite_fts_order.py \
  tests/adapters/test_sqlite_cjk_order.py \
  tests/retrieval/test_strategy.py \
  tests/interfaces/test_cli_retrieval.py -k retrieval_authority_invalid \
  tests/interfaces/test_mcp_contract.py -k retrieval_authority_invalid \
  tests/interfaces/test_mcp_context_completeness.py -k retrieval_authority_invalid
```

Expected: failures are limited to duplicate locators being accepted, inverse schedules producing
different order, revision 1 still being reported, missing `RetrievalAuthorityError`, or generic
internal-error mapping. Any score, membership, active-authority, schema, or unrelated failure stops
implementation.

## Task 3: Enforce locator admissibility and the typed recovery contract

**Files:**
- Create: `src/mke/retrieval/errors.py`
- Modify: `src/mke/retrieval/__init__.py`
- Modify: `src/mke/domain/__init__.py`
- Modify: `src/mke/retrieval/readiness.py`
- Modify: `src/mke/interfaces/public_errors.py`
- Modify: `src/mke/interfaces/mcp_contract.py`
- Modify: `src/mke/interfaces/mcp_completeness_contract.py`
- Modify: `src/mke/cli.py`
- Modify: interface/domain/readiness tests listed above.

**Interfaces:**
- Produces:

```python
class RetrievalAuthorityError(RuntimeError):
    problem = "retrieval_authority_invalid"
    cause = "active retrieval candidates contain duplicate stable Evidence locators"
    next_step = "restore_valid_database_or_reingest_into_new_database"
```

- [ ] **Step 1: Add the typed exception and Run-local manifest check**

In `validate_manifest`, maintain:

```python
seen_locators: set[tuple[str, int, int]] = set()
locator = (item.locator_kind, item.locator_start, item.locator_end)
if locator in seen_locators:
    raise ManifestValidationError("Evidence locators must be unique within one Run")
seen_locators.add(locator)
```

Keep all existing locator-kind/range/text validation.

- [ ] **Step 2: Add the complete-active-authority doctor check**

`doctor_retrieval_strategy` performs one read-only grouped query across active Publications:

```sql
SELECT 1
FROM sources
JOIN assets ON assets.asset_id = sources.asset_id
JOIN publications ON publications.publication_id = sources.active_publication_id
JOIN evidence
  ON evidence.run_id = publications.run_id
 AND evidence.source_id = sources.source_id
GROUP BY assets.sha256, evidence.locator_kind,
         evidence.locator_start, evidence.locator_end
HAVING COUNT(*) > 1
LIMIT 1
```

Add `RetrievalReadinessCheck("stable_locator_identity", ...)`. On a duplicate, return the exact
authority problem/cause/next-step and keep `active_publication_impact=unchanged` at the CLI layer.
The missing/unreadable/projection branches report the new check as `not_ready`; no path is exposed.

- [ ] **Step 3: Map the error through current public shapes**

Catch `RetrievalAuthorityError` before broad handlers in:

```text
CLI Search and Ask
legacy MCP Search and Ask
strict-v1 MCP Search and Ask
v2 MCP Search
```

Reuse `error.problem`, `error.cause`, and `error.next_step`. Add only the exact cause string to
`_ALLOWLISTED_CAUSES`. Do not alter Pydantic models, tool registration, schema fixtures, or valid
success payloads.

- [ ] **Step 4: Run Task 3 tests**

```bash
uv run pytest -q \
  tests/domain/test_manifest.py \
  tests/interfaces/test_public_errors.py \
  tests/interfaces/test_cli_retrieval.py \
  tests/interfaces/test_mcp_contract.py \
  tests/interfaces/test_mcp_v1_schemas.py \
  tests/interfaces/test_mcp_context_completeness.py
```

Expected: Task 3 tests pass. FTS/CJK ordering RED files remain failing and uncommitted.

- [ ] **Step 5: Commit Task 3 only**

Stage the exact Task 3 paths, inspect `git diff --cached`, and commit:

```bash
git add \
  src/mke/retrieval/errors.py \
  src/mke/retrieval/__init__.py \
  src/mke/domain/__init__.py \
  src/mke/retrieval/readiness.py \
  src/mke/interfaces/public_errors.py \
  src/mke/interfaces/mcp_contract.py \
  src/mke/interfaces/mcp_completeness_contract.py \
  src/mke/cli.py \
  tests/domain/test_manifest.py \
  tests/interfaces/test_public_errors.py \
  tests/interfaces/test_cli_retrieval.py \
  tests/interfaces/test_mcp_contract.py \
  tests/interfaces/test_mcp_v1_schemas.py \
  tests/interfaces/test_mcp_context_completeness.py
git diff --cached --check
git commit -m "fix(retrieval): reject duplicate stable locators"
```

Do not stage `tests/adapters/test_sqlite_fts_order.py` or
`tests/adapters/test_sqlite_cjk_order.py`.

## Task 4: Make FTS order stable inside one matched statement

**Files:**
- Modify: `src/mke/adapters/sqlite/__init__.py`
- Create: `tests/adapters/test_sqlite_fts_order.py`
- Modify: `tests/adapters/test_sqlite_fts.py`
- Modify: `tests/adapters/test_sqlite_evidence_access.py`

**Interfaces:**
- Consumes: `RetrievalAuthorityError`.
- Produces one shared SQL shape used by `_search_fts`, `_search_fts_page`, and
  `observe_fts5_rank`.

- [ ] **Step 1: Verify the focused FTS RED**

```bash
uv run pytest -q tests/adapters/test_sqlite_fts_order.py
```

Expected: inverse stores differ or `evidence_id` remains visible in `ORDER BY`.

- [ ] **Step 2: Join stable content identity and order only ties**

Every affected FTS query joins:

```sql
JOIN assets ON assets.asset_id = sources.asset_id
```

Use:

```sql
ORDER BY score, locator_start, locator_kind, locator_end, source_sha256
```

where `score` is `rank` or `bm25(active_evidence_fts)` and `source_sha256` aliases
`assets.sha256`. No `evidence_id` appears in the order clause.

- [ ] **Step 3: Detect duplicate matched projections before page selection**

Use one materialized matched CTE and one integrity CTE:

```sql
WITH matched AS MATERIALIZED (
  SELECT evidence.evidence_id,
         active_evidence_fts.publication_id,
         evidence.source_id,
         evidence.locator_kind,
         evidence.locator_start,
         evidence.locator_end,
         assets.sha256 AS source_sha256,
         rank AS score,
         length(CAST(evidence.text AS BLOB)) AS text_bytes
  FROM active_evidence_fts
  JOIN evidence ON evidence.evidence_id = active_evidence_fts.evidence_id
  JOIN sources ON sources.source_id = evidence.source_id
  JOIN assets ON assets.asset_id = sources.asset_id
  WHERE active_evidence_fts MATCH ?
    AND sources.active_publication_id = active_evidence_fts.publication_id
),
integrity AS (
  SELECT EXISTS(
    SELECT 1 FROM matched
    GROUP BY source_sha256, locator_kind, locator_start, locator_end
    HAVING COUNT(*) > 1
  ) AS duplicate_stable_locator
)
```

The final statement returns the integrity flag with page rows. `_search_fts_page` uses a
left-joined sentinel so an empty page still exposes the integrity flag. Raise
`RetrievalAuthorityError` before loading any full Evidence text.

The query trace must contain exactly one `active_evidence_fts MATCH`.

- [ ] **Step 4: Preserve metadata-first paging and exact diagnostic parity**

`_search_fts_page` returns at most `page_size + 1` metadata rows and keeps
`length(CAST(evidence.text AS BLOB))`; it never selects `evidence.text`.

`observe_fts5_rank` uses the same stable key for both `rank` and BM25 orders and returns unchanged
float values. Tests compare `float.hex()` before/after for all rows.

- [ ] **Step 5: Run FTS tests**

```bash
uv run pytest -q \
  tests/adapters/test_sqlite_fts_order.py \
  tests/adapters/test_sqlite_fts.py \
  tests/adapters/test_sqlite_evidence_access.py
```

Expected: pass; one `MATCH`, metadata-only page SQL, stable inverse-store projections, exact score
hex, no gap/duplicate at page sizes 1/2/full, and typed duplicate failure.

- [ ] **Step 6: Commit Task 4**

```bash
git add \
  src/mke/adapters/sqlite/__init__.py \
  tests/adapters/test_sqlite_fts_order.py \
  tests/adapters/test_sqlite_fts.py \
  tests/adapters/test_sqlite_evidence_access.py
git commit -m "fix(retrieval): stabilize FTS tie ordering"
```

## Task 5: Make CJK order stable and bump runtime revisions

**Files:**
- Modify: `src/mke/retrieval/cjk_active_scan.py`
- Modify: `src/mke/retrieval/strategy.py`
- Modify: `src/mke/adapters/sqlite/__init__.py`
- Create: `tests/adapters/test_sqlite_cjk_order.py`
- Modify: `tests/retrieval/test_cjk_active_scan.py`
- Modify: `tests/retrieval/test_strategy.py`
- Modify: `tests/adapters/test_sqlite_cjk_active_scan.py`
- Modify: `tests/performance/test_cjk_active_scan_performance.py`
- Modify: `tests/evaluation/test_retrieval_order_workflow.py`

**Interfaces:**
- Changes:

```python
@dataclass(frozen=True)
class CjkActiveScanCandidate:
    ...
    document_id: str  # required sha256:<asset-digest>

@dataclass(frozen=True)
class CjkActiveScanResult:
    ...
    document_id: str  # required sha256:<asset-digest>
```

- [ ] **Step 1: Verify the focused CJK RED**

```bash
uv run pytest -q \
  tests/adapters/test_sqlite_cjk_order.py \
  tests/retrieval/test_cjk_active_scan.py \
  tests/retrieval/test_strategy.py
```

Expected: current fallback to `source_id`, `evidence_id` tie order, or revision 1 fails assertions.

- [ ] **Step 2: Require stable document identity and reject duplicates**

Before scoring a non-empty term set:

```python
seen: set[tuple[str, str, int, int]] = set()
for candidate in candidates:
    projection = (
        candidate.document_id,
        candidate.locator_kind,
        candidate.locator_start,
        candidate.locator_end,
    )
    if projection in seen:
        raise RetrievalAuthorityError
    seen.add(projection)
```

Sort:

```python
key=lambda item: (
    -item.overlap_count,
    -item.overlap_ratio,
    item.document_id,
    item.locator_kind,
    item.locator_start,
    item.locator_end,
)
```

Remove the `document_id or source_id` and `evidence_id` fallbacks.

- [ ] **Step 3: Load asset SHA-256 without changing scan caps**

The active-scan query joins `assets`, selects `assets.sha256`, and constructs:

```python
document_id=f"sha256:{row['source_sha256']}"
```

Keep the existing row count, text byte, candidate pool, and top-10 caps byte-for-byte. The
evaluation-only CJK trigram candidate remains revision 1 and keeps its own stable `document_id`.

- [ ] **Step 4: Bump exactly the runtime revisions**

Set the three descriptors and `CJK_ACTIVE_SCAN_PARAMETERS` to revision 2. Keep
`QUERY_POLICY_REVISION == 1`.

- [ ] **Step 5: Run CJK and structural performance tests**

```bash
uv run pytest -q \
  tests/adapters/test_sqlite_cjk_order.py \
  tests/retrieval/test_cjk_active_scan.py \
  tests/retrieval/test_strategy.py \
  tests/adapters/test_sqlite_cjk_active_scan.py \
  tests/performance/test_cjk_active_scan_performance.py
```

Expected: pass with stable inverse-store projections, typed duplicate failure, exact caps, and
revision 2.

- [ ] **Step 6: Run the non-canonical development regression in temporary workspaces**

Add
`test_development_candidate_is_stable_without_recording` to
`tests/evaluation/test_retrieval_order_workflow.py`. It writes all generated state under
`tmp_path`, requires `stable_order_rate == 1.0`, exact zero deltas, and asserts the canonical
benchmark paths do not change.

```bash
uv run pytest -q \
  tests/evaluation/test_retrieval_order_workflow.py::test_development_candidate_is_stable_without_recording
```

Expected: pass; the test uses temporary output paths, observes `stable_order_rate=1.0`, requires
membership/score/non-tied deltas `0`, and proves no canonical freeze file is created. The first
canonical development command remains Task 8 Step 4.

- [ ] **Step 7: Commit Task 5**

Stage only Task 5 paths and commit:

```bash
git add \
  src/mke/retrieval/cjk_active_scan.py \
  src/mke/retrieval/strategy.py \
  src/mke/adapters/sqlite/__init__.py \
  tests/adapters/test_sqlite_cjk_order.py \
  tests/retrieval/test_cjk_active_scan.py \
  tests/retrieval/test_strategy.py \
  tests/adapters/test_sqlite_cjk_active_scan.py \
  tests/performance/test_cjk_active_scan_performance.py \
  tests/evaluation/test_retrieval_order_workflow.py
git diff --cached --check
git commit -m "fix(retrieval): stabilize CJK tie ordering"
```

## Task 6: Close cursor, interface, and schema compatibility

**Files:**
- Modify: `tests/application/test_mcp_cursor.py`
- Modify: `tests/interfaces/test_cli_retrieval.py`
- Modify: `tests/interfaces/test_mcp_contract.py`
- Modify: `tests/interfaces/test_mcp_context_completeness.py`
- Modify: `tests/interfaces/test_mcp_legacy_schema_snapshot.py`
- Modify: `tests/interfaces/test_mcp_v1_schemas.py`
- Modify: `tests/fixtures/mcp-context-completeness-v1/mcp-tool-schemas.json` only if exact
  regenerated bytes are identical; otherwise leave it untouched.

**Interfaces:**
- Consumes: descriptor revision 2 and existing cursor codec.
- Produces no new runtime model or schema.

- [ ] **Step 1: Add exact Search cursor upgrade tests**

Create a revision-1 Search cursor under the same owner and active authority, then validate against
revision 2:

```python
with pytest.raises(CursorExpiredError, match="retrieval_policy_changed"):
    validate_search_cursor(
        parsed, material, authority,
        strategy_id="cjk-active-scan-overlap-v1",
        strategy_revision=2,
        query_policy="numeric-grouping-v1",
        query_policy_revision=1,
    )
```

The MCP result must be:

```text
problem=cursor_expired
cause=retrieval policy changed
next_step=repeat_search_under_current_strategy
```

The consumer test discards all revision-1 matches before issuing a new initial query.

- [ ] **Step 2: Prove Read cursor continuity and owner restart**

Validate the same Read cursor before and after a strategy-only descriptor change under one owner.
Then rotate owner epoch/key and assert `owner_restarted`. Search and Read both expire after the
owner restart.

- [ ] **Step 3: Prove exact public-schema compatibility**

Run:

```bash
uv run pytest -q \
  tests/application/test_mcp_cursor.py \
  tests/interfaces/test_mcp_legacy_schema_snapshot.py \
  tests/interfaces/test_mcp_v1_schemas.py \
  tests/interfaces/test_mcp_context_completeness.py
```

Expected: exact legacy, v1, and v2 schemas/tool inventory remain unchanged. The frozen schema file
must retain its existing SHA-256 if no generated schema field changed.

- [ ] **Step 4: Commit Task 6**

```bash
git add \
  tests/application/test_mcp_cursor.py \
  tests/interfaces/test_cli_retrieval.py \
  tests/interfaces/test_mcp_contract.py \
  tests/interfaces/test_mcp_context_completeness.py \
  tests/interfaces/test_mcp_legacy_schema_snapshot.py \
  tests/interfaces/test_mcp_v1_schemas.py
git commit -m "test(retrieval): lock revision two cursor compatibility"
```

## Amendment C Decision — Layered Historical Authority and Compatibility Closure

This approved amendment preserves completed Tasks 0–6 and supersedes the original Tasks 7–9, their post-Task-6 file ownership, commands, gates, and Final Acceptance. Where an earlier post-Task-6 instruction conflicts with this amendment, the amendment controls.

Replace the blocked Task 7 entry condition with a layered closure:

1. insert **Task 6R** to repair three verified evaluation-contract mismatches;
2. split Task 7 into **Task 7A**, which implements and tests compatibility against temporary
   output, and **Task 7B**, which records canonical compatibility only after the one-shot holdout;
3. merge every remaining source/test/doc write from original Tasks 8 and 9 into
   **Task 8A — Complete candidate source**;
4. make the clean final Task 8A HEAD the unique candidate source seal, then run
   **Task 8B — Observe once**; and
5. make **Task 8R — Proof-only closure** atomically publish canonical JSON, run
   historical/full/installed verification from the sealed source and one shared wheel, and commit
   proof artifacts without any source/test/doc write.

Task 6R does not make every historical/current-replay test green. Its purpose is to make the
authority layers explicit without weakening the live numeric CLI:

```text
historical bytes frozen
archived record self-consistent
current runtime replay compatible
revision-2 differential valid
```

The complete 133-test historical matrix becomes green in Task 7A, when current replay has an
authorized compatibility path. It is rerun in Task 8R after the final source/test/doc commit and
the one-shot observation.

This amendment changes evaluation validation, tests, plan ordering, and compatibility-proof
timing only. It does not change retrieval ranking, cursor semantics, frozen corpora, historical
artifact bytes, public schemas, promotion authority, or product scope.

## Why the Earlier Repair Shape Was Rejected

Tasks 0–6 completed in seven semantic commits. The original Task 7 matrix then returned:

```text
62 passed
71 failed
```

Verified failure families:

| Family | Result | Verified cause |
|---|---:|---|
| E1 baseline | 25 passed | none |
| E2 numeric | 30 failed | archived scope hashes are still compared with current checkout bytes |
| E3-A Chinese | 29 failed, 1 passed | SQL-trace validator recognizes only revision-1 ordering |
| E3-B CJK trigram | 12 failed | downstream of the same Chinese diagnostic mismatch |
| E3-C dense | 12 passed | none |
| E3-D hybrid RRF | 11 passed | none |
| E3-E relevance gate | 13 passed | none |

An additional focused run of `tests/evaluation/test_retrieval_order_workflow.py` returned
`2 passed, 3 failed`: two new tests assert live revision 2/passed, while three stale tests still
assert live revision 1/failed.

The initial Task 6R draft proposed removing current-source hash comparison from
`load_numeric_protocol`. That would make the public `mke eval retrieval-numeric` path accept an
archived protocol against unbound current source. It would also turn
`test_validator_rejects_source_content_change` into a shadow contract. The default live loader and
public CLI must remain fail-closed; only an explicit archive/compatibility path may validate
recorded scope identity without comparing current bytes.

The initial draft also treated the trace as exactly two statements and forbade `LIMIT` globally.
The live trace contains two MATCH statements plus a legitimate
`active_evidence_fts_config ... LIMIT 1` rank-configuration probe. Only the two MATCH statements
own ordering proof.

Finally, the original Task 7 canonical artifact would bind current source before Task 8 writes
`retrieval_order_artifact.py` and updates `retrieval_order_workflow.py`. Canonical generation must
occur after the final source-writing commit or it is stale by construction.

The first reviewed amendment still sealed source too early: original Task 9 subsequently creates
the installed-proof script/tests, ADR, maintainer how-to, documentation tests, and edits public
docs. All of those writes must occur before development/holdout. After holdout, factual results
belong in retained handoff/PR evidence, not new source or documentation edits.

These findings correct the plan; they do not establish implementation success.

## Premises and Authority

### Preserved premises

1. The approved design remains the product authority.
2. Historical observation/protocol bytes remain immutable.
3. Archived identity and current-source replay are distinct authorities.
4. Current retrieval strategy revision is `2`; query-policy revision remains `1`.
5. The live revision-2 stable SQL ordering is the intended runtime contract.
6. Any membership, exact score-hex, non-tied order, metric, gate, verdict, or historical-byte
   drift is a STOP.
7. Comparison-only proof never authorizes promotion.

### Corrected premise

The complete historical matrix is not a valid Task 6R precondition because several tests execute
the current runtime through archived source locks. Task 6R must preserve that live failure while
adding a separate archive path. Task 7A owns current replay and makes the matrix green.

### Authority layers

| Layer | What it proves | What it must not prove |
|---|---|---|
| `historical_bytes_frozen` | checked-in artifact/protocol bytes match Task 0 digests | current runtime compatibility |
| `archived_record_self_consistent` | recorded keys, paths, SHA syntax/order, manifests, fixtures, schema record, and artifact fields are internally valid | current checkout generated the record |
| `current_runtime_replay_compatible` | current revision replays frozen inputs through an explicit compatibility path | historical artifact was produced by revision 2 |
| `revision_2_differential_valid` | only preregistered equal-score permutations differ; metrics/gates/verdicts are unchanged | promotion or general retrieval quality |

Immutable historical inputs comprise the original 13-entry Task 0 SHA map plus the post-Task-2
current-runtime observation:

```text
benchmarks/retrieval/retrieval-order-v1-current-runtime-observation.json
1a98e4e6c4eabc01663991646aac46e4a73033eef8a7e17a27db2e0fdce71691
```

The 14th item is not retroactively called a Task 0 hash. Task 6R appends it to the source inventory
and the immutable-hash test. Canonical compatibility binds the exact 14-entry set.

### Preserved product boundaries

- Run, Publication, Evidence, and active-only authority.
- Frozen development/holdout partitions, corpus bytes, query IDs, qrels, score groups, gates, and
  thresholds.
- Python, CLI, MCP, cursor, installed-wheel, source-pack, and consumer contracts.
- No GraphRAG, dense/RRF/reranker runtime, OCR, Agent loop, HTTP/SaaS, provider, model, dependency,
  or new public command.

### Not authorized

- Any runtime retrieval modification.
- Rewriting historical artifacts/protocols or refreshing their checked-in identities.
- Corpus/query/span/order tuning.
- Development/holdout before the amended gates.
- Holdout retry, receipt deletion, or candidate substitution.
- Push, PR, merge, tag, release, deploy, cleanup, Stage 2, or promotion.

## Architecture

```text
                        IMMUTABLE HISTORY
  Task 0 SHA map ------------------------------+
                                                |
  archived protocol/artifact bytes              |
          |                                     |
          v                                     v
  recorded schema/path/SHA checks       historical_bytes_frozen
          |
          v
  archived_record_self_consistent

                        LIVE COMPATIBILITY
  current source + frozen manifests/fixtures
          |
          +--> strict live loader (default/public CLI)
          |       |
          |       +--> stale archived source lock => fail closed
          |
          +--> explicit compatibility loader
                  |
                  +--> recorded scope validated lexically
                  +--> current source identity recorded separately
                  +--> current schema and frozen inputs replayed
                  |
                  v
          revision_2_differential_valid
```

The compatibility loader is an internal Python path only. It adds no CLI flag and does not change
the default `load_numeric_protocol` or `run_numeric_comparison` authority.

```text
  SQLiteStore.observe_fts5_rank()
          |
          v
  normalize all traced statements
          |
          +--> select statements containing active_evidence_fts MATCH
          |       |
          |       +--> require exactly two
          |       +--> require exactly one rank and one BM25 statement
          |       +--> require stable revision-2 ORDER BY
          |       +--> reject LIMIT and opaque evidence_id ordering here
          |
          +--> ignore non-MATCH statements for ordering proof
                  |
                  +--> config probe LIMIT 1 remains valid
```

No generalized SQL parser is introduced.

## State Machine

```text
  IMPLEMENTATION_STOPPED
          |
          | complete Amendment C approval
          v
  PLAN_LANDING_ONLY
          |
          | actual public plan diff authority-review clean
          v
  TASK_6R_AUTHORIZED
          |
          | targeted RED/GREEN + bounded pre-resume gate
          v
  TASK_6R_COMMITTED_CLEAN
          |
          | authority code-diff review clean
          v
  TASK_7A_AUTHORIZED
          |
          | temp compatibility + 133-test matrix green
          v
  TASK_7A_COMMITTED_CLEAN
          |
          | Task 8A completes every remaining source/test/doc write
          v
  CANDIDATE_SOURCE_DOCS_SEALED
          |
          | Task 8B development once, then holdout once
          v
  HOLDOUT_SUCCEEDED_TERMINAL
          |
          | Task 7B/8R canonical compatibility + final verification
          v
  PROOF_ARTIFACTS_COMMITTED

  HOLDOUT_FAILED_TERMINAL
          |
          +--> STOP; retain receipt/evidence; no Task 8R

  HOLDOUT_ARTIFACT_DURABILITY_UNCONFIRMED
          |
          +--> STOP; retain complete visible bytes; no Task 8R
```

Invalid transitions:

- Task 6R directly to development/holdout.
- Task 7A generating or committing the canonical compatibility artifact.
- Candidate sealing before installed-proof code/tests, ADR, how-to, docs, and documentation tests.
- Canonical compatibility generation before the final source/test/doc commit.
- Direct canonical holdout observation without the receipt-bound private capability.
- Any source/test/doc write after the candidate seal or holdout.
- Any failed development command to holdout.
- Any holdout receipt state to retry or deletion.
- Failed or durability-unconfirmed holdout to Task 8R.
- Any comparison result to runtime promotion.

## Task 6R — Repair Evaluation Authority Contracts

### Allowed paths

Modify:

- `docs/superpowers/reviews/2026-07-26-deterministic-retrieval-order-source-inventory.md`
- `src/mke/evaluation/numeric_comparison.py`
- `tests/evaluation/test_numeric_comparison.py`
- `tests/evaluation/test_numeric_fixture_corpus.py`
- `src/mke/evaluation/chinese_runner.py`
- `tests/evaluation/test_chinese_runner.py`
- `tests/evaluation/test_retrieval_order_workflow.py`
- `tests/evaluation/test_retrieval_order_historical_freeze.py`

Verification-only:

- all historical artifact tests;
- all runtime retrieval, cursor, interface, and schema tests.

No runtime retrieval file or historical artifact/protocol is writable.

### Step 1 — Append the execution finding

Append, without changing the Task 0 disposition:

- the blocked command and counts;
- numeric archived/current authority conflation;
- Chinese trace revision mismatch;
- stale workflow revision assertions;
- the decision that default live validation remains strict; and
- canonical compatibility generation is deferred until all source/test/doc work and holdout
  finish.

Append the post-Task-2 observation path and exact digest as the 14th immutable historical input.
Do not relabel it as part of the original Task 0 freeze.

### Step 2 — Numeric authority RED

Add tests proving:

1. default `load_numeric_protocol` rejects a copied archived protocol after one bound current
   source file changes;
2. the public/current runner preserves the stable failed integrity result for that mismatch;
3. an explicit archive/compatibility loader accepts the same recorded scope only after checking
   exact key set, exact lexical path allowlist/order, lowercase SHA-256 syntax, and schema-hash
   syntax;
4. archive mode still validates manifest/fixture hashes and current SQLite schema compatibility;
5. live mode still rejects symlink/path escape and current source mutation;
6. `refresh_numeric_protocol_scope` changes only scope hashes in a copied protocol and makes the
   copied protocol live-valid; and
7. the checked-in protocol SHA remains exact.

The RED must fail because no explicit archive/compatibility path exists.

### Step 3 — Numeric narrow GREEN

Refactor the shared parse path so authority is explicit:

```python
load_numeric_protocol(...)  # unchanged strict live default
load_archived_numeric_protocol(...)  # internal compatibility path
```

Equivalent private naming is acceptable, but a caller must not select archive behavior through a
public CLI flag or an implicit fallback.

Also extract one module-private execution core:

```python
def _evaluate_numeric_protocol(protocol: NumericProtocol) -> NumericComparisonReport: ...
```

`run_numeric_comparison(path)` must always use the strict live loader, then call this core.
Task 7A may validate with the archived loader and pass the resulting protocol to the same core.
Do not duplicate the numeric runner, monkeypatch loader selection, export the helper from
`mke.evaluation`, or add a CLI mode.

Archive scope validation:

- requires exact `files` and `sqlite_schema_sha256` fields;
- requires the exact `_EXPECTED_SCOPE_PATHS` count, order, and repository-relative lexical values;
- rejects absolute paths, `..`, duplicates, wrong order, uppercase/malformed digests, and extra
  fields;
- does not resolve scope entries through current filesystem topology and does not compare their
  recorded SHA values to current bytes;
- continues to validate frozen manifests/fixtures against their bytes and hashes; and
- continues to compare the recorded SQLite schema hash with the live replay schema through the
  existing gate.

Live scope validation remains byte-exact against the current checkout. `refresh` remains the only
explicit current-source lock refresh path and never touches the checked-in protocol in this stage.

Remove the shadow full-protocol validator in
`tests/evaluation/test_numeric_fixture_corpus.py`. Keep independent corpus facts there, and route
protocol authority tests through production loaders.

### Step 4 — Chinese trace RED

Use captured live traces plus hostile synthetic traces to prove:

1. all statements are normalized before selection;
2. exactly two MATCH statements are selected from a trace that may contain other statements;
3. exactly one selected statement uses `rank AS score` and one uses
   `bm25(active_evidence_fts) AS score`;
4. both selected statements require evidence, sources, and assets joins, active-publication
   binding, and the complete revision-2 stable key;
5. `LIMIT` is rejected inside either selected MATCH statement;
6. the non-MATCH config probe `... LIMIT 1` is allowed;
7. any `evidence_id` in the selected `ORDER BY` clause is rejected;
8. missing/extra MATCH, missing locator/source key, old revision-1 order, or extra score statement
   is rejected; and
9. a hostile trace containing sentinel query/path/opaque-ID text cannot surface those values in
   the rendered stable failure.

### Step 5 — Chinese narrow GREEN

Change only `_valid_rank_sql_trace` and minimal private helpers in `chinese_runner.py`.

The validator filters the two MATCH statements, validates their structural substrings explicitly,
and ignores non-MATCH statements for ordering proof. It does not execute SQL, parse arbitrary
input, log raw statements, or alter `SQLiteStore.observe_fts5_rank`.

### Step 6 — Workflow-test authority cleanup

Keep the live tests that assert:

- `strategy_revision == 2`;
- `query_policy_revision == 1`;
- development observation is passed; and
- the internal current CLI returns exit 0 with redacted stable output.

Replace the three stale live revision-1/failure assertions with an immutable-record test over:

- `benchmarks/retrieval/retrieval-order-v1-current-runtime-observation.json`.

That test validates the recorded pre-maintenance failure's schema, revision 1, failed order status,
stable public problem/cause/next-step fields, privacy boundary, and exact post-Task-2 immutable
hash. It must not replay the current runtime and claim revision 1.

### Step 7 — Task 6R verification

Run focused:

```bash
uv run pytest -q \
  tests/evaluation/test_numeric_comparison.py \
  tests/evaluation/test_numeric_fixture_corpus.py \
  tests/evaluation/test_chinese_runner.py \
  tests/evaluation/test_retrieval_order_workflow.py \
  tests/evaluation/test_retrieval_order_historical_freeze.py
```

Run adjacent families expected to be current-compatible after the trace repair:

```bash
uv run pytest -q \
  tests/evaluation/test_baseline.py \
  tests/evaluation/test_chinese_artifact.py \
  tests/evaluation/test_cjk_lexical_artifact.py \
  tests/evaluation/test_dense_artifact.py \
  tests/evaluation/test_hybrid_rrf_artifact.py \
  tests/evaluation/test_relevance_gate_artifact.py
```

Run the numeric artifact current path separately and require the known source-lock failure to
remain until Task 7A. Any different problem/cause is a STOP.

Then run Ruff on the seven code/test paths, canonical Pyright, `git diff --check`, the original 13
frozen SHA checks plus the exact post-Task-2 observation hash, and exact scope inspection.

Expected scope:

```text
no runtime retrieval diff
no historical artifact/protocol diff
no Task 7 compatibility module/test/artifact
no development freeze
no holdout receipt/artifact
```

### Step 8 — Commit and review

Commit the eight allowed paths with:

```bash
git commit -m "fix(eval): separate historical replay authority"
```

The worktree must be clean. Return the actual code diff for authority review. Only a clean review
authorizes Task 7A.

## Task 7A — Implement Compatibility Without Canonical Publication

### Allowed paths

Create:

- `src/mke/evaluation/_atomic_json_publication.py`
- `src/mke/evaluation/retrieval_order_compatibility.py`
- `tests/evaluation/test_atomic_json_publication.py`
- `tests/evaluation/test_retrieval_order_compatibility.py`

Modify:

- `tests/evaluation/test_numeric_artifact.py`

Do not create:

- `benchmarks/retrieval/retrieval-order-v2-compatibility.json`.

### Step 1 — Freeze family evidence capabilities

Before any current replay, produce a typed family-adapter table with:

```text
family
recorded_order_projection
recorded_exact_score = direct | derived_from_recorded_parent | not_recorded
historical_runtime_profile
historical_source_tree_resolved
tie_group_authority
allowed_delta
```

E1 and E2 do not record exact ranking score hex in their checked-in artifacts. Their capability is
therefore frozen before any current replay as:

```text
deterministic_historical_subprocess_replay
```

The verified local authority is:

```text
source path: eea3d51c36c0b3b845b8efb60eff553ddc200b88:src/mke
source tree object: 30c0a65e265ce0342462ffc44c2c4fe799f959b5
recorded source identity: c3cec8853547fd09d8fad10865666ce2bb1a507afe19a066a364ab2424064665
runtime: Python 3.13.12 / SQLite 3.51.1 / PyMuPDF 1.27.2.3
```

Do not use an artifact `evaluation_commit` field as a source-snapshot pointer. Materialize only the
artifact's exact recorded `src/mke` file list from the verified tree object into an isolated
temporary root, require every path/blob/digest to match the frozen source identity, and import no
unrecorded package file. Execute twice in fresh subprocesses with a sanitized environment,
checkout-external cwd, `PYTHONNOUSERSITE=1`, cleared inherited `PYTHONPATH`/`PYTHONHOME`, a new
`PYTHONPATH` containing only the materialized historical root, and the exact recorded runtime.
Resolve the interpreter from the existing project environment only; do not download, install, or
guess one. Before replay, the subprocess reports and the controller verifies:

- `sys.version_info[:3] == (3, 13, 12)`, `sqlite3.sqlite_version == "3.51.1"`, and
  `fitz.VersionBind == "1.27.2.3"`; complete `sys.version` is informational only because the
  immutable artifacts do not record compiler/build text;
- `mke` module origins under the materialized historical root;
- stdlib and PyMuPDF origins under the selected interpreter environment, never the current
  checkout or user site; and
- copied protocol/manifest/fixture paths and digests against immutable inputs.

The only child form is `python -B -P -c <hashed-bootstrap>`. Tests freeze the bootstrap digest,
the exact 107 recorded Python blobs, the checkout-external cwd/environment, module and third-party
origins, and two byte-identical stdout payloads. Both fresh runs must produce byte-identical
score-hex and tie-group output. The E1/E2 capability is fixed from this replay or downgraded before
any current replay starts.

If a blob is absent, a recorded path/digest differs, the runtime profile cannot be reproduced, or
the two historical replays differ, E1 and E2 both mechanically downgrade to
`no_ordered_delta_authority` before any current replay. Current output may not influence this
choice. Under that capability, any ordered-projection difference is a STOP. Never encode unknown
scores as zero, infer historical ties from current scores, fetch history, create a branch, modify
the retained worktree, or hand-label ties afterward.

Where a child artifact derives scores from an immutable parent, the adapter must validate the
parent path/hash and the exact derivation before using `derived_from_recorded_parent`.

### Step 2 — Differential RED

Require each inventoried family to expose:

```text
historical artifact/protocol path + frozen SHA
archived self-consistency status
current source identity
runtime profile
preidentified exact-score tie groups
before/after stable projections
membership delta
score-hex delta
non-tied pair delta
metric delta
gate delta
verdict delta
```

Only a permutation wholly inside a tie group mechanically derived from immutable evidence before
current replay is allowed.

### Step 3 — Explicit current replay

- E1/E3 families use their existing model-free runners and frozen inputs.
- E2 numeric uses the explicit archived loader for the recorded lock and binds current source
  identity separately. The default live loader/public CLI remains strict.
- Current SQLite schema must still equal the protocol's frozen schema hash.
- E3-B retains its evaluation-only revision-1 scorer.
- No embedding model is loaded; no historical scorer or artifact is rewritten.

Use typed family adapters with a shared result contract. Do not build one permissive family
`if/elif` chain that silently omits unsupported fields.

### Step 4 — Repair numeric test scaffolding

`tests/evaluation/test_numeric_artifact.py` currently uses the stale checked-in protocol as a
live-recording fixture. Change only test scaffolding so dynamic record/validate tests operate on a
temporary current-compatible protocol or the explicit compatibility path, while preserving:

- a test that default live validation rejects source mutation;
- artifact-field, nested-schema, gate, environment, and privacy tamper tests; and
- the checked-in historical artifact/protocol byte freeze.

Do not weaken `numeric_artifact.py` production defaults merely to make tests green.

### Step 5 — Freeze the internal record and publication interfaces

The compatibility module exposes an internal maintainer CLI only:

```bash
uv run python -m mke.evaluation.retrieval_order_compatibility record \
  --protocol tests/fixtures/retrieval-order-v1/protocol.json \
  --artifact <output.json> \
  --repository .

uv run python -m mke.evaluation.retrieval_order_compatibility validate \
  --protocol tests/fixtures/retrieval-order-v1/protocol.json \
  --artifact <output.json> \
  --repository .
```

Valid `--json` output is one redacted JSON object with empty stderr. Success exits 0, integrity or
proof failure exits 1, and usage exits 2. No `mke eval` command or public package export is added.

`record` is temporary-only. It must reject the resolved canonical repository path
`benchmarks/retrieval/retrieval-order-v2-compatibility.json` before any corpus open or replay.
Canonical publication is not an alias of this command; Task 8R uses the separately gated
`record-canonical` interface.

The temporary `record` path builds and validates completely in memory, then uses the private
shared publication helper. Task 8A integrates `record-canonical` with synthetic receipt/artifact
authority before the candidate seal; Task 8R may invoke that already-tested path but may not first
implement or repair it. The helper:

1. exclusive-creates a temporary file in the destination directory;
2. writes the complete canonical bytes, flushes, file-`fsync`s, reads back, reparses, and verifies
   the exact digest;
3. atomically publishes without replacement using a same-directory hard-link or native
   no-replace rename; it must not use check-then-rename;
4. directory-`fsync`s after publication; and
5. removes only its private temporary name.

The final path must be either absent or contain the complete validated bytes; partial authority is
forbidden. A preexisting destination returns exit 1 and leaves bytes unchanged. Publication
failure returns a stable redacted error; if the no-replace publication already made the final path
visible, the complete bytes are retained and canonical retry is still forbidden. Its typed result
uses two independent dimensions:

```text
output_state =
  absent | complete_preexisting | complete_visible | not_applicable

publication_outcome =
  not_attempted | published | failed_before_visibility | durability_unconfirmed
```

`output_state=complete_visible` plus `publication_outcome=durability_unconfirmed` is a terminal
publication failure, not success. Every failure path freezes one exact pair. The read-only
`validate` command may prove complete bytes/schema/digests but cannot upgrade a terminal outcome
or authorize retry.

Task 8A must reuse this exact helper for development freeze, holdout receipt, and retrieval-order
artifact. Task 8R uses it for canonical compatibility. No second writer or fallback publication
path is allowed.

### Step 6 — Temporary artifact proof

Build and validate compatibility under `tmp_path` only. Add deterministic repeated-build equality
and tamper tests for source identity, tie-group classification, membership, score, order, metrics,
gates, verdict, runtime profile, artifact hashes, preexisting output, partial-build failure, and
redaction. Fault-inject write, file-`fsync`, readback, no-replace race, and directory-`fsync`
failure. Every case must leave the final path absent or byte-exact and complete.

Also test temporary `record` rejection of the canonical path before replay, stable result fields,
and read-only `validate` behavior. No repository benchmark path is written.

### Step 7 — Historical matrix

Run:

```bash
uv run pytest -q \
  tests/evaluation/test_baseline.py \
  tests/evaluation/test_numeric_artifact.py \
  tests/evaluation/test_chinese_artifact.py \
  tests/evaluation/test_cjk_lexical_artifact.py \
  tests/evaluation/test_dense_artifact.py \
  tests/evaluation/test_hybrid_rrf_artifact.py \
  tests/evaluation/test_relevance_gate_artifact.py \
  tests/evaluation/test_retrieval_order_historical_freeze.py \
  tests/evaluation/test_atomic_json_publication.py \
  tests/evaluation/test_retrieval_order_compatibility.py
```

Expected: all 133 original historical tests plus the new compatibility tests pass. Recompute the
14-entry immutable input map. The freeze test must assert the exact 14 paths, every digest, and
canonical sorted serialization; a count-only assertion is insufficient. The post-Task-2 current
runtime observation remains item 14 and is not relabeled as Task 0 evidence.

Run focused runtime retrieval/order/cursor/interface/schema tests, Ruff, Pyright, and
`git diff --check`.

### Step 8 — Commit and review

Commit only the compatibility module, shared publication helper, and the three test paths:

```bash
git commit -m "test(eval): prepare retrieval order compatibility"
```

No canonical JSON is included. Return the actual Task 7A diff for authority review before Task 8.

## Task 8A — Complete Candidate Source

Task 8A completes every remaining source, test, script, ADR, how-to, and public-doc write before
observation.

### Step 1 — Workflow and artifact state machine

Create/modify the original Task 8 paths:

- `src/mke/evaluation/retrieval_order_artifact.py`
- `src/mke/evaluation/retrieval_order_protocol.py`
- `src/mke/evaluation/retrieval_order_workflow.py`
- `src/mke/evaluation/retrieval_order_compatibility.py`
- `tests/evaluation/test_retrieval_order_artifact.py`
- `tests/evaluation/test_retrieval_order_protocol.py`
- `tests/evaluation/test_retrieval_order_workflow.py`
- `tests/evaluation/test_retrieval_order_compatibility.py`

Implement atomic no-replace development freeze, pre-observation holdout receipt, no retry, exact
candidate HEAD/profile binding, redacted JSON, and tamper rejection by reusing
`_atomic_json_publication.py`.

All state-machine tests that invoke a holdout partition must use a `tmp_path` synthetic protocol,
manifests, and fixture bytes whose hashes all differ from the canonical holdout. Copied retry
tests must also use synthetic bytes.

Static scanning is supplemental only. Add a runtime authority gate before any fixture open:

- every call with `partition="holdout"` requires a typed capability, regardless of protocol path,
  serialization, alias, helper, symlink, or direct Python entry point;
- only the `holdout` command may create that capability, after the complete holdout receipt has
  been atomically published;
- the production capability binds the canonical protocol and holdout-fixture digests, receipt
  path/digest, candidate HEAD/profile, and one-use state;
- the observer consumes it once and rejects direct, pre-receipt, mismatched, and second calls
  before fixture bytes are opened; and
- tests use a separate `SyntheticHoldoutCapability`, created only after proving every referenced
  fixture digest differs from every canonical holdout fixture digest.

Split protocol loading into a metadata-only preflight and a partition-lazy loader. Metadata
preflight validates protocol structure and partition metadata without opening development or
holdout fixture files. Development loads only development bytes. A holdout call validates and
consumes its typed capability before loading only holdout bytes. Rejection therefore happens
before any fixture read, including copied/reserialized protocol, alias/helper/direct-call,
symlink, mixed-canonical-fixture, and second-call cases.

Add fixture-open spies for every rejection. Also add a guard test and static check proving no test
module invokes:

```text
canonical tests/fixtures/retrieval-order-v1/protocol.json
+ partition="holdout"
```

before or after the canonical observation. The explicit Task 8B command plus its published receipt
is the only canonical capability issuer.

Complete the `record-canonical` implementation and wiring in this pre-seal task. Its production
capability requires the successful holdout receipt/artifact and exact candidate-seal inputs.
Synthetic-repository tests cover success, missing receipt, failed holdout, candidate-seal
mismatch, repeated invocation, and every no-replace publication fault. These tests use synthetic
receipts/artifacts and never open the canonical holdout. Task 8R is invocation-only: any
interface, serialization, or integration defect found there is a terminal STOP, not authority to
modify source.

`record-canonical` also owns a durable no-replace attempt receipt at
`benchmarks/retrieval/retrieval-order-v2-compatibility-attempt.json`. After bounded path, schema,
digest, candidate-seal, and successful-holdout preflight but before archive or current replay, it
publishes canonical attempt bytes binding:

```text
command_schema
candidate_seal
protocol_digest
development_freeze_digest
holdout_receipt_digest
retrieval_artifact_digest
compatibility_target
```

Only the process that successfully creates those bytes may derive the canonical-publication
capability. If the attempt receipt already exists, the command returns
`retrieval_order_canonical_publication_already_started` even when the compatibility artifact is
absent. Every later replay, build, validation, or directory-`fsync` failure retains the attempt
receipt and permanently closes canonical retry. The compatibility artifact cross-binds the exact
attempt-receipt digest.

Use the shared atomic publication helper for the development freeze, holdout receipt, and final
retrieval-order artifact. Inject the same write/`fsync`/readback/no-replace/directory-`fsync`
failures at workflow boundaries and require absent-or-complete final bytes.

Artifact and compatibility validators are pure read-only paths. They may read canonical bytes,
schema, digests, frozen fixture hashes, and cross-bindings, but they never call
`observe_retrieval_order_partition` or any ranking/retrieval runner. Add call-counter tests around
every post-holdout validator by monkeypatching the observer and requiring zero canonical calls.
Synthetic holdout calls are counted separately. Do not add a mutable global counter or new
test-only persistence.

Run focused tests, Ruff, Pyright, and `git diff --check`, then commit:

```bash
git commit -m "feat(eval): validate deterministic retrieval order"
```

This is not yet the candidate seal.

### Step 2 — Installed proof and documentation before observation

Complete every original Task 9 write:

- `scripts/retrieval_order_installed_proof.py`
- `tests/scripts/test_retrieval_order_installed_proof.py`
- `scripts/consumer_source_pack_proof.py`
- `tests/scripts/test_consumer_source_pack_proof.py`
- `docs/decisions/0012-deterministic-retrieval-order.md`
- `docs/how-to/run-deterministic-retrieval-order-proof.md`
- `tests/evaluation/test_retrieval_order_documentation.py`
- `docs/explanation/architecture.md`
- `docs/reference/contracts.md`
- `docs/reference/mcp-contract.md`
- `docs/reference/cli.md`
- `docs/how-to/use-mke-mcp.md`
- `docs/how-to/enable-cjk-retrieval.md`
- `docs/README.md`

Installed-proof tests use synthetic temporary proof artifacts and the same-wheel external-store
contract. They do not open the canonical holdout. Documentation describes commands, contracts,
recovery, cursor semantics, tie-only compatibility, and non-claims; it does not predict or record
an unobserved pass.

`retrieval_order_installed_proof.py` must accept an explicit prebuilt candidate wheel for Task 8R,
validate its metadata and sealed-source receipt, and never rebuild when that input is supplied. Its
frozen Task 8R input contract is:

```text
--mke-wheel <exact path from candidate receipt>
--candidate-receipt <candidate-artifact-receipt.json>
--protocol <copied protocol>
--development-freeze <copied freeze>
--holdout-receipt <copied receipt>
--artifact <copied retrieval-order artifact>
--compatibility <copied compatibility artifact>
```

Paths must be explicit; globbing, “first wheel in directory”, and implicit sibling discovery are
forbidden. Tests reject zero/multiple wheels, a wrong wheel, a wheel/receipt SHA mismatch, a
candidate-seal mismatch, and an attempted silent rebuild.

Add a Task-8R-only `--attempt-claim <external-json>` option to
`consumer_source_pack_proof.py`. After bounded argument/interpreter/source preflight but before
any build or child interpreter, the controller uses the reviewed no-replace publication helper to
write a complete claim binding the sealed SHA, exact normalized command, both interpreter paths,
candidate-output path, script digest, and command schema. A preexisting claim returns
`retrieval_order_source_pack_already_started`; any later failure retains the claim. Preserve
existing invocations that omit this option, but only the invocation carrying real interpreters,
`--candidate-output`, and `--attempt-claim` qualifies as the Task 8R source-pack proof. Tests cover
claim creation ordering, preexistence, every publication fault, post-claim build failure, and no
second real invocation.

Freeze `--help` tests for the internal compatibility, retrieval-order proof, and source-pack
attempt-claim options. Help and the how-to must say:

```text
archive validation -> historical bytes are self-consistent only
current replay -> current runtime compatibility only
differential validation -> revision-2 comparison only
temporary output -> never canonical authority
```

The how-to gives one fast-preflight-to-expensive-proof command order.

The how-to and tests also freeze this command-to-authority mapping:

| Command | Authority and expected boundary |
|---|---|
| `mke eval retrieval-numeric` | strict live authority; a stale checked-in lock exits 1 with the existing `retrieval_numeric_fixture_invalid` contract |
| `retrieval_order_compatibility record` | archive self-consistency + current replay + differential; temporary/noncanonical only |
| `retrieval_order_compatibility validate` | pure read-only validation of an existing artifact's archive/current/differential/canonical states |
| `retrieval_order_compatibility record-canonical` | one-shot publication only after successful holdout and candidate seal |

The three internal compatibility modes use exact, independently frozen result schemas:

```text
mke.retrieval_order_compatibility_record_result.v1
mke.retrieval_order_compatibility_validate_result.v1
mke.retrieval_order_compatibility_record_canonical_result.v1
```

Tests freeze required field types, success/failure values, finite
`problem`/`cause`/`next_step` combinations, exit 0/1/2 behavior, and help wording. The strict live
command's expected stale-lock failure is not a compatibility-closure failure.

Run focused installed-proof/documentation tests and all documentation contract tests, then commit:

```bash
git commit -m "docs(retrieval): prepare deterministic order proof"
```

### Step 3 — Pre-observation candidate verification

Run:

- focused retrieval-order protocol/workflow/artifact tests;
- Task 7A compatibility tests using temporary output;
- the full 133-test historical matrix;
- the runtime capability tests and supplemental guard proving no canonical holdout replay in the
  test suite;
- the full test suite;
- Ruff;
- Pyright;
- build and CI-parity commands;
- installed-proof tests with synthetic artifacts;
- consumer source-pack and compiled-export tests that do not consume canonical holdout; and
- `tests/evaluation/test_retrieval_order_historical_freeze.py`, requiring the exact 14 paths,
  digests, and canonical sorted serialization.

Do not run the canonical same-wheel installed proof yet because its canonical retrieval-order
artifact does not exist.

Verify a clean worktree. The final clean HEAD after all Task 8A commits is the unique candidate
source/test/doc seal. Record its SHA. No source, test, script, ADR, how-to, or doc may change after
this point; any needed change invalidates uncommitted observation evidence and returns to
authority review.

## Plan Amendment D+ — Layered Strict-Live and Compatibility CI Authority

This amendment was approved after the first Task 8A Step 3 CI-parity stop. The stop proved a
contract contradiction rather than a new retrieval defect:

- the existing CI step allowed the strict-live numeric command to exit `0` or `1`, but then
  required `integrity_status=passed`;
- the approved strict-live contract requires the frozen revision-1 source lock to exit `1` with
  the existing source-identity failure after revision-2 source changes; and
- the same step incorrectly attempted to validate that failed live observation against the
  immutable historical numeric artifact.

The correction is a layered CI authority gate, not a historical refresh, fallback, waiver, or
promotion. It preserves two independent claims:

```text
strict-live negative control
  -> the frozen revision-1 lock is rejected as current authority

temporary compatibility positive control
  -> archived bytes are self-consistent
  -> current runtime replay remains compatible
  -> only the approved revision-2 differential is admitted
  -> temporary output never becomes canonical authority
```

This amendment supersedes only Task 8A CI-parity routing and the exact Task 8A modification scope
needed to express that routing. Tasks 8B, 7B/8R, canonical publication, holdout, promotion, runtime
retrieval, historical artifact bytes, and every other plan boundary remain unchanged.

### D0 — Plan-only landing and authority gate

Land this amendment as a plan-only commit and stop. Do not modify CI, tests, source, scripts,
artifacts, fixtures, or documentation in the same commit. Resume only after review of the actual
plan diff.

### D1 — Exact Task 8A repair scope

After the plan diff is review-clean, modify exactly:

- `.github/workflows/ci.yml`
- `tests/evaluation/test_retrieval_order_documentation.py`

The two existing Task 8A commits remain retained. Do not amend or rewrite them. Commit the bounded
repair separately:

```bash
git commit -m "ci(eval): reconcile strict-live retrieval parity"
```

Do not change workflow triggers, job topology, permissions, action pins, Python matrix,
`prune-cache`, dependency installation, or any other CI step. Do not modify a runtime,
evaluation module, historical protocol/artifact, canonical JSON, fixture, ADR, how-to, proof
script, dependency, schema, or public product contract.

### D2 — TDD contract

First extend `test_retrieval_order_documentation.py` so the current workflow is RED because it:

- accepts strict-live exit `0`;
- does not assert the exact expected failure tuple;
- invokes `numeric_artifact validate` on a failed live observation; and
- lacks the temporary compatibility record/validate lane.

The test must freeze the exact CI step name and both authority lanes without treating generic
workflow text as proof. It must also prove that the temporary destination is under
`$RUNNER_TEMP`, is not any canonical benchmark path, and that the persistent CI contract preserves
preexisting canonical path state rather than requiring canonical files to remain absent forever.

### D3 — Strict-live negative control

Rename the numeric step so its name explicitly distinguishes archived-lock rejection from current
compatibility validation.

Run the existing command unchanged:

```bash
uv run mke eval retrieval-numeric \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --json
```

Require exact exit `1`; exit `0`, exit `2`, or any other exit fails the CI step. Parse the bounded
JSON and require:

```text
integrity_status = failed
candidate_status = not_recorded
exactly one integrity failure
problem   = retrieval_numeric_fixture_invalid
cause     = protocol-bound input identity mismatch
next_step = restore_numeric_protocol_inputs
subject_id = null
```

Do not run `mke.evaluation.numeric_artifact validate` against this failed observation. This lane
proves that archived revision-1 source identity cannot silently become current authority; it does
not claim that retrieval runtime, compatibility, or candidate quality failed.

### D4 — Temporary compatibility positive control

Only after the strict-live negative control passes, use a new no-replace destination under
`$RUNNER_TEMP` and run:

```bash
uv run python -m mke.evaluation.retrieval_order_compatibility record \
  --protocol tests/fixtures/retrieval-order-v1/protocol.json \
  --artifact "$TEMPORARY_COMPATIBILITY_JSON" \
  --repository . --json

uv run python -m mke.evaluation.retrieval_order_compatibility validate \
  --protocol tests/fixtures/retrieval-order-v1/protocol.json \
  --artifact "$TEMPORARY_COMPATIBILITY_JSON" \
  --repository . --json
```

Require exit `0` for both commands. Freeze the exact record result:

```text
schema_version = mke.retrieval_order_compatibility_record_result.v1
status = passed
mode = record
authority_layer = archive_current_differential
canonical = false
output_state = complete_visible
publication_outcome = published
problem/cause/next_step/first_failed_gate = none
historical_revision = 1
current_revision = 2
```

Freeze the exact validate result:

```text
schema_version = mke.retrieval_order_compatibility_validate_result.v1
status = passed
mode = validate
authority_layer = artifact_validation
canonical = false
output_state = complete_preexisting
publication_outcome = not_attempted
problem/cause/next_step/first_failed_gate = none
historical_revision = 1
current_revision = 2
```

Read the temporary artifact and require:

- `integrity_status=passed`;
- `compatibility_status=passed`;
- exactly seven frozen family names;
- every membership, score-hex, non-tied-pair, metric, gate, and verdict delta is zero;
- limitations remain exactly historical compatibility, tie-permutation-only,
  no-relevance-improvement, no-runtime-promotion, and public-holdout-not-observed; and
- `historical_capability.status` is one of the validator-authorized states. A runtime-profile
  mismatch may select the stricter `no_ordered_delta_authority`; it never authorizes a previously
  unproved tie permutation.

Before the temporary record, snapshot the existence and SHA-256 of all five canonical paths. After
pure validation, require the exact same existence and bytes:

```text
benchmarks/retrieval/retrieval-order-v1-development-freeze.json
benchmarks/retrieval/retrieval-order-v1-holdout-receipt.json
benchmarks/retrieval/retrieval-order-v1-artifact.json
benchmarks/retrieval/retrieval-order-v2-compatibility-attempt.json
benchmarks/retrieval/retrieval-order-v2-compatibility.json
```

For the current Task 8A candidate all five paths must additionally remain absent. The persistent CI
guard uses unchanged-before/after semantics so the same workflow remains valid after a separately
authorized Task 8B/7B/8R later commits canonical evidence.

### D5 — Focused and complete verification

Run the documentation RED/GREEN test plus adjacent workflow/source-identity contracts, including:

- `tests/evaluation/test_retrieval_order_documentation.py`
- `tests/evaluation/test_github_actions_dependencies.py`
- `tests/evaluation/test_dense_documentation.py`
- `tests/evaluation/test_dense_artifact.py`
- `tests/scripts/test_compiled_library_export_proof.py`

Then rerun the complete Task 8A Step 3 from the final repair HEAD and capture the real exit and
summary for the full suite. Run the amended CI-parity block exactly as committed. The final clean
HEAD after this commit and all successful Task 8A gates becomes the replacement candidate seal.

Task 8B remains forbidden. Do not run development, holdout, canonical compatibility,
canonical installed proof, source-pack attempt, push, PR, merge, release, deployment, promotion,
or cleanup.

If the bounded two-file repair or the full rerun reveals any new authority conflict outside this
exact known stale-lock routing problem, stop. Do not add another fallback, refresh a historical
artifact, widen source identity, modify another file, or create a further amendment without a new
authority decision.

### D6 — Long-term lifecycle and non-claims

The strict-live negative lane may be removed only by a separately approved maintenance change
after either:

1. a revisioned current strict-live numeric protocol is independently designed, frozen, and
   landed; or
2. every revision-1 numeric consumer and CI obligation is explicitly retired.

The revision-1 historical lock and artifact are never refreshed merely to make strict-live green.
This amendment does not redesign evaluation source identity. Any future move from broad
whole-source identity to a minimal dependency manifest is a separate maintenance decision with
its own regression evidence.

A green two-lane CI step proves exact rejection of stale live authority plus bounded
archive/current/differential compatibility on the tested runtime matrix. It does not prove
retrieval-quality improvement, segmentation or contextual-retrieval value, production readiness,
runtime promotion, broad portability, accuracy, latency, SLA, adoption, or release status.

## Plan Amendment E — Final Candidate Regression Reconciliation

This amendment was approved after the Plan Amendment D+ repair reached the complete-suite gate.
The two-file D1 repair is retained at commit
`74390b1c07914c9716e0bcd6becad3a2f7037b8a`, but the candidate is not sealed:

- the D1 actual-diff review found that the persistent CI step incorrectly requires all five
  canonical retrieval-order files to remain absent forever, although D+ requires unchanged
  before/after state so the workflow remains valid after separately authorized canonical
  publication;
- the complete suite returned 9 failures, 3371 passes, 14 skips, and 5 warnings;
- one failure is an omitted historical-protocol test migration already required by Task 1;
- two failures are stale CLI success expectations that contradict the approved strict-live
  revision-1 rejection contract; and
- six failures share one Task 8A proof implementation defect:
  `ProofConfig.command_timeout` does not exist and the frozen field is
  `ProofConfig.command_timeout_seconds`.

These are four bounded pre-seal reconciliation items. They are not evidence of a retrieval-quality
regression and do not authorize a historical refresh, runtime change, validator relaxation,
fallback, observation, promotion, or publication.

This amendment supersedes only:

1. D1/D4's implementation of persistent canonical-path state preservation;
2. the incomplete Task 1 migration of `test_hybrid_rrf_protocol.py`;
3. the two stale strict-live numeric CLI success assertions; and
4. the Task 8A source-pack attempt-claim timeout-field typo.

Every other design, plan, D+, Task 8A, Task 8B, 7B/8R, historical-freeze, candidate-seal,
one-shot, proof, publication, and non-claim boundary remains unchanged.

### E0 — Plan-only landing and authority gate

Starting from clean branch `codex/deterministic-retrieval-order-maintenance` at exact HEAD
`74390b1c07914c9716e0bcd6becad3a2f7037b8a`, append this amendment to the existing implementation
plan immediately after Plan Amendment D+ and before Task 8B.

Modify exactly:

- `docs/superpowers/plans/2026-07-26-deterministic-retrieval-order-maintenance-implementation.md`

Do not modify CI, source, tests, scripts, fixtures, artifacts, ADRs, how-to documents, or any other
path in E0. Do not run tests, evaluation, proof, observation, or publication commands.

Commit:

```bash
git add docs/superpowers/plans/2026-07-26-deterministic-retrieval-order-maintenance-implementation.md
git commit -m "docs(plan): reconcile candidate regression gates"
```

Verify one changed path, one new commit, exact inserted-block bytes, `git diff --check`, public
neutrality, unchanged design-spec bytes, all five canonical paths absent, and a clean worktree.
Then stop for review of the actual plan diff. Do not enter E1 before that review is clean.

### E1 — Preserve canonical state without permanent absence

**Files:**

- Modify: `.github/workflows/ci.yml`
- Modify: `tests/evaluation/test_retrieval_order_documentation.py`

**Authority boundary:**

The persistent CI step owns only unchanged-before/after existence and SHA-256 state. The current
Task 8A controller separately owns the candidate-specific fact that all five canonical paths are
absent. Do not encode that temporary candidate fact as a permanent workflow requirement.

- [ ] **Step 1: Write the focused RED**

In `test_numeric_ci_step_preserves_all_canonical_paths`, retain assertions for:

```text
canonical_state_before
canonical_state_after
assert canonical_state_before == canonical_state_after
each of the five canonical paths exactly once
```

Replace the assertions that require these strings to be present:

```text
assert all(value is None for value in canonical_state_before.values())
assert all(value is None for value in canonical_state_after.values())
```

with assertions that both strings are absent from the named numeric CI step. Keep the test scoped
to `_numeric_ci_step()`; generic workflow text is not proof.

- [ ] **Step 2: Run the RED**

Run:

```bash
uv run pytest -q \
  tests/evaluation/test_retrieval_order_documentation.py::test_numeric_ci_step_preserves_all_canonical_paths
```

Expected: fail because the committed workflow still contains the permanent absence assertions.

- [ ] **Step 3: Make the minimal workflow repair**

In the named step
`Reject archived numeric lock and validate current retrieval-order compatibility`, remove only:

```python
assert all(value is None for value in canonical_state_before.values())
assert all(value is None for value in canonical_state_after.values())
```

Do not alter the five-path inventory, before-state serialization, after-state hashing, exact
before/after equality, strict-live negative lane, temporary compatibility lane, result schemas,
family/differential assertions, workflow triggers, job topology, permissions, action pins, Python
matrix, `prune-cache`, dependency installation, or any unrelated step.

- [ ] **Step 4: Run focused GREEN and adjacent contracts**

Run:

```bash
uv run pytest -q \
  tests/evaluation/test_retrieval_order_documentation.py \
  tests/evaluation/test_github_actions_dependencies.py \
  tests/evaluation/test_dense_documentation.py \
  tests/evaluation/test_dense_artifact.py \
  tests/scripts/test_compiled_library_export_proof.py
```

Expected: pass.

- [ ] **Step 5: Verify current-candidate absence outside persistent CI**

Run this controller preflight from the repository root:

```bash
for path in \
  benchmarks/retrieval/retrieval-order-v1-development-freeze.json \
  benchmarks/retrieval/retrieval-order-v1-holdout-receipt.json \
  benchmarks/retrieval/retrieval-order-v1-artifact.json \
  benchmarks/retrieval/retrieval-order-v2-compatibility-attempt.json \
  benchmarks/retrieval/retrieval-order-v2-compatibility.json
do
  test ! -e "$path"
done
```

This command is an execution gate, not committed workflow content.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/ci.yml \
  tests/evaluation/test_retrieval_order_documentation.py
git commit -m "fix(ci): preserve canonical retrieval evidence"
```

### E2 — Align archived protocol and strict-live CLI tests

**Files:**

- Modify: `tests/evaluation/test_hybrid_rrf_protocol.py`
- Modify: `tests/interfaces/test_cli_evaluation.py`

Do not modify `src/mke/evaluation/hybrid_rrf_protocol.py`, `src/mke/cli.py`, any protocol or
artifact bytes, or any runtime source.

- [ ] **Step 1: Reproduce the three authority REDs**

Run:

```bash
uv run pytest -q \
  tests/evaluation/test_hybrid_rrf_protocol.py::test_protocol_lock_is_byte_stable \
  tests/interfaces/test_cli_evaluation.py::test_cli_eval_numeric_outputs_passing_json \
  tests/interfaces/test_cli_evaluation.py::test_cli_eval_numeric_outputs_human_status_first
```

Expected: exactly three failures:

```text
HybridRrfProtocolError: input identity drift
numeric JSON CLI expected exit 0 but returned exit 1
numeric human CLI expected exit 0 but returned exit 1
```

- [ ] **Step 2: Bind historical RRF tests to recorded authority**

In `test_hybrid_rrf_protocol.py`:

1. import `load_hybrid_rrf_protocol_lock`;
2. define the exact checked-in protocol path;
3. add a helper that loads that checked-in protocol with `repository_root=ROOT`;
4. change `test_protocol_lock_is_byte_stable` to load the recorded protocol, validate it through
   the production loader, render it, require a trailing newline, require parsed equality, and
   require rendered UTF-8 bytes to equal the checked-in file bytes exactly;
5. keep `test_protocol_freezes_candidate_rrf_arms_and_inputs` on
   `build_hybrid_rrf_protocol_lock` so the current-source builder contract remains covered; and
6. change every validator rejection test to begin from a deep copy of the loaded recorded
   protocol, not the current-source builder, so path, identity, candidate, revision, and locator
   mutations cannot pass through unrelated current-source drift.

The historical validator continues to prove recorded bytes and schema. The current-source builder
continues to exist only for a new record or revision-2 compatibility construction.

- [ ] **Step 3: Freeze the exact strict-live numeric CLI failure**

In `test_cli_evaluation.py`, replace only the two stale success tests and rename them exactly:

```text
test_cli_eval_numeric_outputs_exact_stale_lock_json
test_cli_eval_numeric_outputs_exact_stale_lock_human_status
```

- JSON mode requires exit `1`, empty stderr, schema
  `mke.retrieval_numeric_comparison.v1`, `protocol_id=unknown`,
  `candidate_id=numeric-grouping-v1`, revision `1`, `integrity_status=failed`,
  `candidate_status=not_recorded`, no gates, and exactly one integrity failure:

  ```text
  problem   = retrieval_numeric_fixture_invalid
  cause     = protocol-bound input identity mismatch
  next_step = restore_numeric_protocol_inputs
  subject_id = null
  ```

- human mode requires exit `1` and exact ordered lines:

  ```text
  mke eval retrieval-numeric
  protocol=unknown candidate=numeric-grouping-v1 revision=1
  integrity_status=failed candidate_status=not_recorded
  problem=retrieval_numeric_fixture_invalid cause=protocol-bound_input_identity_mismatch next_step=restore_numeric_protocol_inputs
  ```

Retain path/traceback redaction assertions. Rename the tests to describe the stale-lock result.
Do not change other numeric CLI malformed-input, exception-mapping, help, or rendering tests.

- [ ] **Step 4: Run focused GREEN and complete adjacent files**

Run:

```bash
uv run pytest -q \
  tests/evaluation/test_hybrid_rrf_protocol.py::test_protocol_lock_is_byte_stable \
  tests/interfaces/test_cli_evaluation.py::test_cli_eval_numeric_outputs_exact_stale_lock_json \
  tests/interfaces/test_cli_evaluation.py::test_cli_eval_numeric_outputs_exact_stale_lock_human_status
```

Then run:

```bash
uv run pytest -q \
  tests/evaluation/test_hybrid_rrf_protocol.py \
  tests/interfaces/test_cli_evaluation.py
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add tests/evaluation/test_hybrid_rrf_protocol.py \
  tests/interfaces/test_cli_evaluation.py
git commit -m "test(eval): align archived retrieval authority"
```

### E3 — Bind the source-pack attempt claim to the real timeout field

**Files:**

- Modify: `scripts/consumer_source_pack_proof.py`

The existing source-pack attempt-claim tests are the regression tests. Do not modify their
fixtures, publication faults, expected normalized command, one-shot behavior, schemas, or test
file.

- [ ] **Step 1: Reproduce the six proof REDs**

Run:

```bash
uv run pytest -q \
  tests/scripts/test_consumer_source_pack_proof.py::test_attempt_claim_is_published_before_build_and_retained_on_failure \
  tests/scripts/test_consumer_source_pack_proof.py::test_attempt_claim_publication_fault_never_starts_build
```

Expected: six failures with:

```text
AttributeError: 'ProofConfig' object has no attribute 'command_timeout'
```

- [ ] **Step 2: Make the one-field repair**

In `_publish_task8r_attempt_claim`, change only:

```python
str(config.command_timeout)
```

to:

```python
str(config.command_timeout_seconds)
```

Do not add an alias or second field. Do not change `ProofConfig`, CLI flags, the normalized-command
schema, publication order, atomic no-replace behavior, candidate seal, interpreter checks, or
output paths.

- [ ] **Step 3: Run focused and complete proof GREEN**

Run:

```bash
uv run pytest -q \
  tests/scripts/test_consumer_source_pack_proof.py::test_attempt_claim_is_published_before_build_and_retained_on_failure \
  tests/scripts/test_consumer_source_pack_proof.py::test_attempt_claim_publication_fault_never_starts_build
```

Then run:

```bash
uv run pytest -q tests/scripts/test_consumer_source_pack_proof.py
uv run ruff check scripts/consumer_source_pack_proof.py \
  tests/scripts/test_consumer_source_pack_proof.py
uv run pyright
```

Expected: pass with Pyright reporting zero errors.

- [ ] **Step 4: Commit**

```bash
git add scripts/consumer_source_pack_proof.py
git commit -m "fix(proof): bind source-pack timeout field"
```

### E4 — Replacement candidate verification

From the final E3 HEAD, rerun the exact nine-failure reproduction set and require zero failures:

```bash
uv run pytest -q --tb=short \
  tests/evaluation/test_hybrid_rrf_protocol.py::test_protocol_lock_is_byte_stable \
  tests/interfaces/test_cli_evaluation.py \
  tests/scripts/test_consumer_source_pack_proof.py
```

Then rerun:

1. the D5 focused workflow/documentation group;
2. the focused retrieval-order protocol/workflow/artifact group;
3. the full historical compatibility matrix;
4. runtime capability and no-canonical-holdout guards;
5. the complete test suite with actual exit code and final summary captured;
6. Ruff;
7. Pyright;
8. build;
9. the amended CI-parity block exactly as committed;
10. synthetic installed-proof tests;
11. eligible consumer source-pack and compiled-export groups;
12. the exact 14 immutable historical hashes;
13. product proof and demo gates required by Task 8A Step 3; and
14. every other Task 8A Step 3 command not reached after the prior full-suite stop.

The core repository commands include:

```bash
uv run pytest -q \
  tests/evaluation/test_retrieval_order_protocol.py \
  tests/evaluation/test_retrieval_order_workflow.py \
  tests/evaluation/test_retrieval_order_artifact.py \
  tests/evaluation/test_retrieval_order_compatibility.py

uv run pytest -q \
  tests/evaluation/test_baseline.py \
  tests/evaluation/test_numeric_artifact.py \
  tests/evaluation/test_chinese_artifact.py \
  tests/evaluation/test_cjk_lexical_artifact.py \
  tests/evaluation/test_dense_artifact.py \
  tests/evaluation/test_hybrid_rrf_artifact.py \
  tests/evaluation/test_relevance_gate_artifact.py \
  tests/evaluation/test_retrieval_order_historical_freeze.py \
  tests/evaluation/test_atomic_json_publication.py \
  tests/evaluation/test_retrieval_order_compatibility.py

uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
```

Run the remaining Task 8A Step 3 CI-parity, installed-proof, consumer, compiled-export,
runtime-capability, and no-canonical-holdout commands from their already frozen command ledger
without substitutions or omissions.

Before the first gate and after the last gate, run the exact E1 five-path absence command and
require all five canonical paths absent. Verify:

- the design-spec digest remains
  `8522af9fc801f1f30518f450ee5e8538efa0d67fe0039352d58b95c52f52b42b`;
- the plan digest matches the reviewed E0 plan;
- the exact 14 historical bytes remain unchanged;
- the implementation repair touches exactly the five paths authorized by E1–E3;
- no canonical observation, receipt, artifact, compatibility, or proof-attempt file exists;
- `git diff --check` passes; and
- the worktree is clean.

The final clean HEAD after every successful Task 8A Step 3 gate becomes the replacement candidate
source/test/doc seal.

If any new failure appears after these four known reconciliation items, stop at the first failing
gate. Do not create Amendment F, expand another path, refresh historical bytes, relax a validator,
change runtime retrieval, add a fallback, retry a canonical action, or continue to Task 8B without
a new architecture-level decision.

### E5 — Stop boundary and non-claims

Task 8B remains forbidden throughout E0–E4. Do not run development, holdout, canonical
compatibility, canonical installed proof, source-pack attempt, push, PR, merge, release,
deployment, promotion, or cleanup.

A green E4 proves only that:

- persistent CI separates temporary compatibility from canonical-state preservation;
- recorded historical protocols are tested as recorded authority;
- strict-live revision-1 numeric rejection is represented consistently in CLI tests and CI;
- the Task 8A source-pack attempt-claim controller uses its frozen timeout field; and
- the replacement candidate passes the repository's pre-observation gates.

It does not prove retrieval-quality improvement, segmentation or contextual-retrieval value,
production readiness, runtime promotion, broad portability, accuracy, latency, SLA, adoption,
release status, or successful canonical observation.

## Plan Amendment F — Close Pre-Observation Authority Gaps

### F+ — Authority, purpose, and precedence

This amendment applies after the replacement candidate sealed by Amendment E. A read-only
authority review found eight pre-observation gaps that can make a one-shot holdout or compatibility
record internally self-consistent without proving that it observed the frozen candidate and the
frozen protocol expectations. Amendment F repairs those gaps before any canonical development,
holdout, compatibility, installed proof, or source-pack attempt is allowed.

This is evaluation-authority maintenance, not a retrieval feature. It does not change normal
Search, Ask, CLI, MCP, ingestion, Run, Publication, Evidence, active-only authority, ranking
scores, retrieval strategy selection, or cursor schemas. It does not add GraphRAG, dense
retrieval, RRF, a reranker, OCR, an Agent loop, HTTP/SaaS, a provider, a dependency, a runtime
fallback, or a promotion path.

The frozen development and holdout partitions are public, nonblind mechanism-regression slices.
The one-shot rule prevents tuning after the first retained observation; it does not make the
holdout blind, independent, representative, or predictive. A passing result remains development
evidence only. Canonical receipts are audit slots rather than availability mechanisms: a visible
failed attempt is never overwritten or retried under the same protocol identity. Any future
campaign would require a separately approved protocol/schema/path rather than an append-only
retry extension in this stage.

Amendment F supersedes only Amendment E's permission to enter Task 8B after E4. Task 8B,
Task 7B, and Task 8R remain forbidden until F1-F6 are complete, the final implementation diff is
authority-review clean under F7, and a separate resume authorization is given. All earlier frozen
historical bytes, Plan Amendments B-E, comparison-only boundaries, one-shot publication rules,
and non-claims remain authoritative unless this amendment explicitly narrows them.

The approved implementation scope is exactly these eleven public paths:

- `src/mke/evaluation/retrieval_order_workflow.py`;
- `tests/evaluation/test_retrieval_order_workflow.py`;
- `src/mke/evaluation/retrieval_order_artifact.py`;
- `tests/evaluation/test_retrieval_order_artifact.py`;
- `src/mke/evaluation/retrieval_order_compatibility.py`;
- `tests/evaluation/test_retrieval_order_compatibility.py`;
- `scripts/consumer_source_pack_proof.py`;
- `tests/scripts/test_consumer_source_pack_proof.py`;
- `docs/decisions/0012-deterministic-retrieval-order.md`;
- `docs/explanation/architecture.md`; and
- `tests/evaluation/test_retrieval_order_documentation.py`.

Do not create a new source module. Reuse the existing evaluation-only candidate-seal mechanism so
that this repair does not expand the frozen `src/mke/**/*.py` inventory again. Do not modify any
runtime retrieval module, fixture, protocol, historical artifact, CI workflow, dependency file,
release document, or canonical JSON.

The threat model is bounded to operator error and mutations observable at the explicitly named
filesystem and Git preflight/recheck points. It does not claim protection from a hostile kernel,
administrator, filesystem, Git binary, build tool, or a concurrent path retarget after the final
prepublication recheck. Prefer call-owned scratch workspaces, lexical containment, no-follow
checks, immutable digests, and narrow rechecks; do not build a general sandbox, directory-FD
publication primitive, or security boundary.

This is the final bounded pre-observation repair for this stage. Its budget is the eight enumerated
failure mechanisms, the eleven listed paths, F1-F5, and at most one targeted review-fix round per
task before returning to authority review. F6 and F7 have zero repair rounds. If a fix requires a
new module, runtime retrieval change, fixture/protocol rewrite, historical-byte refresh,
dependency, additional public path, or another amendment discovered only while chasing a new
failure, stop this stage. The next decision is to abandon the canonical observation or explicitly
approve a separate stage; do not automatically author Amendment G.

For every F1-F5 RED, author the targeted test before changing the corresponding implementation or
documentation. Record the exact pytest node IDs, command, nonzero exit, and stable assertion or
exception signature. Only those named nodes count as targeted RED evidence; an unrelated
whole-file failure does not. The named-node list becomes that task's immutable RED ledger, and the
task may enter implementation only after every listed node fails for the preregistered reason.

### F0 — Plan-only landing and authority gate

F0 changes only:

- `docs/superpowers/plans/2026-07-26-deterministic-retrieval-order-maintenance-implementation.md`.

Land the approved Amendment F block immediately before `## Task 8B — Seal and Observe Once`.
The starting plan digest must be
`f1be8417e09222b773077fadb943901b102d8a399da47711ba6afc85b3fad6f1`; the design digest must remain
`8522af9fc801f1f30518f450ee5e8538efa0d67fe0039352d58b95c52f52b42b`. Before staging, compare the
approved source and destination bytes with `cmp` and SHA-256, read the complete no-index diff, and
prove that removing the inserted block reconstructs the starting plan byte-for-byte. Then read the
cached and committed diffs, run `git diff --check`, scan the inserted block for private paths and
workflow markers, require exactly one changed path and one semantic commit, and finish with a clean
worktree.

Commit:

```bash
git add docs/superpowers/plans/2026-07-26-deterministic-retrieval-order-maintenance-implementation.md
git commit -m "docs(plan): close pre-observation authority gaps"
```

F0 runs no tests, evaluation command, observation, proof, build, compatibility replay, source-pack
attempt, publication, or cleanup. Stop after the plan-only commit and return its exact diff and
digest for authority review. F1 remains forbidden until that actual plan diff is review-clean.

### F1 — Make the candidate seal cover the whole one-shot transition

Modify:

- `src/mke/evaluation/retrieval_order_workflow.py`;
- `tests/evaluation/test_retrieval_order_workflow.py`.

#### F1.1 — Targeted RED

Add focused tests that fail against the current implementation and prove all of the following:

1. after a holdout receipt becomes visible, the only allowed dirty paths before observation and
   before artifact publication are the development freeze and the receipt;
2. canonical development starts with an empty status and repeats the same candidate seal after
   observation but before freeze construction/publication; a HEAD or worktree mutation inside the
   observer or immediately before publication stops with the freeze absent;
3. each allowed canonical evidence path is exactly untracked (`??`), not merely present in an
   allowed path set; staging, partial indexing, deletion, modification, or rename of an allowed
   path is rejected even when the normalized path set is unchanged;
4. an unexpected modified, staged, renamed, deleted, or untracked path stops before fixture open
   when present at capability consumption, and stops before artifact publication when introduced
   during observation;
5. both the source and destination of a porcelain rename are checked rather than discarding the
   source path;
6. a HEAD change between the first HEAD read, status inspection, and the final HEAD read is
   rejected;
7. rewriting the allowed development-freeze or receipt bytes without changing the status path set
   is rejected before fixture open and again before artifact publication;
8. validated development-freeze and receipt bytes, their exact digests, candidate HEAD, runtime
   profile, and the exact normalized status records remain bound to the production holdout
   capability;
9. an exception after receipt visibility retains the receipt's exact
   `AtomicPublicationResult`, reports a terminal started transition, leaves the artifact absent
   unless complete bytes became visible, and never authorizes retry; and
10. a successful synthetic path still opens the fixture only after receipt publication and emits
   the existing schema without changing public fields.

Include fault injection at the capability-consume boundary, inside the observer, and immediately
before artifact publication. The tests must prove fixture-open and artifact-publication call
counts, not infer ordering only from final files.

Run the new nodes and require the expected failures before implementation.

#### F1.2 — Implement the fail-closed seal

Harden the existing evaluation-only candidate-seal helper without adding a module:

- read HEAD, inspect `git status --porcelain=v1 -z --untracked-files=all`, parse complete
  normalized `(XY, path[, rename_source])` records including both rename paths, then read HEAD
  again;
- require both HEAD values to equal the expected 40-character lowercase commit;
- validate every status path lexically under the repository and compare it with the explicit
  expected status map, not only an allowed dirty-path set;
- require canonical evidence inputs that are allowed after publication to have exactly the
  untracked `??` state;
- remove the permissive `require_clean=False` behavior from production holdout capability
  consumption;
- repeat the empty-status development seal after the development observation and once more
  immediately before freeze publication, requiring every seal to equal the first;
- use `{development_freeze: "??", holdout_receipt: "??"}` as the exact post-receipt status map;
- before any holdout fixture read, after observation before artifact construction, and immediately
  before artifact publication, revalidate the seal, validate both retained schemas, and require
  the development-freeze and receipt digests/cross-bindings to equal the values authorized when
  the receipt became visible; and
- preserve the receipt publication object on every exception after receipt visibility.

Do not delete or rewrite a visible receipt, do not retry, and do not make an already-started
transition successful through later validation.

#### F1.3 — GREEN and commit

Run:

```bash
uv run pytest -q tests/evaluation/test_retrieval_order_workflow.py
uv run ruff check src/mke/evaluation/retrieval_order_workflow.py \
  tests/evaluation/test_retrieval_order_workflow.py
uv run pyright
```

Then inspect the two-path diff and commit:

```bash
git add src/mke/evaluation/retrieval_order_workflow.py \
  tests/evaluation/test_retrieval_order_workflow.py
git commit -m "fix(eval): seal one-shot observation state"
```

### F2 — Bind observations and retained artifacts to the frozen protocol

Modify:

- `src/mke/evaluation/retrieval_order_workflow.py`;
- `tests/evaluation/test_retrieval_order_workflow.py`;
- `src/mke/evaluation/retrieval_order_artifact.py`;
- `tests/evaluation/test_retrieval_order_artifact.py`.

#### F2.1 — Targeted RED

Add tests that prove the current forward-versus-reverse-only comparison is insufficient:

- a shared pure oracle derives each expected tie order from the frozen case fields and the
  strategy-specific key, independent of candidate array order and runtime result order;
- reversing or shuffling fixture candidates leaves the derived oracle unchanged, while a frozen
  expected projection that contradicts the derived key fails before observation;
- a different FTS candidate text/term-frequency shape, a different CJK overlap tuple, or a
  duplicate complete strategy key fails before observation rather than being sorted as a tie;
- identical forged forward and reverse projections that disagree with
  `expected_stable_projections` fail;
- a missing, extra, duplicated, reordered, or substituted case fails;
- a case with the wrong strategy fails;
- missing, extra, duplicated, or projection-mismatched score entries fail;
- `True` is rejected for integer revisions and integer counters and for the floating
  `stable_order_rate`;
- a retained development freeze or holdout artifact with internally matching forged observations
  fails pure validation against the frozen protocol; and
- pure validators do not call the observer, open a holdout fixture outside normal protocol
  loading, create a workspace, or mutate retained bytes.

Add a real-pagination regression that spies on
`KnowledgeEngine.search_evidence_page` and fails while the workflow merely slices the result of
one `engine.search()` call. Cover page sizes `1`, `2`, and the full case size for both FTS and CJK
cases. Inject duplicate, gap, reorder, wrong position, and premature/late
`more_in_selected_pool` states.

#### F2.2 — Implement protocol-bound observation

For each partition, derive the exact ordered case inventory from the loaded protocol contract.
Own one shared module-private pure evaluation helper in
`mke.evaluation.retrieval_order_artifact`; workflow imports it in the existing dependency
direction. Do not place it in workflow, duplicate it, export it, or add a source file. The helper
is an independent secondary-key oracle, not a second implementation of either primary ranker:

- for FTS, require a nonempty current compiled query and require every single-Evidence candidate
  text to equal the frozen query byte-for-byte, giving the same term-frequency and document-length
  shape; then derive the order from
  `locator_start, locator_kind, locator_end, asset_sha256`;
- for CJK, compile the frozen query terms without calling the active-scan selector, compute each
  candidate's overlap count and ratio through a small pure fixture predicate, require the exact
  same nonzero tuple for every candidate, then derive the order from
  `content_fingerprint, locator_kind, locator_start, locator_end`; and
- reject duplicate complete strategy keys because they do not define a total frozen order.

The helper must reject a case that does not meet those executable tie predicates rather than
silently manufacturing an oracle. Require the checked-in expected sequence to equal the derived
secondary-key order before any observation. During real observation, separately require one exact
primary score/tie tuple across every projection in the case; the pure oracle never treats its own
sorting as proof that the primary values tied.

Require each observed case to match its frozen `case_id`, strategy, derived oracle, and
`expected_stable_projections`. Require forward and reverse schedules to equal each other and the
derived frozen projection sequence. Require the score map to contain every and only the observed
projection exactly once, with no duplicate keys or extra entries. Compute aggregate counts only
from this validated inventory.

Replace the self-slicing pagination metric with calls to the existing application API:

```python
KnowledgeEngine.search_evidence_page(...)
```

For each required page size, advance by the returned page length while
`more_in_selected_pool` is true, require positive progress, preserve one active-authority
snapshot, collect the exact result projections, and compare them with the non-paged frozen
projection sequence. Count any duplicate, gap, reorder, incorrect position, authority drift, or
termination mismatch as a pagination failure. Do not add or change a runtime pagination API.
This metric is a revision-2 regression over the existing application API for the frozen corpus;
it does not freeze offset pagination, candidate-pool construction, MCP cursor encoding, or a
future pagination implementation. A future strategy revision may replace those mechanics, but it
must either preserve the exact result sequence or publish a new reviewed protocol.

Make retained validation independently reconstruct the same expected case and projection
authority from the protocol. Use exact numeric types: `type(value) is int` for revisions and
counters and `type(value) is float` for `stable_order_rate`; never accept JSON booleans through
Python numeric equality. Validation remains pure and read-only.

#### F2.3 — GREEN and commit

Run:

```bash
uv run pytest -q \
  tests/evaluation/test_retrieval_order_protocol.py \
  tests/evaluation/test_retrieval_order_workflow.py \
  tests/evaluation/test_retrieval_order_artifact.py \
  tests/adapters/test_sqlite_evidence_access.py \
  tests/adapters/test_sqlite_fts_order.py \
  tests/adapters/test_sqlite_cjk_order.py
uv run ruff check src/mke/evaluation/retrieval_order_workflow.py \
  src/mke/evaluation/retrieval_order_artifact.py \
  tests/evaluation/test_retrieval_order_workflow.py \
  tests/evaluation/test_retrieval_order_artifact.py
uv run pyright
```

Then inspect the four-path diff and commit:

```bash
git add src/mke/evaluation/retrieval_order_workflow.py \
  src/mke/evaluation/retrieval_order_artifact.py \
  tests/evaluation/test_retrieval_order_workflow.py \
  tests/evaluation/test_retrieval_order_artifact.py
git commit -m "fix(eval): bind order evidence to protocol"
```

### F3 — Close compatibility path and candidate-authority gaps

Modify:

- `src/mke/evaluation/retrieval_order_compatibility.py`;
- `tests/evaluation/test_retrieval_order_compatibility.py`.

#### F3.1 — Targeted RED

Add tests that fail against the current compatibility implementation and prove:

1. archived authority validation finishes before any historical directory creation, copy,
   Git blob materialization, or child process;
2. absolute paths, empty components, `.`, `..`, backslash aliases, non-normalized POSIX paths,
   repository escape, source symlinks, symlink parents, and scratch-target escape are rejected
   before the first write;
3. canonical CLI arguments are checked lexically before resolution, so an existing or dangling
   symlink at the canonical basename or any parent cannot alias the expected path;
4. before compatibility attempt publication the exact allowed dirty set is the development
   freeze, holdout receipt, and retrieval artifact;
5. after attempt publication the exact allowed dirty set additionally contains only the attempt
   receipt;
6. all four canonical evidence paths are exactly untracked (`??`); staging, partial indexing,
   deletion, rename, or an in-place content rewrite is rejected even if the path set is unchanged;
7. unexpected worktree state or HEAD drift before attempt, at capability consumption, during
   replay, or before final publication fails closed;
8. `_CanonicalPublicationCapability.consume()` verifies the attempt plus the exact validated
   development-freeze, holdout-receipt, retrieval-artifact, protocol, candidate HEAD, runtime
   seal, digests, schemas, cross-bindings, and normalized post-attempt status records, rather than
   only the attempt digest; and
9. every exception after attempt visibility retains the attempt publication state, leaves the
   canonical compatibility artifact absent unless complete bytes became visible, and cannot
   authorize retry;
10. path-preflight rejection returns exactly
    `status=failed`, `mode=record_canonical`, `output_state=not_applicable`,
    `publication_outcome=not_attempted`,
    `problem=retrieval_order_canonical_publication_unauthorized`,
    `cause=canonical_path_preflight_failed`,
    `next_step=correct_canonical_paths_before_first_attempt`, and
    `first_failed_gate=path_preflight`; and
11. every post-attempt failure carries the visible attempt publication state,
    `next_step=retain_attempt_and_stop`, and the exact first failed gate. It must never reuse a
    preflight remediation such as `wait_for_successful_holdout`.

Use call counters to prove no directory, copy, Git materialization, observer, replay, child, or
publication action occurs before a malformed input is rejected.

#### F3.2 — Implement lexical containment and sealed publication

Move complete archived authority validation ahead of historical source/input materialization.
Build and validate the complete source/input materialization plan in memory before creating the
historical directory or running any Git blob, copy, or child action. Accept only normalized
relative POSIX manifest paths with no empty, `.`, `..`, absolute, backslash, or platform-drive
component. Before reading or copying, require the lexical source and all existing source parents
to be non-symlinks under the repository. Before writing, require the lexical destination and
parents to remain under the call-owned scratch root and to contain no symlink.

Preserve canonical arguments until the canonical-path validator has checked the literal
repository-relative path, parent chain, and basename. Only then resolve the bound path. Do not
let early CLI `.resolve()` calls erase symlink evidence.

Reuse a module-level evaluation-only candidate-seal helper owned by
`mke.evaluation.retrieval_order_workflow`; do not export it through the package, CLI, or MCP, do
not duplicate its Git parser, and do not create a new module. Bind the canonical capability to the
attempt digest, candidate HEAD, runtime profile, exact retained input identities, and the exact
post-attempt normalized status records. Revalidate the protocol, development freeze, holdout
receipt, retrieval artifact, and attempt schema/digest/cross-bindings at capability consumption
and immediately before final publication. Preserve the attempt publication object in every
post-attempt failure result.

Keep the existing result schema and fields. Freeze the exact path-preflight tuple above. After the
attempt is visible, preserve the underlying problem/cause and first failed gate but always expose
the attempt's visible publication state and `next_step=retain_attempt_and_stop`. Update the
existing `record-canonical --help` text and focused tests to distinguish:

```text
preflight rejected -> not attempted; correct the input before any attempt
attempt visible -> terminal; retain the attempt and stop
```

#### F3.3 — GREEN and commit

Run:

```bash
uv run pytest -q \
  tests/evaluation/test_retrieval_order_compatibility.py \
  tests/evaluation/test_atomic_json_publication.py \
  tests/evaluation/test_retrieval_order_historical_freeze.py
uv run ruff check src/mke/evaluation/retrieval_order_compatibility.py \
  tests/evaluation/test_retrieval_order_compatibility.py
uv run pyright
```

Then inspect the two-path diff and commit:

```bash
git add src/mke/evaluation/retrieval_order_compatibility.py \
  tests/evaluation/test_retrieval_order_compatibility.py
git commit -m "fix(eval): contain compatibility authority"
```

### F4 — Make the source-pack attempt claim lexically one-shot

Modify:

- `scripts/consumer_source_pack_proof.py`;
- `tests/scripts/test_consumer_source_pack_proof.py`.

#### F4.1 — Targeted RED

Add focused tests for:

- a dangling symlink at `--attempt-claim`;
- a symlink in any claim parent;
- a parent or basename retargeted between initial preflight and the designated final
  prepublication recheck;
- an existing regular claim;
- a claim inside the repository or candidate-output directory; and
- a valid absent basename in a stable external parent.

For every rejection, prove the build command, interpreter proof, candidate-output write, and
claim publication were never entered. For post-visibility faults, prove one complete claim is
retained and retry stays closed. Freeze the existing two-field failure shape with these exact
actionable codes:

```text
preflight rejected before visibility
  {"status":"failed","code":"retrieval_order_source_pack_claim_invalid"}

any failure after claim visibility
  {"status":"failed","code":"retrieval_order_source_pack_attempt_terminal"}
```

#### F4.2 — Implement the lexical claim binding

Validate the supplied claim path and every parent before calling `resolve()`. Require an absent,
non-symlink basename in an existing external non-symlink directory, outside the repository and
candidate-output tree. Bind the resolved parent plus literal basename and the parent's filesystem
identity, then recheck that binding immediately before the no-replace publication. Reject a
retargeted parent, a newly visible basename, or any symlink without following it.

Keep the existing attempt schema, public fields, build ordering, no-replace helper, and timeout
contract unchanged. This closes stale lexical-path and operator-error aliases visible by the final
recheck; it does not claim directory-FD binding or race-free defense against a concurrent retarget
after that check.

Add both exact codes to the existing finite stable-code set. Preserve the claim publication object
inside the controller so every later exception maps to the terminal code regardless of its
internal root exception; do not expose a path or traceback. Update `--help` and focused tests with:

```text
claim preflight invalid -> correct the path; no attempt started
claim visible -> any later failure is terminal; retain the claim and stop
```

#### F4.3 — GREEN and commit

Run:

```bash
uv run pytest -q tests/scripts/test_consumer_source_pack_proof.py
uv run ruff check scripts/consumer_source_pack_proof.py \
  tests/scripts/test_consumer_source_pack_proof.py
uv run pyright
```

Then inspect the two-path diff and commit:

```bash
git add scripts/consumer_source_pack_proof.py \
  tests/scripts/test_consumer_source_pack_proof.py
git commit -m "fix(proof): seal source-pack attempt path"
```

### F5 — Correct the documented deterministic-order contract

Modify:

- `docs/decisions/0012-deterministic-retrieval-order.md`;
- `docs/explanation/architecture.md`;
- `tests/evaluation/test_retrieval_order_documentation.py`.

#### F5.1 — Targeted RED

Replace the current documentation test that only searches for
`stable semantic SQL key` with exact assertions for the two implemented strategy-specific keys.
The RED test must reject claims that the CJK key is SQL-derived or that Publication revision or
Evidence text identity participates in either current tie-break key.

#### F5.2 — Document the live implementation exactly

State that FTS orders by:

```text
score, locator_start, locator_kind, locator_end, source_sha256
```

and CJK active scan orders in Python by:

```text
-overlap_count, -overlap_ratio, content_fingerprint,
locator_kind, locator_start, locator_end
```

Explain that `source_sha256` and `content_fingerprint` both bind immutable Source bytes in their
respective paths. Opaque IDs remain identity fields, not ordering authority. Publication
revision and Evidence text identity are not current tie-break fields. State explicitly that the
owner-selected FTS and CJK strategies have strategy-specific tie semantics; this ADR does not
promise one cross-strategy display order. Preserve the existing revision-2 cursor invalidation,
active-only authority, historical-layering, one-shot publication, and non-goal statements.

#### F5.3 — GREEN and commit

Run:

```bash
uv run pytest -q tests/evaluation/test_retrieval_order_documentation.py
uv run ruff check tests/evaluation/test_retrieval_order_documentation.py
```

Then inspect the three-path diff and commit:

```bash
git add docs/decisions/0012-deterministic-retrieval-order.md \
  docs/explanation/architecture.md \
  tests/evaluation/test_retrieval_order_documentation.py
git commit -m "docs(retrieval): state exact stable order keys"
```

### F6 — Replacement candidate verification

From the final F5 HEAD, first require all five canonical files to remain absent:

```bash
test ! -e benchmarks/retrieval/retrieval-order-v1-development-freeze.json && \
  test ! -e benchmarks/retrieval/retrieval-order-v1-holdout-receipt.json && \
  test ! -e benchmarks/retrieval/retrieval-order-v1-artifact.json && \
  test ! -e benchmarks/retrieval/retrieval-order-v2-compatibility-attempt.json && \
  test ! -e benchmarks/retrieval/retrieval-order-v2-compatibility.json
```

Run the complete Amendment F focused group:

```bash
uv run pytest -q \
  tests/evaluation/test_retrieval_order_protocol.py \
  tests/evaluation/test_retrieval_order_workflow.py \
  tests/evaluation/test_retrieval_order_artifact.py \
  tests/evaluation/test_retrieval_order_compatibility.py \
  tests/evaluation/test_retrieval_order_documentation.py \
  tests/evaluation/test_atomic_json_publication.py \
  tests/evaluation/test_retrieval_order_historical_freeze.py \
  tests/adapters/test_sqlite_evidence_access.py \
  tests/adapters/test_sqlite_fts_order.py \
  tests/adapters/test_sqlite_cjk_order.py \
  tests/scripts/test_consumer_source_pack_proof.py
```

The closed F6 command ledger is exactly the focused group above plus the already frozen Amendment
E E4 and Task 8A Step 3 commands represented by these groups:

1. the exact nine-failure regression set retained by Amendment E;
2. the D5 workflow/documentation group;
3. the focused runtime/order/cursor/interface/schema group;
4. the full historical compatibility matrix;
5. runtime-capability and no-canonical guards;
6. the complete test suite with exit code and final summary captured;
7. Ruff;
8. Pyright;
9. build;
10. the committed numeric CI-parity block;
11. synthetic installed-proof tests;
12. eligible consumer source-pack and compiled-export groups;
13. the exact 14 immutable historical hashes;
14. product proof and demo; and
15. the Task 8A Step 3 commands that were already explicitly enumerated before Amendment F.

This list is exhaustive. It does not authorize a newly discovered test, proof, observation, or
command merely because an earlier paragraph says "remaining." Run each command block at most once
from the final F5 HEAD, capture its exit and final summary on the first invocation, and do not
restart a passed command. F6 has a cumulative wall-clock budget of 120 minutes and zero repair
rounds. A failure, timeout, missing final summary, or lost command result is `BLOCKED`; it does not
authorize a retry, substitution, or repair inside F6.

Every command in the focused, E4, Task 8A, and minimum ledgers is an independent fail-fast gate.
Invoke one command at a time, record exit and summary, and start the next command only after the
previous gate returned exit `0`. If an earlier section prints multiple shell commands in one fence,
split them at command boundaries rather than pasting the fence as one script. Record the F6 start
time before the focused command and stop when cumulative elapsed time reaches 120 minutes.

At minimum, run each of these as a separate gate:

```bash
uv run pytest -q
```

```bash
uv run ruff check .
```

```bash
uv run pyright
```

```bash
uv build
```

```bash
uv run mke proof run
```

```bash
uv run mke demo --verify
```

Before each proof capable of writing a candidate output, use only a call-owned temporary
destination and verify that it is absent. Eligible source-pack verification is limited to the
existing non-Task-8R lanes and synthetic attempt-claim tests; do not invoke the real
`--attempt-claim` flow. Do not pass a canonical holdout, compatibility, installed-proof, or
source-pack-attempt path.

After the final gate, repeat the five-path absence check. Also require:

- the design digest remains
  `8522af9fc801f1f30518f450ee5e8538efa0d67fe0039352d58b95c52f52b42b`;
- the plan digest equals the review-clean F0 digest;
- all 14 immutable historical hashes remain exact;
- the implementation delta is confined to the eleven F+ paths;
- no fixture, protocol, historical artifact, CI, runtime retrieval, dependency, or release path
  changed;
- `git diff --check` passes; and
- the worktree is clean.

The final clean committed HEAD after every successful gate becomes the replacement candidate seal.
If any gate fails, stop at the first failure. Do not relax a validator, update expected bytes,
rewrite a fixture, retry a canonical action, expand scope, or continue to Task 8B without a new
reviewed amendment.

### F7 — Actual-diff review and stop boundary

Return the exact start and final HEADs, semantic commits, eleven-path range diff, RED and GREEN
evidence, full verification summaries, immutable hashes, plan/design digests, five-path absence
proof, and mini-retro. The worktree must be clean.

The implementation is not authorized to enter Task 8B until an independent authority review has
read the actual F1-F6 diff and the user has explicitly resumed the one-shot observation. Review
findings are evidence that the F6-verified candidate is not review-clean and therefore make this
stage `BLOCKED`. Do not repair a material F7 finding inside Amendment F: any repair would create a
new HEAD that has not passed the one-invocation F6 ledger. The next authority decision is to
abandon canonical observation or approve a separately planned stage with a new verification
budget.

Throughout F0-F7, do not run development observation, holdout observation, canonical
compatibility, canonical installed proof, a real source-pack attempt, push, PR, merge, tag,
release, deployment, promotion, or cleanup.

A green F6 proves only that the evaluation controller now:

- binds one-shot transitions to the sealed HEAD and exact allowed worktree state;
- compares observed order with frozen protocol expectations through real application pagination;
- validates retained artifacts with exact schemas and numeric types;
- contains historical and canonical paths before side effects;
- preserves no-replace attempt receipts as terminal authority; and
- documents the live strategy-specific stable keys accurately.

It does not prove retrieval-quality improvement, segmentation or contextual-retrieval value,
runtime promotion, production readiness, broad portability, latency, accuracy, SLA, adoption,
release status, or successful canonical development/holdout/compatibility observation.

## Task 8B — Seal and Observe Once

Run the canonical development command exactly once:

```bash
uv run python -m mke.evaluation.retrieval_order_workflow development \
  --protocol tests/fixtures/retrieval-order-v1/protocol.json \
  --record-development-freeze \
    benchmarks/retrieval/retrieval-order-v1-development-freeze.json \
  --json
```

On nonzero exit, stop without opening holdout.

If development passes, run the canonical public nonblind holdout command exactly once:

```bash
uv run python -m mke.evaluation.retrieval_order_workflow holdout \
  --protocol tests/fixtures/retrieval-order-v1/protocol.json \
  --development-freeze \
    benchmarks/retrieval/retrieval-order-v1-development-freeze.json \
  --record-holdout-receipt \
    benchmarks/retrieval/retrieval-order-v1-holdout-receipt.json \
  --record benchmarks/retrieval/retrieval-order-v1-artifact.json \
  --json
```

The receipt is atomically published before any fixture open. Only after publication may the
command create the receipt-bound private capability and enter canonical observation. The
capability is consumed once. The retrieval-order artifact also uses the same absent-or-complete
atomic publication helper. No canonical file is deleted, overwritten, or retried. On any failure,
retain exact evidence and stop.

The retained Task 8B handoff records the exact command, exit, receipt digest, artifact digest when
present, and first failed gate as its immutable command ledger. A successful terminal transition
requires one no-replace holdout attempt receipt plus one byte-valid successful artifact bound to
that receipt. Observation failure enters `HOLDOUT_FAILED_TERMINAL`; visible complete artifact bytes
whose directory `fsync` failed enter `HOLDOUT_ARTIFACT_DURABILITY_UNCONFIRMED`. Neither state may
enter Task 8R. A later validator can report bytes valid but cannot convert either terminal state
to success.

Do not run tests, docs generators, formatters, or commands that can reopen canonical holdout
between development and holdout. Do not generate canonical compatibility before holdout.

## Task 7B / Task 8R — Canonical Compatibility and Final Proof Closure

This task begins only after a terminal successful holdout and no source/test/doc change after the
candidate seal.

### Step 1 — Source-seal preflight

Verify:

- candidate source files match the development freeze;
- runtime profile matches development and holdout;
- only the expected uncommitted canonical development freeze, holdout receipt, and retrieval-order
  artifact exist;
- the 14-entry immutable input map remains exact; and
- no source/test/doc file changed after the candidate seal.

### Step 2 — Record canonical compatibility once

Run exactly:

```bash
uv run python -m mke.evaluation.retrieval_order_compatibility record-canonical \
  --protocol tests/fixtures/retrieval-order-v1/protocol.json \
  --development-freeze \
    benchmarks/retrieval/retrieval-order-v1-development-freeze.json \
  --holdout-receipt \
    benchmarks/retrieval/retrieval-order-v1-holdout-receipt.json \
  --retrieval-artifact \
    benchmarks/retrieval/retrieval-order-v1-artifact.json \
  --candidate-head <exact-Task-8A-seal-SHA> \
  --attempt-receipt \
    benchmarks/retrieval/retrieval-order-v2-compatibility-attempt.json \
  --artifact benchmarks/retrieval/retrieval-order-v2-compatibility.json \
  --repository . \
  --json
```

The execution handoff substitutes the already-recorded exact 40-hex candidate seal; it never
derives this argument from an unreviewed current HEAD.

Before any corpus open or current replay, `record-canonical` validates the passing development
freeze, terminal successful holdout receipt/artifact, exact candidate HEAD/profile bindings,
absence of both canonical destinations, and the 14-entry immutable map. It then atomically
publishes the durable compatibility-attempt receipt before any archive/current replay. Only the
process that created this receipt may derive and consume the private one-use
canonical-publication capability. Missing, preexisting, already-consumed, or seal-mismatched
capability state fails closed. A later process cannot retry even if compatibility output is
absent. The compatibility builder never reopens or reruns the holdout partition; it consumes the
already-published holdout artifact as bytes only.

The artifact binds source file identities/digests and runtime profile, not the post-proof commit
SHA. It includes the exact 14-entry immutable input map, the family capability matrix, and the
four-layer status fields.

`record-canonical` builds and validates in memory, then atomically publishes the path. Existing
output or any build/validation failure exits 1 and preserves existing bytes or absence. It uses the
reviewed shared absent-or-complete helper, including file and directory `fsync`, readback, exact
digest validation, and OS-level no-replace publication. After a failed canonical record, stop; do
not modify source or record again.

Run `validate` twice against the same bytes; do not rebuild canonical output to obtain a different
result. `validate` is pure read-only: it checks bytes, schema, digests, and cross-bindings and never
calls any ranking/retrieval observer.

### Step 3 — Prepare one clean sealed proof source and wheel

The retained observation checkout now contains five intentional, uncommitted canonical proof
artifacts. Existing consumer source-pack and compiled-export controllers require a clean source
checkout, so they must not run against that retained checkout.

Create one task-owned detached proof worktree with:

```bash
git worktree add --detach <task-owned-proof-worktree> <exact-Task-8A-seal-SHA>
```

Verify its exact HEAD, detached state, empty porcelain status, source tree, lockfile, and package
metadata before use. Every proof command must execute the script copy under
`<task-owned-proof-worktree>/scripts/`; changing cwd while executing a retained-checkout script
path is forbidden because the controllers derive repository authority from `Path(__file__)`.
This worktree is an authority-isolation lane only: it may not receive a branch, commit, source
edit, canonical record, or independent implementation.

In an external task-owned evidence directory:

1. verify that `<external-evidence-directory>/source-pack-attempt.claim.json` and candidate output
   are absent;
2. run the consumer source-pack proof exactly once from the clean sealed worktree:

   ```bash
   cd <task-owned-proof-worktree>
   UV_OFFLINE=1 uv run python \
     <task-owned-proof-worktree>/scripts/consumer_source_pack_proof.py \
     --python <resolved-python-3.12> \
     --python <resolved-python-3.13> \
     --attempt-claim \
       <external-evidence-directory>/source-pack-attempt.claim.json \
     --candidate-output <external-evidence-directory>/candidate \
     --json
   ```

   After bounded preflight and before its build, the sealed controller no-replace publishes the
   complete attempt claim. A “real invocation” is exactly a controller CLI run carrying the two
   real interpreters, `--attempt-claim`, and `--candidate-output`; pre-seal unit/synthetic tests do
   not count. This is the only real source-pack build/proof invocation in Task 8R. A claim retained
   after failure permanently forbids another real invocation.
3. copy the canonical protocol, development freeze, holdout receipt, retrieval-order artifact, and
   compatibility artifact from the retained checkout as read-only proof inputs;
4. recompute and compare every copied digest with the retained canonical bytes before and after
   each proof; and
5. parse `candidate/candidate-artifact-receipt.json`, require its exact `wheel_filename`,
   `source_commit`, `wheel_sha256`, `proof_input_wheel_sha256`, and receipt digest, then select the
   wheel by that exact filename without globbing; and
6. require
   `<task-owned-proof-worktree>/scripts/retrieval_order_installed_proof.py` and
   `<task-owned-proof-worktree>/scripts/compiled_library_export_proof.py
   --mke-wheel <exact-wheel>` to reuse that exact wheel.

The two post-build proof commands are exact:

```bash
cd <task-owned-proof-worktree>
UV_OFFLINE=1 uv run python \
  <task-owned-proof-worktree>/scripts/retrieval_order_installed_proof.py \
  --python <resolved-python-3.12> \
  --python <resolved-python-3.13> \
  --mke-wheel <external-evidence-directory>/candidate/<exact-wheel-filename> \
  --candidate-receipt \
    <external-evidence-directory>/candidate/candidate-artifact-receipt.json \
  --protocol <external-evidence-directory>/inputs/protocol.json \
  --development-freeze <external-evidence-directory>/inputs/development-freeze.json \
  --holdout-receipt <external-evidence-directory>/inputs/holdout-receipt.json \
  --artifact <external-evidence-directory>/inputs/retrieval-order-artifact.json \
  --compatibility <external-evidence-directory>/inputs/compatibility.json \
  --json

UV_OFFLINE=1 uv run python \
  <task-owned-proof-worktree>/scripts/compiled_library_export_proof.py \
  --python <resolved-python-3.12> \
  --python <resolved-python-3.13> \
  --mke-wheel <external-evidence-directory>/candidate/<exact-wheel-filename> \
  --json
```

Every angle-bracketed Task 8R value is a mechanical output of the sealed-source/interpreter/
candidate-receipt preflight and is copied verbatim into the retained command ledger. None is an
implementation-time product or authority choice.

The retrieval-order proof consumes the explicit candidate receipt and all copied canonical inputs.
The compiled-export result is paired with the already-validated candidate receipt by the Task 8R
controller. Every result must bind or be externally cross-checked against the same candidate seal
SHA and `proof_input_wheel_sha256`; installed and compiled-export results must equal the receipt's
value. No controller may rebuild or silently substitute a second wheel. Before and after every
proof, verify the proof worktree HEAD/clean status and candidate receipt, exact wheel, and copied
input digests. The final handoff reports the proof-worktree path, HEAD, clean status, unique wheel
SHA, one claim digest, and one candidate-receipt digest.
The proof worktree is retained and reported at task return; removing it remains outside this
amendment's cleanup authority.

### Step 4 — Final matrices

Rerun:

- the complete historical/compatibility matrix;
- all retrieval-order protocol/workflow/artifact tests;
- cursor, Python, CLI, MCP v1/v2, exact-read, schema, active-only, supersession, Publication, and
  Evidence provenance tests;
- the full test suite;
- Ruff;
- Pyright;
- CI-parity commands;
- the exact same-wheel `scripts/retrieval_order_installed_proof.py` under the required external
  Python 3.12 and 3.13 environments;
- compiled-library export proof; and
- read-only revalidation of the retained Step 3 source-pack attempt claim, consumer source-pack
  JSON, candidate receipt, source commit, and wheel digest.

Do not rerun `consumer_source_pack_proof.py` in this step. The installed and compiled-export proofs
run from the clean sealed proof worktree/evidence directory and consume the one Step 3 wheel. All
repository tests run from the retained checkout. Before the final full suite, run the runtime
capability proof plus the supplemental guard/static check that no test can execute canonical
holdout. Post-holdout validators are pure read-only: they validate canonical receipt/artifact
bytes, schema, digests, and cross-bindings and use synthetic copied fixtures for retry behavior;
they never invoke the canonical ranking/retrieval observer. A call-counter test requires the
canonical observer count to remain zero for every validator. The Task 8R controller establishes
the lifecycle count of exactly one from the unique holdout attempt receipt, unique successful
artifact, and retained Task 8B command ledger; synthetic capability calls are excluded.

Rerun `tests/evaluation/test_retrieval_order_historical_freeze.py` and require exact equality of
all 14 paths, digests, and canonical sorted serialization. Any source identity drift, unexpected
dirty path, shared-wheel mismatch, membership/score/non-tied order/metric/gate/verdict delta, or
consumer regression is a STOP. Do not rerun holdout.

The final read-only controller requires exactly one source-pack attempt claim, one candidate
receipt, and one wheel at the receipt's exact filename. It rejects a second claim/output, missing
claim fields, retained-checkout script provenance, implicit sibling discovery, wheel globbing, or
any build fallback.

### Step 5 — Commit proof artifacts

Stage only:

- `benchmarks/retrieval/retrieval-order-v1-development-freeze.json`
- `benchmarks/retrieval/retrieval-order-v1-holdout-receipt.json`
- `benchmarks/retrieval/retrieval-order-v1-artifact.json`
- `benchmarks/retrieval/retrieval-order-v2-compatibility-attempt.json`
- `benchmarks/retrieval/retrieval-order-v2-compatibility.json`

Commit:

```bash
git commit -m "test(eval): freeze deterministic retrieval order proof"
```

Re-run validators that do not mutate canonical artifacts and verify a clean worktree.

Task 8R completion still does not authorize push, PR, merge, release, or promotion.

## Maintainer Result and Help Contract

Every internal compatibility/workflow/proof `--json` command returns one bounded redacted object
with empty stderr. Success and failure include:

```text
status
schema_version
mode
authority_layer
canonical
output_state
publication_outcome
problem
cause
next_step
first_failed_gate
stage_statuses
historical_revision
current_revision
```

For compatibility commands the field contract is exact:

| Field | Type and allowed values |
|---|---|
| `schema_version` | string; the mode-specific `.v1` value frozen in Task 8A |
| `status` | string; `passed|failed` |
| `mode` | string; `record|validate|record_canonical` |
| `authority_layer` | string; `archive_current_differential|artifact_validation|canonical_publication` as fixed by mode |
| `canonical` | boolean; `true` only for `record_canonical` or validation of the canonical artifact |
| `output_state` | string; the four-value enum below |
| `publication_outcome` | string; the four-value enum below |
| `problem`, `cause`, `next_step` | strings; `none` on success, otherwise one frozen registry row |
| `first_failed_gate` | string; `none` or one frozen stage name |
| `stage_statuses` | ordered array of `{name: string, status: not_run|passed|failed}` |
| `historical_revision`, `current_revision` | integers; `1` and `2` after valid archive binding, otherwise `0` before that gate |

Fields not applicable to a mode are represented by stable explicit values, not omitted through a
catch-all. No absolute path, raw query, Evidence content, opaque ID, cursor, traceback, or arbitrary
exception text is emitted.

The finite stable failures and their one allowed cause/next-step pair are:

| Problem | Cause | Next step |
|---|---|---|
| `retrieval_order_archive_invalid` | `recorded_structure_or_identity_invalid` | `inspect_immutable_archive` |
| `retrieval_order_compatibility_incomplete` | `unapproved_family_delta` | `inspect_first_failed_family` |
| `retrieval_order_canonical_publication_unauthorized` | `required_success_authority_missing` | `wait_for_successful_holdout` |
| `retrieval_order_canonical_publication_already_started` | `attempt_receipt_exists` | `retain_attempt_and_stop` |
| `retrieval_order_canonical_output_exists` | `destination_preexists` | `validate_retained_bytes` |
| `retrieval_order_holdout_unauthorized` | `typed_capability_missing_or_mismatched` | `restore_approved_transition` |
| `retrieval_order_holdout_already_started` | `holdout_receipt_exists` | `retain_receipt_and_stop` |
| `retrieval_order_candidate_seal_mismatch` | `candidate_inputs_do_not_match_seal` | `return_to_authority_review` |
| `retrieval_order_shared_wheel_mismatch` | `wheel_or_receipt_digest_mismatch` | `retain_evidence_and_stop` |
| `retrieval_order_publication_failed_before_visibility` | `publication_failed_before_final_path` | `retain_attempt_and_stop` |
| `retrieval_order_publication_durability_unconfirmed` | `directory_fsync_failed_after_visibility` | `retain_visible_bytes_and_stop` |
| `retrieval_order_source_pack_already_started` | `source_pack_claim_exists` | `retain_claim_and_stop` |
| `retrieval_order_proof_preflight_invalid` | `proof_source_or_input_binding_invalid` | `inspect_first_failed_gate` |

The strict live numeric command preserves its existing
`retrieval_numeric_fixture_invalid`/`restore_numeric_protocol_inputs` result rather than inventing
a compatibility alias. `output_state` is exactly
`absent|complete_preexisting|complete_visible|not_applicable`; `publication_outcome` is exactly
`not_attempted|published|failed_before_visibility|durability_unconfirmed`. Tests freeze the valid
pair for every path. Generic current-observation rescue text such as
`restore_frozen_protocol_and_retry_current_observation` is forbidden for canonical development,
holdout, compatibility publication, and proof modes.

Before expensive replay/build work, each controller runs bounded source/profile/path/receipt
preflights. The final JSON records ordered stage statuses and the first failed gate. Optional
stage-duration diagnostics are informational only, excluded from canonical artifacts/digests and
all performance claims, and never change a gate or verdict.

Top-level and subcommand `--help` use the same archive/current/differential/canonical terminology
as the JSON. Tests lock help text, exit codes, finite problems, retry guidance, and redaction.

## Test Coverage Map

```text
numeric live authority
  +-- default loader current hash exact ------------ critical regression
  +-- public/current runner remains fail closed ---- integration
  +-- refresh copied protocol only ----------------- integration

numeric archived authority
  +-- exact lexical allowlist/order ---------------- unit
  +-- lowercase recorded SHA syntax ---------------- unit
  +-- no current-file hash comparison -------------- regression
  +-- manifest/fixture bytes remain exact ---------- integration
  +-- current schema compatibility remains -------- integration
  +-- no shadow test validator --------------------- architecture

Chinese trace authority
  +-- two MATCH statements selected ---------------- unit
  +-- rank + BM25 exact roles ---------------------- unit
  +-- full stable locator/source key --------------- unit
  +-- LIMIT rejected only in MATCH ----------------- unit
  +-- config LIMIT 1 accepted ---------------------- regression
  +-- opaque ID ORDER BY rejected ------------------ unit
  +-- hostile trace redaction ---------------------- privacy
  +-- E3-A/E3-B current replay --------------------- integration

workflow authority
  +-- live revision 2/passed ----------------------- integration
  +-- archived revision 1/failure from JSON -------- immutable record
  +-- no stale live revision claim ----------------- regression

compatibility
  +-- family score capability frozen before replay - authority
  +-- E1/E2 deterministic historical subprocess ---- critical
  +-- hashed bootstrap + 107 exact blobs ----------- isolation
  +-- interpreter/module-origin preflight ----------- isolation
  +-- pre-current zero-delta downgrade only --------- authority
  +-- temporary deterministic build ---------------- integration
  +-- temporary record rejects canonical path ------- lifecycle
  +-- record-canonical synthetic pre-seal integration lifecycle
  +-- durable canonical attempt receipt ------------- one-shot
  +-- all family deltas/tie groups ----------------- differential
  +-- atomic no-replace canonical record ------------ lifecycle
  +-- absent-or-complete fault injection ------------ durability
  +-- final 133-test matrix + full suite ----------- regression

one-shot lifecycle
  +-- all holdout tests use different synthetic bytes privacy/authority
  +-- every holdout call requires typed capability -- critical
  +-- metadata preflight + lazy partition load ------ critical
  +-- copied/alias/symlink/mixed bypass rejected ---- regression
  +-- fixture unopened on rejected call ------------ critical
  +-- post-holdout validators never observe --------- authority
  +-- all source/test/docs before seal ------------- lifecycle
  +-- no source/test/docs after holdout ------------- lifecycle
  +-- clean sealed proof worktree ------------------- source authority
  +-- proof scripts originate from sealed worktree -- source authority
  +-- durable source-pack attempt claim ------------- one-shot
  +-- source-pack build/proof exactly once ---------- artifact authority
  +-- one shared-wheel installed/export proof ------- consumer

immutable authority
  +-- exact 14 paths and digests -------------------- historical freeze
  +-- canonical sorted serialization ---------------- deterministic

maintainer DX
  +-- finite stable errors and retry guidance ------- operations
  +-- authority layer/mode/canonical visible -------- explanation
  +-- help contract and first failed gate ----------- time to result
```

## Error and Rescue Registry

| Codepath | Failure | Rescue | Stable result |
|---|---|---|---|
| live numeric loader | current source lock mismatch | existing runner boundary | `retrieval_numeric_fixture_invalid` |
| archived numeric loader | invalid recorded structure/path/SHA | compatibility boundary | `retrieval_order_archive_invalid` |
| archived numeric loader | current SQLite schema mismatch | existing gate | `no_scope_expansion` failed |
| numeric refresh | invalid copied protocol or write failure | restore copied bytes, re-raise | original exception type plus byte-identical copied protocol |
| Chinese trace validator | missing/old/extra MATCH proof | runner boundary | `retrieval_chinese_rank_invalid` |
| non-MATCH config probe | contains `LIMIT 1` | excluded from ordering proof | accepted if MATCH proof is valid |
| compatibility builder | any unapproved delta | no rescue | `retrieval_order_compatibility_incomplete` |
| historical source materializer | missing blob/path/digest/profile or nondeterministic replay | pre-current downgrade for E1 and E2 together | `no_ordered_delta_authority` |
| temporary compatibility record | canonical destination requested | reject before corpus/replay | `retrieval_order_canonical_publication_unauthorized` |
| canonical compatibility record | attempt receipt already exists | reject before archive/current replay | `retrieval_order_canonical_publication_already_started` |
| canonical compatibility record | missing capability | reject before archive/current replay | `retrieval_order_canonical_publication_unauthorized` |
| canonical compatibility record | seal mismatch | reject before attempt publication | `retrieval_order_candidate_seal_mismatch` |
| atomic publication | failure before final-path visibility | no retry after canonical attempt | `retrieval_order_publication_failed_before_visibility` |
| atomic publication | directory-`fsync` failure after complete visibility | retain bytes; no retry | `retrieval_order_publication_durability_unconfirmed` |
| compatibility record | preexisting final output | no overwrite/retry | `retrieval_order_canonical_output_exists` |
| development | any failed gate | no rescue | stop before holdout |
| canonical holdout observer | missing/mismatched/consumed capability | reject before fixture open | `retrieval_order_holdout_unauthorized` |
| holdout command | receipt already exists | reject before capability/fixture | `retrieval_order_holdout_already_started` |
| holdout | observation failure after receipt | no rescue/retry | `HOLDOUT_FAILED_TERMINAL` |
| holdout artifact publication | complete visible but directory durability unknown | no rescue/retry | `HOLDOUT_ARTIFACT_DURABILITY_UNCONFIRMED` |
| clean proof worktree | wrong HEAD, dirty source, or copied-input digest mismatch | no proof execution | `retrieval_order_proof_preflight_invalid` |
| source-pack proof | attempt claim already exists | no second invocation | `retrieval_order_source_pack_already_started` |
| same-wheel proofs | wheel SHA or candidate seal differs across receipts | no rebuild/substitution | `retrieval_order_shared_wheel_mismatch` |
| post-holdout validator | observer call attempted | fail test before observation | read-only authority violation |
| final verification | source drift or regression | no holdout retry | blocked with exact failing gate |

No catch-all rescue, silent fallback, auto-refresh, or auto-retry is added.

## Security and Privacy

- No network, credential, secret, untrusted external input, dependency, endpoint, or runtime
  persistence surface is added. The only new persistence is bounded evaluation proof/attempt
  evidence described in this amendment.
- Historical tree resolution uses only local Git objects, exports to a task-owned temporary
  directory, materializes only the frozen recorded path set, and never fetches, switches a branch,
  or mutates the retained worktree.
- Historical subprocesses use a checkout-external cwd, `PYTHONNOUSERSITE=1`, cleared inherited
  `PYTHONPATH`/`PYTHONHOME`, a new path containing only the materialized historical package, exact
  runtime versions, and verified module origins.
- Archive scope uses an exact lexical allowlist and cannot select arbitrary repository paths.
- Live scope retains resolved repository-bound path and byte checks.
- Canonical publication uses same-directory OS-level no-replace semantics and exact readback; it
  cannot silently replace existing evidence or leave accepted partial bytes.
- Every holdout observer call requires a typed capability. Production capability authority comes
  only from the already-published canonical receipt; synthetic capability creation rejects any
  canonical holdout fixture digest. Metadata-only preflight and lazy partition loading reject
  before any fixture bytes.
- Canonical compatibility first publishes a no-replace attempt receipt; its existence closes
  cross-process retry even if the final compatibility artifact is absent.
- The detached proof worktree is bound to the sealed SHA; copied canonical inputs are read-only and
  hash-verified before external proof execution. Proofs execute only script copies from that
  worktree, and a durable external attempt claim closes source-pack retries.
- SQL validators inspect runtime-generated diagnostic text; they never execute supplied SQL.
- Tests prove stable errors do not expose raw query/Evidence, opaque ID, cursor, absolute path, or
  traceback.
- Canonical artifacts contain stable locators/digests and public-neutral evidence only.

## Performance

All new work is evaluation-only. Archive scope validation is bounded by the fixed eight-path list.
SQL trace checks are bounded string checks over the captured statement tuple. Compatibility replay
uses existing model-free runners and frozen inputs. The two historical subprocesses, atomic
publication readback, and one sealed proof worktree add bounded maintainer-proof cost only.

No runtime search query, index, row cap, byte cap, connection, cache, model load, or public latency
contract changes. Wall-clock numbers remain informational.

## Deployment and Rollback

This stage has no deployment.

```text
plan amendment
  -> Task 6R authority repair
  -> Task 7A temp compatibility
  -> Task 8A all source/test/docs
  -> candidate seal
  -> Task 8B development once
  -> Task 8B holdout once
  -> Task 7B/8R canonical compatibility + final proof
```

Each pre-observation code phase is a semantic commit and can be reverted. Reverting Task 6R returns
the known 71-failure block; therefore code rollback is mechanically simple but Task 7 becomes
blocked again. After a holdout receipt exists, rollback does not erase or reopen the observation;
the retained receipt/artifact remains terminal evidence.

Reversibility:

- code/test changes before observation: high;
- one-shot holdout state: intentionally irreversible;
- historical artifacts: unchanged;
- promotion: not authorized.

## Developer Experience

The maintainer sees one authority per command:

```text
archive check -> recorded identity only
live numeric CLI -> current lock strict
compatibility -> archive + current replay + differential
workflow current -> revision 2
workflow historical -> immutable JSON record
canonical holdout -> published receipt + one-use capability
external proof -> sealed clean worktree + one shared wheel
```

The public numeric command is not silently redefined. A stale protocol continues to fail with a
stable error and an explicit refresh path. The compatibility command/module owns cross-revision
explanation. Temporary `record` cannot address the canonical path; only post-holdout
`record-canonical` can derive its publication capability.

Debug paths:

1. archive syntax/identity failure -> inspect recorded structure;
2. live source-lock failure -> refresh only a copied/current protocol through the maintainer path;
3. Chinese rank proof failure -> inspect the two selected MATCH statements;
4. workflow revision conflict -> distinguish live observation from archived JSON;
5. differential failure -> stop on the exact family and delta;
6. publication failure -> inspect absent-or-complete final path; never retry canonical evidence;
7. canonical holdout authority failure -> verify receipt/candidate binding before any fixture open;
8. proof checkout failure -> verify clean sealed SHA and shared-wheel digest; and
9. post-receipt failure -> retain evidence; never retry holdout.

## Documentation

Required public documentation changes are:

- the approved plan amendment; and
- an append-only Task 0 source-inventory execution finding; and
- the original Task 9 ADR, proof how-to, architecture/contracts/MCP/CLI/CJK docs, docs index, and
  their documentation tests, all completed in Task 8A before observation.

The design spec remains byte-identical. After the candidate seal and holdout, no doc is edited to
record results; run facts stay in retained handoff/PR evidence until a later authorized
publication phase.

## Worktree and Parallelization

Use the retained implementation branch sequentially. Numeric, Chinese, and workflow-test repairs
share one authority gate; Task 7A depends on them; Task 8 and canonical compatibility are strictly
ordered. The only additional worktree is the read-only detached Task 8R proof worktree at the
sealed SHA. It is not an implementation or parallel-authority lane.

## Rejected Alternatives

1. **Relax default numeric loading** — rejected because it weakens the public/current source lock.
2. **Refresh checked-in historical locks** — rejected because it rewrites history.
3. **Treat all 64-character hashes as sufficient everywhere** — rejected because live,
   manifest, fixture, schema, and canonical byte authority remain strict.
4. **Require all 133 tests before Task 7A** — rejected because several are current replay tests
   whose authorized path is Task 7A.
5. **Generate canonical compatibility in original Task 7** — rejected because Tasks 8 and 9 still
   write source, tests, scripts, ADR, and docs.
6. **Validate historical revision 1 by replaying current revision 2** — rejected as an authority
   contradiction; validate the immutable JSON record instead.
7. **Forbid LIMIT across the whole SQL trace** — rejected because the rank-config probe correctly
   uses `LIMIT 1`.
8. **Change runtime SQL** — rejected because the live runtime already implements the approved
   stable order.
9. **Add a SQL parser** — rejected as unnecessary for bounded runtime-generated traces.
10. **Run holdout before compatibility tests** — rejected; temporary Task 7A verification must be
    green first.
11. **Regenerate compatibility after a failure until it passes** — rejected as proof tuning.
12. **Infer historical ties from current scores** — rejected because E1/E2 do not record exact
   historical score hex.
13. **Run canonical holdout from pytest** — rejected because it would consume or replay the
   one-shot corpus outside the approved receipt transition.
14. **Use a static scan as the holdout authority** — rejected because aliases, helpers, and direct
    Python calls can bypass textual checks; a runtime receipt-bound capability is required.
15. **Run source/compiled proofs from the dirty retained observation checkout** — rejected because
    existing controllers require a clean source checkout.
16. **Build one wheel per proof** — rejected because independently built inputs weaken
    same-candidate consumer evidence.
17. **Publish with check-then-rename** — rejected because it permits replacement races and cannot
    guarantee absent-or-complete canonical authority.
18. **Let temporary `record` write the canonical path** — rejected because a pre-holdout mistake
    would irreversibly consume the no-replace publication slot.
19. **Rerun source-pack proof in the final matrix** — rejected because the controller rebuilds;
    Task 8R must retain and revalidate its one Step 3 wheel/receipt/result.
20. **Let a validator replay canonical holdout** — rejected because validation is bytes/schema/
    digest/cross-binding only after the one-shot observation.
21. **Gate holdout only by canonical protocol path or digest** — rejected because copied,
    reserialized, aliased, symlinked, or mixed-fixture protocols can bypass wrapper identity; every
    holdout call needs a typed capability before lazy fixture load.
22. **Track canonical/source-pack one-shot state only in process memory or final output** —
    rejected because a crash before final publication permits a fresh-process retry; durable
    no-replace attempt evidence must exist before irreversible replay/build work.

## Stop Gates

Stop and return `BLOCKED` if:

- targeted RED does not isolate the verified authority mismatch;
- live numeric default becomes permissive;
- archive mode becomes an implicit fallback or public CLI flag;
- a runtime retrieval file appears necessary;
- a historical artifact/protocol byte changes;
- the pre-maintenance observation JSON is replayed as if current;
- a raw sentinel appears in stable output;
- any unapproved membership, score-hex, non-tied order, metric, gate, or verdict delta appears;
- a family with unrecorded scores infers ties from current output or records unknown as zero;
- E1/E2 historical capability is selected after current replay, the exact recorded source set is
  not reconstructed, or the two historical subprocess outputs differ;
- canonical compatibility is generated before the candidate source seal;
- a canonical compatibility or attempt-receipt path already exists, a failed record attempts
  retry, or replay starts before attempt-receipt publication;
- temporary `record` can address the canonical destination, or `record-canonical` proceeds without
  a successful holdout/candidate-seal capability or was not fully integrated with synthetic
  authority before the seal;
- any canonical publication path can contain partial bytes or replace an existing destination;
- any source/test/script/ADR/how-to/doc changes after candidate seal;
- any holdout path can be called without a typed capability, synthetic capability accepts a
  canonical fixture digest, development opens holdout bytes, or a rejected call opens any fixture;
- development fails;
- holdout receipt exists and code attempts retry/delete/overwrite, or failed/durability-unconfirmed
  holdout proceeds to Task 8R;
- the proof worktree is dirty or not at the sealed SHA, copied canonical inputs differ, or external
  proof receipts do not bind one identical wheel SHA, or a proof executes a script outside the
  sealed proof worktree;
- source-pack attempt claim is absent/preexisting/malformed, source-pack proof runs more than once,
  a proof selects a wheel by glob/implicit sibling, or a post-holdout validator invokes the
  observer;
- stable JSON/help omits authority layer, output/publication outcome, first failed gate, or safe
  next step;
- final historical/full/consumer verification fails; or
- scope, Ruff, Pyright, diff-check, hash, or clean-worktree gates fail for a new cause.

Do not tune fixtures, queries, spans, keys, order, score groups, thresholds, or validators after a
stop. Do not consume holdout again.

## Non-Claims

- Task 6R does not make the historical matrix fully green.
- Task 7A does not publish canonical compatibility evidence.
- A green historical matrix proves bounded validator/current-replay compatibility, not that
  revision 2 produced historical observations.
- Development/holdout proof covers the frozen deterministic-order mechanism only.
- No result proves contextual retrieval, segmentation quality, general RAG quality, production
  adoption, enterprise readiness, latency improvement, or user/business impact.
- No comparison-only result authorizes runtime promotion.
- This amendment adds no new Agent memory, compilation, multimodal, or knowledge-base capability.

## Deferred Taste Decisions

These do not block this stage and remain out of scope:

- replace raw SQL trace inspection with typed diagnostic fields;
- retain or deprecate the internal `current` subcommand after the stage;
- replace the explicit historical matrix with pytest markers.

They require separate evidence and must not be smuggled into this repair.

## Final Acceptance

- [ ] **C1 (P1)** — Add Task 6R numeric live/archive REDs and explicit loader separation.
- [ ] **C2 (P1)** — Remove the numeric shadow validator while preserving corpus facts.
- [ ] **C3 (P1)** — Add Chinese MATCH-only trace REDs, config-probe allowance, and privacy test.
- [ ] **C4 (P1)** — Replace stale live workflow assertions with archived-record validation.
- [ ] **C5 (P1)** — Run Task 6R gates, commit, and obtain authority code-diff review.
- [ ] **C6 (P1)** — Implement the shared absent-or-complete atomic publication helper, Task 7A
  temporary compatibility, and dynamic numeric test scaffolding without weakening production
  defaults.
- [ ] **C7 (P1)** — Freeze E1/E2 historical subprocess capability before current replay, assert
  exact interpreter/module origins and 14-item authority; reject temporary canonical output; run
  the 133-test historical matrix plus compatibility/runtime gates, commit, and obtain authority
  review.
- [ ] **C8 (P1)** — Implement Task 8A workflow/artifact state machine with receipt-bound canonical
  holdout capability on every holdout path, metadata-only/lazy partition loading, pure read-only
  validators, synthetic holdout tests, pre-seal `record-canonical` integration, atomic publication
  reuse, stable error/help contracts, then verify and commit.
- [ ] **C9 (P1)** — Complete original Task 9 installed-proof code/tests, ADR, docs, and
  documentation tests; run pre-observation verification and seal the final clean HEAD.
- [ ] **C10 (P1)** — Run Task 8B development once, then holdout once if development authorizes it.
- [ ] **C11 (P1)** — Atomically record canonical compatibility after holdout; create the detached
  attempt receipt and compatibility artifact; create the detached clean proof worktree; publish
  one external source-pack attempt claim; run source-pack build/proof once; run final historical,
  full, CI, and same-wheel installed/export proof plus read-only source-pack result validation
  without canonical holdout replay.
- [ ] **C12 (P1)** — Commit only five canonical proof artifacts and return for authority review.
