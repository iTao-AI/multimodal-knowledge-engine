# Real PDF Intake Design

## Goal

Add a faster real-PDF intake slice by replacing the fixture-only PDF parser with a PyMuPDF-backed
adapter while preserving the current clean Evidence lifecycle.

D1 should make MKE useful for ordinary text-layer PDFs:

```text
local PDF
-> PyMuPDF text-layer intake
-> PdfIntakeReport
-> page Evidence candidate
-> existing Run validation and Publication activation
-> active Search / evidence-only Ask
```

This is not an OCR, table extraction, embedding retrieval, or generative Ask slice.

## Current State

- The current PDF adapter is a minimal regex parser for deterministic uncompressed fixture PDFs.
- The application and domain layers already prove the trustworthy lifecycle:
  `Source -> Run -> candidate Evidence -> RunManifest -> Publication -> active Search`.
- MCP and CLI already expose ingest, Run inspection, active Search, and evidence-only Ask.
- The legacy RAG-OCR project contains validated implementation experience around document
  parsing, header-recursive chunking, hybrid retrieval, low-confidence refusal, and Agent tool
  safety, but its service layout and API shape must not be copied into MKE.

## Decision

Use PyMuPDF for D1 PDF text-layer intake.

Reasons:

- It substantially accelerates support for real text-layer PDFs compared with extending the
  fixture-only parser.
- It provides page-level text extraction and layout metadata that can support later chunking,
  page diagnostics, table-aware extraction, and OCR routing without changing MKE domain contracts.
- It runs locally and fits the current offline proof model.
- It must stay behind `src/mke/adapters/pdf/`; domain and application contracts must continue to
  depend only on project-owned DTOs.

The implementation PR must add an ADR for this dependency choice because PyMuPDF is dual-licensed
under AGPL or commercial license terms. The ADR must state:

- PyMuPDF is the current open-source PDF adapter for the public project.
- MKE's domain and application contracts are not PyMuPDF-specific.
- Closed-source or commercial redistribution requires license review, a commercial PyMuPDF
  license, or a replacement permissive adapter.
- The adapter can be swapped without changing `Evidence`, `RunManifest`, `Publication`, Search, or
  Ask contracts.

This is an explicit speed-first decision for the open-source proof. The known escape route is a
future PDF extraction sidecar that emits a stable MKE-owned JSON contract, similar to the current
short-video transcript sidecar pattern. D1 does not implement that sidecar because in-process
PyMuPDF is the fastest path to real text-layer PDF validation.

The dependency must be pinned as `pymupdf>=1.24.0,<2` in the implementation PR. A future major
upgrade requires re-running the PDF smoke harness because extraction order, repair behavior, and
encryption handling are part of the intake contract.

## Legacy RAG-OCR Reuse Policy

D1 treats RAG-OCR as a verified prototype asset, not as a codebase to transplant.

Allowed reuse:

- Reuse lessons from document parsing, chunk statistics, failure-case tracking, quality gates, and
  Agent tool safety.
- Convert public-safe legacy learnings into MKE tests, fixtures, adapter contracts, or evaluation
  manifests.
- Port small focused algorithms only after isolating dependencies, rewriting names to MKE
  vocabulary, adding tests first, and fitting the code behind MKE-owned ports.

Disallowed reuse:

- Do not copy the legacy service layout, multi-service startup scripts, database collection model,
  endpoint naming, `/api/v1` style routes, private evidence paths, or personal planning material.
- Do not import legacy modules from their old repository path at runtime.
- Do not introduce LangChain, Milvus, Redis, FastAPI, or reranker dependencies into D1.
- Do not expose legacy terms such as `knowledge_base`, `chunk`, `job`, `fast`, or `accurate` in
  MKE public contracts.

Migration candidates recorded for later slices:

| Legacy capability | D1 handling | Later MKE target |
|---|---|---|
| Header-recursive Markdown splitting | Audit only | `Segment` / `Passage` design after page Evidence is stable |
| Hybrid retrieval, RRF, rerank | Audit only | retrieval quality / eval slice |
| Low-confidence refusal and `DocumentQualityReport` | Use as design input | Search and Ask quality report slice |
| Agent tool safety constraints | Reuse principles | MCP and future HTTP contract hardening |
| OCR parser routing | Audit only | OCR routing slice after text-layer intake |

## D1 Scope

Implement one PDF intake adapter that can read ordinary text-layer PDFs and produce stable
page-addressed Evidence.

