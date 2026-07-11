# Architecture

## Product Boundary

Multimodal Knowledge Engine converts documents and media into published Evidence that users and Agents can search, cite, and ask questions over.

## Domain Vocabulary

`Library`, `Source`, `Asset`, `Run`, `Artifact`, `Segment`, `Passage`, `Evidence`, and `Publication` are the public product concepts.

## Lifecycle

```text
Source
  -> immutable Asset
  -> observable Run
  -> candidate Evidence and RunManifest
  -> validated Run
  -> active Search projection
  -> atomic Publication switch
  -> Search / Ask Evidence
```

A failed, interrupted, superseded, or partial Run never changes the active Publication. Retry
creates a new immutable Run.

The current PDF and short-video slices implement only the lifecycle concepts needed to prove
trustworthy Search:
`Library`, `Source`, `Asset`, `Run`, `Evidence`, `RunManifest`, and `Publication`. `Artifact`,
`Segment`, and `Passage` remain public vocabulary for later cross-modal and Ask workflows, but
their durable semantics are not stabilized before the PDF and video slices validate the lifecycle.

## Publication Semantics

Publication is atomic per `Source`.

```text
candidate Evidence + RunManifest
  -> validate counts, locators, extractor fingerprint, required stages
  -> check Run generation and Source active revision
  -> create Publication
  -> replace this Source's active FTS5 rows
  -> switch Source.active_publication_id
  -> persist a successful transcript intake report when required
  -> mark Run published
```

Candidate, failed, superseded, or historical output is not stored in the active FTS5 projection.
Search reads only active Publication rows and joins back through the active Publication identity.
A stale Run that loses the Source generation or active revision check is marked `superseded`
without changing active Search visibility.

For recognized `faster-whisper-v1:<64 lowercase hex>` Manifests, activation additionally requires
a validated `TranscriptIntakeReport`. The Publication row, active FTS5 replacement, Source pointer,
successful report, `published` Run state, and publication event commit in one SQLite transaction.
Any failure rolls all of them back. Failed and superseded Runs therefore cannot expose a successful
report, and legacy PDF or sidecar video Publications remain valid without one.

## Transcript Protocol

The provider-neutral transcript boundary uses project-owned `VideoMediaInfo`,
`VideoTranscriptSegment`, optional `TranscriptionProvenance`, `ParsedVideoTranscript`, and
`TranscriptExtractionResult` DTOs. Existing `mke.video_transcript.v1` sidecars may omit the
additive `transcription` object. First-party faster-whisper output must provide complete validated
provenance before a later runtime adapter can construct a successful `TranscriptIntakeReport`.

The shared parser enforces a 15-minute media-duration limit, a 10,000-segment limit, positive
integer millisecond media duration, stable timestamp ranges within that duration, bounded identity
strings, and exact provider/model revision rules. Application preflight rejects missing, empty,
non-MP4, or over-100-MiB inputs before hashing, provider execution, or Run creation.

## Current Runtime Shape

The runtime is an in-process CLI plus a project-owned application service. SQLite remains the
domain truth and owns the rebuildable active FTS5 projection. The built-in PDF adapter extracts
page-addressed text Evidence from deterministic text-layer PDFs. Video transcription now sits
behind a project-owned `TranscriptProvider` port: the default `SidecarTranscriptProvider` reads
timestamp-addressed transcript Evidence from a deterministic local sidecar for the documented
short MP4 fixture profile, while `LocalCommandTranscriptProvider` also binds the package-owned
faster-whisper subprocess. `src/mke/runtime.py` is the shared CLI/MCP composition root. Preparation
is explicit; doctor, ingest, MCP startup, and adapter execution are cache-only. Requests cannot
supply command argv or download policy. Deterministic proof remains sidecar-backed and model-free.
CLI faster-whisper ingest performs readiness before engine construction, while successful
provenance uses the runtime profile resolved by CTranslate2. Adapter failure metadata remains typed
through the provider and application layers so interfaces can return the correct operator action.
Cancellation remains latched for the active MCP worker, closing the interval between worker start
and child-process registration.

The real transcription proof builds a temporary SQLite workspace and invokes the same application
composition without calling model preparation. The deployment proof builds the project wheel,
installs `wheel[transcription]` under lock-derived constraints in an external temporary
environment, then compares installed CLI results with a real stdio MCP Python SDK client. Both
paths require an already prepared exact model revision and remain cache-only.

