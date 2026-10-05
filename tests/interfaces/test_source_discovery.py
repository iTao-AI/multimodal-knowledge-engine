from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from mke.application import KnowledgeEngine
from mke.interfaces import source_discovery
from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.interfaces.mcp_server import build_mcp_server
from mke.runtime import RuntimeConfig
from scripts.mcp_context_completeness_consumer import tool_snapshot
from tests.source_discovery_support import publish_pages


def call(config: McpRuntimeConfig, operation: str, raw: object) -> dict[str, Any]:
    from mke.interfaces.source_schemas import BrowseSourceEvidenceV1Request, ListSourcesV1Request

    request = (
        ListSourcesV1Request if operation == "list_sources_v1" else BrowseSourceEvidenceV1Request
    )(root=raw)
    return getattr(source_discovery, operation)(config, request).model_dump(mode="json")


def test_native_inventory_keeps_historical_ten_tools_byte_equivalent(tmp_path: Path) -> None:
    server = build_mcp_server(McpRuntimeConfig(RuntimeConfig(tmp_path / "mke.sqlite"), tmp_path))
    actual = {tool.name: tool_snapshot(tool) for tool in asyncio.run(server.list_tools())}
    old = json.loads(
        Path("tests/fixtures/mcp-context-completeness-v1/mcp-tool-schemas.json").read_text()
    )["tools"]
    assert set(actual) == set(old) | {
        "list_sources_v1", "browse_source_evidence_v1",
        "list_sources_v2", "browse_source_evidence_v2",
    }
    assert {name: actual[name] for name in old} == old
    for name in ("list_sources_v1", "browse_source_evidence_v1"):
        tool = actual[name]
        assert tool["annotations"]["readOnlyHint"] is True
        assert tool["annotations"]["openWorldHint"] is False
        assert tool["inputSchema"]["required"] == ["request"]
        assert tool["outputSchema"]


def test_catalog_browse_budget_pagination_and_exact_read(tmp_path: Path) -> None:
    from mke.interfaces.mcp_completeness_contract import read_evidence_v1
    from mke.interfaces.mcp_schemas import ReadEvidenceV1Request

    database = tmp_path / "mke.sqlite"
    texts = ("三🙂" * 1000,) * 20
    source, publication = publish_pages(database, texts, name="/private/secret/large.pdf")
    config = McpRuntimeConfig(RuntimeConfig(database), tmp_path)
    catalog = call(config, "list_sources_v1", {})
    assert catalog["schema_version"] == "mke.list_sources_response.v1"
    assert catalog["sources"][0]["display_name"] == "large.pdf"
    assert "/private/" not in json.dumps(catalog)
    assert catalog["selection"] == {"status": "complete", "returned": 1}
    request: dict[str, Any] = {"source_id": source, "publication_id": publication, "page_size": 20}
    entries: list[dict[str, Any]] = []
    sizes: list[int] = []
    while True:
        result = call(config, "browse_source_evidence_v1", request)
        assert result["ok"] is True, result
        assert result["schema_version"] == "mke.browse_source_evidence_response.v1"
        assert len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode()) <= 32768
        assert sum(len(item["excerpt"]["text"].encode()) for item in result["entries"]) <= 16384
        assert result["output"]["incomplete_excerpt_count"] == len(result["entries"])
        sizes.append(len(result["entries"]))
        entries.extend(result["entries"])
        if result["selection"]["status"] == "complete":
            break
        request = {"cursor": result["selection"]["next_cursor"]}
    assert len(sizes) > 1 and sizes[0] < 20
    assert [item["evidence"]["locator"]["start"] for item in entries] == list(range(1, 21))
    evidence = entries[0]["evidence"]
    request = {"evidence_id": evidence["evidence_id"], "max_bytes": 101}
    chunks: list[str] = []
    while True:
        result = read_evidence_v1(config, ReadEvidenceV1Request(root=request)).model_dump(
            mode="json"
        )
        assert result["ok"] is True
        assert result["evidence"] == evidence
        assert result["content"]["offset_bytes"] == len("".join(chunks).encode())
        chunks.append(result["content"]["text"])
        if result["complete"]:
            break
        request = {"cursor": result["next_cursor"]}
    assert "".join(chunks) == texts[0]
    assert (
        evidence["evidence_text_sha256"]
        == "sha256:" + hashlib.sha256(texts[0].encode()).hexdigest()
    )


