# CJK Lexical Runtime Promotion Implementation Plan

Status: completed under the amended active-scan-first plan. Targeted re-review CLEAN with zero
findings; ready for user-authorized push and Ready PR creation.

Planning base: `main@1fdea11d70b410a0cddcf86a74af165be83daf14`.

Design: [CJK Lexical Runtime Promotion Design](../specs/2026-06-26-cjk-lexical-runtime-promotion-design.md)

Review: [CJK Lexical Runtime Promotion Autoplan Review](../reviews/2026-06-26-cjk-lexical-runtime-promotion-autoplan-review.md)

## Goal

Promote a verified lexical CJK recovery path into normal runtime Search and Ask without adding a
second persistent runtime projection unless performance or correctness forces that fallback.

The amended first implementation target is `cjk-active-scan-overlap-v1`: a bounded active Evidence
scan strategy that uses the same overlap thresholds that made E3-B pass, but reads SQLite domain
truth directly instead of building `cjk_lexical_fts`.

This plan is lexical-only. It does not implement embeddings, vector search, hybrid retrieval, RRF,
reranking, query rewrite, HTTP, UI, or legacy RAG-OCR service migration.

## Amendment Summary

Task 0.5 was executed in a clean isolated worktree and triggered the planned stop condition.

| Variant | Gates | Recall@5 | nDCG@10 | Second persistent projection |
|---|---:|---:|---:|---|
| `current_runtime` | failed | `0.295455` | `0.277279` | no |
| `active_fts_generated_terms` | failed | `0.295455` | `0.277279` | no |
| `unicode61_projection` | failed | `0.295455` | `0.277279` | yes |
| `trigram_projection` | passed | `0.659091` | `0.610619` | yes |
| `app_scan_no_projection` | passed | `0.659091` | `0.619152` | no |

Accepted conclusion:

- `trigram_projection` remains a valid fallback design.
- `app_scan_no_projection` is smaller and passed current quality gates.
- The implementation must not continue with persistent projection lifecycle first.
- The implementation must validate active scan under stricter runtime, performance, diagnostics,
  Ask, CLI, MCP, and installed-wheel proof gates before any default flip.

Also fixed artifact path drift: the current E3-A canonical artifact is
`benchmarks/retrieval/retrieval-chinese-v1-baseline.json`.

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

Do not reuse a worktree created before this amendment. If an old
`codex/cjk-lexical-runtime-promotion` worktree exists, confirm it is clean, remove it, and recreate
from latest `main`.

## Runtime Data Flow

```text
Owner startup
  -> RuntimeConfig(retrieval_strategy)
    -> KnowledgeEngine
      -> SQLiteStore
        -> Search(query)
          -> compile numeric-grouping-v1 query
             ├── non-empty: active_evidence_fts
             └── empty + eligible CJK terms:
                   active text Evidence scan
                   -> overlap score
                   -> deterministic top-k Evidence
        -> Ask(question)
          -> strategy-aware eligibility
          -> Search(question)
          -> cited answer or stable refusal
```

No new persistent CJK projection is created by the active-scan path.

## Task 0.5: Tokenizer Alternative Spike Completion Record

This task is complete. Do not rerun it as implementation unless the branch state or fixtures change.

Required implementation follow-up:

- record the spike result in ADR-0008;
- keep `trigram_projection` as a fallback design;
- implement `cjk-active-scan-overlap-v1` first;
- stop if implementation cannot meet the added runtime and performance gates without adding a
  projection.

Verification already observed in the spike:

```bash
uv run pytest tests/retrieval tests/evaluation -q
uv run pytest tests/evaluation/test_cjk_lexical_candidate.py -q
uv run mke eval retrieval-cjk-lexical \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --candidate cjk-trigram-overlap-v1 \
  --json > /tmp/mke-e3b-tokenizer-spike.json
```

## Task 1: Add ADR-0008 And Strategy Vocabulary

Add ADR-0008 before changing runtime behavior.

Expected files:

