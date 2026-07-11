import pytest

from mke.application import KnowledgeEngine
from mke.domain import ManifestValidationError
from tests.conftest import PDF_FIXTURES, VIDEO_FIXTURES


def test_snapshot_enriches_pdf_and_video_provenance(tmp_path) -> None:
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


def test_observation_distinguishes_empty_and_no_active(tmp_path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        assert engine._store.observe_active_publications().state == "empty"  # pyright: ignore[reportPrivateUsage]
        engine.prepare_pdf_candidate(PDF_FIXTURES / "text-layer.pdf")
        assert engine._store.observe_active_publications().state == "no_active_publication"  # pyright: ignore[reportPrivateUsage]
    finally:
        engine.close()


def test_corrupt_manifest_count_fails_closed(tmp_path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        result = engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
        engine._store._connection.execute("UPDATE run_manifests SET evidence_count = 99 WHERE run_id = ?", (result.run_id,))  # pyright: ignore[reportPrivateUsage]
        engine._store._connection.commit()  # pyright: ignore[reportPrivateUsage]
        with pytest.raises(ManifestValidationError):
            engine._store.observe_active_publications()  # pyright: ignore[reportPrivateUsage]
    finally:
        engine.close()
