# Use MKE As A Local MCP Server

Use this guide when an Agent needs local tool access to MKE Evidence.

## Start The Server

```bash
uv sync --locked
uv run mke --db .tmp/mke.sqlite mcp --allowed-root .
```

The server uses stdio. Configure the Agent client to run the command above from the repository
root. It can reuse a database created by `mke --db <path> ingest <file>`.

To enable bounded compiled-empty CJK retrieval, select the strategy when the owner starts:

```bash
uv run mke --db .tmp/mke.sqlite \
  --retrieval-strategy cjk-active-scan-overlap-v1 \
  mcp --allowed-root .
```

For rollback, restart the owner process with the same database:

```bash
uv run mke --db .tmp/mke.sqlite \
  --retrieval-strategy numeric-grouping-v1 \
  mcp --allowed-root .
```

This changes owner routing only. It does not migrate the database or rebuild a CJK projection,
and MCP tool requests cannot override the owner-selected strategy. Search and Ask tool schemas
remain limited to query/question and limit fields.

After explicit model preparation, start cache-only local transcription with:

```bash
uv run mke --db .tmp/mke.sqlite mcp --allowed-root ./library \
  --transcript-provider faster-whisper
```

Startup runs the same read-only checks as `mke transcription doctor`. See
[Use Local Transcription](./use-local-transcription.md).

To verify the installed wheel rather than the repository environment, use the cache-only deployment
proof:

```bash
HF_HUB_OFFLINE=1 uv run python scripts/transcription_deployment_proof.py \
  --fixture tests/fixtures/video/spoken-evidence.mp4 \
  --model-cache "$MKE_MODEL_CACHE" \
  --python 3.12 \
  --json
```

The proof builds a wheel, installs `mke[transcription]` into an isolated temporary environment, and
uses the MCP Python SDK over stdio. It compares installed CLI and MCP results for ingest, Run
inspection, Search, and evidence-only Ask. It does not prepare or download a model unless the
operator explicitly supplies `--allow-model-download`.

The verified run on Darwin 25.4.0 arm64 with Python 3.12 passed both CLI and MCP flows using
`faster-whisper` 1.2.1 and the exact cached `small` revision
`536b0662742c02347bc0e980a01041f333bce120`. Other platforms remain unverified.

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
- `ingest_file`: ingests a supported `.pdf` or `.mp4` under `--allowed-root`; PDF success includes
  `intake_report`.
- `get_run`: returns Run state, append-only Run events, and PDF `intake_report` when present.
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
- Scanned-PDF OCR, arbitrary or long videos, audio-only ingest, bundled model weights, and external
  providers are outside this MCP slice.
- MCP `ingest_file(config, path)` cannot accept provider, model, cache, download, endpoint,
  credential, command argv, or retrieval-policy overrides. Provider and retrieval policy are
  owner startup configuration.
- The server rejects paths outside `--allowed-root`.
- The server rejects PDF inputs above 100 MB before opening the PDF extractor.
