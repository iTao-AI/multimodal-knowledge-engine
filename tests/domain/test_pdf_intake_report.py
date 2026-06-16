from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    PYMUPDF_TEXT_FINGERPRINT,
    CandidateEvidence,
    PdfIntakeReport,
    RunManifest,
    validate_manifest,
)


def test_pdf_intake_report_summary_fields_are_immutable() -> None:
    report = PdfIntakeReport(
        total_pages=3,
        extracted_pages=2,
        empty_pages=1,
        total_extracted_chars=120,
        page_char_counts=(80, 40, 0),
        suspected_scanned_pages=1,
        extraction_mode="pymupdf-text",
        failure_reason=None,
    )

    assert report.total_pages == 3
    assert report.extracted_pages == 2
    assert report.page_char_counts == (80, 40, 0)
    assert report.failure_reason is None


def test_validate_manifest_accepts_legacy_and_pymupdf_pdf_fingerprints() -> None:
    evidence = [
        CandidateEvidence(
            evidence_id="ev_page",
            locator_kind="page",
            locator_start=1,
            locator_end=1,
            text="Page text",
        )
    ]

    for fingerprint in (PDF_EXTRACTOR_FINGERPRINT, PYMUPDF_TEXT_FINGERPRINT):
        validate_manifest(
            RunManifest(
                run_id="run_pdf",
                evidence_count=1,
                required_stages=("candidate_evidence", "pdf_text_extraction"),
                extractor_fingerprint=fingerprint,
                asset_sha256="a" * 64,
            ),
            evidence,
        )
