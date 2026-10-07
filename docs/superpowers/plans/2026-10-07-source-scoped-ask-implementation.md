# Single-Source Evidence-Only CLI Ask Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan inline. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in scoped CLI Ask and an ordinary SDK consumer that verify bounded selected Evidence.

**Architecture:** Project-owned CLI DTOs compose one existing scoped Search snapshot. The SDK example discovers the same selected authority and verifies exact-read bytes; existing application Ask and MCP registry remain unchanged.

**Tech Stack:** Existing Python 3.12/3.13, Pydantic 2, SQLite, argparse and official MCP SDK; no dependency changes.

**Spec:** `docs/superpowers/specs/2026-10-07-source-scoped-ask-design.md`

**Git Base:** `main` at `3f5469254788013463b3494efe90f63edcd89570`.

**Status:** In progress. Local implementation and semantic commits are authorized; remote delivery is a later gate.

## Global Constraints

- Unscoped CLI Ask/Search, application Ask and existing MCP schemas stay unchanged; inventory remains fifteen tools.
- Explicit Source/active Publication pair, four current strategies, no Library fallback or historical access.
- Freeze bounded first page: limit 1..20/default 5, scoped question <=512 UTF-8 bytes.
- Per excerpt 2,048 bytes, combined excerpts 16,384, complete canonical envelope 32,768.
- Evidence selection is deterministic; it does not generate or verify a semantic answer.
- No dependency/lock, provider/model, permission, Release/tag/deploy or costly-proof changes.

## Review Focus

- Envelope-driven shrink must change complete to more_available and retain positive progress.
- A bad final citation must reject the entire packet; shrinking must not hide an identity failure.
- Process-bound Search cursors must not become cross-process CLI Ask continuations.
- SDK reads must verify exact byte offsets, digest, excerpt window and complete citation, including Unicode chunks.
- Publication change between discovery, Search and read must fail without a partial successful receipt.

## Task 1: Scoped CLI Ask Vertical Slice

**Files:** Create `src/mke/interfaces/source_ask.py`, `src/mke/interfaces/source_ask_schemas.py`, `tests/interfaces/test_source_ask.py`, `tests/interfaces/test_cli_source_ask.py`, and `tests/fixtures/source-ask-v1/cli-response-schema.json`; modify `src/mke/cli.py` and `src/mke/interfaces/cli_parser.py`.

**Interfaces:** Consume `search_source_evidence_v1(config, SearchSourceEvidenceV1Request)` and existing scope/citation/budget DTOs. Produce `ask_source_evidence(config, source_id, publication_id, question, limit=5) -> SourceAskResponseV1` and the paired CLI options from the spec.

- [x] Write actual CLI failures for missing opt-in route, stronger distractor exclusion, zero result, both selection statuses and paired option errors. Add DTO/service failures for scope/count/status and envelope-shrink truth.
- [x] Run the new tests before code; expected failures identify the absent CLI route/DTO/service.
- [x] Implement strict response DTOs and one-snapshot assembly. Validate all input citations before shrinking; errors preserve scoped Search recovery under the new response schema.
- [x] Add parser/dispatch and bounded JSON/human rendering, with one owner shutdown and unchanged old Ask route.
- [x] Generate the new CLI schema snapshot and verify its exact current model; preserve historical/current MCP fixture bytes.
- [x] Run new CLI/service tests plus existing CLI Ask/Search and contract fixtures; expect all passed. Commit only this slice's intentional files.

## Task 2: Ordinary SDK Citation Consumer

**Files:** Create `scripts/source_evidence_consumer.py`, `tests/scripts/test_source_evidence_consumer.py` and `tests/proof/test_source_ask_consumer.py`.

**Interfaces:** Consume existing `ListSourcesResponseV1`, `SearchSourceEvidenceResponseV1`, `ReadEvidenceResponseV1`, SDK `ClientSession`/`stdio_client`, and Task 1 selection semantics. Produce a bounded verification receipt from `list_sources_v1 -> search_source_evidence_v1 -> read_evidence_v1` under one owner.

- [x] Write failing consumer tests for strict descriptor/authority checks, changed identity, offsets/digest and Unicode excerpt-window validation; write actual CLI/SDK acceptance for PDF and declared timestamp fixtures with a stronger unrelated Source.
- [x] Run tests before consumer implementation; expected failures name the absent consumer, then actual validation failures as each boundary is introduced.
- [x] Implement discovery, first-page selection and streamed exact-read verification. Preserve complete/more_available and reject all unverified or stale results before emitting one bounded receipt.
- [x] Run actual subprocess and official SDK tests across the four strategies plus zero result and mismatch/replacement. Expect all passed; make no installed-wheel or model-quality claim.
- [x] Commit only consumer code and its tests.

## Task 3: Documentation, Focused Review And Local Candidate

**Files:** Create `docs/decisions/0017-single-source-evidence-only-cli-ask.md` and `docs/how-to/ask-within-one-source.md`; modify `README.md`, `README_CN.md`, `docs/README.md`, `docs/tutorials/getting-started.md`, `docs/reference/cli.md`, `docs/reference/contracts.md`, `docs/reference/mcp-contract.md`, `docs/how-to/use-mke-mcp.md`, `docs/how-to/search-within-one-source.md` and `docs/explanation/architecture.md` as needed by actual behavior.

**Interfaces:** Document Task 1/2 behavior, limits, errors and checkout-only verification without altering old contract claims.

- [x] Update ordinary entry points, schema/reference links, fixed Evidence-only limitations and the runnable SDK example; explain first-page scope versus excerpt completeness.
- [x] Run affected tests, Ruff, Pyright, local documentation links/index checks and `git diff --check`. Expect all passed; reuse unchanged broad baseline evidence.
- [ ] Perform focused documentation audit and one fresh whole-branch code review using the current Sol model/high; fix actionable findings with targeted regression and re-review.
- [ ] Commit documentation and completed plan, keep exact behavior-input/test evidence bound, and preserve ignored receipts/old worktrees.
- [ ] Prepare a public-neutral PR title/body and exact HEAD/diff/verification/limits; return one local READY candidate for remote approval.
