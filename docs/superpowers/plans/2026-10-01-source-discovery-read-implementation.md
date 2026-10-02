# Source Discovery And Exact Evidence Read Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Discover an active Source, browse its stored page or timestamp Evidence, and reuse exact read to reconstruct and verify complete text.

**Architecture:** Extend the existing SQLite active-authority snapshot with bounded catalog and Source-scoped reads. Shared application projections and authenticated cursors feed strict additive MCP responses and CLI commands. Keep the existing exact-read, retrieval, Publication, and export contracts.

**Tech Stack:** Python 3.12–3.13, SQLite, project-owned dataclasses, Pydantic 2, installed MCP 1.29.1 FastMCP and stdio SDK.

**Spec:** `docs/superpowers/specs/2026-10-01-source-discovery-read.md`

**Status:** Completed local delivery on 2026-10-02. All three tasks and the final independent whole-branch review are complete, with no open findings or remaining work within the approved local gate. Starting HEAD: `102b114d150f005ed66f680b995b7b9733d985cb`; branch: `codex/source-discovery-read`.

**Acceptance:** Feature HEAD `0af8cfb43a79a0e02d45ba42dfd9416fe42b978a` passed the full suite (`4388 passed, 14 skipped`), lint, configured types, product proof, demo, native consumer, package inspection and documentation audit. See the [final review](../reviews/2026-10-01-source-discovery-read-review.md) for results and limits. The local branch, clean isolated worktree and validation evidence are retained; publication is a separate authorization scope.

## Global Constraints

- Keep the current search ranking, default CJK strategy, opt-in mixed strategy, Evidence unit, publication authority, export formats, and exact-read contract unchanged.
- Return only active Publications from the configured library. Do not expose host paths, original files, inactive candidates, or unpublished revisions.
- Both tools accept page size 1–20 with default 10 and an opaque continuation cursor.
- Use additive mke.list_sources_response.v1 and mke.browse_source_evidence_response.v1 schemas. Preserve all existing MCP schema versions and export consumers.
- An optional page range has positive inclusive start/end boundaries; an optional timestamp_ms range has non-negative start and larger exclusive end, selecting segments that overlap it.
- Sort by locator start, locator end, then Evidence ID.
- Catalog and browsing cursors bind the operation, library/runtime owner, active-set fingerprint, page size, position, and response schema. Browse cursors additionally bind Source/Publication identity, locator filter, and ordering version.
- No mandatory all-library text materialization is permitted.
- Coverage metadata is a projection of the selected Publication's producing Run, not an inferred capability score.
- Do not add OCR, models, raw-file access, or new extraction behavior in this slice.
- Authorized: local implementation, verification with existing environments, documentation, review, and semantic local commits. No push, PR, merge, release, deployment, new installation, or model download is included.

## Review Focus

- A copied database with the same active IDs but a different configured library must reject a cursor; bind an opaque keyed database identity in addition to owner/active-set identity (Task 1 and Task 2).
- Oversized names, metadata, text previews, and PDF coverage arrays must obey response limits with explicit errors/omission indicators and positive continuation progress (Task 1).
- Concurrent Publication replacement must not mix metadata, coverage, or Evidence from different reads; validate and read in one existing SQLite transaction without nested BEGIN (Task 1).
- A CLI command that spans multiple pages must keep one runtime owner and authenticate each continuation, stopping on changed authority (Task 2).
- A consumer must distinguish preview completeness, stored-Evidence completeness, and original-media coverage, verifying exact UTF-8 bytes and citation provenance rather than inferring OCR or scene understanding (Task 3).

## Implementation Decisions

