# Chinese Hybrid Retrieval Evaluation Design

## Status

- Stage: Approved for E3-A implementation after autoplan review.
- Slice: E3.
- Design date: 2026-06-25.
- Baseline: `main@b04df63a1c07b8df3dcd1284cdbea42dd4e31e1c`.
- Depends on:
  - the completed E1 deterministic retrieval baseline;
  - the completed E2 numeric candidate comparison and promotion;
  - the existing active-Publication-only Search and evidence-only Ask contracts.

Only E3-A is approved for immediate implementation. E3-B through E3-F remain
evidence-gated follow-up stages. Their implementation plans must not be written until the
preceding canonical artifact exists and the next candidate boundary is approved.

## Goal

Build a reproducible Chinese retrieval-evaluation program that can compare:

```text
current ASCII-oriented FTS5 lexical
  vs CJK lexical retrieval
  vs local dense retrieval
  vs CJK lexical + dense + Reciprocal Rank Fusion
  vs hybrid retrieval + reranking
```

The program must determine which smallest retrieval strategy, if any, improves Chinese page-level
Evidence retrieval without weakening active Publication isolation, deterministic evaluation, local
operation, refusal behavior, or rollback.

E3 is not accepted merely because the repository contains embeddings, a vector extension, RRF, or
a reranker. Every candidate must be evaluated against a frozen development/holdout protocol and
may be recorded as rejected.

## Current Evidence

MKE currently provides:

- page-addressed text-layer PDF Evidence and timestamp-addressed short-video Evidence;
- observable immutable Runs and atomic per-Source Publication switching;
- active-Publication-only FTS5 Search and evidence-only Ask;
- a deterministic product proof through `mke proof run`;
- E1, a 24-query English retrieval baseline;
- E2, a frozen development/holdout comparison that promoted the bounded
  `numeric-grouping-v1` query policy.

The current retrieval boundary remains narrow:

- Search uses one SQLite FTS5 projection and orders by the configured FTS5 `rank`;
- query compilation extracts ASCII alphanumeric and underscore terms;
- CJK-only Search and Ask inputs do not have a usable lexical query;
- no repository-visible Chinese corpus, graded qrels, nDCG, dense retrieval, fusion, reranking,
  or local resource comparison exists;
- no current artifact demonstrates that hybrid retrieval or reranking improves quality.

Before public documentation describes the current lexical scorer as BM25, E3-A must verify and
document the actual SQLite FTS5 `rank` behavior used by the supported runtime. The project must
not use a familiar market label when the implementation evidence supports only the more precise
term `FTS5 lexical retrieval`.

## Chosen Program

E3 is split into six independently reviewable stages:

1. **E3-A — Chinese lexical baseline and failure characterization**
2. **E3-B — CJK lexical retrieval candidate**
3. **E3-C — Local dense retrieval candidate**
4. **E3-D — CJK lexical/dense RRF candidate**
5. **E3-E — Reranker candidate**
6. **E3-F — Conditional promotion and demonstration**

Each stage must be able to stop with a trustworthy negative result. Candidate rejection is a valid
outcome and does not justify changing the corpus, queries, qrels, or gates in place.

## Rejected Alternatives

| Alternative | Decision | Reason |
|---|---|---|
| Add CJK lexical, dense, RRF, reranking, and query rewriting in one PR | Rejected | It would change multiple independent variables and make quality deltas uninterpretable. |
| Promote hybrid retrieval before a Chinese baseline exists | Rejected | Familiar terminology is not evidence that the strategy improves this product. |
| Reuse the legacy RAG-OCR service layout | Rejected | FastAPI, Milvus, Redis, LangChain/Chatchat, request-owned provider configuration, and mixed service DTOs conflict with current architecture. |
| Copy the legacy RRF or hybrid modules | Rejected | E3 requires project-owned Evidence identity, deterministic tie-breaking, provenance, and Publication filtering. |
| Use an external API as the canonical benchmark | Rejected | Provider drift, credentials, network availability, cost, and hidden preprocessing prevent independent offline reproduction. |
| Require Milvus or another standalone vector service | Rejected | The first Chinese corpus is small and local; a distributed service would add operational complexity without demonstrated need. |
| Change Passage/chunk segmentation with retrieval algorithms | Rejected | Retrieval and segmentation deltas must remain separable. |
| Add query rewrite or HyDE now | Deferred | E3-A must first identify vocabulary-mismatch failures that lexical, dense, and hybrid retrieval do not already address. |
| Build a Web UI as part of E3 | Deferred | A proof command, architecture diagram, comparison table, and short recording are sufficient to demonstrate this slice. |

