# v0.1.5 Release Closeout Implementation Plan

Status: approved design landed and actual spec diff accepted; implementation plan pending approval,
mechanical landing, and actual plan-diff review.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` as the primary
> controller, `superpowers:test-driven-development` for version and release-presentation changes,
> `superpowers:systematic-debugging` for unexpected failures, and
> `superpowers:verification-before-completion` before every completion claim. Do not run competing
> full-branch controllers.

**Goal:** Publish the already-merged local-first Agent-consumption contract as `v0.1.5`, with MCP
selection completeness, bounded continuation, exact active-Evidence reconstruction, and
deterministic equal-score order accurately presented and proved, without changing product runtime
behavior or importing unfinished retrieval-coverage comparison evidence.

**Architecture:** Treat the release as an ordered identity-and-evidence closure around unchanged
runtime code: land exact `0.1.5` identity and public presentation, rehearse the primary Agent path,
obtain actual-diff review, seal one candidate tree, run the complete branch proof matrix, publish a
Draft PR, require reviewed-tree/merge-tree equality, rerun the complete proof matrix from fresh
exact main, then separately tag, publish a zero-asset GitHub Release, verify the Git-less public
archive, and record immutable public facts in a docs-only closeout.

**Tech Stack:** Python 3.12 and 3.13, uv, Hatchling, pytest, Ruff, Pyright, SQLite/FTS5, stdio MCP,
Markdown, Git, GitHub Actions, and GitHub Releases.

## Provenance And Starting Authority

- Planning baseline: `33106ec2cfeabf6c1c448fad57fb2489e3712543`.
- Planning tree: `69b8f252a009f714006aa4907aa5254ec966a0ae`.
- Reviewed spec landing commit: `6d9e3c120bcde6cf3a54f54d33af30466ceeac9a`.
- Reviewed spec landing tree: `8edceef56d8162d708b2ce9960174d4fdef5d144`.
- Approved design:
  `docs/superpowers/specs/2026-07-28-v0-1-5-release-closeout-design.md`.
- Approved design SHA-256:
  `260b178bcac6255d7f3a7ad1a29272bca45234e1a5599939609147ff320da48e`.
- Plan destination:
  `docs/superpowers/plans/2026-07-28-v0-1-5-release-closeout-implementation.md`.
- Current package, module, root-lock, installed-smoke, and release-presentation identity:
  `0.1.4`.
- Target package and tag identity: `0.1.5` / `v0.1.5`.
- Latest public release at design approval: `v0.1.4`, public, non-draft, non-prerelease, zero
  attached assets.
- The five canonical retrieval-order artifacts and fixed-profile query-plan fixture are retained
  evidence. They are inputs to pure validation only; they are never refreshed by this release.
- The unfinished retrieval-coverage comparison is a separate, protected evidence owner. Its
  branches, worktrees, fixtures, observations, receipts, artifacts, and results are outside this
  plan.

The implementation handoff must supply the exact reviewed plan-landing commit. Call it
`REVIEWED_PLAN_HEAD`. Implementation must not start if that commit has not passed independent
actual-diff review.

## Global Constraints

- Release closeout changes version identity, release presentation, documentation routing, tests,
  and publication evidence only.
- Do not change retrieval, ranking, tokenization, Evidence granularity, MCP behavior, tool schemas,
  public DTOs, cursor behavior, Publication authority, SQLite schema, ingestion, Search, Ask, CLI
  semantics, or product proof semantics.
- Do not introduce GraphRAG, dense/RRF/reranker runtime, OCR runtime, an Agent loop, HTTP/SaaS, a
  provider, a dependency, PyPI publication, deployment, or uploaded Release assets.
- Do not claim relevance, recall, precision, latency, throughput, segmentation quality,
  contextual-retrieval quality, production adoption, user count, or business impact.
- Do not access, read, hash, copy, normalize, repair, remove, or use any unfinished
  retrieval-coverage comparison input or retained evidence.
- Do not run `retrieval_order_installed_proof.py` for `v0.1.5`.
- Do not record canonical retrieval-order evidence, rerun development/holdout observation, refresh
  the frozen numeric protocol, or convert the strict-live numeric expected negative into success.
- Keep the five canonical retrieval-order files, historical evaluation artifacts, current MCP
  fixture, frozen v0.1.4 tool fixture, fixed query-plan fixture, and `docs/releases/v0.1.4.md`
  byte-identical.
- `uv.lock` may change only at the root editable package version from `0.1.4` to `0.1.5`. Any
  dependency, source, marker, hash, resolution, or transitive-package drift is terminal.
- Use existing Python 3.12 and 3.13 interpreters. Do not download interpreters or packages during
  offline proof.
- “Offline” means cache-warmed `UV_OFFLINE=1` execution. It does not mean cold installation or
  air-gapped package acquisition.
- Every proof controller binds its own exact wheel across its own interpreter cells. Different
  controllers may build different wheels from the same sealed source; cross-controller byte
  equality is not required or claimed.
- All wheels, constraints, receipts, temporary compatibility artifacts, logs, and proof ledgers
  remain in task-owned physical paths outside the repository.
- Retain task-owned proof outputs through release closeout. Deletion is a later, exact-path,
  separately approved cleanup action.
- Any tracked byte, index, HEAD, tree, or source-state drift after candidate sealing invalidates
  all candidate wheels, receipts, logs, rehearsal results, and proof results. Repair requires a
  reviewed commit, a fresh seal, and the complete matrix from the beginning.
- Push, Draft PR creation, Ready transition, merge, remote branch deletion, annotated tag,
  GitHub Release creation, post-release docs publication, and cleanup remain separate external
  authorization gates.
- Public files must remain public-neutral. Do not write local absolute paths, private task labels,
  coordination identifiers, raw tracebacks, tokens, secrets, or private proof locations.
- Do not mark checkboxes in this plan during candidate implementation. Execution truth lives in
  the retained private ledger until the post-release docs-only closeout.

## Release State Ownership

| State | Entered only after |
|---|---|
| `PUBLIC_SPEC_LANDED` | reviewed spec commit is exact |
| `IMPLEMENTATION_PLAN_APPROVED` | this complete plan is approved, landed, and actual-diff clean |
| `RELEASE_BRANCH_ACTIVE` | Task 0 live authority and prerequisite checks pass |
| `CANDIDATE_SEALED` | Tasks 1-6 are committed, verified, and independently review-clean |
| `DRAFT_PR` | Task 7 complete matrix passes and push/PR approval is granted |
| `MERGE_APPROVED` | exact-head hosted checks and review are clean and user approves merge |
| `MERGED_NOT_PUBLISHED` | squash merge tree equals the reviewed tree |
| `LOCAL_TAG_READY` | fresh exact-main matrix passes and publication authority is granted |
| `REMOTE_TAG_VISIBLE_RELEASE_ABSENT` | exact annotated tag is visible remotely and Release is absent |
| `RELEASE_VISIBLE_UNVERIFIED` | zero-asset GitHub Release is visible but archive proof is pending |
| `PUBLICATION_VERIFIED` | persisted Release identity and Git-less archive proof pass |
| `RELEASE_CLOSED` | docs-only closeout, retrospective, and approved local cleanup complete |

No task may skip a state or infer a later state from a plan, candidate, branch-only proof, or
unread external response.

## Exact File And Responsibility Map

### Landed authority

- `docs/superpowers/specs/2026-07-28-v0-1-5-release-closeout-design.md`
  (reviewed, immutable after plan landing);
- `docs/superpowers/plans/2026-07-28-v0-1-5-release-closeout-implementation.md`
  (mechanically landed, immutable during implementation).

### Version identity

Modify:

- `pyproject.toml`;
- `src/mke/__init__.py`;
- `uv.lock`;
- `tests/test_version_identity.py`;
- `tests/test_bootstrap.py`;
- `tests/proof/test_mcp_deployment_client.py`;
- `scripts/release_consumer_smoke.py`;
- `tests/scripts/test_release_consumer_smoke.py`.

### Current release presentation

Modify:

- `scripts/release_presentation_audit.py`;
- `tests/scripts/test_release_presentation_audit.py`;
- `tests/evaluation/test_dense_documentation.py`;
- `README.md`;
- `README_CN.md`;
- `CHANGELOG.md`;
- `docs/README.md`;
- `docs/how-to/verify-release.md`;
- `docs/how-to/prepare-local-embeddings.md`;
- `docs/how-to/evaluate-dense-retrieval.md`;
- `docs/how-to/enable-cjk-retrieval.md`;
- `docs/how-to/evaluate-numeric-retrieval.md`;
- `docs/how-to/run-chinese-retrieval-evaluation.md`.

Add:

- `docs/releases/v0.1.5.md`.

### Primary Agent MCP path and troubleshooting

Modify:

- `tests/evaluation/test_mcp_context_completeness_documentation.py`;
- `README.md`;
- `README_CN.md`;
- `docs/README.md`;
- `docs/tutorials/getting-started.md`;
- `docs/how-to/use-mke-mcp.md`;
- `docs/how-to/run-mcp-context-completeness-proof.md`;
- `docs/how-to/verify-release.md`;
- `docs/reference/cli.md`;
- `docs/releases/v0.1.5.md`.

Verification-only by default:

- `tests/interfaces/test_cli_mcp.py`;
- `docs/reference/mcp-contract.md`.

`docs/reference/mcp-contract.md` may be modified only if a focused RED proves that the current
canonical page lacks one of the approved current/upgrade/acquisition boundaries. Existing
completeness, request-envelope, cursor, chunk, digest, active-authority, and ten-tool text is not a
reason to rewrite it.

### Post-release docs-only closeout

After verified publication, and only under separate docs-publication authority:

- `docs/releases/v0.1.5.md`;
- `docs/how-to/verify-release.md`.

No other path is authorized. A required path outside this map is a design-amendment stop, not an
implementation convenience.

## Protected Byte Manifest

Before the first implementation write and after every semantic commit, verify these exact hashes:

```text
0d8761037e9132461a1d6bbf2eac0a39471dfaa38c65acbdc2400a87ff8bffd8  benchmarks/retrieval/retrieval-order-v1-development-freeze.json
8f390ada3632c12527eb75747a2ce21721317fffdd30bd9fc177e8f305dc3203  benchmarks/retrieval/retrieval-order-v1-holdout-receipt.json
104a41a6aa0c719313d508c79d00886a18483bbf3eeeadcdbc8899dd927283c1  benchmarks/retrieval/retrieval-order-v1-artifact.json
df18d9738548fa33af5c7f76dfa26e89a721f1c08a2df0e034a7688c67e81604  benchmarks/retrieval/retrieval-order-v2-compatibility-attempt.json
f9a5883f3ac47652cbd18ef0bb08b61ceb00065955a3db575df0fd41689240ba  benchmarks/retrieval/retrieval-order-v2-compatibility.json
1f6a70a69edb9a3b182e21a9b125a37d81ed4dca869c16d1f5d5b807554ffdc1  tests/fixtures/retrieval-order-v1/fts-query-plan.json
fe3a6ce74d0e037a1a5fa33eba1df941c2130981e100d424f7756b34b2724248  docs/releases/v0.1.4.md
f372f9733c8c352d7610d16412d9f98304dde325dd235ce81e30b4c6253cc3cd  tests/fixtures/consumer-source-pack-v1/mcp-tool-schemas.json
48b3b6c3a8d17af460ceff23ae64e619486f5792eb77b35416841e73a8190561  tests/fixtures/mcp-context-completeness-v1/mcp-tool-schemas.json
```

## Private Proof Ledger Contract

Create one task-owned physical ledger root with:

```bash
LEDGER_ROOT="$(mktemp -d /private/tmp/mke-v015-release.XXXXXX)"
```

Require:

- `/private` and `/private/tmp` are physical non-symlink ancestors;
- the ledger is outside the repository;
- every candidate-output child is absent before its single controller invocation;
- no preexisting file is reused;
- each command records exact argv, start/end monotonic time, exit status, stdout/stderr digest,
  output inventory, and source-seal pre/post state;
- public-safe scalar results may later enter closeout docs, but raw local paths do not;
- the entire ledger is retained through release closeout.

Use this source seal before and after every expensive branch or exact-main lane:

```text
head
tree
branch or detached state
complete porcelain-v1 -z bytes
index tree
expected package version
tracked-file inventory digest
```

The precondition is a clean worktree and index. Any mismatch is terminal and invalidates all
results from that seal.

---

## Task 0: Reconcile Release Authority Before The First Write

**Files:** none.

- [ ] **Step 1: Read repository authority**

Read `AGENTS.md`, the approved design, this implementation plan, current architecture/ADR, release
verification docs, relevant proof controllers, tests, and CI. Do not inspect any protected
comparison worktree.

- [ ] **Step 2: Prove the exact plan ancestry and clean state**

Require:

```bash
test "$(git rev-parse HEAD)" = "$REVIEWED_PLAN_HEAD"
test "$(git rev-list --count 6d9e3c120bcde6cf3a54f54d33af30466ceeac9a..HEAD)" -eq 2
test "$(git diff --name-only 6d9e3c120bcde6cf3a54f54d33af30466ceeac9a..HEAD)" = \
  "docs/superpowers/plans/2026-07-28-v0-1-5-release-closeout-implementation.md"
