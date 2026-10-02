# ADR-0014: Active Source Discovery And Evidence Browsing

- Status: Accepted
- Date: 2026-10-02

## Context

Search answers a query-local question. A user or Agent also needs to discover an active Source and
read known pages or timestamp Evidence without first finding a matching keyword. Offline export
navigation already provides a bounded viewing surface; runtime navigation must share SQLite
Publication authority rather than create a competing index or change retrieval admission.

## Decision

Add read-only `list_sources_v1` and `browse_source_evidence_v1` over project-owned projections and
one coherent SQLite read transaction. Validate the configured Library and active Source/Asset/
Publication/Run/Manifest/Evidence graph, then authenticate continuations and read selected metadata,
producing-Run coverage and Evidence membership within that snapshot. A missing Library with
surviving Sources fails authority validation; a genuinely empty database remains supported.

Catalog order is content fingerprint, then Source ID. Browsing requires an explicit active Source
and Publication and orders by locator start, end, then Evidence ID. Positive PDF ranges are
inclusive. Timestamp ranges select overlapping intervals with a nonnegative start and larger
exclusive end. Neither read path activates or changes a Publication.

Requests have disjoint initial and cursor-only branches with page size 1–20/default 10. Responses
are additive strict `mke.list_sources_response.v1` / `mke.browse_source_evidence_response.v1` success/
error unions. Selected pages terminate with `complete` or return `more_available`; budget-limited
pages advance by actual returned count, never silently omit remaining entries. Mandatory metadata
that cannot fit fails explicitly. Canonical responses retain the 32,768-byte envelope and
16,384-byte combined preview-content budgets; each prefix preview is at most 2,048 UTF-8 bytes.
Selected Evidence is preflighted against the existing 16 MiB readable ceiling. Catalogs do not
materialize Library Evidence text.

Reuse the existing owner/HMAC cursor envelope. Bind operation, owner epoch, keyed configured
Database identity, active-set fingerprint, page size, position and response schema. Browsing also
binds Source/Publication, locator filter and ordering version. Library copying under another
configured identity, owner restart, changed active Publications, altered bindings and cross-tool
reuse cannot silently continue a snapshot. No filesystem path is exposed by this binding.

Coverage projects only the selected Publication's producing Run. PDF extraction mode and scalar
page/character/empty/suspected-scan counts remain persisted observations. Catalogs explicitly omit
`page_char_counts`; selected Sources return at most 256 count entries with total/omission metadata,
using bounded SQLite JSON projections before Python decoding. Missing reports are `not_observed`.
Transcript coverage identifies stored transcript Evidence and discloses persisted intake provenance
when available, without quality or scene claims. Empty text or suspected scans do not prove absent
semantic content.

Reuse unchanged `read_evidence_v1` for complete text. Consumers verify every read descriptor's full
citation lineage, UTF-8 offsets/counts and final SHA-256. Preview completeness, stored-text
completeness and original-media coverage are distinct. Labels and extracted text remain untrusted.
CLI catalog/browse/read commands share the same adapters and automatically traverse authenticated
pages/chunks under one owner, emitting NDJSON canonical responses without unchecked offsets.

## Compatibility And Verification

The current source checkout has twelve tools. The new current fixture is
`tests/fixtures/source-discovery-v1/mcp-tool-schemas.json`; historical eight/ten-tool fixtures,
release claims and all ten previous tool schemas/descriptions/annotations remain immutable.
Consumers that compare exact inventories must migrate explicitly. This decision does not assert
that a new package, wheel proof, release or hosted application has been published.

A standalone official-SDK example uses actual CLI ingest and stdio tools/list/call against declared
public synthetic mixed-PDF and sidecar inputs. It checks independent byte/digest/citation integrity,
coverage disclosure, pagination and actual response sizes. See
[Discover And Read Sources](../how-to/discover-and-read-sources.md). Storage/contract regressions
cover stale authority, copied libraries, invalid ownership and bounded metadata/text. Release and
whole-branch verification remain separate gates.

## Consequences

Known-Source navigation no longer depends on Search recall. SQLite remains domain truth; there is
no catalog index, generative Ask change, OCR capability, new model, raw-file API or hosted service.
Search ordering/strategy defaults, extraction behavior, atomic Publication lifecycle, exports and
exact-read schemas remain unchanged. A rollback can remove the two additive registrations and CLI
routes without a database migration; exact-inventory consumers must select matching expectations.