## Architecture Constraints

Existing ADR constraints remain unchanged:

- SQLite is domain truth.
- Retrieval indexes are rebuildable projections.
- Search and Ask read only active Publications.
- Domain and application contracts use project-owned DTOs and ports.
- External model and storage libraries remain inside adapters.
- Provider URLs, keys, model download policy, and arbitrary strategy expressions are not
  request-controlled.
- Random vectors and silent fallback are prohibited.

Changing any of these constraints requires a new ADR in the same promotion PR.

## Retrieval Architecture

### Comparison-Time Shape

E3-B through E3-E first run as off-default evaluation candidates:

```text
frozen corpus
  -> normal ingest and active Publication
  -> immutable active Evidence snapshot
       |                    |                         |
       v                    v                         v
 current FTS5 Search   CJK lexical projection   evaluation-only vector projection
       |                    |                         |
       +--------------------+-----------+-------------+
                                        v
                                  optional RRF
                                        |
                                  optional reranker
                                        |
                                  ordered Evidence IDs
                                        |
                                  graded-qrel metrics
```

The comparison path must not change normal runtime defaults, public Search/Ask DTOs, or
Publication behavior. Each stage builds only the temporary projection required by its candidate:
E3-B builds a CJK lexical projection, while E3-C through E3-E may additionally build a local,
rebuildable vector projection from the same immutable snapshot of active Evidence.

Every vector row is bound to:

- `evidence_id`;
- `publication_id`;
- `source_id`;
- model provider identity;
- model name and immutable revision;
- embedding dimension;
- normalized embedding configuration fingerprint.

The evaluator must reject a projection row whose Evidence is not present in the frozen active
snapshot or whose Publication/model identity does not match the current comparison run.

### Promotion-Time Shape

Only E3-F may integrate an approved strategy into normal Search:

```text
candidate Evidence
  -> build every projection required by the selected strategy
       |-> CJK lexical rows when selected
       `-> embeddings when dense retrieval is selected
  -> validate counts, Evidence/Publication identity, tokenizer/model fingerprints,
     vector dimension, and finiteness
  -> Run validation
  -> atomic Publication activation
       |-> activate matching lexical projection identity
       |-> activate matching vector projection identity when required
       `-> switch Source.active_publication_id
```

For a promoted CJK lexical, dense, or hybrid strategy:

- new Publications must not activate if any required lexical or embedding batch is missing or
  invalid;
- a failed reprocessing Run leaves the previous Publication and its approved projections
  searchable;
- runtime startup must fail readiness when the selected strategy lacks a complete projection for
  active Publications;
- switching to a strategy whose required projection is absent requires an explicit projection
  preparation/rebuild operation; model-backed rebuilds remain cache-only;
- normal ingest, Search, Ask, MCP, proof, and doctor operations must not download models;
- switching back to the existing `numeric-grouping-v1` strategy requires no migration or index
  rebuild.

The exact promotion transaction and migration contract must be specified in the E3-F ADR after a
candidate passes comparison gates.

## Project-Owned Boundaries

Future candidate work may introduce project-owned concepts equivalent to:

- `LexicalProjection`: builds and searches deterministic CJK lexical rows for active Evidence;
- `EmbeddingProvider`: converts validated text batches or one query into fixed-dimension vectors;
- `VectorProjection`: writes, validates, activates, searches, and rebuilds vector rows;
- `RankedEvidence`: internal candidate identity plus rank and strategy provenance;
- `RetrievalStrategy`: an owner-selected allowlisted strategy identifier;
- `RerankerProvider`: scores a bounded ordered Evidence candidate set.

