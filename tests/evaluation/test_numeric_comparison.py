import json
from dataclasses import replace
from pathlib import Path

import pytest

from mke.evaluation.numeric_comparison import (
    GATE_ORDER,
    CompiledQuery,
    NumericComparisonGate,
    NumericProtocol,
    load_numeric_protocol,
    render_numeric_comparison_json,
    run_numeric_comparison,
)
from mke.evaluation.report import IntegrityFailure, RetrievalEvaluationReport

PROTOCOL = Path("tests/fixtures/retrieval-numeric-v1/protocol-lock.json")


def test_checked_in_protocol_produces_passing_candidate_comparison() -> None:
    report = run_numeric_comparison(PROTOCOL)
    payload = json.loads(render_numeric_comparison_json(report))

    assert report.integrity_status == "passed"
    assert report.candidate_status == "passed"
    assert report.integrity_failures == ()
    assert tuple(gate.gate_id for gate in report.gates) == GATE_ORDER
    assert all(gate.status == "passed" for gate in report.gates)
    assert payload["schema_version"] == "mke.retrieval_numeric_comparison.v1"
    assert payload["protocol_id"] == "retrieval-numeric-v1"
    assert payload["candidate_id"] == "numeric-grouping-v1"
    assert payload["candidate_revision"] == 1
    assert payload["development"]["manifest_id"] == (
        "retrieval-numeric-v1-development"
    )
    assert payload["holdout"]["manifest_id"] == "retrieval-numeric-v1-holdout"
    assert payload["e1"]["manifest_id"] == "retrieval-eval-v1"
    assert payload["limitations"] == [
        "public_holdout_not_blind",
        "small_engineering_challenge_set",
        "ascii_compact_integers_only",
        "tokenizer_adjacent_separator_equivalence",
        "no_general_retrieval_quality_claim",
    ]


def test_comparison_records_only_the_allowlisted_e1_delta() -> None:
    payload = json.loads(
        render_numeric_comparison_json(run_numeric_comparison(PROTOCOL))
    )
    current = {
        result["query_id"]: result for result in payload["e1"]["current"]["results"]
    }
    candidate = {
        result["query_id"]: result
        for result in payload["e1"]["candidate"]["results"]
    }

    assert current["water-answerable-01"]["first_relevant_rank"] is None
    assert candidate["water-answerable-01"]["first_relevant_rank"] == 1
    assert {
        query_id
        for query_id in current
        if current[query_id] != candidate[query_id]
    } == {"water-answerable-01"}


def test_comparison_compiled_queries_preserve_noneligible_text() -> None:
    report = run_numeric_comparison(PROTOCOL)

    assert len(report.compiled_queries) == 38
    grouped = next(
        item
        for item in report.compiled_queries
        if item.query_id == "numeric-dev-grouped-01"
    )
    assert grouped.eligible_tokens == ("410000",)
    assert grouped.current == '"410000" "grouped" "daily" "withdrawal"'
    assert grouped.candidate == (
        '("410000" OR "410 000") AND "grouped" AND "daily" AND "withdrawal"'
    )
    assert all(
        item.current == item.candidate
        for item in report.compiled_queries
        if not item.eligible_tokens
    )


def test_protocol_validation_happens_before_evaluation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = json.loads(PROTOCOL.read_text())
    payload["candidate"]["id"] = "unknown"
    invalid = tmp_path / "protocol-lock.json"
    invalid.write_text(json.dumps(payload))

    def unexpected(*args: object, **kwargs: object) -> RetrievalEvaluationReport:
        raise AssertionError("evaluation must not run")

    monkeypatch.setattr(
        "mke.evaluation.numeric_comparison._run_retrieval_evaluation",
        unexpected,
    )

    report = run_numeric_comparison(invalid)

    assert report.integrity_status == "failed"
    assert report.candidate_status == "not_recorded"
    assert report.integrity_failures[0].problem == (
        "retrieval_numeric_protocol_invalid"
    )
    assert report.integrity_failures[0].cause == "protocol validation failed"


