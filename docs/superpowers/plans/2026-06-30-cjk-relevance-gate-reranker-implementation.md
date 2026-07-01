# CJK Relevance Gate Reranker Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record a comparison-only E3-E deterministic relevance gate and reranker candidate over the
existing E3-D lexical+dense union, without changing Search, Ask, MCP, owner startup, Publication,
ingestion, or runtime defaults.

**Architecture:** Add evaluation-only modules that load the canonical E3-C dense artifact and E3-D
RRF artifact, derive public Evidence/query features, select one frozen relevance-gate profile on
development, optionally observe holdout, and validate the resulting artifact by independent
recomputation. The candidate is not a runtime strategy.

**Tech Stack:** Python 3.12/3.13, existing JSON artifacts, existing Chinese retrieval fixtures,
pytest, Ruff, Pyright, Hatch/uv, existing `mke eval` CLI patterns.

---

Status: implementation in progress; Tasks 0-8 are complete on local branch
`codex/e3e-relevance-gate-reranker`. This plan depends on the approved
[CJK Relevance Gate Reranker Candidate Design](../specs/2026-06-30-cjk-relevance-gate-reranker-design.md).

Planning base: `main@0ed1ee1c7763d65b1cd493d002908361df410521`.

Implementation base: `main@03a7583fd7161585bc039832b517cc3be97ddca9`.

Recommended implementation branch:

```bash
git switch main
git fetch origin
git pull --ff-only
git worktree add .worktrees/e3e-relevance-gate-reranker \
  -b codex/e3e-relevance-gate-reranker origin/main
cd .worktrees/e3e-relevance-gate-reranker
```

Use `high` reasoning depth for implementation and review fixes. Use `xhigh` only for protocol,
artifact-integrity, holdout-observation, or architecture-amendment stop conditions.

## Non-Negotiable Boundaries

- E3-E is comparison-only.
- Do not change the runtime default `cjk-active-scan-overlap-v1`.
- Do not change normal Search, Ask, MCP, owner startup, Publication, ingestion, or runtime
  strategy behavior.
- Do not change the dense model, model revision, threshold, projection, or model-cache contract.
- Do not change E3-D RRF inputs, `k`, arm weights, or tie-breakers.
- Do not add API reranking, LLM judging, query rewrite, HyDE, Passage/chunk segmentation, HTTP, UI,
  Milvus, Redis, pgvector, LangChain, LlamaIndex, or LangGraph runtime contracts.
- Do not read qrels, grades, query category labels, split labels, or expected locators inside
  candidate scoring code.
- Do not alter E1/E2/E3-A/E3-B/E3-C/E3-D qrels, fixtures, observations, metrics, gates, or
  verdicts. Source/scope identity refresh is allowed only after proving normalized semantic
  equality.
- Do not observe holdout unless development has been frozen with exclusive-create semantics.
- If development gates fail, record a valid negative and do not observe holdout.
- If a validator failure requires changing a gate or candidate contract, stop for planning review.

## File Structure

Create or modify these files:

| File | Responsibility |
|---|---|
| `src/mke/evaluation/relevance_gate_features.py` | Query/Evidence feature extraction for allowed public features. |
| `src/mke/evaluation/relevance_gate_candidate.py` | Profile definitions, gate decisions, deterministic rerank scorecard, and reason codes. |
| `src/mke/evaluation/relevance_gate_protocol.py` | Frozen E3-E protocol lock builder and validator. |
| `src/mke/evaluation/relevance_gate_workflow.py` | Development/holdout workflow and artifact construction. |
| `src/mke/evaluation/relevance_gate_artifact.py` | Model-free canonical artifact validator and CLI entrypoint. |
| `src/mke/cli.py` | `mke eval retrieval-relevance-gate` command and stable public errors. |
| `src/mke/evaluation/__init__.py` | Lazy exports only if needed; avoid import-time optional dependencies. |
| `tests/evaluation/test_relevance_gate_features.py` | Feature extraction and forbidden-input tests. |
| `tests/evaluation/test_relevance_gate_candidate.py` | Gate profile, rerank, reason-code, and tie-break tests. |
| `tests/evaluation/test_relevance_gate_protocol.py` | Protocol lock tests. |
| `tests/evaluation/test_relevance_gate_workflow.py` | Development/holdout state machine tests. |
| `tests/evaluation/test_relevance_gate_artifact.py` | Artifact validator regression tests. |
| `tests/evaluation/test_relevance_gate_documentation.py` | Durable docs/status tests. |
| Existing CLI evaluation tests | CLI success/failure coverage. |
| `tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json` | Canonical E3-E protocol lock. |
| `benchmarks/retrieval/cjk-relevance-gate-reranker-v1-development-freeze.json` | Development freeze artifact. |
| `benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json` | Canonical E3-E comparison artifact. |
| `benchmarks/retrieval/cjk-relevance-gate-reranker-v1-holdout-receipt.json` | Conditional holdout receipt. |
| `docs/how-to/evaluate-relevance-gate-reranker.md` | Reproduction guide and interpretation boundary. |
| `docs/explanation/architecture.md` | Explain E3-E as comparison-only; no runtime promotion. |
| `docs/README.md` | Link new spec, plan, review, and how-to. |
| `docs/superpowers/plans/2026-06-30-cjk-relevance-gate-reranker-implementation.md` | Keep checklist and completion evidence current. |
| `docs/superpowers/reviews/2026-06-30-cjk-relevance-gate-reranker-review.md` | Durable implementation review after pre-PR review. |

