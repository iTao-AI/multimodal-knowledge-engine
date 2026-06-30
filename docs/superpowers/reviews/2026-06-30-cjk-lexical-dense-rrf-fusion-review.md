# CJK Lexical Dense RRF Fusion Implementation Review

Date: 2026-06-30

Scope: comparison-only E3-D rank-only RRF candidate
`cjk-active-scan-qwen3-rrf-v1`.

## Result

Development completed as a valid negative. Fused Recall@5 was `0.772727`, nDCG@10 was
`0.735153`, and MRR@5 was `0.690909`, but unanswerable no-hit fell to `0.000000` from the lexical
arm's `0.500000`. The frozen development gate therefore blocked holdout: holdout was not observed,
no holdout receipt exists, and `runtime_promotion_status=not_evaluated` remains frozen.

Diagnostics record union grade-2 coverage `18`, one fused ranking-headroom case, six lexical-only
recoveries, two dense-only recoveries, ten shared recoveries, and four misses from both arms. They
make future E3-E and segmentation investigations eligible; they do not implement either path.

## Evidence Integrity

- Lexical rank is derived only from `retrieved_locators` list order.
- Dense rows are filtered at E3-C threshold `0.58` while preserving recorded dense ranks.
- RRF consumes ranks only, with deterministic Evidence identity, dedupe, and tie-breaks.
- The canonical comparison artifact validates by independent recomputation.
- E1/E2/E3-A/E3-B normalized semantics remained equal before identity-only refresh.
- E1/E2/E3-A/E3-B/E3-C/E3-D canonical validators pass after the refresh chain.
- Development freeze SHA-256 is
  `4f772e358e18bd29a62d343d8476e544518529eaeac08cf663cd0ae703af6216`.
- Comparison artifact SHA-256 is
  `52b8c97a8e8eec8f7efe321eb62b15346cba389cd273203339008c577ab95388`.

## Scope Limits

No runtime Search, Ask, MCP, owner startup, Publication, ingestion, or default changed. The branch
does not add API embeddings, reranking, query rewrite, segmentation, HTTP/UI, Milvus, Redis, or
pgvector. It did not rerun dense scoring for tuning and did not observe holdout after the valid
negative result.

## Review Status

The implementation self-review found no scope expansion. Authoritative pre-PR review remains
`pending` in the scheme-window; no PR has been created.