@pytest.mark.parametrize(
    ("partition", "policy"),
    [
        ("development", "current"),
        ("development", "numeric-grouping-v1"),
        ("holdout", "current"),
        ("holdout", "numeric-grouping-v1"),
        ("e1", "current"),
        ("e1", "numeric-grouping-v1"),
    ],
)
def test_evaluation_failure_is_redacted_and_not_recorded(
    monkeypatch: pytest.MonkeyPatch,
    partition: str,
    policy: str,
) -> None:
    from mke.evaluation import numeric_comparison

    original = numeric_comparison._run_retrieval_evaluation  # pyright: ignore[reportPrivateUsage]

    def fail_selected(
        path: Path,
        *,
        query_policy: str,
    ) -> RetrievalEvaluationReport:
        if path.stem.startswith(partition) or (
            partition == "e1" and path.name == "retrieval-eval-v1.json"
        ):
            if query_policy == policy:
                return RetrievalEvaluationReport(
                    manifest_id=partition,
                    benchmark_scope="small_english_page_timestamp_corpus",
                    quality_gate="none",
                    status="failed",
                    quality_status="not_recorded",
                    document_count=0,
                    results=(),
                    metrics=None,
                    integrity_failures=(
                        IntegrityFailure(
                            problem="private",
                            cause="SECRET /Users/mac/private",
                            next_step="private",
                        ),
                    ),
                    duration_ms=1,
                )
        return original(path, query_policy=query_policy)  # type: ignore[arg-type]

    monkeypatch.setattr(
        numeric_comparison,
        "_run_retrieval_evaluation",
        fail_selected,
    )

    report = run_numeric_comparison(PROTOCOL)

    assert report.integrity_status == "failed"
    assert report.candidate_status == "not_recorded"
    failure = report.integrity_failures[0]
    assert failure.problem == "retrieval_numeric_evaluation_incomplete"
    assert failure.cause == f"{partition} {policy} evaluation failed"
    assert "/Users/" not in render_numeric_comparison_json(report)
    assert "SECRET" not in render_numeric_comparison_json(report)


def test_trustworthy_gate_failure_is_candidate_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.evaluation import numeric_comparison

    original = numeric_comparison._evaluate_gates  # pyright: ignore[reportPrivateUsage]

    def reject(
        protocol: NumericProtocol,
        reports: dict[str, dict[str, RetrievalEvaluationReport]],
        compiled: tuple[CompiledQuery, ...],
    ) -> tuple[NumericComparisonGate, ...]:
        gates = list(original(protocol, reports, compiled))
        gates[2] = replace(
            gates[2],
            status="failed",
            observed="no_improvement",
            next_step="do_not_promote",
        )
        return tuple(gates)

    monkeypatch.setattr(numeric_comparison, "_evaluate_gates", reject)

    report = run_numeric_comparison(PROTOCOL)

    assert report.integrity_status == "passed"
    assert report.candidate_status == "rejected"
    assert report.integrity_failures == ()


def test_semantic_payload_is_deterministic_without_duration() -> None:
    first = json.loads(render_numeric_comparison_json(run_numeric_comparison(PROTOCOL)))
    second = json.loads(
        render_numeric_comparison_json(run_numeric_comparison(PROTOCOL))
    )

    first.pop("duration_ms")
    second.pop("duration_ms")
    assert first == second


def test_missing_protocol_is_fixed_public_failure(tmp_path: Path) -> None:
    report = run_numeric_comparison(tmp_path / "private" / "missing.json")

    assert report.integrity_status == "failed"
    assert report.candidate_status == "not_recorded"
    assert report.integrity_failures[0].problem == (
        "retrieval_numeric_protocol_invalid"
    )
    assert report.integrity_failures[0].cause == "protocol file is missing"
    assert str(tmp_path) not in render_numeric_comparison_json(report)


def test_protocol_loader_accepts_only_the_frozen_candidate() -> None:
    protocol = load_numeric_protocol(PROTOCOL)

    assert protocol.candidate_id == "numeric-grouping-v1"
    assert protocol.candidate_revision == 1
