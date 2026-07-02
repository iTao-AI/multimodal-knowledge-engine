# Documentation

This repository uses Diataxis plus architecture decision records and approved implementation
history. Start with the release and proof guides unless you are auditing implementation history.

## Release And First Run

- [v0.1.0 Release Notes](./releases/v0.1.0.md)
- [Verify The Release](./how-to/verify-release.md)
- [Getting Started](./tutorials/getting-started.md)
- [Run The Local Product Proof](./how-to/run-local-product-proof.md)
- [Use MKE As A Local MCP Server](./how-to/use-mke-mcp.md)

`v0.1.0` ships `cjk-active-scan-overlap-v1` as the current owner-startup CJK runtime strategy.
E3-C dense, E3-D RRF, and E3-E relevance-gate/reranker records are comparison-only evidence.

## Current Product Contracts

- [Architecture](./explanation/architecture.md)
- [Public Contracts](./reference/contracts.md)
- [CLI Reference](./reference/cli.md)
- [Enable Bounded CJK Retrieval](./how-to/enable-cjk-retrieval.md)
- [Use Local Transcription](./how-to/use-local-transcription.md)

## Retrieval Evaluation

- [Run Retrieval Evaluation](./how-to/run-retrieval-evaluation.md)
- [Evaluate The Numeric Retrieval Candidate](./how-to/evaluate-numeric-retrieval.md)
- [Run The Chinese Retrieval Evaluation](./how-to/run-chinese-retrieval-evaluation.md)
- [Evaluate The Dense Retrieval Candidate](./how-to/evaluate-dense-retrieval.md)
- [Evaluate The Hybrid RRF Retrieval Candidate](./how-to/evaluate-hybrid-rrf-retrieval.md)
- [Evaluate The Relevance Gate Reranker Candidate](./how-to/evaluate-relevance-gate-reranker.md)

The runtime boundary is fixed for `v0.1.0`: only E3-F changes the default retrieval strategy.
Dense, RRF, and relevance-gate/reranker artifacts remain comparison-only and do not change Search,
Ask, MCP, owner startup, Publication, ingestion, or runtime defaults.

## Documentation Areas

| Area | Purpose |
|---|---|
| `tutorials/` | Learning-oriented, verified walkthroughs |
| `how-to/` | Task-oriented operational guides |
| `reference/` | Exact public contracts, configuration, and commands |
| `explanation/` | Architecture and domain reasoning |
| `decisions/` | Long-lived accepted architecture decisions |
| `superpowers/specs/` | Approved public-neutral designs |
| `superpowers/plans/` | Executable implementation plans |
| `superpowers/reviews/` | Durable public-neutral plan and PR review reports |

Documentation changes ship in the same PR as affected behavior. Private generated artifacts and
private planning notes do not belong in this repository.

## Current Decisions

- [ADR-0001](./decisions/0001-local-first-pilot-architecture.md) defines the local-first Pilot architecture.
- [ADR-0002](./decisions/0002-source-publication-and-active-search-projection.md) defines Source Publication and active Search projection semantics.
- [ADR-0003](./decisions/0003-video-dependency-and-transcription-strategy.md) defines the short-video dependency and transcription strategy.
- [ADR-0004](./decisions/0004-pymupdf-pdf-intake-adapter.md) defines the PyMuPDF PDF intake adapter and licensing boundary.
- [ADR-0005](./decisions/0005-optional-local-command-transcription-provider.md) defines the optional local-command transcription provider boundary.
- [ADR-0006](./decisions/0006-first-party-local-transcription-runtime.md) defines the cache-only faster-whisper runtime.
- [ADR-0007](./decisions/0007-numeric-grouping-query-policy.md) promotes the bounded numeric grouping query policy and defines rollback.
- [ADR-0008](./decisions/0008-cjk-active-scan-retrieval-strategy.md) defines `cjk-active-scan-overlap-v1`.

## Implementation History

Superpowers docs are public-neutral implementation history. They are useful for audits and future
planning, but release readers should start from release notes, how-to guides, reference docs, and
ADRs.

- [v0.1.0 Release Readiness Design](./superpowers/specs/2026-07-02-v0-1-0-release-readiness-design.md)
- [v0.1.0 Release Readiness Implementation Plan](./superpowers/plans/2026-07-02-v0-1-0-release-readiness-implementation.md)
- [v0.1.0 Release Readiness Plan Review](./superpowers/reviews/2026-07-02-v0-1-0-release-readiness-review.md)
- [CJK Lexical Runtime Promotion Implementation Review](./superpowers/reviews/2026-06-27-cjk-active-scan-runtime-promotion-implementation-review.md)
- [Local Dense Retrieval Candidate Implementation Review](./superpowers/reviews/2026-06-28-local-dense-retrieval-candidate-review.md)
- [CJK Lexical Dense RRF Fusion Implementation Review](./superpowers/reviews/2026-06-30-cjk-lexical-dense-rrf-fusion-review.md)
- [CJK Relevance Gate Reranker Implementation Review](./superpowers/reviews/2026-06-30-cjk-relevance-gate-reranker-review.md)

## Development Verification

Use the verified bootstrap commands in the [Getting Started tutorial](./tutorials/getting-started.md)
before changing product behavior.
