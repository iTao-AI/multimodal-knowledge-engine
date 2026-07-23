# Evaluate The Hybrid RRF Retrieval Candidate

This guide reproduces the comparison-only E3-D candidate
`cjk-active-scan-qwen3-rrf-v1`. It applies rank-only RRF over the current
`cjk-active-scan-overlap-v1` lexical observations and the canonical E3-C
`qwen3-embedding-0.6b-exact-v1` dense artifact.

## Result

```text
candidate_status=completed
development_status=valid_negative
holdout_status=not_observed
e3e_status=eligible
segmentation_status=eligible
runtime_promotion_status=not_evaluated
```

The development result is a valid negative. Fused ranking improved answerable quality, but its
unanswerable no-hit rate fell from lexical `0.500000` to `0.000000`. The frozen refusal gate
therefore failed and holdout was not observed. `e3e_status=eligible` and
`segmentation_status=eligible` are diagnostics-derived follow-up signals, not approval to add a
reranker or change page-level segmentation.

The dense arm uses the E3-C selected threshold `0.58`. Threshold filtering preserves each row's
recorded dense rank; it does not compress or reorder ranks. Lexical rank comes only from
`retrieved_locators` list order. Fusion uses `k=60`, equal arm weights, input depth `10`, output
depth `10`, and never combines raw lexical and dense scores.

| Arm | Recall@5 | nDCG@10 | MRR@5 | Unanswerable no-hit | Hard-negative failure |
|---|---:|---:|---:|---:|---:|
| Fused RRF | `0.772727` | `0.735153` | `0.690909` | `0.000000` | `0.200000` |
| Lexical runtime | `0.681818` | `0.643390` | `0.636364` | `0.500000` | `0.300000` |
| Dense E3-C | `0.545455` | `0.574244` | `0.545455` | `0.500000` | `0.000000` |

Development diagnostics:

- `union_grade2_coverage_at_10=18`
- `fused_lost_union_grade2_count=1`
- `ranking_headroom_count=1`
- `lexical_only_recovery_count=6`
- `dense_only_recovery_count=2`
- `both_arm_recovery_count=10`
- `neither_arm_miss_count=4`

Canonical identities:

- Development freeze SHA-256:
  `c43cdebf9f8bf541a285cd4d459e98c5fdfc6778b1fa4fdeddce4342304450fa`
- Comparison artifact SHA-256:
  `581decff2c271150f7e9bd80b289b23963e1b5ed9fc6a23977241a18f414270e`
- Canonical E3-C dense artifact SHA-256:
  `935431ce7a549f43216d78c2186e2c62c3aad2f67b84fc404e26e03156e519cc`
- Current runtime semantic digest:
  `sha256:b32dc4a1479cb3ea8e0ebedf2c27b04a10a6d91eee96e0cd0308bcf921e97959`

## Run Development

The output paths use exclusive-create semantics. Use absent paths when reproducing the recording:

```bash
uv run mke eval retrieval-hybrid-rrf \
  --protocol tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json \
  --candidate cjk-active-scan-qwen3-rrf-v1 \
  --dense-artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --development-only \
  --record-development-freeze benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-development-freeze.json \
  --json
```

For this canonical result, stop after development because
`development_status=valid_negative`. Do not run the holdout command and do not create a holdout
receipt.

The conditional holdout command is documented for the frozen protocol contract only. It may run
only when an exclusive development freeze records `development_status=passed`:

```bash
uv run mke eval retrieval-hybrid-rrf \
  --protocol tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json \
  --candidate cjk-active-scan-qwen3-rrf-v1 \
  --dense-artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --development-freeze benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-development-freeze.json \
  --record benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json \
  --record-holdout-receipt benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-holdout-receipt.json \
  --json
```

## Validate

The model-free validator independently recomputes the development result from the frozen protocol
and canonical dense artifact:

```bash
uv run python -m mke.evaluation.hybrid_rrf_artifact validate \
  --artifact benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json \
  --protocol tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json \
  --dense-artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --repository .
```

Dense cache-ready replay is an optional corroborating check when the embedding extra and an
already-populated local model cache are available. It is not an E3-D artifact acceptance gate and
does not retune the selected threshold or regenerate E3-D ranks:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 UV_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
uv run python -m mke.evaluation.dense_replay validate \
  --artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --protocol tests/fixtures/retrieval-dense-v1/protocol-lock.json \
  --model-cache <model-cache> \
  --repository .
```

## Scope

E3-D changes no Search, Ask, MCP, owner startup, Publication, ingestion, or runtime default
behavior. It adds no API adapter, reranker, query rewrite, segmentation, HTTP/UI, Milvus, Redis, or pgvector
integration. The evidence comes from a small public Chinese page-level corpus and is not a
production-quality or statistical-significance claim.
