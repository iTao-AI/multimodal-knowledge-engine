"""Strict versioned MCP response schemas for Evidence provenance."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, ClassVar, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    GetJsonSchemaHandler,
    RootModel,
    StrictInt,
    StringConstraints,
    TypeAdapter,
    model_validator,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from mke.interfaces.public_errors import is_public_error_cause

StrictId = Annotated[str, StringConstraints(pattern=r"^[a-z]+_[0-9a-f]{32}$")]
Fingerprint = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
PublicText = Annotated[str, StringConstraints(min_length=1, max_length=1_000_000)]
MachineToken = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,127}$")]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class PageLocatorV1(_StrictModel):
    kind: Literal["page"]
    start: int = Field(gt=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_single_page(self) -> PageLocatorV1:
        if self.end != self.start:
            raise ValueError("page locator start and end must match")
        return self


class TimestampLocatorV1(_StrictModel):
    kind: Literal["timestamp_ms"]
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_interval(self) -> TimestampLocatorV1:
        if self.end <= self.start:
            raise ValueError("timestamp locator end must follow start")
        return self


type LocatorV1 = Annotated[PageLocatorV1 | TimestampLocatorV1, Field(discriminator="kind")]


class EvidenceRefV1(_StrictModel):
    schema_version: Literal["mke.evidence_ref.v1"] = "mke.evidence_ref.v1"
    evidence_id: Annotated[StrictId, Field(pattern=r"^ev_[0-9a-f]{32}$")]
    source_id: Annotated[StrictId, Field(pattern=r"^src_[0-9a-f]{32}$")]
    content_fingerprint: Fingerprint
    publication_id: Annotated[StrictId, Field(pattern=r"^pub_[0-9a-f]{32}$")]
    publication_revision: int = Field(gt=0)
    run_id: Annotated[StrictId, Field(pattern=r"^run_[0-9a-f]{32}$")]
    locator: LocatorV1
    text: PublicText


class ActivePublicationObservationV1(_StrictModel):
    schema_version: Literal["mke.active_publication_observation.v1"] = (
        "mke.active_publication_observation.v1"
    )
    library_id: Literal["local"] = "local"
    state: Literal["empty", "no_active_publication", "active"]
    source_count: int = Field(ge=0)
    active_publication_count: int = Field(ge=0)
    active_evidence_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_state_counts(self) -> ActivePublicationObservationV1:
        counts = (
            self.source_count,
            self.active_publication_count,
            self.active_evidence_count,
        )
        valid = (
            self.state == "empty"
            and counts == (0, 0, 0)
            or self.state == "no_active_publication"
            and self.source_count > 0
            and counts[1:] == (0, 0)
            or self.state == "active"
            and all(value > 0 for value in counts)
            and self.active_publication_count <= self.source_count
            and self.active_publication_count <= self.active_evidence_count
        )
        if not valid:
            raise ValueError("observation state does not match counts")
        return self


class _PublicErrorV1(_StrictModel):
    ok: Literal[False]
    problem: MachineToken
    cause: Annotated[str, StringConstraints(min_length=1, max_length=512)]
    active_publication_impact: Literal["unchanged"] = "unchanged"
    next_step: MachineToken

    @model_validator(mode="after")
    def validate_public_cause(self) -> _PublicErrorV1:
        if not is_public_error_cause(self.cause):
            raise ValueError("error cause is not approved for the public boundary")
        return self


class ListLibrariesSuccessV1(_StrictModel):
    schema_version: Literal["mke.list_libraries_response.v1"] = "mke.list_libraries_response.v1"
    ok: Literal[True] = True
    observation: ActivePublicationObservationV1


class ListLibrariesErrorV1(_PublicErrorV1):
    schema_version: Literal["mke.list_libraries_response.v1"] = "mke.list_libraries_response.v1"


class SearchLibrarySuccessV1(_StrictModel):
    schema_version: Literal["mke.search_library_response.v1"] = "mke.search_library_response.v1"
    ok: Literal[True] = True
    query: PublicText
    observation: ActivePublicationObservationV1
    results: list[EvidenceRefV1] = Field(max_length=20)

    @model_validator(mode="after")
    def validate_observation_results(self) -> SearchLibrarySuccessV1:
        if self.observation.state != "active" and self.results:
            raise ValueError("Search results require an active Publication observation")
        if len(self.results) > self.observation.active_evidence_count:
            raise ValueError("Search results exceed observed active Evidence")
        return self


class SearchLibraryErrorV1(_PublicErrorV1):
    schema_version: Literal["mke.search_library_response.v1"] = "mke.search_library_response.v1"


class AskLibrarySuccessV1(_StrictModel):
    schema_version: Literal["mke.ask_library_response.v1"] = "mke.ask_library_response.v1"
    ok: Literal[True] = True
    question: PublicText
    answer_status: Literal["evidence_found", "insufficient_evidence"]
    summary: PublicText
    observation: ActivePublicationObservationV1
    evidence: list[EvidenceRefV1] = Field(max_length=20)
    limitations: list[PublicText]

    @model_validator(mode="after")
    def validate_observation_evidence(self) -> AskLibrarySuccessV1:
        has_evidence = bool(self.evidence)
        if (self.answer_status == "evidence_found") != has_evidence:
            raise ValueError("Ask answer status does not match Evidence")
        if self.observation.state != "active" and has_evidence:
            raise ValueError("Ask Evidence requires an active Publication observation")
        if len(self.evidence) > self.observation.active_evidence_count:
            raise ValueError("Ask Evidence exceeds observed active Evidence")
        return self


class AskLibraryErrorV1(_PublicErrorV1):
    schema_version: Literal["mke.ask_library_response.v1"] = "mke.ask_library_response.v1"


class ListLibrariesResponseV1(
    RootModel[Annotated[ListLibrariesSuccessV1 | ListLibrariesErrorV1, Field(discriminator="ok")]]
):
    pass


class SearchLibraryResponseV1(
    RootModel[Annotated[SearchLibrarySuccessV1 | SearchLibraryErrorV1, Field(discriminator="ok")]]
):
    pass


class AskLibraryResponseV1(
    RootModel[Annotated[AskLibrarySuccessV1 | AskLibraryErrorV1, Field(discriminator="ok")]]
):
    pass


def _max_utf8_bytes(limit: int) -> Callable[[str], str]:
    def validate(value: str) -> str:
        if len(value.encode()) > limit:
            raise ValueError(f"value exceeds {limit} UTF-8 bytes")
        return value

    return validate


def _non_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be blank")
    return value


Utf8BoundedQuery = Annotated[
    str, AfterValidator(_max_utf8_bytes(512)), AfterValidator(_non_blank)
]
Utf8BoundedCursor = Annotated[str, AfterValidator(_max_utf8_bytes(4096))]


class SearchInitialV2(_StrictModel):
    query: Utf8BoundedQuery
    limit: StrictInt = Field(default=5, ge=1, le=20)


class SearchContinuationV2(_StrictModel):
    cursor: Utf8BoundedCursor


type SearchInputV2 = SearchInitialV2 | SearchContinuationV2
SEARCH_INPUT_V2: TypeAdapter[SearchInputV2] = TypeAdapter(SearchInputV2)


class ReadInitialV1(_StrictModel):
    evidence_id: str
    max_bytes: StrictInt = Field(default=16384, ge=4, le=16384)


class ReadContinuationV1(_StrictModel):
    cursor: Utf8BoundedCursor


type ReadInputV1 = ReadInitialV1 | ReadContinuationV1
READ_INPUT_V1: TypeAdapter[ReadInputV1] = TypeAdapter(ReadInputV1)


class _RequestCapture(RootModel[object]):
    model_config = ConfigDict(frozen=True, strict=True)

    branches: ClassVar[tuple[type[BaseModel], ...]] = ()

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        del core_schema, handler
        return {"oneOf": [branch.model_json_schema() for branch in cls.branches]}


class SearchLibraryV2Request(_RequestCapture):
    branches = (SearchInitialV2, SearchContinuationV2)


class ReadEvidenceV1Request(_RequestCapture):
    branches = (ReadInitialV1, ReadContinuationV1)


class ActiveAuthoritySnapshotV1(_StrictModel):
    schema_version: Literal["mke.active_authority_snapshot.v1"] = "mke.active_authority_snapshot.v1"
    observation: ActivePublicationObservationV1
    active_set_fingerprint: Fingerprint


class EvidenceDescriptorV1(_StrictModel):
    evidence_id: str
    source_id: str
    content_fingerprint: Fingerprint
    publication_id: str
    publication_revision: int = Field(gt=0)
    run_id: str
    locator: LocatorV1
    evidence_text_sha256: Fingerprint
    original_utf8_bytes: int = Field(gt=0)


class EvidenceExcerptV1(_StrictModel):
    kind: Literal["query_window", "prefix_fallback"]
    text: str
    start_utf8_byte: int = Field(ge=0)
    end_utf8_byte: int = Field(gt=0)
    prefix_omitted: bool
    suffix_omitted: bool
    complete: bool
    returned_utf8_bytes: int = Field(gt=0, le=2048)
    content_trust: Literal["untrusted_evidence"]


class EvidenceReadAffordanceV1(_StrictModel):
    tool: Literal["read_evidence_v1"] = "read_evidence_v1"
    evidence_id: str


class SearchMatchV2(_StrictModel):
    evidence: EvidenceDescriptorV1
    excerpt: EvidenceExcerptV1
    read: EvidenceReadAffordanceV1


class SearchSelectionCompleteV2(_StrictModel):
    schema_version: Literal["mke.search_selection.v2"] = "mke.search_selection.v2"
    status: Literal["complete"]
    returned: int = Field(ge=0)


class SearchSelectionMoreV2(_StrictModel):
    schema_version: Literal["mke.search_selection.v2"] = "mke.search_selection.v2"
    status: Literal["more_available"]
    returned: int = Field(ge=0)
    next_cursor: Utf8BoundedCursor


class SearchSelectionCappedV2(_StrictModel):
    schema_version: Literal["mke.search_selection.v2"] = "mke.search_selection.v2"
    status: Literal["capped"]
    returned: int = Field(ge=0)
    limit_reason: Literal["retrieval_strategy_cap"]


SearchSelectionV2 = Annotated[
    SearchSelectionCompleteV2 | SearchSelectionMoreV2 | SearchSelectionCappedV2,
    Field(discriminator="status"),
]


class SearchOutputBudgetV1(_StrictModel):
    schema_version: Literal["mke.search_output_budget.v1"] = "mke.search_output_budget.v1"
    incomplete_excerpt_count: int = Field(ge=0)
    content_budget_bytes: Literal[16384] = 16384
    envelope_budget_bytes: Literal[32768] = 32768


class SearchLibrarySuccessV2(_StrictModel):
    schema_version: Literal["mke.search_library_response.v2"] = "mke.search_library_response.v2"
    ok: Literal[True] = True
    authority_snapshot: ActiveAuthoritySnapshotV1
    query: str
    matches: list[SearchMatchV2] = Field(max_length=20)
    selection: SearchSelectionV2
    output: SearchOutputBudgetV1


class SearchLibraryErrorV2(_PublicErrorV1):
    schema_version: Literal["mke.search_library_response.v2"] = "mke.search_library_response.v2"


class SearchLibraryResponseV2(
    RootModel[Annotated[SearchLibrarySuccessV2 | SearchLibraryErrorV2, Field(discriminator="ok")]]
):
    pass


class EvidenceContentV1(_StrictModel):
    text: str
    offset_bytes: int = Field(ge=0)
    returned_utf8_bytes: int = Field(gt=0, le=16384)
    content_trust: Literal["untrusted_evidence"] = "untrusted_evidence"


class ReadEvidenceSuccessV1(_StrictModel):
    schema_version: Literal["mke.read_evidence_response.v1"] = "mke.read_evidence_response.v1"
    ok: Literal[True] = True
    authority_snapshot: ActiveAuthoritySnapshotV1
    evidence: EvidenceDescriptorV1
    content: EvidenceContentV1
    complete: bool
    next_cursor: Utf8BoundedCursor | None = None

    @model_validator(mode="after")
    def validate_terminality(self) -> ReadEvidenceSuccessV1:
        if self.complete == (self.next_cursor is not None):
            raise ValueError("Read terminality does not match cursor")
        return self


class ReadEvidenceErrorV1(_PublicErrorV1):
    schema_version: Literal["mke.read_evidence_response.v1"] = "mke.read_evidence_response.v1"


class ReadEvidenceResponseV1(
    RootModel[Annotated[ReadEvidenceSuccessV1 | ReadEvidenceErrorV1, Field(discriminator="ok")]]
):
    pass
