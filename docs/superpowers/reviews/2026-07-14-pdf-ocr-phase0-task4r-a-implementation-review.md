# PDF OCR Phase 0 Task 4R-A Implementation Review

Date: 2026-07-14

Status: targeted authority re-review accepted / CLEARED FOR TASK 4R-B. Task 4R-A is complete and
accepted at implementation commit `3b029a47c69f32d63e9cae688196e205d96f8af7`. Task 4R-B requires
a separate dispatch and has not started.

## Scope

The reviewed range is
`85b09a7e4fe1da165578ad826f4c707a55ca0840..3b029a47c69f32d63e9cae688196e205d96f8af7`.
Its exact diff changed only:

- `scripts/pdf_ocr_candidate_compatibility.py`
- `tests/scripts/test_pdf_ocr_candidate_compatibility.py`

The script changed by 33 insertions and 20 deletions; its test changed by 111 insertions and no
deletions. The aggregate diff contains 144 insertions and 20 deletions and is limited to the
model-free candidate-wheel authority and call-owned prepared-wheelhouse rebind harness.

## Findings And Resolution

- A destination nested under retained evidence, including a destination reached through a
  symlinked parent, could be created and removed before failure while still changing retained
  directory metadata. The helper now resolves the existing destination parent before any write,
  rejects source/destination overlap, and proves retained entries, regular-file bytes and digests,
  and observable directory metadata remain unchanged.
- A filename beginning with the canonical MKE project prefix but carrying an invalid or alternate
  wheel tag could be treated as a third-party wheel. Receipt authority, prepared inventory, and the
  rebind copy path now share a fail-closed prefix-aware classifier: an MKE-like filename must pass
  the strict project wheel parser or be rejected.

Targeted authority re-review reported no additional findings. Historical 0.1.1 receipt validation,
current 0.1.2 generation authority, exact third-party wheel copying, and the stable failure contract
remain intact.

## Accepted Evidence

Independent verification recorded:

- Focused adversarial regressions: `4 passed, 98 deselected`.
- Complete candidate compatibility suite: `102 passed, 5 warnings`.
- Protocol, router, and provider suites: `86 passed, 5 warnings`.
- Ruff passed.
- Pyright passed with `0 errors`.
- `git diff --check` passed.
- The committed receipt freeze remains exactly
  `91c782fb147fbb1f59f2c2f447f79d8c8c82188860b2b6afeb4455c92630fcbb`.

## Accepted Boundary

This acceptance proves only the model-free harness and controller authority required by Task 4R-A.
It does not prove a real retained-wheelhouse copy/rebind, the offline 16-cell matrix, real provider
startup, Apple Vision execution, or receipt refresh. Those operations belong to the unstarted Task
4R-B and require a separate dispatch.

Task 4R as a whole is not complete. This review does not select an OCR provider, establish a Phase 0
viability result, change production PDF intake, or authorize production OCR.
