# Run Retrieval Evaluation

Use this command to record the current retrieval behavior on the versioned
`retrieval-eval-v1` corpus. It is separate from `mke proof run`: product proof verifies lifecycle
and interface correctness, while retrieval evaluation measures locator retrieval and evidence-only
Ask refusal.

## Prerequisite

```bash
uv sync --locked
```

## Run The Baseline

Human-readable output:

```bash
uv run mke eval retrieval \
  --manifest tests/fixtures/retrieval-eval-v1.json
```

JSON output:

```bash
uv run mke eval retrieval \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --json | python -m json.tool
```

The command validates fixture paths, byte sizes, and SHA-256 values, creates one immutable
snapshot, ingests it into two fresh temporary SQLite workspaces, and compares ordered stable
locator results. Evaluation runtime is offline and does not download fixtures or models.

## Interpret The Result

- `status=passed` means all integrity gates passed.
- `quality_status=baseline_recorded` means the observed metrics were recorded.
- `quality_gate=none` means low quality scores do not fail E1.
- `locator_recall_at_1/3/5` are macro averages over the 16 answerable queries.
- `mrr_at_5` averages the reciprocal rank of the first relevant locator.
- `answerable_zero_hit_rate` counts answerable queries with no Search result.
- `unanswerable_no_hit_rate` measures no-hit behavior for lexical confusers and out-of-corpus
  queries.
- `ask_refusal_rate` is a derived contract observation: in E1, evidence-only Ask refuses exactly
  when the same Search returns no rows.

Exit codes are `0` for a complete trustworthy observation, `1` for an integrity failure, and `2`
for invalid CLI usage. Explicit `--db` is rejected because evaluation owns two temporary
workspaces.

## Recorded E1 Observation

The reviewed baseline has three distinct code identities:

- main merge base:
  `721784eabcb9fbb737166578010c9e1a46a25fef`;
- implementation start after the approved design commits:
  `3992b0e9371d1a8c9e019d3bbe2b32aac9665914`;
- evaluation-code commit:
  `79bafb07ac592b684e6ceab15dc389dc33702978`.

| Metric | Value |
|---|---:|
| `locator_recall_at_1` | 0.875000 |
| `locator_recall_at_3` | 0.937500 |
| `locator_recall_at_5` | 0.937500 |
| `mrr_at_5` | 0.937500 |
| `answerable_zero_hit_rate` | 0.062500 |
| `unanswerable_no_hit_rate` | 1.000000 |
| `ask_refusal_rate` | 1.000000 |

The only answerable query with no relevant locator in the first five results was
`water-answerable-01`. No lexical-confuser or out-of-corpus query produced a false positive, and
Ask refused all eight unanswerable queries.

These scores apply only to `retrieval-eval-v1`: two small English text-layer PDFs plus one
sidecar-backed short-video fixture using page/timestamp Evidence. They do not establish stable
product quality, statistical significance, CJK behavior, private-corpus behavior, OCR quality,
semantic retrieval quality, or latency.

The canonical machine-readable observation is
`benchmarks/retrieval/retrieval-eval-v1-baseline.json`. CI validates its schema and provenance but
does not require later scores to equal it.

Validate the artifact locally with:

```bash
uv run python -m mke.evaluation.baseline \
  --artifact benchmarks/retrieval/retrieval-eval-v1-baseline.json \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --repository . \
  --main-ref main
```

The validator derives the manifest and fixture checksums from actual files, verifies the fixed
historical code metadata plus the byte size and SHA-256 of the recorded evaluation content files,
checks the recorded environment shape, and recomputes aggregate consistency from the stored
per-query results. Historical commit IDs remain audit metadata; validation does not require the
feature commits to exist locally or remain ancestors of `HEAD`, so the same artifact remains
verifiable after a squash merge and feature-branch deletion. The retained `--main-ref` option is
accepted for command compatibility but is not used to resolve historical commits. The validator
does not compare a current evaluation run's scores with the historical baseline.

## Compare A Retrieval Change

Capture JSON before and after:

```bash
uv run mke eval retrieval \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --json > /tmp/retrieval-before.json

# Apply the retrieval change, then rerun:
uv run mke eval retrieval \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --json > /tmp/retrieval-after.json
```

Compare only reports with the same manifest and report schema versions and unchanged
page/timestamp Evidence segmentation. Query text is available in the committed manifest but is
not copied into normal report output.

E1 does not add algorithm improvement, embeddings, hybrid retrieval, CJK evaluation, private
corpora, OCR, real-ASR quality evaluation, or a latency benchmark.