@pytest.mark.parametrize(
    "operation,raw",
    [("list_sources_v1", {"page_size": value}) for value in (0, 21, True, "2")]
    + [
        ("list_sources_v1", {"cursor": "garbage", "page_size": 2}),
        ("browse_source_evidence_v1", {"source_id": "", "publication_id": "pub"}),
        (
            "browse_source_evidence_v1",
            {
                "source_id": "src",
                "publication_id": "pub",
                "locator_range": {"kind": "page", "start": 0, "end": 2},
            },
        ),
        (
            "browse_source_evidence_v1",
            {
                "source_id": "src",
                "publication_id": "pub",
                "locator_range": {"kind": "timestamp_ms", "start": 2, "end": 2},
            },
        ),
    ],
)
def test_invalid_requests_are_bounded(tmp_path: Path, operation: str, raw: object) -> None:
    config = McpRuntimeConfig(RuntimeConfig(tmp_path / "mke.sqlite"), tmp_path)
    result = call(config, operation, raw)
    assert result["ok"] is False and result["problem"] == "invalid_request"
    assert len(json.dumps(result)) < 2048


def test_cursor_owner_library_tool_tampering_and_changed_authority(tmp_path: Path) -> None:
    database = tmp_path / "mke.sqlite"
    source, publication = publish_pages(database, ("one", "two"))
    publish_pages(database, ("another",), fingerprint="b")
    config = McpRuntimeConfig(RuntimeConfig(database), tmp_path)
    initial = call(config, "list_sources_v1", {"page_size": 1})
    token = initial["selection"]["next_cursor"]
    assert call(config, "list_sources_v1", {"cursor": token})["selection"]["status"] == "complete"
    assert (
        call(config, "browse_source_evidence_v1", {"cursor": token})["problem"] == "invalid_cursor"
    )
    assert (
        call(config, "list_sources_v1", {"cursor": token[:-3] + "xxx"})["problem"]
        == "invalid_cursor"
    )
    restarted = replace(config, runtime=RuntimeConfig(database))
    assert call(restarted, "list_sources_v1", {"cursor": token})["problem"] == "cursor_expired"
    copied = tmp_path / "copied.sqlite"
    shutil.copyfile(database, copied)
    foreign = replace(config, runtime=replace(config.runtime, db_path=copied))
    assert call(foreign, "list_sources_v1", {"cursor": token})["problem"] == "invalid_cursor"
    browse = call(
        config,
        "browse_source_evidence_v1",
        {
            "source_id": source,
            "publication_id": publication,
            "page_size": 1,
        },
    )
    browse_token = browse["selection"]["next_cursor"]
    engine = KnowledgeEngine(database)
    try:
        from mke.domain import (
            PDF_EXTRACTOR_FINGERPRINT,
            REQUIRED_PDF_STAGES,
            CandidateEvidence,
            RunManifest,
        )

        run = engine.create_run(source)
        engine.persist_validated_candidate(
            run.run_id,
            [
                CandidateEvidence("ev_" + "f" * 32, "page", 1, 1, "replacement"),
            ],
            RunManifest(
                run.run_id,
                1,
                tuple(sorted(REQUIRED_PDF_STAGES)),
                PDF_EXTRACTOR_FINGERPRINT,
                "a" * 64,
            ),
        )
        engine.activate_publication(run.run_id)
    finally:
        engine.close()
    assert call(config, "list_sources_v1", {"cursor": token})["problem"] == "cursor_expired"
    assert (
        call(config, "browse_source_evidence_v1", {"cursor": browse_token})["problem"]
        == "cursor_expired"
    )


