from pathlib import Path


def test_demo_covers_ingest_search_ask_refusal_and_rollback() -> None:
    from scripts.cjk_active_scan_demo import run_demo

    report = run_demo(
        Path("tests/fixtures/retrieval-chinese-v1/development/adversarial.pdf")
    )

    assert report == {
        "active_strategy": "cjk-active-scan-overlap-v1",
        "ask": {"page": 5, "status": "evidence_found"},
        "ingest": {"run_state": "published"},
        "refusal": {"evidence_count": 0, "status": "insufficient_evidence"},
        "rollback": {
            "ask_problem": "invalid_question",
            "search_results": 0,
            "strategy": "numeric-grouping-v1",
        },
        "search": {"page": 5, "results": 1},
        "status": "passed",
    }
