from pathlib import Path
from time import perf_counter

import pytest

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
    compile_cjk_overlap_terms,
)

_PERFORMANCE_BUDGET_SECONDS = 2.0


def test_long_query_fanout_fails_within_fixed_budget() -> None:
    started = perf_counter()

    with pytest.raises(CjkActiveScanError) as raised:
        compile_cjk_overlap_terms("发布证据检索" * 100, require_terms=True)

    assert perf_counter() - started < _PERFORMANCE_BUDGET_SECONDS
    assert raised.value.problem == "cjk_scan_budget_exceeded"


def test_large_active_row_count_fails_before_text_scan(tmp_path: Path) -> None:
    engine = _published_engine(
        tmp_path / "row-budget.sqlite",
        count=CJK_ACTIVE_SCAN_PARAMETERS.max_active_evidence_rows + 1,
        text="普通证据页面",
    )
    try:
        started = perf_counter()
        with pytest.raises(CjkActiveScanError) as raised:
            engine.search("发布证据检索")
        elapsed = perf_counter() - started
    finally:
        engine.close()

    assert elapsed < _PERFORMANCE_BUDGET_SECONDS
    assert raised.value.problem == "cjk_scan_budget_exceeded"


def test_high_fanout_candidate_pool_fails_within_fixed_budget(
    tmp_path: Path,
) -> None:
    engine = _published_engine(
        tmp_path / "candidate-budget.sqlite",
        count=CJK_ACTIVE_SCAN_PARAMETERS.max_candidate_pool + 1,
        text="发布证据检索 完整匹配",
    )
    try:
        started = perf_counter()
        with pytest.raises(CjkActiveScanError) as raised:
            engine.search("发布证据检索")
        elapsed = perf_counter() - started
    finally:
        engine.close()

    assert elapsed < _PERFORMANCE_BUDGET_SECONDS
    assert raised.value.problem == "cjk_candidate_pool_capped"


def test_maximum_allowed_active_text_volume_scans_within_fixed_budget(
    tmp_path: Path,
) -> None:
    text_budget = CJK_ACTIVE_SCAN_PARAMETERS.max_active_evidence_text_bytes
    prefix = "发布证据检索"
    text = prefix + "x" * (text_budget - len(prefix.encode("utf-8")))
    engine = _published_engine(
        tmp_path / "text-budget.sqlite",
        count=1,
        text=text,
    )
    try:
        started = perf_counter()
        results = engine.search("发布证据检索")
        elapsed = perf_counter() - started
    finally:
        engine.close()

    assert elapsed < _PERFORMANCE_BUDGET_SECONDS
    assert [item.locator_start for item in results] == [1]


def _published_engine(db_path: Path, *, count: int, text: str) -> KnowledgeEngine:
    engine = KnowledgeEngine(
        db_path,
        retrieval_strategy="cjk-active-scan-overlap-v1",
    )
    source = engine.ensure_source(
        "performance-fixture",
        "e" * 64,
        media_type="application/pdf",
    )
    run = engine.create_run(source.source_id)
    evidence = [
        CandidateEvidence(
            evidence_id=f"evidence_{index:05d}",
            locator_kind="page",
            locator_start=index,
            locator_end=index,
            text=text,
        )
        for index in range(1, count + 1)
    ]
    engine.persist_validated_candidate(
        run.run_id,
        evidence,
        RunManifest(
            run_id=run.run_id,
            evidence_count=count,
            required_stages=tuple(sorted(REQUIRED_PDF_STAGES)),
            extractor_fingerprint=PDF_EXTRACTOR_FINGERPRINT,
            asset_sha256="e" * 64,
        ),
    )
    engine.activate_publication(run.run_id)
    return engine
