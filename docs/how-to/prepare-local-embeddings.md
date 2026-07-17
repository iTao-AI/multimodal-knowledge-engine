# Prepare Local Embeddings

This guide covers the E3-C PR 1 local embedding prerequisite for
`qwen3-embedding-0.6b-exact-v1`. It is comparison-only and does not change normal Search, Ask,
MCP, or the runtime default. Dense comparison scoring, a future API adapter, fusion, reranking, and
runtime promotion remain separate evidence-gated work.

## Scope

The exact local candidate is:

| Field | Value |
|---|---|
| Candidate | `qwen3-embedding-0.6b-exact-v1` |
| Model | `Qwen/Qwen3-Embedding-0.6B` |
| Revision | `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3` |
| Runtime | `sentence-transformers==5.6.0` |
| Vector reference | `exact-cosine-v1` |
| sqlite-vec probe | `sqlite-vec==0.1.9`, rejected with `projection_size_limit_exceeded` |
| Remote code | prohibited |
| Operation | cache-only after explicit prepare |

Installing packages may use a package index. Only prepare may download model files. Doctor,
compatibility proof, installed-wheel proof, evaluation, Search, Ask, and MCP remain cache-only.

## Install The Optional Runtime

Source checkout:

```bash
uv sync --locked --extra embedding
```

Built wheel:

```bash
uv build
uv venv /tmp/mke-embedding-wheel --python 3.13
uv pip install --python /tmp/mke-embedding-wheel/bin/python \
  "dist/multimodal_knowledge_engine-0.1.3-py3-none-any.whl[embedding]"
```

Fully offline from a pre-populated package cache:

```bash
uv export --locked --extra embedding --no-dev --no-emit-project \
  --output-file /tmp/mke-embedding-constraints.txt
uv venv --clear /tmp/mke-embedding-wheel --python 3.13 --no-python-downloads
uv pip install --offline --python /tmp/mke-embedding-wheel/bin/python \
  --constraint /tmp/mke-embedding-constraints.txt \
  "dist/multimodal_knowledge_engine-0.1.3-py3-none-any.whl[embedding]"
```

If the offline install reports a missing registry package, populate the package cache under a
separate authorization. Do not change `uv.lock`, upgrade dependencies, or substitute a model.

## Prepare And Diagnose The Model Cache

Use an operator-controlled cache outside the repository. The canonical local proof used the
documented macOS cache location:

```bash
mke embedding prepare --allow-model-download \
  --model qwen3-embedding-0.6b \
  --model-revision 97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3 \
  --model-cache "$HOME/Library/Caches/mke/embedding" \
  --json
```

One explicit authorization covers one prepare process for this exact model, revision, cache, and
transport policy. Hugging Face Hub-managed Range resumes may occur inside that process. MKE does
not start a second process, retry loop, alternate model/provider, or silent fallback.

Doctor is always cache-only:

```bash
mke embedding doctor \
  --model qwen3-embedding-0.6b \
  --model-revision 97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3 \
  --model-cache "$HOME/Library/Caches/mke/embedding" \
  --json
```

MKE never deletes model caches. Removing a model cache or stale partial files is a manual operator action
and requires a separate authorization in this workflow.

## Validate The Compatibility Artifact

The checked-in PR 1 artifact is:

```text
benchmarks/retrieval/qwen3-embedding-0.6b-compatibility.json
```

It records:

| Field | Value |
|---|---:|
| Schema | `mke.dense_compatibility.v2` |
| Snapshot fingerprint | `sha256:05b8ff893f9930fc968d88c51facc8c2fb67d3d6a6f0d16413dc94dee1adbf42` |
| Snapshot bytes | `1207489041` |
| Physical memory bytes | `17179869184` |
| Compatibility stress peak RSS bytes | `4456693760` |
| Single-query peak RSS bytes | `2804580352` |
| Selected adapter | `exact-cosine-v1` |
| sqlite-vec result | `projection_size_limit_exceeded` |

The amended PR 1 hard gates are:

- supported proof host physical memory `>= 16 GiB`;
- complete snapshot `<= 1.5 GiB`;
- compatibility stress peak RSS `<= 6 GiB` and `<= 40% physical memory`;
- 70-Evidence exact projection `<= 1 MiB`;
- one query embedding plus exact-KNN `<= 5 s`.

The single-query model-load RSS is report-only, but the evidence must be present, cache-only,
installed-wheel, and bound to the same model fingerprint.

Run the model-free artifact validation:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run python - <<'PY'
import json
from pathlib import Path
from mke.evaluation.dense_compatibility import (
    load_dense_corpus_lock,
    validate_dense_compatibility_report,
)
root = Path(".").resolve()
lock = load_dense_corpus_lock(
    Path("tests/fixtures/retrieval-dense-v1/corpus-lock.json"),
    repository_root=root,
)
report = json.loads(
    Path("benchmarks/retrieval/qwen3-embedding-0.6b-compatibility.json").read_text()
)
validate_dense_compatibility_report(report, lock)
PY
```

## Run The Installed-Wheel Offline Proof

After the package cache and model cache exist, run each supported Python version once:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 UV_OFFLINE=1 \
python scripts/dense_retrieval_deployment_proof.py \
  --wheel dist/multimodal_knowledge_engine-0.1.3-py3-none-any.whl \
  --corpus-lock tests/fixtures/retrieval-dense-v1/corpus-lock.json \
  --model-cache "$HOME/Library/Caches/mke/embedding" \
  --python 3.13 \
  --repository .
```

The proof installs `wheel[embedding]` in an external venv, clears hostile Python environment
variables, runs cache-only doctor, records the fresh single-query smoke process, and then runs the
70-Evidence compatibility stress process. It reads no dense qrels and makes no retrieval-quality
claim.

## What This Does Not Do

- It does not change runtime Search, Ask, MCP, owner startup, or `active_evidence_fts`.
- It does not read dense qrels, select a threshold, observe holdout, or make an E3-D verdict.
- It does not implement a future API adapter, RRF, reranking, query rewrite, HTTP, UI, or
  persistent vector projection.
- It does not prove broad dense-retrieval quality; it proves this exact model/revision/runtime
  prerequisite is compatible under the amended PR 1 resource contract.
