# CJK Lexical Dense RRF Fusion Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record a comparison-only E3-D rank-only RRF fusion candidate over the current CJK
lexical runtime arm and the E3-C dense arm, without changing normal Search, Ask, CLI runtime, MCP,
Publication, or runtime defaults.

**Architecture:** Add model-free evaluation modules that load the canonical E3-C dense artifact,
bind lexical and dense observations to stable Evidence identity, run deterministic rank-only RRF,
record development and holdout artifacts, and validate every derived field independently. Dense
cache-ready replay remains optional corroboration, not an E3-D acceptance gate or second fusion
scoring source.

**Tech Stack:** Python 3.12/3.13, SQLite-backed existing evaluation fixtures, JSON artifacts,
pytest, Ruff, Pyright, Hatch/uv, existing `mke eval` CLI patterns.

---

Status: implementation complete with a development valid negative; holdout was not observed. This
plan depends on the approved
[CJK Lexical Dense RRF Fusion Candidate Design](../specs/2026-06-30-cjk-lexical-dense-rrf-fusion-design.md).

Planning base: `main@0fe1d5640f914e8307ec938e36ba145419c64872`.

Recommended implementation branch:

```bash
git switch main
git fetch origin
git pull --ff-only
git worktree add .worktrees/e3d-rrf-fusion -b codex/e3d-rrf-fusion origin/main
cd .worktrees/e3d-rrf-fusion
```

Use `high` reasoning depth for implementation and review fixes. Use `xhigh` only for protocol,
artifact-integrity, holdout-observation, or architecture-amendment stop conditions.

## Non-Negotiable Boundaries

- E3-D is comparison-only. Do not change the runtime default `cjk-active-scan-overlap-v1`.
- Do not change normal Search, Ask, MCP, owner-startup, Publication, ingestion, or runtime
  strategy behavior.
- Do not change the dense model, model revision, prompt, threshold, projection, or model-cache
  contract.
- Do not implement API embeddings, reranking, query rewrite, HyDE, Passage/chunk segmentation,
  HTTP, UI, Milvus, Redis, pgvector, or a persistent production vector projection.
- Do not combine lexical and dense raw scores. RRF must use ranks only.
- Do not alter E1/E2/E3-A/E3-B/E3-C qrels, fixtures, observations, metrics, gates, or verdicts.
  Source/scope identity refresh is allowed only after proving normalized semantic equality.
- Do not observe holdout unless development has been frozen with exclusive-create semantics.
- Do not rerun dense scoring to tune E3-D. E3-D consumes the canonical E3-C dense artifact.
- If development gates fail, record a valid negative and do not observe holdout.
- If current-runtime semantic observations drift from Task 0 snapshots, stop for planning review.
- If a validator failure requires changing a gate or candidate contract, stop for planning review.

## File Structure

Create or modify these files:

| File | Responsibility |
|---|---|
| `src/mke/evaluation/rrf_fusion.py` | Pure rank-only RRF contract, scoring, deterministic tie-breaks, and diagnostics. |
| `src/mke/evaluation/hybrid_rrf_protocol.py` | Frozen E3-D protocol lock builder/validator. |
| `src/mke/evaluation/hybrid_rrf_workflow.py` | Development/holdout workflow and artifact construction. |
| `src/mke/evaluation/hybrid_rrf_artifact.py` | Model-free canonical artifact validator and CLI entrypoint. |
| `src/mke/cli.py` | `mke eval retrieval-hybrid-rrf` command and stable public error rendering. |
| `src/mke/evaluation/__init__.py` | Lazy exports only if needed; avoid import-time heavy dependencies. |
| `tests/evaluation/test_rrf_fusion.py` | Unit tests for fusion, dedupe, tie-breaks, and diagnostics. |
| `tests/evaluation/test_hybrid_rrf_protocol.py` | Protocol lock tests. |
| `tests/evaluation/test_hybrid_rrf_workflow.py` | Development/holdout state machine and semantic drift tests. |
| `tests/evaluation/test_hybrid_rrf_artifact.py` | Artifact validator regression tests. |
| `tests/interfaces/test_cli_evaluation.py` or existing CLI evaluation tests | CLI success/failure tests. |
| `tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json` | Canonical E3-D protocol lock. |
| `benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-development-freeze.json` | Development freeze artifact. |
| `benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json` | Canonical E3-D comparison artifact. |
| `benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-holdout-receipt.json` | Exclusive holdout observation receipt. |
| `docs/how-to/evaluate-hybrid-rrf-retrieval.md` | Reproduction guide and interpretation boundary. |
| `docs/explanation/architecture.md` | Explain E3-D as comparison-only; no runtime promotion. |
| `docs/README.md` | Link the new how-to, plan, and final review. |
| `docs/superpowers/plans/2026-06-30-cjk-lexical-dense-rrf-fusion-implementation.md` | Keep checklist and completion evidence current. |
| `docs/superpowers/reviews/2026-06-30-cjk-lexical-dense-rrf-fusion-review.md` | Durable final/pre-PR review record after implementation review. |

## Task 0: Baseline And Snapshot Gate

**Files:**

- Read: `AGENTS.md`
- Read: `docs/superpowers/specs/2026-06-30-cjk-lexical-dense-rrf-fusion-design.md`
- Read: `benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json`
- Read: `tests/fixtures/retrieval-dense-v1/protocol-lock.json`
- Read: `tests/fixtures/retrieval-chinese-v1/protocol.json`
- Read: `src/mke/retrieval/strategy.py`

- [x] **Step 1: Confirm implementation starts from latest main**

Run:

```bash
git status --short --branch
git rev-parse HEAD origin/main
git merge-base --is-ancestor origin/main HEAD
gh pr list --state open --json number,title,headRefName,mergeStateStatus,isDraft,url
```

Expected: branch is clean and based on the intended latest `origin/main`; no open prerequisite PR
blocks E3-D. If the branch is not based on latest `origin/main`, stop and recreate the worktree.

- [x] **Step 2: Run current baseline validators before editing**

Run:

```bash
uv run mke eval retrieval \
  --manifest tests/fixtures/retrieval-eval-v1.json --json > /tmp/mke-e1-before.json
uv run mke eval retrieval-numeric \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --json > /tmp/mke-e2-before.json
uv run mke eval retrieval-chinese \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --json > /tmp/mke-e3a-before.json
uv run mke eval retrieval-cjk-lexical \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --candidate cjk-trigram-overlap-v1 \
  --json > /tmp/mke-e3b-before.json
uv run python -m mke.evaluation.baseline \
  --artifact benchmarks/retrieval/retrieval-eval-v1-baseline.json \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --repository .
uv run python -m mke.evaluation.numeric_artifact validate \
  --artifact benchmarks/retrieval/numeric-grouping-v1-comparison.json \
  --observed /tmp/mke-e2-before.json \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --repository .
uv run python -m mke.evaluation.chinese_artifact validate \
  --artifact benchmarks/retrieval/retrieval-chinese-v1-baseline.json \
  --observed /tmp/mke-e3a-before.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
uv run python -m mke.evaluation.cjk_lexical_artifact validate \
  --artifact benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json \
  --observed /tmp/mke-e3b-before.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
uv run python -m mke.evaluation.dense_artifact validate \
  --artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --protocol tests/fixtures/retrieval-dense-v1/protocol-lock.json \
  --repository .
```

Expected: every validator passes. If a validator fails only because source identity includes future
E3-D files, do not refresh now; that belongs after implementation and semantic equality checks.

- [x] **Step 3: Save normalized pre-change semantic snapshots**

Create a local-only helper under `/tmp`, not the repository:

```bash
python - <<'PY'
import json
from pathlib import Path

def normalize(value):
    if isinstance(value, dict):
        return {
            k: normalize(v)
            for k, v in sorted(value.items())
            if k not in {"duration_ms", "elapsed_ms", "created_at", "environment"}
        }
    if isinstance(value, list):
        return [normalize(v) for v in value]
    return value

for name in ("e1", "e2", "e3a", "e3b"):
    source = Path(f"/tmp/mke-{name}-before.json")
    target = Path(f"/tmp/mke-{name}-before-normalized.json")
    target.write_text(json.dumps(normalize(json.loads(source.read_text())), sort_keys=True))
PY
```

Expected: four normalized files exist under `/tmp`. They are comparison aids only and must not be
committed.

## Task 1: Implement The Pure RRF Contract

**Files:**

- Create: `src/mke/evaluation/rrf_fusion.py`
- Create: `tests/evaluation/test_rrf_fusion.py`

- [x] **Step 1: Write RED tests for rank-only scoring and validation**

Add tests shaped like:

```python
import pytest

from mke.evaluation.rrf_fusion import (
    ArmRankedResult,
    RrfCandidateConfig,
    RrfFusionError,
    fuse_ranked_results,
)


def result(locator: str, rank: int, arm: str = "lexical") -> ArmRankedResult:
    return ArmRankedResult(
        arm_id=arm,
        stable_locator_id=locator,
        document_id=locator.split("|")[0],
        locator_kind="page",
        locator_start=1,
        locator_end=1,
        source_text_digest="sha256:" + "1" * 64,
        rank=rank,
    )


def test_rrf_uses_rank_not_raw_score() -> None:
    config = RrfCandidateConfig.default()
    fused = fuse_ranked_results(
        query_id="q1",
        lexical=(result("doc-a|page|1|1|x", 10),),
        dense=(result("doc-b|page|1|1|y", 1, arm="dense"),),
        config=config,
    )
    assert [row.stable_locator_id for row in fused[:2]] == [
        "doc-b|page|1|1|y",
        "doc-a|page|1|1|x",
    ]


def test_duplicate_locator_merges_arm_contributions() -> None:
    config = RrfCandidateConfig.default()
    fused = fuse_ranked_results(
        query_id="q1",
        lexical=(result("doc-a|page|1|1|x", 1),),
        dense=(result("doc-a|page|1|1|x", 3, arm="dense"),),
        config=config,
    )
    assert len(fused) == 1
    assert fused[0].arms == ("dense", "lexical")
    assert fused[0].lexical_rank == 1
    assert fused[0].dense_rank == 3


def test_invalid_rank_bool_fails() -> None:
    config = RrfCandidateConfig.default()
    bad = ArmRankedResult(
        arm_id="lexical",
        stable_locator_id="doc|page|1|1|x",
        document_id="doc",
        locator_kind="page",
        locator_start=1,
        locator_end=1,
        source_text_digest="sha256:" + "1" * 64,
        rank=True,  # type: ignore[arg-type]
    )
    with pytest.raises(RrfFusionError, match="rank"):
        fuse_ranked_results(query_id="q1", lexical=(bad,), dense=(), config=config)
```

- [x] **Step 2: Run RED tests**

Run:

```bash
uv run pytest tests/evaluation/test_rrf_fusion.py -q
```

Expected: fails because `mke.evaluation.rrf_fusion` does not exist.

- [x] **Step 3: Implement minimal RRF dataclasses and fusion**

Implement `src/mke/evaluation/rrf_fusion.py` with these public names:

```python
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


class RrfFusionError(ValueError):
    """Raised when RRF input or derived output is invalid."""


@dataclass(frozen=True)
class RrfCandidateConfig:
    candidate_id: str
    candidate_revision: int
    k: int
    lexical_weight: float
    dense_weight: float
    input_depth: int
    output_depth: int
    score_decimals: int

    @classmethod
    def default(cls) -> "RrfCandidateConfig":
        return cls(
            candidate_id="cjk-active-scan-qwen3-rrf-v1",
            candidate_revision=1,
            k=60,
            lexical_weight=1.0,
            dense_weight=1.0,
            input_depth=10,
            output_depth=10,
            score_decimals=12,
        )


@dataclass(frozen=True)
class ArmRankedResult:
    arm_id: str
    stable_locator_id: str
    document_id: str
    locator_kind: str
    locator_start: int
    locator_end: int
    source_text_digest: str
    rank: int


@dataclass(frozen=True)
class FusedRrfResult:
    query_id: str
    stable_locator_id: str
    document_id: str
    locator_kind: str
    locator_start: int
    locator_end: int
    source_text_digest: str
    rank: int
    portable_score: str
    arms: tuple[str, ...]
    lexical_rank: int | None
    dense_rank: int | None
    best_individual_rank: int


def fuse_ranked_results(
    *,
    query_id: str, lexical: tuple[ArmRankedResult, ...],
    dense: tuple[ArmRankedResult, ...], config: RrfCandidateConfig,
) -> tuple[FusedRrfResult, ...]
```

Implementation rules:

- reject non-string or empty `query_id`;
- reject `bool`, zero, negative, or non-int ranks;
- reject duplicate locators inside one arm;
- truncate each arm to `input_depth`;
- compute `weight / (k + rank)` with rank base `1`;
- format score with `Decimal` from stringified float and `ROUND_HALF_UP`;
- sort by score descending, arm count descending, best individual rank ascending, lexical rank
  ascending with missing as `999999`, dense rank ascending with missing as `999999`,
  stable locator ID ascending;
- output at most `output_depth`.

The signature above is the required public function signature. The implementation must provide a
real body following the rules in this step before the GREEN test run.

- [x] **Step 4: Run fusion tests**

Run:

```bash
uv run pytest tests/evaluation/test_rrf_fusion.py -q
```

Expected: all `test_rrf_fusion.py` tests pass.

- [x] **Step 5: Commit Task 1**

Run:

```bash
git add src/mke/evaluation/rrf_fusion.py tests/evaluation/test_rrf_fusion.py
git commit -m "feat(eval): add rank-only RRF fusion contract"
```

## Task 2: Freeze The E3-D Protocol Lock

**Files:**

- Create: `src/mke/evaluation/hybrid_rrf_protocol.py`
- Create: `tests/evaluation/test_hybrid_rrf_protocol.py`
- Create: `tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json`

- [x] **Step 1: Write RED protocol tests**

Add tests for:

- schema version exactly `mke.hybrid_rrf_protocol.v1`;
- candidate ID exactly `cjk-active-scan-qwen3-rrf-v1`;
- candidate revision is non-bool integer `1`;
- RRF config is exactly `k=60`, equal weights, input depth `10`, output depth `10`;
- arms are exactly `cjk-active-scan-overlap-v1` and `qwen3-embedding-0.6b-exact-v1`;
- bound inputs include Chinese protocol, qrels, E3-C dense artifact, runtime strategy source,
  RRF source, workflow source, artifact source, metrics source, and CLI source;
- mutating any input file identity fails validation;
- malformed locator or bad candidate value raises `HybridRrfProtocolError`.

Use this test shape:

```python
from pathlib import Path

import pytest

from mke.evaluation.hybrid_rrf_protocol import (
    HybridRrfProtocolError,
    build_hybrid_rrf_protocol_lock,
    render_hybrid_rrf_protocol_lock_json,
    validate_hybrid_rrf_protocol_lock,
)


def test_protocol_lock_is_byte_stable(repository_root: Path) -> None:
    protocol = build_hybrid_rrf_protocol_lock(repository_root=repository_root)
    rendered = render_hybrid_rrf_protocol_lock_json(protocol)
    assert rendered.endswith("\\n")
    validate_hybrid_rrf_protocol_lock(protocol, repository_root=repository_root)


def test_protocol_rejects_bool_revision(repository_root: Path) -> None:
    protocol = build_hybrid_rrf_protocol_lock(repository_root=repository_root)
    protocol["candidate"]["candidate_revision"] = True
    with pytest.raises(HybridRrfProtocolError, match="candidate"):
        validate_hybrid_rrf_protocol_lock(protocol, repository_root=repository_root)
```

- [x] **Step 2: Run RED protocol tests**

Run:

```bash
uv run pytest tests/evaluation/test_hybrid_rrf_protocol.py -q
```

Expected: fails because the module does not exist.

- [x] **Step 3: Implement protocol builder and validator**

Implement `src/mke/evaluation/hybrid_rrf_protocol.py` with:

```python
SCHEMA_VERSION = "mke.hybrid_rrf_protocol.v1"
CANDIDATE_ID = "cjk-active-scan-qwen3-rrf-v1"
CANDIDATE_REVISION = 1
LEXICAL_ARM_ID = "cjk-active-scan-overlap-v1"
DENSE_ARM_ID = "qwen3-embedding-0.6b-exact-v1"
```

The builder must produce deterministic sorted JSON containing:

- candidate fields;
- RRF config fields;
- arm IDs;
- split IDs `development` and `holdout`;
- references to:
  - `tests/fixtures/retrieval-chinese-v1/protocol.json`;
  - `tests/fixtures/retrieval-chinese-v1/qrel-adjudication.json`;
  - `benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json`;
  - `src/mke/retrieval/strategy.py`;
  - `src/mke/evaluation/rrf_fusion.py`;
  - `src/mke/evaluation/hybrid_rrf_protocol.py`;
  - `src/mke/evaluation/hybrid_rrf_workflow.py`;
  - `src/mke/evaluation/hybrid_rrf_artifact.py`;
  - `src/mke/evaluation/graded_metrics.py`;
  - `src/mke/cli.py`.

Use `Path.read_bytes()` and SHA-256 for file identities. Reject absolute paths and missing files
with `HybridRrfProtocolError("hybrid RRF protocol identity drift")`.

- [x] **Step 4: Generate the checked-in protocol lock**

Run:

```bash
mkdir -p tests/fixtures/retrieval-hybrid-rrf-v1
uv run python - <<'PY'
from pathlib import Path
from mke.evaluation.hybrid_rrf_protocol import (
    build_hybrid_rrf_protocol_lock,
    render_hybrid_rrf_protocol_lock_json,
)
root = Path(".")
protocol = build_hybrid_rrf_protocol_lock(repository_root=root)
Path("tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json").write_text(
    render_hybrid_rrf_protocol_lock_json(protocol),
    encoding="utf-8",
)
PY
```

Expected: `tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json` is created and validates.

- [x] **Step 5: Run protocol tests**

Run:

```bash
uv run pytest tests/evaluation/test_hybrid_rrf_protocol.py -q
```

Expected: protocol tests pass.

- [x] **Step 6: Commit Task 2**

Run:

```bash
git add src/mke/evaluation/hybrid_rrf_protocol.py \
  tests/evaluation/test_hybrid_rrf_protocol.py \
  tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json
git commit -m "feat(eval): freeze hybrid RRF protocol"
```

## Task 3: Bind E3-C Arm Observations To Fusion Inputs

**Files:**

- Modify: `src/mke/evaluation/hybrid_rrf_workflow.py`
- Modify: `tests/evaluation/test_hybrid_rrf_workflow.py`

- [x] **Step 1: Write RED tests for arm extraction and identity binding**

Add tests for:

- extracting 24 development and 24 holdout dense observations from the E3-C artifact;
- extracting matching current-runtime lexical observations from the E3-C artifact;
- deriving lexical rank strictly from each observation's `retrieved_locators` list order;
- rejecting non-list lexical `retrieved_locators`, duplicate lexical locators for one query, or
  lexical rows missing `query_id`, `split`, or `category`;
- rebinding lexical locators to source-text digests through the dense artifact inventory;
- rejecting a lexical locator that cannot be rebound;
- filtering dense rows by the frozen E3-C selected threshold and proving a below-threshold dense row
  is excluded before RRF input construction;
- preserving dense arm rank from the recorded E3-C dense row after threshold filtering; thresholding
  must not renumber a surviving dense result;
- rejecting duplicate dense stable locator IDs;
- rejecting dense observations whose `rank` order disagrees with their list order or whose selected
  threshold disagrees between E3-C comparison state and threshold report;
- rejecting a dense artifact whose `e3d_status` is not `eligible`;
- rejecting a dense artifact whose `runtime_promotion_status` is not `not_evaluated`.

Use names:

```python
from mke.evaluation.hybrid_rrf_workflow import (
    HybridRrfWorkflowError,
    load_hybrid_rrf_inputs,
)


def test_load_hybrid_inputs_binds_development_and_holdout(repository_root: Path) -> None:
    inputs = load_hybrid_rrf_inputs(
        dense_artifact_path=repository_root / "benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json",
        protocol_path=repository_root / "tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json",
        repository_root=repository_root,
    )
    assert len(inputs.development.queries) == 24
    assert len(inputs.holdout.queries) == 24
    assert inputs.state.runtime_promotion_status == "not_evaluated"
```

- [x] **Step 2: Run RED workflow tests**

Run:

```bash
uv run pytest tests/evaluation/test_hybrid_rrf_workflow.py -q
```

Expected: fails because workflow module or functions do not exist.

- [x] **Step 3: Implement input DTOs and loader**

Add focused dataclasses:

```python
@dataclass(frozen=True)
class HybridRrfQueryInput:
    split: str
    query_id: str
    category: str
    lexical: tuple[ArmRankedResult, ...]
    dense: tuple[ArmRankedResult, ...]
    qrels: tuple[GradedQrel, ...]
    ask_status: str
    compiled_query_empty: bool
    ascii_token_count: int


@dataclass(frozen=True)
class HybridRrfPartitionInput:
    split: str
    queries: tuple[HybridRrfQueryInput, ...]


@dataclass(frozen=True)
class HybridRrfInputs:
    development: HybridRrfPartitionInput
    holdout: HybridRrfPartitionInput
    dense_artifact_sha256: str
    current_runtime_semantic_digest: str
```

Implementation notes:

- load and validate the E3-D protocol first;
- load and validate the E3-C dense artifact with the existing dense artifact validator;
- lexical observations come from `current_runtime.semantics.results`;
- dense observations come from `development_candidate.observations` and `holdout_candidate.observations`;
- lexical ranks are `1..N` from the recorded `retrieved_locators` order and must not use any lexical
  score field;
- only use dense results that satisfy the selected threshold already recorded by E3-C;
- dense ranks are the recorded E3-C `rank` values after threshold filtering; do not recompute,
  compress, or renumber dense ranks;
- use frozen locator inventory from dense candidate results and qrels to attach source-text digest;
- raise `HybridRrfWorkflowError` with stable messages, not raw JSON key errors.

- [x] **Step 4: Run input binding tests**

Run:

```bash
uv run pytest tests/evaluation/test_hybrid_rrf_workflow.py -q
```

Expected: all current workflow tests pass.

- [x] **Step 5: Commit Task 3**

Run:

```bash
git add src/mke/evaluation/hybrid_rrf_workflow.py tests/evaluation/test_hybrid_rrf_workflow.py
git commit -m "feat(eval): bind hybrid RRF arm inputs"
```

## Task 4: Compute Development Fusion And Diagnostics

**Files:**

- Modify: `src/mke/evaluation/hybrid_rrf_workflow.py`
- Modify: `tests/evaluation/test_hybrid_rrf_workflow.py`
- Modify: `tests/evaluation/test_rrf_fusion.py`

- [x] **Step 1: Write RED tests for development metrics and diagnostics**

Add tests that assert:

- development returns `development_status=passed` only when gates pass;
- development valid negative does not access holdout;
- `union_grade2_coverage_at_10` is recomputed from qrels and arm inputs;
- `fused_lost_union_grade2_count` detects relevant Evidence present in union but absent from top-5;
- `ranking_headroom_count` equals union-present-but-fused-missed count for answerable queries;
- per-arm recovery counts sum consistently for answerable queries;
- unanswerable and hard-negative rates are not trusted from input artifact fields.

Use this shape:

```python
from mke.evaluation.hybrid_rrf_workflow import run_hybrid_rrf_development


def test_development_records_complete_diagnostics(repository_root: Path) -> None:
    report = run_hybrid_rrf_development(
        protocol_path=repository_root / "tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json",
        dense_artifact_path=repository_root / "benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json",
        repository_root=repository_root,
    )
    assert report["candidate"]["candidate_id"] == "cjk-active-scan-qwen3-rrf-v1"
    assert report["development_status"] in {"passed", "valid_negative"}
    assert report["diagnostics"]["query_count"] == 24
    assert "union_grade2_coverage_at_10" in report["diagnostics"]
```

- [x] **Step 2: Run RED development tests**

Run:

```bash
uv run pytest tests/evaluation/test_hybrid_rrf_workflow.py tests/evaluation/test_rrf_fusion.py -q
```

Expected: fails because `run_hybrid_rrf_development` is not implemented.

- [x] **Step 3: Implement development runner**

Implement:

```python
def run_hybrid_rrf_development(
    *,
    protocol_path: Path,
    dense_artifact_path: Path,
    repository_root: Path,
) -> dict[str, object]
```

Rules:

- fuse only development queries;
- compute `GradedQueryMetricInput` from fused top-10;
- calculate metrics through existing `calculate_graded_metrics`;
- compute diagnostics independently from qrels and arm/fused results;
- compare fused metrics against lexical and dense input-arm metrics;
- if development gates fail, return `development_status="valid_negative"` with
  `holdout_status="not_observed"` and no holdout data;
- if development gates pass, return `development_status="passed"` with deterministic development
  payload ready to freeze.

The signature above is the required public function signature. The implementation must provide a
real body following the rules in this step before the GREEN test run.

