# ADR-0003: Video Dependency And Transcription Strategy

- Status: Accepted
- Date: 2026-06-15

## Context

PR 4 adds the first short local video path to the same Source Publication lifecycle that already
protects PDF Evidence. The slice must stay deterministic, offline, and CI-friendly. It must not
turn the repository into a video processing platform, download large speech models, call external
transcription services, or depend on hosted worker architecture.

The product proof needs timestamp Evidence, not a general media pipeline.

## Decision

- The PR 4 runtime supports one documented local video profile:
  - MP4 container.
  - H.264 video track.
  - AAC audio track.
  - Short fixture-sized media intended for deterministic tests and demo proof.
- Video Evidence uses integer millisecond locators:
  - `locator_kind = "timestamp_ms"`.
  - `locator_start` and `locator_end` are non-negative integers.
  - `locator_end` must be greater than `locator_start`.
  - Segments must be generated in stable ascending order.
- Transcription is represented by a project-owned adapter that reads a deterministic local
  transcript sidecar next to the video fixture.
  - Sidecar format is JSON and versioned as `mke.video_transcript.v1`.
  - The sidecar records container, video codec, audio codec, audio presence, duration, and
    transcript segments.
  - The adapter rejects missing audio, unsupported codecs, explicit transcription failure, empty
    transcript text, and unstable timestamp ranges before candidate Evidence can publish.
- `ffmpeg` / `ffprobe` are optional fixture maintenance tools, not runtime dependencies.
  - They may be used by maintainers to generate or inspect fixtures.
  - CI and wheel-installed `mke demo --verify` must not require `ffmpeg` or `ffprobe`.
- Model and cache behavior for PR 4 is intentionally simple:
  - No speech model is downloaded.
  - No provider credentials are read.
  - No network calls are made.
  - No persistent model cache is created.
- Fixture policy:
  - The repository fixture is generated test media with repository-compatible licensing.
  - Fixture size must stay small enough for normal source checkout and CI.
  - The transcript sidecar is the canonical expected transcription for the fixture.
- CI strategy:
  - Run the normal test suite.
  - Build the package.
  - Install the wheel.
  - Run wheel-installed `mke demo --verify`, which proves both PDF page Evidence and video
    timestamp Evidence without external dependencies.

## Consequences

- PR 4 proves the lifecycle and timestamp Evidence contract without taking on nondeterministic
  speech recognition.
- Unsupported real-world video files fail closed and leave active Search unchanged.
- A future real transcription adapter can replace the deterministic sidecar adapter behind the
  same application boundary, but must preserve offline/CI behavior or introduce a separate
  optional smoke path.
- This ADR does not authorize Ask, MCP, HTTP, workspace UI, OCR, long-video processing, external
  services, model downloads, or hosted multi-worker coordination.
