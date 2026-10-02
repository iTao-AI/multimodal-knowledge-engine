"""Shared Source discovery operations for native MCP and CLI consumers."""

from __future__ import annotations

from dataclasses import asdict
from typing import cast

from pydantic import ValidationError

from mke.adapters.sqlite import EvidenceNotFoundError, EvidenceResponseTooLargeError
from mke.application import KnowledgeEngine
from mke.application.evidence_access import ResponseTooLargeError, canonical_json_bytes
from mke.application.mcp_cursor import (
    CursorExpiredError,
    InvalidCursorError,
    ParsedCursor,
    parse_cursor_untrusted,
)
from mke.application.source_cursor import (
    BROWSE_ORDER,
    CATALOG_ORDER,
    SourceCursorPayload,
    encode_source_cursor,
    library_binding,
    untrusted_source_route,
    validate_source_cursor,
)
from mke.application.source_discovery import assemble_source_page
from mke.domain import ManifestValidationError
from mke.domain.evidence_access import ActiveAuthoritySnapshot
from mke.domain.source_discovery import SourceBrowsePage, SourceCatalogPage, SourceLocatorRange
from mke.interfaces.mcp_completeness_contract import (
    _authority,  # pyright: ignore[reportPrivateUsage]
    _cursor_recovery,  # pyright: ignore[reportPrivateUsage]
    _descriptor,  # pyright: ignore[reportPrivateUsage]
)
from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.interfaces.mcp_schemas import (
    EvidenceExcerptV1,
    EvidenceReadAffordanceV1,
    SearchMatchV2,
    SearchOutputBudgetV1,
)
from mke.interfaces.source_schemas import (
    BROWSE_SOURCE_INPUT_V1,
    LIST_SOURCES_INPUT_V1,
    BrowseSourceEvidenceErrorV1,
    BrowseSourceEvidenceResponseV1,
    BrowseSourceEvidenceSuccessV1,
    BrowseSourceEvidenceV1Request,
    ListSourcesErrorV1,
    ListSourcesResponseV1,
    ListSourcesSuccessV1,
    ListSourcesV1Request,
    SourceContinuationV1,
    SourceMetadataV1,
    SourceSelectionCompleteV1,
    SourceSelectionMoreV1,
    SourceSelectionV1,
)
from mke.runtime import build_engine

type SourceResponse = ListSourcesResponseV1 | BrowseSourceEvidenceResponseV1


def list_sources_v1(
    config: McpRuntimeConfig,
    request: ListSourcesV1Request,
) -> ListSourcesResponseV1:
    return cast(ListSourcesResponseV1, _operation(config, request.root, browse=False))


def browse_source_evidence_v1(
    config: McpRuntimeConfig,
    request: BrowseSourceEvidenceV1Request,
) -> BrowseSourceEvidenceResponseV1:
    return cast(BrowseSourceEvidenceResponseV1, _operation(config, request.root, browse=True))


def _selection(count: int, cursor: str | None) -> SourceSelectionV1:
    if cursor is None:
        return SourceSelectionCompleteV1(status="complete", returned=count)
    return SourceSelectionMoreV1(status="more_available", returned=count, next_cursor=cursor)


def _catalog_success(page: SourceCatalogPage, cursor: str | None) -> ListSourcesResponseV1:
    return ListSourcesResponseV1(
        root=ListSourcesSuccessV1(
            authority_snapshot=_authority(page.authority),
            sources=[
                SourceMetadataV1.model_validate_json(canonical_json_bytes(asdict(item)))
                for item in page.sources
            ],
            selection=_selection(len(page.sources), cursor),
        )
    )


def _browse_success(
    page: SourceBrowsePage,
    cursor: str | None,
) -> BrowseSourceEvidenceResponseV1:
    return BrowseSourceEvidenceResponseV1(
        root=BrowseSourceEvidenceSuccessV1(
            authority_snapshot=_authority(page.authority),
            source=SourceMetadataV1.model_validate_json(canonical_json_bytes(asdict(page.source))),
            entries=[
                SearchMatchV2(
                    evidence=_descriptor(item.descriptor),
                    excerpt=EvidenceExcerptV1(**asdict(item.preview)),
                    read=EvidenceReadAffordanceV1(evidence_id=item.descriptor.evidence_id),
                )
                for item in page.entries
            ],
            selection=_selection(len(page.entries), cursor),
            output=SearchOutputBudgetV1(
                incomplete_excerpt_count=sum(not item.preview.complete for item in page.entries),
            ),
        )
    )


def _error(browse: bool, problem: str, cause: str, next_step: str) -> SourceResponse:
    if browse:
        return BrowseSourceEvidenceResponseV1(
            root=BrowseSourceEvidenceErrorV1(
                ok=False,
                problem=problem,
                cause=cause,
                next_step=next_step,
            )
        )
    return ListSourcesResponseV1(
        root=ListSourcesErrorV1(
            ok=False,
            problem=problem,
            cause=cause,
            next_step=next_step,
        )
    )


