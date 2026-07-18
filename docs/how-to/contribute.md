# Contributing

This guide is the executable repository workflow. The short root
[`CONTRIBUTING.md`](../../CONTRIBUTING.md) remains the entry point, while [`AGENTS.md`](../../AGENTS.md)
defines the current Agent rules and product boundaries.

## Prepare An Isolated Change

1. Read `AGENTS.md`, the affected accepted ADRs, current reference or release documentation, and
   relevant tests.
2. Fetch the intended base and require a clean starting checkout. Do not overwrite unrelated
   operator changes.
3. Create a short `codex/<scope>-<slug>` branch in an isolated worktree for multi-step or
   independently reviewed changes. Verify that the worktree directory is ignored before creation.
4. Record the exact base, branch, worktree, and allowed file scope before editing.

Use one primary controller per phase. Parallel work requires at least two independent lanes with
clear file ownership and independent verification; the parent retains shared contracts,
integration, full verification, and the terminal report.

## Implement And Verify By Risk

Use risk-based verification that matches the change:

- Behavior and bug fixes use TDD: add a focused failing test, observe the expected RED, implement
  the minimum change, then observe GREEN.
- Contract, persistence, and public interface changes run focused contract/integration tests plus
  the repository's full verification gates.
- Documentation-only changes run their documentation contracts, link/status checks, presentation
  audit when release-facing text changes, and exact changed-file scans.
- Dependency, release, evaluation, or evidence changes follow their accepted ADR or current plan
  and preserve every recorded identity and semantic boundary.

Always inspect `git diff`, run `git diff --check`, and report only commands actually executed.
Never claim a test, review, build, push, or publication without command evidence.

## Prepare And Verify A Pull Request

Do not push or create a PR without authorization. When authorized:

1. Push the exact reviewed commit without force.
2. Create or update the PR with `Summary`, `Completion`, `Verification`,
   `Documentation Impact`, and `Risk / Migration` sections.
3. Use ordinary bullets for completed facts. Checkbox items are only for real pending gates that
   affect merge readiness; the default template intentionally contains no checkbox.
4. Read back the persisted title, body, base, head, and draft state and compare them with the
   intended values.
5. Query the actual pull request and checks for hosted state. Local workflow YAML does not prove
   that a hosted check exists, ran, or passed.

Reconcile the final PR body as gates change: every satisfied `[ ]` gate becomes `[x]`. After merge
and before closeout, synchronize actual checks, authorization, merge identity, mergeability,
review blockers, necessary links, cleanup, remaining risk, and explicit non-claims. Attempt the
write-back, then read back the persisted PR body. If the write-back or persisted-body readback
fails, or the body still drifts from actual state, record the exact blocker or pending trigger and
you must not claim complete closeout.

Before merge, require the reviewed HEAD and checks head to identify the same commit, all binding
checks to be successful, the base to remain approved, and platform review/mergeability to be clear.
For a squash merge, record both commit identities and prove the reviewed tree equals the merge
tree.

## Terminal State And Safe Cleanup

Report one terminal state:

- `READY`: the requested gate is complete;
- `WAITING`: an external check is nonterminal, with its exact URL/state recorded; or
- `BLOCKED`: a concrete authority, ownership, verification, or scope gate failed.

Do not repeatedly poll unchanged hosted state. Resume after a bounded wait or a new event.

Cleanup is separately gated. Remove only a task-owned branch or worktree that is clean, inactive,
and whose results are retained by a verified merge or another explicit authority. Confirm remote
state before deletion, prune only stale worktree metadata, and leave unrelated worktrees, caches,
artifacts, model files, and operator-owned evidence untouched.

Do not merge, tag, release, publish, or deploy without the corresponding explicit authorization.
