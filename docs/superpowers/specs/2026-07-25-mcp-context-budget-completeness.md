# MCP Context Budget and Completeness Contract

Status: approved design for mechanical public spec landing and implementation planning.
Implementation, dependency changes, publication, deployment, and release remain pending.

Planning baseline: `d0b3b8e3f73005851570cf8fcf546030a9e2ceb5`.

## Summary

MKE already exposes active-Publication Evidence through Python, CLI, and local stdio MCP.
The current MCP Search and Ask contracts are bounded by caller limits but do not tell a
consumer whether more selected results exist, whether retrieval stopped at a strategy cap,
or whether a returned Evidence text is complete. Strict v1 also has no bounded continuation
path for an authoritative Evidence item that exceeds its text model limit.

This design adds exactly two local, read-only MCP tools:

```text
search_library_v2
  -> bounded relevance-preserving Evidence excerpts
  -> explicit selected-result completeness
  -> full Run / Publication / Evidence provenance

read_evidence_v1
  -> bounded UTF-8 chunks
  -> exact active-authority Evidence reconstruction
  -> final SHA-256 verification
```

The tools reuse the existing application, retrieval, SQLite, Run, Publication, Evidence,
and active-only authority. They add no Agent loop, answer generator, persistence layer,
remote service, provider, or retrieval strategy.

## Problem Evidence

### RED-1: selected-result completeness is not observable

Given two active Evidence items matching one query:

1. call current Search with `limit=1`;
2. observe one returned item;
3. observe no `complete`, `more_available`, `capped`, or cursor field.

The consumer cannot distinguish one authoritative match from one returned match with more
selected matches omitted.

### RED-2: strict v1 has no bounded complete-Evidence read path

Given one active admissible Evidence item whose text exceeds the current 1,000,000-character
strict model bound:

1. legacy MCP can produce an oversized result;
2. strict v1 fails through the generic redacted boundary;
3. Compiled Library Export rejects the case under its separate bounded contract;
4. no versioned MCP tool can read the complete item in bounded chunks.

The consumer must either risk an oversized response or lose the MCP path to authoritative
Evidence.

### Relevance failure

A prefix-only preview may omit the only matched term when the match occurs later in a large
Evidence item. A bounded preview therefore needs a deterministic query-centered window and
an explicit fallback when a reliable matched span is unavailable.

## Product Decision

The supported contract is:

> A local MCP consumer can search active-Publication Evidence with explicit selected-result
> and per-item completeness, then retrieve any incomplete active Evidence item through a
> bounded, authority-bound, exact UTF-8 read path.

The capability is additive. New consumers should prefer `search_library_v2`. Existing
legacy and strict-v1 tool calls remain compatible. Exact full-inventory consumers must
adopt the additive ten-tool inventory explicitly.

## Goals

1. Make page continuation, strategy caps, and shortened Evidence text separately observable.
2. Keep every successful result bound to the current per-Source active Publication set.
3. Preserve Source, Publication revision, producing Run, locator, and source-byte identity.
4. Provide a bounded exact read path for an incomplete Evidence excerpt.
5. Keep every new response a closed, versioned success/error union.
6. Enforce deterministic UTF-8 byte budgets before serialization.
7. Keep legacy/v1 success schemas and valid bounded responses unchanged.
8. Improve oversized v1 Search/Ask failures with a typed stable error.
9. Prove the real installed-wheel stdio consumer path through the locked official MCP SDK.
10. Stop after this capability closes; do not expand into retrieval promotion or a platform.

## Non-Goals

This work does not add:

- `ask_library_v2` or `list_libraries_v2`;
- answer generation, summarization, or an internal Agent loop;
- exhaustive corpus-wide retrieval or total-match counting;
- changes to lexical ranking, CJK scoring, dense retrieval, RRF, reranking, or evaluation
  promotion;
