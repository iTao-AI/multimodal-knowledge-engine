# Enable Bounded CJK Retrieval

The deterministic retrieval order revision changes only equal-score ordering and cursor revision
authority. It does not add a retrieval strategy or change CJK routing, scoring, active
Publication scope, or quality claims. See the
[deterministic order proof](./run-deterministic-retrieval-order-proof.md).

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

Under the default `cjk-active-scan-overlap-v1`, mixed ASCII+CJK and numeric queries with a
compiled non-empty expression remain FTS-only. The runtime does not discard ASCII or numeric
constraints after an FTS zero-hit.

## Try The Mixed-Intent Candidate

To require both the compiled ASCII/numeric clauses and literal CJK support, explicitly select
`mixed-cjk-fts-intent-v1` at owner startup:

```bash
uv run mke --db .tmp/mke.sqlite \
  --retrieval-strategy mixed-cjk-fts-intent-v1 \
  search "Atlas 缓存失效原因"
```

For compiled-nonempty mixed queries, the candidate checks every active FTS `MATCH` row before
applying CJK trigram overlap. It selects at most 10 results after ranking; Search limits and MCP
page slices follow that selection. A query without CJK keeps the numeric FTS behavior. A
compiled-empty CJK query keeps the existing bounded active-scan route. A missing ASCII clause,
unsupported CJK intent, short CJK phrase without eligible trigrams, or unsupported paraphrase
produces no Evidence. Ask then reports `insufficient_evidence` for a valid mixed question.

The mixed route caps the complete matched set at 10,000 rows and 16 MiB of original UTF-8 text,
the eligible pool at 1,000, and raw/normalized query length at 512 characters with at most 128
deduplicated CJK terms. Exceeding a bound returns a typed error; it does not return a clipped or
ASCII-only answer. Excerpts and citations use the original Evidence text. MCP
`search_library_v2` exposes `more_available` for another selected page and `capped` when the
10-result strategy cap discarded eligible candidates; `read_evidence_v1` remains the exact-read
path for an incomplete excerpt.

This is an opt-in lexical candidate. It may miss wording with insufficient literal CJK overlap.
The default and rollback strategies remain available with no migration or index rebuild.

The default active scan reads only Evidence owned by active Publications. It permits at most 512 CJK query
characters, 128 overlap terms, 10,000 active Evidence rows, 16 MiB total UTF-8 active Evidence
text, a 1,000-candidate pool, and 10 returned results. Row and text-volume checks happen before
text is loaded for scoring. Budget failures use stable `problem`, `cause`, and `next_step` fields.

## Doctor And Rebuild

Run the read-only readiness check against the owner's database:

```bash
uv run mke --db .tmp/mke.sqlite retrieval doctor \
  --strategy cjk-active-scan-overlap-v1 --json
```

The check reports SQLite readability, active Publication inspectability, exact consistency of the
required `active_evidence_fts` base projection, and that an additional CJK projection is not
required. Missing or inconsistent base FTS state returns `retrieval_projection_not_ready`.
The same readiness checks apply to `mixed-cjk-fts-intent-v1`; replace the `--strategy` value to
inspect that candidate. Additional CJK rebuild is a stable no-op:

```bash
uv run mke --db .tmp/mke.sqlite retrieval rebuild \
  --strategy cjk-active-scan-overlap-v1 --json
```

Its successful result contains `action="noop"`, `projection="none"`, and
`scope="additional_cjk_projection"`. The mixed candidate also has no additional projection;
its no-op rebuild reports `scope="additional_projection"`. Rebuild requests for
`numeric-grouping-v1` or `current`
return `retrieval_rebuild_not_supported`; recovery requires republishing active Sources.

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
  --wheel dist/multimodal_knowledge_engine-0.1.7-py3-none-any.whl \
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
CJK support. Japanese and Korean behavior is unvalidated. Later E3-C through E3-E comparisons are
artifact-bound evaluations and do not change the runtime default documented here.
