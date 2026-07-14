# PDF OCR Phase 0 Task 5A Implementation Review

Date: 2026-07-14

Status: ACCEPTED / CLEARED FOR TASK 5B at reviewed HEAD
`fecb732c5950855897219609b9ea0f63e7d75fa6`.

## Scope

This review covers the evaluation-only compact `RunManifest` fingerprint contract implemented in
`1953053c801b37ab6a43c9872f0108c7b49c98a3` and its test-authority repair in
`fecb732c5950855897219609b9ea0f63e7d75fa6`. The reviewed range is
`bc0a42ea60eefd92fa37e91aa78db96a0a0696a4..fecb732c5950855897219609b9ea0f63e7d75fa6`.

The implementation recognizes only `pdf-ocr-eval-v1:<64 lowercase hex>`, requires exactly
`pdf_ocr_extraction` and `candidate_evidence`, rejects duplicate stages, and requires positive page
locators. It rejects invalid versions, digest lengths or case, fingerprint/stage mismatches, and
invalid locator forms. Existing builtin and PyMuPDF PDF fingerprints and recognized video
fingerprints remain compatible. Normal PDF ingest continues to emit `pymupdf-text-v1`.

## Finding And Resolution

The initial targeted review found one P2 test-authority gap. The MCP regression case-folded the
schema but searched for `runmanifest`, which would not detect a conventional `run_manifest`
property. The CLI regression rejected `--extractor-fingerprint` but did not exercise
`--run-manifest`. Current production behavior was already closed, so this was a coverage defect
rather than a public-contract defect.

The repair binds the MCP `ingest_file` schema property set exactly to `{"path"}`. It therefore
fails on `run_manifest`, `manifest`, `extractor_fingerprint`, or any other additional request-time
authority property. The CLI test now requires both `--extractor-fingerprint` and `--run-manifest`
to fail with usage error code 2 and name the rejected option. The repair changed exactly those two
interface tests; source, ADR, plan, dependencies, receipts, artifacts, workflows, and Task 5B
surfaces remained byte-identical during the repair.

## Verdict

The targeted authority re-review found no remaining findings. Task 5A is accepted. ADR-0010 is
Accepted, and Task 5B is cleared only for a later independent dispatch.

## Fresh Verification

- Focused domain, application, CLI, and MCP suite: `122 passed, 5 warnings`.
- Ruff: passed.
- Pyright: `0 errors, 0 warnings`.
- `git diff --check`: passed.
- Targeted repair changed exactly two interface tests.

## Claim Boundary

Task 5A validates only compact fingerprint syntax, exact stage compatibility, duplicate stages,
and page locators. Structured extractor-identity payload validation and digest/producer authority
remain Task 5B work. This acceptance does not establish OCR quality, provider selection,
production OCR capability, runtime promotion, or release authority.
