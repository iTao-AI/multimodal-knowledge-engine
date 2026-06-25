# Chinese Retrieval Baseline Implementation Plan

**Status:** Completed locally on `codex/e3a-chinese-retrieval-baseline`; stopped before push/PR.

**Completion:** Tasks 1–11 were executed. The inline checkboxes below are retained as the approved
historical execution procedure, not as pending work.

**Review follow-up:** Six implementation findings returned across two targeted review passes were
verified and remediated with TDD. Canonical environment validation now compares the artifact
against an exact repository-derived contract sourced from `pyproject.toml`, the CI Python matrix,
`uv.lock`, and the approved SQLite rank profile; well-formed but impossible version mutations
remain fail-closed while the same artifact validates under supported Python 3.12 and 3.13
runtimes. Rank proof requires real production-equivalent SQL traces, complete result ordering, a
non-empty predeclared probe, and Search-prefix equality. The canonical report also records enough
scorer evidence for the artifact validator to independently recompute every non-empty query's
result count, ordered Evidence identity digest, and rank/`bm25()` score-pair digest without
re-ingestion. Artifact recording independently recomputes miss classifications while enforcing
partition locator inventory and strict JSON scalar types; qrel `review_date` is locked to the
approved `2026-06-25` record. The E1, E2, and E3-A canonical artifacts were refreshed through the
durable recovery journal with semantic observations unchanged.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic offline E3-A Chinese retrieval baseline that freezes five approved
text-layer PDFs, 48 development/holdout queries, graded page qrels, mechanically observed
miss-symptom classifications, and a canonical artifact without changing runtime retrieval
behavior.

**Architecture:** A new strict `mke.retrieval_chinese_protocol.v1` protocol sits beside E1 rather
than widening the binary E1 schema. The evaluator snapshots exact fixture bytes, keeps
development and holdout corpora isolated, ingests each partition through the normal
`KnowledgeEngine` in two fresh workspaces per partition, reads active Evidence from SQLite domain truth through
an evaluation-only diagnostic port, independently verifies the FTS projection, executes the
existing `numeric-grouping-v1` strategy, computes graded metrics, verifies FTS5 `rank` against
`bm25()` for every non-empty compiled query, classifies every direct-Evidence miss using compiled
clause semantics, and records a content-addressed artifact. Existing Search, Ask, Publication,
E1, E2, CLI, MCP, and runtime defaults remain unchanged.

**Tech Stack:** Python 3.12/3.13, stdlib dataclasses/JSON/hashlib/math/tempfile, SQLite FTS5,
PyMuPDF through the existing adapter, pytest, argparse, GitHub Actions.

**Approved design:**
`docs/superpowers/specs/2026-06-25-chinese-hybrid-retrieval-evaluation-design.md`

**Baseline verified on 2026-06-25:**

```text
uv run pytest -q      -> 669 passed, 1 skipped, 5 warnings
uv run ruff check .   -> passed
uv run pyright        -> 0 errors, 0 warnings
```

**Implementation boundary:** E3-A records the current lexical failure modes. Do not add CJK
tokenization, a second FTS projection, embeddings, `sqlite-vec`, vector search, RRF, reranking,
query rewrite, Passage/chunk segmentation, OCR, HTTP, UI, model downloads, new runtime strategy
selectors, or Publication projection activation changes.

---

## Locked Decisions

### CLI And Schema

```text
mke eval retrieval-chinese \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json

mke eval retrieval-chinese \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --json
```

Use these schema identifiers:

```text
mke.retrieval_chinese_protocol.v1
mke.retrieval_chinese_report.v1
mke.retrieval_chinese_baseline.v1
```

Use this benchmark scope:

```text
small_public_chinese_page_corpus
```

The evaluation command returns `0` when the current run's protocol, fixture, qrel, ingestion,
active-Evidence/FTS projection, rank, determinism, and rendering integrity pass. It does not claim
that the checked-in canonical artifact has been validated; artifact record/validate commands are
separate operations with their own `0` success, `1` integrity failure, and `2` usage-error exits.
Low Recall, MRR, nDCG, unanswerable no-hit, or Ask outcome-rate values do not cause exit `1`.

### Public Holdout Governance And E3-B Start Rule

E3-A records the current baseline across both splits. E3-B and later candidate stages must freeze
candidate identity, revision, parameters, development gates, and promotion gates before observing
holdout results. Tuning uses development only. Each frozen candidate receives one canonical
holdout observation; the required second workspace proves determinism and is not a second tuning
attempt. Changing candidate code, parameters, gates, qrels, or fixture bytes after holdout
observation marks that observation contaminated for promotion.

Development queries execute only against the 34-page development corpus. Holdout queries execute
only against the 36-page holdout corpus. Each partition is duplicated solely for determinism, so
E3-A uses four temporary SQLite workspaces in total.

E3-B is eligible only when E3-A integrity passes, qrel review has `review_status=complete`, and at
least one development answerable grade-`2` miss has `compiled_query_empty`. E3-B may target
deterministic CJK lexical compilation/index coverage only. Other miss symptoms do not authorize
semantic retrieval, query rewrite, segmentation, or a larger candidate.

### Corpus Audit Already Completed

The planning window downloaded each approved URL exactly once to `/tmp/mke-e3a-corpus`, did not
copy any file into the repository, and verified these identities:

| Partition | Repository path | Source URL or origin | Source temporary path | Pages | Bytes | SHA-256 |
|---|---|---|---|---:|---:|---|
| development | `development/ub-service-core-2.0-zh.pdf` | `https://www.openeuler.org/projects/ub-service-core/white-paper/UB-Service-Core-SW-Arch-RD-2.0-zh.pdf` | `/tmp/mke-e3a-corpus/ub-service-core-2.0-zh.pdf` | 26 | 1,168,641 | `13e8f1da824de892931653e17df2a8b20f77fe84b2a7472b13113405efbf296d` |
| development | `development/adversarial.pdf` | repository-authored fixture | `/tmp/mke-e3a-corpus/development-adversarial-spaced.pdf` | 8 | 4,350 | `be3b88352b0a80d6d165de146ff81be224b706d3eb3721d969266e64505af8dd` |
| holdout | `holdout/copyright-law-2020.pdf` | `https://scjgj.cq.gov.cn/zt_225/cjscjz/zcfg/flv/202308/P020230822697998631731.pdf` | `/tmp/mke-e3a-corpus/copyright-law-2020.pdf` | 14 | 182,479 | `e1217f1df0bb98586a883819505f17a29140fb114ce5f1a444ea0a60d22c9d2b` |
| holdout | `holdout/administrative-compulsion-law-2011.pdf` | `https://www.safe.gov.cn/heilongjiang/file/file/20190426/a520a4e30df34b8bafd708231731dab9.pdf` | `/tmp/mke-e3a-corpus/administrative-compulsion-law-2011.pdf` | 14 | 198,629 | `80d1a49a1641f73f53df7f2cfe008b4f8e8419a538f37d183f9758ec52e90d0d` |
| holdout | `holdout/adversarial.pdf` | repository-authored fixture | `/tmp/mke-e3a-corpus/holdout-adversarial-spaced.pdf` | 8 | 4,399 | `52d2319515195c7a0b8572f4a6f86eec6856cb189a24f3272c2792ad5fe76924` |

The real source page-character counts from `page.get_text("text", sort=True)` are:

```python
{
    "ub-service-core-2.0-zh.pdf": (
        77, 410, 4089, 388, 1864, 764, 418, 1231, 694, 711, 651, 683, 463,
        783, 303, 539, 635, 400, 478, 634, 625, 516, 818, 429, 939, 870,
    ),
    "copyright-law-2020.pdf": (
        874, 917, 929, 1027, 1006, 992, 810, 920, 942, 949, 980, 1028,
        1046, 422,
    ),
    "administrative-compulsion-law-2011.pdf": (
        490, 826, 665, 745, 803, 806, 802, 746, 816, 776, 854, 781, 747, 758,
    ),
}
```

The generated fixture page-character counts are:

```python
{
    "development/adversarial.pdf": (60, 41, 59, 57, 34, 31, 32, 32),
    "holdout/adversarial.pdf": (46, 43, 46, 44, 33, 30, 68, 47),
}
```

Redistribution records:

- openEuler document page 2 states that use is governed by
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode.txt).
- The two law texts are laws or official state documents covered by Article 5 of the Copyright
  Law of the People's Republic of China.
- The generated fixtures were authored for this repository.

If any temporary source is missing or differs from the exact identity above, stop and request a
new, exact download/generation authorization. Do not redownload, regenerate, substitute, or accept
new bytes automatically.

### Generated Fixture Text

`development/adversarial.pdf` has exactly these eight page texts:

1. `星河调度平台将任务检查间隔设为 45 秒。该策略自 2026 年 3 月 15 日起生效，单次最多处理 240 个任务。`
2. `星河归档平台每 45 分钟执行一次历史清理。该任务只删除超过 90 天的临时文件。`
3. `DataBridge X7 网关负责将边缘事件写入中心消息队列，并使用 FlowToken A-731 标识路由批次。`
4. `DataBridge X9 网关只负责读取设备状态，不写入中心消息队列，也不使用 FlowToken A-731。`
5. `蓝湖缓存服务在节点失联时保留最近一次有效快照，并拒绝发布不完整索引。`
6. `蓝湖缓存服务在磁盘空间不足时进入只读模式，但不会切换活动索引。`
7. `青岚分析引擎只有在来源校验通过且索引构建完成后，才切换活动版本。`
8. `青岚分析引擎在来源校验失败时记录告警；索引构建任务保持候选状态。`

`holdout/adversarial.pdf` has exactly these eight page texts:

1. `海岳审计终端 AuditNode R5 的日志保留期为 180 天，超过期限后进入离线归档。`
2. `海岳监控终端 AuditNode R3 的指标保留期为 18 天，超过期限后直接删除。`
3. `云舟路由服务使用 RouteKey ZH-2048 标识跨区域路由，并拒绝未知租户的数据包。`
4. `云舟存储服务使用 StorageKey ZH-2048 标识归档批次，不参与跨区域路由。`
5. `松涛归档器只有在主副本校验一致且审批状态为通过时，才发布归档索引。`
6. `松涛归档器在审批未通过时保留候选索引，并记录主副本校验结果。`
7. `北辰采集代理 PolicySync V2 每 12 秒上报一次心跳，单批最多 320 条记录，自 2025 年 11 月 8 日起生效。`
8. `北辰同步代理 PolicySync V1 每 12 分钟同步一次配置，单批最多 32 条记录。`

### Query And Qrel Lock

Protocol categories:

```python
ChineseQueryCategory = Literal[
    "chinese_exact_lexical",
    "chinese_word_boundary",
    "proper_noun_mixed",
    "number_date_unit",
    "semantic_paraphrase",
    "multi_condition",
    "ranking_hard_negative",
    "unanswerable",
]
```

Qrel notation below is `<document-id>:p<page>=<grade>`. Grade `2` is direct Evidence, grade `1`
is supporting Evidence, and grade `0` is a deliberate distractor.

Document IDs:

```text
ub-service-core
development-adversarial
copyright-law
administrative-compulsion-law
holdout-adversarial
```

#### Development Queries

