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

## Plan Amendment B — Separate Lock-Bound Cache Warm From Offline Proof

### Trigger And Authority Diagnosis

Plan Amendment A was executed once against its newly reviewed candidate and stopped at its first
required preparation failure. Its exact local wheel, one-file wheelhouse, manifest, lock identity,
and dry-run checks all passed. The dry run nevertheless reported that one package would still be
downloaded. The only authorized non-dry-run preparation command then failed while trying to obtain
the locked `setuptools==83.0.0` registry artifact with network disabled.

This is the second substantive failure in the same Task 7 transcription-prerequisite lane:

1. the original Task 7 run proved that the registry artifact recorded in `uv.lock` was absent from
   the uv cache;
2. Amendment A proved that an exact matching wheel supplied through `--find-links` can participate
   in candidate discovery without becoming the cached identity used by the locked registry
   artifact during installation.

The retained evidence therefore falsifies Amendment A's A3 recovery mechanism. Classify this as a
proof-orchestration and package-cache authority error, not as:

- a product runtime regression;
- a dependency-set, version, marker, source, or lock change;
- a transcription-quality or model failure;
- a failure of the local wheel's filename, size, digest, metadata, or compatibility;
- cold-offline, air-gapped, or cache-portability evidence;
- Task 7 completion or release readiness.

The authoritative uv behavior for this recovery is:

- `--locked` keeps `uv.lock` unchanged;
- `--extra transcription` selects the already-declared optional dependency closure;
- `--offline` permits only cached data and locally available inputs;
- `--find-links` adds candidate distribution locations but is not accepted here as a cache-import
  or registry-URL alias.

The final bullet is bound by the two observed runs, not asserted as a general uv cache-format
contract.

This amendment supersedes Amendment A A3 and A4. A1 and A2 remain retained diagnostic evidence but
do not authorize another local-wheel preparation, another `--find-links` invocation, manual
installation, or cache mutation. The two stopped Task 7 histories and the stopped Amendment A
history remain non-acceptance evidence and may not be reused to accept a later candidate.

This amendment does not change the release scope, project dependency set, `uv.lock`, runtime,
public API, CLI, MCP, schemas, retrieval behavior, Evidence authority, comparison boundary, release
claims, or publication authority.

### B0 — Land And Review This Amendment

Land this complete amendment immediately after Amendment A and before Task 8 as one plan-only
commit.

Before the write, require:

- starting HEAD
  `4ec8cd86fb31e4ee9ff753b4a35e4fdfe44c6e8d`;
- starting tree and index tree
  `1249b1b7d2a7bea82924e55d42770fd0ede3833d`;
- clean worktree and index;
- current plan SHA-256
  `01019d5e15d9a7b6cd6b0a742d2da58d7478a97bb94d4f940d8335874af99a9c`;
- design specification SHA-256
  `260b178bcac6255d7f3a7ad1a29272bca45234e1a5599939609147ff320da48e`;
- `uv.lock` SHA-256
  `1f2e215c08fefc9fe60b2a22467fadd546af2da13de0926282515d2211ffcab9`;
- all nine protected hashes remain exact;
- all stopped-ledger, source-wheel, wheelhouse, manifest, and failure-record identities remain
  unchanged.

Requirements:

- modify only
  `docs/superpowers/plans/2026-07-28-v0-1-5-release-closeout-implementation.md`;
- preserve the approved design specification, `uv.lock`, source, tests, release documentation,
  canonical evidence, fixtures, and historical release bytes exactly;
- insert the approved amendment bytes with one Markdown separator and preserve Task 8 onward
  byte-for-byte;
- verify source/extracted-block equality, SHA-256, inverse reconstruction of the parent plan,
  balanced fences, unique Amendment B and B0–B4 headings, unchanged Task 0–13 heading sequence,
  complete no-index/cached/committed diff, marker scan, range `git diff --check`, one-path scope,
  one-commit ancestry, and clean final state;
- perform no sync, package or interpreter download, cache mutation, environment preparation, test,
  build, proof, model operation, observation, comparison, GitHub, publication, release, or cleanup
  action;
- terminal stop for independent actual plan-diff review.

Use commit message:

```text
docs(plan): separate cache warm from offline proof
```

The plan-only commit creates a new candidate HEAD/tree. B1 must not begin until its actual plan diff
is review-clean and the new exact candidate seal has been returned to the execution controller.

### B1 — Re-Seal The Candidate And Retained Failure Authority

After B0 review passes, create a fresh call-owned prerequisite-recovery ledger outside the
repository under a physical no-symlink ancestor chain. Do not reuse either Task 7 ledger or the
Amendment A prerequisite root as the new ledger.

Before any sync, bind:

- the new reviewed HEAD, tree, and index tree;
- clean worktree and index;
- exact plan, design specification, `uv.lock`, and nine protected hashes;
- exact Python and uv identities already approved by Task 7;
- exact project-environment identity and metadata state;
- the original Task 7 failure record and failure-log digests;
- the Amendment A manifest, dry-run log, preparation-failure log, and BLOCKED-record digests;
- the retained source wheel and copied wheel identities without opening, copying, installing, or
  otherwise consuming them again;
