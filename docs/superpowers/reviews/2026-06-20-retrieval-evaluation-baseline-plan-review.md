# Retrieval Evaluation Baseline Autoplan Review

## Status

- Result: approved after plan corrections; implementation not started
- Review mode: CEO scope hold, engineering full review, developer-experience polish
- Independent voices: Codex and Claude for CEO, engineering, and DX
- Design review: skipped because E1 has no UI or visual surface

## Scope Verdict

E1 remains a deterministic offline observation and regression baseline for the current
active-Publication FTS5 path. It does not improve retrieval, add a retrieval dependency, or set a
quality threshold.

The review narrowed the decision claim. A 3-document, 24-query English corpus with 16 answerable
queries can expose coarse lexical failure classes and regressions, but it cannot by itself select
or validate CJK tokenization, semantic retrieval, fusion, or reranking. One answerable query changes
an answerable macro rate by 6.25 percentage points.

## Architecture Verdict

```text
external manifest + checksummed fixtures
                  |
                  v
 strict schema / bounds / path validation
                  |
                  v
 immutable validated fixture snapshot
                  |
        +---------+---------+
        |                   |
        v                   v
 fresh workspace A   fresh workspace B
        |                   |
 normal ingest -> active Publication/Evidence
        |                   |
 narrow ActiveEvidenceRef qrel validation
        |                   |
 current Search + current evidence-only Ask
        +---------+---------+
                  |
 ordered stable-locator and metric comparison
                  |
 public-safe report + canonical baseline artifact
```

The evaluation package remains separate from `mke.proof`. Product proof owns lifecycle and
CLI/MCP cases; retrieval evaluation owns external manifests, qrels, metrics, and two-workspace
comparison. A shared report or runner abstraction would be premature.

## Findings Incorporated

| # | Finding | Resolution |
|---|---|---|
| 1 | E1 was described as evidence for broad retrieval-algorithm selection. | Limited E1 to coarse English, segmentation-preserving observation/regression; later selection requires expanded development/holdout slices. |
| 2 | Active-Evidence enumeration reused `SearchResult`, carrying text and random IDs. | Added project-owned `ActiveEvidenceRef` with only Source and locator fields. |
| 3 | Fixture validation and later ingest had a mutation interval. | Added an evaluator-owned immutable snapshot, revalidation, sidecar adjacency, duplicate Asset identity rejection, and manifest bounds. |
| 4 | Ask refusal looked like an independent quality signal. | Kept it only as a derived public-contract observation and added Search/Ask consistency as an integrity gate. |
| 5 | Exact locator qrels become ambiguous after Passage chunking. | Required one active Evidence row per stable locator and declared new qrels/schema necessary when segmentation changes. |
| 6 | Wrong-result answerable failures were not part of the completion record. | Required reporting every answerable query with no relevant locator in the first five results. |
| 7 | Generic renderer names collided conceptually with `mke.proof`. | Renamed them to retrieval-specific renderer names. |
| 8 | Renderer failure was listed as a hard gate without a safe CLI boundary. | Added fixed redacted human/JSON fallbacks and exit `1`. |
| 9 | CI discarded the only machine-readable baseline. | Added a reviewed canonical JSON artifact with manifest, fixture, environment, metric, and per-query identity; no score gate. |
| 10 | Global `--db` could be silently ignored by evaluation. | Required explicit usage error for `--db` with `eval`. |
| 11 | Missing manifest and invalid JSON shared a misleading error. | Required distinct stable causes. |
| 12 | Small-corpus and no-quality-gate semantics were easy to miss. | Added scope and quality-gate fields to help, human output, JSON, README, and how-to requirements. |
| 13 | Existing video bytes were trusted only through the future manifest. | Added direct checksum and size tests for the MP4 and transcript sidecar. |
| 14 | A private restore-point path was temporarily present in the plan. | Removed it before public review output. |

## Decisions Not Adopted

