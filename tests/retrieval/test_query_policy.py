import pytest

from mke.retrieval.query_policy import (
    DEFAULT_RETRIEVAL_QUERY_POLICY,
    compile_fts5_query,
)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", ""),
        ("hello world", '"hello" "world"'),
        ("410000 withdrawals", '"410000" "withdrawals"'),
        ("410,000 withdrawals", '"410" "000" "withdrawals"'),
        ("02139 postal district", '"02139" "postal" "district"'),
        ("ZX410000 equipment model", '"zx410000" "equipment" "model"'),
        ("火山灰 航空安全", ""),
        ("* : ( ) NEAR", '"near"'),
    ],
)
def test_current_policy_preserves_existing_compilation(query: str, expected: str) -> None:
    assert compile_fts5_query(query, policy="current") == expected


def test_current_policy_remains_runtime_default() -> None:
    assert DEFAULT_RETRIEVAL_QUERY_POLICY == "current"
    assert compile_fts5_query("410000 withdrawals") == '"410000" "withdrawals"'


def test_unknown_policy_fails_closed() -> None:
    with pytest.raises(ValueError, match="retrieval query policy is unsupported"):
        compile_fts5_query("hello", policy="unknown")  # type: ignore[arg-type]
