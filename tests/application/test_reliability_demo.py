from pathlib import Path

import pytest

from mke.application import KnowledgeEngine, PdfIngestError
from mke.domain import FailurePoint, RunState
from tests.conftest import PDF_FIXTURES


def _texts(engine: KnowledgeEngine, query: str) -> list[str]:
    return [match.text for match in engine.search(query)]


@pytest.mark.parametrize(
    "failure_point",
    [
        FailurePoint.BEFORE_VALIDATION,
        FailurePoint.DURING_CANDIDATE_WRITES,
        FailurePoint.DURING_ACTIVE_FTS_REPLACEMENT,
        FailurePoint.AFTER_PUBLICATION_INSERT,
        FailurePoint.AFTER_ACTIVE_POINTER_SWITCH,
    ],
)
def test_failure_injection_preserves_previous_active_publication(
    tmp_path: Path, failure_point: FailurePoint
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    first = engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
    before = _texts(engine, "trustworthy")

    with pytest.raises(PdfIngestError, match=failure_point.value):
        engine.reprocess_pdf(PDF_FIXTURES / "text-layer-revised.pdf", failure_point=failure_point)

    assert _texts(engine, "trustworthy") == before
    assert _texts(engine, "revised") == []
    assert engine.get_run(first.run_id).state == RunState.PUBLISHED


def test_retry_lineage_creates_new_run_and_successfully_replaces_publication(
    tmp_path: Path,
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")

    with pytest.raises(PdfIngestError) as failure:
        engine.reprocess_pdf(
            PDF_FIXTURES / "text-layer-revised.pdf",
            failure_point=FailurePoint.BEFORE_VALIDATION,
        )
    failed_run_id = failure.value.run_id
    assert failed_run_id is not None

    retry = engine.retry_pdf(failed_run_id, PDF_FIXTURES / "text-layer-revised.pdf")

    assert retry.retry_of_run_id == failed_run_id
    assert retry.run_state == RunState.PUBLISHED
    assert _texts(engine, "starts") == []
    assert _texts(engine, "revised") == ["Revised trustworthy evidence replaces page one."]


def test_activation_failure_leaves_validated_run_retryable(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")

    with pytest.raises(PdfIngestError) as failure:
        engine.reprocess_pdf(
            PDF_FIXTURES / "text-layer-revised.pdf",
            failure_point=FailurePoint.AFTER_PUBLICATION_INSERT,
        )
    run_id = failure.value.run_id
    assert run_id is not None

    assert engine.get_run(run_id).state == RunState.VALIDATED
    assert _texts(engine, "revised") == []

    activation = engine.activate_publication(run_id)

    assert activation.published is True
    assert _texts(engine, "revised") == ["Revised trustworthy evidence replaces page one."]


def test_activation_conflict_supersedes_stale_run_without_search_change(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
    stale = engine.prepare_pdf_candidate(PDF_FIXTURES / "text-layer-revised.pdf")
    newer = engine.reprocess_pdf(PDF_FIXTURES / "text-layer.pdf")

    activation = engine.activate_publication(
        stale.run_id, failure_point=FailurePoint.DURING_ACTIVATION_CONFLICT
    )

    assert activation.published is False
    assert activation.run_state == RunState.SUPERSEDED
    assert engine.get_run(stale.run_id).state == RunState.SUPERSEDED
    assert engine.get_run(newer.run_id).state == RunState.PUBLISHED
    assert _texts(engine, "revised") == []


def test_startup_marks_unfinished_runs_interrupted(tmp_path: Path) -> None:
    db_path = tmp_path / "mke.sqlite"
    engine = KnowledgeEngine(db_path)
    prepared = engine.prepare_pdf_candidate(
        PDF_FIXTURES / "text-layer.pdf", leave_running_for_test=True
    )
    engine.close()

    restarted = KnowledgeEngine(db_path)

    assert restarted.get_run(prepared.run_id).state == RunState.INTERRUPTED
    assert [event.event_type for event in restarted.get_run_events(prepared.run_id)][-1] == (
        "run_interrupted"
    )


def test_run_events_are_append_only_and_queryable(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    result = engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")

    assert [event.event_type for event in engine.get_run_events(result.run_id)] == [
        "run_created",
        "run_started",
        "candidate_validated",
        "publication_activated",
    ]
