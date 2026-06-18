from mke.interfaces.public_errors import (
    PublicError,
    public_error_from_cause,
    public_error_from_exception,
    render_public_error_line,
)


def test_video_duration_limit_cause_is_allowlisted_exactly() -> None:
    error = public_error_from_cause(
        "video media exceeds duration limit",
        problem="video_ingest_failed",
        next_step="fix_input_or_retry",
    )

    assert error.cause == "video media exceeds duration limit"


def test_public_error_payload_and_human_line_share_exact_fields() -> None:
    error = PublicError(
        problem="video_ingest_failed",
        cause="transcription failed",
        next_step="fix_input_or_retry",
        run_id="run_123",
    )

    assert error.payload() == {
        "ok": False,
        "problem": "video_ingest_failed",
        "cause": "transcription failed",
        "active_publication_impact": "unchanged",
        "next_step": "fix_input_or_retry",
        "run_id": "run_123",
    }
    assert render_public_error_line(error) == (
        "problem=video_ingest_failed cause=transcription failed "
        "active_publication_impact=unchanged next_step=fix_input_or_retry "
        "run_id=run_123"
    )


def test_unknown_exception_is_fully_redacted() -> None:
    sensitive = RuntimeError(
        "argv=['secret'] stderr=TOKEN /Users/name/.cache/model "
        "https://private.example Traceback"
    )

    error = public_error_from_exception(
        sensitive,
        problem="internal_error",
        next_step="check_server_logs",
    )

    assert error.payload() == {
        "ok": False,
        "problem": "internal_error",
        "cause": "operation failed; details were redacted",
        "active_publication_impact": "unchanged",
        "next_step": "check_server_logs",
    }
