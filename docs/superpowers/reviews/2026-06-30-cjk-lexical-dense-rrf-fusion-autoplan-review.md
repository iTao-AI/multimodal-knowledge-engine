# CJK Lexical Dense RRF Fusion Candidate Autoplan Review

Status: clean and approved for implementation after plan amendments.

Review date: 2026-06-30

Reviewed inputs:

- `main@0fe1d5640f914e8307ec938e36ba145419c64872`
- [CJK Lexical Dense RRF Fusion Candidate Design](../specs/2026-06-30-cjk-lexical-dense-rrf-fusion-design.md)
- [CJK Lexical Dense RRF Fusion Candidate Implementation Plan](../plans/2026-06-30-cjk-lexical-dense-rrf-fusion-implementation.md)
- `benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json`
- `src/mke/evaluation/dense_artifact.py`
- `src/mke/evaluation/dense_replay.py`
- existing E1, E2, E3-A, E3-B, and E3-C artifact validation patterns

Review mode: selective expansion with strict comparison-only scope.

UI review: skipped because E3-D adds no graphical interface.

DX review: included because E3-D adds evaluation CLI behavior, artifact validation, public error
messages, and operator-facing reproduction docs.

Outside voices: not run in this host because the current coordination rules prohibit silently
spawning subagents. Missing outside voice is recorded as `N/A`, not as consensus. This review
therefore treats every finding as a primary planning-window finding that must be checked against
repository files.

## Verdict

E3-D should proceed as planned: rank-only RRF over the current CJK lexical runtime arm and the
canonical E3-C dense arm. The plan correctly avoids runtime promotion, API adapters, reranking,
query rewrite, segmentation, and raw-score weighting.

Two plan amendments were required before implementation:

1. The plan now freezes how arm ranks are derived: lexical ranks come only from
   `retrieved_locators` list order, dense candidates are threshold-filtered by the frozen E3-C
   selected threshold, and surviving dense rows keep their recorded E3-C rank.
2. The artifact validator test path no longer allows a permanent skip before the canonical artifact
   exists. Task 6 must validate a temporary generated artifact under `tmp_path`; Task 8 then switches
   the same validation path to the checked-in artifact.

No unresolved architecture, evidence-integrity, or DX findings remain.

## Premise Review

| Premise | Verdict | Review basis |
|---|---|---|
| E3-D should test fusion before reranking | Accepted | E3-C found complementarity, but the project has not yet proven whether relevant Evidence is present in the bounded union but poorly ranked. |
| RRF should be rank-only | Accepted | FTS-like lexical ranking and dense cosine are not calibrated score spaces; rank-only RRF isolates one variable. |
| Runtime default should not change | Accepted | E3-D is a comparison artifact. No Search, Ask, MCP, owner-startup, Publication, or runtime strategy behavior changes are required. |
| Dense scoring should not rerun to tune E3-D | Accepted | E3-D consumes the canonical E3-C dense artifact. Cache-ready replay remains verification only. |
| Reranker can follow immediately if fusion under-ranks a relevant union | Accepted as conditional | Only if diagnostics show relevant Evidence exists in the bounded union and fusion misses top-5. |
| Passage or segmentation should wait | Accepted as conditional | If neither lexical nor dense top-10 contains relevant Evidence, the next branch is Passage/segmentation or query understanding, not reranking. |

## Existing Code Leverage

| Sub-problem | Existing implementation | Decision |
|---|---|---|
| Dense artifact integrity | `src/mke/evaluation/dense_artifact.py` | Reuse the model-free rebuild pattern and current-runtime semantic digest binding. |
| Dense replay proof | `src/mke/evaluation/dense_replay.py` | Keep replay as cache-ready verification, not E3-D scoring input. |
| Graded metrics | `src/mke/evaluation/graded_metrics.py` | Reuse existing Recall, MRR, nDCG, refusal, and hard-negative metrics. |
| Chinese protocol/qrels | `src/mke/evaluation/chinese_protocol.py` and `tests/fixtures/retrieval-chinese-v1/protocol.json` | Reuse frozen split and qrel semantics; do not create new qrels. |
| Artifact hardening | E1/E2/E3-A/E3-B validators | Reuse source identity, semantic equality, bool/int rejection, and tamper-regression patterns. |
| CLI style | existing `mke eval ...` commands in `src/mke/cli.py` | Add one evaluation command with stable public errors and no runtime selector. |

