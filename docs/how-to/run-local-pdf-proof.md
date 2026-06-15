# Run The Local PDF Proof

Use this workflow to verify the current trustworthy PDF slice from a clean checkout.

```bash
uv sync --locked
uv run mke demo --verify
```

The demo creates a temporary SQLite workspace, ingests the repository text-layer PDF fixture,
forces a failed reprocess, verifies the previous active Publication remains searchable, retries a
publishable candidate, and cleans up the temporary workspace before exit.

For lower-level inspection:

```bash
uv run mke --db .tmp/mke.sqlite ingest tests/fixtures/pdf/text-layer.pdf
uv run mke --db .tmp/mke.sqlite search trustworthy
uv run mke --db .tmp/mke.sqlite run get <run_id>
```

Remove `.tmp/mke.sqlite*` when done. The local proof does not require credentials, model downloads,
external services, or network calls.
