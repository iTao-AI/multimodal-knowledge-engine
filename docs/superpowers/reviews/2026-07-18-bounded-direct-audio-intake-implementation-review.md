# Bounded Direct-Audio Intake Implementation Review

Status: **CLEAN / ACCEPTED**

This record captures the approved PR C entry-gate reconciliation, the returned implementation
review result, the accepted bounded install-projection repair, and the accepted MCP diagnostic
authority repair. The earlier Task 10 Step 6 acceptance remains recorded. A later bounded repair
that removes circular terminal-candidate authority has passed targeted actual-diff re-review. It
does not complete Steps 8-10 or authorize real-ASR, release, redistribution, production-readiness,
or deployment activity.

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

## Locked-Root Install Projection Repair Accepted

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

Career targeted actual-diff re-review covered
`91993c658a81a9a1afb1bef4b3499731bfb9fb22..2f8af9eb481e7852337dae272ce4646beeec6434`
at reviewed HEAD `2f8af9eb481e7852337dae272ce4646beeec6434`. The verdict was `CLEAN`, with no
Critical, Important, or Minor finding. Independent review confirmed the exact four-file scope; the
reuse of PR A `_candidate_wheel_authority()` without a second resolver; exact 54-line, 5,819-byte
roots with SHA-256 `e653870bfb252d22309bbe6b66bf7790bd89d167e41094dd5a358a20f876aebf`
for both interpreter cells; fixed-hash `mcp==1.28.1` and the unique candidate wheel; exact staged
root validation before and after pip; preservation of `--require-hashes`, `--no-index`,
`--only-binary=:all:`, constraints, isolated configuration, and dependency installation; and an
unchanged serialized `mke.direct_audio_terminal_authorization.v1` schema. The fresh targeted
12-test slice, Ruff, canonical full Pyright, and `git diff --check` passed.

The repair is `CLEAN / ACCEPTED`. This acceptance clears only the gate to begin a fresh Step 8;
Steps 8-10 remain incomplete. Every earlier Step 8 artifact and the failed Step 9 wheel,
authorization, repository observations, public aggregate, and bounded install diagnostic remain
historical evidence and cannot be reused as final authority. The real deployment-controller
invocation count remains three and retry count remains two. This acceptance does not authorize a
fourth controller invocation, a Step 8 build, authorization-only execution, manual pip replay,
model load, ASR, provider or product-path execution, downloads, push, PR, merge, release, or
deployment.

## MCP Diagnostic Authority Repair Accepted

The retained MCP failure diagnostic previously checked mode and link count through `lstat()` and
then read bytes through a separate open, so replacement could separate the checked inode from the
parsed inode. It also accepted stage, overflow, and capture-failure combinations that the producer
could not generate. Repair commit `67ffa385614f1f9f3fe2583aff3e9cfdc35520c3` closes both gaps in
the MCP client, deployment controller, and their two test files. The validator now descriptor-reads
once and binds regular-file type, mode `0600`, `nlink=1`, size, bytes, final-path identity, and
pre/post metadata to the same inode. Producer and validator use one semantic rule for stage,
overflow, and capture-failure authority.

Identity-closure commit `d9364668d73b8ad1b2e1669b7cd52dcf83ac9923` mechanically refreshes
16 validator-proven evaluation paths. Targeted actual-diff re-review covered
`a9814f0429437ec229ed9eede27afe3c7c5e59aa..d9364668d73b8ad1b2e1669b7cd52dcf83ac9923`
at reviewed HEAD `d9364668d73b8ad1b2e1669b7cd52dcf83ac9923` and returned
`CLEAN / ACCEPTED`, with no remaining Critical, Important, or Minor finding. The substantive scope
is exactly four MCP client/controller and test paths; the other 16 paths are the validator-proven
identity closure.

Fresh focused suites reported `110 passed, 5 warnings`. Independent mutation checks rejected a
checked `0600` inode replaced by a `0644` regular file, rejected same-inode mode drift, and rejected
all four generator-impossible stage/overflow/capture-failure combinations as `mcp_failed`.
Exact-limit stderr, overflow, and capture-failure positive cases were accepted. Invalid producer
combinations normalized to `stage=stderr` with `capture_failed=true`. The descriptor validator
bound regular-file type, `0600`, `nlink=1`, size, bytes, final-path identity, and pre/post metadata
to the same inode. `semantic-equality.json` reported `true` for all 16 refreshed paths and unchanged
E3-B behavior. No further targeted finding remains.

Steps 6 and 7 remain accepted and complete. Step 8 is again the next incomplete gate; Steps 8-10
remain incomplete. Every earlier Step 8 or Step 9 wheel, authorization, public aggregate,
diagnostic, and related artifact remains historical evidence and cannot be reused as final
authority. The real deployment-controller invocation count remains four and retry count remains
three. A fifth invocation did not occur.

