# Run The MCP Context Completeness Proof

Use this proof to verify one locally built wheel through the locked official MCP SDK on
Python 3.12 and Python 3.13. Both interpreters and all lock-derived packages must already be present in
the local uv cache. The proof runs with `UV_OFFLINE=1`; it does not install globally or download
dependencies.

```bash
uv export --locked --no-dev --no-emit-project \
  --output-file /ABSOLUTE/PATH/TO/mke-core-requirements.txt

UV_OFFLINE=1 uv run python scripts/mcp_context_completeness_proof.py \
  --python /ABSOLUTE/PATH/TO/python3.12 \
  --python /ABSOLUTE/PATH/TO/python3.13 \
  --constraints /ABSOLUTE/PATH/TO/mke-core-requirements.txt \
  --candidate-output /ABSOLUTE/PATH/TO/candidate-output \
  --json
```

The controller builds exactly one wheel, creates temporary external environments, installs that
same wheel under the exported lock-derived constraints offline into both, and invokes the
standalone consumer from an arbitrary external working directory. It verifies that `mke.__file__`
and `sys.executable` belong to the external environment, not the source checkout. Temporary
environments are removed when the controller exits; the requested candidate output remains
available for inspection.

A successful closed receipt reports `source_import="installed_wheel"`,
`network_access="not_used"`, both Python versions, ten tools, contract proof-point statuses, and
the greatest observed canonical and SDK result byte counts. A failure prints only
`{"status":"failed","code":"<stable-machine-code>"}`.

The proof covers exact discovery, structured/compatibility text equality, Search continuation,
query-centered incomplete excerpts, exact Read reconstruction and final SHA-256, terminal CJK
caps, cursor tamper and expiry, bounded legacy calls, typed oversized v1 failures, reconnect, and
wire-size gates. It does not prove corpus-exhaustive Search, semantic summaries, production
readiness, deployment, adoption, performance, hosted operation, or arbitrary Evidence size.

## Safe Troubleshooting

An issue may include dependency and Python versions, the public problem code, the failed proof
step, and whether restart/reconnect succeeded. Never include Evidence or query text, a cursor,
database path, username, local filename, private configuration, credentials, environment dumps,
or tracebacks. Re-run with the documented public fixture rather than attaching private input.
