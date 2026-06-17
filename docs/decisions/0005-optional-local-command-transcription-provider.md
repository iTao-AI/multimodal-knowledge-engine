# ADR-0005: Optional Local Command Transcription Provider

- Status: Accepted
- Date: 2026-06-17

## Context

ADR-0003 intentionally kept video transcription deterministic by reading a local
`mke.video_transcript.v1` sidecar. That decision made the PDF and short-video proof stable,
offline, and CI-friendly, but it also means the project cannot yet prove that a real local
transcription process can feed timestamp Evidence into the same Publication lifecycle.

D3-A adds the first real transcription extension point without turning MKE into a broad media
processing platform. The immediate target is a short MP4 smoke path. General audio formats,
large-video processing, diarization, hosted transcription, and bundled speech-model runtimes remain
outside this decision.

## Decision

- Add a project-owned `TranscriptProvider` port behind `KnowledgeEngine`.
- Keep the sidecar provider as the default provider for normal product proof, `mke proof run`, and
  `mke demo --verify`.
- Add an optional `LocalCommandTranscriptProvider` for trusted local operator smoke tests.
- The local command provider accepts only an argv tuple/list, never a shell string.
- The implementation must run commands with `shell=False`.
- The command configuration must be trusted local configuration or an explicit proof-only smoke
  command. MCP requests and normal ingest requests must not include provider commands.
- The command receives the input path through an explicit `{input}` argv placeholder.
- The command writes a project-owned transcript JSON object to stdout.
- D3-A reuses the existing `mke.video_transcript.v1` transcript JSON shape so sidecar and local
  command output share the same parser and validation rules.
- The provider must enforce timeout, stdout and stderr size limits, stable failure messages, and
  cleanup after failure.

## Consequences

- MKE gains a real transcription adapter boundary while preserving deterministic proof behavior.
- Agent-facing MCP contracts stay narrow: Agents can ask MKE to ingest a file, but cannot supply a
  command to execute.
- Local command failures fail the Run and leave active Search unchanged.
- Future providers such as `faster-whisper`, `whisper.cpp`, cloud ASR, diarization, or audio-only
  ingest can be added behind the same port without changing Source Publication semantics.
- This ADR does not authorize bundled speech models, network calls, provider credentials, arbitrary
  command execution through MCP, long-video processing, general audio ingest, or generated answers.
