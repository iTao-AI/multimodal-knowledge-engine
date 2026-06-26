# CJK Lexical Candidate Implementation Plan

Status: completed locally for the E3-B execution window.

Implementation branch: `codex/e3b-cjk-lexical-candidate`.

## Goal

Implement an off-default E3-B comparison for `cjk-trigram-overlap-v1`, using the unchanged E3-A
protocol and fixtures. The PR must produce a canonical comparison artifact, validate it
independently, and prove that current E1/E2/E3-A behavior is not changed.

## Completion Evidence

The implementation records
`benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json` as the canonical E3-B comparison
artifact. It reports `candidate_status=passed`, current Recall@5 `0.295455`, candidate Recall@5
`0.659091`, current nDCG@10 `0.277279`, and candidate nDCG@10 `0.610619`.

All frozen development and holdout gates pass in the canonical artifact. The candidate remains
comparison-only: runtime Search/Ask defaults, embeddings, vector search, hybrid retrieval, RRF,
reranker, query rewrite, HTTP, UI, and MCP behavior are not promoted or changed by E3-B.

## Scope

In scope:

- evaluation-only CJK trigram projection;
- compiled-empty fallback candidate semantics;
- deterministic overlap scorer;
- comparison report and canonical artifact;
- artifact validator;
- CLI/CI gates for candidate comparison;
- documentation for running and interpreting the candidate.

Out of scope:

- runtime default promotion;
- embeddings, vector search, hybrid retrieval, RRF, reranker, or query rewrite;
- new external dependencies or model downloads;
- UI, HTTP, or MCP behavior changes;
- modifying E3-A protocol, qrels, or fixtures.

## Task 1: Freeze The Candidate Contract

Add tests first for the frozen candidate metadata and parameter contract.

Expected files:

- `tests/evaluation/test_cjk_lexical_candidate.py`
- `src/mke/evaluation/cjk_lexical_candidate.py`

Required RED tests:

- candidate ID must be exactly `cjk-trigram-overlap-v1`;
- revision must be integer `1`, not `true`;
- `minimum_overlap_count=2`;
- `minimum_overlap_ratio=0.30`;
- `max_results=10`;
- non-allowlisted candidate ID is rejected with a stable evaluation error;
- changing any frozen parameter changes the candidate identity digest.

Implementation notes:

- Keep the contract in evaluation code, not retrieval runtime config.
- Do not add the candidate to the runtime `RetrievalQueryPolicy` allowlist.

Verification:

```bash
uv run pytest tests/evaluation/test_cjk_lexical_candidate.py -q
```

## Task 2: Detect SQLite Trigram Support

Add a compatibility probe that creates an in-memory FTS5 table with `tokenize='trigram'`.

Required RED tests:

- installed runtime with `trigram` support returns tokenizer identity and SQLite version;
- simulated unsupported tokenizer raises `CjkLexicalCandidateUnsupported`;
- public CLI error maps to a stable problem/cause/next_step without traceback or local paths.

Implementation notes:

- Use the installed Python `sqlite3` module.
- Do not rely on local developer SQLite assumptions.
- Run the compatibility check in Python 3.12 and Python 3.13 wheel proof.

Verification:

```bash
uv run pytest tests/evaluation/test_cjk_lexical_candidate.py -q
```

## Task 3: Build The Evaluation-Only Projection

Build a temporary projection from active E3-A Evidence rows.

Expected behavior:

- projection table is separate from `active_evidence_fts`;
- row count equals active Evidence row count;
- aggregate text digest equals the active Evidence snapshot digest;
- source/publication/locator/Evidence identity is preserved;
- projection is rebuilt from fixtures during validation, not trusted from the recorded artifact.

Required RED tests:

- mutating active Evidence text before projection causes digest mismatch;
- dropping a row causes row-count mismatch;
- changing a locator causes locator inventory mismatch;
- projection never writes to the production active FTS table.

Implementation notes:

- Reuse existing E3-A snapshot/publish helpers where possible.
- Keep projection creation local to the evaluation runner or an evaluation adapter helper.
- Bind all SQL values; never interpolate raw query text.

Verification:

```bash
uv run pytest tests/evaluation/test_cjk_lexical_candidate.py tests/adapters/test_sqlite_fts.py -q
```

## Task 4: Implement CJK Term Compilation

