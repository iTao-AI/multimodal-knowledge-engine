import json
from pathlib import Path
from typing import cast

import pytest

from mke.application import KnowledgeEngine
from mke.domain import ActiveEvidenceRef
from mke.evaluation.manifest import (
    EvaluationQuery,
    RetrievalEvaluationManifest,
    StableLocator,
    load_retrieval_manifest,
)
from mke.evaluation.metrics import AskStatus
from mke.evaluation.report import render_retrieval_json_report
from mke.evaluation.runner import (
    _run_retrieval_evaluation,  # pyright: ignore[reportPrivateUsage]
    run_retrieval_evaluation,
)
from mke.retrieval import RetrievalQueryPolicy

MANIFEST = Path("tests/fixtures/retrieval-eval-v1.json")


def _copy_corpus(tmp_path: Path) -> Path:
    source = load_retrieval_manifest(MANIFEST)
    root = tmp_path / "fixtures"
    for document in source.documents:
        for fixture in (document.primary_file, *document.supporting_files):
            target = root / Path(*fixture.path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.resolve(fixture).read_bytes())
    manifest = root / "retrieval-eval-v1.json"
    manifest.write_bytes(MANIFEST.read_bytes())
    return manifest


def _no_search(
    engine: KnowledgeEngine,
    query: EvaluationQuery,
    source_documents: dict[str, str],
) -> tuple[StableLocator, ...]:
    del engine, query, source_documents
    return ()


def _refuse(engine: KnowledgeEngine, query: EvaluationQuery) -> AskStatus:
    del engine, query
    return "insufficient_evidence"


def _find_evidence(engine: KnowledgeEngine, query: EvaluationQuery) -> AskStatus:
    del engine, query
    return "evidence_found"


def test_checked_in_evaluation_records_complete_deterministic_baseline() -> None:
    report = run_retrieval_evaluation(MANIFEST)

    assert report.status == "passed"
    assert report.quality_status == "baseline_recorded"
    assert report.document_count == 3
    assert report.query_count == 24
    assert report.answerable_count == 16
    assert report.unanswerable_count == 8
    assert report.metrics is not None
    assert report.integrity_failures == ()
    assert [item.query_id for item in report.results] == [
        query.query_id for query in load_retrieval_manifest(MANIFEST).queries
    ]


def test_public_runner_is_identical_to_explicit_current_policy() -> None:
    current = run_retrieval_evaluation(MANIFEST)
    explicit_current = _run_retrieval_evaluation(MANIFEST, query_policy="current")
    candidate = _run_retrieval_evaluation(
        MANIFEST,
        query_policy="numeric-grouping-v1",
    )

    assert current.results == explicit_current.results
    assert current.metrics == explicit_current.metrics
    assert current.status == explicit_current.status == "passed"
    assert candidate.status == "passed"


def test_unknown_query_policy_fails_before_engine_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_engine(*args: object, **kwargs: object) -> KnowledgeEngine:
        raise AssertionError("engine must not be constructed")

    monkeypatch.setattr("mke.evaluation.runner.KnowledgeEngine", unexpected_engine)

    report = _run_retrieval_evaluation(
        MANIFEST,
        query_policy="unknown",  # type: ignore[arg-type]
    )

    assert report.status == "failed"
    assert report.integrity_failures[0].problem == "retrieval_eval_incomplete"
    assert report.integrity_failures[0].cause == "retrieval query policy is unsupported"


def test_current_policy_matches_canonical_e1_semantics() -> None:
    report = _run_retrieval_evaluation(MANIFEST, query_policy="current")
    observed = json.loads(render_retrieval_json_report(report))
    canonical = json.loads(
        Path("benchmarks/retrieval/retrieval-eval-v1-baseline.json").read_text()
    )

    assert report.status == "passed"
    assert report.quality_status == "baseline_recorded"
    for key in (
        "documents",
        "queries",
        "answerable",
        "unanswerable",
        "category_counts",
        "metrics",
    ):
        assert observed[key] == canonical[key]
    assert [
        {
            **item,
            "retrieved_locators": [
                f"{locator['document_id']}:{locator['locator_kind']}:"
                f"{locator['locator_start']}..{locator['locator_end']}"
                for locator in item["retrieved_locators"]
            ],
        }
        for item in observed["results"]
    ] == canonical["results"]


