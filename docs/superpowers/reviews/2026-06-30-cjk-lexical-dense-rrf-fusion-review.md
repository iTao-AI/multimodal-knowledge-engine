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
  `b3396dbd0e79582fd374c0189a34a3581ffa7edfe82771c89c5ecd81fc82b477`.
- Comparison artifact SHA-256 is
  `a06a54b3d58417321192c535041bf798cbebfa5fac83a48c71a218cef8c33699`.

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
- Cache-ready dense replay is unmet optional corroboration, not a completed gate. It failed before
  replay because the embedding optional dependency was not installed (`huggingface_hub` and
  `sentence_transformers` unavailable). No dependency installation, download, or dense rescoring was
  performed.
- Scheme-window targeted re-review is `CLEAN / 0 findings`; no unresolved implementation findings
  remain.

## Review Status

The implementation self-review found no scope expansion. pre-PR review status:
scheme-window targeted re-review CLEAN / 0 findings, with no unresolved implementation findings.
PR #46 was created as Ready, passed post-merge CI and CodeQL, and was squash merged to
`main@158d0614fec2ef49da9db5882c589a832c48331f`.

Post-merge status: E3-D remains a valid negative. Holdout was not observed, no holdout receipt
exists, and `runtime_promotion_status=not_evaluated` remains frozen. No Search, Ask, MCP, owner
startup, Publication, ingestion, runtime default, artifact metric, protocol, qrel, or fixture
changes were made after the merge.
