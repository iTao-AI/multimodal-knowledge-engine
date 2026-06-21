# Retrieval Evaluation Baseline Design

## Status

- Stage: Completed and merged through
  [PR #23](https://github.com/iTao-AI/multimodal-knowledge-engine/pull/23).
- Slice: E1.
- Design date: 2026-06-20.
- Merge date: 2026-06-21.
- Merge commit:
  [`98f02cca11d88e081106a89889a4f60376fad217`](https://github.com/iTao-AI/multimodal-knowledge-engine/commit/98f02cca11d88e081106a89889a4f60376fad217).
- Depends on: the completed PDF/video lifecycle, evidence-only Ask, MCP contract, product proof,
  real PDF intake, and D3-B local transcription milestones.

## Goal

Build a deterministic, offline retrieval-evaluation baseline for the current active-Publication
FTS5 implementation.

E1 must answer a question that the existing product proof intentionally does not answer:

> Given fixed public English PDF and video Evidence, how well does the current retrieval path find
> the correct page or timestamp, and how often does evidence-only Ask refuse an unanswerable query?

E1 records the current behavior honestly. It does not improve retrieval, set an arbitrary quality
target, or turn a baseline score into a product claim. Its 16 answerable queries give a coarse
macro signal: one query moves an answerable rate by 6.25 percentage points. E1 can expose large
lexical failure classes and regressions, but it cannot resolve small quality differences.

## Current State

MKE already proves:

- text-layer PDF and short-video ingest,
- page- and timestamp-addressed Evidence,
- active-Publication-only Search and Ask,
- failed reprocessing isolation,
- deterministic CLI-equivalent and MCP contract behavior through `mke proof run`,
- optional real local transcription through the completed D3-B slice.

The current retrieval implementation is still intentionally narrow:

- SQLite FTS5 is the only active retrieval projection.
- Query normalization extracts ASCII alphanumeric and underscore terms.
- Multi-term queries use the current FTS5 conjunction behavior.
- Search ordering uses the current FTS5 rank, locator start, and Evidence ID tie-breakers.
- Evidence-only Ask delegates to Search and returns either matched Evidence or
  `insufficient_evidence`.
- No repository-visible query set, qrels, Recall@k, MRR, false-positive baseline, or retrieval
  quality report exists.

`mke proof run` remains a lifecycle and contract proof. E1 adds a separate evaluation surface so
product correctness and retrieval quality are not conflated.

## Chosen Approach

Add a project-owned evaluation package and a formal CLI entrypoint:

```text
mke eval retrieval --manifest MANIFEST.json
mke eval retrieval --manifest MANIFEST.json --json
```

The checked-in E1 manifest uses:

- two small, redistribution-safe, text-layer English USGS PDF fact sheets,
- the existing deterministic short-video fixture and transcript sidecar,
- 24 manually reviewed queries,
- binary page/timestamp qrels,
- two fresh temporary SQLite workspaces per run.

The command ingests the corpus through the normal application service, verifies every qrel against
published active Evidence, evaluates Search and Ask, compares both fresh runs for deterministic
ordered locator results, calculates baseline metrics, and emits a public-safe report.

Low Recall, MRR, or refusal performance does not fail E1. Integrity, completeness, locator
correctness, and determinism failures do.

The checked-in corpus remains repository data rather than wheel package data. Source-tree and
wheel-installed commands both accept an explicit external manifest path; the wheel gate proves
installed-code identity and path independence, not that the benchmark corpus is bundled into the
package.

## Rejected Alternatives

| Alternative | Decision | Reason |
|---|---|---|
| Add retrieval cases to `mke proof run` | Rejected | Product correctness and quality measurement have different failure semantics. |
| Improve FTS5 while introducing the evaluation harness | Rejected | The first report must measure the unmodified baseline. |
| Introduce `sqlite-vec`, RRF, or reranking in E1 | Rejected | Algorithm selection must follow evidence from the baseline. |
| Use private learning material | Rejected for E1 | The baseline must be repository-visible and independently reproducible. |
| Download fixtures during CI | Rejected | Upstream availability or content drift must not change required checks. |
| Generate all PDF content locally | Rejected | Public real-world text-layer PDFs provide a more meaningful extraction and retrieval baseline. |
| Use graded relevance in the first manifest | Deferred | Binary exact-locator qrels are less subjective and directly test MKE Evidence identity. |
| Snapshot exact floating-point scores as the only CI assertion | Rejected | It produces brittle approval tests and hides whether a change is actually better or worse. |
| Bundle the benchmark corpus into the wheel | Rejected for E1 | The evaluator supports explicit external manifests; test assets and public PDFs remain repository data. |
| Reuse `mke.proof` report or runner DTOs | Rejected | Product proof and retrieval evaluation have different sequencing, metrics, and failure semantics; a shared base would be premature. |

## Corpus

### Directory Layout

The checked-in assets live under the fixture root:

```text
tests/fixtures/
  retrieval-eval-v1.json
  eval/
    retrieval/
      README.md
      usgs-volcano-hazards.pdf
      usgs-water-use-2005.pdf
  video/
    short-audio.mp4
    short-audio.mp4.mke-transcript.json
```

All manifest paths are relative to the manifest directory. Absolute paths and `..` path segments
are invalid. Resolved corpus and supporting-file paths must remain below the manifest directory.

### PDF 1: Volcano Hazards

- Title: `What are Volcano Hazards?`
- Publisher: U.S. Geological Survey.
- Source:
  `https://pubs.usgs.gov/fs/fs002-97/fs00297.pdf`
- Pages: 2.
- Expected size: 563,382 bytes.
- SHA-256:
  `bdb8a5b6c648194e0fcc6f932b70976350bdc864c8187632c47f0cb64a21da4e`.
- Verified text-layer character counts at design time: 5,842 and 8,626.

### PDF 2: Water Use

- Title: `Summary of Estimated Water Use in the United States in 2005`
- Publisher: U.S. Geological Survey.
- Publication page:
  `https://pubs.usgs.gov/fs/2009/3098/`
- Source:
  `https://pubs.usgs.gov/fs/2009/3098/pdf/2009-3098.pdf`
- Pages: 2.
- Expected size: 400,168 bytes.
- SHA-256:
  `ef27346a9f2eab19d438a0740d43c606a9b739147e09d89d1121df294ed3c585`.
- Verified text-layer character counts at design time: 6,755 and 9,716.

### Redistribution Record

USGS states that USGS-authored or produced reports and information are in the U.S. public domain
and asks users to acknowledge USGS as the source:

- `https://www.usgs.gov/faqs/are-usgs-reportspublications-copyrighted`
- `https://www.usgs.gov/information-policies-and-instructions/acknowledging-or-crediting-usgs`

The exact candidate PDFs had no extractable `copyright`, `courtesy`, `photo by`, or equivalent
third-party rights label during design inspection. The implementation must preserve the exact
checksums above and add a fixture README containing:

- title,
- publisher,
- source URL,
- retrieval date,
- public-domain policy URL,
- requested USGS attribution,
- byte size,
- page count,
- SHA-256,
- a statement that the fixture is used for deterministic retrieval evaluation.

If the exact downloaded bytes do not match the approved checksum, implementation must stop rather
than silently accept a newer upstream file.

### Video Document

E1 reuses:

- `tests/fixtures/video/short-audio.mp4`
- `tests/fixtures/video/short-audio.mp4.mke-transcript.json`

The video remains sidecar-backed so the retrieval baseline is model-free and does not mix ASR
variance with Search quality. `spoken-evidence.mp4` remains part of the separate D3-B real-ASR
proof and is not an E1 corpus document.

The manifest records checksums for both the MP4 and its transcript sidecar because either file can
change the resulting timestamp Evidence.

## Manifest Contract

E1 uses JSON and does not add a YAML dependency.

The checked-in manifest is named `retrieval-eval-v1` and has this conceptual shape:

```json
{
  "schema_version": "mke.retrieval_eval.v1",
  "manifest_id": "retrieval-eval-v1",
  "documents": [
    {
      "document_id": "usgs-volcano-hazards",
      "media_type": "application/pdf",
      "primary_file": {
        "path": "eval/retrieval/usgs-volcano-hazards.pdf",
        "sha256": "bdb8a5b6c648194e0fcc6f932b70976350bdc864c8187632c47f0cb64a21da4e",
        "bytes": 563382
      },
      "supporting_files": []
    },
    {
      "document_id": "short-video-timestamp-proof",
      "media_type": "video/mp4",
      "primary_file": {
        "path": "video/short-audio.mp4",
        "sha256": "4e3c9feffa503e193165ddf27c40c0e0edf9f256c2e8e1e2d863bd7ba3e1fe49",
        "bytes": 13025
      },
      "supporting_files": [
        {
          "role": "transcript_sidecar",
          "path": "video/short-audio.mp4.mke-transcript.json",
          "sha256": "5688603821b9262f85592912ef957d852ea34448e7292c927ea5071a0668e995",
          "bytes": 506
        }
      ]
    }
  ],
  "queries": [
    {
      "query_id": "volcano-answerable-01",
      "text": "volcanic ash aircraft",
      "category": "answerable",
      "relevant_locators": [
        {
          "document_id": "usgs-volcano-hazards",
          "locator_kind": "page",
          "locator_start": 1,
          "locator_end": 1
        }
      ]
    }
  ]
}
```

### Validation Rules

- `schema_version` must equal `mke.retrieval_eval.v1`.
- `manifest_id`, document IDs, query IDs, supporting-file roles, and category names use bounded
  lowercase ASCII identifiers with hyphens or underscores.
- Document IDs and query IDs are unique.
- Documents use only supported `application/pdf` and `video/mp4` media types.
- File paths are non-empty relative POSIX paths without `..`; resolution must remain below the
  manifest directory.
- SHA-256 values are exactly 64 lowercase hexadecimal characters.
- Expected byte sizes are positive integers.
- The manifest contains 1–32 documents, 2–1,000 queries, at least one answerable query, and at
  least one unanswerable query.
- The total declared fixture size is at most 100 MiB.
- Each document has one primary file.
- A video document used by the sidecar provider has exactly one `transcript_sidecar`.
- The video sidecar path is exactly `<primary path>.mke-transcript.json`.
- Primary paths and primary SHA-256 values are unique so application-level Asset deduplication
  cannot collapse two manifest documents into one Source.
- Query text is non-empty, at most 1,000 characters, and contains at least one currently searchable
  ASCII token.
- Query categories are exactly `answerable`, `lexical_confuser`, or `out_of_corpus`.
- `answerable` queries have one or more relevant locators.
- `lexical_confuser` and `out_of_corpus` queries have no relevant locators.
- Locators use project-owned `page` or `timestamp_ms` kinds with valid positive page numbers or
  non-negative timestamp ranges.
- Every qrel document ID exists in the same manifest.

Unknown fields are rejected so a misspelled evaluation requirement cannot be silently ignored.

## Query Set

The first manifest contains exactly 24 manually reviewed English queries:

| Group | Count | Expected qrels |
|---|---:|---|
| Volcano PDF answerable | 6 | One or more exact page locators |
| Water-use PDF answerable | 6 | One or more exact page locators |
| Short-video answerable | 4 | One or more exact timestamp locators |
| Lexical-confuser unanswerable | 4 | Empty |
| Out-of-corpus unanswerable | 4 | Empty |

The query set must include:

- exact terminology,
- short natural-language phrases,
- multi-term queries,
- at least one answerable query with multiple relevant locators,
- lexical-confuser queries that share terms with the corpus but whose requested fact is absent,
- unrelated out-of-corpus queries.

The approved queries were written by inspecting the exact asset bytes. They do not depend on
web-page text that is absent from the PDF or sidecar.

### Approved Query And Qrel Inventory

The query text and qrels are frozen before baseline implementation so the benchmark cannot be
tuned after seeing current FTS5 results.

| Query ID | Category | Query text | Relevant locator |
|---|---|---|---|
| `volcano-answerable-01` | `answerable` | `eruption clouds aviation` | Volcano PDF, page 1 |
| `volcano-answerable-02` | `answerable` | `volcanic gas acid rain` | Volcano PDF, page 1 |
| `volcano-answerable-03` | `answerable` | `Mount St Helens eruption` | Volcano PDF, pages 1 and 2 |
| `volcano-answerable-04` | `answerable` | `basalt lava fast moving streams` | Volcano PDF, page 2 |
| `volcano-answerable-05` | `answerable` | `pyroclastic flows valleys` | Volcano PDF, page 2 |
| `volcano-answerable-06` | `answerable` | `lahars wet concrete` | Volcano PDF, page 2 |
| `water-answerable-01` | `answerable` | `410000 million gallons withdrawals` | Water-use PDF, page 1 |
| `water-answerable-02` | `answerable` | `California irrigation withdrawals` | Water-use PDF, page 1 |
| `water-answerable-03` | `answerable` | `self supplied domestic 42.9 million people` | Water-use PDF, page 1 |
| `water-answerable-04` | `answerable` | `thermoelectric once through cooling` | Water-use PDF, page 2 |
| `water-answerable-05` | `answerable` | `water use trends 1950 2005` | Water-use PDF, page 2 |
| `water-answerable-06` | `answerable` | `public supply increased steadily` | Water-use PDF, page 2 |
| `video-answerable-01` | `answerable` | `video evidence timestamp` | Video, 0–1,200 ms |
| `video-answerable-02` | `answerable` | `timestamp search` | Video, 0–1,200 ms and 1,200–2,200 ms |
| `video-answerable-03` | `answerable` | `active publication spoken` | Video, 1,200–2,200 ms |
| `video-answerable-04` | `answerable` | `finds spoken timestamp proof` | Video, 1,200–2,200 ms |
| `confuser-01` | `lexical_confuser` | `volcano evacuation shelter locations` | None |
| `confuser-02` | `lexical_confuser` | `Mount St Helens casualty count` | None |
| `confuser-03` | `lexical_confuser` | `California groundwater contamination 2005` | None |
| `confuser-04` | `lexical_confuser` | `timestamp proof speaker identity` | None |
| `out-of-corpus-01` | `out_of_corpus` | `photosynthesis chlorophyll wavelength` | None |
| `out-of-corpus-02` | `out_of_corpus` | `Roman empire tax policy` | None |
| `out-of-corpus-03` | `out_of_corpus` | `quantum entanglement photon experiment` | None |
| `out-of-corpus-04` | `out_of_corpus` | `database transaction isolation levels` | None |

The exact manifest uses:

- `document_id="usgs-volcano-hazards"` for both volcano pages,
- `document_id="usgs-water-use-2005"` for both water-use pages,
- `document_id="short-video-timestamp-proof"` for both video segments,
- `locator_kind="page"` with one-based page numbers,
- `locator_kind="timestamp_ms"` with the exact start and end values shown above.

### Design-Time Feasibility Preflight

Before approving this spec, the exact candidate PDF bytes and existing video fixture were ingested
twice into fresh temporary SQLite workspaces using the current unmodified application service.
The 24 approved queries produced identical ordered stable locator results across both workspaces.

This preflight confirms that the determinism gate is reachable without changing Search behavior.
It is not the official E1 baseline because the versioned manifest, report contract, integrity
checks, and committed corpus assets do not exist yet.

## Qrel Identity

Relevance is binary and locator-specific:

```text
document_id + locator_kind + locator_start + locator_end
```

Evaluation never compares random Run, Source, Publication, or Evidence IDs. During each fresh run,
the runner maps runtime Source/Evidence records back to stable manifest document IDs and compares
only the stable locator identity.

One query may have multiple relevant locators. A retrieved item counts as relevant only when all
four identity fields match an approved qrel.

E1 requires exactly one active Evidence row per stable locator. This makes Recall and MRR
unambiguous for the current page/segment Evidence model. If later Passage chunking produces
multiple searchable rows for one page or timestamp range, comparison with
`retrieval-eval-v1` is invalid until a new manifest/report version defines deduplication or
Passage-level qrels.

## Evaluation Data Flow

```text
manifest path
  -> parse strict JSON
  -> validate schema, IDs, paths, limits, checksums, and byte sizes
  -> copy and revalidate exact fixture bytes in an evaluator-owned snapshot
  -> create fresh temporary SQLite workspace A
  -> ingest all documents through KnowledgeEngine
  -> require every Run to reach published
  -> map manifest document IDs to active Source/Evidence
  -> validate every answerable qrel resolves to active Evidence
  -> run Search at limit 5 for all queries
  -> run evidence-only Ask at limit 5 for all queries
  -> calculate query outcomes and aggregate metrics
  -> repeat in fresh temporary SQLite workspace B
  -> compare ordered stable locator results and aggregate values
  -> emit one public-safe report
```

All corpus documents are ingested before queries run. E1 measures cross-document retrieval in one
Library, not isolated one-document searches.

The runner uses the same `KnowledgeEngine.search()` and `KnowledgeEngine.ask()` methods as current
CLI and MCP behavior. It must not reproduce FTS SQL or add evaluation-only query rewriting.

The immutable snapshot closes the interval between validation and ingest. Both fresh workspaces
ingest the same staged bytes, and MP4/sidecar adjacency is preserved.

## Metrics

E1 records:

- `locator_recall_at_1`
- `locator_recall_at_3`
- `locator_recall_at_5`
- `mrr_at_5`
- `answerable_zero_hit_rate`
- `unanswerable_no_hit_rate`
- `ask_refusal_rate`
- counts grouped by query category

### Definitions

For an answerable query with relevant set `R` and the first `k` ordered results `S_k`:

```text
locator_recall@k = |R intersect S_k| / |R|
```

Aggregate Recall@k is the arithmetic mean over answerable queries.

`MRR@5` uses the reciprocal rank of the first relevant locator in the first five results, or zero
when none is found, averaged over answerable queries.

`answerable_zero_hit_rate` is the fraction of answerable queries whose Search returns no results.

`unanswerable_no_hit_rate` is the fraction of lexical-confuser and out-of-corpus queries whose
Search returns no results.

`ask_refusal_rate` is the fraction of unanswerable queries whose Ask result is
`insufficient_evidence`.

In E1, Ask delegates to Search with the same query and limit, so `ask_refusal_rate` is a derived
contract observation and must equal `unanswerable_no_hit_rate`. It is retained to verify the
public Ask contract, not presented as an independent answer-quality metric. The runner fails
integrity if Search emptiness and Ask status disagree.

`lexical_confuser` and `out_of_corpus` qrels intentionally encode expected exact-fact retrieval as
empty. Their no-hit rate is not a general topical-relevance judgment.

Metrics are rounded to six decimal places for serialized output. Each metric also includes its
unrounded per-query sum and query count so the macro average remains auditable. Rate metrics use
zero-or-one per-query values, so their sum is also the number of queries satisfying the condition.

Duration is diagnostic only and is not a performance metric or quality gate.

## Hard Gates And Exit Codes

E1 separates evaluation integrity from quality observations.

The command exits `1` when any of these integrity gates fails:

- invalid or unreadable manifest,
- schema, ID, category, path, checksum, or byte-size validation failure,
- missing primary or supporting fixture,
- fixture bytes change while the evaluator creates its immutable snapshot,
- a document Run does not reach `published`,
- a qrel references a locator that does not exist in active Evidence,
- more than one active Evidence row maps to the same stable locator,
- a query or document is skipped,
- Ask status disagrees with Search emptiness under the current evidence-only contract,
- the two fresh runs produce different ordered stable locator results,
- the two fresh runs produce different non-duration aggregate values,
- report serialization fails,
- normal CLI output exposes an absolute path, raw Evidence text, full document content, traceback,
  secret, host identity, or environment-specific temporary name.

The command exits `0` when all integrity gates pass, regardless of measured retrieval scores.

Success uses:

```text
status=passed
quality_status=baseline_recorded
```

Exit codes:

| Code | Meaning |
|---|---|
| `0` | Evaluation completed, integrity gates passed, and baseline metrics were recorded. |
| `1` | Evaluation did not produce a trustworthy complete baseline. |
| `2` | CLI usage or argument parsing error. |

E1 does not introduce `quality_status=passed` or a minimum Recall/MRR threshold.

## Public Report Contract

Human output begins with the command header, one scope line, and one aggregate line:

```text
mke eval retrieval
scope=small_english_page_timestamp_corpus quality_gate=none
evaluation=retrieval manifest=retrieval-eval-v1 status=passed quality_status=baseline_recorded documents=3 queries=24 answerable=16 unanswerable=8 locator_recall_at_1=0.000000 locator_recall_at_3=0.000000 locator_recall_at_5=0.000000 mrr_at_5=0.000000 answerable_zero_hit_rate=0.000000 unanswerable_no_hit_rate=0.000000 ask_refusal_rate=0.000000
```

It then prints one bounded line per query using stable IDs and locator summaries, followed by any
integrity failures. The zero metric values above illustrate formatting and are not expected E1
scores.

JSON has this conceptual shape:

```json
{
  "evaluation": "retrieval",
  "schema_version": "mke.retrieval_eval_report.v1",
  "manifest_id": "retrieval-eval-v1",
  "benchmark_scope": "small_english_page_timestamp_corpus",
  "quality_gate": "none",
  "status": "passed",
  "quality_status": "baseline_recorded",
  "documents": 3,
  "queries": 24,
  "answerable": 16,
  "unanswerable": 8,
  "metrics": {
    "locator_recall_at_1": {"value": 0.0, "sum": 0.0, "count": 16},
    "locator_recall_at_3": {"value": 0.0, "sum": 0.0, "count": 16},
    "locator_recall_at_5": {"value": 0.0, "sum": 0.0, "count": 16},
    "mrr_at_5": {"value": 0.0, "sum": 0.0, "count": 16},
    "answerable_zero_hit_rate": {"value": 0.0, "sum": 0.0, "count": 16},
    "unanswerable_no_hit_rate": {"value": 0.0, "sum": 0.0, "count": 8},
    "ask_refusal_rate": {"value": 0.0, "sum": 0.0, "count": 8}
  },
  "category_counts": {
    "answerable": 16,
    "lexical_confuser": 4,
    "out_of_corpus": 4
  },
  "results": [
    {
      "query_id": "volcano-answerable-01",
      "category": "answerable",
      "relevant_locator_count": 1,
      "retrieved_locator_count": 5,
      "relevant_retrieved_at_1": 1,
      "relevant_retrieved_at_3": 1,
      "relevant_retrieved_at_5": 1,
      "first_relevant_rank": 1,
      "ask_status": "evidence_found",
      "retrieved_locators": [
        {
          "document_id": "usgs-volcano-hazards",
          "locator_kind": "page",
          "locator_start": 1,
          "locator_end": 1
        }
      ]
    }
  ],
  "integrity_failures": [],
  "duration_ms": 12
}
```

The zero values above illustrate types, not expected E1 scores.

Reports must not echo:

- query text,
- absolute manifest or fixture paths,
- random domain IDs,
- Evidence text,
- document text,
- raw exceptions,
- local usernames,
- temporary directory names,
- environment variables,
- dependency cache paths.

Query text remains in the operator-supplied manifest and test fixtures but not in normal report
output, allowing the same contract to evaluate a private local manifest later without copying its
queries into logs.

## Error Contract

Evaluation failures use stable public fields:

```text
problem
cause
next_step
```

Expected stable problems include:

- `retrieval_eval_manifest_invalid`
- `retrieval_eval_fixture_invalid`
- `retrieval_eval_ingest_failed`
- `retrieval_eval_qrel_invalid`
- `retrieval_eval_incomplete`
- `retrieval_eval_nondeterministic`

Stable causes may name a manifest document ID, query ID, field name, expected checksum, or
repository-relative fixture key. They must not include absolute paths or raw exception messages.
Unknown exceptions use the existing redacted fallback.

## Architecture And File Boundaries

E1 adds:

```text
src/mke/evaluation/
  __init__.py
  manifest.py
  metrics.py
  report.py
  runner.py
```

Responsibilities:

- `manifest.py`: strict JSON parsing, immutable evaluation DTOs, path/checksum validation.
- `metrics.py`: pure binary-qrel metric calculations with no storage or filesystem access.
- `report.py`: immutable result/report DTOs plus public-safe
  `render_retrieval_human_report` and `render_retrieval_json_report` serialization.
- `runner.py`: two-workspace orchestration, normal ingest/Search/Ask calls, stable runtime-to-
  manifest identity mapping, integrity gates, and determinism comparison.
- `cli.py`: argument parsing and delegation only.

The evaluator needs to prove that every qrel resolves to currently published Evidence, including
qrels that Search does not return. E1 therefore adds a project-owned `ActiveEvidenceRef` DTO and
one read-only `KnowledgeEngine.list_active_evidence()` method backed by
`SQLiteStore.list_active_evidence()`. The DTO contains only `source_id`, `locator_kind`,
`locator_start`, and `locator_end`; it does not carry Evidence text or random Evidence/Publication
IDs. The method returns only Evidence belonging to each Source's active Publication in stable
locator order. This method is an internal diagnostics/evaluation seam: it is not exposed through
CLI, MCP, or a new public service contract, and it must not alter the existing Search SQL or
ordering.

Evaluation code may depend on project-owned domain/application contracts. Domain and application
code must not depend on evaluation code.

E1 must not:

- change `SQLiteStore.search`,
- change `_to_fts_query`,
- change Search ordering,
- change Ask validation or answer statuses,
- add an evaluation-only retrieval adapter,
- add an embedding dependency,
- add network access.

## Testing Strategy

### Unit Tests

- strict manifest parsing and unknown-field rejection,
- duplicate and malformed IDs,
- invalid paths and root escape prevention,
- checksum and byte-size mismatch,
- manifest count/size bounds, duplicate Asset identity, and sidecar adjacency,
- immutable fixture snapshot identity,
- invalid categories and qrel cardinality,
- pure Recall@1/3/5 and MRR@5 calculations,
- multiple relevant locators,
- zero-hit and unanswerable rates,
- Search/Ask consistency for the derived refusal metric,
- six-decimal serialization,
- report redaction.

### Integration Tests

- ingest all three checked-in documents into one temporary Library,
- resolve every answerable qrel to active Evidence,
- evaluate all 24 queries,
- run the complete evaluation twice and compare stable ordered locators,
- verify random Run/Evidence IDs do not affect comparison,
- verify a corrupted fixture fails before ingest,
- verify a fixture mutation during snapshot fails closed,
- verify a nonexistent qrel fails after ingest,
- verify duplicate active stable locators fail closed,
- verify low synthetic metrics still return success when integrity passes,
- verify skipped or partially executed queries fail closed.

### CLI Contract Tests

- human success output,
- JSON success output,
- renderer failure fallback for human and JSON modes,
- exit `1` for integrity failure,
- exit `2` for usage errors,
- explicit rejection of global `--db` for evaluation,
- no traceback or absolute path,
- no query or Evidence text in reports.

### Regression Protection

Required CI runs the checked-in manifest through the public CLI. CI asserts:

- exit `0`,
- `status=passed`,
- `quality_status=baseline_recorded`,
- three documents,
- 24 queries,
- 16 answerable queries,
- eight unanswerable queries,
- no integrity failures.

CI prints the current metrics and validates the checked-in canonical baseline artifact's schema and
provenance, but does not compare current scores to that artifact or assert exact score values in
E1.

## Documentation

The implementation PR updates:

- `README.md` and `README_CN.md` with the distinction between product proof and retrieval
  evaluation,
- `docs/README.md`,
- `docs/reference/cli.md`,
- a new `docs/how-to/run-retrieval-evaluation.md`,
- `benchmarks/retrieval/retrieval-eval-v1-baseline.json`,
- fixture provenance in `tests/fixtures/eval/retrieval/README.md`,
- the E1 implementation plan and durable review.

The baseline document records:

- exact Git commit,
- manifest ID and fixture checksums,
- manifest checksum plus Python, SQLite, and PyMuPDF versions,
- actual metric values,
- every answerable query with no relevant locator at rank 5,
- category-level misses and false positives,
- what the baseline proves,
- what it does not prove,
- the next algorithm decision that the evidence supports.

The canonical JSON artifact omits duration, raw content, paths, and random IDs. It is a reviewed
observation, not a CI threshold. The baseline document must not describe an observed score as a
stable product metric until the query set, corpus, evaluation protocol, and Evidence segmentation
are versioned and unchanged.

## Non-Goals

E1 does not implement:

- Unicode or CJK tokenization,
- OR-query policy changes,
- query rewriting,
- semantic embeddings,
- `sqlite-vec`,
- hybrid retrieval,
- RRF,
- reranking,
- generated answers,
- graded qrels or nDCG,
- private corpus ingestion,
- network fixture acquisition,
- scanned-PDF OCR,
- real-ASR quality evaluation,
- latency or throughput benchmarking,
- HTTP, workspace UI, or hosted evaluation services.

## Acceptance Criteria

E1 is complete when:

1. The exact approved PDFs and existing sidecar-backed video assets are represented in a strict
   offline manifest with verified checksums and provenance.
2. The manifest contains exactly 24 reviewed queries with the approved category distribution.
3. Every answerable qrel resolves to active page or timestamp Evidence after normal ingest.
4. `mke eval retrieval --manifest tests/fixtures/retrieval-eval-v1.json` completes two fresh runs,
   verifies deterministic ordered locators, and exits `0`.
5. Human and JSON reports expose complete baseline metrics without query text, raw Evidence,
   absolute paths, random IDs, or private environment details.
6. Corrupt fixtures, invalid qrels, incomplete runs, and nondeterministic results fail closed with
   stable errors and exit `1`.
7. Required CI runs the public CLI and gates evaluation integrity without freezing exact quality
   scores.
8. A public-safe canonical JSON artifact records the manifest/fixture/environment identity,
   observed metrics, and per-query outcomes without becoming a score gate.
9. The implementation PR records the observed FTS5 baseline and its known misses without changing
   retrieval behavior.
10. The existing full test suite, Ruff, Pyright, build, product proof, demo, and model-free package
   gates remain green.

## Follow-Up Decision

After E1 records the baseline, the next design may use the same versioned manifest as a regression
suite for English retrieval changes that preserve page/timestamp Evidence segmentation. The E1
corpus can reveal coarse lexical failure classes, but it is not sufficient by itself to select or
validate CJK tokenization, semantic retrieval, fusion, or reranking.

A later candidate-comparison design must freeze an expanded development/holdout protocol before
tuning. It must add the query and corpus slices required by the decision under test, including a
separate CJK slice for Unicode/CJK work and hard negatives for ranking work. Candidate work may
then include:

- Unicode/CJK tokenization,
- explicit AND/OR query policy,
- semantic retrieval through a rebuildable adapter,
- `sqlite-vec`,
- RRF,
- reranking.

That later design must set improvement and regression gates from observed evidence, report
local-first resource cost changes, and avoid selecting and judging an algorithm only on the same
visible E1 queries. It must not assume hybrid retrieval is necessary before the baseline identifies
the actual failure modes.
