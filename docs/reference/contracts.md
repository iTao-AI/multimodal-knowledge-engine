# Planned Public Contracts

These contracts are approved for implementation but are not implemented yet.

## HTTP

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

```text
mke init
mke serve
mke library create
mke ingest <file>
mke run get <run_id>
mke search
mke ask
mke mcp
mke demo --verify
```

## MCP

```text
list_libraries
ingest_file
get_run
search_library
ask_library
```

HTTP, CLI, MCP, and the workspace must use the same application services and project-owned DTOs.
