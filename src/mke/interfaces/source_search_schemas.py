"""Strict additive public contract for one selected active Source Search."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import AfterValidator, Field, RootModel, StrictInt, TypeAdapter, model_validator

from mke.interfaces.mcp_schemas import (
    ActiveAuthoritySnapshotV1,
    Fingerprint,
    SearchMatchV2,
    SearchOutputBudgetV1,
    SearchSelectionCompleteV2,
    SearchSelectionMoreV2,
    Utf8BoundedCursor,
    Utf8BoundedQuery,
    _PublicErrorV1,  # pyright: ignore[reportPrivateUsage]
    _RequestCapture,  # pyright: ignore[reportPrivateUsage]
    _StrictModel,  # pyright: ignore[reportPrivateUsage]
)
from mke.interfaces.public_errors import MIXED_CJK_OPERATION_SAFE_CAUSES


def _identity(value: str) -> str:
    if not value.strip() or len(value.encode()) > 512:
        raise ValueError("identity must be nonblank and within 512 UTF-8 bytes")
    return value


BoundedIdentity = Annotated[str, AfterValidator(_identity)]


class SourceSearchInitialV1(_StrictModel):
    source_id: BoundedIdentity
    publication_id: BoundedIdentity
    query: Utf8BoundedQuery
    limit: StrictInt = Field(default=5, ge=1, le=20)


class SourceSearchContinuationV1(_StrictModel):
    cursor: Utf8BoundedCursor = Field(min_length=1)


type SourceSearchInputV1 = SourceSearchInitialV1 | SourceSearchContinuationV1
SOURCE_SEARCH_INPUT_V1: TypeAdapter[SourceSearchInputV1] = TypeAdapter(SourceSearchInputV1)


class SearchSourceEvidenceV1Request(_RequestCapture):
    branches = (SourceSearchInitialV1, SourceSearchContinuationV1)


class SourceSearchScopeV1(_StrictModel):
    schema_version: Literal["mke.source_search_scope.v1"] = "mke.source_search_scope.v1"
    source_id: BoundedIdentity
    publication_id: BoundedIdentity
    publication_revision: StrictInt = Field(gt=0)
    run_id: BoundedIdentity
    content_fingerprint: Fingerprint


class SearchSourceEvidenceSuccessV1(_StrictModel):
    schema_version: Literal["mke.search_source_evidence_response.v1"] = (
        "mke.search_source_evidence_response.v1"
    )
    ok: Literal[True] = True
    scope: SourceSearchScopeV1
    authority_snapshot: ActiveAuthoritySnapshotV1
    query: str
    matches: list[SearchMatchV2] = Field(max_length=20)
    selection: Annotated[
        SearchSelectionCompleteV2 | SearchSelectionMoreV2,
        Field(discriminator="status"),
    ]
    output: SearchOutputBudgetV1

    @model_validator(mode="after")
    def coherent_scope(self) -> Self:
        if self.selection.returned != len(self.matches):
            raise ValueError("selection count differs from matches")
        if isinstance(self.selection, SearchSelectionMoreV2) and not self.matches:
            raise ValueError("continuation must make positive progress")
        for match in self.matches:
            evidence = match.evidence
            if (
                evidence.source_id != self.scope.source_id
                or evidence.publication_id != self.scope.publication_id
                or evidence.publication_revision != self.scope.publication_revision
                or evidence.run_id != self.scope.run_id
                or evidence.content_fingerprint != self.scope.content_fingerprint
                or match.read.evidence_id != evidence.evidence_id
            ):
                raise ValueError("Evidence citation differs from selected Source scope")
        return self


class SearchSourceEvidenceErrorV1(_PublicErrorV1):
    schema_version: Literal["mke.search_source_evidence_response.v1"] = (
        "mke.search_source_evidence_response.v1"
    )

    def _allows_operation_cause(self, cause: str) -> bool:
        return cause in MIXED_CJK_OPERATION_SAFE_CAUSES


class SearchSourceEvidenceResponseV1(
    RootModel[
        Annotated[
            SearchSourceEvidenceSuccessV1 | SearchSourceEvidenceErrorV1,
            Field(discriminator="ok"),
        ]
    ]
):
    pass
