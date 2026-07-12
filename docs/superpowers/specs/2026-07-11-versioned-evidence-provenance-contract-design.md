# Versioned Evidence Provenance Contract Design

Status: implemented and merged by PR #63 at
`0ccc82874e2a4a01e01badcf959ba5a5e0dcbc13`; post-merge checks passed and the
authoritative targeted re-review closed as `CLEAN / 0 findings`.

Planning base: `main@793788f2d74a1ec072fe205e89acd13ab595bad7`.

## Goal

Give a generic Agent consumer one narrow, versioned, read-only contract for observing an MKE
Library and consuming active-Publication Evidence through the existing stdio MCP tools.

The contract must let a consumer connect one returned Evidence item to:

- the Evidence identity;
- the Source identity;
- a portable fingerprint of the ingested source bytes;
- the active Publication identity and revision;
- the Run that produced the Publication;
- a page or timestamp locator;
- the Evidence text.

Search and Ask must expose the same strict Evidence projection. A consumer must also be able to
distinguish an empty Library, a Library with Sources but no active Publication, and an active
Library whose query produced no match.

## Existing Authority And Constraints

MKE already owns the required facts in SQLite:

```text
assets.sha256
    -> sources.source_id
    -> runs.run_id
    -> run_manifests.asset_sha256
    -> publications.publication_id + revision
    -> evidence.evidence_id + locator + text
```

Search already filters through `sources.active_publication_id`; Ask delegates to Search and refuses
when no active Evidence matches. The change must reuse those authorities and must not add a second
catalog, projection, persistence schema, or orchestration layer.

## Approaches Considered

### A. Add parallel v1 read-only MCP tools with a shared strict projection

`list_libraries_v1`, `search_library_v1`, and `ask_library_v1` are added beside the existing tools.
Their outputs are versioned strict envelopes. Search and Ask map one MCP-only provenance enrichment
of the unchanged domain `SearchResult` into the same `mke.evidence_ref.v1` model. A single SQLite
read snapshot returns the active-Publication observation and search results.

This is the selected approach. It exposes every required fact without an extra round trip or
consumer-owned join while preserving existing tool outputs for current consumers.

### B. Replace the existing read-only tool outputs in place

Literal response versions would reveal the break but would not provide negotiation or fallback.
Existing consumers would fail immediately. Rejected in favor of parallel v1 tools.

### C. Add separate observation and Evidence-detail round trips

This would preserve current read responses, but it would require Agents to perform extra calls and
could observe a different active Publication between calls. It also duplicates facts that the
Search query can already bulk-enrich. Rejected.

### D. Keep MCP unchanged and let each consumer infer provenance

The current payload does not expose Run, Publication revision, or portable content identity, so a
consumer cannot reconstruct the contract without reading SQLite internals. Rejected because it
breaks the application boundary and cannot fail closed.

## Selected Architecture

```text
Agent / Tool Client
        |
        | list_libraries_v1 / search_library_v1 / ask_library_v1
        v
strict versioned MCP response models
        |
        v
MKE application snapshot methods
        |
        | one SQLite read transaction
        v
active Publication observation + unchanged existing retrieval path
        |
        +--> SearchResult[] from active_evidence_fts or bounded CJK active scan
        |
        +--> one bulk publications/runs/run_manifests provenance lookup
        v
mke.evidence_ref.v1
```

The existing CLI `Search` presentation, `KnowledgeEngine.search()`, retrieval strategy selection,
evaluation behavior, `SearchResult`, and existing MCP tools remain unchanged. New snapshot methods
are used by the v1 MCP surface so the observation and returned Evidence refer to the same SQLite
snapshot. The enrichment lookup is one bounded query over the returned Evidence IDs, never one
query per result.

## Evidence Projection

Both `search_library_v1.results[]` and `ask_library_v1.evidence[]` use this exact shape:

```json
{
  "schema_version": "mke.evidence_ref.v1",
  "evidence_id": "ev_<opaque-id>",
  "source_id": "src_<opaque-id>",
  "content_fingerprint": "sha256:<64-lowercase-hex>",
  "publication_id": "pub_<opaque-id>",
  "publication_revision": 2,
  "run_id": "run_<opaque-id>",
  "locator": {
    "kind": "page",
    "start": 1,
    "end": 1
  },
  "text": "bounded Evidence text"
}
```

