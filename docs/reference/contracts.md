# Public Contracts

These contracts are organized around one application service layer and project-owned DTOs. The
current implementation exposes the PDF and short-video CLI path plus a deterministic local product
proof needed to prove active Publication Search and Ask semantics across CLI-equivalent and MCP
contract paths.

## HTTP

Status: planned. HTTP is not part of the current local CLI/MCP proof.

```text
POST /libraries
GET  /libraries
POST /libraries/{library_id}/sources
GET  /runs/{run_id}
POST /search
POST /ask
GET  /evidence/{evidence_id}
GET  /health
```

## CLI

Status:

| Command | Status | Notes |
|---|---|---|
| `mke --db <path> ingest <file>` | implemented in PR 2, extended in PR 4, D1, and D3-B protocol work | PyMuPDF text-layer PDF path and documented short MP4 fixture profile. Persists candidate Evidence, validates a RunManifest, and activates a Source Publication atomically. PDF and eligible transcript success include intake summaries. |
| `mke --db <path> search <query>` | implemented in PR 2, extended in E3-F | Searches active Publication Evidence through the selected owner-startup strategy. |
| `mke --db <path> run get <run_id>` | implemented in PR 3, extended in D1 | Prints Run state, retry lineage, PDF intake summary when present, and append-only Run events. |
| `mke proof run` | implemented in D2 | Runs the deterministic product proof harness across CLI-equivalent application behavior and MCP contract behavior. |
| `mke proof transcript-smoke --fixture <short-mp4> -- <command> {input}` | implemented in D3-A | Proof-only trusted-local smoke for `LocalCommandTranscriptProvider`; not part of normal ingest and not exposed through MCP. |
| `mke proof transcription-run --fixture <short-spoken-mp4>` | implemented in D3-B PR 3 | Runs cache-only real ASR and validates published timestamp Evidence, Search, Ask, and the transcription intake report. |
| `mke demo --verify` | implemented in PR 3, extended in PR 4 | Compatibility-oriented deterministic offline PDF and short-video proof using temporary SQLite workspace and repository fixtures. |
| `mke --db <path> mcp --allowed-root <path>` | implemented in C1 | Runs a local stdio MCP server for Agent-facing ingest, Run inspection, and active Evidence Search. |
| `mke --db <path> ask <question>` | implemented in C2 | Returns deterministic evidence-only Ask output using active Publication Search. |
| `mke transcription prepare --allow-model-download` | implemented in D3-B | Explicit exact-revision acquisition; no database or Run. |
| `mke transcription doctor` | implemented in D3-B | Read-only dependency, profile, language, and cache checks. |
| `mke eval retrieval-chinese --protocol <protocol.json>` | implemented in E3-A | Records the current FTS5 lexical baseline over isolated Chinese development/public-holdout corpora; no quality threshold or runtime promotion. |
| `mke eval retrieval-cjk-lexical --protocol <protocol.json> --candidate cjk-trigram-overlap-v1` | implemented in E3-B | Runs an off-default comparison-only CJK trigram-overlap candidate for compiled-empty queries; no runtime default, HTTP, UI, MCP, embedding, vector, hybrid, RRF, reranker, or query-rewrite change. |
| `mke retrieval doctor --strategy <strategy>` | implemented in E3-F | Read-only SQLite, active Publication, and required base FTS consistency inspection. |
| `mke retrieval rebuild --strategy <strategy>` | implemented in E3-F | Additional CJK projection no-op for active scan; base FTS rebuild returns stable not-supported. |
| `mke init` | planned | Workspace initialization after lifecycle proof. |
| `mke serve` | planned | Single-owner local process after CLI proof. |
| `mke library create` | planned | May be implicit in first CLI path. |

The PDF CLI uses a local SQLite database path supplied with `--db`. It does not expose a general
FTS query language: Search tokenizes user input into escaped terms before querying FTS5. The
`numeric-grouping-v1` preserves compact numeric tokens and adds a tokenizer-adjacent right-grouped
alternative for eligible standalone ASCII integers. E3-F adds the allowlisted
`--retrieval-strategy` owner-startup selector. `cjk-active-scan-overlap-v1` compiles once with the
numeric policy, keeps compiled non-empty queries on active FTS5, and scans active Evidence only
for eligible compiled-empty CJK queries. It is the default when the selector is omitted.
`numeric-grouping-v1` is the primary rollback and
`current` the lower-level rollback. Strategy changes require no migration or index rebuild. The
active strategy requires the existing `active_evidence_fts` projection for compiled non-empty
queries but adds no CJK projection. Doctor compares that base projection exactly with active
Publication Evidence before reporting ready. The
built-in PDF extractor uses PyMuPDF behind the adapter boundary and extracts text-layer page text
with `page.get_text("text", sort=True)`. Successful PDF ingest and Run inspection expose
`PdfIntakeReport` summary fields: total pages, extracted pages, empty pages, extracted characters,
page character counts, suspected scanned pages, extraction mode, and failure reason when present.
The default video transcript adapter supports the documented short MP4 fixture profile with a
local `mke.video_transcript.v1` sidecar. D3-A adds a project-owned `TranscriptProvider` port and an
optional trusted-local `LocalCommandTranscriptProvider` that reads the same transcript JSON shape
from stdout, but normal ingest does not accept provider commands. The shared schema returns a
provider-neutral `ParsedVideoTranscript(media, segments, transcription_provenance | None)`.
Existing sidecars without `transcription` provenance remain compatible. First-party output must
provide complete faster-whisper provenance. D3-B adds explicit preparation, cache-only doctor and
ingest, and shared CLI/MCP runtime composition. OCR, scanned PDFs, bundled model weights, long
videos, page coordinates, tables, layout-aware chunking, hybrid
retrieval, rerank, and Unicode-aware retrieval are non-goals.

