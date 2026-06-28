# Local Dense Retrieval Candidate Design

Status: approved E3-C design, including the 2026-06-28 autoplan amendments; implementation has
not started.
Implementation has not started. This document defines an off-default, comparison-only local dense
retrieval candidate and does not approve runtime promotion.

## Context

The planning baseline is `main@5ed0a722b83f9b4c70aec7c9333d8bf7d17b9335`.

E3-A established the frozen Chinese retrieval protocol and current FTS5 failure modes. E3-B then
recorded the comparison-only `cjk-trigram-overlap-v1` candidate. E3-F subsequently promoted the
smaller `cjk-active-scan-overlap-v1` strategy to runtime default without adding a persistent CJK
projection.

The relevant repository-visible results are:

| Observation | Recall@5 | nDCG@10 | Unanswerable no-hit | Hard-negative failure |
|---|---:|---:|---:|---:|
| E3-A historical FTS5 baseline | `0.295455` | `0.277279` | `0.500000` | `0.235294` |
| E3-B frozen trigram candidate | `0.659091` | `0.610619` | `0.500000` | `0.235294` |
| E3-F current runtime default | `0.659091` | `0.619152` | `0.500000` | `0.235294` |

The E3-B comparison still has grade-`2` misses in `semantic_paraphrase`, `multi_condition`, and
`ranking_hard_negative`. Dense retrieval is justified only if it retrieves Evidence that the
shipped lexical strategy misses without weakening refusal or hard-negative behavior.

## Problem

The current runtime improves Chinese lexical coverage, but lexical overlap cannot reliably recover
all semantic paraphrases or multi-condition formulations. The repository does not yet show whether
a local dense model adds complementary Evidence recall, whether that gain survives holdout, or
whether the resource and refusal costs are acceptable.

Testing dense retrieval with an API-only model would combine retrieval quality with provider
network, alias, preprocessing, credential, and availability behavior. Testing an unfrozen local
model would make the result equally hard to reproduce. E3-C therefore needs one immutable local
reference path before any API integration or fusion work.

E3-C is a bounded research and engineering track, not a claim that retrieval optimization is the
only remaining product priority. Its decision utility is narrow: a positive result permits an E3-D
fusion experiment; a negative result rejects this exact model, prompt, page-Evidence, and
projection candidate for E3-D. It does not prove that all dense retrieval models are unsuitable.

## Goals

E3-C must:

- freeze one current Chinese-capable embedding model and runtime before qrel scoring;
- preserve the E3-A protocol, qrels, fixtures, and the E3-B comparison artifact;
- compare the historical baseline, frozen E3-B candidate, current runtime lexical strategy, and
  one dense candidate;
- use a project-owned embedding port and vector-projection port;
- perform cache-only local inference and exact cosine KNN;
- select a refusal threshold from development only, then observe holdout once;
- record quality, complementarity, latency, memory, model size, and projection size;
- decide whether an E3-D RRF experiment is justified without claiming that RRF is effective;
- preserve the current Search, Ask, CLI runtime, and MCP behavior.

## Approaches Considered

### Model Audit

The model audit was performed against official model cards and repository metadata on
`2026-06-28`.