- ingestion segmentation, Passage promotion, or representative-corpus expansion;
- OCR runtime or OCR-E1;
- persistent cursors, a cursor table, cache, queue, or second authority;
- HTTP, remote MCP, cloud service, SaaS, authentication, RBAC, billing, or deployment;
- runtime telemetry, analytics, hosted observability, or background jobs;
- a new provider, account, model, download path, dependency, or framework migration;
- an MCP Python SDK 2.x migration; or
- production, adoption, quality, latency, throughput, or SLA claims.

## Existing Authority and Reuse

The implementation must reuse:

- `KnowledgeEngine` as the shared application façade;
- the existing PEP 249 snapshot transaction pattern;
- per-Source active Publication graph validation;
- active-only FTS and CJK selection;
- `SearchResultProvenance` and `mke.evidence_ref.v1` provenance fields;
- current query policy and retrieval strategy;
- current owner runtime and stdio process lifecycle;
- current strict Pydantic model and public-error patterns;
- current installed-wheel, real-stdio, and standalone-consumer proof patterns.

The MCP adapter must not add direct parallel SQLite reads, alternate ranking, alternate
Publication selection, a second Evidence store, or a second export authority.

```text
MCP stdio request
  -> strict project input validation
  -> shared owner runtime
  -> existing active-authority application/repository path
  -> strategy-aware selection or active Evidence read
  -> deterministic excerpt/chunk and response budgeting
  -> strict structured MCP result
```

## Public Tool Inventory

The eight existing tools remain:

- `list_libraries`
- `ingest_file`
- `get_run`
- `search_library`
- `ask_library`
- `list_libraries_v1`
- `search_library_v1`
- `ask_library_v1`

Add:

- `search_library_v2`
- `read_evidence_v1`

No other tool is part of this capability.

## Shared Strict Wire Rules

`search_library_v2` returns:

```text
SearchLibraryV2Success | SearchLibraryV2Error
schema_version = mke.search_library_response.v2
discriminator = ok
```

`read_evidence_v1` returns:

```text
ReadEvidenceV1Success | ReadEvidenceV1Error
schema_version = mke.read_evidence_response.v1
discriminator = ok
```

Every new public model is frozen, strict, and rejects extra fields. Cross-field invalid
states must be rejected before repository access. UTF-8 byte limits use encoded-byte
validators; character-count validators do not stand in for byte budgets.

Both additive tools expose one required top-level `request` parameter. Its value is the
strict initial-or-continuation union described below. This native FastMCP envelope preserves
the difference between the two branches without SDK-private schema mutation. A missing
top-level `request` is rejected by FastMCP input validation; an invalid value inside the
present envelope is translated to the tool's typed strict error response before repository
access.

FastMCP registration explicitly enables structured output. Tests must validate
`outputSchema`, `structuredContent`, and the SDK's compatibility text content.

## Active Authority Snapshot

Both new success responses contain one complete `ActiveAuthoritySnapshotV1`:

```json
{
  "schema_version": "mke.active_authority_snapshot.v1",
  "observation": {
    "schema_version": "mke.active_publication_observation.v1",
    "library_id": "local",
    "state": "active",
    "source_count": 2,
    "active_publication_count": 2,
    "active_evidence_count": 12
  },
  "active_set_fingerprint": "sha256:<digest>"
}
```

Observation counts are not authority. The fingerprint is derived in the same existing
read transaction as validation and search/read. Its canonical UTF-8 JSON preimage contains:

- a domain separator and fingerprint schema version;
- `library_id`;
- records sorted bytewise by `source_id`;
- for each record: `source_id`, `content_fingerprint`, `active_publication_id`,
  `active_revision`, `run_id`, `manifest_evidence_count`, `manifest_sha256`,
  sorted `required_stages`, and `extractor_fingerprint`.

Display-only metadata is excluded. The fingerprint is never persisted, activated, or called
a Publication. It is only a derived continuation-invalidation observation.

## Evidence Descriptor

Search matches and Read chunks use one shared strict descriptor:

```json
{
  "evidence_id": "ev_<opaque-id>",
  "source_id": "src_<opaque-id>",
  "content_fingerprint": "sha256:<source-byte-digest>",
  "publication_id": "pub_<opaque-id>",
  "publication_revision": 1,
  "run_id": "run_<opaque-id>",
  "locator": {"kind": "page", "start": 1, "end": 1},
  "evidence_text_sha256": "sha256:<complete-evidence-text-digest>",
  "original_utf8_bytes": 1000001
}
```

`content_fingerprint` continues to identify original Source bytes.
`evidence_text_sha256` identifies the complete authoritative Evidence text bytes.

## `search_library_v2`

### Input

The tool exposes one strict runtime union:

Initial:

```json
{"request": {"query": "publication authority", "limit": 10}}
```

Continuation:

```json
{"request": {"cursor": "<opaque-token>"}}
```

Rules:

- the outer call requires exactly one `request` property;
- inside `request`, initial requires `query`, permits optional `limit`, and forbids `cursor`;
- inside `request`, continuation requires `cursor` and forbids `query` and `limit`;
- `query` is non-blank and at most 512 encoded UTF-8 bytes;
- `limit` is a strict integer in `1..20`; booleans are invalid;
- cursor is at most 4096 encoded UTF-8 bytes;
- empty, null-valued, scalar, and mixed `request` values fail before repository access;
- no request-time strategy or output-budget override exists.

The signed cursor carries the normalized query and limit. Consumers do not repeat bound
state on continuation.

### Search Success Shape

```json
{
  "schema_version": "mke.search_library_response.v2",
  "ok": true,
  "authority_snapshot": {
    "schema_version": "mke.active_authority_snapshot.v1",
    "observation": {
      "schema_version": "mke.active_publication_observation.v1",
      "library_id": "local",
      "state": "active",
      "source_count": 2,
      "active_publication_count": 2,
      "active_evidence_count": 12
    },
    "active_set_fingerprint": "sha256:<digest>"
  },
  "query": "publication authority",
  "matches": [],
  "selection": {
    "schema_version": "mke.search_selection.v2",
    "status": "complete",
    "returned": 0
  },
  "output": {
    "schema_version": "mke.search_output_budget.v1",
    "incomplete_excerpt_count": 0,
    "content_budget_bytes": 16384,
    "envelope_budget_bytes": 32768
  }
}
```

### Selection Completeness

`selection.status` is a closed union:

| Status | Required fields | Forbidden fields | Meaning |
|---|---|---|---|
| `complete` | `status`, `returned` | cursor, cap reason | all strategy-selected results were emitted and no eligible match was discarded by a strategy cap |
| `more_available` | `status`, `returned`, `next_cursor` | cap reason | more results remain in the current strategy-selected pool |
| `capped` | `status`, `returned`, `limit_reason` | cursor | the selected pool is exhausted, but the strategy discarded additional eligible matches |

`more_available` takes priority while an item remains inside the selected pool, including a
pool already known to have an outer strategy cap. Only the terminal page reports `capped`.
`capped` never claims corpus-exhaustive matching.

There is no redundant `has_more` boolean.

### Per-Item Completeness

Each match contains the shared Evidence descriptor plus:

```json
{
  "excerpt": {
    "kind": "query_window",
    "text": "deterministic UTF-8-safe matched window",
    "start_utf8_byte": 20000,
    "end_utf8_byte": 22048,
    "prefix_omitted": true,
    "suffix_omitted": true,
    "complete": false,
    "returned_utf8_bytes": 2048,
    "content_trust": "untrusted_evidence"
  },
  "read": {
    "tool": "read_evidence_v1",
    "evidence_id": "ev_<opaque-id>"
  }
}
```

Selection completeness and item completeness are independent:

- `selection.status` controls collection continuation;
- `excerpt.complete` controls whether exact Evidence read is needed.

The top-level output budget may report `incomplete_excerpt_count` as a diagnostic. It is
not a control-flow field. There is no aggregate `output.complete`.

### Excerpt Algorithm

