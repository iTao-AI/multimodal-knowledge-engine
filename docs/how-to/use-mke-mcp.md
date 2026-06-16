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
- `ask_library`: returns deterministic cited Evidence or an insufficient-Evidence state.

CLI names stay human-oriented (`ingest`, `search`, `run get`). MCP tool names are explicit for
Agents (`ingest_file`, `search_library`, `ask_library`, `get_run`).

## Example Agent Flow

1. Call `list_libraries`.
2. Call `ingest_file` with `tests/fixtures/pdf/text-layer.pdf`.
3. Call `get_run` with the returned `run_id`.
4. Call `search_library` with `publication active`.
5. Call `ask_library` with:

```json
{
  "question": "What does the document say about Publication failures?",
  "limit": 5
}
```

6. Cite returned Evidence locators.

`ask_library` does not produce model-generated answers. It returns an Evidence packet with
`answer_status="evidence_found"` or `answer_status="insufficient_evidence"`, plus cited page or
timestamp Evidence when active Search matches the question terms.

## Boundaries

- HTTP and workspace UI are not implemented yet.
- Generative Ask, model providers, prompt templates, and model retries are not implemented yet.
- Scanned-PDF OCR, arbitrary videos, real speech-model transcription, and external providers are
  outside this MCP slice.
- The server rejects paths outside `--allowed-root`.
