# Run The Consumer Source-Pack Proof

This how-to runs a source-built proof against the current source checkout. The controller builds
the current source checkout once, installs that same wheel into two fresh environments for Python
3.12 and Python 3.13, and runs a copied standalone client through the official MCP SDK.

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
`server_exit_nonzero`, `command_output_exceeded`, `cleanup_failed`, and `proof_failed`. These are
stable redacted failures: paths, identifiers, Evidence text, filenames, stderr, tracebacks,
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

This source-built wheel is not the tagged `v0.1.1` Release wheel. This proof is not a Release
artifact, not a release gate, not a PyPI proof, not a deployment, not a production-readiness proof,
and not a release verification step. It also does not prove installation from an empty machine,
network-independent cache provisioning, or OS-level isolation.
