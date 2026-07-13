# Consumer Source-Pack Proof Task 7 Blocker Review

Review target: Task 7 CI placement and final verification closure.

Review status: targeted blocker analysis and dedicated-workflow resolution completed and verified
at commit `44fa5b3571173b09400c76f3b326633c63d08f31`.

## Declared Dense Source Identity

The initial Task 7 implementation added the consumer proof job to `.github/workflows/ci.yml`.
That file is not a neutral CI-only surface for this repository: `dense_source_identity()` includes
its literal path, and committed dense/hybrid artifacts freeze the resulting file identity. The
working-tree edit therefore caused the existing artifact validators to report source-identity
drift even though no evaluation implementation, protocol, fixture, or artifact had changed.

Representative dense/hybrid tests pass at the planning base with the committed primary CI bytes.
After restoring `.github/workflows/ci.yml` byte-for-byte, the same representative tests are the
required regression gate in the feature worktree. No dense artifact refresh or evaluation change
is authorized. The feature-worktree regression completed with 116 passing dense/hybrid tests and
no source-identity failure.

## Dedicated Workflow Resolution

Task 7 now owns `.github/workflows/consumer-source-pack-proof.yml`. It preserves the approved
single-job proof semantics while avoiding the declared dense source-identity surface:

- `pull_request` and `push` to `main` triggers, `contents: read`, bounded concurrency, and a bounded
  job timeout;
- existing pinned checkout, uv, and setup-python action revisions;
- explicit Python 3.12 and 3.13 setup-step output paths;
- one online locked provisioning step that prepares controller and per-interpreter caches; and
- one later `UV_OFFLINE=1` controller invocation that builds and reuses one wheel across both
  interpreters without a matrix or online retry.

Focused workflow tests read only the dedicated workflow and separately require
`.github/workflows/ci.yml` to remain byte-identical to `HEAD`.

## Unchanged Path-Sensitive Release Test

The current feature worktree name contains a token used as a failure-stage selector by one existing
release consumer-smoke parametrization. That test therefore observes `venv_failed` before reaching
its expected `proof_failed` stage. The exact parametrized case passes from the planning-base main
checkout and fails from this named feature worktree without any change to its test or implementation
surface.

This was classified as an unchanged path-sensitive test condition, not a consumer proof defect.
The named feature-worktree run retained the single classified residual and no dense/hybrid
failure. After commit `44fa5b3571173b09400c76f3b326633c63d08f31`, the required neutral
detached-worktree command `UV_OFFLINE=1 uv run pytest -q` completed with
`1584 passed, 5 skipped, 5 warnings in 117.75s` and exit code `0`. The neutral pass closes the
final gate without changing the historical diagnosis.

## Exact Marker Allowlist

The changed-text audit remains fail-closed but recognizes three exact contract-test occurrences:

- the public safe-cause template-token sentence in the standalone client;
- the structurally identical sentence in the consumer-owned schema expectation fixture; and
- the standalone independence test's exact negative assertion against local home-directory paths.

The audit compares complete stripped lines at the expected files. It continues to reject any other
incomplete marker, actual private absolute path, or private workflow term. The allowlist does not
delete, weaken, or generalize the public error contract or its negative path assertion.

## Verification And Authority Boundaries

This targeted resolution may create the dedicated workflow, update its focused shape tests, update
the approved implementation plan, and persist this review. It may not modify producer runtime,
canonical schemas, evaluation behavior or artifacts, frozen source bytes, release consumer-smoke
behavior, versioning, publication, or deployment surfaces.

Before handoff, verification must include workflow RED/GREEN evidence, primary CI byte identity,
the complete focused consumer suite, representative dense/hybrid regressions, Ruff, Pyright, build,
all approved product/provenance proofs, release presentation audit, exact dual-interpreter offline
JSON, forbidden-surface and changed-text audits, diff check, and one current-worktree full pytest
run. Any residual beyond the single classified release-smoke parametrization is a stop condition.

Commit, final detached-worktree verification, push, PR, merge, release, publication, and deployment
remain outside this execution handoff unless separately authorized.
