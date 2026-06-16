# Real PDF Intake Engineering Review

Review date: 2026-06-16

Reviewed artifact:

- `docs/superpowers/specs/2026-06-16-real-pdf-intake-design.md`

## Verdict

Approved for implementation planning after required engineering constraints are folded into the
spec and plan.

D1 remains a coherent slice: replace the fixture-only PDF extractor with a PyMuPDF-backed
text-layer intake adapter, attach `PdfIntakeReport` diagnostics to PDF Runs, and preserve the
existing active Publication lifecycle.

## Architecture Findings

| Priority | Finding | Resolution |
|---|---|---|
| High | `IngestResult` has no slot for `PdfIntakeReport`, but CLI and MCP need the report fields. | Extend `IngestResult` with `intake_report: PdfIntakeReport | None = None`. |
| High | The extractor return type is underspecified. The new adapter must return both report and pages. | Define `PdfExtractionResult(report, pages)` as a project-owned DTO. |
| High | The PyMuPDF extraction call must be explicit. Default `get_text()` ordering is not enough for multi-column PDFs. | Use `page.get_text("text", sort=True)` and cover it with a multi-column fixture test. |
| Medium | The spec claims adapter replaceability, but current application code imports `extract_text_pages()` directly. | Add a small extractor protocol or callable boundary before wiring PyMuPDF. |

## Testing Findings

Required implementation-plan coverage:

- Multi-page text-layer PDF success.
- Empty page accounting without Evidence creation.
- Encrypted PDF failure.
- Truncated or damaged PDF failure.
- 50+ page page-numbering fixture or generated PDF.
- Multi-column text ordering through `sort=True`.
- Failed extraction leaves active Search unchanged.
- `IngestResult` carries `intake_report`.
- CLI ingest and `mke run get` expose intake summary fields.
- MCP ingest exposes intake summary and avoids path or stack-trace leaks.
- MCP rejects oversized PDFs before opening PyMuPDF.
- Existing Ask, Search, and Publication failure-injection tests keep passing.

Concurrency conflict coverage is deferred because the current Pilot runtime is still a local
single-owner process. The existing latest-request-wins Publication tests remain the D1 boundary.

## Performance And Security Findings

| Priority | Finding | Resolution |
|---|---|---|
| High | PyMuPDF dependency version was not constrained. | Pin `pymupdf>=1.24.0,<2`. |
| High | MCP accepts files under the allowed root without a size ceiling. | Add a 100 MB PDF size guard before opening PyMuPDF. |
| Medium | Text normalization goals conflict unless priority is defined. | Preserve page semantics first; normalize line endings and unsafe controls; use one-line formatting only at CLI rendering. |
| Medium | A new extractor fingerprint can break validation of old manifest rows. | Recognize both `builtin-pdf-text-v1` and `pymupdf-text-v1` for PDF manifests. |
| Medium | PyMuPDF can extract non-ASCII text, but current Search and Ask query tokenization is ASCII-only. | Keep Unicode retrieval out of D1 and document it as a later retrieval-quality slice. |

## Follow-Up

The implementation plan must explicitly cover:

- `PdfIntakeReport` and `PdfExtractionResult` DTO placement.
- `IngestResult` extension.
- PyMuPDF adapter boundary and `get_text("text", sort=True)`.
- PyMuPDF version pin and ADR.
- Encrypted, damaged, large, and multi-column PDF tests.
- Legacy PDF fingerprint compatibility.
- MCP 100 MB file-size guard.
- Text normalization priority.
- Non-ASCII retrieval limitation.
