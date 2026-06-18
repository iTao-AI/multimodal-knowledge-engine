# Real Local Transcription Deployment Proof Design

## Status

- Stage: Approved after autoplan review, pending implementation plan.
- Slice: D3-B.
- Depends on: D3-A `TranscriptProvider` port and trusted local command boundary.

## Goal

Build a deployable real-transcription slice for short MP4 files without weakening MKE's current
deterministic product proof.

D3-B must prove this end-to-end path:

```text
short spoken MP4 without a transcript sidecar
  -> first-party faster-whisper adapter command
  -> mke.video_transcript.v1
  -> TranscriptProvider
  -> Run / candidate Evidence / Publication
  -> timestamp Search and evidence-only Ask
  -> CLI and owner-configured stdio MCP
```

The required CI path remains model-free and does not access model hosting. Real model execution is
an explicit opt-in proof and deployment check.

## Why This Slice

D3-A established the provider boundary, bounded subprocess capture, stable transcript schema, and
fail-closed Publication semantics. It intentionally did not ship an ASR runtime. As a result, MKE
can prove timestamp Evidence with a sidecar and can execute a fake trusted local command, but it
cannot yet transcribe an ordinary spoken MP4.

D3-B closes that gap without rebuilding the application around a model SDK. It also proves that
the same capability can be used by a local operator through CLI and by an Agent through MCP, while
keeping provider selection and model policy under the server owner's control.

## Scope

D3-B includes:

- one first-party `faster-whisper` adapter command,
- `small` multilingual model as the default real-proof model,
- CPU `int8` as the default execution profile,
- explicit model preparation with opt-in download,
- normal CLI MP4 ingest using the configured real provider,
- stdio MCP MP4 ingest using owner-process provider configuration,
- read-only transcription diagnostics and a separate model preparation command,
- a successful `TranscriptIntakeReport` attached to the Run,
- a source-controlled, redistribution-safe spoken MP4 fixture,
- an opt-in real transcription proof,
- an isolated wheel-installed CLI and stdio MCP deployment proof,
- model-free unit, contract, lifecycle, and packaging tests.

## Non-Goals

D3-B does not implement:

- audio-only file ingest,
- long-video chunking or checkpointed transcription,
- diarization or speaker identity,
- bundled model weights,
- required-CI model downloads,
- arbitrary local model directories,
- request-time provider, command, endpoint, or credential overrides,
- AutoDL deployment,
- remote self-hosted ASR,
- vendor ASR APIs,
- HTTP, Queue, Webhook, or workspace UI,
- GPU scheduling or multi-GPU execution,
- transcription quality benchmarking across models,
- OCR or retrieval algorithm changes.

## Chosen Approach

### First-Party Adapter Command

MKE will ship a package-owned executable entrypoint similar to:

```text
mke-transcribe-faster-whisper
```

The executable imports the optional ASR dependencies, validates the input media, runs
`faster-whisper`, and writes one `mke.video_transcript.v1` JSON object to stdout. MKE invokes it
through the existing `LocalCommandTranscriptProvider` with `shell=False`, bounded stdout/stderr,
and a timeout.

The executable is an adapter process protocol, not a third product interface. The public product
interfaces remain CLI and MCP. The runtime factory invokes the adapter with the current Python
interpreter through `python -m mke.adapters.video.faster_whisper_cli`; it must not discover an
arbitrary executable through `PATH` or accept user-supplied command argv. The package may also
register `mke-transcribe-faster-whisper` as an operator-facing alias for the same module entrypoint.

### Rejected Alternatives

| Alternative | Decision | Reason |
|---|---|---|
| Import `faster-whisper` directly into `KnowledgeEngine` | Rejected | It couples model memory, native runtime failures, and optional dependencies to the owner process. |
| Add a local HTTP ASR sidecar now | Deferred | It adds service lifecycle, upload, authentication, retry, and port management before remote execution is required. |
| Keep only a user-supplied command | Rejected for D3-B | D3-A already proves that boundary; D3-B must ship one reproducible real provider path. |
| Download a model during required CI | Rejected | Required checks must not depend on model hosting, network availability, or large caches. |

## Dependency And Model Policy

### Optional Dependency

The core package must remain installable without ASR dependencies. Add a project optional
dependency group:

