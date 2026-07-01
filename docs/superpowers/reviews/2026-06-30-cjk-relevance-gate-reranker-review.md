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
| E3-E protocol lock | `de74fcfdd6283f2852cfea9add501df109f324871ee1f7ffdf30ce435dc9c663` |
| E3-E development freeze | `5a0b8dc74eb799d8639aa458b6702c9edb92395b3fd4fe520f1b902c4edc75a8` |
| E3-E holdout receipt | `00d80a2aa9f50e1c2e28b1d4cf457f3f232acc63ff0e4be7be269db11c91b8f3` |
| E3-E comparison artifact | `97f055944859bc513af3998ea3eabf4fa02fff710db68d6dac4288580c79ef41` |
| E3-C dense artifact input | `1b802acd3fdd1a99cedab811b3570d224f6c1b538a02a4d69781dc6b0bc5f22e` |
| E3-D RRF artifact input | `84b4292b829ca8713bdbc72e46bdf8fe6db7a3fa9e297416f75e35c048abbf7a` |

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

## Scope

No runtime defaults changed. Search, Ask, MCP, owner startup, Publication, ingestion, and runtime
strategy behavior are unchanged.

Candidate scoring uses query text, Evidence text, stable locator identity, source text digest,
document identity, arm provenance, and rank provenance. It does not use qrels, grades, query
category labels, split labels, or expected locators as candidate scoring input.

No API reranker, LLM judge, local cross-encoder, query rewrite, HyDE, segmentation, HTTP/UI,
Milvus, Redis, pgvector, LangChain, LlamaIndex, or LangGraph runtime contract was introduced.

## Review Notes

Self-review found no unresolved implementation findings. Remaining risks are evidence-scope risks:
the corpus is small, holdout is public after the protocol freeze, and holdout hard-negative failure
means this artifact should inform future design rather than be promoted.
