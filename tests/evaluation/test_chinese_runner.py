import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from mke.adapters.sqlite import SQLiteStore
from mke.evaluation.chinese_protocol import load_chinese_retrieval_protocol
from mke.evaluation.chinese_runner import run_chinese_retrieval_evaluation
from mke.evaluation.diagnostic_ports import FtsRankProfile

PROTOCOL = Path("tests/fixtures/retrieval-chinese-v1/protocol.json")


def _rank_sql(score: str) -> str:
    return f"""
        WITH matched AS MATERIALIZED (
          SELECT evidence.evidence_id,
                 evidence.locator_kind,
                 evidence.locator_start,
                 evidence.locator_end,
                 assets.sha256 AS source_sha256,
                 {score} AS score
          FROM active_evidence_fts
          JOIN evidence
            ON evidence.evidence_id = active_evidence_fts.evidence_id
          JOIN sources ON sources.source_id = evidence.source_id
          JOIN assets ON assets.asset_id = sources.asset_id
          WHERE active_evidence_fts MATCH 'synthetic'
            AND sources.active_publication_id =
                active_evidence_fts.publication_id
        )
        SELECT matched.evidence_id, matched.score
        FROM matched
        ORDER BY matched.score, matched.locator_start,
                 matched.locator_kind, matched.locator_end,
                 matched.source_sha256
    """


def _valid_revision_two_trace() -> tuple[str, ...]:
    return (
        _rank_sql("rank"),
        "SELECT 1 FROM active_evidence_fts_config "
        "WHERE k = 'rank' LIMIT 1",
        _rank_sql("bm25(active_evidence_fts)"),
    )


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


def test_runner_accepts_captured_revision_two_match_trace_and_config_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.evaluation import chinese_runner

    original = SQLiteStore.observe_fts5_rank
    captured: list[tuple[str, ...]] = []

    def capture_rank_proof(
        store: SQLiteStore, compiled_query: str
    ) -> FtsRankProfile:
        observed = original(store, compiled_query)
        captured.append(observed.sql_trace)
        return observed

    monkeypatch.setattr(SQLiteStore, "observe_fts5_rank", capture_rank_proof)

    report = run_chinese_retrieval_evaluation(PROTOCOL)

    assert report.integrity_status == "passed"
    assert captured
    assert all(
        chinese_runner._valid_rank_sql_trace(trace)  # pyright: ignore[reportPrivateUsage]
        for trace in captured
    )
    assert all(
        any(
            "active_evidence_fts_config" in statement
            and "LIMIT 1" in statement
            for statement in trace
        )
        for trace in captured
    )


def test_rank_trace_normalizes_before_selecting_two_match_statements() -> None:
    from mke.evaluation import chinese_runner

    assert chinese_runner._valid_rank_sql_trace(  # pyright: ignore[reportPrivateUsage]
        _valid_revision_two_trace()
    )


@pytest.mark.parametrize(
    "statements",
    [
        (_rank_sql("rank"),),
        (
            _rank_sql("rank"),
            _rank_sql("bm25(active_evidence_fts)"),
            _rank_sql("rank"),
        ),
        (
            _rank_sql("rank").replace(
                "JOIN assets ON assets.asset_id = sources.asset_id",
                "",
            ),
            _rank_sql("bm25(active_evidence_fts)"),
        ),
        (
            _rank_sql("rank").replace(
                "matched.locator_kind",
                "matched.evidence_id",
            ),
            _rank_sql("bm25(active_evidence_fts)"),
        ),
        (
            _rank_sql("rank").replace(
                (
                    "AND sources.active_publication_id =\n"
                    "                active_evidence_fts.publication_id"
                ),
                "",
            ),
            _rank_sql("bm25(active_evidence_fts)"),
        ),
        (
            _rank_sql("rank").replace(
                "matched.source_sha256",
                "matched.evidence_id",
            ),
            _rank_sql("bm25(active_evidence_fts)"),
        ),
        (
            _rank_sql("rank") + " LIMIT 10",
            _rank_sql("bm25(active_evidence_fts)"),
        ),
        (
            _rank_sql("rank").replace(
                (
                    "matched.score, matched.locator_start,\n"
                    "                 matched.locator_kind, matched.locator_end,\n"
                    "                 matched.source_sha256"
                ),
                "matched.score, matched.locator_start, matched.evidence_id",
            ),
            _rank_sql("bm25(active_evidence_fts)"),
        ),
        (
            _rank_sql("rank").replace(
                (
                    "matched.score, matched.locator_start,\n"
                    "                 matched.locator_kind, matched.locator_end,\n"
                    "                 matched.source_sha256"
                ),
                (
                    "rank, evidence.locator_start, "
                    "evidence.evidence_id"
                ),
            ),
            _rank_sql("bm25(active_evidence_fts)"),
        ),
        (
            _rank_sql("rank"),
            _rank_sql("rank"),
        ),
        (
            _rank_sql("rank + bm25(active_evidence_fts)"),
            _rank_sql("bm25(active_evidence_fts)"),
        ),
    ],
)
def test_rank_trace_rejects_invalid_match_authority(
    statements: tuple[str, ...],
) -> None:
    from mke.evaluation import chinese_runner

    assert not chinese_runner._valid_rank_sql_trace(  # pyright: ignore[reportPrivateUsage]
        statements
    )


def test_hostile_rank_trace_never_reaches_stable_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = SQLiteStore.observe_fts5_rank
    sentinel = "SECRET /private/sentinel evidence_id cursor"

    def hostile_rank_proof(
        store: SQLiteStore, compiled_query: str
    ) -> FtsRankProfile:
        observed = original(store, compiled_query)
        hostile = (
            "SELECT evidence_id FROM active_evidence_fts "
            f"WHERE active_evidence_fts MATCH '{sentinel}'"
        )
        return replace(
            observed,
            sql_trace=(*observed.sql_trace, hostile),
        )

    monkeypatch.setattr(SQLiteStore, "observe_fts5_rank", hostile_rank_proof)

    report = run_chinese_retrieval_evaluation(PROTOCOL)
    rendered = json.dumps(
        [item.__dict__ for item in report.integrity_failures],
        ensure_ascii=False,
    )

    assert report.integrity_status == "failed"
    assert report.integrity_failures[0].problem == "retrieval_chinese_rank_invalid"
    assert report.integrity_failures[0].cause == "FTS5 rank evidence is inconsistent"
    assert report.integrity_failures[0].next_step == (
        "inspect_fts5_rank_configuration"
    )
    assert sentinel not in rendered
    assert "/private/" not in rendered
    assert "cursor" not in rendered


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
