# Multimodal Knowledge Engine

[English](./README.md)

Multimodal Knowledge Engine 是一个本地优先、可被 Agent 调用的 Evidence 引擎，用于导入、检索和问答文档与媒体资料。

## 当前状态

仓库处于 bootstrap 阶段，目前只包含已批准的 Pilot 架构、文档治理与交付流程。PDF 导入、视频处理、Search、Ask、MCP 和 workspace 尚未实现。

## Pilot 目标

首个经过验证的产品切片将让一个 PDF 和一个短视频经过可观察 Run，只发布成功输出，并返回带稳定页码或时间戳的 Evidence。

## 架构原则

- 使用项目自有领域模型与 ports。
- SQLite 保存领域事实。
- 检索索引是可重建投影。
- Asset 与 Artifact 不可变且内容寻址。
- Search 与 Ask 只读取 active Publication。
- Pilot 使用单机单 owner process 与单 worker。

详见[架构说明](./docs/explanation/architecture.md)和 [ADR-0001](./docs/decisions/0001-local-first-pilot-architecture.md)。

## 文档

从 [docs/README.md](./docs/README.md) 开始。批准后的实施历史保存在 `docs/superpowers/`；长期架构决策保存在 `docs/decisions/`。

## 开发状态

bootstrap 开发基线已可用：

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run pyright
uv run mke
```

当前 `mke` 命令只报告 bootstrap 状态，产品工作流仍未实现。
