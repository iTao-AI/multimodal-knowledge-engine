# Real Local Transcription Protocol And Lifecycle Review

## Status

- Result: CLEAN
- Scope: D3-B PR 1 protocol and lifecycle only
- Review date: 2026-06-18

## Scope Check

The implementation remains within the approved protocol/lifecycle scope. It adds project-owned
transcript, media, provenance, report, error, fingerprint, resource, and atomic visibility
contracts without adding an ASR runtime, model management, new transcription commands, public
provider configuration, or deployment proof.

## Findings Resolved

1. Run-start failures now enter the same recovery path as later ingest failures, preventing a Run
   from remaining pending when the transition to running fails.
2. Application validation now proves that a provider result's report, parsed provenance, media
   duration, segment count, and canonical fingerprint describe the same transcript before
   activation.
3. The public error allowlist now exactly matches the duration preflight cause, preserving a stable
   specific error without exposing raw exception text.

Regression tests cover all three findings.

## Lifecycle Review

- A recognized `faster-whisper-v1:<64 lowercase hex>` Publication requires a successful report.
- Publication creation, active FTS replacement, Source pointer switching, successful report
  insertion, Run publication, and the publication event share one SQLite transaction.
- Activation failure rolls back the complete visibility change and preserves previous active Search
  results.
- Failed and superseded Runs expose no successful transcript report.
- Legacy PDF and sidecar video Publications remain compatible without transcript provenance or a
  transcript report.

## Boundary Review

- No optional ASR, PyAV, or model dependency was introduced.
- No model resolution, download, preparation, doctor, or new transcription command exists.
- CLI and MCP share a typed redacted public error serializer.
- MCP input schemas contain no provider, model, argv, cache, endpoint, credential, or download
  controls.
- `mke proof run` and `mke demo --verify` remain deterministic and sidecar-backed.

## Verification

| Command | Result |
|---|---|
| `uv run pytest -q` | `270 passed, 5 warnings` |
| `uv run ruff check .` | passed |
| `uv run pyright` | `0 errors, 0 warnings, 0 informations` |
| `uv build` | sdist and wheel built successfully |
| `uv run mke proof run` | passed, `8/8` cases |
| `uv run mke demo --verify` | passed |
| `git diff --check` | passed |

## Remaining Risk

Real faster-whisper runtime behavior, model/cache preparation, spoken fixtures, and deployment proof
remain intentionally deferred to the sequential D3-B runtime and proof changes. The current
transaction model continues to assume the documented local single-owner SQLite runtime.

## Conclusion

No unresolved blocker remains for the protocol/lifecycle change.
