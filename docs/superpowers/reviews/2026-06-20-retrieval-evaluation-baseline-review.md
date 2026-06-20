# Retrieval Evaluation Baseline Implementation Review

## Status

- Review type: lightweight execution self-check.
- Result: clear after targeted verification.
- Full `gstack-review`: intentionally not run per implementation instruction.
- Branch: `codex/retrieval-eval-baseline`.
- Base: `3992b0e9371d1a8c9e019d3bbe2b32aac9665914`.

## Scope Check

- Added strict offline manifest, fixture snapshot, metrics, reports, two-workspace runner, CLI,
  CI gates, documentation, and canonical baseline artifact.
- Added only one internal read-only application seam: `list_active_evidence()`.
- Did not change `SQLiteStore.search`, `_to_fts_query`, Search ordering, Ask validation/statuses,
  Publication semantics, or transcription behavior.
- Evaluation invokes existing ingest, Search, and Ask contracts and performs no network call.

## Observed Baseline

- Documents: 3.
- Queries: 24 (`16` answerable, `4` lexical confusers, `4` out of corpus).
- Recall@1: `0.875000`.
- Recall@3 and Recall@5: `0.937500`.
- MRR@5: `0.937500`.
- Answerable zero-hit rate: `0.062500`.
- Unanswerable no-hit and Ask refusal rates: `1.000000`.
- Answerable miss at rank 5: `water-answerable-01`.
- Unanswerable false positives: none.

## Verification

- `uv run pytest -q`: `505 passed, 1 skipped`.
- `uv run ruff check .`: passed after mechanical import ordering fix.
- `uv run pyright`: `0 errors`.
- `uv build`: wheel and source distribution built.
- Human and JSON retrieval evaluation: passed.
- `uv run mke proof run`: 8/8 cases passed.
- `uv run mke demo --verify`: passed.

## Remaining Risks

- Sixteen answerable queries provide only coarse macro signal.
- The corpus is small, English-only, and mostly page-level.
- Empty unanswerable qrels measure exact-fact no-hit behavior, not general topical relevance.
- Comparison is invalid after Evidence segmentation changes without a new manifest/report version.
- Determinism is verified on supported CI/local environments, not every SQLite build.
