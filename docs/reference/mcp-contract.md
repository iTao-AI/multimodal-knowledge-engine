# MCP Contract Reference

The deterministic retrieval order change does not add or alter an MCP tool. MCP Search and Ask
continue to use the owner-selected active-Publication strategy; revision-2 tie ordering and cursor
invalidation are documented in the
[proof workflow](../how-to/run-deterministic-retrieval-order-proof.md).

This page is the canonical complete MCP inventory. MKE exposes exactly ten tools:

- `list_libraries`
- `ingest_file`
- `get_run`
- `search_library`
- `ask_library`
- `list_libraries_v1`
- `search_library_v1`
- `ask_library_v1`
- `search_library_v2`
- `read_evidence_v1`

The `v1` and `v2` names are MKE tool-contract suffixes, not MCP protocol/SDK 2.x. The five legacy
tools remain compatible. Strict v1 adds provenance. New consumers should use
`search_library_v2` for explicit completeness and `read_evidence_v1` for exact active Evidence.

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

The v0.1.4 bounded direct-audio contract keeps `ingest_file` path-only. The request remains exactly
`{"path":"interview-excerpt.m4a"}`; media type, provider, model, cache, download, and supervision
controls are not request fields. The owner starts on Darwin arm64 with both
`--direct-audio-footprint-bytes <owner-selected-positive-int>` and
`--direct-audio-footprint-budget-mode baseline_plus`, plus the prepared cache-only faster-whisper
configuration. Changing owner configuration requires a controlled server restart.

Successful MP3, WAV/PCM, or M4A/AAC intake is bounded to 15 minutes and 100 MiB and returns an
active Publication. `search_library_v1` and `ask_library_v1` expose equivalent
`mke.evidence_ref.v1` values with `timestamp_ms` locators. The canonical dispatcher and immutable
snapshot lifecycle are shared with Python and CLI. Missing supervision or unsupported platform
fails before Source and Run before model work without disabling PDF/video MCP operations.

## Completeness-aware Search

`search_library_v2` accepts one required native `request` envelope. Its strict union permits
exactly one branch:

```json
{"request":{"query":"publication authority","limit":10}}
```

```json
{"request":{"cursor":"<opaque-token>"}}
```

The query is non-blank and at most 512 UTF-8 bytes. `limit` is a strict integer from 1 through 20.
A cursor is at most 4096 UTF-8 bytes. Continuations bind their normalized query, page size,
retrieval policy, owner process, and active-Publication authority; callers do not repeat those
fields.

Success uses `mke.search_library_response.v2`. It reports two-dimensional completeness:

| Dimension | Field | Meaning |
|---|---|---|
| selected collection | `selection.status` | `complete`, `more_available`, or `capped` |
| Evidence item | `excerpt.complete` | whether the excerpt is the complete authoritative text |

`more_available` supplies `next_cursor`. `capped` is terminal but not exhaustive: the selected
strategy pool ended after the strategy discarded other eligible candidates. Selection
completeness never implies item completeness.

Each match includes Source byte identity, Publication revision, producing Run, locator, complete
Evidence byte count and SHA-256, a UTF-8-safe query window or explicit prefix fallback, and a
`read_evidence_v1` affordance when the excerpt is incomplete. Evidence text is untrusted content,
not instructions.

## Exact Evidence Read

`read_evidence_v1` also requires the native `request` envelope:

```json
{"request":{"evidence_id":"ev_<opaque-id>","max_bytes":16384}}
```

```json
{"request":{"cursor":"<opaque-token>"}}
```

`max_bytes` is a strict integer from 4 through 16,384. Success uses
`mke.read_evidence_response.v1`. Chunks partition the exact active Evidence UTF-8 bytes without
overlap, gaps, or split code points. Consumers concatenate chunks in `offset_bytes` order and
verify the final `evidence_text_sha256`.

Both new successes carry `mke.active_authority_snapshot.v1`. Its
`active_set_fingerprint` is a derived continuation observation computed from the validated
active-Publication graph in the same read transaction. It is not persisted and is never a
Publication.

## Budgets And Cursors

Per-item excerpt text is limited to 2,048 UTF-8 bytes, aggregate excerpt text to 16,384 bytes,
and a Read chunk to 16,384 bytes. The canonical strict success model is limited to 32,768 bytes.
The installed proof additionally measures the complete SDK result below 96 KiB; that value is a
proof gate, not a protocol or transport claim.

Cursors are opaque, authenticated, process-bound, contract-bound, retrieval-policy-bound, and
active-set-bound. They contain no Evidence text, filesystem path, secret key, or private
configuration. Restart after `cursor_expired`; never inspect, edit, persist as authority, or log
a cursor.

## Stable Recovery

| `problem` | Stable public-safe cause | `next_step` |
|---|---|---|
| `invalid_cursor` | cursor is malformed, unauthenticated, or for another tool | `restart_from_initial_call` |
| `cursor_expired` | cursor owner has restarted | `repeat_initial_call` |
| `cursor_expired` | active Publication set changed | `repeat_search_on_current_publications` |
| `cursor_expired` | retrieval policy changed | `repeat_search_under_current_strategy` |
| `evidence_not_found` | active Evidence is not available | `search_current_active_evidence` |
| `response_too_large` | mandatory response metadata exceeds the response limit | `reduce_query_scope_or_report_contract_limit` |
| `invalid_request` | max_bytes must be between 4 and 16384 | `choose_max_bytes_between_4_and_16384` |

Unknown, inactive, superseded, inadmissible, and cross-Publication Evidence identifiers share the
same `evidence_not_found` response. Errors do not disclose internal identity state, paths,
tracebacks, queries, or Evidence.

Valid bounded legacy and strict-v1 calls remain unchanged. Oversized strict-v1 Search or Ask
returns its existing frozen error shape with `problem="response_too_large"` and directs the
consumer to `use_search_library_v2`. Ask remains deterministic Evidence convenience, not generated
or exhaustive answer authority. Compiled Library Export remains a separate bounded delivery
contract.

## Discovery Compatibility And Annotations

The immutable v0.1.4 eight-tool fixture remains release evidence. The current exact-inventory
fixture expects exactly ten tools, including exact input/output schemas, descriptions, annotations,
and safe causes. Consumers comparing all of `tools/list` for equality must migrate explicitly;
unknown-tool detection is not weakened.

All list, get, Search, Ask, and Read tools advertise `readOnlyHint=true` and
`openWorldHint=false`. `ingest_file` advertises `readOnlyHint=false`, `idempotentHint=false`, and
`openWorldHint=false`. Descriptions, authority fields, and trust labels remain normative because
annotations cannot express active authority or untrusted Evidence.