```toml
[project.optional-dependencies]
transcription = [
  "faster-whisper>=1.2.1,<2",
  "av>=11,<18",
]
```

The exact resolved dependency graph belongs in `uv.lock`. D3-B does not add `faster-whisper`,
CTranslate2, PyAV, ONNX Runtime, or model weights to the core dependency list.

PyAV is declared directly because the adapter imports it for media inspection. It must not be
treated as an accidental transitive dependency. `faster-whisper` is MIT licensed and PyAV is
BSD-3-Clause licensed; the implementation PR must record this dependency and license review.

### Default Model Profile

The built-in real-proof defaults are:

```text
model = small
model_revision = 536b0662742c02347bc0e980a01041f333bce120
device = cpu
compute_type = int8
language = auto
```

The revision pins the default `Systran/faster-whisper-small` snapshot used by the proof. Operators
may override the model identifier, revision, device, compute type, language, and cache directory
through trusted process-start configuration. D3-B does not accept an arbitrary local model
directory: model identity is always the configured identifier plus revision, while model files may
already exist in the configured cache.

### Download Policy

Model download is denied by default:

```text
local_files_only = true
```

Normal ingest, real proof execution, and MCP are cache-only. `mke transcription doctor` is also
read-only and never downloads. Only the side-effect-free operator command
`mke transcription prepare --allow-model-download` may acquire the exact configured model
revision. Agent-facing MCP requests cannot enable downloads. A configured cache directory is
process-local configuration and must never appear in public output.

Model resolution uses one explicit algorithm:

1. Map the built-in `small` alias to `Systran/faster-whisper-small`.
2. Reject absolute paths, relative paths, `..`, and repository identifiers outside the documented
   identifier grammar.
3. Require a full commit SHA for `model_revision`.
4. Resolve the exact revision locally first.
5. Only `transcription prepare --allow-model-download` may retry resolution with network access.
6. Pass the internally resolved snapshot path to `WhisperModel`; never accept that path from a
   CLI or MCP caller.

If implementation uses `huggingface_hub` directly for this resolution, it must be a declared
optional dependency rather than an accidental transitive dependency.

The preparation command distinguishes these acquisition results without exposing paths:

- `already_cached`,
- `downloaded`.

Normal ingest is cache-only, so a successful `TranscriptIntakeReport` records
`model_source=cache`.

## Architecture

### Components

```text
src/mke/
  domain/
    ParsedVideoTranscript
    TranscriptIntakeReport
  adapters/video/
    faster_whisper_cli.py
    runtime.py
    schema.py
    providers.py
  interfaces/
    CLI adapter
    MCP adapter
    shared public error serializer
  application/
    KnowledgeEngine
```

Responsibilities:

| Component | Responsibility |
|---|---|
| `faster_whisper_cli.py` | Optional-dependency import, media probe, model resolution, ASR, timestamp normalization, JSON output. |
| `runtime.py` | Convert trusted typed runtime configuration into a `TranscriptProvider`. |
| `schema.py` | Validate provider-neutral transcript payloads and return typed media, segments, and optional provenance. |
| `LocalCommandTranscriptProvider` | Execute the first-party command with the existing bounded and sanitized process boundary. |
| `KnowledgeEngine` | Convert validated transcript segments into candidate Evidence and apply the existing Run/Publication lifecycle. |
| Runtime composition root | Build one `KnowledgeEngine` from typed owner configuration for CLI and MCP. |
| Public error serializer | Map typed application failures to the same safe CLI and MCP fields. |
| CLI | Parse operator configuration and serialize stable results. |
| MCP | Bind owner-process configuration to existing Agent tools without adding provider arguments to tool requests. |

### Typed Runtime Configuration

Use explicit configuration types, not arbitrary dictionaries:

```text
SidecarTranscriptionConfig
FasterWhisperTranscriptionConfig
ModelPreparationConfig
```

`FasterWhisperTranscriptionConfig` contains only trusted startup settings:

- model identifier,
- model revision,
- device,
- compute type,
- optional language,
- optional cache directory,
- subprocess timeout,
- bounded stdout/stderr limits.

`ModelPreparationConfig` contains the model identity, revision, optional cache directory, and the
explicit download permission. Download permission is not part of normal ingest or MCP runtime
configuration.

