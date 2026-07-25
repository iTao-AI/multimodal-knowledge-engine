from mke.application.evidence_access import build_excerpt, read_utf8_chunk
from mke.domain.evidence_access import MatchHint


def test_query_window_finds_a_match_after_the_prefix() -> None:
    text = "前缀" * 1500 + "publication authority" + "后缀" * 1500
    excerpt = build_excerpt(text, (MatchHint("publication authority", 0, 0),))
    assert excerpt.kind == "query_window"
    assert "publication authority" in excerpt.text
    assert excerpt.returned_utf8_bytes <= 2048
    assert excerpt.complete is False


def test_prefix_fallback_is_explicit() -> None:
    excerpt = build_excerpt("abcdef", ())
    assert excerpt.kind == "prefix_fallback"


def test_utf8_chunks_reconstruct_exact_bytes() -> None:
    data = ("A中🙂e\u0301" * 100).encode()
    offset = 0
    chunks = []
    while offset < len(data):
        chunk = read_utf8_chunk(data, offset=offset, max_bytes=4)
        chunks.append(chunk)
        offset = chunk.next_offset_bytes
    assert b"".join(chunk.text.encode() for chunk in chunks) == data
    assert all(chunk.returned_utf8_bytes > 0 for chunk in chunks)
