from pathlib import Path
from typing import Any

import pytest

from mke.adapters.sqlite import EvidenceNotFoundError, EvidenceResponseTooLargeError
from mke.application import KnowledgeEngine
from mke.application.evidence_access import build_excerpt
from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    ActiveAuthoritySnapshot,
    CandidateEvidence,
    RunManifest,
)


def test_search_page_and_read_share_active_authority(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        evidence_id = _publish(engine, ("publication authority one", "publication authority two"))
        observed: list[ActiveAuthoritySnapshot] = []
        page = engine.search_evidence_page(
            "publication authority",
            position=0,
            page_size=1,
            authority_validator=observed.append,
        )
        read = engine.read_active_evidence(
            evidence_id,
            authority_validator=lambda authority: observed.append(authority),
        )
        assert page.more_in_selected_pool is True
        assert page.authority == read.authority == observed[0] == observed[1]
        assert read.text == "publication authority one"
    finally:
        engine.close()


def test_read_rejects_unknown_evidence(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        with pytest.raises(EvidenceNotFoundError):
            engine.read_active_evidence(
                "ev_missing",
                authority_validator=lambda _authority: None,
            )
    finally:
        engine.close()


def test_read_continuation_uses_bounded_blob_range_without_full_text(
    tmp_path: Path,
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        evidence_id = _publish(engine, ("prefix " + "x" * 50_000 + " suffix",))
        statements: list[str] = []
        connection = engine._store._connection  # pyright: ignore[reportPrivateUsage]
        connection.set_trace_callback(statements.append)
        snapshot = engine.read_active_evidence(
            evidence_id,
            offset_bytes=4096,
            range_bytes=1024,
            authority_validator=lambda _authority: None,
        )
        connection.set_trace_callback(None)

        assert snapshot.text is None
        assert len(snapshot.range_bytes) <= 1027
        evidence_queries = [
            statement
            for statement in statements
            if "WHERE evidence.evidence_id" in statement
        ]
        assert len(evidence_queries) == 2
        assert "length(CAST(evidence.text AS BLOB))" in evidence_queries[0]
        assert "evidence.text," not in evidence_queries[0]
        assert "substr(CAST(evidence.text AS BLOB)" in evidence_queries[1]
        assert "evidence.text," not in evidence_queries[1]
    finally:
        engine.close()


def test_oversized_initial_read_rejects_before_materializing_text(
    tmp_path: Path,
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        evidence_id = _publish(engine, ("bounded",))
        connection = engine._store._connection  # pyright: ignore[reportPrivateUsage]
        connection.execute(
            "UPDATE evidence SET text = ? WHERE evidence_id = ?",
            ("x" * (16 * 1024 * 1024 + 1), evidence_id),
        )
        connection.commit()
        statements: list[str] = []
        connection.set_trace_callback(statements.append)
        with pytest.raises(EvidenceResponseTooLargeError):
            engine.read_active_evidence(
                evidence_id,
                authority_validator=lambda _authority: None,
            )
        connection.set_trace_callback(None)

        evidence_queries = [
            statement
            for statement in statements
            if "WHERE evidence.evidence_id" in statement
        ]
        assert len(evidence_queries) == 1
        assert "length(CAST(evidence.text AS BLOB))" in evidence_queries[0]
        assert "evidence.text," not in evidence_queries[0]
    finally:
        engine.close()


@pytest.mark.parametrize("position", (0, 1, 7))
def test_fts_page_uses_metadata_limit_offset_without_gaps(
    tmp_path: Path, position: int
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        _publish(engine, tuple(f"authority match {index}" for index in range(12)))
        statements: list[str] = []
        connection = engine._store._connection  # pyright: ignore[reportPrivateUsage]
        connection.set_trace_callback(statements.append)
        page = engine.search_evidence_page(
            "authority",
            position=position,
            page_size=3,
            authority_validator=lambda _authority: None,
        )
        connection.set_trace_callback(None)

        assert [item.provenance.result.locator_start for item in page.results] == list(
            range(position + 1, position + 4)
        )
        metadata = [
            statement
            for statement in statements
            if "active_evidence_fts MATCH" in statement and "LIMIT" in statement
        ]
        assert len(metadata) == 1
        assert "active_evidence_fts.text" not in metadata[0]
        assert "LIMIT 4 OFFSET" in metadata[0]
        page_order = metadata[0].split("LIMIT 4 OFFSET", maxsplit=1)[0].rsplit(
            "ORDER BY", maxsplit=1
        )[1]
        assert "evidence_id" not in page_order
        for stable_key in (
            "score",
            "locator_start",
            "locator_kind",
            "locator_end",
            "source_sha256",
        ):
            assert stable_key in page_order
    finally:
        engine.close()


def test_fts_page_text_budget_always_progresses_first_candidate(
    tmp_path: Path,
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        _publish(
            engine,
            (
                "authority " + "x" * (9 * 1024 * 1024),
                "authority " + "y" * (9 * 1024 * 1024),
                "authority tail",
            ),
        )
        first = engine.search_evidence_page(
            "authority",
            position=0,
            page_size=3,
            authority_validator=lambda _authority: None,
        )
        second = engine.search_evidence_page(
            "authority",
            position=1,
            page_size=3,
            authority_validator=lambda _authority: None,
        )

        assert len(first.results) == 1
        assert first.more_in_selected_pool is True
        assert first.results[0].provenance.result.locator_start == 1
        assert [item.provenance.result.locator_start for item in second.results] == [2, 3]
    finally:
        engine.close()


def test_search_preserves_numeric_and_cjk_match_hints(tmp_path: Path) -> None:
    numeric = KnowledgeEngine(tmp_path / "numeric.sqlite")
    cjk = KnowledgeEngine(
        tmp_path / "cjk.sqlite",
        retrieval_strategy="cjk-active-scan-overlap-v1",
    )
    try:
        _publish(numeric, ("前缀" * 1000 + " 560 033 202 243 late",))
        numeric_page = numeric.search_evidence_page(
            "560033202243",
            position=0,
            page_size=1,
            authority_validator=lambda _authority: None,
        )
        assert [hint.text for hint in numeric_page.results[0].hints] == [
            "560033202243",
            "560 033 202 243",
        ]
        numeric_excerpt = build_excerpt(
            numeric_page.results[0].provenance.result.text,
            numeric_page.results[0].hints,
        )
        assert numeric_excerpt.kind == "query_window"
        assert "560 033 202 243" in numeric_excerpt.text

        _publish(cjk, ("前缀" * 1000 + " 发布证据检索 late",))
        cjk_page = cjk.search_evidence_page(
            "发布证据检索额外内容",
            position=0,
            page_size=1,
            authority_validator=lambda _authority: None,
        )
        matched = cjk_page.results[0].hints
        assert matched
        assert all(hint.text in "发布证据检索" for hint in matched)
        cjk_excerpt = build_excerpt(
            cjk_page.results[0].provenance.result.text,
            matched,
        )
        assert cjk_excerpt.kind == "query_window"
        assert any(hint.text in cjk_excerpt.text for hint in matched)
    finally:
        numeric.close()
        cjk.close()


@pytest.mark.parametrize("eligible", (9, 10, 11))
@pytest.mark.parametrize("page_size", (5, 10))
def test_cjk_page_cap_uses_actual_strategy_discard(
    tmp_path: Path, eligible: int, page_size: int
) -> None:
    engine = KnowledgeEngine(
        tmp_path / f"cjk-{eligible}-{page_size}.sqlite",
        retrieval_strategy="cjk-active-scan-overlap-v1",
    )
    try:
        _publish(
            engine,
            tuple(f"发布证据检索 完整页面 {index}" for index in range(eligible)),
        )
        position = 0
        terminal: Any = None
        while True:
            terminal = engine.search_evidence_page(
                "发布证据检索",
                position=position,
                page_size=page_size,
                authority_validator=lambda _authority: None,
            )
            position += len(terminal.results)
            if not terminal.more_in_selected_pool:
                break
        assert terminal.eligible_discarded_by_cap is (eligible == 11)
        assert position == min(eligible, 10)
    finally:
        engine.close()


def _publish(engine: KnowledgeEngine, pages: tuple[str, ...]) -> str:
    source = engine.ensure_source("fixture.pdf", "a" * 64)
    run = engine.create_run(source.source_id)
    evidence = [
        CandidateEvidence(
            evidence_id=f"ev_{index:032x}",
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
            asset_sha256="a" * 64,
        ),
    )
    engine.activate_publication(run.run_id)
    return evidence[0].evidence_id
