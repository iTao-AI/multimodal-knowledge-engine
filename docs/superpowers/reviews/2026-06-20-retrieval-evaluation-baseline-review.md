# Retrieval Evaluation Baseline Implementation Review

## Status

- Review type: lightweight execution self-check followed by authoritative `gstack-review`
  remediation.
- Result: targeted findings fixed; ready for targeted re-review.
- Full `gstack-review`: not repeated after remediation.
- Branch: `codex/retrieval-eval-baseline`.
- Main merge base: `721784eabcb9fbb737166578010c9e1a46a25fef`.
- Implementation start: `3992b0e9371d1a8c9e019d3bbe2b32aac9665914`.

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

- Targeted validator and mutation tests: `51 passed`.
- `uv run pytest -q`: `523 passed, 1 skipped`.
- `uv run ruff check .`: passed after mechanical import ordering fix.
- `uv run pyright`: `0 errors`.
- `uv build`: wheel and source distribution built.
- Human and JSON retrieval evaluation: passed.
- Canonical artifact validator: passed against actual manifest, fixture files, and Git history.
- `uv run mke proof run`: 8/8 cases passed.
- `uv run mke demo --verify`: passed.
- `git diff --check`: passed.

## Authoritative Review Findings

1. Canonical code provenance previously mislabeled the implementation start as the main base.
   The artifact and documentation now distinguish `main_merge_base`, `implementation_start`, and
   `evaluation_commit`.
2. CI previously checked only a few artifact fields. The project-owned validator now derives
   manifest and fixture checksums from actual files, verifies Git ancestry and environment shape,
   validates the complete metrics/result/query identity contract, and rejects malformed
   provenance without turning historical scores into a quality gate.
3. Snapshot mutation rejection existed in production but lacked direct regression coverage.
   Tests now mutate fixture bytes after manifest validation and during snapshot copy and verify
   `FixtureValidationError`.

The validator tests also prove that incorrect code provenance, manifest/fixture checksums,
environment shape, metric aggregates, result structure, and query identity fail validation. A
self-consistent alternate historical score set remains valid, confirming the validator does not
compare current run scores to the canonical observation.

## Remaining Risks

- Sixteen answerable queries provide only coarse macro signal.
- The corpus is small, English-only, and mostly page-level.
- Empty unanswerable qrels measure exact-fact no-hit behavior, not general topical relevance.
- Comparison is invalid after Evidence segmentation changes without a new manifest/report version.
- Determinism is verified on supported CI/local environments, not every SQLite build.