| ID | Category | Query | Qrels |
|---|---|---|---|
| `zh-dev-exact-01` | `chinese_exact_lexical` | `MemFabric 内存统一编址 数据访问` | `ub-service-core:p13=2`, `ub-service-core:p14=1` |
| `zh-dev-exact-02` | `chinese_exact_lexical` | `HCOM 高带宽 低延迟 通信框架` | `ub-service-core:p17=2`, `ub-service-core:p16=1`, `ub-service-core:p26=0` |
| `zh-dev-exact-03` | `chinese_exact_lexical` | `UBS IO 全局数据读写缓存` | `ub-service-core:p19=2`, `ub-service-core:p20=1`, `ub-service-core:p6=0` |
| `zh-dev-exact-04` | `chinese_exact_lexical` | `蓝湖缓存服务 不完整索引` | `development-adversarial:p5=2`, `development-adversarial:p6=0` |
| `zh-dev-boundary-01` | `chinese_word_boundary` | `高阶服务软件架构分成几层` | `ub-service-core:p8=2`, `ub-service-core:p7=1` |
| `zh-dev-boundary-02` | `chinese_word_boundary` | `共享内存服务由哪个组件提供` | `ub-service-core:p13=2`, `ub-service-core:p14=1` |
| `zh-dev-boundary-03` | `chinese_word_boundary` | `来源校验通过且索引构建完成` | `development-adversarial:p7=2`, `development-adversarial:p8=1` |
| `zh-dev-mixed-01` | `proper_noun_mixed` | `UBS Engine 负责什么` | `ub-service-core:p10=2`, `ub-service-core:p11=1`, `ub-service-core:p12=1` |
| `zh-dev-mixed-02` | `proper_noun_mixed` | `RoUB 如何迁移 RDMA 应用` | `ub-service-core:p16=2`, `ub-service-core:p18=1` |
| `zh-dev-mixed-03` | `proper_noun_mixed` | `DataBridge X7 网关写入什么队列` | `development-adversarial:p3=2`, `development-adversarial:p4=0` |
| `zh-dev-number-01` | `number_date_unit` | `应用加速 30 50 百分比` | `ub-service-core:p8=2` |
| `zh-dev-number-02` | `number_date_unit` | `3T 以上超大规模虚机` | `ub-service-core:p12=2` |
| `zh-dev-number-03` | `number_date_unit` | `45秒 2026年3月15日 240个任务` | `development-adversarial:p1=2`, `development-adversarial:p2=0` |
| `zh-dev-semantic-01` | `semantic_paraphrase` | `哪个模块把剩余内存组成全局 IO 缓存池` | `ub-service-core:p11=2`, `ub-service-core:p19=0`, `ub-service-core:p20=0` |
| `zh-dev-semantic-02` | `semantic_paraphrase` | `怎样避免虚机因节点内存不足退出` | `ub-service-core:p12=2` |
| `zh-dev-semantic-03` | `semantic_paraphrase` | `哪个组件提供多副本强一致低延迟内存存储` | `ub-service-core:p15=2`, `ub-service-core:p13=1` |
| `zh-dev-semantic-04` | `semantic_paraphrase` | `节点断开后如何防止发布半成品索引` | `development-adversarial:p5=2`, `development-adversarial:p6=0` |
| `zh-dev-multi-01` | `multi_condition` | `哪个通信框架同时屏蔽 RDMA TCP URMA SHM 低级 API 差异` | `ub-service-core:p17=2`, `ub-service-core:p16=1`, `ub-service-core:p26=0` |
| `zh-dev-multi-02` | `multi_condition` | `哪个服务同时支持共享内存和池化内存` | `ub-service-core:p9=2`, `ub-service-core:p13=1` |
| `zh-dev-multi-03` | `multi_condition` | `什么条件下青岚分析引擎切换活动版本` | `development-adversarial:p7=2`, `development-adversarial:p8=1` |
| `zh-dev-hard-01` | `ranking_hard_negative` | `弱一致缓存和强一致存储分别由哪些组件提供` | `ub-service-core:p15=2`, `ub-service-core:p13=1`, `ub-service-core:p14=0` |
| `zh-dev-hard-02` | `ranking_hard_negative` | `哪个星河任务每45秒检查一次` | `development-adversarial:p1=2`, `development-adversarial:p2=0` |
| `zh-dev-unanswerable-01` | `unanswerable` | `灵衢系统是否支持量子密钥分发` | none |
| `zh-dev-unanswerable-02` | `unanswerable` | `DataBridge X7 是否提供生物识别登录` | none |

#### Holdout Queries

| ID | Category | Query | Qrels |
|---|---|---|---|
| `zh-hold-exact-01` | `chinese_exact_lexical` | `著作权即版权` | `copyright-law:p14=2` |
| `zh-hold-exact-02` | `chinese_exact_lexical` | `查封扣押期限不得超过三十日` | `administrative-compulsion-law:p6=2` |
| `zh-hold-exact-03` | `chinese_exact_lexical` | `信息网络传播权` | `copyright-law:p3=2`, `copyright-law:p14=1` |
| `zh-hold-exact-04` | `chinese_exact_lexical` | `冻结决定书三日内交付` | `administrative-compulsion-law:p7=2` |
| `zh-hold-boundary-01` | `chinese_word_boundary` | `受委托创作作品未约定归属` | `copyright-law:p5=2` |
| `zh-hold-boundary-02` | `chinese_word_boundary` | `教育与强制相结合` | `administrative-compulsion-law:p2=2` |
| `zh-hold-boundary-03` | `chinese_word_boundary` | `主副本校验一致且审批通过` | `holdout-adversarial:p5=2`, `holdout-adversarial:p6=1` |
| `zh-hold-mixed-01` | `proper_noun_mixed` | `AuditNode R5 日志保留期` | `holdout-adversarial:p1=2`, `holdout-adversarial:p2=0` |
| `zh-hold-mixed-02` | `proper_noun_mixed` | `RouteKey ZH-2048 跨区域路由` | `holdout-adversarial:p3=2`, `holdout-adversarial:p4=0` |
| `zh-hold-mixed-03` | `proper_noun_mixed` | `PolicySync V2 何时上报心跳` | `holdout-adversarial:p7=2`, `holdout-adversarial:p8=0` |
| `zh-hold-number-01` | `number_date_unit` | `30日 查封扣押 延长期限` | `administrative-compulsion-law:p6=2`, `administrative-compulsion-law:p7=0` |
| `zh-hold-number-02` | `number_date_unit` | `1倍 5倍 故意侵权赔偿` | `copyright-law:p12=2` |
| `zh-hold-number-03` | `number_date_unit` | `12秒 320条 2025年11月8日` | `holdout-adversarial:p7=2`, `holdout-adversarial:p8=0` |
| `zh-hold-semantic-01` | `semantic_paraphrase` | `非强制手段能达到目的时怎么办` | `administrative-compulsion-law:p2=2` |
| `zh-hold-semantic-02` | `semantic_paraphrase` | `查封扣押保管费用由谁承担` | `administrative-compulsion-law:p6=2` |
| `zh-hold-semantic-03` | `semantic_paraphrase` | `委托作品没有合同约定归谁` | `copyright-law:p5=2` |
| `zh-hold-semantic-04` | `semantic_paraphrase` | `版权和著作权是不是同一个概念` | `copyright-law:p14=2` |
| `zh-hold-multi-01` | `multi_condition` | `冻结金额应当相当且不得重复冻结` | `administrative-compulsion-law:p7=2`, `administrative-compulsion-law:p8=1` |
| `zh-hold-multi-02` | `multi_condition` | `合理使用作品时必须满足哪些限制` | `copyright-law:p6=2`, `copyright-law:p7=1` |
| `zh-hold-multi-03` | `multi_condition` | `松涛归档器发布索引需要同时满足什么条件` | `holdout-adversarial:p5=2`, `holdout-adversarial:p6=1` |
| `zh-hold-hard-01` | `ranking_hard_negative` | `延长查封扣押期限需要什么程序` | `administrative-compulsion-law:p6=2`, `administrative-compulsion-law:p7=0`, `administrative-compulsion-law:p8=0` |
| `zh-hold-hard-02` | `ranking_hard_negative` | `哪个北辰代理每12秒上报心跳` | `holdout-adversarial:p7=2`, `holdout-adversarial:p8=0` |
| `zh-hold-unanswerable-01` | `unanswerable` | `著作权法是否要求区块链存证使用国密算法` | none |
| `zh-hold-unanswerable-02` | `unanswerable` | `AuditNode R5 是否支持人脸识别` | none |

The protocol keeps `zh-dev-exact-02` as a named smoke probe, but the evaluator verifies FTS5
`rank` versus `bm25()` for every non-empty compiled query in all four workspaces.

---

## File Map

### New Evaluation Files

- `src/mke/evaluation/chinese_protocol.py`: strict protocol DTOs, graded qrels, fixture
  validation, and immutable snapshot copy.
- `src/mke/evaluation/graded_metrics.py`: pure graded metrics and category aggregates.
- `src/mke/evaluation/chinese_diagnostics.py`: compiled-query diagnostics and deterministic
  miss-symptom classification.
- `src/mke/evaluation/chinese_report.py`: E3-A result/report DTOs and human/JSON rendering.
- `src/mke/evaluation/chinese_runner.py`: partition-isolated four-workspace orchestration using normal ingest,
  current Search, current Ask, active Evidence, rank verification, and determinism checks.
- `src/mke/evaluation/chinese_artifact.py`: canonical artifact recording and independent
  validation.
- `src/mke/evaluation/artifact_refresh.py`: generate E1, E2, and E3-A artifact updates in a
  durable transaction directory, validate the complete set, then replace targets with a
  crash-recovery journal and checksum-verified rollback.
- `src/mke/evaluation/diagnostic_ports.py`: evaluation-only active Evidence and FTS projection
  read models; no public domain or `KnowledgeEngine` facade expansion.
- `src/mke/evaluation/baseline.py`: add a source-identity-only refresh command that preserves and
  revalidates the historical E1 observation.
- `src/mke/evaluation/numeric_comparison.py`: add a scope-fence-only refresh command that
  preserves and revalidates the E2 protocol semantics.

### Modified Product Files

- `src/mke/adapters/sqlite/__init__.py`: implement the evaluation diagnostic port by enumerating
  active Evidence from `sources -> publications -> evidence`, separately enumerating the FTS
  projection, and observing `rank` versus `bm25()` with production-equivalent filtering/order.
- `src/mke/evaluation/__init__.py`: export E3-A runner and renderers.
- `src/mke/cli.py`: add `mke eval retrieval-chinese`.

### Fixtures And Artifacts

- `tests/fixtures/retrieval-chinese-v1/protocol.json`
- `tests/fixtures/retrieval-chinese-v1/qrel-adjudication.json`
- `tests/fixtures/retrieval-chinese-v1/README.md`
- `tests/fixtures/retrieval-chinese-v1/development/ub-service-core-2.0-zh.pdf`
- `tests/fixtures/retrieval-chinese-v1/development/adversarial.pdf`
- `tests/fixtures/retrieval-chinese-v1/holdout/copyright-law-2020.pdf`
- `tests/fixtures/retrieval-chinese-v1/holdout/administrative-compulsion-law-2011.pdf`
- `tests/fixtures/retrieval-chinese-v1/holdout/adversarial.pdf`
- `benchmarks/retrieval/retrieval-chinese-v1-baseline.json`

### Tests

- `tests/evaluation/test_chinese_fixture_corpus.py`
- `tests/evaluation/test_chinese_protocol.py`
- `tests/evaluation/test_graded_metrics.py`
- `tests/evaluation/test_chinese_diagnostics.py`
- `tests/evaluation/test_chinese_report.py`
- `tests/evaluation/test_chinese_runner.py`
- `tests/evaluation/test_chinese_artifact.py`
- `tests/evaluation/test_artifact_refresh.py`
- `tests/evaluation/test_chinese_deployment_proof.py`
- `tests/evaluation/test_chinese_measurement.py`
- `tests/evaluation/test_baseline.py`
- `tests/evaluation/test_numeric_comparison.py`
- `tests/adapters/test_sqlite_fts.py`
- `tests/interfaces/test_cli_evaluation.py`

### CI And Documentation

- `.github/workflows/ci.yml`
- `scripts/chinese_retrieval_measurement.py`
- `README.md`
- `README_CN.md`
- `docs/README.md`
- `docs/tutorials/getting-started.md`
- `docs/reference/cli.md`
- `docs/reference/contracts.md`
- `docs/how-to/run-chinese-retrieval-evaluation.md`
- `docs/explanation/architecture.md`
- `docs/superpowers/plans/2026-06-25-chinese-retrieval-baseline-implementation.md`
- `docs/superpowers/reviews/2026-06-25-chinese-retrieval-baseline-autoplan-review.md`
- `docs/superpowers/reviews/2026-06-25-chinese-retrieval-baseline-review.md`

---

### Task 1: Adjudicate And Freeze The Approved Corpus And Protocol

**Files:**
- Create: `tests/evaluation/test_chinese_fixture_corpus.py`
- Create: `tests/fixtures/retrieval-chinese-v1/protocol.json`
- Create: `tests/fixtures/retrieval-chinese-v1/README.md`
- Create: `tests/fixtures/retrieval-chinese-v1/qrel-adjudication.json`
- Create: the five fixture PDFs listed in the File Map.

- [ ] **Step 1: Write the failing fixture identity test**

Create a parameterized test with the exact bytes, checksums, page counts, and character tuples
from **Corpus Audit Already Completed**:

```python
@pytest.mark.parametrize(
    ("relative", "byte_size", "sha256", "page_chars"),
    (
        (
            "development/ub-service-core-2.0-zh.pdf",
            1168641,
            "13e8f1da824de892931653e17df2a8b20f77fe84b2a7472b13113405efbf296d",
            (77, 410, 4089, 388, 1864, 764, 418, 1231, 694, 711, 651, 683,
             463, 783, 303, 539, 635, 400, 478, 634, 625, 516, 818, 429,
             939, 870),
        ),
        (
            "development/adversarial.pdf",
            4350,
            "be3b88352b0a80d6d165de146ff81be224b706d3eb3721d969266e64505af8dd",
            (60, 41, 59, 57, 34, 31, 32, 32),
        ),
        (
            "holdout/copyright-law-2020.pdf",
            182479,
            "e1217f1df0bb98586a883819505f17a29140fb114ce5f1a444ea0a60d22c9d2b",
            (874, 917, 929, 1027, 1006, 992, 810, 920, 942, 949, 980,
             1028, 1046, 422),
        ),
        (
            "holdout/administrative-compulsion-law-2011.pdf",
            198629,
            "80d1a49a1641f73f53df7f2cfe008b4f8e8419a538f37d183f9758ec52e90d0d",
            (490, 826, 665, 745, 803, 806, 802, 746, 816, 776, 854, 781,
             747, 758),
        ),
        (
            "holdout/adversarial.pdf",
            4399,
            "52d2319515195c7a0b8572f4a6f86eec6856cb189a24f3272c2792ad5fe76924",
            (46, 43, 46, 44, 33, 30, 68, 47),
        ),
    ),
)
def test_chinese_corpus_matches_frozen_bytes(
    relative: str,
    byte_size: int,
    sha256: str,
    page_chars: tuple[int, ...],
) -> None:
    path = FIXTURE_ROOT / relative
    assert path.stat().st_size == byte_size
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha256
    with fitz.open(path) as document:
        assert tuple(
            len(page.get_text("text", sort=True)) for page in document
        ) == page_chars
        assert all(page_chars)
```

