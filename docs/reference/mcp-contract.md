# MCP Contract Reference

The deterministic retrieval order change does not add or alter an MCP tool. MCP Search and Ask
continue to use the owner-selected active-Publication strategy; revision-2 tie ordering and cursor
invalidation are documented in the
[proof workflow](../how-to/run-deterministic-retrieval-order-proof.md).

The opt-in `mixed-cjk-fts-intent-v1` strategy changes selection for compiled-nonempty mixed
queries without changing tool inputs or response schemas. It requires the complete active FTS
match and sufficient CJK overlap. `search_library_v2` uses the same order as Search and Ask;
its cursor binds strategy ID/revision, and cross-strategy continuation fails closed. A selected
page may report `more_available`, while eligible candidates discarded by the 10-result strategy
cap report `capped`. Budget overflow returns a typed error rather than a partial page.

This page is the canonical complete MCP inventory. MKE exposes exactly fifteen tools:

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
- `list_sources_v1`
- `browse_source_evidence_v1`
- `list_sources_v2`
- `browse_source_evidence_v2`
- `search_source_evidence_v1`

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
| `cjk_scan_budget_exceeded` | CJK active Evidence scan would exceed configured local budget | `narrow_query_or_use_projection_strategy` |
| `invalid_request` | max_bytes must be between 4 and 16384 | `choose_max_bytes_between_4_and_16384` |

Agent-facing active-authority recovery is explicit:

| Check | `problem` | Stable public-safe cause | `next_step` | Active Publication impact |
|---|---|---|---|---|
| `stable_locator_identity` | `retrieval_authority_invalid` | active retrieval candidates contain duplicate stable Evidence locators | `restore_valid_database_or_reingest_into_new_database` | `unchanged` |

`cjk_scan_budget_exceeded` is a bounded active-scan budget failure, not an exhaustive no-match. The
Agent should narrow the query or use the already supported projection strategy, and must not retry the unchanged query.

Unknown, inactive, superseded, inadmissible, and cross-Publication Evidence identifiers share the
same `evidence_not_found` response. Errors do not disclose internal identity state, paths,
tracebacks, queries, or Evidence.

Opaque Evidence IDs are addressing identity, not ranking authority and not a cross-strategy
display-order promise.

Valid bounded legacy and strict-v1 calls remain unchanged. Oversized strict-v1 Search or Ask
returns its existing frozen error shape with `problem="response_too_large"` and directs the
consumer to `use_search_library_v2`. Ask remains deterministic Evidence convenience, not generated
or exhaustive answer authority. Compiled Library Export remains a separate bounded delivery
contract.

## Discovery Compatibility And Annotations

The immutable v0.1.4 eight-tool, v0.1.7 ten-tool and Source-discovery twelve-tool fixtures remain
historical evidence. The fourteen-tool PDF snapshot also remains immutable. The current `tests/fixtures/source-search-v1/mcp-tool-schemas.json`
exact-inventory fixture expects exactly fifteen tools, including exact input/output schemas, descriptions, annotations,
and safe causes. Consumers comparing all of `tools/list` for equality must migrate explicitly;
unknown-tool detection is not weakened.

All list, get, Search, Ask, and Read tools advertise `readOnlyHint=true` and
`openWorldHint=false`. `ingest_file` advertises `readOnlyHint=false`, `idempotentHint=false`, and
`openWorldHint=false`. Descriptions, authority fields, and trust labels remain normative because
annotations cannot express active authority or untrusted Evidence.

## Search Within One Selected Source

`search_source_evidence_v1` is an additive read-only tool. Its initial native envelope is
`{"request":{"source_id":"<Source>","publication_id":"<Publication>","query":"terms","limit":5}}`;
IDs are explicit selections from current Source discovery. Limit is strictly integer 1–20,
default5; query is nonblank and <=512 UTF-8 bytes. Continuation accepts exactly
`{"request":{"cursor":"<opaque>"}}`. Mixed branches and unknown fields fail validation.

Success schema is `mke.search_source_evidence_response.v1`. It contains `scope` with schema
`mke.source_search_scope.v1`, Source/Publication/revision/Run/content fingerprint, plus the
existing authority snapshot, query, descriptor/excerpt/read matches, selection and output.
Every citation agrees with the complete selected scope. Empty matches remain a scoped complete
success. Unknown/mismatched/unpublished/superseded selection returns `evidence_not_found` with
`next_step=reselect_active_source`; it never falls back to Library Search.

Source/Publication predicates apply before candidate limits and scan budgets for all four
runtime strategies. Scoped CJK/mixed selection paginates all eligible matches within the
existing1000-candidate and10000-row/16MiB budgets, with explicit budget failure and only
`complete|more_available`. The old Library top10 caps, schemas, defaults and Evidence identities
are unchanged. Native FTS corpus rank statistics remain unchanged.

The separate authenticated cursor binds tool/schema, owner, configured Library, active-set
authority, full scope, query/digest, retrieval policy, page size and actual position. Full scope
is validated inside the same read transaction before candidates are loaded. Cross-tool/Library
reuse or tampering fails `invalid_cursor`; owner/policy/active-set changes fail `cursor_expired`
with the existing explicit recovery actions. The Library-wide authority conservatively expires
the cursor even when another Source's Publication changes. A changed selected Publication
requires rediscovery and explicit reselection.

The full canonical response, including scope/cursor, is <=32,768 bytes; excerpts keep the
existing2048/16384-byte per-item/combined limits. Pages advance by actual returned count and
must make positive progress. Use unchanged `read_evidence_v1` and verify its descriptor/digest.
See [single-Source workflow](../how-to/search-within-one-source.md) and
[ADR-0016](../decisions/0016-single-source-active-publication-search.md). Ask remains unchanged;
the approved follow-up design requires rejection of out-of-scope/stale citations in a separate
implementation slice. This contract adds no permission system or historical/multi-Source access.

