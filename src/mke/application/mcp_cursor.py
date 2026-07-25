from __future__ import annotations

import base64
import hmac
import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Literal

from mke.runtime_owner import CursorOwnerMaterial

MAX_CURSOR_BYTES = 4096


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


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
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


def _decode(
    token: str,
    material: CursorOwnerMaterial,
    *,
    payload_type: type[SearchCursorPayload] | type[ReadCursorPayload],
    expected_tool: str,
) -> SearchCursorPayload | ReadCursorPayload:
    try:
        if not token or len(token.encode()) > MAX_CURSOR_BYTES:
            raise InvalidCursorError("cursor size")
        envelope = json.loads(_unb64(token), object_pairs_hook=_pairs)
        if set(envelope) != {"payload", "mac"}:
            raise InvalidCursorError("cursor envelope")
        payload_bytes = _unb64(str(envelope["payload"]))
        raw = json.loads(payload_bytes, object_pairs_hook=_pairs)
        payload = payload_type(**raw)
        if payload.tool != expected_tool:
            raise InvalidCursorError("wrong cursor tool")
        if payload.owner_epoch != material.epoch:
            raise CursorExpiredError("owner_restarted")
        supplied = _unb64(str(envelope["mac"]))
        expected = hmac.new(material.key, payload_bytes, sha256).digest()
        if not hmac.compare_digest(supplied, expected):
            raise InvalidCursorError("cursor authentication")
        return payload
    except CursorExpiredError:
        raise
    except InvalidCursorError:
        raise
    except Exception:
        raise InvalidCursorError("cursor is malformed") from None


def decode_search_cursor(
    token: str,
    material: CursorOwnerMaterial,
    *,
    current_active_set_fingerprint: str | None = None,
) -> SearchCursorPayload:
    payload = _decode(
        token,
        material,
        payload_type=SearchCursorPayload,
        expected_tool="search_library_v2",
    )
    assert isinstance(payload, SearchCursorPayload)
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
    payload = _decode(
        token,
        material,
        payload_type=ReadCursorPayload,
        expected_tool="read_evidence_v1",
    )
    assert isinstance(payload, ReadCursorPayload)
    if (
        current_active_set_fingerprint is not None
        and payload.active_set_fingerprint != current_active_set_fingerprint
    ):
        raise CursorExpiredError("active_set_changed")
    return payload
