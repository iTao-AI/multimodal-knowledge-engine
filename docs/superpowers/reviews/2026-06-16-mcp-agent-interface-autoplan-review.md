# MCP Agent Interface — Autoplan Review Report

**审查日期：** 2026-06-16  
**分支：** `codex/mcp-agent-interface-plan`  
**审查来源：** Claude（CEO + Eng + DX 三阶段审查，Codex 不可用）  
**计划文件：**
- `docs/superpowers/specs/2026-06-16-mcp-agent-interface-design.md`
- `docs/superpowers/plans/2026-06-16-mcp-agent-interface-implementation.md`

---

## 总体评估

架构分层正确：`mcp_contract`（纯合约）→ `mcp_server`（FastMCP 适配器）→ CLI 接线。范围明确，非目标清晰（无 Ask/HTTP/workspace/OCR/真实转录）。测试计划覆盖了主要路径。

发现 **4 个关键/高危** 问题全部可在实现阶段修复，不涉及架构变更。

---

## 关键问题清单（必须在 PR 里修复）

### 1. [CRITICAL] `KnowledgeEngine(...)` 在 try 块外部 — 数据库打开失败导致 UnboundLocalError

**位置：** `src/mke/interfaces/mcp_contract.py` — `ingest_file`、`get_run`、`search_library` 三个函数

**问题：** 计划中的代码模式：

```python
engine = KnowledgeEngine(config.db_path)  # 如果这里抛异常，engine 未赋值
try:
    ...
finally:
    engine.close()  # UnboundLocalError，原始异常（含路径、堆栈）泄露到 MCP 客户端
```

违反设计文档的错误契约："responses must not include absolute host paths, stack traces, secrets, environment variables, or provider configuration."

**修复：** 与 PR #6 中 `_demo_verify` 的修复模式完全相同：

```python
engine: KnowledgeEngine | None = None
try:
    engine = KnowledgeEngine(config.db_path)
    ...
finally:
    if engine is not None:
        engine.close()
```

三个合约函数（`ingest_file`、`get_run`、`search_library`）都要改。

---

### 2. [HIGH] 缺少 `mcp_tool_failed` 兜底异常处理 — 意外异常带着堆栈跟踪泄露到 MCP 客户端

**位置：** `src/mke/interfaces/mcp_server.py`

**问题：** `@mcp.tool()` 装饰的函数直接调用合约函数，没有任何 try/except。如果 `engine.search()` 抛出 `sqlite3.OperationalError`（schema 不匹配、数据库损坏）或 `OSError`（磁盘满、权限问题），原始异常会传播到 FastMCP SDK，SDK 可能把绝对路径和堆栈跟踪序列化到 MCP 响应中。

设计文档定义了 `problem=mcp_tool_failed` 作为兜底错误码，但实现计划里没有任何代码使用它。

**修复：** 在 `mcp_server.py` 中添加一个工具包装器：

```python
import functools
import logging

logger = logging.getLogger(__name__)

_MCP_TOOL_FAILED = {
    "ok": False,
    "problem": "mcp_tool_failed",
    "cause": "internal error",
    "active_publication_impact": "unchanged",
    "next_step": "check_server_logs",
}

def _safe_tool(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            logger.exception("mcp_tool_failed")
            return _MCP_TOOL_FAILED
    return wrapper
```

然后用 `@_safe_tool` 包装每个 `@mcp.tool()` 函数，或在 `build_mcp_server` 里对四个工具统一 apply。日志写 stderr（MCP 协议 channel 外），`cause` 只返回 `"internal error"`，不暴露路径。

---

### 3. [HIGH] 测试覆盖缺口 — 4 个关键 case 缺失

**位置：** `tests/interfaces/test_mcp_contract.py`

**缺失的测试：**

| # | 测试 | 为什么需要 |
|---|------|-----------|
| 3a | `ingest_file` 对 `allowed_root` 下不存在的文件 | `_resolve_allowed_file` 有三条拒绝路径（不在根目录下 / 不存在 / 是目录），只测了第一条 |
| 3b | `ingest_file` 对 `allowed_root` 下的目录路径 | `is_file()` 拒绝路径完全未覆盖 |
| 3c | `search_library` 对合法查询返回空结果 | 现有测试都 `assert results[0]`，空结果直接 IndexError |
| 3d | `search_library` 对 `limit=1` 和 `limit=20` 边界值 | 只测了 `limit=0` 的拒绝，合法边界未覆盖 |

**同时补充：** `_resolve_allowed_file` 当前只 catch `ValueError`，但 `Path.resolve()` 可能抛 `OSError`（符号链接断链、权限问题、路径超长）。扩大 catch 范围到 `OSError`，映射为 `input_path_rejected`。

---

