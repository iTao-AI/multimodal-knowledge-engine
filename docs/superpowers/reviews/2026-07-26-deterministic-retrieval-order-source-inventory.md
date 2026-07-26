# Deterministic Retrieval Order Source-Authority Inventory

Status: Task 0 inventory complete at
`e974ff214e6468934d3b82d2b5a211a9ee41af60`.

This record freezes the disposition of source-bound historical retrieval artifacts before the
deterministic-order runtime maintenance begins. Historical observation files remain immutable.
Current-source claims belong to the separate revision-2 compatibility record planned for this
maintenance.

## Validator Disposition

| Family | Current binding | Disposition |
|---|---|---|
| E1 baseline | Every `src/mke/**/*.py` file | Preserve archived file-list and aggregate-digest self-consistency; add a revision-2 current-source differential. |
| E2 numeric | Baseline whole-source identity | Keep the archived `source` field immutable; add a revision-2 differential. |
| E3-A Chinese | Every `src/mke/**/*.py` file | Keep the archived `source` field immutable; add a revision-2 differential. |
| E3-B CJK trigram | Includes `src/mke/adapters/sqlite/__init__.py` | Keep the evaluation-only scorer and revision unchanged, preserve archived bytes, and add a revision-2 source differential. |
| E3-C dense | Its explicit source list does not authorize a runtime-order refresh | Preserve artifact bytes; validate consumed E3-A/E3-B identities and current-runtime replay separately. |
| E3-D hybrid RRF | Protocol binds `src/mke/retrieval/strategy.py` | Preserve artifact bytes; require revision-2 replay and verdict equality. |
| E3-E relevance gate | Recomputes from dense/RRF artifacts and current locators | Preserve artifact bytes; require revision-2 replay and verdict equality. |

Historical validators will validate the strict recorded identity embedded in archived artifacts and
protocols. They will not claim that the current checkout generated those historical bytes.
Builders may still compute current-source identity when recording a new artifact or the separate
revision-2 compatibility record.

## Frozen Historical Bytes

| Path | SHA-256 |
|---|---|
| `benchmarks/retrieval/retrieval-eval-v1-baseline.json` | `c2518b2f95a91eb91f2f83953965e186711e2b3d93725e9d83617d0fde530a88` |
| `benchmarks/retrieval/numeric-grouping-v1-comparison.json` | `98fb1f61d824d7b307d3a2745b49ed972fc6d4af292833098a15b13b860ddae9` |
| `benchmarks/retrieval/retrieval-chinese-v1-baseline.json` | `7187d999fc98f2ed0f405756f0a4b02ab4dcbb14fdb8d49d8bfd1ad205295828` |
| `benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json` | `5cb54cc7baea939b439c617ee917badff64bface2f2fe5a85b128185fdf3ed3c` |
| `benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json` | `a992059a24b5afbd26c22f71916d7266ada9c3e9ed1fe1354447c7f5f2c40d26` |
| `benchmarks/retrieval/cjk-active-scan-qwen3-rrf-v1-comparison.json` | `6b77d29fa3b8badd7400e53fa96cd544ecf84d51563170bfc44d56975ff470c3` |
| `benchmarks/retrieval/cjk-relevance-gate-reranker-v1-comparison.json` | `e22e561618726c339bd955d1c7cfcf573080c251549e6a89c8187251d6011e36` |
| `tests/fixtures/retrieval-eval-v1.json` | `a65b33e011c7a39245a2202fa741e57a268b42da9f68d8da0725955834dd4761` |
| `tests/fixtures/retrieval-numeric-v1/protocol-lock.json` | `17c424e49237deba600fef70d47da803fb73f72d2ee65995fc155dc96e22da60` |
| `tests/fixtures/retrieval-chinese-v1/protocol.json` | `00f72934018a52b5b5f5591fba119050882aee9b782e5dac199702b0cf995944` |
| `tests/fixtures/retrieval-dense-v1/protocol-lock.json` | `afca992a7115fdb06e620168d14f8d09055f231c061b59f82c69f0be2a6e4251` |
| `tests/fixtures/retrieval-hybrid-rrf-v1/protocol-lock.json` | `2407fb3d9abfe1a1127c5d9a600dea529c32c308a42cbd3622c52211d314a716` |
| `tests/fixtures/retrieval-relevance-gate-v1/protocol-lock.json` | `6983eb5243493176d6cf97a5e7b5ae888aac9885c25e945583bc291aacf253b1` |

The hashes above were recomputed before any maintenance write. The seven canonical validators
passed against the same checkout. No historical observation or protocol file is authorized for
rewrite; later current-source validation is additive and owned by
`benchmarks/retrieval/retrieval-order-v2-compatibility.json`.

## Task 6R Execution Finding

The original post-Task-6 historical validator command covered:

```bash
uv run pytest -q \
  tests/evaluation/test_baseline.py \
  tests/evaluation/test_numeric_artifact.py \
  tests/evaluation/test_chinese_artifact.py \
  tests/evaluation/test_cjk_lexical_artifact.py \
  tests/evaluation/test_dense_artifact.py \
  tests/evaluation/test_hybrid_rrf_artifact.py \
  tests/evaluation/test_relevance_gate_artifact.py
```

It stopped with `62 passed, 71 failed`. The failures isolated three evaluation-authority
conflicts rather than a new runtime retrieval defect:

- E2 archived numeric scope hashes were still being compared with current checkout bytes.
- E3-A Chinese SQL-trace validation recognized the former opaque-ID ordering instead of the
  revision-2 stable MATCH ordering.
- Three retrieval-order workflow tests still asserted the archived revision-1 live failure after
  the runtime had moved to revision 2.

The strict default `load_numeric_protocol` and public `mke eval retrieval-numeric` path remain
current-source-bound and fail closed. Archived validation is an explicit internal compatibility
authority only. Canonical compatibility generation remains deferred until every source/test/doc
write and the one-shot holdout have completed.

The post-Task-2 observation is appended as immutable historical input 14; it is not retroactively
part of the Task 0 freeze:

| Path | SHA-256 |
|---|---|
| `benchmarks/retrieval/retrieval-order-v1-current-runtime-observation.json` | `1a98e4e6c4eabc01663991646aac46e4a73033eef8a7e17a27db2e0fdce71691` |
