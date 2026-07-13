"""Lazy PP-OCRv6 medium candidate child for Phase 0 evaluation."""

from __future__ import annotations

import argparse
import importlib
import json
import math
import time
from pathlib import Path
from typing import Any, NoReturn, cast

import fitz  # pyright: ignore[reportMissingTypeStubs]

from mke.evaluation.pdf_ocr_provider import normalize_ocr_text

PROVIDER = "ppocrv6-medium-cpu-spike-v1"
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
    detection_model_dir: Path,
    recognition_model_dir: Path,
) -> None:
    _require_file(input_image, "OCR page input is unavailable")
    _require_file(output_path, "OCR result file is unavailable")
    _require_model_dir(detection_model_dir)
    _require_model_dir(recognition_model_dir)
    try:
        module = importlib.import_module("paddleocr")
    except ImportError as error:
        raise PdfOcrChildError("PDF OCR optional dependency is not installed") from error
    paddle_ocr: Any = module.PaddleOCR
    started = time.monotonic()
    pipeline: Any = paddle_ocr(
        text_detection_model_name="PP-OCRv6_medium_det",
        text_detection_model_dir=str(detection_model_dir),
        text_recognition_model_name="PP-OCRv6_medium_rec",
        text_recognition_model_dir=str(recognition_model_dir),
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        device="cpu",
    )
    results: list[Any] = list(pipeline.predict(str(input_image)))
    if len(results) != 1:
        _fail("provider result inventory is invalid")
    raw_json: object = results[0].json
    if not isinstance(raw_json, dict):
        _fail("provider result schema is invalid")
    root = cast(dict[str, object], raw_json)
    raw_payload = root.get("res", root)
    if not isinstance(raw_payload, dict):
        _fail("provider result schema is invalid")
    payload = cast(dict[str, object], raw_payload)
    texts = _list(payload.get("rec_texts"))
    scores = _list(payload.get("rec_scores"))
    boxes = _list(payload.get("rec_boxes"))
    if not texts or not (len(texts) == len(scores) == len(boxes)):
        _fail("provider result inventory is invalid")
    pixmap: Any = fitz.Pixmap(str(input_image))
    width = int(pixmap.width)
    height = int(pixmap.height)
    if width <= 0 or height <= 0:
        _fail("provider image geometry is invalid")
    lines: list[dict[str, object]] = []
    for text_value, score_value, box_value in zip(texts, scores, boxes, strict=True):
        text = _text(text_value)
        score = _score(score_value)
        box = _box(box_value, width=width, height=height)
        lines.append({"text": text, "confidence": score, "box": box})
    normalized_text = normalize_ocr_text(
        "\n".join(cast(str, item["text"]) for item in lines)
    )
    _write_result(
        output_path,
        {
            "schema": "mke.pdf_ocr_eval_result.v1",
            "provider": PROVIDER,
            "profile": PROFILE,
            "page_number": page_number,
            "lines": lines,
            "normalized_text": normalized_text,
            "duration_ms": max(0, round((time.monotonic() - started) * 1000)),
        },
    )


def _require_file(path: Path, cause: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise PdfOcrChildError(cause)


def _require_model_dir(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        raise PdfOcrChildError("model directory is unavailable")


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        _fail("provider result schema is invalid")
    return cast(list[object], value)


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("provider result schema is invalid")
    normalized = normalize_ocr_text(value)
    if not normalized:
        _fail("provider result schema is invalid")
    return normalized


def _score(value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0 <= value <= 1
    ):
        _fail("provider result schema is invalid")
    return float(value)


def _box(value: object, *, width: int, height: int) -> list[float]:
    if not isinstance(value, (list, tuple)):
        _fail("provider result schema is invalid")
    items = cast(list[object] | tuple[object, ...], value)
    if len(items) != 4:
        _fail("provider result schema is invalid")
    numbers: list[float] = []
    for item in items:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
            _fail("provider result schema is invalid")
        numbers.append(float(item))
    x0, y0, x1, y1 = numbers
    if x0 < 0 or y0 < 0 or x1 < x0 or y1 < y0 or x1 > width or y1 > height:
        _fail("provider result schema is invalid")
    return [x0 / width, y0 / height, x1 / width, y1 / height]


def _write_result(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def _fail(cause: str) -> NoReturn:
    raise PdfOcrChildError(cause)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--page-number", required=True, type=int)
    parser.add_argument("--detection-model-dir", required=True, type=Path)
    parser.add_argument("--recognition-model-dir", required=True, type=Path)
    args = parser.parse_args()
    recognize(
        input_image=args.input,
        output_path=args.output,
        page_number=args.page_number,
        detection_model_dir=args.detection_model_dir,
        recognition_model_dir=args.recognition_model_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
