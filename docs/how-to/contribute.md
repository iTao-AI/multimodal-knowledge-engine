# Contributing

This guide is the executable repository workflow. The short root
[`CONTRIBUTING.md`](../../CONTRIBUTING.md) remains the entry point, while [`AGENTS.md`](../../AGENTS.md)
defines the current Agent rules and product boundaries.

## Code Navigation

For a CLI change, start at the `mke.cli` facade. Argument declarations live in
`mke.interfaces.cli_parser`; named command-family handlers carry execution through
`mke.runtime` to `application`, `domain`, and `adapters`. Parser code owns argument
shape, but does not own lifecycle, persistence, or Evidence rules.

For conflicts, treat `AGENTS.md` as the current boundary and use live code, tests, accepted
ADRs, and current reference documentation as the evidence order.

## Prepare An Isolated Change

1. Read `AGENTS.md`, the affected accepted ADRs, current reference or release documentation, and
   relevant tests.
2. Fetch the intended base and require a clean starting checkout. Do not overwrite unrelated
   operator changes.
3. Create a short `codex/<scope>-<slug>` branch. Use an isolated worktree for substantial
   implementation or shared-state conflicts; a focused documentation change does not require one.
   Verify that a new worktree directory is ignored before creation.
4. Record the exact base, branch, worktree, and allowed file scope before editing.

Use one primary controller per phase. Delegate a bounded execution task when it helps, even
when no other lane runs in parallel. Parallel work requires independent scope, file ownership,
and verification; the phase controller retains shared contracts, integration decisions,
acceptance, and the terminal report.

## Local Environment And Preflight

Prepare an environment only when the selected checks need it. Reuse an existing valid environment;
documentation-only work does not require dependency synchronization or runtime preflight.

Prepare the repository-local `.venv` from the lockfile using an installed compatible Python:

```sh
uv sync --locked --offline --python 3.13
```

Before the full test suite, verify that isolated Python imports this worktree's source and `.venv`
metadata:

```sh
uv run --locked --offline python -I -c 'import importlib.metadata as md, pathlib, sys, mke; root=pathlib.Path.cwd().resolve(); source=pathlib.Path(mke.__file__).resolve(); metadata=pathlib.Path(md.distribution("multimodal-knowledge-engine").locate_file("")).resolve(); assert pathlib.Path(sys.prefix).resolve()==root/".venv"; assert source.is_relative_to(root/"src"); assert metadata.is_relative_to(root/".venv"); print(f"source={source}; metadata={metadata}")' || exit 1
.venv/bin/mke --help || exit 1
if .venv/bin/mke __invalid__ >/dev/null 2>&1; then
  echo "mke unexpectedly accepted an invalid command" >&2
  exit 1
else
  exit_code=$?
  test "$exit_code" -eq 2 || exit 1
  printf 'mke invalid-command exit=%s\n' "$exit_code"
fi
```

Run these targeted regressions when changing subprocess proof, historical replay, or direct-audio
CLI boundaries; select the affected cases rather than treating all nine as task-start prerequisites:

```sh
uv run --locked --offline pytest -q \
  tests/proof/test_evidence_provenance_stdio.py::test_evidence_provenance_proof_runs_real_stdio \
  tests/proof/test_local_knowledge.py::test_local_knowledge_proof_runs_real_stdio_mcp_flow \
  tests/proof/test_local_knowledge.py::test_local_knowledge_proof_report_contains_only_public_aggregates \
  tests/proof/test_local_knowledge.py::test_local_knowledge_proof_uses_private_server_stderr_sink \
  tests/proof/test_mcp_deployment_client.py::test_installed_mcp_module_help_has_no_outer_stderr \
  tests/evaluation/test_retrieval_order_compatibility.py::test_historical_capability_uses_exact_tree_runtime_and_two_replays \
  tests/evaluation/test_retrieval_order_compatibility.py::test_compatibility_artifact_exposes_complete_family_differentials \
  tests/evaluation/test_retrieval_order_compatibility.py::test_historical_child_artifact_mismatch_is_terminal_stop \
  tests/scripts/test_direct_audio_deployment_proof.py::test_export_controller_matches_real_cli_leaf_name_and_cwd_contract
```

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
