# Changelog

## [0.1.4] - 2026-07-23

### Added

- Bounded direct-audio intake for MP3, WAV/PCM, and M4A/AAC clips up to 15 minutes and 100 MiB
  through an explicitly supervised cache-only faster-whisper owner on Darwin arm64.
- Python, CLI, and stdio MCP paths publish timestamp Evidence to active Publications for Search,
  Ask, and Compiled Library Export v2.

### Verified

- Model-free direct-audio product wiring, strict media validation, active-Publication behavior,
  portable Export v2 schemas, and Export v1 compatibility for PDF/video-only Libraries.
- `cjk-active-scan-overlap-v1` remains the runtime default.
- Dense, RRF, and reranker artifacts remain comparison-only evidence.

### Not included

- No implicit model download, cloud fallback, production SLA, transcript-accuracy guarantee,
  cross-platform claim, hosted deployment, PyPI publication, or extra GitHub Release assets.
- External wheels and native binaries are not redistributed. LLM Wiki remains an isolated
  downstream compatibility surface, not an MKE dependency or Evidence authority.

## [0.1.3] - 2026-07-17

### Added

- Read-only Compiled Library Export for active Publications with canonical
  `mke.compiled_library_export.v1`, readable `mke.compiled_markdown.v1`, and authoritative
  `mke.evidence_ref.v1` JSONL output.
- Generic installed-wheel Compiled Library Export proof for Python 3.12 and Python 3.13.

### Verified

- Descriptor-bound manifest-last publication, exact digest revalidation, identity-bound cleanup,
  read-only SQLite snapshots, and an independent standard-library consumer.
- PDF OCR Phase 0 records bounded closed-protocol planning evidence: PP-OCRv6 medium is the
  selected production-planning baseline and PaddleOCR-VL 1.6 is a comparison candidate.
- `cjk-active-scan-overlap-v1` remains the runtime default.
- Dense, RRF, and reranker artifacts remain comparison-only evidence.

### Not included

- Production OCR remains excluded. LLM Wiki compatibility remains deferred.
- Retrieval runtime promotion, HTTP/UI/service adapters, hosted deployment, and PyPI publication
  are excluded. The release does not reconstruct source layout.

## [0.1.2] - 2026-07-14

### Added

- Additive read-only `list_libraries_v1`, `search_library_v1`, and `ask_library_v1` tools with
  strict portable `mke.evidence_ref.v1` provenance.
- Standalone external source-pack proof over the official MCP SDK, validating the same wheel in
  fresh Python 3.12 and Python 3.13 environments.
- Strict local `mke.candidate_artifact_receipt.v1` binding a candidate wheel to its clean source
  commit and proof input digest.

### Verified

- Source-byte fingerprint, Publication revision, producing Run, and page or timestamp locator map
  through fresh stores without importing MKE or inspecting SQLite directly.
- Controller output, deadlines, failures, cancellation, subprocess cleanup, owner lifecycle, and
  transition boundaries are bounded or fail closed.
- A separate downstream consumer validated the pre-release candidate boundary documented in
  [the v0.1.2 release notes](./docs/releases/v0.1.2.md).
- E3-C dense, E3-D RRF, and E3-E relevance-gate/reranker remain comparison-only evidence.

### Not included

- PDF OCR Phase 0, layout-aware extraction, retrieval runtime promotion, HTTP/UI/service adapters,
  hosted deployment, and PyPI publication are excluded.

## [0.1.1] - 2026-07-08

### Added

- Public-safe synthetic local knowledge proof over the real stdio MCP transport.
- End-to-end proof coverage for local PDF ingest Runs, published page Evidence, active Publication
  Search, cited evidence-only Ask, and zero-citation `insufficient_evidence` refusal.

### Verified

- The local knowledge proof uses repository-authored synthetic fixtures and emits only aggregate,
  public-safe results without temporary paths, transient identifiers, source text, or tracebacks.
- PR #58 merged as `4e52542610b803df7bfe6dcb7648d464484e8f81`; post-merge CI and CodeQL passed.
- Existing CLI, MCP, Search, Ask, Publication, and retrieval runtime contracts remain unchanged.
- E3-C dense, E3-D RRF, and E3-E relevance-gate/reranker remain comparison-only evidence.

### Not included

- Comparison-only dense/RRF/reranker evidence is not promoted into runtime; HTTP, UI, OCR, and API
  adapters are also not part of this patch release.
- PyPI publication is not part of this release closeout.

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
- Installed-wheel consumer smoke is verified with
  `uv run python scripts/release_consumer_smoke.py --wheel dist/*.whl --json`.
- GitHub Release archive smoke is verified with `uv sync --locked`, `uv run mke proof run`, and
  `uv run mke demo --verify` from the `v0.1.0` release archive.
- E3-F `cjk-active-scan-overlap-v1` is the shipped runtime default and keeps Search/Ask/MCP on active Publication Evidence.
- E3-C dense, E3-D RRF, and E3-E relevance-gate/reranker artifacts are comparison-only evidence.

### Not included

- Dense, hybrid, RRF, reranker, query rewrite, segmentation, OCR, HTTP, UI, API adapter, LangChain,
  LlamaIndex, LangGraph, Milvus, Redis, and pgvector runtime contracts are not part of this release.
- PyPI and package registry publication are not part of this release.
