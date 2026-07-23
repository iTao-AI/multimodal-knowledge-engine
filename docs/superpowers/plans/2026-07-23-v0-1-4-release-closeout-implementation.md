# v0.1.4 Release Closeout Implementation Plan

Status: approved plan source; pending mechanical landing, actual-diff review, and staged execution.

> **For implementers:** Use `superpowers:executing-plans` as the primary implementation
> controller, `superpowers:test-driven-development` for current-identity and presentation changes,
> `superpowers:systematic-debugging` for unexpected failures, `document-release` for the
> release-documentation audit, and `superpowers:verification-before-completion` before every
> completion claim. Do not run competing full-branch controllers.

**Goal:** Publish `v0.1.4` with bounded direct-audio intake as the primary capability, mixed-Library
Compiled Library Export v2 and isolated LLM Wiki compatibility as supporting evidence, and the
merged Torch/Setuptools security maintenance accurately recorded.

**Architecture:** Use one ordered five-stage chain: release-candidate PR, reviewed clean candidate
and one real terminal proof, exact merged-main artifact equality, annotated tag/GitHub Release and
public archive smoke, then a docs-only immutable closeout PR. Keep the accepted dependency receipt
byte-identical and independently bind the fresh `0.1.4` terminal wheel through the existing
non-circular candidate authority.

**Tech Stack:** Python 3.12 and 3.13, uv, Hatchling, pytest, Ruff, Pyright, SQLite, stdio MCP,
faster-whisper, PyAV/FFmpeg, Markdown, Git, GitHub Actions, and GitHub Releases.

## Provenance And Starting State

- Approved baseline: `32e4ed2a457e5a4affd21bd83d5a86983c5dbf11`.
- Baseline tree: resolve and record before creating the task worktree.
- Existing package identity: `0.1.3`.
- Target package/tag identity: `0.1.4` / `v0.1.4`.
- Existing latest release: `v0.1.3`, public, non-draft, non-prerelease, zero assets.
- Existing `v0.1.3` tag target:
  `86b8a2d85631f5e94afa49186909ac62ffd54a15`.
- Current exact-main hosted state at plan approval: ten successful check-runs.
- Open PR, Dependabot alert, and code-scanning alert inventories at approval: empty.
- Direct-audio feature chain: PRs #81, #84, and #85, merged.
- LLM Wiki compatibility evidence: PR #83, merged.
- Security maintenance: Torch PR #79 and Setuptools PR #87, merged.
- Approved design destination:
  `docs/superpowers/specs/2026-07-23-v0-1-4-release-closeout-design.md`.
- This plan destination:
  `docs/superpowers/plans/2026-07-23-v0-1-4-release-closeout-implementation.md`.

Before any write:

1. read repository `AGENTS.md`;
2. fetch current remote refs without changing the checkout;
3. require a clean primary checkout and `main == origin/main`;
4. inventory open PRs, tags, Releases, security alerts, checks, branches, and worktrees;
5. verify `v0.1.4` is absent locally and remotely;
6. record the pre-existing detached historical-source evidence worktree without modifying it; and
7. stop if `main` moved from the approved baseline until the intervening diff is reviewed.

## Global Constraints

- Release closeout changes version, presentation, documentation, and mechanical provenance only.
- Do not change direct-audio runtime behavior, SQLite schema, public DTOs, CLI/MCP schemas, Export
  v1/v2 schemas, retrieval strategy, dependency versions, workflows, fixtures, model identity, or
  supervision behavior.
- Do not replay or regenerate `benchmarks/audio/dependency-artifacts.json`.
- Keep the canonical dependency receipt file SHA-256
  `49196028327ba0d34be5bcabfeb55bd6d455f4e68e88a35e858e7c30db8ef111`
  and payload digest
  `c6cc4b963e4a5a53fe6df51c52430f20e09f9194a6723f4f0958b7d521b903f9`.
- Keep `docs/releases/v0.1.3.md` and completed v0.1.3/direct-audio implementation history
  byte-identical.
- Do not global-replace `0.1.3` or `v0.1.3`.
- `uv.lock` may change only in the root project version. Compare parsed package/dependency
  projections before and after.
- Keep OCR receipts and scorecard byte-identical.
- Keep external direct-audio wheelhouse, model cache, fixtures, and retained evidence read-only.
- Do not download a model, voice, fixture, wheel, interpreter, or dependency.
- Use explicit distinct CPython 3.12 and 3.13 executables.
- The owner-selected terminal proof pair is `2147483648 / baseline_plus`. It is proof input only,
  not a runtime default or recommendation.
