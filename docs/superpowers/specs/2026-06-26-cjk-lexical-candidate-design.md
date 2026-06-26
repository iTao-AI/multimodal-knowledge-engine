# CJK Lexical Candidate Design

Status: implemented as an off-default E3-B comparison. No runtime default behavior was changed.

## Context

E3-A merged as PR #29 and was closed out by PR #30. The squash-landed `main` baseline is
`bf7929694d91181dad9903eb001f816810871786`.

The canonical E3-A artifact reports:

| Metric | Current value |
|---|---:|
| Recall@1 | `0.227273` |
| Recall@3 | `0.295455` |
| Recall@5 | `0.295455` |
| MRR@5 | `0.261364` |
| nDCG@10 | `0.277279` |
| Answerable zero-hit | `0.681818` |
| Unanswerable no-hit | `0.500000` |
| Ask input rejection | `0.562500` |

The dominant failure mode is not semantic ranking. It is lexical coverage: `25` misses are
classified as `compiled_query_empty`, and E3-A marks E3-B `eligible` because development contains
`10` answerable `compiled_query_empty` misses.

## Problem

The current `numeric-grouping-v1` query compiler extracts ASCII/numeric tokens. Chinese-only
queries often produce no FTS5 `MATCH` expression, so Search returns zero rows before ranking can
matter.

E3-B should test the smallest deterministic lexical change that addresses this specific failure
mode without moving the project to embeddings, hybrid retrieval, RRF, reranking, query rewrite, or
runtime default promotion.

## Selected Candidate

Candidate identifier: `cjk-trigram-overlap-v1`

Revision: `1`

The candidate is a comparison-only lexical fallback:

1. Run the current `numeric-grouping-v1` compilation path.
2. If the current compiled query is non-empty, preserve the current Search result path.
3. If the current compiled query is empty, evaluate a CJK trigram-overlap projection.
4. Record current and candidate observations side by side in a canonical comparison artifact.

The candidate is intentionally narrow. It targets the exact E3-A failure class while preserving
E1/E2 behavior and current mixed ASCII/identifier/numeric retrieval semantics.

## Candidate Semantics

### Projection

The implementation creates an evaluation-only FTS5 projection using SQLite's built-in `trigram`
tokenizer when available in the installed Python SQLite runtime. It does not alter
`active_evidence_fts`, does not rebuild the normal active Publication projection, and does not
change runtime defaults.

Projection rows are copied from the active Evidence snapshot produced by the E3-A fixture ingest:

- stable Evidence identity;
- source and publication identity;
- locator kind/start/end;
- page text;
- deterministic row order.

The projection is valid only if its row count and aggregate text digest match the active Evidence
snapshot used by the current baseline.

### Query Terms

The CJK component derives deterministic query terms:

- CJK runs are normalized by removing whitespace and using Unicode case folding.
- Runs of length `>= 3` produce unique overlapping 3-character shingles.
- ASCII/numeric terms use the current compiler semantics for specificity diagnostics but do not
replace the current path for mixed queries.
- Runs too short for trigram matching are recorded as diagnostics, not silently treated as hits.

All generated terms are quoted before entering FTS5. Raw user query text is never interpolated into
SQL.

### Candidate Pool

For compiled-empty queries, the candidate retrieves a trigram candidate pool using an `OR` query
over generated terms. The implementation must bind the FTS5 `MATCH` expression as a parameter and
must record:

- generated terms;
- omitted below-minimum terms;
- pool row count;
- SQL trace proving exactly one candidate `MATCH` query for the projection;
- projection tokenizer identity.

### Overlap Filter And Ranker

The final candidate list is not raw FTS5 trigram rank. It applies a deterministic project-owned
overlap filter over the frozen page text:

| Parameter | Frozen value |
|---|---:|
| `minimum_overlap_count` | `2` |
| `minimum_overlap_ratio` | `0.30` |
| `max_results` | `10` |

For each candidate page, the scorer counts unique generated query terms present in the normalized
page text. A page is retained only when both thresholds pass.

Ranking order:

1. overlap count descending;
2. overlap ratio descending;
3. FTS5 `rank` ascending;
4. document ID ascending;
5. locator start ascending;
6. Evidence ID ascending.

This keeps SQLite trigram as a deterministic candidate generator and keeps the final decision
auditable in Python.

## Development-Only Planning Probe

A local read-only development probe on the E3-A development partition, with holdout untouched, found
the selected fallback shape plausible:

| Strategy | Development Recall@5 | Unanswerable no-hit | Hard-negative failures | Recovered compiled-empty misses |
|---|---:|---:|---:|---:|
| current | `8/22` (`0.363636`) | `1/2` | `1/2` | `0` |
| raw trigram-overlap for all queries | `17/22` (`0.772727`) | `2/2` | `0/2` | `7` |
| trigram-overlap fallback only for compiled-empty queries | `15/22` (`0.681818`) | `1/2` | `1/2` | `7` |

The fallback-only candidate is selected despite the lower development Recall@5 because it preserves
the current path for ASCII, numeric, and mixed-language queries. Raw trigram-overlap for every query
is rejected for E3-B because it would expand E3-B from a targeted CJK coverage candidate into a
broader replacement ranking strategy.

The probe is not a checked-in observation and is not promotion evidence. The implementation must
produce its own canonical artifact from the frozen protocol.

## Gates

### Integrity Gates

The implementation must fail closed unless all gates pass:

- E3-A baseline artifact validates on the current branch.
- E1 and E2 artifacts validate and retain semantic equality except duration/environment fields.
- E3-A protocol, qrel adjudication, fixture bytes, and locator inventory are unchanged.
- SQLite `trigram` tokenizer support is detected in Python 3.12 and Python 3.13 installed-wheel
  environments, or the candidate exits with a stable unsupported-runtime error.
- Candidate projection row count and aggregate text digest match the active Evidence snapshot.
- Candidate SQL trace proves parameterized `MATCH` usage and one projection query per candidate
  search.
- The artifact validator independently rebuilds the projection and recomputes candidate results
  from frozen fixture text.
- Development and holdout observations are deterministic across two fresh workspaces.

### Development Candidate Gates

Before holdout is observed, the implementation must freeze and enforce these development gates:

| Gate | Required result |
|---|---:|
| Development answerable Recall@5 | `>= 0.65` |
| Development Recall@5 absolute delta vs current | `>= +0.25` |
| Development compiled-empty answerable misses recovered | `>= 6` of `10` |
| Development unanswerable no-hit | `>= current` |
| Development hard-negative failures | `<= current` |
| Proper noun / mixed query Recall@5 | `>= current` |
| E1/E2 semantic equality | unchanged |

If any development gate fails, the candidate artifact records `candidate_status=failed` and no
runtime promotion is proposed.

### Holdout Observation Gates

Holdout is observed only after candidate semantics and development gates are frozen.

The holdout result can support later E3-C/E3-D planning only if:

- holdout Recall@5 is not lower than current;
- holdout nDCG@10 is not lower than current;
- holdout unanswerable no-hit is not lower than current;
- holdout hard-negative failures are not higher than current;
- no fixture, qrel, or protocol identity changes occur after development gates are locked.

These gates do not promote the candidate to runtime default. They only determine whether later dense
or fusion work has a credible lexical baseline.

## Non-Goals

E3-B does not:

- change the runtime default retrieval policy;
- add embeddings, vector search, hybrid retrieval, RRF, reranking, or query rewrite;
- add `jieba`, external tokenizers, model downloads, services, or network access;
- change E1, E2, or E3-A canonical artifacts except to revalidate them;
- expose a new HTTP, MCP, or product API;
- claim general Chinese production quality.

## Recommendation

The implementation records `cjk-trigram-overlap-v1` as an off-default E3-B comparison artifact.
The canonical comparison reports `candidate_status=passed`, overall Recall@5 `0.659091`, and
nDCG@10 `0.610619`, with all frozen development and holdout gates passing. It does not promote the
candidate to runtime default and does not migrate legacy RAG-OCR code.
