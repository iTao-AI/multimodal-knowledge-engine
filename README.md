# Multimodal Knowledge Engine

[中文说明](./README_CN.md)

Multimodal Knowledge Engine is a local-first Evidence engine for ingesting, searching, and asking questions over documents and media.

## Current Status

This repository now has a deterministic local cross-modal proof: `mke demo --verify` ingests a
text-layer PDF and a short local video, proves failed PDF reprocessing leaves the active
Publication searchable, retries the validated candidate path, and verifies active-only Search for
page and timestamp Evidence. Ask, MCP, HTTP, and the workspace are not implemented yet.

The proof covers the lifecycle boundary, not broad media support. It does not perform scanned-PDF
OCR, arbitrary video processing, real speech-model transcription, hosted coordination, or external
provider calls.

## Pilot Goal

The first verified product slice will process one PDF and one short local video through observable Runs, publish only successful output, and return page- or timestamp-addressable Evidence.

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
[Run The Local Product Proof](./docs/how-to/run-local-product-proof.md). Approved implementation
history is kept under `docs/superpowers/`; long-lived architecture decisions are kept under
`docs/decisions/`.

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the development workflow and [SECURITY.md](./SECURITY.md) for responsible vulnerability reporting.

## Development Status

The primary local proof is:

```bash
uv sync --locked
uv run mke demo --verify
```

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
uv run mke --db .tmp/mke.sqlite run get <run_id>
```

The default no-argument `mke` command still reports bootstrap status for compatibility.

## License

MIT. See [LICENSE](./LICENSE).
