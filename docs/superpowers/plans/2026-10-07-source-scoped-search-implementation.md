# Single-Source Search Implementation Plan

Status: Completed locally on 2026-10-07. Hosted delivery remains a separate authorization.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for inline implementation. Steps use checkbox syntax for tracking.

**Goal:** Public CLI/stdio MCP consumers can completely paginate Search within one selected active Source/Publication.

**Architecture:** Reuse canonical transactional Evidence page selection with early parameterized Source predicates. Add an independent public response and authenticated cursor payload so all previous tool schemas and unscoped behavior remain frozen. The controller implements shared contracts inline and requests one bounded fresh-context final review.

**Tech Stack:** Existing Python 3.12/3.13, SQLite FTS5, Pydantic, official MCP Python SDK, uv/pytest.

**Spec:** [Approved design](../specs/2026-10-07-source-scoped-search-design.md)

## Global Constraints

- Base `6d7924bd8992e2ade7502c56c43838cb67947d35`; retain previous worktrees/evidence.
- Single Source and active Publication only; Search implementation, Ask follow-up design only.
- No unscoped contract/default/order/identity changes; historical fixtures remain byte-identical.
- No dependencies/lock changes, provider/model calls, Release/deploy, remote delivery or cleanup.
- Initial IDs are explicit; continuation is cursor-only. Limit 1–20/default5; query <=512 UTF-8 bytes.
- Scoped selection paginates within existing candidate/scan budgets with explicit budget failure.
- Envelope <=32768 bytes; combined excerpts <=16384; each excerpt <=2048 UTF-8 bytes.

## Versions And Native Capability Matrix

Verified 2026-10-07 in the isolated worktree using the existing lock and cached offline packages:
Python3.12.13, SQLite3.50.4, mcp1.29.1, Pydantic2.13.5, PyMuPDF1.27.2.3,
pytest9.1.1, Ruff0.16.8, Pyright1.1.414. No lock modification or model acquisition.

| Surface | Existing native capability | Project-owned addition |
|---|---|---|
| SQLite FTS5 | Parameterized MATCH, relational WHERE, rank, ORDER/LIMIT | Source/Publication predicate before matched-set limits; active graph remains SQLite authority |
| CJK/mixed strategies | Existing overlap selection and explicit budgets | Source-filtered reads/budgets; full scoped pool up to1000 instead of Library top10 |
| MCP1.29.1 | FastMCP structured tools; ClientSession/stdio_client | Strict additive DTO and operation-specific cursor/authority rules |
| Source navigation | Active Source/Publication discovery; descriptor-bound exact read | Reuse selected IDs and unchanged read_evidence_v1 |
| CLI | Per-command owner and automatic Source/read pagination | Scoped Search opt-in; old route unchanged |

