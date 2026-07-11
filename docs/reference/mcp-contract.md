# MCP Contract Reference

MKE keeps the five legacy tools unchanged: `list_libraries`, `ingest_file`, `get_run`,
`search_library`, and `ask_library`. Consumers that need strict provenance opt into the additive
read-only tools `list_libraries_v1`, `search_library_v1`, and `ask_library_v1`.

The response schema versions are `mke.list_libraries_response.v1`,
`mke.search_library_response.v1`, and `mke.ask_library_response.v1`. Every response is a strict
success/error union discriminated by `ok`; unknown, missing, or extra fields fail validation.

Search results and Ask citations share `mke.evidence_ref.v1`:

```json
{
  "schema_version": "mke.evidence_ref.v1",
  "evidence_id": "ev_<opaque-id>",
  "source_id": "src_<opaque-id>",
  "content_fingerprint": "sha256:<source-byte-digest>",
  "publication_id": "pub_<opaque-id>",
  "publication_revision": 1,
  "run_id": "run_<opaque-id>",
  "locator": {"kind": "page", "start": 1, "end": 1},
  "text": "selected Evidence text"
}
```

`content_fingerprint` identifies the original source bytes. Opaque IDs are not promised stable
across independent stores. Locators are either one positive page or a non-empty
`timestamp_ms` interval.

Every success includes `mke.active_publication_observation.v1`. Its state is `empty`,
`no_active_publication`, or `active`. Only `active` with an empty result list means a normal
no-match. MKE validates Source, Publication, Run, RunManifest, Asset, and Evidence ownership,
revision, count, published state, and fingerprint equality before returning trusted provenance.

The v1 Search/Ask snapshot calls unchanged retrieval first, then perform one bulk enrichment in
the same SQLite PEP 249 transaction. They do not change `SearchResult`, ranking, CLI, evaluation,
or legacy MCP behavior and do not issue a nested `BEGIN` or per-result provenance query.