## Bounded Offline Receipt Replay — Clean / Accepted

The accepted external dependency and license projection does not follow ordinary MKE source or
documentation commits. The static validator continues to require one exact candidate MKE wheel and
the same candidate binding in both interpreter cells. When the final candidate wheel bytes change,
one bounded offline replay through the existing reviewed receipt controller is therefore permitted
without weakening that cross-binding.

The replay must use a call-owned wheelhouse composed of byte-identical copies of the accepted 60
external wheels and the fresh candidate wheel. The accepted interpreters, lockfile, constraints,
fixtures, descriptor bootstrap, offline nested-pip contract, and controller bytes remain unchanged.
The preserved replay changed exactly 17 leaves. Thirteen are mechanically candidate-derived: four
candidate installed `source_wheel_sha256` rows, two per-cell root-requirement digests, two per-cell
full-wheelhouse manifest digests, two preflight digests, the receipt self-digest, and candidate
wheel bytes/SHA. Candidate filename/version and all 60 external-wheel rows remain unchanged.

Four leaves are a newly authorized controlled-supervisor observation: baseline `213064 -> 196680`,
budget `25378888 -> 25362504`, observed maximum `27591136 -> 27607520`, and overshoot
`2212248 -> 2245016`. Budget minus baseline remains exactly 24 MiB; observed maximum exceeds
budget; overshoot equals observed maximum minus budget; `budget_outcome` remains
`exceeded_terminated`; cleanup remains `sigterm_sent=true`, `waited=true`, and
`process_group_absent=true`; and every other supervisor field is equal. This is a controlled
allocator feasibility observation only, not a real-provider budget, product default, production
ceiling, SLA, or runtime approval.

The exact 17-leaf comparison proves every other receipt leaf equal, including constraints,
controller, PyAV/FFmpeg/component, fixture, license, redistribution, and non-claim authority. The
historical canonical payload/file identities were
`fd369d35cb97754839f62ed6ee72dbb69f4cedc85eae40f3c0891d314e0dc61e` and
`befc901781c597b8e80f380cf5e29a183c672132c31590efff7d9ff1dad373b7`. The bounded replay identities
are `3dca3bc7737728ef49376f11d40e9611cf62552147840a0026b7ded5218a681a` and
`1fe3cd6fddd1bb07a949192c64fcf90ee2b9ac5fd22df1e8a334a5d446a611af`.

Targeted actual-diff re-review covered
`1b784eb10c279113c8299e404fa0dd35ef2be7a5..794bbde8cbf9a65f57d76840b924089c9948aab9`
at reviewed HEAD `794bbde8cbf9a65f57d76840b924089c9948aab9` and returned `CLEAN / ACCEPTED`
with no Critical, Important, or Minor finding. Independent review confirmed that the committed
receipt is byte-identical to the preserved generated replay, the JSON path inventory is unchanged,
the semantic diff is exactly the 13 candidate-derived and four bounded-observation leaves above,
and all stated supervisor invariants hold while every other supervisor field remains equal. The
external 60-wheel manifest recomputed to
`04960db80c29a372f7d29028cf4a9f646845df0c207ca39b1eb618b232624d06`. The fresh wheel remained
353200 bytes with SHA-256
`e3abdf24589be880aa2c135cd8687ed6c21e0ea0ed2ec5fe1742703ef665c3d0` and contained the exact
current `mcp_deployment_client.py` bytes. Static receipt validation plus the direct-audio
documentation and presentation suite reported `215 passed`; the live presentation audit returned
`status=ok`.

This record preserves the prior receipt and every previous Step 8/Step 9 artifact as historical
evidence. It does not complete Step 8 or authorize authorization-only, Step 9, manual MCP replay,
model, ASR, provider or product execution, download, release, redistribution, or deployment. It
does not establish real-ASR success, production readiness, accuracy, or SLA authority. The
historical real deployment-controller invocation and retry counts remain four and three; a fifth
invocation did not occur.

## MCP Gate Operator Diagnostic Repair — Clean / Accepted

The later authorized Step 9 run failed closed with the unchanged public `mcp_failed` aggregate.
Provider-free investigation did not identify a specific product-flow defect. It proved that the
installed MCP child silently discarded diagnostic persistence failure and that parent rejection of
an otherwise successful child result or exact source identity generated no operator diagnostic.

Repair commit `bf9fa248381c5edac6b6a77996288d36fa7d1ad9` changes exactly:

- `src/mke/proof/mcp_deployment_client.py`;
- `scripts/direct_audio_deployment_proof.py`;
- `tests/proof/test_mcp_deployment_client.py`; and
- `tests/scripts/test_direct_audio_deployment_proof.py`.

