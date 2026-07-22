# Bounded Direct-Audio Intake Implementation Review

Status: **TARGETED AUTHORITY RE-REVIEW PENDING**

This record captures the approved PR C entry-gate reconciliation, the returned implementation
review result, and a later bounded install-projection repair awaiting targeted authority re-review.
The earlier Task 10 Step 6 acceptance remains recorded, but the pending repair does not clear a
fresh Step 8, real-ASR, release, redistribution, production-readiness, or deployment gate.

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

- Exact current reviewed HEAD: `28e0e8e01e132ea9318a2ee2c73e56b1276fdf05`.
- Verdict: `CLEAN / compiled export proof canonical temp-root repair ACCEPTED`.
- The earlier whole-branch verdict at `ecb9593fc0549caa1cebf90e677a4060602f2a10` remains accepted;
  the targeted repairs amend that durable result without reopening the whole-branch review.
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

The authorization-only preflight after the original Step 7 read-back exposed one additional
direct-entry operability defect before any real provider execution. The documented command
`python scripts/direct_audio_deployment_proof.py` could not resolve
`direct_audio_dependency_receipt` without `PYTHONPATH`, although package import and
`python -m scripts.direct_audio_deployment_proof` remained valid. The accepted repair range is
`bf20425b3920969ef6558a5ace81587ffaa7e844..a44347bf3c655626cf7e83a8c9b6432b8165f42d`.
It changed exactly:

- `scripts/direct_audio_deployment_proof.py`; and
- `tests/scripts/test_direct_audio_deployment_proof.py`.

The repair is a narrow dual-mode sibling import with no `sys.path` mutation, fallback controller,
dependency, workflow, public-contract, or evaluation-artifact change. Direct script execution
uses the sibling module; package import and module execution preserve the existing `scripts.*`
authority. The exact diff is `30 insertions, 2 deletions`.

The first terminal repository sequence then exposed a Darwin call-owned path defect in the
Compiled Library Export proof controller. `tempfile.mkdtemp()` returned the owned directory through
the `/var` alias while direct-audio snapshot authority correctly rejected that symlink-bearing
parent before model-free audio ingestion. The accepted repair range is
`ce3a3b2aa7d74eca2aec0231d691dd82277a2f11..28e0e8e01e132ea9318a2ee2c73e56b1276fdf05`.
It changed exactly:

- `scripts/compiled_library_export_proof.py`; and
- `tests/scripts/test_compiled_library_export_proof.py`.

The controller now resolves the freshly allocated root with `strict=True`, verifies that the
unresolved and resolved paths are directories with equal `(st_dev, st_ino)` identity, and passes
the canonical path to candidate preparation, interpreter workspaces, the publisher, and normal
cleanup. The audio snapshot symlink policy and all production `src/mke` paths are unchanged. The
exact diff is `83 insertions`. Targeted review returned
`CLEAN / compiled export proof canonical temp-root repair ACCEPTED` without reopening the accepted
whole-branch review.

## Verification Identity

The earlier whole-branch targeted verification on `ecb9593fc0549caa1cebf90e677a4060602f2a10`
established:

- exact residual repair scope: two files;
- focused presentation and direct-audio documentation suite: `214 passed`;
- live presentation audit: `status=ok, violations=[]`;
- affirmative and safe-negation probe: `8/8 passed`;
- incremental `git diff --check`: passed; and
- tracked worktree: clean.

Targeted re-review and accepted execution evidence for current exact HEAD
`a44347bf3c655626cf7e83a8c9b6432b8165f42d` established:

- exact substantive scope: two files, `30 insertions, 2 deletions`;
- direct-path and module-path `--help`: passed with identical CLI help;
- focused direct-path regression: `1 passed, 23 deselected, 5 warnings`;
- full pytest: `2985 passed, 14 skipped, 5 warnings`;
- Ruff: passed;
- Pyright: `0 errors, 0 warnings`;
- canonical E1 through E3-E validators: `7/7 passed`; and
- no evaluation identity refresh was required for `a44347b`; commit scope and
  `git diff --check` were clean.

Targeted re-review and accepted execution evidence for exact HEAD
`28e0e8e01e132ea9318a2ee2c73e56b1276fdf05` established:

- exact substantive scope: two files, `83 insertions`;
- focused symlink-parent regression RED on the unresolved alias and GREEN with `1 passed`;
- full Compiled Library Export proof controller suite: `51 passed`;
- adjacent audio snapshot, Publication, and export-documentation slices: `79 passed, 5 warnings`;
- full pytest: `2986 passed, 14 skipped, 5 warnings`;
- Ruff: passed;
- Pyright: `0 errors, 0 warnings`;
- canonical E1 through E3-E validators: `7/7 passed`; and
- no evaluation identity refresh was required; commit scope and `git diff --check` were clean.

