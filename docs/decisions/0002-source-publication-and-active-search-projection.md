# ADR-0002: Source Publication And Active Search Projection

- Status: Accepted
- Date: 2026-06-15

## Context

The first executable slice must prove that Multimodal Knowledge Engine is a trustworthy
Evidence engine, not only a document ingestion demo. A failed or partial Run must not become
searchable, and inactive candidate output must not affect Search ranking or result truncation.

ADR-0001 already establishes SQLite as Pilot domain truth, retrieval indexes as rebuildable
projections, and active-Publication-only Search. This ADR defines the concrete Source-level
Publication protocol for the first PDF slice.

## Decision

- Publication is atomic per `Source`.
- `Source` stores `active_publication_id`, `active_revision`, and `requested_generation`.
- Each `Run` captures immutable `source_generation` and `based_on_active_revision` at creation.
- Creating a Run increments `Source.requested_generation` in the same transaction.
- Publication activation uses a latest-request-wins rule:
  - `run.source_generation = source.requested_generation`
  - `run.based_on_active_revision = source.active_revision`
- A Run that fails this activation check becomes `superseded` and cannot publish.
- Run states are `queued`, `running`, `validated`, `published`, `failed`, `superseded`, and
  `interrupted`. The active implementation design owns the state transition diagram.
- `validated` means candidate output is complete but not searchable. Only `published` output is
  searchable.
- Candidate `Evidence` and the `RunManifest` are persisted in ordinary relational tables.
- The first retrieval projection is SQLite FTS5, but it stores only active Publication rows.
- The activation transaction creates the `Publication`, replaces that Source's active FTS5 rows,
  switches `Source.active_publication_id`, increments `Source.active_revision`, marks the Run
  `published`, and appends the publication event.
- Search reads active FTS5 rows and still joins back through active Publication identity.

## Consequences

- Candidate, failed, superseded, or historical output cannot affect Search results or ranking.
- Reprocessing a Source cannot let an older Run overwrite a newer request.
- Library Search may aggregate different active generations across Sources. Cross-Source snapshot
  consistency is outside the Pilot.
- The first implementation has a stricter Publication protocol, but avoids a later redesign when
  video and agent-facing interfaces are added.
- FTS5 is a Pilot projection, not a long-term ranking contract.
- The activation transaction must be a single SQLite transaction. If it fails, the Run stays
  `validated` and can be retried. No partial Publication state is observable.
