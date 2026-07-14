# Run The Consumer Source-Pack Proof

This how-to runs a source-built proof against the current source checkout. The controller builds
the current source checkout once, installs that same wheel into two fresh environments for Python
3.12 and Python 3.13, and runs a copied standalone client through the official MCP SDK. This
source-built proof is a `v0.1.2` release-candidate verification gate.

## Prerequisites

- Provide explicit `python3.12` and `python3.13` executables.
- Provision the uv cache with the locked dependencies and build tooling before running offline.
  The command below requires a prepared uv cache; it cannot install air-gapped from an empty
  machine or a never-provisioned cache.
- In CI, a distinct online provisioning/prewarm step prepares the controller and both interpreter
  caches before the offline proof step. `UV_OFFLINE=1` verifies reuse of that provisioned,
  lock-derived cache content. The controller does not enable network access or recover online from
  a cache miss.

Run from the repository root:

```bash
UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py \
  --python "$(command -v python3.12)" \
  --python "$(command -v python3.13)" \
  --json
```

## Candidate Artifact Handoff

Maintainers can add an operator-supplied local output to the same proof:

```bash
UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py \
  --python "$(command -v python3.12)" \
  --python "$(command -v python3.13)" \
  --candidate-output artifacts/m4b-candidate \
  --json
```

The target directory must not already exist. Candidate creation also requires a clean Git
checkout using the `sha1` object format. Before building, the controller pins that commit and
creates an immutable tracked snapshot with `git archive`; the wheel, locked dependency export,
and copied proof inputs all come from that snapshot. After both interpreter proofs and owned-temp
cleanup, the controller requires the live checkout to remain at the same clean HEAD. The final
directory becomes visible through a platform atomic no-replace rename; if that primitive is not
available or another process creates the target first, publication fails closed without replacing
the target. The directory contains exactly the proven wheel and
`candidate-artifact-receipt.json`.

The strict receipt uses `mke.candidate_artifact_receipt.v1` and contains exactly:

- identity: `schema_version`, `repository`, `source_commit`, `package_name`, and
  `package_version`;
- wheel identity: `wheel_filename`, `wheel_bytes`, `wheel_sha256`, and `requires_python`;
- proof binding: `consumer_proof_schema`, `consumer_proof_status`, and
  `proof_input_wheel_sha256`; and
- receipt identity: `receipt_sha256`.

`source_commit` is the exact Git commit ID and is 40 lowercase hexadecimal characters.
`wheel_sha256`, `proof_input_wheel_sha256`, and `receipt_sha256` are 64 lowercase hexadecimal
SHA-256 digests, and the two wheel digests must match. The receipt's canonical SHA-256 uses UTF-8
JSON with ASCII escaping, sorted keys, compact separators, no NaN, and omits `receipt_sha256` from
its own hash input.

This is local maintainer output, not a Release or PyPI artifact. The hosted workflow exercises the
same candidate-output path under `$RUNNER_TEMP`, but the result is not uploaded by the workflow.
Regenerate the wheel and receipt from the exact merged clean commit before any downstream handoff;
do not reuse feature-branch output as merged-commit evidence.

The controller copies the standalone consumer and its external consumer assets into an external
working directory. Each installed wheel starts an MKE stdio server through the official MCP SDK;
the consumer does not import MKE, read the repository, or read SQLite directly. These checks run
under a shared OS principal. They verify dependency and working-directory boundaries, but they do
not claim that an OS sandbox prevents filesystem access.

Controller subprocess stdout and stderr are hard bounded. MCP server stderr is hard bounded by a
consumer-owned pipe. Raw MCP stdout framing is owned by the official MCP SDK and is not claimed to
be hard-capped before SDK parsing. Structured Search and Ask payloads are bounded after parsing by
the independent validator.

## Output Contract

A successful command emits one JSON object with exactly these fields:

- identity: `proof`, `status`, `manifest_schema`, `evidence_schema`, and `pack_id`;
- counts and observations: `source_count`, `published_run_count`,
  `active_publication_count`, `active_evidence_count`, and `observed_states`; and
- verification flags: `installed_identity`, `external_isolation`, `strict_schema_validation`,
  `search_ask_projection_equal`, `exact_manifest_mapping`, `fresh_store_mapping`, `redaction`, and
  `cleanup`.

The consumer validates `mke.consumer_source_pack_manifest.v1` independently and maps every
returned `mke.evidence_ref.v1` to exactly one manifest source by `content_fingerprint`. The same
mapping must hold in a second fresh store, so generated database identifiers are not consumer
identity.

Failure emits only `{"status":"failed","code":"<stable_code>"}`. The stable codes are
`source_pack_manifest_invalid`, `source_pack_identity_mismatch`, `wheel_build_failed`,
`environment_create_failed`, `install_failed`, `installed_identity_failed`,
`external_isolation_failed`, `consumer_schema_invalid`, `consumer_payload_invalid`,
`manifest_mapping_missing`, `manifest_mapping_ambiguous`, `manifest_locator_mismatch`,
`observation_state_mismatch`, `mcp_startup_timeout`, `mcp_tool_timeout`, `mcp_transport_failed`,
`server_exit_nonzero`, `command_output_exceeded`, `candidate_artifact_invalid`, `cleanup_failed`,
and `proof_failed`. These are stable redacted failures: paths, identifiers, Evidence text, filenames, stderr, tracebacks,
environment values, and exception messages are not included.

## What This Proves

- One wheel built from the current checkout works in fresh Python 3.12 and Python 3.13
  environments using provisioned locked dependencies.
- A standalone external client discovers and validates the exact MCP tool schemas, exercises the
  success flow over real stdio, and verifies source identity by exact fingerprint mapping.
- Controller subprocess output, MCP server stderr, structured Search/Ask payloads, deadlines,
  process cleanup, and public failures remain bounded and redacted within the ownership boundaries
  above.

## What This Does Not Prove

This source-built wheel is not the final tagged `v0.1.2` Release wheel, not a GitHub Release asset,
not a PyPI artifact, not a deployment, and not proof of production adoption. Candidate output is
local release-gate evidence, not publication. The proof also does not establish installation from
an empty machine, network-independent cache provisioning, or OS-level isolation.
