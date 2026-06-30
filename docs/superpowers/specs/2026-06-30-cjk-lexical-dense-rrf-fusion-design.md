# CJK Lexical Dense RRF Fusion Candidate Design

Status: implemented and merged by PR #46. E3-D recorded a development valid negative;
holdout was not observed and `runtime_promotion_status=not_evaluated` remains frozen.

Post-merge closeout: PR #46 was squash merged to `main@158d0614fec2ef49da9db5882c589a832c48331f`;
post-merge CI and CodeQL checks passed.

## Context

The planning baseline is `main@0fe1d5640f914e8307ec938e36ba145419c64872`.

MKE has completed the Chinese retrieval evaluation sequence through E3-C:

| Stage | Result |
|---|---|
| E3-A | Recorded the Chinese lexical baseline and failure classes. |
| E3-B | Recorded the comparison-only CJK trigram lexical candidate. |
| E3-F | Promoted `cjk-active-scan-overlap-v1` as the current runtime default without adding a persistent CJK projection. |
| E3-C PR 1 | Proved the local Qwen3 embedding prerequisite, model lifecycle, cache-only readiness, resource gates, and exact-cosine projection boundary. |
| E3-C PR 2 | Recorded the comparison-only dense candidate and set `e3d_status=eligible`. |

The E3-C implementation plan, review, how-to guide, and artifact are the current sources of truth
for E3-C completion. The older E3-C design file still contains a stale status line saying PR 2 had
not started; this E3-D design follows the repository-visible artifacts and completed plan/review
records instead.

Repository-visible E3-C evidence:

- Dense candidate: `qwen3-embedding-0.6b-exact-v1`.
- Model: `Qwen/Qwen3-Embedding-0.6B`.
- Revision: `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`.
- Comparison artifact:
  `benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json`.
- Artifact SHA-256:
  `25a46056052b36034492f481370c645c6c499185569da756769bbe378848d298`.
- Dense result: `candidate_status=completed`, `e3d_status=eligible`,
  `runtime_promotion_status=not_evaluated`, `selected_threshold=0.58`.

The relevant current results are:

| Arm | Split | Recall@5 | nDCG@10 | MRR@5 | Unanswerable no-hit | Hard-negative failure |
|---|---|---:|---:|---:|---:|---:|
| `cjk-active-scan-overlap-v1` | combined E3-F observation | `0.659091` | `0.619152` | not recorded in the E3-F summary | `0.500000` | `0.235294` |
| `qwen3-embedding-0.6b-exact-v1` | development | `0.545455` | `0.574244` | `0.545455` | `0.500000` | `0.000000` |
| `qwen3-embedding-0.6b-exact-v1` | holdout | `0.772727` | `0.751694` | `0.727273` | `0.500000` | `0.000000` |

The dense arm recovered target grade-2 misses that lexical runtime missed, especially in
`semantic_paraphrase`, `multi_condition`, and `ranking_hard_negative`. E3-D is justified because
the two arms now have observed complementarity; it is not justified as runtime promotion.

## Problem

The project has proven a strong lexical runtime and one local dense candidate separately. It has
not proven whether a hybrid result can preserve lexical precision, dense semantic recovery, refusal
behavior, hard-negative safety, and deterministic Evidence identity at the same time.

The tempting next step is to add reranking or query rewriting, but that would change multiple
variables before the project knows whether the missing value is candidate generation or final
ranking. E3-D therefore isolates one variable: rank-only fusion of the already validated lexical
and dense ranked lists.

## Goals

E3-D must:

- record a comparison-only lexical+dense RRF candidate;
- consume the current runtime lexical observations and the canonical E3-C dense observations;
- use rank-only fusion, not raw FTS rank, BM25-like score, or cosine score arithmetic;
- bind every fused result to stable Evidence identity and source-text digest;
- prove that dedupe, rank contribution, and tie-breaking are deterministic;
- measure quality, refusal, hard-negative behavior, union coverage, ranking headroom, and per-arm
  contribution;
- decide whether a future reranker candidate is justified;
- decide whether remaining failures point instead to Passage/segmentation or query understanding;
- keep normal Search, Ask, CLI runtime, MCP, Publication, and runtime default behavior unchanged.

