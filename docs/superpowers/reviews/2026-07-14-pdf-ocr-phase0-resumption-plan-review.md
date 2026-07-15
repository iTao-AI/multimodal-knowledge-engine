# PDF OCR Phase 0 Resumption Plan Review

Date: 2026-07-14

Status: targeted authority re-review accepted / CLEARED FOR TASK 4R-A. Task 4R-B remains gated on
Task 4R-A implementation plus separate authority review and dispatch. Tasks 4R, 5A, 5B, 5C, and 6
have not started.

## Main Reconciliation

The OCR branch reconciles `main` at `a080878a68ac652595f55f50c231f9db9629d55c` through merge
commit `804b9205c35b657ab3aba51faf4cdc40ab0e4057`. A merge commit is required instead of rebase or
squash because the accepted Task 4 review records implementation commits
`040cb6cea2439f5f9d46b09862b17fa1fee59e39` and
`936f5b7a883b432e772613bdd3f88354beaf27f9`; preserving those commits keeps reviewed provenance
auditable.

## Resumption Gates

- The retained package and provider-startup receipts bind an MKE 0.1.1 wheel. After reconciliation
  with MKE 0.1.2, they are historical evidence and must be regenerated offline from the merged
  committed tree before scorecard work.
- The model receipt may remain the same model provenance only after a fresh descriptor-bound rehash
  confirms unchanged file, component, tree, and aggregate identities.
- The evaluation-only `pdf-ocr-eval-v1:<sha256>` manifest contract must bind the complete canonical
  structured identity without impersonating an existing text-layer fingerprint.
- Retrieval provenance receives one current-main canonical refresh only after Task 5A and Task 5B
  code stabilizes. The refresh must cover the complete E1 through E3-E dependency chain and prove
  normalized semantic equality.

No package or model download, provider execution, artifact refresh, scorecard generation,
production OCR change, or Task 6 work is part of this review record.

## Targeted Review Findings And Resolution

- The extractor identity was open-ended and its canonical bytes were undefined. The amended
  contract now freezes exact top-level and nested keys, current routing-policy fields, rational
  encoding, deterministic list ordering, strict types and uniqueness, compact `json.dumps`
  arguments, no trailing newline, and fail-closed mutation requirements.
- The prior wording blurred compact domain validation with structured evaluation authority. Task
  5A now validates only fingerprint syntax, exact stages, and page locators. Task 5B is the sole
  current structured identity producer and validates digest equality before candidate persistence.
  SQLite does not validate that payload, public application inputs do not expose it, and the future
  production OCR report gate remains unimplemented work in Tasks 7-9.
- Task 5C was open-ended and could repeat an invalid E2 observation order. It now reuses the
  current-main release-closeout Task 4 closure: exact 21-path maximum allowlist, hidden refreshed
  E2 protocol, recoverable five-target transaction, detached downstream validation mirror, exact
  backups and restoration, complete regression and seven-validator gates, and normalized semantic
  equality. `artifact_refresh.py` cannot be extended in this task.
- Task 4R did not precisely bind its execution source or commands. It now freezes `task4r_start` at
  the review-cleared resumption commit containing merge `804b9205c35b657ab3aba51faf4cdc40ab0e4057`,
  builds the exact committed HEAD, records rather than overclaims commit provenance, names the two
  writable receipts and byte-identical model receipt, freezes operator and call-owned inputs, uses
  only offline prepared evidence, and stages exactly the two regenerated receipt files.

These resolutions do not clear Task 4R. Targeted authority re-review remains required before any
Task 4R, 5A, 5B, 5C, or 6 execution.

## Second Targeted Review Findings And Resolution

This is the second review of the same Task 4R executability boundary. It identified four remaining
gaps:

- The compatibility controller and its tests still used fixed 0.1.1 wheel filename and runtime
  assertions, so the planned 0.1.2 refresh could not execute. Task 4R is now split. Task 4R-A uses
  TDD to introduce strict safe-version wheel parsing, current-generation repository-version
  matching, historical receipt self-consistency, cross-candidate MKE identity, passed-cell version,
  and provider-runtime authority. It commits only the evaluation script and tests before evidence
  work begins.
