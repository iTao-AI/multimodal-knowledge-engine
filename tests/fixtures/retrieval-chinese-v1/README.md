# Chinese Retrieval V1 Fixtures

This directory freezes a small public Chinese page-level corpus for the E3-A lexical baseline.
It contains one development technical document, two public holdout law documents, and two
repository-authored adversarial fixtures. Development and holdout are evaluated as separate
corpora.

The corpus is public and intentionally small. The holdout is visible rather than statistically
blind, the real documents cover different domains, and the selected Evidence is limited to
deterministic text-layer PDF pages. These fixtures do not support a claim of general Chinese
retrieval quality, arbitrary PDF support, OCR support, or production readiness.

## Frozen Identity And Provenance

All source bytes were retrieved or generated once, inspected outside the repository, and copied
into this directory only after byte size, page count, extracted character count, and SHA-256
verification. The retrieval date is `2026-06-25`.

| Partition | File | Title and publisher | Source | Pages | Bytes | SHA-256 |
|---|---|---|---|---:|---:|---|
| development | `development/ub-service-core-2.0-zh.pdf` | `灵衢®系统高阶服务软件架构参考设计`, Huawei Technologies Co., Ltd. / unifiedbus.com | [openEuler project source](https://www.openeuler.org/projects/ub-service-core/white-paper/UB-Service-Core-SW-Arch-RD-2.0-zh.pdf) | 26 | 1,168,641 | `13e8f1da824de892931653e17df2a8b20f77fe84b2a7472b13113405efbf296d` |
| development | `development/adversarial.pdf` | `MKE development adversarial Chinese retrieval fixture`, Multimodal Knowledge Engine | Repository-authored fixture | 8 | 4,350 | `be3b88352b0a80d6d165de146ff81be224b706d3eb3721d969266e64505af8dd` |
| holdout | `holdout/copyright-law-2020.pdf` | `中华人民共和国著作权法`, National People's Congress public legal text | [Chongqing Administration for Market Regulation source](https://scjgj.cq.gov.cn/zt_225/cjscjz/zcfg/flv/202308/P020230822697998631731.pdf) | 14 | 182,479 | `e1217f1df0bb98586a883819505f17a29140fb114ce5f1a444ea0a60d22c9d2b` |
| holdout | `holdout/administrative-compulsion-law-2011.pdf` | `中华人民共和国行政强制法`, National People's Congress public legal text | [State Administration of Foreign Exchange source](https://www.safe.gov.cn/heilongjiang/file/file/20190426/a520a4e30df34b8bafd708231731dab9.pdf) | 14 | 198,629 | `80d1a49a1641f73f53df7f2cfe008b4f8e8419a538f37d183f9758ec52e90d0d` |
| holdout | `holdout/adversarial.pdf` | `MKE holdout adversarial Chinese retrieval fixture`, Multimodal Knowledge Engine | Repository-authored fixture | 8 | 4,399 | `52d2319515195c7a0b8572f4a6f86eec6856cb189a24f3272c2792ad5fe76924` |

Page 2 of the openEuler technical document states that use is governed by
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode.txt). The two law documents are
laws or official state documents covered by Article 5 of the Copyright Law of the People's
Republic of China. The two adversarial fixtures were authored for this repository.

## Extracted Character Counts

The tuple order is PDF page order. Counts use PyMuPDF
`page.get_text("text", sort=True)` without normalization.

```python
{
    "development/ub-service-core-2.0-zh.pdf": (
        77, 410, 4089, 388, 1864, 764, 418, 1231, 694, 711, 651, 683, 463,
        783, 303, 539, 635, 400, 478, 634, 625, 516, 818, 429, 939, 870,
    ),
    "development/adversarial.pdf": (60, 41, 59, 57, 34, 31, 32, 32),
    "holdout/copyright-law-2020.pdf": (
        874, 917, 929, 1027, 1006, 992, 810, 920, 942, 949, 980, 1028,
        1046, 422,
    ),
    "holdout/administrative-compulsion-law-2011.pdf": (
        490, 826, 665, 745, 803, 806, 802, 746, 816, 776, 854, 781, 747, 758,
    ),
    "holdout/adversarial.pdf": (46, 43, 46, 44, 33, 30, 68, 47),
}
```

## Generated Fixture Text

`development/adversarial.pdf` contains exactly:

1. `星河调度平台将任务检查间隔设为 45 秒。该策略自 2026 年 3 月 15 日起生效，单次最多处理 240 个任务。`
2. `星河归档平台每 45 分钟执行一次历史清理。该任务只删除超过 90 天的临时文件。`
3. `DataBridge X7 网关负责将边缘事件写入中心消息队列，并使用 FlowToken A-731 标识路由批次。`
4. `DataBridge X9 网关只负责读取设备状态，不写入中心消息队列，也不使用 FlowToken A-731。`
5. `蓝湖缓存服务在节点失联时保留最近一次有效快照，并拒绝发布不完整索引。`
6. `蓝湖缓存服务在磁盘空间不足时进入只读模式，但不会切换活动索引。`
7. `青岚分析引擎只有在来源校验通过且索引构建完成后，才切换活动版本。`
8. `青岚分析引擎在来源校验失败时记录告警；索引构建任务保持候选状态。`

`holdout/adversarial.pdf` contains exactly:

1. `海岳审计终端 AuditNode R5 的日志保留期为 180 天，超过期限后进入离线归档。`
2. `海岳监控终端 AuditNode R3 的指标保留期为 18 天，超过期限后直接删除。`
3. `云舟路由服务使用 RouteKey ZH-2048 标识跨区域路由，并拒绝未知租户的数据包。`
4. `云舟存储服务使用 StorageKey ZH-2048 标识归档批次，不参与跨区域路由。`
5. `松涛归档器只有在主副本校验一致且审批状态为通过时，才发布归档索引。`
6. `松涛归档器在审批未通过时保留候选索引，并记录主副本校验结果。`
7. `北辰采集代理 PolicySync V2 每 12 秒上报一次心跳，单批最多 320 条记录，自 2025 年 11 月 8 日起生效。`
8. `北辰同步代理 PolicySync V1 每 12 分钟同步一次配置，单批最多 32 条记录。`

The generated fixtures use PyMuPDF `1.27.2.3`, the built-in `china-s` font, 612 by 792 point
pages, 12-point text, and `document.save(..., garbage=4, deflate=True, clean=True)`. The
planning-time command was:

```bash
UV_OFFLINE=1 uv run python generate.py
```

The generator created one page per exact string with `page.insert_textbox(...)`, set
repository-owned title/author/subject metadata, and failed if any text did not fit.

## Qrel Review

`qrel-adjudication.json` records one complete partition-page review performed on `2026-06-25`.
Each of the 24 development queries has 34 judgments in stable document/page order. Each of the 24
holdout queries has 36 judgments in stable document/page order. The 1,680 total judgments use
grade `2` for independently answer-capable Evidence, grade `1` for relevant but insufficient
Evidence, grade `0` for a protocol-designated confuser, and `non_relevant` for every remaining
page.

The qrels in `protocol.json` are derived from the non-`non_relevant` judgments. The review records
one completed adjudication and makes no inter-rater agreement claim.
