# v0.1.5 Release Closeout Design

Status: approved design source; pending mechanical landing and actual-diff review.

Date: 2026-07-28

Planning baseline: `33106ec2cfeabf6c1c448fad57fb2489e3712543`

Planning tree: `69b8f252a009f714006aa4907aa5254ec966a0ae`

## Context

The current mainline has two completed capability groups that are not yet represented by a
public version boundary:

1. MCP context completeness:
   - bounded search-selection completeness;
   - continuation of selected results;
   - exact active-Evidence reconstruction in bounded UTF-8 chunks;
   - an exact current ten-tool MCP inventory; and
   - installed-wheel and consumer proof on supported Python lanes.
2. Deterministic equal-score retrieval ordering:
   - semantic Source-byte-bound secondary keys for default FTS5 and CJK paths;
   - revision-2 cursor behavior;
   - preserved membership, primary scores, non-tied order, active-only authority, and
     compatibility evidence; and
   - retained canonical evidence that can be pure-validated without replay, observation, or
     publication.

At design approval:

- local `HEAD`, `main`, and `origin/main` were equal to the planning baseline;
- the main worktree and index were clean;
- `v0.1.4` was the latest public, non-draft, non-prerelease GitHub Release;
- package, module, and root-lock release identity remained `0.1.4`;
- no `v0.1.5` tag or GitHub Release existed; and
- no open public pull request was part of the release candidate.

An unfinished retrieval-coverage comparison asks a different question: whether Evidence
granularity or contextual retrieval changes retrieval completeness on a frozen corpus. It is
excluded from this release. None of its branches, worktrees, fixture bytes, artifacts, observations,
or results may be read, copied, normalized, modified, deleted, or used as release evidence.

## Release Decision

Publish the already-merged, already-proved Agent-consumption contract as `v0.1.5`.

This is release closeout, not feature expansion. The release changes version identity, release
presentation, documentation routing, and release verification only. It does not create or promote
new retrieval behavior.

The release headline is:

> An Agent can determine whether bounded MCP search selection is complete, continue selected
> results, reconstruct exact active Evidence in bounded UTF-8 chunks, and receive deterministic
> equal-score order across equivalent local stores.

The release keeps MKE local-first, Evidence-authoritative, and Agent-callable. It does not turn MKE
into a hosted RAG service, a general Agent runtime, or a retrieval-quality claim.

## Alternatives Considered

### Maintenance only

Keeping package identity at `0.1.4` would avoid immediate release work, but public identity would
remain behind the completed MCP and deterministic-order contracts. A later release would have a
wider and less coherent change set.

### Release the current mainline, then resume the comparison

This creates one bounded version for the completed consumer contract and preserves the unfinished
comparison as comparison-only work. Existing tests, CI, canonical evidence, and installed
consumer proofs can support the release without runtime changes.

### Wait for the comparison

This would couple a stable consumer contract to an unresolved experiment and increase pressure to
promote comparison-only results. Fewer version numbers would not compensate for the mixed evidence
boundary.

The selected alternative is the second one.

## Goals

- Publish package and module version `0.1.5` from one exact verified merged-main commit.
- Make MCP selection completeness and exact Evidence recovery the primary current release story.
- Make deterministic equal-score ordering a supported mechanism invariant without claiming
  relevance improvement.
- Preserve Source, Run, Publication, Evidence, SQLite, Search, Ask, CLI, and local stdio MCP
  authority.
- Preserve legacy and strict-v1 compatibility while documenting the additive ten-tool inventory.
- Preserve all canonical retrieval-order bytes and historical evaluation records.
- Prove one exact wheel per proof controller across that controller's supported Python lanes.
- Publish an annotated `v0.1.5` tag and public zero-asset GitHub Release.
- Verify the public source archive through an exact Git-less allowlist.
- Record immutable release facts in a separate post-release docs-only closeout.

## Release Value

Primary developer persona:

> An Agent/tooling engineer evaluating a local-first knowledge component who wants a bounded stdio
> MCP contract, exact Evidence recovery, cache-warmed offline installed-wheel verification, and
> proof that equal-score ordering does not depend on opaque generated IDs.

Primary developer outcome:

> From an acquired source archive or checkout with `uv`, supported Python interpreters, and the
> lock cache already prepared, one documented stdio flow can search, observe the completeness
> state, continue if needed, reconstruct exact Evidence bytes, and verify the final digest without
> a hosted service.

## Allowed Claims