- Prepared mode validates an already matching MKE wheel and does not copy or replace retained
  evidence. Task 4R-A now requires a descriptor-bound copy/rebind helper that preserves and proves
  the retained source, copies the exact third-party inventory, and replaces only the MKE wheel in a
  call-owned destination. All source drift, links, unexpected entries, collisions, and missing or
  duplicate MKE wheels fail closed.
- `xcrun --find swift` resolves the Swift driver rather than the Apple Vision child. Task 4R-B now
  typechecks and compiles `scripts/pdf_ocr_apple_vision.swift` into a call-owned executable and
  passes only that executable to provider startup.
- The prior cleanup and diff commands did not match their filesystem and Git semantics. Task 4R-B
  now uses a trap limited to its two `mktemp` roots, records wheel authority before deleting those
  roots, verifies their removal, audits uncommitted changes with `git diff --name-only` and
  `git status --short`, and stages only the two regenerated receipts. It freezes a new clean
  `task4r_evidence_start` after Task 4R-A and reports the plan start, harness commit, and evidence
  start separately.

Task 5A now has exact RED/GREEN commands covering domain, PDF/video application, CLI, and MCP tests;
only new OCR domain cases may be RED, while existing behavior and no-new-input assertions remain
green. These resolutions still do not clear Task 4R-A or Task 4R-B. Status remains PENDING TARGETED
AUTHORITY RE-REVIEW, and Tasks 4R, 5A, 5B, 5C, and 6 remain unstarted.

## Third Targeted Review Finding And Resolution

The third review found one remaining Task 4R-B executability conflict. The committed compatibility
suite freezes `benchmarks/ocr/candidate-environments.json` at exact SHA-256
`91c782fb147fbb1f59f2c2f447f79d8c8c82188860b2b6afeb4455c92630fcbb`, while Task 4R-B must
replace that receipt with canonical 0.1.2 evidence. Running the complete suite without updating the
freeze would necessarily fail, but changing the test was absent from the approved file scope.

The plan now preserves the exact freeze unchanged throughout Task 4R-A. Task 4R-B generates both
receipts first, computes the canonical package receipt SHA-256, and mechanically updates only that
frozen test literal before running the complete compatibility and focused suites. Its exact staged
set is the two receipts plus `tests/scripts/test_pdf_ocr_candidate_compatibility.py`; review must
prove the test diff contains only the new frozen SHA. `model-artifacts.json` remains byte-identical,
and no Task 4R-B controller behavior change is authorized. The receipts bind wheel, package, model,
and runtime bytes, not `source_commit`; the post-generation freeze is not a source-commit binding.

## Accepted Targeted Re-review Evidence

Targeted authority re-review accepted implementation-plan commit
`3673c8373da6973b0961f789204be14adce3d4dd` with no findings. The reviewed range was
`dccf5bb7eb4d1ff7527e1ee5801554576c4dfcd1..3673c8373da6973b0961f789204be14adce3d4dd`.
Its exact diff changed the four approved documentation files with 79 insertions and 7 deletions.

The accepted plan preserves the exact historical committed-receipt SHA gate through Task 4R-A.
For Task 4R-B it freezes the executable order: generate canonical package and startup receipts,
calculate the new package receipt SHA-256, mechanically update only the frozen SHA literal, run the
complete suite, then commit exactly the two receipts plus the test file. The reviewed commit changed
no controller, test, receipt, artifact, dependency, or workflow bytes. `git diff --check`, exact
changed-file audit, and clean-worktree verification passed.

This acceptance clears only Task 4R-A. It does not claim implementation, matrix or provider
execution, receipt refresh, Task 4R-B authority, or production OCR. Every Task 4R, 5A, 5B, 5C, and
6 checkbox remains uncompleted. Task 4R-B requires the completed Task 4R-A implementation and its
separate authority review and dispatch.
