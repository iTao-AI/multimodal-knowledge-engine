# Use MKE As A Local MCP Server

The deterministic retrieval order maintenance does not change MCP request schemas or active
Publication authority. Owner-selected Search uses revision-2 deterministic tie ordering; stale
cursor revisions fail closed. See the
[deterministic order proof](./run-deterministic-retrieval-order-proof.md) for evaluation-only
authority and non-claims.

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

For bounded v0.1.4 direct audio on Darwin arm64, start the owner with the same prepared
cache and the explicit supervision pair:

```bash
uv run mke --db .tmp/mke.sqlite mcp --allowed-root ./library \
  --transcript-provider faster-whisper \
  --model-cache "$MKE_MODEL_CACHE" \
  --direct-audio-footprint-bytes "$DIRECT_AUDIO_FOOTPRINT_BYTES" \
  --direct-audio-footprint-budget-mode baseline_plus
```

Changing either owner setting requires a controlled server restart. `ingest_file` remains
path-only; a direct-audio request is `{"path":"interview-excerpt.m4a"}` and contains no runtime
control.

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

For an installed wheel, use absolute paths so the owner identity and file authority do not depend
on a repository checkout or working directory:

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

## Choose A Tool

- Prefer `search_library_v2` for loss-aware active Evidence Search. Follow its opaque cursor while
  selection is `more_available`.
- Call `read_evidence_v1` when an excerpt is incomplete or an active Evidence ID is already known.
- Use `search_library_v1` or legacy `search_library` only for compatibility.
- Treat Ask as deterministic Evidence convenience, not generated or exhaustive answer authority.
- Use Compiled Library Export as a separate bounded delivery contract.

The [MCP contract reference](../reference/mcp-contract.md) is the sole complete inventory and
schema authority. The immutable eight-tool release fixture remains historical evidence; exact
inventory consumers must migrate to the current ten-tool expectation.

Continuation calls contain only the opaque token:

```json
{"request":{"cursor":"<opaque-token>"}}
```

Do not decode, log, or edit it. A process restart, active Publication change, or retrieval-policy
change can expire it; follow the reference recovery table and repeat the appropriate initial call.

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
- Scanned-PDF OCR, arbitrary or long media, full-length audio, bundled model weights, and external
  providers are outside this MCP slice. Direct audio is bounded to the v0.1.4 profile.
- MCP `ingest_file(config, path)` cannot accept provider, model, cache, download, endpoint,
  credential, command argv, or retrieval-policy overrides. Provider and retrieval policy are
  owner startup configuration.
- The server rejects paths outside `--allowed-root`.
- The server rejects PDF inputs above 100 MB before opening the PDF extractor.
