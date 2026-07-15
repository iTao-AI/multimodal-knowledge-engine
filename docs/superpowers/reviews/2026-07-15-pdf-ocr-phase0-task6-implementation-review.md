# PDF OCR Phase 0 Task 6 Implementation Review

Date: 2026-07-15

Status: ACCEPTED / CLEARED FOR SEPARATE PRODUCTION PLANNING

## Scope

This review covers Task 6 at implementation HEAD
`ff85c1a59690ce108f24d325f943711c4abc1987`: installed-wheel scorecard validation, disposable
Publication replay, official MCP SDK Search/Ask calls, exact portable page EvidenceRef validation,
network denial, stable output, and call-owned cleanup. It does not cover a new OCR provider run,
production OCR, public inputs, runtime promotion, release, or deployment.

## Authority Finding And Resolution

The Task 4R package/startup receipts and Task 5B scorecard extractor identities bind MKE wheel
SHA-256 `6f499710dce8f4ac3e23ac0513c0020a8367f83b38755d43f6ffc4fb49056218`. Task 6 instead built and
reused MKE wheel SHA-256 `e17ed9ce1f374eb10a5e006f56d34c50bacc35f497d32654faf40459fa0316b1`.
Its internal candidate imports installed-wheel `publish_and_verify` but supplies recognized text
from the closed protocol expected truth; it does not invoke `run_phase0_scorecard` or execute an OCR
provider or model.

The evidence claim is therefore composed, not a same-wheel end-to-end OCR claim:

- `6f499710dce8f4ac3e23ac0513c0020a8367f83b38755d43f6ffc4fb49056218` is the reviewed real OCR
  package/startup and scorecard authority.
- `e17ed9ce1f374eb10a5e006f56d34c50bacc35f497d32654faf40459fa0316b1` is the installed consumer,
  Publication replay, Search/Ask, and EvidenceRef authority.

This distinction is now explicit in the design, plan, and decision record. A final installed-wheel
real OCR ingest remains a production/public-surface gate rather than a Phase 0 rerun blocker.

## Accepted Decision

Phase 0 is accepted as `GO` for a separate production plan. The sole selected planning baseline is
`ppocrv6-medium-cpu-spike-v1` with profile `phase0-200dpi-plain-text-v1`. Current numeric ceilings
are provisional regression and planning budgets for the closed synthetic protocol, not production
SLAs. Representative-corpus evidence and final installed-wheel real OCR ingest remain required
before exposing a public capability.

## Fresh Verification

- Consumer tests passed: `19 passed, 5 warnings`.
- Ruff passed.
- Focused Pyright passed with `0 errors`.
- `git diff --check` passed.
- The package/scorecard wheel digest differs from the Task 6 consumer wheel digest as recorded
  above.
- The internal candidate uses installed `publish_and_verify` with protocol expected truth and does
  not call `run_phase0_scorecard`.

## Strict Pyright Closure

A post-acceptance PR-gate review found that bare `uv run pyright` passed on main but reported 368
errors on the Phase 0 branch. The errors were confined to the four OCR test files added or modified
by this work; the earlier description of them as pre-existing baseline failures was incorrect. The
local closure commit `test(ocr): close strict typing gate` adds typed JSON narrowing and monkeypatch
helpers, exact private-test-seam suppressions, and fixes for real call, index, and narrowing issues
without changing test assertions or evidence bytes. Fresh bare Pyright now reports `0 errors, 0
warnings, 0 informations`; Ruff passed, the four-file OCR suite passed with `292 passed, 5
warnings`, and full pytest passed with `2006 passed, 5 skipped, 5 warnings`.

## Claim Boundary

This acceptance clears only production planning. It does not authorize production OCR, a public
OCR flag, runtime promotion, an approved production SLA, release, or deployment.
