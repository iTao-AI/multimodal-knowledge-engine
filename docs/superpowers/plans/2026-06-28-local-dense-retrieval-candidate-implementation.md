# Local Dense Retrieval Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove one immutable, cache-only Qwen3 dense retrieval candidate against the frozen
Chinese retrieval protocol, without changing normal Search, Ask, CLI runtime, or MCP behavior.

**Architecture:** Add project-owned embedding and vector-projection ports, a cache-only
SentenceTransformers adapter, and an exact-cosine evaluation projection. Deliver the work in two
independent PRs: PR 1 proves dependencies, model lifecycle, vector correctness, portability, and
resource feasibility without new dense candidate qrel scoring; PR 2 freezes the threshold
protocol, scores development, observes holdout once, and records independently validated
comparison evidence.

**Tech Stack:** Python 3.12/3.13, `sentence-transformers==5.6.0`,
`huggingface-hub>=1.21.0,<2`, `sqlite-vec==0.1.9`, NumPy float32, SQLite, pytest, Ruff, Pyright,
Hatch/uv, GitHub Actions.

---

Status: PR 1 Tasks 0-6A, authoritative review, CI isolation fix, PR publication, squash merge, and
post-merge cleanup are complete. [PR #41](https://github.com/iTao-AI/multimodal-knowledge-engine/pull/41)
was squash-merged to `main@75d69364872cd28ef47b9e179989d93e6a259e6f`; post-merge CI, CodeQL, and
Dependency Graph passed. PR 2 has not started.

The targeted re-review covered the four fixes since
`00a4c0f2c95851635b17c5f55096a7f8fc4eb9a8`, durable documentation, and the permitted
historical artifact identity refresh. Independent verification recorded `72` targeted tests,
targeted Ruff, targeted Pyright with `0 errors`, model-free dense compatibility artifact
validation, four artifact-refresh tests, `git diff --check`, and a clean worktree. No runtime,
Search, Ask, MCP, default-strategy, or PR 2 scope drift was found.

The PR #41 CI follow-up at `c0590d1a0f6e72a991300cbc6637e5094a4ba148` fixed only test isolation:
core jobs skip the four true sqlite-vec integration tests when the optional dependency is absent,
synthetic dense tests freeze host-dependent inputs, and artifact refresh tests keep the production
environment-drift guard fail-closed. No resource ceiling, artifact, metric, gate, identity,
runtime, Search, Ask, MCP, or PR 2 behavior changed.

Planning base: `main@5ed0a722b83f9b4c70aec7c9333d8bf7d17b9335`.

Design:
[Local Dense Retrieval Candidate Design](../specs/2026-06-28-local-dense-retrieval-candidate-design.md)

Program design:
[Chinese Hybrid Retrieval Evaluation Design](../specs/2026-06-25-chinese-hybrid-retrieval-evaluation-design.md)

Autoplan review:
[Local Dense Retrieval Candidate Autoplan Review](../reviews/2026-06-28-local-dense-retrieval-candidate-autoplan-review.md)

## Non-Negotiable Boundaries

- E3-C is comparison-only. Do not change the runtime default
  `cjk-active-scan-overlap-v1` or normal Search, Ask, MCP, and owner-startup behavior.
- Do not implement an embedding API adapter, RRF, reranking, query rewrite, new segmentation,
  HTTP/UI, a persistent production vector projection, or an external vector service.
- Do not change E1/E2/E3-A/E3-B qrels, fixture bytes, historical observations, metrics, gates, or
  verdicts. Refresh only explicitly permitted source/scope identities after proving semantic
  equality.
- Only `mke embedding prepare --allow-model-download` may use the network. Doctor, evaluation,
  validators, installed-wheel proof, Search, Ask, and MCP remain cache-only.
- One explicit model-download authorization covers one `prepare` process for the approved
  model/revision/cache/transport tuple. Hugging Face Hub-managed requests and Range resumes inside
  that invocation are allowed; MKE never starts another process, SDK retry loop, transport
  fallback, alternate model/provider, or second network `snapshot_download` call.
- This model-network boundary starts after package installation. Installing `wheel[embedding]` may
  use a package index, or may be fully offline from a pre-populated wheelhouse.
- The exact model is `Qwen/Qwen3-Embedding-0.6B` at revision
  `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`. Reject aliases, arbitrary repositories, arbitrary
  revisions, remote code, and silent model/provider fallback.
- New PR 1 dense code, compatibility tests, and proof scripts must not import or consume qrels,
  run candidate qrel scoring, select a threshold, inspect candidate holdout results, or make a
  retrieval-quality claim. Existing frozen E1/E2/E3-A/E3-B regression commands may parse their
  historical qrels; those outputs are regression-only and cannot influence the dense candidate.
- PR 2 may begin only after PR 1 is merged to `main`. Do not stack PR 2 on an unmerged feature
  branch.
- Holdout may be observed exactly once, after the candidate, threshold algorithm, model,
  projection adapter, and development-selected threshold are frozen.
- If any stop condition in the design fires, leave the branch clean at the last valid checkpoint,
  record the evidence, and return to the planning window. Do not improvise a substitute.
- The PR 1 stress proof targets hosts with at least `16 GiB` physical memory and gates peak RSS at
  both `6 GiB` and `40%` of physical memory. The superseded `4 GiB` observation remains historical
  evidence; no rerun may be selected to make the old contract pass.

Autoplan review clarifications:

- a negative result constrains only `qwen3-embedding-0.6b-exact-v1`; it is not a universal dense
  retrieval verdict;
- `e3d_status=eligible` means only “run a separate E3-D fusion experiment”; it does not claim RRF
  effectiveness, and `runtime_promotion_status` remains `not_evaluated`;
- development and holdout must use separate snapshots and projections; the 70-Evidence combined
  projection exists only for PR 1 compatibility/resource measurement;
- cross-workspace canonical identity is the stable document locator plus text digest, never random
  runtime Evidence, Source, or Publication IDs;
- provider-neutral embedding contracts do not contain local tokenizer, cache, padding, dtype, or
  batch-lifecycle methods;
- the model-free validator verifies structure and derivations, while only cache-ready replay can
  prove retrieval-observation authenticity.

## Delivery Map

| PR | Purpose | Terminal evidence |
|---|---|---|
| PR 1 — dense prerequisites | Prove the exact local model and vector boundary before quality scoring | Cache-only model readiness, Python 3.12/3.13 installed-wheel proof, no truncation, deterministic embeddings, exact-KNN equivalence, resource report |
| PR 2 — dense comparison | Evaluate complementarity under the frozen protocol | Development threshold trace, one holdout observation, canonical artifact, model-free validator, cache-ready replay, `e3d_status` |

The planning docs must land before either implementation PR starts.

## Execution Setup

Before each PR, read the latest project rules and verify the repository rather than trusting this
planning snapshot:

```bash
cd <repository-root>
git fetch origin
git status --short --branch
git rev-parse HEAD origin/main
git worktree list
gh pr list --state open
sed -n '1,260p' AGENTS.md
```

Create a fresh isolated worktree from the latest `origin/main`. Recommended PR 1 names:

```bash
git worktree add .worktrees/dense-prerequisites -b codex/dense-prerequisites origin/main
cd .worktrees/dense-prerequisites
```

Recommended PR 2 names after PR 1 has merged:

```bash
git fetch origin
git worktree add .worktrees/dense-comparison -b codex/dense-comparison origin/main
cd .worktrees/dense-comparison
```

Use `high` reasoning depth for implementation and targeted review remediation. Raise to `xhigh`
only for compatibility stop conditions, evidence-integrity failures, or an architecture boundary
that would amend this plan.

## Baseline Gate For Both PRs

### Task 0: Reproduce The Frozen Baseline

**Files:**

- Read: `AGENTS.md`
- Read: `docs/superpowers/specs/2026-06-28-local-dense-retrieval-candidate-design.md`
- Read: `docs/superpowers/plans/2026-06-28-local-dense-retrieval-candidate-implementation.md`
- Read: `tests/fixtures/retrieval-chinese-v1/protocol.json`
- Read: `benchmarks/retrieval/retrieval-chinese-v1-baseline.json`
- Read: `benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json`
- Read: `src/mke/retrieval/strategy.py`

- [x] **Step 1: Confirm branch isolation and a clean baseline**

```bash
git status --short --branch
git merge-base --is-ancestor origin/main HEAD
git diff --check origin/main...HEAD
```

Expected: a clean new branch whose `HEAD` is the intended `origin/main` commit.

- [x] **Step 2: Run the current regression and artifact gates**

```bash
uv sync --all-extras --dev
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke eval retrieval \
  --manifest tests/fixtures/retrieval-eval-v1.json --json > /tmp/mke-e1-before.json
uv run mke eval retrieval-numeric \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --json > /tmp/mke-e2-before.json
uv run mke eval retrieval-chinese \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --json > /tmp/mke-e3a-before.json
uv run mke eval retrieval-cjk-lexical \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --candidate cjk-trigram-overlap-v1 \
  --json > /tmp/mke-e3b-before.json
uv run python -m mke.evaluation.baseline \
  --artifact benchmarks/retrieval/retrieval-eval-v1-baseline.json \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --repository .
uv run python -m mke.evaluation.numeric_artifact validate \
  --artifact benchmarks/retrieval/numeric-grouping-v1-comparison.json \
  --observed /tmp/mke-e2-before.json \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --repository .
uv run python -m mke.evaluation.chinese_artifact validate \
  --artifact benchmarks/retrieval/retrieval-chinese-v1-baseline.json \
  --observed /tmp/mke-e3a-before.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
uv run python -m mke.evaluation.cjk_lexical_artifact validate \
  --artifact benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json \
  --observed /tmp/mke-e3b-before.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
uv run mke proof run
uv run mke demo --verify
```

Expected: all current tests and validators pass. If a command path has changed on latest `main`,
inspect the actual CLI/module and update this plan before implementation; do not bypass a gate.

- [x] **Step 3: Capture semantic payloads for later equality checks**

The generated reports live only under `/tmp`. Remove duration/platform fields and preserve
normalized payloads for before/after comparison. Do not edit canonical artifacts in Task 0.

Expected: E3-A remains `Recall@5=0.295455`, `nDCG@10=0.277279`; E3-B remains
`Recall@5=0.659091`, `nDCG@10=0.610619`; the runtime default remains
`cjk-active-scan-overlap-v1`.

---

# PR 1: Dense Prerequisites

PR 1 proves feasibility and stops before qrel scoring. Its public result is “the exact local model
and vector path are reproducible and within the declared ceilings,” not “dense retrieval is good.”

## Task 1: Add Project-Owned Embedding Contracts

**Files:**

- Create: `src/mke/embeddings/__init__.py`
- Create: `src/mke/embeddings/contracts.py`
- Create: `tests/embeddings/test_contracts.py`
- Modify: `src/mke/interfaces/public_errors.py`
- Modify: `tests/interfaces/test_public_errors.py`

- [x] **Step 1: Write RED contract tests**

Cover:

- the only canonical model ID/revision/dimension/dtypes/instruction are the frozen design values;
- model and candidate revisions reject `bool`, floats, aliases, empty strings, and arbitrary IDs;
- query text is non-empty, bounded, and encoded with the exact `Instruct: ...\nQuery:` template;
- document text is unprefixed and Evidence order is stable;
- vectors require count equality, unique Evidence IDs, dimension `1024`, finite float32 values,
  and `abs(norm - 1.0) <= 1e-5`;
- no `sentence_transformers`, torch, Hugging Face, NumPy, or sqlite-vec object appears in a public
  project-owned DTO;
- failures map to stable redacted `problem`, `cause`, and `next_step` fields.

Use project values with this shape, adapted to current naming conventions:

```python
@dataclass(frozen=True)
class EmbeddingModelSpec:
    model_id: str
    model_revision: str
    query_instruction: str
    dimension: int
    max_length: int
    input_dtype: Literal["float32"]
    output_dtype: Literal["float32"]
    normalize: Literal[True]
    query_batch_size: Literal[1]
    document_batch_size: Literal[4]


@dataclass(frozen=True)
class EmbeddingEvidenceInput:
    document_id: str
    locator_kind: str
    locator_start: int
    locator_end: int
    text: str
    text_sha256: str
    runtime_evidence_id: str
    runtime_publication_id: str


@dataclass(frozen=True)
class EmbeddedEvidence:
    stable_locator_id: str
    vector: tuple[float, ...]


class EmbeddingProvider(Protocol):
    def embed_documents(
        self, evidence: tuple[EmbeddingEvidenceInput, ...]
    ) -> EmbeddingBatch: ...
    def embed_query(self, query: str) -> tuple[float, ...]: ...


class LocalEmbeddingRuntime(Protocol):
    def tokenize_lengths(self, texts: tuple[str, ...]) -> tuple[int, ...]: ...
```

- [x] **Step 2: Run the tests and confirm RED**

```bash
uv run pytest tests/embeddings/test_contracts.py tests/interfaces/test_public_errors.py -q
```

Expected: failures because the embedding package and public mappings do not exist.

- [x] **Step 3: Implement immutable DTOs and validation**

Keep validation in project code. SDK conversion belongs only in adapters. Store portable vectors as
tuples of Python floats after validating their float32 origin; never serialize provider tensors.
Use stable locator identity plus text digest for cross-run ordering and digests. Runtime IDs are
checked only against the current immutable snapshot and are never canonical across fresh ingests.

Required stable error causes include:

```text
embedding optional dependency is not installed
configured embedding model is not cached
configured embedding model snapshot is incomplete
configured embedding model revision is unavailable
embedding input would be truncated
embedding output count is invalid
embedding output dimension is invalid
embedding output contains non-finite values
embedding output is not normalized
```

- [x] **Step 4: Run focused tests and static checks**

```bash
uv run pytest tests/embeddings/test_contracts.py tests/interfaces/test_public_errors.py -q
uv run ruff check src/mke/embeddings tests/embeddings src/mke/interfaces/public_errors.py
uv run pyright src/mke/embeddings tests/embeddings
```

Expected: pass.

- [x] **Step 5: Commit**

```bash
git add src/mke/embeddings tests/embeddings \
  src/mke/interfaces/public_errors.py tests/interfaces/test_public_errors.py
git commit -m "feat(embedding): define local dense contracts"
```

## Task 2: Lock The Optional Runtime Dependency Boundary

**Files:**

- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `tests/packaging/test_embedding_extra.py`
- Modify: `.github/workflows/ci.yml`

- [x] **Step 1: Write RED packaging tests**

Assert:

- core wheel import succeeds without the `embedding` extra;
- importing embedding contracts does not import torch or SentenceTransformers;
- loading the adapter without the extra returns the stable dependency-missing error;
- the extra pins `sentence-transformers==5.6.0` and `sqlite-vec==0.1.9`;
- `huggingface-hub` is a declared direct dependency of the extra because project lifecycle code
  imports it;
- no LangChain, LlamaIndex, external vector service, or provider API SDK is added.

- [x] **Step 2: Confirm RED**

```bash
uv run pytest tests/packaging/test_embedding_extra.py -q
```

- [x] **Step 3: Add and lock the optional extra**

Use this direct boundary unless the resolver proves an incompatibility:

```toml
[project.optional-dependencies]
embedding = [
  "sentence-transformers==5.6.0",
  "sqlite-vec==0.1.9",
  "huggingface-hub>=1.21.0,<2",
]
```

Regenerate `uv.lock` with uv. Do not hand-edit it. Review every new direct and transitive package,
license, platform wheel, and source. A resolver conflict is a stop condition until reviewed.

```bash
uv lock
uv sync --extra embedding --dev
uv tree --extra embedding
```

- [x] **Step 4: Add model-free Python 3.12/3.13 extra gates**

The CI gate may install the extra and run imports, contract tests, a synthetic exact-cosine proof,
and a synthetic sqlite-vec compatibility proof. It must not download or load the Qwen snapshot.
Use a separate job or an explicitly larger timeout rather than consuming the existing core
10-minute job without evidence.

- [x] **Step 5: Verify and commit**

```bash
uv run pytest tests/packaging/test_embedding_extra.py -q
uv run ruff check .github tests/packaging
git diff -- pyproject.toml uv.lock .github/workflows/ci.yml
git add pyproject.toml uv.lock .github/workflows/ci.yml tests/packaging/test_embedding_extra.py
git commit -m "build(embedding): lock local dense runtime extra"
```

## Task 3: Implement Model Prepare And Doctor Lifecycle

**Files:**

- Create: `src/mke/embeddings/readiness.py`
- Create: `tests/embeddings/test_readiness.py`
- Modify: `src/mke/cli.py`
- Create: `tests/interfaces/test_cli_embedding.py`
- Modify: `docs/reference/cli.md`

- [x] **Step 1: Write RED readiness tests**

Cover:

- exact allowlisted model and revision normalization;
- aliases such as `main`, arbitrary repositories/revisions, and `trust_remote_code` are rejected
  before a network call;
- prepare is the only path that sets `local_files_only=False` and only when
  `--allow-model-download` is present;
- doctor and every library load set `local_files_only=True`;
- snapshot completeness requires the SentenceTransformers configuration, tokenizer
  configuration, model configuration, and `model.safetensors`;
- every resolved regular file is hashed by streaming reads and recorded as relative path, byte
  size, and SHA-256; Hugging Face snapshot symlinks may resolve only to a regular file under the
  same model cache `blobs/` directory. Reject cross-cache, chained, dangling, device, and directory
  links, and hash content under the snapshot-relative logical path;
- the snapshot fingerprint is a deterministic digest of sorted file manifest entries;
- incomplete, unreadable, mutated, wrong-revision, or oversized snapshots fail closed;
- errors contain no absolute cache path, SDK exception, URL query, or traceback;
- repeated prepare against a complete exact snapshot reports `already_cached` without network.

Use project-owned results:

```python
@dataclass(frozen=True)
class EmbeddingSnapshotFile:
    relative_path: str
    byte_size: int
    sha256: str


@dataclass(frozen=True)
class EmbeddingReadiness:
    status: Literal["ready", "not_ready"]
    model_id: str
    model_revision: str
    snapshot_fingerprint: str | None
    checks: tuple[ReadinessCheck, ...]
    cause: str | None
    next_step: str | None
```

- [x] **Step 2: Confirm RED**

```bash
uv run pytest tests/embeddings/test_readiness.py tests/interfaces/test_cli_embedding.py -q
```

- [x] **Step 3: Implement cache-only lifecycle and CLI**

Add:

```text
mke embedding prepare --allow-model-download --model qwen3-embedding-0.6b \
  --model-revision 97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3 \
  --model-cache <outside-repo-cache> --json

mke embedding doctor --model qwen3-embedding-0.6b \
  --model-revision 97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3 \
  --model-cache <outside-repo-cache> --json
```

`prepare` first validates the exact standard cache snapshot directly, without SDK resolution. A
complete snapshot returns `already_cached`. A missing or incomplete snapshot without permission
fails before `snapshot_download`. With explicit permission it calls
`snapshot_download(repo_id=..., revision=..., cache_dir=..., local_files_only=False,
max_workers=1)` exactly once. An SDK failure returns the stable download error immediately; MKE
must not reinvoke the SDK. `doctor` and cache-only adapter loads use
`snapshot_download(..., local_files_only=True, max_workers=1)` once and never download. The exact
model and revision are allowlisted defaults; explicit flags, when present, must equal those values.
Omission must never mean “latest.” Use a documented OS cache default plus
`MKE_EMBEDDING_CACHE`/CLI override, and reject every resolved cache path inside the repository for
both prepare and doctor.

- [x] **Step 4: Verify model-free behavior**

```bash
uv run pytest tests/embeddings/test_readiness.py tests/interfaces/test_cli_embedding.py -q
uv run mke embedding doctor --model qwen3-embedding-0.6b \
  --model-revision 97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3 \
  --model-cache /tmp/mke-empty-embedding-cache --json
```

Expected: tests pass; the empty-cache doctor returns `not_ready`, a stable next step, no download,
no absolute path, and no traceback.

- [x] **Step 5: Commit**

```bash
git add src/mke/embeddings/readiness.py src/mke/cli.py \
  tests/embeddings/test_readiness.py tests/interfaces/test_cli_embedding.py \
  docs/reference/cli.md
git commit -m "feat(embedding): add cache-only model lifecycle"
```

## Task 4: Add The SentenceTransformers Adapter

**Files:**

- Create: `src/mke/adapters/embedding/__init__.py`
- Create: `src/mke/adapters/embedding/sentence_transformers.py`
- Create: `tests/adapters/test_sentence_transformers_embedding.py`
- Modify: `src/mke/embeddings/__init__.py`

- [x] **Step 1: Write RED adapter tests using fakes**

Verify:

- dependency imports are lazy and translated to the stable error contract;
- the model is constructed from the resolved snapshot path with CPU, no network, no remote code,
  `max_seq_length=8192`, and left padding;
- query input is exactly
  `Instruct: Given a Chinese user query, retrieve relevant evidence passages that answer the query\nQuery:{query}`;
- documents have no instruction prefix and are processed in stable locator-ID order with batch
  size `4`;
- query batch size is `1`;
- output is requested as normalized float32 NumPy data, then converted to project DTOs;
- tokenize-only preflight returns actual token lengths and refuses any `>8192` input before
  encoding;
- count, identity, dimension, dtype, finite-value, norm, and partial-batch failures are rejected;
- provider objects and absolute snapshot paths never escape in public results or errors;
- cancellation between batches stops before the next encode call.

- [x] **Step 2: Confirm RED**

```bash
uv run pytest tests/adapters/test_sentence_transformers_embedding.py -q
```

- [x] **Step 3: Implement the adapter behind `EmbeddingProvider`**

Keep imports inside the adapter factory. Do not add the adapter to normal `RuntimeConfig`,
`KnowledgeEngine`, Search, Ask, or MCP.

- [x] **Step 4: Verify and commit**

```bash
uv run pytest tests/adapters/test_sentence_transformers_embedding.py \
  tests/embeddings/test_contracts.py -q
uv run ruff check src/mke/adapters/embedding tests/adapters/test_sentence_transformers_embedding.py
uv run pyright src/mke/adapters/embedding tests/adapters/test_sentence_transformers_embedding.py
git add src/mke/adapters/embedding src/mke/embeddings/__init__.py \
  tests/adapters/test_sentence_transformers_embedding.py
git commit -m "feat(embedding): add Qwen3 cache-only adapter"
```

## Task 5: Add Exact-Cosine And sqlite-vec Projection Adapters

**Files:**

- Create: `src/mke/vector/__init__.py`
- Create: `src/mke/vector/contracts.py`
- Create: `src/mke/adapters/vector/__init__.py`
- Create: `src/mke/adapters/vector/exact_cosine.py`
- Create: `src/mke/adapters/vector/sqlite_vec.py`
- Create: `tests/vector/test_contracts.py`
- Create: `tests/adapters/test_exact_cosine_projection.py`
- Create: `tests/adapters/test_sqlite_vec_projection.py`

- [x] **Step 1: Write RED project-owned vector tests**

Use contracts equivalent to:

```python
@dataclass(frozen=True)
class RankedEvidence:
    stable_locator_id: str
    rank: int
    score: float
    adapter_id: str


class VectorProjection(Protocol):
    def replace(self, batch: EmbeddingBatch) -> ProjectionIdentity: ...
    def validate(self, expected: ProjectionIdentity) -> None: ...
    def search(self, query_vector: tuple[float, ...], *, top_k: int) \
        -> tuple[RankedEvidence, ...]: ...
    def close(self) -> None: ...
```

Test:

- dimension `1024`, normalized finite vectors, unique stable locator IDs, and complete inventory;
- atomic replace: failed validation leaves no partial active projection;
- source-text/model/vector aggregate digests bind every row;
- exact cosine uses float32 inputs and returns cosine similarity, portable score rounded to six
  decimals, then sorts score descending and stable locator ID ascending;
- `top_k=10` is enforced for the canonical candidate;
- sqlite-vec load/insert/search/delete/transaction/rebuild behavior;
- sqlite-vec order equals the independent project exact-cosine reference for synthetic normal,
  tie, negative, and near-tie vectors;
- for each 34- or 36-row partition, sqlite-vec returns every exact distance before project code
  converts `similarity = 1 - cosine_distance`, validates range/finite values, rounds to six
  decimals, applies the stable locator tie-break, and truncates to top 10; SQL must not `LIMIT 10`
  before canonical tie resolution;
- rank-10/rank-11 vectors whose raw scores differ but round to the same portable score preserve the
  project-owned locator tie-break;
- extension-unavailable and incompatible results fail closed; no lexical fallback;
- temporary projection files remain outside the repository and are removed on normal completion.

- [x] **Step 2: Confirm RED**

```bash
uv run pytest tests/vector tests/adapters/test_exact_cosine_projection.py \
  tests/adapters/test_sqlite_vec_projection.py -q
```

- [x] **Step 3: Implement the reference first, then sqlite-vec**

The project-owned reference is the correctness oracle. The selected sqlite-vec adapter must expose
the same project-owned output. Do not compare or fuse lexical and cosine raw scores.

- [x] **Step 4: Verify and commit**

```bash
uv run pytest tests/vector tests/adapters/test_exact_cosine_projection.py \
  tests/adapters/test_sqlite_vec_projection.py -q
uv run ruff check src/mke/vector src/mke/adapters/vector tests/vector \
  tests/adapters/test_exact_cosine_projection.py tests/adapters/test_sqlite_vec_projection.py
uv run pyright src/mke/vector src/mke/adapters/vector tests/vector
git add src/mke/vector src/mke/adapters/vector tests/vector \
  tests/adapters/test_exact_cosine_projection.py tests/adapters/test_sqlite_vec_projection.py
git commit -m "feat(vector): add exact local projection adapters"
```

## Task 0.5: Run The Compatibility And Resource Spike

This is the hard pre-qrel gate for new dense code. Complete Tasks 1–5 first, then stop for explicit
download authorization. The compatibility runner and its inputs do not read or score qrels.
Historical regression commands elsewhere in PR 1 remain separate from this proof.

**Files:**

- Create: `src/mke/evaluation/dense_compatibility.py`
- Create: `tests/evaluation/test_dense_compatibility.py`
- Create: `scripts/dense_retrieval_deployment_proof.py`
- Create: `tests/scripts/test_dense_retrieval_deployment_proof.py`
- Create: `tests/fixtures/retrieval-dense-v1/corpus-lock.json`
- Create after successful proof: `benchmarks/retrieval/qwen3-embedding-0.6b-compatibility.json`

- [x] **Step 1: Write RED compatibility tests**

The report schema must contain no qrels or relevance metrics. It records:

- exact model/revision/snapshot manifest/package/platform/Python identities;
- CPU and remote-code-disabled proof;
- every frozen Evidence token length and a zero-truncation verdict;
- repeated query and document vector digests, max component delta, norm delta, rank/order delta,
  and the proposed `1e-5` score tolerance verdict;
- sqlite-vec versus exact-cosine order/score proof, or a structured sqlite-vec rejection selecting
  the project exact-cosine reference;
- model snapshot bytes, peak RSS, 70-Evidence projection bytes, model load duration, projection
  build duration, and one-query-plus-KNN duration;
- all resource ceilings and one overall compatibility verdict.

The validator must reject missing fields, bool-as-int, non-finite values, wrong model identity,
wrong package versions, manifest tampering, impossible measurements, and a passing verdict with a
failed gate.

- [x] **Step 2: Confirm RED with synthetic inputs**

```bash
uv run pytest tests/evaluation/test_dense_compatibility.py \
  tests/scripts/test_dense_retrieval_deployment_proof.py -q
```

- [x] **Step 3: Implement a cache-only proof runner**

The proof runner must:

1. prove it is running from an installed wheel in an isolated environment and external cwd;
2. clear `PYTHONPATH`, `PYTHONHOME`, and `VIRTUAL_ENV` from child execution;
3. disable network and reject any attempted download;
4. read the frozen Evidence text without loading qrels or category/relevance fields;
5. tokenize, embed, build, search fixed non-qrel probes, measure, and validate;
6. write only to an explicit `/tmp` output path until the report is accepted.

`corpus-lock.json` is the qrel-free PR 1 input. It binds the unchanged E3-A document fixture bytes,
page/Evidence locator inventory, protocol file digest, and expected Evidence count, but contains no
query, qrel, category, grade, development metric, or holdout metric. Build and validate this lock
without importing the qrel parser. Any mismatch with the frozen document bytes stops the proof.

- [x] **Step 4: Stop and request exact download authorization**

2026-06-29 execution amendment: authorization is invocation-level, not individual HTTP-request
level. One explicit authorization covers exactly one `prepare` process and Hugging Face
Hub-managed transport requests/Range resumes within that process. It does not authorize MKE to
start a second process or reinvoke `snapshot_download`. Hugging Face Hub 1.21.0 exposes no public
retry-count or disable-resume parameter, so transport requests must not be described as
retry-count bounded.

The outer proof supervisor enforces one immutable model/revision/cache/transport tuple, a maximum
45-minute process lifetime, and termination after 10 minutes without model-cache byte progress.
Termination never starts another command automatically. MKE calls network `snapshot_download`
once with `max_workers=1` and has no retry loop or silent fallback.

The execution window must report:

```text
Model: Qwen/Qwen3-Embedding-0.6B
Revision: 97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3
Cache: operator-selected path outside the repository
Networked command: one explicitly authorized mke embedding prepare process only
Expected largest weight file: model.safetensors, about 1.19 GB
Authorization policy: library-managed requests/Range resumes are allowed inside this invocation;
any new CLI invocation or process restart requires a new explicit authorization
Stop gates: total wall clock <= 45 minutes; no cache-byte progress <= 10 minutes
```

The completed host-specific proof used explicit regular HTTP with
`HF_HUB_DISABLE_XET=1 HF_HUB_DOWNLOAD_TIMEOUT=30` after two separately authorized failed
invocations exposed an Xet no-progress stall and an HTTP peer close. Those environment variables
were proof transport inputs, not product defaults. The successful third invocation completed the
exact 12-file snapshot in about 46 seconds. Two stale process-unique partials remain outside the
repository and require separate deletion authorization.

- [x] **Step 5: Run the one authorized prepare, then cache-only doctor**

Recorded host-specific command after authorization:

```bash
HF_HUB_DISABLE_XET=1 HF_HUB_DOWNLOAD_TIMEOUT=30 uv run mke embedding prepare \
  --allow-model-download \
  --model qwen3-embedding-0.6b \
  --model-revision 97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3 \
  --model-cache "$HOME/Library/Caches/mke/embedding" --json
uv run mke embedding doctor \
  --model qwen3-embedding-0.6b \
  --model-revision 97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3 \
  --model-cache "$HOME/Library/Caches/mke/embedding" --json
```

Expected: prepare succeeds once; doctor is `ready`, cache-only, and reports a complete redacted
manifest identity. Library-managed transport resumes are allowed only within the authorized
process. If a process fails or an outer gate fires, stop. Do not broaden model/revision/cache/
transport policy or start a new invocation without explicit authorization.

- [x] **Step 6: Run Python 3.12 and 3.13 installed-wheel proof**

2026-06-29 resource-measurement amendment: the original stress peak ceiling of `4 GiB` had no
declared minimum host class and conflated the qrel-free determinism stress workload with a normal
runtime query. On a `16 GiB` Apple Silicon host, the first Python 3.12 installed-wheel stress proof
measured `4,300,947,456` bytes, only `5,980,160` bytes above that old limit, while the host had no
swap activity and every non-resource gate passed. No qrels had been read or scored. That result
remains a failure under the superseded contract and must never be relabeled as passing.

Before another real proof, write RED tests and update the report/validator so they:

- record physical memory and reject a host below `16 GiB`;
- require stress peak RSS `<= 6 GiB` and `<= 40%` of physical memory;
- independently recompute the peak-RSS ratio and reject bool, non-positive, inconsistent, or
  non-finite resource fields;
- label the 70-Evidence double-embedding run as `compatibility_stress`, not runtime Search memory;
- run a separate fresh cache-only model-load-plus-single-query process and record its peak RSS as
  report-only evidence; missing, non-finite, source-tree, wrong-interpreter, or networked query-smoke
  evidence fails proof integrity, but the measured value has no PR 1 ceiling;
- bump the compatibility report schema so a superseded `4 GiB` report cannot validate under the
  amended contract.

Use isolated venvs outside the repository, install the built `wheel[embedding]`, run from an
external cwd with hostile `PYTHONPATH`, and keep network disabled. Both environments must prove
installed identity, cache-only model load, no truncation, deterministic output within tolerance,
projection equivalence, and all ceilings:

```text
host physical memory >= 16 GiB
snapshot <= 1.5 GiB
compatibility stress peak RSS <= 6 GiB and <= 40% of physical memory
70-Evidence projection <= 1 MiB
one query embedding plus exact-KNN <= 5 s
single-query peak RSS = report-only
```

After the amended tests and validator pass, run one fresh Python 3.12 installed-wheel proof and one
fresh Python 3.13 installed-wheel proof. Each version gets one canonical run; do not repeat a
version to select a lower RSS. Reuse the complete external model cache and pre-populated package
cache without network access. The earlier source-worktree Python 3.13 observation and superseded
Python 3.12 result remain execution evidence, not canonical amended-contract proofs.

- [x] **Step 7: Apply stop conditions**

Stop and return to planning if Qwen3 fails package, Python, CPU, snapshot, remote-code,
determinism, truncation, or the amended resource gates. If sqlite-vec alone fails, record its structured
rejection and select the project exact-cosine reference only if every exact-reference gate passes.
Do not automatically choose BGE or another model. The observed sqlite-vec file-size rejection is
not a candidate failure when exact-cosine passes every required gate.

- [x] **Step 8: Record and commit compatibility evidence**

Only after both Python proofs pass:

```bash
git add src/mke/evaluation/dense_compatibility.py \
  tests/evaluation/test_dense_compatibility.py \
  scripts/dense_retrieval_deployment_proof.py \
  tests/scripts/test_dense_retrieval_deployment_proof.py \
  tests/fixtures/retrieval-dense-v1/corpus-lock.json \
  benchmarks/retrieval/qwen3-embedding-0.6b-compatibility.json
git commit -m "test(embedding): prove Qwen3 dense compatibility"
```

## Task 6: Finish PR 1 Documentation, CI, And Review Evidence

**Files:**

- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/reference/cli.md`
- Modify: `docs/explanation/architecture.md`
- Create: `docs/how-to/prepare-local-embeddings.md`
- Create after implementation review:
  `docs/superpowers/reviews/2026-06-28-local-dense-prerequisites-review.md`
- Modify: `.github/workflows/ci.yml`

- [x] **Step 1: Write RED documentation/packaging assertions**

Add tests that require:

- the optional install and exact prepare/doctor commands;
- source-checkout installation, built `wheel[embedding]` installation, and fully offline install
  from a pre-populated wheelhouse;
- comparison-only wording and no Search/Ask/MCP dense claim;
- the model license/source/revision, cache-only boundary, external cache, resource ceilings, and
  API-adapter deferral;
- architecture diagrams showing SDKs remain behind project-owned ports;
- CI model-free gates and local cache-ready proof separation.

- [x] **Step 2: Update docs and the model-free CI gate**

Do not commit local cache files, model weights, virtualenvs, raw absolute paths, or raw GStack
artifacts. CI may install the extra and run synthetic/model-free proofs only.

## Task 6A: Refresh Historical Artifact Identities

Approved targeted amendment after implementation reproduced a sequencing conflict: PR 1 changes
`pyproject.toml`, `uv.lock`, source files, and CI workflow bytes, while the frozen E1/E2/E3-A/E3-B
artifacts bind those identities. The original Task 14 occurs in PR 2, so it cannot make PR 1
validators pass.

Do not run this refresh until Tasks 4, 5, 0.5, and Task 6 Steps 1-2 are complete and all PR 1
source, lock, workflow, tests, and documentation bytes are frozen. Run the transaction once.

**Files:**

- Modify: `src/mke/evaluation/artifact_refresh.py`
- Modify: `tests/evaluation/test_artifact_refresh.py`
- Identity-only refresh targets:
  - `benchmarks/retrieval/retrieval-eval-v1-baseline.json`
  - `tests/fixtures/retrieval-numeric-v1/protocol-lock.json`
  - `benchmarks/retrieval/numeric-grouping-v1-comparison.json`
  - `benchmarks/retrieval/retrieval-chinese-v1-baseline.json`
  - `benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json`

- [x] **Step 1: Write RED five-target transaction tests**

Require atomic replacement and checked-in validation of all five targets, byte-identical rollback
when replacement of the fifth target fails, recovery coverage for the fifth target, and fail-closed
rollback for any qrel, fixture, manifest, protocol candidate, observation, metric, gate, verdict,
compiled-query, locator, or candidate-contract change. Identity-only source/scope changes pass.

- [x] **Step 2: Extend the supported transaction without weakening validators**

Add the E3-B observed input, record step, staged validation, checked-in validation, backup,
replacement, and recovery coverage. Do not delete bound source paths, shrink the E2 scope fence,
relax a validator, convert an integrity failure to a warning, create an E3-C comparison artifact, or
read dense candidate qrels.

- [x] **Step 3: Run the one identity refresh after PR 1 bytes are frozen**

Use Task 0 normalized E1/E2/E3-A/E3-B snapshots as the semantic oracle. Historical evaluation may
read its own frozen qrels only for this approved regression workflow. Before replacement, require
exact equality for qrels, fixture bytes, manifests, candidate contracts, locators, compiled
queries, ordered results, observations, metrics, gates, and verdicts. Only declared source/scope
identity metadata derived from final PR 1 bytes may change.

- [x] **Step 4: Validate and commit separately**

Run all four observed evaluations, all canonical validators, targeted artifact-refresh tests, and
the Task 0 normalized semantic comparison again. Any semantic delta, unknown invalidation path, or
unexplained artifact diff is a stop condition.

```bash
git add src/mke/evaluation/artifact_refresh.py \
  tests/evaluation/test_artifact_refresh.py \
  tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  benchmarks/retrieval/retrieval-eval-v1-baseline.json \
  benchmarks/retrieval/numeric-grouping-v1-comparison.json \
  benchmarks/retrieval/retrieval-chinese-v1-baseline.json \
  benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json
git commit -m "test(eval): refresh PR 1 artifact identities"
```

- [x] **Step 3: Run the complete PR 1 verification**

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
uv run mke eval retrieval-numeric \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --json > /tmp/mke-e2-after-pr1.json
uv run mke eval retrieval-chinese \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --json > /tmp/mke-e3a-after-pr1.json
uv run mke eval retrieval-cjk-lexical \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --candidate cjk-trigram-overlap-v1 \
  --json > /tmp/mke-e3b-after-pr1.json
uv run python -m mke.evaluation.baseline \
  --artifact benchmarks/retrieval/retrieval-eval-v1-baseline.json \
  --manifest tests/fixtures/retrieval-eval-v1.json --repository .
uv run python -m mke.evaluation.numeric_artifact validate \
  --artifact benchmarks/retrieval/numeric-grouping-v1-comparison.json \
  --observed /tmp/mke-e2-after-pr1.json \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json --repository .
uv run python -m mke.evaluation.chinese_artifact validate \
  --artifact benchmarks/retrieval/retrieval-chinese-v1-baseline.json \
  --observed /tmp/mke-e3a-after-pr1.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json --repository .
uv run python -m mke.evaluation.cjk_lexical_artifact validate \
  --artifact benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json \
  --observed /tmp/mke-e3b-after-pr1.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json --repository .
git diff --check origin/main...HEAD
```

These historical regression commands may parse frozen qrels, but they do not expose qrels to the
new dense compatibility modules and cannot select any dense setting. Also rerun the cache-ready
Python 3.12/3.13 installed-wheel proof. Compare the normalized
E1/E2/E3-A/E3-B reports to Task 0. Only permitted identity metadata may differ; observations,
metrics, gates, and verdicts must be equal.

- [x] **Step 4: Run `gstack-document-release` and light self-review**

Audit reference/how-to/explanation/README coverage and diagram drift. Do not run the planning
window’s final authoritative `gstack-review` here unless explicitly instructed.

- [x] **Step 5: Commit documentation and CI**

```bash
git add README.md docs .github/workflows/ci.yml
git commit -m "docs(embedding): document local dense prerequisites"
```

- [x] **Step 6: Handoff PR 1 for authoritative review**

Leave a clean local branch. Report exact base/HEAD/diff, dependency graph, model manifest identity,
compatibility artifact identity, resource measurements, Python 3.12/3.13 proof, complete
verification, and unchanged behavior. Do not push or create a PR until authorized after review.

The planning window then runs one authoritative `gstack-review`. The execution window uses
`superpowers:receiving-code-review` for confirmed findings, reruns targeted/full verification, and
returns for targeted re-review. After a clean verdict and user authorization, push and create a
Ready PR. PR #41 has completed this sequence; PR 2 starts only from latest `main`.

---

# PR 2: Dense Comparison Evidence

Start from the latest `origin/main` after PR 1 merge. Confirm the PR 1 compatibility artifact and
cache-ready proof still validate before reading qrels.

## Task 7A: Audit Residual Development Misses

**Files:**

- Create: `src/mke/evaluation/dense_miss_audit.py`
- Create: `tests/evaluation/test_dense_miss_audit.py`
- Create after validation:
  `benchmarks/retrieval/qwen3-embedding-0.6b-development-miss-audit.json`

- [x] **Step 1: Write RED audit tests**

For every current-runtime development grade-2 miss in `semantic_paraphrase`, `multi_condition`,
and `ranking_hard_negative`, record the compiled query, active-scan terms, lexical overlap with
each grade-2 page, page length, answer-span locality when mechanically observable, and whether
numeric/entity/multi-condition constraints are present. The report may label dense,
constraint-preserving decomposition, segmentation, or query rewrite only as hypotheses; query
category is not causal evidence.

Reject holdout input, missing target misses, changed qrels/locators, subjective causal labels,
private paths, and any report that silently reclassifies a query.

- [x] **Step 2: Implement and validate the development-only audit**

```bash
uv run pytest tests/evaluation/test_dense_miss_audit.py -q
```

The audit does not alter the approved candidate or gates. If it proves the target misses are not
plausibly addressable by page-level semantic similarity, stop for a plan amendment before dense
scoring.

- [x] **Step 3: Commit**

```bash
git add src/mke/evaluation/dense_miss_audit.py \
  tests/evaluation/test_dense_miss_audit.py \
  benchmarks/retrieval/qwen3-embedding-0.6b-development-miss-audit.json
git commit -m "test(eval): audit residual Chinese retrieval misses"
```

## Task 7: Freeze The Dense Comparison Protocol

**Files:**

- Create: `tests/fixtures/retrieval-dense-v1/protocol-lock.json`
- Create: `src/mke/evaluation/dense_protocol.py`
- Create: `tests/evaluation/test_dense_protocol.py`

- [x] **Step 1: Write RED protocol tests**

Freeze and validate:

- candidate `qwen3-embedding-0.6b-exact-v1`, revision integer `1` and not `bool`;
- exact model/revision, 1024 dimensions, float32, normalization, CPU, no remote code;
- exact query instruction/template, document prompt none, max length 8192, left padding, document
  batch 4, query batch 1;
- selected PR 1 projection adapter identity and independent exact-cosine reference;
- `top_k=10`, six-decimal portable score, score-desc/Evidence-ID-asc order;
- threshold grid `0.00..1.00` inclusive in `0.01` steps and exact selection algorithm;
- target classes exactly `semantic_paraphrase`, `multi_condition`,
  `ranking_hard_negative`;
- development and holdout gates from the design;
- references to the unchanged E3-A protocol/qrels/fixture/locator inventory, E3-B artifact, current
  runtime strategy, and PR 1 compatibility artifact;
- explicit state fields that prevent holdout observation before development freeze;
- separate development and holdout snapshot/projection identities; combined-corpus candidate
  scoring is invalid;
- exact byte size and SHA-256 identities for every bound input.

Reject missing/extra fields, duplicate thresholds, reordered target classes, bool-as-int,
non-finite numbers, path traversal, absolute locators, unknown Evidence IDs, and any qrel/fixture
identity drift.

- [x] **Step 2: Confirm RED**

```bash
uv run pytest tests/evaluation/test_dense_protocol.py -q
```

- [x] **Step 3: Implement strict protocol loading**

Use repository-relative locators and `Path.resolve()` containment checks. Do not bind feature
commit ancestry; bind durable file bytes, candidate/model identity, and explicit source inventory
so squash merge and shallow clones remain valid.

- [x] **Step 4: Verify and commit**

```bash
uv run pytest tests/evaluation/test_dense_protocol.py -q
git add tests/fixtures/retrieval-dense-v1/protocol-lock.json \
  src/mke/evaluation/dense_protocol.py tests/evaluation/test_dense_protocol.py
git commit -m "test(eval): freeze E3-C dense comparison protocol"
```

## Task 8: Build The Dense Candidate Runner Without Holdout Access

**Files:**

- Create: `src/mke/evaluation/dense_candidate.py`
- Create: `tests/evaluation/test_dense_candidate.py`
- Modify: `src/mke/evaluation/__init__.py`

- [x] **Step 1: Write RED candidate tests**

Test:

- only active frozen Evidence is embedded, in stable locator-ID order;
- development and holdout each build a separate immutable snapshot and temporary projection;
- every returned locator belongs to the query partition, including when a cross-partition page has
  a deliberately higher synthetic similarity;
- canonical inputs and results use `document_id + locator + text_sha256`; random runtime IDs are
  current-snapshot integrity fields only;
- candidate runner reuses PR 1 cache-only model readiness and adapter contracts;
- frozen snapshot inventory, text digest, model fingerprint, and projection identity are checked
  before search;
- every query uses the exact query instruction, `top_k=10`, selected adapter, portable score, and
  deterministic tie-break;
- threshold filtering is explicit and cannot change KNN order;
- candidate results include complete ordered Evidence observations, locators, raw/portable score,
  vector/projection digests, and latency;
- no normal runtime database, Search, Ask, MCP, `RuntimeConfig`, or retrieval default is mutated;
- no lexical fallback occurs on dependency/model/projection failure;
- a development-only API cannot receive a holdout partition;
- cancellation and partial embedding/projection results fail closed.

- [x] **Step 2: Confirm RED**

```bash
uv run pytest tests/evaluation/test_dense_candidate.py -q
```

- [x] **Step 3: Implement the development-only runner**

Separate candidate generation from qrel grading. The candidate layer returns ordered retrieval
observations; metrics and gate decisions belong in comparison code.

- [x] **Step 4: Verify and commit**

```bash
uv run pytest tests/evaluation/test_dense_candidate.py -q
uv run ruff check src/mke/evaluation/dense_candidate.py \
  tests/evaluation/test_dense_candidate.py
uv run pyright src/mke/evaluation/dense_candidate.py \
  tests/evaluation/test_dense_candidate.py
git add src/mke/evaluation/dense_candidate.py src/mke/evaluation/__init__.py \
  tests/evaluation/test_dense_candidate.py
git commit -m "feat(eval): add cache-only dense candidate runner"
```

## Task 9: Implement Development Threshold Selection

**Files:**

- Create: `src/mke/evaluation/dense_threshold.py`
- Create: `tests/evaluation/test_dense_threshold.py`

- [x] **Step 1: Write RED threshold-selection tests**

Use synthetic observations to prove this exact order:

1. reject development thresholds with unanswerable no-hit `<0.500000`;
2. reject thresholds with hard-negative failure `>0.300000`;
3. maximize recovered grade-2 Evidence missed by the current runtime in the three target classes;
4. break ties with dense nDCG@10 descending;
5. break remaining ties with the higher threshold.

Also test:

- grid is exactly 101 values from `0.00` to `1.00`;
- Decimal/integer basis avoids float-step drift;
- number/date recovery is report-only and cannot increase the qualifying recovery count;
- every threshold records inputs, metrics, rejection reasons, recovery identities, and selection
  rank;
- the report includes every equally optimal contiguous threshold interval and development
  leave-one-query-out sensitivity; neither changes the frozen selection rule;
- no eligible threshold returns a valid negative development result rather than throwing or
  observing holdout;
- bool, non-finite, out-of-range, missing, reordered, or coordinated trace/verdict tampering is
  rejected.

- [x] **Step 2: Confirm RED**

```bash
uv run pytest tests/evaluation/test_dense_threshold.py -q
```

- [x] **Step 3: Implement pure selection functions**

Keep selection deterministic and independent of the model adapter. Use existing graded metric
functions where their exact semantics match; add focused tests before extending them.

- [x] **Step 4: Verify and commit**

```bash
uv run pytest tests/evaluation/test_dense_threshold.py \
  tests/evaluation/test_graded_metrics.py -q
git add src/mke/evaluation/dense_threshold.py tests/evaluation/test_dense_threshold.py
git commit -m "feat(eval): select dense refusal threshold"
```

## Task 10: Compare Four Arms And Enforce One Holdout Observation

**Files:**

- Create: `src/mke/evaluation/dense_comparison.py`
- Create: `tests/evaluation/test_dense_comparison.py`

- [x] **Step 1: Write RED comparison tests with frozen synthetic reports**

Require four separately identified arms:

1. E3-A historical FTS5 baseline;
2. frozen E3-B `cjk-trigram-overlap-v1`;
3. current runtime `cjk-active-scan-overlap-v1`;
4. dense `qwen3-embedding-0.6b-exact-v1`.

Test:

- E3-A/E3-B observations are loaded as historical integrity inputs, not rerun with altered policy;
- current runtime lexical observations are regenerated using the shipped strategy and must equal
  the frozen expected semantics;
- development dense observations select and freeze one threshold before any holdout call;
- a state latch prevents a second holdout evaluation in the same run and a protocol completion
  record prevents accidental re-recording without explicit artifact replacement workflow;
- development eligibility requires at least 2 qualifying recovered grade-2 misses, no-hit
  `>=0.5`, hard-negative failure `<=0.3`;
- holdout eligibility requires at least 2 qualifying recovered grade-2 misses, no-hit `>=0.5`,
  hard-negative failure `<=0.142857`;
- development failure creates a valid negative result and does not inspect holdout;
- holdout failure creates `candidate_status=completed` and `e3d_status=not_eligible`, not an
  implementation error;
- no safety-eligible threshold is also a valid completed negative result with exit code `0`;
- `e3d_status` is experiment eligibility only and every result has
  `runtime_promotion_status=not_evaluated`;
- number/date, exact lexical, proper noun, and mixed results are reported but do not incorrectly
  qualify E3-D;
- no arm raw scores are fused or compared across score spaces.

- [x] **Step 2: Confirm RED**

```bash
uv run pytest tests/evaluation/test_dense_comparison.py -q
```

- [x] **Step 3: Implement the comparison state machine**

Use immutable intermediate results. The only path to holdout accepts a frozen development result
containing the selected threshold and candidate/projection/model identities. Any identity change
between partitions fails closed.

- [x] **Step 4: Verify and commit before real qrel scoring**

```bash
uv run pytest tests/evaluation/test_dense_protocol.py \
  tests/evaluation/test_dense_candidate.py \
  tests/evaluation/test_dense_threshold.py \
  tests/evaluation/test_dense_comparison.py -q
git add src/mke/evaluation/dense_comparison.py tests/evaluation/test_dense_comparison.py
git commit -m "feat(eval): compare dense retrieval complementarity"
```

## Task 11: Add The Canonical Artifact And Independent Validators

**Files:**

- Create: `src/mke/evaluation/dense_artifact.py`
- Create: `tests/evaluation/test_dense_artifact.py`
- Create: `src/mke/evaluation/dense_replay.py`
- Create: `tests/evaluation/test_dense_replay.py`
- Modify: `src/mke/evaluation/artifact_refresh.py`
- Modify: `tests/evaluation/test_artifact_refresh.py`

- [x] **Step 1: Write RED model-free artifact tests**

The validator must independently recompute from recorded observations:

- schema, source/protocol/qrel/fixture/locator/model/projection identities;
- threshold grid, every threshold metric/rejection reason, selected threshold, and tie-break;
- per-partition/per-category/overall graded metrics;
- complementarity recovery identities against current runtime;
- development/holdout gates, `candidate_status`, and `e3d_status`;
- complete result order, rank continuity, unique Evidence IDs, locator inventory, portable score
  range/precision, and partition ownership;
- resource and package compatibility linkage to the PR 1 artifact.

It must reject artifact-only tampering, unknown locators, duplicate/missing queries, bool-as-int,
non-finite numbers, source mutation, inconsistent derived fields, and false passing verdicts. It
must pass in a shallow squash-landed clone without feature commit ancestry. A coordinated
replacement of retrieval observations plus all derived fields is outside the model-free oracle and
must be rejected by cache-ready replay instead.

- [x] **Step 2: Write RED cache-ready replay tests**

Replay must:

- verify actual snapshot files against the recorded manifest;
- reconstruct the same frozen Evidence snapshot from page text;
- regenerate document/query embeddings and the temporary projection;
- compare locator/order exactly and portable cosine scores with absolute tolerance `1e-5`;
- reject a true `>1e-5` score mutation, order mutation, vector/source digest mutation, model-file
  mutation, and coordinated report+artifact mutation;
- never download or silently use another adapter.

- [x] **Step 3: Confirm RED**

```bash
uv run pytest tests/evaluation/test_dense_artifact.py \
  tests/evaluation/test_dense_replay.py \
  tests/evaluation/test_artifact_refresh.py -q
```

- [x] **Step 4: Implement strict record/validate/replay paths**

Keep model-free CI validation separate from cache-ready local replay. `artifact_refresh.py` may
refresh only allowlisted source/scope identities and must require before/after semantic equality.
It must not regenerate relevance observations opportunistically.

- [x] **Step 5: Verify and commit**

```bash
uv run pytest tests/evaluation/test_dense_artifact.py \
  tests/evaluation/test_dense_replay.py \
  tests/evaluation/test_artifact_refresh.py -q
git add src/mke/evaluation/dense_artifact.py src/mke/evaluation/dense_replay.py \
  src/mke/evaluation/artifact_refresh.py \
  tests/evaluation/test_dense_artifact.py tests/evaluation/test_dense_replay.py \
  tests/evaluation/test_artifact_refresh.py
git commit -m "feat(eval): validate dense comparison evidence"
```

## Task 12: Add The Comparison CLI And Measurement Harness

**Files:**

- Modify: `src/mke/cli.py`
- Modify: `src/mke/evaluation/__init__.py`
- Modify: `tests/interfaces/test_cli_evaluation.py`
- Create: `scripts/dense_retrieval_measurement.py`
- Create: `tests/scripts/test_dense_retrieval_measurement.py`
- Modify: `.github/workflows/ci.yml`

- [x] **Step 1: Write RED CLI tests**

Command shape:

```text
mke eval retrieval-dense \
  --protocol tests/fixtures/retrieval-dense-v1/protocol-lock.json \
  --candidate qwen3-embedding-0.6b-exact-v1 \
  --model-cache <outside-repo-cache> \
  --development-only \
  --record-development-freeze <development-freeze.json> \
  [--json]

mke eval retrieval-dense \
  --protocol tests/fixtures/retrieval-dense-v1/protocol-lock.json \
  --candidate qwen3-embedding-0.6b-exact-v1 \
  --model-cache <outside-repo-cache> \
  --development-freeze <development-freeze.json> \
  --record <artifact.json> \
  --record-holdout-receipt <holdout-receipt.json> \
  [--json]
```

Test:

- protocol and candidate are required and allowlisted;
- `--development-only` structurally cannot load holdout fixtures, qrels, or projections and
  requires `--record-development-freeze`;
- the holdout form requires a validated committed development freeze and exclusive-create receipt;
  incompatible phase flags are usage errors;
- `--db`, runtime strategy/query policy, arbitrary model/revision, URL, credential, provider,
  request-time adapter, and download flags are rejected as usage errors before evaluation;
- missing dependency/cache/incomplete model/projection/integrity failures return stable redacted
  errors without traceback;
- human and JSON output distinguish historical, current lexical, dense, safety, complementarity,
  resources, `candidate_status`, and `e3d_status`;
- a valid negative comparison returns a recorded result and documented exit behavior;
- valid negative outcomes return exit `0` with `candidate_status=completed`,
  `e3d_status=not_eligible`, and `runtime_promotion_status=not_evaluated`; integrity and execution
  failures return non-zero with the public error contract;
- CLI reference includes an automation example that checks JSON `e3d_status`; `$? == 0` alone only
  means a trustworthy evaluation completed;
- record is atomic and cannot overwrite an existing canonical artifact without the explicit
  maintenance workflow;
- no normal Search/Ask/MCP help or schema changes.

- [x] **Step 2: Confirm RED**

```bash
uv run pytest tests/interfaces/test_cli_evaluation.py \
  tests/scripts/test_dense_retrieval_measurement.py -q
```

- [x] **Step 3: Implement CLI and measurement separation**

The CI measurement path validates the checked-in artifact model-free. The cache-ready local
measurement path requires an already prepared exact model and may run replay. Neither path
downloads.

- [x] **Step 4: Verify and commit**

```bash
uv run pytest tests/interfaces/test_cli_evaluation.py \
  tests/scripts/test_dense_retrieval_measurement.py -q
uv run ruff check src/mke/cli.py scripts/dense_retrieval_measurement.py
uv run pyright src/mke/cli.py scripts/dense_retrieval_measurement.py
git add src/mke/cli.py src/mke/evaluation/__init__.py \
  tests/interfaces/test_cli_evaluation.py \
  scripts/dense_retrieval_measurement.py \
  tests/scripts/test_dense_retrieval_measurement.py .github/workflows/ci.yml
git commit -m "feat(cli): expose dense retrieval comparison"
```

## Task 13: Run Development Once, Freeze, Then Observe Holdout Once

Do not begin until Tasks 7–12 pass and the exact PR 1 compatibility artifact validates.

- [x] **Step 1: Run pre-qrel integrity gates**

```bash
uv run pytest tests/evaluation/test_dense_protocol.py \
  tests/evaluation/test_dense_candidate.py \
  tests/evaluation/test_dense_threshold.py \
  tests/evaluation/test_dense_comparison.py \
  tests/evaluation/test_dense_artifact.py \
  tests/evaluation/test_dense_replay.py -q
```

Revalidate all historical artifacts, exact fixture/qrel bytes, runtime default, model manifest,
and projection adapter. Any mismatch stops the run.

2026-06-29 amendment: PR 2 source additions invalidated E1/E2/E3-A source/scope identities before
dense qrel scoring, while E1/E2/E3-A/E3-B observed evaluations remained normalized-semantics equal
to the Task 0 snapshots. To avoid a gate deadlock, the required Task 14 identity-only refresh is a
Task 13 pre-qrel prerequisite. Do not run development scoring or observe holdout until the refresh
commit exists and E1/E2/E3-A/E3-B validators pass. This amendment does not permit runtime
promotion, threshold tuning before validators, or any semantic artifact drift.

- [x] **Step 2: Run development and freeze the result**

Run the fixed `--development-only --record-development-freeze` command; do not substitute an
unreviewed library entry point. Inspect the full threshold trace. Record:

- whether a safety-eligible threshold exists;
- selected threshold and tie-break evidence;
- qualifying current-runtime grade-2 recovery IDs by target class;
- development safety metrics and all report-only categories;
- dense/current-runtime ordered results and resource measurements.

If no safety-eligible threshold or fewer than two qualifying development recoveries exist, record
the canonical comparison artifact with `holdout_status=not_observed`, no holdout receipt,
`candidate_status=completed`, `e3d_status=not_eligible`, and
`runtime_promotion_status=not_evaluated`; validate it model-free and cache-ready, return exit `0`,
and do not run holdout.

- [x] **Step 3: Lock the development configuration before holdout**

Generate and verify
`benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-development-freeze.json`, binding model
manifest, provider, projection adapter, protocol, qrels, fixtures, source inventory, threshold
algorithm, selected threshold, and development output. Commit this file before the one holdout
observation:

```bash
git add benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-development-freeze.json
git commit -m "test(eval): freeze E3-C development selection"
```

- [x] **Step 4: Run holdout exactly once**

Only if development gates pass, run the one full comparison command with the frozen development
record. The command creates
`benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-holdout-receipt.json` with exclusive-create
semantics and refuses an existing receipt. It binds the development-freeze digest, holdout result
digest, model/projection identity, and public-safe execution identity. Do not tune after viewing
holdout. A failed holdout gate is an honest valid result.

- [x] **Step 5: Record the canonical artifact atomically**

Target:

`benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json`

Then run both validators:

```bash
uv run python -m mke.evaluation.dense_artifact validate \
  --artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --protocol tests/fixtures/retrieval-dense-v1/protocol-lock.json \
  --repository .
uv run python -m mke.evaluation.dense_replay validate \
  --artifact benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json \
  --protocol tests/fixtures/retrieval-dense-v1/protocol-lock.json \
  --model-cache "$HOME/Library/Caches/mke/embedding" \
  --repository .
```

- [x] **Step 6: Commit evidence without changing the result**

```bash
git add tests/fixtures/retrieval-dense-v1/protocol-lock.json \
  benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-development-freeze.json \
  benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-holdout-receipt.json \
  benchmarks/retrieval/qwen3-embedding-0.6b-exact-v1-comparison.json
git commit -m "test(eval): record E3-C dense comparison"
```

## Task 14: Refresh Only Permitted Historical Identities

Task 14 remains PR 2-only. It handles identities invalidated by final E3-C comparison source
changes after PR 1 is merged. It must not repeat, overwrite, or weaken the PR 1 Task 6A semantic
proof, and it must independently explain every new PR 2 invalidation path.

2026-06-29 execution amendment: the necessary identity-only refresh was moved before Task 13
development scoring because Task 13 requires all historical validators to pass before qrels are
scored. The refresh is limited to actual PR 2 invalidations: E1, E2, and E3-A source/scope identity
metadata. E3-B validated before refresh and must remain byte-identical unless a later validator
proves it is invalid. After this pre-qrel refresh is committed, do not repeat, overwrite, or weaken
the semantic-preservation proof in a later Task 14 step.

**Files:**

- Modify only if required by validated source identity changes:
  `benchmarks/retrieval/retrieval-eval-v1-baseline.json`
- Modify only if required:
  `benchmarks/retrieval/numeric-grouping-v1-comparison.json`
- Modify only if required:
  `benchmarks/retrieval/retrieval-chinese-v1-baseline.json`
- Modify only if required:
  `benchmarks/retrieval/cjk-trigram-overlap-v1-comparison.json`
- Modify: `tests/evaluation/test_artifact_refresh.py`

- [x] **Step 1: Identify actual invalidated source inventories**

Run every validator before refreshing. Do not assume a new file invalidates an artifact. For each
failing source/scope identity, show the exact changed path and explain why it is within the
artifact’s declared source boundary.

- [x] **Step 2: Use the supported refresh workflow**

Refresh identity metadata only. Compare normalized before/after observations, metrics, gates, and
verdicts byte-for-byte or structurally. Any semantic delta is a stop condition.

- [x] **Step 3: Verify all artifacts and commit separately**

```bash
uv run pytest tests/evaluation/test_artifact_refresh.py -q
# Run all E1/E2/E3-A/E3-B/E3-C validators here.
git diff -- benchmarks/retrieval
git add benchmarks/retrieval tests/evaluation/test_artifact_refresh.py
git commit -m "test(eval): refresh dense-bound artifact identities"
```

If no historical artifact requires refresh, do not create this commit.

## Task 15: Document The Result And Its Limits

**Files:**

- Create: `docs/how-to/evaluate-dense-retrieval.md`
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/reference/cli.md`
- Modify: `docs/explanation/architecture.md`
- Modify: `docs/superpowers/plans/2026-06-28-local-dense-retrieval-candidate-implementation.md`
- Create:
  `docs/superpowers/reviews/2026-06-28-local-dense-retrieval-candidate-review.md`
- Create/modify documentation tests under `tests/evaluation/`

- [x] **Step 1: Write RED documentation tests**

Require docs to state:

- actual candidate/model/revision/adapter and measured result;
- exact prepare/doctor/eval/validate/replay commands;
- exact source checkout, `wheel[embedding]`, and offline wheelhouse install commands, clearly
  separating package-index network from model-download network;
- development threshold and one-holdout protocol;
- all four comparison arms and E3-D verdict;
- local-first canonical reference and future API adapter boundary;
- comparison-only status and unchanged runtime Search/Ask/MCP behavior;
- actual resource measurements and supported platforms;
- candidate-specific negative-result scope, threshold sensitivity, separate partition projections,
  and the durable development-freeze/holdout-receipt sequence;
- small public corpus, non-blind holdout, Chinese scope, and Japanese/Korean/short-term limits;
- no claim of production quality, hybrid/RRF/reranker behavior, or statistical significance.
- valid-negative exit semantics and a JSON automation example that checks `e3d_status`;
- failed-candidate cleanup: optional packages follow the package manager's uninstall flow, cache
  deletion is a documented manual operator action, and MKE never deletes model caches itself;
- a new model revision or prompt requires a new candidate ID/revision and cannot overwrite this
  candidate's artifact.

- [x] **Step 2: Update docs from actual evidence**

Do not prewrite a positive outcome. If E3-C is negative, document the negative result and why E3-D
remains ineligible. Do not add an ADR because no runtime behavior is promoted.

- [ ] **Step 3: Run document-release audit and commit**

Use `gstack-document-release` to check Diataxis coverage and diagram drift. Keep raw tool artifacts
outside the repository.

```bash
uv run pytest tests/evaluation -q
git diff --check
git add README.md docs tests/evaluation
git commit -m "docs(eval): document E3-C dense evidence"
```

## Task 16: Final Verification And Authoritative Review Handoff

- [ ] **Step 1: Run the complete suite**

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
git diff --check origin/main...HEAD
```

- [ ] **Step 2: Run all canonical evaluations and validators**

Run E1, E2, E3-A, E3-B, and E3-C. Validate every artifact. Confirm E1/E2/E3-A/E3-B normalized
semantic equality to Task 0. Run E3-C model-free validation and cache-ready replay.

- [ ] **Step 3: Run installed-wheel proofs**

In isolated Python 3.12 and 3.13 environments, install the built `wheel[embedding]` offline from
pre-populated package/model caches, run from external cwd with hostile environment variables and
network disabled, and prove:

- installed `mke` and interpreter identity are outside the repository;
- doctor is cache-only ready;
- E3-C comparison reproduces the canonical observations;
- model-free validator and cache-ready replay pass;
- core wheel without the extra still imports and retains current runtime behavior.

- [ ] **Step 4: Inspect the final diff and repository boundary**

```bash
git status --short --branch
git diff --stat origin/main...HEAD
git diff --name-status origin/main...HEAD
git grep -n -E '\.gstack|token|api[_-]?key' \
  -- README.md docs src tests scripts benchmarks pyproject.toml .github || true
```

Verify no model weights, cache files, virtualenvs, raw GStack artifacts, private paths, credentials,
or unrelated runtime changes are present.

- [ ] **Step 5: Leave a clean local branch and hand off**

Report exact base/HEAD/diff, commits, candidate and E3-D verdicts, threshold, metrics,
complementarity recovery IDs, model/projection/artifact identities, resource data, Python proofs,
all verification, and remaining risks. Do not push or create a PR.

The planning window runs one authoritative `gstack-review` against the design, this plan, actual
diff, artifact, and command evidence. Confirmed findings return to the execution window through
`superpowers:receiving-code-review`. After targeted re-review is clean and the user authorizes,
push and create a Ready PR. Merge/cleanup and a docs-only post-merge closeout are separate
authorized actions.

## Final Acceptance Checklist

- [x] PR 1 merged before PR 2 starts.
- [ ] Exact Qwen model/revision and installed dependency graph are frozen.
- [ ] Only prepare can network; every operational/evaluation path is cache-only.
- [ ] Python 3.12/3.13 installed-wheel compatibility and replay pass.
- [ ] No frozen Evidence truncates; embeddings and ranks satisfy the determinism contract.
- [ ] sqlite-vec passes exact-reference equivalence, or its rejection and project reference
  fallback are explicitly recorded before qrel scoring.
- [ ] Development selects one threshold from the full frozen trace.
- [ ] Threshold plateau and development leave-one-query-out sensitivity are recorded without
  changing the selection rule.
- [ ] Development and holdout use separate snapshot/projection inventories.
- [ ] Cross-run identities use stable document locators and text digests, not random runtime IDs.
- [ ] A committed development-freeze file precedes one exclusive-create holdout receipt.
- [ ] Model-free validator independently recomputes structure, metrics, gates, and verdicts from
  recorded observations without claiming to authenticate coordinated observation replacement.
- [ ] Cache-ready replay independently regenerates embeddings and exact-KNN results.
- [ ] E1/E2/E3-A/E3-B semantics, qrels, fixtures, and runtime default remain unchanged.
- [ ] E3-C records an honest positive or negative candidate-specific result, derives `e3d_status`
  from gates, and keeps runtime promotion not evaluated.
- [ ] Search, Ask, CLI runtime, MCP, and normal SQLite domain truth are unchanged.
- [ ] Documentation describes the local reference boundary and actual limitations.
- [ ] Documentation separates install-time network, model prepare network, cache-only operation,
  manual uninstall/cache cleanup, and valid-negative automation semantics.
- [ ] The final branch is clean and passes authoritative pre-PR review.

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---:|---|---|---|---|---|---|
| 1 | CEO | Treat any negative as specific to `qwen3-embedding-0.6b-exact-v1` | Mechanical | Completeness | One model cannot reject dense retrieval as a class. | Universal dense verdict |
| 2 | CEO | Add a development-only residual-miss audit before scoring | Mechanical | Explicit over clever | Query category is not causal evidence that page-level dense similarity fits the miss. | Infer cause from category |
| 3 | CEO | Define `e3d_status` as experiment eligibility only | Mechanical | Explicit over clever | E3-C does not run fusion or evaluate runtime promotion. | Treat eligibility as RRF proof |
| 4 | CEO | Record threshold plateaus and leave-one-query-out sensitivity | Mechanical | Completeness | A 101-point grid on a small development set needs visible stability evidence. | Report only selected threshold |
| 5 | Eng | Split provider-neutral DTOs from `LocalEmbeddingRuntime` lifecycle details | Mechanical | DRY | Future local/API adapters can share data contracts without inheriting tokenizer/cache methods. | Qwen-specific public port |
| 6 | Eng | Canonicalize by document locator plus text digest | Mechanical | Explicit over clever | Runtime UUIDs change across fresh ingests and cannot anchor replay. | Canonical runtime Evidence UUID |
| 7 | Eng | Use separate development and holdout snapshots/projections | Mechanical | Completeness | Combined scoring leaks holdout corpus behavior into development. | Shared 70-row evaluation projection |
| 8 | Eng | Require committed development freeze and exclusive holdout receipt | Mechanical | Completeness | Exactly-once observation needs durable state, not operator memory. | Command-discipline-only holdout |
| 9 | Eng | Restrict cache symlinks and retrieve full partition distances before truncation | Mechanical | Completeness | Valid HF blobs remain usable while link escapes and rounded cutoff ties fail closed. | Blanket symlink ban or SQL `LIMIT 10` |
| 10 | Eng | Separate model-free derivation validation from cache-ready replay | Mechanical | Explicit over clever | Only replay can authenticate coordinated replacement of observations. | Overclaim model-free oracle |
| 11 | DX | Use explicit development/freeze and holdout/receipt command forms | Mechanical | Explicit over clever | The CLI itself prevents phase mixing and accidental holdout reruns. | One overloaded comparison command |
| 12 | CEO | Retain compatibility-first two-PR delivery | Taste | Bias toward action | Package/model feasibility is isolated before candidate qrel scoring. | Development-qrel-first PR |
| 13 | CEO/Eng | Retain the bounded sqlite-vec compatibility spike | Taste | Completeness | It tests a likely SQLite adapter while exact cosine remains the oracle and fallback. | Defer sqlite-vec entirely |
| 14 | CEO | Retain one immutable model rather than a development bakeoff | Taste | Explicit over clever | The hypothesis stays bounded and holdout contamination surface stays small. | Multi-model bakeoff |
| 15 | DX | Separate install network, explicit model prepare, cache-only operation, and manual cleanup | Mechanical | Completeness | These are different trust and recovery boundaries for operators. | Call the whole workflow offline |
| 16 | Design | Skip graphical design review | Mechanical | Pragmatic | E3-C adds CLI/evaluation behavior and no graphical UI. | Invent UI scope |

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|---|---|---|---:|---|---|
| CEO Review | `/plan-ceo-review` | Scope and strategy | 1 | CLEAR | 8 concerns dispositioned; comparison-only scope retained |
| Codex Review | `/codex review` | Independent second opinion | 1 | DEGRADED | Codex-only outside voice; no cross-model consensus claimed |
| Eng Review | `/plan-eng-review` | Architecture and tests | 2 | CLEAR | Original 9 findings resolved; resource amendment targeted review found 0 new issues |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | SKIPPED | No graphical UI scope |
| DX Review | `/plan-devex-review` | Developer experience gaps | 1 | CLEAR | Install, CLI, error, documentation, and cleanup contract reviewed |

- **VERDICT:** CEO, engineering, and DX reviews are clear. The 2026-06-29 amendment supersedes only
  the prepare transport and PR 1 resource-measurement contracts. PR 1 has merged to `main`; PR 2
  may start from latest `main` after separate authorization and must not stack on PR #41 history.

NO UNRESOLVED DECISIONS