Add deterministic candidate-term compilation.

Rules:

- remove whitespace for CJK term generation;
- casefold text;
- generate unique 3-character shingles from CJK runs length `>= 3`;
- preserve current ASCII/numeric token diagnostics;
- record CJK runs shorter than 3 characters as below-minimum diagnostics;
- return no candidate terms when nothing can be matched safely.

Required RED tests:

- Chinese-only query produces expected shingles;
- mixed Chinese-English query records ASCII diagnostics but does not force fallback when current
  compiler is non-empty;
- two-character Chinese query records below-minimum diagnostics and produces no trigram `MATCH`;
- duplicate shingles are deduplicated in stable order;
- quotes and SQL-looking text are safely quoted/bound.

Verification:

```bash
uv run pytest tests/evaluation/test_cjk_lexical_candidate.py -q
```

## Task 5: Implement The Overlap Filter And Ranker

Implement the project-owned scorer over frozen page text.

Rules:

- compute overlap count from unique generated terms present in normalized page text;
- compute overlap ratio as `overlap_count / generated_term_count`;
- retain only rows where count and ratio thresholds pass;
- rank by overlap count, overlap ratio, FTS5 rank, document ID, locator start, Evidence ID;
- return at most 10 rows.

Required RED tests:

- raw FTS5 candidate with insufficient overlap is filtered out;
- exact direct page outranks a lower-overlap distractor;
- equal overlap ties are stable;
- changing recorded score, overlap count, ratio, or locator is rejected by validator;
- SQL trace proves one parameterized projection `MATCH` query.

Verification:

```bash
uv run pytest tests/evaluation/test_cjk_lexical_candidate.py -q
```

## Task 6: Add The Comparison Runner

Add an E3-B runner that records both current and candidate observations.

Expected files:

- `src/mke/evaluation/cjk_lexical_comparison.py`
- `tests/evaluation/test_cjk_lexical_comparison.py`

Runner behavior:

1. Validate the E3-A protocol and qrel adjudication.
2. Run the current E3-A observation using `numeric-grouping-v1`.
3. For each query, use candidate fallback only when the current compiled query is empty.
4. Compute candidate metrics, category deltas, compiled-empty recovery, unanswerable controls, and
   hard-negative deltas.
5. Freeze development gates before recording holdout metrics.
6. Record `candidate_status=passed` only when all development and holdout gates pass.

Required RED tests:

- candidate is not used when current compiled query is non-empty;
- compiled-empty query uses trigram-overlap projection;
- development gate failure records `candidate_status=failed`;
- holdout cannot be observed before candidate identity and development gates are frozen;
- current result payload remains semantically equal to E3-A baseline except duration/environment
  fields.

Verification:

```bash
uv run pytest tests/evaluation/test_cjk_lexical_comparison.py -q
```

## Task 7: Add The Canonical Artifact Validator

Add a strict validator for:

`benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json`

Validator requirements:

- reject unknown keys, bool-as-int, malformed locators, and unordered result arrays;
- verify fixture/protocol/qrel/source identities;
- rebuild active Evidence from frozen fixture text;
- rebuild trigram projection;
- independently recompute candidate terms, projection matches, overlap scores, rankings, metrics,
  gates, and verdict;
- reject observed report replay that bypasses scorer recomputation;
- reject coordinated tampering where locator and score are both changed.

Required RED tests:

- feature-commit ancestry is not required after squash merge;
- shallow squash-landed clone can validate artifact;
- changing any source file covered by source identity requires artifact refresh;
- malformed artifact exits with stable CLI error and no traceback.

Verification:

```bash
uv run pytest tests/evaluation/test_cjk_lexical_artifact.py -q
uv run python -m mke.evaluation.cjk_lexical_artifact validate \
  --artifact benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json \
  --observed /tmp/mke-cjk-lexical-comparison.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
```

## Task 8: Add CLI, CI, And Wheel Proof

Add a CLI command, CI gate, and installed-wheel proof for E3-B.

Recommended CLI shape:

```bash
uv run mke eval retrieval-cjk-lexical \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --candidate cjk-trigram-overlap-v1 \
  --json
```

Required behavior:

- `--record <path>` writes the canonical artifact;
- the module validator validates a recorded artifact against a fresh observed report;
- unsupported SQLite trigram runtime exits with stable error;
- command is deterministic and network-free;
- CI runs artifact validator and comparison gate;
- Python 3.12 and Python 3.13 installed-wheel proof run from an external cwd with hostile
  `PYTHONPATH`.

Verification:

```bash
uv run pytest tests/evaluation/test_cjk_lexical_cli.py -q
uv run mke eval retrieval-cjk-lexical \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --candidate cjk-trigram-overlap-v1 \
  --json > /tmp/mke-cjk-lexical-comparison.json
uv run python -m mke.evaluation.cjk_lexical_artifact validate \
  --artifact benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json \
  --observed /tmp/mke-cjk-lexical-comparison.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
```

## Task 9: Record The Artifact

After all candidate semantics and development gates are frozen:

1. Run the comparison.
2. Record the canonical artifact.
3. Validate it in the source tree.
4. Validate it from installed wheels for Python 3.12 and Python 3.13.

Expected artifact fields:

- candidate identity, revision, parameters, and source identity;
- SQLite runtime/tokenizer identity;
- projection identity;
- current and candidate metrics;
- development gates;
- holdout gates;
- per-query current and candidate results;
- compiled-empty recovery table;
- deterministic rank/overlap proof;
- limitations.

Verification:

```bash
uv run mke eval retrieval-cjk-lexical --record benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json
uv run python -m mke.evaluation.cjk_lexical_artifact validate \
  --artifact benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json \
  --observed /tmp/mke-cjk-lexical-comparison.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
```

## Task 10: Update Documentation

Update only public-neutral project documentation:

- `docs/how-to/run-chinese-retrieval-evaluation.md`
- `docs/reference/cli.md`
- `docs/reference/contracts.md`
- `docs/explanation/architecture.md`
- `docs/README.md`
- relevant `docs/superpowers/` plan/review files.

Documentation must state:

- E3-B is comparison-only;
- runtime default remains unchanged;
- no embeddings/vector/hybrid/RRF/reranker/query rewrite were added;
- the candidate targets compiled-empty CJK lexical failures only;
- results are bounded to the small public E3-A corpus.

Verification:

```bash
uv run pytest tests/evaluation/test_chinese_documentation.py -q
git diff --check
```

## Task 11: Final Verification

Run the full verification set before handing back to the planning window:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke eval retrieval \
  --manifest tests/fixtures/eval/retrieval/manifest.json \
  --json > /tmp/mke-retrieval-eval.json
uv run python -m mke.evaluation.baseline \
  --artifact benchmarks/retrieval/retrieval-eval-v1-baseline.json \
  --manifest tests/fixtures/eval/retrieval/manifest.json \
  --repository .
uv run mke eval retrieval-numeric \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --json > /tmp/mke-numeric-comparison.json
uv run python -m mke.evaluation.numeric_artifact validate \
  --artifact benchmarks/retrieval/numeric-grouping-v1-comparison.json \
  --observed /tmp/mke-numeric-comparison.json \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --repository .
uv run mke eval retrieval-chinese \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --json > /tmp/mke-retrieval-chinese.json
uv run python -m mke.evaluation.chinese_artifact validate \
  --artifact benchmarks/retrieval/retrieval-chinese-v1-baseline.json \
  --observed /tmp/mke-retrieval-chinese.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
uv run mke eval retrieval-cjk-lexical \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --candidate cjk-trigram-overlap-v1 \
  --json > /tmp/mke-cjk-lexical-comparison.json
uv run python -m mke.evaluation.cjk_lexical_artifact validate \
  --artifact benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json \
  --observed /tmp/mke-cjk-lexical-comparison.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
uv run mke proof run
uv run mke demo --verify
git diff --check
```

Also run Python 3.12 and Python 3.13 installed-wheel proof for the new CLI and artifact validator.

## Handoff Requirements

The execution window should stop before push/PR and report:

- branch, base commit, HEAD, diff stat, and commit list;
- candidate status and all gate results;
- artifact SHA-256 and source/protocol/projection identities;
- current vs candidate metrics;
- E1/E2/E3-A validation status;
- Python 3.12/3.13 installed-wheel proof status;
- explicit confirmation that runtime defaults, embeddings, vector search, RRF, reranker, query
  rewrite, HTTP, UI, and MCP behavior were not changed.
