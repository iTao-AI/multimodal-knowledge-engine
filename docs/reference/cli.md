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

## Retrieval Evaluation

```bash
mke eval retrieval --manifest <manifest.json> [--json]
```

The manifest is required. Evaluation validates and snapshots exact fixture bytes, ingests the
corpus into two fresh temporary SQLite workspaces, calls the current Search and evidence-only Ask
contracts at limit 5, and compares ordered stable locator outcomes. It does not use the global
`--db`; explicitly supplying `--db` with `eval` is a usage error.

Human output begins with:

```text
mke eval retrieval
scope=small_english_page_timestamp_corpus quality_gate=none
evaluation=retrieval manifest=<id> status=<passed|failed> quality_status=<baseline_recorded|not_recorded> ...
```

Successful reports include document/query/category counts, Recall@1/3/5, MRR@5, answerable
zero-hit rate, unanswerable no-hit rate, Ask refusal rate, and one bounded stable-locator line per
query. JSON uses schema `mke.retrieval_eval_report.v1`. Neither format includes query text,
Evidence text, random IDs, absolute paths, tracebacks, or temporary directory names.

Evaluation failure fields are `problem`, `cause`, `next_step`, and optional `subject_id`.

| Code | Meaning |
|---|---|
| `0` | Integrity gates passed and the baseline was recorded. |
| `1` | A trustworthy complete baseline was not produced. |
| `2` | Invalid CLI usage. |

`quality_gate=none` is intentional: low retrieval scores are observations, not E1 failures. See
[Run Retrieval Evaluation](../how-to/run-retrieval-evaluation.md) for metric definitions,
recorded values, and comparison guidance.

## Numeric Retrieval Comparison

```bash
mke eval retrieval-numeric --protocol <protocol-lock.json> [--json]
```

This historical comparison command reads candidate identity from the strict protocol and owns
temporary workspaces. The public holdout is locked but not blind. Its passing artifact supported
ADR-0007 promotion; the command remains protocol-owned and does not accept the runtime policy
selector.

Human output begins with:

```text
mke eval retrieval-numeric
protocol=<id> candidate=numeric-grouping-v1 revision=1
integrity_status=<passed|failed> candidate_status=<passed|rejected|not_recorded>
```

JSON uses schema `mke.retrieval_numeric_comparison.v1` and includes current/candidate observations
for development, holdout, and E1; compiled query pairs; ordered gates; fixed integrity failures;
duration; and limitations. Exit codes are `0` passing comparison, `1` trustworthy rejection or
integrity failure, and `2` invalid usage. Explicit `--db`, candidate overrides, output paths,
providers, URLs, models, SQL, regex, import paths, tokenizer expressions, and executable commands
are not accepted.

If either repeated evaluator observation differs, the fixed public failure is
`retrieval_numeric_nondeterministic` with cause
`numeric comparison results were not deterministic` and next step
`inspect_numeric_comparison_runtime`.

See [Evaluate The Numeric Retrieval Candidate](../how-to/evaluate-numeric-retrieval.md).

## Chinese Retrieval Evaluation

```bash
mke eval retrieval-chinese --protocol <protocol.json> [--json]
```

The command records the current FTS5 lexical baseline on isolated Chinese development and public
holdout corpora. It is baseline-only: `quality_gate=none`, and it makes no dense, hybrid, RRF,
reranker, CJK-support, or runtime-promotion claim. `--protocol` is required. `--json` selects one
JSON object. Global `--db` and `--retrieval-query-policy` are usage errors for all `eval`
commands.

Human stdout begins with exactly:

```text
mke eval retrieval-chinese
integrity_status=<passed|failed> quality_status=<baseline_recorded|not_recorded> quality_gate=none
e3b_decision=<eligible|not_justified> reason=<stable_reason>
documents=<n> queries=<n> development=<n> holdout=<n> duration_ms=<n>
```

Human mode writes only these ordered progress phases to stderr:

```text
protocol_validated
development_ingested
holdout_ingested
determinism_verified
```

JSON mode keeps stderr empty. A failure never emits a later success phase.

JSON schema `mke.retrieval_chinese_report.v1` contains exactly:

```text
schema_version
protocol_id
benchmark_scope
quality_gate
integrity_status
quality_status
documents
queries
split_counts
results
metrics
qrel_adjudication
e3b_decision
e3b_evidence
e3b_reason
fts5_rank_profile
fts5_rank_observations
integrity_failures
duration_ms
limitations
```

Results separate query `category`, `compiled_query_empty`, and `ascii_token_count`. Reports do not
include raw query text, raw Evidence text, absolute paths, random IDs, exception text, hostnames,
or usernames.

| Code | Meaning |
|---|---|
| `0` | Integrity passed and a baseline was recorded; observed quality may still be low. |
| `1` | Integrity failed or the final report could not be rendered. |
| `2` | Invalid CLI usage. |

Stable failures and recovery:

| `problem` | Exact `cause` | `next_step` |
|---|---|---|
| `retrieval_chinese_protocol_invalid` | `Chinese retrieval protocol is invalid` | `restore_checked_in_protocol` |
| `retrieval_chinese_qrels_invalid` | `Chinese retrieval qrel review is invalid` | `restore_checked_in_qrel_review` |
| `retrieval_chinese_fixture_invalid` | `Chinese retrieval fixture identity is invalid` | `verify_fixture_identity` |
| `retrieval_chinese_ingest_failed` | `Chinese retrieval fixture could not be published` | `inspect_publication_failure` |
| `retrieval_chinese_evidence_invalid` | `active Evidence and retrieval projection are inconsistent` | `inspect_active_evidence_projection` |
| `retrieval_chinese_rank_invalid` | `FTS5 rank evidence is inconsistent` | `inspect_fts5_rank_configuration` |
| `retrieval_chinese_incomplete` | `Chinese retrieval evaluation did not complete` | `rerun_evaluation` |
| `retrieval_chinese_artifact_invalid` | `Chinese retrieval baseline artifact is invalid` | `regenerate_chinese_artifact` |
| `retrieval_artifact_refresh_failed` | `retrieval artifact transaction did not complete` | `recover_checked_in_artifacts` |

Copy-paste recovery commands are in the how-to guide.

See [Run The Chinese Retrieval Evaluation](../how-to/run-chinese-retrieval-evaluation.md).

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
- `--retrieval-query-policy` is a global owner option with allowlisted values
  `numeric-grouping-v1` and `current`. The default is `numeric-grouping-v1`; `current` is the
  rollback selector.
- The SQLite schema is created automatically when the database is opened.
- `ingest` supports PyMuPDF text-layer PDFs and the documented short MP4 fixture profile.
- Video ingest defaults to `<video>.mke-transcript.json`. Selecting
  `--transcript-provider faster-whisper` uses the cache-only first-party adapter. It does not run a
  system `ffmpeg`, download during ingest, or accept command argv.
- `search` reads only active Publication rows in SQLite FTS5. Eligible standalone compact ASCII
  integers also match tokenizer-adjacent conventional right-grouped document tokens.
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
mke --db <path> [--retrieval-query-policy <policy>] mcp --allowed-root <path>
```

- Runs a local stdio MCP server.
- `--allowed-root` defaults to the current working directory.
- `ingest_file` rejects paths outside `--allowed-root`.
- Implemented MCP tools are `list_libraries`, `ingest_file`, `get_run`, `search_library`, and
  `ask_library`.
- Retrieval policy is owner startup configuration. It is not present in MCP tool schemas.
- `--retrieval-query-policy current` rolls Search and Ask query compilation back without changing
  the database or rebuilding the FTS5 projection.
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