The retrieval evaluator is a separate offline diagnostics surface. It validates a strict external
manifest, snapshots exact fixture bytes, ingests through the same application service into two
fresh temporary SQLite workspaces, and compares stable page/timestamp locator outcomes from the
existing Search and evidence-only Ask contracts. It does not duplicate retrieval SQL, change
Publication behavior, or impose a quality threshold.

The E2 numeric comparator added a project-owned query-policy compiler at the SQLite composition
boundary. After the frozen candidate passed all 14 gates, ADR-0007 promoted
`numeric-grouping-v1` as the runtime default for that stage. It preserves the compact numeric token and
adds one right-grouped adjacent-token phrase inside the same FTS5 `MATCH` statement. Owner
configuration may select allowlisted `current` rollback through typed `RuntimeConfig` and the
global CLI/MCP startup option. The selector is fixed before engine construction and is not exposed
through Search, Ask, or MCP request DTOs.

Policy selection changes query compilation only. It does not change indexed text, tokenizer
configuration, ranking SQL, Publication semantics, result DTOs, Search limits, database schema, or
index contents, so rollback requires no migration or rebuild. Development, public holdout, and E1
observations are compared through the existing evaluation runner from one protocol-bound immutable
snapshot. The comparator traces the actual FTS5 statements executed by Search and checks the
observed SQLite schema and local provider identities before passing its scope gates. The result is
bound into a source-content-addressed artifact whose nested observations and metrics are
independently validated.

E3-A is another offline diagnostics surface, not a runtime retrieval layer. It ingests the
development corpus into two temporary SQLite workspaces and the public holdout corpus into two
separate workspaces. Active Evidence is enumerated from SQLite domain truth; the FTS5 projection
is independently checked for exact Evidence IDs, locator labels, and text hashes. Search, Ask
Search, and full-result rank probes remain separate observations. The probe established that the
current `rank` pseudo-column equals SQLite FTS5 default `bm25()` ordering and scores for this
protocol, so documentation may name the observed profile `sqlite_fts5_default_bm25`.

The FTS5 query compiler remains ASCII-oriented. E3-A records graded metrics and deterministic miss
symptoms without claiming a general CJK tokenizer or broad CJK retrieval support.

E3-B adds an offline comparison candidate, not a runtime retrieval layer. The
`cjk-trigram-overlap-v1` runner first observes the unchanged `numeric-grouping-v1` path. Only when
that compiler returns an empty query does it build an evaluation-only SQLite FTS5 `trigram`
projection from the immutable active Evidence snapshot and apply a deterministic overlap scorer
over frozen page text. The normal `active_evidence_fts` projection, Publication activation,
Search/Ask DTOs, owner runtime selector, CLI/MCP runtime behavior, HTTP, UI, embeddings, vector
search, hybrid retrieval, RRF, reranker, and query rewrite remain unchanged.

E3-F adds a runtime strategy boundary without adding persistent state:

```text
owner-startup retrieval strategy
  -> compile once with numeric-grouping-v1
     -> compiled non-empty -> active_evidence_fts -> active Publication Evidence
     -> compiled-empty + eligible CJK -> bounded active Evidence scan -> overlap rank
     -> compiled-empty + ineligible -> stable validation result
```

`cjk-active-scan-overlap-v1` reads text only through active Publication joins in SQLite domain
truth. It does not create projection rows, metadata, caches, vectors, or schema changes. Mixed
ASCII+CJK and numeric compiled non-empty queries are FTS-only even after an FTS zero-hit, so the
runtime never silently discards ASCII or numeric constraints. Search and Ask share this routing;
MCP tools cannot override it per request.

The strategy still requires the existing `active_evidence_fts` base projection for compiled
non-empty queries. Doctor checks that the FTS5 table exists and exactly matches active Publication
Evidence. "No projection" in the active-scan contract means no additional CJK projection.

After the E3-F launch gate, `cjk-active-scan-overlap-v1` is the default when the owner omits the
selector. The owner can still select an allowlisted strategy before `KnowledgeEngine`
construction. Doctor checks are read-only. Active-scan rebuild is a stable no-op only for the
additional CJK projection; base FTS rebuild is not implemented. Rollback to `numeric-grouping-v1`
or `current` requires no migration. E3-C through E3-E remain future, evidence-gated stages. The E3-F strategy
does not add embedding, vector search, hybrid retrieval, RRF, reranking, query rewrite,
Passage/chunk, OCR, HTTP, or UI behavior.

