# ADR-0015: Local PDF Extraction Observations

- Status: Accepted
- Date: 2026-10-05

## Context

A nonempty PDF text layer can coexist with informative or decorative raster images. The existing
suspected-scan count only examines empty-text pages and cannot disclose that mixed-page scope.
Strict older Source and export schemas reject extra fields, so adding a field in place would
break consumers. SQLite Publication authority and exact stored text must remain unchanged.

## Decision

The existing PyMuPDF adapter records one displayed-raster Boolean per page with
`get_image_info(hashes=False, xrefs=False)` alongside unchanged normalized text character counts.
The method is `pymupdf-displayed-raster-v1`; scope is `text_layer_only`. Decorative raster images
count as present. Vector graphics and semantic content are outside this observation. The original
empty-page `get_images()` suspected-scan calculation and `suspected_scanned_pages <= empty_pages`
invariant remain unchanged. No random fallback, OCR route, model or retrieval change is introduced.

Persist new observations in an additive `pdf_extraction_observations` table keyed by immutable
producing `run_id`. Validate strict Boolean arrays, page/count lengths, extraction mode and
nonnegative character counts. The report and new observation are written in the same transaction;
successful normal intake also shares Publication activation, active FTS replacement, Source
pointer and Run transition. A write failure rolls these operations back. Once observed, a report
cannot be replaced with conflicting same-Run observations. Retry creates a new Run as before.

Explicit `list_sources_v2` / `browse_source_evidence_v2` and CLI `--contract-version v2` expose a
closed `mke.pdf_extraction_observation.v1` object. Old v1 responses and default CLI routes keep
their exact shape. Non-PDF Sources carry null. Missing older records are `not_observed`, with
nullable counts/method/scope and empty detail arrays; unknown is never converted to zero.

SQLite derives text-only, mixed text/raster, raster-only and neither counts over all observed
pages. Catalog returns aggregates only. Browse returns at most 256 contiguous page details,
with an inclusive returned range and exact omitted ranges. A requested page range bounds these
details; it does not change whole-document counts. Aggregation and bounded detail selection occur
before Python materialization in the same validated active-Publication transaction. This binds
metadata, report and Evidence to one producing Run. Versioned cursors cannot cross tool contracts.

Explicit Export v3 adds this same object to each PDF Source descriptor and canonical Markdown
derivative, while keeping exact EvidenceRef JSONL unchanged. Export v1/v2 and default v1 remain
strict and unchanged. Read-only export tolerates pre-migration databases without migrating them.
The independent stdlib v3 consumer validates closed fields, counts/ranges, page character counts
against exact Evidence, hashes, inventory and full lineage. The offline Viewer validates v2/v3;
v2 PDFs display unknown scope and v3 PDFs display aggregate/detail limitations and mixed-page
warnings. Text and citation identity remain unchanged and untrusted labels are escaped.

## Compatibility, Verification And Rollback

The current exact MCP inventory is fourteen tools. The twelve-tool Source-discovery fixture and
eight/ten-tool release fixtures remain immutable; all previous tools retain exact schemas,
descriptions and annotations. Current consumers explicitly select the new fourteen-tool fixture.
This local implementation does not publish a release or claim a new dual-Python installed-wheel
proof. The existing immutable v0.1.7 release evidence remains separate.

Provider-free regressions cover old rows, malformed observations, report-write and activation
rollback, replacements, identity, bounded/omitted details, export forgery and HTML escaping. A
[standalone native proof](../how-to/observe-pdf-extraction-scope.md) ingests declared six-page
synthetic input, compares CLI/MCP metadata and exact reads, validates actual v3 output and checks
the Viewer payload against the same Source/Publication/Run and UTF-8 bytes. No OCR or original-media
semantic completeness follows from that proof.

The additive schema changes the whole SQLite schema fingerprint. Current numeric compatibility
replay therefore derives its schema expectation from the current runtime in a temporary scope;
archived validation retains the frozen schema and input hashes. Strict-live numeric comparison
still rejects an outdated fence. No historical protocol/artifact, retrieval gate, rank or quality
claim is changed. Tests distinguish these contexts and still reject wrong observed schema data.

Rollback can use v1 Source routes and v1/v2 export immediately. Retain the additive table and
records when reverting application code; older readers ignore them. Do not backfill unknown old
Runs by inspecting current files, rewrite Evidence, delete reports or change active Publications.
Removal of the additive routes requires exact-inventory consumers to select the matching fixture.
