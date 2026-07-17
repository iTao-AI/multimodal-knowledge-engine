# v0.1.3 Release Closeout Implementation Review

Status: `ACCEPTED / RELEASED / POST-RELEASE DOCS PENDING REVIEW`

Date: 2026-07-17

## Scope

At the original pre-publication candidate-review checkpoint, this review recorded the local release
candidate through Tasks 1–4 of the approved v0.1.3 closeout plan. That checkpoint covered package
identity, the release presentation contract, current release documentation, and the identity-only
retrieval provenance closure. Publication had not started at that checkpoint.

Starting commit: `c9dda6b78337f5ba89bb1a68da03368302947b16`.

Implemented commits:

1. `7918c82` — `chore(release): set v0.1.3 identity`
2. `a1d715b` — `test(release): define v0.1.3 presentation contract`
3. `e989bdc` — `docs(release): prepare v0.1.3 candidate`
4. `22e8bce` — `test(eval): refresh v0.1.3 release identities`
5. `85bd56e` — `docs(release): record v0.1.3 candidate state`
6. `402ef15` — `fix(release): close presentation review gaps`
7. `fbb429b` — `fix(release): audit wrapped presentation claims`

Reviewed HEAD: `fbb429bfa53d5faab395c3f493c2a7fa25eedc32`.

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

At that candidate-review checkpoint, no tag, GitHub Release, PyPI publication, deployment,
production OCR, or verified LLM Wiki compatibility claim existed.

## Authoritative Review Repair

The first authoritative review found two bounded release-closeout blockers:

1. the presentation audit accepted affirmative claims outside the approved OCR, deployment,
   adoption, impact, registry-publication, and GitHub Release asset boundaries; and
2. the public release-verification guide did not co-bind the Compiled Library Export proof to the
   independently validated candidate wheel, or include the complete archive Evidence-provenance
   and standalone Compiled Library Export smoke.

The repair adds mutation coverage for each prohibited affirmative claim, explicit negation-aware
PyPI and package-registry checks, and a live-checkout acceptance test alongside the existing
missing-release-note regression. The public guide now includes a closed canonical candidate
validator, exact compiled-proof digest equality, Evidence provenance proof, and a real archive
`mke library export` plus standalone consumer smoke. Legitimate negative boundary statements
remain accepted.

These tracked changes invalidate the earlier Task 5 candidate receipt, wheel, installed smoke, and
compiled-proof output. None is reused or presented as current evidence.

## Wrapped-Claim Residual And Resolution

The first repair still evaluated a physical Markdown line before its neighboring context. An
affirmative claim whose key phrase crossed an ordinary soft line break could therefore remain
undetected. Commit `fbb429bfa53d5faab395c3f493c2a7fa25eedc32` replaced that path with one
logical-paragraph evaluation, with explicit boundaries for blank lines, fenced blocks, headings,
tables, blockquotes, and distinct list items.

Mutation coverage now rejects wrapped provider promotion, public OCR runtime, extra GitHub Release
assets, package-registry publication, deployment, production adoption, and business impact exactly
once. Wrapped legitimate negations remain accepted, distinct Markdown blocks are not combined, and
the live repository audit remains clean.

## Targeted Authority Re-review

Targeted authority re-review of reviewed HEAD
`fbb429bfa53d5faab395c3f493c2a7fa25eedc32` returned `CLEAN`. The two initial findings and the
wrapped-claim residual are closed. No finding remains.

Verdict: `ACCEPTED / CLEARED FOR RELEASE-CANDIDATE PR`.

The review-closure commit invalidated all earlier candidate wheel, receipt, installed-smoke, and
compiled-proof evidence. The complete candidate authority was rebuilt from clean commit
`57133fcdb7e3c49582028aa02b51e2b1e32c5378` before PR action.

## Final Candidate And Publication

PR #73 preserved reviewed head `57133fcdb7e3c49582028aa02b51e2b1e32c5378`. Its required Python
3.12/3.13, embedding-extra, source-pack, compiled-export, and CodeQL checks passed before the PR was
squash-merged. Merge commit `86b8a2d85631f5e94afa49186909ac62ffd54a15` has parent
`5d707cfcc98da8ce76d31238c14158cd78b03803`; its tree
`88862bf57464e4eb630eb938a573d5188e3feed6` exactly equals the reviewed feature tree.

Fresh exact-main verification produced:

- full pytest: `2345 passed, 5 skipped, 5 warnings`;
- Ruff: passed; Pyright: 0 errors; build: passed;
- product proof: 8/8; demo, local-knowledge, Evidence-provenance, and presentation audit: passed;
- artifact regression: `191 passed, 5 warnings`; all seven canonical validators: passed;
- candidate wheel `multimodal_knowledge_engine-0.1.3-py3-none-any.whl`, `309326` bytes, SHA-256
  `50bccd685957c1b21e9b45d066060f0a89dd7f4e71e6f86b3546ce3ea4a2b036`;
- canonical receipt digest `b6527b462c1f76907c46477c30fff1202dfc44ba3c8cea17cb633072c9a1accc`,
  receipt file SHA-256 `fac2dc1b1166712944268e389beef1cd27e740ce32b4f4fa6ffad1808434e4f6`,
  and `source_commit=86b8a2d85631f5e94afa49186909ac62ffd54a15`;
- receipt-bound installed smoke: passed; and
- compiled-export proof: passed with two interpreters and exact wheel-digest equality.

The post-merge workflows for the exact merge SHA passed. Annotated tag object
`447ebdf7416b6c6e25c8f6d2017d1ef48b465c0f` peels to the merge commit. The public, latest-at-
publication, non-draft, non-prerelease GitHub Release was published at `2026-07-17T02:10:45Z`
with zero extra assets.

The public archive `multimodal-knowledge-engine-0.1.3.tar.gz` is `3691525` bytes with SHA-256
`a8f0a595f6f039628feb2a9d3e13237b37b000aa311e1b7b7b013e0e8303496e`. Locked archive smoke
passed product proof 8/8, demo, local-knowledge, Evidence provenance, and a real Compiled Library
Export accepted by the standalone consumer with two sources and three Evidence records.

No package registry publication, deployment, production OCR, verified LLM Wiki compatibility,
runtime promotion, adoption, or business-impact claim was made.
