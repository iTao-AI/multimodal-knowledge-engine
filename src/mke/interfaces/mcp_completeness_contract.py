from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from typing import Any, cast

from pydantic import ValidationError

from mke.adapters.sqlite import EvidenceNotFoundError, EvidenceResponseTooLargeError
from mke.application.evidence_access import (
    ResponseTooLargeError,
    assemble_read_chunk,
    assemble_search_page,
)
from mke.application.mcp_cursor import (
    CursorExpiredError,
    InvalidCursorError,
    ParsedCursor,
    ReadCursorPayload,
    SearchCursorPayload,
    encode_read_cursor,
    encode_search_cursor,
    parse_cursor_untrusted,
    untrusted_read_route,
    untrusted_search_route,
    validate_read_cursor,
    validate_search_cursor,
)
from mke.domain.evidence_access import ActiveAuthoritySnapshot
from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.interfaces.mcp_schemas import (
    READ_INPUT_V1,
    SEARCH_INPUT_V2,
    ActiveAuthoritySnapshotV1,
    ActivePublicationObservationV1,
    EvidenceContentV1,
    EvidenceDescriptorV1,
    EvidenceExcerptV1,
    EvidenceReadAffordanceV1,
    PageLocatorV1,
    ReadContinuationV1,
    ReadEvidenceErrorV1,
    ReadEvidenceResponseV1,
    ReadEvidenceSuccessV1,
    ReadEvidenceV1Request,
    SearchContinuationV2,
    SearchLibraryErrorV2,
    SearchLibraryResponseV2,
    SearchLibrarySuccessV2,
    SearchLibraryV2Request,
    SearchMatchV2,
    SearchOutputBudgetV1,
    SearchSelectionCappedV2,
    SearchSelectionCompleteV2,
    SearchSelectionMoreV2,
    TimestampLocatorV1,
)
from mke.retrieval.errors import RetrievalAuthorityError
from mke.retrieval.query_policy import QUERY_POLICY_REVISION
from mke.retrieval.strategy import get_retrieval_strategy_descriptor
from mke.runtime import build_engine


def search_library_v2(
    config: McpRuntimeConfig, request: SearchLibraryV2Request
) -> SearchLibraryResponseV2:
    raw = request.root
    try:
        branch = SEARCH_INPUT_V2.validate_python(raw)
    except ValidationError:
        return _search_error(*_classify_request(raw, search=True))
    material = config.runtime.owner_state.cursor_material()
    parsed_cursor: ParsedCursor | None = None
    parsed: SearchCursorPayload | None = None
    if isinstance(branch, SearchContinuationV2):
        try:
            parsed_cursor = parse_cursor_untrusted(branch.cursor)
        except InvalidCursorError as error:
            return _search_cursor_error(error)
        query, limit, position = untrusted_search_route(parsed_cursor)
    else:
        query, limit, position = branch.query.strip(), branch.limit, 0
    engine = build_engine(config.runtime)
    try:
        descriptor = get_retrieval_strategy_descriptor(
            cast(str, config.runtime.retrieval_strategy)
        )

        def validate(authority: ActiveAuthoritySnapshot) -> None:
            nonlocal parsed
            if parsed_cursor is not None:
                parsed = validate_search_cursor(
                    parsed_cursor,
                    material,
                    authority,
                    strategy_id=descriptor.strategy_id,
                    strategy_revision=descriptor.revision,
                    query_policy=descriptor.base_query_policy,
                    query_policy_revision=QUERY_POLICY_REVISION,
                )

        snapshot = engine.search_evidence_page(
            query,
            position=position,
            page_size=limit,
            authority_validator=validate,
        )

        def cursor_factory(next_position: int) -> str:
            return encode_search_cursor(
                material,
                SearchCursorPayload(
                    "mke.mcp_cursor.v1",
                    "search_library_v2",
                    material.epoch,
                    snapshot.authority.active_set_fingerprint,
                    snapshot.normalized_query,
                    f"sha256:{sha256(snapshot.normalized_query.encode()).hexdigest()}",
                    snapshot.strategy_id,
                    snapshot.strategy_revision,
                    snapshot.query_policy,
                    snapshot.query_policy_revision,
                    next_position,
                    limit,
                    "mke.search_library_response.v2",
                ),
            )

        return _search_success(
            assemble_search_page(snapshot, page_size=limit, cursor_factory=cursor_factory)
        )
    except (InvalidCursorError, CursorExpiredError) as error:
        return _search_cursor_error(error)
    except ResponseTooLargeError:
        return _search_error(
            "response_too_large",
            "mandatory response metadata exceeds the response limit",
            "reduce_query_scope_or_report_contract_limit",
        )
    except RetrievalAuthorityError as error:
        return _search_error(error.problem, error.cause, error.next_step)
    except Exception:
        return _search_error(
            "internal_error",
            "operation failed; details were redacted",
            "check_server_logs",
        )
    finally:
        engine.close()


