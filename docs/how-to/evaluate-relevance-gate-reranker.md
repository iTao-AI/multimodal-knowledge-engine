# Evaluate The Relevance Gate Reranker Candidate

This guide reproduces the comparison-only E3-E candidate
`cjk-relevance-gate-reranker-v1`. It applies a deterministic relevance gate and reranker over the
E3-D lexical+dense union. It is not a runtime strategy and does not change Search, Ask, MCP, owner
startup, Publication, ingestion, or the runtime default.

## Result

```text
candidate_status=completed
development_status=passed
holdout_status=observed
holdout_gate_status=failed
selected_profile=strict-constraint
runtime_promotion_status=not_evaluated
```

Development selected `strict-constraint` because it passed the frozen refusal and hard-negative
gates while preserving the best available Recall@5 and nDCG@10 from allowed public Evidence
features. The public holdout was then observed exactly once after the exclusive development freeze.
Holdout recorded `holdout_gate_status=failed` because hard-negative failure was above the current
runtime comparator. This is useful evidence for future work, but it is not runtime promotion.

| Split | Recall@5 | nDCG@10 | MRR@5 | Unanswerable no-hit | Hard-negative failure |
|---|---:|---:|---:|---:|---:|
| Development | `0.727273` | `0.659562` | `0.645455` | `0.500000` | `0.100000` |
| Holdout | `0.636364` | `0.571515` | `0.537879` | `0.500000` | `0.142857` |

Development diagnostics:

- `input_union_count=62`
- `allowed_count=48`
- `dropped_grade2_count=2`
- `dense_only_recovery_retained_count=0`
- `lexical_only_recovery_retained_count=6`
- `union_only_recovery_retained_count=6`
- `empty_result_no_hit_count=6`

Canonical identities:

- Development freeze SHA-256:
  `a1d4144b9aa705a2706576049dbd7016ac4b315ca8eec31fc4245bd128c3ff11`
- Holdout receipt SHA-256:
  `1ca27d4c3aabb94de4f3c8633a32c1ea7b5dff42c99b91f7cbb6e8c93f966dbc`
- Comparison artifact SHA-256:
  `ce47ec469807a633036e705afb81522181745d7b9ae2e16274f8f5adbf60feda`
- Protocol lock SHA-256:
  `08835508f7bde601c3fa64b74ab4f7e1d4d48f500b4cdb82b84f5b83bed84e53`
- Canonical E3-C dense artifact SHA-256:
  `d259f0f1977be4520d01e8b9f7dd7061b0bf644889317e2f0e2cf51900d8106c`
- Canonical E3-D RRF artifact SHA-256:
  `e0881c07d54db5847db13611a3ce7e013284ede15c7d1b1237d6b3ffa8c5f7d5`

## Run Development

The output path uses exclusive-create semantics. Use an absent path when reproducing the
development freeze:

```bash
uv run mke eval retrieval-relevance-gate \
  --protocol tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json \
  --candidate cjk-relevance-gate-reranker-v1 \
  --development-only \
  --record-development-freeze benchmarks/retrieval/cjk-relevance-gate-reranker-v1-development-freeze.json \
  --json
```

If development records `development_status=valid_negative`, stop after development and do not
observe holdout. A valid negative is still a completed comparison artifact, not a failure to work
around by changing gates or adding new scoring inputs.

## Run Holdout

The holdout phase is allowed only after the exclusive development freeze records
`development_status=passed`. It creates a holdout receipt before scoring the public holdout:

```bash
uv run mke eval retrieval-relevance-gate \
  --protocol tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json \
  --candidate cjk-relevance-gate-reranker-v1 \
  --development-freeze benchmarks/retrieval/cjk-relevance-gate-reranker-v1-development-freeze.json \
  --record benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json \
  --record-holdout-receipt benchmarks/retrieval/cjk-relevance-gate-reranker-v1-holdout-receipt.json \
  --json
```

For the canonical E3-E result, the holdout gate failed honestly and no runtime promotion was
performed.

## Validate

The model-free validator independently recomputes feature rows, gate decisions, rerank order,
metrics, diagnostics, selected profile, and state from the frozen protocol and checked-in
artifacts:

```bash
uv run python -m mke.evaluation.relevance_gate_artifact validate \
  --artifact benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json \
  --protocol tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json \
  --repository .
```

Successful output is:

```text
relevance gate artifact valid
```

Dense cache-ready replay remains only an optional corroborating check when the embedding extra and
an already-populated local model cache are available. Do not install packages or download models
to satisfy E3-E artifact acceptance.

## Scoring Boundary

The deterministic relevance gate uses only query text, Evidence text, stable locator identity,
source text digest, document identity, arm provenance, and rank provenance. It does not read qrels,
grades, query category labels, split labels, or expected locators as candidate scoring input.
It does not read qrels, grades, query category labels, split labels, or expected locators as candidate scoring input.

No API reranker, LLM judge, local cross-encoder, query rewrite, HyDE, or segmentation is part of
this candidate. It also adds no HTTP/UI, Milvus, Redis, pgvector, LangChain, LlamaIndex, or
LangGraph runtime contract. Search, Ask, MCP, owner startup, Publication, ingestion, and runtime
defaults remain unchanged.

Boundary summary: API reranker, LLM judge, local cross-encoder, query rewrite, HyDE, segmentation,
Milvus, Redis, pgvector, LangChain, LlamaIndex, or LangGraph are out of scope.
