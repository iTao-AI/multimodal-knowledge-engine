# Real Local Transcription Deployment Proof Autoplan Review

## Status

- Review target: `docs/superpowers/specs/2026-06-18-real-local-transcription-deployment-proof-design.md`
- Mode: Selective expansion
- Product type: local CLI tool, Python package, and stdio MCP server
- Review state: approved
- UI review: skipped because D3-B has no graphical interface
- Independent voice: Codex CLI; Claude subagent was unavailable in this host

## Executive Verdict

The D3-B direction is valid: reuse the D3-A subprocess boundary, ship one first-party local ASR
path, and prove the same capability through CLI and owner-configured stdio MCP. The original design
was not implementation-ready because it left the error protocol, report atomicity, provenance data
flow, short-media resource boundary, and wheel-proof reproducibility underspecified.

The reviewed design keeps the approved product scope and hardens it with one selective addition:
`mke transcription prepare` separates explicit model acquisition from read-only diagnostics and
cache-only ingest. Delivery is split into three sequential PRs so protocol/lifecycle correctness is
reviewed before runtime and deployment proof work.

## Confirmed Premises

1. D3-B proves real local transcription, not transcription quality leadership.
2. Short MP4, CLI, and stdio MCP are sufficient for this slice.
3. D3-A's `TranscriptProvider` and bounded subprocess boundary are reused.
4. The Apple Silicon `small`/CPU/`int8` profile is a hypothesis until the real proof records it.
5. Required CI remains model-free; real model execution is opt-in.
6. HTTP, cloud ASR, long-video processing, audio-only ingest, and workspace UI remain deferred.

## What Already Exists

| Existing capability | Reuse decision |
|---|---|
| `TranscriptProvider` application port | Reuse unchanged as the application dependency boundary. |
| `LocalCommandTranscriptProvider` | Reuse its `shell=False`, timeout, bounded capture, and child cleanup behavior. |
| `mke.video_transcript.v1` | Extend additively with optional provenance; old sidecars remain valid. |
| Run, candidate Evidence, Publication, and active-only Search | Reuse; do not create a parallel video lifecycle. |
| CLI public error fields | Generalize into a shared typed serializer used by CLI and MCP. |
| MCP `ingest_file`, `get_run`, `search_library`, `ask_library` | Keep tool schemas unchanged; bind provider policy at server startup. |
| Deterministic `mke proof run` and `mke demo --verify` | Preserve as sidecar-backed, model-free gates. |
| PDF intake report storage | Reuse the report concept, not its post-activation separate-commit pattern. |

## Scope Decisions

### Accepted

- Add `mke transcription prepare` as the only model-download path.
- Define a 100 MiB, 15-minute, and 10,000-segment D3-B input envelope.
- Make successful transcript report insertion atomic with Publication activation.
- Add one runtime composition root and one typed public error serializer for CLI and MCP.
- Use a canonical extractor-identity hash instead of delimiter-based dynamic fingerprints.
- Split implementation into three independently reviewable PRs.

### Deferred

- Queue-backed asynchronous ingest, progress streaming, resumability, and long-video checkpoints.
- Local HTTP ASR sidecar, remote self-hosted ASR, AutoDL, and vendor APIs.
- Transcription quality benchmarks and model comparisons.
- PyPI publication, container release, and a general multi-platform support claim.
- Dynamic provider discovery or a plugin SDK.

### Rejected

- Importing `faster-whisper` directly into `KnowledgeEngine`.
- Allowing request-time MCP model, download, command, cache, endpoint, or credential overrides.
- Downloading models during normal ingest, MCP startup, required CI, or real-proof execution.

## Architecture Review

### Reviewed Architecture

```text
CLI flags --------------------\
                               -> RuntimeConfig -> build_engine() -> KnowledgeEngine
MCP owner startup config -----/                         |
                                                         v
                                             TranscriptProvider port
                                               /                 \
                                      Sidecar provider      Local command provider
                                                                  |
                                                                  v
                                                    first-party adapter process
                                                    probe -> resolve cache -> ASR
                                                                  |
                                                                  v
                                              ParsedVideoTranscript + report
                                                                  |
                                                                  v
                                        candidate Evidence -> validate -> activate
                                                                  |
                                                                  v
                                        Publication + FTS + report + Run published
                                                  one SQLite transaction
```

