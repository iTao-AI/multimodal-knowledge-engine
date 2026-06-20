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

`mke proof run` and `mke demo --verify` intentionally use the deterministic sidecar transcript
provider. They do not load or download a speech model.

## Optional Cache-Only Real Transcription Proof

After explicitly preparing the exact model revision described in
[Use Local Transcription](./use-local-transcription.md), run:

```bash
HF_HUB_OFFLINE=1 uv run mke proof transcription-run \
  --fixture tests/fixtures/video/spoken-evidence.mp4 \
  --model small \
  --model-revision 536b0662742c02347bc0e980a01041f333bce120 \
  --model-cache <external-model-cache> \
  --json
```

This separate proof executes real local ASR and validates a published Run, timestamp Evidence,
keyword Search, and evidence-only Ask. It is cache-only and does not change the deterministic
eight-case proof.

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
- Bundled model weights or speech-model quality evaluation.
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

Remove `.tmp/mke.sqlite*` when done. The deterministic local proof does not require credentials,
model downloads, external services, `ffmpeg`, or network calls at runtime. The optional real proof
requires a separately prepared exact model revision but remains cache-only while it runs.

## Optional Local Transcript Smoke

D3-A adds a proof-only local command smoke path for trusted operators who already have a local
transcriber wrapper. It proves that command-produced `mke.video_transcript.v1` JSON can flow
through the same Run, Publication, Search, and Ask lifecycle:

```bash
uv run mke proof transcript-smoke --fixture tests/fixtures/video/short-audio.mp4 -- <transcriber-command> {input}
```

The command is passed as argv and runs with `shell=False`. It must write a valid transcript JSON
object to stdout. This smoke command is not exposed through MCP, and normal `mke ingest` requests
cannot supply command argv. Public failures use `video_ingest_failed` without exposing argv,
stderr, absolute paths, stack traces, secrets, or temporary directory names.

For local PDF intake smoke coverage against public-safe or private local PDFs, run:

```bash
uv run python scripts/pdf_intake_smoke.py <pdf-directory>
```

The smoke harness prints redacted aggregate JSON using filenames only. Do not commit private source
PDFs, private local paths, or raw private extraction output.
