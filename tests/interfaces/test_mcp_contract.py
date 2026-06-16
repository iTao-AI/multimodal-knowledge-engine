from pathlib import Path

import pytest

from mke.interfaces.mcp_contract import (
    McpRuntimeConfig,
    ask_library,
    get_run,
    ingest_file,
    list_libraries,
    search_library,
)
from tests.conftest import PDF_FIXTURES, VIDEO_FIXTURES


def _config(tmp_path: Path, allowed_root: Path) -> McpRuntimeConfig:
    return McpRuntimeConfig(db_path=tmp_path / "mke.sqlite", allowed_root=allowed_root)


def test_list_libraries_returns_implicit_local_library() -> None:
    result = list_libraries()

    assert result == {
        "libraries": [
            {
                "library_id": "local",
                "name": "Local Library",
                "status": "implicit",
                "active_publication_scope": "source",
            }
        ]
    }


def test_ingest_file_publishes_pdf_and_search_returns_page_evidence(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)

    ingest = ingest_file(config, "text-layer.pdf")

    assert ingest["ok"] is True
    assert ingest["run_state"] == "published"
    assert ingest["evidence_count"] == 2
    assert ingest["media_type"] == "application/pdf"
    assert ingest["active_publication_impact"] == "changed"

    search = search_library(config, "publication active")
    assert search["ok"] is True
    assert search["query"] == "publication active"
    result = search["results"][0]
    assert result["locator"] == {"kind": "page", "start": 2, "end": 2}
    assert "Publication search returns only active page two." in result["text"]


def test_mcp_ingest_file_returns_pdf_intake_summary(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)

    result = ingest_file(config, "text-layer.pdf")

    assert result["ok"] is True
    assert result["intake_report"]["total_pages"] == 2
    assert result["intake_report"]["extracted_pages"] == 2


def test_ingest_file_publishes_video_and_search_returns_timestamp_evidence(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, VIDEO_FIXTURES)

    ingest = ingest_file(config, "short-audio.mp4")

    assert ingest["ok"] is True
    assert ingest["run_state"] == "published"
    assert ingest["evidence_count"] == 2
    assert ingest["media_type"] == "video/mp4"

    search = search_library(config, "timestamp proof", limit=2)
    assert search["ok"] is True
    result = search["results"][0]
    assert result["locator"] == {"kind": "timestamp_ms", "start": 1200, "end": 2200}
    assert "Active publication search finds spoken timestamp proof." in result["text"]


def test_ingest_file_rejects_paths_outside_allowed_root(tmp_path: Path) -> None:
    outside = tmp_path / "outside.pdf"
    outside.write_bytes((PDF_FIXTURES / "text-layer.pdf").read_bytes())
    config = _config(tmp_path, PDF_FIXTURES)

    result = ingest_file(config, str(outside))

    assert result == {
        "ok": False,
        "problem": "input_path_rejected",
        "cause": "input path must be under allowed root",
        "active_publication_impact": "unchanged",
        "next_step": "choose_file_under_allowed_root",
    }


def test_ingest_file_rejects_missing_file_under_allowed_root(tmp_path: Path) -> None:
    config = _config(tmp_path, tmp_path)

    result = ingest_file(config, "missing.pdf")

    assert result == {
        "ok": False,
        "problem": "input_path_rejected",
        "cause": "input file does not exist",
        "active_publication_impact": "unchanged",
        "next_step": "choose_file_under_allowed_root",
    }


def test_ingest_file_rejects_directory_under_allowed_root(tmp_path: Path) -> None:
    materials = tmp_path / "materials"
    materials.mkdir()
    config = _config(tmp_path, tmp_path)

    result = ingest_file(config, "materials")

    assert result == {
        "ok": False,
        "problem": "input_path_rejected",
        "cause": "input path must be a file",
        "active_publication_impact": "unchanged",
        "next_step": "choose_file_under_allowed_root",
    }


def test_ingest_file_rejects_empty_path(tmp_path: Path) -> None:
    config = _config(tmp_path, tmp_path)

    result = ingest_file(config, "  ")

    assert result == {
        "ok": False,
        "problem": "input_path_rejected",
        "cause": "input path must not be empty",
        "active_publication_impact": "unchanged",
        "next_step": "choose_file_under_allowed_root",
    }


def test_ingest_file_rejects_unsupported_media_type(tmp_path: Path) -> None:
    note = tmp_path / "note.txt"
    note.write_text("not supported")
    config = _config(tmp_path, tmp_path)

    result = ingest_file(config, "note.txt")

    assert result == {
        "ok": False,
        "problem": "unsupported_media_type",
        "cause": "supported suffixes are .pdf and .mp4",
        "active_publication_impact": "unchanged",
        "next_step": "choose_supported_file",
    }


