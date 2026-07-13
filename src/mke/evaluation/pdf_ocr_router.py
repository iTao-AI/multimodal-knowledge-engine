"""Pure page routing and bounded rendering for PDF OCR Phase 0 evaluation."""

from __future__ import annotations

import hashlib
import math
import os
import re
import unicodedata
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn, cast, overload

import fitz  # pyright: ignore[reportMissingTypeStubs]

from mke.evaluation.pdf_ocr_protocol import PageRoute


@dataclass(frozen=True)
class EvaluationRoutingPolicy:
    accepted_text_min_chars: int = 32
    accepted_text_max_replacement_ratio: float = 0.01
    ocr_text_max_chars: int = 8
    ocr_min_image_coverage: float = 0.80
    render_dpi: int = 200
    max_pages: int = 32
    max_page_pixels: int = 25_000_000
    max_total_rendered_pixels: int = 100_000_000
    max_rendered_file_bytes: int = 32 * 1024 * 1024
    max_total_rendered_bytes: int = 96 * 1024 * 1024

    def __post_init__(self) -> None:
        integer_limits = (
            self.accepted_text_min_chars,
            self.ocr_text_max_chars,
            self.render_dpi,
            self.max_pages,
            self.max_page_pixels,
            self.max_total_rendered_pixels,
            self.max_rendered_file_bytes,
            self.max_total_rendered_bytes,
        )
        if any(type(value) is not int or value <= 0 for value in integer_limits):
            raise ValueError("routing integer limits must be positive")
        ratios = (
            self.accepted_text_max_replacement_ratio,
            self.ocr_min_image_coverage,
        )
        if any(
            not math.isfinite(value)
            or not 0 <= value <= 1
            for value in ratios
        ):
            raise ValueError("routing ratios must be finite values in [0, 1]")


EVALUATION_POLICY = EvaluationRoutingPolicy()


@dataclass(frozen=True)
class PageInspection:
    page_number: int
    normalized_text: str
    text_chars: int
    replacement_ratio: float
    hidden_text_present: bool
    displayed_image_coverage: float
    drawing_count: int
    width_points: float
    height_points: float


@dataclass(frozen=True)
class PageDecision:
    page_number: int
    route: PageRoute
    reasons: tuple[str, ...]
    inspection: PageInspection


@dataclass(frozen=True)
class PdfInspectionResult:
    decisions: tuple[PageDecision, ...]
    source_sha256: str
    source_bytes: int

    def __len__(self) -> int:
        return len(self.decisions)

    def __iter__(self) -> Iterator[PageDecision]:
        return iter(self.decisions)

    @overload
    def __getitem__(self, index: int) -> PageDecision: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[PageDecision, ...]: ...

    def __getitem__(self, index: int | slice) -> PageDecision | tuple[PageDecision, ...]:
        return self.decisions[index]


@dataclass(frozen=True)
class RenderedPage:
    page_number: int
    relative_path: PurePosixPath
    width_pixels: int
    height_pixels: int
    bytes: int
    sha256: str


class PdfOcrRoutingError(RuntimeError):
    def __init__(
        self,
        *,
        problem: str,
        cause: str,
        next_step: str,
    ) -> None:
        super().__init__(f"{problem}: {cause}")
        self.problem = problem
        self.cause = cause
        self.next_step = next_step


def inspect_pdf(
    path: Path,
    policy: EvaluationRoutingPolicy = EVALUATION_POLICY,
) -> PdfInspectionResult:
    document, source_sha256, source_bytes = _open_identified_pdf(path)
    try:
        if document.needs_pass:
            _fail("pdf_ocr_pdf_invalid", "PDF is encrypted", "use_unencrypted_pdf")
        page_count = int(document.page_count)
        if page_count <= 0:
            _fail("pdf_ocr_pdf_invalid", "PDF has no pages", "use_valid_pdf")
        if page_count > policy.max_pages:
            _fail(
                "pdf_ocr_input_limit_exceeded",
                "PDF page count exceeds the evaluation limit",
                "reduce_pdf_ocr_input",
            )
        return PdfInspectionResult(
            decisions=tuple(
                route_page(_inspect_page(document.load_page(index), index + 1), policy)
                for index in range(page_count)
            ),
            source_sha256=source_sha256,
            source_bytes=source_bytes,
        )
    finally:
        document.close()