| Area | Allowed `v0.1.5` claim | Required authority |
|---|---|---|
| MCP search completeness | `search_library_v2` reports `complete`, `more_available`, or `capped`, including per-item excerpt completeness and bounded continuation. | MCP contract tests, current ten-tool inventory, sealed-source two-interpreter consumer proof |
| Exact Evidence recovery | `read_evidence_v1` reconstructs active Evidence in gap-free, non-overlapping UTF-8 chunks and reports a final SHA-256. | MCP completeness proof and active-only authority tests |
| Compatibility | Legacy and v1 calls remain available; oversized requests retain typed recovery. | Interface/schema tests and consumer proof |
| Local-first consumption | The verified consumer path is local stdio MCP and an installed wheel in a prepared cache-warmed environment; no hosted service is required. | Python 3.12/3.13 installed-wheel proof built from sealed release source |
| Deterministic FTS ties | Equal primary-score FTS rows use the documented semantic Source-byte-bound secondary key. | Revision-2 unit/integration tests and canonical evidence |
| Deterministic CJK ties | Equal-overlap CJK rows use the documented semantic Source-byte-bound Python key. | CJK tests and canonical evidence |
| Cursor behavior | Revision-2 cursors invalidate incompatible prior ordering state. | Cursor/interface tests |
| Preserved semantics | Candidate membership, primary scores, non-tied ordering, active-only Publication authority, and public result schema remain unchanged. | Differential compatibility evidence |
| Canonical evidence | Five committed retrieval-order artifacts can be pure-validated with observation, replay, builders, recorders, and publication fenced. | Canonical evidence test and production validators |
| Maintenance | The already-merged GitHub Actions pin update is release maintenance, not a product/runtime headline. | Mainline diff and hosted checks |

## Explicit Non-Claims

The release does not claim:

- exhaustive corpus-wide search or total-match counting;
- semantic summarization or answer generation;
- relevance, recall, precision, latency, throughput, or performance improvement;
- segmentation or contextual-retrieval quality;
- a development or holdout result from the unfinished comparison;
- runtime promotion of any comparison;
- GraphRAG;
- dense retrieval, RRF, or reranker runtime promotion;
- OCR runtime;
- an Agent loop;
- HTTP, SaaS, a hosted service, or new provider support;
- a new dependency;
- PyPI publication, deployment, production adoption, user count, or business impact;
- cold-cache, empty-machine, or air-gapped package acquisition or installation;
- a portable fixed SQLite query plan across all SQLite/FTS builds; or
- one unified display order across different retrieval strategies.

## Existing Authority and Reuse

The release reuses:

- the current MCP, retrieval, Evidence, Publication, and active-only runtime;
- the exact current ten-tool MCP contract;
- the MCP context-completeness proof workflow, which builds one wheel from sealed source and proves
  that wheel on Python 3.12 and 3.13;
- `consumer_source_pack_proof.py` for an external installed-wheel claim and canonical candidate
  receipt;
- `compiled_library_export_proof.py` for its own explicit or source-built wheel proof;
- `release_consumer_smoke.py`, updated only for current release identity;
- current CI strict-live numeric failure routing and temporary retrieval-order compatibility
  record/validate flow;
- five committed canonical retrieval-order artifacts and their pure validator;
- the fixed-profile query-plan fixture as structural evidence only;
- `scripts/release_presentation_audit.py` and its tests, extended to make `v0.1.5` current while
  preserving the historical `v0.1.4` contract; and
- existing release verification, release note, README, changelog, and documentation-index
  patterns.

No new release framework, package publisher, hosted environment, provider, or artifact type is
required.

`retrieval_order_installed_proof.py` remains historical evidence, not a current `v0.1.5` gate.
Its candidate receipt is bound to the committed canonical `candidate_seal.head`
`7af0ba1ecf662e9bebb125c85b429e675233fbe4`, while a new release receipt must bind the new clean
release HEAD. Relaxing that comparison, rewriting canonical evidence, or re-observing
development/holdout solely for this release is forbidden.

## Release Architecture