def test_get_run_returns_state_and_events(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)
    ingest = ingest_file(config, "text-layer.pdf")

    result = get_run(config, str(ingest["run_id"]))

    assert result["ok"] is True
    assert result["run"]["run_id"] == ingest["run_id"]
    assert result["run"]["state"] == "published"
    assert result["run"]["retry_of_run_id"] is None
    assert [event["event"] for event in result["events"]] == [
        "run_created",
        "run_started",
        "candidate_validated",
        "publication_activated",
    ]


def test_mcp_get_run_returns_pdf_intake_summary(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)
    ingest = ingest_file(config, "text-layer.pdf")

    result = get_run(config, str(ingest["run_id"]))

    assert result["ok"] is True
    assert result["intake_report"]["total_pages"] == 2


def test_get_run_unknown_id_returns_stable_error(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)

    result = get_run(config, "run_missing")

    assert result == {
        "ok": False,
        "problem": "run_not_found",
        "cause": "unknown run: run_missing",
        "active_publication_impact": "unchanged",
        "next_step": "check_run_id",
    }


def test_search_library_rejects_empty_query(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)

    result = search_library(config, "   ")

    assert result == {
        "ok": False,
        "problem": "invalid_query",
        "cause": "query must not be empty",
        "active_publication_impact": "unchanged",
        "next_step": "provide_non_empty_query",
    }


def test_search_library_rejects_invalid_limit(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)

    result = search_library(config, "publication", limit=0)

    assert result == {
        "ok": False,
        "problem": "invalid_query",
        "cause": "limit must be between 1 and 20",
        "active_publication_impact": "unchanged",
        "next_step": "choose_limit_between_1_and_20",
    }


def test_search_library_rejects_boolean_limit(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)

    result = search_library(config, "publication", limit=True)

    assert result == {
        "ok": False,
        "problem": "invalid_query",
        "cause": "limit must be between 1 and 20",
        "active_publication_impact": "unchanged",
        "next_step": "choose_limit_between_1_and_20",
    }


def test_search_library_returns_empty_results_for_no_match(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)
    ingest_file(config, "text-layer.pdf")

    result = search_library(config, "definitely absent")

    assert result == {"ok": True, "query": "definitely absent", "results": []}


def test_search_library_accepts_limit_boundaries(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)
    ingest_file(config, "text-layer.pdf")

    lower = search_library(config, "publication", limit=1)
    upper = search_library(config, "publication", limit=20)

    assert lower["ok"] is True
    assert len(lower["results"]) == 1
    assert upper["ok"] is True
    assert 0 < len(upper["results"]) <= 20


def test_search_library_rejects_limit_above_max(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)

    result = search_library(config, "publication", limit=21)

    assert result == {
        "ok": False,
        "problem": "invalid_query",
        "cause": "limit must be between 1 and 20",
        "active_publication_impact": "unchanged",
        "next_step": "choose_limit_between_1_and_20",
    }


def test_ask_library_returns_pdf_evidence_packet(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)
    ingest_file(config, "text-layer.pdf")

    result = ask_library(config, "publication active")

    assert result["ok"] is True
    assert str(result["ask_id"]).startswith("ask_")
    assert result["question"] == "publication active"
    assert result["answer_status"] == "evidence_found"
    assert result["summary"] == "1 active Evidence item matched the search terms."
    assert result["limitations"] == [
        "No model-generated answer is produced in this slice.",
        "The summary is deterministic and only reports matched Evidence count.",
    ]
    evidence = result["evidence"][0]
    assert evidence["locator"] == {"kind": "page", "start": 2, "end": 2}
    assert "Publication search returns only active page two." in evidence["text"]


def test_ask_library_returns_video_evidence_packet(tmp_path: Path) -> None:
    config = _config(tmp_path, VIDEO_FIXTURES)
    ingest_file(config, "short-audio.mp4")

    result = ask_library(config, "timestamp proof")

    assert result["ok"] is True
    assert result["answer_status"] == "evidence_found"
    evidence = result["evidence"][0]
    assert evidence["locator"] == {"kind": "timestamp_ms", "start": 1200, "end": 2200}
    assert "Active publication search finds spoken timestamp proof." in evidence["text"]


def test_ask_library_returns_insufficient_evidence(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)
    ingest_file(config, "text-layer.pdf")

    result = ask_library(config, "audio diarization")

    assert result == {
        "ok": True,
        "ask_id": result["ask_id"],
        "question": "audio diarization",
        "answer_status": "insufficient_evidence",
        "summary": "No active Evidence matched the search terms.",
        "evidence": [],
        "limitations": [
            "No answer is produced because no active Evidence matched the search terms.",
            "No model-generated answer is produced in this slice.",
        ],
    }
    assert str(result["ask_id"]).startswith("ask_")


