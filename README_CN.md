# Multimodal Knowledge Engine

[English](./README.md)

Multimodal Knowledge Engine 是一个本地优先、可被 Agent 调用的 Evidence 引擎，用于导入、检索和问答文档与媒体资料。

## 当前状态

仓库现在已有确定性的本地 product proof：`mke proof run` 会在临时 SQLite workspace 中执行有序的 CLI-equivalent 和 MCP contract cases。它会导入 PyMuPDF text-layer PDF 和短本地视频，证明失败的 PDF reprocess 不会改变 active Publication，并验证 page Evidence 与 timestamp Evidence 都只来自 active Search 和 evidence-only Ask。
首个 Agent-facing interface 是本地 stdio MCP server，支持 ingest、Run 检查和 active Evidence Search。
现在 C2 已加入 evidence-only Ask；HTTP 和 workspace 尚未实现。

E1 另行提供确定性的离线 retrieval baseline：
`mke eval retrieval --manifest tests/fixtures/retrieval-eval-v1.json`。它会在两个全新的
workspace 中，用 24 个冻结 query 评估两个公开英文 PDF 和现有 sidecar-backed 短视频。
`status=passed` 只表示 evaluation integrity 通过；`quality_gate=none` 表示观测到的
Recall、MRR、no-hit 与 Ask refusal 不是产品质量门槛。

E2 新增 numeric retrieval protocol：
`mke eval retrieval-numeric --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json`。
`numeric-grouping-v1` candidate 通过了冻结的 development、公开 holdout 和完整 E1
门槛，使 E1 Recall@1 从 `0.875000` 提升到 `0.937500`。它继续作为主要 rollback，切换
不需要数据库 migration 或 index rebuild。

E3-A 新增独立的中文 retrieval 观测面，用于记录当前 FTS5 lexical retrieval 行为。它在
隔离的 development 与公开 holdout corpus 上冻结 5 个公开 text-layer PDF fixture、
48 个 protocol-owned query 和 1,680 条已审阅 query-page judgment。canonical observation
记录 Recall@5 `0.295455`、nDCG@10 `0.277279`，以及 25 个
`compiled_query_empty` miss。这些是 baseline observation，不是产品质量门槛，也不表示
已具备通用中文检索能力。

E3-B 新增 off-default 的 `cjk-trigram-overlap-v1` 对比候选：
`mke eval retrieval-cjk-lexical --protocol tests/fixtures/retrieval-chinese-v1/protocol.json --candidate cjk-trigram-overlap-v1`。
该候选只在当前 `numeric-grouping-v1` 编译为空时，进入 evaluation-only SQLite FTS5
`trigram` projection fallback。canonical comparison 记录 Recall@5 `0.659091`、nDCG@10
`0.610619`，冻结的 development 与 holdout gates 均通过。

E3-F 将 `cjk-active-scan-overlap-v1` 提升为默认 owner-startup strategy。compiled non-empty query 始终
走 active FTS5，包括 FTS zero-hit；只有 eligible compiled-empty CJK query 才扫描 SQLite
domain truth 中 active Publication 的 Evidence。runtime 不创建 persistent CJK projection，
MCP tool schema 也没有 request-time strategy override。Task 0.5 的 runtime evidence 为
Recall@5 `0.659091`、nDCG@10 `0.619152`。HTTP、UI、vector search、hybrid retrieval、
RRF、reranker 和 query rewrite 仍不在范围内。

E3-C PR 1 新增 comparison-only 的本地 embedding 前置证明，候选为
`qwen3-embedding-0.6b-exact-v1`，模型为 `Qwen/Qwen3-Embedding-0.6B`，revision 为
`97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`。它证明 optional package boundary、
cache-only prepare/doctor lifecycle、exact-cosine reference，以及 Python 3.12/3.13
installed-wheel compatibility。它不改变正常 Search、Ask、MCP 或 runtime default；E3-C
dense comparison scoring、future API adapter、fusion、reranking 和 runtime promotion 仍是独立
evidence-gated 工作。

这个 proof 验证的是生命周期边界，不代表已经支持广泛媒体处理。当前不包含扫描 PDF OCR、任意视频处理、托管协调或外部 provider 调用。D3-A 增加了 trusted-local `LocalCommandTranscriptProvider`；D3-B 增加了供 CLI 和 owner-started MCP 显式选择的 optional cache-only faster-whisper runtime。`mke proof run` 与 `mke demo --verify` 仍保持 sidecar-backed、deterministic；`mke proof transcription-run` 使用可再分发的 spoken fixture 证明真实本地 ASR，`scripts/transcription_deployment_proof.py` 则证明隔离安装 wheel 后的 CLI 与 stdio MCP SDK 流程。只有显式 preparation 可以下载模型，doctor、ingest、proof 和 MCP 正常运行均为 cache-only。

