# Multimodal Knowledge Engine

[English](./README.md)

Multimodal Knowledge Engine 是一个本地优先、可被 Agent 调用的 Evidence 引擎，用于导入、检索和问答文档与媒体资料。

## 当前状态

仓库现在已有确定性的本地跨模态 proof：`mke demo --verify` 会导入 text-layer PDF 和短本地视频，证明失败的 PDF reprocess 不会改变 active Publication，重试 validated candidate 路径，并验证 page Evidence 与 timestamp Evidence 都只来自 active Search。Ask、MCP、HTTP 和 workspace 尚未实现。

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

开发流程见 [CONTRIBUTING.md](./CONTRIBUTING.md)，安全漏洞报告方式见 [SECURITY.md](./SECURITY.md)。

## 开发状态

主要本地 proof 是：

```bash
uv sync --locked
uv run mke demo --verify
```

开发检查命令是：

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
```

底层 ingest 和 Search 命令仍可用：

```bash
uv run mke --db .tmp/mke.sqlite ingest tests/fixtures/pdf/text-layer.pdf
uv run mke --db .tmp/mke.sqlite ingest tests/fixtures/video/short-audio.mp4
uv run mke --db .tmp/mke.sqlite search trustworthy
uv run mke --db .tmp/mke.sqlite search timestamp
uv run mke --db .tmp/mke.sqlite run get <run_id>
```

无参数 `mke` 命令仍报告 bootstrap 状态以保持兼容。

## License

MIT，详见 [LICENSE](./LICENSE)。
