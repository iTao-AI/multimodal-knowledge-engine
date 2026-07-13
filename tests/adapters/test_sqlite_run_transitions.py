from pathlib import Path

import pytest

from mke.adapters.sqlite import SQLiteStore
from mke.domain import (
    PYMUPDF_TEXT_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    CandidateEvidence,
    RunManifest,
    RunState,
    RunTransitionError,
)


def _running_run(store: SQLiteStore) -> str:
    source = store.ensure_source("fixture.pdf", "a" * 64)
    run = store.create_run(source.source_id)
    store.mark_run_running(run.run_id)
    return run.run_id


def test_interrupted_run_cannot_be_validated_or_append_event(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "mke.sqlite")
    run_id = _running_run(store)
    store.interrupt_unfinished_runs()
    before = store.get_run_events(run_id)

    with pytest.raises(RunTransitionError) as error:
        store.persist_validated_candidate(
            run_id,
            [CandidateEvidence("ev_1", "page", 1, 1, "trusted text")],
            RunManifest(
                run_id,
                1,
                tuple(sorted(REQUIRED_PDF_STAGES)),
                PYMUPDF_TEXT_FINGERPRINT,
                "a" * 64,
            ),
        )

    assert error.value.actual is RunState.INTERRUPTED
    assert store.get_run(run_id).state is RunState.INTERRUPTED
    assert store.get_run_events(run_id) == before
    row = store._connection.execute(  # pyright: ignore[reportPrivateUsage]
        "SELECT COUNT(*) AS count FROM evidence WHERE run_id = ?", (run_id,)
    ).fetchone()
    assert row is not None
    assert int(row["count"]) == 0


def test_second_running_transition_has_no_duplicate_event(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "mke.sqlite")
    run_id = _running_run(store)
    before = store.get_run_events(run_id)
    with pytest.raises(RunTransitionError):
        store.mark_run_running(run_id)
    assert store.get_run_events(run_id) == before