- Add focused `domain/source_discovery.py`, `application/source_discovery.py`, `application/source_cursor.py`, `interfaces/source_schemas.py`, and `interfaces/source_discovery.py` modules. Extend existing facades and registration points minimally.
- Reuse `_read_and_validate_active_publication_rows`, active-set fingerprint derivation, cursor parsing/authentication, `EvidenceDescriptor`, `build_excerpt(..., hints=())`, and the 32768-byte canonical/16384-byte content budgets. Validate mandatory metadata before returning output; overflow is a bounded public error. Budget-limited successful pages return a cursor for remaining entries, never silent omission.
- Catalog order is `(content_fingerprint, source_id)`; browse ordering version is `locator-start-end-evidence-id-v1`. SQL reads selected bounded rows after authority validation. Catalog reads no Evidence text. Browse preflights selected Evidence byte size and reads only its bounded page; reuse the existing 16 MiB readable Evidence ceiling.
- Request envelopes use strict initial/continuation branches. Initial list has `page_size`; initial browse has `source_id`, `publication_id`, optional `locator_range`, and `page_size`; continuation is cursor-only. A page range uses `{kind: page, start, end}` and a timestamp range uses `{kind: timestamp_ms, start, end}`. Reject unknown fields, booleans masquerading as integers, wrong kinds, and invalid ranges.
- New cursor payloads keep authenticated `mke.mcp_cursor.v1` envelopes. Bind configured database identity with an owner-keyed digest, never a public filesystem path. Validate cursors inside the storage snapshot before using their route. Cursor errors reuse bounded `invalid_cursor`/`cursor_expired` recovery semantics.
- PDF catalog coverage carries report presence, extraction mode, total/extracted/empty/suspected page counts; these existing fields are scalars. The persisted `page_char_counts` array is omitted explicitly in catalog summaries. Selected Source coverage returns at most 256 counts and marks omission. Read array details with bounded SQLite JSON projections rather than parsing unbounded arrays in every catalog entry. Missing reports use `not_observed`.
- Transcript coverage identifies stored transcript Evidence and includes persisted `TranscriptIntakeReport` provenance when available; a missing report is `not_observed`. Do not infer provider quality or visual understanding.
- CLI commands are `mke sources list`, `mke source browse <source_id> --publication-id <id>`, and `mke evidence read <evidence_id>`. Catalog/browse use `--page-size` with the same default/bounds. Browse accepts paired `--page-start/--page-end` or `--start-ms/--end-ms`. Read accepts `--max-bytes` with existing bounds. `--json` streams one existing canonical response per line. Each command automatically follows authenticated continuations within one owner and exits nonzero on a public error; there is no unchecked numeric-offset option.
- Reuse existing installed development dependencies through a local `.venv` source overlay created without pip/install; its `.pth` points at this worktree `src`, and isolated subprocesses resolve the current module and local metadata. Verify module identity before checks; do not sync/install. Keep verification logs under ignored task-owned `artifacts/source-discovery-read/`. Full-suite results belong to the final candidate; task iterations use focused tests.
- Existing versioned historical tool fixtures remain immutable. Introduce a current twelve-tool expectation fixture and route current consumers/tests to it while asserting the original ten tool schemas remain equal. Historical release notes remain historical.

### Task 1: Strict projections, coherent storage, coverage, and authenticated cursors

**Files:**
- Create: `src/mke/domain/source_discovery.py`, `src/mke/application/source_discovery.py`, `src/mke/application/source_cursor.py`, `src/mke/interfaces/source_schemas.py`.
- Modify: `src/mke/application/__init__.py`, `src/mke/adapters/sqlite/__init__.py`; minimal reuse exports only if needed.
- Create tests: `tests/domain/test_source_discovery.py`, `tests/adapters/test_sqlite_source_discovery.py`, `tests/application/test_source_cursor.py`, `tests/interfaces/test_source_schemas.py`.

