# Use Local Transcription

This guide configures optional cache-only `faster-whisper`. Real ASR proof evidence is deferred to
PR 3.

## Install And Prepare

```bash
uv sync --locked --extra transcription
uv run mke transcription prepare --allow-model-download --json
```

Preparation is the only download-capable path. It opens no database, creates no Run, and returns
`already_cached` or `downloaded` without exposing cache paths.

## Check Readiness

```bash
uv run mke transcription doctor --json
```

Doctor is read-only and cache-only. Exit codes are `0` ready, `1` not ready, and `2` invalid usage.

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
