# Multimodal Knowledge Engine

[中文说明](./README_CN.md)

Multimodal Knowledge Engine is a local-first Evidence engine for ingesting, searching, and asking questions over documents and media.

## Current Status

This repository now has a deterministic local product proof: `mke proof run` executes ordered
CLI-equivalent and MCP contract cases against a temporary SQLite workspace. It ingests a PyMuPDF
text-layer PDF and a short local video, proves failed PDF reprocessing leaves the active
Publication searchable, and verifies active-only Search and evidence-only Ask for page and
timestamp Evidence. The first Agent-facing interface is a local stdio MCP server for ingest, Run
inspection, active Evidence Search, and evidence-only Ask. HTTP and the workspace are not
implemented yet.

The proof covers the lifecycle boundary, not broad media support. It does not perform scanned-PDF
OCR, arbitrary video processing, bundled model weights, hosted coordination, or
external provider calls. D3-A adds an optional trusted-local `LocalCommandTranscriptProvider`
boundary and a proof-only `mke proof transcript-smoke` command, but normal ingest, MCP ingest,
`mke proof run`, and `mke demo --verify` remain sidecar-backed and deterministic. D3-B adds an
optional cache-only faster-whisper runtime for configured CLI and owner-started MCP; real
spoken-fixture proof remains deferred.

PDF intake uses PyMuPDF behind the `src/mke/adapters/pdf/` boundary and exposes a
`PdfIntakeReport` through `mke ingest`, `mke run get`, MCP `ingest_file`, and MCP `get_run`.
PyMuPDF licensing and the future sidecar escape route are documented in
[ADR-0004](./docs/decisions/0004-pymupdf-pdf-intake-adapter.md). MCP rejects PDF inputs above
100 MB before opening the extractor.

C2 Ask is evidence-only: `ask_library` and `mke ask` return cited page or timestamp Evidence when
active Search matches the question terms, or `insufficient_evidence` when it does not. MKE does
not call an LLM or generate natural-language answers in this slice.

## Verified Product Slice

The current verified product slice processes text-layer PDFs and the documented short local video
fixture through observable Runs, publishes only successful output, and returns page- or
timestamp-addressable Evidence.

## Architecture

- Project-owned domain models and ports.
- SQLite as domain truth.
- Rebuildable retrieval projections.
- Immutable content-addressed Assets and Artifacts.
- Search and Ask read only active Publications.
- One local owner process and worker for the Pilot.

See [Architecture](./docs/explanation/architecture.md) and [ADR-0001](./docs/decisions/0001-local-first-pilot-architecture.md).

## Documentation

Start at [docs/README.md](./docs/README.md). To verify the current proof directly, see
[Run The Local Product Proof](./docs/how-to/run-local-product-proof.md). To connect a local Agent,
see [Use MKE As A Local MCP Server](./docs/how-to/use-mke-mcp.md) and
[Use Local Transcription](./docs/how-to/use-local-transcription.md). Approved implementation history
is kept under `docs/superpowers/`; long-lived architecture decisions are kept under
`docs/decisions/`.

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the development workflow and [SECURITY.md](./SECURITY.md) for responsible vulnerability reporting.

## Development Status

The primary local proof is:

```bash
uv sync --locked
uv run mke proof run
uv run mke proof run --json
```

`mke demo --verify` remains available as a compatibility proof with its phase-oriented output.

The development checks are:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
```

The lower-level ingest and Search commands remain available:

```bash
uv run mke --db .tmp/mke.sqlite ingest tests/fixtures/pdf/text-layer.pdf
uv run mke --db .tmp/mke.sqlite ingest tests/fixtures/video/short-audio.mp4
uv run mke --db .tmp/mke.sqlite search trustworthy
uv run mke --db .tmp/mke.sqlite search timestamp
uv run mke --db .tmp/mke.sqlite ask "publication active"
uv run mke --db .tmp/mke.sqlite run get <run_id>
uv run mke --db .tmp/mke.sqlite mcp --allowed-root .
```

The default no-argument `mke` command still reports bootstrap status for compatibility.

## License

MIT. See [LICENSE](./LICENSE).