## Task 0: Baseline And Snapshot Gate

**Files:**

- Read: `AGENTS.md`
- Read: `docs/superpowers/specs/2026-06-30-cjk-relevance-gate-reranker-design.md`
- Read: `benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json`
- Read: `benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json`
- Read: `tests/fixtures/retrieval-chinese-v1/protocol.json`

- [x] **Step 1: Confirm implementation starts from latest main**

Run:

```bash
git status --short --branch
git rev-parse HEAD origin/main
git merge-base --is-ancestor origin/main HEAD
gh pr list --state open --json number,title,headRefName,mergeStateStatus,isDraft,url
```

Expected: branch is clean and based on latest `origin/main`; no open prerequisite PR blocks E3-E.
If not, stop and recreate the worktree.

- [x] **Step 2: Run current validators before editing**

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
uv run python -m mke.evaluation.hybrid_rrf_artifact validate \
  --artifact benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json \
  --protocol tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json \
  --dense-artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --repository .
```

Expected: every validator passes. If source identity fails because E3-E files are not yet included,
do not refresh yet; identity refresh belongs after semantic equality checks.

- [x] **Step 3: Save normalized pre-change semantic snapshots**

Create local-only snapshots:

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

Expected: four normalized files exist under `/tmp`. Do not commit them.

## Task 1: Freeze Protocol Lock

**Files:**

- Create: `src/mke/evaluation/relevance_gate_protocol.py`
- Create: `tests/evaluation/test_relevance_gate_protocol.py`
- Create: `tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json`

- [x] **Step 1: Write RED tests for protocol identity**

Cover these cases:

- candidate ID must equal `cjk-relevance-gate-reranker-v1`;
- candidate revision must equal integer `1` and reject bool;
- protocol binds E3-C dense artifact path and SHA-256;
- protocol binds E3-D RRF artifact path and SHA-256;
- protocol binds Chinese qrel/review identity;
- profile catalog is exactly `lexical-floor`, `balanced-constraint`, `strict-constraint`;
- protocol rejects unknown profiles, extra profiles, or missing source inventory.

Run:

```bash
uv run pytest tests/evaluation/test_relevance_gate_protocol.py -q
```

Expected: tests fail because the module and protocol file do not exist.

- [x] **Step 2: Implement protocol builder and validator**

Implementation requirements:

- Use repository-relative paths only.
- Compute byte sizes and SHA-256 for all bound inputs.
- Validate source inventory without reading qrel grades in candidate code.
- Return stable `RelevanceGateProtocolError` with `problem`, `cause`, and `next_step`.

- [x] **Step 3: Record canonical protocol lock**

Run the protocol builder, write:

```text
tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json
```

Then rerun:

```bash
uv run pytest tests/evaluation/test_relevance_gate_protocol.py -q
```

Expected: all protocol tests pass.

- [x] **Step 4: Commit Task 1**

Stage only the protocol module, tests, and protocol lock:

```bash
git add \
  src/mke/evaluation/relevance_gate_protocol.py \
  tests/evaluation/test_relevance_gate_protocol.py \
  tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json
