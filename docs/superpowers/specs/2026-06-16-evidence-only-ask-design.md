# Evidence-Only Ask Design

## Goal

Add the first `ask_library` capability as a deterministic Evidence packet, not as a
model-generated answer.

This is C2 of the Agent-facing interface work:

```text
active Publication Search
-> evidence-only Ask service
-> MCP ask_library
-> Agent receives cited page or timestamp Evidence plus refusal state
```

The feature is optimized for engineering trust and Agent integration. Human-friendly answer
generation, prompt design, model providers, and workspace UI remain later concerns.

## Current State

- C1 exposes MCP stdio tools for `list_libraries`, `ingest_file`, `get_run`, and
  `search_library`.
- `KnowledgeEngine.search()` reads only active Publication rows from SQLite FTS5.
- Search results already include `evidence_id`, `publication_id`, `source_id`, locator kind,
  locator range, and Evidence text.
- `docs/reference/contracts.md` marks `ask_library` as planned.
- The project has no model provider boundary, prompt contract, embedding retrieval, HTTP server,
  or workspace UI.

## Decision

Implement `ask_library` before HTTP, UI, and model generation, but keep it non-generative.

`ask_library` returns a structured Evidence packet:

- If active Evidence is found, return `answer_status="evidence_found"` with a deterministic
  count summary and cited Evidence.
- If no active Evidence is found, return `answer_status="insufficient_evidence"` with an empty
  Evidence list and a clear limitation.
- Do not synthesize facts, infer beyond retrieved Evidence, or call an LLM.

This preserves the project's core boundary: MKE is an Evidence engine. A downstream Agent may use
the returned Evidence to produce a natural-language answer, but that generated answer is outside
this slice.

## Why Not Generative Ask Yet

Generative Ask would require new decisions that are not needed to prove the Agent-facing Evidence
contract:

- provider selection and credentials,
- prompt and refusal policy,
- citation grounding checks,
- model-output tests and evaluation data,
- privacy and cost boundaries,
- fallback behavior when model calls fail.

Adding those now would obscure whether the Evidence lifecycle and Agent contract are correct.
C2 should instead make the trusted input to a future grounded-answer layer explicit and testable.

## Contract

### MCP Tool

Add:

```text
ask_library
```

Input:

```json
{
  "question": "What does the document say about Publication failures?",
  "limit": 5
}
```

Rules:

- `question` is required and must not be empty after trimming.
- `question` must be no longer than 1000 characters after trimming.
- `question` must contain at least one searchable ASCII token for the current SQLite FTS5
  tokenizer. CJK-only and punctuation-only questions are rejected in C2 instead of silently
  returning insufficient Evidence.
- `limit` defaults to 5.
- `limit` must be between 1 and 20.
- The tool searches only active Publication Evidence.
- The tool returns the same locator shape as `search_library`.
- The response includes `ask_id` so Agent logs can correlate an Ask result with service logs.

Success with Evidence:

```json
{
  "ok": true,
  "ask_id": "ask_...",
  "question": "What does the document say about Publication failures?",
  "answer_status": "evidence_found",
  "summary": "2 active Evidence items matched the search terms.",
  "evidence": [
    {
      "evidence_id": "ev_...",
      "publication_id": "pub_...",
      "source_id": "src_...",
      "locator": {
        "kind": "page",
        "start": 2,
        "end": 2
      },
      "text": "Failed or partial processing never becomes searchable."
    }
  ],
  "limitations": [
    "No model-generated answer is produced in this slice.",
    "The summary is deterministic and only reports matched Evidence count."
  ]
}
```

Success without Evidence:

```json
{
  "ok": true,
  "ask_id": "ask_...",
  "question": "What does the document say about audio diarization?",
  "answer_status": "insufficient_evidence",
  "summary": "No active Evidence matched the search terms.",
  "evidence": [],
  "limitations": [
    "No answer is produced because no active Evidence matched the search terms.",
    "No model-generated answer is produced in this slice."
  ]
}
```

Validation failure:

```json
{
  "ok": false,
  "problem": "invalid_question",
  "cause": "question must not be empty",
  "active_publication_impact": "unchanged",
  "next_step": "provide_non_empty_question"
}
```

Unsupported question terms use the same `invalid_question` problem code:

```json
{
  "ok": false,
  "problem": "invalid_question",
  "cause": "question must contain at least one searchable ASCII token",
  "active_publication_impact": "unchanged",
  "next_step": "provide_searchable_question"
}
```

Limit validation uses the existing stable shape:

```json
{
  "ok": false,
  "problem": "invalid_query",
  "cause": "limit must be between 1 and 20",
  "active_publication_impact": "unchanged",
  "next_step": "choose_limit_between_1_and_20"
}
```

