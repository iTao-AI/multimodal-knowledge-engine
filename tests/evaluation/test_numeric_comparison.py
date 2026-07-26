import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from mke.evaluation.numeric_comparison import (
    GATE_ORDER,
    CompiledQuery,
    NumericComparisonGate,
    NumericComparisonReport,
    NumericProtocol,
    load_numeric_protocol,
    refresh_numeric_protocol_scope,
    render_numeric_comparison_json,
    run_numeric_comparison,
)
from mke.evaluation.report import IntegrityFailure, RetrievalEvaluationReport
from mke.evaluation.runner import (
    RetrievalEvaluationEvidence,
    RetrievalEvaluationObservation,
)

PROTOCOL = Path("tests/fixtures/retrieval-numeric-v1/protocol-lock.json")
PROTOCOL_SHA256 = (
    "17c424e49237deba600fef70d47da803fb73f72d2ee65995fc155dc96e22da60"
)


def _copy_numeric_repository(tmp_path: Path) -> tuple[Path, Path]:
    repository = tmp_path / "repository"
    shutil.copytree("tests/fixtures", repository / "tests/fixtures")
    shutil.copytree("src", repository / "src")
    shutil.copy2("pyproject.toml", repository / "pyproject.toml")
    shutil.copy2("uv.lock", repository / "uv.lock")
    return (
        repository,
        repository / "tests/fixtures/retrieval-numeric-v1/protocol-lock.json",
    )


def _write_protocol_payload(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _copy_live_numeric_repository(tmp_path: Path) -> tuple[Path, Path]:
    repository, protocol_path = _copy_numeric_repository(tmp_path)
    refresh_numeric_protocol_scope(
        protocol_path=protocol_path,
        repository_root=repository,
    )
    return repository, protocol_path


def _run_archived_numeric_comparison(
    protocol_path: Path,
) -> NumericComparisonReport:
    from mke.evaluation import numeric_comparison

    with tempfile.TemporaryDirectory(
        prefix="mke-test-archived-numeric-"
    ) as snapshot_root:
        protocol = numeric_comparison.load_archived_numeric_protocol(
            protocol_path,
            snapshot_root=Path(snapshot_root),
        )
        return numeric_comparison._evaluate_numeric_protocol(protocol)  # pyright: ignore[reportPrivateUsage]


def _with_two_match_statements(
    evidence: RetrievalEvaluationEvidence,
) -> RetrievalEvaluationEvidence:
    return replace(
        evidence,
        match_statements_per_search=(
            2,
            *evidence.match_statements_per_search[1:],
        ),
    )


def _with_wrong_schema(
    evidence: RetrievalEvaluationEvidence,
) -> RetrievalEvaluationEvidence:
    return replace(
        evidence,
        sqlite_schema_sha256="0" * 64,
    )


def test_checked_in_protocol_produces_passing_candidate_comparison() -> None:
    report = _run_archived_numeric_comparison(PROTOCOL)
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
        render_numeric_comparison_json(
            _run_archived_numeric_comparison(PROTOCOL)
        )
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
    report = _run_archived_numeric_comparison(PROTOCOL)

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
        "mke.evaluation.numeric_comparison._observe_retrieval_evaluation",
        unexpected,
    )

    report = run_numeric_comparison(invalid)

    assert report.integrity_status == "failed"
    assert report.candidate_status == "not_recorded"
    assert report.integrity_failures[0].problem == (
        "retrieval_numeric_protocol_invalid"
    )
    assert report.integrity_failures[0].cause == "protocol validation failed"


