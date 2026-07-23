# v0.1.4 Release Implementation Review

Status: **CLEAN / ACCEPTED**

This record freezes the accepted local candidate state after implementation Tasks 1-7 and the
accepted dependency-authority version-boundary repair. Independent targeted actual-diff review
accepted exact repair HEAD `a921f2a2f5dea9e27512b67e521f758fc899f9cb` and tree
`1dbd9a8b80c7077e3104ce144da8066dae2f0e6c` with zero findings. Task 8 Steps 1-7 remain entirely
unstarted. No final candidate was built, no terminal real-ASR proof was run, and no push, PR,
merge, tag, GitHub Release, archive proof, publication, or cleanup was performed.

## Candidate Identity

- Starting baseline: `32e4ed2a457e5a4affd21bd83d5a86983c5dbf11`.
- Approved authority landing: `560033202243f100832aea22692622caf3b5bff3`.
- Package identity commit: `bb48a28d22b5edfd088b8f71e8e822c8d9a471fc`.
- Atomic presentation and release-documentation commit:
  `b65f3f72343ae6ba6c6f26116dcba71d12777a97`.
- Evaluation identity closure commit: `b0e5c4949613db11f032c033abaef46527bd211f`.
- Initial docs-only acceptance commit: `4fffc3e3941475ccf7d8ff7ceb5d6ea9010ff42c`.
- Accepted dependency-authority repair commit:
  `a921f2a2f5dea9e27512b67e521f758fc899f9cb`.
- Branch: `codex/v0-1-4-release-closeout`.
- Package identity: `0.1.4` in project metadata, module metadata, lock root, and release-consumer
  smoke authority.

The Task 3/4 atomic lane is the result of the 2026-07-23 Career amendment. Its reproducible RED
contained only the expected missing or stale current-release documentation and presentation
failures. The audit and complete current-release documentation then landed together in one GREEN
commit; no RED intermediate commit exists.

## Exact Branch Scope

Before this Task 6 durable-state record, the branch changed exactly 51 paths relative to the
starting baseline: 1 changelog, 2 top-level READMEs, 12 retrieval benchmark artifacts, 16 current
documentation surfaces, 2 approved Superpowers authority documents, 1 package manifest, 2 release
scripts, 1 module-version file, 7 focused tests, 4 evaluation protocol locks, 2 root identity
tests, and `uv.lock`.

Task 6 added only this review and updated the existing implementation plan checklist. At that
durable-state checkpoint, the resulting branch diff was exactly 59 paths, 2,237 insertions, and
258 deletions. Its scope was:

- current release entry points: `CHANGELOG.md`, `README.md`, `README_CN.md`, `docs/README.md`,
  `docs/releases/v0.1.4.md`, and the affected current tutorial, how-to, reference, and ADR files;
- package identity: `pyproject.toml`, `src/mke/__init__.py`,
  `scripts/release_consumer_smoke.py`, its focused tests, and `uv.lock`;
- presentation contract: `scripts/release_presentation_audit.py` and the focused documentation
  and presentation tests;
- evaluation identity closure: the validator-proven 16 JSON artifacts/protocol locks and the
  five exact digest consumers within the established 21-path allowlist;
- durable authority: the approved design, this implementation plan, and this review.

No production runtime, dependency version, workflow, direct-audio receipt, OCR artifact,
historical release record, historical direct-audio authority, or other plan was changed.

## Release Claim Matrix

| Surface | v0.1.4 claim | Boundary retained |
|---|---|---|
| Package | Local package and installed-smoke identity is `0.1.4`. | No registry or PyPI publication claim. |
| Direct audio | Bounded MP3, WAV, and M4A intake is documented as released on the verified Darwin arm64 owner path. | 15-minute and 100-MiB input limits; explicit owner supervision; prepared cache; no implicit download, cloud fallback, broad platform, accuracy, production ceiling, or SLA claim. |
| Product path | Python, CLI, and stdio MCP share Publication, Search/Ask, and timestamp Evidence authority. | HTTP and hosted deployment remain out of scope. |
| Compiled Library Export | Export v1 remains stable; v2 provides the closed audio-capable contract and standalone consumer proof surface. | No automatic or bundled LLM Wiki integration. |
| LLM Wiki | Compatibility remains isolated downstream evidence. | LLM Wiki is not a dependency, schema owner, runtime component, or Evidence authority. |
| Retrieval evaluation | Existing quality observations and verdicts are unchanged; release identities are rebound to `0.1.4`. | No new benchmark, model, prompt, threshold, quality, or production claim. |
| OCR | Existing phase-0 evaluation authority remains frozen. | OCR remains evaluation-only, not a production OCR claim. |

## Current And Historical Version Classification