- absence of any Task 7 acceptance ledger for the new candidate;
- absence of real ASR, model download, observation, comparison, GitHub, or publication actions.

The new ledger must state:

```text
failure_count_same_lane=2
amendment_a_recovery=falsified
network_cache_warm=approved_pending
offline_proof=not_started
task_7=not_started
```

Any candidate, source, lock, protected-byte, retained-evidence, environment-identity, or cleanliness
drift is terminal before network use. Do not repair or continue in the same invocation.

### B2 — Perform One Lock-Bound Online Cache Warm

This step is the sole approved network package-acquisition action. It occurs before offline proof
and is not itself release acceptance evidence.

Immediately before the command, re-prove every B1 identity. Record:

- `uv.lock` bytes and SHA-256;
- HEAD, tree, index tree, and porcelain;
- project-environment identity and metadata state;
- the absence of interpreter or model-download authorization;
- the expected missing locked distribution:
  `setuptools==83.0.0`,
  filename `setuptools-83.0.0-py3-none-any.whl`,
  size `1008090`,
  SHA-256
  `29b23c360f22f414dc7336bb39178cc7bcbf6021ed2733cde173f09dba19abb3`;
- a controller invocation count of zero.

Invoke exactly once:

```bash
UV_PYTHON_DOWNLOADS=never \
uv sync --locked --extra transcription
```

Do not set `UV_OFFLINE`. Do not add `--find-links`, `--no-index`, `--refresh`, `--upgrade`,
`--inexact`, another index, another cache directory, or another package argument.

Require:

- invocation count exactly one;
- exit `0`;
- `uv.lock` remains byte-identical with its exact pre-command SHA-256;
- the selected dependency graph remains the existing locked `transcription` extra;
- no dependency version, source, marker, or resolution change;
- no interpreter download;
- no transcription-model download, model construction, fixture open, ASR, product proof,
  observation, comparison, or publication action;
- the command output identifies no newly acquired package outside the exact locked missing
  `setuptools==83.0.0` distribution;
- HEAD, tree, index tree, tracked bytes, and clean porcelain remain exact after the command;
- the controller records exact argv, start and finish times, exit code, bounded stdout/stderr
  bytes and digests, and before/after authority identities.

This gate does not claim a single HTTP request, a particular internal cache path, a portable cache
layout, or a cold-offline installation. Normal uv-managed cache and project-environment writes are
authorized only as effects of this one command.

Any nonzero exit, second invocation requirement, package outside the existing lock, lock rewrite,
interpreter request, model action, source drift, or repository mutation is terminal. Do not retry,
fall back to the retained wheel, alter the cache, or continue to B3.

### B3 — Prove The Original Offline Prerequisite

Only after B2 passes, re-prove:

- the exact new candidate seal and clean repository state;
- byte-identical plan, design specification, `uv.lock`, and nine protected files;
- the B2 command ledger and its single invocation count;
- no model download, ASR, observation, comparison, or publication action;
- the retained Amendment A evidence remains unchanged.

Then invoke the original Task 7 prerequisite command exactly once and without `--find-links`:

```bash
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never \
uv sync --locked --extra transcription
```

Immediately after that command, run this read-only environment probe exactly once:

```bash
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never \
uv run --frozen --no-sync python - <<'PY'
from importlib.metadata import version

expected = {
    "ctranslate2": "4.8.0",
    "faster-whisper": "1.2.1",
    "setuptools": "83.0.0",
}
observed = {name: version(name) for name in expected}
assert observed == expected, observed

import ctranslate2  # noqa: F401
import faster_whisper  # noqa: F401

print("transcription_extra_environment=passed")
PY
```

Require:

- invocation count exactly one;
- exit `0`;
- no network or interpreter download;
- no unavailable distribution;
- no lock, dependency, source, marker, or resolution drift;
- no model download, model construction, fixture open, or real ASR;
- `uv.lock`, HEAD, tree, index tree, tracked bytes, and clean porcelain remain exact;
- a final offline environment probe executed with `uv run --frozen --no-sync` observes installed
  `setuptools` version exactly `83.0.0` and imports the already-locked transcription dependency
  surface without constructing a model or opening media;
- exact argv, duration, exit code, bounded stdout/stderr bytes and digests, environment probe
  result, and post-command authority identities are retained.

The B3 result proves only that this prepared environment can execute the exact locked
transcription-extra sync with network disabled. It does not prove that a fresh empty cache can do
so.

Any failure is terminal. Do not run another online warm, another offline sync, another local-wheel
preparation, Task 7, or a weakened substitute gate.

### B4 — Re-Seal And Run Task 7 Once From The Beginning

Only after B1–B3 pass and the candidate remains exact may Task 7 restart.

Requirements:

- create a fresh absent physical Task 7 ledger at a path unrelated to the original Task 7 attempt,
  Amendment A, and B1–B3; do not copy their ledger files or logs, and do not count any earlier
  command as a Task 7 gate execution;
