# Documentation

This repository uses Diataxis plus architecture decision records and approved implementation
history. Start with the release, proof, MCP, architecture, and evaluation guides unless you are
auditing implementation history.

## Release And First Run

- [v0.1.3 Release Notes](./releases/v0.1.3.md)
- [v0.1.2 Release Notes](./releases/v0.1.2.md)
- [v0.1.1 Release Notes](./releases/v0.1.1.md)
- [v0.1.0 Release Notes](./releases/v0.1.0.md)
- [Verify The Release](./how-to/verify-release.md)
- [Getting Started](./tutorials/getting-started.md)
- [Run The Local Product Proof](./how-to/run-local-product-proof.md)
- [Run The Local Knowledge Proof](./how-to/run-local-knowledge-proof.md)
- [Use MKE As A Local MCP Server](./how-to/use-mke-mcp.md)
- [MCP Contract Reference](./reference/mcp-contract.md)
- [Run The Evidence Provenance Proof](./how-to/run-evidence-provenance-proof.md)
- [Run The Consumer Source-Pack Proof](./how-to/run-consumer-source-pack-proof.md) documents a
  source-built proof for the current source checkout as a `v0.1.3` release-candidate verification
  gate.

`v0.1.3` leads with Compiled Library Export through `mke.compiled_library_export.v1`, readable
`mke.compiled_markdown.v1`, and authoritative `mke.evidence_ref.v1` JSONL. It retains the external
same-wheel Python 3.12/3.13 source-pack proof and owner lifecycle hardening while keeping
`cjk-active-scan-overlap-v1` as the current owner-startup CJK runtime strategy.
E3-C dense, E3-D RRF, and E3-E relevance-gate/reranker records are comparison-only evidence and
do not change Search, Ask, MCP, owner startup, Publication, ingestion, or runtime defaults.

## Proof And Product Contracts

- [Architecture](./explanation/architecture.md)
- [Public Contracts](./reference/contracts.md)
- [CLI Reference](./reference/cli.md)
- [Direct-Audio Dependency And License Evidence](./reference/direct-audio-dependency-and-license-evidence.md)
  records the PR A dependency, license, and synthetic-fixture feasibility receipt; the accepted
  PR C product candidate is documented separately.
- [Enable Bounded CJK Retrieval](./how-to/enable-cjk-retrieval.md)
- [Use Local Transcription](./how-to/use-local-transcription.md)
- [Export A Compiled Library](./how-to/export-compiled-library.md)
- [Run The Compiled Library Export Proof](./how-to/run-compiled-library-export-proof.md)
- [Use bounded direct audio](./how-to/use-direct-audio.md) — accepted v0.1.4 candidate golden paths
- [Run the direct-audio proof](./how-to/run-direct-audio-proof.md) — model-free first; terminal proof requires separate authorization

The architecture guide is the shortest path to the Evidence lifecycle, active Publication
semantics, SQLite domain truth, rebuildable retrieval projections, and the shared CLI/MCP
application contract.

The compiled Library guides document the read-only export command, exact portable schemas,
transactional manifest-last publication, and generic installed-wheel consumer proof. LLM Wiki
compatibility has separate independently verified external downstream evidence; LLM Wiki remains
outside MKE runtime and Evidence authority.

## Architecture And Evaluation

- [Run Retrieval Evaluation](./how-to/run-retrieval-evaluation.md)
- [Evaluate The Numeric Retrieval Candidate](./how-to/evaluate-numeric-retrieval.md)
- [Run The Chinese Retrieval Evaluation](./how-to/run-chinese-retrieval-evaluation.md)
- [Prepare Local Embeddings](./how-to/prepare-local-embeddings.md)
- [Evaluate The Dense Retrieval Candidate](./how-to/evaluate-dense-retrieval.md)
- [Evaluate The Hybrid RRF Retrieval Candidate](./how-to/evaluate-hybrid-rrf-retrieval.md)
  records comparison-only `cjk-active-scan-qwen3-rrf-v1` rank-only RRF evidence; it
  does not combine raw lexical and dense scores.
- [Evaluate The Relevance Gate Reranker Candidate](./how-to/evaluate-relevance-gate-reranker.md)

The runtime boundary remains fixed for `v0.1.3`: only E3-F changes the default retrieval strategy.
Comparison-only dense preparation does not change normal Search, Ask, MCP, or the runtime default.
Dense, RRF, and relevance-gate/reranker artifacts remain evaluation artifacts, not runtime
features.

## Documentation Areas

| Area | Purpose |
|---|---|
| `tutorials/` | Learning-oriented, verified walkthroughs |
| `how-to/` | Task-oriented operational guides |
| `reference/` | Exact public contracts, configuration, and commands |
| `explanation/` | Architecture and domain reasoning |
| `decisions/` | Long-lived accepted architecture decisions |
| [`superpowers/`](./superpowers/README.md) | Public-neutral implementation history and artifact storage |
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
- [ADR-0009](./decisions/0009-versioned-evidence-provenance-contract.md) defines the additive strict Evidence provenance read contract.
- [ADR-0010](./decisions/0010-pdf-ocr-evaluation-manifest-fingerprint.md) defines the evaluation-only PDF OCR manifest fingerprint and its non-production boundary.
- [ADR-0011](./decisions/0011-bounded-direct-audio-intake.md) defines the accepted v0.1.4 candidate's bounded audio authority and rollback.

## Implementation History

[Superpowers Workspace](./superpowers/README.md) records public-neutral implementation history. It
is useful for audits and future planning, but release readers should start from release notes,
how-to guides, reference docs, and ADRs.

- [v0.1.0 Release Readiness Design](./superpowers/specs/2026-07-02-v0-1-0-release-readiness-design.md)
- [v0.1.0 Release Readiness Implementation Plan](./superpowers/plans/2026-07-02-v0-1-0-release-readiness-implementation.md)
- [v0.1.0 Release Readiness Plan Review](./superpowers/reviews/2026-07-02-v0-1-0-release-readiness-review.md)
- [CJK Lexical Runtime Promotion Implementation Review](./superpowers/reviews/2026-06-27-cjk-active-scan-runtime-promotion-implementation-review.md)
- [Local Dense Retrieval Candidate Implementation Review](./superpowers/reviews/2026-06-28-local-dense-retrieval-candidate-review.md)
- [CJK Lexical Dense RRF Fusion Implementation Review](./superpowers/reviews/2026-06-30-cjk-lexical-dense-rrf-fusion-review.md)
- [CJK Relevance Gate Reranker Implementation Review](./superpowers/reviews/2026-06-30-cjk-relevance-gate-reranker-review.md)
- [MKE Candidate Artifact Receipt Prerequisite Implementation Plan](./superpowers/plans/2026-07-13-candidate-artifact-receipt-implementation.md) — completed historical implementation record; the v0.1.3 exact-main and public-archive release gates were completed without publishing the candidate artifact.

## Development Verification

Use the verified bootstrap commands in the [Getting Started tutorial](./tutorials/getting-started.md)
before changing product behavior. Follow the [contributor workflow](./how-to/contribute.md) for
risk-based verification, pull requests, and safe task-owned cleanup.
