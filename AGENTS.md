# AGENTS.md

This file defines the execution rules for Codex when working in this repository.

## Project Purpose

Multimodal Knowledge Engine is a local-first, Agent-callable Evidence engine for ingesting, searching, and asking questions over documents and media.

The first verified product slice proves:

- Text-layer PDFs and the documented short local video fixture can be ingested through observable Runs.
- Search and Ask return stable page or timestamp Evidence from active Publications.
- Failed or partial processing never becomes searchable.
- CLI and MCP use one canonical application contract. HTTP and workspace UI remain planned.

## Explicit Non-Goals

- Do not rebuild the legacy `multimodal-rag-ocr` service layout or APIs.
- Do not create a hosted multi-tenant platform, RBAC system, billing system, or distributed control plane in the first slice.
- Do not introduce LangGraph into the first slice.
- Do not make LangChain, LlamaIndex, or a retrieval SDK part of domain or application contracts.
- Do not copy private planning material, personal motivations, private paths, or unverified metrics into this repository.

## Source Of Truth

Priority order:

1. Actual code, tests, migrations, configuration, and command output.
2. Accepted ADRs in `docs/decisions/`.
3. Current public specifications and plans in `docs/superpowers/`.
4. Issues and PR descriptions.
5. External GStack artifacts and historical notes.

If sources conflict, report the conflict. Do not silently follow an older plan over current code, or silently change an accepted ADR.

## Required Reading By Change Type

| Change | Read first |
|---|---|
| Any implementation | `AGENTS.md`, relevant tests, current Git status |
| Domain or persistence | `docs/explanation/architecture.md`, relevant ADRs |
| HTTP, CLI, or MCP contract | generated contract reference and contract tests |
| Retrieval or evaluation | retrieval ADR, benchmark manifest, eval tests |
| Run, Evidence, or Publication | publication and provenance explanations |
| User workflow or frontend | getting-started guide and affected how-to guides |

If a referenced document does not exist yet, inspect the relevant implementation and tests instead. Do not invent its contents.

## Canonical Vocabulary

Public product concepts are:

`Library`, `Source`, `Asset`, `Run`, `Artifact`, `Segment`, `Passage`, `Evidence`, and `Publication`.

- Public API paths do not include speculative `/api`, `/v1`, or `/v2` segments.
- Do not expose legacy product terms such as `knowledge_base`, product-level `collection`, `chunk`, `job`, `fast`, or `accurate`.
- Provider and storage implementation names may appear only in configuration, manifests, adapters, benchmarks, and ADRs.

## Architecture Constraints

- The domain and application layers use project-owned DTOs and ports.
- SQLite is domain truth for the first Pilot. Retrieval indexes are rebuildable projections.
- Assets and Artifacts are immutable and content-addressed.
- Search and Ask read only active Publications.
- A retry creates a new immutable Run. Crash recovery may resume the same Run only after checkpoint and fingerprint validation.
- Any required-stage, embedding-batch, or indexing failure must fail the Run and prevent Publication switching.
- Random vectors and silent fallbacks are prohibited.
- The current runtime is local CLI plus stdio MCP over one owner process and SQLite. A future
  `mke serve` process must keep the same domain and application contracts.

Changing any constraint above requires an ADR in the same PR.

## Framework Reuse And Project-Owned Logic

- Before building ingestion, parsing, retrieval, MCP, process-control, or provider infrastructure, inspect the installed library and framework versions, existing adapters, relevant source boundaries, and current official documentation.
- Prefer native capabilities behind project-owned ports when they satisfy the approved contract, deterministic tests, offline and privacy requirements, authority separation, compatibility, and maintenance cost. Keep project-owned logic when framework semantics do not match or would introduce unnecessary coupling, hosted dependencies, runtime side effects, or migration risk. Framework runtime, index, trace, or checkpoint state never owns `Library`, `Run`, `Evidence`, or `Publication` authority.

## Working Model

Codex is the primary project Agent and owns planning, implementation, testing, documentation, PR preparation, and final verification.

Use GStack and Superpowers when they match the task:

- Ambiguous product or architecture work: `superpowers:brainstorming`.
- Multi-step implementation: `superpowers:writing-plans`.
- Plan review when scope or risk warrants it: `autoplan` or the relevant focused plan review.
- Bugs and unexplained failures: default to `superpowers:systematic-debugging`; use `investigate` instead for cross-system or environment investigations, after two evidence-backed repair rounds fail to close the same problem, or when a formal investigation record is required. Do not run both full procedures for the same problem.
- Implementation: `superpowers:test-driven-development` and focused verification.
- Final diff review: run `review` once before PR unless an explicitly designated independent authority already owns the same full-diff review; fixes receive targeted re-review by default.
- Frontend behavior: `qa-only` or `qa` when a fix loop is intended.
- Completion claims: `superpowers:verification-before-completion`.

Do not require a second-model review for every change. Recommend an independent second view only for major architecture decisions, high-risk cross-module changes, important milestones, or unresolved uncertainty.

### Phase Ownership And Parallel Work

- Use one primary controller per phase. GStack owns a review or shipping phase when its selected
  controller is active; Superpowers owns a planning, implementation, debugging, or verification
  phase when its selected controller is active. Do not run competing full-branch controllers over
  the same mutable worktree.
- Delegate only when there are at least two independent lanes with clear file ownership and
  independent verification. Do not parallelize changes that share contracts, artifacts, or an
  ordered dependency chain merely to increase activity.
- The parent Agent owns shared contracts, integration, full verification, and the single terminal
  report. Subagents return bounded evidence to the parent; they do not publish competing completion
  claims or mutate the same files concurrently.

## Low-Friction Execution

- Complete safe, discoverable workflow steps proactively instead of asking the user to remember them.
- When a required action cannot be performed automatically because it is risky or requires authorization, stop and report:
  - current state,
  - recommended action,
  - why it is needed,
  - impact of proceeding or skipping.
- Do not stop merely to ask whether to run an obvious test, inspect a relevant file, or update documentation required by the current change.
- Never claim that a review, test, documentation update, push, release, or deployment happened without actual evidence.

## Design And Plan Persistence

Persist approved Superpowers artifacts when a change affects architecture, public contracts, multiple modules, or multiple PRs:

```text
docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md
docs/superpowers/plans/YYYY-MM-DD-<topic>-implementation.md
docs/superpowers/reviews/YYYY-MM-DD-<topic>-review.md
```

Use the Issue or PR body for small fixes, dependency updates, wording changes, and local refactors.

Superpowers specs and plans are implementation history. Long-lived architecture decisions belong in `docs/decisions/`.

- Keep active plan checklists current as work is completed.
- Mark completed plans explicitly so later Agents do not treat historical work as pending.
- After `review`, `autoplan`, or equivalent plan/PR review, persist durable
  public-neutral findings under `docs/superpowers/reviews/` when this repository is the downstream
  execution target.
- If the related spec or plan changes materially after a review is persisted, mark the older review
  as superseded in the same PR or add a replacement review file.
- Do not commit raw GStack review artifacts, timelines, restore points, learnings, or private planning notes. Extract durable public decisions into ADRs or project documentation.

## Task Start And Handoff

- Before making decisions, inspect the current repository.
- Before starting a new task, sync from the latest `main`, confirm `AGENTS.md` exists, and inspect relevant ADRs, specs, plans, tests, and open PR context.
- Use an isolated worktree for implementation plans or changes that should not share state with the current checkout.
- Do not start feature implementation from a branch whose bootstrap or prerequisite PR is still unmerged.
- At task completion, report the branch and PR, actual verification results, documentation impact, remaining risks, and any deferred Issue.

### Terminal Handoff

- Use `READY` when the requested local or hosted gate is complete, `WAITING` when an external gate
  is still running, and `BLOCKED` when a concrete failed authority or ownership gate prevents safe
  progress.
- A waiting handoff records the exact external state and the next gate. Do not keep polling
  unchanged hosted state; resume only after a bounded wait or a new event.
- One phase produces one terminal report from its primary controller. Intermediate worker reports
  are evidence inputs, not additional terminal handoffs.

## TDD And Verification

- Add or update a failing test before implementing behavior changes.
- Bug fixes require a regression test that demonstrates the root cause.
- Use unit tests for domain behavior, contract tests for public schemas, and integration tests for storage, worker, Publication, and provider boundaries.
- Mock remote providers in required CI. Keep optional real-provider smoke tests separate.
- Verification depth must match the blast radius.