The retrieval/application path returns stable match hints and selection metadata. MCP does
not reconstruct ranking or guess matched spans.

- FTS hints come from compiled query-clause diagnostics.
- CJK preserves scorer-matched terms.
- normalized indices map back to original text before byte offsets are calculated;
- with multiple reliable spans, choose the earliest UTF-8 byte span, then clause/term order;
- balance the remaining byte budget around the span;
- move boundaries inward to complete UTF-8 code points;
- if no reliable span exists, return `kind="prefix_fallback"`;
- never label a prefix fallback as query-centered;
- guarantee code-point safety, not grapheme-cluster safety.

Cursor position advances only past items actually emitted under the aggregate budget.
Budget-dropped items remain the first item of the next page.

## `read_evidence_v1`

### Input

Initial:

```json
{"request": {"evidence_id": "ev_<opaque-id>", "max_bytes": 16384}}
```

Continuation:

```json
{"request": {"cursor": "<opaque-token>"}}
```

Rules:

- the outer call requires exactly one `request` property;
- inside `request`, initial requires `evidence_id`, permits optional `max_bytes`, and forbids
  `cursor`;
- inside `request`, continuation requires only `cursor` and forbids `evidence_id` and
  `max_bytes`;
- `max_bytes` is a strict integer in `4..16384`; booleans are invalid;
- cursor is at most 4096 encoded UTF-8 bytes;
- the cursor binds Evidence identity, chunk size, position, owner, authority, and contract;
- empty, null-valued, scalar, and mixed `request` values fail before repository access.

### Read Success Shape

```json
{
  "schema_version": "mke.read_evidence_response.v1",
  "ok": true,
  "authority_snapshot": {
    "schema_version": "mke.active_authority_snapshot.v1",
    "observation": {
      "schema_version": "mke.active_publication_observation.v1",
      "library_id": "local",
      "state": "active",
      "source_count": 2,
      "active_publication_count": 2,
      "active_evidence_count": 12
    },
    "active_set_fingerprint": "sha256:<digest>"
  },
  "evidence": {
    "evidence_id": "ev_<opaque-id>",
    "source_id": "src_<opaque-id>",
    "content_fingerprint": "sha256:<source-byte-digest>",
    "publication_id": "pub_<opaque-id>",
    "publication_revision": 1,
    "run_id": "run_<opaque-id>",
    "locator": {"kind": "page", "start": 1, "end": 1},
    "evidence_text_sha256": "sha256:<complete-evidence-text-digest>",
    "original_utf8_bytes": 1000001
  },
  "content": {
    "text": "UTF-8-safe chunk",
    "offset_bytes": 0,
    "returned_utf8_bytes": 16384,
    "content_trust": "untrusted_evidence"
  },
  "complete": false,
  "next_cursor": "<opaque-token>"
}
```

Rules:

- chunks partition the exact complete UTF-8 byte sequence without overlap or gaps;
- UTF-8 code points are never split;
- `offset_bytes` starts a half-open byte range;
- every non-terminal success makes positive progress;
- the complete Evidence descriptor is stable across chunks;
- `complete=true` exactly when `next_cursor` is absent;
- current published Evidence is non-empty; corrupt empty rows fail closed;
- initial read computes one O(total Evidence bytes) text hash;
- continuation revalidates authority, descriptor, byte count, and bounded range without
  rehashing the full text on every chunk;
- the consumer reconstructs bytes and verifies final `evidence_text_sha256`.

Published Evidence is not mutated in place by application-owned operations. Same-length
out-of-band SQLite tampering is not claimed to be detected on every intermediate chunk;
final hash verification detects reconstruction drift.

A finite maximum readable Evidence size must be proved before shipping. The provisional
design ceiling is 128 MiB. If proof does not support it, implementation must lower and
document the ceiling rather than ship an unbounded hash/read path.

## Cursor Contract

`OwnerRuntimeState` owns:

- an ephemeral per-owner HMAC-SHA256 key;
- a random non-secret `owner_epoch`.

