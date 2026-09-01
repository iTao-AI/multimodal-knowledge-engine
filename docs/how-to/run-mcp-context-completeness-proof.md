# Run The MCP Context Completeness Proof

This current-checkout proof documents the MCP consumer failure-branch/recovery proof added on the
current default branch after stable `v0.1.6`. It is not part of stable `v0.1.6`; it is not a package publication,
hosted deployment, model/provider change, or retrieval-quality claim. The immutable
release record remains in the [v0.1.6 Release Notes](../releases/v0.1.6.md).

The proof covers the exact ten-tool inventory, bounded continuation, exact active Evidence reads,
legacy/v1 compatibility, and cache-warmed offline execution on Python 3.12 and 3.13. Stable failure
codes map to operator actions in [Verify The Release](./verify-release.md); proof JSON is not
relabelled as the product `problem/cause/next_step` contract.

Use this proof to verify one locally built wheel through the locked official MCP SDK on
Python 3.12 and Python 3.13. Both interpreters and all lock-derived packages must already be present in
the local uv cache. The proof runs with `UV_OFFLINE=1`; it does not install globally or download
dependencies.

```bash
uv export --locked --no-dev --no-emit-project --no-header \
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

Before building the wheel, the controller independently runs the same no-header locked export and
requires its exact bytes to equal `--constraints`. A missing, stale, empty, or arbitrary constraints
file fails before build or installation.

A successful closed aggregate v1 receipt retains its existing top-level shape and reports
`source_import="installed_wheel"`,
`network_access="not_used"`, `dependency_constraints="uv_lock_exact"`, both Python versions, ten
tools, contract proof-point statuses, and the greatest observed canonical and SDK result byte
counts. A failure prints only
`{"status":"failed","code":"<stable-machine-code>"}`.

Each per-interpreter installed consumer records four Agent decisions at the existing contract
boundary. The controller requires the new consumer observations from both lanes, but they are not
aggregate v1 fields; the aggregate receipt remains closed and unchanged.

| Decision | Per-interpreter consumer observations (not aggregate v1 fields) | Meaning |
|---|---|---|
| normal no-match -> stop the search branch without treating it as transport failure | `normal_no_match="passed"` | An active, exhaustive empty Search result is a normal no-match. |
| capped selection -> preserve the non-exhaustive result boundary | `cjk_cap="passed"` | `selection.status="capped"` is terminal but not exhaustive. |
| evidence_not_found -> search current active Evidence instead of retrying an old identity | `inactive_evidence_recovery="passed"` | After active Publication is authority and changes, the old Evidence address returns the existing `problem="evidence_not_found"` and `next_step="search_current_active_evidence"`. |
| CJK scan budget -> narrow the query or use the supported projection strategy; do not retry unchanged | `cjk_scan_budget_recovery="passed"` | `cjk_scan_budget_exceeded` is a bounded active-scan budget failure, not an exhaustive no-match. |

The CJK budget branch sends 131 distinct CJK characters (393 UTF-8 bytes), within the 512-byte
request bound. The existing error directs the Agent to `narrow_query_or_use_projection_strategy`;
it must not retry the unchanged query. This read-only Search observation adds no ingest, provider,
or external-network side effect.

Evidence text is untrusted content, and active Publication is authority. These observations do not
change a runtime schema or claim retrieval quality gain, a generated answer, or a real external
consumer; they prove only the installed-wheel consumer's bounded decisions.

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
