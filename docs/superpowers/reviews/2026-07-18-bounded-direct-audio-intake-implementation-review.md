# Bounded Direct-Audio Intake Implementation Review

Status: **CLEAN — TASK 10 STEP 6 ACCEPTED**

This record captures the approved PR C entry-gate reconciliation and the returned implementation
review result. The review acceptance clears only Task 10 Step 8 as the next gate; it is not a
real-ASR, release, redistribution, production-readiness, or deployment claim.

## Frozen v1 Downstream Authority

The verified LLM Wiki v1 workflow consumed and validated:

- the top-level manifest schema, complete Source inventory, active-Publication observation, and
  Evidence schema;
- Source identity, `display_name`, `content_fingerprint`, `media_type`, Publication and Run
  authority, `extractor_fingerprint`, and `required_stages`;
- Evidence and Markdown relative paths, counts, digests, and complete `mke.evidence_ref.v1`
  records;
- Markdown frontmatter, Evidence anchors, Page and Timestamp headings, and exact Evidence text;
  and
- the return path to content fingerprint, locator, manifest leaf, and complete EvidenceRef.

The following v1 behavior remains frozen:

- omitting `--format-version` and explicitly selecting `v1` produce exact v1 bytes for the same
  snapshot;
- existing v1 golden artifacts, schema, standalone consumer, and proof behavior do not change;
- v1 and v2 consumers do not cross-consume;
- Source, Run, Publication, and Evidence UUIDs retain their existing run-local random semantics;
  no deterministic identifiers are introduced for cross-run tree equality; and
- LLM Wiki remains an external downstream view, not an MKE dependency, schema owner, runtime
  component, or Evidence authority.

## Exact Minimal v2 Contract

V2 reuses the complete v1 field set and structure. It adds no Source, manifest-entry, Evidence,
Markdown-frontmatter, success-response, or error-response field. Only these version literals
change:

```text
mke.compiled_library_export.v1
  -> mke.compiled_library_export.v2

mke.compiled_markdown.v1
  -> mke.compiled_markdown.v2

mke.compiled_library_export_response.v1
  -> mke.compiled_library_export_response.v2
```

Evidence remains `mke.evidence_ref.v1`.

V2 success responses contain exactly:

```text
schema_version
ok
library_id
source_count
evidence_count
manifest_sha256
```

V2 error responses contain exactly:

```text
schema_version
ok
problem
cause
active_publication_impact
next_step
```

V2 adds no container, codec, channel, sample-rate, duration, provider, model, or transcript-report
field. Existing `media_type`, `required_stages`, `extractor_fingerprint`, and timestamp Evidence
carry the complete audio authority.

The closed v2 Source matrix uses the live domain validator's exact stage and fingerprint
authority:

| Media type | Locator | Required-stage authority | Extractor-fingerprint authority |
|---|---|---|---|
| `application/pdf` | page | PDF text stages | `builtin-pdf-text-v1` or `pymupdf-text-v1` |
| `application/pdf` | page | comparison-only PDF OCR stages | `pdf-ocr-eval-v1:<64 lowercase hex>` |
| `video/mp4` | `timestamp_ms` | video transcription stages | existing builtin, local-command, or faster-whisper video fingerprints |
| `audio/mpeg`, `audio/wav`, `audio/mp4` | `timestamp_ms` | audio transcription stages | `faster-whisper-audio-v1:<64 lowercase hex>` |

PDF OCR remains comparison-only authority and is not represented as production OCR.

## Stable v1 Mixed-Library Failure

Default v1 and explicit v1 fail closed when an active audio Source would make the Library
incomplete. They do not omit a Source or adjust counts. The command-local response is:

```text
problem = unsupported_active_media_type
cause = active Library contains media unsupported by export v1
active_publication_impact = unchanged
next_step = rerun_library_export_with_format_version_v2
```

This export-local error does not expand the shared MCP or `PublicError` allowlist.

## Version-Selected Authority Path

The version selector must travel through the complete authority path:

```text
CLI --format-version
-> interfaces.library_export.run_library_export
-> KnowledgeEngine.compiled_library_snapshot
-> SQLiteStore.compiled_library_snapshot
-> closed v1 or v2 DTO
-> renderer
-> descriptor-bound publisher
-> version-matched response
-> proof
-> independent consumer
```

