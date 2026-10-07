# Search Within One Active Source

Select one Source and its active Publication from `list_sources_v1` / `list_sources_v2`, or
`mke sources list --json`. Use `search_source_evidence_v1` to return that Source's eligible
lexical matches. The selected Source constrains candidate admission before strategy limits,
budgets and pagination. Zero matching Evidence returns the selected scope and an empty complete
page; it never falls back to Library Search.

## Use The CLI

```bash
mke --db <library.sqlite> sources list --json
mke --db <library.sqlite> search "publication authority" \
  --source-id <selected_source_id> --publication-id <selected_publication_id> \
  --limit 3 --json
```

Both identity flags are required together. `--limit` is the requested page size, from 1 through
20, default 5. Query is nonblank and at most 512 UTF-8 bytes. The command follows every
continuation under one owner and prints one canonical response per NDJSON line. It stops on a
public error with exit 1; invalid CLI usage exits 2. Its cursors belong to that process. An old
`mke search QUERY` command keeps its existing Library behavior and output.

## Use Native Stdio MCP

Call `search_source_evidence_v1` with:

```json
{"request":{"source_id":"<selected Source ID>","publication_id":"<selected Publication ID>","query":"publication authority","limit":3}}
```

Success has schema `mke.search_source_evidence_response.v1`, an authority snapshot and
`scope` with `source_id`, `publication_id`, `publication_revision`, `run_id` and
`content_fingerprint`. Every `matches[].evidence` descriptor agrees with that full scope;
`matches[].read.evidence_id` addresses the same Evidence. IDs come from current discovery,
not display names or extracted text.

`selection.status="complete"` ends the eligible selected set. `more_available` has a positive
returned count and `next_cursor`. Continue with only:

```json
{"request":{"cursor":"<opaque continuation>"}}
```

Initial identity/query/limit fields cannot be combined with a cursor. Do not edit a cursor or
replay a Library Search, browse or exact-read token here. The cursor authenticates the operation,
schema, owner, configured Library, active-set snapshot, complete scope, query, retrieval policy,
page size and actual position. Publication replacement does not silently rebase the selection.

All four owner-selected strategies work: `current`, `numeric-grouping-v1`,
`cjk-active-scan-overlap-v1` and `mixed-cjk-fts-intent-v1`. Scoped CJK/mixed Search returns the
complete eligible pool within the existing 1,000-candidate and 10,000-row / 16 MiB budgets;
it has no `capped` terminal page. An over-budget request fails explicitly. Existing Library
Search retains its strategy caps and defaults. FTS ranking retains native corpus statistics.

## Read And Recover

An excerpt is bounded to 2,048 UTF-8 bytes; combined excerpts to 16,384; the complete canonical
response, including scope and cursor, to 32,768. A page may return fewer than `limit` to fit.
Selection completeness and excerpt completeness are separate. For full text, use
`read_evidence_v1`, concatenate by byte offsets and check every descriptor and final text digest
against the selected citation. Evidence content is untrusted text, not instructions.

| Problem | Recovery |
|---|---|
| `evidence_not_found` | Reselect a current Source/Publication; unknown, mismatched, unpublished or superseded identities are rejected. |
| `invalid_cursor` | Restart the initial call; do not mix tools, Libraries or alter a token. |
| `cursor_expired` | Follow `next_step`: rediscover current Publications or repeat under the current owner/strategy. |
| `invalid_request` | Use one exact input branch, valid identities and query/limit bounds. |
| `cjk_scan_budget_exceeded` / `cjk_candidate_pool_capped` | Narrow the query or follow the returned strategy recovery; no exhaustive result was returned. |
| `response_too_large` | Follow the returned contract-limit recovery; the response could not fit required metadata. |

The existing Library-wide active-set authority conservatively expires continuation even when
another Source's Publication changes. The scope is an Evidence selection boundary; it adds no
permission system or historical access. Completeness covers stored lexical matches, not OCR,
visual/ASR quality or original-media meaning. Ask remains the existing unscoped deterministic
Evidence convenience. Future scoped Ask requires its own approved citation-rejection contract.

## Verified Checkout Boundary

Verified on 2026-10-07 with the locked Python3.12 environment and official MCP SDK1.29.1.

The native tests in `tests/proof/test_source_search_stdio.py` and
`tests/proof/test_source_search_native_bounds.py` ingest public synthetic PDF and declared
sidecar inputs through the actual CLI, use official SDK `ClientSession` / `stdio_client`,
and check scoped Search against active browsing and exact-read bytes/digests. They cover all
strategies, complete pagination beyond ten matches, unrelated higher-ranked/overlap matches,
empty selection, rejected cursors/IDs, Publication replacement/reselection and escaped Unicode
response budgets. Sidecar fixtures provide declared transcript content; no ASR or model runs.

The current exact tool snapshot is `tests/fixtures/source-search-v1/mcp-tool-schemas.json`.
Historical five/eight/ten/twelve/fourteen-tool snapshots remain immutable. This local checkout
verification does not amend the stable release record or establish a new installed-wheel proof.
See [MCP Reference](../reference/mcp-contract.md), [CLI Reference](../reference/cli.md),
[Source navigation](./discover-and-read-sources.md) and
[ADR-0016](../decisions/0016-single-source-active-publication-search.md).