Required behavior:

- Open PDFs through PyMuPDF using the current recommended `pymupdf` import.
- Extract text per page with `page.get_text()` or an equivalent plain-text mode.
- Preserve 1-based page numbers in `locator_start` and `locator_end`.
- Publish extracted text pages when at least one page has trustworthy text. Mixed PDFs with both
  text pages and scanned-like pages may publish the text pages, but the intake report must expose
  the scanned-like page count so downstream Agents do not treat the extraction as complete OCR.
- Normalize extracted page text enough for stable tests:
  - trim surrounding whitespace,
  - collapse internal whitespace where needed for deterministic CLI output,
  - keep source text content unchanged enough for Search and citation.
- Produce a `PdfIntakeReport` for every attempted PDF Run.
- Fail closed when no publishable text Evidence can be produced.
- Keep all existing Publication safety guarantees.

`PdfIntakeReport` should be a project-owned DTO, not a PyMuPDF object. It should include:

- total page count,
- extracted page count,
- empty page count,
- total extracted character count,
- per-page character counts,
- suspected scanned page count,
- extraction mode,
- stable failure reason when ingestion cannot publish.

For D1, the application result must carry the intake report so CLI and MCP can expose stable
summary fields. The report does not need to become a first-class queryable product object yet.

A page is suspected scanned in D1 when plain text extraction returns no meaningful text and PyMuPDF
reports embedded images on that page. This is a routing hint, not an OCR result.

## Decision Audit Trail

| Decision | Outcome | Reason |
|---|---|---|
| Use PyMuPDF in-process for D1 | Accepted | Speed and real-PDF coverage matter more than sidecar isolation for this slice. |
| Treat PyMuPDF licensing as ADR-governed risk | Accepted | The project remains open-source; closed-source redistribution needs later license review or adapter replacement. |
| Keep sidecar extraction as an escape route | Accepted, deferred | The video sidecar pattern is proven, but implementing a PDF sidecar now would slow the current intake milestone. |
| Reuse RAG-OCR only as verified migration input | Accepted | MKE keeps its clean core and avoids importing legacy service shape. |
| Require diverse real-PDF smoke evidence | Accepted | "Ordinary PDF" needs measured smoke coverage, not only fixture success. |
| Keep `PdfIntakeReport` out of first-class query storage | Accepted for D1 | The report must be visible through application results, CLI, MCP, and Run inspection before a storage model is stabilized. |

## Implementation Constraints

D1 must make the adapter boundary explicit before adding PyMuPDF logic:

- Define `PdfIntakeReport` and `PdfExtractionResult` as project-owned DTOs.
- Extend `IngestResult` with `intake_report: PdfIntakeReport | None = None`.
- Add a small PDF extractor protocol or callable boundary so the application service is not tied to
  a module-level `extract_text_pages()` function.
- Use `page.get_text("text", sort=True)` for the first implementation. The `sort=True` choice is
  part of the D1 contract because multi-column PDFs otherwise produce unstable reading order.
- Store the report as Run-attached diagnostics, not as a standalone product object. The storage
  adapter may use a `pdf_intake_reports` table keyed by `run_id`.
- Preserve backward manifest compatibility by recognizing both `builtin-pdf-text-v1` and the new
  `pymupdf-text-v1` PDF extractor fingerprints during validation.

Text normalization priority:

1. Preserve page boundaries and semantic text content.
2. Normalize line endings to `\n` and strip leading/trailing page whitespace.
3. Remove NUL/control characters that cannot safely be indexed.
4. Keep stored Evidence text readable; CLI rendering may collapse whitespace for one-line output.

D1 does not change Search tokenization. Non-ASCII text may be extracted and stored, but current
Search and Ask still build FTS queries from ASCII tokens only. Unicode-aware retrieval is a later
retrieval-quality slice.

## Error Semantics

Current CLI error shape remains:

```text
problem=<stable_problem_code> cause=<human_readable_cause> active_publication_impact=<impact> next_step=<operator_action>
```

D1 may keep `problem=pdf_ingest_failed`, but the cause must become more specific for common PDF
intake failures:

- invalid or unreadable PDF,
- encrypted or permission-blocked PDF,
- no extractable text,
- suspected scanned PDF without OCR enabled,
- extractor exception.

All PDF intake failures must leave `active_publication_impact=unchanged`.

No failed or partial `PdfIntakeReport`, page extraction output, or candidate Evidence may become
searchable.