Add a second test that reads `protocol.json` and asserts:

```python
assert payload["schema_version"] == "mke.retrieval_chinese_protocol.v1"
assert payload["protocol_id"] == "retrieval-chinese-v1"
assert payload["rank_probe_query_id"] == "zh-dev-exact-02"
assert len(payload["documents"]) == 5
assert len(payload["queries"]) == 48
assert Counter(item["split"] for item in payload["queries"]) == {
    "development": 24,
    "holdout": 24,
}
assert Counter(item["category"] for item in payload["queries"]) == {
    "chinese_exact_lexical": 8,
    "chinese_word_boundary": 6,
    "proper_noun_mixed": 6,
    "number_date_unit": 6,
    "semantic_paraphrase": 8,
    "multi_condition": 6,
    "ranking_hard_negative": 4,
    "unanswerable": 4,
}
```

Add a third test for `qrel-adjudication.json`. Require schema
`mke.retrieval_chinese_qrel_adjudication.v1`, all 48 query IDs in protocol order, all five
document IDs, exactly 34 ordered page judgments for each development query, exactly 36 ordered
page judgments for each holdout query, exactly 1,680 query-page judgments, and qrels derived
byte-for-byte from the non-`non_relevant` judgments. Summary counts must be computed from the
judgment records rather than accepted from the JSON.

- [ ] **Step 2: Run the fixture test to verify RED**

Run:

```bash
uv run pytest tests/evaluation/test_chinese_fixture_corpus.py -q
```

Expected: FAIL because the fixture tree and protocol do not exist.

- [ ] **Step 3: Re-verify the approved temporary bytes without network**

Run `shasum -a 256`, `wc -c`, and a PyMuPDF page/character script against all five temporary
files. Require the exact table above. Stop if any source is missing or differs.

- [ ] **Step 4: Copy only the verified bytes into the fixture tree**

Use explicit source/destination pairs. Do not use globs:

```bash
mkdir -p tests/fixtures/retrieval-chinese-v1/development
mkdir -p tests/fixtures/retrieval-chinese-v1/holdout
cp /tmp/mke-e3a-corpus/ub-service-core-2.0-zh.pdf \
  tests/fixtures/retrieval-chinese-v1/development/ub-service-core-2.0-zh.pdf
cp /tmp/mke-e3a-corpus/development-adversarial-spaced.pdf \
  tests/fixtures/retrieval-chinese-v1/development/adversarial.pdf
cp /tmp/mke-e3a-corpus/copyright-law-2020.pdf \
  tests/fixtures/retrieval-chinese-v1/holdout/copyright-law-2020.pdf
cp /tmp/mke-e3a-corpus/administrative-compulsion-law-2011.pdf \
  tests/fixtures/retrieval-chinese-v1/holdout/administrative-compulsion-law-2011.pdf
cp /tmp/mke-e3a-corpus/holdout-adversarial-spaced.pdf \
  tests/fixtures/retrieval-chinese-v1/holdout/adversarial.pdf
```

- [ ] **Step 5: Perform complete partition-corpus page adjudication**

Render or extract every frozen page in stable document/page order. For each answerable query,
review every page in its own corpus partition and record:

- every independently answer-capable page as grade `2`;
- every relevant but insufficient page as grade `1`;
- every deliberate confuser used by the protocol as grade `0`;
- every remaining page as `non_relevant`;
- a bounded public-safe `decision_basis` string of 1-500 characters.

Development queries review the two development documents and 34 pages. Holdout queries review the
three holdout documents and 36 pages. Unanswerable queries receive the same complete inventory and
must contain only `non_relevant`. Stop and return to the planning/review window if adjudication
changes a query, category, direct-answer definition, or fixture. Do not silently patch the
approved qrel table during implementation.

Use this exact adjudication shape:

```json
{
  "schema_version": "mke.retrieval_chinese_qrel_adjudication.v1",
  "protocol_id": "retrieval-chinese-v1",
  "method": "complete_partition_page_review",
  "review_date": "2026-06-25",
  "review_status": "complete",
  "document_page_counts": {
    "ub-service-core": 26,
    "development-adversarial": 8,
    "copyright-law": 14,
    "administrative-compulsion-law": 14,
    "holdout-adversarial": 8
  },
  "query_page_judgment_count": 1680,
  "queries": [
    {
      "query_id": "zh-dev-exact-01",
      "split": "development",
      "decision_basis": "The listed page directly states the requested fact; all other development pages are non-relevant.",
      "judgments": [
        {
          "document_id": "ub-service-core",
          "locator_kind": "page",
          "locator_start": 1,
          "locator_end": 1,
          "grade": "non_relevant"
        }
      ]
    }
  ]
}
```

The example shows one item shape, not a complete query inventory. In the checked-in artifact,
`judgments` contains every page in stable document/page order for that query's partition.
`grade` is exactly `0`, `1`, `2`, or `"non_relevant"`. The validator derives reviewed document
IDs, page counts, answerable counts, qrels, and the global 1,680 total from these records. E3-A
records one completed review and makes no inter-rater disagreement claim.

- [ ] **Step 6: Create the strict protocol and adjudication JSON**

Encode exactly the five document identities and 48 rows from **Query And Qrel Lock**. Each qrel
has this shape:

```json
{
  "document_id": "ub-service-core",
  "locator_kind": "page",
  "locator_start": 13,
  "locator_end": 13,
  "grade": 2
}
```

Document entries include `document_id`, `split`, `media_type`, `primary_file`, and empty
`supporting_files`. Query entries include `query_id`, `split`, `category`, `text`, and `qrels`.
Do not add candidate configuration or a quality threshold. Bind the adjudication artifact by path
and SHA-256 in the protocol.

- [ ] **Step 7: Create the provenance README**

Record:

- exact titles, publishers, source URLs, retrieval date `2026-06-25`, bytes, page counts,
  character tuples, and SHA-256 values;
- openEuler page-2 CC BY 4.0 statement and license URL;
- Article 5 redistribution basis for both laws;
- exact generated page text and the planning-time generation command/runtime
  (`PyMuPDF 1.27.2.3`, built-in `china-s`, 612x792 points, 12 points,
  `garbage=4`, `deflate=True`, `clean=True`);
- public holdout and small-engineering-corpus limitations.
- the complete partition-corpus review method, derived page/query counts, and the explicit absence
  of an inter-rater agreement claim.

- [ ] **Step 8: Run the fixture test to verify GREEN**

Run:

```bash
uv run pytest tests/evaluation/test_chinese_fixture_corpus.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add tests/evaluation/test_chinese_fixture_corpus.py \
  tests/fixtures/retrieval-chinese-v1/protocol.json \
  tests/fixtures/retrieval-chinese-v1/qrel-adjudication.json \
  tests/fixtures/retrieval-chinese-v1/README.md \
  tests/fixtures/retrieval-chinese-v1/development/ub-service-core-2.0-zh.pdf \
  tests/fixtures/retrieval-chinese-v1/development/adversarial.pdf \
  tests/fixtures/retrieval-chinese-v1/holdout/copyright-law-2020.pdf \
  tests/fixtures/retrieval-chinese-v1/holdout/administrative-compulsion-law-2011.pdf \
  tests/fixtures/retrieval-chinese-v1/holdout/adversarial.pdf
git commit -m "test(eval): freeze Chinese retrieval corpus"
```

---

### Task 2: Add The Strict Chinese Protocol Loader

**Files:**
- Create: `src/mke/evaluation/chinese_protocol.py`
- Create: `tests/evaluation/test_chinese_protocol.py`

- [ ] **Step 1: Write protocol parser RED tests**

Cover valid loading plus:

- unknown/missing fields;
- invalid schema/protocol/query/document IDs;
- absolute, `..`, backslash, symlink, and outside-root fixture paths;
- non-string or blank query text and queries longer than 1,000 characters;
- query text with no alphanumeric Unicode character;
- unknown split/category/document;
- qrel split mismatch;
- qrel grade `true`, non-integer, negative, or above `2`;
- duplicate locators inside one query;
- answerable query without grade `2`;
- unanswerable query with any qrel;
- hard-negative query without both grade `2` and grade `0`;
- adjudication path/checksum mismatch, wrong partition coverage/order, missing/duplicate page
  judgment, invalid grade, qrel disagreement, invalid review status, or an absent/oversized
  `decision_basis`;
- `decision_basis` containing absolute paths, control characters, exception text, credentials, or
  copied raw document passages;
- document/query/category count drift;
- duplicate query text across development and holdout;
- duplicate exact fixture bytes across partitions;
- missing, unreadable, changed, or mutating-during-snapshot fixture.

The first test imports:

```python
from mke.evaluation.chinese_protocol import (
    ChineseProtocolValidationError,
    load_chinese_retrieval_protocol,
    snapshot_chinese_retrieval_fixtures,
)
```

- [ ] **Step 2: Run the tests to verify RED**

```bash
uv run pytest tests/evaluation/test_chinese_protocol.py -q
```

Expected: import failure because the module does not exist.

- [ ] **Step 3: Implement immutable protocol DTOs**

Use these project-owned types:

```python
ChineseSplit = Literal["development", "holdout"]
QrelGrade = Literal[0, 1, 2]

@dataclass(frozen=True)
class ChineseEvaluationDocument:
    document_id: str
    split: ChineseSplit
    media_type: Literal["application/pdf"]
    primary_file: FixtureFile

@dataclass(frozen=True, order=True)
class GradedQrel:
    locator: StableLocator
    grade: QrelGrade

@dataclass(frozen=True)
class ChineseEvaluationQuery:
    query_id: str
    split: ChineseSplit
    category: ChineseQueryCategory
    text: str
    qrels: tuple[GradedQrel, ...]

@dataclass(frozen=True)
class QrelAdjudication:
    path: Path
    sha256: str
    review_status: Literal["complete"]
    reviewed_query_count: int
    query_page_judgment_count: int

@dataclass(frozen=True)
class ChineseRetrievalProtocol:
    schema_version: str
    protocol_id: str
    rank_probe_query_id: str
    root: Path
    documents: tuple[ChineseEvaluationDocument, ...]
    queries: tuple[ChineseEvaluationQuery, ...]
    qrel_adjudication: QrelAdjudication
```

Use `str.isalnum()` for the minimum query-character gate so CJK-only queries are valid. Reuse
`FixtureFile` and `StableLocator` from `mke.evaluation.manifest`; do not modify E1 types.

- [ ] **Step 4: Implement strict loading and fixture validation**

Implement `load_chinese_retrieval_protocol(path: Path) -> ChineseRetrievalProtocol` and
`snapshot_chinese_retrieval_fixtures(protocol: ChineseRetrievalProtocol, destination: Path) ->
ChineseRetrievalProtocol`.

Require exactly:

```python
EXPECTED_SPLIT_COUNTS = {"development": 24, "holdout": 24}
EXPECTED_CATEGORY_COUNTS = {
    "chinese_exact_lexical": 8,
    "chinese_word_boundary": 6,
    "proper_noun_mixed": 6,
    "number_date_unit": 6,
    "semantic_paraphrase": 8,
    "multi_condition": 6,
    "ranking_hard_negative": 4,
    "unanswerable": 4,
}
```

Require each development qrel to reference a development document and each holdout qrel to
reference a holdout document. Validate adjudication coverage by constructing the exact expected
ordered page inventory from the frozen PDF page counts. Do not accept caller-provided summary
counts as evidence of review completeness.

Snapshot with exclusive target creation (`"xb"`), calculate checksum during copy, verify byte
count/checksum before and after, and reject any mutation.

- [ ] **Step 5: Run the protocol tests**

```bash
uv run pytest tests/evaluation/test_chinese_protocol.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mke/evaluation/chinese_protocol.py \
  tests/evaluation/test_chinese_protocol.py
git commit -m "feat(eval): add Chinese retrieval protocol"
```

---

### Task 3: Add Graded Retrieval Metrics

**Files:**
- Create: `src/mke/evaluation/graded_metrics.py`
- Create: `tests/evaluation/test_graded_metrics.py`

- [ ] **Step 1: Write metric RED tests**

Test:

- Recall@1/3/5 counts only grade `2`;
- MRR@5 uses the first grade-`2` result;
- DCG uses `(2**grade - 1) / log2(rank + 1)`;
- nDCG@5/10 uses the ideal sorted qrel gains and excludes unanswerable queries;
- one query with two grade-`2` locators receives fractional Recall;
- answerable zero-hit means no grade-`2` result in top 10;
- hard-negative failure when grade `0` is ahead of all grade `2`, or grade `2` is absent while
  a designated grade `0` is returned;