def read_evidence_v1(
    config: McpRuntimeConfig, request: ReadEvidenceV1Request
) -> ReadEvidenceResponseV1:
    raw = request.root
    try:
        branch = READ_INPUT_V1.validate_python(raw)
    except ValidationError:
        problem, cause, next_step = _classify_request(raw, search=False)
        return _read_error(problem, cause, next_step)
    material = config.runtime.owner_state.cursor_material()
    parsed_cursor: ParsedCursor | None = None
    parsed: ReadCursorPayload | None = None
    if isinstance(branch, ReadContinuationV1):
        try:
            parsed_cursor = parse_cursor_untrusted(branch.cursor)
        except InvalidCursorError as error:
            return _read_cursor_error(error)
        evidence_id, max_bytes, position = untrusted_read_route(parsed_cursor)
    else:
        evidence_id, max_bytes, position = branch.evidence_id, branch.max_bytes, 0
    engine = build_engine(config.runtime)
    try:

        def validate(authority: ActiveAuthoritySnapshot) -> None:
            nonlocal parsed
            if parsed_cursor is not None:
                parsed = validate_read_cursor(
                    parsed_cursor,
                    material,
                    authority,
                )

        snapshot = engine.read_active_evidence(
            evidence_id,
            offset_bytes=position,
            range_bytes=max_bytes if parsed_cursor is not None else None,
            authority_validator=validate,
        )

        def cursor_factory(next_position: int, digest: str) -> str:
            record = snapshot.record
            return encode_read_cursor(
                material,
                ReadCursorPayload(
                    "mke.mcp_cursor.v1",
                    "read_evidence_v1",
                    material.epoch,
                    snapshot.authority.active_set_fingerprint,
                    record.evidence_id,
                    record.source_id,
                    record.content_fingerprint,
                    record.publication_id,
                    record.publication_revision,
                    record.run_id,
                    record.locator_kind,
                    record.locator_start,
                    record.locator_end,
                    digest,
                    record.original_utf8_bytes,
                    next_position,
                    max_bytes,
                    "mke.read_evidence_response.v1",
                ),
            )

        projection = assemble_read_chunk(
            snapshot,
            max_bytes=max_bytes,
            cursor_factory=cursor_factory,
            bound_text_sha256=None if parsed is None else parsed.evidence_text_sha256,
        )
        if parsed is not None and asdict(projection.descriptor) != {
            key: value
            for key, value in asdict(parsed).items()
            if key in asdict(projection.descriptor)
        }:
            raise CursorExpiredError("evidence_changed")
        return _read_success(projection)
    except EvidenceNotFoundError:
        return _read_error(
            "evidence_not_found",
            "active Evidence is not available",
            "search_current_active_evidence",
        )
    except EvidenceResponseTooLargeError:
        return _read_error(
            "response_too_large",
            "active Evidence exceeds the readable size limit",
            "reduce_query_scope_or_report_contract_limit",
        )
    except (InvalidCursorError, CursorExpiredError) as error:
        return _read_cursor_error(error)
    except Exception:
        return _read_error(
            "internal_error",
            "operation failed; details were redacted",
            "check_server_logs",
        )
    finally:
        engine.close()


def _authority(value: ActiveAuthoritySnapshot) -> ActiveAuthoritySnapshotV1:
    observation = value.observation
    return ActiveAuthoritySnapshotV1(
        observation=ActivePublicationObservationV1(
            state=observation.state,  # type: ignore[arg-type]
            source_count=observation.source_count,
            active_publication_count=observation.active_publication_count,
            active_evidence_count=observation.active_evidence_count,
        ),
        active_set_fingerprint=value.active_set_fingerprint,
    )


def _descriptor(value: Any) -> EvidenceDescriptorV1:
    locator = (
        PageLocatorV1(kind="page", start=value.locator_start, end=value.locator_end)
        if value.locator_kind == "page"
        else TimestampLocatorV1(
            kind="timestamp_ms", start=value.locator_start, end=value.locator_end
        )
    )
    return EvidenceDescriptorV1(
        evidence_id=value.evidence_id,
        source_id=value.source_id,
        content_fingerprint=value.content_fingerprint,
        publication_id=value.publication_id,
        publication_revision=value.publication_revision,
        run_id=value.run_id,
        locator=locator,
        evidence_text_sha256=value.evidence_text_sha256,
        original_utf8_bytes=value.original_utf8_bytes,
    )


