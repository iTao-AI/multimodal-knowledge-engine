"""Operation-specific authenticated Source cursors using the shared envelope."""

from __future__ import annotations

import hmac
import re
from dataclasses import dataclass, fields
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, cast

from mke.application.mcp_cursor import (
    CursorExpiredError,
    InvalidCursorError,
    ParsedCursor,
    authenticate_cursor,
    encode_authenticated_cursor,
)
from mke.domain.evidence_access import ActiveAuthoritySnapshot
from mke.domain.source_discovery import SourceLocatorRange
from mke.runtime_owner import CursorOwnerMaterial

CATALOG_ORDER = "content-fingerprint-source-id-v1"
BROWSE_ORDER = "locator-start-end-evidence-id-v1"


@dataclass(frozen=True)
class SourceCursorPayload:
    schema_version: Literal["mke.mcp_cursor.v1"]
    tool: Literal["list_sources_v1", "browse_source_evidence_v1"]
    owner_epoch: str
    active_set_fingerprint: str
    library_binding: str
    position: int
    page_size: int
    response_schema: str
    source_id: str
    publication_id: str
    locator_kind: str
    locator_start: int
    locator_end: int
    ordering_version: str


def library_binding(material: CursorOwnerMaterial, database_identity: str | Path) -> str:
    identity = str(Path(database_identity).resolve()).encode()
    return (
        "sha256:"
        + hmac.new(material.key, b"mke.source.library.v1\0" + identity, sha256).hexdigest()
    )


def encode_source_cursor(material: CursorOwnerMaterial, payload: SourceCursorPayload) -> str:
    return encode_authenticated_cursor(material, payload)


def validate_source_cursor(
    parsed: ParsedCursor,
    material: CursorOwnerMaterial,
    authority: ActiveAuthoritySnapshot,
    *,
    tool: str,
    library_binding: str,
) -> SourceCursorPayload:
    authenticate_cursor(parsed, material, expected_tool=tool)
    if set(parsed.raw) != {field.name for field in fields(SourceCursorPayload)}:
        raise InvalidCursorError("cursor payload fields")
    integers = {"position", "page_size", "locator_start", "locator_end"}
    for key, value in parsed.raw.items():
        if type(value) is not (int if key in integers else str):
            raise InvalidCursorError("cursor field type")
    payload = SourceCursorPayload(**cast(Any, parsed.raw))
    digest = re.compile(r"sha256:[0-9a-f]{64}\Z")
    if (
        payload.schema_version != "mke.mcp_cursor.v1"
        or payload.library_binding != library_binding
        or digest.fullmatch(payload.library_binding) is None
        or digest.fullmatch(payload.active_set_fingerprint) is None
        or payload.position < 1
        or not 1 <= payload.page_size <= 20
    ):
        raise InvalidCursorError("cursor source bindings")
    if tool == "list_sources_v1":
        if (
            payload.response_schema != "mke.list_sources_response.v1"
            or payload.ordering_version != CATALOG_ORDER
            or payload.source_id
            or payload.publication_id
            or payload.locator_kind
            or payload.locator_start != 0
            or payload.locator_end != 0
        ):
            raise InvalidCursorError("cursor catalog bindings")
    elif tool == "browse_source_evidence_v1":
        if (
            payload.response_schema != "mke.browse_source_evidence_response.v1"
            or payload.ordering_version != BROWSE_ORDER
            or not payload.source_id
            or not payload.publication_id
        ):
            raise InvalidCursorError("cursor browse bindings")
        if payload.locator_kind:
            try:
                SourceLocatorRange(
                    cast(Literal["page", "timestamp_ms"], payload.locator_kind),
                    payload.locator_start,
                    payload.locator_end,
                )
            except ValueError:
                raise InvalidCursorError("cursor locator bindings") from None
        elif payload.locator_start or payload.locator_end:
            raise InvalidCursorError("cursor locator bindings")
    else:
        raise InvalidCursorError("cursor tool")
    if payload.active_set_fingerprint != authority.active_set_fingerprint:
        raise CursorExpiredError("active_set_changed")
    return payload


def untrusted_source_route(
    parsed: ParsedCursor,
) -> tuple[str, str, SourceLocatorRange | None, int, int]:
    """Route only; caller must validate inside the SQLite authority callback."""
    raw = parsed.raw
    locator = None
    if raw.get("locator_kind"):
        try:
            locator = SourceLocatorRange(
                cast(Any, raw.get("locator_kind")),
                cast(Any, raw.get("locator_start")),
                cast(Any, raw.get("locator_end")),
            )
        except ValueError:
            raise InvalidCursorError("cursor locator bindings") from None
    return (
        cast(str, raw.get("source_id", "")),
        cast(str, raw.get("publication_id", "")),
        locator,
        cast(int, raw.get("position", 0)),
        cast(int, raw.get("page_size", 1)),
    )