Neither is persisted. A cursor is canonical UTF-8 JSON with sorted keys, compact separators,
no floats, no duplicate/unknown fields, a base64url envelope, and HMAC-SHA256 authentication.

The cursor binds:

- schema and tool kind;
- owner epoch;
- active-set fingerprint;
- normalized query and query fingerprint, or Evidence ID;
- retrieval strategy ID/revision and query-policy revision;
- stable position;
- page or chunk size;
- relevant project contract version;
- full Evidence text SHA-256 for Read.

It contains no Evidence text, filesystem path, HMAC key, or private configuration.

Continuation validation order:

1. reject malformed or oversized tokens before repository access;
2. resolve and validate the current active Publication set;
3. if `owner_epoch` differs, return `cursor_expired`;
4. otherwise verify HMAC with constant-time comparison and verify tool kind;
5. compare active-set fingerprint;
6. compare retrieval policy for Search;
7. validate referenced active Evidence and its full provenance graph for Read;
8. validate descriptor, byte count, and bound position;
9. continue or return a stable public failure.

A same-epoch invalid MAC is `invalid_cursor`. A different epoch is `cursor_expired`.

## Output Budgets

Initial server limits:

| Layer | Limit |
|---|---:|
| Per-item excerpt text | 2,048 UTF-8 bytes |
| Aggregate excerpt text | 16,384 UTF-8 bytes |
| Read chunk | maximum 16,384 UTF-8 bytes |
| Canonical strict success model | 32,768 bytes |
| Complete SDK `CallToolResult` | measured gate below 96 KiB under the locked SDK |

The application enforces the 32 KiB canonical model budget. The 96 KiB value is an
installed-proof ceiling, not an MCP protocol or transport claim.

Rules:

- measure each named layer after deterministic serialization;
- include metadata in the response budget;
- assemble under budget instead of clipping after serialization;
- do not publish a self-referential `used_bytes` field;
- if mandatory metadata cannot fit, return `response_too_large`;
- proof receipts record actual canonical and SDK-wire bytes.

## Stable Errors and Recovery

New strict response families include:

- `invalid_cursor`
- `cursor_expired`
- `evidence_not_found`
- `response_too_large`
- strict input validation failures
- redacted `internal_error`

Unknown, inactive, superseded, inadmissible, and cross-Publication Evidence IDs return one
uniform `evidence_not_found` payload.

| Problem | Public-safe cause category | `next_step` |
|---|---|---|
| `invalid_request` | missing/extra/mixed/null/scalar request branch | `use_exactly_one_supported_request_branch` |
| `invalid_request` | query exceeds 512 UTF-8 bytes | `narrow_query_to_512_utf8_bytes` |
| `invalid_cursor` | malformed, tampered, or wrong tool | `restart_from_initial_call` |
| `invalid_cursor` | cursor exceeds 4096 UTF-8 bytes | `restart_from_initial_call` |
| `cursor_expired` | owner restarted | `repeat_initial_call` |
| `cursor_expired` | active Publication set changed | `repeat_search_on_current_publications` |
| `cursor_expired` | retrieval policy changed | `repeat_search_under_current_strategy` |
| `evidence_not_found` | unknown, inactive, superseded, or inadmissible | `search_current_active_evidence` |
| `response_too_large` | mandatory response metadata cannot fit | `reduce_query_scope_or_report_contract_limit` |
| `invalid_request` | `max_bytes` outside `4..16384` | `choose_max_bytes_between_4_and_16384` |

Recovery guidance must not disclose which inactive or unknown internal identity was present.

## Legacy and Strict-v1 Compatibility

The following stay unchanged:

- existing tool names and input schemas;
- legacy schema snapshot;
- strict-v1 response schemas;
- valid bounded legacy/v1 success payloads;
- Ask summary strings and answer status;
- Python and CLI contracts;
- Export contracts and limits;
- ranking and retrieval behavior.

Ask descriptions and documentation clarify that its count describes returned Evidence, not
an exhaustive total. Consumers needing explicit completeness use `search_library_v2`.