### Data Flow And Shadow Paths

```text
INPUT -> PRECHECK -> PROBE -> TRANSCRIBE -> PARSE -> CANDIDATE -> ACTIVATE -> OUTPUT
  |         |          |          |          |          |           |          |
missing   >100 MiB   no audio   timeout    invalid    invalid     conflict    JSON
wrong     wrong ext  >15 min    native     UTF-8     manifest    rollback    redacted
type      no access  codec      failure    schema    DB error    superseded  stable
```

- Missing, empty, unsupported, or oversized input fails before model loading.
- Cache miss fails before a Run is created because model acquisition is a separate command.
- Failures after Run creation mark the Run failed and preserve the previous active Publication.
- Activation conflict produces `superseded`, not a success report.
- Published Run, active Publication, FTS rows, and successful report become visible atomically.

### Run State Machine

```text
queued -> running -> validated -> published
   |         |           |           ^
   |         |           +-> superseded
   |         +-> failed
   +-> failed

interrupted is a recovery classification for abandoned work; D3-B cancellation must attempt
failed cleanup immediately. published and superseded are terminal for this ingest attempt.
```

### Deployment Sequence

```text
build wheel
  -> isolated environment outside repository
  -> install wheel[transcription] with lock-derived constraints
  -> prepare exact model revision (explicit network opt-in)
  -> doctor (read-only)
  -> CLI ingest/search/ask
  -> start stdio MCP with owner config
  -> ingest/get_run/search/ask via real MCP client
  -> record redacted environment and proof JSON
```

### Rollback Flow

```text
problem detected?
  -> stop using faster-whisper owner config
  -> return CLI/MCP to default sidecar provider
  -> keep additive DB table and old transcript schema compatibility
  -> revert runtime/interface commits if needed
  -> active Publications remain searchable because failed candidates never activate
```

Reversibility is 4/5. The optional dependency and adapter can be disabled without changing
existing sidecar-backed data. The additive report table can remain during rollback.

## Error And Rescue Registry

| Method or code path | Failure | Public handling | Run impact |
|---|---|---|---|
| `transcription prepare` | dependency missing, invalid revision, network failure, cache permission | Stable code, cause, next step; no raw path | No Run |
| `transcription doctor` | invalid config, unsupported compute profile, cache miss | `ready|not_ready`, exit 0/1, usage exit 2 | No Run |
| Runtime composition root | invalid owner config or optional dependency absent | Typed public startup error | No Run |
| MCP startup preflight | provider not ready | Exit before stdio protocol with safe stderr | No Run |
| Adapter spawn and bounded read | executable/import failure, timeout, output limit, cancellation | Stable adapter exit-code mapping; stderr stays internal | Failed if Run exists |
| PyAV probe | bad container/codec, no audio, duration or size limit | Stable media-profile error | Failed if Run exists |
| Model inference | native runtime error, empty speech, generator failure | Stable transcription error | Failed |
| Transcript parser | invalid UTF-8/JSON/provenance/timestamps/count | Provider-neutral schema error | Failed |
| Candidate persistence | manifest or SQLite failure | Typed lifecycle error | Failed; active unchanged |
| Activation transaction | conflict or SQLite failure | Superseded or typed lifecycle error | No partial publication/report |
| CLI/MCP serializer | unexpected internal exception | Safe generic public error; full detail only in internal logs | Existing lifecycle state retained |

## Failure Modes Registry

| Code path | Failure mode | Rescued? | Required test? | User sees | Logged? |
|---|---|---:|---:|---|---:|
| Model preparation | exact revision unavailable | Yes | Yes | Stable revision error and recovery command | Yes |
| Doctor | model not cached | Yes | Yes | `not_ready`, run `transcription prepare` | Yes |
| Runtime factory | CLI and MCP config drift | Prevented | Yes | Same behavior from both interfaces | N/A |
| Adapter process | timeout or capture overflow | Yes | Yes | Stable safe cause | Yes |
| Media probe | oversized or too long | Yes | Yes | Limit and corrective action | Yes |
| Transcript parser | provenance/config mismatch | Yes | Yes | Invalid provider output | Yes |
| Candidate write | database failure | Yes | Yes | Active Publication unchanged | Yes |
| Activation | report insert fails | Yes | Yes | Transaction rollback, no partial state | Yes |
| Activation | latest-request conflict | Yes | Yes | Run superseded, no success report | Yes |
| MCP client | cancellation or server shutdown | Yes | Yes | Tool cancellation; child terminated | Yes |