git diff --quiet
git diff --cached --quiet
test -z "$(git status --porcelain=v1)"
```

Recompute and require the approved design SHA-256. Read the complete landed plan diff and record
its SHA-256.

- [ ] **Step 3: Reconcile public lifecycle state read-only**

Read:

```bash
git ls-remote origin refs/heads/main refs/tags/v0.1.5 'refs/tags/v0.1.5^{}'
gh pr list --state open --json number,title,isDraft,headRefName,baseRefName,url
gh release list --limit 20
gh release view v0.1.4 --json tagName,name,isDraft,isPrerelease,publishedAt,url,assets
git worktree list --porcelain
git branch --all --verbose --no-abbrev
```

Require:

- remote main is still the planning baseline;
- `v0.1.5` tag and Release are absent;
- no open PR owns this release branch;
- the release worktree is clean;
- every other registered worktree is classified by owner using only the worktree inventory;
- no comparison-owned worktree is entered, hashed, normalized, or modified.

If remote main moved, stop for intervening-diff review. Do not rebase or merge automatically.

- [ ] **Step 4: Prove prepared offline execution prerequisites**

Resolve one existing Python 3.12 interpreter and one existing Python 3.13 interpreter. Probe each
with isolated `-I -S -B` commands and require exact minor set `{3.12, 3.13}`. Record resolved
executables and `sys.version_info[:3]` privately.

Prepare the local development environment only from the existing lock/cache:

```bash
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never uv sync --locked --dev
```

A cache miss, interpreter download request, lock rewrite, or dependency resolution drift is a
terminal prerequisite failure.

- [ ] **Step 5: Freeze protected bytes and implementation baseline**

Verify the protected byte manifest. Record:

- `REVIEWED_PLAN_HEAD`;
- its tree;
- exact clean porcelain bytes;
- the allowlisted implementation path set;
- the current non-evaluation `src/mke` inventory and digest.

Do not commit or continue on any mismatch.

---

## Task 1: Lock Exact `0.1.5` Version And Installed-Smoke Identity

**Files:** exact version-identity group.

- [ ] **Step 1: Write the version RED**

Update only the current identity assertions to require:

```python
assert pyproject["project"]["version"] == "0.1.5"
assert mke.__version__ == "0.1.5"
assert installed_metadata_version == "0.1.5"
```

Require the release consumer to accept only:

```text
multimodal_knowledge_engine-0.1.5-py3-none-any.whl
module version 0.1.5
installed metadata version 0.1.5
```

Run:

```bash
UV_OFFLINE=1 uv run --frozen --no-sync pytest -q \
  tests/test_version_identity.py \
  tests/test_bootstrap.py \
  tests/proof/test_mcp_deployment_client.py::test_installed_mcp_module_help_has_no_outer_stderr \
  tests/scripts/test_release_consumer_smoke.py
```

Expected RED: only stale `0.1.4` package/module/metadata/wheel assertions. Any behavior, schema,
network, fixture, or MCP failure is not the authorized RED and must stop the task.

- [ ] **Step 2: Apply the minimal identity change**

Set `0.1.5` only in:

- `pyproject.toml`;
- `src/mke/__init__.py`;
- the current release identity in `scripts/release_consumer_smoke.py`.

Refresh the root lock entry offline:

```bash
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never uv lock --offline
```

Do not global-replace `0.1.4`.

- [ ] **Step 3: Prove root-lock-only semantic equality**

Parse the parent and working `uv.lock` files with `tomllib`. Require:

1. the root package name remains `multimodal-knowledge-engine`;
2. only its `version` changes from `0.1.4` to `0.1.5`;
3. after normalizing that one field back to `0.1.4`, the complete parsed lock objects are equal;
4. no package count, dependency edge, marker, source, hash, extra, or resolution changes.

Also require the raw diff contains no other `uv.lock` hunk.

- [ ] **Step 4: Run GREEN and adjacent identity checks**

Refresh the editable package metadata from the exact new lock without network:

```bash
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never uv sync --locked --dev
```

Run the RED command unchanged, then:

```bash
UV_OFFLINE=1 uv run --frozen --no-sync pytest -q \
  tests/packaging \
  tests/proof/test_mcp_deployment_client.py \
  tests/scripts/test_release_consumer_smoke.py