Primary material checked: [SQLite FTS5](https://www.sqlite.org/fts5.html),
[SQLite SELECT](https://www.sqlite.org/lang_select.html),
[MCP SDK1.29.1](https://github.com/modelcontextprotocol/python-sdk/blob/v1.29.1/README.md).
The upstream default docs now describe SDK2; keep the installed1.x API and project `<2` bound.
Context7 is unavailable in this session. Current source/adapters and the versioned SDK are the
implementation authority. Retrieval benchmark manifests/protocols and freeze tests were inspected;
no evaluation corpus, historical byte record or default promotion is changed.

## Review Focus

- An unrelated Source exhausts scan/candidate budgets: only selected rows should be admitted.
- More than10 CJK/mixed matches: finish all eligible scoped pages without capped terminal output.
- Library copied under another configured database: reject otherwise authentic continuation.
- Publication switches inside a read versus between pages: coherent old snapshot, then expiry.
- Unicode/JSON escaping plus scope/cursor metadata: exact envelope measurement and positive progress.

### Task 1: Source-Bound Candidate Admission

**Files:** Create `src/mke/domain/source_search.py`; modify `src/mke/domain/evidence_access.py`,
`src/mke/application/__init__.py`, `src/mke/adapters/sqlite/__init__.py`;
test `tests/adapters/test_sqlite_source_search.py`.

**Interfaces:** Produces `SourceSearchScope` (Source/Publication/revision/Run/content identity)
and `KnowledgeEngine.search_source_evidence_page(source_id, publication_id, query, *, position,
page_size, authority_validator, scope_validator=None) -> EvidenceSearchPage`; page has optional scope, absent for old calls.

- [x] Write real SQLite regressions for all four strategies/branches, >10 matches paged by3,
  unrelated high-ranked candidates, unrelated budget interference, zero hits, wrong selections,
  read-snapshot replacement and unchanged unscoped results.
- [x] Run `uv run --locked --offline pytest -q tests/adapters/test_sqlite_source_search.py`;
  expect new-method failures before implementation.
- [x] Implement scope resolution and predicates before candidate selection; preserve old SQL when
  scope is absent; use scoped max_results=max_candidate_pool only for the opt-in route.
- [x] Run new tests plus `tests/retrieval`, Source adapter and Evidence/provenance tests; expect PASS.
- [x] Commit only intentional core/tests and approved design/plan/ADR changes.

### Task 2: Authenticated Public MCP And CLI Search

**Files:** Create `src/mke/application/source_search_cursor.py`,
`src/mke/interfaces/source_search_schemas.py`, `src/mke/interfaces/source_search.py`;
modify cursor encoder type, CLI/parser and MCP server; tests in `tests/application`,
`tests/interfaces/test_source_search.py`, `tests/interfaces/test_cli_source_search.py`;
create `tests/fixtures/source-search-v1/mcp-tool-schemas.json` and migrate current consumers.

**Interfaces:** Consumes Task1 page/scope; produces strict `SearchSourceEvidenceV1Request`,
`SearchSourceEvidenceResponseV1` and `search_source_evidence_v1(config, request)`;
CLI opts in with `--source-id/--publication-id`, optional `--limit/--json`.

- [x] Write DTO/real adapter regressions for cursor-only and initial disjointness, malformed IDs,
  tampering, cross-tool/Library, restart/policy/Publication expiry, full-scope descriptor agreement,
  Unicode envelope budgets and zero results. Add actual CLI subprocess pagination/rejection tests.
- [x] Run new tests and witness missing-contract/route failures.
- [x] Implement strict schema, separate authenticated cursor validator and bounded full-envelope
  assembly; register one new read-only native tool and preserve all existing registrations.
- [x] Keep old fourteen-tool fixture immutable, generate a new fifteen-tool current snapshot,
  migrate current exact-inventory consumers explicitly and preserve pinned historical proof routes.
- [x] Run affected contract/cursor/CLI/consumer tests, Ruff and Pyright; expect PASS; commit atomically.

### Task 3: Native Acceptance, Documentation And Final Review

**Files:** Create `tests/proof/test_source_search_stdio.py` and
`tests/proof/test_source_search_native_bounds.py`; update contract references,
getting-started/Source how-to; persist bounded public review outcomes if they affect contracts.

**Interfaces:** Consumes Task2 public tools/CLI; uses actual native CLI ingest and SDK stdio,
public DTOs, Source discovery, active descriptors and exact read for independent acceptance.

- [x] Write native tests covering two real ingested Sources, complete pagination and all strategies,
  empty scoped selection, invalid/mixed cursor rejection and Publication replacement; verify each
  success against active Evidence/read descriptors. Witness failures before the missing behavior
  is implemented; reuse Task2 RED when that public behavior is already implemented.
- [x] Run native acceptance and record actual response sizes/exit/errors in ignored artifacts.
- [x] Update user workflow, scope/errors, current inventory and Ask-only follow-up design; audit
  docs with `gstack-workflows:document-release` within local authorization.
- [x] Run `uv run --locked --offline pytest -q`, Ruff, Pyright, `git diff --check`; no paid/provider
  or additional installed-wheel costly proof. Run packaging only if inventory changes require it.
- [x] Fresh bounded reviewer checks full diff against spec; fix substantiated defects with TDD and
  focused re-verification. Mark plan complete, commit intended files and report exact clean HEAD,
  actual gates, method and remaining remote approval to the coordinating owner once.

## Local Acceptance

- Final full suite on reviewed `ed46b1f99956b125b3d1361095bf560e1d31c3d4`: 4,510 passed,
  34 skipped, five existing PyMuPDF Swig deprecation warnings; 304.77 seconds.
- Native CLI ingest and official SDK stdio acceptance: eight passed, covering all four strategies
  and relevant FTS/CJK/mixed branches, PDF/timestamp Evidence, 13 selected matches over five pages,
  empty selection, cursor/identity rejection and Publication replacement/reselection.
- Escaped Unicode acceptance: 20 matches over three pages, maximum Search canonical envelope
  28,628 bytes and maximum full SDK result 65,731 bytes, with exact-read citation/digest checks.
- Ruff, Pyright and full-range diff-check passed. Offline wheel/sdist build passed; all four new
  module byte payloads in the wheel equal source. Later test/docs-only commits preserve build
  package/dependency inputs. No additional installed-wheel consumer proof was performed.
- Native fifteen-tool fixture matches exactly; historical five/eight/ten/twelve/fourteen tool
  schemas and recorded fixture bytes remain unchanged. Lock, dependencies and runtime defaults
  are unchanged. Current exact-inventory consumers migrate without ignoring unknown tools.
- Local document-release audit and current inventory/source workflow checks passed. Full-suite
  findings closed the ADR index, a second inventory assertion and a test stub matching directory
  names instead of command argv; the release product script was unaffected.
- One fresh bounded read-only review passed on `3810386fde231325fed1c0352e149158aa5cc94d`;
  targeted re-review of `3810386..ed46b1f` passed. No Critical/Important/Minor findings remain.

The final closeout commit changes this plan only. Source, tests, schemas and dependency inputs
remain exactly those of the reviewed full-suite HEAD. Ask is the approved follow-up design only;
push/PR/merge/release, additional proof and retained-worktree cleanup are not part of this local
completion.
