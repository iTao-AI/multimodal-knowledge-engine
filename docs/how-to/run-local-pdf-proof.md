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
