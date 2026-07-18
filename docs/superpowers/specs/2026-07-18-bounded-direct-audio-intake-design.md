# Bounded Direct Audio Intake Design

Status: authority-amended written design approved on 2026-07-18 for staged implementation
planning and full plan review. This document does not authorize implementation, dependency or
model acquisition, public claims, version publication, or deployment.

Planning baseline: `6dfc1882a78f23023e26018df7ec1d60adcd8e3e`.

Target release candidate: v0.1.4 after feature acceptance and a separate release closeout.

## Summary

MKE already compiles text-layer PDFs and short spoken MP4 files into active Publications with
page or timestamp `mke.evidence_ref.v1` provenance. It also exports complete active Libraries as
deterministic Markdown plus machine-verifiable Evidence sidecars. The remaining gap for the
approved local multimodal knowledge-compiler story is direct audio-only intake.

This design adds one bounded, owner-configured, local, cache-only direct-audio path:

```text
MP3 / WAV / M4A
  -> immutable source snapshot
  -> strict audio-v1 profile inspection
  -> cache-only faster-whisper
  -> timestamp Evidence
  -> Run / Publication
  -> Search / Ask / mke.evidence_ref.v1
  -> Compiled Library Export v2
  -> standalone Agent consumer
```

The feature reuses the existing transcription model, preparation, readiness, process, report,
Publication, Search/Ask, and Evidence authorities. It does not reinterpret an audio file as a
video, does not expand request-time model controls, and does not turn MKE into a general audio
platform.

## Product Decision

The supported product contract is:

> An operator can explicitly configure MKE's existing cache-only faster-whisper runtime and ingest
> a bounded local MP3, WAV, or M4A file through Python, CLI, or the existing stdio MCP `ingest_file`
> tool. A successful Run publishes timestamp Evidence into the same active Library and can be
> exported through a versioned complete-Library contract without weakening source identity or
> downstream provenance.

This is an additive local multimodal compiler capability. Search and evidence-only Ask remain
consumer projections, not the product's primary authority or a newly promoted RAG runtime.

## Why This Stage

- The existing `faster-whisper` stack already accepts audio paths and emits timestamped segments.
- MKE already owns cache-only model preparation, exact revision readiness, bounded subprocesses,
  timestamp Evidence, transcript reports, installed-wheel proof patterns, and external consumers.
- Audio-only input is common in personal and small-team knowledge workflows: voice notes and
  bounded clips or excerpts from meetings, interviews, lectures, and downloaded spoken material.
- The feature completes the public PDF + audio + video compiler story before selective OCR, while
  keeping runtime and dependency growth small.
- The work is independently useful for local Agent consumption and produces a stronger engineering
  story than another retrieval-strategy experiment without new benchmark evidence.

## Existing Foundations

The implementation must reuse these current authorities:

- `KnowledgeEngine`, Run states, latest-request-wins Source generations, and atomic Publication
  activation;
- candidate-before-publication visibility and active-only Search/Ask;
- integer-millisecond timestamp locators and `mke.evidence_ref.v1`;
- `TranscriptionProvenance` and `TranscriptIntakeReport`;
- `FasterWhisperTranscriptionConfig`, exact model revision, explicit prepare, read-only doctor,
  owner-selected device/compute/language, and cache-only normal execution;
- `ActiveProcessController`, bounded `shell=False` subprocess execution, timeout, cancellation, and
  descendant cleanup;
- existing optional `[transcription]` dependencies and lockfile;
- SQLite's generic `assets.media_type` storage and transcript report table; and
- deterministic Compiled Library Export and standalone consumer patterns.

The following existing contracts remain historical and byte-compatible:

- `mke.video_transcript.v1`;
- MP4/H.264/AAC short-video profile;
- existing video extractor fingerprints and required stages;
- `ingest_video`, `video_ingest_failed`, video fixtures, product proof, and deployment proof;
- `mke.compiled_library_export.v1`, `mke.compiled_markdown.v1`, and the v1 standalone consumer;
- the current read-only MCP v1 tools and their frozen safe-cause fixture.

## Goals

1. Support a strict direct-audio profile for MP3, WAV, and M4A up to 15 minutes and 100 MiB.
2. Bind Source SHA-256 to the exact bytes inspected and transcribed.
3. Reuse the pinned cache-only faster-whisper owner policy with no normal-run download path.
4. Publish ordered timestamp Evidence only after complete transcript, manifest, report, and
   lifecycle validation.
5. Expose the capability through one canonical Python dispatcher, CLI `ingest`, and the existing
   stdio MCP `ingest_file(path)` tool without request-time provider controls.
6. Preserve all existing PDF and video behavior.
7. Export a complete mixed PDF/video/audio Library through a new closed v2 export contract while
   preserving v1 compatibility.
8. Prove all three formats through redistribution-safe fixtures, installed-wheel Python 3.12/3.13
   environments, real cache-only ASR, CLI/MCP, Search/Ask, export, and an independent consumer.
9. Record dependency, bundled-media-library, model, fixture, platform, and claim boundaries before
   v0.1.4 publication.

## Non-Goals

This stage does not add:

- diarization, speaker identity, speaker count, or speaker-attributed Evidence;
- streaming, live microphone capture, partial transcript publication, or incremental Evidence;
- full-length meetings, interviews, lectures, or other long-form recordings beyond the fixed
  limits;
- long-audio workers, chunking, background queues, resume, streaming, or files beyond the fixed
  limits;
- arbitrary WAV/M4A codecs, arbitrary containers, playlists, subtitle tracks, or media conversion;
- GPU scheduling, multi-device orchestration, CUDA support claims, or cross-platform performance
  claims;
- cloud ASR, hosted fallback, source upload, AutoDL orchestration, endpoint/token controls, or
  implicit network access;
- request-time provider, model, revision, cache, device, language, download, URL, or command
  controls in MCP;
- a generic audio plugin framework;
- changes to chunking, lexical ranking, dense retrieval, RRF, reranking, or answer generation;
- an HTTP service, workspace UI, multi-tenancy, RBAC, review authority, freshness policy, or
  business-decision authority;
- LLM Wiki as a dependency or Evidence authority; or
- a production SLA, arbitrary-language quality guarantee, real-user adoption, or deployment claim.

## Supported Audio-v1 Profile

The suffix chooses the expected profile; inspected bytes remain the authority. Suffix matching is
case-insensitive, while display name casing is preserved.

| Suffix | Canonical MKE media type | Required semantic profile |
|---|---|---|
| `.mp3` | `audio/mpeg` | MPEG audio container with MPEG Layer III audio |
| `.wav` | `audio/wav` | RIFF/WAVE with signed 16-bit little-endian PCM |
| `.m4a` | `audio/mp4` | ISO Base Media/M4A container with AAC-LC audio |

All formats additionally require:

- exactly one decodable audio stream;
- zero video, subtitle, data, or attachment streams;
- one or two channels;
- sample rate from 8,000 through 48,000 Hz inclusive;
- `0 < input_bytes <= 100 * 1024 * 1024`;
- `0 < media_duration_ms <= 900_000`;
- no more than 10,000 accepted transcript segments;
- ordered, finite, non-overlapping integer-millisecond segment ranges within media duration; and
- non-empty normalized UTF-8 transcript text within existing Evidence bounds.

The project validates normalized container/codec semantics rather than a single decoder
implementation name. The closed v1 normalizer accepts only:

- MP3 container tokens containing `mp3`, with codec alias `mp3` or `mp3float`, normalized to
  container `mp3` and codec `mp3`;
- WAV container tokens containing `wav`, with codec `pcm_s16le`, normalized to container `wav` and
  codec `pcm_s16le`; and
- ISO-BMFF format tokens containing both `mp4` and `m4a`, with codec `aac` and the locked PyAV
  profile normalized to AAC Low Complexity, normalized to container `m4a` and codec `aac`.

The committed fixture inventory freezes the exact observed PyAV format-token set and, when PyAV
exposes it, the ISO-BMFF major/compatible-brand metadata. Missing required tokens, unknown aliases,
an unknown AAC profile, or any non-AAC-LC profile fails closed until separately reviewed.

An extension/container/codec mismatch, unknown duration, multiple audio streams, any video stream,
unsupported channel or sample-rate profile, corrupt media, or over-limit input is unsupported. MKE
does not transcode it into the profile.

## User Journey

### Verify the deterministic product path first

Run the model-free proof before preparing a real model or ingesting operator material:

```bash
UV_OFFLINE=1 uv run mke proof direct-audio --json
```

This one-command path uses committed redistribution-safe fixtures and a deterministic provider to
exercise inspection, Publication, Search/Ask, timestamp Evidence, Export v2, the independent
consumer, and cleanup. It neither constructs a real ASR model nor permits a download. Passing it
proves the product wiring, not transcript quality or readiness of the operator's model cache.

### Prepare once

The existing explicit preparation command remains the only download-capable path:

```bash
uv sync --locked --extra transcription
uv run mke transcription prepare \
  --allow-model-download \
  --model small \
  --model-revision 536b0662742c02347bc0e980a01041f333bce120 \
  --model-cache "$MKE_MODEL_CACHE" \
  --json
```

No audio-specific model or second cache is introduced.

### Check readiness

```bash
HF_HUB_OFFLINE=1 uv run mke transcription doctor \
  --model small \
  --model-revision 536b0662742c02347bc0e980a01041f333bce120 \
  --model-cache "$MKE_MODEL_CACHE" \
  --json
```

Doctor remains read-only and does not open a Library database or create a Run.

### Ingest

```bash
HF_HUB_OFFLINE=1 uv run mke \
  --db .tmp/mke.sqlite \
  ingest interview-excerpt.m4a \
  --transcript-provider faster-whisper \
  --model-cache "$MKE_MODEL_CACHE" \
  --json
```

The same owner configuration applies to MP3, WAV, M4A, and the existing supported MP4 path. The
default sidecar owner does not silently switch to faster-whisper. Direct audio presented to a
sidecar owner fails before Source/Run creation with a stable next step to configure the
faster-whisper owner.

### Consume and export

Search, Ask, and MCP return the existing timestamp `mke.evidence_ref.v1`. A Library containing
direct audio is exported explicitly with the v2 contract:

```bash
uv run mke --db .tmp/mke.sqlite library export \
  --format-version v2 \
  --output .tmp/compiled-library \
  --json
```