UV_OFFLINE=1 uv run --frozen --no-sync ruff check \
  src/mke/__init__.py \
  tests/test_version_identity.py \
  tests/test_bootstrap.py \
  tests/proof/test_mcp_deployment_client.py \
  scripts/release_consumer_smoke.py \
  tests/scripts/test_release_consumer_smoke.py
UV_OFFLINE=1 uv run --frozen --no-sync pyright
```

Reverify protected bytes and `git diff --check`.

- [ ] **Step 5: Commit the atomic identity change**

Stage exactly the eight version-identity paths. Inspect the complete cached diff and commit:

```bash
git commit -m "chore(release): set v0.1.5 identity"
```

Require a clean worktree afterward. Do not begin presentation work if lock authority is not exact.

---

## Task 2: Define The `v0.1.5` Presentation Contract With Targeted RED

**Files:** presentation audit tests and current-wheel documentation test only.

Tasks 2 and 3 are one atomic RED -> implementation -> GREEN lane. Do not commit the RED-only
intermediate state.

- [ ] **Step 1: Add current-versus-historical release RED tests**

In `tests/scripts/test_release_presentation_audit.py`, require:

- `EXPECTED_VERSION == "0.1.5"`;
- `docs/releases/v0.1.5.md` is current and `docs/releases/v0.1.4.md` is immutable historical
  authority;
- `_audit_v014_contract` remains strict and a separate `_audit_v015_contract` exists;
- the current release-facing inventory points to `v0.1.5`;
- current wheel commands name exactly
  `multimodal_knowledge_engine-0.1.5-py3-none-any.whl`;
- README EN, README CN, and `docs/README.md` each contain exactly one H1;
- current `v0.1.5` Agent-consumption value precedes historical capability records;
- the release note contains Try it, Upgrade, acquisition, proof/evidence, limitations, and no
  database/data/schema migration;
- an absent `Publication verification` section is valid before publication, but once that heading
  exists the audit requires its complete immutable field set and rejects placeholders or partial
  facts;
- GitHub Release is source-only with zero attached assets and PyPI is absent;
- “offline” is always qualified as prepared cache-warmed execution;
- release presentation does not claim exhaustive search, retrieval quality, performance,
  comparison results, runtime promotion, deployment, adoption, or business value;
- historical `v0.1.4` direct-audio facts and exact wheel command remain unchanged.

Add independent negative tests for affirmative or wrapped claims about:

- relevance, recall, precision, latency, throughput, or faster Agent retrieval;
- segmentation or contextual-retrieval improvement;
- exhaustive corpus search or total-match counting;
- GraphRAG, dense/RRF/reranker runtime, OCR runtime, Agent loop, HTTP/SaaS, provider, PyPI,
  deployment, adoption, or uploaded assets;
- cold-cache or empty-machine offline installation.

- [ ] **Step 2: Update only the current dense-wheel assertion**

In `tests/evaluation/test_dense_documentation.py`, change only the current release wheel literal
or assertion from `0.1.4` to `0.1.5`. Do not alter direct-audio history, dense comparison semantics,
or promotion boundaries.

- [ ] **Step 3: Run one authoritative presentation RED**

Run:

```bash
UV_OFFLINE=1 uv run --frozen --no-sync pytest -q \
  tests/scripts/test_release_presentation_audit.py \
  tests/evaluation/test_dense_documentation.py
```

Expected RED categories:

- missing `v0.1.5` current release note and inventory;
- stale `0.1.4` current identity/wheel presentation;
- duplicate H1/current story ordering;
- missing exact `v0.1.5` evidence and non-claim contract.

Existing v0.1.4 historical controls must pass. If a historical control fails, stop before any
production or documentation edit.

---

## Task 3: Implement The Current `v0.1.5` Release Presentation

**Files:** presentation implementation and current release documentation group.

- [ ] **Step 1: Extend the audit without weakening historical rules**

In `scripts/release_presentation_audit.py`:

- set `EXPECTED_VERSION = "0.1.5"`;
- make `docs/releases/v0.1.5.md` current;
- move `docs/releases/v0.1.4.md` into immutable historical inventory;
- retain `_audit_v013_contract` and `_audit_v014_contract`;
- add a separate strict `_audit_v015_contract`;
- require exactly one H1 in each entry point;
- require current release content before historical sections;
- update exact current wheel selectors to `0.1.5`;
- preserve result schema `{"status", "violations"}` and all public function signatures;
- add a conditional post-publication record check: the section may be absent before publication,
  but if present it must contain the complete exact public fact inventory and no placeholder;
- preserve comparison, direct-audio, compiled-export, downstream, private-marker, and claim
  boundaries;
- update the CLI description to audit `v0.1.5`.

The new v0.1.5 contract must require all of:

```text
search_library_v2
complete
more_available
capped
read_evidence_v1
evidence_text_sha256
active Publication
ten tools
deterministic equal-score
Source bytes
revision 2
legacy
v1
no relevance improvement claim
no runtime promotion
source archive or checkout
zero assets
no PyPI
cache-warmed
```

Do not replace deterministic string/structure checks with a generalized natural-language
classifier.

- [ ] **Step 2: Write the public-neutral release surfaces**

Update:

- `README.md`;
- `README_CN.md`;
- `CHANGELOG.md`;
- `docs/README.md`;
- `docs/how-to/verify-release.md`;
- the five current-wheel how-to files.

Add `docs/releases/v0.1.5.md`.

Required release note structure:

```text
# v0.1.5
## What changed
## Try it
## Upgrade from v0.1.4
## Verification
## Boundaries and non-claims
```

Required facts:

- package/module identity is `0.1.5`;
- primary path is local stdio MCP;
- `search_library_v2` exposes bounded selection completeness;
- `read_evidence_v1` reconstructs exact active Evidence and final digest;
- equal-score FTS and CJK order uses documented Source-byte-bound semantic keys;
- valid legacy/v1 bounded calls remain compatible;
- exact `tools/list` consumers update eight tools to ten;
- old cursors are restarted with a new initial call;
- database/data/schema migration is none;
- acquisition is a source archive or checkout; GitHub Release has zero assets; PyPI is absent;
- offline proof assumes prepared interpreters and warm lock-derived caches;
- the already-merged GitHub Actions pin update is maintenance only, not a product/runtime
  capability;
- retrieval quality, performance, segmentation, contextual retrieval, and comparison promotion are
  explicit non-claims.

Keep v0.1.4 history byte-identical.

- [ ] **Step 3: Make current entry points singular**

For each of `README.md`, `README_CN.md`, and `docs/README.md`:

- preserve the language switch;
- leave exactly one H1;
- put the current v0.1.5 Agent-consumption story before historical capabilities;
- preserve architecture, authority, comparison-only, direct-audio, export, and installation
  boundaries;
- do not duplicate long reference content that belongs in the MCP contract or release note.

- [ ] **Step 4: Update exact current-wheel docs mechanically**

In exactly:

- `docs/how-to/prepare-local-embeddings.md`;
- `docs/how-to/evaluate-dense-retrieval.md`;
- `docs/how-to/enable-cjk-retrieval.md`;
- `docs/how-to/evaluate-numeric-retrieval.md`;
- `docs/how-to/run-chinese-retrieval-evaluation.md`;

change only the current wheel reference from `0.1.4` to `0.1.5`. Do not change comparison
protocols, metrics, candidate status, or runtime promotion wording.

- [ ] **Step 5: Run the unchanged GREEN and live audit**

Run the exact Task 2 command unchanged, then:

```bash
UV_OFFLINE=1 uv run --frozen --no-sync python \
  scripts/release_presentation_audit.py --root . --json
UV_OFFLINE=1 uv run --frozen --no-sync pytest -q \
  tests/scripts/test_release_presentation_audit.py \
  tests/evaluation/test_dense_documentation.py \
  tests/evaluation/test_mcp_context_completeness_documentation.py
UV_OFFLINE=1 uv run --frozen --no-sync ruff check \
  scripts/release_presentation_audit.py \
  tests/scripts/test_release_presentation_audit.py \
  tests/evaluation/test_dense_documentation.py
