# Trustworthy PDF And Video Slice Design

Supersedes: `docs/superpowers/specs/2026-06-13-pilot-design.md` for active implementation order.

## Goal

Build an executable local-first Evidence path that ingests a real text-layer PDF, returns stable
page Evidence through Search, and proves failed or partial reprocessing never changes searchable
visibility. Immediately after that proof, add a short-video path that returns stable timestamp
Evidence through the same lifecycle.

## Current State

- The repository is in the bootstrap stage.
- No product-domain behavior, persistence, ingestion, retrieval, HTTP, MCP, or workspace behavior
  exists yet.
- ADR-0001 defines the local-first Pilot architecture.
- ADR-0002 defines Source-level Publication and active Search projection semantics.

## Product Proof

The first proof is not complete when the domain model exists. It is complete when a reviewer can
run one deterministic local command and see:

1. A repository fixture PDF is ingested.
2. Search returns page-addressed Evidence from the active Publication.
3. A forced failed reprocess leaves the previous active Publication searchable.
4. A successful retry atomically replaces the active Publication.
5. Candidate or failed output never appears in Search and never affects ranking.

The PR 3 golden path is:

```bash
uv sync --locked
uv run mke demo --verify
```

## Required Semantics

- A `Source` has an active Publication pointer, an active revision, and a requested generation.
- A `Run` captures the Source generation and active revision at creation time.
- Publication activation uses latest-request-wins generation checks plus active revision compare
  and swap.
- Candidate Evidence and Run manifests are persisted but not searchable.
- FTS5 contains only rows for active Publications.
- `validated` means candidate output is complete. `published` means user-visible Search has
  changed.
- `failed`, `superseded`, and `interrupted` Runs are terminal and cannot publish.

## Run State Machine

ADR-0002 defines the authoritative Run states. Valid transitions are:

```text
queued -> running -> validated -> published
                  \-> failed
                  \-> interrupted
        \-> superseded

validated -> superseded
```

- `queued` means a Run is recorded but processing has not started.
- `running` means extraction, candidate Evidence persistence, or manifest construction is in
  progress.
- `validated` means candidate Evidence and the Run manifest passed validation but are not
  searchable.
- `published` means the active Publication pointer and active Search projection changed in one
  transaction.
- `failed` means processing or validation failed before publication.
- `superseded` means a newer request won the generation or active revision check.
- `interrupted` means the process stopped before reaching a safe terminal state and the Run cannot
  publish.

## Milestones

### PR 2: PDF Happy Path With Minimal Publication Correctness

- Add the minimal lifecycle model: `Library`, `Source`, `Asset`, `Run`, `Evidence`,
  `RunManifest`, and `Publication`.
- Add SQLite migrations and SQLAlchemy Core adapters.
- Add text-layer PDF extraction behind project-owned ports.
- Add active-only FTS5 projection.
- Implement Run generation, active revision compare-and-swap, `validated` and `published` states,
  and stale Run rejection.
- Implement a narrow CLI path for PDF ingest and Search.
- Add a public-safe fixture PDF with stable expected Evidence.

### PR 3: Reliability Proof And Golden Demo

- Add reprocessing, retry lineage, failure injection, interrupted Run handling, and Run event
  observability.
- Prove failures before validation, during candidate persistence, during active projection
  replacement, and during activation do not change Search visibility.
- Failure points that must not affect Search include before validation, during candidate Evidence
  writes, during FTS5 replacement, after Publication insert, after active pointer switch, and
  during activation conflict.
- Implement `mke demo --verify` as a deterministic offline product proof.
- Update README, getting-started tutorial, CLI reference, error catalog, and CI to use the demo as
  the primary reviewer path.

### PR 4: Short Video With Timestamp Evidence

- Add one documented local video path.
- Decide and document `ffmpeg`, transcription, fixture, model/cache, offline, and CI behavior
  before implementation.
- Persist timestamp-addressed Evidence using integer millisecond locators.
- Use the same Publication lifecycle and active projection protocol as PDF.
- Extend `mke demo --verify` to prove one PDF and one short video can both be searched.

## Explicit Non-Goals

- Scanned-PDF OCR, complex layouts, tables, image understanding, or page coordinates.
- General FTS query language or a stable long-term ranking contract.
- Cross-Source snapshot consistency.
- Multiple owner processes, multiple workers, Redis, or hosted coordination.
- Automatic checkpoint resume or automatic retry.
- HTTP, MCP, Ask, workspace UI, or public stabilization of `Artifact`, `Segment`, and `Passage`
  before the PDF and video lifecycle is proven.
- External services, credentials, model downloads, or network calls for the PDF demo.

## Acceptance

The trustworthy PDF milestone is accepted only when PR 2 and PR 3 are both merged and CI proves
the wheel-installed CLI can run `mke demo --verify`.

The cross-modal milestone is accepted only when the same demo proves both page Evidence for a PDF
and timestamp Evidence for a short video.