PDF intake 使用位于 `src/mke/adapters/pdf/` 边界内的 PyMuPDF，并通过 `mke ingest`、`mke run get`、MCP `ingest_file` 和 MCP `get_run` 暴露 `PdfIntakeReport`。PyMuPDF 许可边界和未来 sidecar 替换路径见 [ADR-0004](./docs/decisions/0004-pymupdf-pdf-intake-adapter.md)。MCP 会在打开 extractor 前拒绝超过 100 MB 的 PDF 输入。

C2 Ask 只返回 Evidence：`ask_library` 和 `mke ask` 会在 active Search 命中问题词时返回带页码或时间戳的 cited Evidence；没有命中时返回 `insufficient_evidence`。当前 slice 不调用 LLM，也不生成自然语言答案。

## 已验证产品切片

当前经过验证的产品切片会让 text-layer PDF 和文档化的短本地视频 fixture 经过可观察 Run，只发布成功输出，并返回带稳定页码或时间戳的 Evidence。真实本地转录 proof 已在 Darwin 25.4.0 arm64、Python 3.13.12 上验证；转录的隔离 wheel-installed CLI/MCP proof 已使用 Python 3.12 验证。numeric retrieval promotion 包含 Python 3.12/3.13 的隔离 installed-wheel CLI/MCP proof。

## 架构原则

- 使用项目自有领域模型与 ports。
- SQLite 保存领域事实。
- 检索索引是可重建投影。
- Asset 与 Artifact 不可变且内容寻址。
- Search 与 Ask 只读取 active Publication。
- Pilot 使用单机单 owner process 与单 worker。

详见[架构说明](./docs/explanation/architecture.md)和 [ADR-0001](./docs/decisions/0001-local-first-pilot-architecture.md)。

## 文档

从 [docs/README.md](./docs/README.md) 开始。要直接验证当前 proof，见
[Run The Local Product Proof](./docs/how-to/run-local-product-proof.md)。要连接本地 Agent，见
[Use MKE As A Local MCP Server](./docs/how-to/use-mke-mcp.md)；本地转录准备与 proof 见
[Use Local Transcription](./docs/how-to/use-local-transcription.md)；记录当前 retrieval
行为见 [Run Retrieval Evaluation](./docs/how-to/run-retrieval-evaluation.md)。批准后的
numeric candidate 对比流程见
[Evaluate The Numeric Retrieval Candidate](./docs/how-to/evaluate-numeric-retrieval.md)。
当前中文 lexical failure profile 见
[Run The Chinese Retrieval Evaluation](./docs/how-to/run-chinese-retrieval-evaluation.md)。
E3-C PR 1 本地 embedding 前置准备与验证见
[Prepare Local Embeddings](./docs/how-to/prepare-local-embeddings.md)。
实施历史保存在 `docs/superpowers/`；长期架构决策保存在 `docs/decisions/`。

开发流程见 [CONTRIBUTING.md](./CONTRIBUTING.md)，安全漏洞报告方式见 [SECURITY.md](./SECURITY.md)。

## 开发状态

主要本地 proof 是：

```bash
uv sync --locked
uv run mke proof run
uv run mke proof run --json
uv run mke eval retrieval --manifest tests/fixtures/retrieval-eval-v1.json
uv run mke eval retrieval-numeric \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json
uv sync --locked &&
uv run mke eval retrieval-chinese \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json
uv run mke eval retrieval-cjk-lexical \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --candidate cjk-trigram-overlap-v1
```

`mke demo --verify` 仍作为 compatibility proof 可用，并保留 phase-oriented 输出。

可选的真实转录 proof 需要安装 `transcription` extra，并提前准备精确 model revision。请将
`MKE_MODEL_CACHE` 设置为仓库外、由 operator 管理的目录：

```bash
HF_HUB_OFFLINE=1 uv run mke proof transcription-run \
  --fixture tests/fixtures/video/spoken-evidence.mp4 \
  --model-cache "$MKE_MODEL_CACHE" \
  --json
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
uv run mke --db .tmp/mke.sqlite ask "publication active"
uv run mke --db .tmp/mke.sqlite run get <run_id>
uv run mke --db .tmp/mke.sqlite mcp --allowed-root .
uv run mke --db .tmp/mke.sqlite --retrieval-query-policy current search "410000 withdrawals"
uv run mke --db .tmp/mke.sqlite --retrieval-strategy cjk-active-scan-overlap-v1 search "蓝湖缓存服务 不完整索引"
```

无参数 `mke` 命令仍报告 bootstrap 状态以保持兼容。

## License

MIT，详见 [LICENSE](./LICENSE)。
