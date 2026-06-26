# CJK Lexical Runtime Promotion Implementation Plan

Status: approved for execution handoff. Not implemented in this planning branch.

Planning base: `main@ee1eca081dffb9350f1fb9d20a3d32a06efa1785`.

Design: [CJK Lexical Runtime Promotion Design](../specs/2026-06-26-cjk-lexical-runtime-promotion-design.md)

Review: [CJK Lexical Runtime Promotion Autoplan Review](../reviews/2026-06-26-cjk-lexical-runtime-promotion-autoplan-review.md)

## Goal

Promote the verified E3-B `cjk-trigram-overlap-v1` lexical candidate into normal runtime Search and
Ask as the default owner-startup retrieval strategy, while preserving direct rollback to
`numeric-grouping-v1` and `current`.

This plan is lexical-only. It does not implement embeddings, vector search, hybrid retrieval, RRF,
reranking, query rewrite, HTTP, UI, or legacy RAG-OCR service migration.

## Execution Setup

Recommended branch:

```bash
git switch main
git pull --ff-only
git switch -c codex/cjk-lexical-runtime-promotion
```

Before editing:

```bash
git status --short --branch
uv run pytest tests/retrieval tests/evaluation -q
uv run mke eval retrieval --manifest tests/fixtures/retrieval-eval-v1.json --json \
  > /tmp/mke-e1-before.json
uv run python -m mke.evaluation.baseline \
  --artifact benchmarks/retrieval/retrieval-eval-v1-baseline.json \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --repository .
```

Before artifact refresh work, inspect `src/mke/evaluation/artifact_refresh.py`. The existing
transaction covers E1, E2, and E3-A; this implementation must extend the refresh path or add a
recoverable companion transaction for the E3-B CJK lexical artifact.

## Task 1: Add ADR-0008 And Strategy Vocabulary

Add ADR-0008 before changing runtime behavior.

Expected files:

- `docs/decisions/0008-cjk-lexical-retrieval-strategy.md`
- `src/mke/retrieval/strategy.py`
- compatibility exports from `src/mke/retrieval/__init__.py`
- tests under `tests/retrieval/`

Required RED tests:

- supported strategies are exactly `current`, `numeric-grouping-v1`, and
  `cjk-trigram-overlap-v1`;
- default strategy is `cjk-trigram-overlap-v1`;
- `numeric-grouping-v1` remains a valid rollback strategy;
- invalid strategy fails with a stable public error;
- boolean-like or non-string strategy values are rejected before engine construction;
- legacy `RetrievalQueryPolicy` helpers remain available for existing E1/E2/E3 evaluation code.

Implementation notes:

- Introduce `RetrievalStrategy` as the owner-facing concept.
- Keep `RetrievalQueryPolicy` as the lower-level compiler concept for `current` and
  `numeric-grouping-v1`.
- Do not expose strategy selection through Search or Ask request DTOs.

Verification:

```bash
uv run pytest tests/retrieval/test_query_policy.py tests/retrieval -q
```

## Task 2: Implement CJK Lexical Runtime Projection Schema

Promote the E3-B evaluation projection into a rebuildable active projection.

Expected files:

- `src/mke/adapters/sqlite/__init__.py`
- `src/mke/retrieval/cjk_lexical.py`
- storage integration tests under `tests/storage/` or `tests/retrieval/`

Required RED tests:

- migration creates the CJK FTS5 projection and metadata table without changing domain tables;
- projection uses SQLite FTS5 `trigram` tokenizer and records tokenizer identity;
- projection row count equals active text Evidence row count;
- projection text digest matches active Evidence text;
- projection can be dropped and rebuilt from SQLite domain truth;
- `numeric-grouping-v1` and `current` runtime startup do not require the CJK projection to be ready;
- unsupported `trigram` tokenizer fails closed only when the selected strategy needs it.

Implementation notes:

- Keep the projection separate from `active_evidence_fts`.
- Store strategy revision and source identity metadata.
- Do not treat projection rows as domain truth.
- Do not copy E3-B evaluation-only temporary tables into runtime code without adapting lifecycle
  and readiness semantics.

Verification:

```bash
uv run pytest tests/storage tests/retrieval -q
```

## Task 3: Add Projection Doctor And Rebuild Commands

Add cache-only local readiness and rebuild commands.

Expected public shape:

```bash
mke retrieval doctor --strategy cjk-trigram-overlap-v1 --json
mke retrieval rebuild --strategy cjk-trigram-overlap-v1 --json
```

Required RED tests:

- `doctor` returns `ready` when metadata matches active Evidence identity;
- `doctor` returns `not_ready` when projection table is missing, row count differs, digest differs,
  strategy revision differs, or tokenizer is unsupported;
- `doctor` output includes stable `problem`, `cause`, and `next_step`;
- `doctor` output never exposes tracebacks or absolute local paths;
- `rebuild` is idempotent;
- `rebuild` updates only projection tables and metadata;
- `rebuild` refuses unsupported strategies with usage exit behavior.

Implementation notes:

- Rebuild from active domain rows, not from existing projection rows.
- Keep all operations offline and local.
- Do not auto-rebuild during Search or Ask.

Verification:

```bash
uv run pytest tests/cli tests/retrieval tests/storage -q
```

## Task 4: Wire Runtime Search Strategy

Implement the promoted strategy in normal Search and Ask.

Expected files:

- `src/mke/adapters/sqlite/__init__.py`
- `src/mke/application/__init__.py`
- `src/mke/runtime.py`
- `tests/application/`
- `tests/retrieval/`

Required RED tests:

- default runtime strategy is `cjk-trigram-overlap-v1`;
- non-empty `numeric-grouping-v1` compiled queries use the existing active FTS Search path;
- compiled-empty eligible CJK queries use the CJK projection and overlap ranker;
- short or ineligible CJK queries remain no-hit or insufficient-input according to existing Ask
  semantics;
- hard-negative and unanswerable fixture queries do not become false positives beyond E3-B gates;
- missing or stale CJK projection fails closed for the selected default strategy;
- rollback strategy `numeric-grouping-v1` works without CJK projection readiness;
- strategy selection is fixed at owner construction and cannot be changed per request.

Implementation notes:

- Reuse E3-B term derivation and overlap scorer semantics.
- Preserve ranking tie-breakers exactly.
- Parameterize FTS5 `MATCH` expressions.
- Avoid silent fallback from selected `cjk-trigram-overlap-v1` to `numeric-grouping-v1` when the
  projection is stale; using the numeric branch for non-empty compiled queries is expected.

Verification:

```bash
uv run pytest tests/application tests/retrieval tests/storage -q
```

## Task 5: Bind Projection Build To Publication Activation

Ensure a selected CJK strategy cannot publish partial searchable state.

Required RED tests:

- activating a new Publication under `cjk-trigram-overlap-v1` builds both active FTS and CJK
  projection before the new Publication is visible to Search;
- injected CJK projection failure fails the Run or activation path and preserves the previous active
  Publication;
- retry creates a new immutable Run rather than mutating failed Run identity;
- `numeric-grouping-v1` activation path remains unaffected by CJK projection failure injection;
- crash recovery does not mark a partially projected Publication active.

Implementation notes:

- Follow existing Run/Publication required-stage semantics.
- Treat CJK projection as a required projection only when the owner-selected strategy requires it.
- Keep projection rebuild separate from Run creation unless the command intentionally repairs an
  existing active projection.

Verification:

```bash
uv run pytest tests/storage tests/application tests/proof -q
```

## Task 6: Update CLI And MCP Owner Startup Contracts

Add the preferred strategy selector and preserve compatibility.

Expected files:

- `src/mke/cli.py`
- MCP runtime configuration module and tests
- `docs/reference/cli.md`
- `docs/reference/contracts.md`
- `docs/how-to/use-mke-mcp.md`

