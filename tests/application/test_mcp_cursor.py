from dataclasses import replace
from hashlib import sha256

import pytest

from mke.application.mcp_cursor import (
    CursorExpiredError,
    InvalidCursorError,
    ReadCursorPayload,
    SearchCursorPayload,
    decode_search_cursor,
    encode_read_cursor,
    encode_search_cursor,
    parse_cursor_untrusted,
    validate_read_cursor,
    validate_search_cursor,
)
from mke.domain import ActivePublicationObservation
from mke.domain.evidence_access import ActiveAuthoritySnapshot
from mke.runtime_owner import OwnerRuntimeState


def _payload() -> SearchCursorPayload:
    return SearchCursorPayload(
        schema_version="mke.mcp_cursor.v1",
        tool="search_library_v2",
        owner_epoch="a" * 32,
        active_set_fingerprint="sha256:" + "b" * 64,
        normalized_query="query",
        query_fingerprint=f"sha256:{sha256(b'query').hexdigest()}",
        strategy_id="sqlite-fts-v1",
        strategy_revision=1,
        query_policy="numeric-grouping-v1",
        query_policy_revision=1,
        position=1,
        page_size=5,
        response_schema="mke.search_library_response.v2",
    )


def _read_payload() -> ReadCursorPayload:
    return ReadCursorPayload(
        schema_version="mke.mcp_cursor.v1",
        tool="read_evidence_v1",
        owner_epoch="a" * 32,
        active_set_fingerprint="sha256:" + "b" * 64,
        evidence_id="ev_" + "1" * 32,
        source_id="src_" + "2" * 32,
        content_fingerprint="sha256:" + "3" * 64,
        publication_id="pub_" + "4" * 32,
        publication_revision=1,
        run_id="run_" + "5" * 32,
        locator_kind="page",
        locator_start=1,
        locator_end=1,
        evidence_text_sha256="sha256:" + "6" * 64,
        original_utf8_bytes=100,
        position=4,
        max_bytes=16,
        response_schema="mke.read_evidence_response.v1",
    )


def _authority() -> ActiveAuthoritySnapshot:
    return ActiveAuthoritySnapshot(
        ActivePublicationObservation("local", "active", 1, 1, 1),
        "sha256:" + "b" * 64,
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


def test_revision_one_search_cursor_expires_under_revision_two() -> None:
    owner = OwnerRuntimeState(cursor_key=b"k" * 32, owner_epoch="a" * 32)
    payload = replace(
        _payload(),
        strategy_id="cjk-active-scan-overlap-v1",
        strategy_revision=1,
    )
    parsed = parse_cursor_untrusted(
        encode_search_cursor(owner.cursor_material(), payload)
    )

    with pytest.raises(CursorExpiredError, match="retrieval_policy_changed"):
        validate_search_cursor(
            parsed,
            owner.cursor_material(),
            _authority(),
            strategy_id="cjk-active-scan-overlap-v1",
            strategy_revision=2,
            query_policy="numeric-grouping-v1",
            query_policy_revision=1,
        )


def test_read_cursor_survives_strategy_change_but_owner_restart_expires_both() -> None:
    from mke.retrieval.strategy import get_retrieval_strategy_descriptor

    first = OwnerRuntimeState(cursor_key=b"k" * 32, owner_epoch="a" * 32)
    search_payload = replace(
        _payload(),
        strategy_id="cjk-active-scan-overlap-v1",
        strategy_revision=1,
    )
    search = parse_cursor_untrusted(
        encode_search_cursor(first.cursor_material(), search_payload)
    )
    read = parse_cursor_untrusted(
        encode_read_cursor(first.cursor_material(), _read_payload())
    )

    before = get_retrieval_strategy_descriptor("numeric-grouping-v1")
    assert validate_read_cursor(read, first.cursor_material(), _authority()) == (
        _read_payload()
    )
    after = get_retrieval_strategy_descriptor("cjk-active-scan-overlap-v1")
    assert (before.strategy_id, after.strategy_id) == (
        "numeric-grouping-v1",
        "cjk-active-scan-overlap-v1",
    )
    assert validate_read_cursor(read, first.cursor_material(), _authority()) == (
        _read_payload()
    )

    second = OwnerRuntimeState(cursor_key=b"z" * 32, owner_epoch="b" * 32)
    with pytest.raises(CursorExpiredError, match="owner_restarted"):
        validate_search_cursor(
            search,
            second.cursor_material(),
            _authority(),
            strategy_id="cjk-active-scan-overlap-v1",
            strategy_revision=2,
            query_policy="numeric-grouping-v1",
            query_policy_revision=1,
        )
    with pytest.raises(CursorExpiredError, match="owner_restarted"):
        validate_read_cursor(read, second.cursor_material(), _authority())
