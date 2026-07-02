# Changelog

## [0.1.0] - 2026-07-02

### Added

- First public small-version identity for Multimodal Knowledge Engine.
- Local-first Library, Source, Run, Evidence, and Publication lifecycle over SQLite domain truth.
- Deterministic CLI proof with `mke proof run` and compatibility proof with `mke demo --verify`.
- Text-layer PDF ingest and documented short local video ingest through observable Runs.
- Active-Publication-only Search and evidence-only Ask with page or timestamp Evidence.
- Local stdio MCP tools for ingest, Run inspection, Search, and Ask over the same application contract.
- Default owner-startup CJK runtime strategy: `cjk-active-scan-overlap-v1`.
- Reproducible retrieval evaluation records for English, numeric, Chinese lexical, dense, RRF, and relevance-gate/reranker candidates.

### Verified

- Core verification commands are `uv run pytest -q`, `uv run ruff check .`, `uv run pyright`,
  `uv build`, `uv run mke proof run`, `uv run mke demo --verify`, and
  `uv run python scripts/release_presentation_audit.py --root .`.
- E3-F `cjk-active-scan-overlap-v1` is the shipped runtime default and keeps Search/Ask/MCP on active Publication Evidence.
- E3-C dense, E3-D RRF, and E3-E relevance-gate/reranker artifacts are comparison-only evidence.

### Not included

- Dense, hybrid, RRF, reranker, query rewrite, segmentation, OCR, HTTP, UI, API adapter, LangChain,
  LlamaIndex, LangGraph, Milvus, Redis, and pgvector runtime contracts are not part of this release.
- Stage 2 installed-package consumer smoke, tag creation, and GitHub Release publication are separate gates after this presentation-readiness work merges.
