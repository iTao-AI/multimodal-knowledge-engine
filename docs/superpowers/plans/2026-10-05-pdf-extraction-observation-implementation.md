# PDF Extraction Observation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the public Source-reading entry, then disclose local PDF text/raster scope consistently through opt-in catalog, browse, export and Viewer contracts.

**Architecture:** One write owner executes the ordered plan inline with `superpowers:executing-plans`. Reuse PyMuPDF, producing-Run reports and existing active-Publication transactions. Explicit versions isolate strict older schemas. A fresh independent review follows integration.

**Tech Stack:** Locked Python 3.13, PyMuPDF, SQLite, Pydantic, official MCP SDK, stdlib consumers and offline HTML.

**Spec:** [Frozen M1 design](../specs/2026-10-05-pdf-extraction-observation-design.md).

**Status:** Completed locally on 2026-10-05. The
[acceptance review](../reviews/2026-10-05-pdf-extraction-observation-review.md) records the reviewed
code, executed checks and unverified file-origin/clipboard behavior. No remote operation is part
of this completion.

## Global Constraints

- Local commits/validation only. No push, PR, merge, Release, provider or new dependency.
- Preserve old Evidence bytes/locators, Search, Ask, required stages, atomic Publication and strict old contracts/defaults.
- Root owns shared DTOs, storage, interfaces and integration. Read-only audits do not mutate the worktree.
- Keep raw test/run/UI receipts ignored. Public fixtures are small synthetic additions; historical bytes stay frozen.
- Reuse unaffected evidence; select verification by changed surface. Report actual failures and any unmet acceptance.

## Review Focus

Unknown versus zero; displayed raster versus resources/semantic content; report/Run identity;
transaction rollback; bounded materialization; explicit omitted ranges; legacy contract isolation;
independent consumer identity; HTML escaping and unchanged complete text/citations.

---

### Task 1: C0 public navigation

**Files:** `README.md`, `README_CN.md`.

- [x] Put discover → choose → browse → complete read → verify citation at the first entry.
- [x] Link the existing discovery and Viewer guides; reuse the existing screenshot.
- [x] Distinguish source-checkout features from immutable v0.1.7.
- [x] Check links and `git diff --check`; semantic documentation commit.

### Task 2: Producer and run-bound storage

**Files:** `src/mke/domain/__init__.py`,
`src/mke/adapters/pdf/extractor.py`, `src/mke/adapters/sqlite/__init__.py`, relevant PDF tests.

- [x] RED: new generated mixed/decorative/image-only/blank tests fail because the raster observation is absent.
- [x] GREEN: retain normalized text/legacy scan logic; collect displayed-raster booleans on every page.
- [x] RED: roundtrip, old rows, malformed arrays and observation-write rollback tests fail on missing persistence.
- [x] GREEN: additive table; same report/activation transaction; strict validation and producing-Run projection.
- [x] Run PDF extractor/intake/report/application tests; review exact diff; commit.

### Task 3: Versioned Source consumers

**Files:** new `domain/pdf_observation.py`, `domain/source_discovery.py`, `application/source_cursor.py`,
`interfaces/source_schemas.py`, `interfaces/source_discovery.py`, `interfaces/mcp_server.py`,
`interfaces/cli_parser.py`, `cli.py`, Source/schema/cursor/stdio tests and new current fixture.

- [x] RED: opt-in v2 payloads/ranges, cross-version cursors and old projection tests fail.
- [x] GREEN: add strict observation/v2 schemas, isolated v1 serialization, v2 tool/schema cursor bindings and CLI routing.
- [x] Catalog has no pages; browse uses at most 256 entries and explicit returned/omitted ranges.
- [x] Freeze legacy fixtures; explicitly migrate exact current inventory from 12 to 14 while proving old subsets identical.
- [x] Run Source discovery, schemas, cursor and native stdio tests; commit.

### Task 4: Export v3 and independent validator

**Files:** `domain/library_export.py`, `application/library_export.py`,
`application/__init__.py`, `adapters/sqlite/__init__.py`, `adapters/filesystem/library_export.py`,
`interfaces/library_export.py`, `interfaces/cli_parser.py`, new `scripts/compiled_library_export_consumer_v3.py`, export tests.

- [x] RED: native v3 export and independent consumer reject/roundtrip tests fail on absent v3.
- [x] GREEN: explicit third branch everywhere; bound observation to snapshot Run in the same read transaction.
- [x] Use the same observation shape; preserve exact Evidence JSONL and v1/v2 shapes/bytes/defaults.
- [x] Independent stdlib validation checks strict keys, identities, counts, ranges, inventory and hashes.
- [x] Run export domain/application/storage/filesystem/CLI/consumer checks; commit.

### Task 5: Offline Viewer observation display

**Files:** `scripts/build_compiled_library_viewer.py`, `tests/scripts/test_compiled_library_viewer.py`.

- [x] RED: v3 warnings, old v2 unknown, omitted page and escaping tests fail.
- [x] GREEN: validate v2/v3 explicitly; show Source summary/scope and selected-page warnings without changing text/citation.
- [x] Build actual v2/v3 HTML; inspect changed UI in a browser, including hostile labels/text and normal reading.
- [x] Run Viewer tests and focused diff review; commit.

### Task 6: Docs, native proof and final acceptance

**Files:** new ADR-0015; architecture; discovery/export/Viewer guides; CLI/MCP/generated references;
new provider-free consumer proof and tests as needed; spec/plan/review status.

- [x] Document observed/unknown semantics, opt-in versions, inventory migration, limitations and rollback.
- [x] Actual CLI ingestion/discovery/browse/exact-read → native MCP calls → v3 export/independent validator → Viewer build proves shared identities and exact text.
- [x] Repair current verification scaffolding: migrate temporary inventory directories and derive a separate current numeric replay schema scope; keep frozen archived validation and strict-live rejection unchanged.
- [x] Run proportionate integrated checks (full provider-free pytest, ruff, pyright, build if package surface warrants it), contract generation verification and diff checks once final inputs are stable.
- [x] Fresh Sol high independent final review; fix concrete findings with targeted re-verification.
- [x] Mark plan complete; retain local evidence; final semantic commit and report exact HEAD, results, documentation, limitations and remote authorization residue.
