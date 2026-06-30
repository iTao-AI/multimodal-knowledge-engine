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
  `8c9352782ee7a7936804ba68edf135cc620b0886741de97bb1ae6c43204442da`.
- Comparison artifact SHA-256 is
  `fd958c2b87c3b5e971e5b17cd8ef1369a7dc0bd63f1ea83b8b207fa9e83b26e4`.

## Scope Limits

No runtime Search, Ask, MCP, owner startup, Publication, ingestion, or default changed. The branch
does not add API embeddings, reranking, query rewrite, segmentation, HTTP/UI, Milvus, Redis, or
pgvector. It did not rerun dense scoring for tuning and did not observe holdout after the valid
negative result.

## Task 11 Verification

- Focused RRF/protocol/workflow/artifact/CLI tests passed.
- Full verification passed: `uv run pytest -q`, `uv run ruff check .`, `uv run pyright`,
  `uv build`, `uv run mke proof run`, and `uv run mke demo --verify`.
- Canonical E1/E2/E3-A/E3-B/E3-C/E3-D validators passed after the final artifact identity refresh.
- Public-boundary scan found only synthetic command/test-string matches for `Traceback` redaction,
  not private paths, credentials, raw GStack artifacts, model cache, venv, or personal context.
- Cache-ready dense replay was attempted with the existing model cache but failed before replay
  because the embedding optional dependency was not installed (`huggingface_hub` and
  `sentence_transformers` unavailable). No dependency installation, download, or dense rescoring was
  performed.
- Final local `gstack-review` checklist pass found no unresolved critical or informational findings.

## Review Status

The implementation self-review found no scope expansion. The final local pre-PR review checklist
pass found no unresolved findings. Authoritative scheme-window review remains the next step before
any PR publication, so the scheme-window pre-PR review status is still `pending`; no PR has been
created.
