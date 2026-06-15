# Public Contracts

These contracts are planned around one application service layer and project-owned DTOs. The
current implementation exposes only the narrow PDF CLI path needed to prove active Publication
Search semantics.

## HTTP

Status: planned after PDF and video lifecycle validation.

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
| `mke --db <path> ingest <file>` | implemented in PR 2 | Text-layer PDF path only. Persists candidate Evidence, validates a RunManifest, and activates a Source Publication atomically. |
| `mke --db <path> search <query>` | implemented in PR 2 | Searches only active Publication rows in the SQLite FTS5 projection. |
| `mke run get <run_id>` | PR 3 target | Used for Run observability. |
| `mke demo --verify` | PR 3 target | Golden local proof path. |
| `mke init` | planned | Workspace initialization after lifecycle proof. |
| `mke serve` | planned | Single-owner local process after CLI proof. |
| `mke library create` | planned | May be implicit in first CLI path. |
| `mke ask` | planned | Deferred until Search Evidence is trustworthy. |
| `mke mcp` | planned | Deferred until PDF and video contracts are stable. |

The PR 2 PDF CLI uses a local SQLite database path supplied with `--db`. It does not expose a
general FTS query language: Search tokenizes user input into escaped terms before querying FTS5.
The built-in PDF extractor supports deterministic text-layer PDFs with uncompressed text showing
operators; OCR, scanned PDFs, page coordinates, tables, and complex layout are non-goals.

## MCP

Status: planned after PDF and video lifecycle validation.

```text
list_libraries
ingest_file
get_run
search_library
ask_library
```

HTTP, CLI, MCP, and the workspace must use the same application services and project-owned DTOs.
