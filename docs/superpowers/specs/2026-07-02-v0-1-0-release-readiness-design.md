# v0.1.0 Release Readiness Design

Status: approved for implementation planning.

Planning base: `main@24691fb0805e4a46bcad41f1699cbef52e65589a`.

## Context

MKE now has enough repository-visible product evidence for a first small release. The release should
not claim a complete RAG platform. It should present the current product slice accurately:

- local-first `Library` / `Source` / `Run` / `Evidence` / `Publication` lifecycle;
- text-layer PDF and short local video ingestion;
- stable Search and Ask over active Publications;
- CLI and stdio MCP over the same application contract;
- deterministic `mke proof run` and `mke demo --verify`;
- bounded Chinese retrieval runtime through `cjk-active-scan-overlap-v1`;
- comparison-only retrieval evidence for dense, RRF, and relevance-gate/reranker candidates.

The current repository still reads like an active implementation log in several public entry points.
`pyproject.toml` and `src/mke/__init__.py` still report `0.0.0`. E3-C, E3-D, and E3-E are documented,
but their relationship to the shipped runtime is easy to misread without a release-level decision
table. The release needs a presentation cleanup, version identity, release notes, and a consumer
smoke path before tagging `v0.1.0`.

## Release Goal

Ship `v0.1.0` as the first public small version of MKE:

> A local-first, Agent-callable Evidence engine with CLI/MCP contracts, deterministic proof, bounded
> PDF/video ingestion, active-Publication retrieval, and a reproducible retrieval evaluation program.

The release is not a claim that dense, hybrid, RRF, reranker, query rewrite, OCR, HTTP, or UI runtime
capabilities are complete.

## Non-Goals

Do not add product functionality as part of `v0.1.0` readiness:

- no dense runtime promotion;
- no hybrid/RRF runtime;
- no reranker runtime;
- no cross-encoder;
- no query rewrite, HyDE, or segmentation rewrite;
- no OCR migration from the legacy project;
- no HTTP server, Web UI, or public deployment surface;
- no LangChain, LlamaIndex, LangGraph, Milvus, Redis, pgvector, or hosted service contract;
- no model download as a core release gate.

These remain future `0.1.x` polish or `0.2.0` capability work depending on contract impact.

## Release Scope

The release readiness work has three stages.

### Stage 1: Release presentation readiness PR

This PR prepares repository-visible release identity and public documentation.

It should:

- bump the package version from `0.0.0` to `0.1.0`;
- add a `CHANGELOG.md` entry and `docs/releases/v0.1.0.md`;
- rewrite README and README_CN into release-first entry points;
- add an E3 decision table that separates shipped runtime from comparison evidence;
- add a release presentation audit script and tests;
- run `gstack-document-release` as the documentation audit before PR review;
- keep runtime behavior unchanged.

### Stage 2: Release consumer smoke PR

This PR proves the release can be consumed outside the source checkout.

It should:

- build a wheel from the current branch;
- install it in a fresh temporary environment;
- run core CLI proof commands from outside the repository;
- verify package identity comes from installed site-packages, not the source tree;
- run a lightweight MCP contract or owner-startup smoke;
- keep optional `[embedding]` and `[transcription]` extras separate from the core release gate;
- document any host prerequisites and fail closed on missing host capabilities.

### Stage 3: Tag and release

After Stages 1 and 2 are merged:

- create tag `v0.1.0` at the verified release commit;
- create the GitHub Release with the checked-in release notes;
- verify release archive identity and run post-release smoke from a clean temp directory;
- only then record demo/video and portfolio-sync handoffs.

## E3 Release Decision Table

The release must include this decision boundary in README, release notes, or both:

| Stage | Result | Runtime impact |
|---|---|---|
| E3-A Chinese baseline | Baseline recorded; current lexical miss modes identified. | None |
| E3-B CJK lexical candidate | `cjk-trigram-overlap-v1` comparison passed. | None |
| E3-F CJK active-scan runtime | `cjk-active-scan-overlap-v1` promoted as default owner-startup strategy. | Shipped runtime |
| E3-C dense candidate | Qwen3 exact-cosine dense comparison completed; E3-D eligible. | None |
| E3-D RRF fusion | Valid negative; recall improved but refusal collapsed. | None |
| E3-E relevance gate/reranker | Development passed, holdout observed, holdout gate failed. | None |

This table is a release safety requirement. It prevents comparison-only artifacts from being
misread as shipped runtime features.

## Documentation Shape

Use Diataxis as an audit lens, not as a reason to generate unnecessary pages.

Required release documents:

| File | Purpose |
|---|---|
| `README.md` | First public entry point; outcome-first English release overview. |
| `README_CN.md` | Chinese release overview with the same capability and non-goal boundaries. |
| `CHANGELOG.md` | Versioned release history. |
| `docs/releases/v0.1.0.md` | Release notes, verification, scope, risk, and upgrade path. |
| `docs/README.md` | Documentation navigation, including release notes and proof guides. |
| `docs/how-to/verify-release.md` | Post-release verification and consumer-smoke instructions. |

If `gstack-document-release` finds a critical documentation gap, the implementation should decide
whether to fill it in the release PR or defer it explicitly. Use `gstack-document-generate` only for
clear missing standalone docs, not to rewrite the whole documentation set.

## Release Audit Contract

Add a repository-local audit that fails on presentation drift. The audit should check at least:

- version identity matches `0.1.0`;
- README and README_CN mention the current runtime default;
- README and release notes explicitly state dense/RRF/reranker are comparison-only;
- release notes link proof, demo, CLI, MCP, and retrieval evaluation docs;
- no stale `pending`, `not merged`, or pre-release status phrases appear in release-facing files;
- no private local paths, raw GStack artifacts, local model cache paths, credentials, or stack traces appear in release-facing files;
- `CHANGELOG.md`, `docs/releases/v0.1.0.md`, and package version agree.

The audit does not replace full tests. It protects the public presentation surface.

## Verification Gates

Stage 1 must pass:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
uv run python scripts/release_presentation_audit.py --root .
git diff --check origin/main...HEAD
```

Stage 2 must additionally prove installed-package consumption from a fresh temp environment.

Optional extras should be verified separately and reported separately. A missing local model cache
or optional dependency must not fail the core release if the core package, proof, demo, CLI, and MCP
contracts pass.

## Version Policy

Use:

- `v0.1.0` for this first public small release;
- `v0.1.x` for release polish, docs, small bug fixes, and non-contract-breaking DX improvements;
- `v0.2.0` for dense/hybrid/reranker runtime promotion, query rewrite, segmentation, OCR, HTTP/UI,
  or other contract-expanding work.

## Risks

| Risk | Mitigation |
|---|---|
| README overclaims dense/hybrid/reranker runtime support | E3 decision table plus release audit checks. |
| Release tag points at a commit without consumer-smoke evidence | Stage 2 must merge before tag/release. |
| Optional model/cache proof blocks the core release | Treat optional extras as separate reported gates. |
| Docs remain too long and development-log shaped | Rewrite entry points around current capability, proof, and explicit non-goals. |
| Future work disappears from the roadmap | Release notes should list deferred `0.1.x` and `0.2.0` candidates without approving them. |

## Approval

Approved next action: create an implementation branch for Stage 1 release presentation readiness.
Do not tag, release, push, create PR, or run external publication steps without explicit user
authorization.
