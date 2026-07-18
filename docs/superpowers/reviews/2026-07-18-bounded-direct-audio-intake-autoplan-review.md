# Bounded Direct Audio Intake Plan Review

## Scope

This record captures one full structured review of the bounded direct-audio design and
implementation plan. The reviewed committed revision is
`c150c3c3c49990265cb756ef45a3669cd683714c`, reconciled against live `main` at
`23aaa682b69d019ecc4e73ab8d9239152b9770cf`.

The review covered product boundaries, implementation architecture, engineering failure modes,
developer experience, verification layering, and review/terminal-proof sequencing. It did not
review implementation code because implementation has not started.

## Verdict

`CLEARED FOR STAGED IMPLEMENTATION; PR A REQUIRES SEPARATE DISPATCH`

- CEO/product review: clean after accepted bounded-scope, proof, and license-authority amendments.
- Design review: skipped because the plan adds no graphical or browser UI.
- Engineering review: clean after accepted path, identity, resource, admission, and input-lineage
  amendments.
- Developer-experience review: clean after accepted onboarding, example, recovery, migration, and
  review-sequencing amendments.

No unresolved product or architecture decision remains in the plan. The review introduced no new
dependency direction or external side effect.

## Accepted Durable Amendments

1. Preserve the 15-minute/100-MiB closed product boundary and describe meetings, interviews, and
   lectures only as bounded clips or excerpts.
2. Split delivery into PR A feasibility/license evidence, PR B internal foundation, PR C public
   activation/Export v2/terminal proof, and a separate release closeout.
3. Make PR A receipt authority exact over external constraints, a canonical wheelhouse manifest,
   PyAV/FFmpeg components, licenses/notices, fixtures, supported platforms, and native-child
   containment without binding ordinary MKE commits.
4. Put PyAV inspection and faster-whisper execution behind receipt-backed bounded child processes;
   keep PR B free of public runtime activation.
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

## Prerequisites And Non-Claims

PR A still requires a separate implementation dispatch, and acquisition remains separately
authorized. PR B waits for accepted/merged PR A. PR C waits for accepted/merged PR A, PR B, and the
independent LLM Wiki compatibility docs/evidence PR.

At this review point, that downstream compatibility evidence has not been accepted or merged. The
expected compatibility outcome is therefore not treated as an established fact, and the exact
Export v2 shape remains intentionally unfrozen. No implementation, package/model acquisition,
push, pull request, merge, release, or deployment occurred as part of this review.
