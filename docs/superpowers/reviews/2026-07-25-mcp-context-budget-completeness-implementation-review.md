# MCP Context Budget and Completeness Implementation Review

Status: **CLEAN / ACCEPTED**

This durable record captures the completed implementation, independent full-diff review, targeted
repair reviews, evaluation identity closure, and final verification for the MCP context budget and
completeness capability.

Reviewed branch: `codex/mcp-context-budget-spec`.

Review base, merge-base, `main`, and `origin/main`:
`d0b3b8e3f73005851570cf8fcf546030a9e2ceb5`.

Reviewed implementation HEAD:
`a4839ad10c9501c69c7a6b6fe8794cb1b31bb69a`.

Reviewed range:
`d0b3b8e3f73005851570cf8fcf546030a9e2ceb5...a4839ad10c9501c69c7a6b6fe8794cb1b31bb69a`.

The reviewed implementation range changed 62 files with 7,399 insertions and 185 deletions. The
worktree and index were clean at the reviewed HEAD. This implementation review and the associated
plan checkbox closure are documentation-only follow-up changes; they do not change runtime
behavior or the accepted implementation verdict.

## Delivered Contract

The implementation adds exactly two local, read-only MCP tools:

- `search_library_v2` provides bounded relevance-preserving Evidence excerpts, explicit
  selected-result completeness, per-item content completeness, complete active-authority
  provenance, and opaque continuation cursors.
- `read_evidence_v1` provides bounded UTF-8 chunks for exact reconstruction of one active Evidence
  item, stable complete-Evidence SHA-256 identity, and opaque continuation cursors.

The current MCP inventory is exactly ten tools:

- `list_libraries`
- `ingest_file`
- `get_run`
- `search_library`
- `ask_library`
- `list_libraries_v1`
- `search_library_v1`
- `ask_library_v1`
- `search_library_v2`
- `read_evidence_v1`

Both additive tools use the required native `request` envelope and closed strict input branches.
Search accepts either an initial query and optional page limit or a cursor-only continuation. Read
accepts either an initial Evidence ID and optional byte limit or a cursor-only continuation.
Malformed, oversized, empty, and mixed branches fail before repository access.

Search collection completeness and Evidence text completeness remain independent:

- `selection.status="complete"` means the strategy-selected pool was emitted without a known
  outer strategy discard;
- `selection.status="more_available"` carries a cursor for the remaining selected pool;
- terminal `selection.status="capped"` reports `retrieval_strategy_cap` without claiming
  corpus-exhaustive matching; and
- `excerpt.complete=false` identifies an item that requires `read_evidence_v1` for exact content.

The implementation enforces the approved UTF-8 and response limits:

- 2,048 bytes per Evidence excerpt;
- 16,384 aggregate excerpt bytes;
- 16,384 bytes per Read chunk;
- 32,768 bytes per canonical strict success model;
- a measured complete SDK result below 96 KiB;
- 16 MiB maximum readable Evidence; and
- 16 MiB maximum simultaneously loaded FTS page text.

## Authority And Compatibility

`KnowledgeEngine` remains the shared application facade. SQLite validates the active
Run/Publication/Evidence graph and derives the active-set fingerprint in the same read transaction
as Search selection or Evidence range read. The MCP adapter does not add a second store, direct
parallel authority read, alternate Publication selector, or alternate ranking path.

Every Search match and Read chunk remains bound to:

- Source identity and original Source-byte fingerprint;
- active Publication ID and revision;
- producing Run ID;
- Evidence ID and locator;
- complete Evidence text byte count and SHA-256; and
- the complete active-Publication set observed in the transaction.

Owner-local HMAC cursors bind owner epoch, active-set fingerprint, tool and response schemas,
position and page or chunk size, and the relevant Search policy or Evidence descriptor. Malformed
tokens fail before repository access. Syntactically valid continuations observe current authority
before epoch, authentication, tool, active-set, policy, descriptor, and position validation.

Existing Python and CLI contracts are unchanged. Existing legacy and strict-v1 tool names, input
schemas, valid bounded successes, Ask summaries, Publication behavior, Evidence behavior, and
Export contracts remain unchanged. Strict-v1 Search and Ask add only the approved typed
`response_too_large` recovery for complete Evidence text beyond the existing v1 model limit.

