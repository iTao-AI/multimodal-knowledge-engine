# Chinese Retrieval Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic offline E3-A Chinese retrieval baseline that freezes five approved
text-layer PDFs, 48 development/holdout queries, graded page qrels, failure classifications, and a
canonical artifact without changing runtime retrieval behavior.

**Architecture:** A new strict `mke.retrieval_chinese_protocol.v1` protocol sits beside E1 rather
than widening the binary E1 schema. The evaluator snapshots exact fixture bytes, ingests all PDFs
through the normal `KnowledgeEngine`, reads active Evidence through a narrow diagnostic DTO,
executes the existing `numeric-grouping-v1` FTS5 strategy in two fresh workspaces, computes graded
metrics, verifies FTS5 `rank` against `bm25()`, classifies every direct-Evidence miss, and records a
content-addressed artifact. Existing Search, Ask, Publication, E1, E2, CLI, MCP, and runtime
defaults remain unchanged.

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

The command returns `0` when protocol, fixture, qrel, ingestion, determinism, report, and artifact
integrity pass. Low Recall, MRR, nDCG, unanswerable no-hit, or Ask-refusal values do not cause
exit `1`.

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
| `zh-hold-hard-01` | `ranking_hard_negative` | `查封扣押与冻结期限分别如何规定` | `administrative-compulsion-law:p6=2`, `administrative-compulsion-law:p7=2`, `administrative-compulsion-law:p8=1` |
| `zh-hold-hard-02` | `ranking_hard_negative` | `哪个北辰代理每12秒上报心跳` | `holdout-adversarial:p7=2`, `holdout-adversarial:p8=0` |
| `zh-hold-unanswerable-01` | `unanswerable` | `著作权法是否要求区块链存证使用国密算法` | none |
| `zh-hold-unanswerable-02` | `unanswerable` | `AuditNode R5 是否支持人脸识别` | none |

The protocol uses `zh-dev-exact-02` as the FTS5 rank probe because its current compiled query is
non-empty and produces multiple rows.

---

## File Map

### New Evaluation Files

- `src/mke/evaluation/chinese_protocol.py`: strict protocol DTOs, graded qrels, fixture
  validation, and immutable snapshot copy.
- `src/mke/evaluation/graded_metrics.py`: pure graded metrics and category aggregates.
- `src/mke/evaluation/chinese_diagnostics.py`: compiled-query diagnostics and deterministic
  failure classification.
- `src/mke/evaluation/chinese_report.py`: E3-A result/report DTOs and human/JSON rendering.
- `src/mke/evaluation/chinese_runner.py`: two-workspace orchestration using normal ingest,
  current Search, current Ask, active Evidence, rank verification, and determinism checks.
- `src/mke/evaluation/chinese_artifact.py`: canonical artifact recording and independent
  validation.
- `src/mke/evaluation/baseline.py`: add a source-identity-only refresh command that preserves and
  revalidates the historical E1 observation.
- `src/mke/evaluation/numeric_comparison.py`: add a scope-fence-only refresh command that
  preserves and revalidates the E2 protocol semantics.

### Modified Product Files

- `src/mke/domain/__init__.py`: add a read-only `ActiveEvidenceSnapshot` diagnostic DTO.
- `src/mke/adapters/sqlite/__init__.py`: enumerate full active Evidence snapshots and observe FTS5
  `rank` versus `bm25()` for one compiled query.
- `src/mke/application/__init__.py`: expose active Evidence snapshots for evaluation.
- `src/mke/evaluation/__init__.py`: export E3-A runner and renderers.
- `src/mke/cli.py`: add `mke eval retrieval-chinese`.

### Fixtures And Artifacts

- `tests/fixtures/retrieval-chinese-v1/protocol.json`
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
- `tests/evaluation/test_baseline.py`
- `tests/evaluation/test_numeric_comparison.py`
- `tests/adapters/test_sqlite_fts.py`
- `tests/interfaces/test_cli_evaluation.py`

### CI And Documentation