Minimum verification targets:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
```

Run only commands that exist in the current repository. If a target is not implemented yet, report that fact instead of claiming it passed.

## Documentation Policy

Documentation changes ship in the same PR as the behavior they describe.

| Change type | Required documentation action |
|---|---|
| HTTP, CLI, MCP, config, or error contract | Update reference docs and generated contract snapshots |
| Architecture, domain lifecycle, or Publication semantics | Add or update ADR and explanation docs |
| Installation, demo, or user workflow | Update tutorial or how-to docs |
| Internal refactor with no behavior change | Record `No documentation impact` in the PR |

Run `document-release` as a pre-merge documentation audit for important features, public contract changes, architecture changes, and release PRs. It is not mandatory for every small internal change.

If the audit would commit, push, update a PR body, or require a version decision without authorization, stop and recommend the exact next action.

## Git And Pull Requests

- Inspect `git status` before editing.
- Never overwrite or revert unrelated user changes.
- Use a short `codex/<scope>-<slug>` branch.
- Route all intended changes to `main` through a PR.
- Keep each PR independently reviewable and verifiable. Avoid phase-sized PRs containing unrelated capabilities.
- Stage only intentional files. Never use `git add -A` or `git add .`.
- Do not push, create a PR, merge, release, or publish without explicit user authorization.
- Query the actual pull request and checks for hosted state. Local workflow YAML is not hosted-state
  authority and must not be used alone to claim that checks exist, passed, or are required.
- After creating or updating a PR, read back the persisted title, body, base, head, and draft state.
  Use ordinary bullets for completed facts. Add checkboxes only for real pending gates whose
  completion affects merge readiness.
- Reconcile the final PR body as gates change: every satisfied `[ ]` gate becomes `[x]`. After
  merge and before closeout, synchronize actual checks, authorization, merge identity,
  mergeability, review blockers, necessary links, cleanup, remaining risk, and explicit
  non-claims. Attempt the write-back, then read back the persisted PR body. If the write-back or
  persisted-body readback fails, or the body still drifts from actual state, record the exact
  blocker or pending trigger and you must not claim complete closeout.
- Before merge, bind review evidence and successful checks to the same reviewed HEAD and checks
  head. For a squash merge, verify that the reviewed tree equals the merge tree; commit-SHA
  inequality alone is expected and is not tree evidence.
- Cleanup is a separate ownership gate. Remove only a task-owned branch or worktree that is clean,
  inactive, and whose results are retained by merged history or another explicit authority. Never
  infer ownership from a familiar name, and never clean unrelated worktrees, caches, or evidence.

## Issues

- Treat direct user requests, PR review findings, CI failures, and bugs within the current PR scope as work to handle directly. Do not require the user to create an Issue first.
- Create or recommend a GitHub Issue only when the work is outside the current PR, cannot be completed now, requires cross-PR tracking, needs continued investigation, or benefits from public collaboration.
- When deferring work to an Issue, include the observed problem, evidence, scope, acceptance criteria, and why it is not being handled in the current PR.
- Do not use Issues as a transcript of routine execution or as a substitute for an approved spec, plan, or PR.

PR descriptions default to Simplified Chinese for local review efficiency. Keep section headings,
commands, code identifiers, API names, CLI output, file paths, and public product terms in English.
Switch a PR description to English only when the PR is intended for external collaborators or the
user explicitly asks for English.

PR descriptions must include:

- Result-focused summary.
- Completed acceptance items.
- Actual verification commands and results.
- Scope and explicit non-scope when needed.
- Risk, migration, or rollback notes when applicable.
- Documentation impact.

## Security And Public Boundaries

- Never commit secrets, tokens, cookies, private configuration, private source material, or personal paths.
- Do not accept arbitrary provider URLs, keys, or filesystem output paths through public contracts.
- Do not expose absolute paths or stack traces in API responses.
- Treat uploaded files, extracted content, model output, and external provider responses as untrusted.
- Public claims and metrics must be backed by repository-visible tests, benchmarks, or explicitly referenced evidence.

## Definition Of Done

A task is complete only when:

- The requested behavior exists and matches accepted scope.
- Relevant tests were added or updated and actually passed.
- Required documentation was updated in the same PR.
- The diff contains no unrelated edits or sensitive information.
- Public contracts and architecture constraints remain consistent.
- Verification results and remaining risks are reported clearly.
