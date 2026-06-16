# Real PDF Intake Autoplan Review

Review date: 2026-06-16

Reviewed artifact:

- `docs/superpowers/specs/2026-06-16-real-pdf-intake-design.md`

## Verdict

Approved with design adjustments.

The design keeps the existing Evidence lifecycle intact while accelerating real text-layer PDF
support through a PyMuPDF-backed adapter. The scope remains limited to text-layer intake,
`PdfIntakeReport`, and controlled RAG-OCR reuse policy. OCR, table extraction, hybrid retrieval,
rerank, HTTP, workspace UI, and generative Ask remain out of scope.

## Findings

| Priority | Finding | Resolution |
|---|---|---|
| Critical | PyMuPDF is dual-licensed under AGPL or commercial terms, which creates redistribution risk for downstream closed-source use. | Keep in-process PyMuPDF for D1 speed, require an ADR in the implementation PR, and document sidecar extraction as the future escape route. |
| High | The short-video path already uses a sidecar pattern, while D1 chooses an in-process PDF adapter. | Accept the asymmetry for speed. Record the PDF sidecar path as a deferred option rather than implementing it in D1. |
| High | "Ordinary text-layer PDF" needs measurable smoke coverage. | Add a D1 smoke harness requirement for 10-20 diverse PDFs with aggregate extraction results. |
| Medium | `PdfIntakeReport` should be operator-visible through Run inspection, not only ingest output. | Require `mke run get` to expose intake summary when a Run has one, without making the report a first-class queryable object in D1. |

## Public Boundary Check

- No raw review artifacts are committed.
- No local restore paths or private evidence paths are included.
- RAG-OCR is referenced only as a legacy capability source and migration policy, not as a runtime dependency.
- PyMuPDF licensing risk is treated as an architecture decision, not hidden in implementation details.

## Follow-Up

Before implementation starts, run engineering review against the updated design and implementation
plan. The implementation PR must include:

- PyMuPDF dependency ADR.
- TDD coverage for successful text-layer extraction, no-text failure, mixed PDF diagnostics, CLI
  and MCP intake summary output, and Run inspection.
- Smoke evidence for diverse PDF extraction without committing private documents.
