# Chinese Retrieval Baseline Implementation Review

## Status

- Review type: lightweight pre-handoff self-review.
- Scope: E3-A only.
- Result: implementation matches the approved HOLD SCOPE plan; final Task 11 verification remains
  to be recorded before PR preparation.
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
