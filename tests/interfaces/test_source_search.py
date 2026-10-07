from __future__ import annotations

import base64
import json
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from mke.interfaces.mcp_completeness_contract import search_library_v2
from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.interfaces.mcp_schemas import SearchLibraryV2Request
from mke.runtime import RuntimeConfig
from tests.source_discovery_support import publish_pages


def call(config: McpRuntimeConfig, request: dict[str, object]) -> dict[str, Any]:
    from mke.interfaces.source_search import search_source_evidence_v1
    from mke.interfaces.source_search_schemas import SearchSourceEvidenceV1Request

    return search_source_evidence_v1(
        config,
        SearchSourceEvidenceV1Request(root=request),
    ).model_dump(mode="json")


def setup(
    root: Path, *, text: str = "needle", count: int = 13
) -> tuple[
    McpRuntimeConfig,
    dict[str, object],
]:
    database = root / "mke.sqlite"
    source, publication = publish_pages(database, (text,) * count, fingerprint="f")
    publish_pages(database, (text,) * 20, fingerprint="a")
    return McpRuntimeConfig(RuntimeConfig(database), root), {
        "source_id": source,
        "publication_id": publication,
        "query": "needle",
        "limit": 3,
    }


def test_public_scope_complete_pagination_and_every_citation(tmp_path: Path) -> None:
    config, initial = setup(tmp_path)
    try:
        page = call(config, initial)
        scope = page["scope"]
        authority = page["authority_snapshot"]
        found: list[dict[str, Any]] = []
        cursors: set[str] = set()
        while True:
            assert page["ok"] is True
            assert page["schema_version"] == "mke.search_source_evidence_response.v1"
            assert page["scope"] == scope and page["authority_snapshot"] == authority
            for item in page["matches"]:
                evidence = item["evidence"]
                assert {field: evidence[field] for field in scope if field != "schema_version"} == {
                    field: value for field, value in scope.items() if field != "schema_version"
                }
                assert item["read"]["evidence_id"] == evidence["evidence_id"]
                found.append(evidence)
            if page["selection"]["status"] == "complete":
                break
            cursor = page["selection"]["next_cursor"]
            assert cursor not in cursors and page["selection"]["returned"] > 0
            cursors.add(cursor)
            page = call(config, {"cursor": cursor})
        assert [item["locator"]["start"] for item in found] == list(range(1, 14))
        assert len(cursors) == 4
        assert scope["source_id"] == initial["source_id"]
        empty = call(config, {**initial, "query": "outsideonly"})
        assert empty["ok"] is True and empty["matches"] == [] and empty["scope"] == scope
        assert empty["selection"]["status"] == "complete"
    finally:
        config.runtime.process_controller.shutdown()


@pytest.mark.parametrize(
    "patch",
    [
        {"source_id": ""},
        {"source_id": " "},
        {"source_id": True},
        {"publication_id": None},
        {"publication_id": "x" * 513},
        {"limit": 0},
        {"limit": True},
        {"limit": 21},
        {"query": " "},
        {"query": "三" * 171},
        {"cursor": "garbage"},
        {"extra": "field"},
        {"source_id": "\ud800"},
        {"publication_id": "\ud800"},
        {"query": "\ud800"},
        {"cursor": "\ud800"},
    ],
)
def test_invalid_initial_or_mixed_branches_fail(tmp_path: Path, patch: dict[str, object]) -> None:
    config, initial = setup(tmp_path)
    try:
        error = call(config, {**initial, **patch})
        assert error["ok"] is False and error["problem"] in {"invalid_request", "invalid_query"}
        assert error["active_publication_impact"] == "unchanged"
    finally:
        config.runtime.process_controller.shutdown()


def test_unknown_and_mismatched_ids_are_not_found(tmp_path: Path) -> None:
    config, initial = setup(tmp_path)
    try:
        for patch in ({"source_id": "src_missing"}, {"publication_id": "pub_missing"}):
            result = call(config, {**initial, **patch})
            assert not result["ok"] and result["problem"] == "evidence_not_found"
            assert "matches" not in result
    finally:
        config.runtime.process_controller.shutdown()