```text
current clean main
    |
    v
release-only branch/worktree
    |
    +--> version identity + root lock entry
    +--> release presentation + v0.1.5 release note
    +--> presentation/version regression tests
    |
    X--> no production runtime behavior change
    X--> no MCP schema change
    X--> no canonical evidence rewrite
    X--> no unfinished-comparison input
    |
    v
reviewed release tree
    |
    +--> source-pack proof builds one receipt-bound candidate wheel
    |       |
    |       +--> release consumer smoke
    |       +--> optional explicit-wheel compiled Library export proof
    |
    +--> independent MCP completeness proof builds from the same sealed source
    |       |
    |       +--> one proof-owned wheel, Python 3.12 + Python 3.13
    |
    +--> compiled Library proof builds from the same sealed source when an
    |    explicit candidate wheel is not used
    |
    +--> full tests / Ruff / Pyright / CI parity
    +--> canonical pure validation
    +--> temporary strict-live compatibility record + validate
    |
    v
Draft PR -> reviewed exact head -> squash merge
    |
    +--> require reviewed tree == merge tree
    |
    v
exact-main rebuild and fresh proof
    |
    v
local annotated tag ready
    |
    v
remote tag visible, Release absent
    |
    v
zero-asset GitHub Release visible, unverified
    |
    v
public archive smoke + archive identity
    |
    v
post-release docs-only immutable record + retrospective
    |
    v
separate comparison-resume decision
```

The release is an artifact and presentation change around an unchanged product runtime. The
important coupling is between release identity and the existing consumer proofs. It must not create
coupling to unfinished comparison work.

## Release State Machine

```text
PUBLIC_SPEC_LANDED
    |
    | actual spec diff clean
    v
IMPLEMENTATION_PLAN_APPROVED
    |
    v
RELEASE_BRANCH_ACTIVE
    |
    | version/docs/tests only
    v
CANDIDATE_SEALED
    |
    | all local proof gates pass
    v
DRAFT_PR
    |
    | exact-head hosted checks + review clean
    v
MERGE_APPROVED
    |
    | reviewed tree == merge tree
    v
MERGED_NOT_PUBLISHED
    |
    | fresh exact-main proof matrix
    | separate publication approval
    v
LOCAL_TAG_READY
    |
    | push exact annotated tag and read back
    v
REMOTE_TAG_VISIBLE_RELEASE_ABSENT
    |
    | create zero-asset Release and read back
    v
RELEASE_VISIBLE_UNVERIFIED
    |
    | archive smoke and identity pass
    v
PUBLICATION_VERIFIED
    |
    | docs-only immutable closeout + retrospective
    v
RELEASE_CLOSED
```

Forbidden transitions:

- `PUBLIC_SPEC_LANDED -> RELEASE_BRANCH_ACTIVE` without actual-diff review and an approved
  implementation plan.
- `CANDIDATE_SEALED -> LOCAL_TAG_READY` without PR review and merge-tree equality.
- `MERGED_NOT_PUBLISHED -> LOCAL_TAG_READY` without separate publication authority.
- Any tracked, index, HEAD, tree, or source-byte drift after `CANDIDATE_SEALED` -> reuse of any
  candidate wheel, receipt, log, or proof. Repair requires a reviewed commit, a fresh seal, and the
  complete matrix from the beginning.
- `REMOTE_TAG_VISIBLE_RELEASE_ABSENT` or `RELEASE_VISIBLE_UNVERIFIED` -> blind retry, tag movement,
  tag deletion, or Release mutation without persisted-state readback and fresh authority.
- Any state -> comparison promotion.
- Any failure state -> automatic evidence regeneration, hidden proof rerun, or reuse of a failed or
  preexisting call-owned output path.

## Exact Maximum Implementation Allowlist

The implementation plan may only shrink this default-deny maximum allowlist. A path not listed
below requires a separately reviewed design amendment. Global version replacement is forbidden.

- `pyproject.toml`
- `src/mke/__init__.py`
- `uv.lock`
- `tests/test_version_identity.py`
- `tests/test_bootstrap.py`
- `tests/proof/test_mcp_deployment_client.py`
- `scripts/release_consumer_smoke.py`
- `tests/scripts/test_release_consumer_smoke.py`
- `scripts/release_presentation_audit.py`
- `tests/scripts/test_release_presentation_audit.py`
- `tests/evaluation/test_mcp_context_completeness_documentation.py`
- `tests/evaluation/test_dense_documentation.py`
- `tests/interfaces/test_cli_mcp.py`
- `README.md`
- `README_CN.md`
- `CHANGELOG.md`
- `docs/README.md`
- `docs/how-to/verify-release.md`
- `docs/tutorials/getting-started.md`
- `docs/how-to/use-mke-mcp.md`
- `docs/how-to/run-mcp-context-completeness-proof.md`
- `docs/how-to/prepare-local-embeddings.md`
- `docs/how-to/evaluate-dense-retrieval.md`
- `docs/how-to/enable-cjk-retrieval.md`
- `docs/how-to/evaluate-numeric-retrieval.md`
- `docs/how-to/run-chinese-retrieval-evaluation.md`
- `docs/reference/cli.md`
- `docs/reference/mcp-contract.md`
- new `docs/releases/v0.1.5.md`

