# Repository Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a verified development baseline and public documentation governance before feature implementation begins.

**Architecture:** Keep the bootstrap intentionally small: a Python package and CLI smoke path, repository policy, Diataxis documentation, ADRs, and required CI checks. Do not implement product-domain behavior in this plan.

**Tech Stack:** Python 3.12, uv, hatchling, pytest, Ruff, Pyright, GitHub Actions.

---

### Task 1: Verify Bootstrap Package

**Files:**
- Modify: `src/mke/cli.py`
- Test: `tests/test_bootstrap.py`

- [ ] **Step 1: Run the bootstrap tests**

Run: `uv run pytest -q`

Expected: `2 passed`.

- [ ] **Step 2: Run static checks**

Run: `uv run ruff check .`

Expected: `All checks passed!`

Run: `uv run pyright`

Expected: `0 errors`.

- [ ] **Step 3: Run the CLI smoke**

Run: `uv run mke`

Expected: `multimodal-knowledge-engine: bootstrap stage`

### Task 2: Add Required CI

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/pull_request_template.md`
- Create: `uv.lock`

- [ ] **Step 1: Add a CI workflow**

The workflow must cancel redundant runs for the same Git ref, check out the repository, install `uv`, select Python 3.12, run `uv sync --locked`, then run `uv run pytest -q`, `uv run ruff check .`, and `uv run pyright`.

- [ ] **Step 2: Add the PR template**

The template must contain `Summary`, `Completion`, `Verification`, `Documentation impact`, and optional `Risk / Migration`.

- [ ] **Step 3: Generate and verify the dependency lock**

Run: `uv lock`

Expected: `uv.lock` exists and resolves the project and development dependencies.

Run: `uv lock --check`

Expected: exit code `0`.

- [ ] **Step 4: Validate workflow and template presence**

Run: `test -f .github/workflows/ci.yml && test -f .github/pull_request_template.md`

Expected: exit code `0`.

### Task 3: Verify Documentation Governance

**Files:**
- Modify: `docs/README.md`
- Modify: `README.md`
- Modify: `README_CN.md`

- [ ] **Step 1: Check required document roots**

Run:

```bash
test -f AGENTS.md
test -f docs/decisions/0001-local-first-pilot-architecture.md
test -f docs/superpowers/specs/2026-06-13-pilot-design.md
test -f docs/superpowers/plans/2026-06-13-bootstrap-implementation.md
```

Expected: exit code `0`.

- [ ] **Step 2: Scan for private or premature claims**

Run: `git grep -n "/Users/" -- ':!docs/superpowers/plans/2026-06-13-bootstrap-implementation.md'`

Expected: no matches.

### Task 4: Prepare The Local Bootstrap Commit

**Files:**
- Modify: all intentional bootstrap files

- [ ] **Step 1: Review the complete diff**

Run: `git status --short && git diff --check && git diff --stat`

Expected: only bootstrap files; no whitespace errors.

- [ ] **Step 2: Stage intentional files**

Run:

```bash
git add .github .gitignore AGENTS.md README.md README_CN.md docs pyproject.toml src tests uv.lock
```

Expected: only intended bootstrap files are staged.

- [ ] **Step 3: Commit locally**

Run: `git commit -m "chore: bootstrap multimodal knowledge engine"`

Expected: local commit on `codex/bootstrap`. Do not push or create a PR without explicit authorization.
