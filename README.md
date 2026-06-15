# Multimodal Knowledge Engine

[中文说明](./README_CN.md)

Multimodal Knowledge Engine is a local-first Evidence engine for ingesting, searching, and asking questions over documents and media.

## Current Status

This repository now has the first narrow PDF CLI slice: a text-layer PDF can be ingested into SQLite, atomically published, and searched through active Publication Evidence. Video processing, Ask, MCP, the workspace, and the golden `mke demo --verify` proof are not implemented yet.

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

Start at [docs/README.md](./docs/README.md). Approved implementation history is kept under `docs/superpowers/`; long-lived architecture decisions are kept under `docs/decisions/`.

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the development workflow and [SECURITY.md](./SECURITY.md) for responsible vulnerability reporting.

## Development Status

The bootstrap development baseline is available:

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke
```

The narrow PDF commands are available:

```bash
uv run mke --db .tmp/mke.sqlite ingest tests/fixtures/pdf/text-layer.pdf
uv run mke --db .tmp/mke.sqlite search trustworthy
```

The default no-argument `mke` command still reports bootstrap status. `mke demo --verify` remains a PR 3 target.

## License

MIT. See [LICENSE](./LICENSE).
