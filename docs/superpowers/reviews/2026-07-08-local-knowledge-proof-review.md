# Local Knowledge Proof Implementation Review

## Status

- Review date: 2026-07-08.
- Scope: public-safe synthetic local knowledge proof on
  `codex/v0-1-1-local-knowledge-proof`.
- Result: both authoritative P1 findings were remediated with adversarial regression tests.
- Targeted re-review: `CLEAN / 0 findings` at implementation commit `0cdb4f9`.
- Full review: not repeated after the targeted remediation review.

The related implementation history is recorded in the
[Local Knowledge Proof Implementation Plan](../plans/2026-07-07-local-knowledge-proof-implementation.md)
and the durable product boundary remains defined by the
[Local Knowledge Proof Design](../specs/2026-07-07-local-knowledge-proof-design.md).

## Scope Check

The reviewed change proves the existing shipped path from repository-authored synthetic local
PDF files through real stdio MCP ingest Runs, published Evidence, active Publication Search,
evidence-only Ask, and `insufficient_evidence` refusal.

The remediation changed only proof validation, adversarial proof tests, and the canonical E1
source-content identity. It did not change MCP schemas, runtime behavior, fixture text, proof
output structure, Search or Ask contracts, or Publication semantics. Dense retrieval, RRF,
reranking, HTTP, UI, OCR, API adapters, network access, and model downloads remain out of scope.

## Authoritative Findings And Resolution

| Severity | Finding | Resolution | Regression evidence |
|---|---|---|---|
| P1 | Search and Ask accepted page Evidence based only on shape and count. Evidence from unrelated content, including plausible content that reused query terms, could pass; negative or reversed page locators were also accepted. | Evidence is now bound to the fixed synthetic fixture content by SHA-256, query terms remain required, and page locators require `start >= 1` and `end >= start`. | Adversarial cases cover unrelated text, same-keyword fabricated text, negative page starts, and reversed page ranges. |
| P1 | Published Run inspection required only a non-empty events list, so malformed entries, index gaps, missing lifecycle stages, or events after activation could pass. | Run events now require the public event shape, contiguous indices beginning at one, the required lifecycle in order, and final `publication_activated`. | Adversarial cases cover malformed shape, discontinuous indices, missing `candidate_validated`, and a post-activation event. |

The first remediation commit, `ea2e738`, added lifecycle and locator validation. The follow-up
commit, `0cdb4f9`, tightened Evidence binding from query-term matching to exact fixture-content
identity before targeted re-review.

## Verification

- Targeted local knowledge proof suite: `19 passed`.
- Full test suite: `1319 passed, 5 skipped`; the five existing PyMuPDF/SWIG deprecation warnings
  remained.
- Ruff: clean.
- Pyright: `0 errors, 0 warnings, 0 informations`.
- Build: source distribution and wheel built successfully for package version `0.1.0`.
- Existing product proof: `8 passed, 0 failed`.
- Existing demo: `result=passed`.
- Local knowledge proof: `status=passed` with its existing public aggregate output structure.
- Release presentation audit: `status=ok`, zero violations.
- Canonical E1 baseline: validated after the restricted source-identity refresh; historical
  observations were unchanged.
- Diff check: clean.
- Targeted re-review: `CLEAN / 0 findings`.

## Remaining Risks

- Exact Evidence-content hashes intentionally bind this proof to the committed synthetic fixture
  text. An intentional fixture revision must update the proof identity and canonical E1 source
  identity together.
- This proof demonstrates a deterministic two-document local knowledge case. It is not a general
  retrieval-quality benchmark and does not promote comparison-only dense, RRF, or reranker
  evidence into the shipped runtime.

## CI Identity Refresh

PR CI exposed stale canonical artifact identities after the proof source files entered the complete
`src/mke/**/*.py` inventory. The recoverable artifact refresh updated only E2 `source` and E3-A
`source_identity`. The existing dependency graph then required provenance-only rebinding through
E3-C, E3-D, and E3-E, including their protocol locks and derived freeze/receipt digests.

Normalized before/after comparisons confirmed unchanged observations, metrics, thresholds, gates,
diagnostics, and verdict/status fields. E1 and E3-B remained byte-identical. No model execution,
new qrel input, holdout observation, Search/Ask/runtime change, or retrieval promotion occurred.
All E1 through E3-E canonical validators passed, and the related artifact suite passed `147` tests.

## Merge Closeout

[PR #58](https://github.com/iTao-AI/multimodal-knowledge-engine/pull/58) was squash-merged as
`4e52542610b803df7bfe6dcb7648d464484e8f81` on 2026-07-08. The resulting `main` push passed the
Python 3.12 and 3.13 CI jobs, both embedding-extra jobs, and CodeQL analysis for Python and Actions.
The feature branches and isolated implementation worktree were removed only after those checks
completed successfully.

This merge did not create a version tag, GitHub Release, or PyPI publication. Those remain separate
release actions.