def test_comparison_uses_one_protocol_bound_snapshot_for_all_observations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    shutil.copytree("tests/fixtures", repository / "tests/fixtures")
    shutil.copytree("src", repository / "src")
    shutil.copy2("pyproject.toml", repository / "pyproject.toml")
    shutil.copy2("uv.lock", repository / "uv.lock")
    protocol_path = repository / "tests/fixtures/retrieval-numeric-v1/protocol-lock.json"
    source_manifest = repository / "tests/fixtures/retrieval-numeric-v1/development.json"
    from mke.evaluation import numeric_comparison

    original = numeric_comparison._observe_retrieval_evaluation  # pyright: ignore[reportPrivateUsage]
    observed_paths: list[Path] = []

    def observe(
        path: Path,
        *,
        query_policy: str,
    ) -> RetrievalEvaluationObservation:
        observed_paths.append(path)
        result = original(path, query_policy=query_policy)  # type: ignore[arg-type]
        if len(observed_paths) == 1:
            source_manifest.write_text("{}\n", encoding="utf-8")
        return result

    monkeypatch.setattr(
        numeric_comparison,
        "_observe_retrieval_evaluation",
        observe,
    )

    report = _run_archived_numeric_comparison(protocol_path)

    assert report.integrity_status == "passed"
    assert len(observed_paths) == 6
    assert all(path != source_manifest for path in observed_paths)
    assert all(len(path.parts) > 3 for path in observed_paths)
    assert len(Path(os.path.commonpath(observed_paths)).parts) > 1


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

    original = numeric_comparison._observe_retrieval_evaluation  # pyright: ignore[reportPrivateUsage]

    def fail_selected(
        path: Path,
        *,
        query_policy: str,
    ) -> RetrievalEvaluationObservation:
        if path.stem.startswith(partition) or (
            partition == "e1" and path.name == "retrieval-eval-v1.json"
        ):
            if query_policy == policy:
                return RetrievalEvaluationObservation(
                    report=RetrievalEvaluationReport(
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
                    ),
                    evidence=None,
                )
        return original(path, query_policy=query_policy)  # type: ignore[arg-type]

    monkeypatch.setattr(
        numeric_comparison,
        "_observe_retrieval_evaluation",
        fail_selected,
    )

    report = _run_archived_numeric_comparison(PROTOCOL)

    assert report.integrity_status == "failed"
    assert report.candidate_status == "not_recorded"
    failure = report.integrity_failures[0]
    assert failure.problem == "retrieval_numeric_evaluation_incomplete"
    assert failure.cause == f"{partition} {policy} evaluation failed"
    assert "/Users/" not in render_numeric_comparison_json(report)
    assert "SECRET" not in render_numeric_comparison_json(report)


def test_nondeterministic_evaluation_uses_fixed_numeric_error_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.evaluation import numeric_comparison

    def nondeterministic(
        path: Path,
        *,
        query_policy: str,
    ) -> RetrievalEvaluationObservation:
        del path, query_policy
        return RetrievalEvaluationObservation(
            report=RetrievalEvaluationReport(
                manifest_id="retrieval-numeric-v1-development",
                benchmark_scope="small_english_page_timestamp_corpus",
                quality_gate="none",
                status="failed",
                quality_status="not_recorded",
                document_count=1,
                results=(),
                metrics=None,
                integrity_failures=(
                    IntegrityFailure(
                        problem="retrieval_eval_nondeterministic",
                        cause="private detail",
                        next_step="private",
                    ),
                ),
                duration_ms=1,
            ),
            evidence=None,
        )

    monkeypatch.setattr(
        numeric_comparison,
        "_observe_retrieval_evaluation",
        nondeterministic,
    )

    report = _run_archived_numeric_comparison(PROTOCOL)

    assert report.integrity_status == "failed"
    assert report.candidate_status == "not_recorded"
    assert report.integrity_failures == (
        IntegrityFailure(
            problem="retrieval_numeric_nondeterministic",
            cause="numeric comparison results were not deterministic",
            next_step="inspect_numeric_comparison_runtime",
        ),
    )


