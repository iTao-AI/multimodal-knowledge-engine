# Run The Chinese Retrieval Evaluation

E3-A records the current FTS5 lexical retrieval baseline. It is offline, evaluation-only, and
does not promote a new runtime strategy.

## Run The Evaluation

```bash
uv sync --locked &&
uv run mke eval retrieval-chinese \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json
```

For JSON:

```bash
uv run mke eval retrieval-chinese \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --json > /tmp/mke-retrieval-chinese.json
```

The protocol contains five public text-layer PDF fixtures: 34 development pages and 36 holdout
pages. Its 48 queries are split 24/24 across eight categories. The complete adjudication stores
1,680 ordered query-page judgments with grades `0` (irrelevant/distractor), `1` (related but not a
direct answer), and `2` (direct answer). Development and holdout are ingested into separate
workspaces.

## Interpret The Result

`integrity_status=passed` means the protocol, fixture identities, qrel review, partition
isolation, active Evidence, FTS projection, repeated observations, and rank probe passed.
`quality_status=baseline_recorded` and `quality_gate=none` mean low scores are observations, not
command failures.

| Metric | Value |
|---|---:|
| Recall@1 | `0.227273` |
| Recall@3 / Recall@5 | `0.295455` |
| MRR@5 | `0.261364` |
| nDCG@5 | `0.270109` |
| nDCG@10 | `0.277279` |
| Answerable zero-hit rate | `0.681818` |
| Hard-negative failure rate | `0.235294` |
| Unanswerable no-hit rate | `0.500000` |
| Ask input-rejection rate | `0.562500` |
| Ask insufficient-Evidence rate | `0.083333` |
| Ask Evidence-found rate | `0.354167` |

Category answerable zero-hit counts are Chinese exact lexical `5/8`, Chinese word boundary `6/6`,
proper-name mixed `0/6`, number/date/unit `4/6`, semantic paraphrase `7/8`, multi-condition `6/6`,
and ranking hard-negative `2/4`. The four unanswerable queries are reported separately.

`invalid_question` means the ASCII-oriented compiler produced no searchable input.
`insufficient_evidence` means the input was valid but Search returned no Evidence.

## Miss Symptoms And Rank Evidence

The canonical symptoms are 25 `compiled_query_empty`, 2
`compiled_clauses_absent_from_direct_page`, 2 `matching_direct_page_not_returned`, and 1
`distractor_ranked_ahead`. These labels describe observed conditions; they are not causal
diagnoses.

The independent rank probe established profile `sqlite_fts5_default_bm25`: for every non-empty
compiled query, complete `rank` and `bm25(active_evidence_fts)` result sets had the same order and
score pairs, with no persistent rank override.

## E3-B Decision

E3-B is `eligible` because qrel review is complete, all 1,680 judgments are present, and 10
answerable development misses had `compiled_query_empty`. Eligibility authorizes planning only.
E3-B preserves the protocol and fixture bytes and records the first off-default candidate
comparison as `cjk-trigram-overlap-v1`.

## Run The E3-B CJK Lexical Comparison

```bash
uv run mke eval retrieval-cjk-lexical \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --candidate cjk-trigram-overlap-v1 \
  --json > /tmp/mke-cjk-lexical-comparison.json
```

To record the canonical artifact:

```bash
uv run mke eval retrieval-cjk-lexical \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --candidate cjk-trigram-overlap-v1 \
  --record benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json \
  --json > /tmp/mke-cjk-lexical-comparison.json
```

`cjk-trigram-overlap-v1` is comparison-only. It first uses the unchanged
`numeric-grouping-v1` compiler. Only queries whose current compiled query is empty enter the
evaluation-only SQLite FTS5 `trigram` projection and deterministic overlap scorer. The normal
`active_evidence_fts` table, runtime default retrieval policy, Search/Ask DTOs, HTTP, UI, MCP,
embeddings, vector search, hybrid retrieval, RRF, reranking, and query rewrite are unchanged.

