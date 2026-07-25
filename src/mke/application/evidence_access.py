from __future__ import annotations

import json
import unicodedata

from mke.domain.evidence_access import EvidenceExcerpt, MatchHint, Utf8Chunk

MAX_EXCERPT_BYTES = 2048
MAX_EXCERPT_CONTENT_BYTES = 16384
MAX_READ_CHUNK_BYTES = 16384
MAX_CANONICAL_MODEL_BYTES = 32768
MAX_READABLE_EVIDENCE_BYTES = 16 * 1024 * 1024
MAX_SEARCH_PAGE_TEXT_BYTES = 16 * 1024 * 1024


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
    normalized = unicodedata.normalize("NFKC", text).casefold()
    for hint in hints:
        needle = unicodedata.normalize("NFKC", hint.text).casefold()
        character = normalized.find(needle) if needle else -1
        if character >= 0:
            byte_start = len(text[:character].encode())
            byte_end = len(text[: character + len(hint.text)].encode())
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