The one historical same-wheel diagnostic attempted before the repair was committed returned
`candidate_artifact_invalid` because candidate-source authority requires a clean Git snapshot. It
is inconclusive execution-order evidence, was not rerun, and is not passing same-wheel authority.

## Bounded Install-Diagnostic Repair Acceptance

Targeted actual-diff review of exact HEAD
`45c1895a9fc4e40284450825bca16fc71193c439`, with parent
`bbcf107ea3fbcea7c9695f4a07024e5b86957b07`, returned
`CLEAN / bounded install-diagnostic repair ACCEPTED`. The repair changed exactly:

- `scripts/direct_audio_deployment_proof.py`; and
- `tests/scripts/test_direct_audio_deployment_proof.py`.

The exact diff is `482 insertions, 4 deletions`. The first closure rejects non-absolute,
non-normalized, parent-traversing, alias, and symlink-parent operator diagnostic paths before file
creation while preserving canonical Darwin `/private/var` paths. The second closure maps both file
and parent descriptor close failures to the closed internal diagnostic-write error, retains the
public `install_failed` classification, closes each descriptor once, and limits best-effort cleanup
to the same created `(st_dev, st_ino)` identity so an operator replacement is not removed.

Accepted verification for that exact repair reported:

- focused findings: `7 passed`;
- complete diagnostic set: `17 passed`;
- deployment-proof file: `41 passed`;
- documentation and presentation tests: `214 passed`;
- committed combined read-back: `255 passed`;
- full pytest: `3003 passed, 14 skipped, 5 warnings`;
- Ruff: passed;
- Pyright: `0 errors, 0 warnings`;
- canonical E1 through E3-E validators: `7/7 passed`, with no identity refresh; and
- `git diff --check`: passed.

The public failure aggregate remains the same four fields and bytes-equivalent closed meaning:

```json
{"canonical":false,"failure":"install_failed","schema_version":"mke.direct_audio_deployment_proof.v1","status":"failed"}
```

The real deployment-controller invocation count is exactly one. That invocation failed
`install_failed`; the retry count remains zero. The failure receipt and bounded operator failure
summary are historical evidence only and do not identify the old run's exact failing install
substep. No ASR, provider, model, or product success is established.

## Historical Terminal Evidence Boundary

All earlier Step 8 wheels, binding reports, and authorization manifests are retained historical
evidence only. This includes wheel digest
`8a9269593e7846b9142e70c897279ae52fe82607dd24dcbecd5965d8e4192dbb`, binding-report digests
`f42d27810f7f6eef9a8d2ee20c00cca338d0a0d09549f2bf4b1915259d8d910b` and
`840286cd333dccffe34b9fc3e4385a65afb0d36d39156856f19ee6573cb8b225`, and authorization-manifest
digest `dc7df6ff38323d12c3e81627d0a4c201baafd498449e137e2a38e1f0b15e03c8`. They are prohibited as
final authority because later tracked repairs changed the source HEAD. A fresh Step 8 wheel,
terminal-input binding, and authorization-only result are required before Step 9 can proceed.

All Step 8 material created before the docs-only acceptance commit recording the bounded
install-diagnostic verdict is also historical and prohibited as final authority. Only artifacts
built and bound from that acceptance commit can clear the next Step 8 gate.

## Static Candidate Receipt Authority Acceptance

The full locked dependency closure exposed a static cross-binding false-green in the independent
`--validate-receipt` lane. After recomputing the wheelhouse manifest and canonical self-digest, a
receipt could omit the candidate MKE wheel and rows, omit the candidate from one interpreter cell,
or bind Python 3.12 and Python 3.13 to different MKE candidates while reporting passed.

Repair commit `a158a4d50ef2ffa315538f3b6a6f242a1c5c56bc` closes that finding by requiring:

- exactly one `multimodal-knowledge-engine` candidate in the wheel inventory;
- exactly two top-level candidate installed rows with cells `3.12` and `3.13`;
- identical candidate filename, version, and SHA-256 in both rows, matching the unique wheel; and
- the existing exact per-cell projection back to the top-level installed rows.

Career targeted re-review of
`893d520a83d82454f44516dc6815f50a8efca520..a158a4d50ef2ffa315538f3b6a6f242a1c5c56bc`
returned CLEAN with no new finding. The exact four-file repair is `143 insertions, 4 deletions`.
Independent mutation replay returned passed for the positive artifact and
`committed_receipt_invalid` for absent-candidate, one-cell-only, and two-different-candidate
receipts after their required digests were recomputed. A malformed candidate cell through the
descriptor bootstrap returned the same closed failure without a raw traceback. The canonical
bootstrap CLI exited zero with empty stderr; focused receipt, deployment, documentation, and proof
tests reported `311 passed, 5 warnings`; focused Ruff passed; focused Pyright reported `0 errors`;
and `git diff --check` passed.