- `.github/workflows/ci.yml`
- `README.md`
- `README_CN.md`
- `docs/README.md`
- `docs/reference/cli.md`
- `docs/reference/contracts.md`
- `docs/how-to/run-chinese-retrieval-evaluation.md`
- `docs/explanation/architecture.md`
- `docs/superpowers/plans/2026-06-25-chinese-retrieval-baseline-implementation.md`
- `docs/superpowers/reviews/2026-06-25-chinese-retrieval-baseline-autoplan-review.md`
- `docs/superpowers/reviews/2026-06-25-chinese-retrieval-baseline-review.md`

---

### Task 1: Freeze The Approved Corpus And Protocol

**Files:**
- Create: `tests/evaluation/test_chinese_fixture_corpus.py`
- Create: `tests/fixtures/retrieval-chinese-v1/protocol.json`
- Create: `tests/fixtures/retrieval-chinese-v1/README.md`
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

- [ ] **Step 5: Create the strict protocol JSON**

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
Do not add candidate configuration or a quality threshold.

- [ ] **Step 6: Create the provenance README**

Record:

- exact titles, publishers, source URLs, retrieval date `2026-06-25`, bytes, page counts,
  character tuples, and SHA-256 values;
- openEuler page-2 CC BY 4.0 statement and license URL;
- Article 5 redistribution basis for both laws;
- exact generated page text and the planning-time generation command/runtime
  (`PyMuPDF 1.27.2.3`, built-in `china-s`, 612x792 points, 12 points,
  `garbage=4`, `deflate=True`, `clean=True`);
- public holdout and small-engineering-corpus limitations.

- [ ] **Step 7: Run the fixture test to verify GREEN**

Run:

```bash
uv run pytest tests/evaluation/test_chinese_fixture_corpus.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add tests/evaluation/test_chinese_fixture_corpus.py \
  tests/fixtures/retrieval-chinese-v1/protocol.json \
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
class ChineseRetrievalProtocol:
    schema_version: str
    protocol_id: str
    rank_probe_query_id: str
    root: Path
    documents: tuple[ChineseEvaluationDocument, ...]
    queries: tuple[ChineseEvaluationQuery, ...]
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
- Ask refusal counts `insufficient_evidence` or `invalid_question`;
- Ask invalid-question rate is separately reported;
- macro aggregation is stable and rounded only in `MetricValue.value`;
- category aggregates include all eight categories;
- invalid duplicate retrieved locators, unsupported Ask statuses, or answerable input without
  grade `2` raises `ValueError`.

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
    ask_refusal_rate: MetricValue
    ask_invalid_question_rate: MetricValue
    category_metrics: tuple[CategoryMetrics, ...]
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
- Modify: `src/mke/domain/__init__.py`
- Modify: `src/mke/adapters/sqlite/__init__.py`
- Modify: `src/mke/application/__init__.py`
- Modify: `tests/adapters/test_sqlite_fts.py`
- Create: `tests/evaluation/test_chinese_diagnostics.py`
- Create: `src/mke/evaluation/chinese_diagnostics.py`

- [ ] **Step 1: Write active-snapshot and rank-observation RED tests**

Require:

```python
@dataclass(frozen=True)
class ActiveEvidenceSnapshot:
    evidence_id: str
    publication_id: str
    source_id: str
    locator_kind: str
    locator_start: int
    locator_end: int
    text: str
