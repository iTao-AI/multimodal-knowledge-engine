"""One canonical scoped Search operation shared by public CLI and MCP."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from hashlib import sha256
from typing import cast

from pydantic import ValidationError

from mke.adapters.sqlite import EvidenceNotFoundError, EvidenceResponseTooLargeError
from mke.application.evidence_access import (
    MAX_CANONICAL_MODEL_BYTES,
    ResponseTooLargeError,
    assemble_search_page,
    canonical_json_bytes,
)
from mke.application.mcp_cursor import (
    CursorExpiredError,
    InvalidCursorError,
    ParsedCursor,
    parse_cursor_untrusted,
)
from mke.application.source_cursor import library_binding
from mke.application.source_search_cursor import (
    SourceSearchCursorPayload,
    encode_source_search_cursor,
    untrusted_source_search_route,
    validate_source_search_cursor,
)
from mke.domain import ManifestValidationError
from mke.domain.evidence_access import ActiveAuthoritySnapshot, EvidenceSearchPage
from mke.domain.source_search import SourceSearchScope
from mke.interfaces.mcp_completeness_contract import (
    _classify_request,  # pyright: ignore[reportPrivateUsage]
    _cursor_recovery,  # pyright: ignore[reportPrivateUsage]
    _search_success,  # pyright: ignore[reportPrivateUsage]
)
from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.interfaces.source_search_schemas import (
    SOURCE_SEARCH_INPUT_V1,
    SearchSourceEvidenceErrorV1,
    SearchSourceEvidenceResponseV1,
    SearchSourceEvidenceV1Request,
    SourceSearchContinuationV1,
)
from mke.retrieval.cjk_active_scan import CjkActiveScanError
from mke.retrieval.errors import RetrievalAuthorityError
from mke.retrieval.query_policy import QUERY_POLICY_REVISION
from mke.retrieval.strategy import get_retrieval_strategy_descriptor
from mke.runtime import build_engine


def _error(problem: str, cause: str, next_step: str) -> SearchSourceEvidenceResponseV1:
    return SearchSourceEvidenceResponseV1(
        root=SearchSourceEvidenceErrorV1(
            ok=False,
            problem=problem,
            cause=cause,
            next_step=next_step,
        )
    )


def search_source_evidence_v1(
    config: McpRuntimeConfig,
    request: SearchSourceEvidenceV1Request,
) -> SearchSourceEvidenceResponseV1:
    try:
        branch = SOURCE_SEARCH_INPUT_V1.validate_python(request.root)
    except (ValidationError, UnicodeError):
        try:
            recovery = _classify_request(request.root, search=True)
        except UnicodeError:
            recovery = _classify_request(None, search=True)
        return _error(*recovery)
    engine = None
    try:
        material = config.runtime.owner_state.cursor_material()
        binding = library_binding(material, config.runtime.db_path)
        descriptor = get_retrieval_strategy_descriptor(cast(str, config.runtime.retrieval_strategy))
        parsed: ParsedCursor | None = None
        validated: SourceSearchCursorPayload | None = None
        if isinstance(branch, SourceSearchContinuationV1):
            parsed = parse_cursor_untrusted(branch.cursor)
            source, publication, query, limit, position = untrusted_source_search_route(parsed)
        else:
            source, publication, query, limit, position = (
                branch.source_id,
                branch.publication_id,
                branch.query.strip(),
                branch.limit,
                0,
            )

        def validate(authority: ActiveAuthoritySnapshot) -> None:
            nonlocal validated
            if parsed is not None:
                validated = validate_source_search_cursor(
                    parsed,
                    material,
                    authority,
                    library_binding=binding,
                    strategy_id=descriptor.strategy_id,
                    strategy_revision=descriptor.revision,
                    query_policy=descriptor.base_query_policy,
                    query_policy_revision=QUERY_POLICY_REVISION,
                )

        def validate_scope(scope: SourceSearchScope) -> None:
            if validated is not None and (
                validated.publication_revision != scope.publication_revision
                or validated.run_id != scope.run_id
                or validated.content_fingerprint != scope.content_fingerprint
            ):
                raise InvalidCursorError("cursor selected authority identity")

        engine = build_engine(config.runtime)
        snapshot = engine.search_source_evidence_page(
            source,
            publication,
            query,
            position=position,
            page_size=limit,
            authority_validator=validate,
            scope_validator=validate_scope,
        )
        scope = snapshot.scope
        assert scope is not None

        def cursor_factory(next_position: int) -> str:
            return encode_source_search_cursor(
                material,
                SourceSearchCursorPayload(
                    "mke.mcp_cursor.v1",
                    "search_source_evidence_v1",
                    material.epoch,
                    snapshot.authority.active_set_fingerprint,
                    binding,
                    scope.source_id,
                    scope.publication_id,
                    scope.publication_revision,
                    scope.run_id,
                    scope.content_fingerprint,
                    snapshot.normalized_query,
                    f"sha256:{sha256(snapshot.normalized_query.encode()).hexdigest()}",
                    snapshot.strategy_id,
                    snapshot.strategy_revision,
                    snapshot.query_policy,
                    snapshot.query_policy_revision,
                    next_position,
                    limit,
                    "mke.search_source_evidence_response.v1",
                ),
            )

        return _assemble(snapshot, limit, cursor_factory)
    except (InvalidCursorError, CursorExpiredError) as error:
        return _error(*_cursor_recovery(error))
    except EvidenceNotFoundError:
        return _error(
            "evidence_not_found", "active Evidence is not available", "reselect_active_source"
        )
    except (ResponseTooLargeError, EvidenceResponseTooLargeError):
        return _error(
            "response_too_large",
            "mandatory response metadata exceeds the response limit",
            "reduce_query_scope_or_report_contract_limit",
        )
    except (CjkActiveScanError, RetrievalAuthorityError) as error:
        return _error(error.problem, error.cause, error.next_step)
    except ManifestValidationError:
        return _error(
            "evidence_not_found", "active Evidence is not available", "reselect_active_source"
        )
    except Exception:
        return _error(
            "internal_error", "operation failed; details were redacted", "check_server_logs"
        )
    finally:
        if engine is not None:
            engine.close()


def _assemble(
    snapshot: EvidenceSearchPage,
    limit: int,
    cursor_factory: Callable[[int], str],
) -> SearchSourceEvidenceResponseV1:
    assert snapshot.scope is not None
    for count in range(min(len(snapshot.results), limit), -1, -1):
        if count == 0 and snapshot.results:
            break
        try:
            projection = assemble_search_page(
                snapshot,
                page_size=count,
                cursor_factory=cursor_factory,
            )
        except ResponseTooLargeError:
            continue
        payload = _search_success(projection).model_dump(mode="json")
        payload["schema_version"] = "mke.search_source_evidence_response.v1"
        payload["scope"] = {
            "schema_version": "mke.source_search_scope.v1",
            **asdict(snapshot.scope),
        }
        response = SearchSourceEvidenceResponseV1.model_validate(payload)
        if len(canonical_json_bytes(response.model_dump(mode="json"))) <= MAX_CANONICAL_MODEL_BYTES:
            return response
    raise ResponseTooLargeError
