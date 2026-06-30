# Local Dense Retrieval Candidate Implementation Review

Date: 2026-06-29

Scope: E3-C PR 2 dense comparison evidence for `qwen3-embedding-0.6b-exact-v1`.

## Result

The PR 2 branch records comparison-only dense evidence for
`Qwen/Qwen3-Embedding-0.6B` revision `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`
through the project-owned exact-cosine adapter.

Canonical result:

- `candidate_status=completed`
- `e3d_status=eligible`
- `runtime_promotion_status=not_evaluated`
- `selected_threshold=0.58`
- `holdout_status=observed`

Development recovered `zh-dev-hard-01` and `zh-dev-semantic-04`. The one holdout observation
recovered `zh-hold-hard-01`, `zh-hold-multi-02`, `zh-hold-multi-03`,
`zh-hold-semantic-03`, and `zh-hold-semantic-04`; `zh-hold-number-01` and
`zh-hold-number-02` remain report-only.

## Evidence Integrity

- The development freeze was committed before holdout and has SHA-256
  `e2c791bf2a9d7ad6ea3047f89fad2c3157038da88f960b3befa1df131d26002d`.
- The holdout receipt was created once with SHA-256
  `69d723fe9ca182404ea25c5f4742edaede9e7ddd4d9b21aa1156f823b205928d`.
- The comparison artifact SHA-256 is
  `25a46056052b36034492f481370c645c6c499185569da756769bbe378848d298`.
- E1/E2/E3-A/E3-B normalized semantic equality to Task 0 snapshots remained true after
  source/scope identity refresh.

## Targeted Review Resolution

Authoritative PR 2 review found one blocking issue: the documented
`python -m mke.evaluation.dense_replay validate` command had no real module entrypoint, so module
execution could return `0` without reading the artifact. The fix adds a RED regression for a
missing artifact, implements the cache-ready replay CLI, keeps model loading cache-only through the
external `--model-cache`, rejects repository-internal model caches, and preserves the existing
model-free artifact validator and measurement harness.

The remediation is validator plumbing only. It does not regenerate qrels, rerun holdout, change the
selected threshold, alter the comparison artifact result, or promote dense retrieval into runtime
Search/Ask/MCP behavior.

Follow-up targeted re-review found that the E3-C artifact source rebinding had not propagated the
refreshed E3-A historical artifact identity into `historical_arms.e3a` and
`comparison.arms[0]`. The fix adds a checked-in-artifact regression for historical arm identities
and rebuilds only the E3-C identity bindings. Metrics, candidate observations, threshold,
development freeze, holdout receipt, E3-D status, and runtime promotion status remain unchanged.

## Scope Limits

This review records evidence, not promotion. PR 2 does not change Search, Ask, MCP, owner startup,
runtime defaults, `active_evidence_fts`, SQLite domain truth, API adapters, hybrid/RRF, reranking,
query rewrite, HTTP, or UI. E3-D eligibility only means a future experiment may be planned.

The result is bound to a small public Chinese page-level corpus with a public non-blind holdout.
It is not a production-quality or statistical-significance claim and does not generalize to
Japanese, Korean, other model revisions, API embeddings, segmentation, or future temporal data.