The current command without `--format-version` remains v1 for backward compatibility. The first
real-input path is therefore explicit and sequential: model-free proof, separately authorized
preparation when needed, read-only doctor, bounded ingest, Search/Ask, and explicit v2 export.

## Canonical Dispatch

Add a canonical application dispatcher:

```text
KnowledgeEngine.ingest_file(path)
  .pdf -> ingest_pdf
  .mp4 -> ingest_video
  .mp3/.wav/.m4a -> ingest_audio
  other -> unsupported media
```

CLI `mke ingest` and MCP `ingest_file(path)` must call the same classifier and application
boundary. `KnowledgeEngine.ingest_pdf`, `ingest_video`, and the new `ingest_audio` remain available
as explicit facades. The dispatcher prevents suffix lists and media mappings from drifting across
Python, CLI, and MCP.

The MCP tool inventory and input schema remain unchanged. `ingest_file` still accepts only `path`;
provider/model/cache/device/language/download controls remain owner startup configuration.

The interface must preserve the operator's original path spelling through final-component symlink
rejection and public presentation. Today MCP resolves the path before dispatch; the implementation
must first perform `lstat` on the unresolved candidate, reject a symlinked final component, then
resolve and prove allowed-root containment. All later I/O receives the containment-validated
resolved target plus bound identity, or an equivalent descriptor-backed authority; it must never
reopen an unresolved parent path after containment. Parent-symlink retarget races must fail for
audio, PDF, and video without reading outside the allowed root.

## Immutable Source And Canonical Media Identity

The audio path must not hash one file and transcribe another.

Before Source or Run creation:

1. resolve the operator path under the existing interface authority;
2. reject missing, empty, non-regular, symlinked, unsupported-suffix, and over-size input;
3. require the faster-whisper owner and a successful lightweight preflight that does not construct
   a model;
4. acquire the existing owner admission lease before any snapshot, child, or model work;
5. open with no-follow and capture file identity where supported;
6. copy bounded bytes into a private call-owned snapshot using the same descriptor;
7. compute the copied snapshot SHA-256 and byte count, rewind the still-open source descriptor, and
   require a second bounded full-read digest to match;
8. require unchanged source device, inode, mode, size, `mtime_ns`, and `ctime_ns`, then atomically
   seal the private snapshot;
9. inspect the snapshot with locked PyAV inside a receipt-backed memory- and
   process-group-bounded package-owned child before constructing the model;
10. map the validated semantic profile to the canonical MKE media type; and
11. process and transcribe only the sealed snapshot.

The application validates the in-memory transcript, manifest, Evidence, and report before deleting
the snapshot. Snapshot cleanup must succeed before candidate persistence and Publication
activation. A cleanup failure returns a stable failure, leaves the Run failed if one exists, and
does not change the active Publication.

### Digest-level media-type authority

SQLite currently deduplicates Asset rows by SHA-256. The implementation must therefore compare a
requested canonical media type with any existing Asset media type for the same digest. A mismatch
fails closed; it must never silently reuse the first value or rewrite historical media identity.

Preflight occurs before `ensure_source`, so a newly rejected audio input cannot create an
incorrectly typed Asset. Existing inconsistent databases are not automatically migrated or
repaired by this feature. They return a stable repair/fresh-library next step and require a
separate operator decision.

## Project-Owned Audio Contracts

### Domain values

Add project-owned audio values with strict frozen validation:

- `AudioMediaInfo`: canonical container, canonical audio codec, channel count, sample rate, and
  positive duration in milliseconds;
- `ParsedAudioTranscript`: `AudioMediaInfo`, ordered timestamp segments, and optional
  `TranscriptionProvenance`;
- `AudioTranscriptExtractionResult`: parsed transcript, extractor fingerprint, and optional
  `TranscriptIntakeReport`;
- `AudioIngestError`: stable problem, next step, and optional Run ID.

Timestamp segment validation and `TranscriptIntakeReport` construction should share existing
helpers. Existing public video symbols remain import-compatible and retain their exact behavior;
implementation may extract shared private validation but must not rename or reinterpret the video
wire contract.

### Audio transcript wire protocol

The package-owned audio child emits one closed compact UTF-8 JSON object:

```json
{
  "format": "mke.audio_transcript.v1",
  "media": {
    "audio_codec": "aac",
    "channels": 1,
    "container": "m4a",
    "duration_ms": 1234,
    "sample_rate_hz": 16000
  },
  "segments": [
    {
      "end_ms": 1200,
      "start_ms": 0,
      "text": "bounded synthetic speech"
    }
  ],
  "transcription": {
    "compute_type": "int8",
    "detected_language": "en",
    "device": "cpu",
    "language": "auto",
    "library_version": "1.2.1",
    "model": "small",
    "model_revision": "536b0662742c02347bc0e980a01041f333bce120",
    "model_source": "cache",
    "provider": "faster-whisper",
    "transcription_duration_ms": 321
  }
}
```

The object is closed. Unknown fields, missing fields, non-finite values, invalid UTF-8, duplicate,
overlapping, out-of-order or out-of-duration segments, excessive output, and mismatched media facts
fail closed. Provider library objects never cross the adapter boundary.

