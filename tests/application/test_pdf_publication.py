from pathlib import Path

import pytest

from mke.application import KnowledgeEngine, PdfIngestError
from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    CandidateEvidence,
    FailurePoint,
    PdfExtractionResult,
    PdfIntakeReport,
    PdfPageText,
    RunEventType,
    RunManifest,
    RunState,
)
from tests.conftest import PDF_FIXTURES


def test_pdf_ingest_publishes_page_evidence_to_active_search(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    result = engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")

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
        required_stages=tuple(sorted(REQUIRED_PDF_STAGES)),
        extractor_fingerprint=PDF_EXTRACTOR_FINGERPRINT,
        asset_sha256="b" * 64,
    )

    engine.persist_validated_candidate(run.run_id, evidence, manifest)

    assert engine.get_run(run.run_id).state == RunState.VALIDATED
    assert engine.search("candidate") == []
    assert [event.event_type for event in engine.get_run_events(run.run_id)] == [
        RunEventType.RUN_CREATED,
        RunEventType.RUN_STARTED,
        RunEventType.CANDIDATE_VALIDATED,
    ]


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

    with pytest.raises(PdfIngestError, match="PDF cannot be opened"):
        engine.ingest_pdf(PDF_FIXTURES / "invalid.pdf")

    with pytest.raises(PdfIngestError, match="extractable text"):
        engine.ingest_pdf(PDF_FIXTURES / "no-text.pdf")

    assert engine.search("anything") == []