## Non-Goals

E3-D must not:

- promote hybrid retrieval into runtime behavior;
- add an API embedding adapter;
- change the dense model, prompt, threshold, revision, projection, or cache lifecycle;
- change `cjk-active-scan-overlap-v1`;
- implement reranking;
- implement query rewrite, HyDE, synonym expansion, or entity expansion;
- implement Passage/chunk segmentation;
- add HTTP, workspace UI, or hosted service behavior;
- reuse legacy RAG-OCR service code;
- add Milvus, Redis, pgvector, or another external vector service;
- claim statistical significance or production quality from the current small public corpus.

## Approaches Considered

| Approach | Decision | Reason |
|---|---|---|
| Rank-only RRF over current runtime lexical top-N and dense top-N | Selected | It isolates fusion, avoids incomparable raw score spaces, and directly tests whether the two proven arms are complementary. |
| RRF plus reranker in one stage | Rejected | It would confound candidate generation and ranking quality. A reranker belongs after E3-D shows relevant Evidence is already present in the bounded union. |
| Change Passage/segmentation before fusion | Deferred | Segmentation is likely important, but E3-C already provides dense complementarity at page-Evidence granularity. E3-D should first measure union coverage and ranking headroom. |
| Weighted sum of FTS and dense scores | Rejected | FTS rank and cosine similarity are not calibrated to the same score space. A weighted sum would require a separate calibration experiment. |
| Use only dense because holdout was stronger | Rejected | Dense does not prove runtime suitability or lexical precision replacement; the shipped strategy remains active-scan lexical. E3-D must compare fusion against both single arms. |

## Selected Candidate

Candidate identifier: `cjk-active-scan-qwen3-rrf-v1`

Candidate revision: `1`

Frozen arms:

| Arm role | Arm ID | Source |
|---|---|---|
| Lexical runtime | `cjk-active-scan-overlap-v1` | Current runtime observations from the E3-C artifact, rebound through the frozen Chinese protocol inventory. |
| Dense candidate | `qwen3-embedding-0.6b-exact-v1` | Dense observations from the E3-C comparison artifact after the selected threshold `0.58`. |

Fusion contract:

| Field | Frozen value |
|---|---|
| Fusion method | Reciprocal Rank Fusion |
| Formula | `sum(weight_arm / (k + rank_arm))` |
| Rank base | `1` |
| `k` | `60` |
| Arm weights | equal, `1.0` each |
| Lexical input depth | `10` results per query, or fewer when the lexical arm returned fewer |
| Dense input depth | `10` thresholded dense results per query, or fewer when the dense arm returned fewer |
| Output depth | `10` results per query |
| Dedupe key | stable locator plus source-text digest |
| Tie-break order | fused score descending, arm-hit count descending, best individual rank ascending, lexical rank ascending, dense rank ascending, stable locator ID ascending |
| Score precision | portable decimal representation owned by the artifact validator |

The candidate does not use raw lexical scores, dense raw cosine scores, or document-level average
vectors. Arm-specific scores may be recorded for diagnostics, but they cannot influence the fused
order except through each arm's rank.

## Architecture

```text
frozen Chinese protocol + qrels + source inventory
                  |
                  v
canonical E3-C dense comparison artifact
                  |
       +----------+-----------+
       |                      |
       v                      v
current runtime lexical   dense candidate
ranked observations       ranked observations
       |                      |
       +----------+-----------+
                  v
       stable Evidence identity binding
                  |
                  v
       rank-only RRF fusion
                  |
                  v
metrics + diagnostics + canonical artifact
```

E3-D runs in evaluation code only. It does not build a new production projection and does not call
normal runtime Search differently. If the implementation needs fresh current-runtime observations
to guard against drift, those observations must be compared against Task 0 snapshots and the E3-C
semantic digest before holdout is recomputed.

## Evidence Identity And Dedupe

Every fused row must bind:

- query ID and split;
- arm contribution set: lexical, dense, or both;
- stable document ID;
- locator kind, start, and end;
- source-text digest;
- dense stable locator ID when available;
- lexical locator rebound through the frozen protocol inventory;
- per-arm rank when present;
- fused rank and fused portable score.

The validator must reject:

- duplicate fused locators for one query;
- lexical locators that cannot be rebound to exactly one frozen source-text digest;
- dense locators whose stable locator ID conflicts with the locator inventory;
- fused rows whose arm contribution, rank, score, or tie-break order cannot be recomputed from the
  frozen arm observations;
- artifact and observed-report coordinated tampering;
- any Evidence outside active-Publication snapshots.

## Metrics And Diagnostics

E3-D records the existing graded metrics:

- Recall@1 / Recall@3 / Recall@5;
- MRR@5;
- nDCG@5 / nDCG@10;
- answerable zero-hit;
- unanswerable no-hit;
- hard-negative failure;
- Ask evidence-found / insufficient-evidence / input-rejection rates where applicable.

E3-D also records fusion-specific diagnostics:

| Diagnostic | Meaning |
|---|---|
| `union_grade2_coverage_at_10` | Whether either arm returned a grade-2 locator in its top-10 input list. |
| `fused_lost_union_grade2_count` | Queries where union contained grade-2 Evidence but fused top-5 did not. |
| `ranking_headroom_count` | Queries where a reranker could help because relevant Evidence exists in the union but is not ranked high enough. |
| `lexical_only_recovery_count` | Queries recovered only by the lexical arm. |
| `dense_only_recovery_count` | Queries recovered only by the dense arm. |
| `both_arm_recovery_count` | Queries where both arms recovered grade-2 Evidence. |
| `neither_arm_miss_count` | Queries where neither arm recovered grade-2 Evidence in top-10. |
| `per_category_delta` | Quality and safety changes by frozen query category. |

These diagnostics are not marketing metrics. They are used to choose the next engineering branch:
reranker, Passage/segmentation, query understanding, or no follow-up.

## Protocol And Artifact State

Expected new files:

- `tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json`
- `benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-development-freeze.json`
- `benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json`
- `benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-holdout-receipt.json`

The protocol lock must bind:

- the frozen Chinese retrieval protocol and qrels;
- the E3-C dense comparison artifact;
- the current runtime strategy descriptor;
- source files that define fusion, metrics, artifact validation, and CLI behavior;
- the exact RRF candidate ID, revision, `k`, weights, input depth, output depth, and tie-breakers.

Artifact state must include:

- `candidate_status`: `not_evaluated`, `completed`, or `failed`;
- `development_status`: `passed`, `valid_negative`, or `failed`;
- `holdout_status`: `not_observed` or `observed`;
- `e3e_status`: `eligible`, `not_eligible`, or `not_evaluated`;
- `segmentation_status`: `eligible`, `not_eligible`, or `not_evaluated`;
- `runtime_promotion_status`: always `not_evaluated` in E3-D.

## Development And Holdout Gates

Development gates:

- model-free validation of E1, E2, E3-A, E3-B, and E3-C passes before scoring;
- current runtime semantic observations match the frozen Task 0 snapshot;
- dense artifact validation passes;
- cache-ready dense replay remains optional corroboration, not a fusion scoring input or an E3-D
  acceptance gate;
- fused Recall@5 is not lower than both input arms on development;
- fused nDCG@10 is not lower than both input arms on development;
- fused candidate has at least one strict development improvement over the best single arm in
  Recall@5, nDCG@10, MRR@5, or target miss recovery;
- unanswerable no-hit is not lower than the current runtime baseline;
- hard-negative failure is not higher than the current runtime baseline;
- diagnostics are complete for every query.

If development does not pass, E3-D records a valid negative result and does not observe holdout.

Holdout gates:

- holdout is observed exactly once after the development freeze exists;
- the holdout receipt is created with exclusive-create semantics;
- fused Recall@5 is not lower than both input arms on holdout;
- fused nDCG@10 is not lower than both input arms on holdout;
- unanswerable no-hit is not lower than the current runtime baseline;
- hard-negative failure is not higher than the current runtime baseline;
- diagnostics are complete for every query.