E3-C PR 1 adds a comparison-only local embedding prerequisite without adding runtime dense
retrieval. Provider-neutral DTOs live under `mke.embeddings` and `mke.vector`; SentenceTransformers,
Hugging Face Hub, torch, NumPy adapter details, and `sqlite-vec` stay behind adapter boundaries.
The `qwen3-embedding-0.6b-exact-v1` compatibility proof validates the exact
`Qwen/Qwen3-Embedding-0.6B` revision `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`, cache-only CPU
float32 loading, zero truncation for the frozen 70-page corpus, deterministic vectors, exact-cosine
ordering, and the amended resource ceilings. This proof does not change normal Search, Ask, MCP,
or the runtime default and does not approve a future API adapter, fusion, reranking, or promotion.

E3-C PR 2 adds a dense comparison evidence path, still off-default. It runs a two-phase protocol:
development first records `selected_threshold=0.58` in a committed development freeze, then exactly
one public holdout observation creates a holdout receipt and comparison artifact. The artifact
compares four arms: E3-A historical FTS5, `cjk-trigram-overlap-v1`,
`cjk-active-scan-overlap-v1`, and `qwen3-embedding-0.6b-exact-v1`. The result is
`candidate_status=completed`, `e3d_status=eligible`, and
`runtime_promotion_status=not_evaluated`. Eligibility means a future E3-D hybrid/RRF experiment
may be planned; it is not runtime promotion and does not change Search, Ask, MCP, owner startup,
SQLite domain truth, API adapters, RRF, reranking, query rewrite, HTTP, or UI.

E3-D adds a comparison-only RRF fusion artifact over the current
`cjk-active-scan-overlap-v1` runtime observations and the E3-C
`qwen3-embedding-0.6b-exact-v1` dense observations. It uses rank-only fusion and does not combine raw lexical and dense scores.
Development recorded `development_status=valid_negative` because
the fused unanswerable no-hit gate regressed, so holdout was not observed. This evidence does not
change Search, Ask, MCP, owner startup, SQLite domain truth, Publication, ingestion, or runtime
default behavior.

E3-E adds a comparison-only deterministic relevance gate and reranker artifact over the E3-D
lexical+dense union. It selects `strict-constraint` on development, records
`development_status=passed`, then observes holdout once after the exclusive development freeze.
Holdout records `holdout_gate_status=failed` and `runtime_promotion_status=not_evaluated` because
hard-negative failure remains above the current runtime comparator. E3-E is not a runtime strategy:
it does not read qrels, grades, query category labels, split labels, or expected locators as
candidate scoring input, and it does not change Search, Ask, MCP, owner startup, SQLite domain
truth, Publication, ingestion, runtime defaults, API reranker, LLM judge, local cross-encoder,
query rewrite, HyDE, segmentation, HTTP, or UI. No API reranker, LLM judge, local cross-encoder,
query rewrite, HyDE, or segmentation is approved by this artifact.

CLI and MCP errors share one project-owned `PublicError` serializer. Only allowlisted stable causes
can reach public output; unknown exception text is replaced with
`operation failed; details were redacted`. Public payloads contain `problem`, `cause`,
`active_publication_impact`, `next_step`, and an optional `run_id`, never local paths, argv, stderr,
cache locations, endpoints, secrets, or tracebacks.

## Versioned Evidence Provenance Snapshot

The additive v1 MCP read tools observe active Publications and return strict Evidence provenance.
They call unchanged retrieval, then bulk-enrich returned Evidence IDs from SQLite before the same
PEP 249 transaction closes. The graph gate compares Source active pointers and revisions,
Publication and published Run ownership, RunManifest counts and asset SHA-256, and active Evidence
ownership. Any missing or mismatched edge fails closed. `SearchResult`, CLI presentation, ranking,
evaluation, and the five legacy MCP contracts remain unchanged.

## Current Module Shape

```text
src/mke/
  runtime.py
  domain/
  application/
  adapters/
    embedding/
      sentence_transformers.py
    pdf/
    sqlite/
    vector/
      exact_cosine.py
      sqlite_vec.py
    video/
      faster_whisper.py
      faster_whisper_cli.py
      process.py
  embeddings/
    contracts.py
    readiness.py
  interfaces/
  proof/
    local_knowledge.py
    transcription.py
    mcp_deployment_client.py
  evaluation/
    manifest.py
    metrics.py
    numeric_artifact.py
    numeric_comparison.py
    chinese_artifact.py
    chinese_diagnostics.py
    chinese_protocol.py
    chinese_report.py
    chinese_runner.py
    dense_compatibility.py
    graded_metrics.py
    report.py
    runner.py
  retrieval/
    query_policy.py
  vector/
    contracts.py
```

The domain and application layers must not depend on FastAPI, database implementations, model SDKs, LangChain, or LlamaIndex.
