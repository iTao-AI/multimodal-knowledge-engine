# AGENTS.md

This file defines the execution rules for Codex when working in this repository.

## Project Purpose

Multimodal Knowledge Engine is a local-first, Agent-callable Evidence engine for ingesting, searching, and asking questions over documents and media.

The first verified product slice proves:

- Text-layer PDFs and the documented short local video fixture can be ingested through observable Runs.
- Search and Ask return stable page or timestamp Evidence from active Publications.
- Failed or partial processing never becomes searchable.
- CLI and MCP use one canonical application contract. The offline HTML viewer and static
  Evidence workspace are bounded viewing surfaces, not an HTTP service or hosted application.

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

The phase controller owns implementation decisions, shared contracts, integration, verification,
and the terminal report within the approved scope. Delegated agents implement and verify their
assigned scope and handle routine fixes. Changes to goals, key design, acceptance, or authorization
return to the owner of the approved design.

Use GStack and Superpowers when they match the task:

- Undecided product or architecture work: select a focused `gstack-workflows` design/plan Skill or
  `superpowers:brainstorming`; reuse approved designs rather than running both.
- Multi-step implementation: `superpowers:writing-plans`.
- Plan review when scope or risk warrants it: `gstack-workflows:autoplan` or a focused plan review.
- Bugs and unexplained failures: default to `superpowers:systematic-debugging`; use `gstack-workflows:investigate` instead for cross-system or environment investigations, after two evidence-backed repair rounds fail to close the same problem, or when a formal investigation record is required. Do not run both full procedures for the same problem.
- Implementation: `superpowers:test-driven-development` and focused verification.
- Final diff review: match depth to risk and reuse the chosen implementation route's review; use `gstack-workflows:review` as a view of that review when useful. Small document or mechanical changes need a focused diff check, not an extra full-branch review. Fixes receive targeted re-review.
- Frontend behavior: `gstack-workflows:qa-only` or `gstack-workflows:qa` when a fix loop is intended.
- Completion claims: `superpowers:verification-before-completion`.

Do not require a second-model review for every change. Recommend an independent second view only for major architecture decisions, high-risk cross-module changes, important milestones, or unresolved uncertainty.

### Phase Ownership And Parallel Work

- Use one primary controller per phase. GStack owns a review or shipping phase when its selected
  controller is active; Superpowers owns a planning, implementation, debugging, or verification
  phase when its selected controller is active. Do not run competing full-branch controllers over
  the same mutable worktree.
- Delegation assigns bounded execution to an agent; it does not require parallel lanes. Parallelize
  only when lanes have independent scope, file ownership, and verification. Do not parallelize
  changes that share contracts or artifacts, or depend on an ordered chain.
- The phase controller retains shared contracts, integration decisions, and acceptance. Execution
  agents own implementation, assigned verification, and routine fixes; they return evidence to the
  controller and do not publish competing completion claims or mutate the same files concurrently.
- Prefer native result delivery and event-driven waits. Combine execution feedback at phase
  boundaries and avoid short polling or repeating checks that already have evidence.

## Low-Friction Execution

- Complete safe, discoverable workflow steps proactively instead of asking the user to remember them.
- Reuse existing authorization within its scope. Send unresolved approval decisions
  to the designated coordinating owner when present; continue independent authorized
  work while awaiting a decision. Tool-required user confirmation remains binding.
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
- Persist durable public-neutral review findings when they affect a shared contract
  or lasting decision. Routine execution/review logs and handoff receipts stay in
  ignored local directories; running a Skill alone does not require a new public file.
- If the related spec or plan changes materially after a review is persisted, mark the older review
  as superseded in the same PR or add a replacement review file.
- Do not commit raw GStack review artifacts, timelines, restore points, learnings, or private planning notes. Extract durable public decisions into ADRs or project documentation.

## Task Start And Handoff

- At task start, confirm the intended Git base, current status, and the relevant rules, contracts,
  tests, and PR context. Sync from `main` when it is the intended base; do not replace an approved
  branch or recovery point merely to restart the workflow.
