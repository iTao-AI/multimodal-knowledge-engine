# Real Video Intake Provider Port Design

## Goal

Build D3-A: a provider-port foundation for real local video transcription while keeping MKE's
current deterministic product proof stable.

D3-A should make the existing short-video path extensible:

- the default path still reads repository sidecars,
- the application layer can accept an injected transcript provider,
- a trusted local command can produce transcript JSON for an MP4 smoke path,
- failed transcription never publishes partial Evidence,
- `mke proof run` and `mke demo --verify` remain deterministic and offline.

This is a provider boundary and smoke slice, not a full audio/video processing platform.

## Current State

The existing video path is deterministic and sidecar-only.

- `KnowledgeEngine._process_video()` calls `extract_transcript_segments(path)` directly.
- `src/mke/adapters/video/transcript.py` reads `<video>.mke-transcript.json`.
- The sidecar format is `mke.video_transcript.v1`.
- The adapter validates media metadata, audio presence, supported codecs, non-empty text, and
  sorted integer millisecond timestamp ranges.
- `mke proof run` and `mke demo --verify` use the sidecar fixture path.
- MCP `ingest_file` routes `.mp4` files to the same `KnowledgeEngine.ingest_video()` path.

That shape is good for proof stability, but it makes real transcription hard to add without
polluting the application layer or duplicating validation logic.

## Decision

Introduce a transcript provider boundary:

```text
KnowledgeEngine
  -> TranscriptProvider.extract(path)
  -> TranscriptExtractionResult
  -> CandidateEvidence(timestamp_ms)
  -> RunManifest
  -> Publication activation
```

The first two providers are:

| Provider | Role | Default? |
|---|---|---|
| `SidecarTranscriptProvider` | Reads `<video>.mke-transcript.json` and preserves ADR-0003 behavior. | Yes |
| `LocalCommandTranscriptProvider` | Runs a trusted local argv command and parses MKE transcript JSON from stdout. | No |

`KnowledgeEngine` should accept `transcript_provider: TranscriptProvider | None = None`, matching
the existing `pdf_extractor` injection style. If no provider is supplied, it uses
`SidecarTranscriptProvider`.

## Transcript Schema

D3-A reuses the existing `mke.video_transcript.v1` JSON shape. The schema is project-owned and
provider-neutral:

```json
{
  "format": "mke.video_transcript.v1",
  "media": {
    "container": "mp4",
    "video_codec": "h264",
    "audio_codec": "aac",
    "has_audio": true,
    "duration_ms": 2200
  },
  "segments": [
    {"start_ms": 0, "end_ms": 1200, "text": "Video evidence introduces timestamp search."}
  ]
}
```

Both sidecar and local-command output must use the same parser and validation module. The parser
must reject:

- non-object JSON,
- unsupported `format`,
- explicit `transcription_error`,
- missing audio,
- unsupported MP4 profile,
- empty segment list,
- non-object segments,
- non-integer timestamps,
- negative or non-increasing timestamp ranges,
- overlapping or unsorted ranges,
- empty text.

Tests should target the public parser/validator, not private sidecar helper functions.

## Local Command Provider

`LocalCommandTranscriptProvider` is an adapter for trusted local commands. It is designed for local
operator smoke tests and future wrappers around tools such as `whisper.cpp`, OpenAI Whisper, or
faster-whisper. D3-A does not bundle or invoke those tools directly.

Configuration:

```text
LocalCommandTranscriptConfig(
  argv=("transcribe-wrapper", "--input", "{input}"),
  timeout_seconds=60,
  max_stdout_bytes=1048576,
  max_stderr_bytes=65536,
  extractor_fingerprint="local-command-video-transcript-v1",
)
```

Rules:

- `argv` must be a tuple/list of strings.
- `argv` must contain exactly one `{input}` placeholder.
- The provider replaces `{input}` with the input file path.
- The provider runs with `shell=False`.
- The provider parses stdout as UTF-8 JSON.
- stderr is only for diagnostics and must not be returned through public contracts.
- Timeouts, non-zero exits, missing executables, invalid JSON, oversized output, and validation
  errors raise `VideoExtractionError` with stable operator-facing messages.