UV_OFFLINE=1 uv run --frozen --no-sync pyright
```

Require `status=ok`, zero violations, historical v0.1.4 controls green, protected hashes exact,
and no private marker.

- [ ] **Step 6: Commit the atomic presentation change**

Stage only Task 2/3 paths. Read the complete cached diff and commit:

```bash
git commit -m "docs(release): prepare v0.1.5 presentation"
```

Require a clean worktree. Do not treat documentation GREEN as candidate proof.

---

## Task 4: Promote The Completeness-Aware Agent MCP Path

**Files:** primary Agent MCP path and troubleshooting group.

- [ ] **Step 1: Write focused MCP documentation RED tests**

Extend `tests/evaluation/test_mcp_context_completeness_documentation.py` to require:

1. exact ten-tool inventory, in this order:
   - `list_libraries`;
   - `ingest_file`;
   - `get_run`;
   - `search_library`;
   - `ask_library`;
   - `list_libraries_v1`;
   - `search_library_v1`;
   - `ask_library_v1`;
   - `search_library_v2`;
   - `read_evidence_v1`;
2. exact global CLI option order `mke --db <path> mcp ...`;
3. one primary three-step Agent flow:
   - start local stdio MCP and issue native `{"request": ...}` search;
   - branch on `complete|more_available|capped`, following only opaque `next_cursor`;
   - continue `read_evidence_v1`, concatenate by `offset_bytes`, and verify
     `evidence_text_sha256`;
4. explicit separation of selection completeness from excerpt completeness;
5. `capped` is terminal but not exhaustive;
6. Evidence text is untrusted content, not instructions;
7. active-only Publication authority and Source-byte identity;
8. exact upgrade rules: legacy/v1 compatibility, eight-to-ten exact inventory update, cursor
   restart, no database/data/schema migration;
9. source archive/checkout acquisition, zero Release assets, no PyPI, cache-warmed offline proof;
10. stable proof code-to-action troubleshooting without relabeling proof codes as product
    `problem/cause/next_step`.

The tests must cover README EN/CN, docs index, tutorial, MCP how-to, proof how-to, CLI reference,
verify-release guide, and v0.1.5 release note.

- [ ] **Step 2: Freeze the proof-controller code inventory**

Require the troubleshooting table to cover the current public stable codes from:

- `release_consumer_smoke.py`;
- `mcp_context_completeness_proof.py`;
- `consumer_source_pack_proof.py`;
- `compiled_library_export_proof.py`.

The required exact code inventory is:

```text
candidate_artifact_invalid
cleanup_failed
cli_ask_failed
cli_ingest_failed
cli_search_failed
command_could_not_start
command_failed
command_output_exceeded
command_timed_out
consumer_failed
consumer_payload_invalid
consumer_proof_failed
consumer_schema_invalid
consumer_smoke_failed
demo_failed
environment_create_failed
external_isolation_failed
fixture_setup_failed
fixture_unavailable
install_failed
installed_identity_failed
locked_constraints_mismatch
locked_constraints_unavailable
manifest_locator_mismatch
manifest_mapping_ambiguous
manifest_mapping_missing
mcp_contract_failed
mcp_startup_timeout
mcp_tool_timeout
mcp_transport_failed
observation_state_mismatch
producer_failed
proof_failed
python_interpreter_unavailable
retrieval_order_publication_durability_unconfirmed
retrieval_order_publication_failed_before_visibility
retrieval_order_source_pack_already_started
retrieval_order_source_pack_attempt_terminal
retrieval_order_source_pack_claim_invalid
runtime_root_inside_repository
server_exit_nonzero
source_pack_identity_mismatch
source_pack_manifest_invalid
venv_failed
wheel_build_failed
wheel_invalid
wheel_unavailable
```

Multiple codes may share one problem/cause/action row only when every code remains listed
verbatim. The table is documentation; proof JSON remains exactly `{"status","code"}` on failure.
The `retrieval_order_source_pack_*` and `retrieval_order_publication_*` rows must be labeled
historical maintenance/attempt-claim recovery only; the v0.1.5 commands do not pass
`--attempt-claim`.

- [ ] **Step 3: Run targeted RED**

Run:

```bash
UV_OFFLINE=1 uv run --frozen --no-sync pytest -q \
  tests/evaluation/test_mcp_context_completeness_documentation.py \
  tests/interfaces/test_cli_mcp.py
```

Expected RED: stale entry-point routing, missing primary three-step flow, stale five-tool CLI text,
or missing proof-code action table. Existing runtime/CLI ordering tests must pass.

- [ ] **Step 4: Update the minimum documentation set**

Update:

- `README.md`;
- `README_CN.md`;
- `docs/README.md`;
- `docs/tutorials/getting-started.md`;
- `docs/how-to/use-mke-mcp.md`;
- `docs/how-to/run-mcp-context-completeness-proof.md`;
- `docs/how-to/verify-release.md`;
- `docs/reference/cli.md`;
- `docs/releases/v0.1.5.md`.

Use the real request envelopes:

```json
{"request":{"query":"publication authority","limit":10}}
```

```json
{"request":{"cursor":"<opaque-token>"}}
```

```json
{"request":{"evidence_id":"ev_<opaque-id>","max_bytes":16384}}
```

```json
{"request":{"cursor":"<opaque-token>"}}
```

Do not invent an HTTP transport, wrapper schema, query total, summary response, or generated
answer.

In `docs/reference/cli.md`, replace the stale five-tool statement with the exact ten-tool
inventory and correct command shape:

```bash
mke --db <library.sqlite3> mcp --allowed-root <directory>
```

Keep legacy/v1 examples under compatibility rather than as the primary Agent path.

- [ ] **Step 5: Decide the conditional MCP reference path**

Run the focused tests against the current `docs/reference/mcp-contract.md`.

- If it already satisfies current, upgrade, and acquisition boundaries, do not modify it.
- If exactly one approved boundary remains RED, make the smallest documentation-only edit and add
  a focused assertion.
- If runtime/tool schema/behavior would need to change, stop.

- [ ] **Step 6: Run GREEN, command-shape checks, and docs audit**

Run the exact Task 4 RED command unchanged, then:

```bash
UV_OFFLINE=1 uv run --frozen --no-sync mke --help >/dev/null
UV_OFFLINE=1 uv run --frozen --no-sync mke \
  --db /private/tmp/mke-v015-help.sqlite3 mcp --help >/dev/null
UV_OFFLINE=1 uv run --frozen --no-sync python \
  scripts/release_presentation_audit.py --root . --json
UV_OFFLINE=1 uv run --frozen --no-sync pytest -q \
  tests/evaluation/test_mcp_context_completeness_documentation.py \
  tests/interfaces/test_cli_mcp.py \
  tests/scripts/test_release_presentation_audit.py
UV_OFFLINE=1 uv run --frozen --no-sync ruff check \
  tests/evaluation/test_mcp_context_completeness_documentation.py
UV_OFFLINE=1 uv run --frozen --no-sync pyright
```

Also run a deterministic shell-block syntax checker over every new or changed `bash` block.
Commands may be parsed and help-checked; do not execute publication or proof commands in this
step.

- [ ] **Step 7: Commit the Agent-facing documentation**

Stage only the Task 4 paths actually needed. Read the complete cached diff and commit:

```bash
git commit -m "docs(mcp): promote completeness-aware agent flow"
```

Require a clean worktree, exact protected hashes, and no non-evaluation `src/mke` diff except the
Task 1 version literal.

---

## Task 5: Rehearse The Evaluator Path Without A Public Performance Claim

**Files:** no tracked files.

- [ ] **Step 1: Create a private rehearsal ledger**

Create an absent child under `LEDGER_ROOT`. Record:

```json
{
  "schema_version": "mke.release_evaluator_rehearsal.v1",
  "status": "pending",
  "candidate_head": null,
  "candidate_tree": null,
  "preconditions": {
    "source_acquired": true,
    "uv_ready": true,
    "python_312_ready": true,
    "python_313_ready": true,
    "lock_cache_warm": true
  },
  "user_visible_steps": 3,
  "selection_statuses": ["complete", "more_available", "capped"],
  "first_verified_value": "not_observed",
  "elapsed_ms": 0,
  "cold_acquisition": "not_measured",
  "cold_cache": "not_measured",
  "public_performance_claim": false
}
```

The actual receipt may include only these public-safe scalar fields. It must not contain document
text, cursor bytes, Evidence IDs, local paths, or host identifiers.

- [ ] **Step 2: Export exact lock constraints**

Write constraints outside the repository:

```bash
uv export --locked --no-dev --no-emit-project --no-header \
  --output-file "$LEDGER_ROOT/rehearsal-constraints.txt"
```

Verify the exact output against a second stdout export before use.

- [ ] **Step 3: Run one timed completeness proof rehearsal**

Create one fresh absent physical candidate-output path and invoke exactly once:

```bash
UV_OFFLINE=1 uv run python scripts/mcp_context_completeness_proof.py \
  --python "$PYTHON312" \
  --python "$PYTHON313" \
  --constraints "$LEDGER_ROOT/rehearsal-constraints.txt" \
  --candidate-output "$LEDGER_ROOT/rehearsal-candidate" \
  --json
