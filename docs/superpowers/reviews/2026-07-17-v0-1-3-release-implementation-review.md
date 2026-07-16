# v0.1.3 Release Closeout Implementation Review

Status: `PENDING AUTHORITATIVE REVIEW`

Date: 2026-07-17

## Scope

This review records the local release candidate through Tasks 1–4 of the approved v0.1.3
closeout plan. It covers package identity, the release presentation contract, current release
documentation, and the identity-only retrieval provenance closure. Publication has not started.

Starting commit: `c9dda6b78337f5ba89bb1a68da03368302947b16`.

Implemented commits:

1. `7918c82` — `chore(release): set v0.1.3 identity`
2. `a1d715b` — `test(release): define v0.1.3 presentation contract`
3. `e989bdc` — `docs(release): prepare v0.1.3 candidate`
4. `22e8bce` — `test(eval): refresh v0.1.3 release identities`

## Package And Lock Identity

`pyproject.toml`, `mke.__version__`, the root project entry in `uv.lock`, bootstrap tests, and the
installed-wheel release consumer smoke agree on `0.1.3`. The offline lock refresh changed only the
root project version. The build produced `multimodal_knowledge_engine-0.1.3-py3-none-any.whl` with
`Version: 0.1.3` metadata.

## Documentation Claim Matrix

- Compiled Library Export is the lead feature and is documented through
  `mke.compiled_library_export.v1`, readable `mke.compiled_markdown.v1`, and authoritative
  `mke.evidence_ref.v1` JSONL.
- PDF OCR Phase 0 remains bounded closed-protocol planning evidence. PP-OCRv6 medium is the
  selected production-planning baseline; PaddleOCR-VL 1.6 remains a comparison candidate.
- Production OCR, verified LLM Wiki compatibility, provider promotion, reconstructed layout,
  hosted integration, PyPI publication, deployment, and business-impact claims remain excluded.
- `cjk-active-scan-overlap-v1` remains the runtime default. Dense, RRF, and reranker artifacts
  remain comparison-only evidence.
- The completed `docs/releases/v0.1.2.md` record is unchanged.

## Evaluation Identity Closure

The version and release-documentation bytes required the established 21-path dependency-closed
provenance refresh. The changed set is exactly:

- `benchmarks/retrieval/retrieval-eval-v1-baseline.json`
- `tests/fixtures/retrieval-numeric-v1/protocol-lock.json`
- `benchmarks/retrieval/numeric-grouping-v1-comparison.json`
- `benchmarks/retrieval/retrieval-chinese-v1-baseline.json`
- `benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json`
- `tests/fixtures/retrieval-dense-v1/protocol-lock.json`
- `benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-development-freeze.json`
- `benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-holdout-receipt.json`
- `benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json`
- `tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json`
- `benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-development-freeze.json`
- `benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json`
- `tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json`
- `benchmarks/retrieval/cjk-relevance-gate-reranker-v1-development-freeze.json`
- `benchmarks/retrieval/cjk-relevance-gate-reranker-v1-holdout-receipt.json`
- `benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json`
- `docs/how-to/evaluate-dense-retrieval.md`
- `docs/how-to/evaluate-hybrid-rrf-retrieval.md`
- `docs/how-to/evaluate-relevance-gate-reranker.md`
- `tests/evaluation/test_relevance_gate_protocol.py`
- `tests/evaluation/test_relevance_gate_workflow.py`

The repository transaction refreshed E1 through E3-B. A call-owned rebinder with SHA-256
`1a8c416693a403c8e50acc60b68d7657a676d5a084b47da3b08c84950ce08f3b` generated E3-C through
E3-E candidates inside a detached validation mirror. E1, E2, E3-A, E3-B, E3-C, E3-D, and E3-E
normalized semantic projections are equal before and after. Observations, ordered results,
metrics, thresholds, gates, diagnostics, selected profile/candidate, status, and verdict did not
change.

## OCR Byte Identity

The four frozen OCR evidence files remain byte-identical to the approved baseline:

- `candidate-environments.json`: `d2232fcbd6775a9f03fa3d2a77b181987b5cfa43c9fdc1efcb48f08f01553d2a`
- `model-artifacts.json`: `3d1e8c45b7ed0c817acaeda3f51954b463016763690e09ca1f23162042219d6e`
- `provider-startup.json`: `1a159461fd73c7069905b0a085f5b900f4b1577dbf418a86adcf96b9c6354652`
- `phase0-scorecard.json`: `b84720bd33999ad333e3ac5105b7abd996ab910b3c9cd458f6c43e66fa709457`

## Verification Evidence

- Task 1 RED: `7 failed, 6 passed`; Task 1 GREEN: `13 passed`.
- Presentation audit fixture suite: `93 passed`.
- Release documentation contract suite: `120 passed`.
- Evaluation documentation/release slice: `39 passed, 680 deselected, 5 warnings`.
- Presentation audit: `status=ok`, zero violations.
- Artifact regression suite: `191 passed, 5 warnings`.
- Seven canonical retrieval validators: passed.
- `git diff --check`, exact changed-file audits, and public-neutral scans: passed.

Complete repository gates and exact candidate receipt/wheel/proof co-binding remain Task 5 work and
must be reported before authoritative review. No tag, GitHub Release, PyPI publication, deployment,
production OCR, or verified LLM Wiki compatibility claim exists.