def _search_success(projection: Any) -> SearchLibraryResponseV2:
    matches = [
        SearchMatchV2(
            evidence=_descriptor(item.descriptor),
            excerpt=EvidenceExcerptV1(**asdict(item.excerpt)),
            read=EvidenceReadAffordanceV1(evidence_id=item.read_evidence_id),
        )
        for item in projection.matches
    ]
    selection_value = projection.selection
    if selection_value.status == "more_available":
        selection = SearchSelectionMoreV2(
            status="more_available",
            returned=selection_value.returned,
            next_cursor=selection_value.next_cursor,
        )
    elif selection_value.status == "capped":
        selection = SearchSelectionCappedV2(
            status="capped",
            returned=selection_value.returned,
            limit_reason="retrieval_strategy_cap",
        )
    else:
        selection = SearchSelectionCompleteV2(status="complete", returned=selection_value.returned)
    return SearchLibraryResponseV2(
        root=SearchLibrarySuccessV2(
            authority_snapshot=_authority(projection.authority),
            query=projection.query,
            matches=matches,
            selection=selection,
            output=SearchOutputBudgetV1(
                incomplete_excerpt_count=projection.incomplete_excerpt_count
            ),
        )
    )


def _read_success(projection: Any) -> ReadEvidenceResponseV1:
    return ReadEvidenceResponseV1(
        root=ReadEvidenceSuccessV1(
            authority_snapshot=_authority(projection.authority),
            evidence=_descriptor(projection.descriptor),
            content=EvidenceContentV1(
                text=projection.chunk.text,
                offset_bytes=projection.chunk.offset_bytes,
                returned_utf8_bytes=projection.chunk.returned_utf8_bytes,
            ),
            complete=projection.complete,
            next_cursor=projection.next_cursor,
        )
    )


def _classify_request(raw: object, *, search: bool) -> tuple[str, str, str]:
    if isinstance(raw, dict):
        data = cast(dict[str, object], raw)
        query = data.get("query")
        cursor = data.get("cursor")
        if search and isinstance(query, str) and len(query.encode()) > 512:
            return (
                "invalid_request",
                "query exceeds 512 UTF-8 bytes",
                "narrow_query_to_512_utf8_bytes",
            )
        if search and isinstance(query, str) and not query.strip():
            return (
                "invalid_request",
                "query must not be empty",
                "provide_non_blank_query",
            )
        if isinstance(cursor, str) and len(cursor.encode()) > 4096:
            return "invalid_cursor", "cursor exceeds 4096 UTF-8 bytes", "restart_from_initial_call"
        if not search and "max_bytes" in data:
            return (
                "invalid_request",
                "max_bytes must be between 4 and 16384",
                "choose_max_bytes_between_4_and_16384",
            )
    return (
        "invalid_request",
        "request must use exactly one supported input branch",
        "use_exactly_one_supported_request_branch",
    )


def _search_error(problem: str, cause: str, next_step: str) -> SearchLibraryResponseV2:
    return SearchLibraryResponseV2(
        root=SearchLibraryErrorV2(ok=False, problem=problem, cause=cause, next_step=next_step)
    )


def _read_error(problem: str, cause: str, next_step: str) -> ReadEvidenceResponseV1:
    return ReadEvidenceResponseV1(
        root=ReadEvidenceErrorV1(ok=False, problem=problem, cause=cause, next_step=next_step)
    )


def _search_cursor_error(error: Exception) -> SearchLibraryResponseV2:
    problem, cause, next_step = _cursor_recovery(error)
    return _search_error(problem, cause, next_step)


def _read_cursor_error(error: Exception) -> ReadEvidenceResponseV1:
    problem, cause, next_step = _cursor_recovery(error)
    return _read_error(problem, cause, next_step)


def _cursor_recovery(error: Exception) -> tuple[str, str, str]:
    if isinstance(error, InvalidCursorError):
        return (
            "invalid_cursor",
            "cursor is malformed, unauthenticated, or for another tool",
            "restart_from_initial_call",
        )
    reason = error.reason  # type: ignore[attr-defined]
    if reason == "owner_restarted":
        return "cursor_expired", "cursor owner has restarted", "repeat_initial_call"
    if reason == "active_set_changed":
        return (
            "cursor_expired",
            "active Publication set changed",
            "repeat_search_on_current_publications",
        )
    if reason == "retrieval_policy_changed":
        return "cursor_expired", "retrieval policy changed", "repeat_search_under_current_strategy"
    return "cursor_expired", "active Evidence descriptor changed", "repeat_initial_call"
