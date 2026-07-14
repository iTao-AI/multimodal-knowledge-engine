"""Lazy PaddleOCR-VL 1.6 candidate child for Phase 0 evaluation."""

from __future__ import annotations

import argparse
import importlib
import json
import math
import os
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
_VENDOR_READ_CHUNK_BYTES = 8192
_SUPPORTED_BLOCK_LABELS = frozenset({"paragraph", "text"})
_MAX_PAGE_DIMENSION = 100_000
_MAX_BLOCKS = 1_000
_MAX_TEXT_BYTES = 1024 * 1024
_MAX_IDENTIFIER = 1_000_000
_TOP_LEVEL_KEYS = {
    "input_path",
    "page_index",
    "page_count",
    "width",
    "height",
    "model_settings",
    "parsing_res_list",
    "layout_det_res",
}
_BLOCK_KEYS = {
    "block_label",
    "block_content",
    "block_bbox",
    "block_id",
    "block_order",
    "group_id",
    "block_polygon_points",
}
_MODEL_SETTINGS = {
    "use_doc_preprocessor": False,
    "use_layout_detection": True,
    "use_chart_recognition": False,
    "use_seal_recognition": False,
    "use_ocr_for_image_block": False,
    "format_block_content": False,
    "merge_layout_blocks": True,
    "markdown_ignore_labels": [
        "number",
        "footnote",
        "header",
        "header_image",
        "footer",
        "footer_image",
        "aside_text",
    ],
    "return_layout_polygon_points": True,
}


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


def validate_observed_vendor_evidence(value: object, markdown: str) -> str:
    """Validate the pinned Phase 0 vendor envelope without exposing vendor-only fields."""
    structured_text = _structured_text(value)
    normalized_markdown = _plain_text(markdown)
    if structured_text != normalized_markdown:
        _fail("provider result schema is invalid")
    return structured_text


def _read_vendor_artifacts(private_root: Path) -> tuple[bytes, bytes]:
    try:
        entries = tuple(private_root.iterdir())
        if len(entries) != 2:
            _fail("provider result inventory is invalid")
        by_suffix: dict[str, tuple[Path, os.stat_result]] = {}
        for entry in entries:
            metadata = entry.lstat()
            if entry.is_symlink() or not stat.S_ISREG(metadata.st_mode):
                _fail("provider result inventory is invalid")
            if entry.suffix not in {".json", ".md"} or entry.suffix in by_suffix:
                _fail("provider result inventory is invalid")
            by_suffix[entry.suffix] = (entry, metadata)
        if set(by_suffix) != {".json", ".md"}:
            _fail("provider result inventory is invalid")
        artifacts: dict[str, bytes] = {}
        total_bytes = 0
        for suffix in (".json", ".md"):
            path, metadata = by_suffix[suffix]
            artifact = _read_bounded_regular_artifact(
                path,
                inventory_metadata=metadata,
                aggregate_remaining=_MAX_VENDOR_TOTAL_BYTES - total_bytes,
            )
            artifacts[suffix] = artifact
            total_bytes += len(artifact)
        return artifacts[".json"], artifacts[".md"]
    except PdfOcrChildError:
        raise
    except OSError as error:
        raise PdfOcrChildError("provider result inventory is invalid") from error


def _read_bounded_regular_artifact(
    path: Path,
    *,
    inventory_metadata: os.stat_result,
    aggregate_remaining: int,
) -> bytes:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or _identity(before) != _identity(inventory_metadata):
        _fail("provider result inventory is invalid")
    flags = os.O_RDONLY
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        after = path.lstat()
        expected_identity = _identity(inventory_metadata)
        if (
            not stat.S_ISREG(opened.st_mode)
            or not stat.S_ISREG(after.st_mode)
            or _identity(before) != expected_identity
            or _identity(opened) != expected_identity
            or _identity(after) != expected_identity
        ):
            _fail("provider result inventory is invalid")
        allowed_bytes = min(_MAX_VENDOR_FILE_BYTES, aggregate_remaining)
        content = bytearray()
        while True:
            request_bytes = min(
                _VENDOR_READ_CHUNK_BYTES,
                max(1, allowed_bytes - len(content) + 1),
            )
            chunk = os.read(descriptor, request_bytes)
            if not chunk:
                break
            content.extend(chunk)
            if (
                len(content) > _MAX_VENDOR_FILE_BYTES
                or len(content) > aggregate_remaining
            ):
                _fail("provider result bytes exceeded the evaluation limit")
        return bytes(content)
    finally:
        os.close(descriptor)


def _identity(metadata: os.stat_result) -> tuple[int, int]:
    return metadata.st_dev, metadata.st_ino