Required RED tests:

- `--retrieval-strategy cjk-trigram-overlap-v1` starts the default strategy;
- omitting the selector uses `cjk-trigram-overlap-v1`;
- `--retrieval-strategy numeric-grouping-v1` rolls back;
- legacy `--retrieval-query-policy numeric-grouping-v1` still works;
- conflicting `--retrieval-strategy` and `--retrieval-query-policy` values fail before engine
  construction with usage exit `2`;
- MCP owner startup accepts the allowlisted strategies;
- MCP Search/Ask tool schemas do not add request-time strategy fields;
- errors are stable and path-redacted.

Implementation notes:

- Prefer `retrieval strategy` language in new docs.
- Keep old query-policy wording only where documenting compatibility.
- Do not add HTTP or UI endpoints.

Verification:

```bash
uv run pytest tests/cli tests/mcp -q
```

## Task 7: Refresh Evaluation Artifacts Without Changing Semantics

Runtime source changes will alter source identities. Refresh artifacts while proving metrics and
verdicts are unchanged.

Artifacts:

- `benchmarks/retrieval/retrieval-eval-v1-baseline.json`
- `benchmarks/retrieval/numeric-grouping-v1-comparison.json`
- `benchmarks/retrieval/chinese-retrieval-v1-baseline.json`
- `benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json`

Required RED tests or scripted checks:

- artifact validators pass after refresh;
- E1 semantic payload is unchanged except permitted source/environment identity fields;
- E2 observations, metrics, gates, and verdict are unchanged;
- E3-A observations, miss classifications, metrics, and E3-B eligibility are unchanged;
- E3-B observations, SQL proof, metrics, gates, and verdict are unchanged;
- any quality metric delta stops the execution before PR creation.

Verification:

```bash
uv run mke eval retrieval \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --json > /tmp/mke-e1-runtime-promotion.json
uv run mke eval retrieval-numeric \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --json > /tmp/mke-e2-runtime-promotion.json
uv run mke eval retrieval-chinese \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --json > /tmp/mke-e3a-runtime-promotion.json
uv run mke eval retrieval-cjk-lexical \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --candidate cjk-trigram-overlap-v1 \
  --json > /tmp/mke-e3b-runtime-promotion.json
uv run python -m mke.evaluation.baseline \
  --artifact benchmarks/retrieval/retrieval-eval-v1-baseline.json \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --repository .
uv run python -m mke.evaluation.numeric_artifact validate \
  --artifact benchmarks/retrieval/numeric-grouping-v1-comparison.json \
  --observed /tmp/mke-e2-runtime-promotion.json \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --repository .
uv run python -m mke.evaluation.chinese_artifact validate \
  --artifact benchmarks/retrieval/retrieval-chinese-v1-baseline.json \
  --observed /tmp/mke-e3a-runtime-promotion.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
uv run python -m mke.evaluation.cjk_lexical_artifact validate \
  --artifact benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json \
  --observed /tmp/mke-e3b-runtime-promotion.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
```

## Task 8: Add Installed-Wheel CLI And MCP Proof

Prove the promoted strategy from installed artifacts, not source-tree imports.

Required proof:

- Python 3.12 installed wheel;
- Python 3.13 installed wheel;
- default `cjk-trigram-overlap-v1` CLI Search/Ask over the Chinese fixture;
- rollback `numeric-grouping-v1` CLI Search/Ask behavior;
- stdio MCP startup with default strategy;
- stdio MCP startup with rollback strategy;
- hostile `PYTHONPATH`, external cwd, and repository import rejection;
- no network access or model download.

Verification command shape:

```bash
uv build
uv run python scripts/cjk_lexical_runtime_deployment_proof.py --python 3.12 --json
uv run python scripts/cjk_lexical_runtime_deployment_proof.py --python 3.13 --json
```

