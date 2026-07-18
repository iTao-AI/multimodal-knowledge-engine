# Bounded Direct Audio Intake Plan Review

## Scope

This record captures one full structured review of the bounded direct-audio design and
implementation plan. The reviewed committed revision is
`c150c3c3c49990265cb756ef45a3669cd683714c`, reconciled against live `main` at
`23aaa682b69d019ecc4e73ab8d9239152b9770cf`.

The review covered product boundaries, implementation architecture, engineering failure modes,
developer experience, verification layering, and review/terminal-proof sequencing. It did not
review implementation code because implementation has not started.

A later actual-diff authority review of
`bf4fc6107ca3afeb7f84da773a2ca0f2ef72d062` found three P1 executability gaps on the shared PR A
offline-input authority. This record now includes the bounded targeted repair and targeted
re-review. The CEO, Engineering, Developer Experience, and full Autoplan phases were not rerun.

## Authority Amendment Notice

This historical full-plan review remains authoritative for all unrelated product, architecture,
staging, compatibility, and verification findings. Its resource-enforcement, target-executable
preflight, and external-binary redistribution-clearance surfaces are amended and superseded by
`docs/superpowers/reviews/2026-07-18-bounded-direct-audio-intake-authority-amendment.md`.

The superseding record defines Darwin arm64 `ri_phys_footprint` polling supervision with
`hard_kernel_enforced=false`, a fixed bounded stdlib target-executable identity probe, and the
separation between local optional-dependency use and unperformed/unclaimed external-binary
redistribution. No other finding or verdict in this review is superseded.

| Historical authority conclusion | Status |
|---|---|
| Aggregate or descendant-sampled native-child resource ceiling | `Superseded` by stable leader identity and leader-only non-aggregate `ri_phys_footprint`; ordinary cooperative descendants remain process-group termination/wait/cleanup scope only |
| Generic or non-executing target-interpreter preflight | `Superseded` by one fixed bounded stdlib identity probe under a sanitized environment with descriptor identity before/after |
| Transitive external-binary redistribution clearance as a local-use feasibility hard stop | `Superseded` by the `local_runtime_only` classification and exact `external_binary_redistribution=not_performed` / `redistribution_authority=not_claimed` literals; committed fixtures remain `repository_distributed` and a hard authority gate |

## Verdict

`CLEARED FOR STAGED IMPLEMENTATION; PR A REQUIRES SEPARATE DISPATCH`

- CEO/product review: clean after accepted bounded-scope, proof, and license-authority amendments.
- Design review: skipped because the plan adds no graphical or browser UI.
- Engineering review: clean after accepted path, identity, resource, admission, and input-lineage
  amendments.
- Developer-experience review: clean after accepted onboarding, example, recovery, migration, and
  review-sequencing amendments.
- Targeted PR A offline-input re-review: wheel compatibility and nested-pip isolation are closed;
  acquisition-preflight execution authority is reconciled under the superseding amendment.

No unresolved product or architecture decision remains in the plan. The review introduced no new
dependency direction or external side effect.

## Accepted Durable Amendments

1. Preserve the 15-minute/100-MiB closed product boundary and describe meetings, interviews, and
   lectures only as bounded clips or excerpts.
2. Split delivery into PR A feasibility/license evidence, PR B internal foundation, PR C public
   activation/Export v2/terminal proof, and a separate release closeout.
3. Make PR A receipt authority exact over external constraints, a canonical wheelhouse manifest,
   PyAV/FFmpeg inventory/direct evidence, `local_runtime_only` external binaries,
   `repository_distributed` fixtures, closed external-binary non-redistribution literals,
   target-executable identities, supported platforms, and supervisory proof without binding
   ordinary MKE commits.
4. Prove the Darwin arm64 polling supervisor with a controlled allocator in the supervisory leader
   in PR A, including stable leader identity, leader-only non-aggregate `ri_phys_footprint`,
   transient overshoot, ordinary-descendant process-group `SIGTERM`/fixed grace/`SIGKILL`/wait-reap,
   and fail-closed leader sampling plus descendant signaling/cleanup; then integrate it in PR B.
   Retain `hard_kernel_enforced=false` and make no sandbox, hostile-media, or `setsid`/`setpgid`
   escape claim.
5. Strengthen immutable intake with unresolved-path symlink rejection, resolved allowed-root
   containment, descriptor-bound copying, a second full digest, file-timestamp identity, and
   same-inode mutation tests.
6. Use a lightweight no-model preflight and acquire existing owner admission before snapshot,
   child, or model work.
7. Reconcile Export v2 against accepted downstream v1 evidence before freezing its exact closed
   shape; retain LLM Wiki as an external view rather than a dependency or Evidence authority.
8. Lead onboarding with the one-command model-free proof, then provide tested Python, CLI, and
   path-only stdio MCP examples, closed recovery mappings, and an explicit v1-to-v2 migration table.
9. Run release-grade installed-wheel and real-provider evidence once on the final PR C candidate;
   reassess repeated findings before entering an assurance loop.
10. Commit the candidate before whole-branch review, persist the returned review result afterward,
    and forbid tracked writes after terminal wheel/proof generation.
11. Identify prepared wheels by full canonical filename, bytes, digest, and parsed tags; resolve
    exactly one compatible wheel per lock-derived distribution/version and Python/platform cell,
    while allowing disjoint tagged wheels and one recorded universal wheel to serve multiple cells.
12. Freeze ordinary pip's own offline subprocess boundary with isolated config, sanitized
    environment, `--no-index`, validated local `--find-links`, binary-only hashed inputs, and no
    index/proxy/cache/source-build fallback.
13. Run the acquisition preflight directly under an existing approved stdlib-only controller
    interpreter with isolated/no-bytecode flags; bind each target executable before/after one fixed
    bounded stdlib identity probe under a sanitized environment, with no pip, `uv`, install,
    environment, bytecode, or cache activity.

## Targeted Repair Status

| Finding | Resolution | Targeted result |
|---|---|---|
| Shared wheelhouse rejected valid same-version cp312/cp313 wheels | Manifest identity is full filename/bytes/SHA-256/parsed tags; compatibility is resolved exactly once per supported cell; disjoint wheels and universal reuse are explicit | Closed |
| Outer offline flag did not constrain ordinary pip | Real nested-pip argv/environment is frozen and tested with no index, config, proxy, cache, or source-build fallback | Closed |
| Read-only preflight used an environment-creating launcher | Preflight uses a direct approved stdlib-only controller, never `uv run`, and runs only the fixed bounded target identity probe with descriptor identity before/after and no package/cache activity | `Superseded` by authority amendment |

The repair changes no product boundary, dependency direction, PR staging, Export v2 authority,
release boundary, or external-side-effect authorization.

## Prerequisites And Non-Claims

PR A still requires a separate implementation dispatch, and acquisition remains separately
authorized. PR B waits for accepted/merged PR A. PR C waits for accepted/merged PR A, PR B, and the
independent LLM Wiki compatibility docs/evidence PR.

PR A does not redistribute external dependency binaries and must record
`external_binary_redistribution=not_performed` and
`redistribution_authority=not_claimed`. Fixture redistribution remains a hard gate. Any future
bundling or release redistribution of external binaries requires separate legal review.

At this review point, that downstream compatibility evidence has not been accepted or merged. The
expected compatibility outcome is therefore not treated as an established fact, and the exact
Export v2 shape remains intentionally unfrozen. No implementation, package/model acquisition,
push, pull request, merge, release, or deployment occurred as part of this review.