def test_cursors_reject_cross_tool_library_tampering_restart_and_policy(tmp_path: Path) -> None:
    config, initial = setup(tmp_path)
    try:
        cursor = call(config, initial)["selection"]["next_cursor"]
        old = search_library_v2(config, SearchLibraryV2Request(root={"cursor": cursor}))
        assert old.root.ok is False and old.root.problem == "invalid_cursor"
        library = search_library_v2(
            config, SearchLibraryV2Request(root={"query": "needle", "limit": 1})
        )
        assert library.root.ok is True
        other_cursor = library.model_dump(mode="json")["selection"]["next_cursor"]
        assert call(config, {"cursor": other_cursor})["problem"] == "invalid_cursor"
        assert (
            call(config, {"cursor": cursor, "query": "different"})["problem"] == "invalid_request"
        )
        assert call(config, {"cursor": cursor, "source_id": initial["source_id"]})["problem"] == (
            "invalid_request"
        )
        envelope = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        raw_bytes = base64.urlsafe_b64decode(
            envelope["payload"] + "=" * (-len(envelope["payload"]) % 4)
        )
        raw = json.loads(raw_bytes)
        assert raw["source_id"] == initial["source_id"]
        assert raw["publication_id"] == initial["publication_id"]
        assert str(tmp_path) not in raw_bytes.decode()
        raw["source_id"] = "src_other"
        envelope["payload"] = (
            base64.urlsafe_b64encode(json.dumps(raw).encode()).rstrip(b"=").decode()
        )
        tampered = base64.urlsafe_b64encode(json.dumps(envelope).encode()).rstrip(b"=").decode()
        assert call(config, {"cursor": tampered})["problem"] == "invalid_cursor"
        assert call(config, {"cursor": "garbage"})["problem"] == "invalid_cursor"
        assert call(config, {"cursor": "x" * 4097})["problem"] == "invalid_cursor"
        copied = tmp_path / "copied.sqlite"
        shutil.copy2(config.runtime.db_path, copied)
        same_owner_copy = McpRuntimeConfig(replace(config.runtime, db_path=copied), tmp_path)
        assert call(same_owner_copy, {"cursor": cursor})["problem"] == "invalid_cursor"
        changed = McpRuntimeConfig(replace(config.runtime, retrieval_strategy="current"), tmp_path)
        assert (
            call(changed, {"cursor": cursor})["next_step"] == "repeat_search_under_current_strategy"
        )
        restarted = McpRuntimeConfig(RuntimeConfig(config.runtime.db_path), tmp_path)
        try:
            assert call(restarted, {"cursor": cursor})["next_step"] == "repeat_initial_call"
        finally:
            restarted.runtime.process_controller.shutdown()
    finally:
        config.runtime.process_controller.shutdown()


def test_publication_change_expires_even_when_unselected_source_changes(tmp_path: Path) -> None:
    config, initial = setup(tmp_path)
    try:
        cursor = call(config, initial)["selection"]["next_cursor"]
        publish_pages(config.runtime.db_path, ("changed",), fingerprint="b")
        error = call(config, {"cursor": cursor})
        assert error["problem"] == "cursor_expired"
        assert error["next_step"] == "repeat_search_on_current_publications"
        assert call(config, initial)["ok"] is True
    finally:
        config.runtime.process_controller.shutdown()


@pytest.mark.parametrize(
    "patch",
    [
        {"publication_revision": 2},
        {"run_id": "run_other"},
        {"content_fingerprint": "sha256:" + "0" * 64},
    ],
)
def test_authentic_cursor_still_rejects_wrong_scope_identity(
    tmp_path: Path,
    patch: dict[str, object],
) -> None:
    from mke.application.mcp_cursor import parse_cursor_untrusted
    from mke.application.source_search_cursor import (
        SourceSearchCursorPayload,
        encode_source_search_cursor,
    )

    config, initial = setup(tmp_path)
    try:
        cursor = call(config, initial)["selection"]["next_cursor"]
        payload = parse_cursor_untrusted(cursor).raw
        payload.update(patch)
        owned = encode_source_search_cursor(
            config.runtime.owner_state.cursor_material(),
            SourceSearchCursorPayload(**cast(Any, payload)),
        )
        assert call(config, {"cursor": owned})["problem"] == "invalid_cursor"
    finally:
        config.runtime.process_controller.shutdown()


def test_full_envelope_budget_and_scope_model_rejects_foreign_citations(tmp_path: Path) -> None:
    from mke.interfaces.source_search_schemas import SearchSourceEvidenceResponseV1

    config, initial = setup(tmp_path, text='needle 三🙂"\n\\' * 1000, count=20)
    try:
        first = call(config, {**initial, "limit": 20})
        response = first
        found: list[dict[str, Any]] = []
        while True:
            assert (
                len(json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode())
                <= 32768
            )
            assert (
                sum(item["excerpt"]["returned_utf8_bytes"] for item in response["matches"]) <= 16384
            )
            assert all(not item["excerpt"]["complete"] for item in response["matches"])
            found.extend(response["matches"])
            if response["selection"]["status"] == "complete":
                break
            assert response["selection"]["returned"] > 0
            response = call(config, {"cursor": response["selection"]["next_cursor"]})
        assert len(found) == 20
        first["matches"][0]["evidence"]["source_id"] = "src_foreign"
        with pytest.raises(ValidationError):
            SearchSourceEvidenceResponseV1.model_validate(first)
    finally:
        config.runtime.process_controller.shutdown()
