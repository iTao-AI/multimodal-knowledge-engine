from pathlib import Path

import pytest

from mke.application import AskValidationError, KnowledgeEngine
from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    CandidateEvidence,
    RunManifest,
)


def test_default_active_scan_strategy_returns_cjk_evidence(tmp_path: Path) -> None:
    db_path = tmp_path / "mke.sqlite"
    _publish_texts(
        db_path,
        [
            "发布证据检索功能应当命中这一页。",
            "完全无关的页面。",
        ],
    )

    default_engine = KnowledgeEngine(db_path)
    rollback_engine = KnowledgeEngine(
        db_path,
        retrieval_strategy="numeric-grouping-v1",
    )
    try:
        matches = default_engine.search("发布证据检索")
        assert rollback_engine.search("发布证据检索") == []
    finally:
        default_engine.close()
        rollback_engine.close()

    assert [match.locator_start for match in matches] == [1]
    assert "发布证据检索功能" in matches[0].text


def test_default_active_scan_strategy_accepts_cjk_ask_question(tmp_path: Path) -> None:
    db_path = tmp_path / "mke.sqlite"
    _publish_texts(db_path, ["发布证据检索功能应当命中这一页。"])

    default_engine = KnowledgeEngine(db_path)
    rollback_engine = KnowledgeEngine(
        db_path,
        retrieval_strategy="numeric-grouping-v1",
    )
    try:
        answer = default_engine.ask("发布证据检索？")
        with pytest.raises(AskValidationError):
            rollback_engine.ask("发布证据检索？")
    finally:
        default_engine.close()
        rollback_engine.close()

    assert answer.answer_status == "evidence_found"
    assert answer.evidence[0].locator_start == 1


def test_active_scan_strategy_preserves_ascii_constraints_in_mixed_query(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mke.sqlite"
    _publish_texts(db_path, ["发布证据检索功能应当命中这一页。"])

    engine = KnowledgeEngine(
        db_path,
        retrieval_strategy="cjk-active-scan-overlap-v1",
    )
    try:
        matches = engine.search("ascii-token-that-does-not-exist 发布证据检索")
    finally:
        engine.close()

    assert matches == []


def test_active_scan_strategy_does_not_read_unpublished_candidate(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mke.sqlite"
    source_id = _publish_texts(db_path, ["旧版发布证据检索内容仍然 active。"])
    _prepare_unpublished_text(
        db_path,
        source_id=source_id,
        text="新版替换内容不能提前 searchable。",
    )

    engine = KnowledgeEngine(
        db_path,
        retrieval_strategy="cjk-active-scan-overlap-v1",
    )
    try:
        active_matches = engine.search("旧版发布证据检索")
        unpublished_matches = engine.search("新版替换内容")
    finally:
        engine.close()

    assert [match.text for match in active_matches] == ["旧版发布证据检索内容仍然 active。"]
    assert unpublished_matches == []


def _publish_texts(db_path: Path, texts: list[str]) -> str:
    engine = KnowledgeEngine(db_path)
    try:
        source = engine.ensure_source("fixture", "c" * 64, media_type="application/pdf")
        run = engine.create_run(source.source_id)
        evidence = [
            CandidateEvidence(
                evidence_id=f"evidence_{index}",
                locator_kind="page",
                locator_start=index,
                locator_end=index,
                text=text,
            )
            for index, text in enumerate(texts, start=1)
        ]
        engine.persist_validated_candidate(
            run.run_id,
            evidence,
            RunManifest(
                run_id=run.run_id,
                evidence_count=len(evidence),
                required_stages=tuple(sorted(REQUIRED_PDF_STAGES)),
                extractor_fingerprint=PDF_EXTRACTOR_FINGERPRINT,
                asset_sha256="c" * 64,
            ),
        )
        engine.activate_publication(run.run_id)
        return source.source_id
    finally:
        engine.close()


def _prepare_unpublished_text(db_path: Path, *, source_id: str, text: str) -> None:
    engine = KnowledgeEngine(db_path)
    try:
        run = engine.create_run(source_id)
        evidence = [
            CandidateEvidence(
                evidence_id="evidence_unpublished",
                locator_kind="page",
                locator_start=1,
                locator_end=1,
                text=text,
            )
        ]
        engine.persist_validated_candidate(
            run.run_id,
            evidence,
            RunManifest(
                run_id=run.run_id,
                evidence_count=len(evidence),
                required_stages=tuple(sorted(REQUIRED_PDF_STAGES)),
                extractor_fingerprint=PDF_EXTRACTOR_FINGERPRINT,
                asset_sha256="c" * 64,
            ),
        )
    finally:
        engine.close()