Passing E3-D does not approve runtime promotion. It only records whether fusion is a credible
candidate and which follow-up branch is justified.

## Follow-Up Decision Rules

After E3-D:

| Observation | Follow-up |
|---|---|
| Union contains relevant Evidence, but fused top-5 misses it | Plan E3-E reranker candidate. |
| Neither lexical nor dense top-10 contains relevant Evidence | Plan Passage/segmentation before reranking. |
| Dense recovers semantic classes but fusion loses lexical precision | Investigate fusion depth, tie-break, or safety filter before reranking. |
| Fusion improves both quality and safety without ranking headroom | Keep runtime promotion as a separate later plan; do not fold it into E3-D. |
| Fusion does not beat the best single arm | Record a valid negative; do not add reranker just to rescue an unproven fusion protocol. |

## CLI Shape

The implementation plan should preserve the existing `mke eval` style. A likely command shape is:

```bash
uv run mke eval retrieval-hybrid-rrf \
  --protocol tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json \
  --candidate cjk-active-scan-qwen3-rrf-v1 \
  --dense-artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --development-only \
  --record-development-freeze benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-development-freeze.json \
  --json
```

Holdout:

```bash
uv run mke eval retrieval-hybrid-rrf \
  --protocol tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json \
  --candidate cjk-active-scan-qwen3-rrf-v1 \
  --dense-artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --development-freeze benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-development-freeze.json \
  --record benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json \
  --record-holdout-receipt benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-holdout-receipt.json \
  --json
```

The E3-D evaluator itself should be model-free. Cache-ready dense replay remains optional
corroboration when the embedding extra and an already-populated local model cache are available,
not a second dense scoring source or an E3-D acceptance gate:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 UV_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
uv run python -m mke.evaluation.dense_replay validate \
  --artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --protocol tests/fixtures/retrieval-dense-v1/protocol-lock.json \
  --model-cache <model-cache> \
  --repository .
```

## Error Handling

Public CLI errors must use stable, redacted `problem`, `cause`, and `next_step` values. They must
not expose absolute paths, tracebacks, model-cache locations, environment variables, provider
endpoints, tokens, or raw exception text.

Required stable failures include:

| `problem` | `next_step` |
|---|---|
| `rrf_protocol_invalid` | `restore_rrf_protocol_inputs` |
| `rrf_dense_artifact_invalid` | `restore_dense_comparison_artifact` |
| `rrf_development_freeze_missing` | `run_rrf_development_phase` |
| `rrf_holdout_already_observed` | `create_new_candidate_revision` |
| `rrf_identity_mismatch` | `refresh_only_after_semantic_equality` |
| `rrf_artifact_invalid` | `rerun_rrf_evaluation_or_restore_artifact` |

## Documentation Impact

If implemented, E3-D must update:

- `docs/how-to/evaluate-dense-retrieval.md` or a new hybrid/RRF how-to;
- `docs/explanation/architecture.md`;
- `docs/README.md`;
- the E3-D implementation plan and durable review.

No ADR is required for comparison-only E3-D. A future runtime promotion, request-surface change,
new projection lifecycle, API adapter, or reranker port would require its own ADR or explicit
design amendment.

## Risks

- The corpus is still small, public, Chinese-only, and non-blind.
- Page-level Evidence may hide segmentation failures.
- Reusing already observed holdout limits statistical confidence; the guardrail is to freeze the
  candidate before running E3-D and not tune after the E3-D holdout receipt.
- Dense replay requires an external model cache that is intentionally outside the repository.
- A positive RRF result can still be unsuitable for runtime if installed-wheel, cache-ready,
  readiness, or rollback proof is not later added in a separate promotion plan.

## Spec Self-Review Acceptance

The spec is ready for implementation-plan writing when:

- the spec is committed on a planning branch;
- self-review finds no placeholders, contradictions, private paths, or scope ambiguity;
- the future implementation plan is explicitly required to define TDD tasks, artifact validators,
  verification, and stop conditions;
- the future `gstack-autoplan` or equivalent durable plan review is explicitly required before
  execution handoff.