`docs/reference/mcp-contract.md` may change only when a focused release-truth RED proves a missing
current, upgrade, or acquisition boundary. No tool schema or runtime-contract edit is authorized.

Historical direct-audio and `v0.1.4` literals in other files remain immutable unless the exact
current-layer audit classifies a listed command as current.

`tests/evaluation/test_dense_documentation.py` may change only its current-wheel literal or
assertion from `0.1.4` to `0.1.5`. Other direct-audio and historical `0.1.4` documentation tests
remain frozen.

The release presentation has two layers:

- current mutable layer: `v0.1.5`;
- immutable historical layer: `v0.1.4`.

The implementation must not introduce a generalized multi-release framework.

## Protected Paths and Bytes

The following are immutable for this release:

- all production runtime behavior outside `src/mke/__init__.py`;
- MCP tool schemas and current tool behavior;
- the five canonical retrieval-order artifacts:
  - `benchmarks/retrieval/retrieval-order-v1-development-freeze.json`,
    SHA-256 `0d8761037e9132461a1d6bbf2eac0a39471dfaa38c65acbdc2400a87ff8bffd8`;
  - `benchmarks/retrieval/retrieval-order-v1-holdout-receipt.json`,
    SHA-256 `8f390ada3632c12527eb75747a2ce21721317fffdd30bd9fc177e8f305dc3203`;
  - `benchmarks/retrieval/retrieval-order-v1-artifact.json`,
    SHA-256 `104a41a6aa0c719313d508c79d00886a18483bbf3eeeadcdbc8899dd927283c1`;
  - `benchmarks/retrieval/retrieval-order-v2-compatibility-attempt.json`,
    SHA-256 `df18d9738548fa33af5c7f76dfa26e89a721f1c08a2df0e034a7688c67e81604`;
  - `benchmarks/retrieval/retrieval-order-v2-compatibility.json`,
    SHA-256 `f9a5883f3ac47652cbd18ef0bb08b61ceb00065955a3db575df0fd41689240ba`;
- frozen historical evaluation artifacts;
- the fixed-profile query-plan fixture,
  SHA-256 `1f6a70a69edb9a3b182e21a9b125a37d81ed4dca869c16d1f5d5b807554ffdc1`;
- `docs/releases/v0.1.4.md`,
  SHA-256 `fe3a6ce74d0e037a1a5fa33eba1df941c2130981e100d424f7756b34b2724248`;
- the frozen v0.1.4 eight-tool fixture,
  SHA-256 `f372f9733c8c352d7610d16412d9f98304dde325dd235ce81e30b4c6253cc3cd`;
- the current ten-tool MCP completeness fixture,
  SHA-256 `48b3b6c3a8d17af460ceff23ae64e619486f5792eb77b35416841e73a8190561`;
- completed historical v0.1.4 design, plan, review, tag, and release records; and
- every branch, worktree, fixture, and retained byte owned by unfinished comparison work.

## Lockfile Rule

`uv.lock` may change only at the root editable package version. Any dependency name, version,
source, marker, hash, resolution, or transitive package drift is a terminal stop.

## Implementation Shape

1. Write targeted RED tests for exact `0.1.5` identity and current release presentation.
2. Update the minimum version and presentation paths.
3. Preserve the historical `v0.1.4` audit contract:
   - historical note and facts remain valid;
   - current release assertions move to `v0.1.5`;
   - tests independently prove both layers;
   - current release-facing and current-wheel inventories point at
     `docs/releases/v0.1.5.md`;
   - `docs/releases/v0.1.4.md` moves into the historical inventory and retains its exact
     `0.1.4` wheel command and bounded-direct-audio contract;
   - `_audit_v014_contract` remains strict while a separate `_audit_v015_contract` freezes MCP
     completeness, deterministic order, compatibility, and non-claim terms; and
   - the already-merged Actions pin update is maintenance only.
4. Repair release-facing information architecture without changing product behavior:
   - exactly one H1 in each README and the documentation index;
   - the current `v0.1.5` story appears before historical capability records;
   - the tutorial and MCP how-to expose one primary v2 flow using the real `request` envelope,
     completeness branch, opaque continuation, exact chunk reconstruction, and final digest
     verification;
   - legacy and v1 examples move under compatibility instead of remaining the primary Agent flow;
   - the CLI reference names the exact ten-tool inventory and the real global-option order
     `mke --db <path> mcp ...`;
   - release proof codes receive a public `code -> problem/cause/next action` troubleshooting
     table without changing proof output schemas; and
   - `docs/how-to/verify-release.md` exposes a short evaluator path first, then the maintainer
     authority workflow, then immutable historical release records.