These are design roles, not approved public class names. The E3-C plan must first inspect existing
ports and DTO conventions and choose the smallest compatible project-owned contract.

Library-specific objects from `sqlite-vec`, model runtimes, HTTP clients, or provider SDKs must not
cross adapter boundaries.

## Vector Projection Candidate

The preferred first compatibility candidate is `sqlite-vec` because it:

- runs inside SQLite without a separate service;
- provides Python bindings and `vec0` virtual tables;
- supports local KNN queries and metadata constraints;
- is distributed under MIT/Apache-2.0 terms;
- fits the existing rebuildable-projection architecture.

It is not yet approved as a production dependency. The upstream project is pre-v1 and documents
possible breaking changes. Before E3-C may select it, an isolated compatibility proof must verify:

- one exact pinned version;
- extension loading under supported Python 3.12 and 3.13 wheel environments;
- supported Darwin and required CI platform behavior;
- the SQLite runtime version and extension-loading capability;
- deterministic insert, delete, rebuild, and exact-KNN behavior;
- transaction and failure behavior required by the projection adapter;
- absence of source-tree imports in installed-wheel proof;
- license and package provenance.

If the compatibility proof fails, E3-C may use a project-owned exact cosine reference projection
for evaluation. It must not jump directly to Milvus, Redis, Qdrant, pgvector, or a hosted vector
service without a separate architecture decision.

The initial corpus is intentionally small, so E3-C uses exact KNN. Approximate indexes, HNSW,
DiskANN, IVF, and distributed vector infrastructure remain outside this program until scale or
latency evidence requires them.

## Model And Provider Policy

### Canonical Local Path

Canonical candidate artifacts must use:

- a locally executed model with an immutable model revision;
- an operator-controlled cache outside the repository;
- explicit preparation as the only model-download path;
- cache-only evaluation, ingest, Search, Ask, MCP, and proof paths;
- recorded provider, model, revision, dimension, runtime, platform, and configuration identity.

The E3-C and E3-E plans must compare current Chinese-capable model candidates using official
documentation, model licenses, package/platform compatibility, memory requirements, and expected
task fit before choosing one. This design intentionally does not approve a model name before that
audit.

### Optional API Path

An external embedding or reranking API may later be implemented behind the same project-owned
port to prove production integration concerns such as timeout, authentication, rate limiting,
redacted errors, and batch validation.

The API path:

- is not required CI;
- is not the canonical promotion artifact;
- cannot receive provider URL, API key, or model choice from Search/Ask/MCP requests;
- must use owner configuration fixed before engine construction;
- must not silently fall back to a different provider or the lexical strategy;
- must not upload private fixtures or user content without a separate trust and privacy decision.

## Legacy RAG-OCR Boundary

The archived RAG-OCR repository is an engineering-history reference, not an implementation
dependency.

Allowed reuse:

- failure cases for embedding timeout, authentication failure, invalid dimensions, missing batch
  output, and reranker response mismatch;
- operational lessons from Milvus/etcd and service coupling;
- Chinese tokenization and hard-negative ideas;
- provider response-shape examples for future test fixtures;
- heading and cross-page segmentation hypotheses for a later independent slice.

Prohibited reuse:

- source-tree transplantation;
- Milvus collection schemas or service wrappers;
- Redis caching;
- FastAPI service topology;
- LangChain/Chatchat DTOs or configuration;
- import-time environment configuration and global provider singletons;
- request-owned endpoints, credentials, or model names;
- silent fallback to random vectors, ungrounded answers, or a different retrieval strategy.

RRF and metric calculations must be implemented from their published definitions using MKE-owned
types and tests rather than copied from the legacy module.

## E3-A Corpus Protocol

### Corpus Composition

E3-A freezes exactly three redistribution-safe real Chinese text-layer PDFs:

