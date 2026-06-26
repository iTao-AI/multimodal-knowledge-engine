# CJK Lexical Runtime Promotion Autoplan And Amendment Review

Status: completed. Amended after Task 0.5 tokenizer alternative spike.

Reviewed artifacts:

- [CJK Lexical Runtime Promotion Design](../specs/2026-06-26-cjk-lexical-runtime-promotion-design.md)
- [CJK Lexical Runtime Promotion Implementation Plan](../plans/2026-06-26-cjk-lexical-runtime-promotion-implementation.md)
- [Chinese Hybrid Retrieval Evaluation Design](../specs/2026-06-25-chinese-hybrid-retrieval-evaluation-design.md)
- [CJK Lexical Candidate Design](../specs/2026-06-26-cjk-lexical-candidate-design.md)

## Original Autoplan Review

The original planning PR ran the `gstack-autoplan` flow for CEO, engineering, and DX phases.

- UI design review was skipped because the plan has no UI surface.
- DX review was run because the plan changes CLI, MCP, commands, errors, docs, and Agent-facing
  behavior.
- External Claude Code CLI and Codex CLI voices were used for independent review.
- Raw GStack artifacts, local restore points, private planning paths, and session transcripts are
  not recorded in this repository.

Original verdict: proceed only after adding:

- tokenizer alternative spike before persistent projection work;
- strategy-aware Ask validation;
- same-transaction Publication activation for CJK projection state;
- existing-database doctor/rebuild upgrade path;
- installed-wheel MCP tool-call proof;
- explicit Default Promotion Launch Gate;
- high-fanout CJK performance gates;
- stale-docs and public-boundary scans.

## Task 0.5 Result

The execution window stopped before Task 1 because the tokenizer alternative spike found a smaller
candidate that satisfies the current E3-B gates without a second persistent runtime projection.

| Variant | Gates | Recall@5 | nDCG@10 | Second persistent projection |
|---|---:|---:|---:|---|
| `current_runtime` | failed | `0.295455` | `0.277279` | no |
| `active_fts_generated_terms` | failed | `0.295455` | `0.277279` | no |
| `unicode61_projection` | failed | `0.295455` | `0.277279` | yes |
| `trigram_projection` | passed | `0.659091` | `0.610619` | yes |
| `app_scan_no_projection` | passed | `0.659091` | `0.619152` | no |

This was a real stop condition. Continuing directly into persistent projection lifecycle would
violate the original plan's own scope gate.

## Targeted Amendment Review

The review scope was intentionally narrower than a full autoplan rerun:

- evaluate whether no-projection active scan is architecturally acceptable as the first
  implementation path;
- identify added safety and performance gates needed to avoid turning a spike shortcut into a
  fragile runtime default;
- update the durable design and plan so execution can continue from `main` without mixing planning
  changes into implementation code.

### What already exists

| Sub-problem | Existing asset | Reuse decision |
|---|---|---|
| CJK term derivation and overlap thresholds | E3-B `cjk-trigram-overlap-v1` comparison code and artifact | Reuse semantics; do not copy evaluation-only tables blindly. |
| Active Publication isolation | Existing SQLite domain truth and Search over active Publications | Reuse as the active-scan source of truth. |
| Rollback lexical path | `numeric-grouping-v1` and `current` | Preserve unchanged. |
| Artifact validation | E1/E2/E3-A/E3-B validators | Refresh source identity only; metrics and verdicts must remain stable. |
| MCP proof pattern | Existing installed-wheel CLI/MCP proof style | Extend to actual `search_library` and `ask_library` calls. |

### Architecture Review

Finding A1: **Projection-first is now over-engineered for the next implementation step.**

- Evidence: Task 0.5 shows `app_scan_no_projection` passes gates with the same Recall@5 as
  `trigram_projection` and higher nDCG@10 on the current protocol.
- Decision: amend E3-F to implement `cjk-active-scan-overlap-v1` first.
- Guardrail: persistent trigram projection remains fallback-only if active scan fails performance,
  diagnostics, or proof gates.

