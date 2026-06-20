# Architecture

## Product Boundary

Multimodal Knowledge Engine converts documents and media into published Evidence that users and Agents can search, cite, and ask questions over.

## Domain Vocabulary

`Library`, `Source`, `Asset`, `Run`, `Artifact`, `Segment`, `Passage`, `Evidence`, and `Publication` are the public product concepts.

## Lifecycle

```text
Source
  -> immutable Asset
  -> observable Run
  -> candidate Evidence and RunManifest
  -> validated Run
  -> active Search projection
  -> atomic Publication switch
  -> Search / Ask Evidence
```

A failed, interrupted, superseded, or partial Run never changes the active Publication. Retry
creates a new immutable Run.

The current PDF and short-video slices implement only the lifecycle concepts needed to prove
trustworthy Search:
`Library`, `Source`, `Asset`, `Run`, `Evidence`, `RunManifest`, and `Publication`. `Artifact`,
`Segment`, and `Passage` remain public vocabulary for later cross-modal and Ask workflows, but
their durable semantics are not stabilized before the PDF and video slices validate the lifecycle.

## Publication Semantics

Publication is atomic per `Source`.

```text
candidate Evidence + RunManifest
  -> validate counts, locators, extractor fingerprint, required stages
  -> check Run generation and Source active revision
  -> create Publication
  -> replace this Source's active FTS5 rows
  -> switch Source.active_publication_id
  -> persist a successful transcript intake report when required
  -> mark Run published
```

Candidate, failed, superseded, or historical output is not stored in the active FTS5 projection.
Search reads only active Publication rows and joins back through the active Publication identity.
A stale Run that loses the Source generation or active revision check is marked `superseded`
without changing active Search visibility.

For recognized `faster-whisper-v1:<64 lowercase hex>` Manifests, activation additionally requires
a validated `TranscriptIntakeReport`. The Publication row, active FTS5 replacement, Source pointer,
successful report, `published` Run state, and publication event commit in one SQLite transaction.
Any failure rolls all of them back. Failed and superseded Runs therefore cannot expose a successful
report, and legacy PDF or sidecar video Publications remain valid without one.

## Transcript Protocol

The provider-neutral transcript boundary uses project-owned `VideoMediaInfo`,
`VideoTranscriptSegment`, optional `TranscriptionProvenance`, `ParsedVideoTranscript`, and
`TranscriptExtractionResult` DTOs. Existing `mke.video_transcript.v1` sidecars may omit the
additive `transcription` object. First-party faster-whisper output must provide complete validated
provenance before a later runtime adapter can construct a successful `TranscriptIntakeReport`.

The shared parser enforces a 15-minute media-duration limit, a 10,000-segment limit, positive
integer millisecond media duration, stable timestamp ranges within that duration, bounded identity
strings, and exact provider/model revision rules. Application preflight rejects missing, empty,
non-MP4, or over-100-MiB inputs before hashing, provider execution, or Run creation.

## Current Runtime Shape

The runtime is an in-process CLI plus a project-owned application service. SQLite remains the
domain truth and owns the rebuildable active FTS5 projection. The built-in PDF adapter extracts
page-addressed text Evidence from deterministic text-layer PDFs. Video transcription now sits
behind a project-owned `TranscriptProvider` port: the default `SidecarTranscriptProvider` reads
timestamp-addressed transcript Evidence from a deterministic local sidecar for the documented
short MP4 fixture profile, while `LocalCommandTranscriptProvider` also binds the package-owned
faster-whisper subprocess. `src/mke/runtime.py` is the shared CLI/MCP composition root. Preparation
is explicit; doctor, ingest, MCP startup, and adapter execution are cache-only. Requests cannot
supply command argv or download policy. Deterministic proof remains sidecar-backed and model-free.
CLI faster-whisper ingest performs readiness before engine construction, while successful
provenance uses the runtime profile resolved by CTranslate2. Adapter failure metadata remains typed
through the provider and application layers so interfaces can return the correct operator action.
Cancellation remains latched for the active MCP worker, closing the interval between worker start
and child-process registration.

The real transcription proof builds a temporary SQLite workspace and invokes the same application
composition without calling model preparation. The deployment proof builds the project wheel,
installs `wheel[transcription]` under lock-derived constraints in an external temporary
environment, then compares installed CLI results with a real stdio MCP Python SDK client. Both
paths require an already prepared exact model revision and remain cache-only.

CLI and MCP errors share one project-owned `PublicError` serializer. Only allowlisted stable causes
can reach public output; unknown exception text is replaced with
`operation failed; details were redacted`. Public payloads contain `problem`, `cause`,
`active_publication_impact`, `next_step`, and an optional `run_id`, never local paths, argv, stderr,
cache locations, endpoints, secrets, or tracebacks.

## Current Module Shape

```text
src/mke/
  runtime.py
  domain/
  application/
  adapters/
    pdf/
    sqlite/
    video/
      faster_whisper.py
      faster_whisper_cli.py
      process.py
  interfaces/
  proof/
    transcription.py
    mcp_deployment_client.py
```

The domain and application layers must not depend on FastAPI, database implementations, model SDKs, LangChain, or LlamaIndex.
