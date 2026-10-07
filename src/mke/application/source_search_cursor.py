"""Authenticated scoped Search continuations, separate from frozen Library cursors."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields
from hashlib import sha256
from typing import Any, Literal, cast

from mke.application.mcp_cursor import (
    CursorExpiredError,
    InvalidCursorError,
    ParsedCursor,
    authenticate_cursor,
    encode_authenticated_cursor,
)
from mke.domain.evidence_access import ActiveAuthoritySnapshot
from mke.runtime_owner import CursorOwnerMaterial


@dataclass(frozen=True)
class SourceSearchCursorPayload:
    schema_version: Literal["mke.mcp_cursor.v1"]
    tool: Literal["search_source_evidence_v1"]
    owner_epoch: str
    active_set_fingerprint: str
    library_binding: str
    source_id: str
    publication_id: str
    publication_revision: int
    run_id: str
    content_fingerprint: str
    normalized_query: str
    query_fingerprint: str
    strategy_id: str
    strategy_revision: int
    query_policy: str
    query_policy_revision: int
    position: int
    page_size: int
    response_schema: Literal["mke.search_source_evidence_response.v1"]


def encode_source_search_cursor(
    material: CursorOwnerMaterial,
    payload: SourceSearchCursorPayload,
) -> str:
    return encode_authenticated_cursor(material, payload)


def validate_source_search_cursor(
    parsed: ParsedCursor,
    material: CursorOwnerMaterial,
    authority: ActiveAuthoritySnapshot,
    *,
    library_binding: str,
    strategy_id: str,
    strategy_revision: int,
    query_policy: str,
    query_policy_revision: int,
) -> SourceSearchCursorPayload:
    authenticate_cursor(parsed, material, expected_tool="search_source_evidence_v1")
    if set(parsed.raw) != {field.name for field in fields(SourceSearchCursorPayload)}:
        raise InvalidCursorError("cursor payload fields")
    integers = {
        "publication_revision",
        "strategy_revision",
        "query_policy_revision",
        "position",
        "page_size",
    }
    for name, value in parsed.raw.items():
        if type(value) is not (int if name in integers else str):
            raise InvalidCursorError("cursor field type")
    payload = SourceSearchCursorPayload(**cast(Any, parsed.raw))
    digest = re.compile(r"sha256:[0-9a-f]{64}\Z")
    if (
        payload.schema_version != "mke.mcp_cursor.v1"
        or payload.response_schema != "mke.search_source_evidence_response.v1"
        or payload.library_binding != library_binding
        or any(
            digest.fullmatch(value) is None
            for value in (
                payload.library_binding,
                payload.active_set_fingerprint,
                payload.content_fingerprint,
            )
        )
        or any(
            not value.strip() or len(value.encode()) > 512
            for value in (
                payload.source_id,
                payload.publication_id,
                payload.run_id,
                payload.normalized_query,
            )
        )
        or payload.normalized_query != payload.normalized_query.strip()
        or payload.query_fingerprint
        != f"sha256:{sha256(payload.normalized_query.encode()).hexdigest()}"
        or payload.publication_revision < 1
        or payload.position < 1
        or not 1 <= payload.page_size <= 20
    ):
        raise InvalidCursorError("cursor scoped Search bindings")
    if payload.active_set_fingerprint != authority.active_set_fingerprint:
        raise CursorExpiredError("active_set_changed")
    if (
        payload.strategy_id != strategy_id
        or payload.strategy_revision != strategy_revision
        or payload.query_policy != query_policy
        or payload.query_policy_revision != query_policy_revision
    ):
        raise CursorExpiredError("retrieval_policy_changed")
    return payload


def untrusted_source_search_route(parsed: ParsedCursor) -> tuple[str, str, str, int, int]:
    """Routing only; authority callback authenticates before any candidate selection."""
    raw = parsed.raw
    source = raw.get("source_id")
    publication = raw.get("publication_id")
    query = raw.get("normalized_query")
    size = raw.get("page_size")
    position = raw.get("position")
    return (
        source if type(source) is str else "",
        publication if type(publication) is str else "",
        query if type(query) is str else "",
        size if type(size) is int else 1,
        position if type(position) is int else 0,
    )