## Architecture Review

```text
E3-C dense artifact
  ├─ current_runtime.semantics.results  ── lexical rank input
  ├─ development_candidate.observations ── dense development rank input
  └─ holdout_candidate.observations     ── dense holdout rank input

frozen E3-D protocol
  ├─ candidate config: k=60, equal weights, depth=10
  ├─ bound source identities
  └─ development/holdout state machine

hybrid_rrf_workflow
  ├─ validates E3-C artifact
  ├─ binds arm rows to stable Evidence identity
  ├─ filters dense rows by selected_threshold
  ├─ calls pure rrf_fusion
  └─ records metrics, diagnostics, freeze, receipt, comparison artifact

hybrid_rrf_artifact
  └─ recomputes deterministic fields from protocol + dense artifact + repository
```

The component boundary is sound. `rrf_fusion.py` remains pure and model-free. Workflow code owns
artifact loading and split state. The validator owns independent recomputation. This keeps E3-D
out of runtime Search/Ask/MCP and prevents a comparison experiment from becoming production policy.

## Error And Rescue Map

| Codepath | What can go wrong | Required behavior |
|---|---|---|
| Protocol load | Missing file, schema drift, source identity mismatch | Raise stable `HybridRrfProtocolError`; CLI exits non-zero without traceback. |
| Dense artifact load | Missing artifact, invalid E3-C status, stale source identity | Raise stable workflow/artifact error; no holdout observation. |
| Arm extraction | Missing `query_id`, wrong split, duplicate locator, unbound lexical row | Fail closed before fusion. |
| Dense thresholding | Selected threshold disagreement or below-threshold row included | Fail closed and reject artifact/observed payload. |
| RRF scoring | Duplicate input, invalid rank, bool-as-int, non-finite score | Fail closed in pure fusion tests. |
| Development freeze | Existing freeze path or failed development gates | Exclusive-create refusal or valid-negative without holdout. |
| Holdout receipt | Receipt already exists or freeze/artifact changed | Refuse observation; no overwrite. |
| Artifact validation | Coordinated tampering of fused rows and observed report | Recompute from protocol and dense artifact; reject mismatch. |
| CLI rendering | Internal path or traceback in public error output | Return stable problem/cause/next-step fields only. |

## Test Diagram

```text
Pure RRF contract
  ├─ rank-only score calculation
  ├─ dedupe by locator + source digest
  ├─ deterministic tie-break order
  └─ invalid rank/type/duplicate rejection

Protocol lock
  ├─ candidate id/revision/config frozen
  ├─ source identity bound
  └─ qrel/fixture mutation rejection

Arm binding
  ├─ lexical rank from retrieved_locators order
  ├─ dense row threshold filtering
  ├─ dense recorded rank preserved
  ├─ stable Evidence digest binding
  └─ E3-C status gates enforced

Workflow state
  ├─ development metrics and diagnostics
  ├─ valid-negative blocks holdout
  ├─ freeze exclusive-create
  ├─ holdout receipt exclusive-create
  └─ artifact mutation after freeze rejected

Artifact validator
  ├─ model-free recomputation
  ├─ fused rank/score/contribution tamper rejection
  ├─ diagnostics tamper rejection
  ├─ bool-as-int and malformed locator rejection
  └─ temporary artifact before Task 8, canonical artifact after Task 8

CLI/DX
  ├─ command success JSON
  ├─ stable failure JSON
  ├─ missing artifact failure
  └─ no request-time runtime override
```

## Findings And Amendments

| Finding | Severity | Resolution |
|---|---|---|
| Arm-rank derivation could be interpreted too loosely, especially lexical rows without source scores and dense rows filtered by threshold. | P1 | Plan now requires lexical rank from `retrieved_locators` list order, threshold filtering before fusion, dense recorded-rank preservation, duplicate rejection, and selected-threshold consistency tests. |
| Artifact validator tests could hide behind a temporary skip until Task 8. | P2 | Plan now requires a `tmp_path` temporary artifact validator test before Task 8 and switching that path to the checked-in artifact after Task 8. |

