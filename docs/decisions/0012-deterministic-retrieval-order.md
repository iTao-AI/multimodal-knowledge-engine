# ADR-0012: Deterministic retrieval order

Status: Accepted

## Context

Search already reads active Publications and returns stable Evidence locators, but legacy
tie-breaking used generated opaque identifiers. Those identifiers are store-local and cannot be
portable semantic order authority. Cursor continuations also need to fail closed when the
retrieval policy revision changes.

## Decision

The active lexical strategies order equal-score results by a stable semantic SQL key derived from
Source byte identity, Publication revision, locator, and Evidence text identity. Opaque database
identifiers remain identity fields, not ordering authority. The retrieval strategy revision is
`revision 2`; a cursor issued for another revision fails with a cursor revision mismatch instead
of silently continuing under changed order.

Search and Ask still read active Publications only. This decision does not change Evidence,
Run, Publication, ingestion, ranking score, or active-only authority. It only makes the final
deterministic order portable across equivalent stores.

Historical evaluation bytes remain immutable. Compatibility is established in layers:
historical bytes are frozen, archived records are self-consistent, the current runtime is replayed
separately, and the revision-2 differential permits only tie reordering. A tie-only compatibility
record is comparison evidence, not promotion evidence.

Development freeze, holdout receipt, retrieval artifact, compatibility attempt, and compatibility
artifact publication use atomic no-replace writes. Canonical holdout and compatibility are
one-shot transitions. A visible durability-uncertain record is terminal and never authorizes a
retry.

## Consequences

- Equivalent active stores can return the same order without sharing generated identifiers.
- Pre-revision-2 cursors are invalidated deliberately.
- Validation paths are pure and read-only; observation and record commands own replay.
- Temporary compatibility output never becomes canonical authority.
- Rollback selects an existing strategy; it does not reinterpret a revision-2 cursor.

## Non-goals

This decision does not add GraphRAG, dense retrieval, RRF, a reranker, OCR, an Agent loop,
HTTP/SaaS, a new provider, a new dependency, runtime promotion, quality improvement claims, or
changes to active Publication authority.