- unanswerable no-hit requires no result;
- Ask input-rejection rate counts only `invalid_question`;
- Ask insufficient-Evidence rate counts only `insufficient_evidence`;
- Ask evidence-found rate counts only `evidence_found`;
- macro aggregation is stable and rounded only in `MetricValue.value`;
- category aggregates include all eight categories;
- compiled-query-empty strata contain exact `true`/`false` query counts;
- ASCII-token strata use fixed buckets `0`, `1`, and `2_plus`;
- invalid duplicate retrieved locators, unsupported Ask statuses, or answerable input without
  grade `2`, non-boolean compiled-query flags, or boolean/negative ASCII-token counts raises
  `ValueError`.

- [ ] **Step 2: Run the tests to verify RED**

```bash
uv run pytest tests/evaluation/test_graded_metrics.py -q
```

Expected: import failure.

- [ ] **Step 3: Implement the metric DTOs and formulas**

Use:

```python
AskObservationStatus = Literal[
    "evidence_found",
    "insufficient_evidence",
    "invalid_question",
]

@dataclass(frozen=True)
class GradedQueryMetricInput:
    query_id: str
    category: ChineseQueryCategory
    qrels: tuple[GradedQrel, ...]
    retrieved: tuple[StableLocator, ...]
    ask_status: AskObservationStatus
    compiled_query_empty: bool
    ascii_token_count: int

@dataclass(frozen=True)
class MetricBreakdown:
    label: str
    query_count: int
    recall_at_1: MetricValue
    recall_at_3: MetricValue
    recall_at_5: MetricValue
    mrr_at_5: MetricValue
    ndcg_at_5: MetricValue
    ndcg_at_10: MetricValue
    answerable_zero_hit_rate: MetricValue
    hard_negative_failure_rate: MetricValue
    unanswerable_no_hit_rate: MetricValue
    ask_input_rejection_rate: MetricValue
    ask_insufficient_evidence_rate: MetricValue
    ask_evidence_found_rate: MetricValue

@dataclass(frozen=True)
class GradedRetrievalMetrics:
    recall_at_1: MetricValue
    recall_at_3: MetricValue
    recall_at_5: MetricValue
    mrr_at_5: MetricValue
    ndcg_at_5: MetricValue
    ndcg_at_10: MetricValue
    answerable_zero_hit_rate: MetricValue
    hard_negative_failure_rate: MetricValue
    unanswerable_no_hit_rate: MetricValue
    ask_input_rejection_rate: MetricValue
    ask_insufficient_evidence_rate: MetricValue
    ask_evidence_found_rate: MetricValue
    category_metrics: tuple[MetricBreakdown, ...]
    compiled_query_empty_metrics: tuple[MetricBreakdown, ...]
    ascii_token_count_metrics: tuple[MetricBreakdown, ...]
```

Keep functions pure; do not import SQLite, application, or report modules.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/evaluation/test_graded_metrics.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mke/evaluation/graded_metrics.py \
  tests/evaluation/test_graded_metrics.py
git commit -m "feat(eval): add graded retrieval metrics"
```

---

### Task 4: Expose Full Active Evidence And Verify FTS5 Rank Semantics

**Files:**
- Create: `src/mke/evaluation/diagnostic_ports.py`
- Modify: `src/mke/adapters/sqlite/__init__.py`
- Modify: `tests/adapters/test_sqlite_fts.py`
- Create: `tests/evaluation/test_chinese_diagnostics.py`
- Create: `src/mke/evaluation/chinese_diagnostics.py`

- [ ] **Step 1: Write active-snapshot and rank-observation RED tests**

Require:

```python
@dataclass(frozen=True)
class EvaluationEvidenceSnapshot:
    evidence_id: str
    publication_id: str
    source_id: str
    locator_kind: str
    locator_start: int
    locator_end: int
    text: str

@dataclass(frozen=True)
class FtsProjectionSnapshot:
    evidence_id: str
    publication_id: str
    source_id: str
    locator_label: str
    text_sha256: str

@dataclass(frozen=True)
class FtsRankObservation:
    evidence_id: str
    locator_start: int
    rank_score: float
    bm25_score: float
```

Tests must prove:

- Evidence snapshot enumeration reads `sources -> publications -> evidence` and does not depend on
  FTS rows;
- FTS projection enumeration is separate, and missing, duplicate, stale, or extra projection rows
  fail the one-to-one integrity check;
- wrong `locator_label` or changed indexed text with otherwise correct IDs also fails;
- a failed reprocess leaves the old snapshot unchanged;
- order is stable by `source_id`, locator, and `evidence_id`;
- every non-empty compiled query returns two complete production-equivalent result sets ordered by
  `rank` and `bm25(active_evidence_fts)` with the same locator/evidence tie-breakers;
- those result sets have identical Evidence IDs/order and finite score pairs equal within absolute
  tolerance `1e-12`;
- stale FTS rows, explicit rank override, deterministic ties, and matches beyond top 10 are
  covered;
- no persistent `rank` override exists in `active_evidence_fts_config`;
- empty/invalid match input is rejected without SQL execution.

- [ ] **Step 2: Run RED**

```bash
uv run pytest tests/adapters/test_sqlite_fts.py -q
```

Expected: failures because the new DTO/methods do not exist.

- [ ] **Step 3: Implement the evaluation-only diagnostic port**

Define an internal `EvaluationRetrievalDiagnostics` protocol in
`mke.evaluation.diagnostic_ports`; do not add these DTOs to `mke.domain` and do not widen the
public `KnowledgeEngine` facade. The E3-A runner receives the SQLite-backed implementation during
workspace construction.

The Evidence snapshot SQL must use domain truth only:

```sql
FROM sources
JOIN publications
  ON publications.publication_id = sources.active_publication_id
JOIN evidence
  ON evidence.run_id = publications.run_id
 AND evidence.source_id = sources.source_id
```

Enumerate the FTS projection independently. Derive the expected locator label and SHA-256 of
Evidence text from the domain snapshot, then compare exact
`(evidence_id, publication_id, source_id, locator_label, text_sha256)` multisets. Reject any
missing, extra, duplicate, stale, wrong-locator, or text-corrupted row before query evaluation. Do
not change `list_active_evidence()`.

- [ ] **Step 4: Implement rank observation**

Execute two diagnostic queries with the same joins and active-Publication filter as production
Search:

```sql
SELECT evidence.evidence_id, evidence.locator_start, rank AS score
FROM active_evidence_fts
JOIN evidence ON evidence.evidence_id = active_evidence_fts.evidence_id
JOIN sources ON sources.source_id = evidence.source_id
WHERE active_evidence_fts MATCH ?
  AND sources.active_publication_id = active_evidence_fts.publication_id
ORDER BY rank, evidence.locator_start, evidence.evidence_id

SELECT evidence.evidence_id, evidence.locator_start,
       bm25(active_evidence_fts) AS score
FROM active_evidence_fts
JOIN evidence ON evidence.evidence_id = active_evidence_fts.evidence_id
JOIN sources ON sources.source_id = evidence.source_id
WHERE active_evidence_fts MATCH ?
  AND sources.active_publication_id = active_evidence_fts.publication_id
ORDER BY bm25(active_evidence_fts), evidence.locator_start, evidence.evidence_id
```

Also expose whether `active_evidence_fts_config` contains a `rank` row. The E3-A runner checks every
non-empty compiled query in all four workspaces and accepts the profile only when the override is
absent, the complete result order is identical, and every score pair is exactly equal or
`math.isclose(value_a, value_b, rel_tol=0.0, abs_tol=1e-12)`.

- [ ] **Step 5: Implement deterministic miss-symptom classification**

Create:

```python
MissSymptom = Literal[
    "compiled_query_empty",
    "distractor_ranked_ahead",
    "compiled_clauses_absent_from_direct_page",
    "compiled_clauses_overconstrained",
    "matching_direct_page_not_returned",
    "other_observed_miss",
]
```

Classification order:

1. grade-`0` ahead of every grade-`2`, or grade-`2` absent while grade-`0` is returned:
   `distractor_ranked_ahead`;
2. empty compiled query: `compiled_query_empty`;
3. no grade-`2` page satisfies any required compiled clause:
   `compiled_clauses_absent_from_direct_page`;
4. grade-`2` pages satisfy some but no page satisfies every required compiled clause:
   `compiled_clauses_overconstrained`;
5. at least one grade-`2` page satisfies every compiled clause but no grade-`2` locator is returned:
   `matching_direct_page_not_returned`;
6. `other_observed_miss`.

Extend the query compiler with an evaluation-only immutable clause diagnostic that represents
actual top-level `AND` clauses and each parenthesized `OR` alternative. Production Search still
receives the same compiled string. Tests cover single clauses, AND, OR groups, multiple grade-`2`
pages, and clauses distributed across pages.

Return structured evidence:

```python
@dataclass(frozen=True)
class MissClassification:
    symptom: MissSymptom
    compiled_query: str
    ascii_token_count: int
    compiled_query_empty: bool
    direct_locators: tuple[StableLocator, ...]
    returned_direct_ranks: tuple[int, ...]
    returned_distractor_ranks: tuple[int, ...]
    direct_page_clause_coverage: tuple[tuple[bool, ...], ...]
    observation: str
```

Never include raw document text in the public result.

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/adapters/test_sqlite_fts.py \
  tests/evaluation/test_chinese_diagnostics.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/mke/evaluation/diagnostic_ports.py \
  src/mke/adapters/sqlite/__init__.py \
  src/mke/evaluation/chinese_diagnostics.py \
  tests/adapters/test_sqlite_fts.py \
  tests/evaluation/test_chinese_diagnostics.py
git commit -m "feat(eval): expose active Chinese retrieval evidence"
```

---

### Task 5: Add The Chinese Report Contract

**Files:**
- Create: `src/mke/evaluation/chinese_report.py`
- Create: `tests/evaluation/test_chinese_report.py`

- [ ] **Step 1: Write report RED tests**

Require stable human and JSON output with:

- protocol/scope/status/quality gate;
- 5 documents, 48 queries, 24/24 split counts;
- aggregate and category metrics;
- per-query split/category/qrel counts, retrieved locators with assigned grades, direct ranks,
  hard-negative failure, Ask status, compiled query, ASCII token count, compiled-query-empty
  status, and optional miss classification;
- FTS5 rank profile `sqlite_fts5_default_bm25`;
- per-query rank observation count, ordered Evidence-ID digest, score-pair digest, and absent
  override observation;
- qrel `review_status=complete` and derived 1,680 judgment count without an inter-rater claim;
- limitations;
- stable integrity failures;
- no raw query text, raw Evidence text, absolute path, random ID, hostname, username, duration in
  the canonical semantic payload, or exception text.

The runtime report may contain `duration_ms`; the artifact must omit it.

Lock the first four human stdout lines:

```text
mke eval retrieval-chinese
integrity_status=passed quality_status=baseline_recorded quality_gate=none
e3b_decision=<eligible|not_justified> reason=<stable_reason>
documents=5 queries=48 development=24 holdout=24 duration_ms=<n>
```

Metrics, query strata, and per-query diagnostics follow. Tests assert this order so detailed query
output cannot hide the integrity/quality/eligibility distinction.

- [ ] **Step 2: Run RED**

```bash
uv run pytest tests/evaluation/test_chinese_report.py -q
```

- [ ] **Step 3: Implement report DTOs**

Use:

```python
@dataclass(frozen=True)
class ChineseQueryResult:
    query_id: str
    split: ChineseSplit
    category: ChineseQueryCategory
    qrel_counts: tuple[int, int, int]
    retrieved_locators: tuple[StableLocator, ...]
    retrieved_grades: tuple[int | None, ...]
    direct_ranks: tuple[int, ...]
    hard_negative_failure: bool
    ask_status: AskObservationStatus
    compiled_query: str
    ascii_token_count: int
    compiled_query_empty: bool
    miss: MissClassification | None

@dataclass(frozen=True)
class E3BDecisionEvidence:
    development_answerable_compiled_query_empty_misses: int
    qrel_review_status: Literal["complete"]
    query_page_judgment_count: int

@dataclass(frozen=True)
class ChineseRetrievalReport:
    protocol_id: str
    benchmark_scope: Literal["small_public_chinese_page_corpus"]
    quality_gate: Literal["none"]
    integrity_status: Literal["passed", "failed"]
    quality_status: Literal["baseline_recorded", "not_recorded"]
    documents: int
    queries: int
    split_counts: Mapping[ChineseSplit, int]
    results: tuple[ChineseQueryResult, ...]
    metrics: GradedRetrievalMetrics | None
    qrel_adjudication: QrelAdjudication
    e3b_decision: Literal["eligible", "not_justified"]
    e3b_evidence: E3BDecisionEvidence
    e3b_reason: Literal[
        "development_compiled_query_empty_miss_observed",
        "no_development_compiled_query_empty_miss",
        "qrel_review_incomplete",
        "evaluation_integrity_failed",
    ]
    fts5_rank_profile: str | None
    fts5_rank_observations: tuple[FtsRankEvidence, ...]
    integrity_failures: tuple[IntegrityFailure, ...]
    duration_ms: int
    limitations: tuple[str, ...]
```

JSON uses exactly these top-level fields and rejects extras:

```python
{
    "schema_version",
    "protocol_id",
    "benchmark_scope",
    "quality_gate",
    "integrity_status",
    "quality_status",
    "documents",
    "queries",
    "split_counts",
    "results",
    "metrics",
    "qrel_adjudication",
    "e3b_decision",
    "e3b_evidence",
    "e3b_reason",
    "fts5_rank_profile",
    "fts5_rank_observations",
    "integrity_failures",
    "duration_ms",
    "limitations",
}
```

