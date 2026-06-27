# Documentation

This repository uses Diataxis plus architecture decision records and approved implementation history.

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

Documentation changes ship in the same PR as affected behavior. Raw GStack artifacts and private planning notes do not belong in this repository.

## Current Product Proof And Plan

- [ADR-0001](./decisions/0001-local-first-pilot-architecture.md) defines the local-first Pilot architecture.
- [ADR-0002](./decisions/0002-source-publication-and-active-search-projection.md) defines Source Publication and active Search projection semantics.
- [ADR-0003](./decisions/0003-video-dependency-and-transcription-strategy.md) defines the short-video dependency and transcription strategy.
- [ADR-0004](./decisions/0004-pymupdf-pdf-intake-adapter.md) defines the PyMuPDF PDF intake adapter and licensing boundary.
- [ADR-0005](./decisions/0005-optional-local-command-transcription-provider.md) defines the optional local-command transcription provider boundary.
- [ADR-0006](./decisions/0006-first-party-local-transcription-runtime.md) defines the cache-only faster-whisper runtime.
- [ADR-0007](./decisions/0007-numeric-grouping-query-policy.md) promotes the bounded numeric grouping query policy and defines rollback.
- [Architecture](./explanation/architecture.md) explains the current domain flow and projection boundary.
- [Public Contracts](./reference/contracts.md) tracks implemented versus planned interfaces.
- [CLI Reference](./reference/cli.md) documents implemented commands, proof output, compatibility demo output, and error fields.
- [Run The Local Product Proof](./how-to/run-local-product-proof.md) explains the deterministic PDF and short-video proof plus the optional local transcript smoke command.
- [Run Retrieval Evaluation](./how-to/run-retrieval-evaluation.md) records the deterministic
  English page/timestamp FTS5 baseline and explains its integrity-versus-quality boundary.
- [Evaluate The Numeric Retrieval Candidate](./how-to/evaluate-numeric-retrieval.md) compares the
  promoted numeric grouping policy against frozen development, public holdout, and E1 inputs.
- [Run The Chinese Retrieval Evaluation](./how-to/run-chinese-retrieval-evaluation.md) records the
  E3-A FTS5 lexical baseline, graded metrics, miss symptoms, and the E3-B CJK lexical comparison.
- [Enable Bounded CJK Retrieval](./how-to/enable-cjk-retrieval.md) covers E3-F owner-startup
  selection, compiled-empty routing, doctor, no-op rebuild, proof, and rollback.
