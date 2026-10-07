from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from mcp.types import CallToolResult, TextContent

from mke.interfaces.mcp_schemas import ActiveAuthoritySnapshotV1, SearchMatchV2


def sdk_result(payload: dict[str, Any]) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))],
        structuredContent=payload,
    )


class ScriptedSession:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.requests: list[dict[str, Any]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        assert name == "read_evidence_v1" and arguments is not None
        self.requests.append(arguments["request"])
        assert self.responses, "consumer read beyond the declared Evidence"
        return sdk_result(self.responses.pop(0))


def read_fixture() -> tuple[SearchMatchV2, ActiveAuthoritySnapshotV1, list[dict[str, Any]]]:
    text = '前🙂引文\n"needle"尾'
    encoded = text.encode()
    excerpt = '引文\n"needle"'
    start = len("前🙂".encode())
    descriptor = {
        "evidence_id": "ev_selected",
        "source_id": "src_selected",
        "content_fingerprint": "sha256:" + "a" * 64,
        "publication_id": "pub_selected",
        "publication_revision": 1,
        "run_id": "run_selected",
        "locator": {"kind": "page", "start": 2, "end": 2},
        "evidence_text_sha256": "sha256:" + hashlib.sha256(encoded).hexdigest(),
        "original_utf8_bytes": len(encoded),
    }
    authority = {
        "schema_version": "mke.active_authority_snapshot.v1",
        "active_set_fingerprint": "sha256:" + "b" * 64,
        "observation": {
            "schema_version": "mke.active_publication_observation.v1",
            "library_id": "local",
            "state": "active",
            "source_count": 1,
            "active_publication_count": 1,
            "active_evidence_count": 1,
        },
    }
    match = SearchMatchV2.model_validate(
        {
            "evidence": descriptor,
            "excerpt": {
                "kind": "query_window",
                "text": excerpt,
                "start_utf8_byte": start,
                "end_utf8_byte": start + len(excerpt.encode()),
                "prefix_omitted": True,
                "suffix_omitted": True,
                "complete": False,
                "returned_utf8_bytes": len(excerpt.encode()),
                "content_trust": "untrusted_evidence",
            },
            "read": {"tool": "read_evidence_v1", "evidence_id": "ev_selected"},
        }
    )
    chunks: list[str] = []
    pending = ""
    for char in text:
        if len((pending + char).encode()) > 4:
            chunks.append(pending)
            pending = ""
        pending += char
    chunks.append(pending)
    offset = 0
    responses: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks):
        responses.append(
            {
                "schema_version": "mke.read_evidence_response.v1",
                "ok": True,
                "authority_snapshot": copy.deepcopy(authority),
                "evidence": copy.deepcopy(descriptor),
                "content": {
                    "text": chunk,
                    "offset_bytes": offset,
                    "returned_utf8_bytes": len(chunk.encode()),
                    "content_trust": "untrusted_evidence",
                },
                "complete": index == len(chunks) - 1,
                "next_cursor": None if index == len(chunks) - 1 else f"read_{index + 1}",
            }
        )
        offset += len(chunk.encode())
    return match, ActiveAuthoritySnapshotV1.model_validate(authority), responses


def test_unicode_exact_read_stream_verifies_excerpt_across_chunk_boundaries() -> None:
    from scripts.source_evidence_consumer import verify_read

    match, authority, responses = read_fixture()
    session = ScriptedSession(responses)
    verified = asyncio.run(verify_read(session, match, authority, max_bytes=4))
    assert verified == {
        "evidence": match.evidence.model_dump(mode="json"),
        "read": match.read.model_dump(mode="json"),
        "verified_utf8_bytes": match.evidence.original_utf8_bytes,
        "exact_text_sha256_verified": True,
        "excerpt_window_verified": True,
    }
    assert session.requests[0] == {"evidence_id": "ev_selected", "max_bytes": 4}
    assert all(set(request) == {"cursor"} for request in session.requests[1:])