The immutable v0.1.4 consumer source-pack and eight-tool fixture remain unchanged. The current
exact-inventory expectation is a separate ten-tool fixture with SHA-256:

```text
25449f379fc91f5af28d41b45833973c3e9c2e7b5d9aa8d8f306962a28765dc9
```

Unknown-tool rejection was not weakened.

## Initial Targeted RED Evidence

Task 0 retained three public-contract REDs before production code changed:

1. the existing tool inventory did not contain `search_library_v2`, so selected-result
   completeness was not observable;
2. strict-v1 oversized Evidence had no typed `response_too_large` recovery to a bounded exact-read
   path; and
3. eleven eligible CJK results had no terminal MCP-visible strategy-cap status.

All three tests became deterministic GREEN through the additive tools and explicit strict-v1 size
preflight. No RED-only production state was committed.

## Independent Review Findings And Resolutions

The independent full-diff review returned nine implementation findings. Each received a targeted
failing regression before the smallest contract-preserving repair:

1. **SQLite Read materialization:** initial reads now preflight metadata and byte length before
   loading text; continuations use bounded BLOB `substr` ranges and do not reload complete
   Evidence.
2. **FTS page materialization:** Search v2 uses metadata-only `LIMIT`/`OFFSET` lookahead, then
   loads ordered page text only within the 16 MiB call bound while preserving first-candidate
   progress. Legacy FTS behavior remains unchanged.
3. **Retrieval match hints:** FTS diagnostic alternatives and CJK scorer-matched terms now travel
   with selected Evidence instead of being reconstructed from the raw query.
4. **Normalized excerpt offsets:** deterministic normalized-to-original span mapping preserves the
   actual matched region through length-changing NFKC and casefold transformations.
5. **Exact CJK cap state:** the terminal cap uses the strategy's explicit discarded-result state;
   exactly ten eligible results are complete, while eleven are capped.
6. **Blank v2 Search input:** blank queries return the typed invalid-request response before
   engine or repository access.
7. **Frozen release error contract:** the producer is compared against frozen machine-token,
   impact, and safe-cause requirements while additive current causes remain permitted. The frozen
   fixture was not rewritten.
8. **Cursor validation phases:** parsing and authentication are separate; malformed tokens make no
   engine call, while syntactically valid continuations observe authority before trusted epoch,
   MAC, tool, active-set, policy, schema, size, position, and descriptor bindings.
9. **Installed-proof dependency identity:** the workflow provisions both supported interpreters,
   prewarms both environments from a locked core export, and retains one job and one exact wheel.

The resulting real-stdio proof also exposed a server-issued Read continuation that incorrectly
re-entered initial full-text assembly. A focused round-trip regression closed that boundary and
proved bounded continuation to terminal completion.

Two later targeted findings were also closed:

1. **Retrieval-normalized excerpt localization:** CJK whitespace-insensitive matches and FTS
   token-separator phrase matches now carry retrieval-owned normalization semantics into
   normalized-to-original span mapping. Late matches containing inter-character whitespace or
   punctuation produce UTF-8-safe `query_window` excerpts containing the actual original region.
   Existing NFKC expansion, combining-mark, emoji, and byte-boundary behavior remains GREEN.
2. **Controller-owned lock proof:** the reusable proof controller independently runs
   `uv export --locked --no-dev --no-emit-project --no-header` and requires exact byte equality
   with the supplied constraints before build or installation. Empty or arbitrary constraints
   fail with `locked_constraints_mismatch`. Successful receipts report
   `dependency_constraints="uv_lock_exact"`.

The accepted repairs do not change public schemas, ranking, cap thresholds, active-Publication
authority, response budgets, dependency inventory, or public non-claims.

## Evaluation Identity Closure

Task 8R reused the existing supported, atomic, and recoverable E1 through E3-E identity procedure.
The approved maximum allowlist remained exactly 21 paths. Individual closures used only the
validator-proven subset required by the current source diff; the final retrieval-span closure used
all 21 approved paths.

Before canonical writes, fresh E1, refreshed-scope E2, E3-A, and E3-B observations proved that
validator failures were exclusively source, scope, or dependency identity drift. Canonical E1
through E3-B targets were refreshed only through
`python -m mke.evaluation.artifact_refresh`. Downstream identities were generated and validated in
a detached mirror before exact-byte, recoverable application.

