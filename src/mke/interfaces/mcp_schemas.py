"""Strict versioned MCP response schemas for Evidence provenance."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, StringConstraints, model_validator

StrictId = Annotated[str, StringConstraints(pattern=r"^[a-z]+_[0-9a-f]{32}$")]
Fingerprint = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
PublicText = Annotated[str, StringConstraints(min_length=1, max_length=1_000_000)]


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
        )
        if not valid:
            raise ValueError("observation state does not match counts")
        return self


class _PublicErrorV1(_StrictModel):
    ok: Literal[False]
    problem: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    cause: Annotated[str, StringConstraints(min_length=1, max_length=512)]
    active_publication_impact: Literal["unchanged"] = "unchanged"
    next_step: Annotated[str, StringConstraints(min_length=1, max_length=128)]


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
    results: list[EvidenceRefV1]


class SearchLibraryErrorV1(_PublicErrorV1):
    schema_version: Literal["mke.search_library_response.v1"] = "mke.search_library_response.v1"


class AskLibrarySuccessV1(_StrictModel):
    schema_version: Literal["mke.ask_library_response.v1"] = "mke.ask_library_response.v1"
    ok: Literal[True] = True
    question: PublicText
    answer_status: Literal["evidence_found", "insufficient_evidence"]
    summary: PublicText
    observation: ActivePublicationObservationV1
    evidence: list[EvidenceRefV1]
    limitations: list[PublicText]


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