def route_page(
    inspection: PageInspection,
    policy: EvaluationRoutingPolicy = EVALUATION_POLICY,
) -> PageDecision:
    accepted_text = (
        inspection.text_chars >= policy.accepted_text_min_chars
        and inspection.replacement_ratio <= policy.accepted_text_max_replacement_ratio
    )
    reasons: tuple[str, ...]
    route: PageRoute
    if (
        inspection.text_chars == 0
        and inspection.displayed_image_coverage == 0
        and inspection.drawing_count == 0
    ):
        route = "blank_nontext"
        reasons = ("no_meaningful_content",)
    elif inspection.hidden_text_present:
        route = "ambiguous_unsupported"
        reasons = ("hidden_text_present",)
    elif inspection.replacement_ratio > policy.accepted_text_max_replacement_ratio:
        route = "ambiguous_unsupported"
        reasons = ("replacement_ratio_exceeded",)
    elif inspection.drawing_count > 0 and not accepted_text:
        route = "ambiguous_unsupported"
        reasons = ("vector_content_without_trusted_text",)
    elif accepted_text and inspection.displayed_image_coverage >= policy.ocr_min_image_coverage:
        route = "ambiguous_unsupported"
        reasons = ("conflicting_text_and_raster",)
    elif accepted_text:
        route = "text_layer_accepted"
        reasons = ("visible_text_threshold_met",)
    elif (
        inspection.text_chars <= policy.ocr_text_max_chars
        and inspection.displayed_image_coverage >= policy.ocr_min_image_coverage
        and inspection.drawing_count == 0
    ):
        route = "ocr_required"
        reasons = ("scan_dominant_raster",)
    else:
        route = "ambiguous_unsupported"
        reasons = ("sparse_or_conflicting_content",)
    return PageDecision(
        page_number=inspection.page_number,
        route=route,
        reasons=tuple(sorted(reasons)),
        inspection=inspection,
    )


def displayed_image_union_coverage(
    *,
    page_width: float,
    page_height: float,
    rectangles: tuple[tuple[float, float, float, float], ...],
) -> float:
    if (
        not math.isfinite(page_width)
        or not math.isfinite(page_height)
        or page_width <= 0
        or page_height <= 0
    ):
        _fail("pdf_ocr_geometry_invalid", "PDF page geometry is invalid", "inspect_pdf_page")
    clipped: list[tuple[float, float, float, float]] = []
    for raw in rectangles:
        if len(raw) != 4 or any(not math.isfinite(value) for value in raw):
            _fail(
                "pdf_ocr_geometry_invalid",
                "PDF image geometry is invalid",
                "inspect_pdf_page",
            )
        x0, y0, x1, y1 = raw
        if x1 <= x0 or y1 <= y0:
            _fail(
                "pdf_ocr_geometry_invalid",
                "PDF image geometry is invalid",
                "inspect_pdf_page",
            )
        clipped_rect = (
            max(0.0, x0),
            max(0.0, y0),
            min(page_width, x1),
            min(page_height, y1),
        )
        if clipped_rect[2] > clipped_rect[0] and clipped_rect[3] > clipped_rect[1]:
            clipped.append(clipped_rect)
    if not clipped:
        return 0.0
    x_coordinates = sorted({value for rect in clipped for value in (rect[0], rect[2])})
    area = 0.0
    for left, right in zip(x_coordinates, x_coordinates[1:], strict=False):
        if right <= left:
            continue
        intervals = sorted(
            (rect[1], rect[3]) for rect in clipped if rect[0] < right and rect[2] > left
        )
        if not intervals:
            continue
        covered_y = 0.0
        start, end = intervals[0]
        for next_start, next_end in intervals[1:]:
            if next_start > end:
                covered_y += end - start
                start, end = next_start, next_end
            else:
                end = max(end, next_end)
        covered_y += end - start
        area += (right - left) * covered_y
    return min(1.0, max(0.0, area / (page_width * page_height)))