@pytest.mark.parametrize(
    ("evidence_change", "failed_gate"),
    [
        (
            _with_two_match_statements,
            "single_match_per_search",
        ),
        (
            _with_wrong_schema,
            "scope_fence",
        ),
    ],
)
def test_evidence_backed_gates_reject_invalid_runtime_observations(
    monkeypatch: pytest.MonkeyPatch,
    evidence_change: object,
    failed_gate: str,
) -> None:
    from collections.abc import Callable

    from mke.evaluation import numeric_comparison

    mutate = cast(
        Callable[
            [RetrievalEvaluationEvidence],
            RetrievalEvaluationEvidence,
        ],
        evidence_change,
    )
    original = numeric_comparison._observe_retrieval_evaluation  # pyright: ignore[reportPrivateUsage]
    changed = False

    def observe(
        path: Path,
        *,
        query_policy: str,
    ) -> RetrievalEvaluationObservation:
        nonlocal changed
        observation = original(path, query_policy=query_policy)  # type: ignore[arg-type]
        if not changed and observation.evidence is not None:
            changed = True
            return replace(
                observation,
                evidence=mutate(observation.evidence),
            )
        return observation

    monkeypatch.setattr(
        numeric_comparison,
        "_observe_retrieval_evaluation",
        observe,
    )

    report = _run_archived_numeric_comparison(PROTOCOL)

    assert report.integrity_status == "passed"
    assert report.candidate_status == "rejected"
    gates = {gate.gate_id: gate for gate in report.gates}
    assert gates[failed_gate].status == "failed"
    assert gates[failed_gate].observed == "requirement_not_met"


def test_trustworthy_gate_failure_is_candidate_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.evaluation import numeric_comparison

    original = numeric_comparison._evaluate_gates  # pyright: ignore[reportPrivateUsage]

    def reject(
        protocol: NumericProtocol,
        reports: dict[str, dict[str, RetrievalEvaluationReport]],
        observations: dict[str, dict[str, RetrievalEvaluationObservation]],
        compiled: tuple[CompiledQuery, ...],
    ) -> tuple[NumericComparisonGate, ...]:
        gates = list(original(protocol, reports, observations, compiled))
        gates[2] = replace(
            gates[2],
            status="failed",
            observed="no_improvement",
            next_step="do_not_promote",
        )
        return tuple(gates)

    monkeypatch.setattr(numeric_comparison, "_evaluate_gates", reject)

    report = _run_archived_numeric_comparison(PROTOCOL)

    assert report.integrity_status == "passed"
    assert report.candidate_status == "rejected"
    assert report.integrity_failures == ()


