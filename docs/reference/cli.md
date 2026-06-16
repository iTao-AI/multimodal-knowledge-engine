# CLI Reference

The CLI is intentionally narrow until the PDF and video lifecycle is proven.

## Primary Proof

```bash
uv sync --locked
uv run mke demo --verify
```

`mke demo --verify` is deterministic and offline. It uses repository PyMuPDF text-layer PDF and
short-video fixtures with a temporary SQLite workspace, then removes the temporary workspace before
exit.

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
mke --db <path> ask <question>
mke --db <path> run get <run_id>
```

- `--db` defaults to `mke.sqlite` in the current working directory.
- The SQLite schema is created automatically when the database is opened.
- `ingest` supports PyMuPDF text-layer PDFs and the documented short MP4 fixture profile.
- Video ingest reads `<video>.mke-transcript.json` sidecars and does not run `ffmpeg`, download
  speech models, or call external services.
- `search` reads only active Publication rows in SQLite FTS5.
- PDF results print `page=<number>`.
- Successful PDF ingest prints stable intake summary fields:
  `pdf_pages`, `extracted_pages`, `empty_pages`, `extracted_chars`, and
  `suspected_scanned_pages`.
- Video results print `timestamp_ms=<start>..<end>` using integer millisecond locators.
- `ask` returns deterministic evidence-only Ask output. It does not call an LLM or generate a
  natural-language answer.
- `run get` prints Run state, retry lineage when present, PDF intake summary when available, and
  append-only Run events.
- To reset a local proof database, remove the selected SQLite file and its `-wal`/`-shm` files.

Successful Ask with Evidence prints:

```text
answer_status=evidence_found evidence_count=1 summary="1 active Evidence item matched the search terms."
page=2 evidence_id=ev_... text=Publication search returns only active page two.
```

Ask with no matching active Evidence is not an error:

```text
answer_status=insufficient_evidence evidence_count=0 summary="No active Evidence matched the search terms."
```

Ask validation failures use the CLI error contract:

```text
problem=invalid_question cause=question must contain at least one searchable ASCII token active_publication_impact=unchanged next_step=provide_searchable_question
```

Successful PDF ingest prints:

```text
run_id=run_... run_state=published evidence_count=2 pdf_pages=2 extracted_pages=2 empty_pages=0 extracted_chars=87 suspected_scanned_pages=0
```

PDF Run inspection includes the same intake summary before Run events:

```text
run_id=run_... state=published source_generation=1
pdf_pages=2 extracted_pages=2 empty_pages=0 extracted_chars=87 suspected_scanned_pages=0
event_index=1 event=run_created
```

## MCP Server Command

```bash
mke --db <path> mcp --allowed-root <path>
```

- Runs a local stdio MCP server.
- `--allowed-root` defaults to the current working directory.
- `ingest_file` rejects paths outside `--allowed-root`.
- Implemented MCP tools are `list_libraries`, `ingest_file`, `get_run`, `search_library`, and
  `ask_library`.
- HTTP and workspace UI remain planned.

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

`mke init`, `mke serve`, and `mke library create` remain planned.

Generative Ask, HTTP, workspace UI, OCR, scanned PDFs, long videos, real speech-model
transcription, tables, page coordinates, hosted coordination, and multi-worker runtime behavior
are outside the current CLI scope.
