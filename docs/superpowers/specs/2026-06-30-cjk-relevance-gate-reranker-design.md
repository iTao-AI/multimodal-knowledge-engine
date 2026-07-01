# CJK Relevance Gate Reranker Candidate Design

Status: implemented on local branch `codex/e3e-relevance-gate-reranker`; scheme-window pre-PR
review comes next.

Planning base: `main@0ed1ee1c7763d65b1cd493d002908361df410521`.

Implementation base: `main@03a7583fd7161585bc039832b517cc3be97ddca9`.

## Context

MKE has completed the Chinese retrieval sequence through E3-D:

| Stage | Repository-visible result |
|---|---|
| E3-A | Recorded the Chinese lexical baseline and failure classes. |
| E3-B | Recorded the off-default CJK lexical candidate. |
| E3-F | Promoted `cjk-active-scan-overlap-v1` as the current runtime default. |
| E3-C | Recorded local dense compatibility and the comparison-only Qwen3 exact-cosine dense candidate. |
| E3-D | Recorded rank-only lexical+dense RRF as a development valid negative. |

The current E3-C dense artifact is:

- `benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json`
- SHA-256: `1b802acd3fdd1a99cedab811b3570d224f6c1b538a02a4d69781dc6b0bc5f22e`
- model: `Qwen/Qwen3-Embedding-0.6B`
- revision: `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`
- selected threshold: `0.58`

The current E3-D RRF artifact is:

- `benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json`
- SHA-256: `84b4292b829ca8713bdbc72e46bdf8fe6db7a3fa9e297416f75e35c048abbf7a`
- `development_status=valid_negative`
- `holdout_status=not_observed`
- `e3e_status=eligible`
- `runtime_promotion_status=not_evaluated`

E3-D proved that lexical and dense candidates are complementary, but also showed that rank-only
fusion is unsafe to promote:

| Arm | Recall@5 | nDCG@10 | MRR@5 | Unanswerable no-hit | Hard-negative failure |
|---|---:|---:|---:|---:|---:|
| Fused RRF | `0.772727` | `0.735153` | `0.690909` | `0.000000` | `0.200000` |
| Current lexical runtime | `0.681818` | `0.643390` | `0.636364` | `0.500000` | `0.300000` |
| E3-C dense | `0.545455` | `0.574244` | `0.545455` | `0.500000` | `0.000000` |

The next useful comparison is not another candidate generator. E3-D already shows relevant Evidence
often exists in the bounded union. E3-E should isolate whether a deterministic relevance gate and
reranking layer can reject distractors and unanswerable matches while preserving the useful
lexical+dense recoveries.

External RAG practice notes influenced only the generic evaluation posture: evaluate precision,
hard negatives, refusal/no-hit behavior, and resource boundaries instead of optimizing recall alone.
The source material itself is not a repository artifact and is not copied into public docs.

## Problem

The current runtime is safe but misses semantic matches. The dense arm recovers some semantic cases
but is not a runtime candidate. RRF combines both arms and improves answerable ranking, but it
returns Evidence for every unanswerable development query. That failure is exactly the kind of
retrieval-layer issue a relevance gate should catch before any future Ask or context construction
layer trusts the union.

E3-E must answer one question:

> Can MKE filter and rerank the existing lexical+dense union to restore refusal behavior while
> retaining enough answerable retrieval gain to justify a future runtime or reranker stage?

## Goals

E3-E must:

- define a comparison-only reranker / relevance-gate protocol over the existing E3-D union;
- keep `cjk-active-scan-overlap-v1` as the runtime default;
- keep Search, Ask, MCP, owner startup, Publication, ingestion, and normal CLI runtime unchanged;
- consume the canonical E3-C dense artifact and the E3-D RRF artifact instead of rescoring dense
  vectors for tuning;
- score only from query text, retrieved Evidence text, arm/rank provenance, and frozen source
  inventory;
- forbid qrels, grades, query category labels, split labels, or holdout outcomes as scoring inputs;
- compare a small frozen catalog of gate/rerank profiles on development only;
- freeze exactly one selected development profile before any holdout observation;
- record no-hit, hard-negative, precision-style, recall, nDCG, MRR, dense-only recovery, and
  dropped-relevant diagnostics;
- independently validate artifact identity, feature derivation, gate decisions, rerank ordering,
  metrics, and state transitions.

## Non-Goals

E3-E must not:

- promote a reranker or relevance gate into runtime behavior;
- change `cjk-active-scan-overlap-v1`, `numeric-grouping-v1`, `current`, Search, Ask, MCP, or
  owner-startup configuration;
