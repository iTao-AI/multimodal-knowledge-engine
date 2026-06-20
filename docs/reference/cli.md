# CLI Reference

The CLI is intentionally narrow until the PDF and video lifecycle is proven.

## Primary Proof

```bash
uv sync --locked
uv run mke proof run
uv run mke proof run --json
```

`mke proof run` is deterministic and offline. It uses repository PyMuPDF text-layer PDF and
short-video fixtures with a temporary SQLite workspace, executes CLI-equivalent application cases
and MCP contract cases, then removes the temporary workspace before exit. `--json` emits a
machine-readable report with public-safe scalar observed fields and no absolute local paths.

Expected human stdout shape:

```text
mke proof run
proof=product status=passed cases=8 passed=8 failed=0 duration_ms=<milliseconds>
case=cli_pdf_ingest status=passed evidence_count=2 intake_report=present
case=cli_pdf_search status=passed locator=page
case=cli_failed_reprocess status=passed active_publication_impact=unchanged
case=cli_video_ingest_search status=passed locator=timestamp_ms
case=cli_ask status=passed answer_status=evidence_found
case=mcp_ingest_file status=passed intake_report=present
case=mcp_get_run status=passed run_state=published
case=mcp_search_and_ask status=passed locator=page answer_status=evidence_found
```

`mke demo --verify` remains available as a compatibility proof with phase-oriented stdout:

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
| `1` | At least one proof case failed. |

Expected duration: a few seconds on a local development machine.

## Real Transcription Proof

```bash
mke proof transcription-run \
  --fixture <short-spoken-mp4> \
  [trusted faster-whisper runtime flags] \
  [--json]
```

This opt-in proof uses the first-party faster-whisper runtime against an already prepared exact
model revision. It never calls preparation or enables model download. Success requires a published
Run, non-empty ordered timestamp Evidence, a keyword Search match, evidence-only Ask, and a
complete `transcript_intake_report`.

JSON output contains one object with:

```text
status
run_state
evidence_count
timestamp_evidence
search_keyword_matched
ask_status
transcript_intake_report
environment
duration_ms
reason
```

`environment` is limited to Python, OS, architecture, faster-whisper, CTranslate2, and PyAV
versions. Reports do not expose paths, hostnames, usernames, cache locations, argv, endpoints,
secrets, or the full transcript. Exit codes are `0` passed, `1` failed, and `2` invalid usage.

## Proof-Only Transcript Smoke

```bash
mke proof transcript-smoke --fixture <short-mp4> -- <transcriber-command> {input}
```

`transcript-smoke` is a local operator smoke command for the optional
`LocalCommandTranscriptProvider`. It is not the normal ingest contract and is not exposed through
MCP. The command argv must be supplied as separate arguments, must include exactly one `{input}`
placeholder, and is executed with `shell=False`. The provider expects stdout to contain the shared
`mke.video_transcript.v1` JSON object.

Expected success stdout shape:

```text
mke proof transcript-smoke
proof=transcript_smoke status=passed provider=local_command evidence_count=<n>
```

Failures use the video ingest error contract and do not expose argv, provider stderr, absolute
paths, stack traces, secrets, or temporary directory names.

## Ingest And Search Commands

```bash
mke --db <path> ingest <file>
mke --db <path> search <query>
mke --db <path> ask <question>
mke --db <path> run get <run_id>
```

`ingest` and `run get` accept `--json` and emit exactly one JSON object.

- `--db` defaults to `mke.sqlite` in the current working directory.
- The SQLite schema is created automatically when the database is opened.
- `ingest` supports PyMuPDF text-layer PDFs and the documented short MP4 fixture profile.
- Video ingest defaults to `<video>.mke-transcript.json`. Selecting
  `--transcript-provider faster-whisper` uses the cache-only first-party adapter. It does not run a
  system `ffmpeg`, download during ingest, or accept command argv.
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
run_id=run_... run_state=published evidence_count=2 pdf_pages=2 extracted_pages=2 empty_pages=0 extracted_chars=<chars> suspected_scanned_pages=0
```

PDF Run inspection includes the same intake summary before Run events:

```text
run_id=run_... state=published source_generation=1
pdf_pages=2 extracted_pages=2 empty_pages=0 extracted_chars=<chars> suspected_scanned_pages=0
event_index=1 event=run_created
```

## Transcription Setup

```bash
mke transcription prepare --allow-model-download [runtime flags] [--json]
mke transcription doctor [runtime flags] [--json]
```

Runtime flags are `--transcript-provider`, `--model`, `--model-revision`, `--device`,
`--compute-type`, `--language`, `--model-cache`, and `--transcription-timeout-seconds`.
Preparation is the only download path. Doctor returns `0` ready, `1` not ready, and `2` for usage.
Invalid owner configuration is a usage error and never emits a Python traceback. Faster-whisper
video ingest runs the same cache-only readiness checks before opening SQLite or creating a Run;
an unsupported explicit language returns `problem=transcription_not_ready` with
`next_step=choose_supported_language`.

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
next_step=<provider-specific recovery action or fix_input_or_retry>
```

First-party adapter failures preserve stable recovery actions such as
`install_transcription_extra`, `run_transcription_prepare`, and
`check_model_configuration`.

## Planned Commands

`mke init`, `mke serve`, and `mke library create` remain planned.

Generative Ask, HTTP, workspace UI, OCR, scanned PDFs, long videos, bundled model weights, tables,
page coordinates, hosted coordination, and multi-worker behavior remain outside scope.
