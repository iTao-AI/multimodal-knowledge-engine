from __future__ import annotations

import base64
import hmac
import json
import re
from dataclasses import asdict, dataclass, fields
from hashlib import sha256
from typing import Any, Literal, cast

from mke.domain.evidence_access import ActiveAuthoritySnapshot
from mke.runtime_owner import CursorOwnerMaterial

MAX_CURSOR_BYTES = 4096
_BASE64URL = re.compile(r"[A-Za-z0-9_-]+\Z")
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")


class InvalidCursorError(ValueError):
    """Cursor syntax, authentication, tool, or bound-field validation failed."""


class CursorExpiredError(ValueError):
    def __init__(
        self,
        reason: Literal[
            "owner_restarted",
            "active_set_changed",
            "retrieval_policy_changed",
            "evidence_changed",
        ],
    ) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class SearchCursorPayload:
    schema_version: Literal["mke.mcp_cursor.v1"]
    tool: Literal["search_library_v2"]
    owner_epoch: str
    active_set_fingerprint: str
    normalized_query: str
    query_fingerprint: str
    strategy_id: str
    strategy_revision: int
    query_policy: str
    query_policy_revision: int
    position: int
    page_size: int
    response_schema: Literal["mke.search_library_response.v2"]


@dataclass(frozen=True)
class ReadCursorPayload:
    schema_version: Literal["mke.mcp_cursor.v1"]
    tool: Literal["read_evidence_v1"]
    owner_epoch: str
    active_set_fingerprint: str
    evidence_id: str
    source_id: str
    content_fingerprint: str
    publication_id: str
    publication_revision: int
    run_id: str
    locator_kind: Literal["page", "timestamp_ms"]
    locator_start: int
    locator_end: int
    evidence_text_sha256: str
    original_utf8_bytes: int
    position: int
    max_bytes: int
    response_schema: Literal["mke.read_evidence_response.v1"]


@dataclass(frozen=True)
class ParsedCursor:
    raw: dict[str, object]
    payload_bytes: bytes
    supplied_mac: bytes


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    if not value or _BASE64URL.fullmatch(value) is None:
        raise InvalidCursorError("cursor base64")
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _encode(
    material: CursorOwnerMaterial,
    payload: SearchCursorPayload | ReadCursorPayload,
) -> str:
    payload_bytes = _canonical(asdict(payload))
    envelope = {
        "payload": _b64(payload_bytes),
        "mac": _b64(hmac.new(material.key, payload_bytes, sha256).digest()),
    }
    return _b64(_canonical(envelope))


def encode_search_cursor(
    material: CursorOwnerMaterial, payload: SearchCursorPayload
) -> str:
    return _encode(material, payload)


def encode_read_cursor(material: CursorOwnerMaterial, payload: ReadCursorPayload) -> str:
    return _encode(material, payload)


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidCursorError("duplicate cursor field")
        result[key] = value
    return result


def parse_cursor_untrusted(token: str) -> ParsedCursor:
    """Parse bounded syntax without opening or authenticating repository state."""
    try:
        if type(token) is not str or not token or len(token.encode()) > MAX_CURSOR_BYTES:
            raise InvalidCursorError("cursor size")
        envelope_value: object = json.loads(
            _unb64(token), object_pairs_hook=_pairs
        )
        if type(envelope_value) is not dict:
            raise InvalidCursorError("cursor envelope")
        envelope = cast(dict[str, object], envelope_value)
        if set(envelope) != {"payload", "mac"}:
            raise InvalidCursorError("cursor envelope")
        payload_value = envelope["payload"]
        mac_value = envelope["mac"]
        if type(payload_value) is not str or type(mac_value) is not str:
            raise InvalidCursorError("cursor envelope")
        payload_bytes = _unb64(payload_value)
        raw_value: object = json.loads(payload_bytes, object_pairs_hook=_pairs)
        if type(raw_value) is not dict:
            raise InvalidCursorError("cursor payload")
        raw = cast(dict[str, object], raw_value)
        position = raw.get("position")
        if position is not None and (type(position) is not int or position < 0):
            raise InvalidCursorError("cursor position")
        page_size = raw.get("page_size")
        if page_size is not None and (
            type(page_size) is not int or not 1 <= page_size <= 20
        ):
            raise InvalidCursorError("cursor page size")
        max_bytes = raw.get("max_bytes")
        if max_bytes is not None and (
            type(max_bytes) is not int or not 4 <= max_bytes <= 16_384
        ):
            raise InvalidCursorError("cursor chunk size")
        return ParsedCursor(raw, payload_bytes, _unb64(mac_value))
    except InvalidCursorError:
        raise
    except Exception:
        raise InvalidCursorError("cursor is malformed") from None


def untrusted_search_route(parsed: ParsedCursor) -> tuple[str, int, int]:
    raw = parsed.raw
    query = raw.get("normalized_query")
    page_size = raw.get("page_size")
    position = raw.get("position")
    return (
        query if type(query) is str else "",
        page_size if type(page_size) is int else 1,
        position if type(position) is int else 0,
    )


def untrusted_read_route(parsed: ParsedCursor) -> tuple[str, int, int]:
    raw = parsed.raw
    evidence_id = raw.get("evidence_id")
    max_bytes = raw.get("max_bytes")
    position = raw.get("position")
    return (
        evidence_id if type(evidence_id) is str else "",
        max_bytes if type(max_bytes) is int else 4,
        position if type(position) is int else 0,
    )


