from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import replace
from pathlib import Path

import pytest

from mke.application import KnowledgeEngine
from mke.application.mcp_cursor import (
    ReadCursorPayload,
    SearchCursorPayload,
    encode_read_cursor,
    encode_search_cursor,
)
from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    ActiveAuthoritySnapshot,
    ActivePublicationObservation,
    CandidateEvidence,
    RunManifest,
)
from mke.interfaces.mcp_contract import McpRuntimeConfig, search_library_v1
from mke.interfaces.mcp_schemas import (
    SearchLibrarySuccessV2,
    SearchSelectionCappedV2,
    SearchSelectionMoreV2,
)
from mke.interfaces.mcp_server import build_mcp_server
from mke.runtime import RuntimeConfig
from mke.runtime_owner import OwnerRuntimeState


def test_search_exposes_selection_completeness(tmp_path: Path) -> None:
    server = build_mcp_server(
        McpRuntimeConfig(RuntimeConfig(tmp_path / "mke.sqlite"), tmp_path)
    )

    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}

    assert "search_library_v2" in tools


def test_v2_search_returns_retrieval_authority_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mke.interfaces.mcp_completeness_contract as contract
    from mke.interfaces.mcp_schemas import SearchLibraryV2Request
    from mke.retrieval.errors import RetrievalAuthorityError

    class InvalidAuthorityEngine:
        def search_evidence_page(
            self, *args: object, **kwargs: object
        ) -> object:
            del args, kwargs
            raise RetrievalAuthorityError

        def close(self) -> None:
            return None

    def build_invalid(_runtime: RuntimeConfig) -> InvalidAuthorityEngine:
        return InvalidAuthorityEngine()

    monkeypatch.setattr(contract, "build_engine", build_invalid)
    config = McpRuntimeConfig(RuntimeConfig(tmp_path / "mke.sqlite"), tmp_path)

    response = contract.search_library_v2(
        config,
        SearchLibraryV2Request(root={"query": "redacted query", "limit": 5}),
    )

    assert response.root.problem == "retrieval_authority_invalid"  # type: ignore[union-attr]
    assert response.root.cause == (  # type: ignore[union-attr]
        "active retrieval candidates contain duplicate stable Evidence locators"
    )
    assert response.root.next_step == (  # type: ignore[union-attr]
        "restore_valid_database_or_reingest_into_new_database"
    )


def test_oversized_v1_has_typed_exact_read_recovery(tmp_path: Path) -> None:
    config = McpRuntimeConfig(RuntimeConfig(tmp_path / "mke.sqlite"), tmp_path)
    engine = KnowledgeEngine(config.db_path)
    try:
        _publish_text(engine, ("prefix " + "x" * 1_000_001 + " late marker",))
    finally:
        engine.close()

    search = search_library_v1(config, "late marker", limit=1)

    assert search.root.problem == "response_too_large"  # type: ignore[union-attr]
    assert search.root.next_step == "use_search_library_v2"  # type: ignore[union-attr]


def test_cjk_cap_is_observable(tmp_path: Path) -> None:
    from mke.interfaces.mcp_completeness_contract import search_library_v2
    from mke.interfaces.mcp_schemas import SearchLibraryV2Request

    config = McpRuntimeConfig(
        RuntimeConfig(
            tmp_path / "mke.sqlite",
            retrieval_strategy="cjk-active-scan-overlap-v1",
        ),
        tmp_path,
    )
    engine = KnowledgeEngine(
        config.db_path,
        retrieval_strategy="cjk-active-scan-overlap-v1",
    )
    try:
        _publish_text(
            engine,
            tuple(f"完整性上下文预算 第 {index} 条证据" for index in range(1, 12)),
        )
    finally:
        engine.close()

    response = search_library_v2(
        config,
        SearchLibraryV2Request(root={"query": "完整性上下文预算", "limit": 5}),
    )
    assert isinstance(response.root, SearchLibrarySuccessV2)
    while isinstance(response.root.selection, SearchSelectionMoreV2):
        response = search_library_v2(
            config,
            SearchLibraryV2Request(
                root={"cursor": response.root.selection.next_cursor}
            ),
        )
        assert isinstance(response.root, SearchLibrarySuccessV2)

    assert isinstance(response.root.selection, SearchSelectionCappedV2)
    assert response.root.selection.limit_reason == "retrieval_strategy_cap"


