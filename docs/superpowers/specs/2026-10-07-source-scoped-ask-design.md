# Single-Source Evidence-Only CLI Ask

Status: Approved implementation scope; interface details frozen for this slice.
Date: 2026-10-07

## Goal And Boundary

Let a caller ask for matching stored Evidence from one explicitly selected active Source and
Publication. Reuse the existing scoped Search contract before candidate limits, budgets and
ranking. Ask remains deterministic Evidence selection; it generates no semantic answer and
does not verify a proposition or full understanding of the original media.

Keep unscoped CLI Ask, application Ask and every existing MCP contract unchanged. The current
inventory remains fifteen tools. No dependencies, model/provider, database migration,
permissions, historical Publication access or multi-Source aggregation are introduced.

## CLI Contract

```text
mke --db <library.sqlite> ask QUESTION
    --source-id <source_id> --publication-id <publication_id>
    [--limit 1..20] [--json]
```

Both identity flags are required together. `--limit` defaults to 5. The new `--limit` and
`--json` options require that explicit scope; an old command follows its unchanged route.
Scoped question validation uses the existing scoped Search query contract: nonblank and at
most 512 UTF-8 bytes. Four owner-selected retrieval strategies retain their existing defaults
and semantics. Identity mismatch, unknown/unpublished/replaced Publication, invalid input and
retrieval budgets preserve scoped Search's typed failure and recovery; no Library fallback.

Freeze one bounded first page, not automatic multi-page Ask. A successful command emits one
strict `mke.source_ask_response.v1` packet with `--json`. Human output renders the same bounded
facts. Exit codes are 0 for a successful packet including zero matches, 1 for a public failure,
and 2 for CLI usage errors. No process-bound cursor is exposed as a reusable Ask continuation.

## Response Contract

Success contains `schema_version`, `ok`, `question`, `answer_status`, `scope`,
`authority_snapshot`, `evidence`, `selection`, `output` and `limitations`.

- `scope` is the existing `mke.source_search_scope.v1` identity: Source, active Publication,
  Publication revision, producing Run and content fingerprint.
- `evidence` contains at most 20 existing SearchMatchV2 citation/excerpt/read descriptors.
  Every complete citation must agree with scope; the read descriptor addresses that same
  Evidence. A mismatched citation fails the entire operation rather than being filtered out.
- `answer_status` is `evidence_found` exactly when Evidence is nonempty; otherwise it is
  `insufficient_evidence`. These statuses describe lexical matching stored text.
- `selection` contains `mode="bounded_first_page"`, `status`, `returned` and `next_step`.
  Status is `complete` only if the underlying Search page is complete and no selected match
  was omitted for the Ask envelope. Otherwise it is `more_available`, with positive progress
  and `next_step="run_scoped_search_for_all_matches"`. Complete nonempty output uses
  `read_selected_evidence`; complete empty output uses `refine_question_in_selected_source`.
- `limitations` is the fixed statement: `Evidence selection only; matches do not verify an
  answer or complete understanding of original media.`
- `output` reuses `mke.search_output_budget.v1`. Per-excerpt maximum is 2,048 UTF-8 bytes,
  combined excerpts 16,384 bytes, and the complete canonical packet 32,768 bytes. Question,
  scope, all citation metadata, selection and limitations count toward that envelope.

Assemble from exactly one validated scoped Search snapshot. Reduce the number of returned
matches when the added Ask envelope cannot fit; recompute selection and incomplete-excerpt
counts. Never emit an empty successful page when Search found matches. If mandatory metadata
and one match cannot fit, return `response_too_large`. Error packets keep the existing
`problem`, safe `cause`, `active_publication_impact` and `next_step` shape under the new schema.

The canonical JSON schema snapshot is `tests/fixtures/source-ask-v1/cli-response-schema.json`.
It is a CLI DTO snapshot, not a change to any historical MCP fixture or tool inventory.

## Ordinary MCP Consumer Example

Provide `scripts/source_evidence_consumer.py` using the installed official MCP SDK over one
stdio owner. The caller supplies the selected Source/Publication, question and page limit.
Discover the active selection through `list_sources_v1`, request a bounded first page from
`search_source_evidence_v1`, then consume every selected citation through `read_evidence_v1`.

Validate strict public DTOs, selected scope/lineage and authority, every exact-read descriptor,
UTF-8 byte offsets/lengths, final SHA-256 and excerpt bytes. Stop on a public error, changed
identity, malformed response or digest mismatch; never return a successful verification receipt
for unverified Evidence. Reads may stream several bounded chunks; the receipt contains bounded
reference metadata, not the complete source text. Its canonical envelope is at most 32,768 bytes.
Disclose first-page completeness and the scoped Search next step. The example adds no MCP tool
and makes no installed-wheel, ASR, model-quality or original-media-understanding claim.

## Acceptance

- Actual CLI subprocess: stronger same-term matches from another Source never enter the
  selected packet; PDF page and declared sidecar timestamp citations remain readable.
- All four strategies, zero matches, complete/more_available, Unicode/escaping and complete
  envelope budgets work; old unscoped behavior and current/historical MCP snapshots remain.
- Actual SDK stdio consumer: scope, citation, locator, exact UTF-8 text/digest and excerpt
  validation succeed for PDF/timestamp inputs; mismatch and replacement fail closed.
- Add tests for the new route and focused shared boundaries. Reuse unchanged Search and
  unrelated capability evidence instead of repeating broad or costly proofs.
- Public entry points, reference docs and how-to reflect actual verified behavior. Produce
  independently reviewable local commits and a concrete remote candidate.