For a valid v1 Search or Ask request whose Evidence text exceeds the current 1,000,000-character
strict model bound, return the existing frozen error shape with:

```json
{
  "schema_version": "mke.search_library_response.v1",
  "ok": false,
  "problem": "response_too_large",
  "cause": "complete Evidence text exceeds the v1 response limit",
  "active_publication_impact": "unchanged",
  "next_step": "use_search_library_v2"
}
```

Ask uses its own existing response schema version with equivalent fields. The implementation
must perform an explicit typed size preflight. It must not relabel arbitrary Pydantic
`ValidationError` as a size error.

The exact safe cause is an additive public-error allowlist entry. The current ten-tool
consumer expectation must include it; the v0.1.4 eight-tool/safe-cause fixture remains
immutable release evidence.

## Exact-Inventory Consumer Migration

The current standalone consumer compares the entire discovered tool schema mapping for
equality. Two additive tools therefore require an explicit migration:

1. preserve the existing v0.1.4 eight-tool fixture as immutable release evidence;
2. create a versioned current expectation with exactly ten tools;
3. validate each expected input and output schema exactly;
4. include the additive stable safe cause;
5. do not weaken validation to ignore unknown tools;
6. document that external consumers asserting full `tools/list` equality must update.

Existing tool-call compatibility and full-inventory discovery compatibility are separate
claims.

## Tool Descriptions and Annotations

Descriptions are normative guidance. Every tool description states:

- when to use it;
- when not to use it;
- mutation and network side effects;
- Evidence-only boundary;
- active-Publication authority;
- untrusted content boundary;
- recovery or exact-read path where applicable.

Selection hierarchy:

- `search_library_v2`: default loss-aware Evidence search for new consumers;
- `read_evidence_v1`: exact active Evidence read when an excerpt is incomplete or an
  active Evidence ID is already known;
- `search_library_v1`: compatibility-only strict full-text Search with no completeness
  claim; use v2 for large or loss-aware output;
- `search_library`: legacy compatibility-only Search;
- `ask_library` and `ask_library_v1`: deterministic Search convenience, not generated or
  exhaustive answer authority;
- `ingest_file`: local Publication-changing tool bounded by configured allowed root.

Accurate advisory annotations:

- search/read/list/get/Ask: `readOnlyHint=true`, `openWorldHint=false`;
- `ingest_file`: `readOnlyHint=false`, `idempotentHint=false`,
  `openWorldHint=false`;
- set `destructiveHint=false` for ingest only if a regression proves prior Publications
  are preserved and no existing data is deleted.

Do not set `idempotentHint` on read-only tools merely because repeat reads are safe.
Annotations cannot express active authority or untrusted Evidence and do not replace
descriptions or response fields.

## Security and Trust

- Treat Evidence text, excerpts, and chunks as untrusted data.
- Never execute or follow instructions contained in Evidence.
- Never interpolate Evidence into system or developer instructions.
- Reject malformed and unauthenticated cursors before repository access.
- Owner restart invalidates all prior cursors.
- Do not log Evidence text, cursor payload/key, local database path, or raw private input.
- Do not return storage paths, stack traces, inactive identifiers, or exception details.
- Keep this a local stdio process; add no network or authentication claim.

## Deterministic Test Plan

### Targeted RED/GREEN

1. Two active matches, `limit=1`:
   - RED: current contract exposes no selection completeness;
   - GREEN: v2 returns `more_available` plus a cursor.
2. Evidence above 1,000,000 characters:
   - RED: strict v1 reaches a generic internal failure and has no bounded read;
   - GREEN: v1 returns typed size error, v2 excerpt is bounded, and Read reconstructs
     exact bytes.
3. More than ten eligible CJK matches:
   - RED: current strategy discards after top-10 without an MCP-visible terminal cap;
   - GREEN: page through selected top-10, then return terminal `capped` with
     `retrieval_strategy_cap`.
