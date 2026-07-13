# PDF OCR Phase 0 Tasks 1-3 Implementation Review

Date: 2026-07-13

Status: implementation review findings are remediated locally; targeted re-review is pending.
Phase 0 remains hard-stopped before package or model acquisition.

## Scope

This resolution covers only the evaluation corpus protocol, four-state router and bounded renderer,
strict provider child boundary, lazy candidate adapters, Apple Vision baseline source, and
model-free tests from Tasks 1-3. It does not add production PDF OCR, a public OCR contract, provider
dependencies, model artifacts, retrieval changes, or runtime promotion.

## Review Resolution

- Inspection now returns a narrow evaluation result that binds `PageDecision` values to the source
  byte count and SHA-256. Rendering re-reads one identified snapshot, verifies that strong identity
  before creating output, and opens the verified bytes rather than independently trusting the path.
- Provider children receive an explicit environment with private call-owned HOME, temporary,
  configuration, and cache roots. Arbitrary parent secrets, proxy configuration, and user settings
  are not inherited.
- The provider runner captures the POSIX process-group identity at spawn and cleans remaining group
  members after every direct-parent exit, including exit zero, while retaining bounded pipe reads,
  parent wait, timeout handling, and controller registration rejection.
- The PaddleOCR-VL adapter accepts exactly one regular JSON file and one regular Markdown file. It
  opens each artifact once with no-follow where available, binds inventory and reads through
  regular-file `lstat`/`fstat` identity checks, and applies per-file and aggregate limits to actual
  descriptor bytes with bounded chunked reads. It validates a strict provisional prose-only
  envelope, rejects unsupported layout structures, and removes its private artifact directory on
  success and failure.
- Parent validation and all three candidate serializers use one NFC, newline, horizontal-whitespace,
  and empty-line normalization contract. Model-free regressions cover repeated whitespace, CR/LF,
  decomposed Unicode, and multiple lines.

## Verification Boundary

Focused Tasks 1-3 protocol, router, and provider tests pass without provider packages or models.
Ruff and Pyright pass for the affected evaluation modules and tests. Swift typechecking passes with
the existing `usesCPUOnly` deprecation warning. No real-provider, ordinary-pip compatibility,
Publication/Search/Ask, scorecard, or full-repository result is claimed here.

## Remaining Task 4 Check

The strict provisional PaddleOCR-VL JSON/Markdown envelope has not been compared with artifacts from
the pinned package because package and model acquisition is outside the current authority. Task 4
must record the exact regular-file inventory and schema before any compatibility adjustment. A
schema mismatch fails closed; it is not evidence to weaken the prose-only boundary.
