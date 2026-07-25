from pathlib import Path

import pytest

from mke.adapters.sqlite import EvidenceNotFoundError
from mke.application import KnowledgeEngine
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
