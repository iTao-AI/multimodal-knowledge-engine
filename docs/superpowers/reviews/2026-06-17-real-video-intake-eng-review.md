# Real Video Intake Provider Port Engineering Review

- Review date: 2026-06-17
- Scope: D3-A Provider Port + MP4 LocalCommand Smoke
- Status: Approved
- Mode: Scope-reduced architecture review

## Summary

The original D3 direction was real audio/video intake. The approved D3-A slice narrows that into a
provider-port foundation plus an optional local-command MP4 smoke path. This preserves the current
deterministic sidecar proof while adding the boundary needed for real transcription providers.

## Findings And Decisions

| Area | Finding | Decision |
|---|---|---|
| Scope | General audio/video intake would pull in codecs, model runtime, diarization, long-video chunking, and provider UX at once. | D3-A is limited to `TranscriptProvider` port + MP4 local-command smoke. |
| Architecture | `KnowledgeEngine._process_video()` currently calls the sidecar helper directly. | Add explicit `transcript_provider` dependency injection, matching the existing PDF extractor pattern. |
| Schema | Current transcript validation is coupled to the sidecar file and tested through a private helper. | Extract shared public schema parsing and validation used by both sidecar and local command providers. |
| Security | Arbitrary command execution must not be available through Agent-facing requests. | Local command configuration is trusted local/operator-only. MCP and normal ingest requests cannot supply commands. |
| Command execution | Shell strings make quoting and injection boundaries hard to review. | Provider config accepts argv tuple/list only and runs with `shell=False`. |
| Proof determinism | A real provider could make `mke proof run` flaky if it becomes the default proof path. | `mke proof run` and `mke demo --verify` keep using sidecar provider. Real provider smoke is separate. |
| ADR | ADR-0003 denies real transcription for the earlier proof slice. | Preserve ADR-0003 and add ADR-0005 to authorize optional local-command provider behavior. |

## Required Implementation Checks

- Add tests for provider injection in `KnowledgeEngine`.
- Add tests for local command success, non-zero exit, timeout, missing executable, oversized output,
  invalid JSON, and schema validation failures.
- Add tests proving MCP cannot receive command argv.
- Add tests proving deterministic proof commands still pass without a local command provider.
- Keep all public error payloads free of absolute paths, stack traces, raw argv, provider stderr,
  secrets, and temp directories.

## Verification For Review

This was a plan-stage review. No source behavior changed during the review.

Recorded gstack review log:

```text
skill=plan-eng-review
status=clean
unresolved=0
critical_gaps=0
issues_found=8
mode=SCOPE_REDUCED
commit=ae9f982
```