- Verify the rules in the actual execution worktree; another checkout's update does
  not update this one. Keep the designated approval owner in the handoff.
- Accept a public-neutral brief or approved spec with scope, constraints, observable acceptance,
  delivery owner, Git starting point, and authorization. Persist larger designs under the paths
  above; small work needs only a brief. Directory placement alone is not approval.
- Reuse approved design; use `superpowers:writing-plans` only for missing implementation details.
  Choose direct execution for small work, or `superpowers:executing-plans` for self-implementation,
  or `superpowers:subagent-driven-development` for managed implementation and review. Do not
  restart the full manager workflow inside a task worker.
- Use an isolated worktree for implementation plans or changes that should not share state with the current checkout.
- Do not start feature implementation from a branch whose bootstrap or prerequisite PR is still unmerged.
- At task completion, report the exact HEAD, branch/PR, acceptance evidence, documentation impact,
  remaining work, and any deferred Issue. Distinguish local completion from hosted delivery;
  missing remote authorization does not prevent preparing a reviewable local result.

Return once on completion or when a decision is needed. State labels are optional;
report an unmet original acceptance goal even when a local fix passes. Worker
reports are evidence inputs to the controller's consolidated result.

## TDD And Verification

- Add or update a failing test before implementing behavior changes.
- Bug fixes require a regression test that demonstrates the root cause.
- Use unit tests for domain behavior, contract tests for public schemas, and integration tests for storage, worker, Publication, and provider boundaries.
- Mock remote providers in required CI. Keep optional real-provider smoke tests separate.
- Verification depth must match the blast radius.
- Reuse evidence when its inputs have not changed. Before another authorized costly
  run, establish the prior failure's cause and usable diagnostics; changing the
  harness or error label does not reset failure of the same acceptance goal. A
  scripted provider test does not prove autonomous model behavior or content quality.
- After a second substantive failure of the same real/costly acceptance goal,
  stop those runs and return to the coordinating owner for a route decision.
  An explicitly frozen stage requires an explicit instruction to resume.

Common verification entry points; select by affected surface rather than running every command
for every task. Documentation-only or mechanical edits use focused checks and `git diff --check`;
packaging, proof, and demo gates apply when affected or required by the release scope:

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

Run `gstack-workflows:document-release` as a pre-merge documentation audit for important features, public contract changes, architecture changes, and release PRs. It is not mandatory for every small internal change.

If the audit would commit, push, update a PR body, or require a version decision without authorization, stop and recommend the exact next action.

## Git And Pull Requests

- Inspect `git status` before editing.
- Never overwrite or revert unrelated user changes.
- Use a short `codex/<scope>-<slug>` branch.
- Route all intended changes to `main` through a PR.
- Keep each PR independently reviewable and verifiable. Avoid phase-sized PRs containing unrelated capabilities.
- Stage only intentional files. Never use `git add -A` or `git add .`.
- Do not push, create a PR, merge, release, or publish without explicit authorization,
  including a valid user delegation.
- Query the actual pull request and checks for hosted state. Local workflow YAML is not hosted-state
  authority and must not be used alone to claim that checks exist, passed, or are required.
- After creating or updating a PR, read back the persisted title, body, base, head, and draft state.
  Use ordinary bullets for completed facts. Add checkboxes only for real pending gates whose
  completion affects merge readiness.
- Correct materially stale PR claims when delivery changes them. Headings and checkbox
  style are not extra merge gates. If documentation write-back fails, report the
  remaining work separately from the verified code, merge and CI result.
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

PR descriptions explain the problem, resulting behavior, actual verification and
material limits. Scale detail to the change; add migration or rollback only when needed.

## Security And Public Boundaries

- Never commit secrets, tokens, cookies, private configuration, private source material, or personal paths.
- Keep raw agent state, temporary screenshots and execution receipts in ignored
  directories. Preserve public specs/plans, ADRs, test fixtures and selected assets;
  ignore rules do not untrack existing files or replace release inventory checks.
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
