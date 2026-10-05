"""Bounded producing-Run observations, independent of visual/semantic completeness."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class PdfObservationRange:
    start: int
    end: int

    def __post_init__(self) -> None:
        if (
            type(self.start) is not int or type(self.end) is not int
            or not 1 <= self.start <= self.end
        ):
            raise ValueError("invalid PDF observation range")


@dataclass(frozen=True)
class PdfPageObservation:
    page_number: int
    text_layer_chars: int
    has_raster_images: bool

    def __post_init__(self) -> None:
        if (
            type(self.page_number) is not int or self.page_number < 1
            or type(self.text_layer_chars) is not int or self.text_layer_chars < 0
            or type(self.has_raster_images) is not bool
        ):
            raise ValueError("invalid PDF page observation")


def omitted_ranges(
    total: int, returned: PdfObservationRange | None,
) -> tuple[PdfObservationRange, ...]:
    if returned is None:
        return (PdfObservationRange(1, total),)
    return tuple(
        PdfObservationRange(start, end)
        for start, end in ((1, returned.start - 1), (returned.end + 1, total))
        if start <= end
    )


@dataclass(frozen=True)
class PdfExtractionObservation:
    status: Literal["observed", "not_observed"] = "not_observed"
    method: Literal["pymupdf-displayed-raster-v1"] | None = None
    extraction_scope: Literal["text_layer_only"] | None = None
    total_pages: int | None = None
    text_only_pages: int | None = None
    mixed_text_raster_pages: int | None = None
    raster_only_pages: int | None = None
    neither_text_nor_raster_pages: int | None = None
    pages: tuple[PdfPageObservation, ...] = ()
    returned_page_range: PdfObservationRange | None = None
    omitted_page_ranges: tuple[PdfObservationRange, ...] = ()
    schema_version: Literal["mke.pdf_extraction_observation.v1"] = (
        "mke.pdf_extraction_observation.v1"
    )

    def __post_init__(self) -> None:
        scalars = (
            self.total_pages, self.text_only_pages, self.mixed_text_raster_pages,
            self.raster_only_pages, self.neither_text_nor_raster_pages,
        )
        if self.schema_version != "mke.pdf_extraction_observation.v1":
            raise ValueError("invalid PDF observation version")
        if self.status == "not_observed":
            if (
                any(value is not None for value in scalars)
                or self.method is not None or self.extraction_scope is not None
                or self.pages or self.returned_page_range is not None or self.omitted_page_ranges
            ):
                raise ValueError("unobserved PDF has no invented signals")
            return
        if (
            self.status != "observed" or self.method != "pymupdf-displayed-raster-v1"
            or self.extraction_scope != "text_layer_only"
            or any(type(value) is not int or value < 0 for value in scalars)
        ):
            raise ValueError("invalid PDF observation counts")
        assert self.total_pages is not None
        counts = tuple(value for value in scalars[1:] if value is not None)
        if self.total_pages < 1 or sum(counts) != self.total_pages:
            raise ValueError("PDF observation categories do not partition pages")
        if type(self.pages) is not tuple or len(self.pages) > 256:
            raise ValueError("PDF observation page bound exceeded")
        if self.pages:
            for page in self.pages:
                if type(page) is not PdfPageObservation:
                    raise ValueError("invalid PDF page observation")
                page.__post_init__()
            returned = PdfObservationRange(self.pages[0].page_number, self.pages[-1].page_number)
            if (
                self.returned_page_range != returned or returned.end > self.total_pages
                or tuple(page.page_number for page in self.pages)
                != tuple(range(returned.start, returned.end + 1))
            ):
                raise ValueError("PDF observation returned range mismatch")
        elif self.returned_page_range is not None:
            raise ValueError("empty PDF observation has no returned range")
        if self.omitted_page_ranges != omitted_ranges(self.total_pages, self.returned_page_range):
            raise ValueError("PDF observation omission mismatch")
        observed = [0, 0, 0, 0]
        for page in self.pages:
            category = int(page.has_raster_images) if page.text_layer_chars else (
                2 if page.has_raster_images else 3
            )
            observed[category] += 1
        if any(part > count for part, count in zip(observed, counts, strict=True)):
            raise ValueError("returned PDF signals exceed category counts")
