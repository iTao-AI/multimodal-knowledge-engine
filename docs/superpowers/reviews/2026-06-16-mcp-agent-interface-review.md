# MCP Agent Interface — Pre-Landing Review Report

**审查日期：** 2026-06-16
**PR：** [#9 feat(mcp): add local agent interface](https://github.com/iTao-AI/multimodal-knowledge-engine/pull/9)
**分支：** `codex/mcp-agent-interface-plan`
**审查来源：** `/gstack-review`（Testing + Maintainability + Security + Performance 专项 + 对抗性审查）
**上游审查：** [autoplan review](./2026-06-16-mcp-agent-interface-autoplan-review.md)

---

## 总体评估

23 文件，+2632/-21 行。MCP 合约层、FastMCP stdio 适配器、CLI 接线、测试、文档全部到位。上游 autoplan 审查的 4 个关键/高危项全部已修复：

1. ✅ `KnowledgeEngine(...)` 在 try 块内部，`engine: KnowledgeEngine | None = None` + finally 判空
2. ✅ `_safe_tool` 包装器应用于全部 4 个 MCP 工具，测试覆盖
3. ✅ 测试缺口补齐：文件缺失、目录拒绝、空搜索结果、limit 边界值、空路径拒绝
4. ✅ SQL LIMIT 下推到 `SQLiteStore.search()`

额外超出计划实现了 `run_id` 包含在错误负载、`log_level="WARNING"`、`OSError` 路径处理。

本次审查发现 **15 项新发现，全部已修复或标记为咨询级别**。

---

## 已修复问题

### 测试覆盖（5 项）

| # | 严重性 | 问题 | 修复 |
|---|--------|------|------|
| T1 | CRITICAL | `PdfIngestError`/`VideoIngestError` 错误分支完全未测试 — 合约函数中的显式 except 子句从未触发 | 添加 `test_ingest_file_returns_stable_error_on_invalid_pdf` |
| T2 | CRITICAL | `search_library` limit>20 上界未测试 — 仅测了 `<1` 分支 | 添加 `test_search_library_rejects_limit_above_max`（limit=21） |
| T3 | CRITICAL | `_resolve_allowed_file` 的 `OSError` 路径未测试 — 仅覆盖了 `ValueError` | 添加 `test_ingest_file_returns_stable_error_on_broken_symlink` |
| T4 | INFORMATIONAL | `_safe_tool` 仅测试异常路径，正常返回路径未验证 | 添加 `test_safe_tool_passes_through_success_result` |
| T5 | INFORMATIONAL | `_safe_tool` 未测试装饰器对带参数函数的参数保留 | 添加 `test_safe_tool_preserves_arguments` |

### 安全（2 项）

| # | 严重性 | 问题 | 修复 |
|---|--------|------|------|
| S1 | INFORMATIONAL | `OSError` 的 `str(error)` 逐字包含在 `cause` 中 — `PermissionError` 字符串包含绝对路径，违反错误契约 | `OSError` 单独 catch，记录日志，返回静态 `cause: "file path cannot be resolved"` |
| S2 | INFORMATIONAL | `ingest_file` 中 `else: engine.ingest_pdf(...)` 将任意非 mp4 文件当作 PDF 处理 — 目前安全（`.pdf` 已在之前守卫），但未来媒体类型扩展会被静默错误路由 | 改为 `elif suffix == ".pdf":` + 兜底 `else: return _failure("unsupported_media_type", ...)` |

### 可维护性（1 项）

| # | 严重性 | 问题 | 修复 |
|---|--------|------|------|
| M1 | INFORMATIONAL | 搜索限制魔数（5、1、20）散布于 `search_library` 函数签名、验证检查和 `mcp_server.py` 默认值中 | 模块级常量 `_DEFAULT_SEARCH_LIMIT`、`_MIN_SEARCH_LIMIT`、`_MAX_SEARCH_LIMIT` |

---

## 咨询项目（非阻塞）

| # | 类别 | 问题 | 位置 |
|---|------|------|------|
| A1 | Performance | CLI 无条件导入 `run_mcp_server` → ~309ms MCP SDK 开销影响所有非 MCP 命令 | `cli.py:14` |
| A2 | Performance | `run_events` 表缺少 `run_id` 索引 → `get_run_events` 全表扫描 | `sqlite/__init__.py` |
| A3 | Performance | 每个 MCP 工具调用打开/关闭 `KnowledgeEngine` → migrate + interrupt 扫描每次执行 | 未来 ADR，设计文档已标记为非目标 |
| A4 | Security | `_safe_tool` 无 `error_id` → 客户端错误无法与服务端日志关联 | `mcp_server.py:65` |
| A5 | Security | CJK 搜索静默返回空 — `_to_fts_query` 仅匹配 `[A-Za-z0-9_]`（预先存在） | `sqlite/__init__.py` |
| A6 | Security | MCP SDK 间接依赖项扩大供应链攻击面 | `pyproject.toml` |
| A7 | Correctness | `search_library`/`get_run` 在每次调用时触发 `interrupt_unfinished_runs()` 写副作用 | `sqlite/__init__.py:46` |

---

## 专项审查结果

| 专项 | 发现数 | 关键 | 信息 |
|------|--------|------|------|
| Testing | 6 | 3 | 3 |
| Maintainability | 2 | 0 | 2 |
| Security | 4 | 0 | 4 |
| Performance | 3 | 0 | 3 |
| Adversarial | 7 | 0 | 7 |

---

## 验证

| 检查 | 结果 |
|------|------|
| `uv run pytest -q` | `96 passed in 0.39s` |
| `uv run ruff check .` | `All checks passed!` |
| `uv run pyright` | `0 errors, 0 warnings, 0 informations` |

---

## 判决

**SHIP。** 4 项 autoplan 关键项全部已修复。本次 15 项新发现中 8 项已自动修复，7 项咨询级为非阻塞项。A1（延迟导入）和 A2（run_events 索引）值得作为独立快速修复 PR 跟进。

---

## 非范围（已确认）

- `ask_library` → C2
- HTTP / REST API
- 工作区 UI
- 认证/授权
- 托管/多工作节点运行时
- OCR、任意视频、真实语音转录
- 外部模型调用
- 长寿命共享 SQLite 连接
