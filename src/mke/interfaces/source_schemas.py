"""Closed additive catalog and browse contracts; old response schemas stay unchanged."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import (
    Field,
    GetJsonSchemaHandler,
    RootModel,
    StrictInt,
    TypeAdapter,
    model_validator,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from mke.domain.pdf_observation import (
    PdfExtractionObservation,
    PdfObservationRange,
    PdfPageObservation,
)
from mke.interfaces.mcp_schemas import (
    ActiveAuthoritySnapshotV1,
    Fingerprint,
    SearchMatchV2,
    SearchOutputBudgetV1,
    Utf8BoundedCursor,
    _PublicErrorV1,  # pyright: ignore[reportPrivateUsage]
    _RequestCapture,  # pyright: ignore[reportPrivateUsage]
    _StrictModel,  # pyright: ignore[reportPrivateUsage]
)


class SourcePageRangeV1(_StrictModel):
    kind: Literal["page"]
    start: int = Field(gt=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.end < self.start:
            raise ValueError("page end precedes start")
        return self


class SourceTimestampRangeV1(_StrictModel):
    kind: Literal["timestamp_ms"]
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.end <= self.start:
            raise ValueError("timestamp end must follow start")
        return self


type SourceLocatorRangeV1 = Annotated[
    SourcePageRangeV1 | SourceTimestampRangeV1, Field(discriminator="kind")
]


class ListSourcesInitialV1(_StrictModel):
    page_size: StrictInt = Field(default=10, ge=1, le=20)


class SourceContinuationV1(_StrictModel):
    cursor: Utf8BoundedCursor = Field(min_length=1)


class BrowseSourceInitialV1(ListSourcesInitialV1):
    source_id: str = Field(min_length=1)
    publication_id: str = Field(min_length=1)
    locator_range: SourceLocatorRangeV1 | None = None


type ListSourcesInputV1 = ListSourcesInitialV1 | SourceContinuationV1
type BrowseSourceInputV1 = BrowseSourceInitialV1 | SourceContinuationV1
LIST_SOURCES_INPUT_V1: TypeAdapter[ListSourcesInputV1] = TypeAdapter(ListSourcesInputV1)
BROWSE_SOURCE_INPUT_V1: TypeAdapter[BrowseSourceInputV1] = TypeAdapter(BrowseSourceInputV1)


class ListSourcesV1Request(_RequestCapture):
    branches = (ListSourcesInitialV1, SourceContinuationV1)

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        del core_schema
        result = handler(LIST_SOURCES_INPUT_V1.core_schema)
        result["oneOf"] = result.pop("anyOf")
        return result


class BrowseSourceEvidenceV1Request(_RequestCapture):
    branches = (BrowseSourceInitialV1, SourceContinuationV1)

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        del core_schema
        result = handler(BROWSE_SOURCE_INPUT_V1.core_schema)
        result["oneOf"] = result.pop("anyOf")
        return result


class PdfSourceCoverageV1(_StrictModel):
    kind: Literal["pdf"] = "pdf"
    report_status: Literal["observed", "not_observed"]
    extraction_mode: str | None
    total_pages: int | None = Field(ge=1)
    extracted_pages: int | None = Field(ge=0)
    empty_pages: int | None = Field(ge=0)
    suspected_scanned_pages: int | None = Field(ge=0)
    total_extracted_chars: int | None = Field(ge=0)
    page_char_counts: list[Annotated[int, Field(ge=0)]] = Field(max_length=256)
    page_char_counts_total: int | None = Field(ge=0)
    page_char_counts_omitted: bool

    @model_validator(mode="after")
    def report_presence(self) -> Self:
        scalars = (
            self.extraction_mode,
            self.total_pages,
            self.extracted_pages,
            self.empty_pages,
            self.suspected_scanned_pages,
            self.total_extracted_chars,
            self.page_char_counts_total,
        )
        if self.report_status == "not_observed":
            if (
                any(value is not None for value in scalars)
                or self.page_char_counts
                or self.page_char_counts_omitted
            ):
                raise ValueError("missing report cannot carry observed coverage")
        elif any(value is None for value in scalars):
            raise ValueError("observed PDF coverage requires scalar counts")
        elif self.page_char_counts_total is not None:
            if self.page_char_counts_total < len(
                self.page_char_counts
            ) or self.page_char_counts_omitted != (
                len(self.page_char_counts) < self.page_char_counts_total
            ):
                raise ValueError("PDF array omission does not match counts")
        return self


class TranscriptReportV1(_StrictModel):
    provider: str = Field(min_length=1, max_length=256)
    model: str = Field(min_length=1, max_length=256)
    model_revision: str = Field(min_length=1, max_length=256)
    library_version: str = Field(min_length=1, max_length=256)
    device: str = Field(min_length=1, max_length=256)
    compute_type: str = Field(min_length=1, max_length=256)
    language: str = Field(min_length=2, max_length=4)
    detected_language: str = Field(min_length=2, max_length=4)
    media_duration_ms: int = Field(gt=0)
    transcription_duration_ms: int = Field(ge=0)
    segment_count: int = Field(gt=0)
    model_source: Literal["cache"]


class TranscriptSourceCoverageV1(_StrictModel):
    kind: Literal["transcript"] = "transcript"
    report_status: Literal["observed", "not_observed"]
    evidence_kind: Literal["stored_transcript"] = "stored_transcript"
    provenance: TranscriptReportV1 | None

    @model_validator(mode="after")
    def report_presence(self) -> Self:
        if (self.report_status == "observed") != (self.provenance is not None):
            raise ValueError("transcript report presence mismatch")
        return self


type SourceCoverageV1 = Annotated[
    PdfSourceCoverageV1 | TranscriptSourceCoverageV1, Field(discriminator="kind")
]


class SourceMetadataV1(_StrictModel):
    source_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    content_fingerprint: Fingerprint
    publication_id: str = Field(min_length=1)
    publication_revision: int = Field(gt=0)
    run_id: str = Field(min_length=1)
    extractor_fingerprint: str = Field(min_length=1)
    required_stages: list[str] = Field(min_length=1)
    evidence_count: int = Field(gt=0)
    coverage: SourceCoverageV1


class SourceSelectionCompleteV1(_StrictModel):
    status: Literal["complete"]
    returned: int = Field(ge=0)


class SourceSelectionMoreV1(_StrictModel):
    status: Literal["more_available"]
    returned: int = Field(gt=0)
    next_cursor: Utf8BoundedCursor = Field(min_length=1)


type SourceSelectionV1 = Annotated[
    SourceSelectionCompleteV1 | SourceSelectionMoreV1, Field(discriminator="status")
]
SOURCE_SELECTION_V1: TypeAdapter[SourceSelectionV1] = TypeAdapter(SourceSelectionV1)


class ListSourcesSuccessV1(_StrictModel):
    schema_version: Literal["mke.list_sources_response.v1"] = "mke.list_sources_response.v1"
    ok: Literal[True] = True
    authority_snapshot: ActiveAuthoritySnapshotV1
    sources: list[SourceMetadataV1] = Field(max_length=20)
    selection: SourceSelectionV1

    @model_validator(mode="after")
    def returned_count(self) -> Self:
        if self.selection.returned != len(self.sources):
            raise ValueError("selection count mismatch")
        return self


class BrowseSourceEvidenceSuccessV1(_StrictModel):
    schema_version: Literal["mke.browse_source_evidence_response.v1"] = (
        "mke.browse_source_evidence_response.v1"
    )
    ok: Literal[True] = True
    authority_snapshot: ActiveAuthoritySnapshotV1
    source: SourceMetadataV1
    entries: list[SearchMatchV2] = Field(max_length=20)
    selection: SourceSelectionV1
    output: SearchOutputBudgetV1

    @model_validator(mode="after")
    def returned_count(self) -> Self:
        if self.selection.returned != len(self.entries):
            raise ValueError("selection count mismatch")
        for entry in self.entries:
            evidence = entry.evidence
            if (
                evidence.source_id != self.source.source_id
                or evidence.publication_id != self.source.publication_id
                or evidence.publication_revision != self.source.publication_revision
                or evidence.run_id != self.source.run_id
                or evidence.content_fingerprint != self.source.content_fingerprint
                or entry.read.evidence_id != evidence.evidence_id
            ):
                raise ValueError("browse entry provenance differs from selected Source")
        if self.output.incomplete_excerpt_count != sum(
            not entry.excerpt.complete for entry in self.entries
        ):
            raise ValueError("incomplete preview count mismatch")
        return self


class ListSourcesErrorV1(_PublicErrorV1):
    schema_version: Literal["mke.list_sources_response.v1"] = "mke.list_sources_response.v1"


class BrowseSourceEvidenceErrorV1(_PublicErrorV1):
    schema_version: Literal["mke.browse_source_evidence_response.v1"] = (
        "mke.browse_source_evidence_response.v1"
    )


class ListSourcesResponseV1(
    RootModel[Annotated[ListSourcesSuccessV1 | ListSourcesErrorV1, Field(discriminator="ok")]]
):
    pass


class BrowseSourceEvidenceResponseV1(
    RootModel[
        Annotated[
            BrowseSourceEvidenceSuccessV1 | BrowseSourceEvidenceErrorV1, Field(discriminator="ok")
        ]
    ]
):
    pass


class PdfObservationRangeV1(_StrictModel):
    start: int = Field(ge=1)
    end: int = Field(ge=1)


class PdfPageObservationV1(_StrictModel):
    page_number: int = Field(ge=1)
    text_layer_chars: int = Field(ge=0)
    has_raster_images: bool


class PdfExtractionObservationV1(_StrictModel):
    schema_version: Literal["mke.pdf_extraction_observation.v1"] = (
        "mke.pdf_extraction_observation.v1"
    )
    status: Literal["observed", "not_observed"]
    method: Literal["pymupdf-displayed-raster-v1"] | None
    extraction_scope: Literal["text_layer_only"] | None
    total_pages: int | None = Field(ge=1)
    text_only_pages: int | None = Field(ge=0)
    mixed_text_raster_pages: int | None = Field(ge=0)
    raster_only_pages: int | None = Field(ge=0)
    neither_text_nor_raster_pages: int | None = Field(ge=0)
    pages: list[PdfPageObservationV1] = Field(max_length=256)
    returned_page_range: PdfObservationRangeV1 | None
    omitted_page_ranges: list[PdfObservationRangeV1] = Field(max_length=2)

    @model_validator(mode="after")
    def validate_signals(self) -> Self:
        PdfExtractionObservation(
            status=self.status, method=self.method, extraction_scope=self.extraction_scope,
            total_pages=self.total_pages, text_only_pages=self.text_only_pages,
            mixed_text_raster_pages=self.mixed_text_raster_pages,
            raster_only_pages=self.raster_only_pages,
            neither_text_nor_raster_pages=self.neither_text_nor_raster_pages,
            pages=tuple(PdfPageObservation(**page.model_dump()) for page in self.pages),
            returned_page_range=(
                None if self.returned_page_range is None
                else PdfObservationRange(**self.returned_page_range.model_dump())
            ),
            omitted_page_ranges=tuple(
                PdfObservationRange(**value.model_dump()) for value in self.omitted_page_ranges
            ),
        )
        return self


class SourceMetadataV2(_StrictModel):
    source_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    content_fingerprint: Fingerprint
    publication_id: str = Field(min_length=1)
    publication_revision: int = Field(gt=0)
    run_id: str = Field(min_length=1)
    extractor_fingerprint: str = Field(min_length=1)
    required_stages: list[str] = Field(min_length=1)
    evidence_count: int = Field(gt=0)
    coverage: SourceCoverageV1
    pdf_extraction_observation: PdfExtractionObservationV1 | None

    @model_validator(mode="after")
    def observation_matches_source(self) -> Self:
        observation = self.pdf_extraction_observation
        if self.media_type != "application/pdf":
            if observation is not None:
                raise ValueError("non-PDF Source has no PDF observation")
            return self
        if observation is None or not isinstance(self.coverage, PdfSourceCoverageV1):
            raise ValueError("PDF Source requires an explicit observation status")
        if observation.status == "observed":
            assert observation.text_only_pages is not None
            assert observation.mixed_text_raster_pages is not None
            if (
                self.coverage.report_status != "observed"
                or self.coverage.extraction_mode != "pymupdf-text"
                or self.coverage.total_pages != observation.total_pages
                or self.coverage.extracted_pages
                != observation.text_only_pages + observation.mixed_text_raster_pages
            ):
                raise ValueError("PDF observation differs from producing report")
        return self


class ListSourcesSuccessV2(_StrictModel):
    schema_version: Literal["mke.list_sources_response.v2"] = "mke.list_sources_response.v2"
    ok: Literal[True] = True
    authority_snapshot: ActiveAuthoritySnapshotV1
    sources: list[SourceMetadataV2] = Field(max_length=20)
    selection: SourceSelectionV1

    @model_validator(mode="after")
    def returned_count(self) -> Self:
        if self.selection.returned != len(self.sources):
            raise ValueError("selection count mismatch")
        return self


class BrowseSourceEvidenceSuccessV2(_StrictModel):
    schema_version: Literal["mke.browse_source_evidence_response.v2"] = (
        "mke.browse_source_evidence_response.v2"
    )
    ok: Literal[True] = True
    authority_snapshot: ActiveAuthoritySnapshotV1
    source: SourceMetadataV2
    entries: list[SearchMatchV2] = Field(max_length=20)
    selection: SourceSelectionV1
    output: SearchOutputBudgetV1

    @model_validator(mode="after")
    def returned_count(self) -> Self:
        if self.selection.returned != len(self.entries):
            raise ValueError("selection count mismatch")
        for entry in self.entries:
            evidence = entry.evidence
            if (
                evidence.source_id != self.source.source_id
                or evidence.publication_id != self.source.publication_id
                or evidence.publication_revision != self.source.publication_revision
                or evidence.run_id != self.source.run_id
                or evidence.content_fingerprint != self.source.content_fingerprint
                or entry.read.evidence_id != evidence.evidence_id
            ):
                raise ValueError("browse entry provenance differs from selected Source")
        if self.output.incomplete_excerpt_count != sum(
            not entry.excerpt.complete for entry in self.entries
        ):
            raise ValueError("incomplete preview count mismatch")
        return self


class ListSourcesErrorV2(_PublicErrorV1):
    schema_version: Literal["mke.list_sources_response.v2"] = "mke.list_sources_response.v2"


class BrowseSourceEvidenceErrorV2(_PublicErrorV1):
    schema_version: Literal["mke.browse_source_evidence_response.v2"] = (
        "mke.browse_source_evidence_response.v2"
    )


class ListSourcesResponseV2(
    RootModel[Annotated[ListSourcesSuccessV2 | ListSourcesErrorV2, Field(discriminator="ok")]]
):
    pass


class BrowseSourceEvidenceResponseV2(
    RootModel[
        Annotated[
            BrowseSourceEvidenceSuccessV2 | BrowseSourceEvidenceErrorV2, Field(discriminator="ok")
        ]
    ]
):
    pass
