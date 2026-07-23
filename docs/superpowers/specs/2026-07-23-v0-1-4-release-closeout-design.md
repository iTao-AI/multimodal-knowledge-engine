# v0.1.4 Release Closeout Design

Status: approved design source; pending mechanical landing and actual-diff review.

Date: 2026-07-23

## Context

The exact approved starting point is `main@32e4ed2a457e5a4affd21bd83d5a86983c5dbf11`.
At approval time:

- local `HEAD`, `main`, and `origin/main` were equal and the primary worktree was clean;
- the exact-main commit had ten completed successful check-runs;
- there were no open pull requests, Dependabot alerts, or code-scanning alerts;
- `v0.1.3` was the latest public, non-draft, non-prerelease GitHub Release;
- no local or remote `v0.1.4` tag or GitHub Release existed; and
- the package and module version remained `0.1.3`.

Since the `v0.1.3` tag target, the merged product line has added:

1. isolated LLM Wiki v1 compatibility evidence for Compiled Library Export;
2. a receipt-backed internal direct-audio foundation;
3. bounded public direct-audio intake through Python, CLI, and stdio MCP;
4. deterministic mixed-Library Compiled Library Export v2;
5. a real installed-wheel, cache-only direct-audio terminal proof on Darwin arm64 with CPython
   3.12 and 3.13; and
6. reviewed security maintenance for Torch 2.13.0 and Setuptools 83.0.0.

The merged direct-audio implementation plan explicitly stopped at a feature candidate and required
a separate release-closeout design and plan. This design supplies that missing release authority.

## Release Decision

`v0.1.4` is a small feature release led by bounded direct-audio intake.

The release headline is:

> MKE can ingest bounded local MP3, WAV/PCM, and M4A/AAC voice notes or clips through an explicitly
> prepared cache-only owner, publish timestamp Evidence, expose the same flow through Python, CLI,
> and stdio MCP, and export complete mixed Libraries through deterministic Compiled Library Export
> v2.

The release keeps MKE local-first and Evidence-authoritative. It does not turn MKE into a hosted
RAG service, a general audio platform, or a model-distribution product.

The isolated LLM Wiki proof is secondary downstream compatibility evidence. LLM Wiki remains
outside MKE runtime, dependency, state, and Evidence authority.

## Goals

- Publish package and module version `0.1.4` from one exact verified merged-main commit.
- Promote the already merged bounded direct-audio candidate to an accurately described released
  capability.
- Preserve the 15-minute, 100-MiB, closed-profile, Darwin-arm64, explicitly prepared cache-only
  owner boundary.
- Preserve Source, Run, Publication, Evidence, SQLite, Search, Ask, CLI, and stdio MCP authority.
- Publish mixed-Library Compiled Library Export v2 while keeping v1 byte-compatible and fail-closed
  for active audio.
- Summarize the accepted isolated LLM Wiki compatibility evidence without making LLM Wiki an MKE
  dependency or authority.
- Record the merged Torch and Setuptools security maintenance without implying unrelated
  dependency promotion.
- Prove the exact candidate wheel through installed smoke, source-pack, Compiled Library Export,
  model-free direct-audio, and one bounded real direct-audio terminal run.
- Publish an annotated `v0.1.4` tag and public GitHub Release with no uploaded assets.
- Verify the public source archive and then record immutable release facts in a separate docs-only
  closeout pull request.

## Included Capabilities

### Bounded Direct Audio

The released direct-audio boundary accepts only the documented MP3, WAV/PCM, and M4A/AAC profiles
for local voice notes and bounded clips or excerpts. Admission is limited to 15 minutes and
100 MiB.

Direct audio is enabled only when all of the following are true:

- the runtime platform is Darwin arm64;
- the owner explicitly composes the cache-only faster-whisper adapter;
- the accepted model snapshot is already prepared locally;
- the owner supplies a positive `direct_audio_footprint_bytes` value; and
- `direct_audio_footprint_budget_mode` is exactly `baseline_plus`.

MKE supplies no default footprint value, recommendation, production ceiling, or SLA. Missing
authority fails before Source and Run creation and before model work. PDF and video behavior
remains available and unchanged.

Successful processing:

- snapshots the admitted audio bytes immutably;
- creates an observable Run;
- publishes timestamp-bearing Evidence only after complete success;
- switches the active Publication atomically;
- supports Search and evidence-only Ask;
- routes through the same Python, CLI, and stdio MCP application boundary; and
- preserves closed error mapping and cleanup authority.