- Local candidate and proof outputs remain outside Git.
- No tracked write may occur after the final reviewed candidate/terminal sequence.
- Push, PR creation, Ready transition, merge, tag, GitHub Release, publication, and cleanup each
  remain separate authorization gates.

## File And Responsibility Map

### Approved release design and plan

- new `docs/superpowers/specs/2026-07-23-v0-1-4-release-closeout-design.md`;
- new `docs/superpowers/plans/2026-07-23-v0-1-4-release-closeout-implementation.md`.

### Current version and installed smoke

- `pyproject.toml`;
- `src/mke/__init__.py`;
- `uv.lock`;
- `tests/test_version_identity.py`;
- `tests/test_bootstrap.py`;
- `scripts/release_consumer_smoke.py`;
- `tests/scripts/test_release_consumer_smoke.py`.

### Release presentation contract

- `scripts/release_presentation_audit.py`;
- `tests/scripts/test_release_presentation_audit.py`;
- `tests/evaluation/test_direct_audio_documentation.py`;
- `tests/evaluation/test_compiled_library_export_documentation.py`;
- `tests/evaluation/test_consumer_source_pack_documentation.py`;
- `tests/evaluation/test_repository_governance_documentation.py`.

### Current release documentation

- `README.md`;
- `README_CN.md`;
- `CHANGELOG.md`;
- `docs/README.md`;
- new `docs/releases/v0.1.4.md`;
- `docs/how-to/verify-release.md`;
- `docs/how-to/run-consumer-source-pack-proof.md`;
- `docs/how-to/run-compiled-library-export-proof.md`;
- `docs/how-to/run-direct-audio-proof.md`;
- `docs/how-to/use-direct-audio.md`;
- `docs/how-to/use-local-transcription.md`;
- `docs/how-to/export-compiled-library.md`;
- `docs/how-to/use-mke-mcp.md`;
- `docs/tutorials/getting-started.md`;
- `docs/reference/cli.md`;
- `docs/reference/contracts.md`;
- `docs/reference/mcp-contract.md`;
- `docs/decisions/0011-bounded-direct-audio-intake.md`.

Modify only files proven by focused current-release tests or exact scans to describe the current
release. Report every additional file and stop for authority if it changes product behavior.

### Conditional retrieval identity closure

At most the established 21-path release/evaluation allowlist. Use the smallest validator-proven
dependency-closed subset produced through `artifact_refresh` and a detached validation mirror.

### Durable review and closeout

- new
  `docs/superpowers/reviews/2026-07-23-v0-1-4-release-implementation-review.md`;
- new
  `docs/superpowers/reviews/2026-07-23-v0-1-4-post-release-closeout.md`;
- the approved design and this plan;
- `docs/how-to/verify-release.md` during the post-release docs-only closure.

---

## Task 1: Establish The Release Worktree And Land Approved Authority

**Files:** the approved release design and plan only.

- [x] **Step 1: Reconcile live entry authority**

Run read-only entry checks:

```bash
git fetch --prune origin
git status --short --branch
git rev-parse HEAD main origin/main
git worktree list --porcelain
git branch --all --verbose --no-abbrev
git tag --list 'v0.1.4'
git ls-remote --tags origin refs/tags/v0.1.4
gh pr list --state open --json number,title,isDraft,headRefName,baseRefName,url
gh release view v0.1.3 --json tagName,name,isDraft,isPrerelease,publishedAt,url,assets
```

Also read current exact-main check-runs and open Dependabot/code-scanning alerts once. Do not poll.

Expected: clean/equal baseline, no v0.1.4 tag/Release, no open PR, no open security alert.

- [x] **Step 2: Create one isolated release worktree**

Create:

```text
branch: codex/v0-1-4-release-closeout
worktree: .worktrees/v0-1-4-release-closeout
```

Do not modify the primary checkout or the pre-existing detached historical-source evidence
worktree.

- [x] **Step 3: Mechanically land the approved design and plan**

Copy the approved public-neutral sources byte-for-byte into their destination paths. Do not edit,
reinterpret, abbreviate, or add private source paths.

Validate:

```bash
git diff --check
git status --short
```

Require exact two-file scope and balanced Markdown fences.

- [x] **Step 4: Commit and hard stop for actual-diff review**

Stage only the two new files and commit:

```bash
git commit -m "docs(release): define v0.1.4 closeout"
```

