# Numeric Retrieval Candidate Comparison Autoplan Review

## Status

- Result: PR 1 implemented and authoritative implementation-review findings remediated locally;
  targeted re-review is pending.
- Review mode: CEO scope hold, full engineering review, and DX polish.
- Independent voice: Codex CLI; no parallel reviewer was used.
- Design review: skipped because E2 has no graphical interface.
- Baseline: `main@e3a3f3656be8889e8e54e06a1de09ebd6412384f`.
- Merge status: local branch only; no PR, push, merge commit, PR 2, or ADR-0007 exists.

## Implementation Evidence

- Candidate verdict: `integrity_status=passed`, `candidate_status=passed`.
- Gates: 14/14 passed.
- E1 Recall@1: `0.875000` current, `0.937500` candidate.
- Unrelated E1 results: exact ordered semantic equality.
- Allowed E1 delta: `water-answerable-01` improved from no hit to rank 1.
- Artifact:
  `benchmarks/retrieval/numeric-grouping-v1-comparison.json`.
- Runtime default remains `current`; PR 2 and ADR-0007 were not implemented.
- All six evaluations, compiled queries, and gates use one protocol-bound immutable snapshot.
- `single_match_per_search` uses traced SQL evidence; `scope_fence` uses protocol-bound
  dependency/execution identities plus observed schema and local-provider identities.
- Artifact validation independently checks exact nested fields, types, order, result/locator
  consistency, recomputed metrics, gates, and verdict before fresh-observation equality.

## Implementation Verification

| Check | Result |
|---|---|
| Targeted regression and affected suites | `118 passed` |
| `uv run pytest -q` | `650 passed, 1 skipped` |
| `uv run ruff check .` | passed |
| `uv run pyright` | `0 errors, 0 warnings` |
| `uv build` | sdist and wheel built |
| E1 evaluation | passed; Recall@1 `0.875000` |
| Numeric comparison | integrity passed; candidate passed; 14/14 gates |
| Numeric candidate E1 Recall@1 | `0.937500` |
| E1 baseline validator | valid |
| Numeric artifact validator | valid against fresh observation |
| `uv run mke proof run` | 8/8 cases passed |
| `uv run mke demo --verify` | passed |
| `git diff --check` | passed |
| Documentation audit | 58 Markdown files checked; feature coverage complete; 2 unrelated historical-plan links remain pre-existing |

Artifact identities:

- comparison artifact SHA-256:
  `60e2d8a974942d572f40ea50e811785096c2823e13439b6eb1d8c8f8ceebf2d6`;
- complete source content SHA-256:
  `ba17dad428445548888bd8ebd6f0dc64b3b43594250c401f6a63d34dcca44f8b`;
- protocol lock SHA-256:
  `1c82bcecb59c6dfa8b7afddf5bf2a7fc311d155c43f02784c1f0384c3d37aa47`.

The branch remains local and unmerged. The completion record intentionally leaves PR 1 merge and
merge-backed durable evidence unchecked. No PR 2 was created.

## Authoritative Implementation Review Remediation

| Finding | Resolution | Regression evidence |
|---|---|---|
| Protocol validation had a mutation interval before six evaluations. | The comparator copies and revalidates every locked manifest and fixture into one temporary protocol snapshot; all six observations and compiled queries use only that snapshot. | Source manifest mutation after the first observation does not alter the comparison. |
| Artifact validation accepted self-consistent malformed nested payloads. | The validator now enforces exact nested schemas and reconstructs result, locator, count, metric, compiled-query, gate, and verdict consistency from the frozen protocol. | Missing fields, wrong types, reversed order, inconsistent counts/metrics, and reordered compiled queries fail. |
| `single_match_per_search` and `scope_fence` were constants. | Evaluation evidence records actual per-Search FTS5 `MATCH` counts, SQLite schema identity, and concrete PDF/sidecar provider identities; the protocol binds dependency and execution source identities. | Injected two-MATCH evidence rejects `single_match_per_search`; an invalid schema identity rejects `scope_fence`. |
| Numeric nondeterminism lost its fixed public mapping. | Any evaluator `retrieval_eval_nondeterministic` failure maps to `retrieval_numeric_nondeterministic`, fixed cause, and fixed next step. | Dedicated redaction-safe mapping regression passes. |
| Completion and durable review state were premature. | Local result, targeted re-review, PR creation, merge, PR 2, and merge-backed evidence are now represented separately. | PR 1 merge remains unchecked and this review states targeted re-review is pending. |

