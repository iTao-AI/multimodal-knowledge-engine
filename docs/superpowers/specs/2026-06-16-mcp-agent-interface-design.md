# MCP Agent Interface Design

## Goal

Expose the current trustworthy Evidence lifecycle to local Agents through a deterministic MCP
stdio server without adding HTTP, workspace UI, hosted coordination, model inference, or Ask
generation.

This is C1 of the interface work:

```text
existing KnowledgeEngine
-> mke mcp --db <path> --allowed-root <path>
-> MCP tools for ingest, run inspection, and active-only Search
-> Agent can cite page or timestamp Evidence
```

## Current State

- `KnowledgeEngine` already owns PDF ingest, short-video ingest, Run lookup, Run events, and
  active-only Search.
- `mke --db <path> ingest <file>`, `search`, `run get`, and `demo --verify` are implemented.
- `docs/reference/contracts.md` lists MCP as planned with:
  `list_libraries`, `ingest_file`, `get_run`, `search_library`, and `ask_library`.
- Ask, HTTP, workspace UI, scanned-PDF OCR, arbitrary video processing, real speech-model
  transcription, and hosted coordination remain outside the current proof.

## Decision

Implement MCP before HTTP and Ask.

Reasons:

- MCP is the narrowest Agent-facing interface for Codex/OpenClaw-style local tool use.
- It can reuse `KnowledgeEngine` directly and avoid a new service process, API server, auth layer,
  OpenAPI snapshot, or browser UI.
- It exposes already-proven Evidence behavior instead of inventing answer generation before
  Search and citation contracts are stable.

Do not implement `ask_library` in C1. The MCP server may list only implemented tools. The contract
documentation must mark `ask_library` as planned until C2 defines evidence-only Ask semantics.

## Dependency Strategy

Use the official MCP Python SDK package as a runtime dependency:

```text
mcp>=1.12.4,<2
```

The MCP command is first-class once implemented, so relying on an optional extra would make the
default `mke mcp` path confusing. The implementation must import MCP server APIs only from the
MCP interface module, so non-MCP application code remains independent of the SDK.

The server uses `FastMCP` and stdio transport. Current SDK documentation shows `FastMCP` tools via
`@mcp.tool()` and `.run()` using stdio by default.

## CLI Contract

Add:

```bash
mke --db <path> mcp --allowed-root <path>
```

- `--db` keeps the existing global CLI option and selects the SQLite domain database.
- `--allowed-root` defaults to the current working directory.
- The MCP server runs over stdio and does not print human-oriented startup logs to stdout.
- Tool calls open and close `KnowledgeEngine` per operation unless a future ADR approves a
  long-lived shared connection.

## Path Safety

`ingest_file` accepts a file path, but that path is not an arbitrary public output path.

Rules:

- Resolve `--allowed-root` and the requested file path with `Path.resolve()`.
- Reject files outside `allowed_root`.
- Reject missing files.
- Reject directories.
- Support only current ingest suffixes:
  - `.pdf`
  - `.mp4`
- Return a stable field-based error payload instead of leaking stack traces.

This keeps local Agent access explicit and prevents a prompt-injected tool call from reading
unrelated files on the host.

## MCP Tools

### `list_libraries`

Returns the implicit local library.

```json
{
  "libraries": [
    {
      "library_id": "local",
      "name": "Local Library",
      "status": "implicit",
      "active_publication_scope": "source"
    }
  ]
}
```

MKE does not yet expose multiple named Libraries. The tool exists to preserve the public contract
shape and give Agents a stable discovery step.

### `ingest_file`

Input:

```json
{
  "path": "tests/fixtures/pdf/text-layer.pdf"
}
```

Success output:

```json
{
  "ok": true,
  "run_id": "run_...",
  "run_state": "published",
  "evidence_count": 2,
  "media_type": "application/pdf",
  "active_publication_impact": "changed"
}
```

Failure output:

```json
{
  "ok": false,
  "problem": "pdf_ingest_failed",
  "cause": "human-readable cause",
  "active_publication_impact": "unchanged",
  "next_step": "fix_input_or_retry"
}
```

Video failures use `problem=video_ingest_failed`. Path validation failures use
`problem=input_path_rejected` and `active_publication_impact=unchanged`.