def test_unknown_pairs_wrong_ranges_and_zero_matches(tmp_path: Path) -> None:
    database = tmp_path / "mke.sqlite"
    source, publication = publish_pages(database, ("one", "two"))
    config = McpRuntimeConfig(RuntimeConfig(database), tmp_path)
    for selected in ((source, "pub_wrong"), ("src_wrong", publication)):
        result = call(
            config,
            "browse_source_evidence_v1",
            {
                "source_id": selected[0],
                "publication_id": selected[1],
            },
        )
        assert result["problem"] == "evidence_not_found"
    for locator, expected in (
        ({"kind": "timestamp_ms", "start": 0, "end": 1}, "invalid_request"),
        ({"kind": "page", "start": 20, "end": 30}, None),
    ):
        result = call(
            config,
            "browse_source_evidence_v1",
            {
                "source_id": source,
                "publication_id": publication,
                "locator_range": locator,
            },
        )
        if expected:
            assert result["problem"] == expected
        else:
            assert result["selection"] == {"status": "complete", "returned": 0}


def test_oversized_metadata_maps_public_error(tmp_path: Path) -> None:
    database = tmp_path / "mke.sqlite"
    publish_pages(database, ("one",), name="/private/secret/" + "a" * 40000 + ".pdf")
    config = McpRuntimeConfig(RuntimeConfig(database), tmp_path)
    result = call(config, "list_sources_v1", {})
    assert result["problem"] == "response_too_large"
    assert "private" not in json.dumps(result) and len(json.dumps(result)) < 2048


def test_oversized_cursor_has_existing_cursor_recovery(tmp_path: Path) -> None:
    config = McpRuntimeConfig(RuntimeConfig(tmp_path / "mke.sqlite"), tmp_path)
    for operation in ("list_sources_v1", "browse_source_evidence_v1"):
        result = call(config, operation, {"cursor": "x" * 4097})
        assert result["problem"] == "invalid_cursor"
        assert result["next_step"] == "restart_from_initial_call"


def test_corrupt_authority_maps_internal_error_without_exception_text(tmp_path: Path) -> None:
    import sqlite3

    database = tmp_path / "mke.sqlite"
    source, publication = publish_pages(database, ("one",))
    with sqlite3.connect(database) as connection:
        connection.execute("DELETE FROM libraries")
    config = McpRuntimeConfig(RuntimeConfig(database), tmp_path)
    for operation, request in (
        ("list_sources_v1", {}),
        ("browse_source_evidence_v1", {"source_id": source, "publication_id": publication}),
    ):
        result = call(config, operation, request)
        assert result["problem"] == "internal_error"
        assert result["cause"] == "operation failed; details were redacted"


def test_catalog_default_ten_and_twenty_boundary(tmp_path: Path) -> None:
    database = tmp_path / "mke.sqlite"
    for fingerprint in "123456789ab":
        publish_pages(database, ("text",), fingerprint=fingerprint)
    config = McpRuntimeConfig(RuntimeConfig(database), tmp_path)
    first = call(config, "list_sources_v1", {})
    assert len(first["sources"]) == 10
    assert first["selection"]["status"] == "more_available"
    last = call(config, "list_sources_v1", {"cursor": first["selection"]["next_cursor"]})
    assert last["selection"] == {"status": "complete", "returned": 1}
    combined = first["sources"] + last["sources"]
    assert len({item["source_id"] for item in combined}) == 11
    twenty = call(config, "list_sources_v1", {"page_size": 20})
    assert twenty["selection"] == {"status": "complete", "returned": 11}
    assert twenty["sources"] == combined


def test_forged_browse_route_is_authenticated_before_unknown_source_use(tmp_path: Path) -> None:
    import base64

    database = tmp_path / "mke.sqlite"
    source, publication = publish_pages(database, ("one", "two"))
    config = McpRuntimeConfig(RuntimeConfig(database), tmp_path)
    initial = call(
        config,
        "browse_source_evidence_v1",
        {
            "source_id": source,
            "publication_id": publication,
            "page_size": 1,
        },
    )
    token = initial["selection"]["next_cursor"]
    envelope = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
    encoded = envelope["payload"]
    payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    payload["source_id"] = "src_does_not_exist"
    envelope["payload"] = (
        base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    )
    forged = base64.urlsafe_b64encode(json.dumps(envelope).encode()).decode().rstrip("=")
    result = call(config, "browse_source_evidence_v1", {"cursor": forged})
    assert result["problem"] == "invalid_cursor"
