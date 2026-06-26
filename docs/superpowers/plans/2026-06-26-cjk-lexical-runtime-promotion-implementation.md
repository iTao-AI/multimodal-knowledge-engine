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

## Task 0.5: Run Tokenizer Alternative Spike

Before adding persistent projection lifecycle code, test whether a smaller tokenizer-only change can
close the same E3-B failure class.

Required spike cases:

- current `active_evidence_fts` tokenizer behavior;
- SQLite FTS5 `unicode61` projection;
- SQLite FTS5 `trigram` projection;
- app-generated n-gram terms without a second persistent runtime projection;
- custom SQLite tokenizer extension, rejected unless it remains local, reproducible, and dependency
  free.

Required evidence:

- each candidate runs against the E3-A protocol and the E3-B comparison candidate class;
- each candidate records portability, dependency, rebuild, artifact, and runtime contract impact;
- if `unicode61` or another smaller option matches the E3-B gates without requiring a second
  persistent projection, stop this plan and re-review a smaller ADR;
- if only `trigram` passes the launch gates, record the rejected alternatives in ADR-0008.

Verification:

```bash
uv run pytest tests/evaluation/test_cjk_lexical_candidate.py -q
uv run mke eval retrieval-cjk-lexical \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --candidate cjk-trigram-overlap-v1 \
  --json > /tmp/mke-e3b-tokenizer-spike.json
```

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
- explicit strategy `cjk-trigram-overlap-v1` is supported before the default is flipped;
- default strategy remains unchanged until the Default Promotion Launch Gate passes;
- `numeric-grouping-v1` remains a valid rollback strategy;
- invalid strategy fails with a stable public error;
- boolean-like or non-string strategy values are rejected before engine construction;
- legacy `RetrievalQueryPolicy` helpers remain available for existing E1/E2/E3 evaluation code.
- `RetrievalStrategyDescriptor` records strategy ID, revision, base query policy, required
  projections, tokenizer, readiness checker, rollback capability, fallback semantics, and explicit
  `dense=none`, `hybrid=none`, and `rerank=none` fields for this slice.
- adding a future strategy descriptor does not change public Search or Ask request DTOs.

Implementation notes:

- Introduce `RetrievalStrategy` as the owner-facing concept.
- Keep `RetrievalQueryPolicy` as the lower-level compiler concept for `current` and
  `numeric-grouping-v1`.
- Do not expose strategy selection through Search or Ask request DTOs.
- ADR-0008 must include a `Default Promotion Gate` section and a `Rejected Alternatives` table.
- ADR-0008 must explicitly state that Japanese and Korean behavior is not validated even though the
  strategy identifier uses `CJK`.
- ADR-0008 must record that common two-character CJK terms can be below the trigram minimum unless
  part of a longer continuous CJK run.

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
- descriptor digest is written to projection metadata and changes when strategy revision or
  projection requirements change.

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
- a pre-E3-F database with active Publications but no CJK projection reports `not_ready`;
- the same pre-E3-F database can start with rollback strategy `numeric-grouping-v1`;
- after `rebuild`, the same database reports `ready` and default CJK Search/Ask works;
- Search and Ask never auto-rebuild the projection.

Stable error contract:

| `problem` | `cause` | `next_step` |
|---|---|---|
| `cjk_projection_missing` | `CJK lexical projection table does not exist` | `run_retrieval_rebuild` |
| `cjk_projection_stale` | `CJK projection metadata does not match active Evidence` | `run_retrieval_rebuild` |
| `cjk_tokenizer_unsupported` | `SQLite FTS5 trigram tokenizer is not available` | `use_numeric_grouping_or_reinstall_sqlite` |
| `cjk_projection_build_failed` | `CJK projection rebuild did not complete` | `inspect_publication_failure` |

Existing database upgrade commands:

```bash
uv run mke --db <existing.sqlite> retrieval doctor \
  --strategy cjk-trigram-overlap-v1 \
  --json
uv run mke --db <existing.sqlite> retrieval rebuild \
  --strategy cjk-trigram-overlap-v1 \
  --json
uv run mke --db <existing.sqlite> \
  --retrieval-strategy cjk-trigram-overlap-v1 \
  search "<cjk query>"
uv run mke --db <existing.sqlite> \
  --retrieval-strategy numeric-grouping-v1 \
  search "<same query>"
```

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
- eligible CJK-only Ask input is not rejected merely because ASCII token count is zero;
- strategy-aware Ask validation accepts eligible CJK trigrams for `cjk-trigram-overlap-v1`;
- `numeric-grouping-v1` and `current` preserve the old CJK-only invalid-input behavior;
- short or ineligible CJK queries remain no-hit, invalid-input, or insufficient-input according to
  the selected strategy's documented eligibility rules;
