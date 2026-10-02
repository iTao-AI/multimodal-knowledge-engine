# Discover a Source and read its active Evidence

Date: 2026-10-01. Status: approved design for local implementation by the design owner under the delegated improvement scope. Publication remains separate.

## Goal and actual baseline

An Agent or operator should discover available Sources, choose one by its name and provenance, browse its page or timestamp Evidence, and read the complete stored text without guessing a matching keyword first.

The runtime already publishes PDF text-layer pages and audio/video transcript segments into active SQLite Publications. search_library_v2 has bounded, loss-aware pagination; read_evidence_v1 has exact UTF-8 reading, digests, and stale-cursor guards. The offline export viewer already has Source navigation. The runtime MCP surface has no equivalent Source catalog or Source-scoped browsing. Search completeness is query-local and does not imply complete document coverage.

Keep the current search ranking, default CJK strategy, opt-in mixed strategy, Evidence unit, publication authority, export formats, and exact-read contract unchanged.

## Chosen design

Add two versioned read-only MCP tools and CLI equivalents, backed by shared application/storage operations:

- list_sources_v1 returns active Source metadata in a bounded catalog.
- browse_source_evidence_v1 returns ordered Evidence descriptors and bounded previews for one explicitly selected active Source/Publication, optionally within a locator range.

Reuse read_evidence_v1 for complete text. This closes the known-document workflow without making search admit unrelated material or promoting an experimental retrieval strategy. Rejected alternatives: change default search ranking to compensate for missing navigation; add a generative answer endpoint; load the entire library's full Evidence text just to list Sources; create a separate catalog index with competing authority.

## Public contract

Catalog entries include Source ID, display name, media type, content fingerprint, active Publication ID and revision, producing Run ID, extractor fingerprint, required stages, and active Evidence count. Return only active Publications from the configured library. Do not expose host paths, original files, inactive candidates, or unpublished revisions.

Source browsing requires source_id and publication_id obtained from the catalog. Evidence entries carry the existing descriptor identity, provenance, locator, text digest, original byte count, and a bounded preview with an explicit truncation signal. Full text is obtained by read_evidence_v1, not by treating a preview as complete.

An optional page range has positive inclusive start/end boundaries; an optional timestamp_ms range has non-negative start and larger exclusive end, selecting segments that overlap it. Reject a locator kind incompatible with that Source. Sort by locator start, locator end, then Evidence ID. An omitted range browses the Source's complete active Evidence set in that order, subject to pagination.

Both tools accept page size 1–20 with default 10 and an opaque continuation cursor. Pagination returns complete or more with a next cursor; if an existing response-size cap is reached, preserve the project's explicit capped/completeness semantics rather than silently dropping entries. No mandatory all-library text materialization is permitted. Share logic with CLI commands; CLI pagination must also pin authority rather than use an unchecked numeric offset across changing snapshots.

Use additive mke.list_sources_response.v1 and mke.browse_source_evidence_response.v1 schemas. Preserve all existing MCP schema versions and export consumers. CLI command names and flags can follow existing conventions in the implementation plan; they must support the same Source/Publication selection and locator semantics.

## Coverage disclosure

Coverage metadata is a projection of the selected Publication's producing Run, not an inferred capability score.

- For PDF, surface the persisted extraction_mode, total_pages, extracted_pages, empty_pages, suspected_scanned_pages, and page_char_counts, subject to bounded response size. Missing reports are explicitly not_observed. Never interpret empty pages or suspected scans as proven missing semantic content.
- For audio/video, disclose transcript Evidence and existing persisted transcription provenance when available. Do not claim visual scene understanding or complete transcription quality.
- Explain that this tool browses stored active Evidence, not every original PDF image or media frame. Display mixed-PDF text-layer limitations in the runnable example.