`mke.video_transcript.v1` stays byte- and behavior-compatible. Direct audio does not use or extend
the existing deterministic video sidecar schema.

### Extractor fingerprint and RunManifest

Add:

```text
REQUIRED_AUDIO_STAGES = {"audio_transcription", "candidate_evidence"}
faster-whisper-audio-v1:<64 lowercase hex>
```

The audio fingerprint digest binds the same canonical provider, model, exact revision, library,
device, compute type, and language identity as the existing video fingerprint. Media bytes remain
bound separately by the RunManifest Asset SHA-256. The new namespace prevents one fingerprint
from ambiguously selecting both video and audio required stages.

Manifest validation requires:

- exact audio stages without duplicates;
- timestamp locators only;
- the new recognized audio fingerprint;
- evidence count, Asset digest, and segment/report consistency; and
- a successful `TranscriptIntakeReport` for every faster-whisper audio Publication.

The existing video fingerprint namespace and required stages do not change.

## First-Party Runtime Boundary

The first-party implementation may share model resolution, model construction, transcription,
segment normalization, process control, error-code mapping, and report building with video. It
must add a media-specific package-owned child entry point that emits only
`mke.audio_transcript.v1`.

The runtime contract remains:

- `faster-whisper>=1.2.1,<2` under the existing `[transcription]` extra;
- exact `Systran/faster-whisper-small` revision already owned by configuration;
- normal execution passes a resolved local model snapshot and `local_files_only=True`;
- `HF_HUB_OFFLINE=1` and a network canary prove no runtime network access;
- the segment generator is fully materialized before success;
- lightweight request preflight checks typed configuration, optional dependency availability,
  static profile grammar, and prepared cache completeness without constructing `WhisperModel`;
- request-time model construction occurs only after admission;
- model resolution, media inspection, transcription, stdout, stderr, memory, time, cancellation,
  process group, parent wait, and descendant cleanup remain bounded by the accepted PR A platform
  cell; timeout and output caps alone are not native-parser memory containment;
- no implicit cache location, fallback identifier, URL, token, or SDK exception enters public
  output.

The existing adapter exit-code values remain stable. Media-specific application composition maps a
shared adapter failure to `video_ingest_failed` or `audio_ingest_failed` without changing the
numeric child protocol.

## Lifecycle And Publication

The success path is:

```text
containment-validated path authority and lightweight owner preflight
  -> acquire existing bounded owner admission lease
  -> immutable snapshot + SHA-256
  -> bounded audio-v1 inspection child
  -> ensure Source with canonical media type
  -> create Run -> RUNNING
  -> cache-only child transcription
  -> strict audio protocol parse
  -> validate provenance, report, fingerprint and timestamp Evidence
  -> clean call-owned snapshot and release admission lease
  -> persist validated candidate
  -> atomic Publication + transcript report + active pointer + FTS + PUBLISHED
```

The current latest-request-wins and transactional activation authority remains unchanged. A
candidate is not searchable. The transcript report becomes observable only with the successful
Publication transaction.

Failure behavior:

- a preflight or readiness failure creates no Source and no Run;
- an admission rejection creates no snapshot, Source, Run, child, or model-factory call;
- a post-Run adapter, schema, manifest, cancellation, storage, or cleanup failure produces a
  failed/interrupted Run with no active-Publication change;
- a superseded Run remains superseded and cannot publish;
- a partial transcript, empty transcript, incomplete report, timeout, or unknown provider output
  never reaches candidate persistence;
- retrying or ingesting a new generation does not remove the previous active Publication until a
  complete replacement publishes.

## Public Error Contract

The stable problem categories are:

- `input_path_rejected` for existing allowed-root and path-resolution failures;
- `unsupported_media_type` for suffixes outside `.pdf`, `.mp4`, `.mp3`, `.wav`, `.m4a`;
- `transcription_not_ready` for owner dependency/cache/profile readiness failure before Run;
- `transcription_busy` when the existing bounded owner admission authority cannot accept another
  direct-audio operation before snapshot/model work;
- `audio_ingest_failed` for a routed direct-audio profile, extraction, validation, lifecycle, or
  storage failure.

`run_id` is present only after Run creation. Every failure reports
`active_publication_impact="unchanged"`.

New audio-specific causes form a closed command-local safe set for CLI and the legacy ingest tool.
Do not add them to the shared `_ALLOWLISTED_CAUSES`, `is_public_error_cause()`, versioned read-tool
schemas, or frozen consumer source-pack fixture. The serializer may accept an explicit
operation-local safe-cause set while existing callers retain their exact behavior. Existing generic
transcription causes may be reused where their meaning is unchanged.

The pre-Run public matrix is closed:

| Problem | Safe cause | Next step |
|---|---|---|
| `input_path_rejected` | existing empty/missing/not-file/outside-root/resolve causes, or `input path must not be a symlink` | `choose_file_under_allowed_root` |
| `unsupported_media_type` | `supported suffixes are .pdf, .mp4, .mp3, .wav, and .m4a` | `choose_supported_file` |
| `transcription_not_ready` | `transcription optional dependency is not installed` | `install_transcription_extra` |
| `transcription_not_ready` | `configured transcription model is not cached` | `run_transcription_prepare` |
| `transcription_not_ready` | `transcription model resolution failed` | `check_model_configuration` |
| `transcription_not_ready` | `transcription device or compute profile is unsupported` | `check_model_configuration` |
| `transcription_not_ready` | `direct audio requires faster-whisper owner` | `configure_faster_whisper_owner` |
| `transcription_busy` | `direct audio owner capacity is busy` | `retry_when_owner_ready` |
| `audio_ingest_failed` | `audio profile is unsupported` | `choose_supported_file` |
| `audio_ingest_failed` | `audio input exceeds supported limits` | `choose_smaller_file` |
| `audio_ingest_failed` | `audio source identity changed during intake` | `retry_with_stable_file` |
| `audio_ingest_failed` | `audio inspection timed out` | `retry_with_supported_file` |
| `audio_ingest_failed` | `audio inspection failed` | `choose_supported_file` |
| `audio_ingest_failed` | `audio intake cleanup failed` | `check_server_logs` |

All rows above omit `run_id`. Once a Run exists, the audio child maps every existing numeric exit
code to `problem=audio_ingest_failed` with that Run ID:

| Exit | Safe cause | Next step |
|---:|---|---|
| 20 | `transcription optional dependency is not installed` | `install_transcription_extra` |
| 21 | `configured transcription model is not cached` | `run_transcription_prepare` |
| 22 | `transcription model resolution failed` | `check_model_configuration` |
| 30 | `audio profile is unsupported` | `choose_supported_file` |
| 31 | `audio file must contain one audio stream` | `choose_supported_file` |
| 32 | `audio input exceeds supported limits` | `choose_smaller_file` |
| 40 | `transcription failed` | `check_server_logs` |
| 41 | `audio transcript must contain at least one segment` | `check_audio` |
| 50 | `audio transcript schema validation failed` | `check_server_logs` |

Controller failures after Run creation are also closed: source replacement or snapshot identity
drift maps to `audio source identity changed during intake / retry_with_stable_file`; cleanup
failure maps to `audio intake cleanup failed / check_server_logs`; manifest, persistence, or
activation failure maps to `audio publication failed / retry_when_owner_ready`. Unknown internal
failures use the existing redacted cause with `fix_input_or_retry`. Every post-Run row includes
`run_id` and preserves `active_publication_impact=unchanged`.

Public causes must not expose an operator path, cache path, child argv, provider stderr, Python
exception, model-host detail, hostname, token, or raw media metadata.

## Compiled Library Export v2

Direct audio cannot be silently added to the closed v1 manifest or Markdown enum. The capability
direction is approved: v1 remains byte-compatible, v1 fails closed rather than silently omitting
an active audio Source, and an explicit v2 represents the complete mixed Library. The intended
version family is:

- `mke.compiled_library_export.v2`;
- `mke.compiled_markdown.v2`;
- `mke.compiled_library_export_response.v2`.

`mke.evidence_ref.v1` and `mke.active_publication_observation.v1` remain unchanged.

The exact v2 closed response shape, manifest and Markdown fields, source matrix, and independent
consumer invariants are intentionally not frozen by this design alone. They must be reconciled
against accepted downstream evidence from the separate LLM Wiki v1 compatibility work before PR C
implements them. This sequencing prevents a speculative schema from becoming authority before a
real consumer has exercised v1, while preserving the approved requirement that a mixed Library
must never lose an audio Source silently.

At the start of PR C, the implementation controller must read the accepted LLM Wiki compatibility
review and perform one bounded schema reconciliation checkpoint. The checkpoint records which v1
fields and Markdown boundaries the downstream proof actually consumed, which remain unchanged in
v2, and which additive v2 fields are necessary for audio completeness. Only a closed shape backed
by that evidence may be implemented and frozen. Any requested shape change beyond additive audio
completeness returns to design authority.

### Compatibility behavior

- `mke library export` with no format flag continues to produce exact v1 output for compatible
  PDF/video-only Libraries.
- `--format-version v1` is the explicit equivalent of the current behavior.
- v1 fails closed when the complete active snapshot contains any media type it cannot represent;
  it never omits an audio Publication or adjusts counts.
- `--format-version v2` exports the complete active PDF/video/audio snapshot.
- The reconciled v2 response identifies the exact manifest and Markdown schema versions.
- Existing v1 validators, golden bytes, proof, workflow, and standalone consumer remain valid.
- A new independent v2 consumer accepts only the reconciled closed v2 contract and rejects v1,
  unknown versions, unknown MIME values, or mixed invalid authority.

### v2 source semantics

The candidate v2 semantics retain v1 provenance authority, deterministic ordering, count and byte
budgets, and the exact active-Publication completeness rule. The reconciliation checkpoint decides
the final closed top-level, source-entry, and Markdown field sets. At minimum, the implemented v2
must represent this media/stage authority without weakening current v1 acceptance:

| Media type | Locator | Required stages | Extractor family |
|---|---|---|---|
| `application/pdf` | page | `pdf_text_extraction` + `candidate_evidence` | `builtin-pdf-text-v1` or `pymupdf-text-v1` |
| `application/pdf` | page | `pdf_ocr_extraction` + `candidate_evidence` | current comparison-only `pdf-ocr-eval-v1:<digest>` |
| `video/mp4` | timestamp_ms | video_transcription + candidate_evidence | existing video fingerprints |
| `audio/mpeg` | timestamp_ms | audio_transcription + candidate_evidence | audio faster-whisper fingerprint |
| `audio/wav` | timestamp_ms | audio_transcription + candidate_evidence | audio faster-whisper fingerprint |
| `audio/mp4` | timestamp_ms | audio_transcription + candidate_evidence | audio faster-whisper fingerprint |

