from pathlib import Path

import fitz  # pyright: ignore[reportMissingTypeStubs]
import pytest

from mke.application import KnowledgeEngine
from mke.domain import ActiveEvidenceRef
from mke.retrieval import compile_fts5_query
from tests.conftest import PDF_FIXTURES


def _write_numeric_pdf(path: Path) -> None:
    pages = (
        "Grouped comma control: 410,000 units.",
        "Grouped space control: 410 000 units.",
        "Grouped hyphen control: 410-000 units.",
        "Grouped slash control: 410/000 units.",
        "Compact control: 410000 units.",
        "Non-adjacent control: 410 accepted units and 000 rejected units.",
        "Identifiers: postal district 02139 and model ZX410000.",
    )
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        written: float = page.insert_textbox(  # pyright: ignore[reportUnknownMemberType]
            fitz.Rect(72, 72, 540, 720),
            text,
            fontsize=12,
            fontname="helv",
        )
        assert written >= 0
    document.save(str(path))  # pyright: ignore[reportUnknownMemberType]
    document.close()


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


@pytest.mark.parametrize(
    ("query", "page"),
    [
        ("410000 grouped comma control", 1),
        ("410000 grouped space control", 2),
        ("410000 grouped hyphen control", 3),
        ("410000 grouped slash control", 4),
        ("410000 compact control", 5),
        ("02139 postal district", 7),
        ("ZX410000 model", 7),
    ],
)
def test_numeric_grouping_matches_adjacent_variants_and_preserves_controls(
    tmp_path: Path,
    query: str,
    page: int,
) -> None:
    fixture = tmp_path / "numeric.pdf"
    _write_numeric_pdf(fixture)
    engine = KnowledgeEngine(
        tmp_path / "mke.sqlite",
        query_policy="numeric-grouping-v1",
    )
    try:
        engine.ingest_pdf(fixture)

        results = engine.search(query)

        assert [item.locator_start for item in results] == [page]
    finally:
        engine.close()


def test_numeric_grouping_rejects_non_adjacent_tokens(tmp_path: Path) -> None:
    fixture = tmp_path / "numeric.pdf"
    _write_numeric_pdf(fixture)
    engine = KnowledgeEngine(
        tmp_path / "mke.sqlite",
        query_policy="numeric-grouping-v1",
    )
    try:
        engine.ingest_pdf(fixture)

        assert engine.search("410000 non adjacent control") == []
    finally:
        engine.close()


def test_numeric_grouping_executes_one_match_statement_per_search(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "numeric.pdf"
    _write_numeric_pdf(fixture)
    engine = KnowledgeEngine(
        tmp_path / "mke.sqlite",
        query_policy="numeric-grouping-v1",
    )
    statements: list[str] = []
    try:
        engine.ingest_pdf(fixture)
        engine._store._connection.set_trace_callback(  # pyright: ignore[reportPrivateUsage]
            statements.append
        )

        engine.search("410000 grouped comma control")

        assert sum("active_evidence_fts MATCH" in statement for statement in statements) == 1
    finally:
        engine.close()
