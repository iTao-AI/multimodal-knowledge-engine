from pathlib import Path

import fitz  # pyright: ignore[reportMissingTypeStubs]
import pytest

from mke.application import KnowledgeEngine, PdfIngestError
from mke.domain import ActiveEvidenceRef, FailurePoint
from mke.evaluation.diagnostic_ports import (
    FtsProjectionIntegrityError,
    validate_fts_projection,
)
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


def _write_repeated_pdf(path: Path, pages: int = 12) -> None:
    document = fitz.open()
    for index in range(1, pages + 1):
        page = document.new_page()
        written: float = page.insert_textbox(  # pyright: ignore[reportUnknownMemberType]
            fitz.Rect(72, 72, 540, 720),
            f"shared rank probe page {index}",
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


def test_policy_rollback_reuses_existing_database_without_index_rebuild(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "numeric.pdf"
    db_path = tmp_path / "mke.sqlite"
    _write_numeric_pdf(fixture)
    promoted = KnowledgeEngine(db_path, query_policy="numeric-grouping-v1")
    try:
        promoted.ingest_pdf(fixture)
        schema_version = promoted._store._connection.execute(  # pyright: ignore[reportPrivateUsage]
            "PRAGMA schema_version"
        ).fetchone()[0]
        assert promoted.search("410000 grouped comma control")
    finally:
        promoted.close()

    rollback = KnowledgeEngine(db_path, query_policy="current")
    try:
        assert rollback._store._connection.execute(  # pyright: ignore[reportPrivateUsage]
            "PRAGMA schema_version"
        ).fetchone()[0] == schema_version
        assert rollback.search("410000 grouped comma control") == []
        assert rollback.search("410 000 grouped comma control")
    finally:
        rollback.close()


def test_evaluation_snapshot_reads_domain_truth_independently_of_fts(
    tmp_path: Path,
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        result = engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
        source_id = engine.get_run(result.run_id).source_id
        store = engine._store  # pyright: ignore[reportPrivateUsage]

        evidence = store.list_evaluation_evidence()
        projection = store.list_fts_projection()

        assert len(evidence) == 2
        assert {item.source_id for item in evidence} == {source_id}
        assert all(item.text for item in evidence)
        assert len(projection) == 2
        validate_fts_projection(evidence, projection)

        store._connection.execute(  # pyright: ignore[reportPrivateUsage]
            "DELETE FROM active_evidence_fts WHERE evidence_id = ?",
            (projection[0].evidence_id,),
        )
        store._connection.commit()  # pyright: ignore[reportPrivateUsage]

        assert store.list_evaluation_evidence() == evidence
        with pytest.raises(FtsProjectionIntegrityError, match="inconsistent"):
            validate_fts_projection(evidence, store.list_fts_projection())
    finally:
        engine.close()


@pytest.mark.parametrize("corruption", ("locator", "text", "extra", "duplicate"))
def test_evaluation_projection_rejects_identity_corruption(
    tmp_path: Path, corruption: str
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
        store = engine._store  # pyright: ignore[reportPrivateUsage]
        evidence = store.list_evaluation_evidence()
        projection = store.list_fts_projection()
        row = projection[0]

        if corruption in {"locator", "text"}:
            store._connection.execute(  # pyright: ignore[reportPrivateUsage]
                "DELETE FROM active_evidence_fts WHERE evidence_id = ?",
                (row.evidence_id,),
            )
            replacement = next(item for item in evidence if item.evidence_id == row.evidence_id)
            store._connection.execute(  # pyright: ignore[reportPrivateUsage]
                """
                INSERT INTO active_evidence_fts(
                  library_id, source_id, publication_id, evidence_id, locator_label, text
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "library-test",
                    row.source_id,
                    row.publication_id,
                    row.evidence_id,
                    "page:999" if corruption == "locator" else row.locator_label,
                    "changed indexed text" if corruption == "text" else replacement.text,
                ),
            )
        else:
            replacement = next(item for item in evidence if item.evidence_id == row.evidence_id)
            store._connection.execute(  # pyright: ignore[reportPrivateUsage]
                """
                INSERT INTO active_evidence_fts(
                  library_id, source_id, publication_id, evidence_id, locator_label, text
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "library-test",
                    row.source_id,
                    row.publication_id,
                    "ev_extra" if corruption == "extra" else row.evidence_id,
                    row.locator_label,
                    replacement.text,
                ),
            )
        store._connection.commit()  # pyright: ignore[reportPrivateUsage]

        with pytest.raises(FtsProjectionIntegrityError, match="inconsistent"):
            validate_fts_projection(evidence, store.list_fts_projection())
    finally:
        engine.close()


def test_failed_reprocess_leaves_evaluation_snapshot_unchanged(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
        before = engine._store.list_evaluation_evidence()  # pyright: ignore[reportPrivateUsage]

        with pytest.raises(PdfIngestError):
            engine.reprocess_pdf(
                PDF_FIXTURES / "text-layer-revised.pdf",
                failure_point=FailurePoint.DURING_ACTIVE_FTS_REPLACEMENT,
            )

        assert engine._store.list_evaluation_evidence() == before  # pyright: ignore[reportPrivateUsage]
    finally:
        engine.close()


def test_rank_observation_matches_complete_production_order_and_scores(
    tmp_path: Path,
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
        store = engine._store  # pyright: ignore[reportPrivateUsage]
        compiled = compile_fts5_query(
            "active page", policy="numeric-grouping-v1"
        )

        observation = store.observe_fts5_rank(compiled)

        assert observation
        assert [item.evidence_id for item in observation.rank_order] == [
            item.evidence_id for item in observation.bm25_order
        ]
        assert all(
            item.rank_score == pytest.approx(item.bm25_score, abs=1e-12)
            for item in observation.rank_order
        )
        assert observation.rank_override_present is False
    finally:
        engine.close()


def test_rank_observation_rejects_empty_input_without_sql(
    tmp_path: Path,
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    statements: list[str] = []
    try:
        store = engine._store  # pyright: ignore[reportPrivateUsage]
        store._connection.set_trace_callback(  # pyright: ignore[reportPrivateUsage]
            statements.append
        )
        with pytest.raises(ValueError, match="compiled query is invalid"):
            store.observe_fts5_rank("")
        assert not any("MATCH" in statement for statement in statements)
    finally:
        engine.close()


def test_rank_observation_covers_ties_beyond_top_ten_and_detects_override(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "repeated.pdf"
    _write_repeated_pdf(fixture)
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        engine.ingest_pdf(fixture)
        store = engine._store  # pyright: ignore[reportPrivateUsage]
        compiled = compile_fts5_query(
            "shared rank probe", policy="numeric-grouping-v1"
        )

        baseline = store.observe_fts5_rank(compiled)

        assert len(baseline.rank_order) == 12
        assert [item.locator_start for item in baseline.rank_order] == list(
            range(1, 13)
        )
        assert [item.evidence_id for item in baseline.rank_order] == [
            item.evidence_id for item in baseline.bm25_order
        ]
        store._connection.execute(  # pyright: ignore[reportPrivateUsage]
            """
            INSERT INTO active_evidence_fts(active_evidence_fts, rank)
            VALUES ('rank', 'bm25(10.0)')
            """
        )
        store._connection.commit()  # pyright: ignore[reportPrivateUsage]

        assert store.observe_fts5_rank(compiled).rank_override_present is True
    finally:
        engine.close()