The candidate Markdown v2 direction keeps deterministic metadata ordering and page/timestamp
headings. Whether the exact v1 field list is reused or additively amended is decided only by the
checkpoint. Audio Evidence continues to use an unambiguous timestamp boundary, and no raw media
bytes or transcript report are copied into the export.

The comparison-only PDF OCR row preserves the exact validation surface that v1 already accepts; it
does not promote Phase 0 OCR into production. Any later production OCR fingerprint or stage is a
closed-contract amendment and cannot be admitted to v2 implicitly. LLM Wiki remains an external
downstream view, never an MKE dependency, runtime component, or Evidence authority.

## Dependency, Binary, Fixture, And License Boundary

No new Python dependency is approved. The implementation reuses the locked `[transcription]`
surface, currently including faster-whisper, PyAV, CTranslate2, and huggingface-hub.

PR A is a feasibility gate before any direct-audio foundation or activation work. It must establish:

- ordinary-pip resolution and import must pass for supported Python 3.12 and 3.13 environments;
- exact locked external dependency versions, PyAV wheel bytes, installed distributions, validation
  platform, canonical lock-derived external constraints and wheelhouse manifest, linked or bundled
  FFmpeg components, and fixture identities must be recorded in a public-safe dependency/license
  receipt;
- the three audio profiles must be decoded by the installed PyAV wheel, not inferred from package
  metadata;
- source-build or system-FFmpeg installation is not claimed unless separately proved;
- the actual PyAV binary wheels used for supported proof environments must receive a transitive
  bundled-library and license audit;
- FFmpeg and other bundled libraries, enabled components, licenses, and required notices must be
  documented from the exact wheel/runtime evidence rather than treating the PyAV package's
  BSD-3-Clause metadata as the complete binary distribution license;
- fixture source, generation, redistribution permission, notices, exact bytes, and profile authority
  must be complete;
- each accepted platform cell must prove the exact child memory-ceiling and process-group cleanup
  mechanisms used before native PyAV/FFmpeg parsing; an unavailable or unproved mechanism is an
  unsupported/failed cell, not a timeout-only fallback;
- model source, exact revision, model-card license, model tree digest, and cache-only authority must
  remain documented for the later PR C proof; and
- no model weights or operator cache files enter Git, sdist, wheel, or Release assets.

The PR A receipt binds the external dependency set, canonical constraints and wheelhouse manifest,
PyAV wheel/runtime, linked or bundled FFmpeg components, licenses, notices, fixture identities,
validation platform, and child-containment authority. It does not bind an MKE source commit or MKE
wheel. Ordinary later product or documentation commits therefore do not invalidate it. Refresh it
only when an external dependency or constraints, prepared wheelhouse, PyAV wheel, platform,
containment mechanism, or fixture authority changes.

Any unresolved license, notice, fixture redistribution, or binary-component obligation is a
no-go hard stop: PR A cannot be accepted and PR B cannot begin. Acquisition of packages, wheels,
models, or external artifacts remains separately authorized and is not implied by this design.

PR C owns a distinct terminal installed proof. That proof binds a fresh final MKE wheel, the
accepted PR A receipt digest, the actual installed package set, and the prepared model tree. It
does not regenerate the complete PR A license analysis merely because tracked MKE source or docs
changed.

## Fixtures

Commit one short redistribution-safe synthetic speech source in each supported format. Each
fixture record must include:

- source speech/voice provenance and redistribution permission;
- deterministic generation or conversion command;
- suffix, canonical media type, container, codec, channels, sample rate, duration, bytes, and
  SHA-256;
- the relationship among the three encodings;
- confirmation that no private recording or personal voice is used; and
- a statement that keyword-level proof is not a general quality benchmark.

Fixture generation may use a maintainer tool such as FFmpeg, but normal runtime and required test
execution must not require a system `ffmpeg` command.

Negative fixtures or in-memory mutations must cover wrong extension, corrupt header, unsupported
WAV codec, non-AAC M4A, multiple audio streams, video stream, unknown/zero/over-limit duration,
unsupported channel/sample-rate profile, empty transcript, invalid UTF-8, excessive output,
segment drift, parent-symlink retarget, path replacement, same-inode same-size mutation during
copy, and digest/media-type mismatch.

## Proof Strategy

### Model-free required tests

Required CI remains model-free and offline. It must cover:

- canonical dispatcher equality across Python, CLI, and MCP;
- exact suffix/MIME/profile matrix and negative cases;
- immutable snapshot, TOCTOU, cleanup, cancellation, and Asset media-type drift;
- allowed-root parent-symlink retarget, same-inode same-size mutation, admission-before-model, and
  receipt-backed native child memory/process-group containment;