### Compiled Library Export v2

Compiled Library Export v1 remains byte-compatible. An active audio Source makes v1 fail closed.
Explicit v2 represents the complete mixed Library and preserves `mke.evidence_ref.v1` as machine
authority.

The installed proof must demonstrate:

- deterministic repeated v2 trees;
- exact Source, Publication, Evidence, locator, and digest authority;
- portable-copy validation; and
- successful standalone v2 consumption without importing MKE or reading SQLite.

### LLM Wiki Compatibility Evidence

The release may state:

> An isolated downstream LLM Wiki workflow ingested a fresh immutable Compiled Library Export,
> compiled it, answered one bounded page query and one bounded timestamp query, and preserved a
> return path through content fingerprint to MKE's canonical manifest and Evidence sidecars.

This is downstream compatibility evidence. It does not establish a bundled adapter, automatic
sync, hosted integration, production adoption, or shared authority.

### Security Maintenance

The release includes already merged lock and receipt maintenance:

- Torch `2.13.0`; and
- Setuptools `83.0.0`.

These are maintenance facts, not new public product contracts. The release must not claim that
MKE distributes external wheels or native libraries.

## Claim Matrix

| Surface | Allowed `v0.1.4` claim | Required boundary |
|---|---|---|
| Direct audio | Bounded MP3, WAV/PCM, and M4A/AAC intake can publish timestamp Evidence. | Darwin arm64, 15 minutes, 100 MiB, explicit owner, prepared cache, no download or cloud fallback. |
| Python / CLI / MCP | All three routes use the canonical application lifecycle and closed errors. | No HTTP, hosted service, request-time provider override, or remote credential flow. |
| Search / Ask | Published audio Evidence participates in active-Publication Search and evidence-only Ask. | No generative answer, transcript-accuracy, adoption, or business-impact claim. |
| Export v2 | Explicit v2 exports complete mixed Libraries deterministically. | v1 remains closed and fails with active audio; EvidenceRef sidecars remain machine authority. |
| Real terminal proof | One exact candidate wheel passes two installed interpreter cells, fixed fixtures, cache-only ASR, MCP, Search/Ask, and v2 consumer gates. | Fixed-fixture Darwin-arm64 proof only; not a production SLA, general benchmark, or hostile-media sandbox. |
| LLM Wiki | Isolated downstream compatibility evidence preserves the return path to MKE authority. | No runtime dependency, bundled adapter, automatic sync, hosted integration, or shared authority. |
| Dependency maintenance | Locked Torch and Setuptools maintenance is included. | No claim of external-binary redistribution authority. |
| Retrieval | Existing lexical and CJK active-scan runtime remains shipped; dense/RRF/reranker records remain comparison-only. | No retrieval runtime promotion. |
| OCR | Existing Phase 0 records remain historical evaluation evidence. | No production OCR or public OCR runtime. |

## Non-Goals

This release does not:

- accept arbitrary codecs or full-length meetings, interviews, or lectures;
- add diarization, long-audio chunking, resume, streaming, or microphone capture;
- add implicit model download, cloud ASR, or network fallback;
- claim transcript accuracy, a quality benchmark, production readiness, an SLA, or cross-platform
  provider support;
- claim hostile-media containment or a hard aggregate RSS ceiling;
- bundle, upload, vendor, or redistribute external wheels, FFmpeg libraries, model files, or native
  binaries;
- add production OCR, layout reconstruction, or a public OCR provider;
- promote dense, RRF, reranker, query rewrite, or HyDE into runtime;
- add HTTP, workspace UI, multi-tenant service, RBAC, billing, or deployment;
- publish to PyPI or another package registry; or
- upload the local wheel, candidate receipt, dependency receipt, model, or terminal proof as a
  GitHub Release asset.

## Version And Historical Evidence Rules

Current release identity becomes `0.1.4` in:

- `pyproject.toml`;
- `src/mke/__init__.py`;
- current package/bootstrap/release-smoke tests;
- current release presentation constants;
- current README, documentation index, changelog, release note, verification, direct-audio,
  export, CLI, MCP, and ADR surfaces that still describe direct audio as a candidate.

Historical facts remain historical:

- `docs/releases/v0.1.3.md` remains byte-identical;
- completed `v0.1.3` design, plan, reviews, tag, archive, and publication records are not rewritten;
- the completed direct-audio design, implementation plan, amendment, and implementation reviews
  remain implementation history;
