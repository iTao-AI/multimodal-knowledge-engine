# Run The Local Product Proof

Use this workflow to verify the current trustworthy PDF and short-video slice from a clean
checkout.

```bash
uv sync --locked
uv run mke proof run
uv run mke proof run --json
```

The proof runner creates a temporary SQLite workspace, executes ordered CLI-equivalent application
checks and MCP contract checks, and cleans up the temporary workspace before exit. The JSON report
uses public-safe scalar fields and does not include absolute local paths, Run IDs, Evidence IDs, raw
Evidence text, or temporary directory names.

`mke demo --verify` remains available and keeps its phase-oriented output, but `mke proof run` is
the primary product proof entrypoint.

## What This Proves

- PyMuPDF text-layer PDF ingest can publish page-addressed Evidence and report intake diagnostics.
- Short local video fixture ingest can publish timestamp-addressed Evidence.
- Failed PDF reprocessing leaves the previous active Publication searchable.
- Search and evidence-only Ask read only active Publication rows.
- MCP `ingest_file`, `get_run`, `search_library`, and `ask_library` expose the same contract-ready
  behavior in process.

## Proof Cases

- `cli_pdf_ingest`
- `cli_pdf_search`
- `cli_failed_reprocess`
- `cli_video_ingest_search`
- `cli_ask`
- `mcp_ingest_file`
- `mcp_get_run`
- `mcp_search_and_ask`

## What This Does Not Prove

- Scanned-PDF OCR.
- Table extraction, page coordinates, or layout-aware chunking.
- Unicode-aware retrieval beyond the current ASCII Search tokenization.
- Arbitrary or long-video processing.
- Real speech-model transcription.
- HTTP or workspace UI.
- stdio MCP server startup; see [Use MKE As A Local MCP Server](./use-mke-mcp.md).
- Hosted coordination, multi-worker behavior, or external provider integration.

For lower-level inspection:

```bash
uv run mke --db .tmp/mke.sqlite ingest tests/fixtures/pdf/text-layer.pdf
uv run mke --db .tmp/mke.sqlite ingest tests/fixtures/video/short-audio.mp4
uv run mke --db .tmp/mke.sqlite search trustworthy
uv run mke --db .tmp/mke.sqlite search timestamp
uv run mke --db .tmp/mke.sqlite ask "publication active"
uv run mke --db .tmp/mke.sqlite run get <run_id>
```

Remove `.tmp/mke.sqlite*` when done. The local proof does not require credentials, model downloads,
external services, `ffmpeg`, or network calls at runtime.

For local PDF intake smoke coverage against public-safe or private local PDFs, run:

```bash
uv run python scripts/pdf_intake_smoke.py <pdf-directory>
```

The smoke harness prints redacted aggregate JSON using filenames only. Do not commit private source
PDFs, private local paths, or raw private extraction output.