- Current package, README, changelog, release note, guide, reference, audit, test, and evaluation
  release identities are `0.1.4` or `v0.1.4`.
- `docs/releases/v0.1.3.md` remains a historical release record byte-for-byte.
- Historical v0.1.3 statements that direct audio and LLM Wiki compatibility were not shipped at
  that time remain historical facts and were not rewritten.
- The canonical direct-audio dependency receipt intentionally retains its historical
  `multimodal_knowledge_engine-0.1.3-py3-none-any.whl` inventory. It was not regenerated or
  presented as the v0.1.4 candidate.
- Synthetic or contradiction-test version text remains test-local where it does not represent a
  current release surface.

## Lock And Evaluation Identity Closure

The offline lock refresh changed only the root project version from `0.1.3` to `0.1.4`. A parsed
old/new comparison showed 97 packages and identical dependency names, versions, sources, markers,
hashes, extras, and resolution graph after normalizing that single root-version field. No
dependency, wheel, interpreter, fixture, or model was downloaded or fetched.

All seven canonical retrieval validators initially failed only on release identity except E3-E,
which already passed. The supported refresh transaction and deterministic detached validation
mirror established the exact 21-path dependency closure:

- 16 generated JSON artifacts and protocol locks are byte-identical across generated, mirror,
  staged, and worktree copies;
- five non-JSON consumers contain exact digest replacements only;
- normalized JSON semantics are equal after excluding the permitted path, byte, SHA, source
  inventory, and dependency identity fields;
- observations, ordering, metrics, thresholds, gates, diagnostics, profiles, candidates,
  statuses, verdicts, corpora, qrels, queries, fixtures, runtime selectors, and quality
  conclusions are unchanged; and
- all seven canonical validators pass from fresh observations.

## Frozen Direct-Audio Authority

The following values were descriptor-read without modifying retained authority:

- receipt file SHA-256:
  `49196028327ba0d34be5bcabfeb55bd6d455f4e68e88a35e858e7c30db8ef111`;
- canonical receipt payload SHA-256:
  `c6cc4b963e4a5a53fe6df51c52430f20e09f9194a6723f4f0958b7d521b903f9`;
- preflight and generation-preflight observed digest:
  `28333a5eea0eb0a60dda76ff38809cf9274550102f5455d78e0e8aef92bd6093`;
- receipt script SHA-256:
  `932c9e17733e343f15fa558f1e54d21248da8f3f13ce4e52acc344b8f7ca2257`;
- constraints SHA-256:
  `f76c6f29ceeea5fa6f6a21d3baa7d6e3455f7cf596cc292b8da7c0ca7ef941e4`;
- root requirements SHA-256:
  `f563f67887a798e698754e2312e1fa35e9c2dc3516260f9d287cfe9f12280034`;
- external 60-wheel manifest SHA-256:
  `67c7e3ba11c08eef9712deb79ad94d1bc801b87c894eda8ac4a46b44b2244bc5`;
- complete historical 61-wheel manifest SHA-256:
  `205ea864294ae9351a2eede8b0bac7d1cfd6ac6b627ee3bb5db764532f800404`;
- inventory relationship: 60 external wheels plus the historical MKE 0.1.3 candidate wheel;
- CPython 3.12 executable SHA-256:
  `e2605291e058fdbe3102e8185d0ac5fe0e063398de617010a6af3a42a78f05e3`;
- CPython 3.13 executable SHA-256:
  `3237648c5222017bba78737370570e4c9d5a01e552cdf2fa11f107c8d00fc06e`;
- `direct-audio.m4a` SHA-256:
  `cd7307b22b74de4fef8bda87582be791528c65d6546e4abdf42128070980e260`;
- `direct-audio.mp3` SHA-256:
  `cc10ce7b07ae0ea8434b690383bb7ef0a43f7af66aec474d410e5a9612158631`;
- `direct-audio.wav` SHA-256:
  `ec82eefefc5a6ccbbfc757864fc94bffd250bf185b03fc0404568063c8f993ac`;
- fixture authority document SHA-256:
  `533bc8a47ba89aeb86de0e7b944da2f1a3f1de8a5ba062b861a3aef854a87ccb`;
- configured model identity: `Systran/faster-whisper-small` at immutable revision
  `536b0662742c02347bc0e980a01041f333bce120`.

No retained model cache or terminal authorization receipt was supplied to this Task 6 process, so
no model-tree digest is asserted here. Task 8 remains responsible for binding a present retained
model tree into an authorized candidate; this record does not infer that identity from
configuration alone.

Historical direct-audio authority remains byte-identical:

- design SHA-256:
  `9f355dd2bec943132ac478f7e1d03a8b1d04fd3aa5f53f6bcc154776d47030ae`;
