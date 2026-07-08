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
  `c16e3918a537382bed745d13d8f6a507589d1a5b73c82de822c0163ce79adb51`
- Holdout receipt SHA-256:
  `5bd7e481f4fc516cd6c738add11a01243ece6a9ccf564d748e202fe949165c41`
- Comparison artifact SHA-256:
  `6e65a73600102a714a557b9e2ecebcce7e467bb4dc7716c767f7742da6275257`
- Protocol lock SHA-256:
  `d9f29327c02d3448e0f4e7931e8382e9427d59174e6b196151be06bf6e5f3442`
- Canonical E3-C dense artifact SHA-256:
  `c9b0e9eabaecd358fc706ffa665742665e44ffda5d560cb065572c42644e96ea`
- Canonical E3-D RRF artifact SHA-256:
  `00a0b3d8c2152a895f298aa3dd1257e8c5871d647db6de2b77d4570b3d11ab4b`

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
