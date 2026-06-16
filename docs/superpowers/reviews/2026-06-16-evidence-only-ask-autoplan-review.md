# Evidence-Only Ask Autoplan Review Report

**Review date:** 2026-06-16
**Review object:** `docs/superpowers/specs/2026-06-16-evidence-only-ask-design.md`
**Branch:** `codex/evidence-only-ask-plan`
**Base commit:** `d5d8f81`
**Review type:** Spec-level pre-implementation review

## Verdict

**APPROVE_WITH_CONCERNS.** The core decision is correct: C2 should implement
`ask_library` as a deterministic Evidence packet, not as model-generated Ask. The design matches
the current project state: MCP C1 exists, Search is active-Publication-only, and there is no model
provider, prompt contract, HTTP server, or workspace UI yet.

The implementation plan must resolve two blocking design gaps and explicitly account for the
high-priority findings below.

## Required Fixes Before Implementation

| ID | Severity | Finding | Required handling |
|---|---|---|---|
| R1 | CRITICAL | `KnowledgeEngine.ask()` return type was not defined beyond "simple DTO". | Define an `AskResult` dataclass in the domain or application boundary. |
| R2 | CRITICAL | `SearchResult` to MCP Evidence dict mapping would be duplicated between `search_library` and `ask_library`. | Extract a shared private mapper in `mcp_contract.py`. |
| R3 | HIGH | Summary wording used "related to the question", but current FTS5 only does token matching. | Use wording such as "matched the search terms". |
| R4 | HIGH | CJK-only questions currently become empty FTS queries and could be mistaken for no Evidence. | Define explicit validation behavior for no searchable tokens. |
| R5 | HIGH | `question` had no maximum length. | Add a max length, recommended 1000 characters after trimming. |
| R6 | HIGH | `insufficient_evidence` merges empty Library and no-match cases. | Record this as an intentional C2 design choice or add a distinguishing field. |
| R7 | HIGH | MCP contract tests did not explicitly require the `insufficient_evidence` path. | Add tests for successful Ask with no Evidence. |
| R8 | HIGH | Ask results lacked a correlation identifier. | Add `ask_id` to successful Ask payloads. |
| R9 | HIGH | Summary behavior was slightly contradictory. | State that C2 summary is deterministic and count-only. |

## Optional Enhancements

| ID | Severity | Finding | Handling |
|---|---|---|---|
| A1 | MEDIUM | CJK and special-character behavior should be covered by tests. | Include if C2 validates no-token questions. |
| A2 | MEDIUM | `answer_status` may need future values. | Keep C2 values explicit and defer new values to later design. |
| A3 | MEDIUM | Discovery behavior for `ask_library` was not described. | Clarify that MCP tool discovery is separate from `list_libraries`. |

## Recommended Implementation Plan Shape

1. Add `AskResult` DTO and `KnowledgeEngine.ask(question, limit)`.
2. Validate empty, overlong, no-searchable-token, and invalid-limit inputs.
3. Add `ask_library(config, question, limit)` in `mcp_contract.py`.
4. Extract `_evidence_from_search_result()` and reuse it from both `search_library` and
   `ask_library`.
5. Add `ask_library` to the FastMCP server.
6. Add `mke ask <question>` as a local smoke/debug path because it can reuse the same service cleanly.
7. Cover application, MCP contract, MCP server, CLI, insufficient Evidence, and no-token tests.
8. Update contracts, CLI/MCP how-to, README files, and docs index.

## Non-Blocking Carryovers

The C1 advisory items remain relevant but should not block C2:

- CLI imports the MCP SDK for non-MCP commands.
- `run_events` has no `run_id` index.
- Each MCP tool call opens and closes `KnowledgeEngine`.
