from __future__ import annotations

import math
import os
import shutil
from pathlib import Path
from typing import Any, cast

import fitz  # pyright: ignore[reportMissingTypeStubs]
import pytest

from mke.evaluation.pdf_ocr_protocol import load_pdf_ocr_evaluation_protocol
from mke.evaluation.pdf_ocr_router import (
    EVALUATION_POLICY,
    EvaluationRoutingPolicy,
    PageInspection,
    PdfOcrRoutingError,
    displayed_image_union_coverage,
    inspect_pdf,
    render_ocr_pages,
    route_page,
)

PROTOCOL_PATH = Path("tests/fixtures/pdf-ocr-phase0-v1/protocol.json")


def _inspection(
    *,
    text: str = "",
    replacement_ratio: float = 0.0,
    hidden: bool = False,
    coverage: float = 0.0,
    drawings: int = 0,
) -> PageInspection:
    return PageInspection(
        page_number=1,
        normalized_text=text,
        text_chars=len(text),
        replacement_ratio=replacement_ratio,
        hidden_text_present=hidden,
        displayed_image_coverage=coverage,
        drawing_count=drawings,
        width_points=612.0,
        height_points=792.0,
    )


def _write_pdf(path: Path, pages: int, *, text: str | None = None) -> None:
    document: Any = fitz.open()
    try:
        for _ in range(pages):
            page: Any = document.new_page(width=612, height=792)
            if text is not None:
                page.insert_text((72, 72), text)
        document.save(path, no_new_id=True)
    finally:
        document.close()


def test_router_matches_closed_protocol() -> None:
    protocol = load_pdf_ocr_evaluation_protocol(PROTOCOL_PATH)

    for document in protocol.documents:
        decisions = inspect_pdf(protocol.resolve(document.fixture), EVALUATION_POLICY)
        assert [item.page_number for item in decisions] == list(
            range(1, len(document.pages) + 1)
        )
        assert [item.route for item in decisions] == [
            item.expected_route for item in document.pages
        ]


def test_hidden_text_never_suppresses_ocr() -> None:
    decision = route_page(
        _inspection(text="hidden", hidden=True, coverage=1.0), EVALUATION_POLICY
    )

    assert decision.route == "ambiguous_unsupported"
    assert "hidden_text_present" in decision.reasons


def test_image_coverage_is_exact_union_clipped_to_page() -> None:
    coverage = displayed_image_union_coverage(
        page_width=100,
        page_height=100,
        rectangles=((0, 0, 60, 100), (40, 0, 110, 100), (-20, 0, 10, 100)),
    )

    assert 0.0 <= coverage <= 1.0
    assert coverage == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("inspection", "route", "reason"),
    [
        (_inspection(), "blank_nontext", "no_meaningful_content"),
        (
            _inspection(text="a" * 32),
            "text_layer_accepted",
            "visible_text_threshold_met",
        ),
        (_inspection(coverage=0.8), "ocr_required", "scan_dominant_raster"),
        (
            _inspection(text="sparse", coverage=0.2),
            "ambiguous_unsupported",
            "sparse_or_conflicting_content",
        ),
        (
            _inspection(text="bad�text", replacement_ratio=0.2),
            "ambiguous_unsupported",
            "replacement_ratio_exceeded",
        ),
        (
            _inspection(drawings=1),
            "ambiguous_unsupported",
            "vector_content_without_trusted_text",
        ),
    ],
)
def test_closed_route_table(
    inspection: PageInspection,
    route: str,
    reason: str,
) -> None:
    decision = route_page(inspection, EVALUATION_POLICY)

    assert decision.route == route
    assert reason in decision.reasons
    assert decision.reasons == tuple(sorted(decision.reasons))


def test_text_normalization_preserves_lines_and_collapses_horizontal_space(
    tmp_path: Path,
) -> None:
    path = tmp_path / "whitespace.pdf"
    _write_pdf(path, 1, text="alpha   beta\nsecond line")

    inspection = inspect_pdf(path, EVALUATION_POLICY)[0].inspection

    assert "alpha beta" in inspection.normalized_text
    assert "second line" in inspection.normalized_text
    assert "\n" in inspection.normalized_text


@pytest.mark.parametrize("rect", [(0, 0, math.nan, 1), (0, 0, 0, 1)])
def test_invalid_image_geometry_is_rejected(rect: tuple[float, float, float, float]) -> None:
    with pytest.raises(PdfOcrRoutingError, match="pdf_ocr_geometry_invalid"):
        displayed_image_union_coverage(
            page_width=100,
            page_height=100,
            rectangles=(rect,),
        )


