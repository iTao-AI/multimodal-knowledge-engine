import sqlite3
from pathlib import Path

import pytest

from mke.application import KnowledgeEngine
from mke.domain import ManifestValidationError
from tests.conftest import PDF_FIXTURES, VIDEO_FIXTURES


def test_snapshot_enriches_pdf_and_video_provenance(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
        page = engine._store.search_provenance_snapshot("publication active", 5)  # pyright: ignore[reportPrivateUsage]
        engine.ingest_video(VIDEO_FIXTURES / "short-audio.mp4")
        timestamp = engine._store.search_provenance_snapshot("timestamp proof", 5)  # pyright: ignore[reportPrivateUsage]
        assert page.observation.state == "active"
        assert page.results[0].content_fingerprint.startswith("sha256:")
        assert page.results[0].result.locator_kind == "page"
        assert timestamp.results[0].result.locator_kind == "timestamp_ms"
    finally:
        engine.close()


def test_observation_distinguishes_empty_and_no_active(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        assert engine._store.observe_active_publications().state == "empty"  # pyright: ignore[reportPrivateUsage]
        engine.prepare_pdf_candidate(PDF_FIXTURES / "text-layer.pdf")
        assert engine._store.observe_active_publications().state == "no_active_publication"  # pyright: ignore[reportPrivateUsage]
    finally:
        engine.close()


@pytest.mark.parametrize(
    "corruption",
    [
        "library",
        "active_pointer",
        "publication_source",
        "run_source",
        "run_state",
        "revision",
        "manifest_count",
        "fingerprint",
        "evidence_source",
        "evidence_run",
    ],
)
def test_corrupt_active_provenance_graph_fails_closed(
    tmp_path: Path, corruption: str
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        first = engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
        second = engine.ingest_pdf(PDF_FIXTURES / "text-layer-revised.pdf")
        connection = engine._store._connection  # pyright: ignore[reportPrivateUsage]
        first_row = connection.execute(
            """
            SELECT sources.source_id, sources.active_publication_id, publications.revision
            FROM sources
            JOIN publications ON publications.publication_id = sources.active_publication_id
            WHERE publications.run_id = ?
            """,
            (first.run_id,),
        ).fetchone()
        second_row = connection.execute(
            """
            SELECT sources.source_id, sources.active_publication_id
            FROM sources
            JOIN publications ON publications.publication_id = sources.active_publication_id
            WHERE publications.run_id = ?
            """,
            (second.run_id,),
        ).fetchone()
        assert first_row is not None and second_row is not None
        source_id = str(first_row["source_id"])
        other_source_id = str(second_row["source_id"])
        publication_id = str(first_row["active_publication_id"])
        statements: dict[str, tuple[str, tuple[object, ...]]] = {
            "library": ("UPDATE libraries SET name = 'other'", ()),
            "active_pointer": (
                "UPDATE sources SET active_publication_id = ? WHERE source_id = ?",
                (str(second_row["active_publication_id"]), source_id),
            ),
            "publication_source": (
                "UPDATE publications SET source_id = ? WHERE publication_id = ?",
                (other_source_id, publication_id),
            ),
            "run_source": (
                "UPDATE runs SET source_id = ? WHERE run_id = ?",
                (other_source_id, first.run_id),
            ),
            "run_state": (
                "UPDATE runs SET state = 'running' WHERE run_id = ?",
                (first.run_id,),
            ),
            "revision": (
                "UPDATE sources SET active_revision = active_revision + 1 WHERE source_id = ?",
                (source_id,),
            ),
            "manifest_count": (
                "UPDATE run_manifests SET evidence_count = 99 WHERE run_id = ?",
                (first.run_id,),
            ),
            "fingerprint": (
                "UPDATE run_manifests SET asset_sha256 = ? WHERE run_id = ?",
                ("f" * 64, first.run_id),
            ),
            "evidence_source": (
                "UPDATE evidence SET source_id = ? WHERE run_id = ?",
                (other_source_id, first.run_id),
            ),
            "evidence_run": (
                "UPDATE evidence SET run_id = ? WHERE run_id = ?",
                (second.run_id, first.run_id),
            ),
        }
        sql, params = statements[corruption]
        connection.execute(sql, params)
        connection.commit()
        with pytest.raises(ManifestValidationError):
            engine._store.observe_active_publications()  # pyright: ignore[reportPrivateUsage]
    finally:
        engine.close()


def test_observation_accepts_mixed_active_and_inactive_sources(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        published = engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
        inactive = engine.ingest_pdf(PDF_FIXTURES / "text-layer-revised.pdf")
        connection = engine._store._connection  # pyright: ignore[reportPrivateUsage]
        connection.execute(
            """
            UPDATE sources
            SET active_publication_id = NULL, active_revision = 0
            WHERE source_id = (SELECT source_id FROM runs WHERE run_id = ?)
            """,
            (inactive.run_id,),
        )
        connection.commit()
        observation = engine._store.observe_active_publications()  # pyright: ignore[reportPrivateUsage]
        assert published.run_state.value == "published"
        assert observation.state == "active"
        assert observation.source_count == 2
        assert observation.active_publication_count == 1
    finally:
        engine.close()


def test_snapshot_holds_one_view_across_second_connection_write(tmp_path: Path) -> None:
    db_path = tmp_path / "mke.sqlite"
    engine = KnowledgeEngine(db_path)
    writer: sqlite3.Connection | None = None
    try:
        result = engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
        writer = sqlite3.connect(db_path)
        writer.execute("PRAGMA busy_timeout = 5000")

        def mutate_after_retrieval(_: int) -> None:
            assert writer is not None
            writer.execute(
                "UPDATE run_manifests SET asset_sha256 = ? WHERE run_id = ?",
                ("f" * 64, result.run_id),
            )
            writer.commit()

        engine._store._search_observer = mutate_after_retrieval  # pyright: ignore[reportPrivateUsage]
        snapshot = engine._store.search_provenance_snapshot("publication active", 5)  # pyright: ignore[reportPrivateUsage]
        assert snapshot.results
        assert snapshot.results[0].content_fingerprint != "sha256:" + "f" * 64
        with pytest.raises(ManifestValidationError):
            engine._store.observe_active_publications()  # pyright: ignore[reportPrivateUsage]
    finally:
        if writer is not None:
            writer.close()
        engine.close()


@pytest.mark.parametrize("limit", [1, 20])
def test_snapshot_uses_fixed_query_shape_without_n_plus_one(
    tmp_path: Path, limit: int
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
        statements: list[str] = []
        connection = engine._store._connection  # pyright: ignore[reportPrivateUsage]
        connection.set_trace_callback(statements.append)
        try:
            snapshot = engine._store.search_provenance_snapshot("publication active", limit)  # pyright: ignore[reportPrivateUsage]
        finally:
            connection.set_trace_callback(None)
        selects = [statement for statement in statements if statement.lstrip().startswith("SELECT")]
        assert snapshot.results
        assert len(selects) == 5
        enrichment_queries = [
            statement
            for statement in selects
            if "FROM evidence" in statement
            and "WHERE evidence.evidence_id IN" in statement
        ]
        assert len(enrichment_queries) == 1
        assert sum("active_evidence_fts MATCH" in statement for statement in selects) == 1
    finally:
        engine.close()