Normalized before/after comparison recorded:

```json
{"identity_only":true,"paths":21,"semantic_change":false}
```

No model ran. No holdout was re-observed. No corpus, fixture, query, qrel, observation, ordered
result, metric, threshold, gate, diagnostic, selected candidate or profile, verdict, status, or
promotion changed.

## Final Verification Evidence

Final verification on reviewed implementation HEAD
`a4839ad10c9501c69c7a6b6fe8794cb1b31bb69a` recorded:

| Gate | Result |
|---|---|
| `UV_OFFLINE=1 uv run pytest -q` | `3162 passed, 14 skipped, 5 warnings` |
| `UV_OFFLINE=1 uv run ruff check .` | GREEN |
| `UV_OFFLINE=1 uv run pyright` | `0 errors, 0 warnings, 0 informations` |
| `UV_OFFLINE=1 uv build` | sdist and wheel built |
| Evaluation artifact regression | `191 passed, 5 warnings` |
| Seven canonical E1 through E3-E validators | GREEN |
| Python 3.12 and 3.13 same-wheel installed proof | GREEN |
| Repository-external real-stdio consumer | GREEN |
| Exact current inventory | 10 tools |
| Maximum canonical strict model | 18,986 bytes |
| Maximum complete SDK result | 38,398 bytes |
| Dependency constraint binding | `dependency_constraints=uv_lock_exact` |
| Installed-proof network result | `network_access=not_used` |
| `git diff --check` and public-boundary scan | GREEN |

The terminal proof ran both interpreters against the same wheel from a repository-external working
directory, imported only the installed package, and verified exact tool schemas, structured and
compatibility text content, Search continuation, exact Read reconstruction, final Evidence
SHA-256, CJK terminal cap, cursor tamper and expiry, legacy/v1 compatibility, reconnect, and wire
budgets.

Final deterministic identities:

```text
constraints sha256:
e6fc533bec87cbd31d641115e9e0901d4c2d7a8c78ad07f91fc25a66f5f827bb

wheel sha256:
9fcbe7edcfdcfe47d5548257f54149826b6f6f524853d94c6f674c42610b523d

ten-tool fixture sha256:
25449f379fc91f5af28d41b45833973c3e9c2e7b5d9aa8d8f306962a28765dc9
```

## Rollback

No database migration was added. A rollback can:

1. unregister `search_library_v2` and `read_evidence_v1`;
2. remove their strict schemas, cursor payloads, application assembly helpers, and bounded adapter
   methods;
3. restore the prior current exact-inventory expectation while retaining the immutable v0.1.4
   source-pack evidence;
4. revert the additive strict-v1 oversized cause and recovery mapping if required;
5. revert the dedicated installed-proof workflow and documentation;
6. revert the identity-only evaluation closure through normal commit history; and
7. rerun frozen schema, full project, installed legacy-consumer, artifact-validator, and release
   fixture checks.

Existing Library data, Source data, Runs, Publications, Evidence, Python, CLI, legacy/v1 MCP, and
Export remain usable because the capability added no migration or alternate authority.

## Claim Boundaries

This review does not claim:

- corpus-exhaustive Search or total-match counting;
- semantic summaries or generated answer authority;
- arbitrary-size Export or arbitrary-size Evidence support;
- production readiness, performance, quality, throughput, latency, SLA, adoption, or deployment;
- remote or HTTP MCP, authentication, hosted service, or multi-tenant operation;
- OCR runtime or OCR promotion;
- GraphRAG, segmentation promotion, retrieval promotion, or corpus expansion; or
- an Agent loop, Agent orchestration platform, or additional MCP tool.

`search_library_v2` exposes bounded strategy-selected results and explicit loss signals.
`capped` is terminal but not exhaustive. Evidence content remains untrusted.

## Publication State And Verdict

At review time, no push, pull request, merge, tag, release, registry publication, deployment, or
cleanup had occurred.

`ACCEPTED` -- the implementation satisfies the approved public contract, independent full-diff
review, targeted repair reviews, evaluation identity closure, and final verification gates. This
verdict authorizes only subsequent repository publication workflow under separate explicit
authorization; it does not itself claim that publication, review hosting, merge, release, or
deployment occurred.
