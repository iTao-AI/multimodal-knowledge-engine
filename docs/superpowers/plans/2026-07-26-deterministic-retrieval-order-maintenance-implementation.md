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

## Task 7: Close historical revision-2 compatibility

**Files:**
- Create: `src/mke/evaluation/retrieval_order_compatibility.py`
- Create: `tests/evaluation/test_retrieval_order_compatibility.py`
- Create: `benchmarks/retrieval/retrieval-order-v2-compatibility.json`

**Interfaces:**
- Produces:

```python
def build_retrieval_order_compatibility(
    *, repository_root: Path, protocol_path: Path
) -> dict[str, object]

def validate_retrieval_order_compatibility(
    *, artifact_path: Path, repository_root: Path, protocol_path: Path
) -> None
```

- [ ] **Step 1: Write the revision-2 differential RED**

Tests first copy the Task 0 artifacts, run every current replay, and require:

```python
assert compatibility["candidate_strategy_revision"] == 2
assert compatibility["query_policy_revision"] == 1
assert all(family["membership_delta"] == 0 for family in families)
assert all(family["score_hex_delta"] == 0 for family in families)
assert all(family["non_tied_pair_delta"] == 0 for family in families)
assert all(family["metrics_delta"] == {} for family in families)
assert all(family["gate_delta"] == {} for family in families)
assert all(family["verdict_delta"] is None for family in families)
```

Before implementation, the record/module is absent and the test fails at import.

- [ ] **Step 2: Implement current-source replay for every inventoried family**

Use the existing model-free runners and validators. Do not reload an embedding model or change a
historical scorer. E1/E2/E3-A replay the current runtime against their frozen manifests; E3-B keeps
its evaluation-only revision-1 scorer; E3-C/D/E recompute from their frozen artifacts and protocol
inputs.

For each ordered query result, compare stable projection, exact score hex when available, and all
pairwise order relations. Classify a changed pair as allowed only when both rows belong to the
same preregistered exact-score group.

- [ ] **Step 3: Build the revision-2 differential**

The compatibility artifact binds:

```text
schema_version=mke.retrieval_order_compatibility.v1
candidate_strategy_revision=2
query_policy_revision=1
current source-file identities
fixed runtime profile
each Task 0 historical artifact path and SHA-256
preidentified equal-score groups
before and after stable projections
FTS score float.hex values
candidate membership
non-tied pair order
recomputed metrics, gates, and verdicts
```

Only a permutation wholly inside a preidentified exact-score group is allowed. The validator
recomputes the record from current source and fails on any extra/missing row or field.

- [ ] **Step 4: Run the complete historical validator matrix**

```bash
uv run pytest -q \
  tests/evaluation/test_baseline.py \
  tests/evaluation/test_numeric_artifact.py \
  tests/evaluation/test_chinese_artifact.py \
  tests/evaluation/test_cjk_lexical_artifact.py \
  tests/evaluation/test_dense_artifact.py \
  tests/evaluation/test_hybrid_rrf_artifact.py \
  tests/evaluation/test_relevance_gate_artifact.py \
  tests/evaluation/test_retrieval_order_compatibility.py
```

Expected: pass. Re-run `shasum -a 256` for every Task 0 historical artifact and protocol; all
values remain exact.

- [ ] **Step 5: Commit Task 7**

```bash
git add \
  src/mke/evaluation/retrieval_order_compatibility.py \
  tests/evaluation/test_retrieval_order_compatibility.py \
  benchmarks/retrieval/retrieval-order-v2-compatibility.json
git diff --cached --check
git commit -m "test(eval): bind retrieval order compatibility"
```

## Task 8: Freeze development and execute holdout once

**Files:**
- Create: `src/mke/evaluation/retrieval_order_artifact.py`
- Create: `tests/evaluation/test_retrieval_order_artifact.py`
- Create: the three canonical benchmark files for freeze, receipt, and artifact.
- Modify: `src/mke/evaluation/retrieval_order_workflow.py`
- Modify: `tests/evaluation/test_retrieval_order_workflow.py`

**Interfaces:**
- Produces the exact maintainer commands from the spec and canonical state transitions:

```text
development: not_recorded -> passed + exclusive freeze
holdout: not_observed -> receipt_committed -> observed
runtime_promotion_status: not_evaluated
```

- [ ] **Step 1: Add workflow and artifact state-machine tests**

Tests reject:

- dirty product source before development;
- protocol/hash/profile/source mismatch;
- development freeze overwrite;
- holdout before passing development;
- holdout candidate HEAD/profile mismatch;
- missing receipt;
- receipt overwrite or canonical retry;
- raw query/Evidence/ID/cursor/path in output;
- non-empty stderr for valid `--json`;
- wrong exit codes;
- artifact tampering in score, membership, order, partition, status, or SHA.

