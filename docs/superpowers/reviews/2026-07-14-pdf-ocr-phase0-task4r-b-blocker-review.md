# PDF OCR Phase 0 Task 4R-B Blocker Review

Date: 2026-07-14

Status: amendment accepted / cleared to retry Task 4R-B. No refreshed evidence is accepted or
committed by this review.

## Scope

This review covers the model-free synthetic provider-startup controller fixture that blocked the
first Task 4R-B evidence attempt. It does not change the compatibility controller, receipt schema,
provider adapters, production runtime, dependencies, or any package or model artifact.

## Root Cause

The first evidence attempt generated a self-consistent MKE 0.1.2 package receipt and completed the
offline matrix and cache-only startup path. The complete compatibility suite then failed before its
targeted controller branches because the fixture read package versions from that receipt while it
still constructed a fixed 0.1.1 wheel and reported a fixed 0.1.1 runtime version. The strict
self-consistency validator correctly rejected the mixed authority. This was a synthetic fixture
gap, not a provider, matrix, receipt-schema, or controller defect.

The failed operation restored its tracked files from call-owned byte-identical backups and removed
its call-owned roots. Its temporary wheel and receipt identities are diagnostic evidence only and
must not be reused.

## Accepted Amendment

- The fixture derives the exact MKE wheel filename and version from the input receipt's strict MKE
  authority.
- The selected PaddleOCR-VL Python 3.13 base cell remains the authority for the expected installed
  package set.
- The synthetic distribution, fake installed runtime, and selected cell remain mutually
  self-consistent.
- Explicit historical 0.1.1 and current 0.1.2 receipt variants exercise the same controller path.
- Existing invalid and drift cases continue to reach their intended fail-closed controller
  boundaries.
- No controller or validator is weakened or modified.

## Retry Gate

After the test-and-documentation amendment is committed with a clean worktree, Task 4R-B must
freeze that exact commit as a new `task4r_evidence_start`. It must rebuild the wheel and regenerate
the package and provider receipts from fresh call-owned roots using only retained offline evidence.
The later evidence commit may change only the two canonical receipts and the committed package
receipt's frozen SHA literal. Task 4R-B Steps 5-10 remain incomplete until that retry and its full
verification finish. Task 5A and later work remain outside this review.
