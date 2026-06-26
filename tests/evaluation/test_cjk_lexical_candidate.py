from dataclasses import replace
import sqlite3
from pathlib import Path

import pytest

from mke.evaluation.cjk_lexical_candidate import (
    CJK_LEXICAL_CANDIDATE,
    CjkLexicalCandidateError,
    CjkLexicalProjectionError,
    CjkLexicalCandidateUnsupported,
    build_cjk_trigram_projection,
    candidate_identity_digest,
    cjk_evidence_identity,
    probe_sqlite_trigram_support,
    render_cjk_lexical_error,
    require_cjk_lexical_candidate,
)
from mke.evaluation.diagnostic_ports import EvaluationEvidenceSnapshot


def _evidence() -> tuple[EvaluationEvidenceSnapshot, ...]:
    return (
        EvaluationEvidenceSnapshot(
            evidence_id="ev_001",
            publication_id="pub_001",
            source_id="src_001",
            locator_kind="page",
            locator_start=1,
            locator_end=1,
            text="第一章 证据 生命周期 包含 发布 之后 的 检索 内容。",
        ),
        EvaluationEvidenceSnapshot(
            evidence_id="ev_002",
            publication_id="pub_001",
            source_id="src_001",
            locator_kind="page",
            locator_start=2,
            locator_end=2,
            text="第二章 主动 Publication 只暴露 成功 Run 的 Evidence。",
        ),
    )


def test_candidate_contract_freezes_identity_and_parameters() -> None:
    assert CJK_LEXICAL_CANDIDATE.candidate_id == "cjk-trigram-overlap-v1"
    assert type(CJK_LEXICAL_CANDIDATE.revision) is int
    assert CJK_LEXICAL_CANDIDATE.revision == 1
    assert CJK_LEXICAL_CANDIDATE.minimum_overlap_count == 2
    assert CJK_LEXICAL_CANDIDATE.minimum_overlap_ratio == 0.30
    assert CJK_LEXICAL_CANDIDATE.max_results == 10


def test_non_allowlisted_candidate_id_is_rejected() -> None:
    with pytest.raises(CjkLexicalCandidateError, match="candidate is unsupported"):
        require_cjk_lexical_candidate("raw-trigram")


def test_candidate_identity_digest_changes_when_parameters_change() -> None:
    baseline = candidate_identity_digest(CJK_LEXICAL_CANDIDATE)
    changed = candidate_identity_digest(
        replace(CJK_LEXICAL_CANDIDATE, minimum_overlap_count=3)
    )

    assert baseline != changed
    assert candidate_identity_digest(CJK_LEXICAL_CANDIDATE) == baseline


def test_sqlite_trigram_probe_returns_runtime_identity() -> None:
    support = probe_sqlite_trigram_support()

    assert support.tokenizer == "trigram"
    assert support.sqlite_version == sqlite3.sqlite_version


def test_sqlite_trigram_probe_fails_closed_when_unsupported() -> None:
    class UnsupportedConnection:
        def __enter__(self) -> "UnsupportedConnection":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def execute(self, statement: str) -> None:
            raise sqlite3.OperationalError(
                f"no such tokenizer at {Path.cwd()}"
            )

    def connect(_: str) -> UnsupportedConnection:
        return UnsupportedConnection()

    with pytest.raises(CjkLexicalCandidateUnsupported) as raised:
        probe_sqlite_trigram_support(connect=connect)

    assert raised.value.problem == "cjk_lexical_unsupported_runtime"
    assert raised.value.cause == "SQLite FTS5 trigram tokenizer is unavailable"
    assert raised.value.next_step == "use_python_sqlite_with_fts5_trigram"


def test_cjk_lexical_public_error_hides_tracebacks_and_local_paths() -> None:
    error = CjkLexicalCandidateUnsupported(
        sqlite3.OperationalError(f"boom at {Path.cwd()}")
    )

    payload = render_cjk_lexical_error(error)

    assert payload == {
        "problem": "cjk_lexical_unsupported_runtime",
        "cause": "SQLite FTS5 trigram tokenizer is unavailable",
        "next_step": "use_python_sqlite_with_fts5_trigram",
    }
    assert str(Path.cwd()) not in repr(payload)


def test_builds_evaluation_only_trigram_projection_with_snapshot_identity() -> None:
    evidence = _evidence()
    identity = cjk_evidence_identity(evidence)
    connection = sqlite3.connect(":memory:")
    try:
        projection = build_cjk_trigram_projection(
            connection,
            evidence,
            expected_identity=identity,
        )

        assert projection.table_name == "temp.mke_cjk_trigram_projection"
        assert projection.tokenizer == "trigram"
        assert projection.row_count == len(evidence)
        assert projection.text_digest == identity.text_digest
        assert projection.locator_inventory_digest == identity.locator_inventory_digest
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda items: (
                replace(items[0], text="changed text"),
                items[1],
            ),
            "text digest mismatch",
        ),
        (lambda items: (items[0],), "row count mismatch"),
        (
            lambda items: (
                replace(items[0], locator_start=99, locator_end=99),
                items[1],
            ),
            "locator inventory mismatch",
        ),
    ],
)
def test_projection_rejects_snapshot_identity_mismatch(
    mutation: object,
    message: str,
) -> None:
    evidence = _evidence()
    identity = cjk_evidence_identity(evidence)
    mutated = mutation(evidence)  # type: ignore[operator]
    connection = sqlite3.connect(":memory:")
    try:
        with pytest.raises(CjkLexicalProjectionError, match=message):
            build_cjk_trigram_projection(
                connection,
                mutated,
                expected_identity=identity,
            )
    finally:
        connection.close()


def test_projection_does_not_write_to_active_evidence_fts() -> None:
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute(
            """
            CREATE VIRTUAL TABLE active_evidence_fts USING fts5(
              evidence_id UNINDEXED,
              text
            )
            """
        )
        connection.execute(
            "INSERT INTO active_evidence_fts(evidence_id, text) VALUES (?, ?)",
            ("active_ev", "production projection row"),
        )

        build_cjk_trigram_projection(connection, _evidence())

        rows = connection.execute(
            "SELECT evidence_id, text FROM active_evidence_fts"
        ).fetchall()
        assert rows == [("active_ev", "production projection row")]
    finally:
        connection.close()