- implementation plan SHA-256:
  `b4b9cc9323ac4ae8a66868dc22d286642c3c3b5d9db35bc575ea108672bc4c32`;
- implementation review SHA-256:
  `c77ab3b8e92413194c1a39d86f88e10f43dced63c29642928ac8294ccda69066`.

## Frozen OCR And Historical Release Authority

- `benchmarks/ocr/candidate-environments.json`:
  `d2232fcbd6775a9f03fa3d2a77b181987b5cfa43c9fdc1efcb48f08f01553d2a`;
- `benchmarks/ocr/model-artifacts.json`:
  `3d1e8c45b7ed0c817acaeda3f51954b463016763690e09ca1f23162042219d6e`;
- `benchmarks/ocr/provider-startup.json`:
  `1a159461fd73c7069905b0a085f5b900f4b1577dbf418a86adcf96b9c6354652`;
- `benchmarks/ocr/phase0-scorecard.json`:
  `b84720bd33999ad333e3ac5105b7abd996ab910b3c9cd458f6c43e66fa709457`;
- frozen OCR aggregate model tree:
  `9877eb33601bc06640608021b4b33f9950ccd6ef990cc0877501ba1d451cc998`;
- `docs/releases/v0.1.3.md`:
  `85aa1ba71cfc9df18ccd8655d7f3de82434c77cff0b8729a53968471fc5e22e0`.

## Focused Verification

- Task 2 current-version RED: `7 failed, 6 passed`; failures were the expected current
  version/wheel identity mismatches.
- Task 2 GREEN: `13 passed, 5 warnings`.
- Atomic Task 3/4 RED: `26 failed, 224 passed`; failures were limited to missing or stale current
  v0.1.4 release and presentation surfaces.
- Atomic Task 3/4 GREEN: `250 passed`.
- Live presentation audit: `status=ok`, `violations=[]`.
- Markdown link/fence audit: 18 changed Markdown files and 175 tracked Markdown files checked,
  `status=ok`.
- `document-release` audit: current identity, bounded direct audio, Export v2, CLI/MCP/contracts,
  how-to, tutorial, ADR, and release note are covered; no critical or common documentation gap.
- Artifact refresh helper tests: `6 passed`.
- Exact digest-consumer tests: `10 passed`.
- Full evaluation artifact regression suite: `191 passed, 5 warnings`.
- Fresh canonical validators: E1, E2, E3-A, E3-B, E3-C, E3-D, and E3-E all passed.
- Staged and committed whitespace gates for each implementation commit passed.

## Authoritative Review Findings And Bounded Repair

Career reviewed exact HEAD `3c60c1dfa18aba65a402e0be1d12207a55fba329` and returned
`ISSUES FOUND`. Task 7 was not accepted. The bounded repair closes three findings:

1. The three canonical retrieval guides now publish every current comparison, development-freeze,
   holdout-receipt, and protocol-lock digest that they name. Documentation tests compute each
   digest from committed bytes and require the corresponding guide value.
2. The five current guides that build and then consume the release wheel now name only
   `multimodal_knowledge_engine-0.1.4-py3-none-any.whl`. The release presentation audit owns this
   exact file inventory and rejects the stale 0.1.3 wheel while historical records, canonical
   receipt contents, and synthetic historical tests remain unchanged. Worktree-bound full-suite
   verification also exposed and repaired the same stale current installed-metadata assertion in
   the MCP deployment-client proof test.
3. Direct-audio wheelhouse authority now distinguishes the external 60-wheel manifest
   `67c7e3ba11c08eef9712deb79ad94d1bc801b87c894eda8ac4a46b44b2244bc5`
   from the complete historical 61-wheel manifest
   `205ea864294ae9351a2eede8b0bac7d1cfd6ac6b627ee3bb5db764532f800404`.
   The relationship is 60 external wheels plus one historical MKE 0.1.3 candidate; canonical
   receipt/evidence bytes are unchanged.

Career targeted authority re-review accepted repair range
`3c60c1dfa18aba65a402e0be1d12207a55fba329..f9c5c3b5211337a0d2d86b3332697ad3755d4420`
as `CLEAN`, with no residual finding. This closes Task 7 but does not authorize Task 8.

Targeted repair verification:

- reviewer reproduction: `2 failed, 8 passed`;
- expanded repair RED: `7 failed, 213 passed`, limited to the accepted digest and wheel identity
  findings;
- repair GREEN: `220 passed`;
- final combined retrieval, Chinese, release-documentation, presentation, and installed-metadata
  suite: `270 passed`;
- worktree-bound installed-MCP/environment regression: `14 passed, 5 warnings`;
- full pytest: `3108 passed, 4 skipped, 5 warnings`;
- Ruff: passed;
- Pyright: `0 errors, 0 warnings`;
- live presentation audit: `status=ok`, `violations=[]`; and
- fresh E1, E2, E3-A, E3-B, E3-C, E3-D, and E3-E validators: `7/7 passed`;
  `identity_refresh=not_required`.