| Model | Decision | Relevant evidence | Reason |
|---|---|---|---|
| [`Qwen/Qwen3-Embedding-0.6B`](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) | Selected | Apache-2.0, 0.6B parameters, 1024 dimensions, 32K context, instruction-aware, official SentenceTransformers usage | Current dense-only model with strong Chinese and multilingual retrieval evidence, no gated download, and no required remote code. |
| [`BAAI/bge-m3`](https://huggingface.co/BAAI/bge-m3) | Rejected as canonical E3-C model | MIT, 0.6B-class, 1024 dimensions, 8192 context, dense/sparse/multi-vector output | Good model, but its additional modes are outside E3-C and its official Python snapshot is materially larger. Selecting it would not simplify the canonical in-process path. |
| [`BAAI/bge-base-zh-v1.5`](https://huggingface.co/BAAI/bge-base-zh-v1.5) | Rejected as primary | MIT, Chinese-focused, 768 dimensions | Stable resource fallback candidate, but an older model family with weaker current retrieval evidence. It may be reconsidered only through a plan amendment if Qwen3 fails compatibility gates. |
| [`Alibaba-NLP/gte-multilingual-base`](https://huggingface.co/Alibaba-NLP/gte-multilingual-base) | Rejected | Apache-2.0, multilingual, 768 dimensions | Official usage requires `trust_remote_code=True`, which expands the model supply-chain boundary. |
| [`google/embeddinggemma-300m`](https://huggingface.co/google/embeddinggemma-300m) | Rejected | 300M parameters, multilingual, on-device focus | The model download is gated and requires acceptance of separate usage terms, weakening unattended reproducibility. |
| Hosted embedding API | Deferred | Strong production integration option | Provider drift, credentials, network availability, hidden preprocessing, and content-upload trust prevent it from serving as the canonical artifact source. |

### Projection Audit

The preferred vector adapter remains [`sqlite-vec`](https://github.com/asg017/sqlite-vec), pinned
to `0.1.9`, because it stays within SQLite, supports cosine KNN, and has Python wheels for required
development and CI platforms. It is still pre-v1 and therefore must pass a compatibility proof
before candidate scoring.

If `sqlite-vec` fails the frozen compatibility gates, E3-C may use a project-owned exact-cosine
reference adapter over validated float32 vectors. It must record the `sqlite-vec` rejection and
must not substitute an external vector service.

## Selected Candidate

Candidate identifier: `qwen3-embedding-0.6b-exact-v1`

Candidate revision: `1`

Model identity:

| Field | Frozen value |
|---|---|
| Model | `Qwen/Qwen3-Embedding-0.6B` |
| Model revision | `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3` |
| Embedding dimension | `1024` |
| Model execution | local CPU |
| Inference dtype | float32 |
| Output dtype | float32 |
| Runtime | `sentence-transformers==5.6.0` plus the locked dependency graph |
| Remote code | prohibited |
| Network during evaluation | prohibited |

The exact model revision is allowlisted. Model aliases such as `main`, arbitrary repository names,
and request-provided revisions are invalid.

## Architecture

```text
frozen E3-A protocol + Evidence snapshot
                  |
                  v
        DenseComparisonRunner
          |              |
          |              +--> current lexical observations
          |                   (E3-A / E3-B / E3-F)
          v
   EmbeddingProvider port
          |
          v
SentenceTransformers adapter
          |
          v
 normalized float32 vectors
          |
          v
   VectorProjection port
          |
          +--> sqlite-vec exact-KNN adapter
          `--> project exact-cosine fallback, only if compatibility fails
          |
          v
      RankedEvidence
          |
          v
comparison report + canonical artifact
```

### Project-Owned Contracts

The implementation must use project-owned values equivalent to:

- `EmbeddingModelSpec`: immutable model, revision, instruction, dimension, length, dtype, and cache
  contract;
- `EmbeddingProvider`: embeds validated document batches and one validated query without exposing
  tokenizer, cache, SDK, or transport details;
- `EmbeddingBatch`: Evidence identities plus fixed-dimension vectors and model fingerprint;
- `VectorProjection`: builds, validates, searches, and reports projection identity;
- `RankedEvidence`: stable Evidence identity, rank, portable score, and candidate provenance.

These names are design roles. The implementation plan must first align them with existing DTO and
port conventions. SentenceTransformers, torch, and sqlite-vec objects must not cross the adapter
boundary.

Local-only concerns use a separate adapter capability: token lengths, padding, cache lifecycle,
dtype selection, and batch size are SentenceTransformers runtime behavior, not part of the
provider-neutral `EmbeddingProvider` contract.

Cross-workspace identity uses `document_id + locator_kind + locator_start + locator_end` plus the
source-text digest. Runtime `evidence_id`, `publication_id`, and `source_id` remain snapshot
integrity fields only because normal ingest assigns non-durable UUID identities.

### Extensibility Boundary

Future BGE, EmbeddingGemma, or owner-configured API providers may implement the same
`EmbeddingProvider` contract. Future exact or approximate vector adapters may implement the same
`VectorProjection` contract after separate evidence and architecture review. Neither extension may
change Evidence identity or Publication filtering.

E3-D consumes independently ordered lexical and dense `RankedEvidence` lists. It does not receive
provider SDK objects or combine raw lexical and cosine scores. E3-E receives a bounded Evidence set
through a separate project-owned reranker port.

## Model Lifecycle

The operator-facing lifecycle is:

```text
mke embedding prepare --allow-model-download ...
mke embedding doctor ...
mke eval retrieval-dense ...
```

Requirements:

- after package installation, `prepare` is the only `mke` command that may download model files;
- the exact model and revision are allowlisted before any network request;
- the cache is operator-controlled and outside the repository;
- `doctor`, evaluation, artifact validation, installed-wheel proof, Search, Ask, and MCP are
  cache-only;
- model readiness requires a complete snapshot and an immutable file manifest;
- model file size and SHA-256 identity are recorded without exposing absolute cache paths;
- no command silently substitutes a different model, provider, revision, dimension, or dtype;
- Search/Ask/MCP requests cannot provide model, revision, cache path, URL, or credential values.

Installing the optional Python dependency extra may require a package index unless the operator
uses a pre-populated wheelhouse. The documentation must distinguish package installation network
from model acquisition network. The canonical cache resolves outside the repository, may use a
documented OS cache default or owner environment override, and is never deleted automatically.

An API adapter remains a later integration path. It must use owner configuration fixed before
engine construction and must handle authentication, timeout, rate limits, batch completeness, and
redacted errors. It cannot replace the local canonical artifact.

## Encoding Contract

The canonical query instruction is:

```text
Given a Chinese user query, retrieve relevant evidence passages that answer the query
```

The exact query template is:

```text
Instruct: Given a Chinese user query, retrieve relevant evidence passages that answer the query
Query:{query}
```

There is no space after `Query:` beyond whitespace already present in the validated query. Documents
receive no instruction.

Frozen settings:

| Setting | Value |
|---|---|
| Query prompt | project-owned exact instruction above |
| Document prompt | none |
| `max_length` | `8192` tokens |
| Padding side | left |
| Embedding dimension | `1024` |
| Normalization | L2 |
| Batch ordering | stable locator ID order |
| Query batch size | `1` |
| Document batch size | `4` |

Task 0.5 tokenizes every frozen Evidence before candidate scoring. If any Evidence would be
truncated at `8192`, implementation stops for a plan amendment. Truncation is never accepted as an
unreported preprocessing choice.

Every output batch must have the expected count, unique Evidence identities, dimension `1024`,
finite float32 values, and `abs(norm - 1.0) <= 1e-5`. Invalid batches fail closed.

## Vector Projection Contract

The E3-C projection is temporary and evaluation-only. It does not modify the runtime database or
the shipped `active_evidence_fts` projection.

Each vector row binds:

- stable locator ID and current-snapshot runtime Evidence ID;
- document and Publication identity;
- locator kind/start/end;
- frozen source-text digest;
- model fingerprint;
- 1024-dimensional normalized float32 vector.

The projection is valid only when its row inventory and aggregate source digest equal the frozen
Evidence snapshot. Inserts, validation, and activation of the temporary projection are atomic.
Partial batches and partial projections are discarded.

Search uses cosine exact-KNN with `top_k=10`. The portable score is the raw cosine similarity
rounded to six decimal places. Canonical ordering is:

1. portable cosine score descending;
2. stable locator ID ascending.

The implementation must prove that the selected adapter returns the same Evidence ordering as an
independent project-owned exact-cosine reference on the frozen probe vectors.

## Comparison Protocol

E3-C reports four arms without changing any runtime setting:

1. E3-A historical FTS5 baseline;
2. E3-B frozen `cjk-trigram-overlap-v1` comparison;
3. current runtime `cjk-active-scan-overlap-v1` lexical results;
4. `qwen3-embedding-0.6b-exact-v1` dense results.

The current runtime strategy is the lexical arm eligible for a future E3-D fusion candidate. The
E3-B artifact remains a frozen integrity and historical comparison input.

### Threshold Selection

Dense KNN always returns neighbors, so E3-C must freeze an abstention threshold before holdout.

Development evaluates the predeclared cosine threshold grid from `0.00` through `1.00`, inclusive,
in steps of `0.01`.

Threshold selection:

1. reject thresholds whose development unanswerable no-hit is below `0.500000`;
2. reject thresholds whose development hard-negative failure rate exceeds `0.300000`;
3. maximize recovered grade-`2` Evidence missed by the current runtime in the target failure
   classes;
4. break ties using dense nDCG@10 descending;
5. break remaining ties using the higher threshold.

The selected threshold, every equally optimal contiguous threshold interval, the full selection
trace, rejected-threshold reasons, and development leave-one-query-out sensitivity are recorded.
The sensitivity report does not change the frozen selection algorithm. Holdout runs once after
this value and every candidate setting are frozen.

### Complementarity Classes

The E3-D eligibility classes are:

- `semantic_paraphrase`;
- `multi_condition`;
- `ranking_hard_negative`.

`number_date_unit` results are reported but cannot independently make E3-D eligible because dense
similarity may retrieve a semantically related passage while discarding numeric constraints.
Exact lexical, word-boundary, and proper-noun behavior remain regression evidence rather than the
reason to add dense retrieval.

## Gates

### Compatibility And Integrity Gates

Before qrel scoring:

- the exact Qwen3 model snapshot is complete and cache-only load succeeds;
- `sentence-transformers`, transformers, torch, and model identity are recorded from the installed
  environment;
- Python 3.12 and Python 3.13 installed-wheel model smoke proofs pass;
- the model runs on CPU without `trust_remote_code`;
- all frozen Evidence fits the `8192` token bound without truncation;
- repeated document and query embeddings satisfy the numeric determinism contract;
- `sqlite-vec==0.1.9` loads and passes insert/delete/transaction/rebuild/exact-KNN proofs on
  required environments, or the recorded project reference fallback is selected;
- projection rows equal the frozen Evidence inventory and source digest;
- E1, E2, E3-A, and E3-B canonical validators pass;
- qrels, protocol, fixtures, locator inventory, and current runtime default remain unchanged.

Qwen3 compatibility or resource failure stops implementation and returns to planning. There is no
automatic model fallback.

### Development Gates

The candidate must:

- select one safety-eligible threshold using the frozen algorithm;
- recover at least `2` current-runtime grade-`2` misses across the target complementarity classes;
- keep unanswerable no-hit `>= 0.500000`;
- keep hard-negative failure `<= 0.300000`;
- preserve current-runtime results and all historical artifact semantics.

Failure records a valid negative E3-C result and prevents holdout scoring for promotion purposes.

### Holdout Gates

After the development configuration is frozen, holdout must:

- recover at least `2` current-runtime grade-`2` misses across the same target classes;
- keep unanswerable no-hit `>= 0.500000`;
- keep hard-negative failure `<= 0.142857`;
- preserve exact fixture, qrel, protocol, model, and projection identity.

All gates must pass for `e3d_status=eligible`. This status means only that running a separately
designed E3-D fusion experiment is justified; it does not claim that RRF works. Every E3-C artifact
also records `runtime_promotion_status=not_evaluated`. A dense candidate does not need to dominate
lexical retrieval alone; it must prove useful complementarity for a later fusion experiment.

## Artifact And Validation

The canonical JSON artifact records:

- source, protocol, qrel, fixture, and locator identities;
- candidate, model, revision, snapshot manifest, instruction, dimension, dtype, and package
  identities;
- projection adapter, schema, row inventory, source digest, vector digest, and size;
- selected threshold and complete development selection trace;
- current lexical and dense ordered Evidence observations;
- complementarity, per-category metrics, overall metrics, latency, memory, and gates;
- one explicit `candidate_status` and `e3d_status`.

Validation is split deliberately:

1. The model-free validator runs in required CI and independently recomputes schema, source
   identities, threshold selection, metrics, gates, and verdict consistency from recorded
   observations. It cannot prove that a coordinated replacement of retrieval observations is
   authentic; only cache-ready replay provides that independent retrieval oracle.
2. The cache-ready replay validator verifies the actual snapshot files, regenerates embeddings and
   the exact-KNN projection, and compares the resulting Evidence ordering and portable scores.

Evidence locator and order equality are exact. Portable cosine scores use an absolute tolerance of
`1e-5`; non-finite scores or larger differences fail. Task 0.5 must show this tolerance is sufficient
across supported local Python environments before qrel scoring. The model-free validator rejects
artifact and derived-field inconsistency; cache-ready replay must reject coordinated replacement of
retrieval observations and their derived fields.

## Resource Contract

Task 0.5 and the canonical artifact report actual measurements. These are feasibility ceilings, not
performance claims:

| Resource | Ceiling |
|---|---:|
| Complete model snapshot | `1.5 GiB` |
| Peak process RSS | `4 GiB` |
| 70-Evidence projection | `1 MiB` |
| One query embedding plus exact-KNN | `5 s` |

The report also records model preparation bytes, model load duration, projection build duration,
per-query median/p95 latency, and platform identity. Future runtime promotion requires its own
user-facing latency decision; passing these ceilings does not approve promotion.

## Error Contract

Public CLI failures use stable `problem`, `cause`, and `next_step` fields. Required mappings include:

- embedding dependency missing;
- model cache missing or incomplete;
- model revision or fingerprint mismatch;
- model output count or dimension mismatch;
- non-finite or non-normalized vector;
- Evidence input would be truncated;
- vector extension unavailable or incompatible;
- projection source identity mismatch;
- nondeterministic embedding, rank, or score;
- artifact validation or replay mismatch.

Errors must not expose absolute paths, raw provider exceptions, model-cache internals, or
tracebacks. There is no silent fallback to another model, provider, projection, or lexical result.

No safety-eligible threshold is a valid negative evaluation outcome, not an operational error. It
returns `candidate_status=completed`, `e3d_status=not_eligible`,
`runtime_promotion_status=not_evaluated`, and exit code `0`. Integrity or execution failures return
the public error contract and a non-zero exit.

A development valid-negative result also records the canonical comparison artifact with
`holdout_status=not_observed` and no holdout receipt. Exit code `0` means the evaluation completed,
not that E3-D is eligible; automation must inspect `e3d_status`.

## Delivery Shape

E3-C implementation is split into two independently reviewable PRs after the planning documents
land.

### PR 1: Dense Prerequisites

- optional embedding dependencies and locked package graph;
- project-owned embedding and vector contracts;
- Qwen3 prepare/doctor and cache-only adapter;
- sqlite-vec compatibility proof and exact-cosine reference;
- Python 3.12/3.13 installed-wheel model and projection proof;
- no candidate qrel scoring and no quality conclusion. Existing frozen E1/E2/E3-A/E3-B regression
  commands may parse their historical qrels, but new PR 1 dense code and compatibility proof must
  not import or consume qrels.

### PR 2: Dense Comparison Evidence

- frozen threshold and gate contract;
- dense comparison runner and CLI;
- development threshold selection and one holdout observation;
- canonical artifact, model-free validator, and cache-ready replay;
- comparison documentation and durable implementation review.

## Stop Conditions

Implementation stops and returns to planning when:

- Qwen3 fails package, CPU, model integrity, determinism, truncation, or resource gates;
- no approved local execution path can load the exact revision without remote code;
- the frozen protocol, qrels, fixtures, or current runtime default would need to change;
- holdout has been observed before threshold and candidate settings are frozen;
- portable ranking cannot be reproduced within the numeric contract.

The following are valid terminal E3-C outcomes, not implementation failures:

- no development threshold satisfies safety gates;
- dense does not recover enough target-class Evidence;
- holdout complementarity or safety gates fail;
- E3-D remains ineligible.

## Non-Goals

E3-C does not:

- change the runtime retrieval default;
- add dense behavior to normal Search, Ask, or MCP;
- implement an embedding API adapter;
- implement RRF, reranking, query rewrite, or segmentation changes;
- create a persistent production vector projection;
- add Milvus, Qdrant, pgvector, Redis, or another vector service;
- reuse legacy RAG-OCR code or service boundaries;
- claim broad Chinese production quality or statistical significance;
- add an ADR, because no runtime architecture or default is promoted.

## Acceptance Criteria

The E3-C implementation is complete when:

- both implementation PRs land independently or a valid negative stop condition is recorded;
- the exact model and runtime compatibility evidence precedes qrel scoring;
- development threshold selection and holdout isolation are independently validated;
- development and holdout use separate Evidence snapshots and projections, and cross-partition
  locators are rejected;
- a committed development freeze precedes the single canonical holdout receipt;
- the canonical artifact reports all four comparison arms and resource evidence;
- all integrity, safety, complementarity, and determinism gates are evaluated honestly;
- `e3d_status` is derived from frozen gates rather than implementation intent;
- `e3d_status` is documented as experiment eligibility and runtime promotion remains not evaluated;
- current runtime, E1/E2/E3-A/E3-B semantics, product proof, and demo remain unchanged;
- public documentation states that dense remains comparison-only.

## Recommendation

Proceed with `qwen3-embedding-0.6b-exact-v1` as the single canonical E3-C model. Establish the
project-owned embedding and vector boundaries first, preserve local reproducibility as the
canonical reference, and treat API integration as a separate future adapter. Start E3-D only if
the frozen dense artifact proves complementary grade-`2` retrieval on development and holdout
without weakening refusal or hard-negative behavior. A negative E3-C result applies to this exact
candidate configuration and does not generalize to every dense model.