No failure mode is both silent and untested in the reviewed design.

## Security And Resource Boundary

- Provider/model/cache/download policy is trusted owner configuration, never an MCP request field.
- The first-party command uses the current interpreter and package module, never PATH discovery or
  user-supplied argv.
- Model identifiers and revisions use strict grammar; local directories and traversal are rejected.
- Adapter stdout is a bounded success protocol; public errors derive from stable exit codes, not
  stderr or raw exception strings.
- Inputs are bounded before hashing/model loading and validated again by the media probe/schema.
- Public payloads exclude paths, cache directories, argv, stderr, stack traces, endpoints,
  credentials, and secrets.

## Test Coverage Plan

```text
CODE PATHS                                      USER FLOWS
[+] config + composition root                   [+] first-time setup
  +-- sidecar defaults                              +-- install extra
  +-- faster-whisper config                         +-- prepare exact revision
  +-- invalid profile                               +-- doctor ready/not-ready
[+] adapter protocol                            [+] normal CLI ingest
  +-- success envelope                              +-- cached model success
  +-- stable exit codes                             +-- size/duration rejection
  +-- timeout/capture/cancel                        +-- JSON-only stdout
[+] schema + report                             [+] owner-configured MCP
  +-- provenance optional/required                  +-- startup preflight
  +-- timestamp/media bounds                        +-- unchanged tool schemas
  +-- canonical fingerprint                         +-- ingest/get/search/ask
[+] lifecycle                                   [+] deployment proof
  +-- validation/candidate failures                 +-- wheel outside repo
  +-- atomic activation + report                    +-- lock constraints
  +-- superseded and rollback                       +-- environment evidence
```

Test pyramid:

- Many unit tests for config, resolver, normalization, schema, fingerprints, exit codes, and
  serialization.
- Integration tests for application lifecycle, SQLite atomicity, CLI composition, and MCP owner
  configuration.
- A few system proofs: cached real transcription and isolated wheel-installed CLI plus stdio MCP.
- Required CI never downloads or runs a model. Real proof is opt-in and records, but does not turn,
  one observed duration into a performance claim.

The hostile test is an oversized malformed MP4 whose adapter emits excessive stderr and is then
cancelled during a concurrent newer ingest. The expected result is bounded cleanup, failed or
superseded Run state, unchanged active Search, and no report or path leak.

## Performance Review

- The first bottleneck is CPU inference, then model memory, then media decode; SQLite is not the
  expected D3-B bottleneck.
- 10x concurrent local ingest is intentionally unsupported. The owner process must serialize or
  externally coordinate work until a queue/worker slice exists.
- File-size, media-duration, segment-count, timeout, stdout, and stderr limits bound the supported
  synchronous profile.
- Model acquisition is separated from ingest so network latency is not hidden inside a Run.

## Developer Experience Review

### Persona

A local AI/platform engineer evaluates MKE from source, proves one real spoken-video flow, and then
connects an Agent through stdio MCP while keeping model and download policy under operator control.

### Empathy Narrative

I want one deterministic command to prove the repository, one explicit command to prepare the
model, and one read-only command to tell me whether the runtime is ready. When ingest fails, I need
the same safe cause and next step from CLI and MCP. I should not need to understand cache paths,
subprocess argv, or internal Python exceptions to recover.

### Golden Path

```bash
uv sync --locked --extra transcription
uv run mke transcription prepare --allow-model-download --json
uv run mke transcription doctor --json
uv run mke --db .tmp/mke.sqlite ingest speech.mp4 \
  --transcript-provider faster-whisper --json
```

The deterministic `mke proof run --json` path remains the under-five-minute first proof. Cached
real transcription targets an under-five-minute local proof on a documented environment. Initial
model acquisition is reported separately and remains network-dependent; it is not folded into a
misleading TTHW claim.

### DX Scorecard

| Dimension | Before | Reviewed target |
|---|---:|---:|
| Getting started | 5/10 | 8/10 |
| CLI/MCP design | 6/10 | 8/10 |
| Error messages | 4/10 | 8/10 |
| Documentation | 6/10 | 8/10 |
| Upgrade path | 7/10 | 8/10 |
| Developer environment | 5/10 | 8/10 |
| Community/ecosystem | 7/10 | 7/10 |
| DX measurement | 4/10 | 7/10 |

