# Product Proof & Evaluation Harness Design

## Goal

Build a deterministic local product proof and evaluation harness for MKE.

D2 adds `mke proof run` as the primary product proof entrypoint. The command must prove that the
current engine can ingest real text-layer PDF and short-video fixtures, publish trustworthy
Evidence, isolate failed Runs, and expose the same verifiable behavior through both CLI-facing and
MCP contract paths.

This is a proof and contract-readiness slice, not a retrieval-quality benchmark.

## Current State

MKE already has a deterministic local proof through `mke demo --verify`. That command uses a
temporary SQLite workspace, ingests the repository PDF fixture, verifies failed PDF reprocessing
does not change active Search, retries a validated candidate, ingests a short-video fixture, and
cleans up.

The current proof is useful but still demo-shaped:

- It is a single hard-coded CLI flow.
- It prints phase lines, but does not expose a structured proof report.
- It does not group assertions as reusable proof cases.
- It does not explicitly prove MCP contract behavior in the same proof surface.
- It is not yet a stable artifact for CI, release checks, or public project inspection.

D2 upgrades that path into a manifest-driven proof harness.

## Decision

Introduce `mke proof run` backed by a project-owned proof module:

```text
src/mke/proof/
  __init__.py
  manifest.py
  report.py
  runner.py
```

Responsibilities:

- `manifest.py`: defines the built-in proof manifest and case identifiers.
- `runner.py`: executes proof cases against an isolated temporary SQLite workspace.
- `report.py`: defines `ProofReport` and `ProofCaseResult` DTOs plus human and JSON formatting.

The runner should call the same application and MCP contract functions that production-facing
entrypoints use:

```text
mke proof run
  -> load built-in proof manifest
  -> create temporary SQLite workspace
  -> run CLI-equivalent application checks through KnowledgeEngine
  -> run MCP contract checks through mke.interfaces.mcp_contract
  -> emit deterministic proof report
  -> return exit code 0 or 1
```

MCP proof cases use `mke.interfaces.mcp_contract` in-process. D2 intentionally does not start the
stdio MCP transport because this slice proves contract behavior, not transport process management.

`mke demo --verify` remains available for compatibility and keeps its current phase-oriented stdout
shape. D2 must not delegate `demo --verify` to the proof runner if doing so changes existing output.
Documentation should make `mke proof run` the primary proof path while preserving the old demo
command as a compatibility proof.

## Public Contract

CLI command:

```bash
mke proof run
mke proof run --json
```