- [x] **Step 4: Run development tests**

Run:

```bash
uv run pytest tests/evaluation/test_hybrid_rrf_workflow.py tests/evaluation/test_rrf_fusion.py -q
```

Expected: development tests pass.

- [x] **Step 5: Commit Task 4**

Run:

```bash
git add src/mke/evaluation/hybrid_rrf_workflow.py \
  tests/evaluation/test_hybrid_rrf_workflow.py \
  tests/evaluation/test_rrf_fusion.py
git commit -m "feat(eval): score hybrid RRF development"
```

## Task 5: Add Development Freeze And Holdout State Machine

**Files:**

- Modify: `src/mke/evaluation/hybrid_rrf_workflow.py`
- Modify: `tests/evaluation/test_hybrid_rrf_workflow.py`

- [x] **Step 1: Write RED state-machine tests**

Cover:

- `record_development_freeze` refuses to overwrite an existing freeze path;
- holdout refuses to run without a development freeze;
- holdout refuses when the development freeze is `valid_negative`;
- holdout receipt uses exclusive-create semantics;
- holdout cannot be observed twice;
- mutating the dense artifact after development freeze causes holdout failure;
- mutating protocol config after development freeze causes holdout failure.

Use this shape:

```python
def test_holdout_refuses_existing_receipt(tmp_path: Path, repository_root: Path) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_text("{}")
    with pytest.raises(HybridRrfWorkflowError, match="holdout"):
        run_hybrid_rrf_holdout(
            protocol_path=repository_root / "tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json",
            dense_artifact_path=repository_root / "benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json",
            development_freeze_path=tmp_path / "freeze.json",
            record_path=tmp_path / "comparison.json",
            holdout_receipt_path=receipt,
            repository_root=repository_root,
        )
```

- [x] **Step 2: Run RED holdout tests**

Run:

```bash
uv run pytest tests/evaluation/test_hybrid_rrf_workflow.py -q
```

Expected: fails on missing freeze/holdout functions.

- [x] **Step 3: Implement freeze and holdout functions**

Implement:

```python
def record_hybrid_rrf_development_freeze(
    *,
    report: dict[str, object],
    target_path: Path,
) -> dict[str, object]


def run_hybrid_rrf_holdout(
    *,
    protocol_path: Path,
    dense_artifact_path: Path,
    development_freeze_path: Path,
    record_path: Path,
    holdout_receipt_path: Path,
    repository_root: Path,
) -> dict[str, object]
```

Rules:

- freeze records protocol SHA, dense artifact SHA, candidate config, source identity, development
  metrics, and diagnostics;
- holdout validates freeze before reading holdout partition;
- holdout computes metrics and diagnostics independently;
- holdout writes receipt before comparison artifact finalization;
- `runtime_promotion_status` remains `not_evaluated`;
- `e3e_status` and `segmentation_status` derive only from diagnostics, not manual fields.

The signatures above are the required public function signatures. The implementation must provide
real bodies following the rules in this step before the GREEN test run.

- [x] **Step 4: Run holdout tests**

Run:

```bash
uv run pytest tests/evaluation/test_hybrid_rrf_workflow.py -q
```

Expected: holdout state-machine tests pass.

- [x] **Step 5: Commit Task 5**

Run:

```bash
git add src/mke/evaluation/hybrid_rrf_workflow.py tests/evaluation/test_hybrid_rrf_workflow.py
git commit -m "feat(eval): freeze hybrid RRF holdout state"
```

## Task 6: Add Canonical Artifact Validator

**Files:**

- Create: `src/mke/evaluation/hybrid_rrf_artifact.py`
- Create: `tests/evaluation/test_hybrid_rrf_artifact.py`

- [x] **Step 1: Write RED artifact validator tests**

Add tests for:

- checked-in artifact validates against protocol and repository;
- missing artifact exits non-zero through module CLI;
- tampering fused rank fails;
- tampering fused score fails;
- tampering arm contribution fails;
- tampering diagnostics fails;
- tampering `runtime_promotion_status` fails;
- coordinated artifact and observed-report tampering fails because validator recomputes from dense
  artifact and protocol;
- malformed locator and bool integer fields fail with `HybridRrfArtifactError`.

Use this shape:

```python
from mke.evaluation.hybrid_rrf_artifact import validate_hybrid_rrf_artifact


def test_artifact_validator_recomputes_from_inputs(repository_root: Path) -> None:
    validate_hybrid_rrf_artifact(
        artifact_path=repository_root / "benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json",
        protocol_path=repository_root / "tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json",
        dense_artifact_path=repository_root / "benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json",
        repository_root=repository_root,
    )
```

Before Task 8 records the canonical artifact, this test must point to a temporary generated artifact
under `tmp_path`. Do not leave a permanent skip. After Task 8, update the same test to validate the
checked-in canonical artifact.

- [x] **Step 2: Run RED artifact tests**

Run:

```bash
uv run pytest tests/evaluation/test_hybrid_rrf_artifact.py -q
```

Expected: fails because artifact module does not exist.

- [x] **Step 3: Implement model-free artifact validator and module CLI**

Implement:

```python
def validate_hybrid_rrf_artifact(
    *,
    artifact_path: Path,
    protocol_path: Path,
    dense_artifact_path: Path,
    repository_root: Path,
) -> None
```

Also support:

```bash
uv run python -m mke.evaluation.hybrid_rrf_artifact validate \
  --artifact benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json \
  --protocol tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json \
  --dense-artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --repository .
```

Success output: `hybrid RRF artifact valid`.

Failure behavior:

- exit non-zero;
- print stable message without traceback by default;
- reject repository-internal absolute private paths in public output.

The signature above is the required public function signature. The implementation must provide a
real body following the validator behavior in this step before the GREEN test run.

- [x] **Step 4: Run artifact tests with temporary artifact**

Run:

```bash
uv run pytest tests/evaluation/test_hybrid_rrf_artifact.py tests/evaluation/test_hybrid_rrf_workflow.py -q
```

Expected: all tests that do not require the final checked-in artifact pass. The temporary artifact
validator test must run against a `tmp_path` artifact rather than skip.

- [x] **Step 5: Commit Task 6**

Run:

```bash
git add src/mke/evaluation/hybrid_rrf_artifact.py tests/evaluation/test_hybrid_rrf_artifact.py
git commit -m "feat(eval): validate hybrid RRF artifacts"
```