4. Only match after excerpt byte 2,048:
   - RED: prefix preview misses the match;
   - GREEN: query window contains the term or an explicit prefix fallback reports the
     limitation.

### Strict Schema

- closed success/error round trips for both response families;
- extra/missing/wrong fields fail;
- the native input schema has one required top-level `request` property and no other property;
- inside `request`, only initial or cursor-only continuation branches are accepted;
- a missing envelope is rejected by FastMCP; empty, null-valued, scalar, and mixed envelope
  values reach the typed strict error without repository access;
- `complete`, `more_available`, and `capped` illegal combinations are unrepresentable;
- terminal Read forbids cursor; non-terminal Read requires it;
- byte validators reject multi-byte overflows;
- structured and compatibility text content match locked SDK expectations.

### Selection and Excerpt

- zero, one, and multiple pages;
- no duplicate or skipped result;
- cursor advances only after emitted items;
- CJK eligible counts 9, 10, and 11 with page limits 5 and 10;
- query windows at beginning, middle, and end;
- multiple terms use stable selection order;
- prefix fallback is explicit;
- byte boundaries cover ASCII, CJK, combining marks, and emoji;
- code-point safety and deterministic repeated serialization.

### Read

- exact byte reconstruction;
- no overlap, gap, or split code point;
- positive progress at `max_bytes=4`;
- terminal state and null cursor;
- stable descriptor and hash across chunks;
- initial one-time full hash and non-quadratic continuation;
- uniform unknown/inactive/superseded/cross-Publication failure;
- descriptor, byte-count, and authority drift fail closed;
- final reconstructed SHA-256 equality.

### Cursor and Authority

- malformed, oversized, tampered, wrong-tool token;
- old epoch versus same-epoch bad MAC;
- no repository call for unauthenticated input;
- active Publication switch for any Source;
- retrieval strategy or query-policy revision change;
- owner restart;
- canonical fingerprint row-order independence;
- fingerprint sensitivity for every authority field;
- display-only field exclusion.

### Budget and Errors

- metadata-heavy items, many tiny items, and one large item;
- exact 32,768-byte application boundary;
- mandatory metadata overflow;
- complete SDK result under measured proof ceiling;
- explicit v1 Search and Ask oversized preflight;
- arbitrary validation/corruption never mislabeled as size;
- no stack, path, cursor, or inactive identity leakage;
- every recovery action names a real operation.

### Regression

- existing Python and CLI tests;
- legacy schema snapshot;
- strict-v1 schema tests and bounded calls;
- Ask summary payloads;
- Export tests;
- current ranking and retrieval tests;
- frozen v0.1.4 eight-tool release fixture;
- exact current ten-tool consumer expectation.

## Installed-Wheel Real-stdio Proof

Build one exact wheel, install it into a repository-external environment, clear
`PYTHONPATH` and source-import affordances, and run the standalone consumer through the
installed console entry point and locked official MCP SDK.

The configuration uses absolute paths:

```json
{
  "command": "/ABSOLUTE/PATH/TO/INSTALLED/mke",
  "args": [
    "--db",
    "/ABSOLUTE/PATH/TO/mke.sqlite",
    "mcp",
    "--allowed-root",
    "/ABSOLUTE/PATH/TO/library"
  ]
}
```

The proof runs from an arbitrary repository-external cwd and verifies:

1. initialization and exact ten-tool `tools/list`;
2. exact input/output schemas, descriptions, and annotations;
3. structured and compatibility text content;
4. `more_available`, cursor-only Search continuation, and no duplicate/gap;
5. incomplete query-centered excerpt and read affordance;
6. cursor-only Read continuation and exact chunk reconstruction;
7. final SHA-256 equality and complete provenance;
8. active-set change and owner-restart expiry;
9. same-epoch tamper rejection;
10. legacy/v1 bounded calls and typed oversized failures;
11. raw canonical and complete `CallToolResult` byte measurements;
12. terminal CJK `capped`;
13. no source-checkout import or Git dependency;
14. reconnect after restart;
15. stdout contains only MCP protocol and diagnostics remain on stderr.

