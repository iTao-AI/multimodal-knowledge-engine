import sqlite3
from pathlib import Path

from mke.adapters.sqlite import SQLiteStore
from mke.application import KnowledgeEngine
from mke.domain import RunEventType
from tests.conftest import PDF_FIXTURES


def test_pr2_database_schema_is_migrated_for_retry_lineage_and_events(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.sqlite"
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE libraries (library_id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE);
        CREATE TABLE assets (
          asset_id TEXT PRIMARY KEY,
          sha256 TEXT NOT NULL UNIQUE,
          media_type TEXT NOT NULL
        );
        CREATE TABLE sources (
          source_id TEXT PRIMARY KEY,
          library_id TEXT NOT NULL REFERENCES libraries(library_id),
          asset_id TEXT NOT NULL REFERENCES assets(asset_id),
          display_name TEXT NOT NULL,
          active_publication_id TEXT,
          active_revision INTEGER NOT NULL DEFAULT 0,
          requested_generation INTEGER NOT NULL DEFAULT 0,
          UNIQUE(library_id, asset_id)
        );
        CREATE TABLE runs (
          run_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL REFERENCES sources(source_id),
          state TEXT NOT NULL,
          source_generation INTEGER NOT NULL,
          based_on_active_revision INTEGER NOT NULL
        );
        CREATE TABLE run_manifests (
          run_id TEXT PRIMARY KEY REFERENCES runs(run_id),
          evidence_count INTEGER NOT NULL,
          required_stages TEXT NOT NULL,
          extractor_fingerprint TEXT NOT NULL,
          asset_sha256 TEXT NOT NULL
        );
        CREATE TABLE evidence (
          evidence_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL REFERENCES runs(run_id),
          source_id TEXT NOT NULL REFERENCES sources(source_id),
          locator_kind TEXT NOT NULL,
          locator_start INTEGER NOT NULL,
          locator_end INTEGER NOT NULL,
          text TEXT NOT NULL
        );
        CREATE TABLE publications (
          publication_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL REFERENCES sources(source_id),
          run_id TEXT NOT NULL UNIQUE REFERENCES runs(run_id),
          revision INTEGER NOT NULL
        );
        CREATE TABLE run_events (
          event_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL REFERENCES runs(run_id),
          event_type TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE active_evidence_fts USING fts5(
          library_id UNINDEXED,
          source_id UNINDEXED,
          publication_id UNINDEXED,
          evidence_id UNINDEXED,
          locator_label UNINDEXED,
          text
        );
        """
    )
    connection.close()

    engine = KnowledgeEngine(db_path)
    result = engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")

    assert result.run_state.value == "published"
    assert [event.event_type for event in engine.get_run_events(result.run_id)] == [
        RunEventType.RUN_CREATED,
        RunEventType.RUN_STARTED,
        RunEventType.CANDIDATE_VALIDATED,
        RunEventType.PUBLICATION_ACTIVATED,
    ]


def test_migration_creates_transcript_intake_reports_table(tmp_path: Path) -> None:
    db_path = tmp_path / "mke.sqlite"
    store = SQLiteStore(db_path)
    store.close()

    connection = sqlite3.connect(db_path)
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("transcript_intake_reports",),
    ).fetchone()
    connection.close()

    assert row == ("transcript_intake_reports",)