- one development document from a Chinese technical documentation source;
- two holdout documents from independent Chinese public-policy, standards, or legal-information
  publishers that are not part of the development source or series.

It also freezes two repository-generated text-layer PDF fixtures:

- one development adversarial fixture;
- one independently authored holdout adversarial fixture.

The generated fixtures exist only to provide controlled Chinese word-boundary, mixed-language,
number/date/unit, semantic-paraphrase, multi-condition, and ranking-hard-negative cases. They must
not duplicate sentences, query text, entities, primary numbers, or distractor construction across
development and holdout.

The real source documents must satisfy all of these gates:

- clear legal basis for repository redistribution;
- stable public source URL;
- text-layer PDF with deterministic extraction under the pinned PDF adapter;
- no personal, private, credential, or access-controlled content;
- sufficient factual density for manually reviewed page-level qrels;
- no dependency on OCR, tables, coordinates, or layout recovery for the selected questions;
- no shared publisher series or mirrored content across development and holdout.

Before downloading any fixture, the implementation window must report the exact source URL,
license or legal basis, target temporary path, intended repository path, expected bytes when
available, and expected SHA-256 when available, then obtain explicit authorization. Downloaded
bytes must first land outside the repository. After retrieval, the implementation must verify and
report the actual byte size, page count, extracted character counts, and SHA-256 before copying an
approved file into the fixture tree.

If permission or redistribution status is unclear, the file is rejected rather than referenced
with an unresolved caveat.

### Development And Holdout

The protocol contains 48 queries:

- 24 development queries;
- 24 public holdout queries.

The holdout is frozen and independently authored before candidate code, but remains visible in the
public repository. It protects against editing the target after implementation; it is not a blind
test or statistical generalization claim.

Future candidate stages use this public holdout under a one-observation rule:

- candidate identity, revision, parameters, development gates, and promotion gates are frozen
  before the holdout observation;
- implementation and tuning use only development queries against the development corpus;
- holdout queries run only against the holdout corpus, so development work cannot observe holdout
  documents or their retrieval behavior;
- each frozen candidate receives one canonical holdout observation, with the evaluator's required
  duplicate holdout workspace run used only to prove determinism;
- changing candidate code, parameters, gates, qrels, or fixture bytes after observing holdout
  results marks that holdout observation as contaminated for promotion;
- a contaminated candidate requires a new protocol version or is reported as development-only
  evidence.

Each side has the same category allocation:

| Category | Per side | Total |
|---|---:|---:|
| Chinese exact lexical | 4 | 8 |
| Chinese word boundary | 3 | 6 |
| Proper noun / mixed Chinese-English | 3 | 6 |
| Number, date, and unit | 3 | 6 |
| Semantic paraphrase | 4 | 8 |
| Multi-condition question | 3 | 6 |
| Ranking hard negative | 2 | 4 |
| Unanswerable | 2 | 4 |
| **Total** | **24** | **48** |

The implementation must define category rules precisely enough that a query cannot be reassigned
after observing candidate results. A query may contain multiple linguistic properties, but it has
one protocol-owned primary category.

### Graded Qrels

Answerable queries use page-level graded qrels:

- `2`: direct Evidence that can answer the query on its own;
- `1`: relevant supporting Evidence that cannot answer the query independently;
- `0`: a deliberately similar or confusable distractor.

Unanswerable queries have no relevant Evidence.

Before protocol freeze, every query receives a complete ordered judgment inventory against its
own corpus partition:

- 24 development queries against 34 development pages;
- 24 holdout queries against 36 holdout pages;
- 1,680 recorded query-page judgments in total.

Each judgment records the exact page locator and one of `0`, `1`, `2`, or `non_relevant`.
Answerable-query review must confirm that every independently answer-capable page is grade `2`,
every relevant but insufficient page is grade `1`, and every designated confuser is grade `0`.
Unanswerable-query review must confirm that every page in its partition is non-relevant. The
validator derives coverage and counts from the ordered judgment records rather than trusting
summary fields. The protocol provenance records the review method, review date, bounded
public-safe decision basis, and `review_status=complete`. E3-A does not claim independent
inter-rater agreement because the protocol does not require two separate annotators.