## Public Surface

D3-A should not change MCP tool schemas.

MCP remains:

```text
ingest_file(config, path)
```

Agents cannot supply a transcription command through MCP. If a future owner process supports local
provider configuration, that configuration must be process-level trusted configuration, not a
per-request Agent payload.

CLI behavior:

- Existing `mke --db <path> ingest <file>` continues to use the default sidecar provider.
- Existing `mke proof run` continues to force the deterministic sidecar path.
- Existing `mke demo --verify` continues to force the deterministic sidecar path.
- D3-A adds a proof-only smoke command for local operators:

```bash
mke proof transcript-smoke --fixture tests/fixtures/video/short-audio.mp4 -- transcribe-wrapper --input {input}
```

That smoke command is not the normal ingest contract and is not exposed through MCP. It exists to
verify the local command provider in a temporary SQLite workspace without changing deterministic
proof behavior.

## Data Flow

```text
MP4 file
  -> KnowledgeEngine.ingest_video(path)
  -> injected TranscriptProvider
      -> SidecarTranscriptProvider OR LocalCommandTranscriptProvider
      -> shared transcript schema parser
      -> TranscriptExtractionResult
  -> CandidateEvidence(locator_kind="timestamp_ms")
  -> RunManifest(extractor_fingerprint=<provider fingerprint>)
  -> persist_validated_candidate()
  -> activate_publication()
  -> Search / Ask reads active Publication only
```

## Failure Semantics

All provider failures fail closed:

- the Run is marked `failed`,
- no candidate Evidence becomes searchable,
- active Search remains unchanged,
- CLI and MCP return `video_ingest_failed`,
- no absolute local paths, stack traces, command argv, provider stderr, credentials, or private
  temp paths appear in public error payloads.

`mke proof run` must not fail because a local transcription command is unavailable. It does not use
the local command provider.

## Testing Strategy

Required tests:

- sidecar provider preserves current fixture behavior,
- shared parser accepts valid `mke.video_transcript.v1`,
- shared parser rejects malformed JSON, unsupported formats, empty segments, invalid timestamp
  ranges, overlap, and empty text,
- `KnowledgeEngine` accepts an injected transcript provider,
- local command provider succeeds with a fake command that emits valid transcript JSON,
- local command provider rejects non-zero exit, timeout, invalid JSON, oversized stdout/stderr, and
  missing executable,
- local command provider uses argv with `shell=False`,
- normal CLI ingest and MCP ingest do not accept provider command overrides,
- failed local command ingest leaves active PDF or video Search unchanged,
- `mke proof run` and `mke demo --verify` still pass through the deterministic sidecar path.

## Non-Goals

- `.mp3`, `.m4a`, `.wav`, or other audio-only ingest.
- Long-video chunking.
- Diarization.
- OCR or scanned-PDF changes.
- Bundled `faster-whisper`, `whisper.cpp`, OpenAI Whisper, or cloud ASR integration.
- Model download, model cache, GPU scheduling, or external provider credentials.
- MCP request-time command execution.
- HTTP, workspace UI, or background worker orchestration.
- Retrieval-quality metrics.

## Documentation Impact

The implementation PR should update:

- `docs/decisions/0005-optional-local-command-transcription-provider.md`,
- `docs/reference/cli.md`,
- `docs/reference/contracts.md`,
- `docs/explanation/architecture.md`,
- `docs/how-to/run-local-product-proof.md` if proof behavior or smoke commands are documented,
- `README.md` and `README_CN.md` if the current status changes.

## Acceptance Criteria

- The application uses a transcript provider port.
- The sidecar path remains the default and current proof commands remain deterministic.
- A fake local command can produce timestamp Evidence through the same Publication lifecycle.
- Local command failures leave active Search unchanged.
- MCP cannot receive or execute a transcription command from a request.
- All verification commands pass:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
```
