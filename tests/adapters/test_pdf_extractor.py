from pathlib import Path
from typing import Any

import pytest

from mke.adapters.pdf import PdfExtractionError, PyMuPDFPdfExtractor
from mke.adapters.pdf.extractor import _normalize_page_text  # pyright: ignore[reportPrivateUsage]
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


def test_pymupdf_extractor_rejects_non_pdf_extension(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("This is not a PDF.")

    with pytest.raises(PdfExtractionError, match="PDF cannot be opened") as exc_info:
        PyMuPDFPdfExtractor().extract(path)

    assert exc_info.value.report is not None
    assert exc_info.value.report.failure_reason == "PDF cannot be opened"
    assert exc_info.value.report.total_pages == 0


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


def test_pymupdf_close_failure_does_not_mask_extraction_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.7\n")

    monkeypatch.setattr("mke.adapters.pdf.extractor.pymupdf.open", _open_close_failing_document)

    with pytest.raises(PdfExtractionError, match="PDF cannot be opened"):
        PyMuPDFPdfExtractor().extract(path)


def test_pymupdf_uses_lightweight_image_detection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "image-only.pdf"
    path.write_bytes(b"%PDF-1.7\n")
    page = _ImageDetectionPage()
    monkeypatch.setattr("mke.adapters.pdf.extractor.pymupdf.open", _ImageDocumentFactory(page))

    with pytest.raises(PdfExtractionError, match="no extractable text"):
        PyMuPDFPdfExtractor().extract(path)

    assert page.seen_full_args == [False]


class TestNormalizePageText:
    def test_empty_string_returns_empty(self) -> None:
        assert _normalize_page_text("") == ""

    def test_crlf_converted_to_lf(self) -> None:
        assert _normalize_page_text("line1\r\nline2") == "line1\nline2"

    def test_bare_cr_converted_to_lf(self) -> None:
        assert _normalize_page_text("line1\rline2") == "line1\nline2"

    def test_nul_replaced_with_space(self) -> None:
        assert _normalize_page_text("before\x00after") == "before after"

    def test_control_characters_replaced_with_space(self) -> None:
        assert _normalize_page_text("text\x01\x0b\x1fend") == "text   end"

    def test_leading_trailing_whitespace_stripped(self) -> None:
        assert _normalize_page_text("  \n  content  \n  ") == "content"

    def test_unicode_text_preserved(self) -> None:
        assert _normalize_page_text("caf\u00e9 - text") == "caf\u00e9 - text"


def _write_blank_and_text_pdf(path: Path) -> None:
    import pymupdf

    doc: Any = pymupdf.open()
    page: Any = doc.new_page()
    page.insert_text((72, 72), "visible text page")
    doc.new_page()
    doc.save(path)


def _write_two_column_pdf(path: Path) -> None:
    import pymupdf

    doc: Any = pymupdf.open()
    page: Any = doc.new_page()
    page.insert_text((320, 72), "right column second")
    page.insert_text((72, 72), "left column first")
    doc.save(path)


def _write_many_pages_pdf(path: Path, pages: int) -> None:
    import pymupdf

    doc: Any = pymupdf.open()
    for index in range(1, pages + 1):
        page: Any = doc.new_page()
        page.insert_text((72, 72), f"page {index} evidence text")
    doc.save(path)


def _write_encrypted_pdf(path: Path) -> None:
    import pymupdf

    pymupdf_api: Any = pymupdf
    doc: Any = pymupdf.open()
    page: Any = doc.new_page()
    page.insert_text((72, 72), "encrypted evidence text")
    doc.save(
        path,
        encryption=pymupdf_api.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw="user-password",
        permissions=int(pymupdf_api.PDF_PERM_ACCESSIBILITY),
    )


class _CloseFailingPage:
    def get_text(self, text_format: str, *, sort: bool) -> str:
        raise RuntimeError("read failed")


class _CloseFailingDocument:
    is_encrypted = False
    page_count = 1

    def load_page(self, page_index: int) -> _CloseFailingPage:
        return _CloseFailingPage()

    def close(self) -> None:
        raise RuntimeError("close failed")


def _open_close_failing_document(path: object) -> _CloseFailingDocument:
    return _CloseFailingDocument()


class _ImageDetectionPage:
    def __init__(self) -> None:
        self.seen_full_args: list[bool] = []

    def get_text(self, text_format: str, *, sort: bool) -> str:
        return ""

    def get_images(self, full: bool = False) -> list[object]:
        self.seen_full_args.append(full)
        return []


class _SinglePageDocument:
    is_encrypted = False
    page_count = 1

    def __init__(self, page: _ImageDetectionPage) -> None:
        self._page = page

    def load_page(self, page_index: int) -> _ImageDetectionPage:
        return self._page

    def close(self) -> None:
        return None


class _ImageDocumentFactory:
    def __init__(self, page: _ImageDetectionPage) -> None:
        self._page = page

    def __call__(self, path: object) -> _SinglePageDocument:
        return _SinglePageDocument(self._page)
