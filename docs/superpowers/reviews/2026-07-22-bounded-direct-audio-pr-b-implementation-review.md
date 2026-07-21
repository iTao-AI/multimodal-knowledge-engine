# Bounded Direct-Audio PR B Implementation Review

## Status

**ACCEPTED / CLEARED FOR PR B PR HANDOFF**

This record covers the bounded internal PR B implementation for Tasks 2 through 4. It does not
start PR C, activate direct audio through a public runtime, or mark any Task 5 through Task 10 step
complete.

## Reviewed Candidate And Findings

The authoritative actual-diff review of candidate
`9227995aa56cc44b5537d1f60633b165c4986a83` requested changes for:

1. failed snapshot creation cleanup that could unlink an inode-distinct staging or sealed path
   replacement;
2. final root removal that could remove a replacement directory after the owned-root identity
   check while leaking the displaced call-owned root; and
3. malformed `container` or `audio_codec` values that could leak an untyped `TypeError` before the
   closed parser rejected the payload.

The review also required the Task 3 ordering statement to reflect the current uncomposed boundary:
PR B proves an internal snapshot and cleanup foundation but has no Source/Run owner path. Task 5 /
PR C owns verification that snapshot creation precedes Source/Run creation.

## Repair Candidate

Commit `1c954b89b745a53bf6fc4bfd2e5aaa0e058b7bb5` binds failed-creation file cleanup to the inode
captured when the staging descriptor is opened, keeps the owned-root descriptor open through file
and root cleanup, and removes only the captured root identity. Darwin uses the existing
`/.vol/<dev>/<ino>` authority; the non-Darwin path resolves the exact root identity beneath a
no-follow parent descriptor. Public paths remain drift detectors rather than deletion authority.

The closed parser now requires exact strings before profile membership. Regressions cover list,
object, null, and boolean values for both media identity fields.

Controlled tests against the prior candidate reported `8 failed, 4 passed`. The same targeted set
passed on the repair, and the combined inspection/parser suite reported `81 passed`. Five cleanup
race repetitions and the Tasks 2 through 4 focused and adjacent video suites also passed.

## Local Verification Closure

Commit `5f6f2e8651fe5c001997288c552e82055c2975f0` records the separate terminal retrieval identity
closure. The validator-proven dependency-closed set contains 16 paths within the approved 21-path
maximum. Staged, detached-mirror, and worktree bytes agreed, all seven canonical validators passed,
and normalized semantic projections remained equal from E1 through E3-E. Observations, ordered
results, metrics, thresholds, gates, diagnostics, selected candidate or profile, status, and verdict
did not change.

Verification bound to that implementation and identity state reported:

- `232 passed` for the combined Tasks 2 through 4 focused and adjacent video suite;
- five cleanup race repetitions with `12 passed` per repetition;
- `191 passed` for the retrieval artifact regression suite;
- `2720 passed, 4 skipped` for the complete repository suite;
- clean Ruff and Pyright results;
- successful offline build, eight-case product proof, verified demo, byte-identity, scope, secret,
  and public-neutral checks.

## Targeted Portability Re-Review And Acceptance

Targeted authority review found one tests-only portability issue after the cleanup repair: the
final-root replacement regression forced both `darwin` and `linux` through one parametrized test.
On `ubuntu-latest`, the synthetic Darwin case entered the production `/.vol/<dev>/<ino>` branch
without the real macOS inode-addressed namespace, so the regression could not prove removal of the
displaced call-owned root on that host.

Commit `1fb1cd88a393207684d0cbf3072a116e4b1f6dfc` contains the exact tests-only correction. The
Darwin regression is collection-gated by the host's actual `sys.platform`; the independent
non-Darwin regression explicitly selects the generic Linux branch. Both retain the original
assertions that cleanup returns `snapshot_cleanup_failed`, preserves the operator-owned replacement
identity and directory, and removes the displaced call-owned root. The commit changes only
`tests/adapters/test_audio_inspection.py` with 23 insertions and 4 deletions. It does not change
production, contract, evaluation, dependency, workflow, or public-surface behavior.

Independent verification bound to reviewed repair HEAD
`1fb1cd88a393207684d0cbf3072a116e4b1f6dfc` reported:

- `81 passed` with five existing SWIG warnings for `tests/adapters/test_audio_inspection.py` and
  `tests/domain/test_audio_contracts.py`;
- clean Ruff results for the changed file;
- Pyright with zero errors and zero warnings for the changed file;
- clean `git diff --check`, exact one-file repair scope, and a clean worktree; and
- acceptance of the execution evidence `2720 passed, 4 skipped, 5 warnings` for the complete suite.

Targeted authority re-review found no remaining actionable finding. Tasks 2 through 4 are locally
accepted and this branch is cleared for PR B PR handoff. This does not mark PR B merged, satisfy the
PR C entry gate, or authorize Task 5 through Task 10.

This acceptance covers only the uncomposed internal PR B foundation. It does not state or imply
public runtime, CLI, or MCP activation; real ASR or model acquisition; a sandbox or hostile-media
containment guarantee; external-binary redistribution authority; a released capability; or release
or deployment.