Report source/destination SHA-256 equality, commit SHA, branch/worktree state, and exact diff.
Do not start Task 2 until the authoritative reviewer accepts the landed bytes.

---

## Task 2: Lock The `0.1.4` Package And Installed-Smoke Identity

**Files:** current version and installed-smoke group.

- [x] **Step 1: Write current-version RED tests**

Update current identity assertions to require:

```python
assert pyproject["project"]["version"] == "0.1.4"
assert mke.__version__ == "0.1.4"
```

Require release consumer smoke to accept only:

```text
multimodal_knowledge_engine-0.1.4-py3-none-any.whl
module version 0.1.4
installed metadata version 0.1.4
```

Run:

```bash
UV_OFFLINE=1 uv run --frozen --no-sync pytest -q \
  tests/test_version_identity.py \
  tests/test_bootstrap.py \
  tests/scripts/test_release_consumer_smoke.py
```

Expected RED: only current version/wheel identity mismatches.

- [x] **Step 2: Bump current package identity**

Set `0.1.4` only in:

- `pyproject.toml`;
- `src/mke/__init__.py`;
- current release consumer smoke implementation.

Refresh the lock without network:

```bash
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never uv lock --offline
```

Parse old and new `uv.lock` files. Require only root
`multimodal-knowledge-engine 0.1.3 -> 0.1.4`; all dependency names, versions, sources, markers,
hashes, extras, and resolution graphs remain equal.

- [x] **Step 3: Run GREEN and commit**

Run the focused tests again, then:

```bash
git diff --check
```

Stage only the seven version/smoke files and commit:

```bash
git commit -m "chore(release): set v0.1.4 identity"
```

---

## Task 3: Define The `v0.1.4` Presentation Contract

**Files:** release presentation contract group.

> **Career authority amendment (2026-07-23):** Tasks 3 and 4 are one atomic
> RED -> docs -> GREEN lane because the presentation audit must reject an incomplete live
> repository while the current v0.1.4 release note and entry-point documentation do not exist.
> The reproducible RED may therefore include both missing Task 4 release surfaces and stale
> candidate wording. No RED intermediate commit is permitted; the combined lane lands only after
> all Task 3/4 documentation and live-audit gates are GREEN.

- [x] **Step 1: Add RED tests for current release surfaces**

Require:

- `EXPECTED_VERSION == "0.1.4"`;
- `docs/releases/v0.1.4.md` is the current release note;
- English and Chinese README current headings describe v0.1.4;
- direct audio is described as released under its bounded platform/profile/owner constraints;
- Export v2 and LLM Wiki compatibility keep their authority boundaries;
- `docs/releases/v0.1.3.md` remains a historical release record;
- the direct-audio ADR is no longer labeled only as an unreleased candidate;
- exact release wheel references use `0.1.4`; and
- overclaims remain rejected.

Add negative/wrapped/contradiction coverage for at least:

- arbitrary or full-length audio;
- cross-platform provider support;
- implicit model download or cloud fallback;
- transcript accuracy or production SLA;
- external wheel/native-binary redistribution;
- bundled/automatic LLM Wiki integration;
- hosted deployment, adoption, or business impact;
- PyPI/registry publication; and
- uploaded Release assets.

Run:

```bash
UV_OFFLINE=1 uv run --frozen --no-sync pytest -q \
  tests/scripts/test_release_presentation_audit.py \
  tests/evaluation/test_direct_audio_documentation.py \
  tests/evaluation/test_compiled_library_export_documentation.py \
  tests/evaluation/test_consumer_source_pack_documentation.py \
  tests/evaluation/test_repository_governance_documentation.py
```

Expected RED: missing v0.1.4 current release surfaces and stale candidate wording.

- [x] **Step 2: Update the audit minimally**

Change current-release constants and release-facing file inventory to v0.1.4. Preserve historical
v0.1.3 checks. Add only the narrow claim guards proven RED.

Do not replace the audit with a generic natural-language classifier.

- [x] **Step 3: Run GREEN without an intermediate commit**

Run the focused suite plus:

```bash
UV_OFFLINE=1 uv run --frozen --no-sync python \
  scripts/release_presentation_audit.py --root . --json
```

Require `status=ok` and zero violations on live repository content.

Do not commit at this point. Continue in the same uncommitted worktree through Task 4.

---

## Task 4: Write Current v0.1.4 Release Documentation (Atomic With Task 3)

**Files:** current release documentation group.

- [x] **Step 1: Inventory current versus historical version text**

Run exact scans for:

```text
0.1.3
v0.1.3
v0.1.4 candidate
accepted candidate
not a released capability
terminal real ASR has not run
```

Classify every match:

1. current release identity that must become v0.1.4;
2. historical v0.1.3 fact that must remain;
3. synthetic test value that remains local to its test; or
4. ambiguous text requiring a focused failing test before modification.

Do not global-replace.

- [x] **Step 2: Add `docs/releases/v0.1.4.md`**

The release note must contain:

- bounded direct-audio headline;
- supported formats and 15-minute/100-MiB limits;
- Darwin-arm64, explicit owner, prepared cache, and owner-supplied supervision boundary;
- Python/CLI/MCP, Publication, Search/Ask, timestamp Evidence;
- Export v1/v2 behavior and standalone v2 consumer;
- isolated LLM Wiki compatibility evidence;
- Torch/Setuptools maintenance;
- verification surfaces; and
- explicit non-goals.

It must not contain private paths, transient IDs, raw transcripts, model output, unverified metrics,
or retained evidence locations.

- [x] **Step 3: Update current entry points**

Update README, README_CN, changelog, docs index, verification guides, direct-audio guides,
getting-started, CLI/MCP/contracts, and ADR-0011 only where they describe current release state.

Keep:

- historical v0.1.3 release note and closeout bytes;
- v0.1.3 statements that compatibility/direct audio were not shipped at that historical time;
- comparison-only retrieval wording;
- OCR evaluation-only wording; and
- direct-audio dependency/license evidence as external historical authority.

- [x] **Step 4: Run documentation and presentation gates**

Run the focused suites from Task 3, all release documentation contract tests, Markdown fence/link
checks available in the repository, and:

```bash
UV_OFFLINE=1 uv run --frozen --no-sync python \
  scripts/release_presentation_audit.py --root . --json
git diff --check
```

Run `document-release` as a report/audit controller. It may identify required documentation gaps,
but must not push, publish, alter version choice, or create a PR.

- [x] **Step 5: Commit**

Commit:

```bash
git commit -m "docs(release): prepare v0.1.4 candidate"
```

---

## Task 5: Close Retrieval Provenance Identity Mechanically

**Files:** validator-proven subset of the established 21-path allowlist only.

- [x] **Step 1: Run all seven canonical validators before writing**

Generate fresh E1, E2, E3-A, and E3-B observations. E2 uses an exclusive call-owned protocol copy
whose scope is refreshed before observation.

Run canonical validators for:

1. E1 baseline;
2. E2 numeric;
3. E3-A Chinese;
4. E3-B CJK lexical;
5. E3-C dense;
6. E3-D hybrid RRF; and
7. E3-E relevance gate.

Record exact failures. If all pass, skip refresh and do not create an empty identity commit.

- [x] **Step 2: Run the accepted transaction only when required**

Use `artifact_refresh`, deterministic builders, and a detached validation mirror. Do not manually
edit generated artifacts.

Begin with the smallest failing dependency set. Expand only when a downstream validator proves a
new identity dependency. Hard stop if the closure exceeds the established 21-path allowlist.

- [x] **Step 3: Prove byte and semantic equality**

Require:

- generated/staged/mirror/worktree byte equality for every closure path;
- all seven validators pass in the detached mirror;
- normalized before/after semantic projections equal;
- no observation, result ordering, metric, threshold, gate, diagnostic, profile, candidate, status,
  or verdict change; and
- no corpus, qrels, query, fixture, runtime selector, or quality conclusion change.

- [x] **Step 4: Commit only a real closure**

Commit:

```bash
git commit -m "test(eval): refresh v0.1.4 release identities"
```

Skip the commit when no path changed.

---

## Task 6: Record Pre-Review Candidate State

**Files:**

- this plan;
- new
  `docs/superpowers/reviews/2026-07-23-v0-1-4-release-implementation-review.md`.

- [x] **Step 1: Freeze historical authority**

Descriptor-read and record without modification:

- canonical direct-audio receipt file and payload digests;
- constraints and external wheelhouse identities;
- three audio fixture digests;
- accepted model identifier/revision/tree identity when retained inputs are present;
- OCR frozen receipt/scorecard digests;
- historical v0.1.3 release note SHA-256; and
- complete changed-file and version/lock semantic audits.

- [x] **Step 2: Write durable pre-review state**

Record:

- starting baseline and commit series;
- exact scope and diff;
- release claim matrix;
- current/historical version-text classification;
- lock semantic equality;
- evaluation closure result;
- frozen receipt/OCR identities;
- focused verification;
- status `PENDING AUTHORITATIVE ACTUAL-DIFF REVIEW`; and
- explicit non-claims.

Do not mark proof, PR, merge, tag, Release, archive, or cleanup complete.

- [x] **Step 3: Commit and hard stop**

Commit:

```bash
git commit -m "docs(release): record v0.1.4 candidate state"
```

Run focused docs/presentation checks and `git diff --check`, then stop for the authoritative
whole-branch actual-diff review.

---

## Task 7: Close Authoritative Review Before Candidate Generation

**Files:** only files required by accepted findings plus the plan/review.

- [ ] **Step 1: Review the complete branch**

Review:

- actual diff against exact baseline;
- version and lock identity;
- current versus historical documentation;
- public claim boundaries;
- dependency receipt immutability and fresh-candidate split;
- candidate/proof/merge/tag ordering;
- evaluation closure;
- security and private-data scans; and
- rollback and cleanup.

Use one whole-branch review. Do not run a competing full review in parallel.

- [ ] **Step 2: Return findings to the execution controller**

For every finding:

- reproduce it;
- classify severity and authority impact;
- use TDD for behavior/contract repairs;
- keep scope surgical; and
- rerun targeted plus required complete verification.

Use `superpowers:receiving-code-review` for repairs. Findings do not automatically authorize a
broader design.

- [ ] **Step 3: Targeted re-review**

Default to targeted actual-diff re-review. Repeat full review only for a material scope,
architecture, authority, or public-claim change.

- [ ] **Step 4: Commit final acceptance before candidate work**

Update the review to `CLEAN / ACCEPTED`, record exact reviewed HEAD/range and verification, and
ensure every tracked implementation/review write is complete.

Commit:

```bash
git commit -m "docs(release): accept v0.1.4 candidate review"
```

After this commit, a new tracked write invalidates Task 8 evidence.

---

## Task 8: Build And Prove The Reviewed Candidate

**Files:** no tracked changes.

- [ ] **Step 1: Verify clean candidate and retained inputs**

Require:

- exact accepted HEAD and clean worktree/index;
- explicit distinct CPython 3.12 and 3.13;
- no active task-owned child process;
- sufficient call-owned temporary disk;
- canonical dependency receipt file and payload exact;
- constraints and external wheelhouse exact;
- fixture exact;
- prepared model exact;
- Export v2 consumer exact;
- Darwin arm64 deny-network authority available; and
- no download or repair needed.

If an input is absent or drifting, stop. Do not acquire or regenerate it.

- [ ] **Step 2: Run repository gates**

```bash
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never uv run --frozen --no-sync pytest -q
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never uv run --frozen --no-sync ruff check .
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never uv run --frozen --no-sync pyright
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never uv build
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never uv run --frozen --no-sync mke proof run
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never uv run --frozen --no-sync mke demo --verify
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never uv run --frozen --no-sync python \
  scripts/local_knowledge_proof.py --json
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never uv run --frozen --no-sync python \
  scripts/evidence_provenance_proof.py --json
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never uv run --frozen --no-sync python \
  scripts/release_presentation_audit.py --root . --json
git diff --check
git status --short
```

Also regenerate fresh observations and run all seven canonical validators on the exact accepted
HEAD. Remove the exclusive E2 protocol copy and prove it absent.

- [ ] **Step 3: Generate one strict candidate output**

Run:

```bash
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never uv run --frozen --no-sync python \
  scripts/consumer_source_pack_proof.py \
  --python "$PYTHON312" \
  --python "$PYTHON313" \
  --candidate-output "$CANDIDATE_OUTPUT" \
  --json
```

Require exactly:

```text
candidate-artifact-receipt.json
multimodal_knowledge_engine-0.1.4-py3-none-any.whl
```

Independently descriptor-read the directory, wheel, and canonical receipt. Require:

- `mke.candidate_artifact_receipt.v1`;
- source commit equals exact accepted HEAD;
- package/version equals `multimodal-knowledge-engine 0.1.4`;
- exact wheel filename, bytes, and SHA-256;
- proof status passed;
- `proof_input_wheel_sha256 == wheel_sha256`; and
- receipt self-digest valid.

- [ ] **Step 4: Co-bind installed proof surfaces**

Use the exact candidate-output wheel:

```bash
UV_OFFLINE=1 uv run --frozen --no-sync python scripts/release_consumer_smoke.py \
  --wheel "$MKE_WHEEL" --json

UV_OFFLINE=1 uv run --frozen --no-sync python scripts/compiled_library_export_proof.py \
  --python "$PYTHON312" \
  --python "$PYTHON313" \
  --mke-wheel "$MKE_WHEEL" \
  --json

UV_OFFLINE=1 uv run --frozen --no-sync mke proof direct-audio --json
```

Require:

- installed release smoke reports `0.1.4`;
- source-pack and compiled-export proofs pass on both interpreters;
- Compiled Library Export v1 and v2 plus standalone v2 consumer pass;
- compiled proof wheel SHA equals candidate receipt wheel SHA; and
- model-free direct-audio reports
  `proof_mode=model_free` and `asr_execution=not_performed`.

- [ ] **Step 5: Run authorization-only**

Validate the dependency receipt statically without modifying it. Run the direct-audio controller
with `--authorization-only`, the exact fresh wheel, explicit retained inputs, and:

```text
direct_audio_footprint_bytes=2147483648
direct_audio_footprint_budget_mode=baseline_plus
```

Use the accepted direct-script entrypoint:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 UV_OFFLINE=1 \
UV_PYTHON_DOWNLOADS=never \
uv run --frozen --no-sync python scripts/direct_audio_deployment_proof.py \
  --python "$PYTHON312" \
  --python "$PYTHON313" \
  --mke-wheel "$MKE_WHEEL" \
  --dependency-receipt benchmarks/audio/dependency-artifacts.json \
  --wheelhouse "$TRANSCRIPTION_WHEELHOUSE" \
  --constraints "$TRANSCRIPTION_CONSTRAINTS" \
  --model-root "$MKE_MODEL_ROOT" \
  --fixture-root tests/fixtures/audio \
  --direct-audio-footprint-bytes 2147483648 \
  --direct-audio-footprint-budget-mode baseline_plus \
  --receipt "$DIRECT_AUDIO_PROOF_RECEIPT" \
  --authorization-only \
  --json
```

Require `mke.direct_audio_terminal_authorization.v1`, `status=ready`, exact manifest/stdout semantic
equality, complete input binding, deny-network method, cleanup owner, and no venv/model/ASR/product
execution.

- [ ] **Step 6: Run one real terminal invocation**

Invoke the accepted controller exactly once with the frozen authorization inputs:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 UV_OFFLINE=1 \
UV_PYTHON_DOWNLOADS=never \
uv run --frozen --no-sync python scripts/direct_audio_deployment_proof.py \
  --python "$PYTHON312" \
  --python "$PYTHON313" \
  --mke-wheel "$MKE_WHEEL" \
  --dependency-receipt benchmarks/audio/dependency-artifacts.json \
  --wheelhouse "$TRANSCRIPTION_WHEELHOUSE" \
  --constraints "$TRANSCRIPTION_CONSTRAINTS" \
  --model-root "$MKE_MODEL_ROOT" \
  --fixture-root tests/fixtures/audio \
  --direct-audio-footprint-bytes 2147483648 \
  --direct-audio-footprint-budget-mode baseline_plus \
  --receipt "$DIRECT_AUDIO_PROOF_RECEIPT" \
  --json
```

Require:

- schema `mke.direct_audio_deployment_proof.v1`;
- `status=passed`, `canonical=true`;
- Python 3.12 and 3.13 installed identity;
- MP3/WAV/M4A Python and CLI paths plus the specified MCP path;
- published Runs, timestamp Evidence, Search/Ask;
- repeated equal Export v2 trees and standalone consumer;
- cache-only accepted model identity;
- network blocked;
- every supervision observation uses the owner pair and remains within budget;
- process group absent and runtime roots cleaned; and
- aggregate/receipt semantic equality.

Record exact wheel/receipt/model/fixture/export/proof digests and observations. Do not claim
accuracy, production, SLA, hard sandboxing, cross-platform behavior, or redistribution.

On failure, hard stop. Do not retry, replay manually, or expand diagnostics without new authority.

- [ ] **Step 7: Stop without tracked writes**

Report exact HEAD, tree, commit series, changed files, diff stat, test counts, candidate receipt,
wheel, all proof identities, terminal aggregate, non-claims, and retained evidence ownership.

Do not update a checkbox or review after this point.

---

## Task 9: Push And Create The Release-Candidate Pull Request

**Files:** no tracked changes.

- [ ] **Step 1: Obtain separate push/PR authorization**

Do not infer authorization from local acceptance.