def test_low_quality_is_not_an_integrity_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mke.evaluation.runner._search_locators",
        _no_search,
    )
    monkeypatch.setattr(
        "mke.evaluation.runner._ask_status",
        _refuse,
    )

    report = run_retrieval_evaluation(MANIFEST)

    assert report.status == "passed"
    assert report.quality_status == "baseline_recorded"
    assert report.metrics is not None
    assert report.metrics.locator_recall_at_5.value == 0.0


def test_nondeterministic_order_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def unstable(*args: object, **kwargs: object) -> tuple[StableLocator, ...]:
        nonlocal calls
        calls += 1
        page = 1 if calls <= 24 else 2
        return (StableLocator("usgs-volcano-hazards", "page", page, page),)

    monkeypatch.setattr("mke.evaluation.runner._search_locators", unstable)
    monkeypatch.setattr(
        "mke.evaluation.runner._ask_status",
        _find_evidence,
    )

    report = run_retrieval_evaluation(MANIFEST)

    assert report.status == "failed"
    assert report.quality_status == "not_recorded"
    assert report.integrity_failures[0].problem == "retrieval_eval_nondeterministic"


def test_corrupt_fixture_fails_before_engine_construction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = _copy_corpus(tmp_path)
    corrupt = manifest_path.parent / "eval/retrieval/usgs-volcano-hazards.pdf"
    corrupt.write_bytes(b"corrupt")

    def unexpected_engine(*args: object, **kwargs: object) -> KnowledgeEngine:
        raise AssertionError("engine must not be constructed")

    monkeypatch.setattr("mke.evaluation.runner.KnowledgeEngine", unexpected_engine)

    report = run_retrieval_evaluation(manifest_path)

    assert report.status == "failed"
    assert report.integrity_failures[0].problem == "retrieval_eval_fixture_invalid"


def test_unknown_qrel_locator_fails_after_ingest(tmp_path: Path) -> None:
    manifest_path = _copy_corpus(tmp_path)
    payload = cast(dict[str, object], json.loads(manifest_path.read_text()))
    queries = cast(list[dict[str, object]], payload["queries"])
    locators = cast(list[dict[str, object]], queries[0]["relevant_locators"])
    locators[0]["locator_start"] = 99
    locators[0]["locator_end"] = 99
    manifest_path.write_text(json.dumps(payload))

    report = run_retrieval_evaluation(manifest_path)

    assert report.status == "failed"
    assert report.integrity_failures[0].problem == "retrieval_eval_qrel_invalid"
    assert report.integrity_failures[0].subject_id == "volcano-answerable-01"


def test_duplicate_active_locator_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = KnowledgeEngine.list_active_evidence

    def duplicate(engine: KnowledgeEngine) -> list[ActiveEvidenceRef]:
        active = original(engine)
        return [*active, active[0]]

    monkeypatch.setattr(KnowledgeEngine, "list_active_evidence", duplicate)

    report = run_retrieval_evaluation(MANIFEST)

    assert report.status == "failed"
    assert report.integrity_failures[0].problem == "retrieval_eval_qrel_invalid"
    assert report.integrity_failures[0].cause == "active Evidence locator is not unique"


def test_search_and_ask_disagreement_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mke.evaluation.runner._ask_status",
        _refuse,
    )

    report = run_retrieval_evaluation(MANIFEST)

    assert report.status == "failed"
    assert report.integrity_failures[0].problem == "retrieval_eval_incomplete"
    assert report.integrity_failures[0].cause == "Search and Ask results disagree"


def test_same_snapshot_feeds_both_workspaces_and_is_cleaned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mke.evaluation import runner

    roots: list[Path] = []
    original = runner._run_workspace  # pyright: ignore[reportPrivateUsage]

    def capture_root(
        manifest: RetrievalEvaluationManifest,
        *,
        query_policy: RetrievalQueryPolicy,
    ) -> object:
        roots.append(manifest.root)
        return original(manifest, query_policy=query_policy)

    monkeypatch.setattr(runner, "_run_workspace", capture_root)

    report = run_retrieval_evaluation(MANIFEST)

    assert report.status == "passed"
    assert len(roots) == 2
    assert roots[0] == roots[1]
    assert not roots[0].exists()


def test_random_runtime_ids_do_not_appear_in_report_results() -> None:
    first = run_retrieval_evaluation(MANIFEST)
    second = run_retrieval_evaluation(MANIFEST)

    assert first.status == second.status == "passed"
    assert first.results == second.results
    for result in first.results:
        for locator in result.retrieved_locators:
            assert locator.document_id in {
                "usgs-volcano-hazards",
                "usgs-water-use-2005",
                "short-video-timestamp-proof",
            }
