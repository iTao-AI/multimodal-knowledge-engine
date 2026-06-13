# AGENTS.md

This file defines the execution rules for Codex when working in this repository.

## Project Purpose

Multimodal Knowledge Engine is a local-first, Agent-callable Evidence engine for ingesting, searching, and asking questions over documents and media.

The first product slice must prove:

- One PDF and one short local video can be ingested through observable Runs.
- Search and Ask return stable page or timestamp Evidence.
- Failed or partial processing never becomes searchable.
- HTTP, CLI, MCP, and the workspace use one canonical contract.

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
- The first runtime is a single-owner `mke serve` process with one worker and no Redis requirement.

Changing any constraint above requires an ADR in the same PR.

## Working Model

Codex is the primary project Agent and owns planning, implementation, testing, documentation, PR preparation, and final verification.

Use GStack and Superpowers when they match the task:

- Ambiguous product or architecture work: `superpowers:brainstorming`.
- Multi-step implementation: `superpowers:writing-plans`.
- Plan review when scope or risk warrants it: `gstack-autoplan` or the relevant focused plan review.
- Bugs and unexplained failures: `gstack-investigate` or `superpowers:systematic-debugging`.
- Implementation: TDD and focused verification.
- Final diff review: `gstack-review`.
- Frontend behavior: `gstack-qa-only` or `gstack-qa` when a fix loop is intended.
- Completion claims: `superpowers:verification-before-completion`.

Do not require a second-model review for every change. Recommend an independent second view only for major architecture decisions, high-risk cross-module changes, important milestones, or unresolved uncertainty.

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
```

Use the Issue or PR body for small fixes, dependency updates, wording changes, and local refactors.

Superpowers specs and plans are implementation history. Long-lived architecture decisions belong in `docs/decisions/`.

- Keep active plan checklists current as work is completed.
- Mark completed plans explicitly so later Agents do not treat historical work as pending.
- Do not commit raw GStack review artifacts, timelines, restore points, learnings, or private planning notes. Extract durable public decisions into ADRs or project documentation.

## Task Start And Handoff

- Before making decisions, inspect the current repository.
- Before starting a new task, sync from the latest `main`, confirm `AGENTS.md` exists, and inspect relevant ADRs, specs, plans, tests, and open PR context.
- Use an isolated worktree for implementation plans or changes that should not share state with the current checkout.
- Do not start feature implementation from a branch whose bootstrap or prerequisite PR is still unmerged.
- At task completion, report the branch and PR, actual verification results, documentation impact, remaining risks, and any deferred Issue.

## TDD And Verification

- Add or update a failing test before implementing behavior changes.
- Bug fixes require a regression test that demonstrates the root cause.
- Use unit tests for domain behavior, contract tests for public schemas, and integration tests for storage, worker, Publication, and provider boundaries.
- Mock remote providers in required CI. Keep optional real-provider smoke tests separate.
- Verification depth must match the blast radius.

Minimum verification targets:

```bash
pytest -q
ruff check .
pyright
cd frontend && npm run test && npm run lint && npm run build
mke demo --verify
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

Run `gstack-document-release` as a pre-merge documentation audit for important features, public contract changes, architecture changes, and release PRs. It is not mandatory for every small internal change.

If the audit would commit, push, update a PR body, or require a version decision without authorization, stop and recommend the exact next action.

## Git And Pull Requests

- Inspect `git status` before editing.
- Never overwrite or revert unrelated user changes.
- Use a short `codex/<scope>-<slug>` branch.
- Route all intended changes to `main` through a PR.
- Keep each PR independently reviewable and verifiable. Avoid phase-sized PRs containing unrelated capabilities.
- Stage only intentional files. Never use `git add -A` or `git add .`.
- Do not push, create a PR, merge, release, or publish without explicit user authorization.

## Issues

- Treat direct user requests, PR review findings, CI failures, and bugs within the current PR scope as work to handle directly. Do not require the user to create an Issue first.
- Create or recommend a GitHub Issue only when the work is outside the current PR, cannot be completed now, requires cross-PR tracking, needs continued investigation, or benefits from public collaboration.
- When deferring work to an Issue, include the observed problem, evidence, scope, acceptance criteria, and why it is not being handled in the current PR.
- Do not use Issues as a transcript of routine execution or as a substitute for an approved spec, plan, or PR.

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
