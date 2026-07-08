# v0.1.1 Release Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Prepare a locally verified `v0.1.1` release candidate whose package identity, release documentation, audit gates, and installed-wheel evidence agree without publishing it.

**Architecture:** Keep the shipped runtime and public contracts unchanged. Treat `v0.1.0` release metadata as immutable history, move current release-facing checks to `v0.1.1`, and make the real stdio MCP local knowledge proof the patch release's primary addition.

**Tech Stack:** Python 3.12/3.13, Hatchling, uv, pytest, Ruff, Pyright, Markdown.

## Global Constraints

- Start from clean `main@4e52542610b803df7bfe6dcb7648d464484e8f81` in the isolated worktree.
- Do not change MCP, runtime, Search, Ask, Publication, retrieval protocol, or evaluation metrics.
- Do not publish PyPI, push, create a PR, create a tag, or create a GitHub Release.
- Keep dense, RRF, and reranker as comparison-only evidence.
- Preserve the published `v0.1.0` release identity as historical documentation.

---

### Task 1: Lock the v0.1.1 identity contract with RED tests

**Files:**
- Modify: `tests/test_version_identity.py`
- Modify: `tests/test_bootstrap.py`
- Modify: `tests/scripts/test_release_presentation_audit.py`
- Modify: `tests/scripts/test_release_consumer_smoke.py`

**Interfaces:**
- Consumes: package metadata, `mke.__version__`, release-facing Markdown, built-wheel metadata.
- Produces: failing assertions that require `0.1.1`, `docs/releases/v0.1.1.md`, current README labels, and installed-wheel identity `0.1.1`.

- [x] **Step 1: Change version and release-audit expectations to `0.1.1`**
- [x] **Step 2: Run targeted tests and confirm failures are caused by the still-current `0.1.0` implementation**
- [x] **Step 3: Record the exact RED failures before implementation edits**

### Task 2: Update package and release-gate implementation identity

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `src/mke/__init__.py`
- Modify: `scripts/release_presentation_audit.py`
- Modify: `scripts/release_consumer_smoke.py`

**Interfaces:**
- Consumes: Task 1 tests.
- Produces: one `0.1.1` package identity, a `v0.1.1` presentation audit, and consumer smoke that rejects any installed module or metadata version other than `0.1.1`.

- [x] **Step 1: Set package and module versions to `0.1.1` and refresh `uv.lock` mechanically**
- [x] **Step 2: Point release audit files and labels at `v0.1.1`**
- [x] **Step 3: Set installed-wheel consumer smoke identity to `0.1.1`**
- [x] **Step 4: Run the targeted identity and release-gate tests to GREEN**

### Task 3: Publish repository-visible v0.1.1 release documentation

**Files:**
- Modify: `CHANGELOG.md`
- Create: `docs/releases/v0.1.1.md`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `docs/README.md`
- Modify: `docs/how-to/verify-release.md`
- Modify: current wheel-command examples under `docs/how-to/` and `docs/reference/`
- Modify: `docs/superpowers/plans/2026-07-07-local-knowledge-proof-implementation.md`
- Modify: `docs/superpowers/reviews/2026-07-08-local-knowledge-proof-review.md`

**Interfaces:**
- Consumes: merged PR #58 facts, merge commit `4e52542610b803df7bfe6dcb7648d464484e8f81`, post-merge CI/CodeQL results, and the stable local knowledge proof command.
- Produces: public-neutral release notes and navigation that identify the real stdio MCP local knowledge proof as the core `v0.1.1` addition while preserving all runtime boundaries.

- [x] **Step 1: Add the `0.1.1` CHANGELOG entry and release notes without inventing tag or Release metadata**
- [x] **Step 2: Update bilingual README and docs navigation to the current release**
- [x] **Step 3: Update release verification and wheel command examples to `0.1.1`**
- [x] **Step 4: Record PR #58 merge and post-merge CI/CodeQL status in the durable local-knowledge plan/review**
- [x] **Step 5: Run targeted documentation and presentation-audit tests**

### Task 4: Verify and commit the release candidate

**Files:**
- Review: all branch changes against `main@4e52542610b803df7bfe6dcb7648d464484e8f81`
- Modify: only files needed to resolve verified release-closeout failures.

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: one atomic local commit on a clean branch, with no remote or release side effects.