def test_semantic_payload_is_deterministic_without_duration() -> None:
    first = json.loads(
        render_numeric_comparison_json(
            _run_archived_numeric_comparison(PROTOCOL)
        )
    )
    second = json.loads(
        render_numeric_comparison_json(
            _run_archived_numeric_comparison(PROTOCOL)
        )
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
    from mke.evaluation import numeric_comparison

    protocol = numeric_comparison.load_archived_numeric_protocol(PROTOCOL)

    assert protocol.candidate_id == "numeric-grouping-v1"
    assert protocol.candidate_revision == 1


def test_checked_in_protocol_hash_remains_exact() -> None:
    import hashlib

    assert hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() == PROTOCOL_SHA256


def test_live_protocol_and_public_runner_reject_current_source_drift(
    tmp_path: Path,
) -> None:
    repository, protocol_path = _copy_numeric_repository(tmp_path)
    source = repository / "src/mke/evaluation/runner.py"
    source.write_bytes(source.read_bytes() + b"\n")

    with pytest.raises(ValueError):
        load_numeric_protocol(protocol_path)

    report = run_numeric_comparison(protocol_path)
    assert report.integrity_status == "failed"
    assert report.candidate_status == "not_recorded"
    assert report.integrity_failures == (
        IntegrityFailure(
            problem="retrieval_numeric_fixture_invalid",
            cause="protocol-bound input identity mismatch",
            next_step="restore_numeric_protocol_inputs",
        ),
    )


@pytest.mark.parametrize("archived", [False, True], ids=["live", "archived"])
@pytest.mark.parametrize(
    ("case", "error_kind"),
    [
        ("top_level_extra_key", "validation"),
        ("claim", "validation"),
        ("manifest_absolute_path", "validation"),
        ("manifest_parent_path", "validation"),
        ("manifest_alternate_path", "validation"),
        ("e1_manifest_digest", "fixture"),
        ("fixture_bytes", "fixture"),
        ("fixture_digest", "fixture"),
    ],
)
def test_production_loaders_reject_protocol_authority_mutations(
    tmp_path: Path,
    archived: bool,
    case: str,
    error_kind: str,
) -> None:
    from mke.evaluation import numeric_comparison

    _, protocol_path = _copy_live_numeric_repository(tmp_path)
    payload = json.loads(protocol_path.read_text(encoding="utf-8"))
    if case == "top_level_extra_key":
        payload["unexpected"] = True
    elif case == "claim":
        payload["claim"] = "broader_claim"
    elif case == "manifest_absolute_path":
        payload["manifests"]["development"]["path"] = "/tmp/development.json"
    elif case == "manifest_parent_path":
        payload["manifests"]["development"]["path"] = "../development.json"
    elif case == "manifest_alternate_path":
        payload["manifests"]["development"]["path"] = (
            "retrieval-numeric-v1/alternate.json"
        )
    elif case == "e1_manifest_digest":
        payload["manifests"]["e1"]["sha256"] = "0" * 64
    elif case == "fixture_bytes":
        payload["fixtures"][0]["bytes"] = 1
    else:
        payload["fixtures"][0]["sha256"] = "0" * 64
    _write_protocol_payload(protocol_path, payload)

    loader = (
        numeric_comparison.load_archived_numeric_protocol
        if archived
        else numeric_comparison.load_numeric_protocol
    )
    expected_error = (
        numeric_comparison._ProtocolFixtureError  # pyright: ignore[reportPrivateUsage]
        if error_kind == "fixture"
        else numeric_comparison._ProtocolValidationError  # pyright: ignore[reportPrivateUsage]
    )
    with pytest.raises(expected_error):
        loader(protocol_path)


@pytest.mark.parametrize("archived", [False, True], ids=["live", "archived"])
def test_production_loaders_reject_manifest_symlink_escape(
    tmp_path: Path,
    archived: bool,
) -> None:
    from mke.evaluation import numeric_comparison

    _, protocol_path = _copy_live_numeric_repository(tmp_path)
    manifest = protocol_path.parent / "development.json"
    outside = tmp_path / "outside.json"
    outside.write_bytes(manifest.read_bytes())
    manifest.unlink()
    manifest.symlink_to(outside)
    payload = json.loads(protocol_path.read_text(encoding="utf-8"))
    payload["manifests"]["development"]["sha256"] = hashlib.sha256(
        outside.read_bytes()
    ).hexdigest()
    _write_protocol_payload(protocol_path, payload)

    loader = (
        numeric_comparison.load_archived_numeric_protocol
        if archived
        else numeric_comparison.load_numeric_protocol
    )
    with pytest.raises(
        numeric_comparison._ProtocolValidationError  # pyright: ignore[reportPrivateUsage]
    ):
        loader(protocol_path)


@pytest.mark.parametrize("archived", [False, True], ids=["live", "archived"])
@pytest.mark.parametrize(
    "relative_path",
    [
        "retrieval-numeric-v1/development.json",
        "retrieval-numeric-v1/holdout.json",
        "retrieval-numeric-v1/development.pdf",
        "retrieval-numeric-v1/holdout.pdf",
    ],
)
def test_production_loaders_reject_bound_fixture_mutation(
    tmp_path: Path,
    archived: bool,
    relative_path: str,
) -> None:
    from mke.evaluation import numeric_comparison

    _, protocol_path = _copy_live_numeric_repository(tmp_path)
    target = protocol_path.parent.parent / relative_path
    target.write_bytes(target.read_bytes() + b"\n")

    loader = (
        numeric_comparison.load_archived_numeric_protocol
        if archived
        else numeric_comparison.load_numeric_protocol
    )
    with pytest.raises(
        numeric_comparison._ProtocolFixtureError  # pyright: ignore[reportPrivateUsage]
    ):
        loader(protocol_path)


def test_public_runner_preserves_protocol_load_start_for_success_duration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.evaluation import numeric_comparison

    _, protocol_path = _copy_live_numeric_repository(tmp_path)
    original = numeric_comparison._evaluate_numeric_protocol  # pyright: ignore[reportPrivateUsage]
    observed_starts: list[float | None] = []

    def evaluate(
        protocol: NumericProtocol,
        *,
        _started_at: float | None = None,
    ) -> NumericComparisonReport:
        observed_starts.append(_started_at)
        return original(protocol)

    monkeypatch.setattr(numeric_comparison.time, "monotonic", lambda: 123.0)
    monkeypatch.setattr(numeric_comparison, "_evaluate_numeric_protocol", evaluate)

    report = run_numeric_comparison(protocol_path)

    assert report.integrity_status == "passed"
    assert observed_starts == [123.0]


def test_archived_protocol_accepts_recorded_scope_without_current_source_bytes(
    tmp_path: Path,
) -> None:
    from mke.evaluation import numeric_comparison

    repository, protocol_path = _copy_numeric_repository(tmp_path)
    source = repository / "src/mke/evaluation/runner.py"
    source.write_bytes(source.read_bytes() + b"\n")

    protocol = numeric_comparison.load_archived_numeric_protocol(protocol_path)

    assert tuple(protocol.manifests) == ("development", "holdout", "e1")
    assert protocol.sqlite_schema_sha256 == json.loads(
        protocol_path.read_text(encoding="utf-8")
    )["scope_fence"]["sqlite_schema_sha256"]


@pytest.mark.parametrize(
    "case",
    [
        "scope_extra_key",
        "scope_file_extra_key",
        "absolute_path",
        "parent_path",
        "duplicate_path",
        "wrong_order",
        "uppercase_file_sha256",
        "malformed_file_sha256",
        "uppercase_schema_sha256",
    ],
)
def test_archived_protocol_rejects_noncanonical_scope(
    tmp_path: Path,
    case: str,
) -> None:
    from mke.evaluation import numeric_comparison

    _, protocol_path = _copy_numeric_repository(tmp_path)
    payload = json.loads(protocol_path.read_text(encoding="utf-8"))
    scope = payload["scope_fence"]
    files = scope["files"]
    if case == "scope_extra_key":
        scope["unexpected"] = True
    elif case == "scope_file_extra_key":
        files[0]["unexpected"] = True
    elif case == "absolute_path":
        files[0]["path"] = "/tmp/pyproject.toml"
    elif case == "parent_path":
        files[0]["path"] = "../pyproject.toml"
    elif case == "duplicate_path":
        files[1]["path"] = files[0]["path"]
    elif case == "wrong_order":
        files[0], files[1] = files[1], files[0]
    elif case == "uppercase_file_sha256":
        files[0]["sha256"] = "A" * 64
    elif case == "malformed_file_sha256":
        files[0]["sha256"] = "0" * 63
    else:
        scope["sqlite_schema_sha256"] = "A" * 64
    _write_protocol_payload(protocol_path, payload)

    with pytest.raises(ValueError):
        numeric_comparison.load_archived_numeric_protocol(protocol_path)


def test_archived_protocol_still_rejects_manifest_identity_drift(
    tmp_path: Path,
) -> None:
    from mke.evaluation import numeric_comparison

    _, protocol_path = _copy_numeric_repository(tmp_path)
    manifest = protocol_path.parent / "development.json"
    manifest.write_bytes(manifest.read_bytes() + b"\n")

    with pytest.raises(ValueError):
        numeric_comparison.load_archived_numeric_protocol(protocol_path)


def test_archived_protocol_schema_mismatch_fails_existing_runtime_gate(
    tmp_path: Path,
) -> None:
    from mke.evaluation import numeric_comparison

    _, protocol_path = _copy_numeric_repository(tmp_path)
    payload = json.loads(protocol_path.read_text(encoding="utf-8"))
    payload["scope_fence"]["sqlite_schema_sha256"] = "0" * 64
    _write_protocol_payload(protocol_path, payload)
    protocol = numeric_comparison.load_archived_numeric_protocol(protocol_path)

    report = numeric_comparison._evaluate_numeric_protocol(protocol)  # pyright: ignore[reportPrivateUsage]

    gates = {gate.gate_id: gate for gate in report.gates}
    assert report.integrity_status == "passed"
    assert report.candidate_status == "rejected"
    assert gates["scope_fence"].status == "failed"


def test_live_protocol_rejects_scope_symlink_escape(tmp_path: Path) -> None:
    repository, protocol_path = _copy_numeric_repository(tmp_path)
    target = repository / "src/mke/evaluation/runner.py"
    outside = tmp_path / "outside.py"
    outside.write_bytes(target.read_bytes())
    target.unlink()
    target.symlink_to(outside)

    with pytest.raises(ValueError):
        load_numeric_protocol(protocol_path)


def test_protocol_rejects_bool_candidate_revision(tmp_path: Path) -> None:
    payload = json.loads(PROTOCOL.read_text())
    payload["candidate"]["revision"] = True
    invalid = tmp_path / "protocol-lock.json"
    invalid.write_text(json.dumps(payload), encoding="utf-8")

    report = run_numeric_comparison(invalid)

    assert report.integrity_status == "failed"
    assert report.candidate_status == "not_recorded"
    assert report.integrity_failures[0].problem == (
        "retrieval_numeric_protocol_invalid"
    )
    assert report.integrity_failures[0].cause == "protocol validation failed"


def test_refresh_scope_changes_only_locked_hash_values(tmp_path: Path) -> None:
    fixture_root = tmp_path / "tests/fixtures"
    shutil.copytree(Path("tests/fixtures"), fixture_root)
    for relative in (
        "pyproject.toml",
        "uv.lock",
        "src/mke/adapters/pdf/__init__.py",
        "src/mke/adapters/sqlite/__init__.py",
        "src/mke/adapters/video/__init__.py",
        "src/mke/application/__init__.py",
        "src/mke/evaluation/runner.py",
        "src/mke/retrieval/query_policy.py",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(relative, destination)
    protocol_root = fixture_root / "retrieval-numeric-v1"
    target = protocol_root / "protocol-lock.json"
    repository = tmp_path
    payload = json.loads(target.read_text(encoding="utf-8"))
    before = json.loads(target.read_text(encoding="utf-8"))
    for record in payload["scope_fence"]["files"]:
        record["sha256"] = "0" * 64
    payload["scope_fence"]["sqlite_schema_sha256"] = "0" * 64
    target.write_text(json.dumps(payload), encoding="utf-8")

    refresh_numeric_protocol_scope(
        protocol_path=target,
        repository_root=repository,
    )

    after = json.loads(target.read_text(encoding="utf-8"))
    before["scope_fence"] = after["scope_fence"]
    assert after == before
    load_numeric_protocol(target)


def test_refresh_scope_leaves_semantically_changed_protocol_untouched(
    tmp_path: Path,
) -> None:
    target = tmp_path / "protocol-lock.json"
    payload = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    payload["claim"] = "changed"
    target.write_text(json.dumps(payload), encoding="utf-8")
    before = target.read_bytes()

    with pytest.raises(ValueError):
        refresh_numeric_protocol_scope(
            protocol_path=target,
            repository_root=Path("."),
        )

    assert target.read_bytes() == before
