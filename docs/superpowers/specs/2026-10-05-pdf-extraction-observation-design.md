# PDF Text/Raster Extraction Observation

Status: Frozen for local implementation. Scope: C0 public navigation, then M1 local PDF observations.

## Problem And Boundary

Source discovery already supports choosing a Source, browsing page/timestamp Evidence, reading its
complete stored text and verifying its citation. The README entry must expose that route and the
offline Viewer, distinguishing source-checkout additions from immutable `v0.1.7`.

A PDF page can contain both extractable text and a raster image. The old suspected-scan count only
examines pages without text, so it cannot disclose mixed pages. M1 adds an observation, not OCR,
image understanding, semantic completeness, vector-graphics coverage, a new processing route,
Source-scoped Search/Ask, or a retrieval/ranking change. Evidence bytes, locators, required stages,
exact read and Publication authority retain their existing semantics.

## Producer Signals

The existing PyMuPDF adapter keeps `get_text("text", sort=True)` and normalization unchanged. Each
page also records `bool(page.get_image_info(hashes=False, xrefs=False))`: a displayed raster-image
signal, including inline images. This uses the locked PyMuPDF adapter, without hashing images,
rendering full pages or consulting a provider. See the official
[Page reference](https://pymupdf.readthedocs.io/en/latest/page.html#Page.get_image_info).

`PdfIntakeReport.page_has_raster_images` is an optional tuple of strict booleans, aligned with the
full existing `page_char_counts`. `None` means no new observation was made. A present tuple must
have `total_pages` entries and `extraction_mode="pymupdf-text"`. The separate
`suspected_scanned_pages <= empty_pages` invariant and its `get_images()` signal remain unchanged.
Decorative images count as raster presence. Vector drawings, image meaning, readable image text,
and visual importance are not observed. Failure to collect the required new signal fails extraction
rather than inventing a negative signal.

The observed categories partition all pages:

- `text_only_pages`: normalized text count > 0, no displayed raster observed.
- `mixed_text_raster_pages`: normalized text count > 0 and displayed raster observed.
- `raster_only_pages`: no normalized text and displayed raster observed.
- `neither_text_nor_raster_pages`: neither signal; this does not prove a blank semantic page.

## Persistence And Atomicity

An additive `pdf_extraction_observations` table is keyed by the producing `run_id`. It stores an
explicit `pymupdf-displayed-raster-v1` method/version and the full boolean array. Existing PDF report
rows and their meanings are not rewritten or backfilled. Old reports and reportless Publications
project the new observation as `not_observed`, with null counts and no page entries.

The report and new observation insert participate in the existing activation transaction, along
with Publication, FTS replacement, active pointer and published Run event. Validation checks tuple
shape and its alignment with the report already validated against candidate Evidence. A report or
observation write failure rolls back replacement and preserves the previous active Publication.
Prepared/failed report writes retain the existing separate transaction. Observations do not grant
permission to bypass required PDF/OCR stages or reinterpret an OCR evaluation fingerprint.

Reads select the active Publication's producing Run inside its validated SQLite transaction, never
the latest report for a Source. Missing new tables in an older read-only Library are supported as
`not_observed` without migration. Bad present records fail closed. No original Source file is
reopened to fill missing history.

## Explicit Public Versions

Closed v1 Source models and Export v1/v2 key sets reject additive fields. Therefore:

- Add `list_sources_v2` and `browse_source_evidence_v2`, with strict `.v2` response schemas. Their
  initial request shape, Evidence descriptors/read affordance and authority are reused. Each v2
  Source includes `pdf_extraction_observation`; non-PDF Sources use null. Old v1 serializers
  explicitly omit this field. CLI `--contract-version v2` opts in; default remains v1.
- v2 cursors bind the new tool name and response schema. Cross-tool/version reuse is rejected;
  owner restart and replacement still expire cursors.
- Add explicit `--format-version v3`, `mke.compiled_library_export.v3`,
  `mke.compiled_library_export_response.v3`, and `mke.compiled_markdown.v3`. Each v3 manifest Source
  contains the same observation object as browsing. Evidence JSONL remains `mke.evidence_ref.v1`
  with exactly the same bytes. Export v1 default and v1/v2 formats remain unchanged.
- The current tool inventory becomes 14. Freeze historical 8/10/12-tool fixtures; add a new current
  fixture and migrate the standalone exact-inventory consumer explicitly. Prove every old tool's
  schema, description and annotations unchanged. Old clients selecting v1 tools continue to work;
  clients requiring exactly twelve tools must update their inventory expectation.

The observation object uses `schema_version="mke.pdf_extraction_observation.v1"`, `status`,
`method`, `extraction_scope="text_layer_only"`, `total_pages`, the four category counts, and
`pages`, `returned_page_range`, `omitted_page_ranges`. Unknown observations keep method, scope,
counts and range null, with empty arrays. Each observed page has `page_number`,
`text_layer_chars`, `has_raster_images`. Booleans are never integers. Strict validators check the
partition, sorted contiguous pages and an exact returned/omitted partition of pages 1..total.

## Returned Scope

Catalog returns scalar categories, no per-page entries, null returned range and omitted range
1..total. Browse returns at most 256 contiguous page observations. Without a PDF page filter it
returns pages 1..min(256,total); with one it starts at the requested start and ends at the smallest
of requested end, total and start+255. Out-of-document filters return no page entries. Omitted
ranges explicitly cover all other pages, including any tail after 256; at most two ranges are
needed. Export v3 uses the first-256 projection. SQLite bounds returned JSON entries before Python
materialization. Evidence pagination/`selection.status` does not describe observation completeness.

The Viewer validates v3 with an independent stdlib consumer and retains v2 input. For v2 input,
or old v3 report history, it says the new signal was not observed. It shows Source counters and
returned/omitted page ranges. A returned mixed page says: “本页含文本与图像；仅提取文本层。涉及图像的问题请核对原页。”
A page outside the observation range says its signal was not returned. Text remains selectable and
citations unchanged. No percentage, OCR confidence, full-page image, original-media file, raw path
or host permission is added. Untrusted labels/text remain escaped.

## Acceptance And Rollback

Provider-free generated public synthetic PDFs cover text-only, informative raster, decorative
raster, image-only and neither-signal pages. Tests cover legacy reports, 256+ pages and filtered
ranges, report identity on replacement, malformed observations, first/replacement write failure,
required-stage validation, strict legacy models, cursor version binding, normal text/citation
identity, independent v3 validation and HTML escaping. Do not change frozen historical fixtures.
Real console CLI, native MCP SDK calls, standalone export validation and actual Viewer build are
the consumer proof. UI observation warnings receive browser inspection; unchanged old screenshots
are reused for C0.

Rollback removes opt-in v2 routes/tool registrations and v3 rendering while retaining historical
Run/Publication/report records. The additive table may remain unused; old code ignores it. Do not
delete observations or invent backfills. Existing v3 exports need explicit regeneration in v2 for
old consumers. New current inventory expectations must revert together with registrations. This
phase stops after M1 local completion; hosted delivery is a separate authorization boundary.
