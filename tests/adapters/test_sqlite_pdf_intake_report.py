import sqlite3
from pathlib import Path

import pytest

from mke.adapters.sqlite import SQLiteStore
from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    CandidateEvidence,
    ManifestValidationError,
    PdfIntakeReport,
    RunManifest,
    RunState,
)


def test_sqlite_persists_pdf_intake_report_for_run(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "mke.sqlite")
    source = store.ensure_source("doc.pdf", "a" * 64)
    run = store.create_run(source.source_id)
    report = PdfIntakeReport(
        total_pages=2,
        extracted_pages=1,
        empty_pages=1,
        total_extracted_chars=20,
        page_char_counts=(20, 0),
        suspected_scanned_pages=1,
        extraction_mode="pymupdf-text",
        failure_reason=None,
    )

    store.persist_pdf_intake_report(run.run_id, report)

    loaded = store.get_pdf_intake_report(run.run_id)
    assert loaded == report


def test_sqlite_returns_none_for_missing_pdf_intake_report(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "mke.sqlite")
    source = store.ensure_source("doc.pdf", "a" * 64)
    run = store.create_run(source.source_id)

    assert store.get_pdf_intake_report(run.run_id) is None


def test_pdf_report_insert_failure_rolls_back_first_publication_atomically(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "mke.sqlite")
    source = store.ensure_source("first.pdf", "a" * 64)
    run_id = _validated_pdf_run(store, source.source_id, "first publication")
    _fail_pdf_report_insertion(store)

    with pytest.raises(sqlite3.IntegrityError, match="injected pdf report insert failure"):
        store.activate_publication(run_id, pdf_intake_report=_pdf_report("first publication"))

    assert store.get_run(run_id).state is RunState.VALIDATED
    assert store.get_pdf_intake_report(run_id) is None
    assert store.get_source(source.source_id).active_publication_id is None
    assert _count_rows(store, "publications") == 0
    assert _count_rows(store, "active_evidence_fts") == 0


def test_pdf_report_insert_failure_preserves_previous_active_publication(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "mke.sqlite")
    source = store.ensure_source("reprocess.pdf", "a" * 64)
    first_run_id = _validated_pdf_run(store, source.source_id, "previous active")
    first_activation = store.activate_publication(first_run_id)
    assert first_activation.published
    before_source = store.get_source(source.source_id)
    before_search = store.search("previous active")

    second_run_id = _validated_pdf_run(store, source.source_id, "replacement evidence")
    _fail_pdf_report_insertion(store)

    with pytest.raises(sqlite3.IntegrityError, match="injected pdf report insert failure"):
        store.activate_publication(
            second_run_id,
            pdf_intake_report=_pdf_report("replacement evidence"),
        )

    assert store.get_run(second_run_id).state is RunState.VALIDATED
    assert store.get_pdf_intake_report(second_run_id) is None
    after_source = store.get_source(source.source_id)
    assert after_source.active_publication_id == before_source.active_publication_id
    assert after_source.active_revision == before_source.active_revision
    assert store.search("previous active") == before_search
    assert store.search("replacement evidence") == []
    assert _count_rows(store, "publications") == 1


def test_pdf_activation_rejects_nonzero_page_without_candidate_evidence(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "mke.sqlite")
    source = store.ensure_source("forged-first.pdf", "a" * 64)
    run_id = _validated_pdf_run(store, source.source_id, "candidate evidence")
    report = _two_page_report("candidate evidence", second_page_chars=5)

    with pytest.raises(ManifestValidationError, match="does not match candidate Evidence"):
        store.activate_publication(run_id, pdf_intake_report=report)

    assert store.get_run(run_id).state is RunState.VALIDATED
    assert store.get_pdf_intake_report(run_id) is None
    assert store.get_source(source.source_id).active_publication_id is None
    assert _count_rows(store, "publications") == 0
    assert _count_rows(store, "active_evidence_fts") == 0


def test_pdf_reprocess_rejects_nonzero_page_without_candidate_evidence(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "mke.sqlite")
    source = store.ensure_source("forged-reprocess.pdf", "a" * 64)
    first_run_id = _validated_pdf_run(store, source.source_id, "previous active")
    first_activation = store.activate_publication(
        first_run_id,
        pdf_intake_report=_pdf_report("previous active"),
    )
    assert first_activation.published
    before_source = store.get_source(source.source_id)
    before_search = store.search("previous active")

    second_run_id = _validated_pdf_run(store, source.source_id, "replacement evidence")
    report = _two_page_report("replacement evidence", second_page_chars=5)

    with pytest.raises(ManifestValidationError, match="does not match candidate Evidence"):
        store.activate_publication(second_run_id, pdf_intake_report=report)

    assert store.get_run(second_run_id).state is RunState.VALIDATED
    assert store.get_pdf_intake_report(second_run_id) is None
    after_source = store.get_source(source.source_id)
    assert after_source.active_publication_id == before_source.active_publication_id
    assert after_source.active_revision == before_source.active_revision
    assert store.search("previous active") == before_search
    assert store.search("replacement evidence") == []
    assert _count_rows(store, "publications") == 1