```

Tests must prove:

- snapshot enumeration returns only rows belonging to each Source's active Publication;
- a failed reprocess leaves the old snapshot unchanged;
- order is stable by `source_id`, locator, and `evidence_id`;
- `observe_fts5_rank('"hcom"')` returns `rank` and `bm25()` values that are finite and equal;
- no persistent `rank` override exists in `active_evidence_fts_config`;
- empty/invalid match input is rejected without SQL execution.

- [ ] **Step 2: Run RED**

```bash
uv run pytest tests/adapters/test_sqlite_fts.py -q
```

Expected: failures because the new DTO/methods do not exist.

- [ ] **Step 3: Implement the read-only snapshot**

Add `list_active_evidence_snapshots(self) -> list[ActiveEvidenceSnapshot]`.

The SQL must join `evidence`, `sources`, and `active_evidence_fts`, and require:

```sql
sources.active_publication_id = active_evidence_fts.publication_id
AND evidence.evidence_id = active_evidence_fts.evidence_id
```

Expose the same method through `KnowledgeEngine`. Do not change `list_active_evidence()`.

- [ ] **Step 4: Implement rank observation**

Add a SQLite adapter diagnostic method
`observe_fts5_rank(self, match_query: str) -> tuple[tuple[str, float, float], ...]`.

Execute:

```sql
SELECT evidence_id, rank, bm25(active_evidence_fts)
FROM active_evidence_fts
WHERE active_evidence_fts MATCH ?
ORDER BY evidence_id
```

Also expose whether `active_evidence_fts_config` contains a `rank` row. The E3-A runner accepts
the profile only when the override is absent and every score pair is exactly equal or
`math.isclose(..., rel_tol=0.0, abs_tol=1e-12)`.

- [ ] **Step 5: Implement deterministic failure classification**

Create:

```python
FailureClass = Literal[
    "no_searchable_cjk_terms",
    "word_boundary_mismatch",
    "proper_noun_or_mixed_language_mismatch",
    "number_date_or_unit_mismatch",
    "semantic_vocabulary_mismatch",
    "multi_condition_overconstraint",
    "ranking_distractor_ahead",
    "segmentation_or_locator_limitation",
    "other_observed_failure",
]
```

Classification order:

1. grade-`0` ahead of every grade-`2`, or grade-`2` absent while grade-`0` is returned:
   `ranking_distractor_ahead`;
2. empty compiled query: `no_searchable_cjk_terms`;
3. multiple direct qrels whose required facts are split across pages:
   `segmentation_or_locator_limitation`;
4. non-empty compiled query and category-specific mismatch using the approved category mapping;
5. `other_observed_failure`.

Return structured evidence:

```python
@dataclass(frozen=True)
class FailureClassification:
    failure_class: FailureClass
    compiled_query: str
    direct_locators: tuple[StableLocator, ...]
    returned_direct_ranks: tuple[int, ...]
    returned_distractor_ranks: tuple[int, ...]
    explanation: str
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
git add src/mke/domain/__init__.py \
  src/mke/adapters/sqlite/__init__.py \
  src/mke/application/__init__.py \
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
  hard-negative failure, Ask status, compiled query, and optional failure classification;
- FTS5 rank profile `sqlite_fts5_default_bm25`;
- limitations;
- stable integrity failures;
- no raw query text, raw Evidence text, absolute path, random ID, hostname, username, duration in
  the canonical semantic payload, or exception text.

The runtime report may contain `duration_ms`; the artifact must omit it.

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
    failure: FailureClassification | None

@dataclass(frozen=True)
class ChineseRetrievalReport:
    protocol_id: str
    benchmark_scope: Literal["small_public_chinese_page_corpus"]
    quality_gate: Literal["none"]
    status: Literal["passed", "failed"]
    quality_status: Literal["baseline_recorded", "not_recorded"]
    document_count: int
    results: tuple[ChineseQueryResult, ...]
    metrics: GradedRetrievalMetrics | None
    fts5_rank_profile: str | None
    integrity_failures: tuple[IntegrityFailure, ...]
    duration_ms: int
    limitations: tuple[str, ...]