**Interfaces:**
- Consumes: `ActiveAuthoritySnapshot`, `EvidenceDescriptor`, `EvidenceExcerpt`, `CursorOwnerMaterial`, `parse_cursor_untrusted`, and current producing-Run report tables.
- Produces: `KnowledgeEngine.list_sources_page(*, position: int, page_size: int, authority_validator: Callable[[ActiveAuthoritySnapshot], None]) -> SourceCatalogPage` and `KnowledgeEngine.browse_source_evidence_page(source_id: str, publication_id: str, *, locator_range: SourceLocatorRange | None, position: int, page_size: int, authority_validator: Callable[[ActiveAuthoritySnapshot], None]) -> SourceBrowsePage`.
- Produces: immutable Source metadata and PDF/transcript coverage DTOs; `ListSourcesV1Request/ResponseV1`, `BrowseSourceEvidenceV1Request/ResponseV1`; operation-specific cursor encoding/validation and shared bounded page assembly. Task 2 consumes these interfaces; final naming changes must be recorded here before handoff.

- [x] **Step 1: Add failing strict DTO/schema tests.** `test_source_ranges_are_strict` rejects page zero, reversed ranges, timestamp equal ends and mixed kinds; `test_additive_responses_are_closed` rejects extra/missing provenance and incorrect terminality. PDF omitted arrays and missing reports have explicit representations.
- [x] **Step 2: Add failing storage/cursor tests and observe RED.** Catalog excludes unpublished/failed Sources and loads no text; browse returns ordered active descriptors, inclusive PDF ranges, timestamp overlap, zero matches, correct digests and Unicode previews. Reject wrong Publication/Source/library graph, superseded Evidence, malformed/forged/cross-tool/restarted cursors and altered bindings. Use a second connection to replace Publication while testing snapshot coherence and continuation expiry. Test large arrays/names/previews against budgets with no repeats or omissions.
- [x] **Step 3: Implement the above interfaces.** Reuse existing active graph validation inside one SQLite read transaction, selected-row SQL limits, producing-Run coverage, keyed library binding and UTF-8-safe previews. Keep read-only operations incapable of activation.
- [x] **Step 4: Run focused GREEN and existing authority regressions.** Run the four new test files plus `tests/adapters/test_sqlite_evidence_access.py`, `tests/adapters/test_sqlite_evidence_provenance.py`, `tests/application/test_pdf_publication.py`, `tests/application/test_audio_publication.py`, `tests/application/test_video_publication.py`, and lint/type checks on affected files. Required result: all pass; record exact RED/GREEN evidence.
- [x] **Step 5: Self-review and commit intentional files.** Commit message: `feat: add active source discovery snapshots and cursors`. Return interface inventory, exact HEAD, test evidence and concerns for a task-scoped spec/quality review.

### Task 2: Shared MCP/CLI adapters and real native consumer workflow

**Files:**
- Create: `src/mke/interfaces/source_discovery.py`, `tests/interfaces/test_source_discovery.py`, `tests/interfaces/test_cli_source_discovery.py`, `tests/proof/test_source_discovery_stdio.py`.
- Modify: `src/mke/interfaces/mcp_server.py`, `src/mke/interfaces/cli_parser.py`, `src/mke/cli.py`, current MCP inventory tests/consumer fixture routing.
- Create: `tests/fixtures/source-discovery-v1/mcp-tool-schemas.json`; public synthetic fixture/client modules needed by the tests.

**Interfaces:**
- Consumes: Task 1 facade methods, strict schemas, projections and cursor APIs; existing `McpRuntimeConfig`, `RuntimeConfig.owner_state`, `read_evidence_v1`.
- Produces: `list_sources_v1(config, request)` and `browse_source_evidence_v1(config, request)` shared operations, native FastMCP tool registration, CLI commands specified above. JSON CLI output uses the same strict canonical models as MCP.

