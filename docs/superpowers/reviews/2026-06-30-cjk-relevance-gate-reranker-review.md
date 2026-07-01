# CJK Relevance Gate Reranker Implementation Review

Review object: E3-E local branch `codex/e3e-relevance-gate-reranker`.

Base: `main@03a7583fd7161585bc039832b517cc3be97ddca9`.

Mode: implementation evidence record for scheme-window pre-PR review. The branch is local branch
only. It records no runtime promotion and no push, PR, merge, release, or deployment action.
This is a local branch only evidence record.

## Result

`cjk-relevance-gate-reranker-v1` is implemented as a comparison-only deterministic relevance gate
and reranker over the E3-D lexical+dense union.

| Field | Value |
|---|---|
| Candidate status | `completed` |
| Development status | `passed` |
| Holdout status | `observed` |
| Holdout gate status | `failed` |
| Selected profile | `strict-constraint` |
| Runtime promotion status | `not_evaluated` |

The development freeze passed the frozen gates. Holdout was observed only after the exclusive
freeze and failed honestly on `holdout_hard_negative_failure_above_current_runtime`.

## Metrics

| Split | Recall@5 | nDCG@10 | MRR@5 | Unanswerable no-hit | Hard-negative failure |
|---|---:|---:|---:|---:|---:|
| Development | `0.727273` | `0.659562` | `0.645455` | `0.500000` | `0.100000` |
| Holdout | `0.636364` | `0.571515` | `0.537879` | `0.500000` | `0.142857` |

Key diagnostics:

- Development: `input_union_count=62`, `allowed_count=48`, `dropped_grade2_count=2`,
  `lexical_only_recovery_retained_count=6`, `dense_only_recovery_retained_count=0`,
  `empty_result_no_hit_count=6`.
- Holdout: `input_union_count=55`, `allowed_count=27`, `dropped_grade2_count=7`,
  `lexical_only_recovery_retained_count=4`, `dense_only_recovery_retained_count=0`,
  `empty_result_no_hit_count=9`.

## Artifact Identities

| Artifact | SHA-256 |
|---|---|
| E3-E protocol lock | `929476fe076e6c9b6d3797d5620516a15a44f6a3e3d78c3860f0eaec5b2e344a` |
| E3-E development freeze | `0377bcfd1350540ea75610cc2ef44fd4b4f86234551f9816adad48598ac1e44e` |
| E3-E holdout receipt | `4731fe5afb7d164a4411efab0ecf880a69838b802d930ac3192eb49930d81351` |
| E3-E comparison artifact | `84dcfa3b4375458f5a4b0e5f91d4c15dfeb35a39ba7fb1bcbefec279d75d7c4e` |
| E3-C dense artifact input | `a1f3e1af3f009ceea57e06b17ff2096ba48129be92c49cc5f52e1d1456328e4c` |
| E3-D RRF artifact input | `b593cae9716b54786fee6858d24935f7c4eba3f652d46872ac4d639b4444a42c` |

## Validator Evidence

Targeted validators pass:

```bash
uv run python -m mke.evaluation.baseline --artifact benchmarks/retrieval/retrieval-eval-v1-baseline.json --manifest tests/fixtures/retrieval-eval-v1.json --repository .
uv run python -m mke.evaluation.numeric_artifact validate --artifact benchmarks/retrieval/numeric-grouping-v1-comparison.json --observed /tmp/mke-e2-after.json --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json --repository .
uv run python -m mke.evaluation.chinese_artifact validate --artifact benchmarks/retrieval/retrieval-chinese-v1-baseline.json --observed /tmp/mke-e3a-after.json --protocol tests/fixtures/retrieval-chinese-v1/protocol.json --repository .
uv run python -m mke.evaluation.cjk_lexical_artifact validate --artifact benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json --observed /tmp/mke-e3b-after.json --protocol tests/fixtures/retrieval-chinese-v1/protocol.json --repository .
uv run python -m mke.evaluation.dense_artifact validate --artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json --protocol tests/fixtures/retrieval-dense-v1/protocol-lock.json --repository .
uv run python -m mke.evaluation.hybrid_rrf_artifact validate --artifact benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json --protocol tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json --dense-artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json --repository .
uv run python -m mke.evaluation.relevance_gate_artifact validate --artifact benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json --protocol tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json --repository .
```