Do not add OCR, models, raw-file access, or new extraction behavior in this slice. The metadata itself must not require loading unbounded page-count arrays into every catalog entry: catalog entries may provide a bounded summary, with detailed counts only in the selected Source response and an explicit omission indicator.

## Authority and native integration

Read Source metadata, producing Run coverage, and Evidence membership from a consistent active-authority snapshot. Reuse the existing runtime owner, authenticated cursor, active-set fingerprint, and exact-read provenance checks.

Catalog and browsing cursors bind the operation, library/runtime owner, active-set fingerprint, page size, position, and response schema. Browse cursors additionally bind Source/Publication identity, locator filter, and ordering version. Changed active Publications, owner restart, tampering, altered filters, cross-tool reuse, or an unrelated library must fail with bounded public errors. Never silently continue a stale catalog against a new Publication.

Authority graph: accepted Source/Run/Publication in SQLite -> application read snapshot -> bounded MCP/CLI projections -> Agent selects a descriptor -> existing exact-read consumer. Names and model text do not grant Evidence identity. Keep SQLite publication writes and activation atomic; read tools cannot publish anything.

Record an ADR or equivalent durable decision for this additive public contract. Verify the actual current MCP implementation and installed dependencies before introducing a new native API; no dependency upgrade is required by the design.

## Verification and observable acceptance

1. A real installed CLI/MCP boundary can list a declared synthetic PDF Source, browse a specified page that a chosen lexical query does not admit, and read its Evidence to completion with the existing digest. This proves discovery/navigation, not improved search recall.
2. The same workflow supports a timestamp segment from a declared transcript Source and accurate locator ordering.
3. A mixed PDF honestly reports text-layer coverage and suspected scans without claiming OCR. Missing coverage information is explicit.
4. Pagination has no repeats or omissions within the pinned active set. Test publication replacement during continuation, cross-Source or cross-library IDs, malformed/forged/restarted cursors, wrong locator kinds, zero matches, oversized previews, Unicode boundaries, and unpublished Evidence.
5. Existing search, exact-read, atomic publication, consumer provenance, and export tests remain green. Run the relevant full suite and important-feature documentation audit on the final candidate. A direct helper call or manually fabricated MCP result alone is insufficient integration evidence.

Use small public synthetic fixtures and one independent consumer script/example. Deliver a concise walkthrough showing catalog -> Source selection -> locator browsing -> exact read -> citation provenance. Update README/docs/tool discovery only for implemented behavior.

## Slices, ownership, and stop condition

1. Define strict catalog/browse projections and coherent storage snapshots, with failing contract and stale-authority tests.
2. Implement shared application operations and MCP/CLI adapters; prove native consumers and exact-read reuse.
3. Add coverage disclosure, the short demonstration, affected references, and final verification/review. Stop at the accepted workflow and explicit remaining gates; do not expand into a retrieval research program.

Delivery owner: the dedicated project task, using Sol Max and Superpowers writing-plans for implementation details. Select direct execution or subagent-driven development once. Behavioral implementation and substantial review use Sol High; bounded mechanical work may use Luna Max. Material changes to public behavior or authority return to the design owner.

Public main was verified at e8b6bf0e6ca44cdd77403f125c9cb9852bc960b5. The prepared branch starts at 0bac59cb2cd7d8c8a31e352bb801a4440112b8ad, with only the current local documentation/workflow update carried from main; no unmerged feature prerequisite is assumed. Preserve all other worktrees, especially retrieval-coverage-stage1-spec, which contains unique implementation and unowned changes.

Authorized: local implementation, verification with existing environments, documentation, review, and semantic local commits. No push, PR, merge, release, deployment, new installation, or model download is included. Report exact HEAD, executed checks, native consumer evidence, and missing gates at local handoff.

## Deferred

Semantic/hybrid retrieval, reranking, OCR runtime promotion, new context units, generative Ask, hosted multi-user catalog, and changes to old retrieval-coverage work. Existing research artifacts are not approval to change the runtime.
