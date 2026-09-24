# Mixed CJK/ASCII Intent Retrieval: Local Review

Status: local candidate review. Default promotion and hosted gates remain separate decisions.

Reviewed against `main@d3d801bb776480516f3062673a43a592ea99b581` and the
[approved design](../specs/2026-09-24-mixed-cjk-fts-intent-design.md).

## Observed Selection

The synthetic fixture keeps the same active Evidence for each old and candidate query:

| Query | Existing numeric FTS page locators | Mixed candidate page locators |
|---|---|---|
| `anchoralpha 账户余额调整流程` | 1, 2 | 1 |
| `anchoralpha 审计权限审批流程` | 1, 2 | 2 |
| `anchorbeta 设备扩展部署方案` | 3, 4 | 3 |
| `anchorbeta 数据泄露处置方案` | 3, 4 | 4 |
| `anchoralpha 服务器退役处理流程` | 1, 2 | none |

In a separate seven-page fixture, the existing FTS top five are pages 1–5, while the mixed
candidate's limited Search and Ask return pages 6–7. Paged MCP Search returns page 6 and then
page 7; the cursor rejects a different strategy or revision. These are synthetic local
observations, not a general retrieval-quality claim. Frozen baseline fixture bytes, qrels, and
receipts were not changed.

## Review Findings Resolved

- A query with only ASCII and more than 512 characters stays on the existing numeric FTS path;
  the mixed-query character bound applies only when CJK is present.
- Mixed-query budget causes are approved only at Search and Ask public boundaries. The complete
  term-budget cause is included; unrelated public errors and the frozen MCP schema fixture keep
  their prior behavior.
- The usage guide records the actual `retrieval rebuild` no-op scope for this strategy:
  `additional_projection`.
- The complete matched FTS set is counted before candidate text is loaded. The SQL contains no
  preselection `LIMIT` or `OFFSET`, and row or byte overflow fails before scoring.

## Verification And Remaining Limits

Focused tests cover the selectors, active and provenance authority, duplicate locators, numeric
and identifier clauses, original UTF-8 excerpt slices, response limits, cursor identity, and
budget boundaries. The built offline wheel was imported from an extracted artifact and exercised
through CLI and stdio MCP; Search, Ask, pagination, and exact read returned the expected locators.
The final offline full suite passed: 4,285 tests passed, 14 skipped, with five third-party SWIG
deprecation warnings. `mke proof run` and `mke demo --verify` passed with local fixtures. Ruff,
Pyright, and offline wheel build passed. A temporary task-local test environment reused existing
dependencies so subprocess proof tests loaded this worktree; no dependency was installed and no
test was changed to bypass a gate.
A local bounded-selector check with 128 terms and 1,001 eligible candidates produced the typed
pool-overflow failure in 0.015 seconds on this host; this is a boundary observation, not a
cross-host latency promise.

The candidate remains an explicitly selected lexical strategy. Short CJK wording and paraphrases
without enough literal trigram overlap can have no Evidence. No provider, migration, new
projection, default promotion, hosted check, PR, merge, or release is claimed here.
