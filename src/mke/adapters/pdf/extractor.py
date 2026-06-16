"""PyMuPDF-backed text-layer PDF extractor."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import pymupdf

from mke.domain import PdfExtractionResult, PdfIntakeReport, PdfPageText


class PdfExtractionError(ValueError):
    """Raised when a PDF cannot produce trustworthy text-layer Evidence."""

    def __init__(self, message: str, report: PdfIntakeReport | None = None) -> None:
        super().__init__(message)
        self.report = report


class PyMuPDFPdfExtractor:
    """Extract text-layer page Evidence and intake diagnostics from local PDFs."""

    extraction_mode = "pymupdf-text"

    def extract(self, path: Path) -> PdfExtractionResult:
        if path.suffix.lower() != ".pdf":
            report = _failure_report("PDF cannot be opened")
            raise PdfExtractionError("PDF cannot be opened", report)
        document: Any | None = None
        try:
            document = pymupdf.open(path)
            if document.is_encrypted:
                report = _failure_report("encrypted PDF is not supported")
                raise PdfExtractionError("encrypted PDF is not supported", report)
            pages: list[PdfPageText] = []
            page_char_counts: list[int] = []
            suspected_scanned_pages = 0
            total_pages = int(document.page_count)
            for page_index in range(total_pages):
                page: Any = document.load_page(page_index)
                text = _normalize_page_text(
                    cast(str, page.get_text("text", sort=True))
                )
                char_count = len(text)
                page_char_counts.append(char_count)
                if text:
                    pages.append(PdfPageText(page_number=page_index + 1, text=text))
                elif page.get_images(full=True):
                    suspected_scanned_pages += 1
            report = PdfIntakeReport(
                total_pages=total_pages,
                extracted_pages=len(pages),
                empty_pages=total_pages - len(pages),
                total_extracted_chars=sum(page_char_counts),
                page_char_counts=tuple(page_char_counts),
                suspected_scanned_pages=suspected_scanned_pages,
                extraction_mode=self.extraction_mode,
                failure_reason=None,
            )
        except PdfExtractionError:
            raise
        except Exception as error:
            report = _failure_report("PDF cannot be opened")
            raise PdfExtractionError("PDF cannot be opened", report) from error
        finally:
            if document is not None:
                document.close()
        if not pages:
            failed = PdfIntakeReport(
                total_pages=report.total_pages,
                extracted_pages=0,
                empty_pages=report.empty_pages,
                total_extracted_chars=0,
                page_char_counts=report.page_char_counts,
                suspected_scanned_pages=report.suspected_scanned_pages,
                extraction_mode=report.extraction_mode,
                failure_reason="PDF has no extractable text",
            )
            raise PdfExtractionError("PDF has no extractable text", failed)
        return PdfExtractionResult(report=report, pages=tuple(pages))


def extract_text_pages(path: Path) -> list[PdfPageText]:
    """Compatibility helper for callers not yet using PdfExtractionResult."""
    return list(PyMuPDFPdfExtractor().extract(path).pages)


def _normalize_page_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", " ")
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f]", " ", text)
    return text.strip()


def _failure_report(reason: str) -> PdfIntakeReport:
    return PdfIntakeReport(
        total_pages=0,
        extracted_pages=0,
        empty_pages=0,
        total_extracted_chars=0,
        page_char_counts=(),
        suspected_scanned_pages=0,
        extraction_mode=PyMuPDFPdfExtractor.extraction_mode,
        failure_reason=reason,
    )
