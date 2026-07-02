# v0.1.0 Release Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this
> plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare MKE for a trustworthy `v0.1.0` release without adding new runtime capabilities.

**Architecture:** Split the release into a presentation-readiness PR, a consumer-smoke PR, and a
final tag/release action. Stage 1 updates release identity, public docs, and audit coverage. Stage 2
proves the built package works outside the source checkout. Stage 3 only tags and publishes after
the first two stages merge.

**Tech Stack:** Python 3.12/3.13, uv, Hatch, pytest, Ruff, Pyright, existing MKE CLI/MCP contracts,
existing evaluation artifact validators, `gstack-document-release` as the pre-PR documentation
audit.

---

Planning base: `main@24691fb0805e4a46bcad41f1699cbef52e65589a`.

Design: [v0.1.0 Release Readiness Design](../specs/2026-07-02-v0-1-0-release-readiness-design.md).

Use `high` reasoning depth. Do not use `xhigh` unless a release-positioning or runtime-contract
reversal is required.

## Non-Negotiable Boundaries

- Do not add dense, hybrid, RRF, reranker, query rewrite, segmentation, OCR, HTTP, UI, API adapter,
  LangChain, LlamaIndex, LangGraph, Milvus, Redis, or pgvector runtime behavior.
- Do not change Search, Ask, MCP, owner startup, Publication, ingestion, or the current runtime
  default except for version strings and release documentation.
- Do not download models or external fixtures for the core release gate.
- Do not tag, publish a GitHub Release, push, create PRs, or merge without explicit authorization.
- Keep all public docs neutral. Do not copy private planning material, local private paths, raw GStack
  artifacts, or local cache paths into the repository.
- If `gstack-document-release` produces risky narrative changes, stop and return findings to the
  planning window.

## Stage 1: Release Presentation Readiness PR

Recommended branch:

```bash
cd <multimodal-knowledge-engine>
git switch main
git fetch origin
git pull --ff-only
git switch -c codex/v0-1-0-release-readiness
```

### Task 0: Baseline inventory

**Files:**

- Read: `AGENTS.md`
- Read: `pyproject.toml`
- Read: `src/mke/__init__.py`
- Read: `README.md`
- Read: `README_CN.md`
- Read: `docs/README.md`
- Read: `docs/reference/contracts.md`
- Read: `docs/how-to/enable-cjk-retrieval.md`
- Read: `docs/how-to/evaluate-dense-retrieval.md`
- Read: `docs/how-to/evaluate-relevance-gate-reranker.md`
- Read: `docs/superpowers/reviews/2026-06-27-cjk-active-scan-runtime-promotion-implementation-review.md`
- Read: `docs/superpowers/reviews/2026-06-28-local-dense-retrieval-candidate-review.md`
- Read: `docs/superpowers/reviews/2026-06-30-cjk-lexical-dense-rrf-fusion-review.md`
- Read: `docs/superpowers/reviews/2026-06-30-cjk-relevance-gate-reranker-review.md`

- [ ] **Step 1: Confirm clean latest base**

Run:

```bash
git status --short --branch
git rev-parse HEAD origin/main
gh pr list --state open --json number,title,headRefName,mergeStateStatus,isDraft,url
```

Expected: branch is clean, based on latest `origin/main`, and no open prerequisite PR blocks release
readiness.

- [ ] **Step 2: Record current version and release surface**

Run:

```bash
python - <<'PY'
from pathlib import Path
print(Path("pyproject.toml").read_text().split('version = "')[1].split('"')[0])
print(Path("src/mke/__init__.py").read_text().split('__version__ = "')[1].split('"')[0])
PY
rg -n "0\\.0\\.0|0\\.1\\.0|runtime_promotion_status|holdout_gate_status|valid_negative|not_evaluated|cjk-active-scan-overlap-v1" README.md README_CN.md docs pyproject.toml src/mke/__init__.py
```

Expected: current version is still `0.0.0`; E3 release facts are visible and need release-level
organization.

### Task 1: Add release presentation audit

**Files:**

- Create: `scripts/release_presentation_audit.py`
- Create: `tests/scripts/test_release_presentation_audit.py`

- [ ] **Step 1: Write RED tests for release drift**

Create tests that assert the audit rejects:

- mismatched `pyproject.toml` and `src/mke/__init__.py` versions;
- missing `cjk-active-scan-overlap-v1` in README or README_CN;
- release-facing docs claiming dense/RRF/reranker runtime support;
- release-facing docs missing comparison-only language for E3-C/D/E;
- stale phrases such as `not merged`, `pending implementation`, or `runtime_promotion_status=not_evaluated` in release entry points where they would confuse readers;
- local absolute paths under `/Users/`, model cache paths, raw GStack artifact paths, credentials, or stack traces.

Run:

```bash
uv run pytest tests/scripts/test_release_presentation_audit.py -q
```

