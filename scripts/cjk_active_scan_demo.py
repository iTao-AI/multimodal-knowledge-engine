#!/usr/bin/env python3
"""Run the bounded CJK active-scan product demo against a local PDF fixture."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from mke.application import AskValidationError, KnowledgeEngine

ACTIVE_STRATEGY = "cjk-active-scan-overlap-v1"
ROLLBACK_STRATEGY = "numeric-grouping-v1"
DEFAULT_FIXTURE = Path(
    "tests/fixtures/retrieval-chinese-v1/development/adversarial.pdf"
)
MATCH_QUERY = "蓝湖缓存服务 不完整索引"
REFUSAL_QUERY = "海底量子电池校准协议"


def run_demo(fixture: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="mke-cjk-demo-") as directory:
        database = Path(directory) / "mke.sqlite"
        active = KnowledgeEngine(database, retrieval_strategy=ACTIVE_STRATEGY)
        try:
            ingested = active.ingest_pdf(fixture)
            search = active.search(MATCH_QUERY, limit=1)
            answer = active.ask(MATCH_QUERY, limit=1)
            refusal = active.ask(REFUSAL_QUERY, limit=1)
        finally:
            active.close()

        rollback = KnowledgeEngine(database, retrieval_strategy=ROLLBACK_STRATEGY)
        try:
            rollback_search = rollback.search(MATCH_QUERY, limit=1)
            try:
                rollback.ask(MATCH_QUERY, limit=1)
            except AskValidationError as error:
                rollback_problem = error.problem
            else:
                rollback_problem = "missing_error"
        finally:
            rollback.close()

    report = {
        "active_strategy": ACTIVE_STRATEGY,
        "ask": {
            "page": answer.evidence[0].locator_start if answer.evidence else None,
            "status": answer.answer_status,
        },
        "ingest": {"run_state": ingested.run_state.value},
        "refusal": {
            "evidence_count": len(refusal.evidence),
            "status": refusal.answer_status,
        },
        "rollback": {
            "ask_problem": rollback_problem,
            "search_results": len(rollback_search),
            "strategy": ROLLBACK_STRATEGY,
        },
        "search": {
            "page": search[0].locator_start if search else None,
            "results": len(search),
        },
        "status": "passed",
    }
    _validate_report(report)
    return report


def _validate_report(report: dict[str, Any]) -> None:
    if (
        report["ingest"]["run_state"] != "published"
        or report["search"] != {"page": 5, "results": 1}
        or report["ask"] != {"page": 5, "status": "evidence_found"}
        or report["refusal"]
        != {"evidence_count": 0, "status": "insufficient_evidence"}
        or report["rollback"]["search_results"] != 0
        or report["rollback"]["ask_problem"] != "invalid_question"
    ):
        raise RuntimeError("CJK active-scan demo proof failed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    args = parser.parse_args()
    print(json.dumps(run_demo(args.fixture), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
