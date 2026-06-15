import pytest

from mke.adapters.sqlite import _to_fts_query  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize(
    "query,expected",
    [
        ("", ""),
        ("   ", ""),
        ("hello world", '"hello" "world"'),
        ("HELLO", '"hello"'),
        ("* : ( ) NEAR", '"near"'),
        ("hello_world", '"hello_world"'),
        ("active page", '"active" "page"'),
        ("trustworthy", '"trustworthy"'),
    ],
)
def test_to_fts_query(query: str, expected: str) -> None:
    assert _to_fts_query(query) == expected
