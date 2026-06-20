# Real Local Transcription Deployment Proof Review

## Status

- Result: authoritative critical finding independently reproduced and resolved
- Scope: D3-B PR 3 deployment proof and documentation
- Review date: 2026-06-20
- Push / PR: not performed

## Scope Check

The remediation changes only the isolated wheel deployment proof and its regression coverage. It
does not change the transcription runtime, model revision, cache policy, public CLI/MCP contracts,
or required model-free CI behavior.

## Finding Disposition

| Severity | Review finding | Verification | Resolution |
|---|---|---|---|
| CRITICAL | Installed CLI and MCP commands inherited the repository working directory and Python module-resolution environment, so a source checkout or hostile `PYTHONPATH` could satisfy the proof instead of the installed wheel. | Confirmed in `scripts/transcription_deployment_proof.py`: installed doctor, ingest, Run inspection, Search, Ask, and MCP client commands omitted both `cwd` and `env`; no installed-package identity check existed. | Every installed-package command now runs from the external temporary runtime root with `PYTHONPATH`, `PYTHONHOME`, and `VIRTUAL_ENV` removed. A pre-doctor identity probe fails closed unless both `mke.__file__` and `sys.executable` are inside the temporary venv and outside the repository. |

## Regression Coverage

- The orchestration test injects repository-directed `PYTHONPATH`, `PYTHONHOME`, and `VIRTUAL_ENV`
  values and asserts every installed-package command receives the external runtime root and the
  sanitized environment.
- The command sequence now requires the identity probe before doctor or any ingest operation.
- A negative identity test rejects an `mke.__file__` resolved from the source repository.
- Existing timeout, bounded output, model-download authorization, report identity, redaction, and
  temporary cleanup coverage remains active.

## Verification

| Command | Result |
|---|---|
| targeted deployment proof and MCP client tests | `10 passed, 5 warnings` |
| targeted Ruff | passed |
| targeted Pyright | `0 errors, 0 warnings, 0 informations` |
| `uv run pytest -q` | `439 passed, 5 warnings` |
| `uv run ruff check .` | passed |
| `uv run pyright` | `0 errors, 0 warnings, 0 informations` |
| `uv build` | sdist and wheel built successfully |
| `uv run mke proof run` | passed, `8/8` cases |
| `uv run mke demo --verify` | passed |
| cache-only real ASR proof | passed; published Run, one timestamp Evidence, Search and Ask matched |
| Python 3.12 offline wheel CLI/MCP proof with hostile `PYTHONPATH` | passed |
| Python 3.13 offline wheel CLI/MCP proof with hostile `PYTHONPATH` | passed |
| `git diff --check` | passed |

## Remaining Risk

Real deployment evidence remains intentionally limited to the documented Darwin arm64 environment
and the exact prepared model revision. Required CI remains model-free. No additional full
`gstack-review` was run during remediation; this durable record captures the authoritative finding
provided by the planning window and the verified resolution.
