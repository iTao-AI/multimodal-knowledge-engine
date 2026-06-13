# Getting Started

The repository is in the bootstrap stage. The development baseline is verified, but no product workflow exists yet.

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

Use the repository only to review the accepted architecture, public contracts, delivery workflow, and development baseline until product commands are implemented.
