"""Additive CLI-only contract for bounded single-Source Evidence selection."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, RootModel, StrictInt, model_validator

from mke.application.evidence_access import MAX_CANONICAL_MODEL_BYTES, canonical_json_bytes
from mke.interfaces.mcp_schemas import (
    ActiveAuthoritySnapshotV1,
    SearchMatchV2,
    SearchOutputBudgetV1,
    Utf8BoundedQuery,
    _PublicErrorV1,  # pyright: ignore[reportPrivateUsage]
    _StrictModel,  # pyright: ignore[reportPrivateUsage]
)
from mke.interfaces.public_errors import MIXED_CJK_OPERATION_SAFE_CAUSES
from mke.interfaces.source_search_schemas import SourceSearchScopeV1

ASK_LIMITATIONS = (
    "Evidence selection only; matches do not verify an answer or complete understanding "
    "of original media."
)


class SourceAskSelectionV1(_StrictModel):
    mode: Literal["bounded_first_page"] = "bounded_first_page"
    status: Literal["complete", "more_available"]
    returned: StrictInt = Field(ge=0, le=20)
    next_step: Literal[
        "read_selected_evidence",
        "run_scoped_search_for_all_matches",
        "refine_question_in_selected_source",
    ]

    @model_validator(mode="after")
    def coherent_next_step(self) -> Self:
        expected = (
            "run_scoped_search_for_all_matches"
            if self.status == "more_available"
            else "read_selected_evidence"
            if self.returned
            else "refine_question_in_selected_source"
        )
        if self.next_step != expected or (self.status == "more_available" and not self.returned):
            raise ValueError("selection recovery or progress is inconsistent")
        return self


class SourceAskSuccessV1(_StrictModel):
    schema_version: Literal["mke.source_ask_response.v1"] = "mke.source_ask_response.v1"
    ok: Literal[True] = True
    question: Utf8BoundedQuery
    answer_status: Literal["evidence_found", "insufficient_evidence"]
    scope: SourceSearchScopeV1
    authority_snapshot: ActiveAuthoritySnapshotV1
    evidence: list[SearchMatchV2] = Field(max_length=20)
    selection: SourceAskSelectionV1
    output: SearchOutputBudgetV1
    limitations: Literal[
        "Evidence selection only; matches do not verify an answer or complete understanding "
        "of original media."
    ] = ASK_LIMITATIONS

    @model_validator(mode="after")
    def coherent_packet(self) -> Self:
        if self.selection.returned != len(self.evidence):
            raise ValueError("selection count differs from Evidence")
        if (self.answer_status == "evidence_found") != bool(self.evidence):
            raise ValueError("answer status differs from Evidence selection")
        for match in self.evidence:
            citation = match.evidence
            if (
                citation.source_id != self.scope.source_id
                or citation.publication_id != self.scope.publication_id
                or citation.publication_revision != self.scope.publication_revision
                or citation.run_id != self.scope.run_id
                or citation.content_fingerprint != self.scope.content_fingerprint
                or match.read.evidence_id != citation.evidence_id
            ):
                raise ValueError("Evidence citation differs from selected Source scope")
            if len(match.excerpt.text.encode("utf-8")) != match.excerpt.returned_utf8_bytes:
                raise ValueError("excerpt byte count differs from text")
        if sum(item.excerpt.returned_utf8_bytes for item in self.evidence) > 16384:
            raise ValueError("combined excerpt budget exceeded")
        if self.output.incomplete_excerpt_count != sum(
            not item.excerpt.complete for item in self.evidence
        ):
            raise ValueError("incomplete excerpt count differs from Evidence")
        if len(canonical_json_bytes(self.model_dump(mode="json"))) > MAX_CANONICAL_MODEL_BYTES:
            raise ValueError("complete response envelope exceeds the byte budget")
        return self


class SourceAskErrorV1(_PublicErrorV1):
    schema_version: Literal["mke.source_ask_response.v1"] = "mke.source_ask_response.v1"

    def _allows_operation_cause(self, cause: str) -> bool:
        return cause in MIXED_CJK_OPERATION_SAFE_CAUSES


class SourceAskResponseV1(
    RootModel[Annotated[SourceAskSuccessV1 | SourceAskErrorV1, Field(discriminator="ok")]]
):
    pass