- `docs/decisions/0008-cjk-active-scan-retrieval-strategy.md`
- `src/mke/retrieval/strategy.py`
- compatibility exports from `src/mke/retrieval/__init__.py`
- tests under `tests/retrieval/`

Required RED tests:

- supported runtime strategies are exactly `current`, `numeric-grouping-v1`, and
  `cjk-active-scan-overlap-v1`;
- `cjk-trigram-overlap-v1` remains an evaluation artifact candidate, not an owner-startup runtime
  strategy in this amended plan;
- explicit strategy `cjk-active-scan-overlap-v1` is supported before the default is flipped;
- default strategy remains unchanged until the Default Promotion Launch Gate passes;
- `numeric-grouping-v1` remains a valid rollback strategy;
- invalid strategy fails with a stable public error;
- boolean-like or non-string strategy values are rejected before engine construction;
- legacy `RetrievalQueryPolicy` helpers remain available for existing E1/E2/E3 evaluation code;
- `RetrievalStrategyDescriptor` records strategy ID, revision, base query policy, required
  projections, term-derivation mode, readiness checker, rollback capability, fallback semantics,
  and explicit `dense=none`, `hybrid=none`, and `rerank=none` fields;
- adding a future strategy descriptor does not change public Search or Ask request DTOs.

ADR-0008 must include:

- E3-A and E3-B evidence basis;
- Task 0.5 spike table and conclusion;
- why active scan is first;
- why persistent trigram projection is deferred to fallback;
- Default Promotion Launch Gate;
- bounded active-scan contract;
- owner-startup selector and compatibility alias;
- rollback paths;
- limitations of public holdout evidence, CJK lexical matching, Japanese/Korean behavior, and
  common two-character CJK terms.

Verification:

```bash
uv run pytest tests/retrieval/test_query_policy.py tests/retrieval -q
```

## Task 2: Implement Bounded Active Evidence Scan

Implement the CJK branch without a second persistent projection.

Expected files:

- `src/mke/retrieval/cjk_active_scan.py`
- `src/mke/adapters/sqlite/__init__.py`
- tests under `tests/retrieval/` and `tests/storage/`

Required RED tests:

- active scan reads only active text Evidence;
- active scan excludes failed, partial, inactive, superseded, and unpublished Evidence;
- eligible CJK compiled-empty queries return the same expected Evidence class as the Task 0.5 spike;
- active scan applies `minimum_overlap_count=2` and `minimum_overlap_ratio=0.30`;
- active scan ranks by overlap count, overlap ratio, document ID, locator start, and Evidence ID;
- active scan does not depend on SQLite FTS5 `trigram` tokenizer availability;
- active scan adds no persistent CJK projection table or metadata table;
- rollback strategies do not call active-scan code;
- generated overlap terms are deduplicated;
- punctuation CJK cases such as `证据。生命周期` are either normalized into eligible terms or return
  stable below-minimum diagnostics;
- mixed ASCII+CJK queries with a compiled non-empty expression remain FTS-only and never silently
  drop ASCII or numeric constraints after an FTS zero-hit. A future constraint-preserving fallback
  requires a separate comparison.

Implementation notes:

- Reuse E3-B term derivation and overlap scorer semantics where possible.
- Keep the active scan bounded and deterministic.
- Do not scan raw filesystem artifacts; scan active SQLite Evidence rows.
- Do not use Python exceptions as public diagnostics.

Verification:

```bash
uv run pytest tests/retrieval tests/storage -q
```

## Task 3: Add Strategy Doctor And No-Projection Rebuild Behavior

Add local strategy readiness commands without inventing projection lifecycle.

Expected command shape:

```bash
mke retrieval doctor --strategy cjk-active-scan-overlap-v1 --json
mke retrieval rebuild --strategy cjk-active-scan-overlap-v1 --json
```

Required RED tests:

- `doctor` returns `ready` when the database is readable and active Publication state can be
  inspected;