- [x] **Step 1: Add failing adapter/discovery tests and observe RED.** Assert twelve registered tools, native `request` envelopes, structured output, read-only annotations and exact old schema equality. Assert both new schema versions, public redaction, invalid ranges/IDs/cursors, 1–20 default-10 pages, explicit more/complete states, and complete exact-read reuse.
- [x] **Step 2: Add failing subprocess CLI/stdin-stdout SDK tests.** Generate a small synthetic PDF with a requested page outside a chosen lexical query, plus timestamp transcript fixture. Invoke the installed CLI entrypoint against current source and a real stdio SDK client. Discover Source -> select explicit Publication -> browse page/time interval -> concatenate exact-read chunks -> verify original digest and citation fields. Exercise multiple catalog/browse pages and fail on replacement during continuation; CLI retains one owner throughout.
- [x] **Step 3: Implement shared adapters and registrations.** Keep storage/cursor validation in the snapshot, apply final canonical response budgets, catch errors through bounded public serializers, and stream CLI pages/chunks under one owner. Preserve all old descriptions/schemas/annotations. Add current fixture routing without rewriting historical expectations.
- [x] **Step 4: Run focused GREEN and consumer regressions.** Run new interface/proof tests, current MCP fixture tests, MCP completeness/contract tests, and existing provenance and source-pack consumer tests. Verify installed module import identity and actual native tool calls in report. Required result: all pass with no transport fabrication.
- [x] **Step 5: Self-review and commit intentional files.** Commit message: `feat: expose source discovery through MCP and CLI`. Return exact HEAD, native consumer evidence and concerns for task-scoped spec/quality review.

### Task 3: Independent example, honest coverage, durable contract and final verification

**Files:**
- Create: `scripts/source_discovery_consumer.py`, `tests/scripts/test_source_discovery_consumer.py`, `docs/how-to/discover-and-read-sources.md`, `docs/decisions/0014-source-discovery-and-browsing.md` (next unused ADR number verified at task start).
- Modify: `README.md`, `docs/reference/mcp-contract.md`, `docs/reference/contracts.md`, `docs/how-to/use-mke-mcp.md`, `docs/tutorials/getting-started.md`, affected current proof/inventory references and this plan.
- Create: `docs/superpowers/reviews/2026-10-01-source-discovery-read-review.md` with public-neutral durable review/validation evidence.

**Interfaces:**
- Consumes: implemented twelve-tool native server and CLI, frozen exact read, Task 1 producing-Run coverage.
- Produces: standalone official-SDK consumer using only native contracts; walkthrough from discovery through citation provenance, explicit text-layer/transcript limits, documented commands and durable ADR.

- [x] **Step 1: Add failing independent-consumer tests and observe RED.** Verify mixed PDF report fields, suspected scans, missing-report `not_observed`, detailed-array omission indicators, transcript provenance, no image/OCR/visual quality claims, UTF-8 reconstruction, and digest/provenance mismatch detection.
- [x] **Step 2: Implement and run the short independent example.** Use public synthetic inputs, real CLI ingest/native stdio SDK tools and an explicitly non-admitting lexical query. Report catalog/page/timestamp/exact-read/coverage observations and measure canonical/SDK bytes. No application helper may fabricate consumer responses.
- [x] **Step 3: Update durable docs and references.** Record additive public contract and authority without changing accepted lifecycle ADRs. Explain page inclusivity, time overlap, complete/more pagination, omission indicators, `not_observed`, stale cursor recovery, same-owner CLI traversal, untrusted names/text and exact digest verification. Add the example to README/tool discovery and preserve historical release records.
- [x] **Step 4: Verify the final candidate.** Run full `pytest -q`, `ruff check .`, `pyright`, product proof, demo, independent native consumer and `git diff --check` using the existing environment. Run packaging only with already available build dependencies; otherwise preserve the specific missing gate. Run the important-feature `gstack-workflows:document-release` audit in local scope. Resolve current-scope failures with regression evidence, no installs or scope expansion.
- [x] **Step 5: Self-review and commit intentional files.** Commit message: `docs: document source discovery and verified exact reads`. Return exact HEAD, executed checks, public-neutral durable findings and missing gates for task review and final whole-branch review. Mark this plan complete only after all local acceptance gates are resolved; retain clean recoverable worktree and task-owned validation evidence.