- [ ] **Step 2: Push normally and create Draft PR**

Use no force, rebase, amend, or base merge. PR title:

```text
release: prepare v0.1.4
```

The Simplified Chinese body must include:

- result-focused summary;
- release capability and non-claims;
- exact reviewed HEAD/tree;
- exact wheel and candidate receipt identities;
- terminal proof summary;
- actual verification;
- documentation impact;
- risk/rollback;
- zero-asset/PyPI/deploy boundary; and
- exactly the real pending checks/merge gates.

Read back title, body, base, head, Draft state, mergeability, comments, reviews, threads, and one
checks snapshot. Stop without polling.

- [ ] **Step 3: Repair only event-backed failures**

Any code/docs change invalidates Task 8. After an authorized repair:

- TDD the root cause;
- rerun required verification;
- repeat authoritative targeted review;
- rebuild the candidate;
- rerun authorization-only and one newly authorized terminal proof; and
- update the PR body with new exact identities.

---

## Task 10: Merge And Establish Exact-Main Artifact Authority

**Files:** no tracked changes.

- [ ] **Step 1: Verify exact-head merge authority**

Require:

- all expected exact-head checks completed/success;
- reviewed head equals PR head;
- no unresolved comments/reviews/threads;
- PR body gates reconciled and read back;
- mergeable state clean; and
- separate Ready/merge authorization.

- [ ] **Step 2: Ordinary squash merge**

Mark Ready only after rechecking authority. Use ordinary squash merge, never admin/force.

Record PR, reviewed head/tree, merge SHA/parent/tree, author, and time. Require reviewed tree equals
merge tree.

- [ ] **Step 3: Verify exact-main hosted state**

Synchronize primary `main` and require:

```text
HEAD == main == origin/main == merge SHA
primary worktree clean
```

Observe exact-main checks through one bounded snapshot. Keep release worktree/branch until all
expected checks succeed.

- [ ] **Step 4: Build exact-main candidate authority**

From clean exact main:

- rerun full repository gates and seven validators;
- build fresh wheel/sdist;
- generate a fresh candidate source-pack receipt binding the merge SHA;
- run release smoke, Compiled Export, model-free direct audio, and presentation audit; and
- require exact-main wheel SHA equals the reviewed Task 8 terminal wheel SHA.

Do not rerun real ASR when reviewed/merge tree equality and exact wheel equality hold.

If the wheel digest differs, hard stop before tag. Do not silently substitute it or rerun the
controller.

- [ ] **Step 5: Hard stop before publication**

Report exact merged-main authority and request separate tag/GitHub Release authorization.

---

## Task 11: Publish `v0.1.4` And Verify The Public Archive

**Files:** no tracked changes before publication.

- [ ] **Step 1: Reconcile publication preconditions**

Require:

- exact-main candidate complete;
- `v0.1.4` absent locally/remotely;
- no open release blocker;
- candidate and terminal wheel equality;
- release notes match actual diff and non-claims; and
- separate publication authorization.

- [ ] **Step 2: Create and push one annotated tag**

Create annotated `v0.1.4` at the exact merge SHA and push only the tag.

Read back:

- tag object SHA;
- object type `tag`;
- peeled commit target;
- annotation; and
- local/remote equality.

- [ ] **Step 3: Create the GitHub Release**

Create:

```text
name: v0.1.4
tag: v0.1.4
draft: false
prerelease: false
assets: 0
```

Use the reviewed release note content. Do not upload local artifacts.

Read back persisted Release metadata and confirm it is latest.

- [ ] **Step 4: Public source-archive smoke**

Download the public GitHub-generated source archive into a call-owned root. Descriptor-read and
record bytes/SHA-256, extract safely, and prove the source tree is the tag target.

Run locked/offline-capable archive gates:

```bash
uv sync --locked
uv run mke proof run
uv run mke demo --verify
uv run python scripts/local_knowledge_proof.py --json
uv run python scripts/evidence_provenance_proof.py --json
uv run mke proof direct-audio --json
uv run python scripts/compiled_library_export_proof.py \
  --python "$PYTHON312" \
  --python "$PYTHON313" \
  --json
uv run python scripts/release_presentation_audit.py --root . --json
```

Run the standalone Compiled Library consumer against the generated output. Do not run real ASR,
download a model, or introduce operator-only inputs into the public archive smoke.

- [ ] **Step 5: Preserve immutable publication evidence**

Record tag, Release, archive, smoke, and exact-main identities outside tracked files. Do not mutate
the tag or Release after successful readback.

