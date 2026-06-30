# Evaluate The Dense Retrieval Candidate

This guide reproduces the E3-C PR 2 comparison-only evidence for
`qwen3-embedding-0.6b-exact-v1`. It records a local exact-cosine dense candidate against the frozen
Chinese retrieval protocol. It does not change Search, Ask, MCP, or runtime defaults and does not implement API adapter, hybrid/RRF, reranker, query rewrite, HTTP, or UI.

## Scope And Result

Candidate:

- Candidate ID: `qwen3-embedding-0.6b-exact-v1`
- Model: `Qwen/Qwen3-Embedding-0.6B`
- Revision: `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`
- Adapter: `exact-cosine-v1`
- Runtime: cache-only local CPU float32 inference from `$HOME/Library/Caches/mke/embedding`

Canonical result:

```text
candidate_status=completed
e3d_status=eligible
runtime_promotion_status=not_evaluated
selected_threshold=0.58
holdout_status=observed
```

Development selected `selected_threshold=0.58` after recovering two current-runtime target misses:
`zh-dev-hard-01` and `zh-dev-semantic-04`. The one holdout observation recovered five target
grade-2 misses: `zh-hold-hard-01`, `zh-hold-multi-02`, `zh-hold-multi-03`,
`zh-hold-semantic-03`, and `zh-hold-semantic-04`. Number/date recoveries
`zh-hold-number-01` and `zh-hold-number-02` are report-only.

| Split | Recall@5 | nDCG@10 | MRR@5 | Unanswerable no-hit | Hard-negative failure |
|---|---:|---:|---:|---:|---:|
| Development | `0.545455` | `0.574244` | `0.545455` | `0.500000` | `0.000000` |
| Holdout | `0.772727` | `0.751694` | `0.727273` | `0.500000` | `0.000000` |

Artifact identities:

- Comparison artifact:
  `benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json`
- Artifact SHA-256: `dd0093bfdf972507dc682dcc0a76b2c130f9f97e9017b1f5bdbdf40dc9f86f95`
- Development freeze SHA-256: `e2c791bf2a9d7ad6ea3047f89fad2c3157038da88f960b3befa1df131d26002d`
- Holdout receipt SHA-256: `69d723fe9ca182404ea25c5f4742edaede9e7ddd4d9b21aa1156f823b205928d`
- Current runtime semantic digest: `sha256:b32dc4a1479cb3ea8e0ebedf2c27b04a10a6d91eee96e0cd0308bcf921e97959`

This result is not a production-quality or statistical-significance claim. The corpus is small,
public, Chinese-only, and page-level. The holdout is public and non-blind. Japanese, Korean,
short-term temporal drift, segmentation, API embeddings, hybrid fusion, RRF, reranking, and
runtime promotion remain out of scope.

## Prerequisites

Run PR 1 compatibility first. Package installation may use a package index, but model files may
only be downloaded through explicit `mke embedding prepare --allow-model-download`. All commands
below are cache-only:

```bash
uv sync --locked --extra embedding
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 UV_OFFLINE=1 \
  uv run mke embedding doctor \
    --model qwen3-embedding-0.6b \
    --model-revision 97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3 \
    --model-cache "$HOME/Library/Caches/mke/embedding" \
    --json
```

For installed-wheel proof, build the wheel and install the embedding extra from an offline
wheelhouse in an external environment. Keep package-index network separate from model-download
network:

```bash
uv build
uv pip install --offline \
  "dist/multimodal_knowledge_engine-0.0.0-py3-none-any.whl[embedding]"
```

MKE never deletes model caches. Failed-candidate cleanup uses the package manager's normal
uninstall flow; deleting `$HOME/Library/Caches/mke/embedding` is a manual operator action outside
MKE.

## Run The Two-Phase Comparison

Phase 1 records development selection and must run before holdout:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 UV_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
uv run mke eval retrieval-dense \
  --protocol tests/fixtures/retrieval-dense-v1/protocol-lock.json \
  --candidate qwen3-embedding-0.6b-exact-v1 \
  --model-cache "$HOME/Library/Caches/mke/embedding" \
  --development-only \
  --record-development-freeze benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-development-freeze.json \
  --json
```

Phase 2 observes holdout exactly once. It refuses an existing
`--record-holdout-receipt` target:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 UV_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
uv run mke eval retrieval-dense \
  --protocol tests/fixtures/retrieval-dense-v1/protocol-lock.json \
  --candidate qwen3-embedding-0.6b-exact-v1 \
  --model-cache "$HOME/Library/Caches/mke/embedding" \
  --development-freeze benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-development-freeze.json \
  --record benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --record-holdout-receipt benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-holdout-receipt.json \
  --json
```

The four comparison arms are:

1. `e3a-historical-fts5-baseline`
2. `cjk-trigram-overlap-v1`
3. `cjk-active-scan-overlap-v1`
4. `qwen3-embedding-0.6b-exact-v1`

If development produces a valid negative result, automation should exit successfully and skip
holdout:

```bash
result="$(uv run mke eval retrieval-dense ... --development-only --json)"
python - <<'PY'
import json, os, sys
payload = json.loads(os.environ["result"])
if payload["e3d_status"] == "not_eligible":
    sys.exit(0)
if payload["e3d_status"] != "not_evaluated":
    raise SystemExit("unexpected dense development state")
PY
```

## Validate And Replay

Model-free artifact validation:

```bash
uv run python -m mke.evaluation.dense_artifact validate \
  --artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --protocol tests/fixtures/retrieval-dense-v1/protocol-lock.json \
  --repository .
```

Cache-ready replay validation:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 UV_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
uv run python -m mke.evaluation.dense_replay validate \
  --artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --protocol tests/fixtures/retrieval-dense-v1/protocol-lock.json \
  --model-cache "$HOME/Library/Caches/mke/embedding" \
  --repository .
```

The replay CLI must print `{"mode":"cache-ready","status":"passed"}` and exit `0`. Missing,
tampered, or non-replayable artifacts print `{"mode":"cache-ready","status":"failed"}` and exit
non-zero. The command loads the model only from the supplied cache and rejects a model cache inside
the repository.

Measurement harness equivalents:

```bash
uv run python scripts/dense_retrieval_measurement.py \
  --repository . \
  --protocol tests/fixtures/retrieval-dense-v1/protocol-lock.json \
  --artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --model-free

HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 UV_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
uv run python scripts/dense_retrieval_measurement.py \
  --repository . \
  --protocol tests/fixtures/retrieval-dense-v1/protocol-lock.json \
  --artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --cache-ready \
  --model-cache "$HOME/Library/Caches/mke/embedding"
```

Any new model revision, prompt, pooling, dimensionality, projection, or scoring rule requires a
new candidate ID or candidate revision and a new artifact. Do not overwrite this candidate's
development freeze, holdout receipt, or comparison artifact.
