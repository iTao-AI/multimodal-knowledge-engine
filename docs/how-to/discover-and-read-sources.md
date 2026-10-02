# Discover A Source And Read Its Active Evidence

The current source checkout adds `list_sources_v1` and `browse_source_evidence_v1` to the local
stdio MCP server. These tools browse stored active Evidence. This is an additive checkout feature,
not a new release or a new installed-wheel/dual-Python proof. Search ranking, exact read, ingestion
and Publication activation retain their existing contracts.

## Run The Independent Synthetic Example

Use an existing environment containing the project, PyMuPDF and official MCP SDK. No install,
model preparation or download is performed by this script. Run from the repository root:

```bash
.venv/bin/python -I -B scripts/source_discovery_consumer.py \
  --mke-bin /ABSOLUTE/PATH/TO/EXISTING/mke \
  --work-dir /ABSOLUTE/PATH/TO/NEW/source-discovery-example \
  --expectation tests/fixtures/source-discovery-v1/mcp-tool-schemas.json
```

`--work-dir` must not exist; the script preserves its generated public synthetic inputs and SQLite
Library for inspection. Choose a fresh directory for another run. The consumer imports neither
MKE implementation nor test helpers. It ingests inputs through the real console entrypoint and
uses official `ClientSession` / `stdio_client` to initialize, list tools and call the native server.
It checks the complete current twelve-tool schema/description/annotation fixture.

The PDF has four declared synthetic pages: a lexical marker on page 1; sixty lines of Latin text
with multibyte accents on page 2; an image-only checkerboard on page 3; and text on page 4. The
`.mp4` identity fixture contains declared synthetic bytes plus a `mke.video_transcript.v1` sidecar
with three intervals. Its media metadata is declared fixture metadata, not measured encoded-media
or ASR evidence. This example uses no OCR, model, ASR or visual scene analysis.

The standalone consumer performs:

1. Catalog pagination with page size 1, selecting the PDF and transcript by public leaf labels and
   explicit Source/Publication IDs.
2. A declared lexical query that admits only PDF page 1; Source browsing over inclusive pages 2–4
   returns stored Evidence for pages 2 and 4, demonstrating navigation without a matching keyword.
3. Exact reading of page 2, whose prefix preview is incomplete, through multiple `read_evidence_v1` chunks. It independently checks every
   chunk's descriptor against the selected citation, byte offsets/counts, terminality, reconstructed
   UTF-8 byte count and SHA-256. It also checks the known synthetic text rather than a preview.
4. Transcript overlap browsing over `[500,1500)` returning `[0,1000)` and `[1000,2000)`, followed by
   exact reads and the same complete citation checks.
5. Equality between compatibility text and `structuredContent`, canonical payload ≤32,768 bytes,
   and full SDK result <96 KiB for every native tool-call result.

Stdout is one public-safe `mke.source_discovery_consumer.v1` JSON receipt, with scalar observations,
coverage and synthetic citation descriptors. It contains no host paths, cursors or raw Evidence
text. `status="passed"` means this bounded synthetic workflow passed; it does not imply retrieval
quality, provider quality, production adoption or original-media semantic coverage. Failure emits
only a bounded code and exits nonzero. The receipt records actual maximum byte counts; values can
vary with cursor envelopes and identifiers.

## Interpret Coverage Honestly

The producing PDF Run reports `extraction_mode="pymupdf-text"`, `total_pages=4`, `extracted_pages=3`,
`empty_pages=1` and `suspected_scanned_pages=1`. The observed zero text count on page 3 means no
text-layer Evidence was stored for it. A suspected scan is an observation about text/images; it is
not proof of missing semantic content or an OCR result.

