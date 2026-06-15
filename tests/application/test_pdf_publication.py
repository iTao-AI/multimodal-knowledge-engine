from pathlib import Path

import pytest

from mke.application import KnowledgeEngine, PdfIngestError
from mke.domain import CandidateEvidence, RunManifest, RunState

FIXTURES = Path(__file__).parents[1] / "fixtures" / "pdf"


def test_pdf_ingest_publishes_page_evidence_to_active_search(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    result = engine.ingest_pdf(FIXTURES / "text-layer.pdf")

    assert result.run_state == RunState.PUBLISHED
    assert result.evidence_count == 2
    matches = engine.search("trustworthy")
    assert [(match.page_number, match.text) for match in matches] == [
        (1, "Trustworthy evidence starts on page one.")
    ]


def test_candidate_evidence_is_not_searchable_before_activation(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    source = engine.ensure_source(display_name="candidate.pdf", asset_sha256="b" * 64)
    run = engine.create_run(source.source_id)
    evidence = [
        CandidateEvidence(
            evidence_id="ev_candidate",
            locator_kind="page",
            locator_start=1,
            locator_end=1,
            text="Candidate evidence must stay hidden.",
        )
    ]
    manifest = RunManifest(
        run_id=run.run_id,
        evidence_count=1,
        required_stages=("pdf_text_extraction", "candidate_evidence"),
        extractor_fingerprint="builtin-pdf-text-v1",
        asset_sha256="b" * 64,
    )

    engine.persist_validated_candidate(run.run_id, evidence, manifest)

    assert engine.get_run(run.run_id).state == RunState.VALIDATED
    assert engine.search("candidate") == []


def test_stale_run_is_superseded_without_changing_active_search(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    source = engine.ensure_source(display_name="stale.pdf", asset_sha256="c" * 64)
    older = engine.create_run(source.source_id)
    newer = engine.create_run(source.source_id)

    engine.persist_validated_candidate(
        older.run_id,
        [
            CandidateEvidence(
                evidence_id="ev_old",
                locator_kind="page",
                locator_start=1,
                locator_end=1,
                text="Older stale evidence.",
            )
        ],
        RunManifest(
            run_id=older.run_id,
            evidence_count=1,
            required_stages=("pdf_text_extraction", "candidate_evidence"),
            extractor_fingerprint="builtin-pdf-text-v1",
            asset_sha256="c" * 64,
        ),
    )

    activation = engine.activate_publication(older.run_id)

    assert activation.published is False
    assert activation.run_state == RunState.SUPERSEDED
    assert engine.get_run(older.run_id).state == RunState.SUPERSEDED
    assert engine.get_run(newer.run_id).state == RunState.QUEUED
    assert engine.search("older") == []


def test_invalid_and_no_text_pdfs_fail_without_publication(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    with pytest.raises(PdfIngestError, match="valid PDF"):
        engine.ingest_pdf(FIXTURES / "invalid.pdf")

    with pytest.raises(PdfIngestError, match="text layer"):
        engine.ingest_pdf(FIXTURES / "no-text.pdf")

    assert engine.search("anything") == []


def test_fts_query_syntax_is_escaped(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    engine.ingest_pdf(FIXTURES / "text-layer.pdf")

    assert engine.search('" OR active* : NEAR(page)') == []
    assert [match.page_number for match in engine.search("active page")] == [2]