- bind the new reviewed plan-only HEAD/tree as the sole candidate;
- rerun every Task 7 Step 1–9 gate in the approved order;
- preserve the original Step 8 command shape and its model-free, no-real-ASR boundary;
- do not reuse any prior test output, build, wheel, receipt, constraints export, compatibility
  result, source-pack result, installed proof, MCP result, digest bundle, or partial summary;
- retain the two stopped Task 7 ledgers, Amendment A evidence, B1–B3 recovery ledger, and fresh
  Task 7 ledger as separate histories;
- bind only the immutable B1–B3 recovery-ledger digest and passed statuses as prerequisite
  authority; record the online cache warm outside the offline proof result, and do not copy its
  command output into Task 7 gate results;
- if any Task 7 gate fails, terminal stop at the first failure without retry, repair, fallback,
  continuation, or Task 8 action;
- no Task 8 action until the complete fresh Task 7 ledger and actual candidate diff pass independent
  authority review.

### Acceptance And Non-Claims

Amendment B is accepted only when:

1. its exact plan diff is independently review-clean;
2. B1 binds the new candidate and all retained failures without consuming old evidence as
   acceptance input;
3. B2 runs exactly one lock-bound online cache warm and preserves `uv.lock` and repository bytes;
4. B3 runs the unchanged offline transcription-extra sync exactly once and passes;
5. a completely fresh Task 7 run passes every Step 1–9 gate without reuse;
6. all protected bytes and historical release evidence remain exact;
7. the final repository is clean and no unapproved lifecycle action occurred.

Stable non-claims:

- no new dependency, version, source, marker, lock, runtime, API, CLI, MCP, schema, retrieval, or
  Evidence behavior;
- no cold-offline, empty-cache, air-gapped, cache-portability, or single-request guarantee;
- no model download, real ASR, transcription-quality, performance, cross-platform, deployment,
  adoption, or business-value claim;
- no comparison result, runtime promotion, PyPI publication, hosted service, tag, GitHub Release,
  or release completion from prerequisite preparation alone;
- online dependency acquisition is disclosed as pre-proof cache warm and is never reported as part
  of offline proof.

The only next authority after a clean B0 plan review is B1–B4 execution under this amendment.
Push, PR, merge, tag, GitHub Release, PyPI, deployment, promotion, cleanup, and comparison work
remain separately gated by the original plan and current user authorization.

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

## Plan Amendment C — Prepare Fresh Exact-Main Environment Before No-Sync Gates

### Trigger And Authority Diagnosis

Task 9 completed against the reviewed release tree:

- PR #96 was marked Ready and squash merged;
- merge commit
  `168181cb4eae7ecd430efe723663f4993bff8d4f`;
- sole merge parent
  `33106ec2cfeabf6c1c448fad57fb2489e3712543`;
- merge tree
  `8910be7b673d8483e0b1a9deb3f9600b80074712`;
- merge tree equals the reviewed branch tree exactly;
- all nine observed post-merge checks completed successfully;
- the remote feature branch was deleted by the repository's accepted server-side merge behavior.

The first Task 10 exact-main attempt then created a fresh detached worktree as required. That
worktree had no synchronized project environment. Task 10 Step 2 nevertheless began with:

```bash
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never \
uv run --frozen --no-sync pytest -q
```

Because `--no-sync` deliberately skips project-environment synchronization, uv created only a
fresh virtual-environment shell and did not install the project or its development dependencies.
The executable resolved for `pytest` was outside the fresh project environment, and collection
stopped with 140 errors; the first concrete error was:

```text
ModuleNotFoundError: No module named 'mke'
```

The wrapper then used zsh's read-only variable name `status` while trying to retain the subprocess
exit value. That secondary controller error prevented the wrapper from persisting its intended
exit field, but it does not erase or replace the authoritative pytest failure.

Classify the stopped run as an exact-main environment-preparation and controller-observability
failure. It is not:

- a product runtime, retrieval, Evidence, Publication, CLI, MCP, schema, or dependency regression;
- a test assertion failure after successful collection;
- a failure of the reviewed release tree or merge-tree equality;
- a transcription, model, real-ASR, comparison, or quality result;
- Task 10 completion or release readiness.

The failed exact-main worktree, its incomplete `.venv`, raw stdout/stderr, seal, tracked inventory,
BLOCKED record, and complete ledger inventory remain immutable non-acceptance history. They must
not be repaired in place, retried, or reused as acceptance input.

The authority sequence for a fresh project checkout is:

```text
exact merged source and lock
-> one explicit locked offline environment sync
-> project-environment and controller self-check
-> no-sync proof gates
-> retained exact-main ledger
-> separate publication authorization
```

This amendment supersedes only the missing environment-preparation boundary between Task 10
Step 1 and Task 10 Step 2, plus the controller exit-code capture used by the exact-main proof. It
does not change Task 7 results, Task 8 or Task 9 history, the release scope, dependency graph,
`uv.lock`, product source, tests, runtime behavior, canonical Evidence, release claims, or Task 11
publication authority.

### C0 — Land And Independently Review This Amendment

Create a new short-lived plan-repair branch from the exact current `origin/main` merge commit
`168181cb4eae7ecd430efe723663f4993bff8d4f`. Do not amend, rebase, or reuse the merged release
branch as the public source of this correction.

