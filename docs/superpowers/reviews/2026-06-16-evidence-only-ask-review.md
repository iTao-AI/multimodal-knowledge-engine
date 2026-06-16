# Evidence-Only Ask Pre-Landing Review

Review date: 2026-06-16

Branch: `codex/evidence-only-ask`

Base: `origin/main` at `d0fac47 feat(mcp): add local agent interface (#9)`

## Scope Check

CLEAN.

The diff stays within C2 evidence-only Ask: domain/application Ask DTO and service, MCP `ask_library`, CLI `mke ask`, contract tests, focused docs, and the approved spec/plan/review artifacts.

Out of scope items remain absent: no LLM provider, prompt template, generated answer, HTTP API, workspace UI, embedding/reranking, OCR, tokenizer expansion, arbitrary video processing, or hosted runtime.

## Findings

Pre-landing review found 1 actionable issue and 0 unresolved issues.

| Severity | Status | Finding |
|---|---|---|
| Informational | Fixed | Python `bool` values were accepted as integer `limit` values at the Ask/Search boundary because `bool` is a subclass of `int`. Added regression coverage and explicit `type(limit) is not int` validation for Ask and MCP Search. |

## Review Notes

- `ask_library` returns deterministic Evidence packets with `ask_id`, `answer_status`, deterministic count summary, cited page/timestamp Evidence, and limitations.
- No-match Ask returns `ok=true`, `answer_status="insufficient_evidence"`, empty Evidence, and does not use the error path.
- Empty, overlong, CJK-only, punctuation-only, and no-searchable-token Ask inputs return `invalid_question`.
- `search_library` and `ask_library` share `_evidence_from_search_result()` for Evidence payload shape.
- CLI `mke ask` reuses `KnowledgeEngine.ask()` and keeps errors in the existing CLI error contract shape.
- No raw GStack artifacts, private paths, private planning notes, or unverified metrics are included.

## Verification

Review fix verification:

- `uv run pytest tests/application/test_ask.py tests/interfaces/test_mcp_contract.py -q` -> `39 passed in 0.10s`

Final branch verification:

| Check | Result |
|---|---|
| `uv run pytest tests/application/test_ask.py tests/interfaces/test_mcp_contract.py tests/interfaces/test_cli_ask.py tests/interfaces/test_mcp_server.py -q` | `47 passed in 0.34s` |
| `uv run pytest -q` | `122 passed in 0.46s` |
| `uv run ruff check .` | `All checks passed!` |
| `uv run pyright` | `0 errors, 0 warnings, 0 informations` |
| `uv build` | built sdist and wheel successfully |
| `uv run mke demo --verify` | `result=passed duration_ms=6` |
| `git diff --check` | passed |
