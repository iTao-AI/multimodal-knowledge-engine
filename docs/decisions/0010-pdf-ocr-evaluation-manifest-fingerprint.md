# ADR-0010: PDF OCR Evaluation Manifest Fingerprint

- Status: Proposed / pending implementation
- Date: 2026-07-14

## Context

The Phase 0 OCR runner must publish disposable Evidence through the current Run and Publication
contracts while preserving the complete evaluation identity. Existing PDF fingerprints identify
the built-in and PyMuPDF text-layer extractors; using either value for OCR-routed output would hide
the router, render, provider, model, package, wheel, and normalization authority that produced the
candidate Evidence.

## Proposed Decision

Introduce an evaluation-only fingerprint with the exact form
`pdf-ocr-eval-v1:<64 lowercase hex SHA-256>`. Its digest is computed from canonical JSON with schema
`mke.pdf_ocr_extractor_identity.v1` and binds protocol and fixture identities, router policy and
thresholds, render DPI and page-image digests, provider and profile, model receipt and tree,
package receipt and installed package set, MKE wheel, and normalization identity.

OCR evaluation Publications use exactly `pdf_ocr_extraction` and `candidate_evidence` stages. A
text-layer-only Publication continues to use `pymupdf-text-v1` and the existing PDF stages; any
OCR-routed page makes the evaluation Publication use the OCR fingerprint and OCR stages.

The validator will accept only the exact version, lowercase 64-hex digest, OCR stages, and page
locators. Prefix-only, wrong-length, uppercase, unknown-version, and fingerprint/stage mismatch
forms fail closed. The scorecard will retain the full structured identity, and the runner will
verify its canonical digest against the compact `RunManifest` fingerprint before activation.

## Scope And Consequences

This proposal is limited to the Phase 0 evaluation runner. It adds no public CLI or MCP input,
production OCR flag, runtime default, SQLite migration, dependency, or production OCR authority.
Existing PDF and video fingerprints and behavior remain compatible. Implementation and acceptance
require Task 5A TDD evidence; this ADR does not claim that the contract is implemented.