- introduce an API embedding or rerank adapter;
- add an LLM judge, LLM query rewrite, HyDE, synonym expansion, or entity expansion;
- add a local cross-encoder or reranker model;
- change the E3-C dense model, revision, prompt, threshold, cache lifecycle, or resource contract;
- change E3-D RRF inputs, `k`, arm weights, or tie-breakers;
- implement Passage/chunk segmentation, OCR, table parsing, HTTP, UI, Milvus, Redis, pgvector, or
  LangChain/LlamaIndex/LangGraph runtime contracts;
- claim statistical significance or production quality from the current small public corpus.

## Approaches Considered

| Approach | Decision | Reason |
|---|---|---|
| Deterministic relevance gate and rerank over the existing E3-D union | Selected | It isolates the failure revealed by E3-D, uses existing repository-visible evidence, and avoids adding a second model or provider before knowing whether simple constraints solve the safety gap. |
| Local cross-encoder reranker | Deferred | It would be a real reranker, but it needs a separate model lifecycle, resource proof, scoring determinism contract, and cache authorization. That is a later candidate if E3-E shows deterministic gating is insufficient. |
| API reranker or LLM judge | Rejected for E3-E | It would introduce network, provider, cost, credential, and non-determinism boundaries into a local-first comparison. It may be evaluated later as an adapter, not as the canonical first reranker protocol. |
| Query rewrite before reranking | Deferred | E3-D shows the union already contains useful relevant Evidence. Query rewrite would change candidate generation and confound the relevance-gate question. |
| Passage/segmentation before reranking | Deferred | E3-D marks segmentation eligible, but E3-E should first test whether current page-level candidates can be filtered safely. |

## Selected Candidate

Candidate identifier: `cjk-relevance-gate-reranker-v1`

Candidate revision: `1`

Candidate type: deterministic relevance gate plus scorecard reranker over a frozen lexical+dense
union.

Frozen inputs:

| Input | Source |
|---|---|
| Chinese protocol and qrels | `tests/fixtures/retrieval-chinese-v1/protocol.json` and related frozen inventory |
| Current lexical runtime observations | E3-D lexical arm observations rebound through source inventory |
| Dense observations | `benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json` |
| RRF union and diagnostics | `benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json` |

The candidate creates a per-query bounded candidate set from the E3-D union, derives relevance
features for each row, applies a frozen gate profile, and reranks eligible rows by a deterministic
scorecard. It returns an empty list when every row is gated out.

## Feature Contract

Each candidate row records:

- query ID;
- candidate profile ID and revision;
- stable locator ID;
- document ID;
- locator kind, start, and end;
- source-text digest;
- arm contribution set: lexical, dense, or both;
- lexical rank, dense rank, and RRF rank when present;
- derived query constraints;
- derived Evidence constraints;
- gate decision: `allowed` or `rejected`;
- gate reason code for rejected rows;
- rerank score and tie-break evidence for allowed rows.

Allowed feature families:

| Feature family | Purpose |
|---|---|
| Arm provenance | Preserve whether a row came from lexical, dense, or both arms. |
| Rank provenance | Use lexical rank, dense rank, and RRF rank as already-validated rank signals. |
| Query-term coverage | Check normalized CJK, ASCII, and mixed-token overlap between query and Evidence text. |
| Numeric/date/unit constraints | Reject rows that drop or contradict explicit numeric/date/unit terms. |
| Proper-noun/mixed-token constraints | Preserve ASCII product names, IDs, law names, and mixed CJK/ASCII terms when present. |
| Evidence identity | Keep stable locator and source-text digest as validator-owned invariants. |

Forbidden scoring inputs:

- qrel grades;
- expected locators;
- query category labels;
- development/holdout split labels;
- Ask outcome labels;
- artifact metric values;
- manual allowlists keyed by query ID;
- private notes or external hand-labeled examples not committed as public qrels.

## Gate And Rerank Profiles

The implementation must freeze a small catalog before development scoring. The initial catalog is:

| Profile | Intent |
|---|---|
| `lexical-floor` | Preserve high-confidence lexical rows and admit dense rows only when they satisfy explicit query constraints. |
| `balanced-constraint` | Allow dense-only semantic recoveries when no required numeric/date/proper-noun constraint is missing. |
| `strict-constraint` | Prefer refusal safety; reject dense-only or weak-overlap rows unless both semantic and constraint features agree. |

Profile selection happens only on development. The selection objective is:

1. pass the refusal and hard-negative gates;
2. maximize Recall@5;
3. maximize nDCG@10;
4. preserve at least one dense-only or union-only recovery when possible;
5. choose the stricter profile on exact metric ties.

If no profile passes development gates, record a valid negative and do not observe holdout.

