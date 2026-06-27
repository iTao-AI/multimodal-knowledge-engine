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

E1 adds a separate deterministic offline retrieval baseline:
`mke eval retrieval --manifest tests/fixtures/retrieval-eval-v1.json`. It evaluates 24 frozen
queries against two public English PDFs and the existing sidecar-backed short video in two fresh
workspaces. `status=passed` means evaluation integrity passed; `quality_gate=none` means the
observed Recall, MRR, no-hit, and Ask-refusal values are not product quality thresholds.

The proof covers the lifecycle boundary, not broad media support. It does not perform scanned-PDF
OCR, arbitrary video processing, bundled model weights, hosted coordination, or
external provider calls. D3-A adds an optional trusted-local `LocalCommandTranscriptProvider`
boundary and a proof-only `mke proof transcript-smoke` command, but normal ingest, MCP ingest,
`mke proof run`, and `mke demo --verify` remain sidecar-backed and deterministic. D3-B adds an
optional cache-only faster-whisper runtime for configured CLI and owner-started MCP.
`mke proof transcription-run` proves real local ASR with the redistribution-safe spoken fixture,
and `scripts/transcription_deployment_proof.py` proves an isolated wheel-installed CLI plus stdio
MCP SDK flow. Model acquisition remains an explicit opt-in preparation step; normal doctor,
ingest, proof, and MCP execution are cache-only.

E2 adds a numeric retrieval protocol:
`mke eval retrieval-numeric --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json`.
The `numeric-grouping-v1` candidate passed the frozen development, public holdout, and full E1
gates, improving E1 Recall@1 from `0.875000` to `0.937500`. ADR-0007 preserves it as the primary
rollback strategy without a database migration or index rebuild.

E3-A adds a separate Chinese retrieval observation surface for the current FTS5 lexical
retrieval path. It freezes five public text-layer PDF fixtures, 48 protocol-owned queries, and
1,680 reviewed query-page judgments across isolated development and public holdout corpora. The
canonical observation records Recall@5 `0.295455`, nDCG@10 `0.277279`, and 25
`compiled_query_empty` misses. These are baseline observations, not a product-quality or general
Chinese-support claim.

E3-B adds an off-default `cjk-trigram-overlap-v1` comparison candidate:
`mke eval retrieval-cjk-lexical --protocol tests/fixtures/retrieval-chinese-v1/protocol.json --candidate cjk-trigram-overlap-v1`.
The candidate only falls back to an evaluation-only SQLite FTS5 `trigram` projection when the
current `numeric-grouping-v1` compiler is empty. The canonical comparison records Recall@5
`0.659091` and nDCG@10 `0.610619`, with all frozen development and holdout gates passing.

E3-F promotes `cjk-active-scan-overlap-v1` as the default owner-startup strategy. Compiled
non-empty queries remain on active FTS5 even when FTS returns no rows; eligible compiled-empty CJK
queries use a bounded scan over active Publication Evidence in SQLite domain truth. The runtime
creates no persistent CJK projection, and MCP tools expose no request-time strategy override.
Task 0.5 records Recall@5 `0.659091` and nDCG@10 `0.619152` for this route. HTTP, UI, embeddings,
vector search, hybrid retrieval, RRF, reranking, and query rewrite remain out of scope. E3-C
through E3-E remain unimplemented and evidence-gated.

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
timestamp-addressable Evidence. The real local transcription proof is verified on Darwin 25.4.0
arm64 with Python 3.13.12; the transcription isolated wheel-installed CLI/MCP proof is verified
with Python 3.12. Numeric retrieval promotion includes an isolated installed-wheel CLI/MCP proof
for Python 3.12 and 3.13.

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
[Use Local Transcription](./docs/how-to/use-local-transcription.md). To record the current
retrieval behavior, see
[Run Retrieval Evaluation](./docs/how-to/run-retrieval-evaluation.md). To reproduce the bounded
candidate comparison, see
[Evaluate The Numeric Retrieval Candidate](./docs/how-to/evaluate-numeric-retrieval.md). To
record the current Chinese lexical failure profile, see
[Run The Chinese Retrieval Evaluation](./docs/how-to/run-chinese-retrieval-evaluation.md). Approved implementation
history is kept under `docs/superpowers/`; long-lived architecture decisions are kept under
`docs/decisions/`.
To operate the E3-F runtime path, see
[Enable Bounded CJK Retrieval](./docs/how-to/enable-cjk-retrieval.md).

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the development workflow and [SECURITY.md](./SECURITY.md) for responsible vulnerability reporting.

## Development Status

The primary local proof is:

```bash
uv sync --locked
uv run mke proof run
uv run mke proof run --json
uv run mke eval retrieval --manifest tests/fixtures/retrieval-eval-v1.json
uv run mke eval retrieval-numeric \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json
uv sync --locked &&
uv run mke eval retrieval-chinese \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json
uv run mke eval retrieval-cjk-lexical \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --candidate cjk-trigram-overlap-v1
```

`mke demo --verify` remains available as a compatibility proof with its phase-oriented output.
The optional real transcription proof requires the `transcription` extra and a separately prepared
exact model revision. Set `MKE_MODEL_CACHE` to an operator-controlled directory outside the
repository:

```bash
HF_HUB_OFFLINE=1 uv run mke proof transcription-run \
  --fixture tests/fixtures/video/spoken-evidence.mp4 \
  --model-cache "$MKE_MODEL_CACHE" \
  --json
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
uv run mke --db .tmp/mke.sqlite ask "publication active"
uv run mke --db .tmp/mke.sqlite run get <run_id>
uv run mke --db .tmp/mke.sqlite mcp --allowed-root .
uv run mke --db .tmp/mke.sqlite --retrieval-strategy current search "410000 withdrawals"
uv run mke --db .tmp/mke.sqlite --retrieval-strategy cjk-active-scan-overlap-v1 search "蓝湖缓存服务 不完整索引"
```

The default no-argument `mke` command still reports bootstrap status for compatibility.

## License

MIT. See [LICENSE](./LICENSE).
