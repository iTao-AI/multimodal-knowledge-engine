import pytest

from mke.evaluation.chinese_diagnostics import classify_miss
from mke.evaluation.chinese_protocol import GradedQrel
from mke.evaluation.manifest import StableLocator
from mke.retrieval.query_policy import compile_fts5_query_diagnostic


def _page(document_id: str, page: int) -> StableLocator:
    return StableLocator(document_id, "page", page, page)


def _qrel(document_id: str, page: int, grade: int) -> GradedQrel:
    return GradedQrel(_page(document_id, page), grade)  # type: ignore[arg-type]


def test_query_diagnostic_models_and_clauses_and_or_alternatives() -> None:
    diagnostic = compile_fts5_query_diagnostic(
        "HCOM 410000 framework",
        policy="numeric-grouping-v1",
    )

    assert diagnostic.compiled_query == (
        '"hcom" AND ("410000" OR "410 000") AND "framework"'
    )
    assert diagnostic.ascii_token_count == 3
    assert [clause.alternatives for clause in diagnostic.clauses] == [
        ("hcom",),
        ("410000", "410 000"),
        ("framework",),
    ]


@pytest.mark.parametrize(
    ("query", "expected_count", "empty"),
    [
        ("纯中文问题", 0, True),
        ("AuditNode R5 日志", 2, False),
        ("", 0, True),
    ],
)
def test_query_diagnostic_records_ascii_token_strata(
    query: str, expected_count: int, empty: bool
) -> None:
    diagnostic = compile_fts5_query_diagnostic(
        query, policy="numeric-grouping-v1"
    )

    assert diagnostic.ascii_token_count == expected_count
    assert diagnostic.compiled_query_empty is empty


@pytest.mark.parametrize(
    ("query", "qrels", "retrieved", "texts", "symptom"),
    [
        (
            "DataBridge X7",
            (_qrel("doc", 1, 2), _qrel("doc", 2, 0)),
            (_page("doc", 2),),
            {_page("doc", 1): "DataBridge X7 direct"},
            "distractor_ranked_ahead",
        ),
        (
            "纯中文问题",
            (_qrel("doc", 1, 2),),
            (),
            {_page("doc", 1): "纯中文问题答案"},
            "compiled_query_empty",
        ),
        (
            "HCOM latency",
            (_qrel("doc", 1, 2),),
            (),
            {_page("doc", 1): "Chinese-only direct answer"},
            "compiled_clauses_absent_from_direct_page",
        ),
        (
            "HCOM latency",
            (_qrel("doc", 1, 2), _qrel("doc", 2, 2)),
            (),
            {
                _page("doc", 1): "HCOM framework",
                _page("doc", 2): "low latency",
            },
            "compiled_clauses_overconstrained",
        ),
        (
            "HCOM latency",
            (_qrel("doc", 1, 2),),
            (),
            {_page("doc", 1): "HCOM latency framework"},
            "matching_direct_page_not_returned",
        ),
    ],
)
def test_miss_classification_uses_mechanical_clause_evidence(
    query: str,
    qrels: tuple[GradedQrel, ...],
    retrieved: tuple[StableLocator, ...],
    texts: dict[StableLocator, str],
    symptom: str,
) -> None:
    result = classify_miss(
        compile_fts5_query_diagnostic(query, policy="numeric-grouping-v1"),
        qrels=qrels,
        retrieved=retrieved,
        direct_page_text=texts,
    )

    assert result.symptom == symptom
    assert result.direct_locators == tuple(
        qrel.locator for qrel in qrels if qrel.grade == 2
    )
    assert len(result.direct_page_clause_coverage) == len(result.direct_locators)
    assert all(text not in result.observation for text in texts.values())


def test_miss_classification_rejects_non_miss() -> None:
    with pytest.raises(ValueError, match="classification requires a direct-Evidence miss"):
        classify_miss(
            compile_fts5_query_diagnostic(
                "HCOM", policy="numeric-grouping-v1"
            ),
            qrels=(_qrel("doc", 1, 2),),
            retrieved=(_page("doc", 1),),
            direct_page_text={_page("doc", 1): "HCOM"},
        )
