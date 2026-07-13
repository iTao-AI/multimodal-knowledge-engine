# Consumer-Ready Source-Pack Proof Implementation Review

Review target: standalone client, controller boundary, source-pack membership, and boundedness
claims after implementation.

Review status: initial implementation review completed and accepted at commit
`44fa5b3571173b09400c76f3b326633c63d08f31`; CI portability resolution completed and accepted by
targeted re-review. Post-commit neutral detached full-suite verification remains pending.

## Finding 1 — Client Failure Propagation

The controller previously mapped every nonzero standalone-client exit to
`server_exit_nonzero`. This made stable client validation, mapping, timeout, and cleanup codes
unreachable from the public controller even when the client emitted its exact redacted failure
object.

The controller now parses nonzero stdout only as one complete JSON document with exactly the keys
`status` and `code`. `status` must equal `failed`, and `code` must belong to the standalone
client-owned stable allowlist. Standard JSON trailing whitespace is accepted because the client
prints a newline; any non-whitespace trailing data, extra or missing field, unknown code, or
controller-only code maps to `server_exit_nonzero`. Focused tests exercise this boundary through
`run_proof`, including both accepted and rejected subprocess results.

## Finding 2 — Exact Output Ownership Boundary

The previous `max_transport_bytes` name suggested that the standalone client hard-capped all raw
MCP transport bytes. In the official MCP SDK stdio architecture, the SDK owns raw protocol stdout
framing. The client-owned pipe passed through `stdio_client(errlog=...)` owns only MCP server
stderr.

The configuration and CLI are now named `max_server_stderr_bytes` and
`--max-server-stderr-bytes`. Controller subprocess stdout and stderr remain incrementally hard
bounded. MCP server stderr remains incrementally hard bounded, including the live noisy-child
termination regression. Raw MCP stdout framing is not claimed to be hard-capped before SDK
parsing. Structured Search and Ask payloads remain bounded by the independent validator after
parsing. No custom MCP transport was added.

## Finding 3 — Exact Source-Root Membership

The prior membership check considered only files with a `.pdf` suffix, so an unexpected regular
file could coexist with the approved manifest entries. Membership now compares the manifest's
normalized relative filenames with every regular file found recursively under the copied source
root. Only after exact set equality does it read each approved file and verify byte count and
SHA-256. Tests reject unexpected non-PDF and nested regular files without changing the frozen
manifest identity or source bytes.

## Finding 4 — Linux Process-Group Reaping Semantics

The controller correctly probes a process group after the direct parent exits so a surviving
descendant still triggers terminate-then-kill cleanup. The previous final success condition also
required that same group ID to become immediately unobservable. On Linux, a killed orphan
descendant can remain briefly observable as a zombie until its external reaper runs, even though it
is no longer live.

The cleanup trigger and process-group signals remain unchanged. After cleanup, success now requires
the direct parent to be reaped and both bounded-output reader threads to exit; it does not require
an immediate `ESRCH` result for the group ID. A controlled regression freezes stale final-probe
semantics, and Linux test helpers treat `/proc` state `Z` as terminated without making `/proc` a
production dependency. Restricted or malformed `/proc` reads fall back to `os.kill(pid, 0)` rather
than assuming termination. Live descendant, timeout, and stdout/stderr overflow regressions remain
in place.

## Documentation And Verification Boundary

The design, implementation plan, how-to, and prior plan review use the exact stderr-specific name
and boundedness statement. Targeted re-review accepted the expanded review-fix set. The final
neutral detached-worktree command `UV_OFFLINE=1 uv run pytest -q` completed with
`1584 passed, 5 skipped, 5 warnings in 117.75s` and exit code `0` at commit
`44fa5b3571173b09400c76f3b326633c63d08f31`.

This resolution does not modify producer runtime, canonical MCP schemas, evaluation behavior or
artifacts, frozen source bytes, primary CI source identity, release verification, versioning,
publication, or deployment surfaces. Commit, push, PR, merge, release, publication, and deployment
remain unauthorized in this execution handoff.