## Data Flow

```text
KnowledgeEngine.ingest_pdf(path)
  -> _sha256_file(path)
  -> Source selection
  -> create Run
  -> mark Run running
  -> PyMuPDFPdfExtractor.extract(path)
       -> PdfIntakeReport
       -> list[PdfPageText]
  -> map pages to CandidateEvidence(locator_kind="page")
  -> RunManifest with PyMuPDF extractor fingerprint
  -> persist validated candidate
  -> activate Publication
```

If extraction fails before candidate validation, the Run is marked `failed` and active Search is
unchanged. If activation fails at any existing injected failure point, the existing transaction
rules continue to apply.

## Public Contract Impact

CLI:

- `mke --db <path> ingest <file>` remains the command.
- Successful PDF ingest should continue printing `run_state` and `evidence_count`.
- D1 must add stable intake fields, for example:

```text
pdf_pages=12 extracted_pages=11 empty_pages=1 extracted_chars=24839 suspected_scanned_pages=0
```

MCP:

- `ingest_file` remains the tool.
- It must expose the same intake summary fields in the successful payload when the ingested file is
  a PDF.
- Path allow-list behavior remains unchanged.
- PDF inputs over MCP must be rejected when the file is larger than 100 MB before opening PyMuPDF.
  This prevents local Agent tool calls from forcing unbounded memory use. The stable problem code
  should be `input_file_too_large`.

Search and Ask:

- No contract change.
- They continue reading only active Publications.

Run inspection:

- `mke --db <path> run get <run_id>` should expose the PDF intake summary when a Run has one.
- This does not make `PdfIntakeReport` a standalone queryable product object in D1.

Docs:

- Update CLI and MCP reference docs to replace "fixture-only PDF" wording.
- Document that OCR and scanned-PDF support remain out of scope for D1.
- Document the PyMuPDF licensing boundary in the ADR and README/developer docs if the dependency is
  added.

## Explicit Non-Goals

- OCR or `page.get_textpage_ocr()`.
- PyMuPDF4LLM, Markdown conversion, or table extraction.
- Header-recursive splitting implementation.
- Hybrid retrieval, RRF, rerank, embeddings, Milvus, Redis, or retrieval SDKs.
- HTTP server or workspace UI.
- Generative Ask or model providers.
- Importing or vendoring legacy RAG-OCR modules.
- Publishing private legacy evidence files or private local paths.

## Testing Strategy

D1 implementation must use TDD.

Required tests:

- A multi-page text-layer PDF ingests successfully and publishes page Evidence.
- Empty pages do not create Evidence but are counted in `PdfIntakeReport`.
- An encrypted PDF fails closed with a stable cause and leaves active Search unchanged.
- A truncated or damaged PDF fails closed with a stable cause and leaves active Search unchanged.
- A multi-column PDF fixture proves the `sort=True` extraction path is used.
- A 50+ page text-layer fixture or generated test PDF preserves page numbering.
- A no-text or scanned-like PDF fails closed and leaves active Search unchanged.
- A malformed PDF fails with `pdf_ingest_failed` and a stable cause.
- Reprocessing a failed or no-text PDF leaves the previous active Publication searchable.
- Existing failure-injection tests still prove no partial candidate output becomes searchable.
- CLI ingest output includes stable intake summary fields when ingest succeeds.
- `mke run get` exposes intake summary for PDF Runs.
- MCP `ingest_file` does not leak absolute paths or stack traces when PyMuPDF raises.
- MCP `ingest_file` rejects PDFs larger than 100 MB before opening the extractor.
- `mke demo --verify` remains deterministic and offline.
- Existing Ask and Search tests remain unchanged except for expected PDF text fixture wording if the
  fixture changes.
- A local smoke harness validates 10-20 diverse text-layer PDFs and records extraction success,
  extracted page count, suspected scanned page count, and failure causes.

Test fixtures committed to the repository must be public-safe and small. If the smoke harness uses
larger or private local documents, commit only the harness and redacted aggregate results, not the
source documents or local paths.

## Acceptance

D1 is accepted when a reviewer can run the standard checks and see that MKE can ingest a normal
text-layer PDF through the same trusted Publication lifecycle while producing an inspectable intake
summary.

Required verification:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke demo --verify
```

The PR must also explain the PyMuPDF licensing boundary and confirm that OCR, layout-aware
chunking, hybrid retrieval, and legacy code transplantation remain out of scope.
