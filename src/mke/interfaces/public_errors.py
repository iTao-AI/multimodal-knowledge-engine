"""Typed and redacted public error contract shared by CLI and MCP."""

from __future__ import annotations

from dataclasses import dataclass

_REDACTED_CAUSE = "operation failed; details were redacted"
_ALLOWLISTED_CAUSES = frozenset(
    {
        "PDF cannot be opened",
        "PDF has no extractable text",
        "PDF input exceeds 100 MB limit",
        "argv must contain exactly one {input} placeholder",
        "demo fixture is missing",
        "demo video fixture is missing",
        "encrypted PDF is not supported",
        "file path cannot be resolved",
        "input file does not exist",
        "input path must be a file",
        "input path must be under allowed root",
        "input path must not be empty",
        "input video is empty",
        "input video is missing",
        "input video must be an MP4 file",
        "input video could not be read",
        "limit must be between 1 and 20",
        "query must not be empty",
        "question must be 1000 characters or fewer",
        "question must contain at least one searchable ASCII token",
        "question must not be empty",
        "stable timestamp locator generation requires increasing ranges",
        "stable timestamp locator generation requires sorted ranges",
        "supported suffixes are .pdf and .mp4",
        "timestamp locators must be integer milliseconds",
        "transcript command executable is missing",
        "transcript command failed",
        "transcript command is required",
        "transcript command produced too much stderr",
        "transcript command produced too much stdout",
        "transcript command stdout is not valid UTF-8",
        "transcript command timed out",
        "transcription failed",
        "unsupported codec for local video proof",
        "unknown run",
        "video media exceeds duration limit",
        "video must contain an audio track",
        "video transcript exceeds segment limit",
        "video transcript format is unsupported",
        "video transcript is not valid JSON",
        "video transcript missing media",
        "video transcript must be a JSON object",
        "video transcript must contain at least one segment",
        "video transcript segment exceeds media duration",
        "video transcript segment must be an object",
        "video transcript sidecar format is unsupported",
        "video transcript sidecar is missing",
        "video transcript sidecar is not valid JSON",
        "video transcript sidecar missing media",
        "video transcript sidecar must be a JSON object",
        "video transcript text must not be empty",
        "video input exceeds 100 MiB limit",
        "video ingest initialization failed",
    }
)


@dataclass(frozen=True)
class PublicError:
    problem: str
    cause: str
    next_step: str
    run_id: str | None = None
    active_publication_impact: str = "unchanged"

    def payload(self) -> dict[str, object]:
        result: dict[str, object] = {
            "ok": False,
            "problem": self.problem,
            "cause": self.cause,
            "active_publication_impact": self.active_publication_impact,
            "next_step": self.next_step,
        }
        if self.run_id is not None:
            result["run_id"] = self.run_id
        return result


def public_error_from_cause(
    cause: str,
    *,
    problem: str,
    next_step: str,
    run_id: str | None = None,
) -> PublicError:
    if cause.startswith("unknown run:"):
        public_cause = "unknown run"
    elif cause in _ALLOWLISTED_CAUSES:
        public_cause = cause
    else:
        public_cause = _REDACTED_CAUSE
    return PublicError(
        problem=problem,
        cause=public_cause,
        next_step=next_step,
        run_id=run_id,
    )


def public_error_from_exception(
    error: BaseException,
    *,
    problem: str,
    next_step: str,
    run_id: str | None = None,
) -> PublicError:
    return public_error_from_cause(
        str(error),
        problem=problem,
        next_step=next_step,
        run_id=run_id,
    )


def render_public_error_line(error: PublicError) -> str:
    return " ".join(
        f"{key}={value}" for key, value in error.payload().items() if key != "ok"
    )