- [x] **Step 1: Run targeted release/version tests**
- [x] **Step 2: Run full pytest, Ruff, Pyright, and build**
- [x] **Step 3: Run release presentation audit and installed-wheel consumer smoke; require reported version `0.1.1`**
- [x] **Step 4: Run product proof 8/8, demo, local knowledge proof, and E1-E3-E canonical validators**
- [x] **Step 5: Run public-boundary scan and `git diff --check`**
- [x] **Step 6: Review the final diff, update this completion record, create one atomic commit, and confirm the worktree is clean**

## Completion Record

Completed locally on 2026-07-08 from `main@4e52542610b803df7bfe6dcb7648d464484e8f81`.

- TDD RED: four focused failures proved the package, audit, and consumer-smoke implementation still
  expected `0.1.0` before the minimal version changes.
- Targeted release/version suite: `73 passed`; focused package/audit/consumer/local-proof suite:
  `61 passed` before the expanded documentation checks.
- Full suite: `1320 passed, 5 skipped`; five existing PyMuPDF/SWIG deprecation warnings remained.
- Ruff: clean. Pyright: `0 errors, 0 warnings, 0 informations`.
- Build: `multimodal_knowledge_engine-0.1.1.tar.gz` and
  `multimodal_knowledge_engine-0.1.1-py3-none-any.whl` built successfully.
- Installed-wheel consumer smoke: `status=passed`, `version=0.1.1`, with install, identity, product
  proof, demo, CLI, and MCP steps passed outside the source checkout.
- Product proof: `8 passed, 0 failed`. Demo: `result=passed`. Local knowledge proof:
  `status=passed` with two published Runs, two page Evidence records, one Search hit, one cited Ask,
  and one zero-citation `insufficient_evidence` refusal.
- Release presentation audit: `status=ok`, zero violations.
- E1 through E3-E canonical validators: passed after identity-only artifact dependency closure.
  The E1-E3-B atomic refresh enforced semantic preservation; E3-C, E3-D, and E3-E normalized
  observations, metrics, thresholds, gates, diagnostics, and verdict/status remained equal.
- PR #58 durable closeout records the squash merge at `4e52542610b803df7bfe6dcb7648d464484e8f81`
  and successful post-merge CI/CodeQL.
- No MCP/runtime/Search/Ask behavior changed. No push, PR, tag, GitHub Release, or PyPI publication
  was performed from this closeout branch.

## Pre-PR Review Remediation

The authoritative pre-PR review found two P1 release-process integrity issues:

1. `docs/how-to/verify-release.md` said Stage 1 and Stage 2 run together for `v0.1.1`, but its
   Stage 2 section still required a separate branch after Stage 1 merged.
2. Four current release-facing command blocks used `--wheel dist/*.whl`, although the consumer
   smoke accepts exactly one wheel and a shell wildcard can expand to multiple old build outputs.

Both findings were reproduced with audit RED tests before implementation changes. The release
guide now allows Stage 1 and Stage 2 on one final release-candidate branch, requires the complete
gate to run again on the resulting `main` commit before tagging, and keeps tag/GitHub Release
creation behind separate authorization. Current release-facing commands now name
`dist/multimodal_knowledge_engine-0.1.1-py3-none-any.whl` exactly; the published `v0.1.0` record is
unchanged.

- RED evidence: `5 failed, 1 passed` across the new focused cases.
- GREEN evidence: `6 passed` across the same cases.
- Audit scope guard: a follow-up RED case reproduced an over-broad `CHANGELOG.md` match; the
  rule was limited to the four current command documents, then all audit tests passed (`50 passed`).
- Targeted release/version/consumer-smoke suite: `80 passed`.
- Full suite after follow-up remediation: `1328 passed, 5 skipped`; Ruff and Pyright passed; sdist
  and wheel builds passed in the release-closeout gate.
- Installed-wheel consumer smoke: `status=passed`, `version=0.1.1`. Product proof: `8/8`; demo
  and local knowledge proof passed.
- E1 through E3-E canonical validators, release presentation audit, relative-link check,
  public-boundary and stale-wording scans, and `git diff --check`: passed.
- First targeted re-review: one P1 remained because the wildcard regex only matched a single-line
  consumer-smoke command. A real multiline command reproduced the gap (`1 failed`); the audit now
  rejects `dist/*.whl` directly in the same four current command documents (`1 passed`, full audit
  tests `51 passed`) without extending to `CHANGELOG.md` or the `v0.1.0` history.
- Follow-up targeted re-review: pending.
- Durable review: [v0.1.1 Release Closeout Review](../reviews/2026-07-08-v0-1-1-release-closeout-review.md).
