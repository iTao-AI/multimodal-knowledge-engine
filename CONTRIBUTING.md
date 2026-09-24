# Contributing

Thank you for helping improve Multimodal Knowledge Engine.

Before contributing:

1. Read `AGENTS.md` and the relevant ADRs, specifications, plans, and tests.
2. Keep changes focused, independently reviewable, and covered by appropriate tests.
3. Update affected documentation in the same pull request.
4. Record actual verification results and remaining risks in the pull request.

See [docs/how-to/contribute.md](./docs/how-to/contribute.md) for the executable, risk-based
worktree, verification, PR, merge, and safe-cleanup workflow.

## Local Environment And Preflight

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

Run these nine targeted regressions for the subprocess proof, historical replay, and direct-audio
CLI failure:

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