@pytest.mark.parametrize("payload", [b"", b"not a PDF"])
def test_zero_and_malformed_pdf_fail_closed(tmp_path: Path, payload: bytes) -> None:
    path = tmp_path / "invalid.pdf"
    path.write_bytes(payload)

    with pytest.raises(PdfOcrRoutingError) as error:
        inspect_pdf(path, EVALUATION_POLICY)
    assert error.value.problem in {"pdf_ocr_input_invalid", "pdf_ocr_pdf_invalid"}
    assert str(tmp_path) not in str(error.value)


def test_encrypted_pdf_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "encrypted.pdf"
    document: Any = fitz.open()
    try:
        document.new_page().insert_text((72, 72), "encrypted")
        document.save(
            path,
            encryption=cast(
                int,
                fitz.PDF_ENCRYPT_AES_256,  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
            ),
            owner_pw="owner",
            user_pw="user",
        )
    finally:
        document.close()

    with pytest.raises(PdfOcrRoutingError) as error:
        inspect_pdf(path, EVALUATION_POLICY)
    assert error.value.cause == "PDF is encrypted"


def test_page_limit_is_checked_before_inspection(tmp_path: Path) -> None:
    path = tmp_path / "pages.pdf"
    _write_pdf(path, 2)
    policy = EvaluationRoutingPolicy(max_pages=1)

    with pytest.raises(PdfOcrRoutingError) as error:
        inspect_pdf(path, policy)
    assert error.value.problem == "pdf_ocr_input_limit_exceeded"


def test_source_replacement_between_identity_check_and_open_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "source.pdf"
    replacement = tmp_path / "replacement.pdf"
    _write_pdf(path, 1, text="first source text remains trustworthy")
    _write_pdf(replacement, 1, text="replacement source differs")
    original_open = fitz.open

    def replacing_open(*args: Any, **kwargs: Any) -> Any:
        shutil.copyfile(replacement, path)
        return original_open(*args, **kwargs)

    monkeypatch.setattr(fitz, "open", replacing_open)
    with pytest.raises(PdfOcrRoutingError) as error:
        inspect_pdf(path, EVALUATION_POLICY)
    assert error.value.cause == "PDF source changed during inspection"


def test_render_writes_only_ocr_pages_with_private_deterministic_names(
    tmp_path: Path,
) -> None:
    protocol = load_pdf_ocr_evaluation_protocol(PROTOCOL_PATH)
    mixed = next(item for item in protocol.documents if item.document_id == "mixed-prose")
    path = protocol.resolve(mixed.fixture)
    decisions = inspect_pdf(path, EVALUATION_POLICY)

    rendered = render_ocr_pages(path, decisions, tmp_path / "rendered", EVALUATION_POLICY)

    assert [str(item.relative_path) for item in rendered] == ["page-0002.png"]
    output = tmp_path / "rendered" / rendered[0].relative_path
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert os.stat(output).st_mode & 0o777 == 0o600
    assert rendered[0].bytes == output.stat().st_size
    assert len(rendered[0].sha256) == 64


def test_render_rejects_source_replaced_after_inspection_without_writing(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.pdf"
    original = Path("tests/fixtures/pdf-ocr-phase0-v1/documents/english-scan.pdf")
    replacement = Path("tests/fixtures/pdf-ocr-phase0-v1/documents/chinese-scan.pdf")
    shutil.copyfile(original, source)
    decisions = inspect_pdf(source, EVALUATION_POLICY)
    shutil.copyfile(replacement, source)
    output_root = tmp_path / "rendered"

    with pytest.raises(PdfOcrRoutingError) as error:
        render_ocr_pages(source, decisions, output_root, EVALUATION_POLICY)

    assert error.value.problem == "pdf_ocr_input_invalid"
    assert error.value.cause == "PDF source changed after inspection"
    assert not output_root.exists()


def test_render_rejects_pixel_and_encoded_byte_limits(tmp_path: Path) -> None:
    protocol = load_pdf_ocr_evaluation_protocol(PROTOCOL_PATH)
    document = protocol.documents[0]
    path = protocol.resolve(document.fixture)
    decisions = inspect_pdf(path, EVALUATION_POLICY)

    with pytest.raises(PdfOcrRoutingError) as pixels:
        render_ocr_pages(
            path,
            decisions,
            tmp_path / "pixels",
            EvaluationRoutingPolicy(max_page_pixels=1),
        )
    assert pixels.value.problem == "pdf_ocr_input_limit_exceeded"

    with pytest.raises(PdfOcrRoutingError) as encoded:
        render_ocr_pages(
            path,
            decisions,
            tmp_path / "bytes",
            EvaluationRoutingPolicy(max_rendered_file_bytes=1),
        )
    assert encoded.value.problem == "pdf_ocr_output_limit_exceeded"