5. Run focused GREEN, adjacent release tests, Ruff, and Pyright.
6. Seal the candidate HEAD and tree before expensive proof.
7. Run the complete proof matrix without tracked writes. Different proof controllers may build
   different private wheels from the same sealed source; each controller must prove one exact
   wheel across its own interpreter cells. Cross-controller wheel-byte equality is not required
   or claimed.
8. If HEAD, tree, index, or any tracked byte changes after sealing, invalidate every branch
   candidate wheel, receipt, log, and proof result. Commit and review the repair, reseal, and rerun
   the complete matrix from the beginning. No lane-local result may be reused.
9. Obtain independent actual-diff review before publication.

There is no production implementation task. If a required test can pass only by changing runtime
retrieval, MCP behavior, Evidence semantics, canonical artifacts, or dependencies, stop.

## Test and Proof Matrix

### Identity and presentation

- exact `pyproject.toml`, `mke.__version__`, package metadata, and root lock entry: `0.1.5`;
- root lock change only;
- exact wheel filename and installed version;
- exactly one H1 in README EN/CN and docs index, with current release first;
- aligned README EN/CN current capability sections and ten-tool count;
- changelog `[0.1.5]` entry;
- new public-neutral release note with Try it, Upgrade, acquisition, proof, and non-claim sections;
- historical `v0.1.4` release note and contract preserved;
- primary MCP v2 path uses the real request envelope and covers
  `complete|more_available|capped`, cursor-only continuation, chunk offsets, and final SHA-256;
- CLI reference and `mke mcp --help` agree on ten tools and global option ordering;
- database, data, and schema migration is `none`;
- valid legacy/v1 bounded calls remain compatible;
- exact-inventory consumers explicitly migrate from eight tools to ten;
- old cursors are not upgrade authority; consumers restart the initial call under the current
  process, policy, and active set;
- public acquisition says source archive or checkout only; GitHub Release supplies no wheel and
  PyPI is absent;
- “offline” is always qualified as cache-warmed proof execution, not cold install;
- proof stable codes map to documented operator action without changing proof JSON;
- release-facing shell blocks pass deterministic command-shape and syntax checks;
- an evaluator rehearsal receipt records preconditions, user-visible step count, first verified
  value, and observed local elapsed time without telemetry or a public performance claim; and
- no private paths, task labels, tokens, or unverified metrics.

### Product and compatibility

- full `pytest`;
- Ruff;
- Pyright;
- package build;
- product proof and demo;
- local knowledge proof;
- Evidence provenance proof;
- model-free direct-audio proof only;
- no real ASR rerun;
- legacy and v1 MCP compatibility; and
- exact current ten-tool inventory.

### Retrieval-order evidence

- canonical five-artifact hash freeze;
- canonical pure validation with replay, observation, build, record, and publication barriers;
- fixed-profile query-plan structural unit test with nonmatching-profile routing;
- strict-live numeric control exits `1` with exactly:
  `retrieval_numeric_fixture_invalid / protocol-bound input identity mismatch /
  restore_numeric_protocol_inputs`;
- the frozen numeric protocol is not refreshed to turn that expected negative into success;
- call-owned temporary strict-live compatibility `record` followed by pure `validate`;
- exact seven-family membership, score-hex, non-tied-pair, metric, gate, and verdict deltas equal
  zero; and
- no canonical record or evidence rewrite.

### Sealed-source installed proof

1. `consumer_source_pack_proof.py --candidate-output ...` creates one receipt-bound candidate
   wheel in a call-owned physical no-follow-safe path.
   - The path is lexically valid, physical, task-owned, and absent before invocation.
   - Exactly one wheel may be visible afterward.
   - A preexisting output, lock or constraint mismatch, or source-seal drift is terminal.
   - The implementation plan states whether call-owned outputs are retained for review or removed
     only after closeout.
   - The historical `--attempt-claim` option is forbidden for `v0.1.5`.
2. `release_consumer_smoke.py` consumes that exact wheel.
   - The external wrapper probes both supplied and installed interpreters.
   - It requires the exact minor set `{3.12, 3.13}`.
   - It records resolved executable plus `sys.version_info[:3]` in the private proof ledger.
   - It rechecks interpreter identity after environment creation.
   - No public proof schema changes.
3. `compiled_library_export_proof.py --mke-wheel` may consume that exact wheel. If the controller
   instead builds its own wheel, it remains bound to the same sealed clean source and one exact
   wheel across Python 3.12 and 3.13.
