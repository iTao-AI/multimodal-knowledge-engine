# Bounded Mixed CJK/ASCII Intent Retrieval

Status: approved for a local, explicitly selected candidate. Default promotion is a separate decision.

Planning baseline: `main@d3d801bb776480516f3062673a43a592ea99b581`.

## Outcome

Queries with the same ASCII anchor and different CJK questions must select Evidence that supports
the requested CJK intent. The candidate is deterministic, local, provider-free lexical retrieval;
it does not claim general semantic question answering.

Add owner-selected `mixed-cjk-fts-intent-v1`, revision `1`. Keep the existing default,
`cjk-active-scan-overlap-v1`, `numeric-grouping-v1`, and `current` behavior and revisions unchanged.
Do not change the ASCII compiler or `QUERY_POLICY_REVISION`. No request-time strategy override,
schema migration, new service, persistent cache, or projection is introduced.

## Routing And Selection

Compile the original query with the existing `numeric-grouping-v1` compiler. Its entire FTS5
expression remains mandatory; a zero-hit result does not trigger a fallback that drops any ASCII,
numeric, grouping, identifier, or proper-name clause.

For a query without CJK, use the unchanged numeric-grouping FTS route. For a compiled-empty CJK
query, use the existing CJK active-scan behavior and Ask validation semantics. For a compiled-nonempty
query containing CJK, select from the complete active-Publication FTS `MATCH` set, then apply CJK
support. Compatibility CJK characters are recognized after NFKC normalization. The original query
still feeds the ASCII compiler; normalization does not rewrite stored Evidence.

The mixed selector:

1. Uses the repository's active-Publication FTS match, stable FTS order, and provenance checks.
   It does not implement an approximate second ASCII matcher.
2. In one consistent read, measures the complete matched set before loading text. More than
   10,000 rows or 16 MiB of original UTF-8 Evidence text produces a typed budget failure. No
   preselection `LIMIT` or `OFFSET` may silently remove a relevant candidate.
3. Forms a comparison view using NFKC, casefold, and whitespace removal. Query CJK runs produce
   deterministic deduplicated trigrams. Raw and normalized queries are bounded at 512 characters,
   and terms at 128.
4. Requires at least two matched trigrams and an overlap ratio of at least 0.30. More than 1,000
   eligible candidates produces a typed failure. No eligible terms or no jointly supported
   candidate produces no Evidence, so Ask retains `insufficient_evidence`.
5. Orders eligible candidates by descending overlap count, descending ratio, then the unchanged
   stable FTS order. Generated opaque IDs are never tie-break authority. The existing maximum of
   10 selected results applies after mixed selection; caller limits and page slices follow it.

Budget overflow, strategy capping, response-byte limits, and normal pagination are separate
conditions. The mixed route must never replace a budget failure with an ASCII-only result.

## Shared Consumption And Identity

Ordinary Search, Ask, provenance snapshots, and paged MCP Search consume the same mixed selection
semantics. Cursors bind the new strategy ID and revision alongside the existing query, policy,
process, and active authority identity. Cross-strategy or cross-revision continuations fail closed.
`more_available` represents more of the selected pool; `capped` represents eligible candidates
discarded by the strategy limit. Exact Evidence read remains available.

Mixed excerpts point to actual CJK support in original Evidence. Any added normalization is an
internal match hint for the new strategy. Every excerpt byte range must be a valid UTF-8 slice of
the unchanged original text, including compatibility expansion and combining-character cases.
Original citation text, hashes, IDs, locators, exports, and immutable Run/Evidence/Publication
semantics remain unchanged.

Readiness checks use the existing base FTS projection and active-Publication authority. The
existing rollback strategies remain directly selectable.

## Frozen Acceptance Classes

Before implementation, freeze public-neutral synthetic Evidence, queries, and expected locators
covering:

- Two unrelated ASCII anchors with distinct CJK intents; the matching Evidence differs by intent.
- A relevant item beyond FTS top five that appears in mixed top five, limited Search and Ask,
  and MCP pagination over multiple pages.
- Numeric grouping (`30/50` versus `99/88`), units (`3T` versus `9T`), leading-zero identifiers,
  adjacency, and proper names. Missing any compiled clause excludes a candidate.
- Shared ASCII anchors with unsupported CJK intent, absent ASCII match, short CJK wording, and
  unsupported paraphrases. These do not manufacture Evidence.
- Compatibility glyphs such as `⽅`/`方`, whitespace breaks, normalization expansion, combining
  characters, and byte-exact original excerpts.
- Equivalent stores with different generated IDs; inactive, superseded, failed, and unpublished
  Evidence; duplicate projection and provenance failures.
- Matched row and byte caps, query and term caps, eligible-pool cap, selected-result cap,
  response-byte bounds, and relevant bounded-performance checks.
- Unchanged baseline strategies/default and their frozen quality outputs. Candidate observations
  are recorded separately without editing prior fixture bytes, qrels, or receipts.

Use RED/GREEN regression and focused checks during implementation. At a stable candidate run the
applicable repository verification and built-artifact CLI/MCP checks with cached offline tools.
Report an unavailable gate as unrun; do not change tests or install dependencies to bypass it.

## Limits

Literal trigram overlap may miss short CJK wording and paraphrases without sufficient shared text.
This design does not add dense retrieval, query rewrite, reranking, a model call, or a general
semantic answer path. It does not authorize default promotion, push, PR, merge, or release.