def _structured_text(value: object) -> str:
    if not isinstance(value, dict):
        _fail("provider result schema is invalid")
    root = cast(dict[str, object], value)
    if set(root) != _TOP_LEVEL_KEYS:
        _fail("provider result schema is invalid")
    width = _bounded_integer(root["width"], minimum=1, maximum=_MAX_PAGE_DIMENSION)
    height = _bounded_integer(root["height"], minimum=1, maximum=_MAX_PAGE_DIMENSION)
    input_path = root["input_path"]
    if (
        not isinstance(input_path, str)
        or not input_path
        or len(input_path) > 4096
        or "\x00" in input_path
    ):
        _fail("provider result schema is invalid")
    if root["page_index"] is not None or root["page_count"] is not None:
        _fail("provider result schema is invalid")
    if root["model_settings"] != _MODEL_SETTINGS:
        _fail("provider result schema is invalid")
    layout_boxes = _layout_boxes(root["layout_det_res"], width=width, height=height)
    blocks = root["parsing_res_list"]
    if not isinstance(blocks, list):
        _fail("provider result schema is invalid")
    block_values = cast(list[object], blocks)
    if (
        not block_values
        or len(block_values) > _MAX_BLOCKS
        or len(layout_boxes) != len(block_values)
    ):
        _fail("provider result schema is invalid")
    lines: list[str] = []
    for index, raw_block in enumerate(block_values):
        if not isinstance(raw_block, dict):
            _fail("provider result schema is invalid")
        block = cast(dict[str, object], raw_block)
        if set(block) != _BLOCK_KEYS:
            _fail("provider result schema is invalid")
        label = block["block_label"]
        content = block["block_content"]
        if (
            label not in _SUPPORTED_BLOCK_LABELS
            or not isinstance(content, str)
            or len(content.encode("utf-8")) > _MAX_TEXT_BYTES
        ):
            _fail("provider result schema is invalid")
        bbox = _bbox(block["block_bbox"], width=width, height=height)
        polygon = _polygon(block["block_polygon_points"], width=width, height=height)
        block_id = _bounded_integer(block["block_id"], minimum=0, maximum=_MAX_IDENTIFIER)
        block_order = _bounded_integer(
            block["block_order"], minimum=0, maximum=_MAX_IDENTIFIER
        )
        group_id = _bounded_integer(block["group_id"], minimum=0, maximum=_MAX_IDENTIFIER)
        layout = layout_boxes[index] if index < len(layout_boxes) else None
        if layout != (label, bbox, polygon, block_order):
            _fail("provider result schema is invalid")
        if block_id != index or group_id > block_id:
            _fail("provider result schema is invalid")
        normalized = _plain_text(content)
        if not normalized:
            _fail("provider result schema is invalid")
        lines.append(normalized)
    return normalize_ocr_text("\n".join(lines))


def _layout_boxes(
    value: object, *, width: int, height: int
) -> list[tuple[str, tuple[int, int, int, int], tuple[tuple[float, float], ...], int]]:
    if not isinstance(value, dict):
        _fail("provider result schema is invalid")
    root = cast(dict[str, object], value)
    if set(root) != {"input_path", "page_index", "boxes"}:
        _fail("provider result schema is invalid")
    if root["input_path"] is not None or root["page_index"] is not None:
        _fail("provider result schema is invalid")
    boxes = root["boxes"]
    if not isinstance(boxes, list):
        _fail("provider result schema is invalid")
    box_values = cast(list[object], boxes)
    if not box_values or len(box_values) > _MAX_BLOCKS:
        _fail("provider result schema is invalid")
    validated: list[
        tuple[str, tuple[int, int, int, int], tuple[tuple[float, float], ...], int]
    ] = []
    for raw in box_values:
        if not isinstance(raw, dict):
            _fail("provider result schema is invalid")
        box = cast(dict[str, object], raw)
        if set(box) != {
            "cls_id",
            "label",
            "score",
            "coordinate",
            "order",
            "polygon_points",
        }:
            _fail("provider result schema is invalid")
        label = box["label"]
        if label not in _SUPPORTED_BLOCK_LABELS:
            _fail("provider result schema is invalid")
        _bounded_integer(box["cls_id"], minimum=0, maximum=_MAX_IDENTIFIER)
        score = _finite_number(box["score"])
        if score < 0.0 or score > 1.0:
            _fail("provider result schema is invalid")
        validated.append(
            (
                cast(str, label),
                _bbox(box["coordinate"], width=width, height=height),
                _polygon(box["polygon_points"], width=width, height=height),
                _bounded_integer(box["order"], minimum=0, maximum=_MAX_IDENTIFIER),
            )
        )
    return validated


def _bbox(value: object, *, width: int, height: int) -> tuple[int, int, int, int]:
    if not isinstance(value, list):
        _fail("provider result schema is invalid")
    items = cast(list[object], value)
    if len(items) != 4:
        _fail("provider result schema is invalid")
    x1 = _bounded_integer(items[0], minimum=0, maximum=width)
    y1 = _bounded_integer(items[1], minimum=0, maximum=height)
    x2 = _bounded_integer(items[2], minimum=0, maximum=width)
    y2 = _bounded_integer(items[3], minimum=0, maximum=height)
    if x2 <= x1 or y2 <= y1:
        _fail("provider result schema is invalid")
    return x1, y1, x2, y2


def _polygon(
    value: object, *, width: int, height: int
) -> tuple[tuple[float, float], ...]:
    if not isinstance(value, list):
        _fail("provider result schema is invalid")
    point_values = cast(list[object], value)
    if len(point_values) != 4:
        _fail("provider result schema is invalid")
    points: list[tuple[float, float]] = []
    for raw in point_values:
        if not isinstance(raw, list):
            _fail("provider result schema is invalid")
        pair = cast(list[object], raw)
        if len(pair) != 2:
            _fail("provider result schema is invalid")
        x = _finite_number(pair[0])
        y = _finite_number(pair[1])
        if x < 0 or x > width or y < 0 or y > height:
            _fail("provider result schema is invalid")
        points.append((x, y))
    return tuple(points)


def _bounded_integer(value: object, *, minimum: int, maximum: int) -> int:
    if type(value) is not int or value < minimum or value > maximum:
        _fail("provider result schema is invalid")
    return value


def _finite_number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("provider result schema is invalid")
    result = float(value)
    if not math.isfinite(result):
        _fail("provider result schema is invalid")
    return result


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