4. MCP completeness proof independently builds one wheel from the same sealed clean source and
   proves that exact wheel on Python 3.12 and 3.13 under exact lock-derived constraints.
5. Each proof records its own wheel name, size, SHA-256, or proof receipt where the existing schema
   supports it. Cross-controller wheel-byte equality is not required or claimed.
6. `retrieval_order_installed_proof.py` is not run with the `v0.1.5` receipt. Current
   deterministic-order authority is runtime tests, canonical pure validation, temporary
   compatibility record/validate, and hosted CI.

Every expensive branch or exact-main checkout proof lane uses the same external Git source seal:

- record exact HEAD, tree, branch, complete porcelain-v1 state, and expected version;
- require a clean worktree and index before proof;
- keep constraints, wheels, receipts, logs, and candidate outputs outside the repository;
- reread the same HEAD, tree, and clean state immediately after proof; and
- invalidate all candidate proof results and stop on any source-seal drift.

This wrapper supplies source authority without changing a proof script or adding a new proof
schema. It does not apply to the Git-less public archive.

For archive MCP proof, the wrapper instead binds:

- downloaded archive descriptor SHA-256;
- safe extraction inventory;
- exact equality with the prerecorded tagged-tree manifest;
- `uv.lock` and exported constraints digests;
- a fresh absent physical candidate-output path;
- exactly one produced wheel; and
- unchanged pre/post archive source inventory.

The locked environment and all build or proof outputs live in call-owned paths outside the
extracted archive. Archive proof must not require HEAD, branch, porcelain state, or synthetic
`.git`.

### Hosted and publication proof

- Draft PR exact head and body readback;
- all hosted checks terminal success;
- no unresolved actionable review, comment, or thread;
- reviewed tree equals squash-merge tree;
- exact-main reruns fresh candidate and proof controllers without reusing branch outputs;
- annotated `v0.1.5` tag targets the exact merge commit;
- public GitHub Release is non-draft, non-prerelease, and has zero assets;
- tag archive tree equals tagged tree;
- archive environment succeeds with `uv sync --locked`;
- explicit `uv build --wheel --out-dir <fresh-absent-physical-path>` produces exactly one archive
  wheel;
- no archive wheel is required to equal any Git-built candidate wheel byte-for-byte.

The exact Git-less archive allowlist is:

- product proof;
- demo;
- local knowledge proof;
- Evidence provenance proof;
- model-free direct-audio proof;
- release presentation audit;
- archive-built wheel consumed by `release_consumer_smoke.py`;
- `mcp_context_completeness_proof.py` only when its documented supported interpreters and
  cache-warmed lock-derived constraints are available;
- native `mke library export` followed by `compiled_library_export_consumer.py`; and
- exactly these deterministic-order tests:
  - `tests/adapters/test_sqlite_fts_order.py`;
  - `tests/adapters/test_sqlite_cjk_order.py`;
  - `tests/application/test_mcp_cursor.py`;
  - `tests/evaluation/test_retrieval_order_canonical_evidence.py`.

The exact Git-less archive denylist is:

- `consumer_source_pack_proof.py`;
- `compiled_library_export_proof.py`, including `--mke-wheel`;
- `retrieval_order_installed_proof.py`;
- temporary compatibility record or replay;
- any other Git historical materialization;
- synthetic `.git`;
- real ASR or model download; and
- unfinished comparison access.

## Error and Rescue Registry