No user challenge was raised. The review does not recommend adding reranking, query rewrite,
segmentation, API embeddings, runtime promotion, or UI work to E3-D.

## DX Review

Target developer: project maintainer or reviewer running local evaluation and validating artifacts.

Developer journey:

| Stage | Expected path | Review result |
|---|---|---|
| Discover | Read docs index and E3-D how-to | Plan adds docs links and reproduction guide. |
| Run | `mke eval retrieval-hybrid-rrf ...` | CLI path is explicit and comparison-only. |
| Validate | `python -m mke.evaluation.hybrid_rrf_artifact validate ...` | Validator has a stable success line and non-zero failure. |
| Debug | Inspect stable error problem/cause/next-step | Required by Task 7. |
| Trust | Compare E1/E2/E3-A/E3-B/E3-C semantics before and after | Required by Task 0 and Task 9. |

DX score: `8/10`. The missing 2 points are intentional: E3-D is not a one-command product demo and
does not attempt hosted UI or interactive notebooks. That is acceptable because this is a durable
evaluation artifact, not a user-facing runtime feature.

## Failure Modes Registry

| Failure mode | Covered by plan |
|---|---|
| Fusion accidentally uses raw dense cosine or lexical score | Yes, pure RRF tests and plan boundary. |
| Threshold filtering silently changes dense rank semantics | Yes, amended Task 3 tests. |
| Lexical row cannot be rebound to stable source-text digest | Yes, Task 3 fail-closed tests. |
| Holdout observed before development freeze | Yes, Task 5 state-machine tests. |
| Canonical artifact validates itself without recomputation | Yes, Task 6 validator recomputes from protocol and dense artifact. |
| Historical E1/E2/E3-A/E3-B semantic drift hidden by source refresh | Yes, Task 9 requires normalized semantic equality before refresh. |
| Implementation changes Search, Ask, MCP, or runtime default | Yes, non-negotiable boundaries and final public-boundary scan. |

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---:|---|---|---|---|---|---|
| 1 | CEO | Keep E3-D comparison-only | Mechanical | Explicit over clever | Runtime promotion requires a separate production contract. | Default hybrid Search |
| 2 | CEO | Keep reranker out of E3-D | Mechanical | One variable at a time | Reranking should follow only if bounded union evidence exists but fusion misranks it. | RRF plus reranker |
| 3 | Eng | Preserve dense recorded rank after threshold filtering | Mechanical | Evidence integrity | Thresholding selects eligible rows; it must not renumber dense evidence. | Compressed dense rank |
| 4 | Eng | Derive lexical rank only from list order | Mechanical | Explicit over clever | Current runtime semantics do not expose a calibrated lexical score. | Hidden lexical score inference |
| 5 | Eng | Require temporary artifact validation before checked-in artifact exists | Mechanical | Completeness | Validator behavior can be tested before Task 8 without a skip. | Permanent or broad skip |
| 6 | DX | Add one explicit reproduction how-to | Mechanical | Developer trust | Reviewers need exact commands and interpretation boundaries. | PR body only |

## GSTACK REVIEW REPORT

| Review | Status | Notes |
|---|---|---|
| CEO | `CLEAN` | Scope and sequencing are correct; no expansion accepted. |
| Design | `SKIPPED` | No graphical UI scope. |
| Engineering | `CLEAN` after amendments | Two evidence-boundary findings were resolved in the plan. |
| DX | `CLEAN` | CLI, validator, docs, and public error paths are specified. |
| Outside voice | `N/A` | Host constraints prevented subagent use; no consensus was claimed. |

Final verdict: proceed to implementation from latest `main` in a fresh execution worktree. Use
`high` reasoning depth for normal implementation and review fixes; use `xhigh` only for protocol,
artifact-integrity, holdout-observation, or architecture-amendment stop conditions.
