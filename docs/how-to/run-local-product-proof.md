# Run The Local Product Proof

Use this workflow to verify the current trustworthy PDF and short-video slice from a clean
checkout.

```bash
uv sync --locked
uv run mke demo --verify
```

The demo creates a temporary SQLite workspace, ingests the repository text-layer PDF fixture,
forces a failed PDF reprocess, verifies the previous active Publication remains searchable,
retries a publishable candidate, ingests the repository short-video fixture with timestamp
Evidence, and cleans up the temporary workspace before exit.

## What This Proves

- Text-layer PDF ingest can publish page-addressed Evidence.
- Short local video fixture ingest can publish timestamp-addressed Evidence.
- Failed PDF reprocessing leaves the previous active Publication searchable.
- Retry creates a new Run and can publish validated candidate output.
- Search reads only active Publication rows.

## What This Does Not Prove

- Scanned-PDF OCR.
- Arbitrary or long-video processing.
- Real speech-model transcription.
- Ask, MCP, HTTP, or workspace UI.
- Hosted coordination, multi-worker behavior, or external provider integration.

For lower-level inspection:

```bash
uv run mke --db .tmp/mke.sqlite ingest tests/fixtures/pdf/text-layer.pdf
uv run mke --db .tmp/mke.sqlite ingest tests/fixtures/video/short-audio.mp4
uv run mke --db .tmp/mke.sqlite search trustworthy
uv run mke --db .tmp/mke.sqlite search timestamp
uv run mke --db .tmp/mke.sqlite run get <run_id>
```

Remove `.tmp/mke.sqlite*` when done. The local proof does not require credentials, model downloads,
external services, `ffmpeg`, or network calls at runtime.