Finding A2: **Removing projection lifecycle shifts the main risk to bounded scans and Publication
isolation.**

- Evidence: active scan reads domain Evidence directly instead of relying on projection readiness.
- Decision: replace projection readiness tasks with active-only row selection, failed/partial Run
  exclusion, and hard performance gates.
- Guardrail: implementation must stop if it needs persistent state to meet the gates.

Finding A3: **The runtime strategy name must not imply a trigram projection.**

- Evidence: `cjk-trigram-overlap-v1` is now misleading for the no-projection runtime path.
- Decision: use `cjk-active-scan-overlap-v1` for owner-startup runtime strategy.
- Guardrail: keep `cjk-trigram-overlap-v1` as the E3-B comparison candidate and projection fallback
  design.

### Code Quality Review

Finding Q1: **Avoid embedding spike-only code into production without a strategy descriptor.**

- Decision: keep `RetrievalStrategyDescriptor`, but change required projection metadata to
  `required_projections=[]` and a `term_derivation_mode` field for active scan.

Finding Q2: **Doctor/rebuild semantics need to be explicit for a no-projection strategy.**

- Decision: `doctor` remains useful; `rebuild` must be either stable no-op success or stable usage
  response saying no projection exists.
- Guardrail: Search and Ask must never auto-run doctor or rebuild.

### Test Review

Coverage map for the amended plan:

```text
CODE PATHS                                      TEST REQUIREMENTS
[+] Runtime strategy parsing
  ├── explicit cjk-active-scan-overlap-v1       strategy allowlist + invalid value tests
  ├── rollback numeric-grouping-v1/current      rollback behavior tests
  └── conflicting selector names                usage exit 2 tests

[+] Search
  ├── non-empty compiled query                  existing active_evidence_fts path unchanged
  ├── empty + eligible CJK terms                active scan returns expected Evidence
  ├── ineligible CJK terms                      stable diagnostic/no-hit behavior
  ├── high-fanout query                         budget/cap diagnostic
  └── inactive/failed/superseded Evidence       not scanned

[+] Ask
  ├── eligible CJK-only question                accepted under active-scan strategy
  ├── same question under rollback strategy     old invalid-input behavior preserved
  └── hard-negative/unanswerable query          no false-positive beyond gates

[+] CLI/MCP
  ├── explicit strategy startup                 installed-wheel CLI/MCP proof
  ├── default after launch gate                 installed-wheel CLI/MCP proof
  ├── rollback startup                          installed-wheel CLI/MCP proof
  └── request-time MCP override                 schema absence test
```

Required additions:

- active Publication isolation regressions;
- active scan budget and candidate-pool cap tests;
- strategy-aware Ask validation tests;
- installed-wheel MCP tool-call proof;
- artifact semantic-equality checks after source identity refresh.

### Performance Review

The active-scan path is acceptable only with hard local budgets.

Required gates:

- maximum CJK query length;
- maximum overlap terms;
- maximum active Evidence rows scanned;
- maximum candidate pool size;
- deterministic timeout or budget failure with stable diagnostics;
- `tests/performance` coverage for worst-case local fixture scale.

If these gates fail, the execution window must stop and ask the review window whether to switch back
to persistent trigram projection.

## NOT In Scope

- Dense retrieval, vector search, hybrid retrieval, RRF, reranker, and query rewrite.
- HTTP API or UI behavior.
- OCR, ASR, PDF parser, chunking, or segmentation expansion.
- LangChain, LlamaIndex, LangGraph, retrieval SDK, or hosted service integration.
- Migration from the legacy RAG-OCR service layout.
- External video publication.
- Persistent CJK projection in the first amended implementation path.

## Failure Modes Registry