---

## Task 12: Post-Release Docs-Only Closeout

**Files:**

- approved design;
- this plan;
- `docs/how-to/verify-release.md`;
- new
  `docs/superpowers/reviews/2026-07-23-v0-1-4-post-release-closeout.md`.

- [ ] **Step 1: Create isolated docs-only branch**

Branch from exact post-release `main`:

```text
codex/v0-1-4-post-release-closeout
```

Require clean/equal primary and unchanged tag/Release.

- [ ] **Step 2: Write immutable release record**

Record:

- release-candidate PR and merge identity;
- reviewed/merge tree equality;
- exact-main checks;
- exact-main wheel and candidate receipt;
- terminal proof co-binding;
- tag object and peeled target;
- Release URL/state/author/time/assets;
- public archive filename/bytes/SHA-256;
- archive smoke results;
- PyPI/registry/deploy not performed; and
- retained evidence and cleanup boundaries.

Mark design/plan complete without rewriting historical v0.1.3 or implementation evidence.

- [ ] **Step 3: Verify docs-only diff**

Run focused release documentation/presentation tests, live presentation audit, Markdown checks,
public-neutral/private-path/secret scans, `git diff --check`, and exact file-scope audit.

Commit:

```bash
git commit -m "docs(release): record v0.1.4 publication"
```

- [ ] **Step 4: Authoritative docs-only review and PR**

Run one bounded actual-diff review. After acceptance and separate authorization, push and create a
Draft docs-only PR. Reconcile body/checks, merge normally, and verify reviewed/merge tree equality
and exact-main checks.

- [ ] **Step 5: Fresh immutable-state verification**

After docs merge, verify again:

- tag object and target unchanged;
- Release public/non-draft/non-prerelease/latest;
- assets still zero;
- presentation audit passes; and
- primary main is clean/equal.

- [ ] **Step 6: Safe task-owned cleanup**

Only after successful exact-main checks:

- remove the clean release and post-release task worktrees;
- delete their local and remote branches;
- prune stale worktree and tracking metadata;
- verify open PR count zero; and
- report final branch/worktree inventory.

Do not modify or remove:

- the pre-existing detached historical-source evidence worktree;
- operator-owned direct-audio wheelhouse/model/evidence;
- LLM Wiki compatibility retained evidence;
- unrelated caches, branches, worktrees, Docker resources, or Releases.

---

## Final Acceptance Matrix

| Requirement | Blocking authority |
|---|---|
| Package identity `0.1.4` | pyproject/module/lock/smoke tests and exact wheel metadata |
| Bounded direct audio released honestly | release note, docs contracts, presentation audit |
| Python/CLI/MCP product path | merged tests plus reviewed terminal proof |
| Timestamp Evidence/Search/Ask | terminal proof aggregate and canonical lifecycle tests |
| Export v1 compatibility/v2 completeness | same-wheel proof, equal trees, standalone consumer |
| LLM Wiki boundary | accepted isolated evidence and explicit non-dependency/non-authority wording |
| Dependency/license authority | unchanged committed receipt and static validation |
| Fresh candidate authority | strict candidate receipt and non-circular terminal binding |
| Python 3.12/3.13 | source-pack/export/terminal installed cells |
| Retrieval non-regression | seven validators and semantic equality closure |
| Security readiness | zero open Dependabot/code-scanning alerts at release gate |
| Publication identity | annotated tag, exact target, public zero-asset Release |
| Archive integrity | public archive digest and source-archive smoke |
| Closeout | docs-only PR, fresh immutable-state proof, safe task-owned cleanup |

## Stop Conditions

Stop immediately when:

- baseline or reviewed head changes unexpectedly;
- worktree/index is dirty for unknown reasons;
- current and historical release identity cannot be separated;
- dependency graph changes beyond root version;
- canonical dependency receipt or retained external input drifts;
- a model/wheel/interpreter/fixture input is absent and would require acquisition;
- evaluation closure exceeds allowlist or changes semantics;
- actual-diff review is not clean;
- terminal authorization is not ready;
- the single real controller invocation fails;
- a tracked write occurs after terminal proof;
- reviewed tree differs from merge tree;
- exact-main wheel differs from reviewed terminal wheel;
- tag/Release identity conflicts;
- public archive smoke fails; or
- cleanup ownership is ambiguous.

No stop condition authorizes an automatic retry, receipt replay, model download, force/admin merge,
tag replacement, Release mutation, PyPI publication, deployment, or broad cleanup.
