# Enable Bounded CJK Retrieval

E3-F adds `cjk-active-scan-overlap-v1`, a local lexical strategy for eligible CJK queries that
the ASCII-oriented FTS5 compiler cannot express. SQLite remains domain truth and no persistent CJK
projection is created.

## Select The Strategy

The strategy is the default when no selector is supplied. Use the explicit selector when the owner
must pin the strategy:

```bash
uv run mke --db .tmp/mke.sqlite \
  --retrieval-strategy cjk-active-scan-overlap-v1 \
  search "蓝湖缓存服务 不完整索引"
```

The selector is owner-startup configuration. `search_library` and `ask_library` MCP tool schemas
do not expose a request-time retrieval strategy.

## Routing Contract

Each query is compiled once with `numeric-grouping-v1`:

```text
query
  -> compiled non-empty -> active FTS5 only, including a zero-hit result
  -> compiled-empty and eligible CJK -> bounded active Evidence scan
  -> compiled-empty and ineligible -> stable validation result
```

Mixed ASCII+CJK and numeric queries with a compiled non-empty expression remain FTS-only. The
runtime does not discard ASCII or numeric constraints after an FTS zero-hit. A future
constraint-preserving mixed-query fallback requires a separate comparison.

The active scan reads only Evidence owned by active Publications. It permits at most 512 CJK query
characters, 128 overlap terms, 10,000 active Evidence rows, and a 1,000-candidate pool. Budget
failures use stable `problem`, `cause`, and `next_step` fields.

## Doctor And Rebuild

Run the read-only readiness check against the owner's database:

```bash
uv run mke --db .tmp/mke.sqlite retrieval doctor \
  --strategy cjk-active-scan-overlap-v1 --json
```

The check reports SQLite readability, active Publication inspectability, and that a persistent CJK
projection is not required. Rebuild is a stable no-op:

```bash
uv run mke --db .tmp/mke.sqlite retrieval rebuild \
  --strategy cjk-active-scan-overlap-v1 --json
```

Its successful result contains `action="noop"` and `projection="none"`.

## Roll Back

Restart the owner with the previous numeric strategy:

```bash
uv run mke --db .tmp/mke.sqlite \
  --retrieval-strategy numeric-grouping-v1 \
  search "410000 withdrawals"
```

`--retrieval-strategy current` remains the lower-level legacy rollback. Neither rollback requires
a schema migration, projection rebuild, or Evidence rewrite. The compatibility
`--retrieval-query-policy` option remains limited to these legacy strategies.

## Run The Demo

The repository demo performs real PDF ingest, CJK Search and Ask, a no-evidence refusal, and the
numeric rollback against a temporary database:

```bash
uv run python scripts/cjk_active_scan_demo.py
```

For isolated installed-wheel CLI and stdio MCP proof on Python 3.12 or 3.13:

```bash
uv build
uv run python scripts/cjk_active_scan_runtime_deployment_proof.py \
  --wheel dist/multimodal_knowledge_engine-0.0.0-py3-none-any.whl \
  --python 3.12 \
  --explicit-only
```

## Evidence And Limits

| Path | Recall@5 | nDCG@10 | Role |
|---|---:|---:|---|
| E3-A `numeric-grouping-v1` | `0.295455` | `0.277279` | Frozen FTS5 lexical baseline |
| E3-B `cjk-trigram-overlap-v1` | `0.659091` | `0.610619` | Evaluation-only trigram comparison |
| Task 0.5 active scan | `0.659091` | `0.619152` | Runtime routing evidence |

The Task 0.5 active-scan run also records unanswerable no-hit rate `0.500000` and hard-negative
failure rate `0.235294`. This small public, text-layer, page-level corpus does not establish broad
CJK support. Japanese and Korean behavior is unvalidated. E3-C through E3-E remain unimplemented.