Before the write, require:

- exact base HEAD and tree:
  `168181cb4eae7ecd430efe723663f4993bff8d4f` /
  `8910be7b673d8483e0b1a9deb3f9600b80074712`;
- clean worktree and index;
- package identity `0.1.5`;
- existing implementation plan SHA-256
  `743f872dfc2ebe51f1cb4f9382668567a6dd18b2d7001460d84a8dc4df9841c9`;
- design specification SHA-256
  `260b178bcac6255d7f3a7ad1a29272bca45234e1a5599939609147ff320da48e`;
- `uv.lock` SHA-256
  `1f2e215c08fefc9fe60b2a22467fadd546af2da13de0926282515d2211ffcab9`;
- all nine protected hashes remain exact;
- the first Task 10 stopped ledger and worktree remain present and unchanged;
- no local or remote `v0.1.5` tag and no GitHub Release `v0.1.5`.

Requirements:

- modify only
  `docs/superpowers/plans/2026-07-28-v0-1-5-release-closeout-implementation.md`;
- insert this complete amendment immediately before
  `## Task 10: Re-Prove Fresh Exact Main`;
- retain one Markdown separator around the inserted block;
- preserve every preexisting plan byte outside that insertion;
- preserve the design specification, `uv.lock`, source, tests, release documentation, canonical
  evidence, fixtures, and historical release bytes exactly;
- verify source/extracted-block byte equality and SHA-256, inverse reconstruction of the parent
  plan, balanced fences, unique Amendment C and C0–C7 headings, unchanged Task 0–13 heading
  sequence, complete no-index/cached/committed diff, marker and credential scan, range
  `git diff --check`, one-path scope, one-commit ancestry, and clean final state;
- perform no environment sync, cache operation, test, build, proof, model operation, observation,
  comparison, GitHub mutation, publication, tag, Release, or cleanup action;
- terminal stop for independent actual plan-diff review.

Use branch:

```text
codex/v0-1-5-exact-main-proof-plan
```

Use commit message:

```text
docs(plan): prepare fresh exact-main environment
```

The amendment creates a new reviewed plan candidate. C1 must not begin until the actual committed
plan diff is independently review-clean.

### C1 — Publish And Merge The Exact Plan Repair

After the C0 actual diff is review-clean, re-prove:

- local branch HEAD/tree and clean index/worktree;
- the one-path C0 diff and exact amendment source identity;
- current `origin/main` still equals the C0 base;
- no matching remote branch or open PR exists;
- the first Task 10 failed worktree and ledger remain unchanged;
- no `v0.1.5` tag or GitHub Release exists.

Push normally without force and create one Draft PR to `main`. The public-neutral PR body must
state:

- the exact Task 10 failure mechanism;
- that the product/retrieval/runtime tree did not regress;
- that the sole tracked change is a release-proof plan correction;
- the new locked offline environment-preparation order;
- the controller exit-capture correction;
- preserved failure history and non-claims;
- pending hosted checks, exact-tree review, squash merge, fresh exact-main proof, and separate
  publication authority.

Read back the persisted title, body bytes, Draft/open state, base, head branch, head SHA, URL, and
complete check inventory. Require the PR head to equal the independently reviewed C0 HEAD.

After all required checks are terminal-success and there are no actionable reviews, comments, or
threads:

1. reconcile the persisted PR body to the actual hosted state;
2. read repository rules and merge settings;
3. require mergeable/clean state and exact reviewed/checks head equality;
4. mark Ready and read back;
5. squash merge without changing the reviewed content;
6. require the merge tree equals the reviewed C0 tree exactly;
7. accept repository-configured server-side remote-branch deletion;
8. read the complete post-merge check inventory on the amendment merge SHA.

Any new substantive diff, failed check, unresolved finding, base movement, tree mismatch, ambiguous
merge state, or publication artifact is terminal. Do not repair, repush, or merge a changed branch
without a new bounded authority review.

### C2 — Retain Both Historical Failure Layers

Before creating a new proof checkout, freeze a read-only recovery record that binds:

- the original reviewed release HEAD/tree;
- PR #96 merge commit/tree and post-merge checks;
- the first Task 10 `EXACT_MAIN_SEAL`;
- the failed pytest argv, first concrete error, stdout/stderr digests, BLOCKED-record digest, and
  ledger-inventory digest;
- the secondary `status` variable controller defect;
- the passed B1–B3 recovery-summary digest
  `97367d9ec8c76388bc59a92de92a7457b6e9ef050a7202c34658a3e2ad89ec6b`, used only to prove
  that the locked cache warm and a later offline transcription sync completed before Task 7;
- the Amendment C reviewed HEAD/tree, PR identity, merge commit/tree, and post-merge checks;
- exact plan, specification, lock, and nine protected identities;
- absence of any Task 10 acceptance summary and absence of `v0.1.5` publication.

The record must classify the first attempt as:

```text
product_regression=false
environment_preparation_missing=true
controller_exit_capture_invalid=true
task_10=not_accepted
retry_of_failed_worktree=forbidden
```

Do not copy results from either the branch proof or failed exact-main proof into the new acceptance
ledger. Only immutable identities and explicit non-acceptance classifications may be referenced.