- hard-negative and unanswerable fixture queries do not become false positives beyond E3-B gates;
- missing or stale CJK projection fails closed for the selected default strategy;
- rollback strategy `numeric-grouping-v1` works without CJK projection readiness;
- strategy selection is fixed at owner construction and cannot be changed per request.
- CJK punctuation joining cases, such as `证据。生命周期`, are either supported by normalization or
  explicitly recorded as below-minimum diagnostics;
- mixed ASCII+CJK queries do not silently drop the CJK part when the ASCII branch is insufficient;
- high-fanout CJK queries are bounded by fixed caps and fail or truncate with stable diagnostics.

Implementation notes:

- Reuse E3-B term derivation and overlap scorer semantics.
- Preserve ranking tie-breakers exactly.
- Parameterize FTS5 `MATCH` expressions.
- Avoid silent fallback from selected `cjk-trigram-overlap-v1` to `numeric-grouping-v1` when the
  projection is stale; using the numeric branch for non-empty compiled queries is expected.
- Deduplicate generated trigram terms before constructing `MATCH`.
- Use fixed bounds: `max_cjk_query_chars=512`, `max_trigram_terms=128`, and a documented candidate
  pool cap. Any truncation must be visible in diagnostics and must not be hidden in metrics.

Verification:

```bash
uv run pytest tests/application tests/retrieval tests/storage -q
uv run pytest tests/performance -q
```

## Task 5: Bind Projection Build To Publication Activation

Ensure a selected CJK strategy cannot publish partial searchable state.

Required RED tests:

- activating a new Publication under `cjk-trigram-overlap-v1` builds both active FTS and CJK
  projection before the new Publication is visible to Search;
- active FTS replacement, CJK projection rows, CJK metadata, source active pointer, Run state, and
  Run event commit in the same SQLite transaction;
- injected CJK projection failure fails the Run or activation path and preserves the previous active
  Publication;
- injected CJK projection failure before rows, before metadata, after metadata, and before commit all
  roll back the entire activation;
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
- installed-wheel stdio MCP tool-call proof: `list_libraries`, `ingest_file`, `get_run`,
  `search_library`, and `ask_library`;
- default MCP Search/Ask returns cited Evidence for the predeclared CJK compiled-empty class;
- rollback MCP Search/Ask preserves old behavior;
- stale CJK projection MCP path returns stable path-redacted error fields;
- MCP tool schemas contain no request-time retrieval strategy field;
- hostile `PYTHONPATH`, external cwd, and repository import rejection;
- no network access or model download.

Verification command shape:

```bash
uv build
wheel=$(ls dist/*.whl | sort | tail -n1)
UV_OFFLINE=1 uv run python scripts/cjk_lexical_runtime_deployment_proof.py \
  --wheel "$wheel" \
  --python 3.12 \
  --json
UV_OFFLINE=1 uv run python scripts/cjk_lexical_runtime_deployment_proof.py \
  --wheel "$wheel" \
  --python 3.13 \
  --json
```

Add `scripts/cjk_lexical_runtime_deployment_proof.py` and tests for it in the implementation PR.

## Task 8.5: Default Promotion Launch Gate

Do not flip the runtime default at the start of implementation.

Required sequence:

1. Implement `cjk-trigram-overlap-v1` behind explicit `--retrieval-strategy`.
2. Complete projection doctor/rebuild, activation isolation, CLI/MCP proof, performance gates,
   docs, and artifact refresh.
3. Run all validators and installed-wheel proofs.
4. Only then change `DEFAULT_RETRIEVAL_STRATEGY` to `cjk-trigram-overlap-v1`.

Go/No-Go gates:

| Gate | Go condition | No-Go action |
|---|---|---|
| G1 evidence | E3-B compiled-empty class lift remains material | stop and keep comparison-only |
| G2 regressions | E1/E2 semantic payloads unchanged | stop and re-review |
| G3 Chinese gates | E3-A/E3-B metrics, gates, qrels, and fixture bytes unchanged | stop and re-review |
| G4 hard negatives | hard-negative and unanswerable gates remain within E3-B limits | stop and re-review |
| G5 runtime | default CLI Search/Ask and MCP tool-call proof pass | stop and fix |
| G6 rollback | `numeric-grouping-v1` and `current` rollback paths work without CJK projection | stop and fix |
| G7 performance | high-fanout and long-query gates stay within fixed local budgets | stop and tune or defer default |
| G8 docs | stale docs scan and public-boundary scan pass | stop and fix docs |