@pytest.mark.parametrize(
    "field",
    [
        "evidence_id",
        "source_id",
        "publication_id",
        "publication_revision",
        "run_id",
        "content_fingerprint",
        "locator",
        "evidence_text_sha256",
        "original_utf8_bytes",
    ],
)
def test_read_rejects_any_changed_citation_field(field: str) -> None:
    from scripts.source_evidence_consumer import ConsumerFailure, verify_read

    match, authority, responses = read_fixture()
    descriptor = responses[1]["evidence"]
    value = descriptor[field]
    descriptor[field] = (
        value + 1
        if type(value) is int
        else {"kind": "page", "start": 3, "end": 3}
        if field == "locator"
        else "sha256:" + "c" * 64
        if field.endswith("fingerprint") or field.endswith("sha256")
        else "changed"
    )
    with pytest.raises(ConsumerFailure):
        asyncio.run(verify_read(ScriptedSession(responses), match, authority, max_bytes=4))


@pytest.mark.parametrize(
    "mutation", ["authority", "offset", "bytes", "text", "early_terminal", "repeat_cursor"]
)
def test_read_rejects_incoherent_stream(mutation: str) -> None:
    from scripts.source_evidence_consumer import ConsumerFailure, verify_read

    match, authority, responses = read_fixture()
    if mutation == "authority":
        responses[1]["authority_snapshot"]["active_set_fingerprint"] = "sha256:" + "c" * 64
    elif mutation == "offset":
        responses[1]["content"]["offset_bytes"] += 1
    elif mutation == "bytes":
        responses[1]["content"]["returned_utf8_bytes"] -= 1
    elif mutation == "text":
        responses[1]["content"]["text"] = "abcd"
    elif mutation == "early_terminal":
        responses[1]["complete"] = True
        responses[1]["next_cursor"] = None
    else:
        responses[1]["next_cursor"] = responses[0]["next_cursor"]
    with pytest.raises(ConsumerFailure):
        asyncio.run(verify_read(ScriptedSession(responses), match, authority, max_bytes=4))


@pytest.mark.parametrize("mutation", ["text", "start", "bytes", "prefix", "complete"])
def test_read_rejects_incoherent_excerpt_window(mutation: str) -> None:
    from scripts.source_evidence_consumer import ConsumerFailure, verify_read

    match, authority, responses = read_fixture()
    payload = match.model_dump(mode="json")
    excerpt = payload["excerpt"]
    if mutation == "text":
        excerpt["text"] = excerpt["text"].replace("needle", "foobar")
    elif mutation == "start":
        excerpt["start_utf8_byte"] += 1
        excerpt["end_utf8_byte"] += 1
    elif mutation == "bytes":
        excerpt["returned_utf8_bytes"] -= 1
    elif mutation == "prefix":
        excerpt["prefix_omitted"] = False
    else:
        excerpt["complete"] = True
    with pytest.raises(ConsumerFailure):
        asyncio.run(
            verify_read(
                ScriptedSession(responses),
                SearchMatchV2.model_validate(payload),
                authority,
                max_bytes=4,
            )
        )


@pytest.mark.parametrize("mutation", ["text", "missing", "error", "extra", "model", "sdk"])
def test_transport_requires_agreeing_bounded_structured_and_text_payloads(mutation: str) -> None:
    from scripts.source_evidence_consumer import ConsumerFailure, checked_call

    _, _, responses = read_fixture()
    result = sdk_result(responses[0])
    if mutation == "text":
        result.content = [TextContent(type="text", text="{}")]
    elif mutation == "missing":
        result.structuredContent = None
    elif mutation == "error":
        result.isError = True
    elif mutation == "extra":
        result.content.append(TextContent(type="text", text="extra"))
    elif mutation == "model":
        result = sdk_result({"untrusted": "x" * 32769})
    else:
        result = CallToolResult.model_validate(
            {
                **result.model_dump(by_alias=True),
                "_meta": {"large": "x" * (96 * 1024)},
            }
        )

    class Session:
        async def call_tool(
            self,
            name: str,
            arguments: dict[str, Any] | None = None,
        ) -> CallToolResult:
            return result

    with pytest.raises(ConsumerFailure):
        asyncio.run(checked_call(Session(), "read_evidence_v1", {}))


def test_consumer_imports_public_dtos_and_sdk_without_producer_or_storage_logic() -> None:
    script = Path("scripts/source_evidence_consumer.py")
    tree = ast.parse(script.read_text())
    modules = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(
        module.startswith(("mke.application", "mke.runtime", "mke.storage", "tests"))
        for module in modules
    )
    assert "mcp.client.stdio" in modules