```

The external controller records monotonic start/end time, exact argv, source seal, exit status,
result digest, one wheel identity, and output inventory.

Require:

- final `candidate_head` and `candidate_tree` are exact 40-hex values from the rehearsal source
  seal;
- `status == "passed"`;
- `python_versions == ["3.12", "3.13"]`;
- `tool_count == 10`;
- `search_continuation == "passed"`;
- `exact_read == "passed"`;
- `legacy_compatibility == "passed"`;
- `network_access == "not_used"`;
- `dependency_constraints == "uv_lock_exact"`.

Set:

```text
status = passed
first_verified_value = exact_evidence_sha256_matched
elapsed_ms = observed monotonic elapsed
```

`first_verified_value` is derived only from the unchanged consumer's successful exact-read digest
check. The public proof does not expose Evidence content, cursor bytes, or a chunk count, so the
rehearsal receipt must not invent those fields.

The elapsed acceptance target is at most five minutes from the declared warm preconditions. If it
exceeds five minutes, repair the public evaluator path or document the target miss before candidate
seal; do not publish a performance claim.

- [ ] **Step 4: Prove no source change and retain the receipt**

Recheck the source seal and `git status`. Retain the rehearsal ledger. Do not reuse its wheel or
result in Task 7.

---

## Task 6: Complete Local Verification And Obtain Actual-Diff Review

**Files:** no new path by default; review fixes must remain inside the exact implementation map.

- [ ] **Step 1: Run focused and adjacent implementation gates**

Run:

```bash
UV_OFFLINE=1 uv run --frozen --no-sync pytest -q \
  tests/test_version_identity.py \
  tests/test_bootstrap.py \
  tests/proof/test_mcp_deployment_client.py \
  tests/scripts/test_release_consumer_smoke.py \
  tests/scripts/test_release_presentation_audit.py \
  tests/evaluation/test_mcp_context_completeness_documentation.py \
  tests/evaluation/test_dense_documentation.py \
  tests/interfaces/test_cli_mcp.py
UV_OFFLINE=1 uv run --frozen --no-sync python \
  scripts/release_presentation_audit.py --root . --json
UV_OFFLINE=1 uv run --frozen --no-sync ruff check .
UV_OFFLINE=1 uv run --frozen --no-sync pyright
git diff --check
```

Require protected hashes exact, no dependency drift, no untracked repository output, and no
runtime diff beyond `src/mke/__init__.py`.

- [ ] **Step 2: Prepare the actual-diff authority bundle**

Record:

- exact base `REVIEWED_PLAN_HEAD`;
- candidate HEAD and tree;
- commit list and path list;
- complete diff;
- version/lock semantic comparison;
- protected hash manifest;
- focused/adjacent results;
- rehearsal receipt digest and public-safe scalar summary;
- remaining non-claims.

Do not create a PR or build final candidate wheels.

- [ ] **Step 3: Stop for independent actual-diff review**

The review must cover:

- spec/plan coverage;
- exact path scope;
- current versus historical release truth;
- version/lock authority;
- primary MCP flow accuracy;
- proof-code/action mapping;
- security/private-marker boundaries;
- release lifecycle and rollback;
- tests and proof completeness.

No implementation window self-review substitutes for this gate.

- [ ] **Step 4: Apply verified review findings with TDD**

For each actionable finding:

1. verify it against live code/docs;
2. write or identify the targeted RED;
3. make the smallest in-scope repair;
4. rerun targeted and adjacent gates;
5. commit one semantic review-fix commit;
6. return for targeted re-review.

Do not amend already reviewed commits unless the review handoff explicitly requires it. Any finding
that requires a new path, runtime behavior, schema, dependency, or protected byte is a design
amendment stop.

- [ ] **Step 5: Require final review clean**

Only a clean actual-diff review authorizes Task 7. Record the final reviewed HEAD/tree. Any later
tracked change invalidates that review.

---

## Task 7: Seal And Prove The Reviewed Branch Candidate

**Files:** no tracked files.

- [ ] **Step 1: Seal the final reviewed candidate**

Record exact:

- HEAD and tree;
- branch;
- clean porcelain-v1 `-z` bytes;
- index tree;
- package version `0.1.5`;
- complete tracked inventory digest;
- protected hash manifest;
- implementation diff and commit inventory.

Call this `BRANCH_SEAL`. Create a fresh branch-proof ledger under `LEDGER_ROOT`. From this point,
any tracked/index/HEAD/tree drift invalidates all Task 7 outputs.

- [ ] **Step 2: Run complete code and product gates**

Run, in order, with source-seal checks around each expensive lane:

```bash
UV_OFFLINE=1 uv run --frozen --no-sync pytest -q
UV_OFFLINE=1 uv run --frozen --no-sync ruff check .
UV_OFFLINE=1 uv run --frozen --no-sync pyright
UV_OFFLINE=1 uv build --out-dir "$LEDGER_ROOT/branch/ordinary-build"
UV_OFFLINE=1 uv run mke proof run
UV_OFFLINE=1 uv run mke demo --verify
UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py
UV_OFFLINE=1 uv run python scripts/evidence_provenance_proof.py
UV_OFFLINE=1 uv run mke proof direct-audio --json
UV_OFFLINE=1 uv run python scripts/release_presentation_audit.py --root . --json
```

The direct-audio proof must remain model-free with `network_access=not_used`,
`proof_mode=model_free`, and `asr_execution=not_performed`. Do not run real ASR.

- [ ] **Step 3: Re-prove canonical retrieval-order authority**

Run:

```bash
UV_OFFLINE=1 uv run --frozen --no-sync pytest -q \
  tests/evaluation/test_retrieval_order_canonical_evidence.py \
  tests/adapters/test_sqlite_evidence_access.py
```

Require:

- all five canonical hashes unchanged;
- canonical pure validation passes;
- observation, replay, builders, recorders, and publication remain fenced;
- fixed-profile query-plan exact equality on the sealed profile;
- nonmatching complete profiles route to not-applicable rather than portable equality.

- [ ] **Step 4: Run strict-live numeric negative and temporary compatibility**

Execute the committed CI step named:

```text
Reject archived numeric lock and validate current retrieval-order compatibility
```

Copy its exact committed `run:` body into a call-owned ledger script, record that script SHA-256,
and run it without modification under a fresh `RUNNER_TEMP`.

Require numeric exit `1` and exactly:

```text
problem = retrieval_numeric_fixture_invalid
cause = protocol-bound input identity mismatch
next_step = restore_numeric_protocol_inputs
```

Require temporary compatibility:

- `record` passed and published only the call-owned temporary artifact;
- pure `validate` passed;
- `canonical == false`;
- seven exact families:
  `e1_baseline`, `e2_numeric`, `e3a_chinese`, `e3b_cjk_lexical`, `e3c_dense`,
  `e3d_hybrid_rrf`, `e3e_relevance_gate`;
- every `membership_delta`, `score_hex_delta`, `non_tied_pair_delta`, `metric_delta`,
  `gate_delta`, and `verdict_delta` equals zero;
- canonical bytes unchanged before/after.

Do not copy the temporary artifact into the repository.

- [ ] **Step 5: Build one source-pack candidate without an attempt claim**

Create a fresh absent physical child:

```text
$LEDGER_ROOT/branch/source-pack-candidate
```

Invoke exactly once:

```bash
UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py \
  --python "$PYTHON312" \
  --python "$PYTHON313" \
  --candidate-output "$LEDGER_ROOT/branch/source-pack-candidate" \
  --json
```

Do not pass `--attempt-claim`.

Require:

- exit `0`, `status=passed`;
- exact interpreter minor set `{3.12, 3.13}`;
- exactly one visible wheel;
- wheel filename
  `multimodal_knowledge_engine-0.1.5-py3-none-any.whl`;
- wheel size and SHA-256 recorded;
- candidate receipt/source commit binds `BRANCH_SEAL`;
- candidate output and receipt digests recorded;
- no source drift.

A preexisting/invalid output, second invocation requirement, path alias, wrong interpreter, lock
drift, or ambiguous visibility is terminal.

- [ ] **Step 6: Consume the exact source-pack wheel**

Run release consumer smoke separately for both existing interpreters against the exact
receipt-bound wheel:

```bash
UV_OFFLINE=1 uv run python scripts/release_consumer_smoke.py \
  --wheel "$SOURCE_PACK_WHEEL" \
  --python "$PYTHON312" \
  --json
UV_OFFLINE=1 uv run python scripts/release_consumer_smoke.py \
  --wheel "$SOURCE_PACK_WHEEL" \
  --python "$PYTHON313" \
  --json
```

Require module and installed metadata version `0.1.5`, installed-wheel import isolation, product
proof, demo, CLI, and MCP smoke passed on both lanes.

Then run the compiled Library controller with the same explicit wheel:

```bash
UV_OFFLINE=1 uv run python scripts/compiled_library_export_proof.py \
  --python "$PYTHON312" \
  --python "$PYTHON313" \
  --mke-wheel "$SOURCE_PACK_WHEEL" \
  --json
