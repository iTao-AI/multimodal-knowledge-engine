# Single-Source Active Publication Search

Status: Approved scope; implementation decisions owned by the delivery controller.

## Goal And Boundary

A caller selects one Source and its active Publication, then retrieves matching active Evidence
from that Source with complete pagination through the public CLI or stdio MCP. Search admission
is constrained before candidate limits, scan budgets, scoring and pagination. An empty scoped
result never falls back to Library Search. Historical Publications, multiple Sources, permissions,
new providers, dependencies, retrieval promotion and generated Ask are outside this slice.

The starting point is merged `6d7924bd8992e2ade7502c56c43838cb67947d35`. Existing unscoped
Search/Ask behavior, Evidence identities, strategy defaults and historical schema fixtures remain
unchanged. Local implementation, verification, documentation and atomic commits are authorized;
remote delivery, new dependencies/lock changes, additional costly proofs and cleanup are separate.

## Public Interface

Add opt-in `search_source_evidence_v1` with a required `request` envelope. Initial input is exactly
`{source_id, publication_id, query, limit?}`; continuation is exactly `{cursor}`. `limit` defaults
to 5 and ranges from 1 through 20. Query is nonblank and at most 512 UTF-8 bytes. Identifiers are
bounded, nonblank strings; unknown, mismatched, unpublished or superseded selections fail with
`evidence_not_found`, without revealing historical state. Select both IDs from `list_sources_v1`
or `list_sources_v2` rather than allowing the request to silently choose a newer Publication.

Success is `mke.search_source_evidence_response.v1` with explicit `scope` containing Source ID,
Publication ID/revision, Run ID and content fingerprint, plus the existing authority snapshot,
query, Evidence descriptors/excerpts/read affordances, output budgets and selection. Selection is
only `complete` or `more_available`, and advances by actual returned count. It describes lexical
matches under the selected strategy, not complete original-media understanding. Each Evidence
descriptor and read affordance must agree with scope and its producing active Publication.

CLI opt-in is `mke search QUERY --source-id ID --publication-id ID --limit N --json`.
Both identity flags are required together. Scoped CLI automatically follows cursors under one
owner and emits one canonical response per line; an error stops traversal with exit 1. Scope-only
`--limit`/`--json` options require scope; an old `mke search QUERY` retains its original route and
output. Cursors are process-bound and are not persisted across CLI commands.

## Retrieval And Authority

The new application entry is `KnowledgeEngine.search_source_evidence_page(source_id,
publication_id, query, *, position, page_size, authority_validator, scope_validator=None) -> EvidenceSearchPage`.
Reuse the existing active graph validation, transactional page selection and enrichment. Resolve
the selected Source/Publication and scope inside that read transaction; validate continuations
before loading/scoring candidates. SQLite remains domain truth and FTS remains a projection.

FTS adds parameterized Source/Publication predicates inside the matched CTE before ORDER/LIMIT.
The CJK scan filters both budget queries and Evidence loads before overlap scoring. Mixed CJK
intent filters its exact FTS match set before row/text budgets and overlap selection. All four
owner strategies are supported; no request-time strategy overrides or new persistent indexes.

For scoped CJK/mixed selection, paginate the entire eligible set within the existing 1,000
candidate budget rather than applying the Library route's 10-result cap. Keep the existing
10,000-row / 16 MiB scan or match-set budget and query/term limits, applied to the selected Source.
Over-budget selection fails explicitly; it cannot silently claim completeness. Library selection
caps and all historical strategy revisions remain unchanged. Ranking retains current native FTS
rank statistics and established strategy-specific stable tie order.

Reuse the owner/HMAC envelope and keyed configured-database binding. A separate payload binds
tool/schema, owner epoch, configured Library, active-set fingerprint, Source/Publication/revision/
Run/content identity, normalized query/digest, strategy/revision/query-policy revision, page size
and position. Cross-tool, altered, mixed-branch or copied-Library cursors fail `invalid_cursor`.
Owner restart, active Publication set change or retrieval policy change fails `cursor_expired`
with an explicit repeat-initial/reselect action. The Library-wide fingerprint conservatively
expires continuation when any active Publication changes, including an unselected Source.
No stale cursor is automatically reinterpreted against a newer Publication.

Canonical responses remain within 32,768 bytes, combined excerpts within 16,384 bytes and each
excerpt within 2,048 UTF-8 bytes. Measure the complete new envelope including scope/cursor and
reduce page count when necessary; an unfit mandatory envelope fails explicitly.

## Acceptance

- Two Sources sharing a query, including unrelated higher-ranked / higher-overlap interference,
  return only the selected Source and all of its matches beyond limit and beyond the old cap.
- Exercise current, numeric-grouping, CJK scan, mixed-intent and their relevant query branches;
  unrelated rows cannot consume scoped scan/match/candidate budgets.
- Empty matches remain scoped; malformed/unknown/mismatched/inactive identities fail closed.
- Publication replacement during one read remains a coherent snapshot; replacement between pages
  expires the cursor. Test cross-tool/Library, tampering, initial/continuation mixing, restart and
  policy changes with public DTO/error projections.
- Native CLI ingest and official SDK stdio calls consume actual active Evidence and exact reads,
  verifying full citation/digest identity and both success and rejection paths without mock-only
  acceptance. Include timestamp Evidence and bounded Unicode/escaping envelopes.
- Preserve historical fixtures and old unscoped behavior; create an additive current schema fixture
  and explicitly migrate current inventory consumers. Document scope/errors and completed gates.

## Ask Follow-Up Design Only

A future opt-in scoped Ask must reuse the same explicit Source/active Publication selection and
scoped candidate admission. It must reject citations from another Source, another Publication,
another authority snapshot or a stale Run rather than silently mixing them. It must disclose
insufficient scoped Evidence without Library fallback. Its answer/cursor policy requires a
separate approved implementation slice; this change does not add an Ask parameter or tool.