## Targeted Re-review Remediation

| Finding | Resolution | Regression evidence |
|---|---|---|
| Recorded gate status could contradict validated observations. | The artifact validator independently recomputes every derivable gate from validated per-query results, compiled queries, and metrics before accepting the recorded status and verdict. | Replacing the E1 candidate observation with current while claiming rank-1 improvement is rejected. |
| Nested integer fields accepted JSON booleans through Python equality. | Revisions, corpus/category counts, result counts, relevance counts, ranks, locators, and metric counts now use explicit non-bool integer parsing with bounded ranges. | Self-consistent bool mutations across eight integer/count/rank positions are rejected. |
| Retrieved locators could name documents outside the frozen manifest. | Locator validation now receives the corresponding manifest document inventory and rejects any unknown `document_id`. | Adding the same `not-in-manifest` locator to both sides of a preserved control is rejected. |
| Protocol candidate revision accepted `true` as revision `1`. | Protocol loading now requires a non-bool integer revision exactly equal to `1` before fixture access or evaluation. | A protocol with `candidate.revision=true` returns the fixed protocol-invalid result. |
| The durable review ended with an implementation-window Verdict. | The tail now reports the actual local implementation and verification state while leaving targeted re-review, PR, and merge status pending. | Plan completion and targeted remediation checklists preserve the remaining review gate. |

## Executive Verdict

E2 should test one bounded response to the only concrete E1 miss:
`water-answerable-01`. The approved candidate preserves the original compact numeric token and
adds an alternative FTS5 phrase for tokenizer-adjacent right-grouped tokens. It does not add
semantic retrieval, CJK tokenization, reranking, a vector index, a dependency, or a second Search
query.

The corrected design separates evidence collection from product-default promotion:

1. PR 1 freezes independent development and public-holdout fixtures, evaluates the off-default
   candidate, and records either a passing or trustworthy rejected artifact.
2. PR 2 exists only for a passing artifact and adds an ADR, default promotion, and an
   owner-controlled `current` rollback selector.

## Confirmed Evidence

- E1 Recall@1 is `0.875000`.
- E1 Recall@3/5 and MRR@5 are `0.937500`.
- `water-answerable-01` is the only answerable miss.
- The compact query contains `410000`; the relevant PDF page contains `410,000`.
- Current FTS5 behavior matches `410,000` and `410 000` through adjacent `410` and `000` tokens.
- The configured tokenizer cannot distinguish comma from other punctuation that produces the same
  adjacent token sequence.

## Scope Decisions

### Accepted

- Freeze repository-generated text-layer development and public-holdout PDFs before candidate code.
- Reuse the strict E1 manifest, ingestion, metrics, report DTO, and two-workspace determinism path.
- Keep the public E1 Python function, CLI, and report schema unchanged.
- Add one private policy-aware evaluator for the numeric comparator.
- Evaluate current and candidate behavior on development, holdout, and the complete E1 corpus.
- Record a canonical semantic artifact after all PR 1 source changes are final.
- Treat a trustworthy rejected candidate as a valid E2 outcome.
- Require a separate ADR-backed promotion PR and an installed-wheel rollback proof.

### Deferred Or Rejected

| Proposal | Decision | Reason |
|---|---|---|
| CJK, semantic, fusion, reranking, or vector retrieval | Deferred | E1 provides no evidence that these are the next required change. |
| Generic candidate plugin framework | Rejected | One observed failure does not justify a generalized platform. |
| Existing USGS page as both development and holdout | Rejected | Different numbers from one page are not independent evidence. |
| Replace compact tokens with grouped phrases | Rejected | Compact-document matches must remain valid. |
| Promote inside the comparison PR | Rejected | Evidence collection and runtime-default change require separate decisions. |
| Distinguish comma grouping from tokenizer-equivalent punctuation | Deferred | It requires original-text separator inspection beyond one FTS5 query. |

## Architecture Verdict

```text
protocol lock + development/holdout/E1 identities
                         |
                         v
          strict path and content validation
                         |
              +----------+----------+
              |                     |
              v                     v
         current policy      numeric-grouping-v1
              |                     |
       two fresh runs         two fresh runs
              |                     |
              +----------+----------+
                         |
         exact per-query and aggregate gates
                         |
           canonical semantic observation
                         |
      reviewed artifact <-> fresh CI observation
```

