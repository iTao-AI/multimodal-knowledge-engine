# ADR-0016: Single-Source Active Publication Search

Status: Accepted
Date: 2026-10-07

## Decision

Add an opt-in `search_source_evidence_v1` tool and scoped CLI Search. Require an explicit Source
and its active Publication on initial selection; never substitute another Publication or fall
back to Library Search. Resolve scope, validate active graph/continuation and retrieve/enrich
Evidence in one SQLite read transaction. Scope identity includes producing Run, Publication
revision and content fingerprint. Every result and exact-read descriptor preserves that lineage.

Source/Publication predicates enter the matched FTS set and CJK domain reads before selection,
scoring budgets and pagination. All four existing runtime strategies are supported. The scoped
route paginates the complete eligible CJK/mixed pool within the existing1000-candidate bound;
the existing10000-row/16MiB budgets remain and over-budget requests fail explicitly. This extends
ADR-0008/0013 only for the additive scoped route: Library top10 caps/defaults/revisions remain
unchanged. Native FTS rank statistics and stable tie keys remain unchanged.

A separate HMAC cursor payload binds operation/schema, owner, keyed configured Library identity,
active-set fingerprint, full Source/Publication identity, query, policy, page size and position.
Continuation is cursor-only. Initial/cursor mixing, cross-tool/Library reuse and tampering fail
closed. Owner/policy/active-set changes require a new initial selection. The existing Library-wide
fingerprint conservatively invalidates cursors even when an unselected Publication changes;
there is no cross-page historical authority or automatic rebase to new Evidence.

Responses disclose scope even when no matching Evidence exists. They retain bounded excerpts,
read affordances and strict error DTOs, with only complete/more_available selection. The complete
canonical envelope, including scope and cursor, is measured before returning a page; pagination
advances by actual returned count. Selection completeness describes eligible lexical matches,
not OCR, model quality or original-media semantic completeness.

## Compatibility And Consequences

Keep all previous Search/Ask tool schemas, responses and identities unchanged. The new current
fifteen-tool expectation is additive; historical five/eight/ten/twelve/fourteen-tool fixtures stay
immutable. Exact-inventory consumers must choose matching current expectations. No database
migration, new index/dependency/model/provider, release or hosted application is introduced.

The CLI holds one owner through automatic traversal and emits canonical NDJSON with `--json`;
an old unscoped command keeps its original output. Process-bound cursors are not persisted across
commands. The selected scope is search authority, not an authorization or permission boundary.

## Ask Deferral At Acceptance

Ask implementation remains deferred. A future scoped Ask must independently reject out-of-scope
or stale citations and avoid Library fallback; this ADR adds no Ask tool or request parameter.

## Follow-Up (2026-10-07)

The later CLI-only Ask slice is decided in
[ADR-0017](./0017-single-source-evidence-only-cli-ask.md). It composes one validated scoped Search
page and independently rejects citation/selection inconsistencies. The Search decision and
fifteen-tool MCP contracts above remain unchanged.