git commit -m "feat(eval): freeze relevance gate protocol"
```

## Task 2: Implement Public Feature Extraction

**Files:**

- Create: `src/mke/evaluation/relevance_gate_features.py`
- Create: `tests/evaluation/test_relevance_gate_features.py`

- [x] **Step 1: Write RED tests for allowed features**

Cover:

- normalized CJK, ASCII, number, date, unit, and mixed-token extraction;
- source-text digest preservation;
- numeric/date/unit required-term detection;
- feature extraction does not accept qrel grades, category labels, split labels, or expected locators;
- feature extraction rejects repo-external or missing source text with stable errors.

Run:

```bash
uv run pytest tests/evaluation/test_relevance_gate_features.py -q
```

Expected: fail because feature extraction does not exist.

- [x] **Step 2: Implement feature extraction**

Implementation requirements:

- Keep functions pure and model-free.
- Use only query text, Evidence text, locator identity, source-text digest, and arm/rank provenance.
- Normalize full-width and half-width forms where existing project helpers already do so; if no
  helper exists, implement a small local normalizer with tests.
- Return immutable dataclasses or typed dictionaries that serialize deterministically.

- [x] **Step 3: Add forbidden-input regression**

Add a test that passes fake qrel/category/split fields into feature construction and proves they
are ignored or rejected, not used in serialized features.

- [x] **Step 4: Commit Task 2**

```bash
git add \
  src/mke/evaluation/relevance_gate_features.py \
  tests/evaluation/test_relevance_gate_features.py
git commit -m "feat(eval): derive relevance gate features"
```

## Task 3: Implement Gate Profiles And Rerank Scorecard

**Files:**

- Create: `src/mke/evaluation/relevance_gate_candidate.py`
- Create: `tests/evaluation/test_relevance_gate_candidate.py`

- [x] **Step 1: Write RED tests for gate decisions**

Cover:

- `lexical-floor` preserves high-confidence lexical rows;
- `balanced-constraint` allows dense-only rows when explicit constraints are preserved;
- `strict-constraint` rejects weak-overlap dense-only rows;
- numeric/date/proper-noun mismatch rejects rows with stable reason codes;
- every rejected row has one stable reason code;
- allowed rows sort by score, arm count, best rank, lexical rank, dense rank, RRF rank, and stable
  locator ID;
- bool values are rejected where integers are required.

Run:

```bash
uv run pytest tests/evaluation/test_relevance_gate_candidate.py -q
```

Expected: fail because candidate scoring does not exist.

- [x] **Step 2: Implement gate profiles**

Implementation requirements:

- Candidate profiles are frozen constants.
- Profile selection is not performed in this module.
- Scorecard uses only allowed features and rank provenance.
- Tie-breaks are deterministic and portable across Python 3.12/3.13.
- Rejection reason enum is stable and documented in tests.

- [x] **Step 3: Commit Task 3**

```bash
git add \
  src/mke/evaluation/relevance_gate_candidate.py \
  tests/evaluation/test_relevance_gate_candidate.py
git commit -m "feat(eval): add relevance gate reranker"
```

## Task 4: Implement Development Workflow

**Files:**

- Create: `src/mke/evaluation/relevance_gate_workflow.py`
- Create: `tests/evaluation/test_relevance_gate_workflow.py`

- [x] **Step 1: Write RED workflow tests**

Cover:

- workflow loads E3-C and E3-D artifacts from protocol-bound paths;
- workflow rebuilds the E3-D union without changing RRF observations;
- scoring never reads holdout when `--development-only` is used;
- selected profile follows the frozen objective;
- no profile passing development records `development_status=valid_negative`;
- development freeze uses exclusive-create semantics;
- accidental holdout observation before development freeze fails closed.

Run:

```bash
uv run pytest tests/evaluation/test_relevance_gate_workflow.py -q
```

Expected: fail because workflow does not exist.

- [x] **Step 2: Implement development scoring**

Implementation requirements:

- Compute metrics through existing graded metrics helpers.
- Compare candidate metrics against the frozen development gates.
- Record all feature rows needed for independent validation.
- Record selected profile and rejected profiles with reasons.
- Do not write holdout fields during development-only mode.

- [x] **Step 3: Run development once**

Run with exclusive output path:

```bash
uv run mke eval retrieval-relevance-gate \
  --protocol tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json \
  --candidate cjk-relevance-gate-reranker-v1 \
  --development-only \
  --record-development-freeze \
    benchmarks/retrieval/cjk-relevance-gate-reranker-v1-development-freeze.json \
  --json > /tmp/mke-e3e-development.json
```

Expected:

- if development passes, continue to Task 5;
- if development is a valid negative, do not observe holdout; continue to artifact validation with
  `holdout_status=not_observed`;
- if development fails for an unfrozen reason, stop for planning review.

- [x] **Step 4: Commit Task 4**

```bash
git add \
  src/mke/evaluation/relevance_gate_workflow.py \
  tests/evaluation/test_relevance_gate_workflow.py \
  benchmarks/retrieval/cjk-relevance-gate-reranker-v1-development-freeze.json