- `doctor` returns stable `not_ready` when no active Publication exists;
- `doctor` output includes stable `problem`, `cause`, and `next_step`;
- `doctor` output never exposes tracebacks or absolute local paths;
- `rebuild` for `cjk-active-scan-overlap-v1` is either a stable no-op success or a stable usage
  response stating that the strategy has no projection to rebuild;
- the chosen `rebuild` behavior is documented in CLI reference and ADR-0008;
- Search and Ask never auto-run doctor or rebuild;
- rollback strategy `numeric-grouping-v1` works in a pre-E3-F database without any CJK readiness
  step.

Stable active-scan error contract:

| `problem` | `cause` | `next_step` |
|---|---|---|
| `no_active_publication` | `No active Publication is available to scan` | `ingest_and_publish_source` |
| `cjk_query_not_eligible` | `Query does not contain enough eligible CJK terms` | `revise_query_or_use_rollback_strategy` |
| `cjk_scan_budget_exceeded` | `CJK active Evidence scan would exceed configured local budget` | `narrow_query_or_use_projection_strategy` |
| `cjk_candidate_pool_capped` | `CJK candidate pool exceeded the configured cap` | `narrow_query` |
| `retrieval_strategy_unsupported` | `Requested retrieval strategy is not supported by this runtime` | `choose_supported_retrieval_strategy` |

Verification:

```bash
uv run pytest tests/cli tests/retrieval tests/storage -q
```

## Task 4: Wire Runtime Search And Ask Strategy

Implement the amended strategy in normal Search and Ask.

Expected files:

- `src/mke/application/__init__.py`
- `src/mke/runtime.py`
- `src/mke/adapters/sqlite/__init__.py`
- `tests/application/`
- `tests/retrieval/`

Required RED tests:

- default runtime strategy remains unchanged until launch gate;
- explicit `cjk-active-scan-overlap-v1` enables the CJK active-scan branch;
- non-empty `numeric-grouping-v1` compiled queries use the existing active FTS Search path;
- compiled-empty eligible CJK queries use active scan and overlap ranker;
- eligible CJK-only Ask input is not rejected merely because ASCII token count is zero;
- strategy-aware Ask validation accepts eligible CJK overlap terms for
  `cjk-active-scan-overlap-v1`;
- `numeric-grouping-v1` and `current` preserve old CJK-only invalid-input behavior;
- short or ineligible CJK queries remain no-hit, invalid-input, or insufficient-input according to
  the selected strategy's documented eligibility rules;
- hard-negative and unanswerable fixture queries do not become false positives beyond E3-B gates;
- rollback strategy `numeric-grouping-v1` works without CJK readiness;
- strategy selection is fixed at owner construction and cannot be changed per request.

Performance and safety bounds:

- `max_cjk_query_chars=512`;
- `max_overlap_terms=128`;
- fixed active Evidence row scan budget;
- fixed candidate pool cap;
- cap hits visible in diagnostics;
- no hidden truncation in metrics.

Verification:

```bash
uv run pytest tests/application tests/retrieval tests/storage -q
uv run pytest tests/performance -q
```

## Task 5: Preserve Publication Isolation Without Projection Lifecycle

Because active scan reads domain truth directly, implementation must prove it does not weaken
Publication isolation.

Required RED tests:

- active scan sees only the active Publication;
- a failed Run with matching CJK text is not searchable;
- an unpublished Run with matching CJK text is not searchable;
- a superseded Publication with matching CJK text is not searchable after a newer Publication is
  active;
- retry creates a new immutable Run rather than mutating failed Run identity;
- crash recovery does not mark partially ingested Evidence active;
- `numeric-grouping-v1` behavior is unchanged.

Implementation notes:

- Do not add a new activation stage.
- Do not change Run/Publication lifecycle semantics.
- If implementation discovers it needs persistent scan state, stop and re-review the projection
  fallback before continuing.

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