The built-in short-video defaults are:

```text
timeout_seconds = 900
max_stdout_bytes = 2 MiB
max_stderr_bytes = 512 KiB
max_input_bytes = 100 MiB
max_media_duration_ms = 900000
max_segment_count = 10000
```

These limits are separate from D3-A's generic local-command defaults because model loading and
native ASR execution can take longer and emit more diagnostics. They remain bounded.

A single runtime composition root validates these types, maps them to `TranscriptProvider`
instances, and creates `KnowledgeEngine`. CLI and MCP must use that same composition root.

### Runtime Construction

CLI and MCP must not build different application stacks:

```text
CLI ----\
         -> typed RuntimeConfig -> engine factory -> KnowledgeEngine
MCP ----/
```

Business logic, provider construction, Run lifecycle, and persistence must not be duplicated in
the interface modules.

## Public Interfaces

### CLI

The golden path separates first-time model acquisition from diagnostics and ingest:

```bash
mke transcription prepare --allow-model-download --json
mke transcription doctor --json
mke --db .tmp/mke.sqlite ingest speech.mp4 \
  --transcript-provider faster-whisper \
  --json
```

`prepare` does not accept media, open the database, or create a Run. `doctor` never mutates the
model cache. Both commands use the built-in model profile unless trusted operator flags override
it.

Normal ingest may select the real provider through trusted local flags:

```bash
mke --db .tmp/mke.sqlite ingest speech.mp4 \
  --transcript-provider faster-whisper \
  --model small \
  --model-revision 536b0662742c02347bc0e980a01041f333bce120 \
  --device cpu \
  --compute-type int8 \
  --json
```

The existing no-option path remains sidecar-backed for compatibility.

Add an operator diagnostic command:

```bash
mke transcription doctor \
  --transcript-provider faster-whisper \
  --model small \
  --device cpu \
  --compute-type int8
```

The doctor command checks package availability, typed configuration, device/compute compatibility,
and exact-revision model availability. It must not transcribe media, download, mutate the cache, or
print cache paths. `doctor --json` emits exactly one object with `status=ready|not_ready`, stable
checks, `cause`, and `next_step`; ready returns `0`, not-ready returns `1`, and CLI usage errors
return `2`.

`ingest`, `run get`, `transcription prepare`, `transcription doctor`, and
`proof transcription-run` support `--json`. JSON mode reserves stdout for one JSON object and
sends logs or progress to stderr.

### MCP

The stdio server accepts the same trusted startup configuration:

```bash
mke --db .tmp/mke.sqlite mcp \
  --allowed-root ./library \
  --transcript-provider faster-whisper \
  --model small \
  --device cpu \
  --compute-type int8
```

The existing MCP tools remain:

```text
list_libraries()
ingest_file(path)
get_run(run_id)
search_library(query, limit)
ask_library(question, limit)
```

No MCP tool accepts provider names, model names, command argv, cache paths, endpoints,
credentials, or download policy. D3-B does not add a capability-discovery tool.

When configured for `faster-whisper`, the MCP server runs the same read-only readiness checks as
`doctor` before starting the stdio protocol. A missing dependency, unsupported profile, or cache
miss exits with a stable public-safe error; MCP startup never downloads a model.

`ingest_file` remains synchronous in D3-B and is limited to the short-video profile. The MCP proof
client uses a timeout at least as large as the configured provider timeout. Client cancellation or
server shutdown must terminate the adapter process; if a Run already exists, it is marked failed
and no candidate output becomes searchable. Queue-backed progress and resumability remain
deferred.

### Interface Selection

| Interface | Use | D3-B status |
|---|---|---|
| Python application API | In-process composition and tests | Existing internal contract |
| CLI | Local files, operator setup, diagnostics, automation, proof | Public |
| MCP | Local Agent access under owner configuration | Public |
| HTTP | Remote clients, uploads, multi-process deployment | Deferred |
| Queue/Webhook | Long-running and remote asynchronous work | Deferred |

Environments without a suitable MCP client may wrap the CLI in an Agent skill. That does not
justify adding HTTP in D3-B.

## Media Probe And Transcript Output

