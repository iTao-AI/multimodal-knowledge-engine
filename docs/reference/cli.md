# CLI Reference

The CLI is intentionally narrow until the PDF and video lifecycle is proven.

## Primary Proof

```bash
uv sync --locked
uv run mke demo --verify
```

`mke demo --verify` is deterministic and offline. It uses repository PDF and short-video fixtures
with a temporary SQLite workspace, then removes the temporary workspace before exit.

Expected stdout shape:

```text
mke demo --verify
phase=ingest_initial status=ok run_id=<run_id> evidence_count=2
phase=failed_reprocess status=ok active_publication_impact=unchanged
phase=retry_publish status=ok run_id=<run_id>
phase=ingest_video status=ok run_id=<run_id> video_evidence_count=2
phase=cleanup status=ok
result=passed duration_ms=<milliseconds>
```

Exit codes:

| Code | Meaning |
|---|---|
| `0` | Proof passed. |
| `1` | Proof failed and printed the CLI error contract. |

Expected duration: a few seconds on a local development machine.

## Ingest And Search Commands

```bash
mke --db <path> ingest <file>
mke --db <path> search <query>
mke --db <path> run get <run_id>
```

- `--db` defaults to `mke.sqlite` in the current working directory.
- The SQLite schema is created automatically when the database is opened.
- `ingest` supports deterministic text-layer PDFs and the documented short MP4 fixture profile.
- Video ingest reads `<video>.mke-transcript.json` sidecars and does not run `ffmpeg`, download
  speech models, or call external services.
- `search` reads only active Publication rows in SQLite FTS5.
- PDF results print `page=<number>`.
- Video results print `timestamp_ms=<start>..<end>` using integer millisecond locators.
- `run get` prints Run state, retry lineage when present, and append-only Run events.
- To reset a local proof database, remove the selected SQLite file and its `-wal`/`-shm` files.

## MCP Server Command

```bash
mke --db <path> mcp --allowed-root <path>
```

- Runs a local stdio MCP server.
- `--allowed-root` defaults to the current working directory.
- `ingest_file` rejects paths outside `--allowed-root`.
- Implemented MCP tools are `list_libraries`, `ingest_file`, `get_run`, and `search_library`.
- `ask_library`, HTTP, and workspace UI remain planned.

`mke mcp --help` prints the command-specific options. Databases created by `mke ingest` can be
reused with `mke mcp --db <path>`.

## Error Contract

CLI failures use stable fields:

```text
problem=<stable_problem_code> cause=<human_readable_cause> active_publication_impact=<impact> next_step=<operator_action>
```

Current PDF failures use:

```text
problem=pdf_ingest_failed
active_publication_impact=unchanged
next_step=fix_input_or_retry
```

Current video failures use:

```text
problem=video_ingest_failed
active_publication_impact=unchanged
next_step=fix_input_or_retry
```

## Planned Commands

`mke init`, `mke serve`, `mke library create`, and `mke ask` remain planned.

Ask, HTTP, workspace UI, OCR, scanned PDFs, long videos, real speech-model transcription,
tables, page coordinates, hosted coordination, and multi-worker runtime behavior are outside the
current CLI scope.