A renderer-only version switch is not accepted.

## PR C Owner-Configured Runtime-Budget Clarification

Direct audio is activated only on Darwin arm64 when the owner explicitly supplies both
`RuntimeConfig.direct_audio_footprint_bytes` and
`RuntimeConfig.direct_audio_footprint_budget_mode="baseline_plus"` at startup. Both fields are
`None`, or both are configured. Configured bytes require `type(value) is int` and `value > 0`, so a
boolean is rejected. The mode accepts only `baseline_plus` at the direct-audio composition boundary;
the generic `SupervisedProcessProfile` retains its historical internal modes.

There is no default, fallback, recommendation, or SLA for `direct_audio_footprint_bytes`. PR A's
`24 MiB baseline_plus` value remains only controlled-allocator mechanism evidence, and
`1 GiB absolute` has no runtime authority. The same configured pair supervises both audio
inspection and transcription. It is owner-startup policy and never enters the path-only
`ingest_file` request schema.

Missing policy fails before Source, Run, snapshot, child, or model work with
`transcription_not_ready / direct audio supervision is not configured /
configure_direct_audio_supervision`. A non-Darwin arm64 runtime fails at the same boundary with
`transcription_not_ready / direct audio runtime is supported only on Darwin arm64 /
run_on_supported_darwin_arm64`. Neither condition changes PDF, video, or the existing
faster-whisper video owner.

PR C does not change the PR A/PR B supervisory mechanism and does not refresh the PR A receipt.
Tasks 9 and 10 bind the configured pair in the terminal authorization manifest. The real proof may
record configured bytes/mode, baseline, observed peak, effective budget, and overshoot only as
fixed-fixture Darwin arm64 observations; it does not establish a production ceiling, SLA,
recommendation, or cross-platform fact.

## Final Implementation Review Result

- Exact reviewed HEAD: `ecb9593fc0549caa1cebf90e677a4060602f2a10`.
- Verdict: `CLEAN / Task 10 Step 6 ACCEPTED`.
- All five returned findings are closed. No further whole-branch review is required before the
  next planned gate.

The closed findings are:

1. Darwin MCP materialization now preserves canonical call-owned path authority through the real
   MP3, WAV, and M4A lifecycle while retaining descriptor, no-follow, cleanup, and symlink-escape
   protections.
2. MCP cancellation and Publication commit use one atomic handshake, excluding the terminal state
   `CancelledError` with a newly active Publication.
3. The standalone v2 consumer accepts the producer's 64 MiB per-rendered-file authority while the
   frozen v1 consumer bytes remain unchanged.
4. The closed direct-audio proof reports `proof_mode="model_free"` and
   `asr_execution="not_performed"`; terminal real-ASR authority remains separate.
5. The presentation audit rejects affirmative terminal real-ASR completion and external
   wheel/native-binary redistribution or bundling claims in the bounded English and Chinese forms.
   The residual ordinary ran/executed and bundles/packages forms were closed by `ecb9593`; safe
   negations remain accepted and cannot mask a later affirmative clause.

The presentation audit remains a bounded public-claim guard, not a general natural-language
classifier.

## Verification Identity

Independent targeted verification on the exact reviewed HEAD established:

- exact residual repair scope: two files;
- focused presentation and direct-audio documentation suite: `214 passed`;
- live presentation audit: `status=ok, violations=[]`;
- affirmative and safe-negation probe: `8/8 passed`;
- incremental `git diff --check`: passed; and
- tracked worktree: clean.

Accepted execution evidence for the same reviewed HEAD is:

- full pytest: `2984 passed, 14 skipped, 5 warnings`;
- Ruff: passed;
- Pyright: `0 errors, 0 warnings`;
- canonical E1 through E3-E validators: `7/7 passed`; and
- no evaluation identity refresh was required for `ecb9593`.

## Next Gate And Non-Claims

Task 10 Step 7 records this returned result. Step 8 is the next incomplete gate. This record does
not claim that the final wheel was rebuilt, real ASR ran, external inputs were acquired, packages
or native binaries may be redistributed, or any push, PR, merge, release, deployment, production
readiness, accuracy, SLA, or cross-platform authority exists.