The child now writes a call-owned intermediate diagnostic, while the parent exclusively writes the
final operator diagnostic through the existing descriptor-bound
`mke.mcp_deployment_diagnostic.v1` authority. Valid child diagnostics retain their exact stage.
Missing or unpersisted child evidence maps to `child_diagnostic_unavailable`; successful-child
result rejection maps to `parent_result_validation`; and exact fixture source rejection maps to
`source_identity`. Diagnostic persistence failure has a distinct closed child exit status. The
public deployment aggregate remains exactly `schema_version`, `status`, `canonical`, and `failure`,
with `failure=mcp_failed`; no raw payload, private path, stderr, transcript, credential, token, or
secret is added.

TDD recorded `11 failed, 4 passed` at RED, `15 passed` at focused GREEN, and
`120 passed, 5 warnings` for the complete MCP client/deployment suites. The initial full suite
reported `3068 passed, 14 skipped, 5 warnings` plus 12 stale evaluation-source identity failures.
Identity-only commit `80f83181588710ff4b2b7faca5717465499adddd` mechanically refreshes the
16 validator-proven paths. Both the detached validation mirror and the actual worktree passed all
seven canonical validators. The focused artifact suite reported `191 passed, 5 warnings`;
feature/mirror bytes matched for all 16 paths; JSON path inventories and normalized semantic
projections were equal; metrics, results, diagnostics, thresholds, statuses, and verdicts were
unchanged; and E3-B remained byte-identical.

Targeted actual-diff re-review of
`c19eee0ab79a2f0df130235483f587d827145fd8..aca8057602c3491de2ff1bb923c7f6e10dc43cf2`
at reviewed HEAD `aca8057602c3491de2ff1bb923c7f6e10dc43cf2` returned
`CLEAN / ACCEPTED` with no Critical, Important, or Minor finding. Fresh verification reported
`120 passed, 5 warnings` for the complete MCP client/deployment suites, four-file Ruff passed,
repository Pyright reported `0 errors, 0 warnings, 0 informations`, and `git diff --check` passed.
All 16 identity paths remained byte-equal to the retained detached mirror. The semantic-equality
report has SHA-256
`c20df765f1d5c95224a464c71d2eb396827d814f530b5d93a8184c67cd66a878` and
`status=passed`.

Steps 6 and 7 remain accepted; Steps 8-10 remain incomplete and no new Step 8 authority has been
created. Every prior Step 8/Step 9 wheel, authorization, aggregate, diagnostic, and observation
remains historical evidence only. The real deployment-controller invocation count remains five
and retry count remains four; a sixth invocation did not occur. No manual MCP replay, model load,
ASR, provider or product execution, download, redistribution, production, accuracy, SLA, release,
or deployment claim is made.

## Circular Terminal Candidate Authority Repair — Clean / Accepted

The canonical receipt remains a closed historical artifact. Its static validator still requires
one exact candidate MKE wheel, the matching installed rows for Python 3.12 and Python 3.13, and all
existing internal cross-bindings. The deployment controller had additionally required the current
terminal candidate to equal that historical candidate's bytes, SHA-256, and candidate-inclusive
root digest. This created circular receipt replay authority after ordinary source changes even
though the accepted plan assigns current wheel identity to Step 8 and assigns external
dependency/license authority to the receipt.

Repair commit `0200089` changes only:

- `scripts/direct_audio_deployment_proof.py`; and
- `tests/scripts/test_direct_audio_deployment_proof.py`.

The repair preserves complete `validate_committed_receipt()` validation, the external 60-wheel
inventory, constraints, two interpreter cells, supervisor and fixture authority, and exact
external installed-distribution rows. It independently validates the fresh candidate's
distribution, version, filename tags, METADATA requirements, live lock projection, constraints,
two-cell candidate-aware root requirements, bytes, and SHA-256. Package-set projection preserves
the receipt's external rows and replaces only the historical candidate source identity with the
fresh candidate authority already bound by the authorization manifest, staging checks, and
installed identity. The serialized `mke.direct_audio_terminal_authorization.v1` schema and public
four-field deployment aggregate are unchanged.

The two original circular comparisons failed at RED and passed at GREEN. Seven structural
candidate-boundary cases then failed before their shared validator existed and passed after the
minimum implementation. Focused candidate tests reported `11 passed`; complete deployment-proof
and receipt-adjacency suites reported `329 passed, 5 warnings`; and the committed candidate
reported `3089 passed, 14 skipped, 5 warnings`. Ruff passed. Pyright reported
`0 errors, 0 warnings, 0 informations`. The offline build and `git diff --check` passed. Fresh
E1 through E3-E validation passed `7/7`, so no evaluation identity closure was created.

