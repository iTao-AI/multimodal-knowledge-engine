import json
import shutil
from pathlib import Path

import pytest

from mke.adapters.sqlite import SQLiteStore
from mke.evaluation.chinese_protocol import load_chinese_retrieval_protocol
from mke.evaluation.chinese_runner import run_chinese_retrieval_evaluation
from mke.evaluation.diagnostic_ports import FtsRankProfile

PROTOCOL = Path("tests/fixtures/retrieval-chinese-v1/protocol.json")


def test_checked_in_protocol_runs_partition_isolated_deterministic_baseline() -> None:
    protocol = load_chinese_retrieval_protocol(PROTOCOL)

    report = run_chinese_retrieval_evaluation(PROTOCOL)

    assert report.integrity_status == "passed"
    assert report.quality_status == "baseline_recorded"
    assert report.documents == 5
    assert report.queries == 48
    assert report.split_counts == {"development": 24, "holdout": 24}
    assert [item.query_id for item in report.results] == [
        item.query_id for item in protocol.queries
    ]
    assert report.metrics is not None
    assert report.qrel_adjudication.review_status == "complete"
    assert report.qrel_adjudication.query_page_judgment_count == 1680
    assert report.fts5_rank_profile == "sqlite_fts5_default_bm25"
    assert report.integrity_failures == ()
    assert all(
        item.miss is not None
        for item in report.results
        if item.qrel_counts[2] and not item.direct_ranks
    )
    assert all(
        not item.rank_override_present for item in report.fts5_rank_observations
    )


def test_runner_records_predeclared_e3b_decision_from_development_only() -> None:
    report = run_chinese_retrieval_evaluation(PROTOCOL)

    expected = sum(
        item.split == "development"
        and item.qrel_counts[2] > 0
        and not item.direct_ranks
        and item.compiled_query_empty
        for item in report.results
    )
    assert expected >= 1
    assert (
        report.e3b_evidence.development_answerable_compiled_query_empty_misses
        == expected
    )
    assert report.e3b_decision == "eligible"
    assert (
        report.e3b_reason
        == "development_compiled_query_empty_miss_observed"
    )


def test_runner_rank_evidence_is_stable_across_fresh_runs() -> None:
    first = run_chinese_retrieval_evaluation(PROTOCOL)
    second = run_chinese_retrieval_evaluation(PROTOCOL)

    assert first.results == second.results
    assert first.metrics == second.metrics
    assert first.fts5_rank_observations == second.fts5_rank_observations


def test_runner_returns_stable_failure_for_fixture_identity_error(
    tmp_path: Path,
) -> None:
    root = tmp_path / "retrieval-chinese-v1"
    shutil.copytree(PROTOCOL.parent, root)
    path = root / "protocol.json"
    fixture = root / "development/adversarial.pdf"
    fixture.write_bytes(fixture.read_bytes() + b"x")

    report = run_chinese_retrieval_evaluation(path)

    assert report.integrity_status == "failed"
    assert report.quality_status == "not_recorded"
    assert report.metrics is None
    assert report.e3b_decision == "not_justified"
    assert report.e3b_reason == "evaluation_integrity_failed"
    assert report.integrity_failures[0].problem == "retrieval_chinese_fixture_invalid"
    assert report.integrity_failures[0].next_step == "verify_fixture_identity"
    assert str(tmp_path) not in json.dumps(report.integrity_failures[0].__dict__)


def test_runner_rejects_empty_rank_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = SQLiteStore.observe_fts5_rank

    def empty_rank_proof(
        store: SQLiteStore, compiled_query: str
    ) -> FtsRankProfile:
        observed = original(store, compiled_query)
        return FtsRankProfile(
            rank_order=(),
            bm25_order=(),
            rank_override_present=observed.rank_override_present,
            sql_trace=observed.sql_trace,
        )

    monkeypatch.setattr(SQLiteStore, "observe_fts5_rank", empty_rank_proof)

    report = run_chinese_retrieval_evaluation(PROTOCOL)

    assert report.integrity_status == "failed"
    assert report.integrity_failures[0].problem == "retrieval_chinese_rank_invalid"


def test_runner_rejects_rank_proof_without_real_sql_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = SQLiteStore.observe_fts5_rank

    def trace_free_rank_proof(
        store: SQLiteStore, compiled_query: str
    ) -> FtsRankProfile:
        observed = original(store, compiled_query)
        return FtsRankProfile(
            rank_order=observed.rank_order,
            bm25_order=observed.bm25_order,
            rank_override_present=observed.rank_override_present,
            sql_trace=(),
        )

    monkeypatch.setattr(SQLiteStore, "observe_fts5_rank", trace_free_rank_proof)

    report = run_chinese_retrieval_evaluation(PROTOCOL)

    assert report.integrity_status == "failed"
    assert report.integrity_failures[0].problem == "retrieval_chinese_rank_invalid"


def test_runner_rejects_rank_order_that_does_not_match_search_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = SQLiteStore.observe_fts5_rank

    def reversed_rank_proof(
        store: SQLiteStore, compiled_query: str
    ) -> FtsRankProfile:
        observed = original(store, compiled_query)
        reversed_order = tuple(reversed(observed.rank_order))
        return FtsRankProfile(
            rank_order=reversed_order,
            bm25_order=reversed_order,
            rank_override_present=observed.rank_override_present,
            sql_trace=observed.sql_trace,
        )

    monkeypatch.setattr(SQLiteStore, "observe_fts5_rank", reversed_rank_proof)

    report = run_chinese_retrieval_evaluation(PROTOCOL)

    assert report.integrity_status == "failed"
    assert report.integrity_failures[0].problem == "retrieval_chinese_rank_invalid"