`content_fingerprint` identifies the original ingested source asset bytes, not the Evidence text,
an extractor output, a filesystem path, or a database row. It is sourced from the validated Run
manifest and is stable when identical bytes are ingested into another MKE store.

Locator validation is discriminated by `kind`:

- `page`: positive integer page number with `start == end`;
- `timestamp_ms`: integer milliseconds with `start >= 0` and `end > start`.

All identifiers remain opaque. The contract does not promise that Source, Run, Publication, or
Evidence IDs are stable across independent stores.

## Active-Publication Observation

Each v1 read-only success response carries one strict observation:

```json
{
  "schema_version": "mke.active_publication_observation.v1",
  "library_id": "local",
  "state": "active",
  "source_count": 2,
  "active_publication_count": 2,
  "active_evidence_count": 2
}
```

Allowed states are derived from authoritative counts:

| State | Required invariant | Consumer interpretation |
|---|---|---|
| `empty` | all counts are zero | Nothing has been ingested. |
| `no_active_publication` | `source_count > 0`, active counts are zero | Sources or Runs exist, but none is published. |
| `active` | active Publication and Evidence counts are positive | Empty Search results mean a normal no-match. |

An active Publication with zero active Evidence is an integrity violation and fails closed instead
of being represented as a fourth state.

The same integrity gate requires the implicit `local` Library, matching Source/Publication/Run/
Evidence identities, `runs.state="published"`, Publication revision equal to the Source active
revision, Run-manifest Evidence count equal to the active Evidence count, and Run-manifest SHA-256
equal to the Source asset SHA-256. A valid-looking but mismatched graph is never returned as trusted
provenance.

`list_libraries_v1` reports the current observation. The v1 Search and Ask paths compute the
observation, unchanged retrieval result, and bulk provenance enrichment in the same PEP 249 SQLite
transaction already provided by `autocommit=False`; they do not issue a nested `BEGIN`. A concurrent
Publication activation therefore cannot mix two states in one response.

## Versioned MCP Response Envelopes

The contract adds three parallel read-only tools:

- `mke.list_libraries_response.v1`;
- `mke.search_library_response.v1`;
- `mke.ask_library_response.v1`.

Each output schema is a top-level `oneOf` discriminated by literal `ok: true | false`. Every object
uses `additionalProperties: false`; every required field is present; every `schema_version` is a
literal constant. The successful Search and Ask branches reference the same
`mke.evidence_ref.v1` definition.

Project-owned Pydantic v2 models generate and validate these schemas. Pydantic is already an MCP
runtime dependency; because MKE will import it directly, it becomes an explicit bounded core
dependency without adding a new installed package family.

The error branch preserves the existing public error vocabulary:

```json
{
  "schema_version": "mke.search_library_response.v1",
  "ok": false,
  "problem": "internal_error",
  "cause": "operation failed; details were redacted",
  "active_publication_impact": "unchanged",
  "next_step": "check_server_logs"
}
```

Unexpected exceptions are converted to the response-specific error model before FastMCP
serialization. Unknown versions, missing required fields, extra fields, invalid identifiers,
invalid locators, invalid count/state combinations, and malformed success/error branches are
rejected by consumer-side validation.

The disclosure boundary covers MKE-owned process/configuration/error data: MKE never injects a
filesystem path, credential, environment value, stderr, traceback, or private database metadata
into the response. `text` is intentionally the selected user-ingested Evidence and is not a secret-
scanning or content-redaction surface; consumers with document-level data-loss-prevention policy
must apply it outside this transport contract.

The existing `list_libraries`, `search_library`, `ask_library`, `ingest_file`, and `get_run` names,
inputs, outputs, and cancellation behavior remain unchanged. Current consumers may migrate to the
parallel v1 read tools explicitly. Strict versioning of write/inspection responses is a separate
compatibility decision and is not part of this read-only provenance slice.

## Consumer Proof

