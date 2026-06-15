# Getting Started

The repository has a verified bootstrap baseline and a narrow PR 2 PDF CLI path. The golden demo and broader product workflows are still planned.

## Prepare The Environment

Install the development dependencies:

```bash
uv sync
```

## Verify The Bootstrap

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke
```

The build command creates an sdist and wheel under `dist/`. The final command prints:

```text
multimodal-knowledge-engine: bootstrap stage
```

## Try The Narrow PDF Path

```bash
uv run mke --db .tmp/mke.sqlite ingest tests/fixtures/pdf/text-layer.pdf
uv run mke --db .tmp/mke.sqlite search trustworthy
```

This path supports only deterministic text-layer PDFs and active Publication Search. It does not
cover scanned-PDF OCR, failure injection, retry lineage, Run observability, video, Ask, MCP, or
`mke demo --verify`; those remain later milestones.
