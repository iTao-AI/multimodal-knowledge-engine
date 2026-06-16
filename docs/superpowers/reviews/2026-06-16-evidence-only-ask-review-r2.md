# Pre-Landing Review: evidence-only ask 第二轮

Branch: `codex/evidence-only-ask`
Base: `main`
Date: 2026-06-16
Reviewer: Claude Opus 4.8 (gstack /review)

## Scope Check

**CLEAN** — 实现完全匹配 stated intent。

- Intent: C2 evidence-only Ask — `ask_library` MCP tool、`mke ask` CLI、shared Evidence mapper、Ask validation
- Delivered: `KnowledgeEngine.ask()`、`AskResult`、MCP `ask_library`、CLI `mke ask`、`_evidence_from_search_result()` shared mapper、contracts/docs

## Findings

### AUTO-FIXED

- `src/mke/cli.py:22` — stale `"narrow PR 2 CLI path"` docstring → 更新为包含 Ask
- `src/mke/interfaces/mcp_contract.py:169` — `ask_library` 在验证前打开 DB → 添加 fail-fast 预验证，与 `search_library` 一致
- `src/mke/interfaces/mcp_server.py:59` — 硬编码 `limit: int = 5` → 使用 `DEFAULT_ASK_LIMIT` 常量
- `src/mke/application/__init__.py:297` — `_normalize_ask_question` 对非 str 输入 `AttributeError` → 添加 `isinstance` runtime guard
- `src/mke/interfaces/mcp_contract.py:20-22` — limit 常量在 application 和 mcp_contract 重复定义 → 整合到 `application` 层并公开为 `DEFAULT_ASK_LIMIT`/`MIN_ASK_LIMIT`/`MAX_ASK_LIMIT`

### ASK → FIXED

- `src/mke/domain/__init__.py:129-130` — `@dataclass(frozen=True)` 含 mutable `list[SearchResult]` 和 `list[str]` → 改为 `tuple[SearchResult, ...]` 和 `tuple[str, ...]`
- `src/mke/cli.py:98-124` — `_search()` 和 `_ask()` 重复 6 行定位器格式化/打印代码 → 提取 `_print_evidence_matches()`

### 未采纳（需后续考虑）

- Testing: `_matched_summary` 复数分支（`evidence_count >= 2`）未经测试；CLI `mke ask` 视频 `timestamp_ms` 路径未经测试；Ask limit 边界接受测试缺失
- Adversarial: SQLite ≥3.36 下纯下划线（`___`）question 是否会触发 FTS5 错误（本机 3.51.1 不触发，无需处理）

### Codex follow-up

- Testing follow-up applied: added coverage for `_matched_summary()` plural output, CLI `mke ask` video `timestamp_ms` output, and `engine.ask(limit=1/20)` boundary acceptance.

## Specialist Review

| Specialist | Dispatched | Findings | Critical | Informational |
|---|---|---|---|---|
| Testing | true | 4 | 0 | 4 |
| Maintainability | true | 3 | 0 | 3 |
| Security | true | 0 | 0 | 0 |
| Performance | true | 0 | 0 | 0 |

## Adversarial Review

Claude adversarial subagent: 5 findings (4 FIXABLE, 1 INVESTIGATE)，全部已处理。

Codex: not installed，skipped。

**Recommendation:** Ship as-is — strongest finding (frozen dataclass with mutable containers) fixed.

## Verification

| Check | Result |
|---|---|
| `uv run pytest -q` | 122 passed |
| `uv run ruff check .` | All checks passed |
| `uv run pyright` | 0 errors, 0 warnings |

## Quality Score: 6.0/10

（审查前：6.5；7 个 informational 发现项已修复）
