# Getting Started

The repository has a deterministic local PDF and short-video proof path. Broader product
workflows are still planned.

## Prepare The Environment

Install the locked development dependencies:

```bash
uv sync --locked
```

## Run The Product Proof

```bash
uv run mke demo --verify
```

Expected output includes these phase lines:

```text
mke demo --verify
phase=ingest_initial status=ok
phase=failed_reprocess status=ok active_publication_impact=unchanged
phase=retry_publish status=ok
phase=ingest_video status=ok
phase=cleanup status=ok
result=passed duration_ms=<milliseconds>
```

The demo uses a temporary SQLite workspace, cleans it up before exit, and is expected to complete
in a few seconds on a local development machine. It makes no network calls.

## Run Development Checks

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

## Record The Chinese Retrieval Baseline

From a checkout with a warm `uv` dependency cache:

```bash
uv sync --locked &&
uv run mke eval retrieval-chinese \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json
```

The target is 2–5 minutes. Human mode writes four bounded progress phases to stderr, then stdout
begins:

```text
mke eval retrieval-chinese
integrity_status=passed quality_status=baseline_recorded quality_gate=none
e3b_decision=<eligible|not_justified> reason=<stable_reason>
documents=5 queries=48 development=24 holdout=24 duration_ms=<n>
```

`integrity_status=passed` means the protocol, fixtures, partition isolation, active Evidence,
FTS5 projection, determinism, and rank evidence were trustworthy. It does not mean the observed
quality is acceptable. See
[Run The Chinese Retrieval Evaluation](../how-to/run-chinese-retrieval-evaluation.md) for metrics,
artifact validation, and recovery.

## Try The Lower-Level Ingest Commands

```bash
uv run mke --db .tmp/mke.sqlite ingest tests/fixtures/pdf/text-layer.pdf
uv run mke --db .tmp/mke.sqlite ingest tests/fixtures/video/short-audio.mp4
uv run mke --db .tmp/mke.sqlite search trustworthy
uv run mke --db .tmp/mke.sqlite search timestamp
uv run mke --db .tmp/mke.sqlite ask "publication active"
uv run mke --db .tmp/mke.sqlite run get <run_id>
```

This path supports deterministic text-layer PDFs, the documented short MP4 fixture profile with a
local transcript sidecar, active Publication Search, and local stdio MCP access through
`mke mcp`. `mke ask` is evidence-only: it reports cited active Evidence or
`insufficient_evidence`, without model-generated answers. This path does not cover scanned-PDF
OCR, long videos, bundled speech-model transcription, generative Ask, HTTP, workspace UI, hosted
coordination, or multi-worker runtime behavior. The optional local-command transcript smoke command
is separate from this deterministic getting-started path.

## Optional: Verify Real Local Transcription

After the deterministic proof passes, follow
[Use Local Transcription](../how-to/use-local-transcription.md) to install the optional
`transcription` extra, set `MKE_MODEL_CACHE` to an operator-controlled directory outside the
repository, and explicitly prepare the exact model revision. Then run the real proof cache-only:

```bash
HF_HUB_OFFLINE=1 uv run mke proof transcription-run \
  --fixture tests/fixtures/video/spoken-evidence.mp4 \
  --model-cache "$MKE_MODEL_CACHE" \
  --json
```

This path is optional and separate from required CI. It validates real local ASR, timestamp
Evidence, Search, and evidence-only Ask without turning one transcript or duration into a quality
or performance claim.