Expected before implementation: tests fail because `scripts/release_presentation_audit.py` does not
exist.

- [ ] **Step 2: Implement the audit**

Implement a small Python script with this interface:

```bash
uv run python scripts/release_presentation_audit.py --root .
```

Success output:

```json
{"status":"ok","violations":[]}
```

Failure output:

```json
{"status":"failed","violations":[{"file":"README.md","rule":"...","message":"..."}]}
```

The script should inspect only tracked repository files and should not read external model caches,
private directories, or raw GStack artifacts.

- [ ] **Step 3: Verify audit tests pass**

Run:

```bash
uv run pytest tests/scripts/test_release_presentation_audit.py -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit audit**

```bash
git add scripts/release_presentation_audit.py tests/scripts/test_release_presentation_audit.py
git commit -m "test(release): add v0.1.0 presentation audit"
```

### Task 2: Set release version identity

**Files:**

- Modify: `pyproject.toml`
- Modify: `src/mke/__init__.py`
- Create or modify: `tests/test_version_identity.py`

- [ ] **Step 1: Add version consistency test**

Test that the project version in `pyproject.toml` equals `mke.__version__` and equals `0.1.0`.

Run:

```bash
uv run pytest tests/test_version_identity.py -q
```

Expected before version update: fails because current version is `0.0.0`.

- [ ] **Step 2: Update version strings**

Change:

- `pyproject.toml`: `version = "0.1.0"`
- `src/mke/__init__.py`: `__version__ = "0.1.0"`

- [ ] **Step 3: Verify version identity**

Run:

```bash
uv run pytest tests/test_version_identity.py -q
uv build
```

Expected: test passes and wheel metadata reports `0.1.0`.

- [ ] **Step 4: Commit version identity**

```bash
git add pyproject.toml src/mke/__init__.py tests/test_version_identity.py
git commit -m "chore(release): set v0.1.0 package identity"
```

### Task 3: Add release notes and CHANGELOG

**Files:**

- Create: `CHANGELOG.md`
- Create: `docs/releases/v0.1.0.md`

- [ ] **Step 1: Create release notes**

`docs/releases/v0.1.0.md` must include:

- release identity and commit placeholder language that will be filled after merge;
- shipped runtime capabilities;
- E3 decision table from the design;
- verification commands;
- explicit non-goals;
- known limitations;
- optional extras boundaries;
- upgrade path for `0.1.x` and `0.2.0`.

- [ ] **Step 2: Create CHANGELOG**

`CHANGELOG.md` must include:

```markdown
# Changelog

## [0.1.0] - 2026-07-02

### Added
...

### Verified
...

### Not included
...
```

Do not overclaim runtime dense, RRF, or reranker support.

- [ ] **Step 3: Verify release docs are linked and clean**

Run:

```bash
rg -n "dense.*runtime|RRF.*runtime|reranker.*runtime|0\\.0\\.0|placeholder-marker" CHANGELOG.md docs/releases/v0.1.0.md
git diff --check
```

Expected: no stale version or placeholder hits. Hits for non-goals are acceptable only if the text
clearly says they are not included.

- [ ] **Step 4: Commit release notes**

```bash
git add CHANGELOG.md docs/releases/v0.1.0.md
git commit -m "docs(release): add v0.1.0 release notes"
```

### Task 4: Rewrite public entry points for release posture

**Files:**

- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `docs/README.md`

- [ ] **Step 1: Rewrite README.md**

README must lead with:

- what MKE is;
- what `v0.1.0` can do;
- quick verification command;
- CLI/MCP positioning;
- current Chinese retrieval runtime;
- comparison-only evidence section;
- explicit non-goals.

Keep detailed historical E3 paragraphs out of the top section. Link to release notes and how-to
guides instead.

- [ ] **Step 2: Rewrite README_CN.md**

Match the English README claims. Do not let README_CN lag on:

- `cjk-active-scan-overlap-v1` default;
- E3-C/D/E comparison-only status;
- `0.1.0` release identity;
- core proof commands.

- [ ] **Step 3: Update docs/README.md navigation**

Add release notes and release verification docs to the navigation. Keep superpowers docs as
history, not primary first-run material.

- [ ] **Step 4: Run entry-point checks**

Run:

```bash
uv run python scripts/release_presentation_audit.py --root .
python - <<'PY'
from pathlib import Path
for path in ["README.md", "README_CN.md", "docs/README.md"]:
    text = Path(path).read_text()
    assert "v0.1.0" in text or "0.1.0" in text, path
    assert "cjk-active-scan-overlap-v1" in text, path