git commit -m "feat(eval): score relevance gate development"
```

## Task 5: Implement Artifact Validator

**Files:**

- Create: `src/mke/evaluation/relevance_gate_artifact.py`
- Create: `tests/evaluation/test_relevance_gate_artifact.py`
- Create or update: `benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json`
- Conditional: `benchmarks/retrieval/cjk-relevance-gate-reranker-v1-holdout-receipt.json`

- [x] **Step 1: Write RED validator tests**

Cover:

- model-free validator independently recomputes feature rows, gate decisions, rerank order, metrics,
  selected profile, diagnostics, and state;
- validator rejects qrel/category/split leakage in serialized scoring features;
- validator rejects modified source text digests;
- validator rejects coordinated metric and result tampering;
- validator rejects missing development freeze;
- validator rejects holdout artifact when development did not pass;
- validator rejects bool/int confusion.

Run:

```bash
uv run pytest tests/evaluation/test_relevance_gate_artifact.py -q
```

Expected: fail because artifact validator does not exist.

- [x] **Step 2: Implement validator and CLI entrypoint**

Required command:

```bash
uv run python -m mke.evaluation.relevance_gate_artifact validate \
  --artifact benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json \
  --protocol tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json \
  --repository .
```

Successful output must be stable and public:

```text
relevance gate artifact valid
```

Failure output must avoid stack traces and absolute paths.

- [x] **Step 3: Conditional holdout observation**

If `/tmp/mke-e3e-development.json` records `development_status=passed`, run exactly once:

```bash
uv run mke eval retrieval-relevance-gate \
  --protocol tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json \
  --candidate cjk-relevance-gate-reranker-v1 \
  --development-freeze \
    benchmarks/retrieval/cjk-relevance-gate-reranker-v1-development-freeze.json \
  --record benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json \
  --record-holdout-receipt \
    benchmarks/retrieval/cjk-relevance-gate-reranker-v1-holdout-receipt.json \
  --json > /tmp/mke-e3e-comparison.json
```

If development is a valid negative, create the comparison artifact without holdout observation:

```bash
uv run mke eval retrieval-relevance-gate \
  --protocol tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json \
  --candidate cjk-relevance-gate-reranker-v1 \
  --development-freeze \
    benchmarks/retrieval/cjk-relevance-gate-reranker-v1-development-freeze.json \
  --record benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json \
  --json > /tmp/mke-e3e-comparison.json
```

- [x] **Step 4: Validate artifact**

Run:

```bash
uv run python -m mke.evaluation.relevance_gate_artifact validate \
  --artifact benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json \
  --protocol tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json \
  --repository .
```

Expected: `relevance gate artifact valid`.

- [x] **Step 5: Commit Task 5**

```bash
git add \
  src/mke/evaluation/relevance_gate_artifact.py \
  tests/evaluation/test_relevance_gate_artifact.py \
  benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json
