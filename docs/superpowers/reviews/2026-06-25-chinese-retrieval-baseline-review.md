# Chinese Retrieval Baseline Implementation Review

## Status

- Review type: lightweight pre-handoff self-review.
- Scope: E3-A only.
- Result: implementation and Task 11 verification match the approved HOLD SCOPE plan.
- Follow-up: seven findings across three targeted review passes and two PR #29 CI failures were
  verified and closed with TDD; no complete `gstack-review` was repeated.
- Branch: `codex/e3a-chinese-retrieval-baseline`.
- Base: `89deeab`.

## Scope Check

- Added the frozen five-document, 48-query, 1,680-judgment Chinese protocol.
- Added isolated evaluation, graded metrics, independent Evidence/projection checks, full-result
  rank probes, safe reports, artifact validation, journaled refresh, CLI, CI, wheel proof,
  measurement, and documentation.
- Did not add CJK tokenization, another FTS projection, embeddings, vector or hybrid retrieval,
  RRF, reranking, query rewrite, Passage/chunk, OCR, HTTP, UI, MCP changes, or runtime promotion.

## Canonical Observation

- Recall@5: `0.295455`.
- nDCG@10: `0.277279`.
- Answerable zero-hit rate: `0.681818`.
- Miss symptoms: 25 `compiled_query_empty`, 2
  `compiled_clauses_absent_from_direct_page`, 2 `matching_direct_page_not_returned`, and 1
  `distractor_ranked_ahead`.
- Rank profile: `sqlite_fts5_default_bm25`.
- E3-B decision: `eligible`, based on complete qrel review, 1,680 judgments, and 10 answerable
  development `compiled_query_empty` misses.

## Self-Review Findings

1. Rank evidence uses stable document/locator identity in canonical digests because runtime
   Evidence UUIDs are intentionally non-deterministic.
2. The E2 observation must be generated against a staged protocol scope before the four-file
   refresh; after replacement, the exact canonical E2 command and validator pass.
3. The rollback regression test preserves the pre-existing E3 artifact instead of assuming that
   target is absent.

No unresolved scope or architecture decision was found. Final authoritative `gstack-review` is
deliberately deferred to the PR preparation window.

## Review Follow-Up Findings

1. The Chinese artifact validator originally rebuilt the expected artifact with the current
   process environment. The first follow-up replaced that behavior with version-shape validation,
   but a second targeted review correctly found that well-formed impossible versions could still
   pass. That intermediate behavior is superseded. The validator now derives one exact contract
   from `pyproject.toml`, the CI Python matrix, `uv.lock`, and the approved SQLite rank profile.
   Artifact environment mutations fail closed, while isolated Python 3.12 and 3.13 validators
   accept the same repository-bound artifact.
2. Rank evidence trusted a synthetic statement count and accepted empty rank result sets. The
   SQLite diagnostic now returns the actual SQL trace. The runner requires exactly two unbounded,
   production-equivalent MATCH queries, full `rank`/`bm25()` equality, Search top-10 prefix
   equality, and a non-empty result for the predeclared rank probe.
3. Artifact recording trusted observed miss fields and allowed locators outside the query
   partition; Python booleans could also compare equal to integer grades/counts. The validator
   now extracts the frozen fixture page inventory independently, restricts each result to its
   partition and limit, recomputes `classify_miss()` from fixture text/qrels/retrieved locators,
   and uses recursive type-strict JSON equality. Regression tests mutate the observed report and
   exercise the re-record path, not only a finished artifact.
4. Qrel adjudication required a `review_date` field but did not validate it. The protocol now
   requires the exact approved ISO date `2026-06-25` and rejects booleans, malformed/impossible
   dates, and alternate dates.
5. The environment schema still trusted plausible artifact strings rather than repository truth.
   Adversarial observed-report-to-record-to-validate tests now replace Python requirements, CI
   versions, the locked PyMuPDF version, and the SQLite profile with well-formed impossible values;
   every mutation is rejected by the repository-derived exact contract.
6. Rank observations exposed only digests, so the validator could not independently recompute
   arbitrary non-probe query evidence. The canonical report now includes each full ordered stable
   Evidence locator and corresponding rank/`bm25()` hexadecimal score pair. Validation checks the
   partition inventory and Search prefix, then independently recomputes every non-empty query's
   result count, ordered identity digest, and score-pair digest. Adversarial re-record tests mutate
   arbitrary non-probe counts and digests and require rejection.