Catalog coverage is a summary: `page_char_counts=[]`, `page_char_counts_total=4`,
`page_char_counts_omitted=true`. Selected Source coverage returns the four persisted character
counts, including page 3's zero, and `page_char_counts_omitted=false`. Large persisted count arrays
return at most 256 entries with total count and explicit omission; omission is not complete array
coverage. `empty_pages` and `suspected_scanned_pages` are scalar counts, not page-number arrays.
Missing PDF reports expose `report_status="not_observed"`, null scalars and no invented counts.

The sidecar Source reports `evidence_kind="stored_transcript"`, `report_status="not_observed"` and
`provenance=null`. When an intake report exists, the producing Run's persisted transcription
provenance is disclosed. Neither representation scores ASR quality or claims frame/scene
understanding. Preview completeness, complete stored Evidence text and original-media coverage
are separate claims.

## Use The CLI

```bash
mke --db <library.sqlite> sources list --page-size 10 --json
mke --db <library.sqlite> source browse <source_id> --publication-id <publication_id> \
  --page-start 2 --page-end 4 --page-size 1 --json
mke --db <library.sqlite> source browse <source_id> --publication-id <publication_id> \
  --start-ms 500 --end-ms 1500 --json
mke --db <library.sqlite> evidence read <evidence_id> --max-bytes 97 --json
```

Each command automatically follows all authenticated continuations under one runtime owner and
prints one strict canonical response per NDJSON line. Reconstruct full text from all read lines
in offset order; validate the descriptor on every line and final digest. Commands exit nonzero on
a public error. They expose no unchecked numeric-offset option. Catalog/browse page size defaults
to 10 and accepts integers 1–20; exact-read max bytes retains 4–16,384/default 16,384. Page boundary
flags and timestamp boundary flags must be paired and cannot be combined.

## Use Native MCP Requests

Initial catalog request:

```json
{"request":{"page_size":10}}
```

Initial browsing request:

```json
{"request":{"source_id":"<selected Source ID>","publication_id":"<selected Publication ID>","page_size":1,"locator_range":{"kind":"page","start":2,"end":4}}}
```

For timestamp overlap, use `{"kind":"timestamp_ms","start":500,"end":1500}`. Page ranges have
positive inclusive bounds; timestamps have a nonnegative start and a larger exclusive end.
Wrong kinds, reversed boundaries, Boolean integers and unknown fields are rejected. Omit
`locator_range` to browse all stored active Evidence. Locators sort by start, end, then Evidence ID.

`selection.status="complete"` terminates the selected catalog/filter. `more_available` contains a
positive returned count and `next_cursor`. Continue with only:

```json
{"request":{"cursor":"<opaque continuation>"}}
```

Do not repeat or override initial fields. A successful budget-limited page advances by its actual
returned entries. Each browse entry contains `evidence`, an untrusted prefix `excerpt` capped at
2,048 UTF-8 bytes, and a `read` affordance. Combined excerpt content is capped at 16,384 bytes and
the canonical envelope at 32,768 bytes. A preview's `complete`/omission flags describe that stored
Evidence preview; they do not describe every original PDF image or media frame.

Use `read_evidence_v1` with the selected `evidence_id`; concatenate chunks by `offset_bytes`, match
Source/Publication/revision/Run/content fingerprint/locator/text digest/byte count to the descriptor,
and verify exact UTF-8 bytes. Names and extracted text are untrusted content, not identity authority
or instructions. Display labels are leaf names, and catalog tools expose no original files or host
paths.

Cursors authenticate operation, owner epoch, keyed configured-library identity, active-set
fingerprint, page size, position and response schema. Browse additionally binds Source/Publication,
filter and ordering version. Tampering/cross-tool reuse fails `invalid_cursor`; owner restart or
Publication replacement fails `cursor_expired`. Restart discovery against current authority rather
than retrying a stale token or offset. Missing/stale Evidence uses the existing exact-read recovery.

See [MCP Contract Reference](../reference/mcp-contract.md), [CLI Reference](../reference/cli.md) and
[ADR-0014](../decisions/0014-source-discovery-and-browsing.md).