The magical moment is one spoken MP4 producing timestamp Evidence through a wheel-installed CLI,
then producing the same report and evidence-only Ask result through a real stdio MCP client without
changing the Agent tool schemas.

## Implementation Tasks

- [ ] **T1 (P1)** — Define parsed transcript, provenance, report, canonical identity, typed runtime
  config, and typed public error contracts.
- [ ] **T2 (P1)** — Add transcript report migration and make report insertion atomic with
  Publication activation; cover rollback and superseded paths.
- [ ] **T3 (P1)** — Implement strict schema/media/resource validation and stable adapter exit-code
  mapping with redaction tests.
- [ ] **T4 (P1)** — Implement exact-revision model preparation, read-only doctor, cache-only
  adapter execution, and cancellation-safe child cleanup.
- [ ] **T5 (P1)** — Add one runtime composition root and route CLI plus MCP through it without
  changing MCP tool schemas.
- [ ] **T6 (P2)** — Add one-object JSON contracts for ingest, run inspection, prepare, doctor, and
  real proof; keep logs on stderr.
- [ ] **T7 (P1)** — Add offline unit/integration coverage, Python 3.12/3.13 wheel-extra checks, and
  failure-injection tests for lifecycle atomicity.
- [ ] **T8 (P1)** — Add the licensed spoken fixture, cached real proof, constrained isolated-wheel
  CLI/MCP proof, platform evidence, ADR, and Diataxis documentation.

## Parallelization

The work is primarily sequential because lifecycle contracts feed runtime and runtime feeds proof:

```text
Lane A: protocol/schema -> SQLite lifecycle -> application integration
Lane B: fixture provenance and documentation skeleton (parallel after contracts stabilize)
Lane C: real proof and wheel/MCP deployment proof (waits for Lane A)
```

Do not split CLI and MCP into separate parallel implementations; both must share the same
composition and error contracts.

## Dream State Delta

D3-B establishes a provider-neutral execution and evidence contract that future remote or vendor
ASR providers can reuse. It does not yet provide asynchronous jobs, long-video checkpoints,
multi-worker coordination, quality evaluation, or remote deployment. Those are the remaining
12-month platform gaps, not hidden requirements of this slice.

## Stale Diagram Audit

- The design's D3-B pipeline remains accurate after adding the explicit prepare/preflight stage.
- `docs/explanation/architecture.md` and public contract diagrams must be updated in the behavior PR
  because they currently describe sidecar-backed video ingest only.
- No UI diagrams apply.

## Decision Audit Trail

| Decision | Result | Reason |
|---|---|---|
| Keep subprocess adapter architecture | Accepted | Preserves process isolation and reuses D3-A. |
| Add `transcription prepare` | Accepted | Separates network side effects from Run lifecycle and MCP. |
| Add async queue now | Deferred | Short synchronous proof is sufficient; queue is a separate architecture slice. |
| Share CLI/MCP composition and errors | Accepted | Prevents two divergent operational contracts. |
| Atomic report activation | Accepted | Prevents published-without-report and report-without-publication states. |
| Explicit short-media limits | Accepted | Timeout alone does not bound hashing, decode, memory, or segment volume. |
| Canonical hashed fingerprint | Accepted | Avoids delimiter ambiguity while reports retain readable identity. |
| Three-PR delivery | Accepted | Reduces review and diagnosis risk without reducing milestone scope. |
| Model-free required CI | Accepted | Keeps required checks deterministic and independent of model hosting. |
| Platform claims | Restricted | Only explicitly verified OS/architecture/Python combinations may be claimed. |

## Completion Summary

| Review area | Result |
|---|---|
| CEO | Direction approved; one selective addition; five major constraints hardened. |
| Design | Skipped; no UI scope. |
| Engineering | 10 findings incorporated; zero unresolved critical gaps in the reviewed design. |
| DX | Golden path, prepare/doctor split, JSON contracts, and platform-proof wording added. |
| Independent voice | Codex found issues consistent with the primary review; no substantive tension. |
| Scope | Three sequential PRs; no product-scope expansion into HTTP/cloud/queue/UI. |
| Unresolved technical decisions | 0 |
