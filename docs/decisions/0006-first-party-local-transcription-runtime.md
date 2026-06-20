# ADR-0006: First-Party Local Transcription Runtime

## Status

Accepted and implemented across all three D3-B stages: protocol and lifecycle in PR #16
(`98ac84f`), runtime and interfaces in PR #17 (`7a8c82b`), and deployment proof and documentation
in PR #18 (`cc4df1b`).

## Decision

MKE ships `faster-whisper` 1.x, PyAV, and `huggingface-hub` in the optional `transcription` extra.
The adapter runs as `python -m mke.adapters.video.faster_whisper_cli` through the current
interpreter. Defaults are model `small`, revision
`536b0662742c02347bc0e980a01041f333bce120`, `cpu`, `int8`, and language `auto`.
`faster-whisper` is MIT licensed; PyAV is BSD-3-Clause licensed.

Only `mke transcription prepare --allow-model-download` may populate the model cache. Doctor,
CLI ingest, MCP startup, and adapter execution use exact-revision cache-only resolution. CLI and
MCP share one typed `RuntimeConfig`; MCP tool inputs cannot override owner provider policy.
CLI faster-whisper ingest completes the same read-only readiness check before opening SQLite or
creating a Run. Successful provenance records the device and compute type resolved by CTranslate2,
not unresolved owner values such as `auto` or `default`.

Registered adapter children are terminated and waited during cancellation or shutdown. The owner
process keeps cancellation latched until the active worker exits, so a child registered after the
initial cancellation signal is terminated immediately.

Required Python 3.12/3.13 CI installs the core wheel and `wheel[transcription]` without a model.
Rollback selects the default sidecar provider.

## Verified Deployment Evidence

The redistribution-safe spoken fixture, cache-only `mke proof transcription-run`, and isolated
wheel-installed CLI plus stdio MCP SDK proof are implemented. Real ASR was verified on Darwin
25.4.0 arm64 with Python 3.13.12, faster-whisper 1.2.1, CTranslate2 4.8.0, and PyAV 17.1.0. The
isolated wheel proof was verified with Python 3.12. These observations establish deployment
evidence for that environment only; they are not quality or performance benchmarks.

HTTP, remote/vendor ASR, queues, long-video processing, audio-only ingest, diarization, GPU
scheduling, request-time provider selection, and quality benchmarking remain out of scope.
