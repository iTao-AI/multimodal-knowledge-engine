"""Lazy PaddleOCR-VL 1.6 candidate child for Phase 0 evaluation."""

from __future__ import annotations

import argparse
import importlib
import json
import re
import shutil
import stat
import tempfile
import time
from pathlib import Path
from typing import Any, NoReturn, cast

from mke.evaluation.pdf_ocr_provider import normalize_ocr_text

PROVIDER = "paddleocr-vl-1.6-cpu-spike-v1"
PROFILE = "phase0-200dpi-plain-text-v1"
_MAX_VENDOR_FILE_BYTES = 8 * 1024 * 1024
_MAX_VENDOR_TOTAL_BYTES = 12 * 1024 * 1024
_SUPPORTED_BLOCK_LABELS = frozenset({"paragraph", "text"})


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
        json_bytes, markdown_bytes = _read_vendor_artifacts(private_root)
        try:
            value: object = json.loads(json_bytes.decode("utf-8"))
            markdown = markdown_bytes.decode("utf-8")
        except (UnicodeError, json.JSONDecodeError) as error:
            raise PdfOcrChildError("provider result schema is invalid") from error
        structured_text = _structured_text(value)
        text = _plain_text(markdown)
        if not text or text != structured_text:
            _fail("provider result schema is invalid")
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
    normalized = normalize_ocr_text(markdown)
    for line in normalized.split("\n"):
        if (
            "|" in line
            or "$" in line
            or re.search(r"!\[[^]]*\]\([^)]*\)", line)
            or re.search(r"\[[^]]+\]\([^)]*\)", line)
            or re.match(r"^(?:#{1,6}|[>*+-]|\d+[.)])\s", line)
            or "```" in line
            or "`" in line
            or "<" in line
            or ">" in line
        ):
            _fail("provider result contains unsupported layout content")
    return normalized


def _read_vendor_artifacts(private_root: Path) -> tuple[bytes, bytes]:
    try:
        entries = tuple(private_root.iterdir())
        if len(entries) != 2:
            _fail("provider result inventory is invalid")
        by_suffix: dict[str, Path] = {}
        total_bytes = 0
        for entry in entries:
            metadata = entry.lstat()
            if entry.is_symlink() or not stat.S_ISREG(metadata.st_mode):
                _fail("provider result inventory is invalid")
            if entry.suffix not in {".json", ".md"} or entry.suffix in by_suffix:
                _fail("provider result inventory is invalid")
            if metadata.st_size > _MAX_VENDOR_FILE_BYTES:
                _fail("provider result bytes exceeded the evaluation limit")
            total_bytes += metadata.st_size
            if total_bytes > _MAX_VENDOR_TOTAL_BYTES:
                _fail("provider result bytes exceeded the evaluation limit")
            by_suffix[entry.suffix] = entry
        if set(by_suffix) != {".json", ".md"}:
            _fail("provider result inventory is invalid")
        return by_suffix[".json"].read_bytes(), by_suffix[".md"].read_bytes()
    except PdfOcrChildError:
        raise
    except OSError as error:
        raise PdfOcrChildError("provider result inventory is invalid") from error


def _structured_text(value: object) -> str:
    if not isinstance(value, dict):
        _fail("provider result schema is invalid")
    root = cast(dict[str, object], value)
    if set(root) != {"res"}:
        _fail("provider result schema is invalid")
    result = root["res"]
    if not isinstance(result, dict):
        _fail("provider result schema is invalid")
    result_payload = cast(dict[str, object], result)
    if set(result_payload) != {"parsing_res_list"}:
        _fail("provider result schema is invalid")
    blocks = result_payload["parsing_res_list"]
    if not isinstance(blocks, list) or not blocks:
        _fail("provider result schema is invalid")
    lines: list[str] = []
    for raw_block in cast(list[object], blocks):
        if not isinstance(raw_block, dict):
            _fail("provider result schema is invalid")
        block = cast(dict[str, object], raw_block)
        if set(block) != {"block_label", "block_content"}:
            _fail("provider result schema is invalid")
        label = block["block_label"]
        content = block["block_content"]
        if label not in _SUPPORTED_BLOCK_LABELS or not isinstance(content, str):
            _fail("provider result schema is invalid")
        normalized = _plain_text(content)
        if not normalized:
            _fail("provider result schema is invalid")
        lines.append(normalized)
    return normalize_ocr_text("\n".join(lines))


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
