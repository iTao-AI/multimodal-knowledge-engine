# ADR-0006: First-Party Local Transcription Runtime

## Status

Accepted for D3-B PR 2.

## Decision

MKE ships `faster-whisper` 1.x, PyAV, and `huggingface-hub` in the optional `transcription` extra.
The adapter runs as `python -m mke.adapters.video.faster_whisper_cli` through the current
interpreter. Defaults are model `small`, revision
`536b0662742c02347bc0e980a01041f333bce120`, `cpu`, `int8`, and language `auto`.
`faster-whisper` is MIT licensed; PyAV is BSD-3-Clause licensed.

Only `mke transcription prepare --allow-model-download` may populate the model cache. Doctor,
CLI ingest, MCP startup, and adapter execution use exact-revision cache-only resolution. CLI and
MCP share one typed `RuntimeConfig`; MCP tool inputs cannot override owner provider policy.
Registered adapter children are terminated and waited during cancellation or shutdown.

Required Python 3.12/3.13 CI installs the core wheel and `wheel[transcription]` without a model.
Rollback selects the default sidecar provider.

## Deferred

Real spoken-fixture evidence and real-model proof remain in PR 3. HTTP, remote/vendor ASR, queues,
long-video processing, and request-time provider selection remain out of scope.