```

Require one exact wheel across its two lanes and `status=passed`.

- [ ] **Step 7: Run independent MCP completeness installed proof**

Export exact lock-derived constraints to a new branch ledger path, verify them byte-for-byte
against a second export, and create a fresh absent candidate-output.

Invoke once:

```bash
UV_OFFLINE=1 uv run python scripts/mcp_context_completeness_proof.py \
  --python "$PYTHON312" \
  --python "$PYTHON313" \
  --constraints "$LEDGER_ROOT/branch/mcp-constraints.txt" \
  --candidate-output "$LEDGER_ROOT/branch/mcp-candidate" \
  --json
```

Require its own one-wheel identity, exact Python minor set, ten tools, continuation, exact read,
CJK cap, cursor expiry, legacy compatibility, installed-wheel source import, no network, and exact
lock constraints. Do not require equality with the source-pack wheel.

- [ ] **Step 8: Run remaining installed and immutable gates**

Run:

- exact current ten-tool fixture tests;
- current/legacy/v1 MCP compatibility tests;
- immutable historical retrieval artifact tests;
- canonical hash test;
- release documentation and command-shape tests;
- the model-free media contract group used by CI.

Do not run real ASR, model download, or any denylisted historical retrieval installed proof.

- [ ] **Step 9: Close the branch proof ledger**

Re-read every retained output and digest. Re-prove `BRANCH_SEAL`, protected hashes, clean status,
and exact reviewed HEAD/tree.

Record a private branch-candidate summary:

```text
status
head/tree
full-suite result
Ruff/Pyright result
ordinary build result
product/demo/local/provenance/model-free-audio result
canonical pure result
query-plan result
numeric expected-negative tuple
temporary compatibility seven-family zero-delta result
source-pack receipt/wheel identity
release-consumer two-lane result
compiled-export result
MCP completeness wheel/two-lane result
rehearsal receipt digest
non-claims
```

No Task 7 output is committed. Terminal stop for push/PR approval.

## Plan Amendment A — Complete Offline Transcription Prerequisite Authority

### Trigger And Classification

The first Task 7 branch-proof attempt stopped at the first required Step 8 prerequisite failure:

```text
UV_OFFLINE=1 uv sync --locked --extra transcription
```

The exact missing distribution was the locked
`setuptools-83.0.0-py3-none-any.whl` required by the transcription dependency graph.
The prior Task 0 offline prerequisite check covered only the development environment:

```text
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never uv sync --locked --dev
```

It therefore did not falsify the later transcription-extra cache requirement. Classify this as an
incomplete prerequisite inventory, not a product regression, dependency-resolution change,
transcription-quality failure, or release-candidate success.

All outputs from the stopped Task 7 attempt remain retained non-acceptance history. They may support
diagnosis, but no test, build, wheel, receipt, compatibility result, MCP result, or partial ledger
from that attempt may be reused to accept a later candidate.

This amendment supersedes Task 0 Step 4 for the next candidate attempt and defines the only
authorized recovery. It does not change the release scope, runtime, dependency set, lock semantics,
public API, retrieval evidence, comparison boundary, or publication authority.

### A0 — Land And Review This Amendment

Land this amendment as one plan-only commit after the stopped candidate HEAD.

Requirements:

- modify only this implementation plan;
- keep the approved design specification byte-identical;
- keep all nine protected files and all historical release bytes byte-identical;
- keep `uv.lock`, source, tests, documentation outside this plan, and generated evidence unchanged;
- perform no prerequisite preparation, sync, test, build, proof, GitHub, release, comparison, or
  cleanup action in the landing task;
- verify the exact inserted block, complete diff, marker scan, balanced fences, Task 0–13 heading
  sequence, range `git diff --check`, and clean final state;
- terminal stop for independent actual plan-diff review.

The plan-only commit invalidates the former reviewed HEAD/tree and branch seal. A clean actual
plan-diff review must record a new reviewed HEAD/tree before any recovery or Task 7 command.

### A1 — Bind The Existing Local Wheel Input

After the amendment diff is review-clean, one existing operator-provided local wheel may be used as
the sole missing prerequisite input. Before reading or copying its bytes, require:

- an explicit absolute physical source path outside the repository;
- every existing lexical ancestor and the source itself is non-symlink;
- the source is a readable regular file;
- exact basename `setuptools-83.0.0-py3-none-any.whl`;
- exact size `1008090`;
- exact SHA-256
  `29b23c360f22f414dc7336bb39178cc7bcbf6021ed2733cde173f09dba19abb3`;
- exact equality with the corresponding filename, size, and SHA-256 already recorded in `uv.lock`;
- wheel metadata identifies project `setuptools`, version `83.0.0`, and a compatible universal
  Python wheel;
- the source is not inside an unfinished comparison worktree, protected comparison evidence, or the
  repository.

Any identity, path-kind, metadata, lock, or readability mismatch is terminal. Do not search for a
substitute, use a second wheel, contact an index, download a package, or edit cache internals.

The existing wheel is prerequisite input only. Its presence does not prove cache portability,
cold-offline installation, air-gapped acquisition, or release readiness.

### A2 — Create A Fresh Call-Owned Prerequisite Wheelhouse

Create a fresh absent physical `PREREQUISITE_ROOT` outside the repository and under a no-symlink
ancestor chain. Create one child wheelhouse and copy only the verified wheel into it.

Before use, require:

- the copied path is a readable non-symlink regular file;
- its basename, size, SHA-256, and wheel metadata equal A1 exactly;
- the wheelhouse contains exactly one file and no symlink, directory alias, or extra distribution;
- the source wheel remains unchanged after the copy;
- a private manifest records source identity, copied identity, lock identity, and byte equality.

Do not move, overwrite, chmod, delete, or otherwise mutate the retained source wheel. Do not write
the wheelhouse, its manifest, or any cache material into the repository.

### A3 — Falsify Then Prepare The Complete Offline Extra

Before each command below, re-prove:

- the new reviewed HEAD/tree and index tree are exact;
- worktree/index porcelain is clean;
- `uv.lock` and all nine protected hashes are exact;
- the copied wheel identity and wheelhouse inventory are exact;
- network and interpreter downloads remain disabled;
- no real ASR, model download, observation, comparison, or publication action has occurred.

First run one dry run whose no-write guarantee is limited to the lockfile and project environment:

```bash
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never \
uv sync --locked --extra transcription \
  --find-links "$PREREQUISITE_WHEELHOUSE" \
  --dry-run
```

Require exit `0`, no unavailable distribution, no lock rewrite, and no project-environment
modification. The dry run authorizes at most one preparation invocation:

```bash
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never \
uv sync --locked --extra transcription \
  --find-links "$PREREQUISITE_WHEELHOUSE"
