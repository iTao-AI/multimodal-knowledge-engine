from __future__ import annotations

import json
import unicodedata
from collections.abc import Callable
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Literal

from mke.domain.evidence_access import (
    ActiveAuthoritySnapshot,
    EvidenceDescriptor,
    EvidenceExcerpt,
    EvidenceReadSnapshot,
    EvidenceSearchPage,
    MatchHint,
    Utf8Chunk,
)

MAX_EXCERPT_BYTES = 2048
MAX_EXCERPT_CONTENT_BYTES = 16384
MAX_READ_CHUNK_BYTES = 16384
MAX_CANONICAL_MODEL_BYTES = 32768
MAX_READABLE_EVIDENCE_BYTES = 16 * 1024 * 1024
MAX_SEARCH_PAGE_TEXT_BYTES = 16 * 1024 * 1024


class ResponseTooLargeError(ValueError):
    """Mandatory strict response metadata cannot fit the canonical budget."""


@dataclass(frozen=True)
class SearchMatchProjection:
    descriptor: EvidenceDescriptor
    excerpt: EvidenceExcerpt
    read_evidence_id: str


@dataclass(frozen=True)
class SearchSelectionProjection:
    status: Literal["complete", "more_available", "capped"]
    returned: int
    next_cursor: str | None = None
    limit_reason: Literal["retrieval_strategy_cap"] | None = None


@dataclass(frozen=True)
class SearchPageProjection:
    authority: ActiveAuthoritySnapshot
    query: str
    matches: tuple[SearchMatchProjection, ...]
    selection: SearchSelectionProjection
    incomplete_excerpt_count: int
    content_budget_bytes: int = MAX_EXCERPT_CONTENT_BYTES
    envelope_budget_bytes: int = MAX_CANONICAL_MODEL_BYTES


@dataclass(frozen=True)
class ReadChunkProjection:
    authority: ActiveAuthoritySnapshot
    descriptor: EvidenceDescriptor
    chunk: Utf8Chunk
    complete: bool
    next_cursor: str | None


def utf8_size(value: str) -> int:
    return len(value.encode())


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()