### C3 — Create A Brand-New Exact-Main Proof Checkout

Create a new detached, task-owned worktree at the Amendment C merge commit. It must use a new
physical worktree path and a new absent physical ledger path. Do not reuse:

- the first Task 10 worktree or its `.venv`;
- the release-branch worktree or project environment;
- any prior constraints file, wheel, receipt, claim, candidate, log, gate output, or summary;
- any prior Task 7 or Task 10 controller invocation count.

Require and retain:

- exact current `origin/main` HEAD and tree;
- detached HEAD at that exact commit;
- clean index and worktree;
- package identity `0.1.5`;
- exact plan, design specification, `uv.lock`, and nine protected hashes;
- absence of untracked repository outputs before environment preparation;
- lexical and physical absence of `.venv` before environment preparation;
- no local or remote `v0.1.5` tag and no GitHub Release `v0.1.5`;
- a new `EXACT_MAIN_C_SEAL` containing complete tracked inventory and digests;
- an explicit declaration that, after C6 passes, `EXACT_MAIN_C_SEAL` is the current
  `EXACT_MAIN_SEAL` consumed by Task 11 and the failed first-attempt seal remains historical only;
- a call-owned ledger root exported privately as `EXACT_MAIN_C_LEDGER`;
- the exact physical CPython 3.13.12 interpreter already approved by Task 7 and B1–B3, bound as
  `APPROVED_PROJECT_PYTHON` by path, resolved identity, version, implementation, mode, size, device,
  inode, and digest; its private path remains ledger-only and is not copied into public text;
- the exact approved uv 0.11.7 executable bound as `APPROVED_UV` by resolved path, version, mode,
  size, device, inode, and digest, with `command -v uv` required to resolve to that same executable
  inside the controller;
- a call-owned proof-controller subprocess launched with `/bin/zsh -f`; its launcher enumerates
  and removes every inherited environment variable whose name matches `UV_*`, plus
  `VIRTUAL_ENV`, `PYTHONHOME`, and `PYTHONPATH`, before adding only `UV_OFFLINE=1`,
  `UV_PYTHON_DOWNLOADS=never`, and `UV_NO_CONFIG=1`; the removed-name inventory and the exact
  resulting three-name `UV_*` set are retained, while the caller's original environment remains
  unchanged;
- explicit proof that the normalized controller has no inherited project, workspace, Python,
  cache, config, group, extra, editable, install-suppression, no-sync, lock/frozen, env-file,
  source, index, or find-links routing, including the formerly hazardous
  `UV_PROJECT_ENVIRONMENT`, `UV_PROJECT`, `UV_WORKING_DIR`, `UV_PYTHON`, `UV_CACHE_DIR`,
  `UV_CONFIG_FILE`, `UV_NO_DEV`, `UV_NO_DEFAULT_GROUPS`, `UV_NO_GROUP`, `UV_NO_EDITABLE`,
  `UV_NO_INSTALL_PROJECT`, and `UV_NO_INSTALL_WORKSPACE`;
- every direct C4–C6 outer uv command uses `--no-config` and the exact bound
  `APPROVED_PROJECT_PYTHON`, while every intentionally nested uv child inherits
  `UV_NO_CONFIG=1`;
- no network, model, ASR, comparison, observation, or publication action.

Before environment preparation, materialize one exact executable runner at the absent path
`$EXACT_MAIN_C_LEDGER/gate-runner.zsh`. Record its bytes and SHA-256 before its first use. The
runner is outside the repository, is never sourced into the controller, and is the only primitive
authorized to execute a C4–C6 child gate. Every use must invoke it as
`/bin/zsh -f "$EXACT_MAIN_C_LEDGER/gate-runner.zsh" ...`; direct shebang execution is forbidden:

```bash
#!/bin/zsh
set -euo pipefail

test "$#" -ge 4
gate_name="$1"
expected_exit="$2"
shift 2
test "$1" = "--"
shift
[[ "$gate_name" =~ '^[a-z0-9][a-z0-9._-]*$' ]]
[[ "$expected_exit" =~ '^[0-9]+$' ]]
test "$expected_exit" -le 255
test -n "${EXACT_MAIN_C_LEDGER:-}"
test -n "${APPROVED_PROJECT_PYTHON:-}"
test "$#" -gt 0

stdout_path="$EXACT_MAIN_C_LEDGER/$gate_name.stdout"
stderr_path="$EXACT_MAIN_C_LEDGER/$gate_name.stderr"
exit_path="$EXACT_MAIN_C_LEDGER/$gate_name.exit"
count_path="$EXACT_MAIN_C_LEDGER/$gate_name.count"
argv_path="$EXACT_MAIN_C_LEDGER/$gate_name.argv"
metadata_path="$EXACT_MAIN_C_LEDGER/$gate_name.metadata"

for output_path in \
  "$stdout_path" "$stderr_path" "$exit_path" "$count_path" "$argv_path" "$metadata_path"
do
  test ! -e "$output_path" && test ! -L "$output_path"
done

printf '%s\n' 1 >"$count_path"
printf '%s\0' "$@" >"$argv_path"
started_ns="$("$APPROVED_PROJECT_PYTHON" -c \
  'import time; print(time.time_ns())')"
set +e
"$@" >"$stdout_path" 2>"$stderr_path"
child_exit=$?
set -e
printf '%s\n' "$child_exit" >"$exit_path"
finished_ns="$("$APPROVED_PROJECT_PYTHON" -c \
  'import time; print(time.time_ns())')"
test "$finished_ns" -ge "$started_ns"

stdout_bytes="$(/usr/bin/wc -c <"$stdout_path" | /usr/bin/tr -d ' ')"
stderr_bytes="$(/usr/bin/wc -c <"$stderr_path" | /usr/bin/tr -d ' ')"
argv_bytes="$(/usr/bin/wc -c <"$argv_path" | /usr/bin/tr -d ' ')"
test "$stdout_bytes" -le 16777216
test "$stderr_bytes" -le 16777216
stdout_sha256="$(/usr/bin/shasum -a 256 "$stdout_path" | /usr/bin/awk '{print $1}')"
stderr_sha256="$(/usr/bin/shasum -a 256 "$stderr_path" | /usr/bin/awk '{print $1}')"
argv_sha256="$(/usr/bin/shasum -a 256 "$argv_path" | /usr/bin/awk '{print $1}')"

{
  printf 'gate=%s\n' "$gate_name"
  printf 'expected_exit=%s\n' "$expected_exit"
  printf 'child_exit=%s\n' "$child_exit"
  printf 'started_ns=%s\n' "$started_ns"
  printf 'finished_ns=%s\n' "$finished_ns"
  printf 'duration_ns=%s\n' "$((finished_ns - started_ns))"
  printf 'stdout_bytes=%s\n' "$stdout_bytes"
  printf 'stdout_sha256=%s\n' "$stdout_sha256"
  printf 'stderr_bytes=%s\n' "$stderr_bytes"
  printf 'stderr_sha256=%s\n' "$stderr_sha256"
  printf 'argv_bytes=%s\n' "$argv_bytes"
  printf 'argv_sha256=%s\n' "$argv_sha256"
} >"$metadata_path"

test "$child_exit" -eq "$expected_exit"
```

Before C4 sync, invoke that exact runner once with a fresh gate name:

```bash
/bin/zsh -f "$EXACT_MAIN_C_LEDGER/gate-runner.zsh" \
  runner-pre-sync-self-test 23 -- \
  /bin/sh -c '
    printf "resolved_uv=%s\n" "$(command -v uv)"
    /usr/bin/env | /usr/bin/sort
    exit 23
  '
```

Require retained exit `23`, invocation count `1`, bounded stdout/stderr, exact metadata, and a
parsed child-visible inventory containing exactly `UV_OFFLINE=1`, `UV_PYTHON_DOWNLOADS=never`, and
`UV_NO_CONFIG=1`, no other `UV_*`, `VIRTUAL_ENV`, `PYTHONHOME`, or `PYTHONPATH`, plus a
`resolved_uv` path whose resolved identity equals `APPROVED_UV`. Also require unchanged
parent-controller process state and unchanged repository authority. This establishes that the
same `zsh -f` runner later used for sync, probes, and proof gates retains a nonzero child exit
before it evaluates success and does not regain shell-startup configuration. Any runner
materialization or self-test failure is terminal; do not edit the runner or start environment
preparation in the same exact-main attempt.

Any authority drift is terminal before environment preparation.

### C4 — Prepare The Fresh Project Environment Offline

This step authorizes exactly one project-environment synchronization invocation in the new
exact-main worktree. Invoke it through the exact C3 runner, inside the exact C3 sanitized
controller:

```bash
/bin/zsh -f "$EXACT_MAIN_C_LEDGER/gate-runner.zsh" environment-sync 0 -- \
  uv sync --no-config --locked --extra transcription \
    --python "$APPROVED_PROJECT_PYTHON"
```

This command must run before any `uv run --frozen --no-sync` gate.

Before invocation, bind:

- invocation count zero;
- exact `EXACT_MAIN_C_SEAL`;
- exact `uv` and approved Python identities;
- exact `uv.lock`;
- lexical and physical absence of `.venv`;
- the exact B1–B3 recovery-summary digest and passed cache-warm/offline-sync statuses, without
  importing any prior gate output as current acceptance evidence;
- absence of every C3-listed routing/configuration variable in the call-owned proof-controller
  subprocess;
- exact `--no-config` and `--python "$APPROVED_PROJECT_PYTHON"` command authority;
- network disabled and interpreter download disabled;
- no model-download authorization.

Require:

- invocation count exactly one;
- exit `0`;
- no network access and no interpreter download;
- no package installed into the fresh project `.venv` outside the existing locked project, default
  development-group, and `transcription` extra closure;
- no model download, model construction, media open, fixture consumption, ASR, product proof,
  observation, comparison, or publication;
- `uv.lock`, HEAD, tree, index tree, tracked bytes, protected hashes, and clean porcelain remain
  exact;
- exact argv, duration, exit code, bounded stdout/stderr bytes and digests, and before/after
  authority identities are retained;