def test_cjk_query_window_maps_whitespace_insensitive_scorer_match(
    tmp_path: Path,
) -> None:
    from mke.interfaces.mcp_completeness_contract import search_library_v2
    from mke.interfaces.mcp_schemas import (
        SearchLibrarySuccessV2,
        SearchLibraryV2Request,
    )

    marker = "发 布 证 据 检 索"
    text = "前缀" * 1500 + marker + "后缀" * 1500
    config = McpRuntimeConfig(
        RuntimeConfig(
            tmp_path / "mke.sqlite",
            retrieval_strategy="cjk-active-scan-overlap-v1",
        ),
        tmp_path,
    )
    engine = KnowledgeEngine(
        config.db_path,
        retrieval_strategy="cjk-active-scan-overlap-v1",
    )
    try:
        _publish_text(engine, (text,))
    finally:
        engine.close()

    response = search_library_v2(
        config,
        SearchLibraryV2Request(root={"query": "发布证据检索", "limit": 1}),
    )

    assert isinstance(response.root, SearchLibrarySuccessV2)
    excerpt = response.root.matches[0].excerpt
    assert excerpt.kind == "query_window"
    assert marker in excerpt.text
    assert (
        text.encode()[excerpt.start_utf8_byte : excerpt.end_utf8_byte].decode()
        == excerpt.text
    )


def test_fts_query_window_maps_token_separator_phrase_match(
    tmp_path: Path,
) -> None:
    from mke.interfaces.mcp_completeness_contract import search_library_v2
    from mke.interfaces.mcp_schemas import (
        SearchLibrarySuccessV2,
        SearchLibraryV2Request,
    )

    marker = "560,033,202,243"
    text = "前缀" * 1500 + f" {marker} " + "后缀" * 1500
    config = McpRuntimeConfig(RuntimeConfig(tmp_path / "mke.sqlite"), tmp_path)
    engine = KnowledgeEngine(config.db_path)
    try:
        _publish_text(engine, (text,))
    finally:
        engine.close()

    response = search_library_v2(
        config,
        SearchLibraryV2Request(root={"query": "560033202243", "limit": 1}),
    )

    assert isinstance(response.root, SearchLibrarySuccessV2)
    excerpt = response.root.matches[0].excerpt
    assert excerpt.kind == "query_window"
    assert marker in excerpt.text
    assert (
        text.encode()[excerpt.start_utf8_byte : excerpt.end_utf8_byte].decode()
        == excerpt.text
    )


def test_blank_search_v2_is_rejected_before_engine_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mke.interfaces.mcp_completeness_contract as contract
    from mke.interfaces.mcp_schemas import SearchLibraryV2Request

    called = False

    def fail_build(_runtime: RuntimeConfig) -> KnowledgeEngine:
        nonlocal called
        called = True
        raise AssertionError("blank query must not open the engine")

    monkeypatch.setattr(contract, "build_engine", fail_build)
    response = contract.search_library_v2(
        McpRuntimeConfig(RuntimeConfig(tmp_path / "mke.sqlite"), tmp_path),
        SearchLibraryV2Request(root={"query": "   ", "limit": 1}),
    )

    assert response.root.problem == "invalid_request"  # type: ignore[union-attr]
    assert called is False