| Failure mode | Severity | Required mitigation |
|---|---|---|
| Active scan reads failed or inactive Evidence | Critical | Active Publication isolation tests and storage-level filtering. |
| Active scan passes small eval but is too slow on larger local DBs | Critical | Hard scan/candidate budgets and performance tests. |
| CJK-only Ask is still rejected before retrieval runs | Critical | Strategy-aware Ask validation tests. |
| MCP proof passes startup but tool calls fail | High | Installed-wheel `search_library` and `ask_library` proof. |
| Runtime strategy name implies a projection that no longer exists | Medium | Use `cjk-active-scan-overlap-v1`; keep trigram name for artifact/fallback only. |
| Docs keep projection-first wording | Medium | Stale-docs grep and docs update. |

## Implementation Tasks

Synthesized from this targeted review.

- [ ] **T1 (P1)** — Strategy — introduce `cjk-active-scan-overlap-v1` descriptor and ADR-0008.
  - Surfaced by: Architecture Review A3.
  - Files: `src/mke/retrieval/strategy.py`, `docs/decisions/0008-cjk-active-scan-retrieval-strategy.md`.
  - Verify: `uv run pytest tests/retrieval -q`.
- [ ] **T2 (P1)** — Retrieval — implement bounded active Evidence scan over active Publication rows.
  - Surfaced by: Architecture Review A1/A2.
  - Files: `src/mke/retrieval/cjk_active_scan.py`, `src/mke/adapters/sqlite/__init__.py`.
  - Verify: `uv run pytest tests/retrieval tests/storage -q`.
- [ ] **T3 (P1)** — Application — make Ask validation strategy-aware for eligible CJK-only questions.
  - Surfaced by: Test Review.
  - Files: `src/mke/application/__init__.py`, `tests/application/`.
  - Verify: `uv run pytest tests/application tests/retrieval -q`.
- [ ] **T4 (P1)** — Performance — add active-scan budget/candidate caps and tests.
  - Surfaced by: Performance Review.
  - Files: `tests/performance/`, retrieval strategy implementation.
  - Verify: `uv run pytest tests/performance -q`.
- [ ] **T5 (P2)** — CLI/MCP — expose owner-startup strategy selector and installed-wheel tool-call proof.
  - Surfaced by: Code Quality and Test Review.
  - Files: `src/mke/cli.py`, MCP runtime configuration, `scripts/cjk_active_scan_runtime_deployment_proof.py`.
  - Verify: Python 3.12/3.13 installed-wheel proof.
- [ ] **T6 (P2)** — Docs and artifacts — refresh source identity and public docs without changing metrics.
  - Surfaced by: Documentation and artifact path drift.
  - Files: benchmark artifacts, ADR, reference docs, how-to docs.
  - Verify: E1/E2/E3-A/E3-B validators and stale-docs scan.

## Completion Summary

- Step 0: Scope Challenge — scope reduced from projection-first to active-scan-first.
- Architecture Review: 3 findings, all folded into design and plan.
- Code Quality Review: 2 findings, all folded into plan.
- Test Review: coverage diagram produced, 5 required groups identified.
- Performance Review: 1 blocking gate added.
- NOT in scope: written.
- What already exists: written.
- TODO updates: none; all items are inside the amended implementation scope.
- Failure modes: 3 critical gaps flagged and converted into required tests/gates.
- Outside voice: skipped; this was a targeted amendment after prior autoplan.
- Parallelization: sequential implementation recommended; strategy, storage, application, CLI/MCP,
  and proof touch shared retrieval/runtime modules.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|---|---|---|---:|---|---|
| CEO Review | `gstack-autoplan` | Scope & strategy | 1 | CLEAR | Original promotion direction accepted with tokenizer spike gate. |
| Eng Review | targeted amendment | Architecture & tests | 1 | CLEAR | Projection-first reduced to active-scan-first with performance and isolation gates. |
| DX Review | `gstack-autoplan` | Developer experience gaps | 1 | CLEAR | CLI/MCP proof, docs, and stale scans retained. |
| Design Review | skipped | No UI surface | 0 | N/A | No UI behavior in scope. |

- **VERDICT:** E3-F is ready to resume implementation from the amended active-scan-first plan.

NO UNRESOLVED DECISIONS