Add `scripts/cjk_lexical_runtime_deployment_proof.py` and tests for it in the implementation PR.

## Task 9: Update Public Documentation And Demo Assets

Required docs:

- ADR-0008;
- architecture explanation;
- CLI reference;
- public contracts;
- Chinese retrieval how-to;
- MCP how-to;
- README or docs index;
- implementation plan completion record;
- durable implementation review.

Required demo assets:

- architecture diagram for active FTS and CJK projection;
- strategy comparison table generated from artifacts;
- direct offline proof command;
- short repository-visible demo script covering ingest, CJK Search/Ask, refusal, and rollback.

Do not publish an external recording without separate authorization.

Verification:

```bash
uv run pytest tests/evaluation/test_chinese_documentation.py -q
uv run python - <<'PY'
from pathlib import Path
docs = [
    Path("docs/decisions/0008-cjk-lexical-retrieval-strategy.md"),
    Path("docs/explanation/architecture.md"),
    Path("docs/reference/cli.md"),
    Path("docs/reference/contracts.md"),
    Path("docs/how-to/run-chinese-retrieval-evaluation.md"),
    Path("docs/how-to/use-mke-mcp.md"),
    Path("docs/README.md"),
]
missing = [path for path in docs if not path.exists()]
if missing:
    raise SystemExit(f"missing docs: {missing}")
print("scoped docs exist")
PY
git diff --check
```

## Task 10: Final Verification And Review Gate

Before handing back to the planning/review window, run:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
git diff --check
```

Also run:

```bash
uv run mke eval retrieval \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --json > /tmp/mke-e1-final.json
uv run mke eval retrieval-numeric \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --json > /tmp/mke-e2-final.json
uv run mke eval retrieval-chinese \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --json > /tmp/mke-e3a-final.json
uv run mke eval retrieval-cjk-lexical \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --candidate cjk-trigram-overlap-v1 \
  --json > /tmp/mke-e3b-final.json
```

Then run a full pre-PR `gstack-review` or hand the clean branch back to the planning/review window
for the established independent review sequence.

## PR Boundary

The implementation PR may include:

- ADR-0008;
- runtime strategy and projection lifecycle;
- CLI/MCP owner-startup selector;
- projection doctor/rebuild;
- artifact source identity refresh;
- proof scripts and docs.

It must not include:

- dense retrieval;
- embeddings or vector storage;
- RRF;
- reranker;
- query rewrite;
- HTTP or UI;
- OCR/ASR expansion;
- legacy RAG-OCR API migration.

## Handoff Prompt For Execution Window

```text
Continue MKE E3-F lexical-only runtime promotion.

Read AGENTS.md, ADR-0007, the E3-A/E3-B docs, and these new planning artifacts:

- docs/superpowers/specs/2026-06-26-cjk-lexical-runtime-promotion-design.md
- docs/superpowers/plans/2026-06-26-cjk-lexical-runtime-promotion-implementation.md
- docs/superpowers/reviews/2026-06-26-cjk-lexical-runtime-promotion-autoplan-review.md

Goal:
- promote cjk-trigram-overlap-v1 as the default owner-startup runtime retrieval strategy;
- preserve numeric-grouping-v1 and current as direct rollback strategies;
- add a persistent rebuildable CJK lexical projection, readiness/doctor and rebuild commands;
- update CLI/MCP owner-startup strategy contract without request-time MCP overrides;
- add ADR-0008, docs, proof, tests, and refreshed canonical artifacts.

Strict non-scope:
- no dense retrieval, embeddings, vector search, hybrid retrieval, RRF, reranker, query rewrite;
- no HTTP/UI behavior change;
- no legacy RAG-OCR API/service migration;
- no external recording or private planning material.

Use TDD. Keep implementation in an isolated worktree/branch. Do not push or create a PR until
review authorization. Stop and report if any E1/E2/E3-A/E3-B metric, gate, protocol, qrel, or
fixture-byte identity changes unexpectedly.
```
