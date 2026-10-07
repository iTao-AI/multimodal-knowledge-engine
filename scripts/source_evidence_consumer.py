#!/usr/bin/env python3
"""Checkout example: discover one active Source and verify its first Evidence page."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Protocol, cast

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult
from pydantic import BaseModel, ValidationError

from mke.interfaces.mcp_schemas import (
    ActiveAuthoritySnapshotV1,
    ReadEvidenceResponseV1,
    ReadEvidenceSuccessV1,
    SearchMatchV2,
)
from mke.interfaces.source_ask_schemas import ASK_LIMITATIONS, SourceAskSelectionV1
from mke.interfaces.source_schemas import (
    ListSourcesResponseV1,
    ListSourcesSuccessV1,
    SourceMetadataV1,
)
from mke.interfaces.source_search_schemas import (
    SearchSourceEvidenceResponseV1,
    SearchSourceEvidenceSuccessV1,
    SourceSearchInitialV1,
    SourceSearchScopeV1,
)
from mke.retrieval.strategy import (
    DEFAULT_RETRIEVAL_STRATEGY,
    SUPPORTED_RETRIEVAL_STRATEGIES,
    RetrievalStrategy,
)

RECEIPT_SCHEMA = "mke.source_evidence_consumer.v1"
CANONICAL_LIMIT = 32768
SDK_LIMIT = 96 * 1024


class ConsumerFailure(RuntimeError):
    """Safe local validation/recovery message; never extracted Evidence or raw SDK errors."""


class ToolSession(Protocol):
    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> CallToolResult: ...


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ConsumerFailure(message)


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def validated[T: BaseModel](model: type[T], value: dict[str, Any]) -> T:
    try:
        return model.model_validate(value)
    except ValidationError as error:
        raise ConsumerFailure("public response schema validation failed") from error


async def checked_call(
    session: ToolSession,
    tool: str,
    request: dict[str, Any],
) -> dict[str, Any]:
    result = await asyncio.wait_for(session.call_tool(tool, {"request": request}), timeout=30)
    require(not result.isError, "SDK tool error; no verified receipt")
    value = result.structuredContent
    require(isinstance(value, dict), "structured response is missing")
    payload = cast(dict[str, Any], value)
    require(len(result.content) == 1, "expected one canonical text response")
    block = result.content[0]
    require(block.type == "text", "expected canonical text response")
    if block.type != "text":
        raise ConsumerFailure("expected canonical text response")
    try:
        require(json.loads(block.text) == payload, "text and structured response disagree")
        require(len(canonical_json(payload)) <= CANONICAL_LIMIT, "response envelope exceeds budget")
    except (ValueError, UnicodeError) as error:
        raise ConsumerFailure("invalid canonical response") from error
    require(
        len(result.model_dump_json(by_alias=True, exclude_none=True).encode()) < SDK_LIMIT,
        "SDK result exceeds transport budget",
    )
    return payload


async def discover_source(
    session: ToolSession,
    source_id: str,
    publication_id: str,
) -> tuple[SourceMetadataV1, ActiveAuthoritySnapshotV1]:
    request: dict[str, Any] = {"page_size": 20}
    authority: ActiveAuthoritySnapshotV1 | None = None
    seen_sources: set[str] = set()
    seen_cursors: set[str] = set()
    while True:
        packet = validated(
            ListSourcesResponseV1,
            await checked_call(
                session,
                "list_sources_v1",
                request,
            ),
        ).root
        if not isinstance(packet, ListSourcesSuccessV1):
            raise ConsumerFailure(f"list_sources_v1: {packet.problem}; {packet.next_step}")
        if authority is None:
            authority = packet.authority_snapshot
        require(packet.authority_snapshot == authority, "authority changed during discovery")
        for source in packet.sources:
            require(source.source_id not in seen_sources, "Source discovery repeated an identity")
            seen_sources.add(source.source_id)
            if source.source_id == source_id:
                require(
                    source.publication_id == publication_id,
                    "selected Publication is not active; rediscover_source_publication",
                )
                return source, authority
        if packet.selection.status == "complete":
            raise ConsumerFailure("selected Source is not active; rediscover_source_publication")
        cursor = packet.selection.next_cursor
        require(bool(cursor) and cursor not in seen_cursors, "discovery made no cursor progress")
        seen_cursors.add(cursor)
        request = {"cursor": cursor}


def validate_excerpt(match: SearchMatchV2) -> bytes:
    descriptor, excerpt = match.evidence, match.excerpt
    encoded = excerpt.text.encode()
    require(match.read.evidence_id == descriptor.evidence_id, "read identity differs from citation")
    require(
        len(encoded) == excerpt.returned_utf8_bytes
        and excerpt.end_utf8_byte - excerpt.start_utf8_byte == len(encoded)
        and 0 <= excerpt.start_utf8_byte < excerpt.end_utf8_byte <= descriptor.original_utf8_bytes,
        "excerpt byte window is inconsistent",
    )
    require(
        excerpt.prefix_omitted == (excerpt.start_utf8_byte > 0)
        and excerpt.suffix_omitted == (excerpt.end_utf8_byte < descriptor.original_utf8_bytes)
        and excerpt.complete == (not excerpt.prefix_omitted and not excerpt.suffix_omitted),
        "excerpt completeness is inconsistent",
    )
    return encoded


async def verify_read(
    session: ToolSession,
    match: SearchMatchV2,
    authority: ActiveAuthoritySnapshotV1,
    *,
    max_bytes: int = 16384,
) -> dict[str, Any]:
    require(type(max_bytes) is int and 4 <= max_bytes <= 16384, "invalid read chunk budget")
    expected_excerpt = validate_excerpt(match)
    request: dict[str, Any] = {"evidence_id": match.evidence.evidence_id, "max_bytes": max_bytes}
    digest = hashlib.sha256()
    offset = 0
    window = bytearray()
    seen_cursors: set[str] = set()
    while True:
        packet = validated(
            ReadEvidenceResponseV1,
            await checked_call(
                session,
                "read_evidence_v1",
                request,
            ),
        ).root
        if not isinstance(packet, ReadEvidenceSuccessV1):
            raise ConsumerFailure(f"read_evidence_v1: {packet.problem}; {packet.next_step}")
        require(packet.authority_snapshot == authority, "authority changed before exact read")
        require(packet.evidence == match.evidence, "read citation differs from selected citation")
        chunk = packet.content.text.encode()
        require(
            packet.content.offset_bytes == offset
            and len(chunk) == packet.content.returned_utf8_bytes
            and 0 < len(chunk) <= max_bytes
            and offset + len(chunk) <= match.evidence.original_utf8_bytes,
            "exact-read byte progress is inconsistent",
        )
        start = max(offset, match.excerpt.start_utf8_byte)
        end = min(offset + len(chunk), match.excerpt.end_utf8_byte)
        if start < end:
            window.extend(chunk[start - offset : end - offset])
        digest.update(chunk)
        offset += len(chunk)
        require(
            packet.complete == (offset == match.evidence.original_utf8_bytes),
            "exact-read terminality differs from original length",
        )
        if packet.complete:
            break
        cursor = packet.next_cursor
        require(bool(cursor) and cursor not in seen_cursors, "read made no cursor progress")
        seen_cursors.add(cast(str, cursor))
        request = {"cursor": cursor}
    require(
        "sha256:" + digest.hexdigest() == match.evidence.evidence_text_sha256,
        "exact-read digest differs from citation",
    )
    require(bytes(window) == expected_excerpt, "excerpt differs from exact-read byte window")
    return {
        "evidence": match.evidence.model_dump(mode="json"),
        "read": match.read.model_dump(mode="json"),
        "verified_utf8_bytes": offset,
        "exact_text_sha256_verified": True,
        "excerpt_window_verified": True,
    }


async def consume_source_evidence(
    session: ToolSession,
    source_id: str,
    publication_id: str,
    question: str,
    *,
    limit: int = 5,
    max_read_bytes: int = 16384,
) -> dict[str, Any]:
    initial = validated(
        SourceSearchInitialV1,
        {
            "source_id": source_id,
            "publication_id": publication_id,
            "query": question,
            "limit": limit,
        },
    )
    source, authority = await discover_source(session, source_id, publication_id)
    packet = validated(
        SearchSourceEvidenceResponseV1,
        await checked_call(
            session,
            "search_source_evidence_v1",
            initial.model_dump(mode="json"),
        ),
    ).root
    if not isinstance(packet, SearchSourceEvidenceSuccessV1):
        raise ConsumerFailure(f"search_source_evidence_v1: {packet.problem}; {packet.next_step}")
    scope = SourceSearchScopeV1(
        source_id=source.source_id,
        publication_id=source.publication_id,
        publication_revision=source.publication_revision,
        run_id=source.run_id,
        content_fingerprint=source.content_fingerprint,
    )
    require(packet.scope == scope, "Search scope differs from discovered Source lineage")
    require(
        packet.authority_snapshot == authority, "authority changed between discovery and Search"
    )
    require(packet.query == question.strip(), "Search query differs from selected question")
    require(len(packet.matches) <= limit, "Search returned more than the requested page")
    require(
        len({match.evidence.evidence_id for match in packet.matches}) == len(packet.matches),
        "Search repeated an Evidence identity",
    )
    for match in packet.matches:
        validate_excerpt(match)
    require(
        sum(match.excerpt.returned_utf8_bytes for match in packet.matches) <= 16384
        and packet.output.incomplete_excerpt_count
        == sum(not match.excerpt.complete for match in packet.matches),
        "Search excerpt budget differs from selected page",
    )
    references = [
        await verify_read(session, match, authority, max_bytes=max_read_bytes)
        for match in packet.matches
    ]
    selection = SourceAskSelectionV1(
        status=packet.selection.status,
        returned=len(references),
        next_step=(
            "run_scoped_search_for_all_matches"
            if packet.selection.status == "more_available"
            else "read_selected_evidence"
            if references
            else "refine_question_in_selected_source"
        ),
    )
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "ok": True,
        "question": question.strip(),
        "answer_status": "evidence_found" if references else "insufficient_evidence",
        "scope": scope.model_dump(mode="json"),
        "authority_snapshot": authority.model_dump(mode="json"),
        "references": references,
        "selection": selection.model_dump(mode="json"),
        "limitations": ASK_LIMITATIONS,
    }
    require(len(canonical_json(receipt)) <= CANONICAL_LIMIT, "verification receipt exceeds budget")
    return receipt


@asynccontextmanager
async def session_for(
    database: Path,
    *,
    strategy: RetrievalStrategy = DEFAULT_RETRIEVAL_STRATEGY,
) -> AsyncGenerator[ClientSession, None]:
    # The SDK filters inherited variables. Preserve only an explicit checkout import path,
    # resolving it before changing the server's working directory to the Library directory.
    source_path = os.environ.get("PYTHONPATH")
    environment = (
        {
            "PYTHONPATH": os.pathsep.join(
                str(Path(part or ".").resolve()) for part in source_path.split(os.pathsep)
            )
        }
        if source_path is not None
        else None
    )
    library = database.resolve()
    parameters = StdioServerParameters(
        command=str(Path(sys.executable).with_name("mke")),
        args=[
            "--db",
            str(library),
            "--retrieval-strategy",
            strategy,
            "mcp",
            "--allowed-root",
            str(library.parent),
        ],
        cwd=str(library.parent),
        env=environment,
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=15)
            yield session


def failure_message(error: BaseException) -> str | None:
    if isinstance(error, ConsumerFailure):
        return str(error)
    if isinstance(error, BaseExceptionGroup):
        group = cast(BaseExceptionGroup[BaseException], error)
        for child in group.exceptions:
            message = failure_message(child)
            if message is not None:
                return message
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--publication-id", required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--retrieval-strategy",
        choices=SUPPORTED_RETRIEVAL_STRATEGIES,
        default=DEFAULT_RETRIEVAL_STRATEGY,
    )
    args = parser.parse_args()

    async def run() -> dict[str, Any]:
        async with session_for(args.db, strategy=args.retrieval_strategy) as session:
            return await consume_source_evidence(
                session,
                args.source_id,
                args.publication_id,
                args.question,
                limit=args.limit,
            )

    try:
        receipt = asyncio.run(run())
    except Exception as error:
        receipt = {
            "schema_version": RECEIPT_SCHEMA,
            "ok": False,
            "problem": "consumer_validation_failed",
            "cause": failure_message(error) or "SDK operation failed; details were redacted",
        }
    print(canonical_json(receipt).decode())
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
