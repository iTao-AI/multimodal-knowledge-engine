from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from mke.adapters.sqlite import SQLiteStore
from mke.application import KnowledgeEngine
from mke.domain import (
    REQUIRED_PDF_STAGES,
    REQUIRED_VIDEO_STAGES,
    CompiledLibrarySnapshot,
    ExportLimits,
    LibraryExportDataError,
    RunState,
)
from tests.conftest import PDF_FIXTURES, VIDEO_FIXTURES


def _copy_fixture(source: Path, target: Path) -> Path:
    shutil.copy2(source, target)
    return target


def _published_database(tmp_path: Path, *, active_sources: int = 2) -> Path:
    db_path = tmp_path / "published.sqlite"
    engine = KnowledgeEngine(db_path)
    try:
        pdf = _copy_fixture(PDF_FIXTURES / "text-layer.pdf", tmp_path / "renamed.pdf")
        engine.ingest_pdf(pdf)
        if active_sources >= 2:
            video = _copy_fixture(VIDEO_FIXTURES / "short-audio.mp4", tmp_path / "renamed.mp4")
            _copy_fixture(
                VIDEO_FIXTURES / "short-audio.mp4.mke-transcript.json",
                video.with_suffix(video.suffix + ".mke-transcript.json"),
            )
            engine.ingest_video(video)
        if active_sources >= 3:
            revised = _copy_fixture(
                PDF_FIXTURES / "text-layer-revised.pdf", tmp_path / "revised.pdf"
            )
            engine.ingest_pdf(revised)
        engine.ensure_source("inactive.pdf", "f" * 64)
    finally:
        engine.close()
    for path in tmp_path.glob("renamed.*"):
        path.rename(path.with_name("unavailable-" + path.name))
    return db_path


def _active_graph(connection: sqlite3.Connection) -> tuple[tuple[object, ...], ...]:
    return tuple(
        tuple(row)
        for row in connection.execute(
            """
            SELECT sources.source_id, sources.library_id, sources.asset_id,
                   sources.active_publication_id, sources.active_revision,
                   publications.source_id, publications.run_id, publications.revision,
                   runs.source_id, runs.state, run_manifests.evidence_count,
                   run_manifests.required_stages, run_manifests.extractor_fingerprint,
                   run_manifests.asset_sha256
            FROM sources
            LEFT JOIN publications
              ON publications.publication_id = sources.active_publication_id
            LEFT JOIN runs ON runs.run_id = publications.run_id
            LEFT JOIN run_manifests ON run_manifests.run_id = runs.run_id
            ORDER BY sources.source_id
            """
        ).fetchall()
    )


def _authority_rows(db_path: Path) -> list[sqlite3.Row]:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute(
            """
            SELECT sources.source_id, sources.display_name, assets.media_type, assets.sha256,
                   publications.publication_id, publications.revision, publications.run_id,
                   run_manifests.required_stages, run_manifests.extractor_fingerprint,
                   evidence.evidence_id, evidence.locator_kind, evidence.locator_start,
                   evidence.locator_end, evidence.text
            FROM sources
            JOIN assets ON assets.asset_id = sources.asset_id
            JOIN publications ON publications.publication_id = sources.active_publication_id
            JOIN run_manifests ON run_manifests.run_id = publications.run_id
            JOIN evidence ON evidence.run_id = publications.run_id
            ORDER BY assets.sha256, sources.source_id, evidence.locator_kind,
                     evidence.locator_start, evidence.locator_end, evidence.evidence_id
            """
        ).fetchall()
    finally:
        connection.close()


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


