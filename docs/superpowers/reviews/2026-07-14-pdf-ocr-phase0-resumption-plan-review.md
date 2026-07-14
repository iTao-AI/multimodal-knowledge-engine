# PDF OCR Phase 0 Resumption Plan Review

Date: 2026-07-14

Status: PENDING TARGETED AUTHORITY RE-REVIEW. Tasks 4R, 5A, 5B, 5C, and 6 have not started.

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
