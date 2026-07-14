# PDF OCR Phase 0 Resumption Plan Review

Date: 2026-07-14

Status: PENDING TARGETED AUTHORITY REVIEW. Tasks 4R, 5A, 5B, 5C, and 6 have not started.

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