- the runner bytes and SHA-256 are re-read immediately before and after the sync and still equal
  the C3 authority.

The sync is environment preparation, not a Task 10 product gate and not release evidence. It
proves only that the already prepared local cache can realize the exact locked project environment
with network disabled. It does not prove cold-cache, empty-cache, air-gapped, or cache-portable
installation.

Immediately after the sync, materialize the following exact probe outside the repository, record
its bytes and SHA-256, and execute it exactly once through the same runner:

```python
from importlib.metadata import version
from pathlib import Path
import shutil
import sys

root = Path.cwd().resolve()
expected_python = (root / ".venv" / "bin" / "python").resolve()
expected_pytest = (root / ".venv" / "bin" / "pytest").resolve()

assert Path(sys.executable).resolve() == expected_python
assert Path(sys.prefix).resolve() == (root / ".venv").resolve()
assert Path(sys.base_prefix).resolve() != Path(sys.prefix).resolve()
pytest_executable = shutil.which("pytest")
assert pytest_executable is not None
assert Path(pytest_executable).resolve() == expected_pytest

import mke
import pytest

assert (root / "src" / "mke") in Path(mke.__file__).resolve().parents
assert (root / ".venv") in Path(pytest.__file__).resolve().parents

expected = {
    "multimodal-knowledge-engine": "0.1.5",
    "pytest": "9.1.1",
    "setuptools": "83.0.0",
    "ctranslate2": "4.8.0",
    "faster-whisper": "1.2.1",
}
observed = {name: version(name) for name in expected}
assert observed == expected, observed

print("exact_main_project_environment=passed")
```

Use the exact top-level invocation:

```bash
/bin/zsh -f "$EXACT_MAIN_C_LEDGER/gate-runner.zsh" environment-probe 0 -- \
  uv run --frozen --no-sync --no-config --no-env-file \
    --python "$APPROVED_PROJECT_PYTHON" \
    python "$EXACT_MAIN_C_LEDGER/environment-probe.py"
```

Re-read the runner bytes and SHA-256 immediately before and after the probe.

Any sync or probe failure is terminal. Do not retry, repair the environment in place, fall back to
the branch `.venv`, permit network, or start Task 10 gates.

### C5 — Re-Prove Controller Exit Capture Through The Prepared Environment

Before the full matrix, invoke the unchanged, hash-bound C3 runner with a new gate name:

```bash
/bin/zsh -f "$EXACT_MAIN_C_LEDGER/gate-runner.zsh" controller-uv-self-test 23 -- \
  uv run --frozen --no-sync --no-config --no-env-file \
    --python "$APPROVED_PROJECT_PYTHON" \
    python -c 'raise SystemExit(23)'
```

Require:

- the six runner output paths are call-owned, absent before invocation, and outside the
  repository;
- the child executes exactly once;
- retained exit value is exactly `23`;
- stdout is empty;
- bounded stderr, stdout, and exit-file bytes and digests are retained;
- the runner bytes and SHA-256 equal the runner proven before C4;
- no read-only-shell-variable error occurs;
- the parent shell's cwd, umask, selected environment variables, signal state, and resource limits
  equal their pre-self-test values;
- repository HEAD/tree/index, tracked bytes, protected hashes, clean porcelain, project
  environment, and locked dependency identities remain exact;

Any failure is terminal. Do not alter the controller and retry in the same exact-main attempt.

### C6 — Run The Complete Task 10 Matrix From Scratch

Only after C2–C5 pass may the complete Task 10 matrix begin.

Requirements:

- create fresh output paths for every gate;
- initialize every Task 10 invocation count at zero;
- run every original Task 10 Step 2 gate in its approved order;
- execute every top-level Task 10 child through
  `/bin/zsh -f "$EXACT_MAIN_C_LEDGER/gate-runner.zsh"` with the unchanged, hash-bound C3 runner and
  its preregistered exact expected exit; expected-negative gates use their approved nonzero exit
  rather than weakening the runner;
- re-read the runner bytes and SHA-256 immediately before and after every child invocation;
- use `UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never` for every top-level repository and model-free gate;
- run every top-level uv command inside the exact C3 sanitized controller environment with
  `--no-config` and the same bound `APPROVED_PROJECT_PYTHON`;
- supersede every top-level repository `uv run` from the original Task 7/Task 10 matrix, including
  commands that were previously plain `uv run`, to the exact prefix
  `uv run --frozen --no-sync --no-config --no-env-file --python "$APPROVED_PROJECT_PYTHON"`;
  preserve the original command, arguments, order, result contract, and expected exit after this
  prefix;
- for the Task 7 Step 4 committed CI body, retain the exact workflow body bytes and SHA-256, apply
  the already approved matrix-placeholder rendering, then mechanically normalize every rendered
  top-level `uv run` occurrence to that same frozen/no-sync/no-config/no-env-file/approved-Python
  prefix; retain the rendered-before and rendered-after bytes, digests, exact normalization diff,
  occurrence count, and proof that no plain rendered `uv run` remains; execute only the normalized
  script, with every other line byte-identical to the approved rendered body;