| Metric | Current | Candidate |
|---|---:|---:|
| Recall@5 | `0.295455` | `0.659091` |
| nDCG@10 | `0.277279` | `0.610619` |
| Development Recall@5 | `0.363636` | `0.681818` |
| Holdout Recall@5 | `0.227273` | `0.636364` |
| Development compiled-empty misses recovered | `0/10` | `7/10` |

All frozen development and holdout gates pass in the canonical artifact. This does not promote the
candidate to runtime default and does not establish broad CJK support. E3-C through E3-F remain
unimplemented and evidence-gated.

## Validate The Canonical Artifact

```bash
uv run python -m mke.evaluation.chinese_artifact validate \
  --artifact benchmarks/retrieval/retrieval-chinese-v1-baseline.json \
  --observed /tmp/mke-retrieval-chinese.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
```

The artifact binds report semantics, qrel/rank evidence, fixtures, and source identity.
Validation does not ingest again. The holdout is public, not blind; one canonical observation is
recorded to avoid iterative tuning against it.

Validate the E3-B comparison artifact:

```bash
uv run python -m mke.evaluation.cjk_lexical_artifact validate \
  --artifact benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json \
  --observed /tmp/mke-cjk-lexical-comparison.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
```

The E3-B validator reruns the comparison from frozen fixture text, rebuilds the evaluation-only
projection, recomputes generated terms, overlap scores, rankings, metrics, gates, and verdict, and
then compares the canonical artifact.

## Prove The Installed Wheel Offline

```bash
uv build
wheel=$(echo dist/*.whl)
UV_OFFLINE=1 uv run python scripts/chinese_retrieval_deployment_proof.py \
  --wheel "$wheel" \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --python 3.12
UV_OFFLINE=1 uv run python scripts/chinese_retrieval_deployment_proof.py \
  --wheel "$wheel" \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --python 3.13
```

The proof clears Python import state, disables Python downloads, uses lock-derived constraints,
installs with `uv pip install --offline`, verifies installed identity, and bounds subprocesses.
If the package cache is absent, it fails closed rather than using the network.

## Recover From Stable Failures

| `next_step` | Command |
|---|---|
| `restore_checked_in_protocol` | `git restore tests/fixtures/retrieval-chinese-v1/protocol.json` |
| `restore_checked_in_qrel_review` | `git restore tests/fixtures/retrieval-chinese-v1/qrel-adjudication.json` |
| `verify_fixture_identity` | `uv run pytest tests/evaluation/test_chinese_fixture_corpus.py -q` |
| `inspect_publication_failure` | `uv run pytest tests/evaluation/test_chinese_runner.py -q` |
| `inspect_active_evidence_projection` | `uv run pytest tests/evaluation/test_chinese_diagnostics.py tests/adapters/test_sqlite_fts.py -q` |
| `inspect_fts5_rank_configuration` | `uv run pytest tests/adapters/test_sqlite_fts.py -q` |
| `rerun_evaluation` | `uv run mke eval retrieval-chinese --protocol tests/fixtures/retrieval-chinese-v1/protocol.json` |
| `regenerate_chinese_artifact` | Rerun JSON evaluation, then the validator above. |
| `recover_checked_in_artifacts` | `uv run python -m mke.evaluation.artifact_refresh recover --repository .` |

Do not substitute fixture bytes or rewrite queries, categories, direct-answer definitions, or
qrels during recovery.

## Upgrade And Rollback Boundary

E3-A adds diagnostics, fixtures, CI, and canonical artifacts only. It requires no database
migration, projection rebuild, runtime selector change, or user-data action. E1/E2 refreshes are
repository provenance maintenance.

Fixture provenance is documented in `tests/fixtures/retrieval-chinese-v1/README.md`. This small
engineering corpus covers text-layer, page-level Evidence only. E3-B establishes one bounded
compiled-empty lexical comparison on this corpus; it does not establish broad CJK support,
dense/vector or hybrid retrieval, RRF, reranking, statistical significance, production quality,
OCR, or arbitrary PDF support.