- historical statements that a capability was not shipped by `v0.1.3` remain valid;
- synthetic test values are changed only when a failing current-release contract test proves they
  represent current identity; and
- OCR receipts and frozen evaluation observations remain bound to their recorded authority.

`uv.lock` may change only through the root project version from `0.1.3` to `0.1.4`.
Dependency names, versions, sources, markers, hashes, extras, and external projections must remain
semantically equal.

## Dependency Receipt And Fresh Candidate Authority

The canonical direct-audio dependency receipt is an accepted historical external-authority
artifact:

- schema: `mke.direct_audio_dependency_receipt.v1`;
- committed file SHA-256:
  `49196028327ba0d34be5bcabfeb55bd6d455f4e68e88a35e858e7c30db8ef111`;
- canonical payload SHA-256:
  `c6cc4b963e4a5a53fe6df51c52430f20e09f9194a6723f4f0958b7d521b903f9`;
- constraints SHA-256:
  `f76c6f29ceeea5fa6f6a21d3baa7d6e3455f7cf596cc292b8da7c0ca7ef941e4`;
- external wheelhouse manifest SHA-256:
  `67c7e3ba11c08eef9712deb79ad94d1bc801b87c894eda8ac4a46b44b2244bc5`;
- complete historical wheelhouse manifest SHA-256:
  `205ea864294ae9351a2eede8b0bac7d1cfd6ac6b627ee3bb5db764532f800404`.

The receipt's internal historical candidate remains
`multimodal_knowledge_engine-0.1.3-py3-none-any.whl`, 353,200 bytes, SHA-256
`e3abdf24589be880aa2c135cd8687ed6c21e0ea0ed2ec5fe1742703ef665c3d0`.
That value is historical internal consistency, not the `v0.1.4` terminal candidate.

The accepted non-circular deployment authority must:

1. validate the committed receipt completely without rewriting it;
2. remove the receipt's historical candidate from the external dependency projection;
3. independently validate the fresh `0.1.4` wheel's distribution, version, filename tags,
   METADATA requirements, current lock/constraints projection, two interpreter-cell roots, bytes,
   and SHA-256;
4. bind the fresh wheel through the terminal authorization manifest, staged-input validation, and
   installed `RECORD` identity; and
5. keep external wheel, license, fixture, interpreter, platform, model, and supervision authority
   unchanged.

The release closeout must not replay or regenerate the canonical dependency receipt. A validator-
proven external dependency or authority drift is a hard stop for a separate maintenance design;
it is not repaired inside this release closeout.

## Release Architecture

### Stage 1: Release-Candidate Pull Request

Create one isolated branch from the exact current `origin/main`. Land this approved design and its
implementation plan, then use tests first to define the `0.1.4` identity and presentation.

The pull request contains:

- package and lock root identity;
- current release smoke and presentation contract;
- new `docs/releases/v0.1.4.md`;
- README, changelog, documentation index, verification, direct-audio, Export v2, CLI/MCP, and ADR
  updates;
- a validator-proven minimal retrieval identity closure when required; and
- a durable implementation review.

No tag or GitHub Release exists in this stage.

### Stage 2: Reviewed Clean Candidate

The authoritative reviewer examines the complete actual branch diff before final candidate
generation. All review repairs and durable acceptance text are committed first.

From that clean reviewed commit:

- run the complete repository gates;
- build one fresh candidate wheel;
- generate one strict `mke.candidate_artifact_receipt.v1`;
- prove the exact same wheel through release smoke, Python 3.12/3.13 source-pack, Compiled Library
  Export v1/v2, and the standalone v2 consumer;
- run the model-free direct-audio proof;
- validate the unchanged dependency receipt and retained inputs;
- generate one terminal authorization manifest; and
- invoke the real direct-audio deployment controller exactly once.

The candidate receipt, Compiled Library proof, and direct-audio terminal proof must report the same
wheel SHA-256. Any tracked write after this sequence invalidates the candidate and terminal proof.

### Stage 3: Pull Request, Merge, And Exact Main

Push and create a Draft pull request only after separate authorization. Bind all review and checks
to one exact head. Do not poll unchanged checks.

After successful exact-head checks and separate merge authorization:

- use ordinary squash merge;
- prove reviewed-tree equality with the merge tree;
- wait for exact-main hosted checks only through bounded event-driven observation;
- build a fresh exact-main wheel;
- generate a fresh candidate receipt that binds the exact merge commit; and
- require the exact-main wheel SHA-256 to equal the reviewed terminal wheel SHA-256.

When tree and wheel equality hold, do not repeat real ASR. If either differs, stop; do not silently
substitute a new wheel or automatically run another terminal proof.

### Stage 4: Annotated Tag And GitHub Release

Publication remains separately authorized. After the exact-main gate:

- create annotated tag `v0.1.4` at the exact verified merge commit;
- push only that tag;
- create a public, non-draft, non-prerelease GitHub Release named `v0.1.4`;
- upload zero assets;
- read back tag object, peeled target, release state, author, publication time, and asset inventory;
- verify that `v0.1.4` is the latest release; and
- run a public source-archive smoke in a call-owned directory.

Archive smoke includes locked sync, product proof, demo, local knowledge, Evidence provenance,
model-free direct audio, Compiled Library Export, and standalone consumption. It does not rerun
real ASR or require the non-distributed wheelhouse/model inputs.

### Stage 5: Post-Release Docs-Only Closeout

Immutable release facts cannot be committed before publication. Create one serial docs-only pull
request after Stage 4 to record:

- release-candidate PR and merge identity;
- annotated tag object and peeled target;
- release URL, state, author, and publication time;
- zero-asset inventory;
- exact-main wheel and candidate receipt identities;
- terminal proof binding and non-claims;
- public archive bytes, SHA-256, and smoke results; and
- final cleanup and unchanged-tag/release verification.

This pull request may update only the approved design, implementation plan,
`docs/how-to/verify-release.md`, and a new durable post-release closeout review unless a focused
documentation contract proves another current-release record is required.

## Review, CI, And Polling

- Use one primary execution controller. The candidate, receipt, review, merge, tag, and archive
  chain is ordered and must not be split across parallel mutable worktrees.
- Run one whole-branch authoritative review before the final candidate.
- Repairs receive targeted re-review by default.
- After PR creation or update, take one exact-head checks snapshot and stop.
- Resume only on a user event, a bounded wait explicitly requested by the user, or a hosted-state
  change.
- Do not set artificial job or local proof time limits merely to shorten the run.
- Preserve normal subprocess-level containment and diagnostics.

## Evaluation Identity Boundary

Changing `src/mke/__init__.py`, release scripts, tests, or documentation may invalidate frozen
retrieval provenance.

Use only the repository's accepted `artifact_refresh` transaction and detached validation mirror.
The maximum authority is the established 21-path allowlist from the current release workflow; use
the smallest validator-proven dependency-closed subset.

Require:

- E1 through E3-E validators all pass;
- generated, staged, detached-mirror, and final bytes are equal;
- normalized semantic projections are equal;
- observations, ordered results, metrics, thresholds, gates, diagnostics, profiles, candidates,
  status, and verdict do not change; and
- no corpus, qrels, queries, runtime strategy, or quality conclusion changes.

Any larger or semantically changed closure is a hard stop.

## Publication And Distribution Boundary

The local candidate wheel, candidate receipt, dependency receipt, terminal receipt, model cache,
external wheelhouse, and proof logs are evidence, not release assets.

`v0.1.4` publishes:

- one annotated Git tag; and
- one zero-asset GitHub Release using GitHub's generated source archives.

PyPI, package registries, deployment, Docker publication, model publication, OCR execution,
external-binary redistribution, and service operation remain outside this closeout.

## Rollback

Before publication, rollback means closing the release-candidate pull request and leaving
`v0.1.3` latest.

After publication:

- do not move or recreate the tag;
- do not mutate immutable release history to hide an error;
- publish a corrective patch release when package behavior or release identity is wrong; and
- use a docs-only correction only for presentation facts that do not change the tagged artifact.

At runtime, direct audio remains disabled when the owner omits the supervision pair or adapter.
PDF and video remain available, and Export v1 remains available for Libraries without active
audio.

## Completion

The release closeout is complete only when:

- the release-candidate and post-release docs-only pull requests are merged;
- exact-main checks for both merges are successful;
- annotated tag and GitHub Release identities are read back and stable;
- public archive smoke passes;
- the primary checkout is clean and synchronized;
- task-owned branches and worktrees are safely removed;
- unrelated retained evidence and the pre-existing detached historical-source worktree are
  untouched; and
- the final report preserves all release identities, verification facts, and non-claims.
