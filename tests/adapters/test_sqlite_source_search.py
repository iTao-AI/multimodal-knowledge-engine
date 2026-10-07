from __future__ import annotations

from pathlib import Path

import pytest

from mke.adapters.sqlite import EvidenceNotFoundError
from mke.application import KnowledgeEngine
from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    CandidateEvidence,
    RunManifest,
)
from mke.domain.evidence_access import ActiveAuthoritySnapshot, SelectedEvidence
from mke.retrieval.cjk_active_scan import CjkActiveScanError
from mke.retrieval.strategy import RetrievalStrategy
from tests.source_discovery_support import publish_pages

CASES: tuple[tuple[RetrievalStrategy, str, str], ...] = (
    ("current", "needle", "needle"),
    ("numeric-grouping-v1", "needle 1000", "needle 1000"),
    ("cjk-active-scan-overlap-v1", "needle", "needle"),
    ("cjk-active-scan-overlap-v1", "知识检索范围", "知识检索范围"),
    ("mixed-cjk-fts-intent-v1", "知识检索范围", "知识检索范围"),
    ("mixed-cjk-fts-intent-v1", "needle 知识检索范围", "needle 知识检索范围"),
)


@pytest.mark.parametrize("strategy,query,text", CASES)
def test_scope_admitted_before_ranking_and_all_pages_exceed_old_cap(
    tmp_path: Path, strategy: RetrievalStrategy, query: str, text: str,
) -> None:
    database = tmp_path / "mke.sqlite"
    source, publication = publish_pages(
        database, tuple(text + " padding" * 30 for _ in range(13)), fingerprint="f",
    )
    other, _ = publish_pages(database, (text,) * 20, fingerprint="a")
    engine = KnowledgeEngine(database, retrieval_strategy=strategy)
    try:
        unscoped = engine.search(query, limit=3)
        assert len(unscoped) == 3 and all(item.source_id == other for item in unscoped)
        results: list[SelectedEvidence] = []
        position = 0
        authorities: list[ActiveAuthoritySnapshot] = []
        while True:
            page = engine.search_source_evidence_page(
                source, publication, query, position=position, page_size=3,
                authority_validator=authorities.append,
            )
            assert page.scope is not None
            assert page.scope.source_id == source and page.scope.publication_id == publication
            assert page.scope.publication_revision == 1
            assert page.scope.content_fingerprint == "sha256:" + "f" * 64
            assert all(
                item.provenance.result.source_id == source
                and item.provenance.result.publication_id == publication
                and item.provenance.run_id == page.scope.run_id
                for item in page.results
            )
            assert page.eligible_discarded_by_cap is False
            results.extend(page.results)
            if not page.more_in_selected_pool:
                break
            assert page.results
            position += len(page.results)
        assert [item.provenance.result.locator_start for item in results] == list(range(1, 14))
        assert len({item.active_set_fingerprint for item in authorities}) == 1
        assert engine.search(query, limit=3) == unscoped
        assert engine.search_evidence_page(
            query, position=0, page_size=3, authority_validator=lambda _: None,
        ).scope is None
    finally:
        engine.close()


def test_zero_hits_never_fall_back_and_unpublished_or_mixed_ids_fail(tmp_path: Path) -> None:
    database = tmp_path / "mke.sqlite"
    source, publication = publish_pages(database, ("selected",), fingerprint="f")
    other, other_publication = publish_pages(database, ("outsideonly",), fingerprint="a")
    engine = KnowledgeEngine(database)
    try:
        unpublished = engine.ensure_source("pending.pdf", "b" * 64)
        page = engine.search_source_evidence_page(
            source, publication, "outsideonly", position=0, page_size=5,
            authority_validator=lambda _: None,
        )
        assert page.results == () and not page.more_in_selected_pool
        assert page.scope is not None and page.scope.source_id == source
        for selected_source, selected_publication in (
            ("src_missing", publication), (source, "pub_missing"),
            (source, other_publication), (other, publication),
            (unpublished.source_id, publication),
        ):
            with pytest.raises(EvidenceNotFoundError):
                engine.search_source_evidence_page(
                    selected_source, selected_publication, "outsideonly",
                    position=0, page_size=5, authority_validator=lambda _: None,
                )
    finally:
        engine.close()


@pytest.mark.parametrize("strategy,query,text", (CASES[3], CASES[5]))
def test_unrelated_candidates_do_not_consume_scoped_budget(
    tmp_path: Path, strategy: RetrievalStrategy, query: str, text: str,
) -> None:
    database = tmp_path / "mke.sqlite"
    source, publication = publish_pages(database, (text,) * 13, fingerprint="f")
    publish_pages(database, (text,) * 1001, fingerprint="a")
    engine = KnowledgeEngine(database, retrieval_strategy=strategy)
    try:
        with pytest.raises(CjkActiveScanError):
            engine.search(query)
        page = engine.search_source_evidence_page(
            source, publication, query, position=0, page_size=20,
            authority_validator=lambda _: None,
        )
        assert len(page.results) == 13 and not page.more_in_selected_pool
        assert not page.eligible_discarded_by_cap
    finally:
        engine.close()


def test_scoped_candidate_budget_fails_instead_of_silent_cap(tmp_path: Path) -> None:
    database = tmp_path / "mke.sqlite"
    source, publication = publish_pages(database, ("知识检索范围",) * 1001)
    engine = KnowledgeEngine(database)
    try:
        with pytest.raises(CjkActiveScanError, match="candidate pool"):
            engine.search_source_evidence_page(
                source, publication, "知识检索范围", position=0, page_size=20,
                authority_validator=lambda _: None,
            )
    finally:
        engine.close()


def test_replacement_during_read_keeps_one_snapshot_then_rejects_old_selection(
    tmp_path: Path,
) -> None:
    database = tmp_path / "mke.sqlite"
    source, publication = publish_pages(database, ("needle old",) * 3)
    engine = KnowledgeEngine(database)
    writer = KnowledgeEngine(database, recover_unfinished_runs=False)
    try:
        run = writer.create_run(source)
        writer.persist_validated_candidate(
            run.run_id, [CandidateEvidence("ev_" + "e" * 32, "page", 1, 1, "needle new")],
            RunManifest(run.run_id, 1, tuple(sorted(REQUIRED_PDF_STAGES)),
                        PDF_EXTRACTOR_FINGERPRINT, "a" * 64),
        )
        def replace_publication(_: ActiveAuthoritySnapshot) -> None:
            writer.activate_publication(run.run_id)

        page = engine.search_source_evidence_page(
            source, publication, "needle", position=0, page_size=2,
            authority_validator=replace_publication,
        )
        assert page.scope is not None and page.scope.publication_id == publication
        assert [item.provenance.result.text for item in page.results] == ["needle old"] * 2
        with pytest.raises(EvidenceNotFoundError):
            engine.search_source_evidence_page(
                source, publication, "needle", position=2, page_size=2,
                authority_validator=lambda _: None,
            )
    finally:
        engine.close()
        writer.close()
