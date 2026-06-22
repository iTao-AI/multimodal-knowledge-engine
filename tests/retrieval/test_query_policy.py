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


def test_numeric_grouping_policy_is_runtime_default() -> None:
    assert DEFAULT_RETRIEVAL_QUERY_POLICY == "numeric-grouping-v1"
    assert compile_fts5_query("410000 withdrawals") == (
        '("410000" OR "410 000") AND "withdrawals"'
    )


def test_unknown_policy_fails_closed() -> None:
    with pytest.raises(ValueError, match="retrieval query policy is unsupported"):
        compile_fts5_query("hello", policy="unknown")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "410000 million gallons",
            '("410000" OR "410 000") AND "million" AND "gallons"',
        ),
        (
            "25600 public supply",
            '("25600" OR "25 600") AND "public" AND "supply"',
        ),
        ("02139 postal district", '"02139" "postal" "district"'),
        ("ZX410000 equipment model", '"zx410000" "equipment" "model"'),
        ("2005 reporting year", '"2005" "reporting" "year"'),
        ("火山灰 航空安全", ""),
    ],
)
def test_numeric_grouping_policy(query: str, expected: str) -> None:
    assert compile_fts5_query(query, policy="numeric-grouping-v1") == expected


@pytest.mark.parametrize(
    "query",
    [
        "",
        "hello world",
        "02139 postal district",
        "ZX410000 equipment model",
        "2005 reporting year",
        "410,000 grouped value",
        "410_000 grouped value",
        "٤١٠٠٠٠ unicode digits",
        "+410000 signed value",
        "-410000 signed value",
        "410000.5 decimal value",
        "410000e3 scientific value",
        "20250101-06 date value",
    ],
)
def test_numeric_grouping_returns_current_compilation_without_eligible_token(
    query: str,
) -> None:
    assert compile_fts5_query(
        query, policy="numeric-grouping-v1"
    ) == compile_fts5_query(query, policy="current")


@pytest.mark.parametrize(
    ("token", "grouped"),
    [
        ("25600", "25 600"),
        ("410000", "410 000"),
        ("1234567", "1 234 567"),
        ("123456789", "123 456 789"),
    ],
)
def test_numeric_grouping_uses_conventional_right_groups(
    token: str,
    grouped: str,
) -> None:
    assert compile_fts5_query(
        f"{token} value", policy="numeric-grouping-v1"
    ) == f'("{token}" OR "{grouped}") AND "value"'


def test_numeric_grouping_supports_multiple_eligible_integers() -> None:
    assert compile_fts5_query(
        "410000 compared 1234567", policy="numeric-grouping-v1"
    ) == (
        '("410000" OR "410 000") AND "compared" AND '
        '("1234567" OR "1 234 567")'
    )


def test_numeric_grouping_has_bounded_expansion_at_manifest_query_limit() -> None:
    query = "410000 " * 142 + "value!"

    compiled = compile_fts5_query(query, policy="numeric-grouping-v1")

    assert len(query) == 1000
    assert len(compiled) < 5000
    assert compiled.count('("410000" OR "410 000")') == 142