git add benchmarks/retrieval/cjk-relevance-gate-reranker-v1-holdout-receipt.json || true
git commit -m "test(eval): record relevance gate comparison artifact"
```

## Task 6: Add CLI Contract

**Files:**

- Modify: `src/mke/cli.py`
- Modify: existing CLI evaluation tests or create `tests/interfaces/test_cli_relevance_gate.py`

- [x] **Step 1: Write RED CLI tests**

Cover:

- command name is `mke eval retrieval-relevance-gate`;
- command accepts `--protocol`, `--candidate`, `--development-only`, `--development-freeze`,
  `--record-development-freeze`, `--record`, and `--record-holdout-receipt`;
- invalid candidate exits with usage error;
- malformed artifact exits non-zero with redacted problem/cause/next_step;
- CLI does not expose runtime Search/Ask/MCP strategy overrides.

Run the targeted CLI tests. Expected: fail before implementation.

- [x] **Step 2: Implement CLI wrapper**

Implementation requirements:

- Keep command under evaluation namespace only.
- Use repository-relative paths in JSON output.
- Return stable JSON for success and stable public errors for failure.
- Do not add owner-startup or MCP request-time selectors.

- [x] **Step 3: Commit Task 6**

```bash
git add src/mke/cli.py tests/interfaces/test_cli_relevance_gate.py
git commit -m "feat(cli): expose relevance gate evaluation"
```

## Task 7: Historical Identity Refresh Gate

**Files:**

- Potentially update E1/E2/E3-A/E3-B/E3-C/E3-D artifacts only if source/scope identity changes.
- Test: existing artifact refresh tests.

- [x] **Step 1: Rerun observed evaluations**

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

- [x] **Step 2: Compare normalized semantics**

Use the existing repository helper if present; otherwise compare JSON after removing duration and
environment fields. Expected:

```text
e1 semantic_equal
e2 semantic_equal
e3a semantic_equal
e3b semantic_equal
```

If any qrel, fixture, observation, metric, gate, or verdict changes, stop for planning review.

- [x] **Step 3: Refresh identity-only artifacts if required**

Refresh only source/scope identities that changed because E3-E added source files. Do not change
metrics or verdicts.

- [x] **Step 4: Commit Task 7**

```bash
git add <only-refreshed-artifacts-and-tests>
git commit -m "test(eval): refresh relevance gate artifact identities"
```

## Task 8: Documentation

**Files:**

- Create: `docs/how-to/evaluate-relevance-gate-reranker.md`
- Modify: `docs/explanation/architecture.md`
- Modify: `docs/README.md`
- Modify: `docs/superpowers/plans/2026-06-30-cjk-relevance-gate-reranker-implementation.md`

- [x] **Step 1: Write reproduction guide**

The how-to must include:

- result interpretation;
- development command;
- conditional holdout command;
- validator command;
- explicit statement that E3-E is comparison-only;
- explicit statement that Search, Ask, MCP, owner startup, Publication, ingestion, and runtime
  default are unchanged.

- [x] **Step 2: Update architecture and docs index**

Architecture must place E3-E after E3-D and before any future runtime promotion, reranker model,
query rewrite, or segmentation plan.

- [x] **Step 3: Add documentation status tests**

Extend documentation tests to assert:

- docs include comparison-only boundary;
- docs include `runtime_promotion_status=not_evaluated`;
- docs do not claim runtime default changes;
- docs do not mention private source paths, non-public planning artifacts, or external private
  materials.

- [x] **Step 4: Commit Task 8**

```bash
git add \
  docs/how-to/evaluate-relevance-gate-reranker.md \
  docs/explanation/architecture.md \
  docs/README.md \
  docs/superpowers/plans/2026-06-30-cjk-relevance-gate-reranker-implementation.md \
  tests/evaluation/test_relevance_gate_documentation.py
git commit -m "docs(eval): document relevance gate comparison"
```

## Task 9: Final Verification And Review Handoff

**Files:**

- Modify: `docs/superpowers/reviews/2026-06-30-cjk-relevance-gate-reranker-review.md`
- Modify: `docs/superpowers/plans/2026-06-30-cjk-relevance-gate-reranker-implementation.md`

- [ ] **Step 1: Run full verification**

Run:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
uv run python -m mke.evaluation.relevance_gate_artifact validate \
  --artifact benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json \
  --protocol tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json \
  --repository .
git diff --check origin/main...HEAD
```

Expected: all pass. If optional dense replay is unavailable because embedding extras or local model
cache are missing, record it as optional corroboration not run; do not install packages or download
models unless separately authorized.

- [ ] **Step 2: Run public-boundary scan**

Check the branch diff for:

- private absolute paths;
- model cache paths;
- non-public planning artifacts;
- credentials, tokens, cookies, `.env`;
- private source-material names.

Expected: no real private or credential material. Synthetic test strings are allowed only when they
are clearly fake.

- [ ] **Step 3: Prepare implementation review**

Create:

```text
docs/superpowers/reviews/2026-06-30-cjk-relevance-gate-reranker-review.md
```

Record:

- candidate status;
- development and holdout status;
- selected profile;
- metrics table;
- artifact SHA-256 values;
- validator evidence;
- explicit non-scope;
- remaining risks.

- [ ] **Step 4: Commit final verification docs**

```bash
git add \
  docs/superpowers/reviews/2026-06-30-cjk-relevance-gate-reranker-review.md \
  docs/superpowers/plans/2026-06-30-cjk-relevance-gate-reranker-implementation.md
git commit -m "docs(eval): finalize relevance gate verification"
```

- [ ] **Step 5: Stop for scheme-window review**

Do not push or create PR yet. Hand off:

- branch;
- worktree path;
- base SHA;
- HEAD SHA;
- diff stat;
- commit list;
- metrics;
- artifact SHA-256 values;
- validation commands and results;
- explicit scope non-changes;
- remaining risks.

The scheme window then runs authoritative pre-PR review before any push/PR.

## Review Status

`gstack-autoplan` was run at plan time through CEO, engineering, and DX dimensions. Design/visual
review was skipped because E3-E has no UI scope.

Current planning review: `CLEAN / 0 unresolved findings` after incorporating the review amendments
recorded in
[CJK Relevance Gate Reranker Autoplan Review](../reviews/2026-06-30-cjk-relevance-gate-reranker-autoplan-review.md).