| Codepath | Failure | Result | Retry policy | Public effect |
|---|---|---|---|---|
| version update | dependency or lock resolution drifts | terminal stop | no automatic retry | no candidate |
| release presentation audit | history rewritten or current claim missing | test failure | repair only after review | no candidate |
| candidate build | build fails or unexpected artifact appears | terminal stop | no hidden second build | no candidate |
| source-pack candidate output | lexical path is invalid or output is preexisting | fail closed | use only a plan-approved fresh call-owned physical path | no candidate receipt |
| source-pack interpreter lanes | resolved or installed minor set is not exactly `{3.12, 3.13}` | fail closed | no path-distinct substitute | no installed proof |
| MCP proof candidate output | output is preexisting, not physical or owned, contains anything before start, yields other than one wheel, or lock constraints drift | fail closed | no substitution or reuse | no MCP proof |
| installed proof | interpreter, profile, or wheel identity mismatch | fail closed | no substitute within that proof lane | no proof claim |
| proof controller stable code | controller returns a documented stable code without product `problem/cause/next_step` | failed proof | use the public code-to-action table; do not relabel it as a product triad | no proof claim |
| canonical validation | committed bytes are invalid or validator enters a forbidden seam | fail closed | no regeneration | release blocked |
| temporary compatibility | any family delta is nonzero or capability is incomplete | fail closed | no canonical rewrite | release blocked |
| post-seal source identity | tracked, index, HEAD, tree, or source-byte drift after candidate seal | all candidate proof invalid | reviewed repair, fresh seal, complete matrix rerun | no PR, merge, or tag |
| hosted CI | any check fails | PR remains Draft | bounded diagnosis requires new review authority | no merge |
| merge | merge tree differs from reviewed tree | stop | no tag | unpublished main |
| local tag | local tag exists, creation or push fails, or target is wrong | stop in measured state | read back local and remote refs; no move, delete, or retry without authority | no verified Release |
| remote tag / absent Release | remote tag is visible but Release is absent | partial public state | retain tag, read back, require fresh authority before create or retry | tag remains public |
| Release create | timeout or ambiguous response | unknown public state | read persisted Release once before any retry; never blind retry | may be visible but unverified |
| Release metadata | persisted tag, target, draft, prerelease, or assets differ | stop | no mutation without fresh authority | visible but unverified |
| archive transport | archive download or readback transport fails | verification incomplete | bounded read-only diagnosis; no claim of archive failure | Release remains unverified |
| archive smoke | archive identity, build, or proof mismatches | stop | do not call release verified | public Release requires a corrective lifecycle decision |

No failure may be converted into success by rewriting frozen evidence, suppressing a gate,
changing runtime retrieval, or silently selecting a different artifact.

## Security and Supply-Chain Boundaries

- No secrets, hosted credentials, or new providers are introduced.
- No dependency additions are allowed.
- Build and proof paths remain call-owned and path-preflighted.
- Every proof lane binds the exact wheel it consumes.
- Cross-controller wheel identity is not inferred.
- Publication requires exact commit, tree, tag, and Release readback.
- No-follow lexical path checks remain authoritative for task-owned candidate-output paths.
- Historical durable-attempt or one-shot claim machinery is not invoked by this release.
- GitHub Release has zero attached binary assets; the source tag and archive are the public
  distribution record.
- PyPI publication is excluded.

| Threat | Likelihood | Impact | Mitigation |
|---|---|---|---|
| stale or wrong source tagged | low | high | exact HEAD/tree and tag-target readback |
| proof silently substitutes a wheel | medium | high | per-lane wheel binding and sealed-source checks |
| historical evidence rewritten | low | high | byte hashes and pure validation |
| private coordination material enters public docs | low | high | marker/path scan and actual-diff review |
| unfinished comparison enters release | medium | high | explicit exclusion and path inventory |
| dependency drift hidden in version bump | low | high | root-only lock diff assertion |

## Developer Experience Contract

The release is a CLI, library, and MCP package closeout, not a new UI.

```text
Discover
  README current release contract
    |
    v
Install
  locked local source or built wheel
    |
    v
Hello world
  start stdio MCP / run existing demo
    |
    v
Agent usage
  search_library_v2 -> completeness state
    | complete
    | more_available/capped -> bounded continuation
    v
read_evidence_v1 -> exact active Evidence bytes + final digest
    |
    v
Debug
  typed problem/cause/next_step and versioned docs
    |
    v
Upgrade
  v0.1.4 -> v0.1.5
    DB/data/schema: no migration
    valid legacy/v1 bounded calls: compatible
    exact tools/list consumer: update eight -> ten
    old cursor: restart the initial call
```

Requirements:

- one current README path, not competing release stories;
- exact copy-paste local commands;
- commands name `0.1.5` only when they describe the current release;
- historical `0.1.4` commands remain clearly historical;
- error and boundary wording leads with what is and is not complete;
- documentation links the MCP contract, deterministic-order ADR/proof, and release verification;
- no hosted playground, SaaS dashboard, or interactive website;
- upgrade notes distinguish no database/data/schema migration from the required exact-inventory
  fixture update and cursor restart; and
- proof controller codes map to operator action, while the structured
  `problem/cause/next_step` promise remains limited to product CLI and MCP surfaces.

Evaluator rehearsal target:

- Preconditions: source archive or checkout already acquired; `uv` and supported Python
  interpreters ready; lock-derived package cache warm.
- At most three user-visible steps reach the primary v2 flow:
  search -> completeness branch -> continuation -> exact read -> digest verification.
- Target local elapsed time is at most five minutes from those preconditions to first verified
  value.