- treat that normalized Step 4 script as one runner child with expected exit `0`; its internal
  numeric invocation must still exit `1` and match the exact approved negative tuple before the
  script proceeds, so normalization does not weaken the expected-negative authority;
- normalize non-`run` top-level uv commands only by adding their supported `--no-config` and
  `--python "$APPROVED_PROJECT_PYTHON"` options while preserving the original subcommand,
  arguments, order, outputs, and result contract;
- retain the already approved environment logic inside intentional nested consumer, installed,
  compiled-export, and MCP proof controllers; those child-created environments are not rewritten
  into the top-level project `.venv` contract, but every nested uv process must inherit the exact
  controller values `UV_OFFLINE=1`, `UV_PYTHON_DOWNLOADS=never`, and `UV_NO_CONFIG=1`;
- the full pytest gate must resolve to the fresh worktree's `.venv/bin/pytest`;
- do not reuse any branch, Task 7, first Task 10, PR, CI, build, wheel, receipt, constraints,
  compatibility, source-pack, installed-proof, MCP, digest, or summary result as exact-main
  acceptance evidence;
- preserve one-shot source-pack and other terminal-lane invocation limits from Task 7;
- re-read every retained result and digest before aggregation;
- stop at the first failed gate without retry, repair, fallback, substitution, continuation, tag,
  Release, or cleanup;
- retain failures as non-acceptance evidence.

A complete pass must include every original Task 10 item:

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
- remaining immutable, interface, installed-artifact, and documentation gates.

The final summary must bind:

- Amendment C merge commit/tree and complete post-merge checks;
- `EXACT_MAIN_C_SEAL`;
- exact runner bytes/SHA-256 plus pre-sync and post-sync self-test identities;
- C4 sync and environment-probe identities;
- every Task 10 command, duration, exit, bounded output digest, result, and invocation count;
- exact-main wheel and receipt identities per controller;
- exact plan, specification, lock, protected hashes, and final clean state;
- explicit non-claims.

### C7 — Reconcile Public State And Stop Before Task 11

After and only after C6 passes:

1. re-prove current public `main` equals the Amendment C merge commit/tree;
2. re-prove complete post-merge checks are successful;
3. re-prove the exact-main source seal and every retained Task 10 result;
4. bind accepted `EXACT_MAIN_C_SEAL` as the current `EXACT_MAIN_SEAL` consumed by Task 11 while
   retaining the first-attempt seal as historical non-acceptance evidence;
5. confirm local and remote `v0.1.5` tag and GitHub Release remain absent;
6. record each existing persisted PR body byte length and SHA-256, preserve that complete text and
   its original chronology, then append one UTC-Z-dated post-merge closeout section to PR #96 and
   one to the Amendment C PR; each appended section must explicitly record the stopped first Task
   10 attempt, the later Amendment C plan-only correction and merge, the still-later accepted fresh
   exact-main proof, and Task 11 publication remaining pending; no earlier pending sentence may be
   silently rewritten to imply that the later proof existed before either merge;
7. read both persisted bodies back exactly;
8. retain the failed first Task 10 history separately from the accepted Amendment C exact-main
   proof;
9. terminal stop for separate Task 11 tag and GitHub Release publication authorization.

The reconciliation must not add a code or documentation commit, change a tag, create a Release,
publish to PyPI, deploy a service, promote retrieval behavior, rerun an observation/comparison, or
delete retained evidence.

### Acceptance And Non-Claims

Amendment C is accepted only when:

1. C0 lands as an exact one-path plan commit and passes independent actual-diff review;
2. the exact reviewed C0 tree passes hosted checks and squash merges with tree equality;
3. the first Task 10 failure remains unchanged and classified as non-acceptance history;
4. C3 creates a brand-new exact-main worktree and ledger at the Amendment C merge commit;
5. C4 performs exactly one locked offline environment sync before any no-sync proof gate;
6. the C4 probe proves `mke`, `pytest`, and the locked transcription dependencies come from the
   fresh project environment;
7. C5 proves the controller retains a nonzero child exit without a read-only-variable failure or
   process-state leak;
8. C6 reruns every Task 10 gate from scratch and all gates pass;
9. public main, post-merge checks, exact-main proof, protected bytes, and final clean state agree;
10. both relevant PR bodies preserve their historical text and append a truthful dated
    completed/pending lifecycle reconciliation;
11. no Task 11 publication or unrelated lifecycle action occurs.

Stable non-claims:

- no product runtime, retrieval, Evidence, Publication, API, CLI, MCP, schema, dependency, version,
  marker, source, or lock change;
- no reuse of branch proof or failed exact-main results as current acceptance evidence;
- no cold-cache, empty-cache, air-gapped, cache-portability, or cross-machine installation claim;
- no model download, real ASR, transcription-quality, performance, cross-platform, deployment,
  adoption, business-value, or production-readiness claim;
- no comparison result, contextual-retrieval or segmentation conclusion, runtime promotion, PyPI
  publication, hosted service, tag, GitHub Release, or release completion from Amendment C alone.

Task 11 remains the only authority for annotated tag creation, tag push, zero-asset GitHub Release,
public archive verification, and final release closeout.

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