### `get_run`

Input:

```json
{
  "run_id": "run_..."
}
```

Success output:

```json
{
  "ok": true,
  "run": {
    "run_id": "run_...",
    "state": "published",
    "source_generation": 1,
    "retry_of_run_id": null
  },
  "events": [
    {"event_index": 1, "event": "run_created"},
    {"event_index": 2, "event": "run_started"},
    {"event_index": 3, "event": "candidate_validated"},
    {"event_index": 4, "event": "publication_activated"}
  ]
}
```

Unknown Run output:

```json
{
  "ok": false,
  "problem": "run_not_found",
  "cause": "unknown run: run_...",
  "active_publication_impact": "unchanged",
  "next_step": "check_run_id"
}
```

### `search_library`

Input:

```json
{
  "query": "timestamp proof",
  "limit": 5
}
```

Rules:

- Search always reads active Publication rows only.
- `limit` defaults to 5.
- `limit` must be between 1 and 20.
- Empty or whitespace-only queries are rejected with `problem=invalid_query`.

Success output:

```json
{
  "ok": true,
  "query": "timestamp proof",
  "results": [
    {
      "evidence_id": "ev_...",
      "publication_id": "pub_...",
      "source_id": "src_...",
      "locator": {
        "kind": "timestamp_ms",
        "start": 0,
        "end": 1200
      },
      "text": "timestamp proof ..."
    }
  ]
}
```

For PDF Evidence, `locator.kind` is `page`, and `start` / `end` are page numbers.

## Error Contract

All MCP tools return structured payloads. They do not raise raw exceptions to the Agent for known
operator errors.

Stable failure fields:

```json
{
  "ok": false,
  "problem": "stable_problem_code",
  "cause": "human-readable cause",
  "active_publication_impact": "unchanged",
  "next_step": "operator_action"
}
```

Known C1 problem codes:

- `input_path_rejected`
- `unsupported_media_type`
- `pdf_ingest_failed`
- `video_ingest_failed`
- `run_not_found`
- `invalid_query`
- `mcp_tool_failed`

Unexpected internal errors may return `mcp_tool_failed`, but responses must not include absolute
host paths, stack traces, secrets, environment variables, or provider configuration.

## Testing Requirements

The implementation must include tests for:

- `list_libraries` returns the implicit local library shape.
- `ingest_file` publishes PDF Evidence via `KnowledgeEngine`.
- `ingest_file` publishes video timestamp Evidence via `KnowledgeEngine`.
- `ingest_file` rejects paths outside `--allowed-root`.
- `ingest_file` rejects unsupported suffixes without changing active Search.
- `get_run` returns Run state plus events.
- `search_library` returns page and timestamp locators.
- `search_library` rejects empty queries and invalid limits.
- `mke mcp` wires `--db` and `--allowed-root` into the MCP server without starting the server in
  CLI parser tests.

Full end-to-end stdio MCP client tests may be deferred if the pure tool-contract layer is covered
and CI still runs the wheel-installed `mke demo --verify`.

## Documentation Requirements

Update in the same PR:

- `docs/reference/contracts.md`: MCP status becomes partially implemented; `ask_library` remains
  planned.
- `docs/reference/cli.md`: `mke mcp` becomes implemented with stdio and path-safety notes.
- `docs/how-to/use-mke-mcp.md`: show local configuration and a minimal Agent workflow.
- `docs/README.md`: link the MCP how-to.
- README files: mention MCP as the first Agent-facing interface only if implemented.

## Explicit Non-Goals

- `ask_library`.
- HTTP server.
- OpenAPI contract.
- Workspace UI.
- Authentication or multi-user authorization.
- Hosted or multi-worker runtime.
- External model calls.
- OCR, arbitrary video processing, real speech-model transcription, or embedding search.
- Long-lived shared SQLite connection across tool calls.

## Acceptance

C1 is accepted when:

1. `mke mcp --allowed-root <path>` starts a stdio MCP server.
2. MCP tools can ingest repository PDF and video fixtures, inspect Runs, and search active
   Evidence.
3. Path safety prevents ingestion outside the configured allowed root.
4. `ask_library` remains explicitly planned, not silently implemented.
5. The following commands pass:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke demo --verify
```
