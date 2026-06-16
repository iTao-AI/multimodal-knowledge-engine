from pathlib import Path

import pytest

from mke.application import AskValidationError, KnowledgeEngine
from tests.conftest import PDF_FIXTURES, VIDEO_FIXTURES


def test_ask_returns_pdf_page_evidence_packet(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")

    result = engine.ask("publication active")

    assert result.ask_id.startswith("ask_")
    assert result.question == "publication active"
    assert result.answer_status == "evidence_found"
    assert result.summary == "1 active Evidence item matched the search terms."
    assert result.limitations == [
        "No model-generated answer is produced in this slice.",
        "The summary is deterministic and only reports matched Evidence count.",
    ]
    assert len(result.evidence) == 1
    match = result.evidence[0]
    assert match.locator_kind == "page"
    assert match.locator_start == 2
    assert match.locator_end == 2
    assert "Publication search returns only active page two." in match.text


def test_ask_returns_video_timestamp_evidence_packet(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    engine.ingest_video(VIDEO_FIXTURES / "short-audio.mp4")

    result = engine.ask("timestamp proof")

    assert result.answer_status == "evidence_found"
    assert result.summary == "1 active Evidence item matched the search terms."
    match = result.evidence[0]
    assert match.locator_kind == "timestamp_ms"
    assert match.locator_start == 1200
    assert match.locator_end == 2200
    assert "Active publication search finds spoken timestamp proof." in match.text


def test_ask_returns_insufficient_evidence_for_no_match(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")

    result = engine.ask("audio diarization")

    assert result.ask_id.startswith("ask_")
    assert result.question == "audio diarization"
    assert result.answer_status == "insufficient_evidence"
    assert result.summary == "No active Evidence matched the search terms."
    assert result.evidence == []
    assert result.limitations == [
        "No answer is produced because no active Evidence matched the search terms.",
        "No model-generated answer is produced in this slice.",
    ]


def test_ask_rejects_empty_question(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    with pytest.raises(AskValidationError) as error:
        engine.ask("   ")

    assert error.value.problem == "invalid_question"
    assert error.value.cause == "question must not be empty"
    assert error.value.next_step == "provide_non_empty_question"


def test_ask_rejects_overlong_question(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    with pytest.raises(AskValidationError) as error:
        engine.ask("x" * 1001)

    assert error.value.problem == "invalid_question"
    assert error.value.cause == "question must be 1000 characters or fewer"
    assert error.value.next_step == "shorten_question"


@pytest.mark.parametrize("question", ["发布时间？", "？！？", "... ---"])
def test_ask_rejects_question_without_searchable_ascii_token(
    tmp_path: Path, question: str
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    with pytest.raises(AskValidationError) as error:
        engine.ask(question)

    assert error.value.problem == "invalid_question"
    assert error.value.cause == "question must contain at least one searchable ASCII token"
    assert error.value.next_step == "provide_searchable_question"


@pytest.mark.parametrize("limit", [0, 21])
def test_ask_rejects_invalid_limit(tmp_path: Path, limit: int) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    with pytest.raises(AskValidationError) as error:
        engine.ask("publication", limit=limit)

    assert error.value.problem == "invalid_query"
    assert error.value.cause == "limit must be between 1 and 20"
    assert error.value.next_step == "choose_limit_between_1_and_20"


@pytest.mark.parametrize("limit", [False, True])
def test_ask_rejects_boolean_limit(tmp_path: Path, limit: bool) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")

    with pytest.raises(AskValidationError) as error:
        engine.ask("publication", limit=limit)

    assert error.value.problem == "invalid_query"
    assert error.value.cause == "limit must be between 1 and 20"
    assert error.value.next_step == "choose_limit_between_1_and_20"
