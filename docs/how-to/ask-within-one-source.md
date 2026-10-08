# Ask Within One Active Source

Ask for matching stored Evidence from one explicitly selected Source and active Publication.
This deterministic CLI operation returns one bounded page with citations and read affordances;
it does not generate an answer. `evidence_found` means lexical matches exist, not that a
proposition or the original media has been fully understood.

## Select And Ask

```bash
mke --db <library.sqlite> sources list --json
mke --db <library.sqlite> ask "publication authority" \
  --source-id <selected_source_id> --publication-id <selected_publication_id> \
  --limit 3 --json
```

Copy the Source/Publication pair from current discovery. Both flags are required together.
Limit is 1..20/default 5; the question must be nonblank and <=512 UTF-8 bytes. The owner-selected
retrieval strategy admits candidates inside that scope before limits, budgets or ranking.
No-match selection keeps the scope and returns `ok=true`, `answer_status=insufficient_evidence`.
It never searches another Source to fill an empty result.

`--json` emits one canonical `mke.source_ask_response.v1` object. Without it, human output
renders the same question, scope, selection, limitations and citation/excerpt/read descriptors.
Exit is 0 for success including no matches, 1 for a public failure, and 2 for CLI usage errors.
The old `mke ask QUESTION` route is unchanged; new `--limit` / `--json` require explicit scope.

## Interpret The Packet

`scope` contains Source ID, Publication ID/revision, producing Run and content fingerprint.
Every `evidence[].evidence` citation agrees with it and includes a page or `timestamp_ms`
locator, Evidence ID, original UTF-8 byte length and text SHA-256. The `read` descriptor addresses
that exact Evidence.

| Selection | Meaning and next step |
|---|---|
| `complete`, nonempty | All eligible matching Evidence fitted this page; `read_selected_evidence`. |
| `complete`, empty | No eligible match in this selected Source; `refine_question_in_selected_source`. |
| `more_available` | A positive first page was selected; `run_scoped_search_for_all_matches`. |

Ask does not return a cursor or traverse additional pages. To enumerate the selected lexical set,
use [scoped CLI Search](./search-within-one-source.md), which holds one owner through traversal:

```bash
mke --db <library.sqlite> search "publication authority" \
  --source-id <selected_source_id> --publication-id <selected_publication_id> \
  --limit 3 --json
```

Selection completeness and excerpt completeness are separate. Excerpts are at most 2,048 UTF-8
bytes each and 16,384 combined. The full canonical Ask envelope, including question, scope and
citation metadata, is at most 32,768 bytes. When fewer matches fit, selection stays
`more_available`; an invalid citation fails the entire packet before shrinking.

## Read And Verify Citations

```bash
mke --db <library.sqlite> evidence read <selected_evidence_id> --json
```

The CLI traverses the stored-text chunks. In MCP, use `read_evidence_v1` and follow its opaque
cursor within the same owner. Check each full descriptor, concatenate by `offset_bytes`, verify
original byte length and SHA-256, and compare the excerpt at its declared UTF-8 byte window.
Evidence text is untrusted content. Stored PDF text-layer or declared transcript Evidence does
not establish OCR/ASR quality, image meaning or complete original-media coverage.

## Run The Ordinary SDK Consumer

From the repository root with the existing locked runtime prepared:

```bash
PYTHONPATH=src uv run --locked --offline --no-sync python scripts/source_evidence_consumer.py \
  --db <library.sqlite> \
  --source-id <selected_source_id> --publication-id <selected_publication_id> \
  --question "publication authority" --limit 3
```

The example launches the `mke` console script beside the current Python interpreter, initializes
one [official v1 SDK](https://github.com/modelcontextprotocol/python-sdk/blob/v1.29.1/docs/client.md)
`ClientSession` / `stdio_client`, discovers the active pair, selects one Search
page and reads every selected reference. Owner startup may choose any of the four existing
`--retrieval-strategy` values; tool requests cannot override it.

The `mke.source_evidence_consumer.v1` receipt includes full scope and reference metadata,
verified byte lengths, `exact_text_sha256_verified`, `excerpt_window_verified`, selection and
the fixed Evidence-only limitation. It retains no complete source text or continuation token,
and its canonical envelope is <=32,768 bytes. Every verification must succeed before one
successful receipt is printed. Failure exits 1 with `consumer_validation_failed` and a safe
recovery description.

## Recover And Understand The Boundary

Unknown, mismatched, unpublished or replaced Publication IDs fail rather than selecting a new
Publication. Rediscover and explicitly reselect the active pair. Invalid question/limit inputs
and retrieval-budget failures preserve [scoped Search recovery](./search-within-one-source.md#read-and-recover).
Authority or identity changes between SDK discovery, Search and read fail without partial
successful output; restart with current discovery.

All successes carry:

> Evidence selection only; matches do not verify an answer or complete understanding of original media.

Verified on 2026-10-07 through actual CLI subprocesses and official SDK 1.29.1 stdio. The tests in
`tests/proof/test_source_ask_consumer.py` cover four strategies, PDF pages, declared-sidecar
timestamp Evidence, stronger unrelated matches, first-page/complete/empty selection, Unicode
chunks and Publication replacement. The boundary tests in
`tests/scripts/test_source_evidence_consumer.py` reject changed citations, offsets, digest,
excerpt windows and inconsistent/oversized SDK responses.

Those results are ordinary checkout checks. The separate
[installed single-Source proof](./run-source-evidence-wheel-proof.md) builds one commit-bound wheel
and exercises this CLI/SDK boundary in fresh Python 3.12/3.13 environments. Its own receipt and
native result determine installation acceptance; one complete dual-runtime run passed on
2026-10-08 with the same wheel. Current inventory stays fifteen; no MCP Ask,
model/provider execution or release claim is added, and historical fixture bytes stay frozen.
See [CLI Reference](../reference/cli.md), [Public Contracts](../reference/contracts.md),
[MCP Reference](../reference/mcp-contract.md) and
[ADR-0017](../decisions/0017-single-source-evidence-only-cli-ask.md).