7. The complete scorer fields were still treated as their own expected evidence: coordinated
   changes to a score or locator plus every dependent result and digest could pass. The validator
   now extracts frozen page text, creates separate development and holdout databases with the
   production `SQLiteStore` schema, directly fills domain/projection rows without normal ingest,
   recompiles each query, and replays the production full-result `rank`/`bm25()` diagnostic.
   Observed locator order and exact score pairs must equal that independent replay before their
   digests are accepted. Regression tests coordinate score-plus-digest and
   locator-plus-result-plus-score-plus-digest mutations; both fail.
8. The fixture-mutation regression test counted `Path.stat()` calls. Linux path resolution made
   the mutation occur before snapshot's explicit `before` stat, so the production before/after
   check correctly saw no change. The test now mutates the temporary source when snapshot opens it
   for `rb`, guaranteeing the mutation occurs between the two production stats without sleeping,
   skipping, or weakening fail-closed behavior.
9. PR #29 Python 3.13 Linux used SQLite 3.40.1 while the checked-in artifact was recorded with
   SQLite 3.51.1. Frozen page text (70 pages, aggregate digest
   `8732310f89e112315b3683382233c30d2a6b3673d205979160c708da328bc56d`), results, metrics,
   result counts, and complete locator order were identical. Three scores differed by exactly one
   ULP; the first was `zh-hold-mixed-03` result 1,
   `-0x1.0bfd00ddd0ed0p+3` versus `-0x1.0bfd00ddd0ed1p+3`. Validation now exposes an internal
   mismatch category while retaining redacted CLI output, permits at most one ULP against
   independent replay, and stores portable 15-significant-digit canonical score evidence.
   Substantive coordinated score mutation remains rejected.

## Verification

- Targeted E3-A suite: `188 passed`.
- Full suite: `827 passed, 1 skipped`.
- `uv run ruff check .`: passed.
- `uv run pyright`: `0 errors`.
- `uv build`: sdist and wheel built.
- E1, E2, and E3-A commands plus all three artifact validators: passed.
- E1 and E2 final observations are semantically equal to the pre-refresh observations after
  excluding runtime duration only.
- `uv run mke proof run --json`: `8/8` passed.
- `uv run mke demo --verify`: passed.
- Offline installed-wheel proof: Python 3.12 in `3812 ms`; Python 3.13 in `3581 ms`.
- Chinese artifact validation passed in isolated Python 3.12 and 3.13 environments using the same
  checked-in artifact and observed report.
- Python 3.12 measurement: sync `15 ms`, evaluator `613 ms`, first report `628 ms`, wheel proof
  `3496 ms`, peak RSS `213843968` bytes, maximum SQLite `844632` bytes.
- Python 3.13 measurement: sync `16 ms`, evaluator `627 ms`, first report `643 ms`, wheel proof
  `3584 ms`, peak RSS `206880768` bytes, maximum SQLite `910552` bytes.
- All fixed time, RSS, and SQLite budgets passed.
- CI YAML, changed-doc links, public-boundary scan, and `git diff --check`: passed.

## Artifact Identity

- E3-A artifact SHA-256:
  `8e912fb18005efd0e60ef6493753f4f9308374349d56f1dde37f7bfcdeb284c2`.
- Protocol SHA-256:
  `00f72934018a52b5b5f5591fba119050882aee9b782e5dac199702b0cf995944`.
- Qrel adjudication SHA-256:
  `b638a7729725d495e809bb52a93b071e65a51b0f0ebcb218d3ee3298a04bd0c4`.
- All 30 observed grade-`2` misses contain a mechanical miss-symptom classification.

## Remaining Risks

- The corpus is small, public, text-layer-only, and page-level; the holdout is not blind.
- Current query compilation is ASCII-oriented, producing zero Recall@5 for the 27-query
  zero-ASCII-token stratum.
- E3-B eligibility is a planning gate, not authorization to implement or promote a candidate.
- PR #29 hosted CI at `c586215` failed before this follow-up. The exact failure shapes now pass in
  isolated Linux Python 3.12/SQLite 3.50.4 and Python 3.13/SQLite 3.40.1 containers, but hosted
  GitHub Actions confirmation remains pending because this implementation window stops before
  push.

## Documentation Audit

`gstack-document-release` audit coverage is complete:

| Surface | Reference | How-to | Tutorial | Explanation |
|---|---|---|---|---|
| `mke eval retrieval-chinese` | `docs/reference/cli.md` | Chinese evaluation how-to | getting started | architecture |
| Canonical E3-A artifact | CLI/contracts reference | validation and recovery | linked from first run | source-of-truth boundary |
| Offline wheel proof and budgets | CI and script contracts | wheel proof commands | warm-cache target | external-runtime isolation |

README navigation, local links, first-run commands, metrics, error/recovery tokens, and
implemented-versus-planned status are synchronized. No CHANGELOG, VERSION, TODOS, release, PR, or
deployment action is required in this implementation window.