@pytest.mark.parametrize(
    ("case", "expected_problem"),
    (
        ("bad_mac", "invalid_cursor"),
        ("old_epoch", "cursor_expired"),
        ("active_drift", "cursor_expired"),
        ("policy_drift", "cursor_expired"),
        ("query_fingerprint", "invalid_cursor"),
        ("wrong_tool", "invalid_cursor"),
        ("wrong_schema", "invalid_cursor"),
    ),
)
def test_cursor_validation_observes_authority_before_trusted_bindings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    expected_problem: str,
) -> None:
    import mke.interfaces.mcp_completeness_contract as contract
    from mke.interfaces.mcp_schemas import SearchLibraryV2Request

    owner = OwnerRuntimeState(cursor_key=b"k" * 32, owner_epoch="a" * 32)
    config = McpRuntimeConfig(
        RuntimeConfig(tmp_path / "mke.sqlite", owner_state=owner),
        tmp_path,
    )
    authority = ActiveAuthoritySnapshot(
        ActivePublicationObservation("local", "active", 1, 1, 1),
        "sha256:" + "b" * 64,
    )
    payload = SearchCursorPayload(
        "mke.mcp_cursor.v1",
        "search_library_v2",
        owner.cursor_material().epoch,
        authority.active_set_fingerprint,
        "authority",
        "sha256:" + __import__("hashlib").sha256(b"authority").hexdigest(),
        "sqlite-fts-v1",
        1,
        "numeric-grouping-v1",
        1,
        1,
        5,
        "mke.search_library_response.v2",
    )
    if case == "old_epoch":
        payload = replace(payload, owner_epoch="c" * 32)
    elif case == "active_drift":
        payload = replace(payload, active_set_fingerprint="sha256:" + "d" * 64)
    elif case == "policy_drift":
        payload = replace(payload, strategy_revision=2)
    elif case == "query_fingerprint":
        payload = replace(payload, query_fingerprint="sha256:" + "e" * 64)
    elif case == "wrong_schema":
        payload = replace(  # type: ignore[arg-type]
            payload, response_schema="mke.search_library_response.v999"
        )
    if case == "wrong_tool":
        read = ReadCursorPayload(
            "mke.mcp_cursor.v1",
            "read_evidence_v1",
            owner.cursor_material().epoch,
            authority.active_set_fingerprint,
            "ev_" + "1" * 32,
            "src_" + "2" * 32,
            "sha256:" + "3" * 64,
            "pub_" + "4" * 32,
            1,
            "run_" + "5" * 32,
            "page",
            1,
            1,
            "sha256:" + "6" * 64,
            100,
            4,
            16,
            "mke.read_evidence_response.v1",
        )
        token = encode_read_cursor(owner.cursor_material(), read)
    else:
        token = encode_search_cursor(owner.cursor_material(), payload)
    if case == "bad_mac":
        envelope = json.loads(_decode_b64(token))
        envelope["mac"] = (
            "A" if not str(envelope["mac"]).startswith("A") else "B"
        ) + str(envelope["mac"])[1:]
        token = _encode_b64(
            json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode()
        )

    class FakeEngine:
        authority_calls = 0
        selection_calls = 0

        def search_evidence_page(self, *args: object, **kwargs: object) -> None:
            del args
            validator = kwargs["authority_validator"]
            assert callable(validator)
            self.authority_calls += 1
            validator(authority)
            self.selection_calls += 1
            raise AssertionError("invalid continuation must not select")

        def close(self) -> None:
            pass

    fake = FakeEngine()

    def build_fake(_runtime: RuntimeConfig) -> FakeEngine:
        return fake

    monkeypatch.setattr(contract, "build_engine", build_fake)
    response = contract.search_library_v2(
        config,
        SearchLibraryV2Request(root={"cursor": token}),
    )

    assert response.root.problem == expected_problem  # type: ignore[union-attr]
    assert fake.authority_calls == 1
    assert fake.selection_calls == 0