- `--retrieval-strategy cjk-active-scan-overlap-v1` starts the explicit strategy;
- omitting the selector keeps current default until launch gate;
- after launch gate, omitting the selector uses `cjk-active-scan-overlap-v1`;
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
- `benchmarks/retrieval/retrieval-chinese-v1-baseline.json`
- `benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json`

Required RED tests or scripted checks:

- artifact validators pass after refresh;
- E1 semantic payload is unchanged except permitted source/environment identity fields;
- E2 observations, metrics, gates, and verdict are unchanged;
- E3-A observations, miss classifications, metrics, and E3-B eligibility are unchanged;
- E3-B observations, SQL proof, metrics, gates, and verdict are unchanged;
- any quality metric delta stops execution before PR creation.

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

Prove the amended strategy from installed artifacts, not source-tree imports.

Required proof:

- Python 3.12 installed wheel;
- Python 3.13 installed wheel;
- explicit `cjk-active-scan-overlap-v1` CLI Search/Ask over the Chinese fixture;
- post-launch default CLI Search/Ask over the Chinese fixture;
- rollback `numeric-grouping-v1` CLI Search/Ask behavior;
- stdio MCP startup with explicit CJK strategy;
- stdio MCP startup with rollback strategy;
- installed-wheel stdio MCP tool-call proof: `list_libraries`, `ingest_file`, `get_run`,
  `search_library`, and `ask_library`;
- CJK MCP Search/Ask returns cited Evidence for the predeclared CJK compiled-empty class;
- rollback MCP Search/Ask preserves old behavior;
- active-scan budget error path returns stable path-redacted error fields;
- MCP tool schemas contain no request-time retrieval strategy field;
- hostile `PYTHONPATH`, external cwd, and repository import rejection;
- no network access or model download.

Verification command shape:

```bash
uv build
wheel=$(ls dist/*.whl | sort | tail -n1)
UV_OFFLINE=1 uv run python scripts/cjk_active_scan_runtime_deployment_proof.py \
  --wheel "$wheel" \
  --python 3.12 \
  --json
UV_OFFLINE=1 uv run python scripts/cjk_active_scan_runtime_deployment_proof.py \
  --wheel "$wheel" \
  --python 3.13 \
  --json
```

Add `scripts/cjk_active_scan_runtime_deployment_proof.py` and tests for it in the implementation
PR.

## Task 8.5: Default Promotion Launch Gate

Do not flip the runtime default at the start of implementation.

Required sequence:

1. Implement `cjk-active-scan-overlap-v1` behind explicit `--retrieval-strategy`.
2. Complete strategy doctor/no-projection rebuild behavior, publication isolation, CLI/MCP proof,
   performance gates, docs, and artifact refresh.
3. Run all validators and installed-wheel proofs.
4. Only then change `DEFAULT_RETRIEVAL_STRATEGY` to `cjk-active-scan-overlap-v1`.

Go/No-Go gates:

| Gate | Go condition | No-Go action |
|---|---|---|
| G1 evidence | Task 0.5 active-scan lift remains material and documented | stop and keep explicit-only |
| G2 regressions | E1/E2 semantic payloads unchanged | stop and re-review |
| G3 Chinese gates | E3-A/E3-B metrics, gates, qrels, and fixture bytes unchanged | stop and re-review |
| G4 hard negatives | hard-negative and unanswerable gates remain within E3-B limits | stop and re-review |
| G5 runtime | explicit and default CLI Search/Ask plus MCP tool-call proof pass | stop and fix |
| G6 rollback | `numeric-grouping-v1` and `current` rollback paths work without active-scan readiness | stop and fix |
| G7 performance | active-scan high-fanout, large-row-count, and long-query gates stay within fixed budgets | stop and choose projection fallback |
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

- architecture diagram for active FTS and active-scan fallback;
- strategy comparison table generated from artifacts and Task 0.5 spike result;
- direct offline proof command;
- short repository-visible demo script covering ingest, CJK Search/Ask, refusal, and rollback.

Do not publish an external recording without separate authorization.

Verification:

```bash
uv run pytest tests/evaluation/test_chinese_documentation.py -q
uv run python - <<'PY'
from pathlib import Path
docs = [
    Path("docs/decisions/0008-cjk-active-scan-retrieval-strategy.md"),
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
python - <<'PY'
from pathlib import Path
patterns = [
    "E3-F remain " + "unimplemented",
    "runtime " + "unchanged",
    "no runtime " + "promotion",
    "CJK-only " + "invalid_question",
    "--retrieval-query-policy " + "current",
    "cjk-trigram-overlap-v1 " + "default",
]
hits = []
for path in [Path("README.md"), *Path("docs").rglob("*.md")]:
    text = path.read_text(encoding="utf-8")
    for pattern in patterns:
        if pattern in text:
            hits.append((str(path), pattern))
if hits:
    for path, pattern in hits:
        print(f"{path}: stale pattern {pattern}")
    raise SystemExit(1)
print("stale-docs scan passed")
PY
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

This plan is allowed as one PR only if the active-scan strategy passes runtime, performance,
rollback, MCP, artifact, and docs gates without adding persistent projection lifecycle.

Stop and split or re-review if any of the following occurs:

- E1/E2/E3-A/E3-B metric, verdict, qrel, protocol, fixture-byte, or semantic-payload identity
  changes unexpectedly;
- active scan exceeds the fixed performance budgets;
- implementation requires a persistent CJK projection;
- CLI/MCP contract changes beyond owner-startup strategy selection and doctor/no-op rebuild
  operations;
- implementation requires dense/vector/hybrid/RRF/reranker/query rewrite work;
- Search/Ask cannot preserve Publication isolation without extra persistent state.

The implementation PR may include:

- ADR-0008;
- runtime strategy descriptor and active-scan branch;
- CLI/MCP owner-startup selector;
- doctor/no-projection rebuild behavior;
- artifact source identity refresh;
- proof scripts and docs.

## Completion Record

- Task 0.5: complete; no-projection active scan selected and projection-first work stopped.
- Tasks 1-6: complete; strategy descriptor, bounded active scan, doctor/no-op rebuild,
  Search/Ask routing, Publication isolation, and owner-startup CLI/MCP contracts implemented.
- Task 7: complete; the first E2 run stopped on scope identity, a supported temporary scope refresh
  proved semantic equality, and E1/E2/E3-A/E3-B artifacts were refreshed only through supported
  recoverable flows.
- Task 8: complete; Python 3.12 and 3.13 installed-wheel CLI/MCP proofs pass offline for explicit,
  default, and rollback paths.
- Task 8.5: complete; G1-G8 passed before `cjk-active-scan-overlap-v1` became the default.
- Task 9: complete; ADR, architecture, README files, tutorial, reference, focused how-to, MCP and
  evaluation guides, demo, durable review, stale scan, public-boundary scan, and document-release
  audit are complete.
- Task 10: complete; final verification commands and results are recorded in the implementation
  review. The 2026-06-27 targeted re-review of `1ede36c..6ad35df` was CLEAN with zero findings.
  Fresh review-window verification recorded `89 passed` with five existing warnings for the
  focused suite, a passing Python 3.12 E2 installed-wheel proof with explicit
  `selected_strategy=numeric-grouping-v1` and `rollback_strategy=current` across CLI and MCP,
  passing Ruff, Pyright with zero errors and warnings, and a passing
  `git diff --check 1ede36c..HEAD`. The worktree remained clean. The branch is ready for a
  user-authorized push and Ready PR; neither action has been performed.

The compiled-empty-only adjudication is final for this slice. Correct and incorrect number/unit
counterexamples showed that FTS-zero-hit active scan dropped constraints; mixed compiled non-empty
queries therefore remain FTS-only. Any future constraint-preserving fallback is separate work.

It must not include:

- persistent CJK projection unless this plan is re-reviewed;
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
Continue MKE E3-F lexical-only runtime promotion from the amended plan.

Read AGENTS.md, ADR-0007, the E3-A/E3-B docs, and these planning artifacts:

- docs/superpowers/specs/2026-06-26-cjk-lexical-runtime-promotion-design.md
- docs/superpowers/plans/2026-06-26-cjk-lexical-runtime-promotion-implementation.md
- docs/superpowers/reviews/2026-06-26-cjk-lexical-runtime-promotion-autoplan-review.md

Task 0.5 already found app_scan_no_projection passes gates and triggered the stop condition. Do not
continue the old persistent projection-first plan.

Goal:
- implement cjk-active-scan-overlap-v1 behind explicit owner-startup strategy selection;
- preserve numeric-grouping-v1 and current as direct rollback strategies;
- prove bounded active Evidence scanning without adding a persistent CJK projection;
- update CLI/MCP owner-startup strategy contract without request-time MCP overrides;
- add ADR-0008, docs, proof, tests, and refreshed canonical artifacts;
- only flip default after the launch gate passes.

Strict non-scope:
- no persistent CJK projection unless this amended plan fails and review window approves fallback;
- no dense retrieval, embeddings, vector search, hybrid retrieval, RRF, reranker, query rewrite;
- no HTTP/UI behavior change;
- no legacy RAG-OCR API/service migration;
- no external recording or private planning material.

Use TDD. Keep implementation in an isolated worktree/branch. Do not push or create a PR until
review authorization. Stop and report if any E1/E2/E3-A/E3-B metric, gate, protocol, qrel, or
fixture-byte identity changes unexpectedly, or if active-scan performance gates fail.
```

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | Autoplan | Continue E3-F lexical-only promotion with launch gates | Taste | P1 completeness | E3-B supports a bounded product-visible fix, but default promotion needs proof | wait for dense by default |
| 2 | Autoplan | Add tokenizer alternative spike before persistent projection implementation | Mechanical | P3 pragmatic | A smaller tokenizer-only approach had to be ruled out before adding projection lifecycle | assume trigram projection is the only viable path |
| 3 | Task 0.5 | Prefer `cjk-active-scan-overlap-v1` over persistent trigram projection as first runtime path | Mechanical | P3 pragmatic | Active scan passed the same quality gates without a second persistent projection | start with `cjk_lexical_fts` |
| 4 | Eng | Make Ask validation strategy-aware for eligible CJK | Mechanical | P1 completeness | Search promotion is incomplete if Agent-facing Ask still rejects CJK-only questions | leave Ask semantics unchanged |
| 5 | Eng | Preserve Publication isolation through active-only scan tests | Mechanical | P5 explicit | Removing projection lifecycle shifts the safety proof to active-row selection | rely on current tests implicitly |
| 6 | Eng | Add hard active-scan performance gate | Mechanical | P1 completeness | The no-projection path is only acceptable if bounded local latency and candidate caps hold | trust small fixture only |
| 7 | DX | Require installed-wheel MCP tool-call proof, not startup-only proof | Mechanical | P1 completeness | MCP is the primary Agent-facing interface | prove only server startup |
| 8 | DX | Add docs stale scan, public-boundary scan, and focused CJK how-to | Mechanical | P5 explicit | Users need one entry point and docs must not retain stale default claims | scatter CJK usage across durable plans |

## GSTACK REVIEW REPORT

Autoplan was previously rerun with CEO, engineering, and DX phases. UI design review was skipped
because this plan has no UI surface. External Claude Code CLI and Codex CLI voices were used; no
in-session subagent tool was used.

Targeted amendment review was performed after Task 0.5 found that `app_scan_no_projection` passes
the current E3-B gates without requiring a second persistent projection.

Result: approved for execution only under the amended active-scan-first path. The persistent
projection path is now fallback-only and requires re-review if needed. The main required safeguards
are strategy-aware Ask validation, active Publication isolation tests, hard active-scan performance
budgets, installed-wheel MCP tool-call proof, explicit default launch gate, stale-docs scan, and
public-boundary scan.

NO UNRESOLVED DECISIONS