Use `integrity_status`, not the ambiguous generic `status`. Eligibility is a next-stage evidence
decision, not a quality pass.

Limitations are fixed:

```python
(
    "public_holdout_not_blind",
    "small_engineering_corpus",
    "text_layer_pdf_only",
    "page_level_evidence_only",
    "current_ascii_oriented_query_compilation",
    "development_and_holdout_real_documents_cover_different_domains",
    "no_general_chinese_quality_claim",
    "no_dense_hybrid_or_reranker_claim",
)
```

- [ ] **Step 4: Run tests and commit**

```bash
uv run pytest tests/evaluation/test_chinese_report.py -q
git add src/mke/evaluation/chinese_report.py \
  tests/evaluation/test_chinese_report.py
git commit -m "feat(eval): add Chinese retrieval report"
```

---

### Task 6: Implement The Partition-Isolated E3-A Runner

**Files:**
- Create: `src/mke/evaluation/chinese_runner.py`
- Create: `tests/evaluation/test_chinese_runner.py`

- [ ] **Step 1: Write runner RED tests**

Test:

- checked-in protocol passes in two fresh workspaces per partition;
- development workspaces ingest only development documents and holdout workspaces ingest only
  holdout documents;
- qrel adjudication contains every ordered page judgment for every query and derives exactly
  1,680 judgments with `review_status=complete`;
- all five documents publish and every qrel locator resolves uniquely;
- all 48 queries execute in protocol order;
- Search limit is exactly 10;
- trace groups are isolated as `direct_search`, `ask_search`, and `rank_probe`;
- a compiled empty query executes zero FTS5 `MATCH` statements for direct Search and is rejected
  before Ask Search, also with zero MATCH;
- a non-empty direct Search executes one MATCH, Ask executes one separate MATCH, and rank probes
  are counted separately;
- Ask `invalid_question` is recorded only when compiled query is empty;
- valid Ask Evidence has the same ordered publication/locator sequence as direct Search;
- every grade-`2` miss has a mechanically observed classification;
- E3-B is `eligible` only when the development split has at least one answerable
  `compiled_query_empty` grade-`2` miss;
- low metrics still return `integrity_status=passed`;
- all non-empty compiled queries prove identical complete `rank` and `bm25()` order/scores and
  produce artifact-bound digests;
- fixture mutation after validation and during snapshot fails closed;
- duplicate active locator, unknown source, failed ingest, nondeterminism, rank override, rank
  mismatch, incomplete query execution, unsupported Ask status, and unexpected exception produce
  stable redacted integrity failures.

- [ ] **Step 2: Run RED**

```bash
uv run pytest tests/evaluation/test_chinese_runner.py -q
```

- [ ] **Step 3: Implement the runner**

The public entry is
`run_chinese_retrieval_evaluation(protocol_path: Path) -> ChineseRetrievalReport`.

Internal flow:

```text
load protocol
-> snapshot exact bytes
-> run development workspace A/B with development documents and queries
-> compare development semantic results/evidence
-> run holdout workspace A/B with holdout documents and queries
-> compare holdout semantic results/evidence
-> combine reports in protocol query order
-> return report with measured duration
```

Workspace flow:

```text
KnowledgeEngine(temp SQLite, query_policy="numeric-grouping-v1")
-> ingest only the selected partition's PDFs
-> map source_id to document_id
-> enumerate EvaluationEvidenceSnapshot from domain truth
-> independently enumerate and validate FTS projection 1:1
-> validate all graded qrels
-> verify rank behavior for every non-empty compiled query
-> evaluate only the selected partition's 24 queries
-> calculate graded metrics
-> classify every direct miss
```

For Ask:

```python
try:
    status = engine.ask(query.text, limit=10).answer_status
except AskValidationError as error:
    if error.problem != "invalid_question" or compiled_query:
        raise ChineseEvaluationIntegrityError(
            "ask validation does not match the compiled query"
        )
    status = "invalid_question"
```

Do not weaken `_normalize_ask_question()` in E3-A.

The runner labels observer output around each application call; it does not install nested SQLite
trace callbacks. For every non-empty query, compare direct Search and Ask Evidence using the full
ordered `(publication_id, source_id, locator_kind, locator_start, locator_end)` sequence. Rank
probe SQL runs only through the diagnostic port and is recorded under its own operation label.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/evaluation/test_chinese_runner.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mke/evaluation/chinese_runner.py \
  tests/evaluation/test_chinese_runner.py
git commit -m "feat(eval): run Chinese retrieval baseline"
```

---

### Task 7: Add Canonical Artifact Recording And Validation

**Files:**
- Create: `src/mke/evaluation/chinese_artifact.py`
- Create: `tests/evaluation/test_chinese_artifact.py`
- Modify: `src/mke/evaluation/baseline.py`
- Modify: `tests/evaluation/test_baseline.py`
- Modify: `src/mke/evaluation/numeric_comparison.py`
- Modify: `tests/evaluation/test_numeric_comparison.py`
- Create: `src/mke/evaluation/artifact_refresh.py`
- Create: `tests/evaluation/test_artifact_refresh.py`

- [ ] **Step 1: Write artifact RED tests**

Require:

- `record` accepts only a successful observed JSON report matching a freshly loaded protocol;
- `validate` independently reloads protocol/fixtures and recomputes counts, metric values,
  per-category aggregates, hard-negative failures, Ask rates, classifications, qrel judgment
  coverage, and FTS5 rank-evidence consistency;
- the artifact binds all sorted `src/mke/**/*.py` files by path, byte size, SHA-256, and aggregate
  SHA-256;
- the artifact binds protocol and all five fixture identities;
- the artifact binds the qrel-adjudication identity and independently checks its full ordered
  query/document/page judgment inventory, derived count, qrels, and review status;
- the artifact records, for every non-empty compiled query, result count, ordered Evidence-ID
  digest, rank/bm25 score-pair digest, and absent-override observation; mutation fails validation;
- validation labels this as adjudication-record and scorer-evidence integrity, not independent
  machine proof that human relevance grades are semantically correct;
- validation works after squash landing in a shallow fresh clone without feature commit ancestry;
- mutation of any source file, fixture, qrel, metric, result, grade, category, classification,
  compiled query, query stratum, rank profile, environment version, or limitation fails;
- booleans are rejected for integer/grade/rank/count fields;
- malformed locators and paths produce one stable error, exit `1`, no traceback, and no absolute
  path.
- E1 source refresh changes only `code.evaluation_content_sha256` and
  `code.evaluation_content_files`, then runs the full E1 validator;
- E1 source refresh rejects changed historical metadata, fixtures, metrics, results, or manifest
  identity and leaves the artifact byte-identical on failure;
- E2 scope refresh changes only the existing ordered `scope_fence.files[*].sha256` values and
  `scope_fence.sqlite_schema_sha256`, then reloads the full protocol;
- E2 scope refresh rejects any changed candidate, claim, manifest, fixture, required-query, file
  path, or scope-fence file inventory and leaves the protocol byte-identical on failure.
- the set-level artifact refresh generates all four target files under a durable transaction
  directory, validates the complete set, then writes and fsyncs a recovery journal before replacing
  targets;
- write failure, validation failure, `os.replace()` failure, handled signal, and restart after
  interruption at any replacement point restore the original four files byte-for-byte;
- a `recover` subcommand and normal command startup both detect an existing journal, restore and
  checksum-verify all backups, then remove the transaction directory before new work.

- [ ] **Step 2: Run RED**

```bash
uv run pytest tests/evaluation/test_chinese_artifact.py -q
```

- [ ] **Step 3: Implement record and validate commands**

Module CLI:

```text
python -m mke.evaluation.chinese_artifact record \
  --observed /tmp/mke-retrieval-chinese.json \
  --artifact benchmarks/retrieval/retrieval-chinese-v1-baseline.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .

python -m mke.evaluation.chinese_artifact validate \
  --artifact benchmarks/retrieval/retrieval-chinese-v1-baseline.json \
  --observed /tmp/mke-retrieval-chinese.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
```

Artifact top-level fields:

```python
{
    "schema_version",
    "protocol_id",
    "protocol_sha256",
    "fixtures",
    "qrel_adjudication",
    "source_identity",
    "environment",
    "report_schema_version",
    "benchmark_scope",
    "quality_gate",
    "documents",
    "queries",
    "split_counts",
    "category_counts",
    "metrics",
    "query_strata",
    "miss_symptom_counts",
    "e3b_decision",
    "e3b_evidence",
    "e3b_reason",
    "fts5_rank_profile",
    "fts5_rank_observations",
    "results",
    "limitations",
}
```

Environment is an exact repository-derived contract, not a snapshot of the recording process. It
records the supported Python requirement and CI matrix, the locked PyMuPDF version, and the
approved SQLite rank profile. Validation must recompute those values from repository sources and
reject any artifact mutation, including well-formed but impossible version values. Do not record
OS username, hostname, paths, duration, current interpreter version, current SQLite library
version, or Git commit ancestry.

- [ ] **Step 4: Implement restricted E1 and E2 identity refresh primitives**

Add these module commands without changing existing validation invocations:

```text
python -m mke.evaluation.baseline refresh-source \
  --artifact benchmarks/retrieval/retrieval-eval-v1-baseline.json \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --repository . \
  --main-ref main

python -m mke.evaluation.numeric_comparison refresh-scope \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --repository .
```

Both commands must write through a temporary sibling file and `os.replace()` only after all
non-refreshable fields validate. `refresh-source` may replace only the two E1 source-content
fields. `refresh-scope` may replace only hashes for the already locked E2 file inventory and the
SQLite schema hash. Neither command may add files, alter observations, or accept a caller-supplied
replacement value.

These primitives are not the Task 9 release operation. Task 9 uses one orchestration command to
stage and validate the E1, E2 protocol, E2 artifact, and E3-A artifact as a set before replacing
any checked-in target.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/evaluation/test_chinese_artifact.py \
  tests/evaluation/test_baseline.py \
  tests/evaluation/test_numeric_comparison.py -q
git add src/mke/evaluation/chinese_artifact.py \
  tests/evaluation/test_chinese_artifact.py \
  src/mke/evaluation/baseline.py \
  tests/evaluation/test_baseline.py \
  src/mke/evaluation/numeric_comparison.py \
  tests/evaluation/test_numeric_comparison.py \
  src/mke/evaluation/artifact_refresh.py \
  tests/evaluation/test_artifact_refresh.py
git commit -m "feat(eval): validate Chinese retrieval artifact"
```

---

### Task 8: Add CLI And Installed-Wheel Evaluation Proof

**Files:**
- Modify: `src/mke/evaluation/__init__.py`
- Modify: `src/mke/cli.py`
- Modify: `tests/interfaces/test_cli_evaluation.py`
- Create: `scripts/chinese_retrieval_deployment_proof.py`
- Create: `tests/evaluation/test_chinese_deployment_proof.py`
- Create: `scripts/chinese_retrieval_measurement.py`
- Create: `tests/evaluation/test_chinese_measurement.py`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Write CLI RED tests**

Test:

- human and JSON command success;
- exact command help states baseline-only, public holdout, no quality threshold, and no
  dense/hybrid/reranker claim;
- human and JSON output distinguish query category from compiled-query-empty and ASCII-token-count
  strata;
- `--db` and `--retrieval-query-policy` remain rejected for all eval commands;
- missing/malformed protocol returns exit `1`, stable public-safe result, no traceback/path;
- rendering failure uses `mke.retrieval_chinese_report.v1` fallback;
- low quality still exits `0`;
- integrity failure exits `1`.
- human mode writes only these stable progress phases to stderr, in order:
  `protocol_validated`, `development_ingested`, `holdout_ingested`,
  `determinism_verified`;
- JSON mode keeps stderr silent;
- failure never emits a later success phase, and progress contains no path, ID, query text, or
  exception text.

- [ ] **Step 2: Run RED**

```bash
uv run pytest tests/interfaces/test_cli_evaluation.py -q
```

- [ ] **Step 3: Add CLI wiring**

Add:

```python
chinese_retrieval = evaluation_subcommands.add_parser(
    "retrieval-chinese",
    description=(
        "Record the current FTS5 lexical baseline on a small public Chinese "
        "development/holdout corpus; no retrieval-quality threshold is applied."
    ),
)
chinese_retrieval.add_argument("--protocol", type=Path, required=True)
chinese_retrieval.add_argument("--json", action="store_true", dest="json_output")
```

Dispatch to `run_chinese_retrieval_evaluation()` and safe human/JSON renderers.
The runner accepts an optional progress callback. Human CLI passes a stderr renderer; JSON and
library callers pass `None`. Stdout remains exclusively the final human or JSON report.

- [ ] **Step 4: Add required CI**

After E1 and E2 validation:

```yaml
- name: Run Chinese retrieval baseline
  run: |
    uv run mke eval retrieval-chinese \
      --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
      --json > /tmp/mke-retrieval-chinese.json
    uv run python -m mke.evaluation.chinese_artifact validate \
      --artifact benchmarks/retrieval/retrieval-chinese-v1-baseline.json \
      --observed /tmp/mke-retrieval-chinese.json \
      --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
      --repository .
```

