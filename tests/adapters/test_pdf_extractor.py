from pathlib import Path

import pytest

from mke.adapters.pdf import PdfExtractionError, PyMuPDFPdfExtractor
from tests.conftest import PDF_FIXTURES


def test_pymupdf_extractor_returns_pages_and_report() -> None:
    result = PyMuPDFPdfExtractor().extract(PDF_FIXTURES / "text-layer.pdf")

    assert result.report.total_pages == 2
    assert result.report.extracted_pages == 2
    assert result.report.empty_pages == 0
    assert result.report.total_extracted_chars > 0
    assert result.report.extraction_mode == "pymupdf-text"
    assert result.pages[0].page_number == 1
    assert "Trustworthy evidence starts on page one." in result.pages[0].text


def test_pymupdf_extractor_counts_empty_pages(tmp_path: Path) -> None:
    path = tmp_path / "blank-and-text.pdf"
    _write_blank_and_text_pdf(path)

    result = PyMuPDFPdfExtractor().extract(path)

    assert result.report.total_pages == 2
    assert result.report.extracted_pages == 1
    assert result.report.empty_pages == 1
    assert result.report.page_char_counts[-1] == 0
    assert [page.page_number for page in result.pages] == [1]


def test_pymupdf_extractor_rejects_invalid_pdf(tmp_path: Path) -> None:
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.7\ntruncated")

    with pytest.raises(PdfExtractionError, match="PDF cannot be opened"):
        PyMuPDFPdfExtractor().extract(path)


def test_pymupdf_extractor_rejects_encrypted_pdf(tmp_path: Path) -> None:
    path = tmp_path / "encrypted.pdf"
    _write_encrypted_pdf(path)

    with pytest.raises(PdfExtractionError, match="encrypted PDF is not supported"):
        PyMuPDFPdfExtractor().extract(path)


def test_pymupdf_extractor_rejects_no_text_pdf() -> None:
    with pytest.raises(PdfExtractionError, match="no extractable text"):
        PyMuPDFPdfExtractor().extract(PDF_FIXTURES / "no-text.pdf")


def test_pymupdf_extractor_uses_sorted_text_order(tmp_path: Path) -> None:
    path = tmp_path / "two-column.pdf"
    _write_two_column_pdf(path)

    result = PyMuPDFPdfExtractor().extract(path)

    text = result.pages[0].text
    assert text.index("left column first") < text.index("right column second")


def test_pymupdf_extractor_preserves_50_page_numbers(tmp_path: Path) -> None:
    path = tmp_path / "many-pages.pdf"
    _write_many_pages_pdf(path, pages=50)

    result = PyMuPDFPdfExtractor().extract(path)

    assert result.report.total_pages == 50
    assert result.report.extracted_pages == 50
    assert result.pages[0].page_number == 1
    assert result.pages[-1].page_number == 50


def _write_blank_and_text_pdf(path: Path) -> None:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "visible text page")
    doc.new_page()
    doc.save(path)


def _write_two_column_pdf(path: Path) -> None:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((320, 72), "right column second")
    page.insert_text((72, 72), "left column first")
    doc.save(path)


def _write_many_pages_pdf(path: Path, pages: int) -> None:
    import pymupdf

    doc = pymupdf.open()
    for index in range(1, pages + 1):
        page = doc.new_page()
        page.insert_text((72, 72), f"page {index} evidence text")
    doc.save(path)


def _write_encrypted_pdf(path: Path) -> None:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "encrypted evidence text")
    doc.save(
        path,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw="user-password",
        permissions=int(pymupdf.PDF_PERM_ACCESSIBILITY),
    )