The proof receipt records deterministic facts only. It is not telemetry.

## Documentation

`docs/reference/mcp-contract.md` is the canonical complete tool inventory and contract.
README/README_CN and architecture summaries link to it instead of maintaining competing
inventories.

Update:

- canonical MCP contract reference;
- installed-wheel quickstart with absolute executable, database, and allowed root;
- tool chooser and two-dimensional completeness example;
- stable problem/cause/`next_step` recovery table;
- compatibility and exact-inventory migration note;
- architecture data flow if currently documented;
- proof documentation and reproducible commands;
- CHANGELOG under the next unreleased/version heading.

Documentation states:

- tool `v2` is an MKE contract suffix, not MCP protocol/SDK 2.x;
- previews can be incomplete and signal it;
- exact active Evidence is available through `read_evidence_v1`;
- cursors are opaque, process-bound, and active-set-bound;
- `capped` is terminal but not exhaustive;
- Evidence content is untrusted;
- Ask is deterministic Evidence convenience, not generated answer authority;
- Export remains a separate bounded delivery contract.

A safe issue checklist includes versions, public problem code, proof step, and restart
result. It excludes Evidence/query text, cursor, database path, username, local filename,
and private configuration.

## Compatibility Matrix

| Consumer | Contract |
|---|---|
| Python API | unchanged |
| CLI | unchanged |
| Legacy MCP tool caller | existing names, schemas, and valid bounded calls unchanged |
| Strict-v1 MCP caller | existing schemas and successes unchanged; typed oversized error added |
| Ask consumer | summary payload unchanged; description clarifies returned count |
| New MCP consumer | explicit selection loss, bounded continuation, and exact Evidence read |
| Export consumer | unchanged independent bounded contract |
| Exact-inventory consumer | versioned expectation migrates from eight to exactly ten tools |
| Installed-wheel standalone consumer | proves ten-tool surface without source imports |

## Rollback

No database migration is required.

Rollback:

1. unregister the two new tools;
2. remove their strict schemas and application helpers;
3. restore the prior exact current-consumer inventory expectation;
4. revert the additive v1 size cause/mapping if necessary;
5. leave existing data, Publication state, Evidence, Python, CLI, legacy/v1, and Export
   untouched;
6. rerun frozen schema, full test, installed legacy consumer, and release-fixture checks.

## Stop Conditions

Stop this capability when:

1. both targeted contract REDs and the relevance RED are deterministic GREEN;
2. both new response families are strict and public-neutral;
3. every page, cap, and incomplete item is explicit;
4. every incomplete active Evidence item has an exact bounded read path;
5. active-only Run/Publication/Evidence authority is preserved;
6. Python/CLI/legacy/v1/Export call regressions pass;
7. exact-inventory migration passes without weakening unknown-tool detection;
8. installed-wheel real-stdio consumer proof passes;
9. full project tests, lint, type checks, build, and required CI pass;
10. public documentation and non-claims match the implementation.

Do not continue into segmentation, retrieval benchmarking, OCR, remote services, Agent
orchestration, SDK migration, or additional tools after these conditions are satisfied.

## Implementation Gate

This design is implementation-ready only after its actual public spec diff is reviewed.
The next steps are:

1. mechanically land this design as a public spec in an isolated project worktree;
2. review the exact spec diff against the baseline and public-neutral boundary;
3. write and review a file-by-file implementation plan;
4. implement targeted RED tests before production code;
5. complete code, docs, installed proof, full verification, and authority review;
6. obtain separate authorization before push, PR, merge, tag, release, or deployment.

## Non-Claims

Until implementation and proof exist, do not claim:

- the two tools exist;
- v2 prevents all context-window loss;
- selected Search is exhaustive;
- excerpts are semantic summaries;
- Export supports arbitrary oversized Evidence;
- the 128 MiB provisional read ceiling is shipped;
- performance, quality, production readiness, external adoption, or deployment.