```

Require exit `0`. The resolver must remain bound to `uv.lock`; `--find-links` may satisfy only the
exact A1 wheel. Any other missing package, version/source drift, lock rewrite, interpreter request,
network requirement, ambiguous wheel, or second preparation requirement is terminal.

Immediately re-prove repository identity and run the original cache-warmed command once without
`--find-links`:

```bash
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never \
uv sync --locked --extra transcription
```

Require exit `0`. This plain-command pass is mandatory: a pass that depends on retaining
`--find-links` in the Task 7 command is not accepted. Re-read the exact wheelhouse manifest,
`uv.lock`, protected hashes, HEAD/tree/index, and clean porcelain after the command.

No direct or manual write to the uv cache is authorized. Project-environment changes may occur only
through the two non-dry-run `uv sync` invocations above. Normal uv-managed cache reads or writes may
occur only as side effects of the three enumerated commands and are not acceptance evidence. The
dry run is required not to write the lockfile or modify the project environment; no stronger
cache-side-effect claim is made. Do not use `uv cache clean`, `uv cache prune`, manual cache
copying, manual site-packages installation, network fallback, or a network package-index request.

### A4 — Re-Seal And Re-Run Task 7 From The Beginning

Only after A1–A3 pass may Task 7 restart.

Requirements:

- use the new reviewed plan-only HEAD/tree as the candidate;
- create a fresh Task 7 ledger at a new absent physical path;
- invoke every Task 7 Step 1–9 gate again in the approved order;
- do not reuse any prior Task 7 command output, temporary compatibility artifact, build, wheel,
  receipt, constraint export, installed proof, or digest;
- preserve the original Step 8 command shape and no-real-ASR boundary;
- retain both the failed historical ledger and the fresh ledger as separate evidence;
- if the same prerequisite, another cache input, or any later required gate fails, terminal stop
  without retry, repair, fallback, or continuation;
- no Task 8 action unless the fresh Task 7 ledger closes completely and passes independent
  authority review.

### Acceptance And Non-Claims

This amendment is accepted only when:

1. its actual plan diff is review-clean;
2. A1 binds the exact locked local wheel;
3. the dry run, one preparation invocation, and plain offline recheck all pass;
4. repository identity remains exact throughout;
5. a completely fresh Task 7 Step 1–9 ledger passes;
6. the final candidate summary clearly separates the stopped historical attempt from the accepted
   fresh attempt.

Even on success, do not claim cold-cache portability, air-gapped package acquisition, real ASR,
model quality, retrieval quality improvement, runtime promotion, production adoption, or release
publication. The result is only a cache-warmed, lock-bound, model-free release-candidate proof.

---

## Task 8: Push And Open A Draft Pull Request

**Files:** no new repository files.

This task requires explicit push/PR authorization after Task 7 is accepted.

- [ ] **Step 1: Re-prove candidate identity**

Require local HEAD/tree equal `BRANCH_SEAL`, worktree/index clean, proof ledger readable, remote
release branch absent or exactly expected, and public main unchanged from the Task 0 value.

If main moved, stop for intervening-diff review before push.

- [ ] **Step 2: Push normally**

Push the reviewed release branch without force. Read back the remote ref and require exact equality
with `BRANCH_SEAL.head`.

- [ ] **Step 3: Create a Draft PR and read persisted state**

Create one Draft PR to `main`. The public-neutral body must state:

- release identity and headline;
- exact implementation scope;
- runtime/schema/dependency non-change;
- full local verification summary;
- branch proof wheel/receipt identities;
- canonical/temporary compatibility authority;
- explicit non-claims;
- remaining lifecycle gates: hosted checks, review, merge, exact-main proof, publication.

Read back title, body bytes, Draft/open state, base, head branch, head SHA, and URL. Require exact
persisted equality.

- [ ] **Step 4: Stop**

Do not mark Ready, merge, tag, publish, delete a branch, or clean proof outputs.

---

## Task 9: Close Hosted Review And Merge The Exact Reviewed Tree

**Files:** only in-scope repair files if hosted/review findings require code or docs changes.

- [ ] **Step 1: Read hosted and review state**

After checks have reached terminal state, read:

- complete check inventory and conclusions;
- PR reviews;
- issue comments;
- inline comments and review threads;
- exact PR head SHA/body.

Do not treat a partial inventory as success.

- [ ] **Step 2: Repair only verified findings**

Any code/docs repair:

- invalidates all Task 7 outputs;
- requires targeted RED/GREEN;
- requires a semantic commit and targeted actual-diff re-review;
- requires a fresh Task 7 seal and complete matrix;
- requires normal push and fresh hosted checks.

Do not reuse a lane-local result or silently rerun a failed one.

- [ ] **Step 3: Require merge readiness**

Require:

- PR exact head equals the latest reviewed seal;
- all required checks terminal success;
- no unresolved actionable review/comment/thread;
- PR mergeable and clean;
- persisted body reflects the final exact verification ledger.

Then stop for explicit merge authorization. The approval request must state whether repository
auto-delete of the remote feature branch is accepted.

- [ ] **Step 4: Mark Ready and squash merge**

Only after merge authorization:

1. read active rulesets and merge-method settings;
2. mark the PR Ready and read back;
3. squash merge without title/body mutation;
4. read persisted merged state;
5. record merge commit and parent;
6. require merge tree equals the reviewed branch tree exactly;
7. read post-merge checks on the merge SHA.

If tree equality fails, stop unpublished. Do not tag.

---

## Task 10: Re-Prove Fresh Exact Main

**Files:** no tracked files.

- [ ] **Step 1: Create a fresh exact-main proof checkout**

Create a new detached, task-owned proof worktree at the exact merge commit. Do not reuse the
branch proof worktree, `.venv`, constraints, wheels, receipts, or output paths.

Require:

- exact merge HEAD/tree;
- clean index/worktree;
- package identity `0.1.5`;
- protected hashes exact;
- public main points at the merge commit.

Record `EXACT_MAIN_SEAL`.

- [ ] **Step 2: Run the complete Task 7 matrix from scratch**

Repeat every Task 7 gate in a fresh exact-main ledger:

- full pytest;
- Ruff;
- Pyright;
- ordinary build;
- product proof;
- demo;
- local knowledge proof;
- Evidence provenance proof;
- model-free direct-audio proof;
- presentation audit;
- canonical pure validation;
- fixed-profile query-plan routing;
- strict-live numeric expected negative;
- temporary compatibility record/validate with seven zero-delta families;
- source-pack candidate without `--attempt-claim`;
- exact-wheel release consumer on Python 3.12 and 3.13;
- explicit-wheel compiled Library proof;
- independent MCP completeness proof on Python 3.12 and 3.13;
- remaining immutable/interface/installed gates.

Use new output paths and new controller invocations. No branch result is authority for exact main.

- [ ] **Step 3: Close exact-main publication readiness**

Re-read all exact-main outputs and re-prove the source seal. Require merge-tree equality still
holds and hosted post-merge checks are successful.

Record:

- merge commit/tree;
- exact-main proof ledger digest;
- exact-main wheel/receipt identities per controller;
- protected hashes;
- public-safe result summary;
- all non-claims.

Stop for separate tag/GitHub Release publication authorization.

---

## Task 11: Publish `v0.1.5` And Verify The Public Archive

**Files:** no tracked repository files.

This task requires explicit publication authority covering annotated tag creation, tag push,
GitHub Release creation, and read-only archive verification.

- [ ] **Step 1: Reconcile pre-publication state**

Require:

- public main and `EXACT_MAIN_SEAL` commit/tree exact;
- exact-main proof green and ledger readable;
- local and remote `v0.1.5` tag absent;
- GitHub Release `v0.1.5` absent;
- no newer main commit;
- no unresolved hosted or review state.

Any conflict stops publication.

- [ ] **Step 2: Create and verify the local annotated tag**

Create:

```bash
git tag -a v0.1.5 "$MERGE_COMMIT" -m "v0.1.5"
```

Read back:

- tag object type and annotation;
- peeled commit;
- target tree.

Require exact equality with `EXACT_MAIN_SEAL`. A preexisting tag, ambiguous state, or wrong target
is terminal; do not move or delete it.

- [ ] **Step 3: Push the tag and measure the partial public state**

Push only `refs/tags/v0.1.5`. Read back the remote tag object and peeled commit. Then read GitHub
Release state and require the Release is still absent.

The measured state is:

```text
REMOTE_TAG_VISIBLE_RELEASE_ABSENT
```

Do not blind-retry a failed or ambiguous push.

- [ ] **Step 4: Create a zero-asset GitHub Release**

Create one public, non-draft, non-prerelease GitHub Release:

- tag: `v0.1.5`;
- target: exact merge commit;
- title: `v0.1.5`;
- notes: public release content derived from `docs/releases/v0.1.5.md`;
- attached assets: none.

On timeout or ambiguous response, read persisted state once before any retry. Do not upload wheels
or other assets.

- [ ] **Step 5: Read persisted Release identity**

Require:

- tag and target exact;
- `isDraft == false`;
- `isPrerelease == false`;
- zero assets;
- expected title/body;
- published URL and timestamp visible.

Until archive proof passes, the state is:

```text
RELEASE_VISIBLE_UNVERIFIED
```

- [ ] **Step 6: Download and safely inventory the public source archive**

Download the public GitHub-generated source archive into a fresh physical path. Record descriptor
SHA-256 before extraction.

Safely extract with:

- no absolute paths;
- no `..` traversal;
- no device/FIFO/socket entry;
- no write outside the extraction root;
- exact single top-level directory.

Build a path/mode/content manifest and require exact equality with the tagged Git tree after
accounting only for the archive top-level prefix. Do not synthesize `.git`.

- [ ] **Step 7: Build and run the exact Git-less allowlist**

Inside the extracted Git-less archive:

```bash
UV_PROJECT_ENVIRONMENT="$ARCHIVE_ENVIRONMENT" \
  UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never uv sync --locked
UV_PROJECT_ENVIRONMENT="$ARCHIVE_ENVIRONMENT" \
  UV_OFFLINE=1 uv build --wheel --out-dir "$ARCHIVE_WHEEL_OUTPUT"