print("entry points mention release identity and runtime")
PY
```

Expected: audit passes and all entry points mention the release identity and runtime default.

- [ ] **Step 5: Commit entry points**

```bash
git add README.md README_CN.md docs/README.md
git commit -m "docs(release): refresh public entry points for v0.1.0"
```

### Task 5: Run document-release audit

**Files:**

- May modify: release-facing docs only if the audit finds factual drift.
- May modify: `docs/how-to/verify-release.md` if generated as a required missing how-to.

- [ ] **Step 1: Run `gstack-document-release` from the feature branch**

Run the skill as a documentation audit. It should review README, docs index, release notes,
contract docs, and how-to coverage.

Expected output: coverage map and specific file findings.

- [ ] **Step 2: Apply factual doc fixes only**

Allowed automatic fixes:

- stale links;
- missing release notes links;
- version mismatch;
- docs index omissions;
- obvious E3 status wording drift.

Stop for planning review if the audit proposes:

- new product positioning;
- removal of large sections;
- architecture claim changes;
- a version bump beyond `0.1.0`;
- new generated docs beyond `docs/how-to/verify-release.md`.

- [ ] **Step 3: Commit audit fixes**

```bash
git add <exact modified docs>
git commit -m "docs(release): apply documentation release audit"
```

### Task 6: Full Stage 1 verification

**Files:**

- No new files unless validation exposes a defect in release docs or audit tests.

- [ ] **Step 1: Run full verification**

Run:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
uv run python scripts/release_presentation_audit.py --root .
git diff --check origin/main...HEAD
```

Expected: all commands pass.

- [ ] **Step 2: Record completion evidence**

Update this plan with:

- final branch name;
- final HEAD;
- verification results;
- release audit result;
- unresolved risks.

- [ ] **Step 3: Commit completion record**

```bash
git add docs/superpowers/plans/2026-07-02-v0-1-0-release-readiness-implementation.md
git commit -m "docs(release): record v0.1.0 readiness verification"
```

### Task 7: Pre-PR review gate

- [ ] **Step 1: Stop for planning-window review**

Do not push or create a PR yet. Hand off:

- branch;
- HEAD;
- diff stat;
- changed files;
- verification results;
- release audit output;
- documentation audit summary;
- known non-goals.

The planning window should run authoritative pre-PR review before push.

## Stage 2: Release Consumer Smoke PR

Start only after Stage 1 is merged.

Recommended branch:

```bash
git switch main
git fetch origin
git pull --ff-only
git switch -c codex/v0-1-0-consumer-smoke
```

### Task 8: Add installed-package smoke script

**Files:**

- Create: `scripts/release_consumer_smoke.py`
- Create: `tests/scripts/test_release_consumer_smoke.py`
- Create or modify: `docs/how-to/verify-release.md`

- [ ] **Step 1: Add tests for source-tree isolation**

The script must fail if `mke.__file__` resolves inside the repository during installed smoke.

- [ ] **Step 2: Implement smoke script**

The script should:

- build or accept a wheel path;
- create a temp venv outside the repository;
- install the wheel;
- clear `PYTHONPATH`, `PYTHONHOME`, and `VIRTUAL_ENV`;
- run from an external cwd;
- execute `mke proof run`;
- execute `mke demo --verify`;
- run a minimal CLI Search/Ask path over a temp database;
- run an MCP contract or owner-startup smoke that does not require a long-lived external service;
- print JSON with `status=passed` or stable failure codes.

- [ ] **Step 3: Keep optional extras separate**

The core smoke must not install `[embedding]` or `[transcription]`. Optional extra smoke may be
documented but must not block the core release.

### Task 9: Run Stage 2 verification

Run:

```bash
uv run pytest tests/scripts/test_release_consumer_smoke.py -q
uv build
uv run python scripts/release_consumer_smoke.py --wheel dist/*.whl --json
uv run pytest -q
uv run ruff check .
uv run pyright
uv run mke proof run
uv run mke demo --verify
git diff --check origin/main...HEAD
```

Expected: all core smoke and repository checks pass.

Stop for planning review before push.

## Stage 3: Tag And GitHub Release

Start only after Stage 1 and Stage 2 are merged and `main` is clean.

### Task 10: Release gate

Before tag:

```bash
git switch main
git fetch origin
git pull --ff-only
git status --short --branch
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
uv run python scripts/release_presentation_audit.py --root .
uv run python scripts/release_consumer_smoke.py --wheel dist/*.whl --json
```

Expected: all pass.

### Task 11: Create release

Only after explicit user authorization:

```bash
git tag -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0
gh release create v0.1.0 --notes-file docs/releases/v0.1.0.md
```

Then run release archive smoke from a fresh temp directory. Record exact tag, commit, archive hash,
and smoke result.

## Deferred Work

Do not include in `v0.1.0`:

- dense runtime promotion;
- hybrid/RRF runtime;
- reranker runtime;
- query rewrite;
- segmentation;
- OCR;
- HTTP/UI;
- API adapters;
- model bakeoffs.

Create separate specs for these only after `v0.1.0` release evidence is stable.
