import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import cast

import fitz  # pyright: ignore[reportMissingTypeStubs]
import pytest

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "retrieval-chinese-v1"


@pytest.mark.parametrize(
    ("relative", "byte_size", "sha256", "page_chars"),
    (
        (
            "development/ub-service-core-2.0-zh.pdf",
            1168641,
            "13e8f1da824de892931653e17df2a8b20f77fe84b2a7472b13113405efbf296d",
            (
                77,
                410,
                4089,
                388,
                1864,
                764,
                418,
                1231,
                694,
                711,
                651,
                683,
                463,
                783,
                303,
                539,
                635,
                400,
                478,
                634,
                625,
                516,
                818,
                429,
                939,
                870,
            ),
        ),
        (
            "development/adversarial.pdf",
            4350,
            "be3b88352b0a80d6d165de146ff81be224b706d3eb3721d969266e64505af8dd",
            (60, 41, 59, 57, 34, 31, 32, 32),
        ),
        (
            "holdout/copyright-law-2020.pdf",
            182479,
            "e1217f1df0bb98586a883819505f17a29140fb114ce5f1a444ea0a60d22c9d2b",
            (
                874,
                917,
                929,
                1027,
                1006,
                992,
                810,
                920,
                942,
                949,
                980,
                1028,
                1046,
                422,
            ),
        ),
        (
            "holdout/administrative-compulsion-law-2011.pdf",
            198629,
            "80d1a49a1641f73f53df7f2cfe008b4f8e8419a538f37d183f9758ec52e90d0d",
            (
                490,
                826,
                665,
                745,
                803,
                806,
                802,
                746,
                816,
                776,
                854,
                781,
                747,
                758,
            ),
        ),
        (
            "holdout/adversarial.pdf",
            4399,
            "52d2319515195c7a0b8572f4a6f86eec6856cb189a24f3272c2792ad5fe76924",
            (46, 43, 46, 44, 33, 30, 68, 47),
        ),
    ),
)
def test_chinese_corpus_matches_frozen_bytes(
    relative: str,
    byte_size: int,
    sha256: str,
    page_chars: tuple[int, ...],
) -> None:
    path = FIXTURE_ROOT / relative
    assert path.stat().st_size == byte_size
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha256
    with fitz.open(path) as document:
        assert tuple(
            len(
                cast(
                    str,
                    page.get_text(  # pyright: ignore[reportUnknownMemberType]
                        "text", sort=True
                    ),
                )
            )
            for page in document
        ) == page_chars
        assert all(page_chars)


def test_chinese_protocol_freezes_inventory() -> None:
    payload = json.loads((FIXTURE_ROOT / "protocol.json").read_text(encoding="utf-8"))

    assert payload["schema_version"] == "mke.retrieval_chinese_protocol.v1"
    assert payload["protocol_id"] == "retrieval-chinese-v1"
    assert payload["rank_probe_query_id"] == "zh-dev-exact-02"
    assert len(payload["documents"]) == 5
    assert len(payload["queries"]) == 48
    assert Counter(item["split"] for item in payload["queries"]) == {
        "development": 24,
        "holdout": 24,
    }
    assert Counter(item["category"] for item in payload["queries"]) == {
        "chinese_exact_lexical": 8,
        "chinese_word_boundary": 6,
        "proper_noun_mixed": 6,
        "number_date_unit": 6,
        "semantic_paraphrase": 8,
        "multi_condition": 6,
        "ranking_hard_negative": 4,
        "unanswerable": 4,
    }


def test_chinese_qrel_adjudication_covers_every_partition_page() -> None:
    protocol = json.loads(
        (FIXTURE_ROOT / "protocol.json").read_text(encoding="utf-8")
    )
    adjudication = json.loads(
        (FIXTURE_ROOT / "qrel-adjudication.json").read_text(encoding="utf-8")
    )

    assert (
        adjudication["schema_version"]
        == "mke.retrieval_chinese_qrel_adjudication.v1"
    )
    assert adjudication["protocol_id"] == "retrieval-chinese-v1"
    assert adjudication["method"] == "complete_partition_page_review"
    assert adjudication["review_status"] == "complete"
    assert adjudication["document_page_counts"] == {
        "ub-service-core": 26,
        "development-adversarial": 8,
        "copyright-law": 14,
        "administrative-compulsion-law": 14,
        "holdout-adversarial": 8,
    }

    documents = {
        item["document_id"]: item for item in protocol["documents"]
    }
    expected_pages = {
        "development": tuple(
            (document_id, page)
            for document_id in ("ub-service-core", "development-adversarial")
            for page in range(1, adjudication["document_page_counts"][document_id] + 1)
        ),
        "holdout": tuple(
            (document_id, page)
            for document_id in (
                "copyright-law",
                "administrative-compulsion-law",
                "holdout-adversarial",
            )
            for page in range(1, adjudication["document_page_counts"][document_id] + 1)
        ),
    }
    assert all(
        documents[document_id]["split"] == split
        for split, locators in expected_pages.items()
        for document_id, _page in locators
    )

    protocol_queries = protocol["queries"]
    reviewed_queries = adjudication["queries"]
    assert [item["query_id"] for item in reviewed_queries] == [
        item["query_id"] for item in protocol_queries
    ]
    assert len(reviewed_queries) == 48

    judgment_total = 0
    for query, reviewed in zip(protocol_queries, reviewed_queries, strict=True):
        assert reviewed["query_id"] == query["query_id"]
        assert reviewed["split"] == query["split"]
        assert 1 <= len(reviewed["decision_basis"]) <= 500
        observed = tuple(
            (item["document_id"], item["locator_start"])
            for item in reviewed["judgments"]
        )
        assert observed == expected_pages[query["split"]]
        assert all(
            item["locator_kind"] == "page"
            and item["locator_start"] == item["locator_end"]
            and item["grade"] in {0, 1, 2, "non_relevant"}
            for item in reviewed["judgments"]
        )
        derived_qrels = [
            {
                "document_id": item["document_id"],
                "locator_kind": item["locator_kind"],
                "locator_start": item["locator_start"],
                "locator_end": item["locator_end"],
                "grade": item["grade"],
            }
            for item in reviewed["judgments"]
            if item["grade"] != "non_relevant"
        ]
        assert derived_qrels == query["qrels"]
        judgment_total += len(reviewed["judgments"])

    assert judgment_total == 1680
    assert adjudication["query_page_judgment_count"] == judgment_total