Video application preflight rejects missing, empty, non-MP4, and inputs larger than 100 MiB before
hashing, provider execution, or Run creation. Parsed output is limited to 15 minutes and 10,000
segments. Timestamp locators use integer milliseconds and each segment must end within the declared
media duration.

Recognized real-provider Manifests use the exact fingerprint grammar:

```text
faster-whisper-v1:<64 lowercase hexadecimal characters>
```

The digest covers canonical provider, model, model revision, library version, the actual device
and compute type resolved by CTranslate2, and requested language identity. Prefix-only, uppercase,
short, or version-mismatched values are rejected.

A successful real-provider activation exposes `TranscriptIntakeReport` fields through CLI ingest,
CLI `run get`, MCP `ingest_file`, and MCP `get_run`:

```text
provider
model
model_revision
library_version
device
compute_type
language
detected_language
media_duration_ms
transcription_duration_ms
segment_count
model_source
```

The MCP key is exactly `transcript_intake_report`. These fields contain no path, argv, stderr, or
cache location. The report, Publication, active FTS5 rows, Source active pointer, `published` Run
state, and publication event become visible atomically. A recognized faster-whisper Publication
cannot activate without a successful report; failed, rolled-back, or superseded Runs expose none.

CLI errors use a field-based contract:

```text
problem=<stable_problem_code> cause=<human_readable_cause> active_publication_impact=<impact> next_step=<operator_action>
```

For PDF ingest failures the current stable problem code is `pdf_ingest_failed`. For video ingest
failures the current stable problem code is `video_ingest_failed`. In both cases the active
Publication impact is `unchanged`.

CLI and MCP use the same typed `PublicError` payload with `ok=false`, `problem`, `cause`,
`active_publication_impact`, `next_step`, and optional `run_id`. Only exact stable causes are
allowlisted. Unknown exception text is replaced with
`operation failed; details were redacted`; public errors never expose paths, argv, stderr, cache
locations, endpoints, credentials, secrets, or stack traces.

First-party adapter exit mappings retain the complete project-owned
`problem`/`cause`/`next_step` triple through provider, application, CLI, and MCP boundaries.
Owner configuration failures occur before ingest and are reported as CLI usage errors. Explicit
language support is checked cache-only before CLI faster-whisper ingest creates a Run.

The real transcription proof report contains `status`, `run_state`, `evidence_count`,
`timestamp_evidence`, `search_keyword_matched`, `ask_status`, `transcript_intake_report`,
`environment`, `duration_ms`, and an optional stable `reason`. Its environment fields are limited
to public-safe platform and dependency versions. The proof never emits local paths, cache
locations, host identity, argv, secrets, or a complete transcript.

Ask validation failures use `invalid_question` for empty, overlong, or no-searchable-token
questions and `invalid_query` for invalid limits. Legacy strategies keep CJK-only Ask inputs
invalid. Under `cjk-active-scan-overlap-v1`, eligible compiled-empty CJK inputs can return
`evidence_found` or `insufficient_evidence`; punctuation-only and ineligible inputs remain invalid.
Compiled non-empty mixed or numeric queries are FTS-only, including zero-hit results, so ASCII
constraints are not discarded. E3-F adds no persistent CJK projection, dense/vector search,
hybrid retrieval, RRF, reranking, query rewrite, OCR, or request DTO.

## MCP

Status: partially implemented.

Implemented tools:

```text
list_libraries
ingest_file
get_run
search_library
ask_library
```

`ask_library` returns deterministic Evidence packets, not model-generated answers. Successful
responses include:

```text
ok
ask_id
question
answer_status
summary
evidence
limitations
```

`answer_status` supports `evidence_found` and `insufficient_evidence` in C2. No-match Ask is not
an error: it returns `ok=true`, `answer_status="insufficient_evidence"`, an empty `evidence` list,
and a limitation explaining that no active Evidence matched the search terms.

The MCP server runs over stdio through `mke mcp --allowed-root <path>`. It uses the same typed
runtime composition root as CLI ingest, Run inspection, Search, and Ask. The owner startup command
may select `--retrieval-strategy cjk-active-scan-overlap-v1` or an explicit rollback; MCP requests
cannot select or override retrieval strategy. `ingest_file`
has the stable contract `ingest_file(config, path)`, only accepts files under the configured
allowed root, and currently supports `.pdf` and `.mp4`. MCP requests cannot include transcription
command argv or override retrieval policy, provider, model, cache, endpoint, credential, or
download policy.
MCP rejects PDF inputs larger than 100 MB with `problem="input_file_too_large"` before opening the
PDF extractor. PDF `ingest_file` success and `get_run` responses include `intake_report` when a
Run has one.
When faster-whisper is selected, startup performs cache-only readiness checks before stdio begins.
Cancellation and shutdown terminate registered adapter children and wait for Run cleanup.
`search_library` and `ask_library` read active Publication Evidence only and share the same
Evidence locator payload shape.

HTTP, CLI, MCP, and the workspace must use the same application services and project-owned DTOs.
