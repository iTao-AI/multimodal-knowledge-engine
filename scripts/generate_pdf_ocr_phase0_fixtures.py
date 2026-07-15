#!/usr/bin/env python3
"""Generate the deterministic public-safe PDF OCR Phase 0 corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import fitz  # pyright: ignore[reportMissingTypeStubs]

_WIDTH = 612.0
_HEIGHT = 792.0
_DPI = 200
_METADATA = {
    "author": "Multimodal Knowledge Engine",
    "creator": "MKE deterministic Phase 0 fixture generator",
    "producer": "PyMuPDF",
    "subject": "Repository-authored synthetic OCR evaluation fixture",
    "creationDate": "D:20260713000000Z",
    "modDate": "D:20260713000000Z",
}

_ENGLISH = "Aurora station uses amber seals for verified cargo."
_CHINESE = "巡检编号为海燕四十二号。"
_MIXED_TEXT = "Text-layer evidence remains authoritative."
_MIXED_SCAN = "Scanned appendix code is ORBIT-731."
_ADVERSARIAL_SCAN = "Full-page scan requires OCR routing."


def generate_fixture_tree(output_root: Path) -> Path:
    output_root.mkdir(parents=True, exist_ok=False)
    documents_root = output_root / "documents"
    documents_root.mkdir()

    _write_image_only_pdf(documents_root / "english-scan.pdf", _ENGLISH, fontname="helv")
    _write_image_only_pdf(documents_root / "chinese-scan.pdf", _CHINESE, fontname="china-s")
    _write_mixed_pdf(documents_root / "mixed-prose.pdf")
    _write_adversarial_pdf(documents_root / "routing-adversarial.pdf")

    document_specs: list[tuple[str, str, list[dict[str, object]]]] = [
        (
            "english-scan",
            "documents/english-scan.pdf",
            [_page(1, "ocr_required", ocr_text=_ENGLISH)],
        ),
        (
            "chinese-scan",
            "documents/chinese-scan.pdf",
            [_page(1, "ocr_required", ocr_text=_CHINESE)],
        ),
        (
            "mixed-prose",
            "documents/mixed-prose.pdf",
            [
                _page(1, "text_layer_accepted", text_layer_text=_MIXED_TEXT),
                _page(2, "ocr_required", ocr_text=_MIXED_SCAN),
            ],
        ),
        (
            "routing-adversarial",
            "documents/routing-adversarial.pdf",
            [
                _page(1, "blank_nontext"),
                _page(2, "ambiguous_unsupported"),
                _page(3, "ambiguous_unsupported"),
                _page(4, "ambiguous_unsupported"),
                _page(5, "ocr_required", ocr_text=_ADVERSARIAL_SCAN),
            ],
        ),
    ]
    documents: list[dict[str, object]] = []
    for document_id, relative_path, pages in document_specs:
        path = output_root / relative_path
        data = path.read_bytes()
        documents.append(
            {
                "document_id": document_id,
                "fixture": {
                    "path": relative_path,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                },
                "pages": pages,
            }
        )
    protocol = {
        "schema": "mke.pdf_ocr_eval_protocol.v1",
        "protocol_id": "pdf-ocr-phase0-v1",
        "providers": [
            "apple-vision-local-v1",
            "paddleocr-vl-1.6-cpu-spike-v1",
            "ppocrv6-medium-cpu-spike-v1",
        ],
        "documents": documents,
        "queries": [
            _query("amber-seals", "amber seals", "english-scan", 1),
            _query("haiyan-42", "海燕四十二号", "chinese-scan", 1),
            _query("orbit-731", "ORBIT-731", "mixed-prose", 2),
        ],
    }
    (output_root / "protocol.json").write_text(
        json.dumps(protocol, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_root


def _page(
    page_number: int,
    route: str,
    *,
    text_layer_text: str | None = None,
    ocr_text: str | None = None,
) -> dict[str, object]:
    return {
        "page_number": page_number,
        "expected_route": route,
        "expected_text_layer_text": text_layer_text,
        "expected_ocr_text": ocr_text,
    }


def _query(query_id: str, text: str, document_id: str, page: int) -> dict[str, object]:
    return {
        "query_id": query_id,
        "text": text,
        "expected_document_id": document_id,
        "expected_evidence_ref": {
            "schema_version": "mke.evidence_ref.v1",
            "locator": {"kind": "page", "start": page, "end": page},
        },
    }


def _write_image_only_pdf(path: Path, text: str, *, fontname: str) -> None:
    png = _render_text_png(text, fontname=fontname)
    document: Any = fitz.open()
    try:
        page: Any = document.new_page(width=_WIDTH, height=_HEIGHT)
        page.insert_image(page.rect, stream=png)
        _save(document, path, title=path.stem)
    finally:
        document.close()


def _write_mixed_pdf(path: Path) -> None:
    scan = _render_text_png(_MIXED_SCAN, fontname="helv")
    document: Any = fitz.open()
    try:
        first: Any = document.new_page(width=_WIDTH, height=_HEIGHT)
        _insert_text(first, _MIXED_TEXT, fontname="helv")
        second: Any = document.new_page(width=_WIDTH, height=_HEIGHT)
        second.insert_image(second.rect, stream=scan)
        _save(document, path, title=path.stem)
    finally:
        document.close()


def _write_adversarial_pdf(path: Path) -> None:
    decorative = _render_decorative_png()
    full_scan = _render_text_png(_ADVERSARIAL_SCAN, fontname="helv")
    document: Any = fitz.open()
    try:
        document.new_page(width=_WIDTH, height=_HEIGHT)

        decorative_page: Any = document.new_page(width=_WIDTH, height=_HEIGHT)
        decorative_page.insert_image(fitz.Rect(36, 36, 136, 96), stream=decorative)

        hidden_page: Any = document.new_page(width=_WIDTH, height=_HEIGHT)
        hidden_page.insert_text(
            (72, 96),
            "Hidden garbage layer must not authorize extraction.",
            fontsize=12,
            fontname="helv",
            render_mode=3,
        )
        hidden_page.insert_image(hidden_page.rect, stream=full_scan)

        vector_page: Any = document.new_page(width=_WIDTH, height=_HEIGHT)
        for offset in range(8):
            x = 72 + offset * 24
            vector_page.draw_rect(fitz.Rect(x, 100, x + 14, 132), color=(0, 0, 0), width=2)

        scan_page: Any = document.new_page(width=_WIDTH, height=_HEIGHT)
        scan_page.insert_image(scan_page.rect, stream=full_scan)
        _save(document, path, title=path.stem)
    finally:
        document.close()


def _render_text_png(text: str, *, fontname: str) -> bytes:
    source: Any = fitz.open()
    try:
        page: Any = source.new_page(width=_WIDTH, height=_HEIGHT)
        _insert_text(page, text, fontname=fontname)
        pixmap: Any = page.get_pixmap(dpi=_DPI, alpha=False, colorspace=fitz.csRGB)
        return bytes(pixmap.tobytes("png"))
    finally:
        source.close()


def _render_decorative_png() -> bytes:
    source: Any = fitz.open()
    try:
        page: Any = source.new_page(width=100, height=60)
        page.draw_rect(page.rect, color=(0.2, 0.3, 0.7), fill=(0.9, 0.7, 0.2), width=2)
        pixmap: Any = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
        return bytes(pixmap.tobytes("png"))
    finally:
        source.close()


def _insert_text(page: Any, text: str, *, fontname: str) -> None:
    written: float = page.insert_textbox(
        fitz.Rect(72, 96, 540, 696),
        text,
        fontsize=18,
        fontname=fontname,
    )
    if written < 0:
        raise RuntimeError("fixture text did not fit")


def _save(document: Any, path: Path, *, title: str) -> None:
    document.set_metadata({**_METADATA, "title": f"MKE PDF OCR Phase 0: {title}"})
    document.save(path, garbage=4, clean=True, deflate=True, no_new_id=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    generate_fixture_tree(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