The query compiler returns the current output byte-for-byte when no eligible integer exists. When
an eligible integer exists, it compiles the original token OR its tokenizer-adjacent grouped
phrase, then conjuncts the remaining clauses. The complete E1 comparison allows only the explicit
`water-answerable-01` delta.

## Findings Incorporated

| Area | Finding | Resolution |
|---|---|---|
| Scope | The initial plan overreached into broad retrieval-family comparison. | Reduced E2 to one E1-observed numeric mismatch. |
| Qrels | A development query originally had multiple relevant locators, making rank-1 success ambiguous. | Every answerable E2 query now has one relevant page. |
| Candidate | Replacing compact tokens would regress compact document text. | Candidate uses original-token OR grouped-phrase disjunction. |
| Semantics | FTS5 phrases prove adjacency, not a comma-specific separator. | Claim and tests now cover tokenizer-adjacent punctuation and non-adjacent negatives. |
| Equivalence | Candidate formatting changed queries without eligible integers. | Candidate must return current compilation byte-for-byte in that case. |
| Public API | A policy argument on the exported E1 runner would change its Python API. | Public wrapper remains exact; a private runner carries the policy. |
| Protocol | Path-root and candidate-revision semantics were undefined. | Exact protocol root/paths and semantic revision `1` are frozen. |
| Failures | Comparator state and error mapping were incomplete. | Exact total state machine and fixed redacted errors are specified. |
| E1 regression | Rank-only checks could hide unrelated hits or reordered results. | Unchanged E1 queries require complete ordered semantic equality. |
| Artifact | Duration conflicted with deterministic output. | Canonical semantic payload excludes duration. |
| Artifact | CI validated a checked-in artifact without comparing the fresh run. | Validator compares reviewed and observed semantic payloads. |
| Artifact | Git ancestry would fail after squash landing. | Identity is complete sorted source content and has a depth-1 clone test. |
| Artifact | Observation could precede final artifact-validator source. | Record only after artifact code is implemented and GREEN. |
| CI | Exit `1` for a trustworthy rejection would stop CI before validation. | CI accepts `0|1`, then requires trustworthy status and artifact agreement. |
| CLI | Candidate flag duplicated the protocol lock. | Candidate identity comes only from the protocol. |
| CLI | Nested report/help/error contracts were ambiguous. | Schema shapes, gate order, limitations, errors, help, and exits are frozen. |
| Fixtures | Generator text diverged from the frozen assertion. | Generator and expected page text now match exactly. |
| Rollback | A constant-only rollback was not operable through installed CLI/MCP. | PR 2 adds typed runtime policy and an owner startup selector. |
| Verification | Several steps named suites without executable commands. | Targeted, full, CI, artifact, and installed-wheel commands are explicit. |
| Documentation | Comparison versus promotion could be missed. | New guide is linked from E1 how-to, CLI reference, docs index, and both READMEs. |

## Verification Design

```text
fixture identity and exact text
  -> protocol schema/path/mutation tests
  -> current compiler characterization
  -> candidate boundary and SQLite adjacency tests
  -> public E1 wrapper equivalence
  -> six deterministic comparison observations
  -> exact E1 and challenge gates
  -> CLI human/JSON/help/error tests
  -> final-source artifact record/validate tests
  -> fresh-observed CI comparison
  -> squash-landed depth-1 clone validation
  -> full suite / Ruff / Pyright / build / proof / demo
  -> conditional installed-wheel CLI/MCP promotion proof
```

## Remaining Risks

- Targeted authoritative re-review is still pending; no merge-backed evidence exists yet.
- The public holdout is independently authored and locked, but not blind.
- Five answerable controls per partition are engineering evidence, not statistical inference.
- The candidate only covers ASCII compact integers with conventional three-digit right grouping.
- Tokenizer-equivalent punctuation is intentionally indistinguishable in this candidate.
- Locale-specific separators, decimals, signs, scientific notation, dates, and identifier semantics
  remain outside the claim.
- E1 and E2 page qrels require a new protocol if Evidence segmentation changes.

## Current Verdict

PR 1 is implemented locally and the latest targeted findings have been remediated. The numeric
artifact validator now independently recomputes every derivable promotion gate and rejects
bool-as-int nested values with explicit integer ranges. Full verification and refreshed artifact
identities are recorded above; targeted re-review has not cleared the branch. Runtime default
remains `current`; no PR 2, ADR-0007, push, PR, or merge exists.