The E3-C dense validator emits the existing `runpy` warning but exits successfully and prints
`dense comparison artifact valid`.

Historical identity refresh was accepted only after normalized E1/E2/E3-A/E3-B semantic payloads
matched their pre-change snapshots. E3-C, E3-D, and E3-E refresh changed identity hashes only:
metrics, gates, selected profile, and verdicts stayed unchanged.

## Final Verification

Full verification on local HEAD passed:

| Command | Result |
|---|---|
| `uv run pytest -q` | `1242 passed, 5 skipped`; existing SWIG deprecation warnings only |
| `uv run ruff check .` | passed |
| `uv run pyright` | `0 errors, 0 warnings, 0 informations` |
| `uv build` | source distribution and wheel built |
| `uv run mke proof run` | `proof=product status=passed cases=8 passed=8 failed=0` |
| `uv run mke demo --verify` | `result=passed` |
| `uv run python -m mke.evaluation.relevance_gate_artifact validate ...` | `relevance gate artifact valid` |
| `git diff --check origin/main...HEAD` | passed |

Optional dense replay was attempted cache-only with `HF_HUB_OFFLINE=1`,
`TRANSFORMERS_OFFLINE=1`, and `UV_OFFLINE=1`. It returned
`{"mode":"cache-ready","status":"failed"}` and is recorded as optional corroboration unmet; no
package installation or model download was performed.

Public-boundary scan found no branch-introduced private paths, credentials, tokens, cookies, raw
GStack artifacts, restore points, transcripts, or private source material. Existing test fixtures
that contain synthetic redaction strings remain test-only.

## Scope

No runtime defaults changed. Search, Ask, MCP, owner startup, Publication, ingestion, and runtime
strategy behavior are unchanged.

Candidate scoring uses query text, Evidence text, stable locator identity, source text digest,
document identity, arm provenance, and rank provenance. It does not use qrels, grades, query
category labels, split labels, or expected locators as candidate scoring input.

No API reranker, LLM judge, local cross-encoder, query rewrite, HyDE, segmentation, HTTP/UI,
Milvus, Redis, pgvector, LangChain, LlamaIndex, or LangGraph runtime contract was introduced.

## Review Notes

Targeted review found one P1 implementation finding after the initial local closeout: the artifact
validator did not bind top-level decision statuses to independently recomputed development, holdout,
and state data. The fix adds regression coverage for `holdout_status`, `reranker_model_status`,
`query_rewrite_status`, `segmentation_status`, and `e3f_runtime_status` drift, then makes
`validate_relevance_gate_artifact()` derive expected statuses from recomputed reports instead of
trusting the artifact's own branch fields.

Targeted follow-up verification passed:

| Command | Result |
|---|---|
| `uv run pytest tests/evaluation/test_relevance_gate_artifact.py tests/evaluation/test_relevance_gate_workflow.py tests/interfaces/test_cli_relevance_gate.py tests/evaluation/test_relevance_gate_documentation.py -q` | `30 passed`; existing SWIG deprecation warnings only |
| `uv run python -m mke.evaluation.relevance_gate_artifact validate ...` | `relevance gate artifact valid` |
| E1/E2/E3-A/E3-B validators with fresh observed payloads | passed after identity-only refresh; metrics, gates, and verdicts unchanged |
| E3-C/E3-D validators | passed after downstream identity-only refresh |
| `uv run ruff check .` | passed |
| `uv run pyright` | `0 errors, 0 warnings, 0 informations` |
| `git diff --check origin/main...HEAD` | passed |

After this fix, there are no unresolved implementation findings.

Remaining risks are evidence-scope risks: the corpus is small, holdout is public after the protocol
freeze, and holdout hard-negative failure means this artifact should inform future design rather
than be promoted.
