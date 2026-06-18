# Real Local Transcription Runtime And Interfaces Review

## Status

- Result: all eight authoritative findings independently reproduced and resolved locally
- Scope: D3-B PR 2 only
- Review date: 2026-06-19
- Push / PR: not performed

## Scope Check

The remediation remains inside optional runtime configuration, preparation and doctor behavior,
cache-only adapter execution, shared CLI/MCP composition, cancellation cleanup, model-free
packaging, ADRs, and documentation. It does not download a model, add a spoken fixture, run real
ASR proof, or add PR 3 deployment-proof work.

## Finding Disposition

| # | Review finding | Verification | Resolution |
|---|---|---|---|
| 1 | Invalid owner configuration leaked a traceback and absolute paths. | Reproduced with `mke transcription doctor --model ../bad --json`. | Configuration construction is inside the argparse usage boundary; invalid values exit 2 without traceback output. |
| 2 | Missing optional runtime was classified as unsupported media. | Reproduced by making PyAV unavailable before `probe_media()`. | Optional runtime imports now precede media probing and map to `DEPENDENCY_MISSING`. |
| 3 | `AdapterFailureSpec.problem` and `next_step` were discarded. | Reproduced across provider, application, CLI, and MCP error flow. | Typed recovery fields now survive every layer and reach the shared public serializer. |
| 4 | Provenance recorded requested rather than resolved runtime profile. | Confirmed against locked faster-whisper 1.2.1 source and a fake CTranslate2 runtime profile. | Provenance and fingerprint input now use `model.model.device` and `model.model.compute_type`. |
| 5 | CLI ingest validated explicit language only after Run creation. | Reproduced by observing engine construction before readiness. | Faster-whisper MP4 ingest runs cache-only readiness before engine construction or SQLite creation. |
| 6 | Cancellation could precede child registration. | Reproduced with a worker that registers its process after cancellation. | `ActiveProcessController` latches cancellation for the active worker and immediately terminates late registrations. |
| 7 | Limits accepted NaN and fractional integer fields. | Reproduced for `timeout_seconds=NaN` and all integer resource slots. | Integer slots require exact positive integers; timeout must be positive and finite. |
| 8 | Completion record claimed a review artifact that did not exist. | Confirmed against the plan and review directory. | This durable review is persisted and the plan completion record names the actual review and remediation state. |

## Regression Coverage

Regression tests cover CLI usage redaction, no-Run language preflight, dependency classification,
typed recovery propagation, resolved runtime provenance, late child registration after
cancellation, and strict limit validation.

## Verification

Targeted remediation verification:

| Command | Result |
|---|---|
| targeted pytest set across runtime, adapter, application, CLI, and MCP | `154 passed, 5 warnings` |
| targeted Ruff | passed |
| `uv run pyright` | `0 errors, 0 warnings, 0 informations` |

Complete verification after documentation:

| Command | Result |
|---|---|
| `uv sync --locked` | passed |
| `uv run pytest -q` | `364 passed, 5 warnings` |
| `uv run ruff check .` | passed |
| `uv run pyright` | `0 errors, 0 warnings, 0 informations` |
| `uv build` | sdist and wheel built successfully |
| `uv run mke proof run` | passed, `8/8` cases |
| `uv run mke demo --verify` | passed |
| Python 3.13 `wheel[transcription]` isolated install and imports | passed |
| Empty-cache `mke transcription doctor --json` | expected `not_ready`, no model download |
| `git diff --check` | passed |

## Remaining Risk

Real model loading and spoken-media transcription remain intentionally unverified in PR 2. Those
platform-specific proof obligations remain deferred to PR 3. The current tests verify the locked
API shape and model-free control flow without downloading weights.