- [ ] **Step 2: Implement exclusive state transitions**

Development records current clean candidate HEAD and profile. Holdout permits exactly the
development-freeze file as expected generated state while requiring product source, tests,
protocol, and fixtures to match the candidate identity. It exclusive-creates the receipt before
opening holdout cases.

The workflow never retries holdout internally and never deletes a failed receipt.

- [ ] **Step 3: Commit all candidate code before canonical observation**

Run focused tests, Ruff, Pyright, and `git diff --check`; then commit workflow/artifact code and
tests:

```bash
git add \
  src/mke/evaluation/retrieval_order_artifact.py \
  src/mke/evaluation/retrieval_order_workflow.py \
  tests/evaluation/test_retrieval_order_artifact.py \
  tests/evaluation/test_retrieval_order_workflow.py
git diff --cached --check
git commit -m "feat(eval): validate deterministic retrieval order"
```

Verify:

```bash
git status --porcelain
git rev-parse HEAD
```

Expected: empty status. Record this SHA as the candidate commit.

- [ ] **Step 4: Run the canonical development command once**

```bash
uv run python -m mke.evaluation.retrieval_order_workflow development \
  --protocol tests/fixtures/retrieval-order-v1/protocol.json \
  --record-development-freeze \
    benchmarks/retrieval/retrieval-order-v1-development-freeze.json \
  --json
```

Expected: exit 0, empty stderr, `stable_order_rate=1.0`, and every delta gate 0.

If this command returns nonzero, stop. Do not inspect or run holdout.

- [ ] **Step 5: Run the canonical public nonblind holdout once**

Without committing or modifying product files after Step 4:

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

Expected: exit 0, empty stderr, `stable_order_rate=1.0`, and every delta gate 0.

Do not run this command again.

- [ ] **Step 6: Validate the artifact and immutable retry rejection**

```bash
uv run python -m mke.evaluation.retrieval_order_artifact validate \
  --artifact benchmarks/retrieval/retrieval-order-v1-artifact.json \
  --protocol tests/fixtures/retrieval-order-v1/protocol.json \
  --repository .
```

Expected: exit 0. A test against a copied temporary fixture proves the second holdout attempt exits
1 without changing receipt/artifact bytes; do not retry the canonical path.

- [ ] **Step 7: Commit the three observation files together**

```bash
git add \
  benchmarks/retrieval/retrieval-order-v1-development-freeze.json \
  benchmarks/retrieval/retrieval-order-v1-holdout-receipt.json \
  benchmarks/retrieval/retrieval-order-v1-artifact.json
git commit -m "test(eval): record deterministic retrieval order proof"
```

## Task 9: Complete installed proof, documentation, and full verification

**Files:**
- Create: `scripts/retrieval_order_installed_proof.py`
- Create: `tests/scripts/test_retrieval_order_installed_proof.py`
- Create: `docs/decisions/0012-deterministic-retrieval-order.md`
- Create: `docs/how-to/run-deterministic-retrieval-order-proof.md`
- Create: `tests/evaluation/test_retrieval_order_documentation.py`
- Modify: documentation paths in the exact file map.

**Interfaces:**
- Consumes: one built wheel, the frozen protocol/artifact, and current Python/CLI/MCP contracts.
- Produces one bounded JSON installed-proof receipt with no public API change.

- [ ] **Step 1: Write the installed-proof RED**

The proof must:

1. build one wheel from the clean candidate;
2. install the same wheel into external Python 3.12 and 3.13 environments;
3. run the frozen inverse fresh-store fixture in an arbitrary external cwd;
4. compare stable projections through Python Search, CLI Search/Ask, and real stdio MCP v1/v2;
5. exercise MCP page sizes 1/2/full and budget-shortened continuation;
6. confirm exact Read still addresses opaque Evidence IDs;
7. deny network and source-checkout imports;
8. report wheel SHA-256, candidate commit, interpreter versions, projection digest, and schema
   digests; and
9. clean only its own temporary directory.

Tests inject timeout, wrong wheel, source import, schema drift, order drift, and child-process
failure. Every case exits nonzero with bounded stderr and no absolute path in JSON.

- [ ] **Step 2: Implement the installed proof**

Reuse reviewed subprocess/environment helpers from `consumer_source_pack_proof.py`; do not copy its
process orchestration. Do not modify the frozen consumer source-pack fixture or tool schema files.

The proof is a repository/installed-artifact controller, not a new `mke` command.

- [ ] **Step 3: Write ADR and public documentation**

ADR 0012 records:

- FTS and CJK path-specific stable keys;
- duplicate locator admissibility and no migration;
- typed recovery;
- three revision bumps and query-policy revision 1;
- Search/Read cursor behavior;
- historical observation immutability and separate revision-2 compatibility; and
- mechanism-only development/holdout non-claims.

Docs state:

```text
On cursor_expired, discard the complete partial Search traversal.
On retrieval_authority_invalid, stop using the database.
Run retrieval doctor.
Restore a valid backup or re-ingest Sources into a new database.
Never delete duplicates in place.
```

No release note changes in this phase.

- [ ] **Step 4: Run focused documentation and installed-proof tests**

```bash
uv run pytest -q \
  tests/scripts/test_retrieval_order_installed_proof.py \
  tests/evaluation/test_retrieval_order_documentation.py \
  tests/evaluation/test_chinese_documentation.py \
  tests/evaluation/test_mcp_context_completeness_documentation.py
```

Expected: pass.

- [ ] **Step 5: Run the complete local verification matrix**

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
UV_OFFLINE=1 uv run mke proof run
UV_OFFLINE=1 uv run mke demo --verify
```

Run the exact same-wheel installed order proof, consumer source-pack proof, and compiled Library
export proof with explicit Python 3.12 and 3.13 interpreters available on the host:

```bash
UV_OFFLINE=1 uv run python scripts/retrieval_order_installed_proof.py \
  --python "$(command -v python3.12)" \
  --python "$(command -v python3.13)" \
  --json
UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py \
  --python "$(command -v python3.12)" \
  --python "$(command -v python3.13)" \
  --json
UV_OFFLINE=1 uv run python scripts/compiled_library_export_proof.py \
  --python "$(command -v python3.12)" \
  --python "$(command -v python3.13)" \
  --json
```

Resolve the two interpreter paths using the same checked-in proof instructions; never guess or
download an interpreter. If either supported interpreter is unavailable, report the exact
environment blocker and do not claim the two-version proof.

- [ ] **Step 6: Verify final scope and commit documentation/proof**

```bash
git diff --check
git status --short
git diff --stat main...HEAD
```

Confirm:

```text
no historical observation bytes changed
no public schema/tool/request field changed
no dependency or migration changed
no segmentation/contextual retrieval code exists
no release/version file changed
```

Stage exact Task 9 paths and commit:

```bash
git add \
  scripts/retrieval_order_installed_proof.py \
  tests/scripts/test_retrieval_order_installed_proof.py \
  docs/decisions/0012-deterministic-retrieval-order.md \
  docs/how-to/run-deterministic-retrieval-order-proof.md \
  tests/evaluation/test_retrieval_order_documentation.py \
  docs/explanation/architecture.md \
  docs/reference/contracts.md \
  docs/reference/mcp-contract.md \
  docs/reference/cli.md \
  docs/how-to/use-mke-mcp.md \
  docs/how-to/enable-cjk-retrieval.md \
  docs/README.md
git diff --cached --check
git commit -m "docs(retrieval): document deterministic order proof"
```

- [ ] **Step 7: Prepare the authority-review handoff**

Return:

```text
final HEAD and commit list
changed paths
targeted RED evidence
development freeze SHA-256
holdout receipt/artifact SHA-256
revision-2 compatibility SHA-256
focused/full/Ruff/Pyright/build/proof results
historical immutable hash comparison
installed Python/CLI/MCP result
remaining non-claims
```

Do not push or create a PR. The next gate is a findings-only full branch-diff authority review.

## Final Acceptance

The implementation is ready for authority review only when all statements are true:

- FTS and CJK return identical stable projections across inverse fresh stores.
- Scores, membership, non-tied order, active-only authority, and public schemas are unchanged.
- Duplicate Run-local locators fail before Publication.
- Invalid legacy candidates fail closed and `retrieval doctor` audits the full active authority.
- Three runtime descriptors and CJK active-scan parameters report revision 2; query policy remains
  revision 1.
- Revision-1 Search cursors expire with full-traversal restart; exact Read continuity and owner
  restart behavior are proven.
- Development and the one canonical public nonblind holdout both pass exact mechanism gates.
- Every Task 0 historical artifact/protocol byte remains unchanged.
- Revision-2 compatibility permits only preregistered equal-score permutations and preserves all
  metrics, gates, and verdicts.
- Python 3.12/3.13 installed-wheel Python/CLI/MCP, consumer source-pack, and compiled-export proofs
  pass against the reviewed candidate.
- Full pytest, Ruff, Pyright, build, product proof, and demo pass.
- No push, PR, merge, release, deployment, promotion, segmentation, or contextual retrieval has
  occurred.
