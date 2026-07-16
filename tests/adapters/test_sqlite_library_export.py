from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from mke.adapters.sqlite import SQLiteStore
from mke.application import KnowledgeEngine
from mke.domain import LibraryExportDataError, RunState


def populated_database(tmp_path: Path) -> Path:
    db_path = tmp_path / "mke.sqlite"
    store = SQLiteStore(db_path)
    try:
        store.ensure_source("example.pdf", "a" * 64)
    finally:
        store.close()
    return db_path


def test_read_only_export_does_not_create_missing_database(tmp_path: Path) -> None:
    db_path = tmp_path / "missing.sqlite"

    with pytest.raises(sqlite3.OperationalError):
        SQLiteStore.open_read_only_export(db_path)

    assert not db_path.exists()


def test_read_only_export_sets_query_only_without_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = populated_database(tmp_path)
    before = db_path.read_bytes()

    def fail_owner_startup(*args: object, **kwargs: object) -> None:
        raise AssertionError("owner startup must not run for export")

    monkeypatch.setattr(SQLiteStore, "migrate", fail_owner_startup)
    monkeypatch.setattr(SQLiteStore, "_probe_fts5", fail_owner_startup)
    store = SQLiteStore.open_read_only_export(db_path)
    try:
        assert store._connection.execute("PRAGMA query_only").fetchone()[0] == 1  # pyright: ignore[reportPrivateUsage]
        with pytest.raises(sqlite3.OperationalError):
            store._connection.execute("UPDATE runs SET state = 'failed'")  # pyright: ignore[reportPrivateUsage]
    finally:
        store.close()

    assert db_path.read_bytes() == before


def test_read_only_export_rejects_incompatible_schema_without_mutation(
    tmp_path: Path,
) -> None:
    db_path = populated_database(tmp_path)
    connection = sqlite3.connect(db_path)
    connection.execute("ALTER TABLE assets DROP COLUMN media_type")
    connection.close()
    before = db_path.read_bytes()

    with pytest.raises(LibraryExportDataError) as exc_info:
        SQLiteStore.open_read_only_export(db_path)

    assert exc_info.value.reason == "provenance"
    assert db_path.read_bytes() == before


def test_read_only_export_does_not_recover_unfinished_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = populated_database(tmp_path)
    owner = SQLiteStore(db_path)
    try:
        source = owner.get_first_source()
        assert source is not None
        run_id = owner.create_run(source.source_id).run_id
    finally:
        owner.close()
    before = db_path.read_bytes()

    def fail_owner_startup(*args: object, **kwargs: object) -> None:
        raise AssertionError("owner startup must not run for export")

    monkeypatch.setattr(SQLiteStore, "migrate", fail_owner_startup)
    monkeypatch.setattr(SQLiteStore, "_probe_fts5", fail_owner_startup)
    monkeypatch.setattr(KnowledgeEngine, "recover_unfinished_runs", fail_owner_startup)
    engine = KnowledgeEngine.open_read_only_export(db_path)
    try:
        assert engine.get_run(run_id).state is RunState.QUEUED
    finally:
        engine.close()

    assert db_path.read_bytes() == before