Descriptor-bootstrap static receipt validation passed with canonical payload SHA-256
`3dca3bc7737728ef49376f11d40e9611cf62552147840a0026b7ded5218a681a` and file SHA-256
`1fe3cd6fddd1bb07a949192c64fcf90ee2b9ac5fd22df1e8a334a5d446a611af`; the receipt bytes were not
changed or regenerated.

Targeted actual-diff re-review covered
`760bfdc4fbf7d965d0ca5bef9ab67d4a5e19ee06..ba4f8d59af544c78e77d2946230ce7542dd4a700`
at reviewed HEAD `ba4f8d59af544c78e77d2946230ce7542dd4a700` and returned
`CLEAN / ACCEPTED`, with no Critical, Important, or Minor finding. Independent review confirmed
complete `validate_committed_receipt()` validation; independent fresh-candidate
distribution/version/tag/METADATA/live-lock/constraints/two-cell-root validation; and fresh
bytes/SHA binding through `AuthorizationManifest`, staged-input validation, and installed
`RECORD` identity. The serialized authorization schema and public aggregate remain unchanged.
Fresh focused evidence reported `543 passed, 5 warnings`; Ruff passed; repository-authoritative
`uv run --frozen --no-sync pyright` reported `0 errors`; the receipt SHA-256 remained
`1fe3cd6fddd1bb07a949192c64fcf90ee2b9ac5fd22df1e8a334a5d446a611af`; and
`git diff --check` passed.

This repair is `CLEAN / ACCEPTED`. Steps 8-10 remain incomplete. Historical Step 8/Step 9 evidence
cannot serve as final authority. The real deployment-controller invocation and retry counts remain
five and four; a sixth invocation did not occur. No authorization-only execution, manual MCP
replay, model load, ASR, provider or product-path execution, download, redistribution, production,
accuracy, SLA, release, or deployment claim is made.

## MCP Module Startup Repair — Clean / Accepted

The sixth authorized terminal run failed closed at the MCP gate. Provider-free reproduction proved
that the direct module entry point returned success while emitting the standard `runpy` warning.
The warning was caused by the public proof import chain eagerly loading
`mke.proof.local_knowledge`, which loaded `mke.proof.mcp_deployment_client` before `python -m`
executed that target. The unchanged deployment-controller policy correctly treats any outer stderr
as failure; the repair does not add a warning allowlist or weaken that boundary.

Repair commit `8b903ba014b3b182e6887176d645495ba2c40e26` performs the minimum lazy import
inside the local-knowledge MCP flow. The existing public exports remain available, local-knowledge
proof behavior remains unchanged, and unknown or nonempty outer stderr remains fail closed.
Identity-only commit `c8581085afbec6279504422913ce850122a8c18d` mechanically refreshes the 16
validator-proven evaluation paths. Its semantic-equality report has SHA-256
`adacd1fc536de10d24d79bdc276cb12ad341bfe0a4a5d2a7be6910966eed408f`; all
normalized semantic projections are equal and E3-B is byte-identical.

Targeted actual-diff re-review covered
`2f2baa40d19dbf9f12f63001a6055e3f27aefbb8..c8581085afbec6279504422913ce850122a8c18d`
at reviewed HEAD `c8581085afbec6279504422913ce850122a8c18d` and returned `CLEAN`, with zero
Critical and zero Informational findings. Independent verification reported `returncode=0`, 2,404
stdout bytes, and zero stderr bytes for the direct isolated module help command. TDD reported
`2 failed, 1 passed` at RED and `3 passed, 5 warnings` at focused GREEN. The complete suite
reported `3092 passed, 14 skipped, 5 warnings`; Ruff passed; Pyright reported
`0 errors, 0 warnings, 0 informations`; `git diff --check` passed; and all seven canonical
validators passed.

Steps 6 and 7 remain accepted and complete. Step 8 is again the next incomplete gate; Steps 8-10
remain incomplete. All earlier Step 8 and Step 9 wheels, authorizations, aggregates, diagnostics,
observations, and related artifacts remain historical evidence only and cannot be reused as fresh
terminal authority. The historical real deployment-controller invocation count is six and the
retry count is five; a seventh invocation did not occur. This record makes no claim of real-ASR
success, accuracy, SLA, production readiness, cross-platform authority, external-binary
redistribution, release, or deployment.

## Next Gate And Non-Claims

Fresh Step 8 is the next incomplete gate and requires separate authorization. This record does not
claim that authorization-only validation was rerun, a manual MCP replay occurred, real ASR, model,
provider, or product-path execution occurred, external inputs were acquired, packages or native
binaries may be redistributed, or any push, PR, merge, release, deployment, production readiness,
accuracy, SLA, or cross-platform authority exists. The historical deployment-controller
invocations are not model, ASR, provider, or product success. The current real
deployment-controller invocation count is six and the retry count is five; a seventh invocation
did not occur.
