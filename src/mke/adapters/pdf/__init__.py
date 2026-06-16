"""Built-in text-layer PDF extraction adapter."""

from mke.adapters.pdf.extractor import (
    PdfExtractionError,
    PyMuPDFPdfExtractor,
    extract_text_pages,
)

__all__ = ["PdfExtractionError", "PyMuPDFPdfExtractor", "extract_text_pages"]