## Task 7: Add CLI Command And Stable Errors

**Files:**

- Modify: `src/mke/cli.py`
- Modify: `src/mke/evaluation/__init__.py`
- Test: existing CLI evaluation test file or `tests/interfaces/test_cli_evaluation.py`

- [x] **Step 1: Write RED CLI tests**

Cover:

- `mke eval retrieval-hybrid-rrf --development-only` requires `--record-development-freeze`;
- holdout phase requires `--development-freeze`, `--record`, and `--record-holdout-receipt`;
- incompatible flags return usage exit `2`;
- protocol failure returns stable public JSON with `problem=rrf_protocol_invalid`;
- dense artifact failure returns `problem=rrf_dense_artifact_invalid`;
- existing `retrieval-dense` CLI still works;
- help text states comparison-only and no runtime promotion.

Use subprocess-style tests consistent with existing CLI tests.

- [x] **Step 2: Run RED CLI tests**

Run:

```bash
uv run pytest tests/interfaces/test_cli_evaluation.py -q
```

Expected: fails until CLI command exists.

- [x] **Step 3: Wire `retrieval-hybrid-rrf` under `mke eval`**

Follow existing parser style in `src/mke/cli.py`.

Required arguments:

- `--protocol`;
- `--candidate`;
- `--dense-artifact`;
- `--development-only`;
- `--record-development-freeze`;
- `--development-freeze`;
- `--record`;
- `--record-holdout-receipt`;
- `--json`.

Render success payloads as JSON when `--json` is set. Human output should include:

```text
candidate_status=<value>
development_status=<value>
holdout_status=<value>
e3e_status=<value>
segmentation_status=<value>
runtime_promotion_status=not_evaluated
```

Stable problems:

- `rrf_protocol_invalid`;
- `rrf_dense_artifact_invalid`;
- `rrf_development_freeze_missing`;
- `rrf_holdout_already_observed`;
- `rrf_identity_mismatch`;
- `rrf_artifact_invalid`.

- [x] **Step 4: Run CLI tests**

Run:

```bash
uv run pytest tests/interfaces/test_cli_evaluation.py tests/evaluation/test_hybrid_rrf_workflow.py -q
```

Expected: CLI and workflow tests pass.

- [x] **Step 5: Commit Task 7**

Run:

```bash
git add src/mke/cli.py src/mke/evaluation/__init__.py tests/interfaces/test_cli_evaluation.py
git commit -m "feat(cli): expose hybrid RRF evaluation"
```

## Task 8: Record Canonical Development And Holdout Artifacts

**Files:**

- Create: `benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-development-freeze.json`
- Create: `benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json`
- Not created after valid negative:
  `benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-holdout-receipt.json`
- Modify: tests that referenced temporary artifacts in Task 6

- [x] **Step 1: Run development phase once**

Run:

```bash
uv run mke eval retrieval-hybrid-rrf \
  --protocol tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json \
  --candidate cjk-active-scan-qwen3-rrf-v1 \
  --dense-artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --development-only \
  --record-development-freeze benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-development-freeze.json \
  --json > /tmp/mke-e3d-development.json
```

Expected:

- exits `0`;
- writes development freeze;
- prints `development_status=passed` or `valid_negative`.

If development is `valid_negative`, stop after Task 8 Step 3, do not run holdout, and update docs
to record the valid negative.

- [x] **Step 2: Skip holdout because development was `valid_negative`**

Run only when `/tmp/mke-e3d-development.json` reports `development_status=passed`:

```bash
uv run mke eval retrieval-hybrid-rrf \
  --protocol tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json \
  --candidate cjk-active-scan-qwen3-rrf-v1 \
  --dense-artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --development-freeze benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-development-freeze.json \
  --record benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json \
  --record-holdout-receipt benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-holdout-receipt.json \
  --json > /tmp/mke-e3d-holdout.json
```

Expected:

- exits `0`;
- creates comparison artifact and holdout receipt;
- `runtime_promotion_status=not_evaluated`;
- holdout receipt path did not exist before command.

- [x] **Step 3: Validate canonical artifact**

Run:

```bash
uv run python -m mke.evaluation.hybrid_rrf_artifact validate \
  --artifact benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json \
  --protocol tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json \
  --dense-artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --repository .
```

Expected: `hybrid RRF artifact valid`.

- [x] **Step 4: Switch temporary artifact tests to the checked-in artifact**

Update any Task 6 temporary-artifact test to use the checked-in artifact.

Run:

```bash
uv run pytest tests/evaluation/test_hybrid_rrf_artifact.py tests/evaluation/test_hybrid_rrf_workflow.py -q
```

Expected: no temporary artifact indirection remains for the canonical validation path; tests pass.

- [x] **Step 5: Commit Task 8**

Run:

```bash
git add benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-development-freeze.json \
  benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json \
  benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-holdout-receipt.json \
  tests/evaluation/test_hybrid_rrf_artifact.py \
  tests/evaluation/test_hybrid_rrf_workflow.py
git commit -m "test(eval): record hybrid RRF comparison artifact"
```

## Task 9: Historical Identity Refresh Gate

**Files:**

- Potentially modify:
  - `benchmarks/retrieval/retrieval-eval-v1-baseline.json`
  - `benchmarks/retrieval/numeric-grouping-v1-comparison.json`
  - `tests/fixtures/retrieval-numeric-v1/protocol-lock.json`
  - `benchmarks/retrieval/retrieval-chinese-v1-baseline.json`
  - `benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json`
  - `benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json`

- [x] **Step 1: Re-run historical observed evaluations**

Run:

```bash
uv run mke eval retrieval \
  --manifest tests/fixtures/retrieval-eval-v1.json --json > /tmp/mke-e1-after.json
uv run mke eval retrieval-numeric \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --json > /tmp/mke-e2-after.json
uv run mke eval retrieval-chinese \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --json > /tmp/mke-e3a-after.json
uv run mke eval retrieval-cjk-lexical \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --candidate cjk-trigram-overlap-v1 \
  --json > /tmp/mke-e3b-after.json
```

Expected: all commands exit `0`.

- [x] **Step 2: Compare normalized semantics to Task 0**

Run:

```bash
python - <<'PY'
import json
from pathlib import Path

def normalize(value):
    if isinstance(value, dict):
        return {
            k: normalize(v)
            for k, v in sorted(value.items())
            if k not in {"duration_ms", "elapsed_ms", "created_at", "environment"}
        }
    if isinstance(value, list):
        return [normalize(v) for v in value]
    return value

for name in ("e1", "e2", "e3a", "e3b"):
    before = json.loads(Path(f"/tmp/mke-{name}-before-normalized.json").read_text())
    after = normalize(json.loads(Path(f"/tmp/mke-{name}-after.json").read_text()))
    if before != after:
        raise SystemExit(f"{name} semantic drift")
    print(f"{name}: semantic_equal")
PY
```

Expected: prints semantic equality for all four. If any semantic drift occurs, stop for planning
review. Do not refresh artifacts.

- [x] **Step 3: Refresh only permitted source/scope identities if validators require it**

Run validators first. If they fail only because new E3-D source files changed source identity, use
the existing supported artifact refresh helpers. Do not alter metrics, observations, qrels,
fixtures, gates, verdicts, or protocol semantics.

Required validators after refresh:

```bash
uv run python -m mke.evaluation.baseline \
  --artifact benchmarks/retrieval/retrieval-eval-v1-baseline.json \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --repository .
uv run python -m mke.evaluation.numeric_artifact validate \
  --artifact benchmarks/retrieval/numeric-grouping-v1-comparison.json \
  --observed /tmp/mke-e2-after.json \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --repository .
uv run python -m mke.evaluation.chinese_artifact validate \
  --artifact benchmarks/retrieval/retrieval-chinese-v1-baseline.json \
  --observed /tmp/mke-e3a-after.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
uv run python -m mke.evaluation.cjk_lexical_artifact validate \
  --artifact benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json \
  --observed /tmp/mke-e3b-after.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
uv run python -m mke.evaluation.dense_artifact validate \
  --artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --protocol tests/fixtures/retrieval-dense-v1/protocol-lock.json \
  --repository .
```

Expected: all validators pass. Any required refresh is identity-only.

- [x] **Step 4: Commit Task 9 if files changed**

If no files changed, record that in the handoff. If files changed, run:

```bash
git add benchmarks/retrieval/retrieval-eval-v1-baseline.json \
  benchmarks/retrieval/numeric-grouping-v1-comparison.json \
  tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  benchmarks/retrieval/retrieval-chinese-v1-baseline.json \
  benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json \
  benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json
git commit -m "test(eval): refresh hybrid RRF artifact identities"
```

## Task 10: Documentation And Public Boundary

**Files:**

- Create: `docs/how-to/evaluate-hybrid-rrf-retrieval.md`
- Modify: `docs/explanation/architecture.md`
- Modify: `docs/README.md`
- Modify: `docs/superpowers/plans/2026-06-30-cjk-lexical-dense-rrf-fusion-implementation.md`
- Create: `docs/superpowers/reviews/2026-06-30-cjk-lexical-dense-rrf-fusion-review.md`
- Modify tests if existing documentation tests require a new expected document.

- [x] **Step 1: Write the how-to guide**

The guide must include:

- candidate ID and comparison-only status;
- exact development and holdout commands;
- artifact validator command;
- dense cache-ready replay command as optional corroboration, not scoring;
- current metrics table after Task 8;
- explicit non-scope: runtime promotion, API adapter, reranker, query rewrite, segmentation,
  HTTP/UI.

- [x] **Step 2: Update architecture and docs index**

Add one concise architecture paragraph:

```markdown
E3-D adds a comparison-only RRF fusion artifact over the current
`cjk-active-scan-overlap-v1` runtime observations and the E3-C
`qwen3-embedding-0.6b-exact-v1` dense observations. It uses rank-only fusion,
does not combine raw lexical and dense scores, and does not change Search, Ask,
MCP, owner startup, SQLite domain truth, or runtime default behavior.
```

Link the how-to, design, plan, and review from `docs/README.md`.

- [x] **Step 3: Update durable review and plan status**

Create the review file with:

- scope;
- result metrics;
- validator evidence;
- holdout status;
- rejected scope drift;
- remaining risks;
- pre-PR review status initially waiting for review.

Update this plan's status line and checklist with actual completed evidence.

- [x] **Step 4: Run documentation checks**

Run:

```bash
uv run pytest tests/evaluation/test_dense_documentation.py tests/evaluation/test_chinese_documentation.py -q
python - <<'PY'
from pathlib import Path
import re, sys
files = [
    Path("docs/README.md"),
    Path("docs/how-to/evaluate-hybrid-rrf-retrieval.md"),
    Path("docs/explanation/architecture.md"),
    Path("docs/superpowers/specs/2026-06-30-cjk-lexical-dense-rrf-fusion-design.md"),
    Path("docs/superpowers/plans/2026-06-30-cjk-lexical-dense-rrf-fusion-implementation.md"),
    Path("docs/superpowers/reviews/2026-06-30-cjk-lexical-dense-rrf-fusion-review.md"),
]
pat = re.compile(r"\\[[^\\]]+\\]\\(([^)]+)\\)")
errors = []
for f in files:
    text = f.read_text(encoding="utf-8")
    for match in pat.finditer(text):
        target = match.group(1)
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        path_part = target.split("#", 1)[0]
        if not path_part:
            continue
        if not (f.parent / path_part).resolve().exists():
            errors.append(f"{f}:{target}")
if errors:
    print("\\n".join(errors))
    sys.exit(1)
print("scoped markdown links valid")
PY
rg -n "/User[s]/|00_Inbox|[.]gstack|toke[n]=|api[_-]?ke[y]|[s]ecret|passwor[d]|Tracebac[k]" \
  docs/how-to/evaluate-hybrid-rrf-retrieval.md \
  docs/superpowers/specs/2026-06-30-cjk-lexical-dense-rrf-fusion-design.md \
  docs/superpowers/plans/2026-06-30-cjk-lexical-dense-rrf-fusion-implementation.md \
  docs/superpowers/reviews/2026-06-30-cjk-lexical-dense-rrf-fusion-review.md || true
```

Expected: documentation tests and link check pass. Any `rg` hit must be an intentional public
boundary test string; otherwise remove it.

- [x] **Step 5: Commit Task 10**

Run:

```bash
git add docs/how-to/evaluate-hybrid-rrf-retrieval.md \
  docs/explanation/architecture.md \
  docs/README.md \
  docs/superpowers/plans/2026-06-30-cjk-lexical-dense-rrf-fusion-implementation.md \
  docs/superpowers/reviews/2026-06-30-cjk-lexical-dense-rrf-fusion-review.md \
  tests/evaluation/test_dense_documentation.py \
  tests/evaluation/test_chinese_documentation.py
git commit -m "docs(eval): document hybrid RRF comparison"
```

## Task 11: Final Verification And Handoff

**Files:**

- Read all changed files.
- Update plan/review docs only if verification evidence changes.

- [x] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/evaluation/test_rrf_fusion.py \
  tests/evaluation/test_hybrid_rrf_protocol.py \
  tests/evaluation/test_hybrid_rrf_workflow.py \
  tests/evaluation/test_hybrid_rrf_artifact.py \
  tests/interfaces/test_cli_evaluation.py -q
```

Expected: focused tests pass.

- [x] **Step 2: Run full local verification**

Run:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
git diff --check origin/main...HEAD
```

Expected: all pass.

- [x] **Step 3: Run canonical validators**

Run:

```bash
uv run python -m mke.evaluation.baseline \
  --artifact benchmarks/retrieval/retrieval-eval-v1-baseline.json \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --repository .
uv run python -m mke.evaluation.numeric_artifact validate \
  --artifact benchmarks/retrieval/numeric-grouping-v1-comparison.json \
  --observed /tmp/mke-e2-after.json \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --repository .
uv run python -m mke.evaluation.chinese_artifact validate \
  --artifact benchmarks/retrieval/retrieval-chinese-v1-baseline.json \
  --observed /tmp/mke-e3a-after.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
uv run python -m mke.evaluation.cjk_lexical_artifact validate \
  --artifact benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json \
  --observed /tmp/mke-e3b-after.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
uv run python -m mke.evaluation.dense_artifact validate \
  --artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --protocol tests/fixtures/retrieval-dense-v1/protocol-lock.json \
  --repository .
uv run python -m mke.evaluation.hybrid_rrf_artifact validate \
  --artifact benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json \
  --protocol tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json \
  --dense-artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --repository .
```

Expected: all validators pass.

- [ ] **Step 4: Cache-ready dense replay optional corroboration remains unmet**

Run:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 UV_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
uv run python -m mke.evaluation.dense_replay validate \
  --artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --protocol tests/fixtures/retrieval-dense-v1/protocol-lock.json \
  --model-cache <model-cache> \
  --repository .
```

Expected when prerequisites are already satisfied: prints
`{"mode":"cache-ready","status":"passed"}` and exits `0`. If the embedding extra or model cache is
not available, do not install dependencies or download models without explicit authorization. Report
the unmet optional corroboration explicitly.

Actual: replay failed with `{"mode":"cache-ready","status":"failed"}` and exit `1` because the
embedding optional dependency was not installed (`ModuleNotFoundError: No module named
'huggingface_hub'`, with `sentence_transformers` unavailable as well). No dependency installation,
download, or dense rescoring was performed. This remains unmet optional corroboration, not a
completed required verification.

- [x] **Step 5: Public-boundary scan**

Run:

```bash
git diff --name-only origin/main...HEAD
git diff origin/main...HEAD -- . \
  | rg -n "/User[s]/|00_Inbox|[.]gstack|toke[n]=|api[_-]?ke[y]|[s]ecret|passwor[d]|Tracebac[k]" || true
```

Expected: no real private path, credential, raw GStack artifact, model cache, venv, or personal
context is present. Intentional synthetic test strings must be documented in the handoff.

- [x] **Step 6: Final commit if verification docs changed**

If Task 11 updates the plan/review evidence, run:

```bash
git add docs/superpowers/plans/2026-06-30-cjk-lexical-dense-rrf-fusion-implementation.md \
  docs/superpowers/reviews/2026-06-30-cjk-lexical-dense-rrf-fusion-review.md
git commit -m "docs(eval): record hybrid RRF verification"
```

- [x] **Step 7: Stop for scheme-window review**

Do not push or create a PR. Hand off:

- branch, worktree, base, HEAD;
- commit list;
- diff stat;
- E3-D metrics and diagnostics;
- artifact SHA-256 values;
- exact verification commands and results;
- skipped cache-ready replay reason, if skipped;
- scope non-changes;
- remaining risks.

The scheme/review window then runs authoritative `gstack-review` before PR publication.

## Stop Conditions

Stop and return to the planning window if any of these occurs:

- development gates fail and the implementation cannot record a clean valid-negative artifact;
- holdout would need to be observed more than once;
- E1/E2/E3-A/E3-B/E3-C normalized semantics drift;
- fusion requires changing RRF `k`, weights, depth, tie-breakers, or raw score use;
- dense artifact needs regeneration or dense model replay to make E3-D pass;
- a validator can pass only by trusting checked-in artifact fields that should be recomputed;
- public CLI output would expose local paths, tracebacks, cache paths, environment variables, or
  raw exception text;
- implementation pressure suggests adding reranker, query rewrite, segmentation, API adapter,
  runtime promotion, or a new projection lifecycle inside E3-D.

## Expected Final Scope Statement

The final PR body must state:

- E3-D records comparison-only rank-only RRF evidence.
- Runtime default remains `cjk-active-scan-overlap-v1`.
- Search, Ask, MCP, owner startup, Publication, and ingestion behavior are unchanged.
- No API adapter, reranker, query rewrite, segmentation, HTTP, UI, Milvus, Redis, pgvector, or
  runtime promotion is included.
- E3-D diagnostics decide whether the next plan is reranker or Passage/segmentation.

## GSTACK REVIEW REPORT

Autoplan review result: `CLEAN` after plan amendments.

Durable review:
[CJK Lexical Dense RRF Fusion Candidate Autoplan Review](../reviews/2026-06-30-cjk-lexical-dense-rrf-fusion-autoplan-review.md).

| Review | Status | Notes |
|---|---|---|
| CEO | `CLEAN` | E3-D remains comparison-only; reranker and segmentation stay follow-up decisions. |
| Design | `SKIPPED` | No graphical UI scope. |
| Engineering | `CLEAN` | Plan now freezes lexical rank derivation, dense threshold filtering, dense rank preservation, and no-skip validator testing. |
| DX | `CLEAN` | CLI, validator, docs, and public error-output boundaries are specified. |
| Outside voice | `N/A` | Current host rules prevented subagent use; no cross-model consensus was claimed. |

NO UNRESOLVED DECISIONS
