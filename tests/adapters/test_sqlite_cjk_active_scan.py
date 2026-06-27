from dataclasses import replace
from pathlib import Path

import pytest

import mke.adapters.sqlite
from mke.application import KnowledgeEngine
from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    CandidateEvidence,
    RunManifest,
)
from mke.retrieval.cjk_active_scan import (
    CJK_ACTIVE_SCAN_PARAMETERS,
    CjkActiveScanError,
)
from mke.retrieval.query_policy import RetrievalQueryPolicy
from tests.conftest import PDF_FIXTURES


def test_sqlite_active_scan_reads_only_active_text_evidence(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        source_id = _publish_text(
            engine,
            "source.pdf",
            "a" * 64,
            ("发布证据检索 旧版本",),
        )
        _publish_text(
            engine,
            "source.pdf",
            "a" * 64,
            ("普通英文 replacement page",),
            source_id=source_id,
        )

        results = engine._store.search_cjk_active_scan(  # pyright: ignore[reportPrivateUsage]
            "发布证据检索"
        )

        assert results == []
    finally:
        engine.close()


def test_sqlite_active_scan_returns_expected_evidence_without_trigram_projection(
    tmp_path: Path,
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        _publish_text(
            engine,
            "cjk.pdf",
            "b" * 64,
            (
                "发布证据检索 生命周期 完整页面",
                "发布证 但没有完整检索短语",
                "完全无关页面",
            ),
        )

        results = engine._store.search_cjk_active_scan(  # pyright: ignore[reportPrivateUsage]
            "发布证据检索"
        )
        cjk_tables = engine._store._connection.execute(  # pyright: ignore[reportPrivateUsage]
            "SELECT name FROM sqlite_master WHERE name LIKE '%cjk%'"
        ).fetchall()

        assert [item.locator_start for item in results] == [1]
        assert cjk_tables == []
    finally:
        engine.close()


def test_rollback_search_path_does_not_call_active_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite", query_policy="numeric-grouping-v1")
    try:
        engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")

        def fail_active_scan(query: str, limit: int | None = None) -> object:
            raise AssertionError("active scan must not run for rollback search")

        monkeypatch.setattr(engine._store, "search_cjk_active_scan", fail_active_scan)  # pyright: ignore[reportPrivateUsage]

        assert engine.search("trustworthy")
    finally:
        engine.close()


def test_compiled_nonempty_zero_hit_does_not_call_active_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = KnowledgeEngine(
        tmp_path / "mke.sqlite",
        retrieval_strategy="cjk-active-scan-overlap-v1",
    )
    try:
        _publish_text(
            engine,
            "constraints.pdf",
            "c" * 64,
            ("应用加速 30 50 百分比",),
        )

        def fail_active_scan(query: str, limit: int | None = None) -> object:
            raise AssertionError("compiled-nonempty query must remain FTS-only")

        monkeypatch.setattr(engine._store, "search_cjk_active_scan", fail_active_scan)  # pyright: ignore[reportPrivateUsage]

        assert engine.search("应用加速 99 88 百分比") == []
    finally:
        engine.close()


def test_compiled_nonempty_numeric_constraints_are_not_dropped(
    tmp_path: Path,
) -> None:
    engine = KnowledgeEngine(
        tmp_path / "mke.sqlite",
        retrieval_strategy="cjk-active-scan-overlap-v1",
    )
    try:
        _publish_text(
            engine,
            "constraints.pdf",
            "c" * 64,
            (
                "应用加速 30 50 百分比",
                "3T 以上超大规模虚机",
            ),
        )

        assert [item.locator_start for item in engine.search("应用加速 30 50 百分比")] == [1]
        assert engine.search("应用加速 99 88 百分比") == []
        assert [item.locator_start for item in engine.search("3T 以上超大规模虚机")] == [2]
        assert engine.search("9T 以上超大规模虚机") == []
    finally:
        engine.close()


def test_compiled_empty_eligible_cjk_calls_active_scan_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = KnowledgeEngine(
        tmp_path / "mke.sqlite",
        retrieval_strategy="cjk-active-scan-overlap-v1",
    )
    try:
        _publish_text(
            engine,
            "cjk.pdf",
            "c" * 64,
            ("发布证据检索 完整页面",),
        )
        active_scan = engine._store.search_cjk_active_scan  # pyright: ignore[reportPrivateUsage]
        active_scan_calls: list[str] = []
        compile_calls: list[str] = []
        compile_query = mke.adapters.sqlite.compile_fts5_query

        def observe_active_scan(query: str, limit: int | None = None):
            active_scan_calls.append(query)
            return active_scan(query, limit=limit)

        def observe_compile(query: str, *, policy: RetrievalQueryPolicy):
            compile_calls.append(query)
            return compile_query(query, policy=policy)

        monkeypatch.setattr(engine._store, "search_cjk_active_scan", observe_active_scan)  # pyright: ignore[reportPrivateUsage]
        monkeypatch.setattr(mke.adapters.sqlite, "compile_fts5_query", observe_compile)

        results = engine.search("发布证据检索")

        assert [item.locator_start for item in results] == [1]
        assert active_scan_calls == ["发布证据检索"]
        assert compile_calls == ["发布证据检索"]
    finally:
        engine.close()


def test_active_scan_rejects_row_count_above_fixed_budget(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        _publish_text(
            engine,
            "cjk.pdf",
            "d" * 64,
            (
                "发布证据检索 第一页",
                "发布证据检索 第二页",
                "发布证据检索 第三页",
            ),
        )
        parameters = replace(
            CJK_ACTIVE_SCAN_PARAMETERS,
            max_active_evidence_rows=2,
        )

        with pytest.raises(CjkActiveScanError) as raised:
            engine._store.search_cjk_active_scan(  # pyright: ignore[reportPrivateUsage]
                "发布证据检索",
                parameters=parameters,
            )

        assert raised.value.problem == "cjk_scan_budget_exceeded"
        assert raised.value.cause == (
            "CJK active Evidence scan would exceed configured local budget"
        )
        assert raised.value.next_step == "narrow_query_or_use_projection_strategy"
    finally:
        engine.close()


def test_active_scan_rejects_text_bytes_above_fixed_budget(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    text = "发布证据检索" + "x" * 64
    try:
        _publish_text(engine, "cjk.pdf", "e" * 64, (text,))
        parameters = replace(
            CJK_ACTIVE_SCAN_PARAMETERS,
            max_active_evidence_text_bytes=len(text.encode("utf-8")) - 1,
        )

        with pytest.raises(CjkActiveScanError) as raised:
            engine._store.search_cjk_active_scan(  # pyright: ignore[reportPrivateUsage]
                "发布证据检索",
                parameters=parameters,
            )

        assert raised.value.problem == "cjk_scan_budget_exceeded"
        assert raised.value.cause == (
            "CJK active Evidence scan would exceed configured local budget"
        )
    finally:
        engine.close()


def test_active_scan_accepts_text_bytes_at_fixed_budget(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    text = "发布证据检索" + "x" * 64
    try:
        _publish_text(engine, "cjk.pdf", "f" * 64, (text,))
        parameters = replace(
            CJK_ACTIVE_SCAN_PARAMETERS,
            max_active_evidence_text_bytes=len(text.encode("utf-8")),
        )

        results = engine._store.search_cjk_active_scan(  # pyright: ignore[reportPrivateUsage]
            "发布证据检索",
            parameters=parameters,
        )

        assert [item.locator_start for item in results] == [1]
    finally:
        engine.close()


def _publish_text(
    engine: KnowledgeEngine,
    display_name: str,
    asset_sha256: str,
    pages: tuple[str, ...],
    *,
    source_id: str | None = None,
) -> str:
    if source_id is None:
        source = engine.ensure_source(display_name=display_name, asset_sha256=asset_sha256)
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