Human output shape:

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
case=mcp_search_and_ask status=passed answer_status=evidence_found
```

JSON output shape:

```json
{
  "proof": "product",
  "status": "passed",
  "cases": 8,
  "passed": 8,
  "failed": 0,
  "duration_ms": 42,
  "results": [
    {
      "case": "cli_pdf_ingest",
      "status": "passed",
      "summary": "PDF ingest published page Evidence and intake diagnostics.",
      "observed": {
        "evidence_count": 2,
        "intake_report": "present"
      },
      "duration_ms": 4
    }
  ]
}
```

JSON must not include absolute local paths, temporary directory names, stack traces, credentials, or
private source text. `observed` values are restricted to public-safe scalars:

- integers for counts,
- booleans only when they do not reveal host state,
- stable enum strings such as `present`, `unchanged`, `evidence_found`, `published`, `page`, and
  `timestamp_ms`.

`observed` must not include Run IDs, Evidence IDs, file paths, directory names, raw Evidence text,
credentials, or exception messages containing host-specific data.

Exit codes:

| Code | Meaning |
|---|---|
| `0` | All proof cases passed. |
| `1` | At least one proof case failed and the report marks the failed case. |

## Proof Cases

D2 ships one built-in proof manifest named `product`.

The manifest is ordered. Later cases may depend on public-safe context captured by earlier cases:

- `mcp_get_run` depends on `mcp_ingest_file` creating a PDF Run and storing that Run ID in internal
  runner context.
- `mcp_search_and_ask` depends on the same MCP workspace containing an active PDF Publication from
  `mcp_ingest_file`.

The manifest schema should still include a stable name field, even though selecting optional
manifests by name is deferred.

Required cases:

| Case | Path | What it proves |
|---|---|---|
| `cli_pdf_ingest` | Application / CLI-equivalent | Text-layer PDF ingest publishes page Evidence and exposes `PdfIntakeReport`. |
| `cli_pdf_search` | Application / CLI-equivalent | Active Search returns page-addressed Evidence from the published PDF. |
| `cli_failed_reprocess` | Application / CLI-equivalent | Injected failed PDF reprocess leaves the previous active Publication searchable. |
| `cli_video_ingest_search` | Application / CLI-equivalent | Short-video sidecar ingest publishes timestamp-addressed Evidence. |
| `cli_ask` | Application / CLI-equivalent | Evidence-only Ask returns cited active Evidence without calling an LLM. |
| `mcp_ingest_file` | MCP contract | `ingest_file` accepts an allowed PDF path and returns an intake report. |
| `mcp_get_run` | MCP contract | `get_run` exposes Run state, events, and PDF intake diagnostics. |
| `mcp_search_and_ask` | MCP contract | `search_library` and `ask_library` return active Evidence only. |

Fixed queries:

| Case | Query or question |
|---|---|
| `cli_pdf_search` | `trustworthy` |
| `cli_failed_reprocess` | `trustworthy` before and after injected failure |
| `cli_video_ingest_search` | `timestamp proof` |
| `cli_ask` | `publication active` |
| `mcp_search_and_ask` search query | `trustworthy` |
| `mcp_search_and_ask` ask question | `publication active` |

Each case records:

- stable case identifier,
- status: `passed` or `failed`,
- short public-safe summary,
- observed fields needed to inspect the assertion,
- duration in milliseconds.

## Failure Semantics

The proof runner must fail closed:

- If a case assertion fails, the case status is `failed`.
- The full report still includes completed cases before and after the failed case when execution can
  continue safely.
- The process exits `1` if any case fails.
- A failed proof must not leave files in the repository working tree.
- The runner must use a temporary SQLite workspace and repository fixtures only.
- Output must use stable failure summaries instead of raw tracebacks.
- Raw exceptions may be attached only to test diagnostics, not to normal CLI output.
- Missing repository fixtures must produce a failed proof report with a stable `fixture_missing`
  reason and the repository-relative fixture key, not a Python traceback.

Failure reports should remain operator-friendly:

```text
proof=product status=failed cases=8 passed=7 failed=1 duration_ms=<milliseconds>
case=mcp_search_and_ask status=failed reason=no active Evidence returned for timestamp query
```

## Fixtures And Inputs

D2 uses existing repository fixtures:

- `tests/fixtures/pdf/text-layer.pdf`
- `tests/fixtures/pdf/text-layer-revised.pdf`
- `tests/fixtures/video/short-audio.mp4`
- `tests/fixtures/video/short-audio.mp4.mke-transcript.json`

No private PDFs, private local paths, network calls, model downloads, provider credentials, or
generated media are part of D2.

The proof manifest should refer to repository-relative fixture paths. The report should expose only
case outcomes and observed contract fields, not host-specific absolute paths.

## Non-Goals

D2 does not implement:

- retrieval precision, recall, MRR, or benchmark scoring,
- embeddings, rerank, hybrid retrieval, or Unicode-aware retrieval,
- scanned-PDF OCR,
- table extraction, page coordinates, or layout-aware chunking,
- arbitrary or long-video processing,
- real speech-model transcription,
- generative Ask,
- HTTP or workspace UI,
- stdio MCP transport lifecycle tests,
- external provider integration,
- release automation or hosted deployment.

## Documentation Impact

D2 should update:

- `README.md` and `README_CN.md`: make `mke proof run` the primary local proof command.
- `docs/how-to/run-local-product-proof.md`: document the proof harness, human output, JSON output,
  and what the proof does and does not prove.
- `docs/reference/cli.md`: add `mke proof run` and `mke proof run --json`.
- `docs/reference/contracts.md`: record `mke proof run` as implemented once shipped.
- `docs/README.md`: link to the updated product proof how-to if needed.

Documentation must stay public-neutral. It should describe product capability and verification
contracts, not private project motivations.

## Testing Strategy

D2 implementation should add focused tests for:

- proof report DTO formatting,
- JSON report schema stability,
- successful `mke proof run`,
- successful `mke proof run --json`,
- failed proof case exit code and report shape,
- MCP proof cases using `McpRuntimeConfig` with an allowed root,
- old `mke demo --verify` behavior remaining available.

Full verification before PR:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke proof run --json
uv run mke demo --verify
git diff --check
```

## Acceptance Criteria

D2 is accepted when:

- `mke proof run` exits `0` and prints all required proof cases as passed.
- `mke proof run --json` emits valid deterministic JSON with no host-specific absolute paths.
- A forced failing case can be tested and produces exit code `1`.
- CLI-equivalent cases and MCP contract cases both run in the same proof report.
- Existing `mke demo --verify` still passes.
- README and reference docs point users to the new primary proof command.
- The implementation introduces no external services, credentials, network calls, or new provider
  dependencies.

## Deferred Work

The following work is intentionally left for later slices:

- `mke eval run` for retrieval-quality metrics.
- Unicode-aware Search and Ask quality gates.
- Optional proof manifests selected by name.
- Stdio MCP transport process smoke tests.
- CI matrix job dedicated to product proof output archival.
- Public benchmark datasets beyond repository fixtures.
