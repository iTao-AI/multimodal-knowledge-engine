# v0.1.4 Post-Release Closeout

Status: `FINAL POST-RELEASE CLOSEOUT RECORD`

Date: 2026-07-24

## Release-Candidate And Merge Authority

- Release-candidate PR: <https://github.com/iTao-AI/multimodal-knowledge-engine/pull/88>
- Reviewed head: `0a60ff6b63ed497cc570456ad0e1b13a99b56e6d`
- Squash merge commit: `84fb533072a965b2ad833d12723e6ac0fff19d55`
- Reviewed feature tree and merge tree:
  `b1d5a0c767e04dd4d402163f16f3ebdce8b1a787`
- Merged at: `2026-07-23T18:35:15Z`

The exact-head merge gates were reconciled before the ordinary squash merge. The reviewed tree
and merge tree are equal. Nine observed exact-main check runs completed successfully on the merge
commit: Python 3.12 and 3.13, both embedding-extra cells, uv graph, both CodeQL analyses,
consumer source-pack proof, and Compiled Library Export proof.

PR #88 is the release-candidate authority. Its immutable `v0.1.4` tag and public GitHub Release
continue to point to release commit `84fb533072a965b2ad833d12723e6ac0fff19d55`; they do not point
to the later documentation work.

## Post-Release Documentation Authority

- Post-release PR: <https://github.com/iTao-AI/multimodal-knowledge-engine/pull/89>
- Reviewed head: `6a03765b25edd5a0b2c432ad3b3bf705ca36b7d4`
- Reviewed tree: `071100feb51dd041c41020f71426b75ebffd7654`
- Squash merge commit: `dbecc45b51e0b884c6c34a329e147310b1e3f83b`

PR #89's reviewed tree equals its squash-merge tree. Its original four-file scope remains
historical PR #89 scope; this later truth-repair candidate is an independent follow-up and is not
retroactively described as part of PR #89's diff.

## Exact-Main Verification

Fresh verification from clean exact main produced:

- full pytest: `3100 passed, 14 skipped, 5 warnings`;
- Ruff: passed; Pyright: 0 errors and 0 warnings; build: passed;
- product proof: 8/8; demo: passed;
- local-knowledge proof, Evidence-provenance proof, and model-free direct-audio proof: passed;
- release-presentation audit: `status=ok` with zero violations;
- fresh E1/E2/E3-A/E3-B observations and all seven E1 through E3-E validators: passed;
- installed release smoke and two-interpreter source-pack/Compiled Export proofs: passed; and
- exact-main wheel equality with the reviewed terminal wheel: passed.

The reviewed/merge tree and exact wheel equality made another real-ASR/controller invocation
unnecessary and prohibited. No real ASR was rerun on exact main.

## Candidate And Terminal Co-Binding

- Wheel: `multimodal_knowledge_engine-0.1.4-py3-none-any.whl`
- Wheel bytes: `353324`
- Wheel SHA-256:
  `3b3c19fd87d015762a6d446e0e47f8719c87218734faa141915a17cca1fa72e3`
- Exact-main sdist SHA-256:
  `0cdb711be8a47ac0016df005af9f9bb6257c5001e0ce7cdf70d57a8e35ff39be`
- Exact-main candidate receipt canonical digest:
  `5b20bbbc829eeb4fa4d066fa83bd1d97f8544ba7865f2db563f1405a0b628b4f`
- Exact-main candidate receipt file SHA-256:
  `f7ceae28989bae12d568a611513a3fac6f848967a3eac923398bb5110de934c2`
- Exact-main candidate receipt source commit:
  `84fb533072a965b2ad833d12723e6ac0fff19d55`
- Reviewed terminal receipt SHA-256:
  `91f3bfcb5e8ef1d1b12d4a31724e0f92f3507ea25c7afaa940e5c430777339fc`

The Task 8 candidate wheel, exact-main wheel, candidate source-pack proof, installed smoke,
Compiled Library Export proof, and terminal authorization/proof all bind the same wheel digest.
The accepted terminal proof returned `mke.direct_audio_deployment_proof.v1`, `status=passed`, and
`canonical=true` across CPython 3.12 and 3.13. Its bounded fixed-fixture evidence covered Python,
CLI, stdio MCP, published Runs, timestamp Evidence, Search/Ask, repeated equal Export v2 trees,
standalone v2 consumption, cache-only model use, network denial, supervision within the supplied
owner budget, and cleanup.

This evidence does not establish transcript accuracy, a production SLA, hard sandboxing,
cross-platform support, arbitrary media support, or external-binary redistribution authority.

## Publication

- Tag: `v0.1.4`
- Annotated tag object: `5453f2d787185a318794d47f084c0f952939946e`
- Peeled target: `84fb533072a965b2ad833d12723e6ac0fff19d55`
- GitHub Release:
  <https://github.com/iTao-AI/multimodal-knowledge-engine/releases/tag/v0.1.4>
- Created at: `2026-07-23T19:06:45Z`
- Published at: `2026-07-23T19:07:19Z` by `iTao-AI`
- State: latest at publication, public, non-draft, non-prerelease
- Additional assets: 0

The tag object and local/remote peeled target were read back after publication. The Release title,
tag, body, author, timestamps, state, latest identity, and zero-asset inventory were also read
back. No wheel, receipt, model, fixture, dependency wheel, or proof log was uploaded.