The accepted canonical receipt identities are:

- payload SHA-256: `fd369d35cb97754839f62ed6ee72dbb69f4cedc85eae40f3c0891d314e0dc61e`;
- file SHA-256: `befc901781c597b8e80f380cf5e29a183c672132c31590efff7d9ff1dad373b7`;
- controller script SHA-256: `932c9e17733e343f15fa558f1e54d21248da8f3f13ce4e52acc344b8f7ca2257`;
- inventory: 61 wheels, 108 installed rows, and 54 packages in each interpreter cell; and
- unique candidate SHA-256: `8a9269593e7846b9142e70c897279ae52fe82607dd24dcbecd5965d8e4192dbb`.

Steps 6 and 7 remain accepted and complete. Step 8 is the next incomplete gate. The real
deployment-controller invocation count remains two and the retry count remains one. No third real
controller invocation, model load, ASR, provider, or product-path execution occurred. This result
does not establish external binary redistribution, production, SLA, release, or deployment
authority. All Step 8 material predating the acceptance commit that records this result remains
historical and cannot serve as final authority.

## Locked-Root Install Projection Repair Pending Review

A later authorized Step 9 execution completed its repository pre-gates and then invoked the real
deployment controller once. It failed closed at `pip-install-3.12` with the unchanged public
`install_failed` aggregate. The bounded diagnostic established that `_stage_cell_impl()` had
replaced the already accepted candidate-aware root authority with one candidate-only direct-URL
line. Because pip hash checking is all-or-nothing, the unchanged ranged candidate metadata did not
become an accepted pinned root merely through constraints. The failure does not establish
dependency, receipt, candidate-wheel metadata, wheelhouse, constraints, or pip drift.

Repair commit `9398f169348188ead18c082b28d20211cf293695` changes exactly:

- `scripts/direct_audio_deployment_proof.py`; and
- `tests/scripts/test_direct_audio_deployment_proof.py`.

The repair reuses the PR A `_candidate_wheel_authority()` implementation rather than adding a
second resolver. It derives the candidate-aware root bytes from the accepted lock projection,
constraints, candidate, and receipt, validates the receipt-bound digest for both cells, and carries
those bytes in a private `AuthorizationManifest` field excluded from `as_dict()`. Staging writes the
selected bytes verbatim, and `_validate_staged_inputs()` now requires exact content and digest both
before and after pip. The serialized `mke.direct_audio_terminal_authorization.v1` schema is
unchanged. The controller still uses `--require-hashes`, `--no-index`, a validated local
`--find-links`, `--only-binary=:all:`, constraints, isolated/config-free pip state, and no
`--no-deps` fallback.

Focused TDD recorded 11 expected RED failures: both cells staged only the candidate line, seven
missing/wrong/noncanonical/duplicate/surplus/replacement mutations passed the old substring check,
and the shared candidate-root projection was absent. GREEN reported `11 passed`; the complete
deployment-proof file reported `59 passed`; receipt/deployment/documentation/proof adjacency
reported `331 passed, 5 warnings`; Ruff passed; and Pyright reported `0 errors, 0 warnings`.
Descriptor-bound projection against the retained accepted inputs reproduced, for both Python 3.12
and 3.13, exactly 54 lines, 5,819 bytes, and SHA-256
`e653870bfb252d22309bbe6b66bf7790bd89d167e41094dd5a358a20f876aebf` without running pip or the
deployment controller.

The repair is `TARGETED AUTHORITY RE-REVIEW PENDING`. The failed Step 9 evidence is historical only;
it does not authorize reuse of its wheel, binding, authorization, or aggregate as final authority.
The real deployment-controller invocation count is three and retry count is two. No fourth
controller invocation, manual pip lane, model load, ASR, provider, product path, download, release,
or deployment occurred during this repair.

## Next Gate And Non-Claims

The next gate is Career targeted actual-diff re-review of the locked-root projection repair. Step 8
remains incomplete and blocked until that review returns. This record does
not claim that a post-repair final wheel was rebuilt, authorization-only validation was rerun, real
ASR, model, or provider execution occurred, external inputs were acquired, packages or native
binaries may be redistributed, or any push, PR, merge, release, deployment, production readiness,
accuracy, SLA, or cross-platform authority exists. The historical deployment-controller
invocations failed before real ASR; the latest stable step was `pip-install-3.12`. Those failures
are not model, ASR, provider, or product success. This record does not claim release,
redistribution authority, production readiness, SLA, deployment, or retry success. The current
real deployment-controller invocation count is three and the retry count is two.