def render_ocr_pages(
    path: Path,
    inspection: PdfInspectionResult,
    output_root: Path,
    policy: EvaluationRoutingPolicy = EVALUATION_POLICY,
) -> tuple[RenderedPage, ...]:
    decisions = inspection.decisions
    expected_pages = tuple(range(1, len(decisions) + 1))
    if tuple(item.page_number for item in decisions) != expected_pages:
        _fail(
            "pdf_ocr_result_invalid",
            "page decision inventory is invalid",
            "inspect_pdf_page",
        )
    document, source_sha256, source_bytes = _open_identified_pdf(path)
    if (
        source_sha256 != inspection.source_sha256
        or source_bytes != inspection.source_bytes
    ):
        document.close()
        _fail(
            "pdf_ocr_input_invalid",
            "PDF source changed after inspection",
            "retry_with_stable_source",
        )
    try:
        output_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    except OSError as error:
        document.close()
        raise PdfOcrRoutingError(
            problem="pdf_ocr_process_failed",
            cause="render output directory is unavailable",
            next_step="inspect_pdf_ocr_run",
        ) from error
    rendered: list[RenderedPage] = []
    total_pixels = 0
    total_bytes = 0
    try:
        if int(document.page_count) != len(decisions):
            _fail(
                "pdf_ocr_result_invalid",
                "page decision inventory is incomplete",
                "inspect_pdf_page",
            )
        for decision in decisions:
            if decision.route != "ocr_required":
                continue
            width_pixels = math.ceil(decision.inspection.width_points * policy.render_dpi / 72)
            height_pixels = math.ceil(decision.inspection.height_points * policy.render_dpi / 72)
            page_pixels = width_pixels * height_pixels
            if page_pixels > policy.max_page_pixels:
                _fail(
                    "pdf_ocr_input_limit_exceeded",
                    "PDF page pixels exceed the evaluation limit",
                    "reduce_pdf_ocr_input",
                )
            total_pixels += page_pixels
            if total_pixels > policy.max_total_rendered_pixels:
                _fail(
                    "pdf_ocr_input_limit_exceeded",
                    "PDF rendered pixels exceed the evaluation limit",
                    "reduce_pdf_ocr_input",
                )
            page: Any = document.load_page(decision.page_number - 1)
            pixmap: Any = page.get_pixmap(
                dpi=policy.render_dpi,
                colorspace=fitz.csRGB,
                alpha=False,
                annots=False,
            )
            if int(pixmap.width) != width_pixels or int(pixmap.height) != height_pixels:
                _fail(
                    "pdf_ocr_geometry_invalid",
                    "rendered page geometry is invalid",
                    "inspect_pdf_page",
                )
            encoded = bytes(pixmap.tobytes("png"))
            if len(encoded) > policy.max_rendered_file_bytes:
                _fail(
                    "pdf_ocr_output_limit_exceeded",
                    "rendered page bytes exceed the evaluation limit",
                    "reduce_pdf_ocr_input",
                )
            total_bytes += len(encoded)
            if total_bytes > policy.max_total_rendered_bytes:
                _fail(
                    "pdf_ocr_output_limit_exceeded",
                    "rendered PDF bytes exceed the evaluation limit",
                    "reduce_pdf_ocr_input",
                )
            relative = PurePosixPath(f"page-{decision.page_number:04d}.png")
            target = output_root / relative.name
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(encoded)
            except BaseException:
                target.unlink(missing_ok=True)
                raise
            rendered.append(
                RenderedPage(
                    page_number=decision.page_number,
                    relative_path=relative,
                    width_pixels=width_pixels,
                    height_pixels=height_pixels,
                    bytes=len(encoded),
                    sha256=hashlib.sha256(encoded).hexdigest(),
                )
            )
    finally:
        document.close()
    return tuple(rendered)