## Source Discovery And Browsing

The current source checkout adds read-only `list_sources_v1` and `browse_source_evidence_v1`;
this does not amend the stable v0.1.7 release record or claim a new installed-wheel proof.
Native envelopes are `{"request":{...}}`. Catalog initial fields are only `page_size`; browse
initial fields are `source_id`, `publication_id`, optional `locator_range` and `page_size`. Both
default to 10 and accept strictly integer 1–20. Continuations are cursor-only
`{"request":{"cursor":"<opaque>"}}`; mixing branches or unknown fields fails validation.

Ranges are `{kind: page, start, end}` with positive inclusive bounds, or
`{kind: timestamp_ms, start, end}` with nonnegative start and greater exclusive end; timestamps
select overlap. Wrong Source locator kinds and Boolean boundaries fail. Catalog orders by content
fingerprint/Source ID. Browsing orders by locator start, end, Evidence ID.

The strict schemas are `mke.list_sources_response.v1` and
`mke.browse_source_evidence_response.v1`. Both include `authority_snapshot` and `selection`; catalog
returns `sources`, while browse returns selected `source`, `entries` and `output`. Source metadata
includes ID, leaf display name, media type, content fingerprint, active Publication ID/revision,
producing Run, extractor fingerprint, required stages, active Evidence count and coverage. An entry
contains unchanged `EvidenceDescriptorV1` under `evidence`, a prefix `excerpt` and exact-read
`read` affordance. `complete` terminates the selected pool; `more_available` requires positive
`returned` and `next_cursor`, including on envelope/content-limited pages. There is no ranking cap
in catalog/browse and no promise of original-media completeness.

Preview content is untrusted and capped at 2,048 UTF-8 bytes per entry / 16,384 per response; the
canonical envelope cap is 32,768 bytes. Mandatory overflow is `response_too_large`. Reuse
`read_evidence_v1` to reconstruct complete stored text and independently verify UTF-8 bytes, digest
and full Source/Publication/revision/Run/fingerprint/locator citation lineage.

Coverage is the selected Publication's persisted producing-Run report, not a capability score.
PDF scalar counts retain their meanings. Catalog `page_char_counts` is empty with an explicit
`page_char_counts_total` / `page_char_counts_omitted`; selected Source arrays contain at most 256
entries and disclose omission. Missing PDF/transcript reports are `not_observed`, with null values
rather than inferred counts/provenance. Transcript `evidence_kind="stored_transcript"` does not
claim ASR quality or scene understanding. Suspected scans do not prove missing semantic content.

## Opt-In PDF Extraction Observation

`list_sources_v2` and `browse_source_evidence_v2` reuse the exact v1 request envelopes, selection,
Evidence descriptors, preview budgets and recovery. Their strict response schemas are
`mke.list_sources_response.v2` and `mke.browse_source_evidence_response.v2`. V2 Source metadata adds
the required `pdf_extraction_observation` field: a closed `mke.pdf_extraction_observation.v1`
object for PDFs and null for other media. V1 fields, descriptions and schemas remain unchanged.
Cursors bind the versioned operation; cross-version reuse fails `invalid_cursor`.

Observed objects have `status="observed"`, `method="pymupdf-displayed-raster-v1"`,
`extraction_scope="text_layer_only"`, positive `total_pages`, and nonnegative `text_only_pages`,
`mixed_text_raster_pages`, `raster_only_pages`, `neither_text_nor_raster_pages` summing to the total.
`pages` contains closed `{page_number,text_layer_chars,has_raster_images}` objects; the first two
are strict integers and the last is a strict Boolean. `returned_page_range` is null or
`{start,end}` with inclusive bounds. `omitted_page_ranges` is the exact complement of returned
page observations. These ranges describe observation materialization, independently of Evidence
pagination and preview completeness.

Catalog returns no page details and omits pages 1–total. Browse returns at most 256 contiguous
page observations, starting at page 1 or the requested inclusive page-range start, clamped to the
document/range. An entirely out-of-document range returns no observations and omits all pages.
SQLite aggregates full counts and bounds rows before Python decoding. The report is read from the
selected active Publication's producing Run in the same transaction as Source/Evidence identity.

A missing new observation is `status="not_observed"`: method, scope, total and category counts
are null; `pages=[]`, `returned_page_range=null`, `omitted_page_ranges=[]`. It does not imply zero
images or full semantic coverage. Decorative raster images count as present; vector graphics,
image meaning, charts, tables, OCR quality and visual completeness are not assessed. The old
`suspected_scanned_pages <= empty_pages` invariant keeps its original meaning and behavior.

See [ADR-0015](../decisions/0015-pdf-extraction-observations.md) and the
[native consumer proof](../how-to/observe-pdf-extraction-scope.md).

Reads validate the Library/Source/Publication graph and load metadata/coverage/Evidence in one
SQLite snapshot. Cursors bind operation, runtime owner, keyed configured-library identity, active
set, page size, position and response schema; browse also binds Source/Publication/filter/order.
Tampering or cross-tool reuse returns `invalid_cursor`; owner restart or active-set change returns
`cursor_expired`. Restart initial discovery against current authority. Host paths, original files
and inactive candidates are not returned. CLI uses these same adapters under one owner.

See [the standalone mixed-PDF/transcript walkthrough](../how-to/discover-and-read-sources.md) and
[ADR-0014](../decisions/0014-source-discovery-and-browsing.md).