The first-party adapter uses PyAV from the optional ASR dependency graph to inspect the input. It
must reject media outside the D3-B profile before publishing transcript JSON:

- container is MP4,
- video stream is H.264,
- audio stream is AAC,
- at least one audio stream exists,
- media duration is positive and does not exceed 15 minutes,
- file size does not exceed 100 MiB,
- normalized segment count does not exceed 10,000.

CLI and MCP reject an oversized file before hashing or starting the adapter. The PyAV probe is the
authoritative duration check and runs before model loading.

The adapter must not call a system shell. D3-B does not require a separately installed `ffmpeg` or
`ffprobe` executable.

On success, the adapter writes exactly one JSON object to stdout. Library logs and diagnostics go
to stderr and remain subject to the existing bounded capture limit. On failure, stdout remains
empty and the adapter exits with a project-owned stable exit code. The parent maps that code to a
typed public failure and never parses stderr into a public response.

The adapter must fully consume the `faster-whisper` segment generator before emitting JSON. A
failure after partial model output must not produce a partial valid payload.

## Timestamp Normalization

`faster-whisper` returns floating-point seconds. D3-B converts them to integer milliseconds using
one project-owned normalization function.

Rules:

1. Convert each non-negative second value with `floor(seconds * 1000 + 0.5)` so half-millisecond
   values round up deterministically.
2. Reject negative or non-finite values.
3. If floating-point rounding creates an overlap of at most 1 ms, clamp the new start to the prior
   segment end.
4. Reject overlaps larger than 1 ms.
5. Reject a segment whose normalized end is not greater than its normalized start.
6. Trim text and reject empty segments.
7. Preserve provider order; do not reorder segments silently.

The shared schema parser validates the normalized result again before the application sees it.

## Transcript Schema And Provenance

D3-B keeps `mke.video_transcript.v1`. It adds optional, backward-compatible transcription
provenance. Sidecar fixtures without provenance remain valid.

Example:

```json
{
  "format": "mke.video_transcript.v1",
  "media": {
    "container": "mp4",
    "video_codec": "h264",
    "audio_codec": "aac",
    "has_audio": true,
    "duration_ms": 6200
  },
  "transcription": {
    "provider": "faster-whisper",
    "model": "small",
    "model_revision": "536b0662742c02347bc0e980a01041f333bce120",
    "library_version": "1.2.1",
    "device": "cpu",
    "compute_type": "int8",
    "detected_language": "en",
    "model_source": "cache",
    "transcription_duration_ms": 1450
  },
  "segments": [
    {
      "start_ms": 0,
      "end_ms": 2800,
      "text": "Evidence becomes searchable after publication."
    }
  ]
}
```

Provider output is untrusted until schema validation succeeds. The parser returns a project-owned
`ParsedVideoTranscript(media, segments, transcription_provenance | None)`. Sidecar payloads may
omit provenance; first-party `faster-whisper` output must include complete provenance. Unknown
provenance fields are not copied into domain objects or public responses.

Schema validation also requires positive `media.duration_ms`, every segment end to be at or before
the media duration, bounded string lengths and enum values, and consistent transcription duration
and segment counts. The provider derives the report and extractor identity only from validated
actual values, not merely from requested configuration.

Shared parser failures must use provider-neutral wording such as `video transcript is not valid
JSON`. Sidecar-only failures, such as a missing `<video>.mke-transcript.json` file, may retain
sidecar-specific wording. The implementation must update CLI allowlists, contract tests, and
reference documentation together when these stable causes change.

## Transcript Intake Report

Add a frozen project-owned `TranscriptIntakeReport` with provider-neutral fields:

```text
provider
model
model_revision
library_version
device
compute_type
detected_language
media_duration_ms
transcription_duration_ms
segment_count
model_source
```

Constraints:

- no command argv,
- no stderr,
- no model cache path,
- no input absolute path,
- no credentials or endpoint,
- stable enum values for `model_source`,
- all durations are non-negative integer milliseconds.

The validated transcript result carries the report alongside segments and extractor identity. The
report is attached to `IngestResult` as
`transcript_intake_report: TranscriptIntakeReport | None = None` and persisted by `run_id` in a
video-specific store contract and table. Public CLI and MCP payloads use the key
`transcript_intake_report`. Do not overload the existing PDF `intake_report` field with a union
that weakens typing.