## Metrics And Diagnostics

E3-E records the existing graded retrieval metrics:

- Recall@1 / Recall@3 / Recall@5;
- MRR@5;
- nDCG@5 / nDCG@10;
- answerable zero-hit;
- unanswerable no-hit;
- hard-negative failure;
- Ask evidence-found / insufficient-evidence / input-rejection rates where available.

E3-E also records relevance-gate diagnostics:

| Diagnostic | Meaning |
|---|---|
| `input_union_count` | Count of E3-D union rows before gating. |
| `allowed_count` | Count of rows that survived the relevance gate. |
| `rejected_count_by_reason` | Rejection counts grouped by stable reason code. |
| `dropped_grade2_count` | Queries where a grade-2 row existed in the union but all grade-2 rows were gated out. |
| `recovered_from_rrf_false_positive_count` | Previously false-positive RRF rows removed while preserving answerable hits. |
| `dense_only_recovery_retained_count` | Dense-only answerable recoveries that survive the gate. |
| `lexical_only_recovery_retained_count` | Lexical-only answerable recoveries that survive the gate. |
| `empty_result_no_hit_count` | Queries where the gate intentionally returns no Evidence. |
| `per_category_delta` | Category-level diagnostics for interpretation only, not scoring. |

## Development And Holdout Gates

Development gates:

- model-free E1, E2, E3-A, E3-B, E3-C, and E3-D validators pass before scoring;
- current runtime semantic observations match the Task 0 snapshot;
- E3-D input union is rebound without semantic drift;
- candidate scoring never reads qrels, category labels, split labels, or expected locators;
- selected profile is frozen with exclusive-create semantics before holdout;
- unanswerable no-hit is at least the current lexical runtime value: `>=0.500000`;
- hard-negative failure is no worse than E3-D RRF: `<=0.200000`;
- Recall@5 is not lower than current lexical runtime: `>=0.681818`;
- nDCG@10 is not lower than current lexical runtime: `>=0.643390`;
- MRR@5 is not lower than current lexical runtime: `>=0.636364`;
- at least one dense-only or union-only answerable recovery is retained, or the artifact records a
  valid negative explaining why all such recoveries were unsafe;
- diagnostics are complete for every query.

Holdout gates:

- holdout may run only when development status is `passed`;
- holdout uses the frozen development profile without retuning;
- holdout records a receipt before writing the comparison artifact;
- holdout metrics must not regress refusal or hard-negative behavior against the current lexical
  runtime holdout observation;
- holdout must not claim runtime promotion; it may only set follow-up status fields.

## Artifact State

Expected implementation artifacts:

- `tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json`
- `benchmarks/retrieval/cjk-relevance-gate-reranker-v1-development-freeze.json`
- `benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json`
- `benchmarks/retrieval/cjk-relevance-gate-reranker-v1-holdout-receipt.json`

The comparison artifact state fields are:

| Field | Values |
|---|---|
| `candidate_status` | `not_evaluated`, `completed`, or `failed` |
| `development_status` | `passed`, `valid_negative`, or `failed` |
| `holdout_status` | `not_observed` or `observed` |
| `e3f_runtime_status` | always `not_evaluated` in E3-E |
| `reranker_model_status` | `not_evaluated`, `eligible`, or `not_eligible` |
| `query_rewrite_status` | `not_evaluated`, `eligible`, or `not_eligible` |
| `segmentation_status` | `not_evaluated`, `eligible`, or `not_eligible` |
| `runtime_promotion_status` | always `not_evaluated` in E3-E |

`runtime_promotion_status` is deliberately frozen. E3-E can only decide whether a later candidate is
worth planning.

## Stop Conditions

Stop for planning review if:

- scoring code needs qrels, category labels, split labels, or expected locators;
- no model-free way exists to rederive gate decisions from artifact inputs;
- source identity refresh would change E1/E2/E3-A/E3-B/E3-C/E3-D metrics or verdicts;
- development fails due to a gate that was not frozen in this design;
- the candidate needs a local reranker model, API provider, query rewrite, segmentation, or runtime
  Search/Ask/MCP change to pass;
- holdout has been observed accidentally before development freeze.

## Expected Outcome

The most likely useful outcome is either:

1. E3-E passes development by restoring refusal while retaining at least part of E3-D's answerable
   gain, making a future runtime-candidate plan credible; or
2. E3-E records a valid negative, proving that deterministic gating is insufficient and that the
   next useful stage should be either a real reranker model, better Passage/segmentation, or query
   understanding.

Both outcomes are useful. A valid negative is acceptable if it is artifact-bound, reproducible, and
does not alter runtime behavior.