def test_revision_one_search_cursor_is_discarded_before_new_initial_query(
    tmp_path: Path,
) -> None:
    import hashlib

    from mke.interfaces.mcp_completeness_contract import search_library_v2
    from mke.interfaces.mcp_schemas import SearchLibraryV2Request

    owner = OwnerRuntimeState(cursor_key=b"k" * 32, owner_epoch="a" * 32)
    config = McpRuntimeConfig(
        RuntimeConfig(tmp_path / "mke.sqlite", owner_state=owner),
        tmp_path,
    )
    engine = KnowledgeEngine(config.db_path)
    observed: list[ActiveAuthoritySnapshot] = []
    try:
        _publish_text(engine, ("authority first", "authority second"))
        engine.search_evidence_page(
            "authority",
            position=0,
            page_size=1,
            authority_validator=observed.append,
        )
    finally:
        engine.close()
    assert len(observed) == 1
    old_payload = SearchCursorPayload(
        "mke.mcp_cursor.v1",
        "search_library_v2",
        owner.cursor_material().epoch,
        observed[0].active_set_fingerprint,
        "authority",
        "sha256:" + hashlib.sha256(b"authority").hexdigest(),
        "cjk-active-scan-overlap-v1",
        1,
        "numeric-grouping-v1",
        1,
        1,
        1,
        "mke.search_library_response.v2",
    )

    expired = search_library_v2(
        config,
        SearchLibraryV2Request(
            root={
                "cursor": encode_search_cursor(
                    owner.cursor_material(),
                    old_payload,
                )
            }
        ),
    )

    assert expired.root.problem == "cursor_expired"  # type: ignore[union-attr]
    assert expired.root.cause == "retrieval policy changed"  # type: ignore[union-attr]
    assert expired.root.next_step == (  # type: ignore[union-attr]
        "repeat_search_under_current_strategy"
    )

    restarted = search_library_v2(
        config,
        SearchLibraryV2Request(root={"query": "authority", "limit": 1}),
    )

    assert isinstance(restarted.root, SearchLibrarySuccessV2)
    assert len(restarted.root.matches) == 1


def test_malformed_cursor_has_zero_engine_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import mke.interfaces.mcp_completeness_contract as contract
    from mke.interfaces.mcp_schemas import SearchLibraryV2Request

    calls = 0

    def build(_runtime: RuntimeConfig) -> KnowledgeEngine:
        nonlocal calls
        calls += 1
        raise AssertionError("malformed cursor must not open the engine")

    monkeypatch.setattr(contract, "build_engine", build)
    response = contract.search_library_v2(
        McpRuntimeConfig(RuntimeConfig(tmp_path / "mke.sqlite"), tmp_path),
        SearchLibraryV2Request(root={"cursor": "not-a-cursor"}),
    )

    assert response.root.problem == "invalid_cursor"  # type: ignore[union-attr]
    assert calls == 0


def test_read_cursor_round_trip_continues_with_server_issued_token(
    tmp_path: Path,
) -> None:
    from mke.interfaces.mcp_completeness_contract import read_evidence_v1
    from mke.interfaces.mcp_schemas import (
        ReadEvidenceSuccessV1,
        ReadEvidenceV1Request,
    )

    config = McpRuntimeConfig(RuntimeConfig(tmp_path / "mke.sqlite"), tmp_path)
    engine = KnowledgeEngine(config.db_path)
    try:
        _publish_text(engine, ("x" * 20_000,))
    finally:
        engine.close()

    first = read_evidence_v1(
        config,
        ReadEvidenceV1Request(
            root={"evidence_id": "ev_00000000000000000000000000000001"}
        ),
    )
    assert isinstance(first.root, ReadEvidenceSuccessV1)
    assert first.root.complete is False
    assert first.root.next_cursor is not None

    continued = read_evidence_v1(
        config,
        ReadEvidenceV1Request(root={"cursor": first.root.next_cursor}),
    )

    assert isinstance(continued.root, ReadEvidenceSuccessV1)
    assert continued.root.content.offset_bytes == 16_384
    assert continued.root.complete is True


def _encode_b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _decode_b64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _publish_text(engine: KnowledgeEngine, pages: tuple[str, ...]) -> None:
    source = engine.ensure_source(display_name="context.pdf", asset_sha256="a" * 64)
    run = engine.create_run(source.source_id)
    evidence = [
        CandidateEvidence(
            evidence_id=f"ev_{index:032x}",
            locator_kind="page",
            locator_start=index,
            locator_end=index,
            text=text,
        )
        for index, text in enumerate(pages, start=1)
    ]
    engine.persist_validated_candidate(
        run.run_id,
        evidence,
        RunManifest(
            run_id=run.run_id,
            evidence_count=len(evidence),
            required_stages=tuple(sorted(REQUIRED_PDF_STAGES)),
            extractor_fingerprint=PDF_EXTRACTOR_FINGERPRINT,
            asset_sha256="a" * 64,
        ),
    )
    engine.activate_publication(run.run_id)
