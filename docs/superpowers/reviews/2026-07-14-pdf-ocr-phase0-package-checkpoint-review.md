# PDF OCR Phase 0 Package Compatibility Checkpoint Review

Date: 2026-07-14

Status: targeted re-review completed and accepted at implementation HEAD
`ba86e74f3f67fe0c153caf60133aebe74c27568b`. The package-only checkpoint is cleared; model
acquisition and real-provider startup remain outside this accepted scope.

## Scope

This review covers Task 4 Steps 1-3 only: the ordinary-pip Python 3.12/3.13 candidate matrix,
immutable distribution receipt, bounded subprocess behavior, offline replay identity,
valid-negative resolver evidence, and their committed tests. It does not cover model artifacts,
real OCR inference, PaddleOCR-VL vendor artifact compatibility, the Phase 0 scorecard, production
PDF intake, or runtime promotion.

## Findings And Resolution

- Bounded commands now clean the captured POSIX process group after every direct-parent exit,
  including successful exits, while retaining timeout, output-bound, parent-wait, and reader-thread
  cleanup behavior.
- The committed candidate receipt is bound to canonical bytes, its frozen SHA-256, non-empty
  candidate inventories, exact aggregate distribution bytes, and the unique MKE wheel identity in
  each candidate inventory.
- Online candidate wheelhouses seed the exact built MKE wheel before resolution. A candidate whose
  required distributions are unavailable for both interpreters can therefore emit a valid MKE-only
  inventory and eight `resolver_failed` cells without fabricating provider compatibility.
- Prepared wheelhouses are read-only evidence. Missing or drifted MKE identity fails closed with
  `prepared_wheelhouses_invalid`; the controller does not supplement or rewrite operator-provided
  inventory.
- Controller-path regressions call `run_package_matrix()` directly. Mutation evidence showed that
  removing the production binding caused all three new cases to fail; restoring the binding
  returned them to green.

## Accepted Evidence

The previously committed package receipt remains canonical and records 16 successful cells across
Python 3.12.13 and 3.13.12, both candidates, and all four MKE extras surfaces. It remains package
compatibility evidence only.

Fresh targeted re-review at `ba86e74f3f67fe0c153caf60133aebe74c27568b` recorded:

- Three controller-path regressions passed.
- The complete candidate compatibility suite passed: `26 passed`.
- The model-free protocol, router, and provider suites passed: `72 passed, 5 warnings`.
- Ruff passed.
- Pyright passed with `0 errors`.
- The committed receipt SHA-256 remained
  `df04fff10a7f170b7dbf51ccafba3e189d15f64719a4e172c165bb0a15ee360e`.
- The incremental diff changed only the compatibility test file; dependency, production,
  model-file, and public-neutral audits passed.

## Remaining Authority Gate

No model was downloaded and no real provider was constructed during this checkpoint. PaddleOCR-VL
`save_to_json` and `save_to_markdown` inventory/schema compatibility remains unobserved. Task 4
Steps 4-6 require separate model-acquisition authority, cache-only real-provider startup, and final
compatibility evidence before Task 5 can begin.
