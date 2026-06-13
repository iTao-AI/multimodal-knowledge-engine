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

If sources conflict, report the conflict. Do not silently follow an older plan over current code.

## Canonical Vocabulary

Public product concepts are:

`Library`, `Source`, `Asset`, `Run`, `Artifact`, `Segment`, `Passage`, `Evidence`, and `Publication`.

- Public API paths do not include speculative `/api`, `/v1`, or `/v2` segments.
- Do not expose legacy product terms such as `knowledge_base`, product-level `collection`, `chunk`, or `job`.
- Provider and storage implementation names may appear only in configuration, adapters, benchmarks, and ADRs.

## Architecture Constraints

- Domain and application layers use project-owned DTOs and ports.
- SQLite is domain truth for the first Pilot. Retrieval indexes are rebuildable projections.
- Assets and Artifacts are immutable and content-addressed.
- Search and Ask read only active Publications.
- A retry creates a new immutable Run.
- Required-stage, embedding-batch, or indexing failure must fail the Run and prevent Publication switching.
- Random vectors and silent fallbacks are prohibited.
- The first runtime is a single-owner `mke serve` process with one worker and no Redis requirement.

Changing these constraints requires an ADR in the same PR.

## Working Model

Codex is the primary project Agent and owns planning, implementation, testing, documentation, PR preparation, and final verification.

- Ambiguous product or architecture work: `superpowers:brainstorming`.
- Multi-step implementation: `superpowers:writing-plans`.
- Plan review when scope or risk warrants it: `gstack-autoplan` or a focused plan review.
- Bugs and unexplained failures: `gstack-investigate` or `superpowers:systematic-debugging`.
- Final diff review: `gstack-review`.
- Completion claims: `superpowers:verification-before-completion`.

Recommend an independent second view only for major architecture decisions, high-risk cross-module changes, important milestones, or unresolved uncertainty.

## Low-Friction Execution

- Complete safe, discoverable workflow steps proactively.
- When authorization or risk prevents automatic action, stop and report current state, recommended action, reason, and impact.
- Never claim a review, test, documentation update, push, release, or deployment happened without evidence.

## Design And Plan Persistence

Persist approved architecture, public contract, cross-module, or multi-PR work in:

```text
docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md
docs/superpowers/plans/YYYY-MM-DD-<topic>-implementation.md
```

Long-lived architecture decisions belong in `docs/decisions/`. Do not commit raw GStack artifacts or private planning notes.

## TDD And Verification

- Add or update a failing test before implementing behavior changes.
- Use unit tests for domain behavior, contract tests for public schemas, and integration tests for storage, worker, Publication, and provider boundaries.
- Mock remote providers in required CI. Keep optional real-provider smoke tests separate.

Minimum verification targets, once implemented:

```bash
pytest -q
ruff check .
pyright
cd frontend && npm run test && npm run lint && npm run build
mke demo --verify
```

Run only commands that exist in the repository.

## Documentation Policy

Documentation changes ship in the same PR as the behavior they describe.

| Change type | Required documentation action |
|---|---|
| HTTP, CLI, MCP, config, or error contract | Update reference docs and contract snapshots |
| Architecture, domain lifecycle, or Publication semantics | Add or update ADR and explanation docs |
| Installation, demo, or user workflow | Update tutorial or how-to docs |
| Internal refactor with no behavior change | Record `No documentation impact` in the PR |

Use `gstack-document-release` as a pre-merge audit for important features, public contract changes, architecture changes, and releases.

## Git And Pull Requests

- Inspect `git status` before editing.
- Use a short `codex/<scope>-<slug>` branch.
- Route intended changes to `main` through a PR.
- Keep each PR independently reviewable and verifiable.
- Stage only intentional files. Never use `git add -A` or `git add .`.
- Do not push, create a PR, merge, release, or publish without explicit user authorization.

## Security And Public Boundaries

- Never commit secrets, tokens, cookies, private configuration, private source material, or personal paths.
- Do not accept arbitrary provider URLs, keys, or filesystem output paths through public contracts.
- Do not expose absolute paths or stack traces in API responses.
- Treat uploaded files, extracted content, model output, and external provider responses as untrusted.
- Public claims and metrics must be backed by repository-visible tests or benchmarks.

## Definition Of Done

A task is complete only when requested behavior exists, relevant tests actually pass, required documentation is updated, the diff contains no unrelated or sensitive content, and remaining risks are reported.