## Application Boundary

Add project-owned Ask DTOs in the domain boundary. They should be simple dataclasses, not model
provider abstractions.

```python
@dataclass(frozen=True)
class AskResult:
    ask_id: str
    question: str
    answer_status: str
    summary: str
    evidence: list[SearchResult]
    limitations: list[str]
```

`answer_status` is a string in C2 with two supported values:

- `evidence_found`
- `insufficient_evidence`

Future answer statuses, such as model-grounded answer variants, require a later ADR or design
spec. C2 tests should assert only the two current values.

The application flow is:

```text
KnowledgeEngine.ask(question, limit)
-> validate question and limit
-> call active-only Search
-> create AskResult with SearchResult Evidence
-> return evidence_found or insufficient_evidence
```

`ask_library` in the MCP contract should call `KnowledgeEngine.ask()` rather than duplicating Ask
composition logic in the MCP layer. `search_library` remains a lower-level retrieval tool.

The MCP contract layer must share one private mapping helper for Search Evidence:

```python
def _evidence_from_search_result(match: SearchResult) -> dict[str, Any]:
    ...
```

Both `search_library` and `ask_library` use that helper so locator payloads cannot drift.

## CLI Shape

Add a deterministic CLI command that reuses the same application service:

```bash
mke --db <path> ask <question>
```

The CLI prints field-based output that is easy to test. It does not try to format a polished human
answer.

Example:

```text
answer_status=evidence_found evidence_count=2 summary="2 active Evidence items matched the search terms."
page=2 evidence_id=ev_... text=Failed or partial processing never becomes searchable.
```

MCP `ask_library` remains the required Agent-facing interface. CLI `mke ask` is included in C2 as
a local smoke/debug path because it can call the same `KnowledgeEngine.ask()` service without
adding a new runtime boundary.

## Error And Refusal Semantics

Known operator errors return `ok=false` and do not affect active Publication state.

Known C2 problem codes:

- `invalid_question`
- `invalid_query`
- `mcp_tool_failed`

No-Evidence refusal is not an error. It returns `ok=true` with
`answer_status="insufficient_evidence"` because the system behaved correctly and found no active
Evidence. C2 intentionally does not distinguish an empty Library from a Library with active
Evidence that did not match the search terms; both are insufficient Evidence for the question.

CJK-only, punctuation-only, and other no-token questions are validation errors rather than
insufficient Evidence because the current FTS5 tokenizer cannot search them. This is a known C2
retrieval limitation, not a semantic judgment about the content.

## Discovery

MCP tool discovery is provided by the MCP server. `ask_library` does not change the
`list_libraries` output because `list_libraries` describes data scope, not available tools.

## Documentation Updates

The implementation PR must update:

- `docs/reference/contracts.md`: mark MCP `ask_library` as implemented and document payloads.
- `docs/reference/cli.md`: document `mke ask` if implemented in C2.
- `docs/how-to/use-mke-mcp.md`: show how an Agent calls `ask_library`.
- `README.md` and `README_CN.md`: describe Ask as evidence-only, not generative.
- `docs/tutorials/getting-started.md` or product proof docs if the demo is extended.

## Tests

Required test coverage:

- `KnowledgeEngine.ask()` returns `evidence_found` for PDF page Evidence.
- `KnowledgeEngine.ask()` returns `evidence_found` for video timestamp Evidence.
- `KnowledgeEngine.ask()` returns `insufficient_evidence` for no active matches.
- Empty question returns `invalid_question`.
- Overlong question returns `invalid_question`.
- CJK-only or punctuation-only question returns `invalid_question` with
  `next_step="provide_searchable_question"`.
- Invalid limit returns `invalid_query`.
- MCP `ask_library` exposes the same payload and is wrapped by `_safe_tool`.
- `search_library` and `ask_library` share the same SearchResult-to-Evidence mapping helper.
- MCP contract tests cover the `insufficient_evidence` path.
- CLI `mke ask` output is deterministic if CLI is included.
- Existing Search tests continue proving only active Publications are visible.

## Explicit Non-Goals

- Model-generated answers.
- Provider configuration, API keys, prompt templates, or model retries.
- Embeddings, rerankers, hybrid retrieval, or semantic search.
- HTTP server, OpenAPI contract, workspace UI, hosted runtime, or auth.
- CJK tokenizer changes or ranking contract changes.
- Long-video, OCR, scanned PDF, tables, page coordinates, or image understanding.

## Acceptance

C2 is accepted when an Agent can call `ask_library` over MCP and receive either cited active
Evidence or an explicit insufficient-Evidence result. The response must be deterministic, testable
offline, and free of model-generated claims.
