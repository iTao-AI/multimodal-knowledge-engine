import hashlib
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

import mke.adapters.sqlite as sqlite_adapter
from mke.application import KnowledgeEngine
from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    CandidateEvidence,
    ManifestValidationError,
    RunManifest,
)
from mke.retrieval.errors import RetrievalAuthorityError
from mke.retrieval.mixed_cjk_fts_intent import (
    MIXED_CJK_FTS_INTENT_PARAMETERS,
    MixedCjkFtsIntentError,
)
from mke.retrieval.strategy import RetrievalStrategyDescriptor


def test_mixed_strategy_keeps_distinct_cjk_intents_for_ascii_anchors(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mke.sqlite"
    publisher = KnowledgeEngine(db_path)
    try:
        _publish_text(
            publisher,
            "intent-cases.pdf",
            "a" * 64,
            (
                "anchoralpha 账户余额调整流程应保留原始凭证。",
                "anchoralpha 审计权限审批流程应记录授权人。",
                "anchorbeta 设备扩展部署方案应保留版本信息。",
                "anchorbeta 数据泄露处置方案应记录通知步骤。",
            ),
        )
    finally:
        publisher.close()

    rollback = KnowledgeEngine(db_path, retrieval_strategy="numeric-grouping-v1")
    try:
        old_orders = {
            "anchoralpha 账户余额调整流程": [1, 2],
            "anchoralpha 审计权限审批流程": [1, 2],
            "anchorbeta 设备扩展部署方案": [3, 4],
            "anchorbeta 数据泄露处置方案": [3, 4],
            "anchoralpha 服务器退役处理流程": [1, 2],
        }
        for query, expected_locators in old_orders.items():
            assert [
                result.locator_start for result in rollback.search(query)
            ] == expected_locators
    finally:
        rollback.close()

    engine = KnowledgeEngine(
        db_path,
        retrieval_strategy="mixed-cjk-fts-intent-v1",  # type: ignore[arg-type]
    )
    try:
        expected_by_query = {
            "anchoralpha 账户余额调整流程": [1],
            "anchoralpha 审计权限审批流程": [2],
            "anchorbeta 设备扩展部署方案": [3],
            "anchorbeta 数据泄露处置方案": [4],
            "anchoralpha 服务器退役处理流程": [],
        }

        for query, expected_locators in expected_by_query.items():
            assert [result.locator_start for result in engine.search(query)] == (
                expected_locators
            )
    finally:
        engine.close()


def test_mixed_selection_promotes_relevant_evidence_past_fts_top_five(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "mke.sqlite"
    filler = " filler" * 400
    pages = (
        "topanchor unrelated short record one",
        "topanchor unrelated short record two",
        "topanchor unrelated short record three",
        "topanchor unrelated short record four",
        "topanchor unrelated short record five",
        "前缀" * 1300 + " topanchor 海岸撤离路线规划" + filler + " 后缀" * 1000,
        "前缀" * 1000 + " topanchor 海岸撤离路线" + filler + " 后缀" * 1000,
    )
    publisher = KnowledgeEngine(db_path)
    try:
        _publish_text(publisher, "top-five.pdf", "b" * 64, pages)
    finally:
        publisher.close()

    rollback = KnowledgeEngine(db_path, retrieval_strategy="numeric-grouping-v1")
    try:
        old_top_five = rollback.search("topanchor 海岸撤离路线规划", limit=5)
        assert [item.locator_start for item in old_top_five] == [1, 2, 3, 4, 5]
    finally:
        rollback.close()

    engine = KnowledgeEngine(
        db_path,
        retrieval_strategy="mixed-cjk-fts-intent-v1",  # type: ignore[arg-type]
    )
    try:
        limited_search = engine.search("topanchor 海岸撤离路线规划", limit=5)
        ask = engine.ask("topanchor 海岸撤离路线规划", limit=5)
        search_snapshot = engine.search_provenance_snapshot(
            "topanchor 海岸撤离路线规划",
            limit=5,
        )
        ask_snapshot = engine.ask_provenance_snapshot(
            "topanchor 海岸撤离路线规划",
            limit=5,
        )

        assert [item.locator_start for item in limited_search] == [6, 7]
        assert [item.locator_start for item in ask.evidence] == [6, 7]
        assert [item.result.locator_start for item in search_snapshot.results] == [6, 7]
        assert [item.locator_start for item in ask_snapshot.result.evidence] == [6, 7]
    finally:
        engine.close()

    from mke.interfaces.mcp_completeness_contract import search_library_v2
    from mke.interfaces.mcp_contract import McpRuntimeConfig
    from mke.interfaces.mcp_schemas import (
        SearchLibrarySuccessV2,
        SearchLibraryV2Request,
        SearchSelectionMoreV2,
    )
    from mke.runtime import RuntimeConfig

    config = McpRuntimeConfig(
        RuntimeConfig(
            db_path,
            retrieval_strategy="mixed-cjk-fts-intent-v1",  # type: ignore[arg-type]
        ),
        tmp_path,
    )
    first = search_library_v2(
        config,
        SearchLibraryV2Request(root={"query": "topanchor 海岸撤离路线规划", "limit": 1}),
    )
    assert isinstance(first.root, SearchLibrarySuccessV2)
    assert [item.evidence.locator.start for item in first.root.matches] == [6]
    assert isinstance(first.root.selection, SearchSelectionMoreV2)

    mismatched_config = McpRuntimeConfig(
        replace(
            config.runtime,
            retrieval_strategy="cjk-active-scan-overlap-v1",
        ),
        tmp_path,
    )
    mismatched = search_library_v2(
        mismatched_config,
        SearchLibraryV2Request(
            root={"cursor": first.root.selection.next_cursor}
        ),
    )
    assert mismatched.root.problem == "cursor_expired"  # type: ignore[union-attr]

    import mke.interfaces.mcp_completeness_contract as completeness_contract

    original_descriptor = completeness_contract.get_retrieval_strategy_descriptor

    def next_revision(strategy_id: str) -> RetrievalStrategyDescriptor:
        return replace(
            original_descriptor(strategy_id),
            revision=original_descriptor(strategy_id).revision + 1,
        )

    with monkeypatch.context() as scoped:
        scoped.setattr(
            completeness_contract,
            "get_retrieval_strategy_descriptor",
            next_revision,
        )
        revision_mismatched = search_library_v2(
            config,
            SearchLibraryV2Request(root={"cursor": first.root.selection.next_cursor}),
        )
    assert revision_mismatched.root.problem == "cursor_expired"  # type: ignore[union-attr]
    assert revision_mismatched.root.cause == "retrieval policy changed"  # type: ignore[union-attr]

    second = search_library_v2(
        config,
        SearchLibraryV2Request(
            root={"cursor": first.root.selection.next_cursor}
        ),
    )
    assert isinstance(second.root, SearchLibrarySuccessV2)
    assert [item.evidence.locator.start for item in second.root.matches] == [7]
    assert second.root.selection.status == "complete"


def test_mixed_search_respects_mcp_excerpt_content_budget_and_continues(
    tmp_path: Path,
) -> None:
    from mke.interfaces.mcp_completeness_contract import search_library_v2
    from mke.interfaces.mcp_contract import McpRuntimeConfig
    from mke.interfaces.mcp_schemas import (
        SearchLibrarySuccessV2,
        SearchLibraryV2Request,
        SearchSelectionCompleteV2,
        SearchSelectionMoreV2,
    )
    from mke.runtime import RuntimeConfig

    db_path = tmp_path / "mke.sqlite"
    long_pages = tuple(
        "前缀" * 1200 + f" budgetanchor 账户余额调整流程 第 {index} 项。" + "后缀" * 1200
        for index in range(1, 11)
    )
    publisher = KnowledgeEngine(db_path)
    try:
        _publish_text(publisher, "mcp-budget.pdf", "7" * 64, long_pages)
    finally:
        publisher.close()

    config = McpRuntimeConfig(
        RuntimeConfig(
            db_path,
            retrieval_strategy="mixed-cjk-fts-intent-v1",  # type: ignore[arg-type]
        ),
        tmp_path,
    )
    first = search_library_v2(
        config,
        SearchLibraryV2Request(
            root={"query": "budgetanchor 账户余额调整流程", "limit": 20}
        ),
    )
    assert isinstance(first.root, SearchLibrarySuccessV2)
    assert first.root.output.content_budget_bytes == 16_384
    assert sum(
        match.excerpt.returned_utf8_bytes for match in first.root.matches
    ) <= first.root.output.content_budget_bytes
    assert (
        len(first.root.model_dump_json().encode())
        <= first.root.output.envelope_budget_bytes
    )
    assert isinstance(first.root.selection, SearchSelectionMoreV2)
    assert len(first.root.matches) < 10

    second = search_library_v2(
        config,
        SearchLibraryV2Request(
            root={"cursor": first.root.selection.next_cursor}
        ),
    )
    assert isinstance(second.root, SearchLibrarySuccessV2)
    assert isinstance(second.root.selection, SearchSelectionCompleteV2)
    assert len(first.root.matches) + len(second.root.matches) == 10


def test_mixed_provenance_reads_fail_closed_for_corrupt_active_manifest(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mke.sqlite"
    publisher = KnowledgeEngine(db_path)
    try:
        _publish_text(
            publisher,
            "corrupt-manifest.pdf",
            "9" * 64,
            ("manifestanchor 账户余额调整流程。",),
        )
    finally:
        publisher.close()

    engine = KnowledgeEngine(
        db_path,
        retrieval_strategy="mixed-cjk-fts-intent-v1",  # type: ignore[arg-type]
    )
    try:
        connection = engine._store._connection  # pyright: ignore[reportPrivateUsage]
        connection.execute(
            "UPDATE run_manifests SET evidence_count = evidence_count + 1"
        )
        connection.commit()

        with pytest.raises(ManifestValidationError):
            engine.search_provenance_snapshot("manifestanchor 账户余额调整流程")
        with pytest.raises(ManifestValidationError):
            engine.search_evidence_page(
                "manifestanchor 账户余额调整流程",
                position=0,
                page_size=1,
                authority_validator=lambda _authority: None,
            )
    finally:
        engine.close()


def test_new_strategy_keeps_long_ascii_query_on_numeric_fts_path(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mke.sqlite"
    text = "longanchor " + "filler " * 130
    query = "longanchor " + "filler " * 130
    assert len(query) > MIXED_CJK_FTS_INTENT_PARAMETERS.max_query_chars

    publisher = KnowledgeEngine(db_path)
    try:
        _publish_text(publisher, "long-ascii.pdf", "8" * 64, (text,))
    finally:
        publisher.close()

    results: dict[str, list[int]] = {}
    for strategy in ("numeric-grouping-v1", "mixed-cjk-fts-intent-v1"):
        engine = KnowledgeEngine(db_path, retrieval_strategy=strategy)  # type: ignore[arg-type]
        try:
            results[strategy] = [item.locator_start for item in engine.search(query)]
        finally:
            engine.close()

    assert results == {
        "numeric-grouping-v1": [1],
        "mixed-cjk-fts-intent-v1": [1],
    }


def test_mixed_strategy_cap_is_distinct_from_mcp_page_continuation(
    tmp_path: Path,
) -> None:
    from mke.interfaces.mcp_completeness_contract import search_library_v2
    from mke.interfaces.mcp_contract import McpRuntimeConfig
    from mke.interfaces.mcp_schemas import (
        SearchLibrarySuccessV2,
        SearchLibraryV2Request,
        SearchSelectionCappedV2,
        SearchSelectionMoreV2,
    )
    from mke.runtime import RuntimeConfig

    db_path = tmp_path / "mke.sqlite"
    publisher = KnowledgeEngine(db_path)
    try:
        _publish_text(
            publisher,
            "cap.pdf",
            "0" * 64,
            tuple("capanchor 账户余额调整流程同质证据。" for _ in range(11)),
        )
    finally:
        publisher.close()

    engine = KnowledgeEngine(
        db_path,
        retrieval_strategy="mixed-cjk-fts-intent-v1",  # type: ignore[arg-type]
    )
    try:
        assert [
            item.locator_start
            for item in engine.search("capanchor 账户余额调整流程", limit=20)
        ] == list(range(1, 11))
    finally:
        engine.close()

    config = McpRuntimeConfig(
        RuntimeConfig(
            db_path,
            retrieval_strategy="mixed-cjk-fts-intent-v1",  # type: ignore[arg-type]
        ),
        tmp_path,
    )
    page = search_library_v2(
        config,
        SearchLibraryV2Request(root={"query": "capanchor 账户余额调整流程", "limit": 5}),
    )
    assert isinstance(page.root, SearchLibrarySuccessV2)
    assert isinstance(page.root.selection, SearchSelectionMoreV2)
    page = search_library_v2(
        config,
        SearchLibraryV2Request(
            root={"cursor": page.root.selection.next_cursor}
        ),
    )
    assert isinstance(page.root, SearchLibrarySuccessV2)
    assert [item.evidence.locator.start for item in page.root.matches] == list(
        range(6, 11)
    )
    assert isinstance(page.root.selection, SearchSelectionCappedV2)
    assert page.root.selection.limit_reason == "retrieval_strategy_cap"


def test_mixed_numeric_identifier_and_short_intent_controls(tmp_path: Path) -> None:
    db_path = tmp_path / "mke.sqlite"
    publisher = KnowledgeEngine(db_path)
    try:
        _publish_text(
            publisher,
            "controls.pdf",
            "c" * 64,
            (
                "controlanchor 应用加速 30 50 百分比 账户余额调整。",
                "controlanchor 应用加速 99 88 百分比 账户余额调整。",
                "capacityanchor 3T 以上超大规模虚机设备扩展部署方案。",
                "leadinganchor 0410000 账单核验流程。",
                "identifieranchor QX-410000A 资产回收流程。",
                "sequenceanchor 1 234 567 序列校验流程。",
                "sequenceanchor 1 gap 234 567 序列校验流程。",
                "strictanchor 应用加速 30 账户余额调整。",
                "shortanchor 系统设置说明。",
                "paraphraseanchor 账户资金变更说明。",
            ),
        )
    finally:
        publisher.close()

    engine = KnowledgeEngine(
        db_path,
        retrieval_strategy="mixed-cjk-fts-intent-v1",  # type: ignore[arg-type]
    )
    try:
        cases = {
            "controlanchor 应用加速 30 50 百分比 账户余额调整": [1],
            "controlanchor 应用加速 99 88 百分比 账户余额调整": [2],
            "capacityanchor 3T 以上超大规模虚机设备扩展部署方案": [3],
            "capacityanchor 9T 以上超大规模虚机设备扩展部署方案": [],
            "leadinganchor 0410000 账单核验流程": [4],
            "identifieranchor QX-410000A 资产回收流程": [5],
            "sequenceanchor 1234567 序列校验流程": [6],
            "strictanchor 应用加速 30 50 账户余额调整": [],
            "missinganchor 账户余额调整": [],
            "paraphraseanchor 账户余额变更流程": [],
            "shortanchor 系统": [],
        }
        for query, expected_locators in cases.items():
            assert [item.locator_start for item in engine.search(query)] == (
                expected_locators
            )

        chinese_only_ask = engine.ask("账户余额调整流程")
        assert chinese_only_ask.answer_status == "evidence_found"
        assert [item.locator_start for item in chinese_only_ask.evidence] == [1, 2, 8]

        short_ask = engine.ask("shortanchor 系统")
        assert short_ask.answer_status == "insufficient_evidence"
        assert short_ask.evidence == ()
    finally:
        engine.close()


def test_mixed_nfkc_hints_map_excerpts_to_original_utf8_slices(
    tmp_path: Path,
) -> None:
    from mke.interfaces.mcp_completeness_contract import search_library_v2
    from mke.interfaces.mcp_contract import McpRuntimeConfig
    from mke.interfaces.mcp_schemas import SearchLibrarySuccessV2, SearchLibraryV2Request
    from mke.runtime import RuntimeConfig

    db_path = tmp_path / "mke.sqlite"
    texts = (
        "前缀" * 1200 + " compatanchor ⽅ 便处理 " + "后缀" * 1200,
        "前缀" * 1100 + " expansionanchor ㍿ " + "后缀" * 1100,
        "前缀" * 1000 + " combininganchor か\u3099くせい " + "后缀" * 1000,
    )
    publisher = KnowledgeEngine(db_path)
    try:
        _publish_text(publisher, "normalization.pdf", "d" * 64, texts)
    finally:
        publisher.close()

    config = McpRuntimeConfig(
        RuntimeConfig(
            db_path,
            retrieval_strategy="mixed-cjk-fts-intent-v1",  # type: ignore[arg-type]
        ),
        tmp_path,
    )
    cases = (
        ("compatanchor 方便处理", 1, "⽅ 便处理"),
        ("expansionanchor 株式会社", 2, "㍿"),
        ("combininganchor がくせい", 3, "か\u3099くせい"),
    )
    for query, locator, original_marker in cases:
        response = search_library_v2(
            config,
            SearchLibraryV2Request(root={"query": query, "limit": 1}),
        )
        assert isinstance(response.root, SearchLibrarySuccessV2)
        assert [item.evidence.locator.start for item in response.root.matches] == [
            locator
        ]
        match = response.root.matches[0]
        original_text = texts[locator - 1]
        excerpt = match.excerpt
        assert excerpt.kind == "query_window"
        assert original_marker in excerpt.text
        assert (
            original_text.encode()[
                excerpt.start_utf8_byte : excerpt.end_utf8_byte
            ].decode()
            == excerpt.text
        )
        assert match.evidence.original_utf8_bytes == len(original_text.encode())
        assert match.evidence.evidence_text_sha256 == (
            "sha256:" + hashlib.sha256(original_text.encode()).hexdigest()
        )


def test_mixed_match_budget_is_checked_before_candidate_text_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "mke.sqlite"
    pages = (
        "budgetanchor 账户余额调整流程。",
        "budgetanchor 不相关的其他页面内容。",
    )
    publisher = KnowledgeEngine(db_path)
    try:
        _publish_text(publisher, "budget.pdf", "e" * 64, pages)
    finally:
        publisher.close()

    engine = KnowledgeEngine(
        db_path,
        retrieval_strategy="mixed-cjk-fts-intent-v1",  # type: ignore[arg-type]
    )
    statements: list[str] = []
    try:
        monkeypatch.setattr(
            sqlite_adapter,
            "MIXED_CJK_FTS_INTENT_PARAMETERS",
            replace(MIXED_CJK_FTS_INTENT_PARAMETERS, max_matched_rows=1),
        )
        connection = engine._store._connection  # pyright: ignore[reportPrivateUsage]
        connection.set_trace_callback(statements.append)
        try:
            with pytest.raises(MixedCjkFtsIntentError) as raised:
                engine.search("budgetanchor 账户余额调整流程", limit=1)
        finally:
            connection.set_trace_callback(None)

        assert raised.value.problem == "mixed_cjk_match_budget_exceeded"
        assert raised.value.next_step == "narrow_query"
        matched_queries = [
            statement
            for statement in statements
            if "active_evidence_fts MATCH" in statement
        ]
        assert len(matched_queries) == 1
        assert "LIMIT" not in matched_queries[0].upper()
        assert "OFFSET" not in matched_queries[0].upper()
        assert "LEFT JOIN MATCHED" in matched_queries[0].upper()
        assert "STATS.MATCHED_ROW_COUNT <= 1" in matched_queries[0].upper()
        assert "STATS.MATCHED_TEXT_BYTES <= 16777216" in matched_queries[0].upper()
        assert not any(
            "SELECT evidence_id, text" in statement for statement in statements
        )
    finally:
        engine.close()


def test_mixed_matched_text_budget_accepts_exact_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "mke.sqlite"
    text = "boundaryanchor 账户余额调整流程。"
    publisher = KnowledgeEngine(db_path)
    try:
        _publish_text(publisher, "boundary.pdf", "f" * 64, (text,))
    finally:
        publisher.close()

    engine = KnowledgeEngine(
        db_path,
        retrieval_strategy="mixed-cjk-fts-intent-v1",  # type: ignore[arg-type]
    )
    try:
        monkeypatch.setattr(
            sqlite_adapter,
            "MIXED_CJK_FTS_INTENT_PARAMETERS",
            replace(
                MIXED_CJK_FTS_INTENT_PARAMETERS,
                max_matched_rows=1,
                max_matched_text_bytes=len(text.encode()),
            ),
        )
        assert [
            result.locator_start
            for result in engine.search("boundaryanchor 账户余额调整流程")
        ] == [1]

        monkeypatch.setattr(
            sqlite_adapter,
            "MIXED_CJK_FTS_INTENT_PARAMETERS",
            replace(
                MIXED_CJK_FTS_INTENT_PARAMETERS,
                max_matched_rows=1,
                max_matched_text_bytes=len(text.encode()) - 1,
            ),
        )
        with pytest.raises(MixedCjkFtsIntentError) as raised:
            engine.search("boundaryanchor 账户余额调整流程")
        assert raised.value.problem == "mixed_cjk_match_budget_exceeded"
    finally:
        engine.close()


def test_mixed_fts_order_is_stable_across_generated_identifier_schedules(
    tmp_path: Path,
) -> None:
    def observe(database: Path, asset_hashes: tuple[str, str]) -> list[str]:
        publisher = KnowledgeEngine(database)
        try:
            for index, asset_hash in enumerate(asset_hashes):
                _publish_text(
                    publisher,
                    f"source-{index}.pdf",
                    asset_hash,
                    ("stableanchor 账户余额调整流程" + " filler" * 20,),
                )
        finally:
            publisher.close()
        engine = KnowledgeEngine(
            database,
            retrieval_strategy="mixed-cjk-fts-intent-v1",  # type: ignore[arg-type]
        )
        try:
            return [
                item.content_fingerprint
                for item in engine.search_provenance_snapshot(
                    "stableanchor 账户余额调整流程"
                ).results
            ]
        finally:
            engine.close()

    first = observe(tmp_path / "first.sqlite", ("1" * 64, "2" * 64))
    inverse = observe(tmp_path / "inverse.sqlite", ("2" * 64, "1" * 64))

    assert first == inverse
    assert first == ["sha256:" + "1" * 64, "sha256:" + "2" * 64]


def test_mixed_search_excludes_superseded_and_unpublished_evidence(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mke.sqlite"
    publisher = KnowledgeEngine(db_path)
    try:
        source_id = _publish_text(
            publisher,
            "superseded.pdf",
            "3" * 64,
            ("authorityanchor 账户余额调整流程旧版本",),
        )
        _publish_text(
            publisher,
            "superseded.pdf",
            "3" * 64,
            ("当前版本不含检索词。",),
            source_id=source_id,
        )
        unpub = publisher.create_run(source_id)
        unpublished = CandidateEvidence(
            evidence_id="evidence_unpublished",
            locator_kind="page",
            locator_start=1,
            locator_end=1,
            text="unpublishedanchor 账户余额调整流程未发布。",
        )
        publisher.persist_validated_candidate(
            unpub.run_id,
            [unpublished],
            RunManifest(
                run_id=unpub.run_id,
                evidence_count=1,
                required_stages=tuple(sorted(REQUIRED_PDF_STAGES)),
                extractor_fingerprint=PDF_EXTRACTOR_FINGERPRINT,
                asset_sha256="3" * 64,
            ),
        )
        failed_source = publisher.ensure_source(
            "failed.pdf",
            "5" * 64,
        )
        failed_run = publisher.create_run(failed_source.source_id)
        failed_evidence = CandidateEvidence(
            evidence_id="evidence_failed",
            locator_kind="page",
            locator_start=1,
            locator_end=1,
            text="failedanchor 账户余额调整流程已失败。",
        )
        publisher.persist_validated_candidate(
            failed_run.run_id,
            [failed_evidence],
            RunManifest(
                run_id=failed_run.run_id,
                evidence_count=1,
                required_stages=tuple(sorted(REQUIRED_PDF_STAGES)),
                extractor_fingerprint=PDF_EXTRACTOR_FINGERPRINT,
                asset_sha256="5" * 64,
            ),
        )
        publisher._store.mark_validated_run_failed(  # pyright: ignore[reportPrivateUsage]
            failed_run.run_id
        )
    finally:
        publisher.close()

    engine = KnowledgeEngine(
        db_path,
        retrieval_strategy="mixed-cjk-fts-intent-v1",  # type: ignore[arg-type]
    )
    try:
        assert engine.search("authorityanchor 账户余额调整流程") == []
        assert engine.search("unpublishedanchor 账户余额调整流程") == []
        assert engine.search("failedanchor 账户余额调整流程") == []
    finally:
        engine.close()


def test_mixed_duplicate_fts_locator_fails_with_existing_authority_error(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mke.sqlite"
    publisher = KnowledgeEngine(db_path)
    try:
        _publish_text(
            publisher,
            "duplicate.pdf",
            "4" * 64,
            ("duplicateanchor 账户余额调整流程",),
        )
        connection = publisher._store._connection  # pyright: ignore[reportPrivateUsage]
        connection.execute(
            """
            INSERT INTO active_evidence_fts(
              library_id, source_id, publication_id, evidence_id,
              locator_label, text
            )
            SELECT library_id, source_id, publication_id, evidence_id,
                   locator_label, text
            FROM active_evidence_fts
            WHERE evidence_id = (
              SELECT evidence_id FROM evidence WHERE text LIKE '%duplicateanchor%'
            )
            """
        )
        connection.commit()
    finally:
        publisher.close()

    engine = KnowledgeEngine(
        db_path,
        retrieval_strategy="mixed-cjk-fts-intent-v1",  # type: ignore[arg-type]
    )
    try:
        with pytest.raises(RetrievalAuthorityError):
            engine.search("duplicateanchor 账户余额调整流程")
    finally:
        engine.close()


def test_mixed_search_loads_text_from_the_same_read_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "mke.sqlite"
    original_text = "snapshotanchor 账户余额调整流程。"
    replacement_text = "snapshotanchor 管理系统升级说明。"
    publisher = KnowledgeEngine(db_path)
    try:
        _publish_text(publisher, "snapshot.pdf", "6" * 64, (original_text,))
    finally:
        publisher.close()

    engine = KnowledgeEngine(
        db_path,
        retrieval_strategy="mixed-cjk-fts-intent-v1",  # type: ignore[arg-type]
    )
    try:
        load_candidates = engine._store._load_fts_candidate_text  # pyright: ignore[reportPrivateUsage]
        mutations = 0

        def mutate_before_text_load(candidates: list[object]):
            nonlocal mutations
            mutations += 1
            assert mutations == 1
            with sqlite3.connect(db_path) as connection:
                connection.execute(
                    "UPDATE evidence SET text = ? WHERE text = ?",
                    (replacement_text, original_text),
                )
                connection.execute(
                    "UPDATE active_evidence_fts SET text = ? WHERE text = ?",
                    (replacement_text, original_text),
                )
            return load_candidates(candidates)  # type: ignore[arg-type]

        monkeypatch.setattr(
            engine._store,  # pyright: ignore[reportPrivateUsage]
            "_load_fts_candidate_text",
            mutate_before_text_load,
        )

        selected = engine.search("snapshotanchor 账户余额调整流程")
        assert [item.text for item in selected] == [original_text]
    finally:
        engine.close()

    current = KnowledgeEngine(
        db_path,
        retrieval_strategy="mixed-cjk-fts-intent-v1",  # type: ignore[arg-type]
    )
    try:
        assert current.search("snapshotanchor 账户余额调整流程") == []
    finally:
        current.close()


def _publish_text(
    engine: KnowledgeEngine,
    display_name: str,
    asset_sha256: str,
    pages: tuple[str, ...],
    *,
    source_id: str | None = None,
) -> str:
    if source_id is None:
        source = engine.ensure_source(
            display_name=display_name,
            asset_sha256=asset_sha256,
        )
        source_id = source.source_id
    run = engine.create_run(source_id)
    evidence = [
        CandidateEvidence(
            evidence_id=f"ev_{run.run_id}_{index}",
            locator_kind="page",
            locator_start=index,
            locator_end=index,
            text=text,
        )
        for index, text in enumerate(pages, start=1)
    ]
    engine.persist_validated_candidate(
        run.run_id,
        evidence,
        RunManifest(
            run_id=run.run_id,
            evidence_count=len(evidence),
            required_stages=tuple(sorted(REQUIRED_PDF_STAGES)),
            extractor_fingerprint=PDF_EXTRACTOR_FINGERPRINT,
            asset_sha256=asset_sha256,
        ),
    )
    engine.activate_publication(run.run_id)
    return source_id