- This is an acceptance target until observed in the retained rehearsal receipt, not a public
  performance claim.
- Cold acquisition and cold-cache time remain unmeasured.

## Performance and Observability

There is no runtime performance change and no performance claim.

Release observability is artifact identity:

- commit and tree;
- candidate wheel name, size, and SHA-256;
- receipt digest;
- interpreter and runtime profile;
- canonical evidence hashes;
- temporary compatibility result and seven zero-delta families;
- hosted-check inventory;
- tag and Release identity; and
- archive tree and wheel digest.

Release proof logs remain outside the repository until closeout. Only exact public-neutral facts
enter the post-release record.

## Deployment, Rollback, and Recovery

This project publishes a Git tag and GitHub Release. It does not deploy a service.

Before tag:

- rollback is branch or PR abandonment, or a normal revert;
- no public release identity exists.

After merge but before tag:

- main contains release identity but remains unpublished;
- a corrective PR is allowed;
- tagging is blocked until exact-main proof is green.

After tag and Release:

- never move or overwrite the tag silently;
- if a material release defect exists, preserve `v0.1.5` history and publish a new corrective
  version after separate authority; and
- docs-only factual corrections use a normal PR and cannot rewrite archived facts.

Post-release cleanup is separately authorized and default-deny:

- inventory all local and remote release refs and registered worktrees;
- prove every target was task-created and is not host-managed;
- prove no running owner, open PR, pending CI, or planned reuse;
- require complete clean porcelain state, including untracked files;
- resolve exact worktree and branch HEAD;
- preserve unique changes through persisted merged PR plus reviewed-tree-equals-merge-tree proof,
  or another exact retained ref;
- do not treat squash merge as feature-commit ancestry;
- do not use `git branch -D` without exact destructive authority and retained-tree or diff proof;
- exclude main, default, protected, tag, unfinished-comparison, and host-managed targets;
- name remote branch deletion explicitly;
- read back complete worktree and local or remote ref inventories afterward;
- stop on mismatch without force, broad glob, or broad prune fallback; and
- preserve proof ledgers and evidence directories unless exact paths and recovery boundaries are
  separately approved.

The one-way door is public tag identity, so publication remains a separate approval gate.

## Post-Release Trajectory

After publication verification:

1. Record tag, Release, archive, checks, diff, and retained proof facts in a docs-only closeout.
2. Complete the release retrospective.
3. Reconcile the excluded comparison work against the new mainline without consuming or
   normalizing retained evidence.
4. Review its nondeterminism stop and choose the smallest bounded repair.
5. Resume only from a frozen development corpus and sealed holdout.
6. Compare maintenance, docs or regression-only work, bounded segmentation comparison, and
   contextual retrieval comparison.
7. Treat comparison outcomes as evidence, never automatic promotion.

The release therefore leaves a published local-first Agent-consumption baseline and a separate,
falsification-first path for retrieval-quality experiments.

## Stop Conditions

Stop and require a reviewed amendment or lifecycle decision if:

- `main` moves before the release branch is created;
- public main or excluded comparison ownership has unexplained state drift;
- release work requires a production runtime, MCP schema, Evidence, or retrieval change;
- any dependency or non-root lock entry changes;
- historical `v0.1.4` facts need deletion or rewrite;
- any canonical retrieval-order artifact, frozen historical artifact, or query-plan fixture changes
  bytes;
- canonical pure validation reaches observation, replay, build, record, or publication;
- temporary compatibility produces fewer than seven families or any nonzero delta;
- any proof lane cannot bind the exact wheel used by both of its interpreter cells;
- any tracked, index, HEAD, tree, or source byte changes after sealing without invalidating every
  candidate wheel, receipt, log, and proof result;
- a task-owned proof candidate-output is preexisting, unsafe, ambiguous, or requires a second
  invocation outside the approved controller contract;
- hosted checks or review are not clean at the exact head;
- reviewed tree differs from merge tree;
- local or remote tag or Release identity conflicts;
- a partial or ambiguous publication state cannot be resolved through read-only persisted-state
  inspection;
- public archive identity, build, or smoke does not match;
- any excluded comparison result appears in the release claim set; or
- publication would require PyPI, deployment, a provider, or asset upload.

## Approval and Execution Boundary

This design authorizes only its mechanical public landing.

The actual landed spec diff must be reviewed before an implementation plan is written. The
implementation plan requires separate approval before implementation.

Implementation does not authorize push, PR, merge, tag, GitHub Release, archive cleanup, PyPI,
deployment, or runtime promotion. Those actions remain at their stated lifecycle gates.