```

Limitations are fixed:

```python
(
    "public_holdout_not_blind",
    "small_engineering_corpus",
    "text_layer_pdf_only",
    "page_level_evidence_only",
    "current_ascii_oriented_query_compilation",
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

### Task 6: Implement The Two-Workspace E3-A Runner

**Files:**
- Create: `src/mke/evaluation/chinese_runner.py`
- Create: `tests/evaluation/test_chinese_runner.py`

- [ ] **Step 1: Write runner RED tests**

Test:

- checked-in protocol passes in two fresh workspaces;
- all five documents publish and every qrel locator resolves uniquely;
- all 48 queries execute in protocol order;
- Search limit is exactly 10;
- a compiled empty query executes zero FTS5 `MATCH` statements;
- a non-empty Search executes one `MATCH`;
- Ask `invalid_question` is recorded only when compiled query is empty;
- valid Ask Search agreement is enforced;
- every grade-`2` miss has a classification;
- low metrics still return `status=passed`;
- FTS5 rank probe is non-empty and proves `rank == bm25()`;
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
-> run workspace 1
-> run workspace 2
-> compare semantic results/evidence
-> return first report with measured duration
```

Workspace flow:

```text
KnowledgeEngine(temp SQLite, query_policy="numeric-grouping-v1")
-> ingest five PDFs
-> map source_id to document_id
-> enumerate ActiveEvidenceSnapshot
-> validate all graded qrels
-> verify rank probe
-> evaluate all 48 queries
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

- [ ] **Step 1: Write artifact RED tests**

Require:

- `record` accepts only a successful observed JSON report matching a freshly loaded protocol;
- `validate` independently reloads protocol/fixtures and recomputes counts, metric values,
  per-category aggregates, hard-negative failures, Ask rates, classifications, and FTS5 rank
  profile consistency;
- the artifact binds all sorted `src/mke/**/*.py` files by path, byte size, SHA-256, and aggregate
  SHA-256;
- the artifact binds protocol and all five fixture identities;
- validation works after squash landing in a shallow fresh clone without feature commit ancestry;
- mutation of any source file, fixture, qrel, metric, result, grade, category, classification,
  compiled query, rank profile, environment version, or limitation fails;
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
    "failure_counts",
    "fts5_rank_profile",
    "results",
    "limitations",
}
```

Environment is limited to Python, SQLite, and PyMuPDF versions. Do not record OS username,
hostname, paths, duration, or Git commit ancestry.

- [ ] **Step 4: Implement restricted E1 and E2 identity refresh commands**

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
  tests/evaluation/test_numeric_comparison.py
git commit -m "feat(eval): validate Chinese retrieval artifact"
```

---

### Task 8: Add CLI And Installed-Wheel Evaluation Proof

**Files:**
- Modify: `src/mke/evaluation/__init__.py`
- Modify: `src/mke/cli.py`
- Modify: `tests/interfaces/test_cli_evaluation.py`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Write CLI RED tests**

Test:

- human and JSON command success;
- exact command help states baseline-only, public holdout, no quality threshold, and no
  dense/hybrid/reranker claim;
- `--db` and `--retrieval-query-policy` remain rejected for all eval commands;
- missing/malformed protocol returns exit `1`, stable public-safe result, no traceback/path;
- rendering failure uses `mke.retrieval_chinese_report.v1` fallback;
- low quality still exits `0`;
- integrity failure exits `1`.

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

Extend the installed-wheel block to run from `$RUNNER_TEMP` with the repository protocol passed by
absolute path. Assert status, document/query counts, empty integrity failures, and installed
`mke.__file__` outside the repository. No network or model is required.

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

- [ ] **Step 2: Record the E3-A artifact**

```bash
uv run python -m mke.evaluation.chinese_artifact record \
  --observed /tmp/mke-e3a.json \
  --artifact benchmarks/retrieval/retrieval-chinese-v1-baseline.json \
  --protocol tests/fixtures/retrieval-chinese-v1/protocol.json \
  --repository .
```

- [ ] **Step 3: Refresh the restricted E1/E2 identities and re-record E2**

Run:

```bash
uv run python -m mke.evaluation.baseline refresh-source \
  --artifact benchmarks/retrieval/retrieval-eval-v1-baseline.json \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --repository . \
  --main-ref main
uv run python -m mke.evaluation.numeric_comparison refresh-scope \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --repository .
uv run mke eval retrieval-numeric \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --json > /tmp/mke-e2.json
uv run python -m mke.evaluation.numeric_artifact record \
  --observed /tmp/mke-e2.json \
  --artifact benchmarks/retrieval/numeric-grouping-v1-comparison.json \
  --protocol tests/fixtures/retrieval-numeric-v1/protocol-lock.json \
  --repository .
```

