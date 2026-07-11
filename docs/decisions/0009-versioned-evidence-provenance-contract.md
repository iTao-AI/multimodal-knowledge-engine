# ADR-0009: Versioned Evidence Provenance Contract

Status: Accepted

## Decision

Add parallel `list_libraries_v1`, `search_library_v1`, and `ask_library_v1` tools while preserving
all five legacy tool contracts. Search and Ask use the same strict `mke.evidence_ref.v1` projection
and `mke.active_publication_observation.v1` state.

The application asks existing retrieval for unchanged `SearchResult` values and bulk-enriches them
inside the same SQLite transaction. The complete active Source/Publication/Run/RunManifest/Asset/
Evidence graph must validate or the response fails closed.

## Consequences

- Existing consumers do not break; new consumers explicitly opt into versioned responses.
- `content_fingerprint` identifies source bytes across stores, while opaque IDs remain store-local.
- Observation and results cannot mix different active Publication snapshots.
- No migration, second persistence model, N+1 query, retrieval/ranking change, or nested `BEGIN` is
  introduced.
- Versioning legacy write and Run-inspection responses remains a separate decision.