def test_ask_library_rejects_empty_question(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)

    result = ask_library(config, "   ")

    assert result == {
        "ok": False,
        "problem": "invalid_question",
        "cause": "question must not be empty",
        "active_publication_impact": "unchanged",
        "next_step": "provide_non_empty_question",
    }


def test_ask_library_rejects_no_searchable_token_question(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)

    result = ask_library(config, "发布时间？")

    assert result == {
        "ok": False,
        "problem": "invalid_question",
        "cause": "question must contain at least one searchable ASCII token",
        "active_publication_impact": "unchanged",
        "next_step": "provide_searchable_question",
    }


def test_ask_library_rejects_overlong_question(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)

    result = ask_library(config, "x" * 1001)

    assert result == {
        "ok": False,
        "problem": "invalid_question",
        "cause": "question must be 1000 characters or fewer",
        "active_publication_impact": "unchanged",
        "next_step": "shorten_question",
    }


def test_ask_library_rejects_invalid_limit(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)

    result = ask_library(config, "publication", limit=21)

    assert result == {
        "ok": False,
        "problem": "invalid_query",
        "cause": "limit must be between 1 and 20",
        "active_publication_impact": "unchanged",
        "next_step": "choose_limit_between_1_and_20",
    }


def test_ask_library_rejects_boolean_limit(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)

    result = ask_library(config, "publication", limit=True)

    assert result == {
        "ok": False,
        "problem": "invalid_query",
        "cause": "limit must be between 1 and 20",
        "active_publication_impact": "unchanged",
        "next_step": "choose_limit_between_1_and_20",
    }


def test_search_and_ask_share_evidence_payload_shape(tmp_path: Path) -> None:
    config = _config(tmp_path, PDF_FIXTURES)
    ingest_file(config, "text-layer.pdf")

    search = search_library(config, "publication active")
    ask = ask_library(config, "publication active")

    assert ask["evidence"][0] == search["results"][0]


def test_ingest_file_returns_stable_error_on_invalid_pdf(tmp_path: Path) -> None:
    corrupt = tmp_path / "bad.pdf"
    corrupt.write_bytes(b"%PDF-1.4 garbage not valid content")
    config = _config(tmp_path, tmp_path)

    result = ingest_file(config, "bad.pdf")

    assert result["ok"] is False
    assert result["problem"] == "pdf_ingest_failed"
    assert result["active_publication_impact"] == "unchanged"
    assert result["next_step"] == "fix_input_or_retry"
    assert "run_id" in result


def test_ingest_file_returns_stable_error_on_broken_symlink(tmp_path: Path) -> None:
    link = tmp_path / "broken.pdf"
    link.symlink_to("/nonexistent/target.pdf")
    config = _config(tmp_path, tmp_path)

    result = ingest_file(config, "broken.pdf")

    assert result["ok"] is False
    assert result["problem"] == "input_path_rejected"
    assert result["active_publication_impact"] == "unchanged"
    assert result["next_step"] == "choose_file_under_allowed_root"


def test_mcp_rejects_oversized_pdf_before_ingest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("mke.interfaces.mcp_contract._MAX_PDF_INPUT_BYTES", 100)
    large_pdf = tmp_path / "large.pdf"
    large_pdf.write_bytes(b"x" * 101)
    config = _config(tmp_path, tmp_path)

    result = ingest_file(config, "large.pdf")

    assert result == {
        "ok": False,
        "problem": "input_file_too_large",
        "cause": "PDF input exceeds 100 MB limit",
        "active_publication_impact": "unchanged",
        "next_step": "choose_smaller_file",
    }


def test_mcp_rejects_oversized_pdf_with_mocked_size_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("mke.interfaces.mcp_contract._MAX_PDF_INPUT_BYTES", 100)
    config = _config(tmp_path, tmp_path)

    accepted = tmp_path / "accepted.pdf"
    accepted.write_bytes(b"x" * 100)
    rejected = tmp_path / "rejected.pdf"
    rejected.write_bytes(b"x" * 101)

    accepted_result = ingest_file(config, "accepted.pdf")
    rejected_result = ingest_file(config, "rejected.pdf")

    assert accepted_result.get("problem") != "input_file_too_large"
    assert rejected_result == {
        "ok": False,
        "problem": "input_file_too_large",
        "cause": "PDF input exceeds 100 MB limit",
        "active_publication_impact": "unchanged",
        "next_step": "choose_smaller_file",
    }
