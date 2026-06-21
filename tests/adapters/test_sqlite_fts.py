from pathlib import Path

import pytest

from mke.application import KnowledgeEngine
from mke.domain import ActiveEvidenceRef
from mke.retrieval import compile_fts5_query
from tests.conftest import PDF_FIXTURES


@pytest.mark.parametrize(
    "query,expected",
    [
        ("", ""),
        ("   ", ""),
        ("hello world", '"hello" "world"'),
        ("HELLO", '"hello"'),
        ("* : ( ) NEAR", '"near"'),
        ("hello_world", '"hello_world"'),
        ("active page", '"active" "page"'),
        ("trustworthy", '"trustworthy"'),
    ],
)
def test_current_query_policy(query: str, expected: str) -> None:
    assert compile_fts5_query(query, policy="current") == expected


def test_list_active_evidence_returns_only_current_publication(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        initial = engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
        source_id = engine.get_run(initial.run_id).source_id
        engine.reprocess_pdf(PDF_FIXTURES / "text-layer-revised.pdf")

        active = engine.list_active_evidence()

        assert active
        assert {item.source_id for item in active} == {source_id}
        assert active == [
            ActiveEvidenceRef(source_id, "page", 1, 1),
            ActiveEvidenceRef(source_id, "page", 2, 2),
        ]
    finally:
        engine.close()