def build_excerpt(
    text: str,
    hints: tuple[MatchHint, ...],
    *,
    max_bytes: int = MAX_EXCERPT_BYTES,
) -> EvidenceExcerpt:
    data = text.encode()
    if not data:
        raise ValueError("Evidence text must not be empty")
    if max_bytes < 1:
        raise ValueError("excerpt byte limit must be positive")
    matches: list[tuple[int, int, int, int]] = []
    normalized, original_spans = _normalized_with_original_spans(text)
    for hint in hints:
        needle = unicodedata.normalize("NFKC", hint.text).casefold()
        character = normalized.find(needle) if needle else -1
        if character >= 0:
            original_start = original_spans[character][0]
            original_end = original_spans[character + len(needle) - 1][1]
            byte_start = len(text[:original_start].encode())
            byte_end = len(text[:original_end].encode())
            matches.append((byte_start, hint.clause_order, hint.term_order, byte_end))
    if matches:
        start, _, _, end = min(matches)
        span = min(max_bytes, len(data))
        left = max(0, start - max(0, span - (end - start)) // 2)
        right = min(len(data), left + span)
        left = max(0, right - span)
        kind = "query_window"
    else:
        left, right, kind = 0, min(len(data), max_bytes), "prefix_fallback"
    while left < right:
        try:
            excerpt = data[left:right].decode()
            break
        except UnicodeDecodeError as error:
            if error.start == 0:
                left += 1
            else:
                right -= 1
    else:
        raise ValueError("excerpt budget cannot fit a UTF-8 code point")
    returned = len(excerpt.encode())
    return EvidenceExcerpt(
        kind=kind,
        text=excerpt,
        start_utf8_byte=left,
        end_utf8_byte=left + returned,
        prefix_omitted=left > 0,
        suffix_omitted=left + returned < len(data),
        complete=left == 0 and returned == len(data),
        returned_utf8_bytes=returned,
    )


def _normalized_with_original_spans(
    text: str,
) -> tuple[str, tuple[tuple[int, int], ...]]:
    normalized_parts: list[str] = []
    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(text):
        end = index + 1
        while end < len(text) and unicodedata.combining(text[end]):
            end += 1
        normalized = unicodedata.normalize("NFKC", text[index:end]).casefold()
        normalized_parts.append(normalized)
        spans.extend((index, end) for _ in normalized)
        index = end
    return "".join(normalized_parts), tuple(spans)


def read_utf8_chunk(data: bytes, *, offset: int, max_bytes: int) -> Utf8Chunk:
    if not 0 <= offset < len(data) or not 4 <= max_bytes <= MAX_READ_CHUNK_BYTES:
        raise ValueError("invalid UTF-8 chunk range")
    end = min(len(data), offset + max_bytes)
    while end > offset:
        try:
            text = data[offset:end].decode()
            break
        except UnicodeDecodeError as error:
            if error.start == 0:
                raise ValueError("offset is not a UTF-8 code-point boundary") from None
            end -= 1
    else:
        raise ValueError("chunk does not make positive progress")
    return Utf8Chunk(text, offset, end - offset, end)


def assemble_search_page(
    snapshot: EvidenceSearchPage,
    *,
    page_size: int,
    cursor_factory: Callable[[int], str],
) -> SearchPageProjection:
    matches: list[SearchMatchProjection] = []
    content_bytes = 0
    for selected in snapshot.results[:page_size]:
        result = selected.provenance.result
        excerpt = build_excerpt(result.text, selected.hints)
        if matches and content_bytes + excerpt.returned_utf8_bytes > MAX_EXCERPT_CONTENT_BYTES:
            break
        content_bytes += excerpt.returned_utf8_bytes
        matches.append(
            SearchMatchProjection(
                descriptor=EvidenceDescriptor(
                    evidence_id=result.evidence_id,
                    source_id=result.source_id,
                    content_fingerprint=selected.provenance.content_fingerprint,
                    publication_id=result.publication_id,
                    publication_revision=selected.provenance.publication_revision,
                    run_id=selected.provenance.run_id,
                    locator_kind=result.locator_kind,  # type: ignore[arg-type]
                    locator_start=result.locator_start,
                    locator_end=result.locator_end,
                    evidence_text_sha256=f"sha256:{sha256(result.text.encode()).hexdigest()}",
                    original_utf8_bytes=len(result.text.encode()),
                ),
                excerpt=excerpt,
                read_evidence_id=result.evidence_id,
            )
        )
    more = snapshot.more_in_selected_pool or len(matches) < len(snapshot.results)
    if more:
        selection = SearchSelectionProjection(
            "more_available",
            len(matches),
            next_cursor=cursor_factory(snapshot.position + len(matches)),
        )
    elif snapshot.eligible_discarded_by_cap:
        selection = SearchSelectionProjection(
            "capped", len(matches), limit_reason="retrieval_strategy_cap"
        )
    else:
        selection = SearchSelectionProjection("complete", len(matches))
    projection = SearchPageProjection(
        snapshot.authority,
        snapshot.normalized_query,
        tuple(matches),
        selection,
        sum(not item.excerpt.complete for item in matches),
    )
    if len(canonical_json_bytes(asdict(projection))) > MAX_CANONICAL_MODEL_BYTES:
        raise ResponseTooLargeError
    return projection


def assemble_read_chunk(
    snapshot: EvidenceReadSnapshot,
    *,
    max_bytes: int,
    cursor_factory: Callable[[int, str], str],
    bound_text_sha256: str | None = None,
) -> ReadChunkProjection:
    if snapshot.text is not None:
        data = snapshot.text.encode()
        digest = f"sha256:{sha256(data).hexdigest()}"
    else:
        data = snapshot.range_bytes
        if bound_text_sha256 is None:
            raise ValueError("continuation requires bound Evidence digest")
        digest = bound_text_sha256
    chunk = read_utf8_chunk(data, offset=0, max_bytes=max_bytes)
    absolute = Utf8Chunk(
        chunk.text,
        snapshot.offset_bytes,
        chunk.returned_utf8_bytes,
        snapshot.offset_bytes + chunk.returned_utf8_bytes,
    )
    record = snapshot.record
    descriptor = EvidenceDescriptor(
        record.evidence_id,
        record.source_id,
        record.content_fingerprint,
        record.publication_id,
        record.publication_revision,
        record.run_id,
        record.locator_kind,
        record.locator_start,
        record.locator_end,
        digest,
        record.original_utf8_bytes,
    )
    complete = absolute.next_offset_bytes == record.original_utf8_bytes
    return ReadChunkProjection(
        snapshot.authority,
        descriptor,
        absolute,
        complete,
        None if complete else cursor_factory(absolute.next_offset_bytes, digest),
    )
