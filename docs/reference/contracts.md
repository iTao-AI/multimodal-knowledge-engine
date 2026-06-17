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
| `mke --db <path> ingest <file>` | implemented in PR 2, extended in PR 4 and D1 | PyMuPDF text-layer PDF path and documented short MP4 fixture profile. Persists candidate Evidence, validates a RunManifest, and activates a Source Publication atomically. PDF success includes an intake summary. |
| `mke --db <path> search <query>` | implemented in PR 2 | Searches only active Publication rows in the SQLite FTS5 projection. |
| `mke --db <path> run get <run_id>` | implemented in PR 3, extended in D1 | Prints Run state, retry lineage, PDF intake summary when present, and append-only Run events. |
| `mke proof run` | implemented in D2 | Runs the deterministic product proof harness across CLI-equivalent application behavior and MCP contract behavior. |
| `mke proof transcript-smoke --fixture <short-mp4> -- <command> {input}` | implemented in D3-A | Proof-only trusted-local smoke for `LocalCommandTranscriptProvider`; not part of normal ingest and not exposed through MCP. |
| `mke demo --verify` | implemented in PR 3, extended in PR 4 | Compatibility-oriented deterministic offline PDF and short-video proof using temporary SQLite workspace and repository fixtures. |
| `mke --db <path> mcp --allowed-root <path>` | implemented in C1 | Runs a local stdio MCP server for Agent-facing ingest, Run inspection, and active Evidence Search. |
| `mke --db <path> ask <question>` | implemented in C2 | Returns deterministic evidence-only Ask output using active Publication Search. |
| `mke init` | planned | Workspace initialization after lifecycle proof. |
| `mke serve` | planned | Single-owner local process after CLI proof. |
| `mke library create` | planned | May be implicit in first CLI path. |

The PDF CLI uses a local SQLite database path supplied with `--db`. It does not expose a general
FTS query language: Search tokenizes user input into escaped terms before querying FTS5. The
built-in PDF extractor uses PyMuPDF behind the adapter boundary and extracts text-layer page text
with `page.get_text("text", sort=True)`. Successful PDF ingest and Run inspection expose
`PdfIntakeReport` summary fields: total pages, extracted pages, empty pages, extracted characters,
page character counts, suspected scanned pages, extraction mode, and failure reason when present.
The default video transcript adapter supports the documented short MP4 fixture profile with a
local `mke.video_transcript.v1` sidecar. D3-A adds a project-owned `TranscriptProvider` port and an
optional trusted-local `LocalCommandTranscriptProvider` that reads the same transcript JSON shape
from stdout, but normal ingest does not accept provider commands. OCR, scanned PDFs, bundled
speech-model transcription, long videos, page coordinates, tables, layout-aware chunking, hybrid
retrieval, rerank, and Unicode-aware retrieval are non-goals.

CLI errors use a field-based contract:

```text
problem=<stable_problem_code> cause=<human_readable_cause> active_publication_impact=<impact> next_step=<operator_action>
```

For PDF ingest failures the current stable problem code is `pdf_ingest_failed`. For video ingest
failures the current stable problem code is `video_ingest_failed`. In both cases the active
Publication impact is `unchanged`.

Ask validation failures use `invalid_question` for empty, overlong, or no-searchable-token
questions and `invalid_query` for invalid limits. CJK-only and punctuation-only Ask inputs return
`invalid_question` in C2 because the current retrieval path only exposes searchable ASCII tokens.

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

The MCP server runs over stdio through `mke mcp --allowed-root <path>`. It reuses the same
`KnowledgeEngine` application service as CLI ingest, Run inspection, and Search. `ingest_file`
has the stable contract `ingest_file(config, path)`, only accepts files under the configured
allowed root, and currently supports `.pdf` and `.mp4`. MCP requests cannot include transcription
command argv or override the process-local transcript provider.
MCP rejects PDF inputs larger than 100 MB with `problem="input_file_too_large"` before opening the
PDF extractor. PDF `ingest_file` success and `get_run` responses include `intake_report` when a
Run has one.
`search_library` and `ask_library` read active Publication Evidence only and share the same
Evidence locator payload shape.

HTTP, CLI, MCP, and the workspace must use the same application services and project-owned DTOs.