Add a dedicated deployment-proof script following the existing numeric proof isolation:

- create the temporary venv from an external runtime root;
- set `UV_OFFLINE=1` and install the wheel with `uv pip install --offline`;
- use `--no-python-downloads` for environment creation and lock-derived constraints for install;
- remove `PYTHONPATH`, `PYTHONHOME`, and `VIRTUAL_ENV`;
- verify `sys.executable` and `mke.__file__` belong to the temporary environment and are outside
  the repository;
- run the command from the external runtime root with the repository protocol passed by absolute
  path;
- assert status, document/query counts, empty integrity failures, partition isolation, and rank
  profile.
- impose a total timeout and per-subprocess timeout, bound stdout/stderr capture, and emit a stable
  public-safe proof JSON containing only Python version, offline status, installed-identity
  status, evaluation status, duration, and failure reason.

Tests must prove hostile `PYTHONPATH` cannot load source-tree code and an empty package cache fails
closed without network access. Run this proof for Python 3.12 and 3.13. No network or model is
required.

Add a repository-owned measurement helper with stable JSON output. Without telemetry or network,
it records:

- warm-cache `uv sync --locked` wall time;
- evaluator wall time from CLI start to complete human report;
- `checkout_to_first_report_ms`, defined exactly as warm-cache sync wall time plus evaluator wall
  time; progress phases are not counted as the first report;
- installed-wheel proof wall time;
- peak child-process RSS;
- maximum temporary SQLite bytes;
- whether each fixed budget passed.

The helper uses bounded subprocess capture and per-step timeouts. Tests inject fake commands and
resource samples; required CI invokes the real helper and writes its JSON summary to
`$GITHUB_STEP_SUMMARY`. The 300-second TTHW target is reported for a checkout with `uv` and a warm
dependency cache; cold-network dependency acquisition is explicitly outside the deterministic
gate.

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/interfaces/test_cli_evaluation.py \
  tests/evaluation/test_chinese_runner.py -q
```

- [ ] **Step 6: Commit**

```bash
git add src/mke/evaluation/__init__.py \
  src/mke/cli.py \
  tests/interfaces/test_cli_evaluation.py \
  scripts/chinese_retrieval_deployment_proof.py \
  tests/evaluation/test_chinese_deployment_proof.py \
  scripts/chinese_retrieval_measurement.py \
  tests/evaluation/test_chinese_measurement.py \
  .github/workflows/ci.yml
git commit -m "feat(cli): expose Chinese retrieval baseline"
```

---

### Task 9: Record The Canonical Observation And Refresh Bound Artifacts

**Files:**
- Create: `benchmarks/retrieval/retrieval-chinese-v1-baseline.json`
- Modify: `benchmarks/retrieval/retrieval-eval-v1-baseline.json`
- Modify: `benchmarks/retrieval/numeric-grouping-v1-comparison.json`
- Modify: `tests/fixtures/retrieval-numeric-v1/protocol-lock.json`
- Test: existing E1/E2 artifact tests plus Chinese artifact tests.

- [ ] **Step 1: Run all three evaluations**

```bash
uv run mke eval retrieval \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --json > /tmp/mke-e1.json
uv run mke eval retrieval-numeric \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --json > /tmp/mke-e2.json
uv run mke eval retrieval-chinese \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --json > /tmp/mke-e3a.json
```

E1 and E2 observations, metrics, gates, and verdict must remain unchanged. Only their bound source
identity may change.

- [ ] **Step 2: Stage and validate the complete artifact set**

```bash
uv run python -m mke.evaluation.artifact_refresh \
  --repository . \
  --e1-observed /tmp/mke-e1.json \
  --e2-observed /tmp/mke-e2.json \
  --e3-observed /tmp/mke-e3a.json
```

The orchestrator must:

1. recover any prior incomplete transaction before new work;
2. copy all four current targets into a durable backup directory and fsync files/directories;
3. generate the refreshed E1 artifact, refreshed E2 protocol, re-recorded E2 artifact, and new
   E3-A artifact under one temporary transaction directory;
4. compare E1/E2 observations, metrics, gates, candidate verdict, query order, and per-query
   results against their checked-in semantic payloads, excluding only declared
   identity/environment fields;
5. validate the staged E1, E2, and E3-A artifacts as a coherent set;
6. write and fsync a journal containing target order, original/staged checksums, backup paths, and
   replacement progress;
7. replace targets in fixed order, fsync each parent directory, and durably advance the journal;
8. remove the journal/backups only after the checked-in set validates;
9. on normal exception or handled signal, restore immediately; after abrupt termination, the next
   invocation or explicit `recover` restores before any other operation.

- [ ] **Step 3: Validate the checked-in set after replacement**

```bash
uv run python -m mke.evaluation.baseline \
  --artifact benchmarks/retrieval/retrieval-eval-v1-baseline.json \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --repository . \
  --main-ref main
uv run python -m mke.evaluation.numeric_artifact validate \
  --artifact benchmarks/retrieval/numeric-grouping-v1-comparison.json \
  --observed /tmp/mke-e2.json \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --repository .
uv run python -m mke.evaluation.chinese_artifact validate \
  --artifact benchmarks/retrieval/retrieval-chinese-v1-baseline.json \
  --observed /tmp/mke-e3a.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
```

Also compare SHA-256 values against the orchestrator's staged manifest and require no leftover
journal, transaction, or backup directory.

- [ ] **Step 4: Commit**

```bash
git add benchmarks/retrieval/retrieval-chinese-v1-baseline.json \
  benchmarks/retrieval/retrieval-eval-v1-baseline.json \
  benchmarks/retrieval/numeric-grouping-v1-comparison.json \
  tests/fixtures/retrieval-numeric-v1/protocol-lock.json
git commit -m "test(eval): record Chinese retrieval baseline"
```

---

### Task 10: Document E3-A Without Overclaiming

**Files:**
- Create: `docs/how-to/run-chinese-retrieval-evaluation.md`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `docs/README.md`
- Modify: `docs/tutorials/getting-started.md`
- Modify: `docs/reference/cli.md`
- Modify: `docs/reference/contracts.md`
- Modify: `docs/explanation/architecture.md`
- Modify: the E3 design and this plan completion status.
- Create: `docs/superpowers/reviews/2026-06-25-chinese-retrieval-baseline-review.md`

- [ ] **Step 1: Add documentation tests/checks**

Use repository link/status consistency scripts where available. Add focused assertions that docs:

- name the current path `FTS5 lexical retrieval`;
- describe `rank` as SQLite FTS5 default BM25 only after the runtime equality proof;
- state that current query compilation is ASCII-oriented;
- publish actual E3-A metrics and category failure counts from the artifact;
- do not claim CJK support, dense/vector retrieval, hybrid retrieval, RRF, reranking, statistical
  significance, production quality, OCR, or arbitrary PDF support;
- keep E3-B through E3-F unimplemented and evidence-gated.
- keep this exact copy-paste first-run block and expected first four lines synchronized across
  README, tutorial, and CLI tests:

```bash
uv sync --locked &&
uv run mke eval retrieval-chinese \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json
```

- [ ] **Step 2: Write the how-to**

Include:

- command and JSON command;
- protocol layout and 48-query allocation;
- graded-qrel and metric semantics;
- interpretation of `integrity_status=passed` versus observed quality and independent artifact
  validation;
- `invalid_question` versus `insufficient_evidence`;
- miss-symptom taxonomy and why it does not claim root cause;
- complete partition-corpus qrel review;
- public-holdout one-observation governance;
- the predeclared E3-B start rule;
- canonical artifact validation;
- fixture provenance and public-holdout limits.
- an exact recovery table mapping every stable `next_step` token to a copy-paste command;
- the offline installed-wheel proof commands for Python 3.12 and 3.13, including the expected
  cache-missing fail-closed behavior;
- the additive upgrade/rollback contract: no database migration, projection rebuild, runtime
  selector change, or user-data action; E1/E2 refresh is repository provenance maintenance.

Keep Diataxis roles separate:

- `docs/tutorials/getting-started.md`: first-run block, expected first four lines, 2-5 minute target,
  and success interpretation only;
- `docs/how-to/run-chinese-retrieval-evaluation.md`: metrics, miss symptoms, governance, E3-B
  eligibility, artifact validation, and installed-wheel proof;
- `docs/reference/cli.md`: complete flags, exact JSON field set, exit codes, progress contract, and
  error/recovery matrix;
- README and docs index: short navigation only.

- [ ] **Step 3: Update public navigation and architecture**

Add E3-A as a separate evaluation surface. Do not draw vector/RRF/reranker modules as implemented;
keep them in an explicitly future/evidence-gated paragraph.

- [ ] **Step 4: Run document-release audit**

Run `gstack-document-release` in audit mode. Apply only E3-A-required documentation fixes. Do not
create a release, bump a version, push, or update a PR.

- [ ] **Step 5: Commit**

```bash
git add README.md README_CN.md docs/README.md docs/tutorials/getting-started.md \
  docs/reference/cli.md docs/reference/contracts.md \
  docs/explanation/architecture.md \
  docs/how-to/run-chinese-retrieval-evaluation.md \
  docs/superpowers/specs/2026-06-25-chinese-hybrid-retrieval-evaluation-design.md \
  docs/superpowers/plans/2026-06-25-chinese-retrieval-baseline-implementation.md \
  docs/superpowers/reviews/2026-06-25-chinese-retrieval-baseline-review.md
git commit -m "docs(eval): document Chinese retrieval baseline"
```

---

### Task 11: Final Verification And Implementation-Window Handoff

**Files:**
- Modify: plan/review completion records only if actual evidence requires updates.

- [ ] **Step 1: Run targeted tests**

```bash
uv run pytest \
  tests/evaluation/test_chinese_fixture_corpus.py \
  tests/evaluation/test_chinese_protocol.py \
  tests/evaluation/test_graded_metrics.py \
  tests/evaluation/test_chinese_diagnostics.py \
  tests/evaluation/test_chinese_report.py \
  tests/evaluation/test_chinese_runner.py \
  tests/evaluation/test_chinese_artifact.py \
  tests/evaluation/test_artifact_refresh.py \
  tests/evaluation/test_chinese_deployment_proof.py \
  tests/evaluation/test_chinese_measurement.py \
  tests/interfaces/test_cli_evaluation.py \
  tests/adapters/test_sqlite_fts.py -q
```

- [ ] **Step 2: Run full verification**

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke proof run
uv run mke demo --verify
```

- [ ] **Step 3: Run evaluation and artifact gates**

Run E1, E2, and E3-A commands plus all three validators exactly as specified in Task 9. Parse the
E3-A JSON and require:

```python
assert payload["integrity_status"] == "passed"
assert payload["quality_status"] == "baseline_recorded"
assert payload["documents"] == 5
assert payload["queries"] == 48
assert payload["split_counts"] == {"development": 24, "holdout": 24}
assert payload["integrity_failures"] == []
assert payload["fts5_rank_profile"] == "sqlite_fts5_default_bm25"
```

Require the E3-B decision record to be `eligible` only when:

```python
assert (
    payload["e3b_evidence"]["development_answerable_compiled_query_empty_misses"]
    >= 1
)
assert payload["qrel_adjudication"]["review_status"] == "complete"
assert payload["qrel_adjudication"]["query_page_judgment_count"] == 1680
assert payload["e3b_decision"] == "eligible"
```

If either evidence condition is false, record E3-B as `not_justified` and stop after E3-A
closeout.

- [ ] **Step 4: Run installed-wheel proof on Python 3.12 and 3.13**

Build the wheel, install it offline into isolated temporary environments using lock-derived
constraints, clear `PYTHONPATH`, `PYTHONHOME`, and `VIRTUAL_ENV`, run from outside the repository,
verify installed module identity, and execute `mke eval retrieval-chinese` with the external
protocol path.

- [ ] **Step 5: Record and enforce CI resource budgets**

On Python 3.12 and 3.13, record source-tree evaluation wall time, each installed-wheel proof wall
time, warm-cache first-report TTHW, peak RSS, and maximum temporary SQLite file size through
`scripts/chinese_retrieval_measurement.py`. Require:

```text
warm-cache checkout-to-first-human-report TTHW <= 300 seconds
one source-tree E3-A run <= 180 seconds
one installed-wheel E3-A proof <= 180 seconds
peak RSS <= 1.5 GiB
each temporary SQLite database <= 64 MiB
complete CI job remains below the existing 10-minute timeout
```

If the measured implementation exceeds a budget, return to planning rather than silently raising
the limit. Give every expensive subprocess its own timeout in addition to the job timeout. Keep
active Evidence snapshots immutable and bounded to one partition; do not copy raw
Evidence text into reports, canonical artifacts, or rank observations. Artifact validation must
not perform an implicit second ingest; CI performs one explicit authoritative evaluation and then
validates its recorded evidence.

- [ ] **Step 6: Run diff and public-boundary checks**

```bash
git diff --check main...HEAD
rg -n "/Users/|API_KEY|token|secret" \
  README.md README_CN.md docs benchmarks tests/fixtures/retrieval-chinese-v1
```