def _inspect_page(page: Any, page_number: int) -> PageInspection:
    rect = page.rect
    width = float(rect.width)
    height = float(rect.height)
    if not all(math.isfinite(value) and value > 0 for value in (width, height)):
        _fail("pdf_ocr_geometry_invalid", "PDF page geometry is invalid", "inspect_pdf_page")
    raw_text = str(page.get_text("text", sort=True))
    normalized = _normalize_text(raw_text)
    text_chars = len(normalized)
    replacement_ratio = normalized.count("�") / max(1, text_chars)
    traces: list[dict[str, object]] = page.get_texttrace()
    hidden = any(
        bool(span.get("chars"))
        and (span.get("type") == 3 or _nonpositive_opacity(span.get("opacity")))
        for span in traces
    )
    image_rectangles: list[tuple[float, float, float, float]] = []
    image_info: list[dict[str, object]] = page.get_image_info()
    for item in image_info:
        bbox = item.get("bbox")
        if not isinstance(bbox, (tuple, list)):
            _fail(
                "pdf_ocr_geometry_invalid",
                "PDF image geometry is invalid",
                "inspect_pdf_page",
            )
        sequence = cast(Sequence[object], bbox)
        if len(sequence) != 4:
            _fail(
                "pdf_ocr_geometry_invalid",
                "PDF image geometry is invalid",
                "inspect_pdf_page",
            )
        values = _rectangle(sequence)
        image_rectangles.append(values)
    coverage = displayed_image_union_coverage(
        page_width=width,
        page_height=height,
        rectangles=tuple(image_rectangles),
    )
    drawings: list[dict[str, object]] = page.get_drawings()
    return PageInspection(
        page_number=page_number,
        normalized_text=normalized,
        text_chars=text_chars,
        replacement_ratio=replacement_ratio,
        hidden_text_present=hidden,
        displayed_image_coverage=coverage,
        drawing_count=len(drawings),
        width_points=width,
        height_points=height,
    )


def _open_identified_pdf(path: Path) -> tuple[Any, str, int]:
    try:
        if path.is_symlink() or not path.is_file():
            _fail("pdf_ocr_input_invalid", "PDF input is not a regular file", "use_valid_pdf")
        before = path.stat()
        if before.st_size <= 0:
            _fail("pdf_ocr_input_invalid", "PDF input is empty", "use_valid_pdf")
        source = path.read_bytes()
        if len(source) != before.st_size:
            _fail(
                "pdf_ocr_input_invalid",
                "PDF source changed during inspection",
                "retry_with_stable_source",
            )
        document: Any = fitz.open(stream=source, filetype="pdf")
        after = path.stat()
    except PdfOcrRoutingError:
        raise
    except Exception as error:
        raise PdfOcrRoutingError(
            problem="pdf_ocr_pdf_invalid",
            cause="PDF cannot be opened",
            next_step="use_valid_pdf",
        ) from error
    identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if identity_before != identity_after:
        document.close()
        _fail(
            "pdf_ocr_input_invalid",
            "PDF source changed during inspection",
            "retry_with_stable_source",
        )
    return document, hashlib.sha256(source).hexdigest(), len(source)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))
    lines: list[str] = []
    for line in normalized.split("\n"):
        cleaned = re.sub(r"[^\S\n]+", " ", line).strip()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)


def _nonpositive_opacity(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value <= 0


def _rectangle(value: Sequence[object]) -> tuple[float, float, float, float]:
    if len(value) != 4:
        _fail(
            "pdf_ocr_geometry_invalid",
            "PDF image geometry is invalid",
            "inspect_pdf_page",
        )
    numbers: list[float] = []
    for item in value:
        if not isinstance(item, (int, float)) or isinstance(item, bool):
            _fail(
                "pdf_ocr_geometry_invalid",
                "PDF image geometry is invalid",
                "inspect_pdf_page",
            )
        numbers.append(float(item))
    return (numbers[0], numbers[1], numbers[2], numbers[3])


def _fail(problem: str, cause: str, next_step: str) -> NoReturn:
    raise PdfOcrRoutingError(problem=problem, cause=cause, next_step=next_step)