def _authenticate(
    parsed: ParsedCursor,
    material: CursorOwnerMaterial,
    *,
    expected_tool: str,
) -> None:
    if parsed.raw.get("owner_epoch") != material.epoch:
        raise CursorExpiredError("owner_restarted")
    expected = hmac.new(material.key, parsed.payload_bytes, sha256).digest()
    if not hmac.compare_digest(parsed.supplied_mac, expected):
        raise InvalidCursorError("cursor authentication")
    if parsed.raw.get("tool") != expected_tool:
        raise InvalidCursorError("wrong cursor tool")


def _strict_payload(
    parsed: ParsedCursor,
    payload_type: type[SearchCursorPayload] | type[ReadCursorPayload],
) -> SearchCursorPayload | ReadCursorPayload:
    expected_fields = {field.name for field in fields(payload_type)}
    if set(parsed.raw) != expected_fields:
        raise InvalidCursorError("cursor payload fields")
    try:
        payload = payload_type(**cast(Any, parsed.raw))
    except TypeError:
        raise InvalidCursorError("cursor payload fields") from None
    for field in fields(payload_type):
        value = getattr(payload, field.name)
        if field.name in {
            "strategy_revision",
            "query_policy_revision",
            "position",
            "page_size",
            "publication_revision",
            "locator_start",
            "locator_end",
            "original_utf8_bytes",
            "max_bytes",
        } and type(value) is not int:
            raise InvalidCursorError("cursor integer field")
        if field.name not in {
            "strategy_revision",
            "query_policy_revision",
            "position",
            "page_size",
            "publication_revision",
            "locator_start",
            "locator_end",
            "original_utf8_bytes",
            "max_bytes",
        } and type(value) is not str:
            raise InvalidCursorError("cursor string field")
    return payload


def _search_payload(parsed: ParsedCursor) -> SearchCursorPayload:
    payload = _strict_payload(parsed, SearchCursorPayload)
    assert isinstance(payload, SearchCursorPayload)
    fingerprint = f"sha256:{sha256(payload.normalized_query.encode()).hexdigest()}"
    valid = (
        payload.schema_version == "mke.mcp_cursor.v1"
        and payload.tool == "search_library_v2"
        and payload.response_schema == "mke.search_library_response.v2"
        and bool(payload.normalized_query.strip())
        and len(payload.normalized_query.encode()) <= 512
        and payload.query_fingerprint == fingerprint
        and _SHA256.fullmatch(payload.active_set_fingerprint) is not None
        and payload.strategy_revision > 0
        and payload.query_policy_revision > 0
        and payload.position >= 0
        and 1 <= payload.page_size <= 20
    )
    if not valid:
        raise InvalidCursorError("cursor search bindings")
    return payload


def _read_payload(parsed: ParsedCursor) -> ReadCursorPayload:
    payload = _strict_payload(parsed, ReadCursorPayload)
    assert isinstance(payload, ReadCursorPayload)
    valid = (
        payload.schema_version == "mke.mcp_cursor.v1"
        and payload.tool == "read_evidence_v1"
        and payload.response_schema == "mke.read_evidence_response.v1"
        and _SHA256.fullmatch(payload.active_set_fingerprint) is not None
        and _SHA256.fullmatch(payload.content_fingerprint) is not None
        and _SHA256.fullmatch(payload.evidence_text_sha256) is not None
        and payload.publication_revision > 0
        and payload.original_utf8_bytes > 0
        and 0 <= payload.position < payload.original_utf8_bytes
        and 4 <= payload.max_bytes <= 16_384
    )
    if not valid:
        raise InvalidCursorError("cursor read bindings")
    return payload


def validate_search_cursor(
    parsed: ParsedCursor,
    material: CursorOwnerMaterial,
    authority: ActiveAuthoritySnapshot,
    *,
    strategy_id: str,
    strategy_revision: int,
    query_policy: str,
    query_policy_revision: int,
) -> SearchCursorPayload:
    _authenticate(parsed, material, expected_tool="search_library_v2")
    payload = _search_payload(parsed)
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


def validate_read_cursor(
    parsed: ParsedCursor,
    material: CursorOwnerMaterial,
    authority: ActiveAuthoritySnapshot,
) -> ReadCursorPayload:
    _authenticate(parsed, material, expected_tool="read_evidence_v1")
    payload = _read_payload(parsed)
    if payload.active_set_fingerprint != authority.active_set_fingerprint:
        raise CursorExpiredError("active_set_changed")
    return payload


def decode_search_cursor(
    token: str,
    material: CursorOwnerMaterial,
    *,
    current_active_set_fingerprint: str | None = None,
) -> SearchCursorPayload:
    parsed = parse_cursor_untrusted(token)
    _authenticate(parsed, material, expected_tool="search_library_v2")
    payload = _search_payload(parsed)
    if (
        current_active_set_fingerprint is not None
        and payload.active_set_fingerprint != current_active_set_fingerprint
    ):
        raise CursorExpiredError("active_set_changed")
    return payload


def decode_read_cursor(
    token: str,
    material: CursorOwnerMaterial,
    *,
    current_active_set_fingerprint: str | None = None,
) -> ReadCursorPayload:
    parsed = parse_cursor_untrusted(token)
    _authenticate(parsed, material, expected_tool="read_evidence_v1")
    payload = _read_payload(parsed)
    if (
        current_active_set_fingerprint is not None
        and payload.active_set_fingerprint != current_active_set_fingerprint
    ):
        raise CursorExpiredError("active_set_changed")
    return payload
