# Use Local Transcription

This guide configures the optional cache-only `faster-whisper` runtime for short spoken MP4 input.
The core install and deterministic product proof remain model-free.

## Install And Prepare

```bash
uv sync --locked --extra transcription
uv run mke transcription prepare \
  --allow-model-download \
  --model small \
  --model-revision 536b0662742c02347bc0e980a01041f333bce120 \
  --model-cache <external-model-cache> \
  --json
```

Preparation is the only download-capable path. It opens no database, creates no Run, and returns
`already_cached` or `downloaded` without exposing cache paths.

## Check Readiness

```bash
HF_HUB_OFFLINE=1 uv run mke transcription doctor \
  --model small \
  --model-revision 536b0662742c02347bc0e980a01041f333bce120 \
  --model-cache <external-model-cache> \
  --json
```

Doctor is read-only and cache-only. Exit codes are `0` ready, `1` not ready, and `2` invalid usage.

An incomplete snapshot is not ready: the exact revision must include the required model,
configuration, tokenizer, and vocabulary files.

## Run The Real ASR Proof

After preparation, run the proof cache-only:

```bash
HF_HUB_OFFLINE=1 uv run mke proof transcription-run \
  --fixture tests/fixtures/video/spoken-evidence.mp4 \
  --model small \
  --model-revision 536b0662742c02347bc0e980a01041f333bce120 \
  --model-cache <external-model-cache> \
  --json
```

The repository fixture uses redistributable synthetic speech and has no transcript sidecar. The
proof validates a published Run, timestamp Evidence, keyword Search, evidence-only Ask, and a
complete transcription intake report without asserting an exact full transcript.

One verified observation on Darwin 25.4.0 arm64 with Python 3.13.12,
`faster-whisper` 1.2.1, CTranslate2 4.8.0, and PyAV 17.1.0 completed in 3038 ms.
This is execution evidence, not a quality or performance guarantee. Other platforms remain
unverified.

## Ingest

```bash
uv run mke --db .tmp/mke.sqlite ingest speech.mp4 \
  --transcript-provider faster-whisper --json
uv run mke --db .tmp/mke.sqlite run get <run_id> --json
```

The supported profile is MP4/H.264/AAC up to 100 MiB, 15 minutes, and 10,000 segments. Override
trusted owner settings with `--model`, `--model-revision`, `--device`, `--compute-type`,
`--language`, `--model-cache`, and `--transcription-timeout-seconds`.

If the model is absent, run preparation explicitly. Failed or cancelled ingest leaves the active
Publication unchanged. Omit `--transcript-provider` to return to deterministic sidecar ingest.

Normal doctor, ingest, proof, and MCP execution never enable model download. HTTP, remote or vendor
ASR, long-video support, audio-only ingest, diarization, GPU scheduling, and quality benchmarking
remain outside this workflow.
