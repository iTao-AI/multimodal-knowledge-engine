# Real PDF Intake Pre-Landing Review

Review date: 2026-06-16

Reviewed branch:

- `codex/real-pdf-intake`

Reviewed diff:

- Base: `origin/main` at `bd9a638`
- Scope: D1 Real PDF Intake

## Verdict

Approved after one documentation fix.

Scope check: CLEAN. The branch implements PyMuPDF text-layer PDF intake, Run-attached
`PdfIntakeReport` diagnostics, CLI/MCP intake summaries, MCP 100 MB PDF guard, old PDF fingerprint
compatibility, and documentation updates. It does not implement OCR, table extraction,
layout-aware chunking, hybrid retrieval, rerank, HTTP, workspace UI, or generative Ask.

## Findings

| Priority | Finding | Resolution |
|---|---|---|
| Informational | `docs/reference/cli.md` used a fixed `extracted_chars=87` example that could drift with fixture text. | Replaced the literal count with `<chars>` in ingest and Run inspection examples. |

## Review Checks

- SQL and data safety: no unsafe value interpolation was introduced; new SQLite writes use bound
  parameters and a keyed `pdf_intake_reports` table.
- Publication safety: Search and Ask still read active Publications only; failed PDF extraction
  and failed activation paths do not publish candidate Evidence.
- Adapter boundary: PyMuPDF imports are contained in `src/mke/adapters/pdf/` and test fixture
  helpers.
- MCP safety: path allow-listing remains in place, and PDF files larger than 100 MB are rejected
  before `KnowledgeEngine` opens the extractor.
- Public boundary: no private paths, private source documents, raw GStack artifacts, or unverified
  metrics were added.

## Verification

| Check | Result |
|---|---|
| `uv run pytest -q` | `143 passed, 5 warnings` |
| `uv run ruff check .` | `All checks passed!` |
| `uv run pyright` | `0 errors, 0 warnings, 0 informations` |
| `uv build` | Built sdist and wheel successfully |
| `uv run mke demo --verify` | `result=passed duration_ms=8` |
| `git diff --check` | Passed with no output |