def test_pdf_activation_accepts_exact_nonzero_page_inventory(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "mke.sqlite")
    source = store.ensure_source("exact-boundary.pdf", "a" * 64)
    text = "exact page evidence"
    run_id = _validated_pdf_run(store, source.source_id, text)
    report = _two_page_report(text, second_page_chars=0)

    activation = store.activate_publication(run_id, pdf_intake_report=report)

    assert activation.published
    assert store.get_pdf_intake_report(run_id) == report


@pytest.mark.parametrize(
    ("report", "message"),
    [
        (
            PdfIntakeReport(
                total_pages=1,
                extracted_pages=1,
                empty_pages=0,
                total_extracted_chars=17,
                page_char_counts=(17,),
                suspected_scanned_pages=0,
                extraction_mode="project-owned-test",
                failure_reason="extraction failed",
            ),
            "successful PDF intake report",
        ),
        (
            PdfIntakeReport(
                total_pages=1,
                extracted_pages=1,
                empty_pages=0,
                total_extracted_chars=16,
                page_char_counts=(16,),
                suspected_scanned_pages=0,
                extraction_mode="project-owned-test",
                failure_reason=None,
            ),
            "does not match candidate Evidence",
        ),
    ],
)
def test_pdf_activation_validates_report_before_publication_visibility(
    tmp_path: Path, report: PdfIntakeReport, message: str
) -> None:
    store = SQLiteStore(tmp_path / "mke.sqlite")
    source = store.ensure_source("invalid-report.pdf", "a" * 64)
    run_id = _validated_pdf_run(store, source.source_id, "candidate evidence")

    with pytest.raises(ManifestValidationError, match=message):
        store.activate_publication(run_id, pdf_intake_report=report)

    assert store.get_run(run_id).state is RunState.VALIDATED
    assert store.get_pdf_intake_report(run_id) is None
    assert store.get_source(source.source_id).active_publication_id is None
    assert _count_rows(store, "publications") == 0


def _pdf_report(text: str, *, failure_reason: str | None = None) -> PdfIntakeReport:
    return PdfIntakeReport(
        total_pages=1,
        extracted_pages=1,
        empty_pages=0,
        total_extracted_chars=len(text),
        page_char_counts=(len(text),),
        suspected_scanned_pages=0,
        extraction_mode="project-owned-test",
        failure_reason=failure_reason,
    )


def _two_page_report(text: str, *, second_page_chars: int) -> PdfIntakeReport:
    return PdfIntakeReport(
        total_pages=2,
        extracted_pages=1,
        empty_pages=1,
        total_extracted_chars=len(text) + second_page_chars,
        page_char_counts=(len(text), second_page_chars),
        suspected_scanned_pages=0,
        extraction_mode="project-owned-test",
        failure_reason=None,
    )


def _validated_pdf_run(store: SQLiteStore, source_id: str, text: str) -> str:
    run = store.create_run(source_id)
    store.mark_run_running(run.run_id)
    store.persist_validated_candidate(
        run.run_id,
        [CandidateEvidence(f"ev_{run.run_id}", "page", 1, 1, text)],
        RunManifest(
            run_id=run.run_id,
            evidence_count=1,
            required_stages=tuple(sorted(REQUIRED_PDF_STAGES)),
            extractor_fingerprint=PDF_EXTRACTOR_FINGERPRINT,
            asset_sha256="a" * 64,
        ),
    )
    return run.run_id


def _fail_pdf_report_insertion(store: SQLiteStore) -> None:
    store._connection.executescript(  # pyright: ignore[reportPrivateUsage]
        """
        CREATE TRIGGER fail_pdf_report
        BEFORE INSERT ON pdf_intake_reports
        BEGIN
          SELECT RAISE(ABORT, 'injected pdf report insert failure');
        END;
        """
    )
    store._connection.commit()  # pyright: ignore[reportPrivateUsage]


def _count_rows(store: SQLiteStore, table: str) -> int:
    row = store._connection.execute(  # pyright: ignore[reportPrivateUsage]
        f"SELECT COUNT(*) AS count FROM {table}"
    ).fetchone()
    assert row is not None
    return int(row["count"])
