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

Documentation changes ship in the same PR as affected behavior. Raw GStack artifacts and private planning notes do not belong in this repository.

## Active Product Plan

- [ADR-0001](./decisions/0001-local-first-pilot-architecture.md) defines the local-first Pilot architecture.
- [ADR-0002](./decisions/0002-source-publication-and-active-search-projection.md) defines Source Publication and active Search projection semantics.
- [ADR-0003](./decisions/0003-video-dependency-and-transcription-strategy.md) defines the short-video dependency and transcription strategy.
- [Architecture](./explanation/architecture.md) explains the current domain flow and projection boundary.
- [Public Contracts](./reference/contracts.md) tracks implemented versus planned interfaces.
- [CLI Reference](./reference/cli.md) documents implemented commands, demo output, and error fields.
- [Trustworthy PDF And Video Slice Design](./superpowers/specs/2026-06-15-trustworthy-pdf-video-slice-design.md) is the active implementation design.
- [Trustworthy PDF And Video Slice Implementation Plan](./superpowers/plans/2026-06-15-trustworthy-pdf-video-slice-implementation.md) is the active executable plan.

## Development Verification

Use the verified bootstrap commands in the [Getting Started tutorial](./tutorials/getting-started.md) before changing product behavior.