Compare `/tmp/mke-e1.json` and `/tmp/mke-e2.json` against the checked-in canonical semantic
payloads before replacement. E1 and E2 observations, metrics, gates, candidate verdict, query
order, and per-query results must remain byte-for-byte equal after excluding only their declared
identity/environment fields. Stop if any semantic field changes.

- [ ] **Step 4: Validate all artifacts**

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

- [ ] **Step 5: Commit**

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

- [ ] **Step 2: Write the how-to**

Include:

- command and JSON command;
- protocol layout and 48-query allocation;
- graded-qrel and metric semantics;
- interpretation of `status=passed` versus observed quality;
- `invalid_question` versus `insufficient_evidence`;
- failure taxonomy;
- canonical artifact validation;
- fixture provenance and public-holdout limits.

- [ ] **Step 3: Update public navigation and architecture**

Add E3-A as a separate evaluation surface. Do not draw vector/RRF/reranker modules as implemented;
keep them in an explicitly future/evidence-gated paragraph.

- [ ] **Step 4: Run document-release audit**

Run `gstack-document-release` in audit mode. Apply only E3-A-required documentation fixes. Do not
create a release, bump a version, push, or update a PR.

- [ ] **Step 5: Commit**

```bash
git add README.md README_CN.md docs/README.md \
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
assert payload["status"] == "passed"
assert payload["quality_status"] == "baseline_recorded"
assert payload["documents"] == 5
assert payload["queries"] == 48
assert payload["split_counts"] == {"development": 24, "holdout": 24}
assert payload["integrity_failures"] == []
assert payload["fts5_rank_profile"] == "sqlite_fts5_default_bm25"
```

- [ ] **Step 4: Run installed-wheel proof on Python 3.12 and 3.13**

Build the wheel, install it offline into isolated temporary environments using lock-derived
constraints, clear `PYTHONPATH`, `PYTHONHOME`, and `VIRTUAL_ENV`, run from outside the repository,
verify installed module identity, and execute `mke eval retrieval-chinese` with the external
protocol path.

- [ ] **Step 5: Run diff and public-boundary checks**

```bash
git diff --check main...HEAD
rg -n "/Users/|Career|求职|面试|\\.gstack|API_KEY|token|secret" \
  README.md README_CN.md docs benchmarks tests/fixtures/retrieval-chinese-v1
```

Review every match; expected public technical uses of “token” are allowed, private paths and
private motivation are not.

- [ ] **Step 6: Perform lightweight pre-handoff review**

Confirm:

- no runtime retrieval behavior changed;
- no CJK, dense, hybrid, RRF, or reranker candidate code exists;
- no model or vector dependency was added;
- no network operation exists in evaluation runtime or CI;
- old active Publication behavior and all proof commands remain green;
- every observed grade-`2` miss is classified;
- the durable review reports actual commands and results.

Do not run the final authoritative `gstack-review`; the separate planning/review window owns that
step before PR creation.

- [ ] **Step 7: Commit final completion records**

```bash
git add docs/superpowers/plans/2026-06-25-chinese-retrieval-baseline-implementation.md \
  docs/superpowers/reviews/2026-06-25-chinese-retrieval-baseline-review.md
git commit -m "docs(eval): record Chinese baseline verification"
```

- [ ] **Step 8: Return the clean local branch**

Report:

- branch, base, HEAD, commit list, and diff stat;
- exact targeted/full verification;
- E1/E2 unchanged evidence;
- E3-A metrics, failure taxonomy, FTS5 rank profile, and artifact SHA-256;
- fixture identities and redistribution evidence;
- remaining E3-B decision boundary;
- clean worktree;
- no push, PR, candidate implementation, or complete `gstack-review`.

---

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