def test_fts_query_syntax_is_escaped(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")

    assert engine.search('" OR active* : NEAR(page)') == []
    assert [match.page_number for match in engine.search("active page")] == [2]


def test_get_run_unknown_id_raises_keyerror(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    with pytest.raises(KeyError, match="unknown run"):
        engine.get_run("run_nonexistent")


def test_create_run_unknown_source_raises_keyerror(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    with pytest.raises(KeyError, match="unknown source"):
        engine.create_run("src_nonexistent")


def test_publishable_after_invalid_pdf_failure(tmp_path: Path) -> None:
    """A failed ingest must not prevent a later successful ingest on the same asset."""
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    with pytest.raises(PdfIngestError):
        engine.ingest_pdf(PDF_FIXTURES / "invalid.pdf")

    result = engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
    assert result.run_state == RunState.PUBLISHED
    assert result.evidence_count == 2
    assert len(engine.search("trustworthy")) == 1


def test_pdf_ingest_result_carries_intake_report(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    result = engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")

    assert result.intake_report is not None
    assert result.intake_report.total_pages == 2
    assert result.intake_report.extracted_pages == 2
    assert engine.get_pdf_intake_report(result.run_id) == result.intake_report


def test_prepare_pdf_candidate_persists_report_after_validation(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    result = engine.prepare_pdf_candidate(PDF_FIXTURES / "text-layer.pdf")

    assert result.run_state == RunState.VALIDATED
    assert result.intake_report is not None
    assert engine.get_pdf_intake_report(result.run_id) == result.intake_report


def test_successful_extraction_report_is_not_persisted_when_validation_fails(
    tmp_path: Path,
) -> None:
    path = tmp_path / "invalid-page.pdf"
    path.write_bytes(b"stub pdf bytes")
    engine = KnowledgeEngine(tmp_path / "mke.sqlite", pdf_extractor=_InvalidPageExtractor())

    with pytest.raises(PdfIngestError, match="positive page numbers") as error:
        engine.ingest_pdf(path)

    run_id = error.value.run_id
    assert run_id is not None
    assert engine.get_run(run_id).state == RunState.FAILED
    assert engine.get_pdf_intake_report(run_id) is None


def test_successful_extraction_report_is_not_persisted_when_candidate_write_fails(
    tmp_path: Path,
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    with pytest.raises(PdfIngestError, match=FailurePoint.DURING_CANDIDATE_WRITES.value) as error:
        engine.reprocess_pdf(
            PDF_FIXTURES / "text-layer.pdf",
            failure_point=FailurePoint.DURING_CANDIDATE_WRITES,
        )

    run_id = error.value.run_id
    assert run_id is not None
    assert engine.get_run(run_id).state == RunState.FAILED
    assert engine.get_pdf_intake_report(run_id) is None


def test_successful_extraction_report_is_not_persisted_when_activation_fails(
    tmp_path: Path,
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")

    with pytest.raises(PdfIngestError, match=FailurePoint.AFTER_PUBLICATION_INSERT.value) as error:
        engine.reprocess_pdf(
            PDF_FIXTURES / "text-layer-revised.pdf",
            failure_point=FailurePoint.AFTER_PUBLICATION_INSERT,
        )

    run_id = error.value.run_id
    assert run_id is not None
    assert engine.get_run(run_id).state == RunState.VALIDATED
    assert engine.get_pdf_intake_report(run_id) is None


def test_interrupted_pdf_run_cannot_validate_or_change_active_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
    before_search = engine.search("trustworthy")
    before_ask = engine.ask("Where is the trustworthy evidence?")
    original_persist = engine._store.persist_validated_candidate  # pyright: ignore[reportPrivateUsage]

    def interrupt_before_validation(*args: object, **kwargs: object) -> None:
        engine._store.interrupt_unfinished_runs()  # pyright: ignore[reportPrivateUsage]
        original_persist(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        engine._store,  # pyright: ignore[reportPrivateUsage]
        "persist_validated_candidate",
        interrupt_before_validation,
    )

    with pytest.raises(PdfIngestError, match="Run state changed") as error:
        engine.reprocess_pdf(PDF_FIXTURES / "text-layer-revised.pdf")

    run_id = error.value.run_id
    assert run_id is not None
    assert engine.get_run(run_id).state is RunState.INTERRUPTED
    event_types = [event.event_type for event in engine.get_run_events(run_id)]
    assert RunEventType.CANDIDATE_VALIDATED not in event_types
    assert RunEventType.PUBLICATION_ACTIVATED not in event_types
    assert engine.search("trustworthy") == before_search
    after_ask = engine.ask("Where is the trustworthy evidence?")
    assert (
        after_ask.answer_status,
        after_ask.summary,
        after_ask.evidence,
        after_ask.limitations,
    ) == (
        before_ask.answer_status,
        before_ask.summary,
        before_ask.evidence,
        before_ask.limitations,
    )


def test_knowledge_engine_accepts_custom_pdf_extractor(tmp_path: Path) -> None:
    path = tmp_path / "stub.pdf"
    path.write_bytes(b"stub pdf bytes")
    engine = KnowledgeEngine(tmp_path / "mke.sqlite", pdf_extractor=_StubExtractor())

    result = engine.ingest_pdf(path)

    assert result.run_state == RunState.PUBLISHED
    assert result.intake_report is not None
    assert result.intake_report.extraction_mode == "stub"
    assert engine.search("stub") != []


def test_failed_pdf_ingest_persists_failure_report(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    with pytest.raises(PdfIngestError) as error:
        engine.ingest_pdf(PDF_FIXTURES / "no-text.pdf")

    report = engine.get_pdf_intake_report(error.value.run_id or "")
    assert report is not None
    assert report.failure_reason == "PDF has no extractable text"
    assert engine.search("anything") == []


def _stub_report() -> PdfIntakeReport:
    return PdfIntakeReport(
        total_pages=1,
        extracted_pages=1,
        empty_pages=0,
        total_extracted_chars=13,
        page_char_counts=(13,),
        suspected_scanned_pages=0,
        extraction_mode="stub",
        failure_reason=None,
    )


class _StubExtractor:
    def extract(self, path: Path) -> PdfExtractionResult:
        return PdfExtractionResult(
            report=_stub_report(),
            pages=(PdfPageText(page_number=1, text="stub evidence"),),
        )


class _InvalidPageExtractor:
    def extract(self, path: Path) -> PdfExtractionResult:
        return PdfExtractionResult(
            report=_stub_report(),
            pages=(PdfPageText(page_number=0, text="stub evidence"),),
        )
