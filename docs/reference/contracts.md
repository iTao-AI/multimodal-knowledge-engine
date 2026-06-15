# Public Contracts

These contracts are planned around one application service layer and project-owned DTOs. The
first implementation only exposes the narrow PDF CLI path needed to prove trustworthy Search and
Publication semantics.

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
| `mke ingest <file>` | PR 2 target | Text-layer PDF path first. |
| `mke search` | PR 2 target | Searches active Publications only. |
| `mke run get <run_id>` | PR 3 target | Used for Run observability. |
| `mke demo --verify` | PR 3 target | Golden local proof path. |
| `mke init` | planned | Workspace initialization after lifecycle proof. |
| `mke serve` | planned | Single-owner local process after CLI proof. |
| `mke library create` | planned | May be implicit in first CLI path. |
| `mke ask` | planned | Deferred until Search Evidence is trustworthy. |
| `mke mcp` | planned | Deferred until PDF and video contracts are stable. |

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