- [Use MKE As A Local MCP Server](./how-to/use-mke-mcp.md) explains the first Agent-facing stdio interface.
- [Use Local Transcription](./how-to/use-local-transcription.md) covers prepare, doctor, ingest, real ASR proof, and recovery.
- [Real Local Transcription Deployment Proof Design](./superpowers/specs/2026-06-18-real-local-transcription-deployment-proof-design.md) defines the redistribution-safe fixture, cache-only proof, and isolated wheel deployment evidence.
- [Real Local Transcription Deployment Proof Implementation Plan](./superpowers/plans/2026-06-18-real-local-transcription-deployment-proof-docs-implementation.md) records the current PR 3 execution history.
- [Real Local Transcription Deployment Proof Autoplan Review](./superpowers/reviews/2026-06-18-real-local-transcription-deployment-proof-autoplan-review.md) records the approved pre-implementation findings.
- [Trustworthy PDF And Video Slice Design](./superpowers/specs/2026-06-15-trustworthy-pdf-video-slice-design.md) records the approved design.
- [Trustworthy PDF And Video Slice Implementation Plan](./superpowers/plans/2026-06-15-trustworthy-pdf-video-slice-implementation.md) records the completed implementation plan.
- [MCP Agent Interface Design](./superpowers/specs/2026-06-16-mcp-agent-interface-design.md) defines the first Agent-facing stdio interface.
- [MCP Agent Interface Implementation Plan](./superpowers/plans/2026-06-16-mcp-agent-interface-implementation.md) records the completed C1 interface plan.
- [MCP Agent Interface Autoplan Review](./superpowers/reviews/2026-06-16-mcp-agent-interface-autoplan-review.md) records the approved review findings for this slice.
- [Evidence-Only Ask Design](./superpowers/specs/2026-06-16-evidence-only-ask-design.md) defines deterministic non-generative Ask.
- [Evidence-Only Ask Implementation Plan](./superpowers/plans/2026-06-16-evidence-only-ask-implementation.md) records the completed C2 Ask plan.
- [Evidence-Only Ask Autoplan Review](./superpowers/reviews/2026-06-16-evidence-only-ask-autoplan-review.md) records the approved pre-implementation review findings.
- [Real PDF Intake Design](./superpowers/specs/2026-06-16-real-pdf-intake-design.md) defines D1 PyMuPDF text-layer intake.
- [Real PDF Intake Implementation Plan](./superpowers/plans/2026-06-16-real-pdf-intake-implementation.md) records the completed D1 intake plan.
- [Real PDF Intake Autoplan Review](./superpowers/reviews/2026-06-16-real-pdf-intake-autoplan-review.md) and [Engineering Review](./superpowers/reviews/2026-06-16-real-pdf-intake-eng-review.md) record the approved D1 review findings.
- [Product Proof And Evaluation Harness Design](./superpowers/specs/2026-06-17-product-proof-evaluation-harness-design.md) defines the D2 deterministic product proof harness.
- [Product Proof And Evaluation Harness Implementation Plan](./superpowers/plans/2026-06-17-product-proof-evaluation-harness-implementation.md) records the completed D2 proof plan.
- [Real Video Intake Provider Port Design](./superpowers/specs/2026-06-17-real-video-intake-provider-port-design.md) defines the D3-A transcript provider boundary and local-command smoke scope.
- [Real Video Intake Provider Port Implementation Plan](./superpowers/plans/2026-06-17-real-video-intake-provider-port-implementation.md) records the D3-A execution plan.
- [Real Video Intake Provider Port Engineering Review](./superpowers/reviews/2026-06-17-real-video-intake-eng-review.md) records the approved D3-A review findings.
- [Retrieval Evaluation Baseline Design](./superpowers/specs/2026-06-20-retrieval-evaluation-baseline-design.md) defines the E1 corpus, qrels, metrics, and integrity gates.
- [Retrieval Evaluation Baseline Implementation Plan](./superpowers/plans/2026-06-20-retrieval-evaluation-baseline-implementation.md) records the E1 execution checklist and verification.
- [Retrieval Evaluation Baseline Plan Review](./superpowers/reviews/2026-06-20-retrieval-evaluation-baseline-plan-review.md) records the approved pre-implementation findings.
- [Retrieval Evaluation Baseline Implementation Review](./superpowers/reviews/2026-06-20-retrieval-evaluation-baseline-review.md) records the lightweight final scope and evidence check.
- [Numeric Retrieval Candidate Comparison Design](./superpowers/specs/2026-06-21-retrieval-candidate-comparison-design.md) defines the frozen E2 protocol and promotion boundary.
- [Numeric Retrieval Candidate Comparison Implementation Plan](./superpowers/plans/2026-06-21-retrieval-candidate-comparison-implementation.md) records the PR 1 execution checklist.
- [Numeric Retrieval Candidate Comparison Autoplan Review](./superpowers/reviews/2026-06-21-retrieval-candidate-comparison-autoplan-review.md) records the approved scope, engineering, and DX findings.
- [Chinese Hybrid Retrieval Evaluation Design](./superpowers/specs/2026-06-25-chinese-hybrid-retrieval-evaluation-design.md) defines E3-A through E3-F; E3-A, E3-B, and E3-F are implemented.
- [Chinese Retrieval Baseline Implementation Plan](./superpowers/plans/2026-06-25-chinese-retrieval-baseline-implementation.md) records the E3-A execution contract.
- [Chinese Retrieval Baseline Autoplan Review](./superpowers/reviews/2026-06-25-chinese-retrieval-baseline-autoplan-review.md) records the approved pre-implementation findings.
- [Chinese Retrieval Baseline Implementation Review](./superpowers/reviews/2026-06-25-chinese-retrieval-baseline-review.md) records the bounded implementation self-review and verification.
- [CJK Lexical Candidate Design](./superpowers/specs/2026-06-26-cjk-lexical-candidate-design.md) defines the merged off-default E3-B `cjk-trigram-overlap-v1` comparison.
- [CJK Lexical Candidate Implementation Plan](./superpowers/plans/2026-06-26-cjk-lexical-candidate-implementation.md) records the completed and merged E3-B execution checklist.
- [CJK Lexical Candidate Plan Review](./superpowers/reviews/2026-06-26-cjk-lexical-candidate-plan-review.md) records the E3-B planning review, rejected alternatives, and post-merge closeout.
- [CJK Lexical Runtime Promotion Design](./superpowers/specs/2026-06-26-cjk-lexical-runtime-promotion-design.md) records the E3-F path and Task 0.5 amendment to no-projection active scan.
- [CJK Lexical Runtime Promotion Implementation Plan](./superpowers/plans/2026-06-26-cjk-lexical-runtime-promotion-implementation.md) records the active-scan runtime, CLI/MCP, proof, and rollback work.
- [CJK Lexical Runtime Promotion Autoplan Review](./superpowers/reviews/2026-06-26-cjk-lexical-runtime-promotion-autoplan-review.md) records the pre-implementation CEO, engineering, and DX review findings.
- [Local Dense Retrieval Candidate Design](./superpowers/specs/2026-06-28-local-dense-retrieval-candidate-design.md) defines the approved comparison-only E3-C Qwen3 embedding and exact-KNN protocol.
- [Local Dense Retrieval Candidate Implementation Plan](./superpowers/plans/2026-06-28-local-dense-retrieval-candidate-implementation.md) splits E3-C into a pre-qrel compatibility PR and a separately reviewed dense comparison PR.

## Development Verification

Use the verified bootstrap commands in the [Getting Started tutorial](./tutorials/getting-started.md) before changing product behavior.
