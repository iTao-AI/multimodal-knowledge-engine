import pytest

from mke.application.mcp_cursor import (
    CursorExpiredError,
    InvalidCursorError,
    SearchCursorPayload,
    decode_search_cursor,
    encode_search_cursor,
)
from mke.runtime_owner import OwnerRuntimeState


def _payload() -> SearchCursorPayload:
    return SearchCursorPayload(
        schema_version="mke.mcp_cursor.v1",
        tool="search_library_v2",
        owner_epoch="a" * 32,
        active_set_fingerprint="sha256:" + "b" * 64,
        normalized_query="query",
        query_fingerprint="sha256:" + "c" * 64,
        strategy_id="sqlite-fts-v1",
        strategy_revision=1,
        query_policy="numeric-grouping-v1",
        query_policy_revision=1,
        position=1,
        page_size=5,
        response_schema="mke.search_library_response.v2",
    )


def test_cursor_round_trip_and_tamper() -> None:
    owner = OwnerRuntimeState(cursor_key=b"k" * 32, owner_epoch="a" * 32)
    token = encode_search_cursor(owner.cursor_material(), _payload())
    assert "=" not in token
    assert decode_search_cursor(token, owner.cursor_material()) == _payload()
    with pytest.raises(InvalidCursorError):
        decode_search_cursor(
            token[:-1] + ("A" if token[-1] != "A" else "B"),
            owner.cursor_material(),
        )


def test_owner_restart_expires_cursor() -> None:
    first = OwnerRuntimeState(cursor_key=b"k" * 32, owner_epoch="a" * 32)
    token = encode_search_cursor(first.cursor_material(), _payload())
    second = OwnerRuntimeState(cursor_key=b"z" * 32, owner_epoch="b" * 32)
    with pytest.raises(CursorExpiredError, match="owner_restarted"):
        decode_search_cursor(token, second.cursor_material())


def test_bound_authority_drift_expires_cursor() -> None:
    owner = OwnerRuntimeState(cursor_key=b"k" * 32, owner_epoch="a" * 32)
    token = encode_search_cursor(owner.cursor_material(), _payload())
    with pytest.raises(CursorExpiredError, match="active_set_changed"):
        decode_search_cursor(
            token,
            owner.cursor_material(),
            current_active_set_fingerprint="sha256:" + "d" * 64,
        )