Add a separate real stdio MCP proof rather than changing the existing eight-case product proof or
the v0.1.1 local-knowledge proof output contract. The new proof uses repository-owned fixtures and
the official MCP SDK to verify:

1. the legacy five tool input/output schemas remain unchanged and the three v1 tools are present;
2. a fresh store reports `empty`;
3. a failed ingest leaves a Source but reports `no_active_publication`;
4. a published PDF produces page-addressed `mke.evidence_ref.v1` values;
5. a published sidecar-backed MP4 produces timestamp-addressed values;
6. v1 Search and Ask return byte-for-byte equal projections for the same Evidence;
7. same-store reingest preserves `source_id` and `content_fingerprint` while changing Run,
   Publication, revision, and Evidence identities;
8. fresh-store ingest preserves `content_fingerprint` while opaque identities may differ;
9. an active Library with no matching query is distinguishable from the first two empty states;
10. malformed schema versions, extra fields, invalid locators, and transport/tool failures fail
   closed;
11. rendered proof output contains no path, credential, stderr, traceback, transient identifier,
    or Evidence text.

The report contains only stable aggregate booleans/counts and schema version names.
Every stdio session and tool call is bounded by an explicit timeout, terminates the child process on
cancellation/failure, and removes temporary stores in `finally` cleanup.

## Compatibility And Migration

This is an additive read-output contract. The legacy five tools remain byte-for-byte compatible.
New consumers opt into the v1 tools and strict envelopes. The new installed-wheel consumer proof
requires both the legacy schemas and the additive v1 schemas, preventing either compatibility path
from drifting silently.

No SQLite migration is required. Existing databases already contain every provenance field.

## Artifact Identity Closure

Changes under `src/mke` invalidate retrieval evaluation source identities even though retrieval
semantics are out of scope. Before implementation, record normalized E1 through E3-E reports and
validate all canonical artifacts. After implementation, perform only the repository-supported
identity dependency closure and require normalized observations, metrics, gates, and verdicts to be
identical. Any semantic drift is a stop condition.

Validator-proven source/scope/dependency identity metadata inside canonical artifacts and
protocol-lock JSON may change when required by the existing atomic refresh workflow. Corpus files,
qrels, query definitions, observations, metrics, gates, and verdicts must not change.

## Documentation

Implementation updates:

- ADR-0009 for the public read-only contract and compatibility boundary;
- architecture explanation for the SQLite snapshot and provenance flow;
- MCP reference and stdio how-to with exact v1 examples;
- consumer-proof how-to and docs index;
- existing proof/schema assertions so installed consumers verify strict output schemas.

No version, CHANGELOG, tag, Release, PyPI, deployment, or release-facing presentation work is in
scope.

## Non-Goals

- No consumer-specific study/advisor/workflow fields, URL/title/freshness policy, country, subject,
  document type, or business metadata.
- No HTML crawler, OCR, HTTP, UI, LangChain, LangGraph, or second Agent orchestration layer.
- No dense, hybrid, RRF, reranker, or query-rewrite runtime promotion.
- No new retrieval strategy, ranking behavior, ingestion lifecycle, Publication semantics, or
  SQLite authority.
- No path, credential, environment, stderr, traceback, provider cache, or internal database metadata
  in public output.
- No release or unrelated dependency work.

## Acceptance Criteria

- v1 Search and Ask use one exact strict `mke.evidence_ref.v1` projection.
- Evidence links Source, source-byte fingerprint, Publication revision, Run, locator, and text.
- Observation distinguishes `empty`, `no_active_publication`, and active no-match.
- Read responses are versioned, machine-readable, and `additionalProperties: false` throughout.
- Observation plus results are one SQLite read snapshot with no N+1 query.
- Existing tools, `SearchResult`, active-only retrieval, Ask refusal, page/timestamp locators,
  Run/Publication lifecycle, cancellation, and redacted public errors remain intact.
- Real stdio MCP consumer proof passes for PDF, video, lifecycle identity, empty states, strict schema,
  and redaction.
- E1 through E3-E normalized semantics remain unchanged after identity-only closure.
- Full tests, Ruff, Pyright, build, product proof, demo, local-knowledge proof, new consumer proof,
  canonical validators, document-release audit, and `git diff --check` pass.