```

Require one exact archive wheel and record name, size, SHA-256, package/module/metadata identity
`0.1.5`. `ARCHIVE_ENVIRONMENT`, wheel output, constraints, logs, and proof outputs must all be
outside the extracted archive. Apply the same `UV_PROJECT_ENVIRONMENT` binding to every
archive-side `uv run`.

Run only:

- product proof;
- demo;
- local knowledge proof;
- Evidence provenance proof;
- model-free direct-audio proof;
- release presentation audit;
- archive-built wheel through `release_consumer_smoke.py`;
- MCP context completeness proof when both prepared interpreters and exact warm constraints are
  available;
- native `mke library export` followed by `compiled_library_export_consumer.py`;
- `tests/adapters/test_sqlite_fts_order.py`;
- `tests/adapters/test_sqlite_cjk_order.py`;
- `tests/application/test_mcp_cursor.py`;
- `tests/evaluation/test_retrieval_order_canonical_evidence.py`.

Run none of:

- `consumer_source_pack_proof.py`;
- `compiled_library_export_proof.py`;
- `retrieval_order_installed_proof.py`;
- temporary compatibility record/replay;
- historical materialization;
- real ASR/model download;
- unfinished comparison access.

- [ ] **Step 8: Close publication verification**

Require:

- public archive manifest equals tagged tree;
- Git-less lock sync/build/proofs green;
- archive source inventory unchanged pre/post proof;
- tag/Release persisted state unchanged;
- zero assets still exact.

Record state:

```text
PUBLICATION_VERIFIED
```

If any archive gate fails, retain the public Release and evidence, report
`RELEASE_VISIBLE_UNVERIFIED`, and stop for a corrective lifecycle decision. Never move the tag or
rewrite the Release silently.

---

## Task 12: Record Post-Release Facts In A Docs-Only Closeout

**Files:** `docs/releases/v0.1.5.md`, `docs/how-to/verify-release.md` only.

This is a new docs-only branch/PR after publication verification. It requires separate
publication authority and does not amend the tagged release.

- [ ] **Step 1: Run a targeted read-only closeout RED**

Use a call-owned Python assertion script outside the repository. Before the docs edit, require it
to fail because the publication-verification section and exact persisted facts are absent. Do not
modify a test path in this post-release task.

Require the post-release sections to record:

- tag;
- merge commit/tree;
- Release URL/timestamp;
- zero assets;
- hosted check inventory;
- public archive descriptor and manifest digest;
- archive wheel identity;
- public Git-less allowlist result;
- exact-main proof status;
- canonical evidence hashes;
- temporary compatibility seven-family zero-delta result;
- retained proof limitations and non-claims.

No local path, private ledger location, elapsed performance claim, or comparison result may enter
the docs.

- [ ] **Step 2: Add immutable public-neutral facts**

Append a clearly dated `Publication verification` section to `docs/releases/v0.1.5.md` and update
`docs/how-to/verify-release.md` so `v0.1.5` appears as immutable history after the reusable
evaluator/maintainer instructions.

Do not modify the tagged release note body on GitHub unless a separate correction is explicitly
authorized.

- [ ] **Step 3: Run docs-only verification**

Run:

```bash
UV_OFFLINE=1 uv run --frozen --no-sync pytest -q \
  tests/scripts/test_release_presentation_audit.py \
  tests/evaluation/test_mcp_context_completeness_documentation.py \
  tests/evaluation/test_dense_documentation.py
UV_OFFLINE=1 uv run --frozen --no-sync python \
  scripts/release_presentation_audit.py --root . --json
UV_OFFLINE=1 uv run --frozen --no-sync ruff check .
UV_OFFLINE=1 uv run --frozen --no-sync pyright
git diff --check
```

Require no runtime, lock, evidence, fixture, workflow, or test-source drift.

- [ ] **Step 4: Commit and publish through a docs-only PR**

Commit:

```bash
git commit -m "docs(release): record v0.1.5 publication"
```

Push/PR and merge remain explicit external actions. Require hosted checks and review clean before
merge. The release tag remains unchanged.

- [ ] **Step 5: Complete the durable retrospective**

The authority owner records a private retrospective using only live diff, tests, PR, hosted checks,
tag, Release, archive, and retained proof evidence. Only verified public-neutral lessons may later
enter the public repository.

---

## Task 13: Close Local Lifecycle And Hand Off Comparison Resume

**Files:** none by default.

- [ ] **Step 1: Require release closed**

Require:

- `PUBLICATION_VERIFIED`;
- post-release docs-only PR merged and hosted checks green;
- public main clean and exact;
- no release PR open;
- retained proof ledger and archive evidence readable;
- no pending release repair.

- [ ] **Step 2: Inventory cleanup targets read-only**

Inventory:

- registered worktrees;
- local branches;
- remote branches;
- tags;
- release proof worktrees;
- task-owned ledger/evidence directories.

Classify each exact target by owner, clean state, HEAD/tree, merged-tree retention, open PR, and
planned reuse. Do not enter or inspect protected comparison worktrees beyond the registration/ref
inventory required to exclude them.

- [ ] **Step 3: Stop for exact cleanup authority**

The cleanup request must name every worktree, local branch, remote branch, and evidence path.
Default:

- remove only clean task-created release worktrees;
- delete only release branch refs whose reviewed tree is retained by merged main;
- explicitly state whether remote release branch deletion is authorized;
- retain proof/evidence directories;
- never remove main, tags, protected comparison refs/worktrees, host-managed worktrees, dirty
  state, or unique unretained changes.

No broad glob, force fallback, recursive workspace deletion, or broad prune is authorized.

- [ ] **Step 4: Read back final inventories**

After approved cleanup, require:

- local main clean at public main;
- only intended branches/worktrees remain;
- public `v0.1.5` tag and Release exact;
- protected comparison ownership unchanged;
- retained evidence manifest unchanged.

- [ ] **Step 5: Prepare the comparison-resume handoff**

The handoff may state only:

- `v0.1.5` is the published local-first Agent-consumption baseline;
- release runtime behavior was unchanged;
- comparison work remained excluded and unread;
- comparison-only results cannot promote runtime;
- resume requires fresh authority review of retained nondeterminism stop, frozen development
  corpus, sealed holdout, and the four alternatives:
  maintenance, docs/regression-only, bounded segmentation comparison, contextual retrieval
  comparison.

Do not read or normalize retained comparison evidence during release closeout.

---

## Final Acceptance Matrix

| Area | Required result |
|---|---|
| Version | package, module, metadata, exact wheel, and root lock are `0.1.5` |
| Lock | only root editable package version changed |
| Runtime | no behavior/schema/dependency change; only `src/mke/__init__.py` version literal |
| Presentation | one H1 per entry point; current v0.1.5 Agent story first |
| MCP | exact ten tools; real request envelope; completeness branch; exact read/digest |
| Compatibility | valid legacy/v1 calls retained; exact inventory migration documented |
| Evidence | five canonical hashes and fixed query-plan fixture unchanged |
| Numeric | exact strict-live expected-negative tuple retained |
| Differential | temporary seven-family compatibility, all six delta classes zero |
| Branch proof | full suite, Ruff, Pyright, build, product and installed proofs green |
| Wheel authority | one exact wheel per controller across Python 3.12/3.13 |
| Review | independent actual-diff review clean before candidate proof and before merge |
| Hosted | all required exact-head and merge-head checks terminal success |
| Merge | reviewed tree equals squash-merge tree |
| Exact main | complete fresh proof matrix; no branch result reused |
| Publication | annotated exact tag; public non-draft/non-prerelease zero-asset Release |
| Archive | safe Git-less tree equality, exact allowlist green, denylist untouched |
| Closeout | docs-only immutable facts, retrospective, exact cleanup gate |
| Comparison | untouched, unread, unclaimed, and separately resumed |

## Stable Stop And Rescue Rules

| Failure | Required response |
|---|---|
| main moved before implementation | stop for intervening-diff review |
| plan/spec/hash/clean-state mismatch | stop before write |
| dependency or lock graph drift | stop; do not accept release identity |
| historical v0.1.4 contract fails | stop; do not weaken historical checks |
| runtime/schema change appears necessary | stop for design amendment |
| proof code table requires proof schema change | stop; document existing code only |
| rehearsal exceeds target | repair docs/flow or record target miss; no performance claim |
| canonical evidence invalid | stop; no regeneration |
| numeric expected negative changes | stop; no fixture refresh |
| compatibility has fewer than seven families or nonzero delta | stop; no canonical rewrite |
| candidate path preexisting/unsafe | stop; use no alternate path without renewed authority |
| source drift after seal | invalidate all outputs; reviewed repair and full rerun |
| hosted check/review failure | PR remains Draft; targeted diagnosis and re-review |
| merge tree differs | stop unpublished; no tag |
| local/remote tag conflict | read persisted refs; no move/delete/retry |
| Release response ambiguous | one persisted readback before any retry |
| Release metadata/assets differ | stop visible-unverified; no silent mutation |
| archive identity/proof fails | retain Release and evidence; corrective lifecycle decision |
| cleanup target dirty/unique/ambiguous | preserve it and stop |

## Approval Boundaries

Approval of this implementation plan authorizes only its mechanical public landing.

After actual plan-diff review, implementation requires a separate approval. Implementation does
not authorize push, Draft PR, Ready transition, merge, remote branch deletion, tag, GitHub Release,
post-release docs publication, cleanup, PyPI, deployment, runtime promotion, or comparison access.
Each lifecycle transition occurs only at the explicit gate above.