- audio DTO, wire schema, fingerprint, required stages, manifest, report, and timestamp Evidence;
- Run/Publication atomicity, failure isolation, supersession, Search, Ask, and portable EvidenceRef;
- existing PDF/video regression contracts;
- v1 export byte compatibility and strict failure on audio;
- v2 mixed PDF/video/audio golden bytes, deterministic repeat export, copy portability, and
  standalone tamper rejection;
- CLI/MCP exact schemas, command-local errors, redaction, and no request-time provider controls;
- documentation and presentation overclaim rejection.

### Installed dependency proof

Using the same MKE wheel in fresh Python 3.12 and 3.13 environments:

- install the locked transcription extra with ordinary pip semantics;
- require exact accepted PR A constraints and wheelhouse-manifest digests, then run `pip check`,
  package identity, dependency inventory, and wheel-byte validation;
- inspect/decode the three committed formats offline through the installed PyAV boundary;
- prove empty-cache doctor is `not_ready` and does not write an implicit cache or access network;
- verify the package-owned audio child protocol with fake model execution; and
- emit a closed public-safe aggregate without local interpreter or cache paths.

### Real cache-only ASR proof

On the explicitly supported local platform and exact prepared model snapshot, build one candidate
wheel and use only its installed commands/modules to:

1. prove doctor `ready` and network denial;
2. ingest MP3, WAV, and M4A through the canonical Python/CLI path;
3. ingest at least one format through real stdio MCP `ingest_file(path)` using the official SDK;
4. observe published Runs and complete transcript reports;
5. Search and Ask for a stable expected keyword without requiring exact full-transcript equality;
6. validate exact ordered timestamp EvidenceRefs and Source byte fingerprints;
7. export the complete Library as v2;
8. validate it with a standalone consumer that imports neither MKE, Pydantic, nor SQLite;
9. copy the export to another root and revalidate without path rewriting;
10. prove active Publication, network, model/cache, output bounds, and cleanup invariants; and
11. emit one closed public-safe aggregate bound to wheel, package set, model tree, fixture, export,
    and consumer identities.

The real proof records elapsed time and peak RSS as observations only. It does not set a
production SLA or claim all platforms.

## CI And Evaluation Identity

- Existing Python 3.12/3.13 matrix, Ruff, Pyright, build, CodeQL, consumer source-pack, and compiled
  export proof remain required.
- Add a dedicated model-free direct-audio contract/proof job only if the ordinary matrix cannot
  provide clear bounded evidence without duplication.
- Do not download models in required GitHub Actions.
- Any workflow timeout must be evidence-based; do not add conservative short job limits.
- Production, documentation, workflow, dependency, or fixture changes that participate in frozen
  retrieval evaluation identity require the existing mechanical-only identity transaction.
  Normalized observations, results, metrics, thresholds, gates, diagnostics, candidate, status,
  and verdict must remain unchanged.
- Evaluation identity refresh is provenance maintenance, not retrieval promotion.

## Documentation And ADR

Add `docs/decisions/0011-bounded-direct-audio-intake.md`. It authorizes bounded direct audio and
supersedes only the earlier audio-only deferral. Historical ADRs remain unchanged as records of
their original scope.

PR C evaluates and updates at least:

- `README.md` and `README_CN.md`;
- architecture explanation and documentation index;
- CLI, MCP, contract, and Compiled Library Export references;
- local transcription and export how-tos;
- getting-started or tutorial flow where direct audio is relevant;
- dependency/license and third-party notice documentation;
- product proof and release verification documentation;
- the feature spec, implementation plan, and implementation review; and
- presentation-audit rules that reject arbitrary codec, long-audio, automatic download, cloud,
  cross-platform, performance, deployment, adoption, and SLA overclaims.

The accepted LLM Wiki compatibility evidence may be referenced as a downstream consumer proof only
after its independent plan succeeds. LLM Wiki remains outside MKE runtime and Evidence authority.

## Staged Delivery Shape

Implementation is divided into three ordered PRs plus a separately authorized release closeout.
Each PR is independently reviewable and must satisfy its own exit gate.

### PR A — Direct-audio feasibility and license evidence

PR A contains only redistribution-safe synthetic fixtures, exact package/PyAV wheel and linked or
bundled FFmpeg component inventory, license/notice/fixture-provenance receipt generation and
validation, focused tests, and necessary public-neutral reference evidence. It does not modify
`src/mke`, add a public runtime, CLI/MCP route, Export schema, or product capability claim.

PR A may proceed in parallel with the independent LLM Wiki compatibility docs/evidence PR because
it does not write README or export shared surfaces. Any unresolved license, notice, fixture
redistribution, or binary-component obligation produces a no-go hard stop. No dependency, wheel,
model, fixture, or other external-artifact acquisition is authorized by this stage.

### PR B — Internal direct-audio foundation

PR B starts only after PR A is accepted and merged. It owns project-defined audio domain and wire
contracts, descriptor-bound immutable snapshotting, strict profile inspection, Asset media-type
authority, the cache-only audio child/provider, internal adapter/storage contracts, necessary video
compatibility regressions, and model-free tests.

PR B does not activate an application user journey. It adds no canonical public dispatcher,
CLI/MCP audio route, Export v2, public capability documentation or claim, real-provider proof, or
release proof. Runtime composition that would expose direct audio publicly moves to PR C. PR B need
not wait for LLM Wiki compatibility because it neither freezes Export v2 nor edits README/export
documentation, but it cannot run in parallel with PR A or bypass the license gate.