Review every match; expected public technical uses of “token” are allowed, private paths and
private motivation or raw planning-tool metadata are not. Inspect the changed public documents for
those boundaries without embedding private workspace names in the repository.

- [ ] **Step 7: Perform lightweight pre-handoff review**

Confirm:

- no runtime retrieval behavior changed;
- no CJK, dense, hybrid, RRF, or reranker candidate code exists;
- no model or vector dependency was added;
- no network operation exists in evaluation runtime or CI;
- old active Publication behavior and all proof commands remain green;
- every observed grade-`2` miss has a mechanical symptom classification;
- all queries passed complete partition-corpus page review;
- the public-holdout governance and E3-B start rule are present in the canonical artifact;
- the durable review reports actual commands and results.

Do not run the final authoritative `gstack-review`; the separate planning/review window owns that
step before PR creation.

- [ ] **Step 8: Commit final completion records**

```bash
git add docs/superpowers/plans/2026-06-25-chinese-retrieval-baseline-implementation.md \
  docs/superpowers/reviews/2026-06-25-chinese-retrieval-baseline-review.md
git commit -m "docs(eval): record Chinese baseline verification"
```

- [ ] **Step 9: Return the clean local branch**

Report:

- branch, base, HEAD, commit list, and diff stat;
- exact targeted/full verification;
- E1/E2 unchanged evidence;
- E3-A metrics, query strata, miss-symptom counts, FTS5 rank profile, E3-B eligibility, and
  artifact SHA-256;
- fixture identities and redistribution evidence;
- remaining E3-B decision boundary;
- clean worktree;
- no push, PR, candidate implementation, or complete `gstack-review`.

---

## Autoplan Review Record

### Phase 1: CEO Scope And Evidence Review

**Mode:** HOLD SCOPE. The reviewed problem remains E3-A only: establish a trustworthy observation
of the current Chinese lexical path before selecting any retrieval candidate.

**Premises confirmed:**

1. The current ASCII-oriented compiler makes a Chinese-specific baseline necessary.
2. A frozen development/public-holdout protocol is useful only when query strata, qrels, and
   observation governance prevent post-hoc interpretation.
3. E3-A must be able to stop without authorizing E3-B.
4. The evaluator must reuse normal ingest, active Publication, Search, and Ask behavior.
5. No algorithm, dependency, projection, runtime default, or public Search/Ask DTO changes belong
   in E3-A.

The user confirmed these premises through the approved E3 design and the authorization to run this
HOLD SCOPE autoplan.

### What Already Exists

| Sub-problem | Existing implementation | E3-A action |
|---|---|---|
| Strict external corpus identity | `mke.evaluation.manifest` | Reuse `FixtureFile`, `StableLocator`, path validation, and immutable-copy pattern; keep a separate graded schema. |
| Two-workspace determinism | `mke.evaluation.runner` | Reuse the pattern independently for development and holdout without widening E1. |
| Current query compilation | `mke.retrieval.query_policy` | Observe the exact default compiler; do not change it. |
| Active-only retrieval | `SQLiteStore.search` | Execute the normal Search SQL and verify Publication identity. |
| Evidence-only Ask | `KnowledgeEngine.ask` | Observe `invalid_question`, `insufficient_evidence`, and `evidence_found` separately. |
| Canonical artifacts | E1 `baseline.py`, E2 `numeric_artifact.py` | Reuse strict schema/identity/error patterns; refresh E1/E2 only through restricted semantic-preserving commands. |
| Installed-wheel proof | existing E1/E2 CI | Extend the same source-tree-isolation pattern to the new command. |

### Dream-State Delta

```text
CURRENT
  ASCII-oriented FTS5 + English/numeric artifacts
      |
      v
E3-A
  adjudicated Chinese protocol
  + current-path query strata
  + mechanical miss symptoms
  + one-observation holdout governance
      |
      v
12-MONTH IDEAL
  smallest proven lexical/dense/hybrid strategy
  + active-Publication projection integrity
  + reproducible local comparison
  + evidence-backed promotion and rollback
```

E3-A deliberately stops before the candidate layers. It supplies the decision boundary and
evidence contract, not a partial implementation of the final retrieval stack.

### Alternatives Reviewed

| Approach | Effort | Risk | Decision |
|---|---:|---|---|
| Keep category-derived causal taxonomy | Low | Produces confident but unprovable root-cause claims | Rejected |
| Use mechanically observable miss symptoms | Medium | Less rhetorically attractive but independently testable | Selected |
| Expand beyond 48 queries for ASCII/CJK pairs | Medium | Reopens frozen protocol scope | Rejected; use compiled-query and ASCII-token strata |
| Repartition real documents across dev/holdout | High | Changes approved corpus and still does not create a blind holdout | Rejected; retain bounded claim and record domain-shift limitation |
| Narrow artifact identity to hand-picked files | Medium | Reopens E1/E2 settled provenance policy and may miss indirect behavior changes | Rejected |
| Refresh E1/E2 through unrestricted manual editing | Low | Can rewrite semantic observations | Rejected; use restricted validated refresh commands |

### Architecture And Data Flow

```text
protocol + adjudication + exact fixture bytes
                  |
                  v
      strict validation + immutable snapshot
                  |
          +-------+------------------+
          |                          |
          v                          v
 development A/B                 holdout A/B
 development corpus              holdout corpus
          |                          |
          v                          v
 domain Evidence + verified FTS projection + current Search/Ask
          |                          |
          +-------------+------------+
                  |
      deterministic semantic comparison
                  |
       graded metrics + query strata
                  |
        mechanical miss symptoms
                  |
      canonical artifact + E3-B decision
```

Shadow paths:

```text
missing/invalid protocol -> stable integrity failure -> exit 1
empty compiled query     -> zero MATCH statements -> Search [] + Ask invalid_question
fixture mutation         -> snapshot rejection -> no evaluation artifact
ingest/Publication error -> stable integrity failure -> no quality claim
workspace mismatch       -> nondeterminism failure -> no canonical record
renderer error           -> fixed redacted fallback -> exit 1
```

No persistent state machine is added. The report state is derived:

```text
inputs invalid / execution incomplete -> failed + not_recorded
integrity and determinism pass        -> passed + baseline_recorded
                                      -> E3-B eligible | not_justified
```

### Error And Rescue Registry

| Codepath | Exact `problem` | Bounded public `cause` | Exact `next_step` |
|---|---|---|---|
| protocol load | `retrieval_chinese_protocol_invalid` | `Chinese retrieval protocol is invalid` | `restore_checked_in_protocol` |
| qrel review load | `retrieval_chinese_qrels_invalid` | `Chinese retrieval qrel review is invalid` | `restore_checked_in_qrel_review` |
| fixture snapshot | `retrieval_chinese_fixture_invalid` | `Chinese retrieval fixture identity is invalid` | `verify_fixture_identity` |
| PDF ingest/Publication | `retrieval_chinese_ingest_failed` | `Chinese retrieval fixture could not be published` | `inspect_publication_failure` |
| domain Evidence/FTS projection | `retrieval_chinese_evidence_invalid` | `active Evidence and retrieval projection are inconsistent` | `inspect_active_evidence_projection` |
| FTS rank observation | `retrieval_chinese_rank_invalid` | `FTS5 rank evidence is inconsistent` | `inspect_fts5_rank_configuration` |
| Search/Ask/determinism | `retrieval_chinese_incomplete` | `Chinese retrieval evaluation did not complete` | `rerun_evaluation` |
| artifact record/validate | `retrieval_chinese_artifact_invalid` | `Chinese retrieval baseline artifact is invalid` | `regenerate_chinese_artifact` |
| artifact-set refresh | `retrieval_artifact_refresh_failed` | `retrieval artifact transaction did not complete` | `recover_checked_in_artifacts` |
| renderer | `retrieval_chinese_render_failed` | `Chinese retrieval report could not be rendered` | `rerun_evaluation` |

Every error test verifies the exact triple, no absolute path, traceback, raw exception text, or
credential. Optional `subject_id` is limited to protocol-owned document/query IDs and is omitted
when the failure cannot be safely attributed.

### Failure Modes Registry

| Codepath | Failure mode | Rescued? | Test? | User sees | Logged/artifact |
|---|---|---:|---:|---|---|
| protocol | path escapes root | yes | yes | stable invalid-protocol result | integrity failure |
| adjudication | partition page omitted, duplicated, misordered, or qrels disagree | yes | yes | stable invalid-qrels result | integrity failure |
| snapshot | source bytes change after validation | yes | yes | stable fixture failure | integrity failure |
| ingest | one PDF does not publish | yes | yes | document-scoped stable failure | integrity failure |
| active Evidence | stale Publication row appears | yes | yes | active-evidence integrity failure | integrity failure |
| query compile | no ASCII token | yes | yes | Search no-hit; Ask input rejection | query result + strata |
| FTS rank | rank override or score/order mismatch | yes | yes | rank integrity failure | integrity failure |
| metrics | malformed grades, duplicate locators, invalid counts | yes | yes | evaluation incomplete | integrity failure |
| determinism | workspace results differ | yes | yes | nondeterminism failure | integrity failure |
| artifact | source/protocol/result mutation | yes | yes | canonical artifact invalid | validator failure |
| holdout | candidate changed after observation | yes | yes | contaminated/not promotable | governance record |

No silent, untested, unrescued failure remains in the planned boundary.

### Security And Public Boundary

- Inputs are checked-in or operator-selected local files; no new network, provider, credential, or
  request-controlled execution surface is added.
- Relative paths, symlinks, checksums, byte counts, JSON types, Unicode bounds, and integer/bool
  confusion receive explicit rejection tests.
- Reports omit raw Evidence text, absolute paths, usernames, hostnames, random IDs, exception text,
  and credentials.
- Public docs retain the bounded corpus/domain/public-holdout limitations and make no CJK,
  hybrid, reranker, production-quality, or statistical claim.

### Deployment, Rollback, And Long-Term Trajectory

```text
merge E3-A
  -> CI runs E1 + E2 + E3-A integrity gates
  -> squash-landed main validates all artifacts
  -> no runtime selector/default/schema migration changes

rollback
  -> revert E3-A commit
  -> remove the evaluation command, fixtures, E3-A artifact, and diagnostic read seams
  -> restore pre-E3-A E1 artifact, E2 protocol, and E2 artifact identities through the revert
  -> existing Search/Ask/Publication behavior remains unchanged
```

Reversibility is `5/5`. The main long-term debt is the visible small public holdout; the
one-observation governance prevents it from silently becoming a tuning set. Any future
segmentation change requires a new qrel protocol rather than reinterpretation of this artifact.

### Phase 1 Completion

| Dimension | Result |
|---|---|
| Scope | HOLD SCOPE; no candidate or runtime expansion |
| External CEO voice | 11 findings; 7 incorporated, 2 partially incorporated through strata/limitations, 2 rejected because they conflict with settled provenance or do not invalidate same-protocol candidate deltas |
| Critical gaps after fixes | 0 |
| UI review | Skipped; no UI scope |
| Deferred items | E3-B through E3-F, query rewrite, segmentation, OCR, HTTP, UI |

### Phase 2: Engineering Review

**Result:** CLEAR after incorporating 12 findings. The review kept E3-A evaluation-only and
changed evidence integrity, not product runtime behavior.

#### Dependency Graph

```text
Task 1 corpus + complete partition judgments
  -> Task 2 strict protocol
      -> Task 3 pure metrics
      -> Task 4 domain-truth/FTS diagnostics + clause diagnostics
          -> Task 5 report contract
              -> Task 6 partition-isolated runner
                  -> Task 7 artifact validators + crash-recoverable set refresh
                      -> Task 8 CLI + offline installed-wheel proof
                          -> Task 9 canonical observation
                              -> Task 10 docs
                                  -> Task 11 verification/handoff
```

Tasks 3 and 4 may run in parallel after Task 2. All later tasks are sequential because their
schemas and evidence contracts depend on prior outputs.

#### Test Coverage Map

| Codepath | Primary tests |
|---|---|
| Frozen bytes and 1,680 ordered judgments | `test_chinese_fixture_corpus.py`, `test_chinese_protocol.py` |
| Metrics and query strata | `test_graded_metrics.py` |
| Domain Evidence vs FTS projection integrity | `test_sqlite_fts.py` |
| AND/OR clause diagnostics and miss symptoms | `test_chinese_diagnostics.py` |
| Human/JSON/public-safe report | `test_chinese_report.py` |
| Four-workspace partition isolation, Search/Ask trace, determinism | `test_chinese_runner.py` |
| Artifact schema, rank evidence, source identity, shallow clone | `test_chinese_artifact.py` |
| Four-file journaled refresh, restart recovery, and rollback | `test_artifact_refresh.py` |
| CLI usage/help/errors | `test_cli_evaluation.py` |
| Offline source-tree isolation on Python 3.12/3.13 | `test_chinese_deployment_proof.py` |

#### Performance And Storage Budget

- One partition snapshot is retained at a time; reports/artifacts never copy raw Evidence text.
- Rank observations store digests rather than full text or unbounded SQL output.
- CI performs one explicit authoritative E3-A run per environment; validation does not re-ingest.
- Final verification records wall time, peak RSS, and SQLite size against the fixed Task 11
  budgets. Budget failure returns to planning.

