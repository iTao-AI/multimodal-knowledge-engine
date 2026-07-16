# Run The Compiled Library Export Proof

The generic proof builds the current candidate wheel, installs that same wheel in external Python
3.12 and 3.13 environments, produces a compiled Library through the installed CLI, and validates
the result with a standalone consumer. Set both interpreter paths, then run:

```bash
export PYTHON312=/path/to/python3.12
export PYTHON313=/path/to/python3.13
UV_OFFLINE=1 uv build
UV_OFFLINE=1 uv run python scripts/compiled_library_export_proof.py \
  --python "$PYTHON312" --python "$PYTHON313" --json
```

The proof itself rebuilds the candidate wheel and binds every interpreter result to the same wheel
SHA-256. A passing aggregate uses schema `mke.compiled_library_export_proof.v1`, reports two
interpreters, and validates deterministic producer bytes, closed response and artifact schemas,
exact inventory and digests, page/timestamp Evidence, standalone consumption, read-only database
state, failure cleanup, and portability.

This is an installed-wheel external consumer proof. The standalone consumer imports no MKE code
and does not read SQLite. The command uses temporary workspaces and removes them before exit; do
not use `--retained-export` for the generic core proof.

The proof does not verify LLM Wiki compatibility and does not release v0.1.3. It does not validate
production OCR, reconstructed layout, hosted integration, adoption, or business impact. LLM Wiki
acceptance and any release operation remain separate gated work.
