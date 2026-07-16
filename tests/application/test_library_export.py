from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from mke.application import KnowledgeEngine
from mke.domain import LibraryExportDataError
from tests.conftest import PDF_FIXTURES


def _active_state(connection: sqlite3.Connection) -> tuple[tuple[object, ...], ...]:
    return tuple(
        tuple(row)
        for row in connection.execute(
            """
            SELECT sources.source_id, sources.active_publication_id, sources.active_revision,
                   publications.run_id, publications.revision, runs.state,
                   run_manifests.evidence_count, run_manifests.asset_sha256
            FROM sources
            LEFT JOIN publications
              ON publications.publication_id = sources.active_publication_id
            LEFT JOIN runs ON runs.run_id = publications.run_id
            LEFT JOIN run_manifests ON run_manifests.run_id = runs.run_id
            ORDER BY sources.source_id
            """
        ).fetchall()
    )


def test_application_delegates_compiled_snapshot_on_query_only_connection(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mke.sqlite"
    owner = KnowledgeEngine(db_path)
    try:
        owner.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
    finally:
        owner.close()

    engine = KnowledgeEngine.open_read_only_export(db_path)
    connection = engine._store._connection  # pyright: ignore[reportPrivateUsage]
    before = _active_state(connection)
    try:
        snapshot = engine.compiled_library_snapshot()
        assert snapshot.observation.active_publication_count == 1
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        assert _active_state(connection) == before
    finally:
        engine.close()


def test_application_failure_rolls_back_and_preserves_query_only_state(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mke.sqlite"
    owner = KnowledgeEngine(db_path)
    try:
        result = owner.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
        connection = owner._store._connection  # pyright: ignore[reportPrivateUsage]
        connection.execute(
            "UPDATE run_manifests SET evidence_count = evidence_count + 1 WHERE run_id = ?",
            (result.run_id,),
        )
        connection.commit()
    finally:
        owner.close()

    engine = KnowledgeEngine.open_read_only_export(db_path)
    connection = engine._store._connection  # pyright: ignore[reportPrivateUsage]
    before = _active_state(connection)
    statements: list[str] = []
    connection.set_trace_callback(statements.append)
    try:
        with pytest.raises(LibraryExportDataError) as exc_info:
            engine.compiled_library_snapshot()
        assert exc_info.value.reason == "provenance"
        assert any(statement == "ROLLBACK" for statement in statements)
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        assert _active_state(connection) == before
    finally:
        connection.set_trace_callback(None)
        engine.close()
