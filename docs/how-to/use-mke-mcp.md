# Use MKE As A Local MCP Server

Use this guide when an Agent needs local tool access to MKE Evidence.

## Start The Server

```bash
uv sync --locked
uv run mke --db .tmp/mke.sqlite mcp --allowed-root .
```

The server uses stdio. Configure the Agent client to run the command above from the repository
root. It can reuse a database created by `mke --db <path> ingest <file>`.

Example client configuration shape:

```json
{
  "mcpServers": {
    "mke": {
      "command": "uv",
      "args": ["run", "mke", "--db", ".tmp/mke.sqlite", "mcp", "--allowed-root", "."]
    }
  }
}
```

## Available Tools

- `list_libraries`: returns the implicit local library.
- `ingest_file`: ingests a supported `.pdf` or `.mp4` under `--allowed-root`.
- `get_run`: returns Run state and append-only Run events.
- `search_library`: searches active Publication Evidence.

CLI names stay human-oriented (`ingest`, `search`, `run get`). MCP tool names are explicit for
Agents (`ingest_file`, `search_library`, `get_run`).

## Example Agent Flow

1. Call `list_libraries`.
2. Call `ingest_file` with `tests/fixtures/pdf/text-layer.pdf`.
3. Call `get_run` with the returned `run_id`.
4. Call `search_library` with `publication active`.
5. Cite returned Evidence locators.

## Boundaries

- `ask_library` is not implemented yet.
- HTTP and workspace UI are not implemented yet.
- Scanned-PDF OCR, arbitrary videos, real speech-model transcription, and external providers are
  outside this MCP slice.
- The server rejects paths outside `--allowed-root`.
