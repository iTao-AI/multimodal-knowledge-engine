# ADR-0017: Single-Source Evidence-Only CLI Ask

Status: Accepted
Date: 2026-10-07

## Decision

Add opt-in CLI Ask with an explicit Source and its active Publication. Compose exactly one
validated `search_source_evidence_v1` snapshot; reuse ADR-0016's scope admission before candidate
limits, budgets and ranking. Keep the application Ask methods, unscoped CLI Ask and all fifteen
MCP tools unchanged. This extends the CLI behavior deferred by ADR-0016 without adding an Ask
MCP tool, new retrieval path or permission boundary.

Freeze bounded first-page selection: limit 1..20/default 5 and question <=512 UTF-8 bytes.
`mke.source_ask_response.v1` discloses the question, full selected Source/Publication/revision/
Run/content scope, authority snapshot, existing citation/excerpt/read descriptors and limitations.
`evidence_found` means lexical matching Evidence was selected; zero matches return
`insufficient_evidence` in that same scope. Neither status verifies a semantic answer or
proposition, and neither permits fallback to another Source or Publication.

Validate all Search citations before any envelope omission. Preserve the 2,048-byte per-excerpt,
16,384-byte combined excerpt and 32,768-byte complete canonical envelope budgets. Shrink the
returned count when the added Ask metadata requires it; never hide an invalid citation or turn
nonempty Search into an empty success. If metadata plus one match cannot fit, return
`response_too_large`.

`selection.mode=bounded_first_page` is `complete` only when the underlying page was complete
and no match was omitted for this envelope. Otherwise it is `more_available` with positive
progress and `next_step=run_scoped_search_for_all_matches`. Completeness concerns eligible
stored lexical matches, separately from excerpt completeness or original-media understanding.
Ask exposes no cursor: the existing CLI scoped Search can traverse all pages under one owner.

## Consumer Verification

Provide an ordinary checkout SDK example using `list_sources_v1`, `search_source_evidence_v1`
and `read_evidence_v1` over one stdio owner. Each call retains its existing read transaction.
The consumer compares observed authority and full selected lineage across discovery, Search and
every read; it does not claim one long transaction across the SDK flow.

Before emitting a bounded verification receipt, consume every selected citation and verify the
complete descriptor, contiguous UTF-8 offsets/lengths, final SHA-256 and excerpt byte window.
Reject a changed Publication, malformed response or inconsistent text instead of emitting a
partial successful receipt. Stream text while retaining only the bounded excerpt window and
reference metadata. This verifies stored Evidence bytes, not ASR, visual meaning or model quality.

## Compatibility And Consequences

No domain/storage migration, dependency, provider/model, runtime strategy/default, permission,
historical access or multi-Source aggregation changes. The new CLI schema has a separate frozen
snapshot; every current/historical MCP inventory fixture remains unchanged. Ordinary SDK
verification is checkout evidence, not an installed-wheel or release proof.

See [Ask Within One Active Source](../how-to/ask-within-one-source.md) and
[ADR-0016](./0016-single-source-active-publication-search.md).