Any No-Go gate blocks default promotion and requires review-window approval before continuing.

## Task 9: Update Public Documentation And Demo Assets

Required docs:

- ADR-0008;
- architecture explanation;
- `README.md`;
- getting-started tutorial;
- CLI reference;
- public contracts;
- focused CJK how-to at `docs/how-to/enable-cjk-retrieval.md`;
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
    Path("docs/how-to/enable-cjk-retrieval.md"),
    Path("docs/how-to/run-chinese-retrieval-evaluation.md"),
    Path("docs/how-to/use-mke-mcp.md"),
    Path("docs/tutorials/getting-started.md"),
    Path("README.md"),
    Path("docs/README.md"),
]
missing = [path for path in docs if not path.exists()]
if missing:
    raise SystemExit(f"missing docs: {missing}")
print("scoped docs exist")
PY
rg -n "E3-F remain unimplemented|runtime.*unchanged|no runtime promotion|CJK-only.*invalid_question|--retrieval-query-policy current" README.md docs
python - <<'PY'
from pathlib import Path
bad = []
patterns = ["/" + "Users/", "." + "gstack", "/autoplan " + "restore point"]
for path in [Path("README.md"), *Path("docs").rglob("*.md")]:
    text = path.read_text(encoding="utf-8")
    if any(pattern in text for pattern in patterns):
        bad.append(str(path))
if bad:
    raise SystemExit("private/public-boundary leak: " + ", ".join(bad))
print("public-boundary scan passed")
PY
git diff --check
```

Every stale-docs grep hit must be updated, marked as historical context, or justified in the
durable review.

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

### Split Or Abort Rule

This plan is allowed as one PR only because default strategy promotion requires atomic safety across
strategy selection, projection lifecycle, activation, CLI/MCP proof, artifact identity, and docs.

Stop and split or re-review if any of the following occurs:

- E1/E2/E3-A/E3-B metric, verdict, qrel, protocol, fixture-byte, or semantic-payload identity
  changes unexpectedly;
- schema lifecycle grows beyond CJK projection tables and metadata;
- CLI/MCP contract changes beyond owner-startup strategy selection and doctor/rebuild operations;
- tokenizer spike shows a smaller approach can satisfy the same gates;
- performance gates require non-trivial ranking or indexing redesign;
- implementation requires dense/vector/hybrid/RRF/reranker/query rewrite work.

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

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | Continue E3-F lexical-only promotion, but add stricter launch gates | Taste | P1 completeness | E3-B supports the smallest product-visible fix, but default promotion needs explicit Go/No-Go evidence | wait for dense by default |
| 2 | CEO | Add tokenizer alternative spike before persistent projection implementation | Mechanical | P3 pragmatic | A smaller tokenizer-only approach must be ruled out before adding projection lifecycle | assume trigram projection is the only viable path |
| 3 | Eng | Make Ask validation strategy-aware for eligible CJK | Mechanical | P1 completeness | Search promotion is incomplete if Agent-facing Ask still rejects CJK-only questions | leave Ask semantics unchanged |
| 4 | Eng | Require same-transaction activation for active FTS, CJK projection, metadata, pointer, and Run event | Mechanical | P5 explicit | Publication switching must not expose partial searchable state | rely on vague before-visible wording |
| 5 | Eng | Add existing-database upgrade path and stable CJK projection error contract | Mechanical | P1 completeness | Existing local databases need copy-paste recovery after default changes | greenfield-only docs |
| 6 | DX | Require installed-wheel MCP tool-call proof, not startup-only proof | Mechanical | P1 completeness | MCP is the primary Agent-facing interface | prove only server startup |
| 7 | DX | Add docs stale scan, public-boundary scan, and focused CJK how-to | Mechanical | P5 explicit | Users need one entry point and docs must not retain stale default claims | scatter CJK usage across durable plans |
| 8 | Eng | Add high-fanout CJK performance gate | Mechanical | P1 completeness | A default strategy must bound query fanout and local latency | rely on small evaluation corpus only |

## GSTACK REVIEW REPORT

Autoplan was rerun with CEO, engineering, and DX phases. UI design review was skipped because this
plan has no UI surface. External Claude Code CLI and Codex CLI voices were used for the review; no
in-session subagent tool was used.

Result: approved for execution only after the plan changes above. The main required changes are:
tokenizer alternative spike, strategy-aware Ask validation, same-transaction projection activation,
existing-database upgrade path, installed-wheel MCP tool-call proof, explicit default launch gate,
performance gate, stale-docs scan, and public-boundary scan.
