from pathlib import Path

from mke.application import KnowledgeEngine
from tests.conftest import PDF_FIXTURES


def test_search_and_ask_snapshots_share_projection(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
        search = engine.search_provenance_snapshot("publication active")
        ask = engine.ask_provenance_snapshot("publication active")
        assert search.results == ask.evidence
        assert ask.result.evidence == tuple(item.result for item in ask.evidence)
    finally:
        engine.close()


def test_snapshot_states_preserve_ask_refusal(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        empty = engine.ask_provenance_snapshot("nothing")
        engine.prepare_pdf_candidate(PDF_FIXTURES / "text-layer.pdf")
        no_active = engine.ask_provenance_snapshot("nothing")
        assert empty.observation.state == "empty"
        assert no_active.observation.state == "no_active_publication"
        assert (
            empty.result.answer_status == no_active.result.answer_status == "insufficient_evidence"
        )
    finally:
        engine.close()