The successful report is inserted in the same SQLite transaction that activates the Publication,
replaces active FTS rows, and marks the Run `published`. Validation, candidate persistence,
activation failure, rollback, or a latest-request-wins `superseded` result must not leave a
success-shaped report. A published Run and its successful report are therefore observable
together or not at all.

Expose the report through:

- successful CLI ingest output,
- `mke run get`,
- MCP `ingest_file`,
- MCP `get_run`.

## Extractor Fingerprint

The faster-whisper path uses a canonical fingerprint:

```text
faster-whisper-v1:<sha256-of-canonical-extractor-identity-json>
```

The canonical identity JSON has fixed project-owned keys, bounded values, UTF-8 encoding, sorted
keys, and compact separators. The Manifest validator requires the exact
`faster-whisper-v1:<64 lowercase hex>` grammar. Human-readable actual profile fields live in the
validated intake report. The validator must not accept an arbitrary non-empty provider string or a
broad prefix-only match.

This keeps the actual model/runtime profile observable while preserving D3-A's value-completeness
guard.

## Failure Semantics

Stable operator-facing failures must cover:

- transcription optional dependency is not installed,
- configured model is not cached and download is disabled,
- model download failed,
- model revision is unavailable,
- device or compute type is unsupported,
- media profile is unsupported,
- media has no audio,
- transcription produced no speech segments,
- transcription timed out,
- subprocess stdout or stderr exceeded its limit,
- adapter stdout was not valid UTF-8 or transcript JSON,
- timestamp normalization failed,
- transcript schema validation failed,
- candidate Evidence validation failed,
- Publication activation failed.

Configuration validation, provider construction, model preparation, MCP startup, and
`transcription doctor` failures
that happen before ingest begins must return a stable error and create no Run. Once ingest has
created a Run, every ordinary extraction or lifecycle exception must be normalized to a typed
application failure and must attempt to mark that Run `failed` in a separate recovery transaction.
Process termination exceptions such as `KeyboardInterrupt` and `SystemExit` are not swallowed.

The first-party adapter owns a versioned exit-code map for dependency, model resolution, media,
transcription, and schema failures. CLI and MCP share one serializer for
`problem`, `cause`, `active_publication_impact`, `next_step`, and optional `run_id`. Raw exception
text and stderr are internal diagnostics only.

For ingestion failures:

- the created Run becomes `failed`,
- no candidate output becomes searchable,
- the active Publication remains unchanged,
- no success-shaped `TranscriptIntakeReport` is visible,
- CLI and MCP return stable public errors,
- logs may contain internal diagnostics but public output must not contain absolute paths, cache
  directories, argv, stderr, stack traces, credentials, endpoints, or secret values.

The first-party adapter must not serialize raw exception strings into its JSON output.

## Extensibility

D3-B preserves future providers without introducing a plugin framework:

```text
TranscriptProvider
  SidecarTranscriptProvider
  LocalCommandTranscriptProvider
    first-party faster-whisper command
  future RemoteASRProvider
  future VendorASRProvider
```

Future provider rules:

- add one typed config and one provider/factory mapping,
- emit the project-owned transcript result,
- keep endpoint and credentials in owner-process configuration,
- do not change `KnowledgeEngine` use cases,
- do not change MCP request schemas merely to select a provider.

Audio-only ingest may later normalize audio into the same transcript pipeline. Long-video work may
move execution behind a worker and checkpoint boundary while reusing Run and Publication
semantics. HTTP may later become another thin interface adapter when a remote client actually
exists.

D3-B does not add dynamic entry-point discovery, a generic provider SDK, or speculative plugin
registration.

## Fixture Policy

Add one short spoken MP4 with no transcript sidecar.

Requirements:

- repository-authored English text with at least one stable Search keyword such as `evidence`,
- synthetic or explicitly licensed voice source,
- no personal voice or private material,
- MP4/H.264/AAC profile,
- short enough for a CPU proof,
- committed provenance, generation instructions, source license, and checksum,
- no exact full-transcript assertion across all runtimes.

The real proof must assert non-empty timestamp Evidence, valid locator ordering, and at least one
stable keyword match. It must record the observed transcript without turning a single run duration
into a performance claim.

