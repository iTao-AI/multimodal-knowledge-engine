# Local Dense Prerequisites Implementation Review

Status: PR 1 implementation evidence recorded through Task 6A. Historical E1/E2/E3-A/E3-B
artifact identities were refreshed only after PR 1 source, lock, workflow, tests, and documentation
bytes were frozen.

Review date: 2026-06-29

Scope: E3-C PR 1 dense prerequisites only. This review covers the optional dependency boundary,
cache-only Qwen3 lifecycle, SentenceTransformers adapter, exact-cosine/sqlite-vec compatibility,
qrel-free compatibility artifact, and installed-wheel proofs. PR 2 dense comparison, threshold
selection, qrel scoring, E3-D eligibility, runtime promotion, API adapters, RRF, reranking, query
rewrite, HTTP, and UI remain out of scope.

## Evidence Summary

- Exact candidate: `qwen3-embedding-0.6b-exact-v1`.
- Model: `Qwen/Qwen3-Embedding-0.6B`.
- Revision: `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`.
- Snapshot fingerprint:
  `sha256:05b8ff893f9930fc968d88c51facc8c2fb67d3d6a6f0d16413dc94dee1adbf42`.
- Snapshot bytes: `1207489041`.
- Runtime: `sentence-transformers==5.6.0`, `huggingface-hub==1.21.0`,
  `sqlite-vec==0.1.9`.
- Canonical compatibility artifact:
  `benchmarks/retrieval/qwen3-embedding-0.6b-compatibility.json`.

No dense qrels were read or scored. The qrel-free `corpus-lock.json` binds only the frozen E3-A
document bytes, page inventory, protocol digest, and extracted text digests. It contains no query,
qrel, category, grade, observation, metric, threshold, or verdict fields.

## Resource Results

The amended PR 1 resource contract targets supported proof hosts with at least `16 GiB` physical
memory. The compatibility stress proof is explicitly not a steady-state Search memory claim.

| Environment | Status | Stress RSS | Ratio | Single-query RSS | Notes |
|---|---:|---:|---:|---:|---|
| Source worktree Python 3.13 | passed | `4164370432` | `0.24239826202392578` | `4164370432` | precheck only |
| Installed wheel Python 3.12 | passed | `4131569664` | `0.24048900604248047` | `4176494592` | canonical proof |
| Installed wheel Python 3.13 | passed | `4456693760` | `0.2594137191772461` | `2804580352` | canonical artifact source |

The canonical artifact records:

- physical memory `17179869184`;
- stress peak RSS `4456693760`;
- single-query report-only peak RSS `2804580352`;
- selected adapter `exact-cosine-v1`;
- `sqlite-vec` structured rejection `projection_size_limit_exceeded`;
- exact-cosine vector digest
  `sha256:7adc56f44b2a0c52183d4a77f92bad56ec111962b1897a09df6e47cd147cd545`;
- document vector digest
  `sha256:10d9fe385490c5f7d849fcfdbc678b672adefd46d8abaa018d7946004d70eef7`;
- query vector digest
  `sha256:393c0445bf659fcafec4f8b30c5dcd218cadd097709f1d2abc37e300b01731d2`.

## Package And Model Authorization Record

Model preparation used one explicitly authorized prepare process for the exact model, revision,
external cache, and host-specific transport policy. Two earlier failed invocations left
process-unique stale partials outside the repository; they were not deleted. The successful
prepare completed the exact 12-file snapshot. Doctor, source compatibility, installed-wheel proof,
and artifact validation were cache-only.

Python 3.13 initially failed before model load because the strict offline package cache lacked
locked embedding transitive wheels. The user authorized one Python 3.13 package cache population
only for the installed-wheel proof prerequisite. That action populated the package cache under the
current `uv.lock` and embedding extra without changing `uv.lock`, changing dependencies, changing
the model, deleting stale partials, or entering PR 2; no model download occurred. The subsequent
single Python 3.13 installed-wheel proof passed.

## Verification

Focused commands run during Task 0.5:

```bash
uv run pytest tests/evaluation/test_dense_compatibility.py \
  tests/scripts/test_dense_retrieval_deployment_proof.py -q
uv run ruff check src/mke/evaluation/dense_compatibility.py \
  scripts/dense_retrieval_deployment_proof.py \
  tests/evaluation/test_dense_compatibility.py \
  tests/scripts/test_dense_retrieval_deployment_proof.py
uv run pyright src/mke/evaluation/dense_compatibility.py \
  scripts/dense_retrieval_deployment_proof.py \
  tests/evaluation/test_dense_compatibility.py \
  tests/scripts/test_dense_retrieval_deployment_proof.py
```

Results:

- focused compatibility/proof tests: `36 passed`;
- focused Ruff: passed;
- focused Pyright: `0 errors`;
- model-free compatibility artifact validation: passed;
- Python 3.12 installed-wheel proof: passed;
- Python 3.13 installed-wheel proof: passed.

Task 6A refresh evidence:

- `artifact_refresh.py` now covers five checked-in targets, including
  `benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json`.
- RED/GREEN coverage proves all five targets are atomically replaced and validated, replacement
  failure on the fifth target rolls every file back byte-identically, recovery restores the E3-B
  target from checksum-verified backups, and E3-B observed semantic drift fails closed.
- The one PR 1 identity refresh transaction returned these checked-in identities:
  - E1 artifact:
    `8b46d3dfea9f5784cf15963aa563dc258ca9463df7df635cbfafbd7edd18e850`;
  - E2 protocol lock:
    `6c826ec1e04761b67fb06ee2c43e68c8c8a5ae6075e5f86dfa7bd1c9e3df3172`;
  - E2 artifact:
    `c1453700258aea8ad95e16d54d996c162d2d713f0d3ed20f79d2b79b0f9d595f`;
  - E3-A artifact:
    `94149a41d4957625aa39e59846114dc2f496fd311cf7afe07eb699dd34bb01d9`;
  - E3-B artifact:
    `2ec97e14cd8e7fb9848bfe81945d87e99b41d39a0e98a11182b1aabd870d208e`.
- E1/E2/E3-A/E3-B observed evaluations were rerun and their normalized semantics matched the Task
  0 snapshots exactly. Qrels, fixture bytes, observations, metrics, gates, verdicts, locators,
  compiled queries, and candidate contracts did not drift.
- Canonical E1/E2/E3-A/E3-B artifact validators passed after refresh.

## Boundary Review

The implementation keeps:

- package dependencies optional under the `embedding` extra;
- SDK objects behind adapters;
- model cache outside the repository;
- only `mke embedding prepare --allow-model-download` as a model-download path;
- doctor, proof, artifact validation, Search, Ask, MCP, and runtime operation cache-only;
- sqlite-vec as a bounded compatibility probe, not a runtime dependency or promotion;
- exact-cosine as the selected PR 1 reference adapter because every exact-reference gate passed.

It does not:

- read dense qrels;
- score dense candidate quality;
- select a threshold;
- observe holdout;
- create an E3-C comparison artifact;
- change runtime default, Search, Ask, MCP, owner startup, or SQLite domain truth;
- implement a future API adapter, RRF, reranker, query rewrite, HTTP, or UI.

## Remaining PR 1 Work

Complete the final PR 1 verification sweep after the Task 6A commit: full pytest, Ruff, Pyright,
build, proof, demo, document-release pre-PR audit, public-boundary scan, and final diff check.

Task 14 remains PR 2-only and must not repeat or overwrite the PR 1 Task 6A semantic proof.