## Public Archive Identity

- Archive: `multimodal-knowledge-engine-v0.1.4.tar.gz`
- Bytes: `4214296`
- SHA-256:
  `e9492e5115110c5fa421c565c51226ba0e25d16a62230f92760f13b1ec1a76ce`
- Reconstructed tree:
  `b1d5a0c767e04dd4d402163f16f3ebdce8b1a787`

The GitHub-generated archive was descriptor-read, safely extracted, and reconstructed to the
exact tagged tree. Locked sync, product proof 8/8, demo, local-knowledge proof,
Evidence-provenance proof, and model-free direct-audio proof passed. The model-free lane reported
`asr_execution=not_performed` and did not use network access.

## Archive-Safe Compiled Library Gate

The release plan initially invoked `scripts/compiled_library_export_proof.py` from the Git-less
public archive. The first invocation omitted `--mke-wheel` and failed closed with
`candidate_artifact_invalid`. A bounded correction built one wheel from the safely extracted
archive; it was 353324 bytes and exactly matched the reviewed wheel SHA-256. Supplying that wheel
to the same controller still failed closed with the same code.

Read-only investigation confirmed the deterministic source-authority mismatch:

1. `run_proof()` selects `_supplied_candidate()` when `--mke-wheel` is present.
2. `_supplied_candidate()` calls `_candidate_source()` before the supplied-wheel copy boundary.
3. `_candidate_source()` requires `_clean_sha1_source_commit()` and a clean Git snapshot.
4. A GitHub source archive has no `.git`, so the controller fails before opening, copying, or
   validating the supplied wheel.

No third generic-controller proof was run. No synthetic `.git`, operator Git metadata, private
helper, code fix, or error-taxonomy expansion was introduced.

The corrected archive-safe authority used the documented native public lane:

- ingest the public PDF fixture;
- ingest the public video fixture with its documented sidecar;
- run a real `mke ... library export`;
- descriptor-audit the generated export tree;
- run the standalone standard-library consumer with exact source mappings; and
- run the release-presentation audit from the archive environment.

The native Export returned two Sources and three Evidence records. Its v1 manifest SHA-256 was
`dd273ce0ee94095a3fa120b5b3cc0444462fb7a3c344c49703f2dbd024ce082b`; the portable schema was
`mke.compiled_library_export.v1`, with `mke.compiled_markdown.v1` and
`mke.evidence_ref.v1`. The standalone consumer returned `status=passed`,
`fingerprint_mapping=exact`, and `portable_copy=true`. The presentation audit returned
`status=ok` with zero violations.

The two generic-controller failures remain real fail-closed history. The native Export and
standalone consumer are the actual Task 11 archive-smoke authority; this is not a claim that the
failed controller invocation later passed.

## Known Controller Limitation

The repository has no native-boundary regression for a Git-less public archive plus an exact
supplied wheel. A future version may add an explicit, non-circular source-authority input and
corresponding regression, or keep archive verification on the archive-safe native consumer lane.
`v0.1.4` did not change the controller and does not claim this limitation is fixed.

## PR #89 Docs-Only Scope And Verification

PR #89 changed exactly:

- the approved v0.1.4 release-closeout design;
- the v0.1.4 release-closeout implementation plan;
- `docs/how-to/verify-release.md`; and
- this new post-release closeout review.

It records immutable publication facts and corrects the durable archive-smoke contract. It does
not change product/controller code, tests, version identity, dependency receipts, evaluation
artifacts, release notes, historical v0.1.3 records, tag, Release, or public archive.

Its docs-only verification recorded:

- Focused release documentation and presentation suite: `271 passed`.
- Live release-presentation audit: `status=ok`, zero violations.
- Markdown fence and relative-link checks: passed.
- Public-neutral, new-diff control-metadata, absolute private-path, GStack-artifact, and
  credential-assignment scans: passed.
- Exact changed-file scope: the four approved documentation paths.
- `git diff --check`: passed.

The `document-release` audit found no new public behavior and no missing release-documentation
quadrant. The immutable record has reference coverage in this review, task-oriented archive
instructions in `docs/how-to/verify-release.md`, and rationale/history in the design and plan.
Existing tutorials remain accurate because the docs-only closeout adds no user workflow.
No architecture diagram changed or drifted, and no VERSION or TODOS file required an update. A
later independent truth-repair candidate corrects release-facing README and consumer-proof framing
without changing PR #89 history or immutable publication identity.

## Distribution And Non-Claims

PyPI and other package registries were not used. No service, model, container, or package was
deployed or published outside the zero-asset GitHub Release. The release does not claim production
readiness, adoption, business impact, transcript accuracy, hostile-media containment, a hard
aggregate RSS ceiling, or cross-platform provider support.

## Retained Evidence And Cleanup

Call-owned private publication, archive-smoke, exact-main, and Task 8 evidence remain retained
outside the repository. Task-owned release-candidate and post-release branches/worktrees were
cleaned after their retained merged history and verification evidence were confirmed. The detached
historical-source worktree remains retained and untouched, as do operator-owned dependency
wheelhouse, model, direct-audio evidence, unrelated worktrees/branches, caches, Docker resources,
and external compatibility evidence.

No post-release closeout gate remains for PR #89. Immutable tag and Release identity remain the
PR #88 release commit; the independent truth-repair candidate must receive its own review and
verification and makes no publication, tag, or release mutation.
