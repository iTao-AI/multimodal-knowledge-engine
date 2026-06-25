# Chinese Retrieval Baseline Implementation Review

## Status

- Review type: lightweight pre-handoff self-review.
- Scope: E3-A only.
- Result: implementation and Task 11 verification match the approved HOLD SCOPE plan.
- Follow-up: four findings from the separate review window were verified and closed with TDD;
  no complete `gstack-review` was repeated in this implementation window.
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

1. The Chinese artifact validator rebuilt the expected artifact with the current process
   environment, so a valid artifact recorded on another supported Python/SQLite/PyMuPDF runtime
   failed validation. The validator now accepts the artifact's recorded environment after strict
   version-shape validation. Python 3.12 and 3.13 isolated validators cover this path.
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

## Verification

- Targeted E3-A suite: `181 passed`.
- Full suite: `817 passed, 1 skipped`.
- `uv run ruff check .`: passed.
- `uv run pyright`: `0 errors`.
- `uv build`: sdist and wheel built.
- E1, E2, and E3-A commands plus all three artifact validators: passed.
- E1 and E2 final observations are semantically equal to the pre-refresh observations after
  excluding runtime duration only.
- `uv run mke proof run --json`: `8/8` passed.
- `uv run mke demo --verify`: passed.
- Offline installed-wheel proof: Python 3.12 in `6511 ms`; Python 3.13 in `6523 ms`.
- Chinese artifact validation passed in isolated Python 3.12 and 3.13 environments using the same
  checked-in artifact and observed report.
- Python 3.12 measurement: sync `12 ms`, evaluator `525 ms`, first report `537 ms`, wheel proof
  `2959 ms`, peak RSS `213893120` bytes, maximum SQLite `910552` bytes.
- Python 3.13 measurement: sync `12 ms`, evaluator `532 ms`, first report `544 ms`, wheel proof
  `3005 ms`, peak RSS `213565440` bytes, maximum SQLite `807552` bytes.
- All fixed time, RSS, and SQLite budgets passed.
- CI YAML, changed-doc links, public-boundary scan, and `git diff --check`: passed.

## Artifact Identity

- E3-A artifact SHA-256:
  `d201ffed051cef2973ec833295d0779f4613693a892a73bfd2eaa4ef4d907ef6`.
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
- Cross-platform SQLite determinism is covered by Python 3.12/3.13 CI and local proof, not every
  SQLite build.

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