#### Engineering Findings Resolved

1. Development and holdout now use separate corpora and duplicate workspaces.
2. Active Evidence comes from domain truth; FTS projection is verified independently.
3. Qrel review stores every page judgment and derives counts.
4. Unsupported inter-rater disagreement claims were removed.
5. Rank and `bm25()` probes use production-equivalent joins, filtering, ordering, and full sets.
6. Miss symptoms use actual compiled AND/OR clause semantics.
7. Canonical artifacts bind per-query rank evidence.
8. E1/E2/E3-A refresh is a journaled, crash-recoverable set transaction.
9. Direct Search, Ask Search, and rank probes have separate trace evidence.
10. Installed-wheel proof is offline and source-tree hostile.
11. CI has explicit runtime, memory, and database budgets.
12. Private restore-path metadata was removed and remains covered by the public-boundary scan.

### Phase 3: Developer Experience Review

**Mode:** DX POLISH. **Product type:** OSS evaluation CLI plus documentation. **Result:** CLEAR
after incorporating nine findings. No UI, hosted service, telemetry, community-program, or API
expansion was accepted.

#### Developer Persona Card

```text
Who:       OSS contributor/operator reproducing and inspecting MKE retrieval behavior
Context:   Starts from a repository checkout with uv installed
Tolerance: 2-5 minutes to a meaningful first report; will inspect JSON for automation
Expects:   one copy-paste path, visible progress, stable exits/errors, offline reproducibility
```

#### Developer Perspective

The contributor opens README, sees the existing proof and retrieval commands, and expects E3-A to
fit the same pattern. They should not need to find the spec or implementation plan. After one
copy-paste block, stderr confirms bounded phases while stdout ends with four lines that separate
integrity, observed quality, and E3-B eligibility. If the command fails, the stable
`problem/cause/next_step` triple points to one documented recovery command. JSON and artifact
validation remain separate advanced paths, so automation is predictable and a successful
evaluation is not confused with a validated checked-in artifact.

#### Relevant DX Baseline

| Surface | First useful result | Reused E3-A pattern |
|---|---|---|
| `mke proof run` | one command after locked sync; human and JSON output | command discoverability and result-first summary |
| `mke eval retrieval` | one manifest-owned command | integrity vs quality separation |
| `mke eval retrieval-numeric` | one protocol-owned command | candidate verdict and public holdout language |
| E3-A target | one protocol-owned command, 2-5 minutes | progress on stderr, result-first stdout, exact recovery |

#### Magical Moment

```bash
uv sync --locked &&
uv run mke eval retrieval-chinese \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json
```

The first report must immediately answer:

1. Was the observation trustworthy?
2. What quality was observed?
3. Does the predeclared rule justify E3-B?

#### Developer Journey

| Stage | Developer action | Planned friction control |
|---|---|---|
| Discover | README/docs index | E3-A command and how-to are linked beside E1/E2 |
| Install | `uv sync --locked` | one locked command; no model/network operation in evaluation |
| First run | copy-paste the two-command block | stable progress phases and 2-5 minute target |
| Interpret | read first four stdout lines | integrity, quality, and eligibility are separate |
| Automate | add `--json`, then run validator separately | exact schema and independent exit semantics |
| Debug | follow `next_step` | recovery table maps stable token to command |
| Package proof | run Python 3.12/3.13 script | offline, external cwd, hostile environment, bounded output |
| Roll back | revert E3-A | no migration; restore bound artifact identities through the revert |

#### First-Time Confusion Report

```text
T+0:00  README shows the E3-A first-run block.
T+0:30  locked sync starts; the documented target and cache assumption are visible.
T+1:00  human stderr reports protocol_validated, then partition progress.
T+2:00  stdout prints integrity, quality, eligibility, then detailed metrics.
T+2:30  contributor knows whether E3-B is justified and where the canonical artifact lives.
```

Addressed confusion points: command discovery, silent long run, result hierarchy, artifact
validation distinction, and exact recovery.

#### DX Scorecard

| Dimension | Before | After |
|---|---:|---:|
| Getting Started | 4/10 | 9/10 |
| CLI Design | 6/10 | 9/10 |
| Errors And Debugging | 6/10 | 9/10 |
| Documentation | 5/10 | 9/10 |
| Upgrade And Migration | 8/10 | 9/10 |
| Environment And Tooling | 7/10 | 9/10 |
| Community And Ecosystem | 8/10 | 8/10 |
| DX Measurement | 5/10 | 9/10 |

Target TTHW is 2-5 minutes with `uv` and a warm dependency cache. The repository-owned
measurement helper records rather than telemeters this evidence.

#### DX Findings Resolved

1. Added the first-run path to README and the getting-started tutorial.
2. Locked result-first human stdout.
3. Separated evaluation and artifact-validator exit semantics.
4. Locked the complete JSON top-level schema and `e3b_reason`.
5. Added stable human progress on stderr and silent JSON mode.
6. Locked exact error triples and recovery commands.
7. Split tutorial, how-to, reference, and navigation responsibilities.
8. Added timeout, bounded capture, and stable output to installed-wheel proof.
9. Added repository-owned TTHW/resource measurement without telemetry.

#### DX Implementation Checklist

- [ ] First-run block is copy-pasteable from README and tutorial.
- [ ] First human report appears within the 300-second supported target.
- [ ] Human progress is ordered, redacted, and absent in JSON mode.
- [ ] First four stdout lines separate integrity, quality, and E3-B eligibility.
- [ ] JSON field set, exits, and error triples are exact and tested.
- [ ] Recovery tokens map to copy-paste commands.
- [ ] Installed-wheel proof is offline, isolated, bounded, and runs on Python 3.12/3.13.
- [ ] Measurement helper records TTHW/runtime/RSS/SQLite size without telemetry.
- [ ] Additive upgrade and complete rollback are documented.

#### Explicit DX Non-Scope

- Web UI, hosted playground, dashboard, artifact explorer, or comparison visualization.
- Telemetry, analytics service, remote benchmark collection, or user tracking.
- Generic community portal, Discord, issue bot, or template expansion.
- New API/MCP surface, runtime selector, fixture/model auto-download, or general-purpose corpus
  framework.
- Demo video or GIF before E3-F chooses a strategy worth demonstrating.

### Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | Keep E3-A scope unchanged | Mechanical | HOLD SCOPE | A trustworthy baseline is the prerequisite; algorithms would confound it | Add candidate code |
| 2 | CEO | Replace causal taxonomy with mechanical miss symptoms | Auto | Explicit over clever | Artifact facts must be independently derivable | Infer cause from query category |
| 3 | CEO | Require complete partition-corpus qrel review | Auto | Completeness | nDCG/hard-negative metrics require complete relevance judgments without leaking holdout corpus into development | Validate only listed locators |
| 4 | CEO | Split Ask outcomes into three rates | Auto | Explicit over clever | Input rejection is not retrieval refusal | Combined refusal rate |
| 5 | CEO | Add compiled-query and ASCII-token strata | Auto | Pragmatic | Distinguishes pure-CJK failure from ASCII-anchor behavior without expanding query count | Add another query tranche |
| 6 | CEO | Verify rank/BM25 for every non-empty query | Auto | Completeness | One smoke probe cannot support a global scorer claim | Single-query proof |
| 7 | CEO | Freeze one-observation holdout governance | Auto | Completeness | Visible holdout must not become a tuning set | Unlimited holdout reruns |
| 8 | CEO | Freeze an evidence-based E3-B start rule | Auto | Bias toward action | Prevents post-hoc candidate justification | Decide after seeing results |
| 9 | CEO | Retain current dev/holdout document allocation | Settled scope | Pragmatic | Same-protocol algorithm deltas remain interpretable; limitation is explicit | Rebuild corpus |
| 10 | CEO | Retain complete E1/E2 source identity and restricted refresh | Settled decision | DRY | Preserves existing approved provenance policy and semantic equality checks | Narrow identity ad hoc |
| 11 | Eng | Isolate development and holdout corpora | Auto | Correctness | Prevents holdout document leakage and makes qrel split rules executable | One shared 70-page corpus |
| 12 | Eng | Read domain Evidence separately from FTS projection | Auto | Explicit over clever | Projection corruption must not redefine domain truth | Snapshot through FTS join |
| 13 | Eng | Persist every page judgment | Auto | Completeness | Coverage must be derived from records, not summary claims | Sparse qrels plus declared counts |
| 14 | Eng | Remove inter-rater disagreement claim | Auto | Correctness | One review pass cannot prove annotator agreement | Constant zero-disagreement field |
| 15 | Eng | Verify full production-equivalent rank ordering | Auto | Completeness | Evidence must cover joins, stale rows, ties, and results beyond top 10 | Evidence-ID ordered probe |
| 16 | Eng | Diagnose compiled clauses, not token counts | Auto | Correctness | FTS AND/OR semantics determine whether a direct page can match | Flat term occurrence counts |
| 17 | Eng | Bind rank evidence in the artifact | Auto | Completeness | A global profile string is not independently inspectable evidence | Profile label only |
| 18 | Eng | Refresh bound artifacts through a recovery journal | Auto | Reversibility | Multi-file replacement is not atomic, so interrupted work must be recoverable on restart | Unjournaled sequential refresh |
| 19 | Eng | Separate Search, Ask, and rank-probe traces | Auto | Explicit over clever | Each operation has a different expected MATCH count | One aggregate statement count |
| 20 | Eng | Reuse offline hostile-environment wheel proof | Auto | DRY | Existing deployment proof establishes the required isolation standard | CI-only external cwd check |
| 21 | Eng | Add fixed CI resource budgets | Auto | Pragmatic | Four workspaces and PDF ingestion must fit the existing job timeout | Unbounded evaluation |
| 22 | Eng | Remove private restore metadata | Mechanical | Public boundary | Repository docs cannot contain workstation paths or raw tooling state | Commit restore comment |
| 23 | DX | Add README/tutorial first-run path | Auto | Zero friction | Contributors should not discover E3-A through implementation history | How-to-only navigation |
| 24 | DX | Lock result-first human stdout | Auto | Fight uncertainty | Integrity, quality, and eligibility are different decisions | Unordered field collection |
| 25 | DX | Separate evaluation and artifact exits | Auto | Explicit over clever | Run integrity does not prove checked-in artifact validity | One overloaded success claim |
| 26 | DX | Lock exact JSON schema and `e3b_reason` | Auto | Completeness | Automation and human interpretation require stable meaning | DTO/schema drift |
| 27 | DX | Emit bounded progress only for human mode | Auto | Speed is a feature | A multi-minute silent command looks hung | No progress or noisy JSON stderr |
| 28 | DX | Lock exact recovery tokens | Auto | Fight uncertainty | Every failure needs a copy-paste next action | Generic inspect/fix wording |
| 29 | DX | Preserve Diataxis roles | Auto | Progressive disclosure | First run, interpretation, reference, and validation serve different needs | One oversized how-to |
| 30 | DX | Bound installed-wheel subprocesses and output | Auto | Credibility | Offline proof must fail closed and remain debuggable | Environment identity only |
| 31 | DX | Measure warm-cache TTHW without telemetry | Auto | Pragmatic | Resource budgets need a reproducible developer-facing method | Unspecified manual timing |

## Required Implementation Skills

At execution time:

1. `superpowers:using-git-worktrees`
2. `superpowers:executing-plans` or `superpowers:subagent-driven-development`
3. `superpowers:test-driven-development`
4. `superpowers:verification-before-completion`
5. `gstack-document-release` for the final documentation audit

Use `superpowers:receiving-code-review` only after the planning window returns verified findings.

## Explicit Non-Scope

- E3-B CJK lexical candidate or tokenizer selection.
- E3-C embedding model or `sqlite-vec` selection.
- Dense/vector retrieval.
- RRF or weighted fusion.
- Reranking.
- Query rewrite or HyDE.
- Passage/chunk segmentation.
- OCR or scanned PDFs.
- HTTP, UI, hosted runtime, auth, or multi-tenancy.
- Model download or API credentials.
- Runtime strategy promotion, migration, or rollback changes.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|---|---|---|---:|---|---|
| CEO Review | `/plan-ceo-review` | Scope and evidence strategy | 1 | CLEAN | HOLD SCOPE; 11 outside-voice findings evaluated, 9 incorporated or partially incorporated, 2 rejected against settled decisions |
| Codex Review | `/codex review` | Independent implementation diff | 0 | SKIPPED | Plan-only branch; no implementation diff exists |
| Eng Review | `/plan-eng-review` | Architecture, data flow, tests, operations | 1 | CLEAN | 12 issues resolved; 0 critical gaps remain |
| Design Review | `/plan-design-review` | UI/visual interaction | 0 | SKIPPED | No UI scope |
| DX Review | `/plan-devex-review` | CLI and documentation experience | 1 | CLEAN | Score 6/10 to 9/10; estimated TTHW 5-9 minutes to target 2-5 minutes |

- **CODEX:** Independent read-only voices reviewed CEO, engineering, and DX phases; accepted
  findings are represented in the spec, plan, and durable review.
- **VERDICT:** CEO + ENG + DX CLEARED — ready for E3-A implementation.

NO UNRESOLVED DECISIONS
