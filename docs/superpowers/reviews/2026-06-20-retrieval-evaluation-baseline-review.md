# Retrieval Evaluation Baseline Implementation Review

## Status

- Review type: lightweight execution self-check, one authoritative `gstack-review`, and targeted
  re-reviews after remediation.
- Result: authoritative findings remediated; final targeted re-review clean.
- Full `gstack-review`: one authoritative pass; no redundant full rerun after targeted fixes.
- Historical implementation branch: `codex/retrieval-eval-baseline` (deleted after merge).
- Main merge base: `721784eabcb9fbb737166578010c9e1a46a25fef`.
- Implementation start: `3992b0e9371d1a8c9e019d3bbe2b32aac9665914`.
- Merged through:
  [PR #23](https://github.com/iTao-AI/multimodal-knowledge-engine/pull/23) on 2026-06-21.
- Merge commit:
  [`98f02cca11d88e081106a89889a4f60376fad217`](https://github.com/iTao-AI/multimodal-knowledge-engine/commit/98f02cca11d88e081106a89889a4f60376fad217).

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

- Targeted validator and mutation tests: `57 passed`.
- `uv run pytest -q`: `529 passed, 1 skipped`.
- `uv run ruff check .`: passed after mechanical import ordering fix.
- `uv run pyright`: `0 errors`.
- `uv build`: wheel and source distribution built.
- Human and JSON retrieval evaluation: passed.
- Canonical artifact validator: passed against actual manifest, fixture files, the complete sorted
  33-file `src/mke/**/*.py` identity, and stored result structure.
- `uv run mke proof run`: 8/8 cases passed.
- `uv run mke demo --verify`: passed.
- CI YAML parse: passed.
- `git diff --check`: passed.

## Post-Merge Checks

The squash-landed `main` commit
[`98f02cca11d88e081106a89889a4f60376fad217`](https://github.com/iTao-AI/multimodal-knowledge-engine/commit/98f02cca11d88e081106a89889a4f60376fad217)
passed:

- [CI](https://github.com/iTao-AI/multimodal-knowledge-engine/actions/runs/27893532842) for
  Python 3.12 and 3.13;
- [CodeQL](https://github.com/iTao-AI/multimodal-knowledge-engine/actions/runs/27893532567)
  for Python and GitHub Actions;
- [Dependabot Updates](https://github.com/iTao-AI/multimodal-knowledge-engine/actions/runs/27893559244);
- the canonical baseline artifact validator against the squash-landed repository state.

The feature branch and implementation worktree were removed after merge. The historical
implementation SHAs remain audit metadata and are not required to exist in the landed branch.

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
4. The first validator revision required the historical implementation and evaluation commits to
   exist locally and remain in the current branch ancestry. That fails after squash landing and
   feature-branch deletion. Historical SHA values are now fixed audit metadata, while durable code
   identity is derived from a fixed list of evaluation/retrieval execution files with byte sizes,
   per-file SHA-256 values, and an aggregate SHA-256. A shallow fresh-clone regression test creates
   a single squash commit, confirms the historical feature commit is absent, and validates the
   artifact successfully without resolving Git history.
5. A non-integer retrieved locator range previously escaped as `ValueError`. The result validator
   now converts it to `BaselineValidationError`; a module-main subprocess test requires exit `1`,
   stable redacted output, empty stderr, and no traceback.
6. The first durable content identity covered only 12 hand-selected files and omitted runtime
   dependencies including `src/mke/adapters/video/schema.py` and `providers.py`. The validator now
   derives a sorted inventory of the complete `src/mke/**/*.py` source tree, recording byte sizes,
   per-file SHA-256 values, and an aggregate SHA-256. Regression tests mutate both omitted examples
   and require fail-closed validation while retaining squash-landed shallow-clone and malformed
   locator CLI coverage.

The validator tests also prove that incorrect historical metadata, durable evaluation content,
manifest/fixture checksums, environment shape, metric aggregates, result structure, and query
identity fail validation. A self-consistent alternate historical score set remains valid,
confirming the validator does not compare current run scores to the canonical observation.

## Remaining Risks

- Sixteen answerable queries provide only coarse macro signal.
- The corpus is small, English-only, and mostly page-level.
- Empty unanswerable qrels measure exact-fact no-hit behavior, not general topical relevance.
- Comparison is invalid after Evidence segmentation changes without a new manifest/report version.
- Determinism is verified on supported CI/local environments, not every SQLite build.