### 4. [HIGH] 客户端切片代替 SQL LIMIT — 数据量增长后浪费内存

**位置：** `src/mke/interfaces/mcp_contract.py:384`（`search_library` 函数）

**问题：**

```python
for match in engine.search(normalized_query)[:limit]:
```

`KnowledgeEngine.search()` 没有 `limit` 参数，FTS5 查询返回全部匹配行，物化为 `SearchResult` 对象后再 Python 切片。limit 上限是 20 所以浪费有限，但 SQL 查询仍扫描全表。

**修复：** 给 `KnowledgeEngine.search()` 和 `SQLiteStore.search()` 加 `limit` 参数，下推到 SQL `LIMIT` 子句。

在 `src/mke/application/__init__.py`：

```python
def search(self, query: str, limit: int | None = None) -> list[SearchResult]:
    return self._store.search(query, limit=limit)
```

在 `src/mke/adapters/sqlite/__init__.py` 的 `search` 方法末尾加 `LIMIT ?`：

```python
if limit is not None:
    rows = cursor.execute(sql + " LIMIT ?", params + [limit]).fetchall()
else:
    rows = cursor.execute(sql, params).fetchall()
```

`mcp_contract.search_library` 调用改为 `engine.search(normalized_query, limit=limit)`，去掉 `[:limit]` 切片。`limit` 在合约层已验证为 1..20，直接传递即可。

---

## 中低严重度问题（实现时顺手修复，不需要单独跟踪）

| # | 问题 | 位置 |
|---|------|------|
| M1 | `ingest_file` 对空字符串路径返回 "must be a file"，实际应是无效路径 | `_resolve_allowed_file` |
| M2 | 操作指南缺少 MCP 客户端配置示例（Claude Code JSON config） | `docs/how-to/use-mke-mcp.md` |
| M3 | CLI 和 MCP 工具命名不对称未说明（`ingest` vs `ingest_file`，`search` vs `search_library`） | `docs/how-to/use-mke-mcp.md` |
| M4 | README 中 MCP 提及无超链接指向操作指南 | `README.md`, `README_CN.md` |
| M5 | 入门教程未更新 MCP 引用（仍称 MCP 为"非目标"） | `docs/tutorials/getting-started.md` |
| M6 | ingest 失败的错误响应不包含 `run_id`（失败的 Run 仍存在于数据库中，但 Agent 无法检查） | `mcp_contract.py` `ingest_file` |
| M7 | FastMCP 默认 `log_level='INFO'` 向 stderr 打印启动日志；若 Agent 将 stderr 视为错误可能造成困扰 | `mcp_server.py` |
| M8 | `mke mcp --help` 输出未在 CLI 参考文档中说明 | `docs/reference/cli.md` |
| M9 | 操作指南示例流程应包含 `get_run` 步骤 | `docs/how-to/use-mke-mcp.md` |
| M10 | CLI 数据库兼容性未记录（通过 `mke ingest` 创建的现有数据库可直接与 `mke mcp --db` 一起使用） | `docs/how-to/use-mke-mcp.md` |

---

## 实现序列（推荐 Codex 执行顺序）

1. **修复 T1+T2** — 将 `Engine()` 移到 try 内部 + 添加 `_safe_tool` 包装器。这两个是阻塞性缺陷。
2. **添加缺失的测试（T3）** — 4 个新测试函数 + `_resolve_allowed_file` 的 `OSError` catch。
3. **实现 SQL LIMIT（T4）** — 向 `engine.search()` 和 `SQLiteStore.search()` 添加 `limit` 参数。
4. **继续 Task 1-6** — 按计划文件正常实现。
5. **文档收口** — Task 5 期间顺手修 M1-M10。
6. **验证** — 按计划 Task 6 运行 `pytest -q`、`ruff check`、`pyright`、`uv build`、`mke demo --verify`。

---

## 审查通过状态

| 审查 | 状态 | 发现数 |
|------|------|--------|
| CEO（战略与范围） | 通过 | 5（0 个未解决） |
| Eng（架构与实现） | 通过 | 14（0 个未解决） |
| DX（开发者体验） | 通过 | 18（0 个未解决） |
| 设计（UI） | 已跳过 | 无 UI 范围 |

**判决：批准实施。** 4 个关键/高危问题是实现细节，不涉及架构返工。所有问题都在 T1-T4 中可修复。计划的分层架构（纯合约 → FastMCP → CLI）正确，允许 Codex 直接按 `implementation.md` 的 Task 1-6 执行，同时将上述修复纳入。

---

## 非范围（已确认）

- `ask_library` → C2
- HTTP / REST API
- 工作区 UI
- 认证/授权
- 托管/多工作节点运行时
- OCR、任意视频、真实语音转录
- 外部模型调用
- 跨工具调用的长寿命共享 SQLite 连接