Metric semantics are fixed:

- Recall@1/3/5 and MRR@5 treat only grade `2` as relevant;
- nDCG@5 and nDCG@10 use the full `0/1/2` gain scale;
- answerable zero-hit records queries with no grade-`2` result;
- hard-negative failure records a designated grade-`0` distractor ranked ahead of every grade-`2`
  target, or a distractor returned when the direct target is absent;
- unanswerable no-hit records whether Search returns no Evidence;
- Ask input rejection, Ask insufficient-Evidence refusal, and Ask evidence-found outcomes are
  reported separately from Search quality and are not E3-B promotion gates.

A baseline quality failure does not make E3-A execution fail. E3-A fails only on protocol,
fixture, qrel, ingestion, active-Evidence, determinism, completeness, or reporting-integrity
errors.

## E3-A Evaluation Contract

E3-A extends the evaluation surface rather than `mke proof run`.

The exact CLI name and schema version are selected in the E3-A plan, but the command must:

1. validate a strict external protocol and every fixture identity;
2. snapshot immutable fixture bytes before ingest;
3. ingest through normal application and Publication behavior;
4. enumerate and validate active Evidence locators;
5. execute the current default FTS5 lexical strategy in two fresh SQLite workspaces per corpus
   partition;
6. compare deterministic ordered locator results;
7. calculate the approved graded metrics and category breakdowns;
8. report compiled-query emptiness and ASCII-token-count strata separately from the protocol's
   human-authored linguistic categories;
9. emit human-readable and JSON reports;
10. produce a public-safe canonical artifact;
11. leave `mke proof run`, E1, E2, Search, Ask, CLI, and MCP runtime behavior unchanged.

The canonical artifact records:

- protocol, fixture, qrel, query-ID, environment, SQLite, PDF adapter, and source-code identity;
- aggregate and per-category metrics;
- compiled-query-empty and ASCII-token-count strata;
- per-query ordered locator outcomes and grades;
- mechanically observed miss-symptom counts;
- per-query FTS5 `rank`/`bm25()` ordering and score-digest evidence;
- verified FTS5 scorer semantics;
- determinism and integrity results;
- explicit limits on what the observation proves.

It omits absolute paths, private environment details, credentials, raw extracted documents,
unstable random IDs, and unsupported product-quality claims.

Required CI gates protocol and artifact integrity, not a minimum Chinese retrieval score.

## E3-A Miss-Symptom Taxonomy

Every answerable miss must receive one primary mechanically observed classification:

- `compiled_query_empty`;
- `distractor_ranked_ahead`;
- `compiled_clauses_absent_from_direct_page`;
- `compiled_clauses_overconstrained`;
- `matching_direct_page_not_returned`;
- `other_observed_miss`.

The query compiler exposes an evaluation-only structured diagnostic for its actual `AND` clauses
and parenthesized `OR` alternatives. The classifier inspects whether each grade-`2` page satisfies
every required clause under the compiler's exact semantics, together with returned ordered
locators. It must not infer word-boundary, semantic, segmentation, or other causal claims from the
human-authored query category. A separate reviewed note may discuss hypotheses, but those
hypotheses are not canonical artifact facts.

E3-B may proceed only when E3-A integrity passes, qrel review is complete, and the development
split contains at least one answerable grade-`2` miss with `compiled_query_empty`. E3-B may target
only deterministic CJK lexical compilation/index coverage. Misses classified as
`compiled_clauses_overconstrained`, `matching_direct_page_not_returned`, or
`other_observed_miss` do not by themselves justify E3-B and must not be used to broaden that
candidate into semantic retrieval, query rewrite, or segmentation work.

## E3-B CJK Lexical Candidate

E3-B may begin only after E3-A is merged and its artifact is validated on squash-landed `main`.

E3-B must:

- use the same E3-A protocol without modifying queries, qrels, or fixture bytes;
- use E3-A failure evidence to select one bounded deterministic CJK lexical candidate;
- freeze the candidate definition, tokenizer/runtime identity, index/query behavior, and promotion
  gates before candidate scoring;
- compare the current ASCII-oriented FTS5 path with the CJK lexical candidate on development and
  holdout;
- report Recall, MRR, nDCG, category deltas, compiled-query or token diagnostics, latency, and
  projection size;
- preserve the current E1 and E2 observations, including ASCII, identifier, leading-zero, and
  numeric-grouping behavior;
- remain local, model-free, deterministic, and free of network access;
- preserve current runtime defaults.

E3-B does not preselect `jieba`, FTS5 `trigram`, a custom tokenizer, or query-only expansion. Its
implementation plan must audit the supported SQLite runtime and any candidate dependency using
official documentation, deterministic packaging, license, installed-wheel support, and index
rebuild requirements. Legacy RAG-OCR tokenization is only a source of test ideas.

The selected candidate must define both document and query token semantics. A query-only change is
not acceptable when indexed CJK token boundaries remain incompatible. If the candidate changes
indexed text or tokenizer configuration, it runs first as a temporary evaluation-only projection
and does not alter the normal active FTS5 table.

E3-B is eligible for later fusion only when it establishes usable grade-`2` Chinese lexical recall
without violating determinism, unanswerable controls, hard-negative safety, or E1/E2 regression
gates. Exact numeric gates are frozen after E3-A observation and before E3-B implementation.

## E3-C Dense Candidate

E3-C may begin only after E3-B is merged and its artifact is validated on squash-landed `main`.

E3-C must:

- freeze model and vector-projection compatibility evidence before candidate scoring;
- use the unchanged E3-A protocol and the frozen E3-B lexical candidate;
- add an off-default local embedding and exact-KNN comparison path;
- compare current lexical, CJK lexical, and dense results on development and holdout;
- report Recall, MRR, nDCG, category deltas, latency, model preparation size, peak process memory
  when measurable, and projection size;
- preserve all E1/E2 results and current runtime defaults.

Dense retrieval is eligible for E3-D only when it demonstrates complementary grade-`2` recall over
the approved CJK lexical candidate on at least one predeclared failure class without violating
corpus integrity, determinism, unanswerable controls, or hard-negative safety gates. Exact numeric
gates are frozen after E3-B observation and before E3-C implementation.

## E3-D RRF Candidate

E3-D may begin only when E3-C establishes complementary CJK lexical and dense results.

The RRF candidate:

- receives two independently ordered lists of stable Evidence IDs;
- deduplicates by Evidence ID;
- uses the published reciprocal-rank formula with an explicitly versioned `k`;
- applies deterministic tie-breaking;
- never combines raw FTS5 and vector distances;
- records each result's lexical rank, dense rank, and fused score for diagnostics;
- does not alter qrels, embedding model, projection, segmentation, or candidate depth while tuning
  fusion.

Development may compare a small predeclared set of `k` values. Holdout is evaluated once after the
development choice is frozen. The exact search depths and candidate `k` set belong in the E3-D
plan.

## E3-E Reranker Candidate

E3-E may begin only when E3-D produces a hybrid candidate whose initial recall leaves a meaningful
ranking problem.

The reranker:

- receives the original query and a bounded hybrid top-N Evidence set;
- returns a complete one-to-one score/order mapping for that set;
- cannot create, remove, or change Evidence identity;
- uses a fixed local model revision for canonical comparison;
- records model/runtime identity and reranking latency;
- fails closed on missing items, duplicates, non-finite scores, response mismatch, timeout, or
  model fingerprint mismatch.

Reranking is promotable only when it improves the frozen ranking metrics, preserves direct-Evidence
Recall, and does not violate hard-negative or unanswerable gates. A latency increase is reported
as an explicit tradeoff rather than hidden by the quality result.

## E3-F Conditional Promotion

E3-F promotes only the smallest strategy supported by prior artifacts:

- lexical remains valid if no candidate passes;
- CJK lexical may be promoted without dense retrieval;
- dense may be promoted without RRF if it dominates the approved gates;
- hybrid may be promoted without reranking;
- the full hybrid-plus-reranker chain is not the default merely because it was implemented.

Promotion requires:

- a new ADR;
- an allowlisted owner startup strategy;
- a direct `numeric-grouping-v1` rollback path;
- cache-only readiness and projection rebuild commands;
- installed-wheel CLI and stdio MCP proof on supported Python versions;
- failure-isolation proof for partial embedding and projection activation;
- current E1, E2, product proof, demo, lint, type checking, build, and evaluation gates;
- documentation explaining measured quality/resource tradeoffs and rejected candidates.

## Public Demonstration Deliverables

E3-F includes:

- one current architecture diagram showing domain truth, lexical projection, vector projection,
  RRF, optional reranker, and active Publication filtering;
- one strategy-comparison table generated from canonical artifacts;
- one direct proof/evaluation command that can run without network access after explicit model
  preparation;
- one repository-visible 2–3 minute demonstration script covering ingest, strategy comparison,
  cited Evidence, refusal, and rollback;
- one externally published recording only after explicit user authorization.

The demonstration must not imply broad Chinese production quality, statistical significance,
arbitrary-document support, hosted availability, or a candidate capability that was rejected.

## Documentation And Decision Records

- This document is the program-level E3 design.
- E3-A receives its own implementation plan and durable autoplan review.
- E3-B, E3-C, E3-D, E3-E, and E3-F each receive a separate plan only after their prerequisite artifact
  is merged.
- Candidate-comparison stages do not need an ADR while runtime defaults and architecture
  constraints remain unchanged.
- E3-F requires an ADR for the promoted strategy, model/projection lifecycle, readiness, and
  rollback.
- Public docs must remain neutral and must not mention private planning, recruiting objectives,
  private workspace paths, or raw planning-tool artifacts.

## E3-A Acceptance Criteria

E3-A is complete when:

1. Exactly three approved real Chinese text-layer PDFs and two independent generated adversarial
   fixtures are frozen with provenance, redistribution basis, bytes, page counts, extracted
   character counts, and SHA-256 values.
2. The strict protocol contains exactly 48 queries with the approved development/holdout and
   category allocation.
3. Every answerable grade-`2` or grade-`1` qrel resolves to an active page Evidence locator, and
   every designated grade-`0` distractor exists.
4. Two fresh workspaces per corpus partition produce identical ordered locator outcomes for the
   current default lexical strategy, and development execution never ingests holdout documents.
5. Reports include Recall@1/3/5, MRR@5, nDCG@5/10, answerable zero-hit, hard-negative failure,
   unanswerable no-hit, separate Ask input-rejection/insufficient-Evidence/evidence-found rates,
   category breakdowns, compiled-query-empty strata, and ASCII-token-count strata.
6. Every grade-`2` miss has one mechanically observed primary miss-symptom classification.
7. The canonical artifact validator independently verifies protocol, source, environment, result,
   metric, classification, adjudication-record coverage, FTS scorer evidence, and report
   consistency; it does not claim to machine-verify human relevance judgment correctness.
8. Required CI gates integrity and determinism without turning observed quality values into fixed
   thresholds.
9. Existing Search, Ask, E1, E2, Publication, CLI, MCP, product proof, transcription, and runtime
   defaults remain unchanged.
10. The implementation plan and durable review apply the predeclared E3-B start rule and record
    whether the development observation justifies a bounded CJK lexical candidate.

## E3-A Planning And Review Sequence

The next approved workflow is:

```text
write E3-A implementation plan
  -> run gstack-autoplan in HOLD SCOPE mode
  -> persist public-neutral review
  -> user reviews spec, plan, and review
  -> generate implementation-window handoff
```

The autoplan must review whether E3-A creates trustworthy evidence for later candidates. It must
not expand E3-A into embedding, vector projection, RRF, reranking, query rewrite, segmentation,
OCR, HTTP, or UI implementation.