### PR C — Public activation, Export v2, and terminal proof

PR C starts only after PR A, PR B, and the independent LLM Wiki compatibility docs/evidence PR are
all accepted and merged. It owns the application lifecycle, canonical
`KnowledgeEngine.ingest_file` dispatcher, CLI/stdio MCP audio route, operation-local errors, the
bounded Export v2 reconciliation checkpoint and implementation, independent consumer, model-free
product proof, same-wheel installed proof, real cache-only provider proof, CI, ADR and public docs,
presentation audit, conditional evaluation identity closure, whole-branch review, and terminal
verification.

After PR C merges, a separate release-closeout PR and separate authorization own the v0.1.4
version, tag, GitHub Release, archive smoke, registry publication, deployment, and post-release
claims.

## Success Criteria

The feature is valid-positive only when all of the following are true:

- all three exact audio-v1 profiles pass byte inspection and real cache-only transcription;
- Source SHA-256 binds the exact inspected/transcribed bytes;
- the canonical media type is stable and digest-level MIME drift fails closed;
- every successful Run has the exact audio stages, fingerprint, transcript report, and ordered
  timestamp Evidence;
- Python, CLI, and MCP use the same dispatcher and owner authority;
- no request can enable download, choose provider/model/cache, or upload source content;
- failed, cancelled, partial, over-limit, unsupported, or cleanup-failed work does not change the
  active Publication;
- PDF and video contracts remain compatible;
- v1 export and consumer remain compatible;
- v2 exports the complete mixed Library and passes an independent installed-wheel consumer;
- Python 3.12/3.13 package evidence, exact local real proof, network denial, model/cache authority,
  and cleanup all pass;
- fixture, dependency, bundled-library, model, and license provenance are complete;
- full repository gates and canonical evaluation validators pass; and
- public docs make only the bounded local direct-audio claim.

## Kill Or Defer Criteria

Do not publish the v0.1.4 capability if any of these remains true:

- an accepted format cannot be distinguished from unsupported content before model construction;
- Source fingerprint can diverge from inspected or transcribed bytes;
- same-digest media-type drift can be silently accepted;
- cache-only execution or network denial cannot be enforced;
- any failure can expose partial Evidence or change the active Publication;
- the v2 export cannot represent every active audio Publication exactly once;
- ordinary Python 3.12/3.13 installation breaks a supported extra or existing proof;
- bundled FFmpeg/transitive license and notice obligations are unresolved;
- the real installed-wheel path cannot return exact timestamp Evidence through CLI/MCP and the
  external consumer; or
- the measured local resource envelope is unsuitable for the approved bounded profile.

A valid-negative result leaves v0.1.3 intact, documents the exact blocker, and does not weaken
existing video, export, or Evidence contracts.

## Claim Boundary

After successful PR C merge and separately authorized v0.1.4 publication, MKE may claim:

> Bounded local voice notes and clips or excerpts from meetings, interviews, lectures, and other
> downloaded spoken material, when encoded as the supported MP3, WAV/PCM, or M4A/AAC profiles, can
> be transcribed through an explicitly prepared, cache-only faster-whisper runtime into timestamped
> active Evidence, then consumed through Python, CLI, stdio MCP, Search/Ask, and a versioned
> deterministic Compiled Library Export.

It may not claim:

- arbitrary audio/container/codec support;
- full-length meeting, interview, or lecture processing, diarization, chunking, resume, streaming,
  long-audio workers, cloud fallback, or implicit model download;
- exact transcript quality, general language coverage, production SLA, or all-platform support;
- hosted deployment, enterprise adoption, real-user impact, or OpenAI/LLM Wiki official
  integration; or
- that Search/Ask or any downstream Markdown replaces Source, Run, Publication, manifest, JSONL,
  or `mke.evidence_ref.v1` authority.

## External References

- faster-whisper documents direct audio-path transcription, local model paths, and PyAV-based
  decoding with bundled FFmpeg libraries:
  `https://github.com/SYSTRAN/faster-whisper/blob/master/README.md`
- faster-whisper model resolution exposes explicit local-only behavior:
  `https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/utils.py`
- PyAV provides container and stream inspection over FFmpeg libraries:
  `https://pyav.org/docs/stable/api/container.html`
- PyAV binary wheels are linked against bundled FFmpeg builds and therefore require exact-binary
  license review rather than package-metadata-only reasoning:
  `https://github.com/PyAV-Org/PyAV`

These references justify feasibility and inspection boundaries. The implementation authority
remains the locked dependency set, committed fixtures, exact wheel/model receipts, tests, proofs,
and reviewed repository diff.

## Open Decision Status

There are no unresolved product or architecture choices in this authority-amended written design.
The exact Export v2 closed shape is deliberately delegated to the bounded PR C reconciliation
checkpoint and is not an open invitation to expand scope. This document may advance to full plan
review. The full plan review is complete and permits staged implementation only; it does not
dispatch PR A or authorize implementation, acquisition, or external side effects. Any later change
to formats, limits, provider authority, export direction, license boundary, public surface, or
non-goals requires an explicit design amendment before implementation.
