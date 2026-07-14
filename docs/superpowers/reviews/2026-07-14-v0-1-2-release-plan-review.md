# v0.1.2 Release Closeout Plan Review

Status: CLEARED FOR IMPLEMENTATION. Explicit authority dispatch is still required before implementation begins.

## Review Target

- Plan commit: `d7b706428f238e4ff1d3b5bf220d10e24438a41c`.
- Targeted re-review commit: `f2c7ae3ec393aad7ed40f9fbd898d587e6d58eed`.
- Approved spec: [v0.1.2 Release Closeout Design](../specs/2026-07-14-v0-1-2-release-closeout-design.md).
- Planning base: `main@16fae017ced5fe67da3fae4a01f26e9e9f1084aa`.

Targeted engineering re-review completed against the amended plan commit and accepted all five amendments. No actionable engineering finding remains. This review closure does not start implementation or authorize any external side effect.

## Review Mode

Engineering execution review. The review checks whether the approved release-closeout design is executable, fail-closed, and internally consistent. It does not expand product or architecture scope and does not authorize implementation.

## Findings

### 1. P1: Final Wheel Authority Split

**Root cause:** The original Task 6 built and tested a `dist/` wheel, ran a separate source-pack proof without candidate output, and later generated a second candidate-output wheel. This split final artifact authority across multiple unpublished wheels whose filename and version could match without byte identity.

**Accepted amendment:** Keep `UV_OFFLINE=1 uv build` as a packaging gate only. Invoke the Python 3.12/3.13 source-pack proof exactly once with `--candidate-output`, parse the exact wheel from its strict receipt, and run installed-wheel consumer smoke against that receipt-bound wheel. Final evidence reports only the candidate-output wheel filename, bytes, SHA-256, receipt SHA-256, and bound source commit.

**Failure behavior:** Treat use of the `dist/` wheel as final authority, multiple source-pack invocations, filename/version-only equivalence, or receipt/wheel SHA disagreement as a hard stop requiring a fresh complete candidate gate.

### 2. P1: Review-Closure Commit Invalidates Receipt

**Root cause:** The original plan stopped after Task 6 for review but treated that evidence as the PR-ready candidate. Recording an accepted review changes the source commit, so the existing candidate receipt can no longer bind the final reviewed commit.

**Accepted amendment:** Make Task 6 a pre-review checkpoint. Add Task 7 to resolve findings, record a clean/accepted verdict in a docs-only review-closure commit, invalidate all prior evidence, and rerun the complete gate in a fresh neutral worktree. The new receipt must bind the review-closure commit, and no tracked write may follow the rerun.

**Failure behavior:** Unresolved findings block closure. The review-closure commit or any later tracked change invalidates every prior wheel, receipt, observation, build output, and temporary worktree. Reuse of old evidence is a hard stop.

### 3. P1: Non-Executable E3-C/D/E Rebinding Description

**Root cause:** The original Task 4 named a prior pattern and generic builders without defining the exact 21-path allowlist, staged mutation boundary, supported builder contracts, dense freeze/receipt exception, semantic projection, or atomic publication behavior.

**Accepted amendment:** Enumerate all 21 maximum paths. Freeze before bytes with `git show`; use the existing atomic helper for E1-E3-B; use a call-owned untracked rebinder for E3-C/D/E that calls or mirrors the named deterministic contracts; constrain dense freeze/receipt rebinding to the verified changed-field pattern from `6c2559b3fec80b3b98608214594f9069e4b5fd2e`; stage all candidate bytes under the evidence directory; require semantic projection equality, exact allowlists, layer validation, and seven final validators before dependency-ordered replacement; record rebinder SHA-256 without committing it.

**Failure behavior:** Any semantic delta, extra path, unsupported mutation, partial publication, model/holdout rerun, validator weakening, or builder limitation is an authority hard stop. Call-owned staged files are discarded; E1-E3-B recovery uses only the existing recovery command.

### 4. P2: Blanket Audit Failure Suppression

**Root cause:** Task 2 used blanket `|| true`, which erased the distinction between an expected documentation-negative result and crashes, unknown rules, malformed output, or unrelated failures.

**Accepted amendment:** Capture the audit exit code and stdout JSON with errexit temporarily disabled, restore errexit, require exit code `1`, valid JSON, `status == "failed"`, and non-empty violations, then verify every violation is limited to Task 3's not-yet-updated current release presentation.

**Failure behavior:** Exit `0`, non-JSON output, raw traceback, unknown rule, empty violations, or any non-documentation/presentation violation is a hard stop. Blanket suppression is prohibited.

### 5. P1: Staged Validators Lack A Complete Repository View

**Root cause:** The amended Task 4 staged E3-C/D/E top-level artifacts outside the repository and required canonical validation before replacement, but it did not define a repository view containing the full staged dependency graph. Canonical builders and validators resolve repository-relative inputs through `repository_root`. In particular, `_validate_state` in `src/mke/evaluation/relevance_gate_artifact.py` resolves and hashes `development_freeze_path` and `holdout_receipt_path` under the supplied repository root. Dense and hybrid builders likewise resolve protocol, corpus, source, and dependency identities through their repository root. Supplying staged top-level artifact/protocol paths while retaining the old repository root therefore validates old dependency bytes or fails; it cannot prove the complete candidate graph.

**Accepted amendment:** After the E1-E3-B atomic helper succeeds, create a call-owned detached validation mirror rooted at `task4_start`. Overlay the exact successful E1-E3-B candidate bytes and every staged E3-C/D/E byte at canonical repository-relative paths. Require the mirror changed set and bytes to equal the complete staged candidate set within the exact 21-path allowlist. Run applicable builders, layer validators, and all seven canonical validators with every path and `repository_root`/`--repository` bound to the mirror. Only after the complete mirror is green may the exact validated downstream bytes be applied to the feature worktree. Capture call-owned pre-apply descriptors and bytes, use per-file atomic replacement in dependency order, restore every touched downstream path on apply or post-apply failure, verify exact restoration, and rerun all seven validators against the real worktree before staging.

**Failure behavior:** Missing mirror coverage, mirror/staged path or byte mismatch, old-root dependency resolution, apply failure, or post-apply validator failure blocks publication of the downstream set. Discard call-owned staging/mirror before application failures. After a touched-path failure, restore every downstream path exactly; restoration failure is a hard stop with exact dirty paths reported. Never stage or commit a partial set, and do not claim filesystem-wide multi-file atomicity.

## Confirmed Strengths

- Runtime-neutral release boundary.
- Downstream pre-release candidate boundary.
- Historical release preservation.
- Sequential commit-sensitive dependency chain.
- No residual full-pytest waiver.
- Separate publication authorization.

## Required Verification After Amendment

- Exact changed-file audit includes only the implementation plan and this review.
- Markdown fence balance is even and all fences are closed.
- Checkbox counts and incomplete status are internally consistent; no checkbox is completed.
- No stale old Task 6 ordering, blanket `|| true`, or `implementation complete` wording remains.
- No stale wording claims that top-level staged paths are canonically validated without the complete validation mirror.
- Every referenced file, function, and regression test exists.
- Public-neutral and private-path scans pass.
- `git diff --check` passes.

## Verdict

CLEARED FOR IMPLEMENTATION.

Implementation may begin only after explicit authority dispatch. This closure itself does not start implementation. Push, PR, merge, tag, GitHub Release, publication, OCR changes, and candidate-artifact worktree changes remain unauthorized.