Career independently read back the targeted repair in the correct isolated worktree environment:

- focused targeted suite: `266 passed, 5 warnings`;
- live presentation audit: `status=ok`;
- repair diff/check and exact 14-path scope: passed;
- canonical retrieval digests and current 0.1.4 wheel-guide contract: passed;
- external 60-wheel and complete historical 61-wheel manifests: independently recomputed and
  matched the recorded values; and
- frozen direct-audio receipt, v0.1.3 release note, OCR authority, and evaluation artifacts:
  unchanged.

The docs-only commit containing this acceptance record becomes the sole accepted HEAD for any
later Task 8 candidate work. Any later tracked write invalidates that candidate authority and
requires renewed review.

## Accepted Dependency-Authority Version-Boundary Repair

The first Task 8 attempt stopped before terminal execution because two controller checks coupled
the fresh candidate identity to the canonical receipt's unique historical MKE version:

1. candidate receipt structure validation required the fresh filename and version to equal the
   historical `0.1.3` candidate row; and
2. package-set projection required each historical installed MKE row's version to equal the fresh
   candidate version instead of replacing exactly that source identity.

The accepted TDD repair is exact range
`4fffc3e3941475ccf7d8ff7ceb5d6ea9010ff42c..a921f2a2f5dea9e27512b67e521f758fc899f9cb`,
with final tree `1dbd9a8b80c7077e3104ce144da8066dae2f0e6c`. Its scope is exactly
`scripts/direct_audio_deployment_proof.py` and
`tests/scripts/test_direct_audio_deployment_proof.py`.

The repair leaves `validate_committed_receipt()` and the canonical receipt internally strict and
unchanged. It validates the fresh universal candidate independently, preserves every historical
external distribution/version row, and replaces exactly one historical MKE row per Python cell
with candidate version `0.1.4` for the authorization projection. The canonical receipt remains
historical `0.1.3`.

Execution-window evidence:

- two focused regressions reproduced the stale-version couplings as RED and passed after repair;
- committed repair diff: exactly two files, 78 insertions, and 15 deletions;
- deployment-proof/receipt adjacency: `357 passed, 5 warnings`;
- full pytest: `3100 passed, 14 skipped, 5 warnings`;
- Ruff: passed;
- Pyright: `0 errors, 0 warnings`;
- model-free product proof: `8/8 passed`;
- live presentation audit: `status=ok`, `violations=[]`;
- canonical retrieval validators: `7/7 passed`, `identity_refresh=not_required`; and
- canonical receipt SHA-256:
  `49196028327ba0d34be5bcabfeb55bd6d455f4e68e88a35e858e7c30db8ef111`.

Independent targeted verification:

- committed focused receipt/deployment suites: `333 passed, 5 warnings`;
- fresh candidate structure, historical-to-fresh package projection, and current
  lock/constraints two-cell roots all passed;
- Python 3.12 and 3.13 roots are each 5,819 bytes with SHA-256
  `f0ac3270d71054d6879175637d197f5fa0fe52546bf94b7319967891aa3e133e`;
- both projected package sets use `0.1.4` while the canonical receipt remains `0.1.3`;
- missing or duplicate historical rows, missing or duplicate projected candidate rows,
  non-universal fresh tags, and unsatisfied candidate requirements remain fail-closed;
- Ruff, Pyright, diff/check, exact two-file scope, and clean worktree/index passed; and
- receipt bytes, external dependency authority, authorization schema, and the public four-field
  aggregate are unchanged.

The targeted review verdict is `CLEAN / ACCEPTED` with zero findings. All candidate,
authorization, or terminal evidence produced before accepted repair HEAD
`a921f2a2f5dea9e27512b67e521f758fc899f9cb` is historical only and is not final candidate
authority.

## Explicit Non-Claims And Next Gate

This state does not claim:

- a built or installed final v0.1.4 wheel;
- terminal authorization readiness or real-ASR execution;
- model accuracy, cross-platform support, production resource defaults, uptime, throughput, SLA,
  adoption, business impact, registry publication, or uploaded Release assets;
- OCR production support;
- a pushed branch, PR, hosted checks, merge, tag, GitHub Release, source-archive smoke, immutable
  publication evidence, post-release documentation closeout, or cleanup.

The next gate is a separately authorized fresh Task 8. It must restart retained-input and
repository verification with accepted repair HEAD
`a921f2a2f5dea9e27512b67e521f758fc899f9cb` as the reviewed repair authority and the new docs-only
acceptance commit as the repository authority. Candidate generation, authorization-only, and real
terminal execution remain prohibited in this closure.
