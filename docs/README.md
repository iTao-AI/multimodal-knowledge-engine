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
- [Architecture](./explanation/architecture.md) explains the current domain flow and projection boundary.
- [Public Contracts](./reference/contracts.md) tracks implemented versus planned interfaces.
- [CLI Reference](./reference/cli.md) documents implemented commands, proof output, compatibility demo output, and error fields.
- [Run The Local Product Proof](./how-to/run-local-product-proof.md) explains the deterministic PDF and short-video proof.
- [Use MKE As A Local MCP Server](./how-to/use-mke-mcp.md) explains the first Agent-facing stdio interface.
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

## Development Verification

Use the verified bootstrap commands in the [Getting Started tutorial](./tutorials/getting-started.md) before changing product behavior.