def _operation(config: McpRuntimeConfig, raw: object, *, browse: bool) -> SourceResponse:
    tool = "browse_source_evidence_v1" if browse else "list_sources_v1"
    response_schema = (
        "mke.browse_source_evidence_response.v1" if browse else "mke.list_sources_response.v1"
    )
    parsed: ParsedCursor | None = None
    engine: KnowledgeEngine | None = None
    try:
        try:
            branch = (BROWSE_SOURCE_INPUT_V1 if browse else LIST_SOURCES_INPUT_V1).validate_python(
                raw
            )
        except ValidationError:
            if isinstance(raw, dict):
                cursor = cast(dict[str, object], raw).get("cursor")
                if isinstance(cursor, str) and len(cursor.encode()) > 4096:
                    return _error(
                        browse,
                        "invalid_cursor",
                        "cursor exceeds 4096 UTF-8 bytes",
                        "restart_from_initial_call",
                    )
            return _error(
                browse,
                "invalid_request",
                "request must use exactly one supported input branch",
                "use_exactly_one_supported_request_branch",
            )
        material = config.runtime.owner_state.cursor_material()
        binding = library_binding(material, config.db_path)
        if isinstance(branch, SourceContinuationV1):
            parsed = parse_cursor_untrusted(branch.cursor)
            source, publication, locator, position, page_size = untrusted_source_route(parsed)
        else:
            position, page_size = 0, branch.page_size
            source, publication, locator = "", "", None
            if browse:
                from mke.interfaces.source_schemas import BrowseSourceInitialV1

                initial = cast(BrowseSourceInitialV1, branch)
                source, publication = initial.source_id, initial.publication_id
                if initial.locator_range is not None:
                    value = initial.locator_range
                    locator = SourceLocatorRange(value.kind, value.start, value.end)
        engine = build_engine(config.runtime)

        def validate(authority: ActiveAuthoritySnapshot) -> None:
            if parsed is not None:
                validate_source_cursor(
                    parsed, material, authority, tool=tool, library_binding=binding
                )

        def cursor_factory(authority: ActiveAuthoritySnapshot, next_position: int) -> str:
            return encode_source_cursor(
                material,
                SourceCursorPayload(
                    "mke.mcp_cursor.v1",
                    tool,
                    material.epoch,
                    authority.active_set_fingerprint,
                    binding,
                    next_position,
                    page_size,
                    response_schema,
                    source,
                    publication,
                    "" if locator is None else locator.kind,
                    0 if locator is None else locator.start,
                    0 if locator is None else locator.end,
                    BROWSE_ORDER if browse else CATALOG_ORDER,
                ),
            )

        if browse:
            page = engine.browse_source_evidence_page(
                source,
                publication,
                locator_range=locator,
                position=position,
                page_size=page_size,
                authority_validator=validate,
            )
            assembly = assemble_source_page(
                page,
                cursor_factory=lambda offset: cursor_factory(page.authority, offset),
                serialize_response=lambda selected, cursor: _browse_success(
                    selected,
                    cursor,
                ).model_dump(mode="json"),
            )
            return _browse_success(assembly.page, assembly.next_cursor)
        catalog = engine.list_sources_page(
            position=position,
            page_size=page_size,
            authority_validator=validate,
        )
        selected_catalog = assemble_source_page(
            catalog,
            cursor_factory=lambda offset: cursor_factory(catalog.authority, offset),
            serialize_response=lambda selected, cursor: _catalog_success(
                selected,
                cursor,
            ).model_dump(mode="json"),
        )
        return _catalog_success(selected_catalog.page, selected_catalog.next_cursor)
    except (InvalidCursorError, CursorExpiredError) as error:
        return _error(browse, *_cursor_recovery(error))
    except EvidenceNotFoundError:
        return _error(
            browse,
            "evidence_not_found",
            "active Evidence is not available",
            "search_current_active_evidence",
        )
    except (EvidenceResponseTooLargeError, ResponseTooLargeError):
        return _error(
            browse,
            "response_too_large",
            "mandatory response metadata exceeds the response limit",
            "reduce_query_scope_or_report_contract_limit",
        )
    except (ManifestValidationError, ValidationError):
        return _error(
            browse, "internal_error", "operation failed; details were redacted", "check_server_logs"
        )
    except ValueError:
        if parsed is not None:
            return _error(browse, *_cursor_recovery(InvalidCursorError("invalid route")))
        return _error(
            browse,
            "invalid_request",
            "request must use exactly one supported input branch",
            "use_exactly_one_supported_request_branch",
        )
    except Exception:
        return _error(
            browse, "internal_error", "operation failed; details were redacted", "check_server_logs"
        )
    finally:
        if engine is not None:
            engine.close()
