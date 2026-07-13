"""Lazy PaddleOCR-VL 1.6 candidate child for Phase 0 evaluation."""

from __future__ import annotations

import argparse
import importlib
import json
import re
import shutil
import tempfile
import time
import unicodedata
from pathlib import Path
from typing import Any, NoReturn

PROVIDER = "paddleocr-vl-1.6-cpu-spike-v1"
PROFILE = "phase0-200dpi-plain-text-v1"


class PdfOcrChildError(RuntimeError):
    def __init__(self, cause: str) -> None:
        super().__init__(cause)
        self.cause = cause


def recognize(
    *,
    input_image: Path,
    output_path: Path,
    page_number: int,
    layout_model_dir: Path,
    vl_model_dir: Path,
) -> None:
    _require_file(input_image, "OCR page input is unavailable")
    _require_file(output_path, "OCR result file is unavailable")
    _require_model_dir(layout_model_dir)
    _require_model_dir(vl_model_dir)
    try:
        module = importlib.import_module("paddleocr")
    except ImportError as error:
        raise PdfOcrChildError("PDF OCR optional dependency is not installed") from error
    paddle_ocr_vl: Any = module.PaddleOCRVL
    started = time.monotonic()
    pipeline: Any = paddle_ocr_vl(
        pipeline_version="v1.6",
        layout_detection_model_dir=str(layout_model_dir),
        vl_rec_model_dir=str(vl_model_dir),
        device="cpu",
    )
    results: list[Any] = list(pipeline.predict(str(input_image)))
    if len(results) != 1:
        _fail("provider result inventory is invalid")
    private_root = Path(tempfile.mkdtemp(prefix="paddle-vl-", dir=output_path.parent))
    try:
        results[0].save_to_json(save_path=private_root)
        results[0].save_to_markdown(save_path=private_root)
        json_files = tuple(private_root.glob("*.json"))
        markdown_files = tuple(private_root.glob("*.md"))
        if len(json_files) != 1 or len(markdown_files) != 1:
            _fail("provider result inventory is invalid")
        value: object = json.loads(json_files[0].read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            _fail("provider result schema is invalid")
        markdown = markdown_files[0].read_text(encoding="utf-8")
        text = _plain_text(markdown)
        if not text:
            _fail("provider result is empty")
        lines = [
            {"text": line, "confidence": 0.0, "box": [0.0, 0.0, 1.0, 1.0]}
            for line in text.split("\n")
        ]
        output_path.write_text(
            json.dumps(
                {
                    "schema": "mke.pdf_ocr_eval_result.v1",
                    "provider": PROVIDER,
                    "profile": PROFILE,
                    "page_number": page_number,
                    "lines": lines,
                    "normalized_text": text,
                    "duration_ms": max(0, round((time.monotonic() - started) * 1000)),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
    finally:
        shutil.rmtree(private_root, ignore_errors=True)


def _plain_text(markdown: str) -> str:
    lines: list[str] = []
    for raw in unicodedata.normalize("NFC", markdown).splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("!["):
            continue
        plain = re.sub(r"^[#>*+-]+\s*", "", stripped)
        plain = re.sub(r"[`*_]", "", plain).strip()
        if plain:
            lines.append(plain)
    return "\n".join(lines)


def _require_file(path: Path, cause: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise PdfOcrChildError(cause)


def _require_model_dir(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        raise PdfOcrChildError("model directory is unavailable")


def _fail(cause: str) -> NoReturn:
    raise PdfOcrChildError(cause)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--page-number", required=True, type=int)
    parser.add_argument("--layout-model-dir", required=True, type=Path)
    parser.add_argument("--vl-model-dir", required=True, type=Path)
    args = parser.parse_args()
    recognize(
        input_image=args.input,
        output_path=args.output,
        page_number=args.page_number,
        layout_model_dir=args.layout_model_dir,
        vl_model_dir=args.vl_model_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
