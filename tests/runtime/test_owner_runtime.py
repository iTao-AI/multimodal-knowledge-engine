from pathlib import Path

from mke.adapters.sqlite import SQLiteStore
from mke.application import KnowledgeEngine
from mke.domain import RunState
from mke.runtime import RuntimeConfig, build_engine
from tests.conftest import PDF_FIXTURES


def _leave_running(db_path: Path) -> str:
    engine = KnowledgeEngine(db_path)
    try:
        return engine.prepare_pdf_candidate(
            PDF_FIXTURES / "text-layer.pdf",
            leave_running_for_test=True,
        ).run_id
    finally:
        engine.close()


def test_sqlite_store_construction_does_not_recover_runs(tmp_path: Path) -> None:
    db_path = tmp_path / "mke.sqlite"
    run_id = _leave_running(db_path)
    store = SQLiteStore(db_path)
    try:
        assert store.get_run(run_id).state is RunState.RUNNING
    finally:
        store.close()


def test_shared_runtime_recovers_only_on_first_engine_build(tmp_path: Path) -> None:
    db_path = tmp_path / "mke.sqlite"
    old_run_id = _leave_running(db_path)
    runtime = RuntimeConfig(db_path)
    first = build_engine(runtime)
    assert first.get_run(old_run_id).state is RunState.INTERRUPTED
    live_run_id = first.prepare_pdf_candidate(
        PDF_FIXTURES / "text-layer.pdf",
        leave_running_for_test=True,
    ).run_id
    first.close()
    second = build_engine(runtime)
    try:
        assert second.get_run(live_run_id).state is RunState.RUNNING
    finally:
        second.close()
