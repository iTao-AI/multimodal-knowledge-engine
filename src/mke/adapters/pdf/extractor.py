"""Small text-layer PDF extractor for the first offline fixture-backed slice."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


class PdfExtractionError(ValueError):
    """Raised when a PDF cannot produce trustworthy text-layer Evidence."""


@dataclass(frozen=True)
class PdfPageText:
    page_number: int
    text: str


_STREAM_RE = re.compile(rb"stream\r?\n(?P<body>.*?)\r?\nendstream", re.DOTALL)
_TEXT_RE = re.compile(rb"\((?P<text>(?:\\.|[^\\)])*)\)\s*Tj")


def extract_text_pages(path: Path) -> list[PdfPageText]:
    """Extract simple text-layer page strings without network or model dependencies.

    This adapter intentionally supports the deterministic PR 2 fixture class: unencrypted,
    uncompressed text-layer PDFs with text showing operators. OCR, compressed object streams,
    complex layout, and coordinates are explicit non-goals for this PR.
    """
    payload = path.read_bytes()
    if not payload.startswith(b"%PDF-"):
        raise PdfExtractionError("input is not a valid PDF")

    pages: list[PdfPageText] = []
    for stream in _STREAM_RE.finditer(payload):
        text = _extract_stream_text(stream.group("body"))
        if text:
            pages.append(PdfPageText(page_number=len(pages) + 1, text=text))

    if not pages:
        raise PdfExtractionError("PDF does not contain a supported text layer")
    return pages


def _extract_stream_text(stream: bytes) -> str:
    parts = [_decode_pdf_string(match.group("text")) for match in _TEXT_RE.finditer(stream)]
    return " ".join(part for part in parts if part).strip()


def _decode_pdf_string(value: bytes) -> str:
    output = bytearray()
    index = 0
    while index < len(value):
        byte = value[index]
        if byte != 0x5C:
            output.append(byte)
            index += 1
            continue
        index += 1
        if index >= len(value):
            break
        escaped = value[index]
        output.append({ord("n"): 10, ord("r"): 13, ord("t"): 9}.get(escaped, escaped))
        index += 1
    return output.decode("latin-1").strip()