def test_read_only_export_rejects_schema_missing_library_name_without_mutation(
    tmp_path: Path,
) -> None:
    db_path = populated_database(tmp_path)
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        PRAGMA foreign_keys = OFF;
        CREATE TABLE libraries_replacement (library_id TEXT PRIMARY KEY);
        INSERT INTO libraries_replacement SELECT library_id FROM libraries;
        DROP TABLE libraries;
        ALTER TABLE libraries_replacement RENAME TO libraries;
        """
    )
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


def test_compiled_snapshot_reads_complete_active_pdf_and_video_from_sqlite(
    tmp_path: Path,
) -> None:
    db_path = _published_database(tmp_path)
    authority = _authority_rows(db_path)

    store = SQLiteStore.open_read_only_export(db_path)
    try:
        snapshot = store.compiled_library_snapshot()
    finally:
        store.close()

    assert snapshot.observation.source_count == 3
    assert snapshot.observation.active_publication_count == 2
    assert len(snapshot.sources) == 2
    actual = [
        (
            source.source_id,
            source.display_name,
            source.media_type,
            source.content_fingerprint.removeprefix("sha256:"),
            source.publication_id,
            source.publication_revision,
            source.run_id,
            source.required_stages,
            source.extractor_fingerprint,
            item.evidence_id,
            item.locator_kind,
            item.locator_start,
            item.locator_end,
            item.text,
        )
        for source in snapshot.sources
        for item in source.evidence
    ]
    expected = [
        (
            str(row["source_id"]),
            str(row["display_name"]),
            str(row["media_type"]),
            str(row["sha256"]),
            str(row["publication_id"]),
            int(row["revision"]),
            str(row["run_id"]),
            tuple(str(row["required_stages"]).split(",")),
            str(row["extractor_fingerprint"]),
            str(row["evidence_id"]),
            str(row["locator_kind"]),
            int(row["locator_start"]),
            int(row["locator_end"]),
            str(row["text"]),
        )
        for row in authority
    ]
    assert actual == expected
    assert {item.locator_kind for source in snapshot.sources for item in source.evidence} == {
        "page",
        "timestamp_ms",
    }
    assert all(
        source.evidence
        == tuple(
            sorted(
                source.evidence,
                key=lambda item: (
                    item.locator_kind,
                    item.locator_start,
                    item.locator_end,
                    item.evidence_id,
                ),
            )
        )
        for source in snapshot.sources
    )


def test_pdf_and_video_export_preserves_comma_joined_manifest_storage(
    tmp_path: Path,
) -> None:
    db_path = _published_database(tmp_path)
    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            """
            SELECT assets.media_type, run_manifests.required_stages
            FROM sources
            JOIN assets ON assets.asset_id = sources.asset_id
            JOIN publications ON publications.publication_id = sources.active_publication_id
            JOIN run_manifests ON run_manifests.run_id = publications.run_id
            ORDER BY assets.media_type
            """
        ).fetchall()
    finally:
        connection.close()
    assert rows == [
        ("application/pdf", ",".join(sorted(REQUIRED_PDF_STAGES))),
        ("video/mp4", ",".join(sorted(REQUIRED_VIDEO_STAGES))),
    ]

    store = SQLiteStore.open_read_only_export(db_path)
    try:
        snapshot = store.compiled_library_snapshot()
    finally:
        store.close()
    assert {source.required_stages for source in snapshot.sources} == {
        tuple(sorted(REQUIRED_PDF_STAGES)),
        tuple(sorted(REQUIRED_VIDEO_STAGES)),
    }


def _mutate_corruption(db_path: Path, corruption: str) -> None:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        active = connection.execute(
            """
            SELECT sources.source_id, sources.asset_id, sources.active_publication_id,
                   publications.run_id
            FROM sources
            JOIN publications ON publications.publication_id = sources.active_publication_id
            ORDER BY sources.source_id
            """
        ).fetchall()
        first, second = active[:2]
        first_source = str(first["source_id"])
        second_source = str(second["source_id"])
        first_publication = str(first["active_publication_id"])
        second_publication = str(second["active_publication_id"])
        first_run = str(first["run_id"])
        second_run = str(second["run_id"])
        statements: dict[str, tuple[str, tuple[object, ...]]] = {
            "library_ownership": (
                "UPDATE sources SET library_id = 'lib_foreign' WHERE source_id = ?",
                (first_source,),
            ),
            "active_pointer": (
                "UPDATE sources SET active_publication_id = ? WHERE source_id = ?",
                (second_publication, first_source),
            ),
            "publication_source": (
                "UPDATE publications SET source_id = ? WHERE publication_id = ?",
                (second_source, first_publication),
            ),
            "run_source": (
                "UPDATE runs SET source_id = ? WHERE run_id = ?",
                (second_source, first_run),
            ),
            "run_state": (
                "UPDATE runs SET state = 'running' WHERE run_id = ?",
                (first_run,),
            ),
            "revision": (
                "UPDATE sources SET active_revision = active_revision + 1 WHERE source_id = ?",
                (first_source,),
            ),
            "manifest_asset": (
                "UPDATE run_manifests SET asset_sha256 = ? WHERE run_id = ?",
                ("0" * 64, first_run),
            ),
            "manifest_count": (
                "UPDATE run_manifests SET evidence_count = evidence_count + 1 WHERE run_id = ?",
                (first_run,),
            ),
            "manifest_stages_json_shaped": (
                "UPDATE run_manifests SET required_stages = "
                "'[\"extract\",\"segment\",\"validate\"]' WHERE run_id = ?",
                (first_run,),
            ),
            "manifest_stages_empty_token": (
                "UPDATE run_manifests "
                "SET required_stages = 'extract,,segment' WHERE run_id = ?",
                (first_run,),
            ),
            "manifest_stages_duplicate": (
                "UPDATE run_manifests "
                "SET required_stages = 'extract,extract' WHERE run_id = ?",
                (first_run,),
            ),
            "manifest_stages_unsorted": (
                "UPDATE run_manifests SET required_stages = "
                "'validate,extract,segment' WHERE run_id = ?",
                (first_run,),
            ),
            "manifest_stages_whitespace": (
                "UPDATE run_manifests SET required_stages = "
                "'extract, segment,validate' WHERE run_id = ?",
                (first_run,),
            ),
            "manifest_extractor": (
                "UPDATE run_manifests SET extractor_fingerprint = 'unsupported' WHERE run_id = ?",
                (first_run,),
            ),
            "evidence_source": (
                "UPDATE evidence SET source_id = ? WHERE run_id = ?",
                (second_source, first_run),
            ),
            "evidence_run": (
                "UPDATE evidence SET run_id = ? WHERE run_id = ?",
                (second_run, first_run),
            ),
            "locator": (
                "UPDATE evidence SET locator_start = -1 WHERE run_id = ?",
                (first_run,),
            ),
            "media_type": (
                "UPDATE assets SET media_type = 'text/plain' WHERE asset_id = ?",
                (str(first["asset_id"]),),
            ),
        }
        if corruption == "duplicate_fingerprint":
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.executescript(
                """
                CREATE TABLE sources_replacement (
                  source_id TEXT PRIMARY KEY,
                  library_id TEXT NOT NULL REFERENCES libraries(library_id),
                  asset_id TEXT NOT NULL REFERENCES assets(asset_id),
                  display_name TEXT NOT NULL,
                  active_publication_id TEXT,
                  active_revision INTEGER NOT NULL DEFAULT 0,
                  requested_generation INTEGER NOT NULL DEFAULT 0
                );
                INSERT INTO sources_replacement SELECT * FROM sources;
                DROP TABLE sources;
                ALTER TABLE sources_replacement RENAME TO sources;
                """
            )
            connection.execute(
                "UPDATE sources SET asset_id = ? WHERE source_id = ?",
                (str(first["asset_id"]), second_source),
            )
        else:
            sql, params = statements[corruption]
            connection.execute(sql, params)
        connection.commit()
    finally:
        connection.close()


@pytest.mark.parametrize(
    "corruption",
    [
        "library_ownership",
        "active_pointer",
        "publication_source",
        "run_source",
        "run_state",
        "revision",
        "manifest_asset",
        "manifest_count",
        "manifest_stages_json_shaped",
        "manifest_stages_empty_token",
        "manifest_stages_duplicate",
        "manifest_stages_unsorted",
        "manifest_stages_whitespace",
        "manifest_extractor",
        "evidence_source",
        "evidence_run",
        "locator",
        "duplicate_fingerprint",
        "media_type",
    ],
)
def test_compiled_snapshot_rejects_corrupt_active_graph_without_mutation(
    tmp_path: Path, corruption: str
) -> None:
    db_path = _published_database(tmp_path)
    _mutate_corruption(db_path, corruption)
    store = SQLiteStore.open_read_only_export(db_path)
    before = _active_graph(store._connection)  # pyright: ignore[reportPrivateUsage]
    statements: list[str] = []
    store._connection.set_trace_callback(statements.append)  # pyright: ignore[reportPrivateUsage]
    try:
        with pytest.raises(LibraryExportDataError) as exc_info:
            store.compiled_library_snapshot()
        assert exc_info.value.reason == "provenance"
        assert any(statement == "ROLLBACK" for statement in statements)
        assert _active_graph(store._connection) == before  # pyright: ignore[reportPrivateUsage]
    finally:
        store._connection.set_trace_callback(None)  # pyright: ignore[reportPrivateUsage]
        store.close()


def test_compiled_snapshot_rejects_missing_asset_without_partial_success(
    tmp_path: Path,
) -> None:
    db_path = _published_database(tmp_path)
    writer = sqlite3.connect(db_path)
    try:
        writer.execute("PRAGMA foreign_keys = OFF")
        asset_id = writer.execute(
            """
            SELECT sources.asset_id
            FROM sources
            WHERE sources.active_publication_id IS NOT NULL
            ORDER BY sources.source_id LIMIT 1
            """
        ).fetchone()[0]
        writer.execute("DELETE FROM assets WHERE asset_id = ?", (asset_id,))
        writer.commit()
        violations = writer.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        writer.close()
    assert any(
        table == "sources" and parent == "assets"
        for table, _rowid, parent, _foreign_key_index in violations
    )

    store = SQLiteStore.open_read_only_export(db_path)
    before = _active_graph(store._connection)  # pyright: ignore[reportPrivateUsage]
    statements: list[str] = []
    store._connection.set_trace_callback(statements.append)  # pyright: ignore[reportPrivateUsage]
    try:
        with pytest.raises(LibraryExportDataError) as exc_info:
            store.compiled_library_snapshot()
        assert exc_info.value.reason == "provenance"
        assert any(statement == "ROLLBACK" for statement in statements)
        assert _active_graph(store._connection) == before  # pyright: ignore[reportPrivateUsage]
    finally:
        store._connection.set_trace_callback(None)  # pyright: ignore[reportPrivateUsage]
        store.close()


@pytest.mark.parametrize(
    "runtime_type_drift",
    ["display_name", "evidence_text", "locator", "publication_revision"],
)
def test_compiled_snapshot_rejects_blob_authority_values_without_coercion(
    tmp_path: Path, runtime_type_drift: str
) -> None:
    db_path = _published_database(tmp_path)
    writer = sqlite3.connect(db_path)
    try:
        row = writer.execute(
            """
            SELECT sources.source_id, sources.active_publication_id, publications.run_id
            FROM sources
            JOIN publications ON publications.publication_id = sources.active_publication_id
            ORDER BY sources.source_id LIMIT 1
            """
        ).fetchone()
        assert row is not None
        source_id, publication_id, run_id = (str(value) for value in row)
        if runtime_type_drift == "display_name":
            writer.execute(
                "UPDATE sources SET display_name = CAST(display_name AS BLOB) "
                "WHERE source_id = ?",
                (source_id,),
            )
        elif runtime_type_drift == "evidence_text":
            writer.execute(
                "UPDATE evidence SET text = CAST(text AS BLOB) WHERE run_id = ?",
                (run_id,),
            )
        elif runtime_type_drift == "locator":
            writer.execute(
                "UPDATE evidence SET locator_start = CAST(locator_start AS BLOB) "
                "WHERE run_id = ?",
                (run_id,),
            )
        else:
            writer.execute(
                "UPDATE sources SET active_revision = CAST(active_revision AS BLOB) "
                "WHERE source_id = ?",
                (source_id,),
            )
            writer.execute(
                "UPDATE publications SET revision = CAST(revision AS BLOB) "
                "WHERE publication_id = ?",
                (publication_id,),
            )
        writer.commit()
    finally:
        writer.close()
    before = db_path.read_bytes()

    store = SQLiteStore.open_read_only_export(db_path)
    statements: list[str] = []
    store._connection.set_trace_callback(statements.append)  # pyright: ignore[reportPrivateUsage]
    try:
        with pytest.raises(LibraryExportDataError) as exc_info:
            store.compiled_library_snapshot()
        assert exc_info.value.reason == "provenance"
        assert any(statement == "ROLLBACK" for statement in statements)
    finally:
        store._connection.set_trace_callback(None)  # pyright: ignore[reportPrivateUsage]
        store.close()
    assert db_path.read_bytes() == before


def test_compiled_snapshot_applies_exact_utf8_and_count_preflight_limits(
    tmp_path: Path,
) -> None:
    db_path = _published_database(tmp_path)
    writer = sqlite3.connect(db_path)
    try:
        writer.execute(
            """
            UPDATE evidence SET text = text || '可信'
            WHERE evidence_id = (
              SELECT evidence_id FROM evidence ORDER BY evidence_id LIMIT 1
            )
            """
        )
        writer.commit()
        count, utf8_bytes = writer.execute(
            "SELECT COUNT(*), SUM(length(CAST(text AS BLOB))) FROM evidence"
        ).fetchone()
    finally:
        writer.close()
    assert count == 4
    store = SQLiteStore.open_read_only_export(db_path)
    try:
        exact = ExportLimits(2, int(count), int(utf8_bytes), 1024)
        snapshot = store.compiled_library_snapshot(limits=exact)
        assert snapshot.evidence_utf8_bytes == utf8_bytes
        too_small = (
            ExportLimits(1, int(count), int(utf8_bytes), 1024),
            ExportLimits(2, int(count) - 1, int(utf8_bytes), 1024),
            ExportLimits(2, int(count), int(utf8_bytes) - 1, 1024),
        )
        for limits in too_small:
            with pytest.raises(LibraryExportDataError) as exc_info:
                store.compiled_library_snapshot(limits=limits)
            assert exc_info.value.reason == "too_large"
    finally:
        store.close()


def test_preflight_limit_rejects_before_evidence_materialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = _published_database(tmp_path)
    store = SQLiteStore.open_read_only_export(db_path)

    def fail_evidence_read() -> list[sqlite3.Row]:
        raise AssertionError("Evidence rows must not materialize after failed preflight")

    monkeypatch.setattr(store, "_read_export_evidence_rows", fail_evidence_read)
    try:
        with pytest.raises(LibraryExportDataError) as exc_info:
            store.compiled_library_snapshot(limits=ExportLimits(1, 1, 1, 1))
        assert exc_info.value.reason == "too_large"
    finally:
        store.close()


@pytest.mark.parametrize("active_sources", [1, 3])
def test_compiled_snapshot_uses_exactly_five_data_selects(
    tmp_path: Path, active_sources: int
) -> None:
    db_path = _published_database(tmp_path, active_sources=active_sources)
    store = SQLiteStore.open_read_only_export(db_path)
    statements: list[str] = []
    store._connection.set_trace_callback(statements.append)  # pyright: ignore[reportPrivateUsage]
    try:
        snapshot = store.compiled_library_snapshot()
    finally:
        store._connection.set_trace_callback(None)  # pyright: ignore[reportPrivateUsage]
        store.close()
    selects = [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith("SELECT")
    ]
    assert snapshot.observation.active_publication_count == active_sources
    assert len(selects) == 5
    assert sum("FROM libraries" in statement for statement in selects) == 1
    assert sum("COUNT(*) AS source_count" in statement for statement in selects) == 1
    assert sum("AS active_pointer_count" in statement for statement in selects) == 1
    assert sum("SUM(length(CAST(text AS BLOB)))" in statement for statement in selects) == 1
    assert sum("FROM evidence" in statement for statement in selects) == 1


def test_compiled_snapshot_is_coherent_across_wal_write_after_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = _published_database(tmp_path)
    before_store = SQLiteStore.open_read_only_export(db_path)
    try:
        before = before_store.compiled_library_snapshot()
    finally:
        before_store.close()

    store = SQLiteStore.open_read_only_export(db_path)
    writer = sqlite3.connect(db_path)
    target = writer.execute(
        """
        SELECT sources.source_id, publications.run_id
        FROM sources
        JOIN publications ON publications.publication_id = sources.active_publication_id
        ORDER BY sources.source_id LIMIT 1
        """
    ).fetchone()
    assert target is not None
    target_source_id, target_run_id = (str(value) for value in target)
    original_read = store._read_export_evidence_rows  # pyright: ignore[reportPrivateUsage]
    changed_name = "concurrent-valid-name.pdf"
    changed_suffix = " concurrent replacement"
    after: list[CompiledLibrarySnapshot] = []

    def mutate_then_read() -> list[sqlite3.Row]:
        with writer:
            writer.execute(
                "UPDATE sources SET display_name = ? WHERE source_id = ?",
                (changed_name, target_source_id),
            )
            writer.execute(
                "UPDATE evidence SET text = text || ? WHERE run_id = ?",
                (changed_suffix, target_run_id),
            )
        after_store = SQLiteStore.open_read_only_export(db_path)
        try:
            after.append(after_store.compiled_library_snapshot())
        finally:
            after_store.close()
        return original_read()

    monkeypatch.setattr(store, "_read_export_evidence_rows", mutate_then_read)
    try:
        raced = store.compiled_library_snapshot()
    finally:
        writer.close()
        store.close()
    assert len(after) == 1
    after_snapshot = after[0]
    assert before != after_snapshot
    before_source = next(
        source for source in before.sources if source.source_id == target_source_id
    )
    after_source = next(
        source for source in after_snapshot.sources if source.source_id == target_source_id
    )
    assert before_source.display_name != changed_name
    assert after_source.display_name == changed_name
    assert all(not item.text.endswith(changed_suffix) for item in before_source.evidence)
    assert all(item.text.endswith(changed_suffix) for item in after_source.evidence)
    assert before.observation == after_snapshot.observation
    assert raced == before or raced == after_snapshot
    assert raced.observation.active_evidence_count == sum(
        len(source.evidence) for source in raced.sources
    )