## Testing Strategy

### Required Model-Free CI

Required CI does not install model weights or access model hosting.

Tests must cover:

- typed config defaults and validation,
- the shared runtime composition root used by both CLI and MCP,
- typed public error serialization and adapter exit-code mapping,
- provider factory selection,
- absence of optional dependency,
- download denied by default,
- fake cached-model resolution,
- fake model download success and failure,
- model revision propagation,
- media probe success and failure,
- 100 MiB file, 15-minute duration, and 10,000-segment boundaries,
- complete segment generator consumption,
- timestamp conversion and 1 ms clamp,
- larger overlap rejection,
- empty speech rejection,
- transcript provenance validation,
- segment timestamps cannot exceed media duration,
- fingerprint normalization and Manifest recognition,
- report validation, persistence, and public serialization,
- report insertion is atomic with Publication activation and absent for superseded Runs,
- no successful report after validation, candidate write, or activation failure,
- failed transcription leaves active Search unchanged,
- CLI normal ingest with owner-selected provider,
- CLI transcription doctor behavior,
- CLI transcription prepare is the only model-download path and creates no Run,
- one-object JSON stdout contracts for ingest, run get, prepare, doctor, and real proof,
- MCP owner configuration reaches `KnowledgeEngine`,
- MCP tools cannot accept provider/model/argv/download overrides,
- existing deterministic proof and demo do not instantiate the real provider,
- public errors redact paths, cache directories, stderr, argv, traceback, endpoints, and secrets,
- subprocess cancellation and server shutdown terminate the child process.

### Opt-In Real Proof

Add a separate command:

```bash
mke proof transcription-run \
  --fixture tests/fixtures/video/spoken-evidence.mp4 \
  --json
```

The proof uses a temporary SQLite workspace and leaves no database or model copy in the repository.
It must verify:

- real adapter execution,
- Run publication,
- timestamp Evidence,
- Search keyword match,
- evidence-only Ask result,
- sanitized human output,
- structured JSON output suitable for milestone evidence.

The model must already be prepared. The proof never downloads and reports the actual non-sensitive
runtime profile and library versions used.

This command is not invoked by `mke proof run`, `mke demo --verify`, or required CI.

### Wheel-Installed Deployment Proof

The implementation must include a repeatable deployment check that:

1. builds the wheel,
2. creates an isolated environment,
3. installs the wheel with the `transcription` extra under constraints exported from `uv.lock`,
4. runs `mke transcription doctor`,
5. runs outside the repository working tree and verifies the CLI and adapter resolve from the
   isolated environment,
6. prepares the exact model revision only when the proof is explicitly allowed network access,
7. runs CLI real ingest against the spoken fixture,
8. starts the installed `mke mcp` stdio server with owner-configured faster-whisper settings,
9. uses an MCP SDK client over stdio to call `ingest_file`, `get_run`, `search_library`, and
   `ask_library`,
10. compares CLI and MCP report fields and verifies timestamp Evidence without exposing provider
    controls in tool schemas.

The real deployment proof is opt-in because it needs model availability. Deterministic packaging
and MCP schema tests remain required CI. The proof records Python, OS, architecture,
`faster-whisper`, CTranslate2, and PyAV versions without exposing local paths. It proves a
wheel-installed local deployment, not publication to PyPI or support for unverified platforms.

## Delivery Sequence

D3-B remains one milestone but should be implemented as three independently reviewable PRs:

1. **Protocol and lifecycle:** typed parsed transcript/result/report DTOs, stable error contract,
   resource limits, canonical fingerprint, schema validation, SQLite migration, and atomic
   activation/report persistence.
2. **Runtime and interfaces:** exact-revision resolver, first-party adapter, shared composition
   root, `prepare`, `doctor`, CLI ingest, MCP startup configuration, cancellation, and model-free
   contract tests.
3. **Deployment proof and docs:** spoken fixture, real cached-model proof, isolated constrained
   wheel-installed CLI/MCP proof, platform evidence, ADR, references, and tutorials.

PR 2 depends on PR 1. PR 3 depends on PR 2. Tests and documentation ship with the behavior they
describe; this sequence is not permission to postpone contract or lifecycle tests.

## Documentation Impact

The implementation PR must update:

- `README.md` and `README_CN.md`,
- `docs/README.md`,
- a new ADR that preserves ADR-0005 as the D3-A decision and records the D3-B first-party runtime,
  dependency, model, and download policy,
- `docs/explanation/architecture.md`,
- `docs/reference/cli.md`,
- `docs/reference/contracts.md`,
- `docs/how-to/run-local-product-proof.md`,
- `docs/how-to/use-mke-mcp.md`,
- a new `docs/how-to/use-local-transcription.md`,
- `docs/tutorials/getting-started.md`,
- video fixture provenance documentation.

The MCP how-to must include owner-configured examples appropriate for an MCP-capable local Agent.
Environments that use a CLI skill should be documented as CLI integration, not mislabeled as MCP.

## Acceptance Criteria

D3-B is complete when all of the following are true:

- MKE core installs and passes required checks without the transcription extra.
- The transcription extra installs from the built wheel on Python 3.12 and 3.13 CI environments
  without downloading model weights.
- `mke transcription prepare` is the only built-in model download path and creates no Run.
- `mke transcription doctor --json` reports stable read-only readiness without leaking local
  paths.
- The default model profile is `small`, CPU, `int8`, pinned to the approved revision.
- Normal ingest, proof execution, and MCP never download; preparation requires explicit operator
  opt-in.
- A short spoken MP4 without a sidecar produces timestamp Evidence through real faster-whisper.
- Normal CLI ingest can use the real provider.
- An owner-configured stdio MCP server can ingest the same video without changing MCP tool schemas.
- CLI and MCP use one runtime/provider construction path.
- CLI and MCP share one typed, redacted public error serializer.
- A successful Run exposes `TranscriptIntakeReport` through CLI and MCP Run inspection.
- Failed transcription or Publication leaves active Search unchanged and exposes no successful
  report.
- The published Publication and successful report become visible atomically.
- `mke proof run` and `mke demo --verify` remain deterministic and sidecar-backed.
- Required verification passes:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
git diff --check
```

- Wheel-extra install and read-only doctor checks pass for Python 3.12 and 3.13 in required CI.
- The opt-in real transcription and wheel-installed stdio MCP proofs pass on at least one explicitly
  documented OS, architecture, and Python environment. Other environments remain unverified.

## Decision Audit

| Decision | Outcome |
|---|---|
| First real ASR provider | `faster-whisper` |
| Integration style | First-party optional adapter command through `LocalCommandTranscriptProvider` |
| Default model | Multilingual `small` |
| Default runtime | CPU `int8` |
| Download policy | Separate explicit `transcription prepare`; ingest and MCP are cache-only |
| Required CI | Model-free and independent of model hosting |
| Real proof | Separate opt-in command |
| Product interfaces | CLI and MCP only |
| MCP provider selection | Owner-process startup configuration only |
| HTTP / remote ASR | Deferred |
| AutoDL / vendor APIs | Extension boundary only |
| Plugin framework | Not introduced |
| Deployment evidence | Built wheel plus real CLI and stdio MCP smoke |
| Short-video boundary | 100 MiB, 15 minutes, 10,000 segments |
| Report visibility | Atomic with Publication activation |
| Fingerprint | Canonical extractor identity hash |
| Delivery | Three sequential, independently reviewable PRs |

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|---|---|---|---:|---|---|
| CEO Review | `/plan-ceo-review` | Scope and strategy | 1 | CLEAR | 6 proposals accepted; 5 directions explicitly deferred |
| Codex Review | `/codex review` | Independent outside voice | 3 | INCORPORATED | Error protocol, resource bounds, atomicity, packaging, and DX gaps folded into the design |
| Eng Review | `/plan-eng-review` | Architecture and tests | 1 | CLEAR | 10 findings incorporated; 0 critical gaps remain in the reviewed plan |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | SKIPPED | No graphical UI scope |
| DX Review | `/plan-devex-review` | Developer experience | 1 | CLEAR | Prepare/doctor split, golden path, JSON contracts, and platform evidence added |

**CODEX:** Three read-only independent passes found no unresolved disagreement after corrections.

**VERDICT:** CEO + ENG + DX CLEARED - ready for implementation planning.

NO UNRESOLVED DECISIONS