| Proposal | Decision | Reason |
|---|---|---|
| Expand E1 to a large ranking benchmark | Deferred | It changes the approved baseline milestone and is not needed to measure current behavior honestly. |
| Add CJK, semantic, fusion, or reranking queries now | Deferred | Each requires a decision-specific corpus/query slice and should not be inferred from the English E1 set. |
| Split the 24 queries into development and holdout sets inside E1 | Deferred | E1 records the current baseline; the later candidate-comparison design must freeze expanded development/holdout sets before tuning. |
| Bundle PDFs and the manifest into the wheel | Rejected for E1 | The public command accepts an explicit external manifest; wheel CI verifies installed-code identity, not bundled benchmark data. |
| Make the checked-in manifest implicit | Rejected for E1 | Explicit input preserves provenance and supports repository or private manifests without hidden discovery. |
| Add `--compare`, `--output`, or quality thresholds | Deferred | The canonical JSON artifact and documented redirection are sufficient for E1. |
| Add graded relevance or Passage qrels | Deferred | Binary page/timestamp identity is the approved E1 contract; segmentation changes require a new evaluation version. |

## Verification Design

```text
fixture size/checksum/provenance
  -> strict manifest/bounds/path tests
  -> immutable snapshot and mutation tests
  -> active-Publication narrow DTO tests
  -> qrel existence and locator uniqueness tests
  -> pure metric and derived Ask-consistency tests
  -> public-safe renderer and renderer-fallback tests
  -> two-workspace integration tests
  -> CLI human/JSON/help/exit/--db tests
  -> source-tree and external-manifest wheel CI
  -> canonical artifact schema/provenance validation
  -> full suite / Ruff / Pyright / build / proof / demo
```

Quality values remain report-only. Integrity failures include invalid manifests, mismatched or
mutated fixtures, non-published ingest, missing or duplicate qrel locators, partial execution,
Search/Ask disagreement, workspace disagreement, unsafe output, and renderer failure.

## Developer Experience

The primary persona is a repository contributor or backend engineer establishing one honest
offline baseline before changing retrieval. The documented path remains explicit:

```bash
uv sync --locked
uv run mke eval retrieval \
  --manifest tests/fixtures/retrieval-eval-v1.json
```

Human output states the narrow English page/timestamp scope and `quality_gate=none`; JSON remains
one complete object for automation. Exit codes remain `0` for a trustworthy completed observation,
`1` for an untrustworthy baseline, and `2` for usage errors. The how-to must explain manual
before/after JSON comparison and require matching manifest/report versions.

## Remaining Risks

- Sixteen answerable queries provide only coarse signal and no statistical inference.
- The corpus is small, English-only, and dominated by page-level Evidence.
- Empty qrels for unanswerable queries measure the current exact-fact/no-hit contract, not general
  topical relevance.
- `retrieval-eval-v1` is comparable only while Evidence segmentation remains page/timestamp based.
- Determinism is verified on supported test environments, not every SQLite build or platform.
- The canonical baseline artifact is evidence for review, not a quality threshold.

## Consensus

| Phase | Shared findings | Disagreement resolved |
|---|---|---|
| CEO | Hold implementation scope; narrow claims; label derived Ask metric; make limitations explicit. | Large benchmark expansion was rejected; later algorithm selection receives its own expanded protocol. |
| Engineering | Narrow DTO, renderer naming, immutable fixture handling, locator contract, safe failures, canonical artifact. | `SearchResult` reuse was rejected because the narrower DTO avoids unnecessary text and ID exposure. |
| DX | Clarify integrity versus quality, corpus scope, `--db`, errors, explicit manifest, and comparison workflow. | Built-in wheel data/default manifest was rejected; E1 keeps explicit external manifests. |

## Verdict

The corrected spec and plan are coherent and ready for a separate implementation window after the
final autoplan approval gate. No retrieval runtime code was implemented by this review.
