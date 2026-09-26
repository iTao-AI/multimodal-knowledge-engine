# ADR-0013: Mixed CJK/ASCII Intent Retrieval

## Status

Accepted for an explicit owner-selected candidate. The default remains
`cjk-active-scan-overlap-v1`; promotion requires a separate decision.

## Context

ADR-0008 deliberately keeps a compiled-nonempty mixed query on FTS5. This preserves every
ASCII and numeric clause, including on zero hits, but queries with the same ASCII anchor and
different CJK intent can receive the same anchor-only Evidence. Dropping FTS constraints in a
fallback was previously rejected because it lost numeric distinctions. The candidate therefore
keeps the complete FTS `MATCH` as admission authority and checks CJK support within that set.

The bounded design and acceptance classes are recorded in the
[mixed-query design](../superpowers/specs/2026-09-24-mixed-cjk-fts-intent-design.md).

## Decision

Add owner-selected `mixed-cjk-fts-intent-v1`, revision `1`. It compiles the original query with
`numeric-grouping-v1` and leaves the compiler and `QUERY_POLICY_REVISION` unchanged. No-CJK
queries use the existing numeric FTS route. Compiled-empty CJK queries use the existing bounded
CJK active scan and Ask validation semantics. Compiled-nonempty mixed queries must first match
every original FTS clause against active Publications; no zero-hit fallback discards constraints.

Before loading mixed candidate text, count all matched rows and their original UTF-8 text bytes
in a consistent read. Caps are 10,000 rows and 16 MiB. An exceeded cap is a typed failure, not
partial selection. Compare query and candidate CJK text after NFKC, casefold, and whitespace
removal. Bound raw and normalized queries at 512 characters and deduplicated CJK trigrams at 128.
Require at least two matched trigrams and an overlap ratio of 0.30. More than 1,000 eligible
candidates is a typed failure. No eligible terms or jointly supported candidate yields no
Evidence.

Rank eligible candidates by overlap count, overlap ratio, then the existing stable FTS order.
Apply the 10-result strategy cap only after ranking, then caller limits and page slices. Search,
Ask, provenance snapshots, and paged MCP Search share these semantics. Cursor identity includes
the new strategy ID/revision and the existing query, policy, process, and active-authority fields.
Strategy capping is distinct from ordinary page continuation and response-byte truncation.

Mixed excerpts use actual CJK support, with internal normalization spans mapped back to original
UTF-8 Evidence byte ranges. Stored text, hashes, locators, citations, exports, Run, Evidence, and
Publication are unchanged. Readiness checks the existing active FTS projection and Publication
authority. The strategy adds no schema, projection, persistent cache, request-time override,
provider, or service.

## Compatibility And Rollback

`cjk-active-scan-overlap-v1` remains the default and the immediate prior behavior;
`numeric-grouping-v1` and `current` remain selectable rollbacks. Their IDs, revisions, outputs,
and frozen evaluation artifacts are unchanged. No migration, index rebuild, or Evidence rewrite
is required to select a rollback.

ADR-0008's FTS-only rule still describes its own strategy. This ADR defines only the new explicit
candidate and does not alter ADR-0007's numeric compiler or ADR-0012's stable FTS order.

## Limits

This lexical selector can miss short CJK wording and paraphrases without enough literal trigram
overlap. It does not claim semantic reasoning, generic Chinese quality, dense or hybrid
retrieval, query rewrite, reranking, default promotion, or hosted behavior.
