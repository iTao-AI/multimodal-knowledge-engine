# ADR-0012: Deterministic retrieval order

Status: Accepted

## Context

Search already reads active Publications and returns stable Evidence locators, but legacy
tie-breaking used generated opaque identifiers. Those identifiers are store-local and cannot be
portable semantic order authority. Cursor continuations also need to fail closed when the
retrieval policy revision changes.

## Decision

FTS orders in SQL by
`score, locator_start, locator_kind, locator_end, source_sha256`.
CJK active scan orders in Python by
`-overlap_count, -overlap_ratio, content_fingerprint, locator_kind, locator_start, locator_end`.
The CJK key is not SQL-derived. `source_sha256` binds immutable Source bytes on the FTS path;
`content_fingerprint` binds immutable Source bytes on the CJK active-scan path.

Opaque database identifiers remain identity fields, not ordering authority.
Publication revision and Evidence text identity are not current tie-break fields.
The owner-selected FTS and CJK strategies have strategy-specific tie semantics.
This ADR does not promise one cross-strategy display order. The retrieval strategy revision is
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
