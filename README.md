# Multimodal Knowledge Engine

[中文说明](./README_CN.md)

Multimodal Knowledge Engine is a local-first Evidence engine for ingesting, searching, and asking questions over documents and media.

## Current Status

This repository is in the bootstrap stage. It currently defines the approved Pilot architecture, documentation governance, and delivery workflow. PDF ingestion, video processing, Search, Ask, MCP, and the workspace are not implemented yet.

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

## Development Status

The bootstrap development baseline is available:

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run pyright
uv run mke
```

The `mke` command currently reports bootstrap status only. Product workflows remain unimplemented.
