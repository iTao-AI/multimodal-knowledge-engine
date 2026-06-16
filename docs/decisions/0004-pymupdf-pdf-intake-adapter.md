# ADR-0004: PyMuPDF PDF Intake Adapter

- Status: Accepted
- Date: 2026-06-16

## Context

D1 must move beyond the fixture-only PDF parser and support ordinary text-layer PDFs while keeping
the MKE domain and application contracts independent from extraction libraries.

PyMuPDF is dual-licensed under AGPL or commercial license terms. Using it in-process is acceptable
for this open-source proof, but downstream closed-source redistribution requires license review,
a commercial PyMuPDF license, or a replacement adapter.

## Decision

- Use `pymupdf>=1.24.0,<2` for the D1 in-process PDF text-layer adapter.
- Keep PyMuPDF behind `src/mke/adapters/pdf/`.
- Expose only project-owned DTOs: `PdfIntakeReport`, `PdfExtractionResult`, and `PdfPageText`.
- Use `page.get_text("text", sort=True)` for page text extraction.
- Treat a future PDF sidecar adapter as the escape route for closed-source or stricter license
  isolation needs.

## Consequences

- D1 reaches real text-layer PDF intake faster than building a sidecar or custom parser.
- The core lifecycle stays independent of PyMuPDF.
- Major PyMuPDF upgrades require re-running the PDF smoke harness.
- OCR, table extraction, PyMuPDF4LLM, and layout-aware chunking remain outside D1.
