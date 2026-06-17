"""Command-line entrypoint for the local-first Evidence engine."""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from collections.abc import Iterable, Sequence
from pathlib import Path

from mke.adapters.video import LocalCommandTranscriptConfig, LocalCommandTranscriptProvider
from mke.application import AskValidationError, KnowledgeEngine, PdfIngestError, VideoIngestError
from mke.domain import FailurePoint, PdfIntakeReport, SearchResult
from mke.interfaces.mcp_server import run_mcp_server
from mke.proof import render_human_report, render_json_report, run_product_proof

_DEFAULT_PDF_FIXTURE = Path("tests/fixtures/pdf/text-layer.pdf")
_DEFAULT_REVISED_PDF_FIXTURE = Path("tests/fixtures/pdf/text-layer-revised.pdf")
_DEFAULT_VIDEO_FIXTURE = Path("tests/fixtures/video/short-audio.mp4")
_REDACTED_ERROR_CAUSE = "operation failed; details were redacted"
_UNKNOWN_RUN_ERROR_CAUSE = "unknown run"
_PUBLIC_ERROR_CAUSES = {
    cause: cause
    for cause in (
        "PDF cannot be opened",
        "PDF has no extractable text",
        "argv must contain exactly one {input} placeholder",
        "demo fixture is missing",
        "demo video fixture is missing",
        "encrypted PDF is not supported",
        "input video is missing",
        "question must contain at least one searchable ASCII token",
        "transcript command executable is missing",
        "transcript command failed",
        "transcript command is required",
        "transcript command produced too much stderr",
        "transcript command produced too much stdout",
        "transcript command stdout is not valid UTF-8",
        "transcript command timed out",
        "transcription failed",
        "unsupported codec for local video proof",
        "video must contain an audio track",
        "video transcript must contain at least one segment",
        "video transcript segment must be an object",
        "video transcript sidecar format is unsupported",
        "video transcript sidecar is missing",
        "video transcript sidecar is not valid JSON",
        "video transcript sidecar missing media",
        "video transcript sidecar must be a JSON object",
        "video transcript text must not be empty",
    )
}


def main(argv: Sequence[str] | None = None) -> int:
    """Run the narrow local Evidence ingest, Search, and Ask CLI path."""
    if argv is None:
        print("multimodal-knowledge-engine: bootstrap stage")
        return 0

    parser = argparse.ArgumentParser(prog="mke")
    parser.add_argument("--db", type=Path, default=Path("mke.sqlite"))
    subcommands = parser.add_subparsers(dest="command", required=True)

    ingest = subcommands.add_parser("ingest")
    ingest.add_argument("file", type=Path)

    search = subcommands.add_parser("search")
    search.add_argument("query", nargs="+")

    ask = subcommands.add_parser("ask")
    ask.add_argument("question", nargs="+")

    run = subcommands.add_parser("run")
    run_subcommands = run.add_subparsers(dest="run_command", required=True)
    run_get = run_subcommands.add_parser("get")
    run_get.add_argument("run_id")

    demo = subcommands.add_parser("demo")
    demo.add_argument("--verify", action="store_true", required=True)
    demo.add_argument("--fixture", type=Path, default=_DEFAULT_PDF_FIXTURE)
    demo.add_argument("--revised-fixture", type=Path, default=_DEFAULT_REVISED_PDF_FIXTURE)
    demo.add_argument("--video-fixture", type=Path, default=_DEFAULT_VIDEO_FIXTURE)

    proof = subcommands.add_parser("proof")
    proof_subcommands = proof.add_subparsers(dest="proof_command", required=True)
    proof_run = proof_subcommands.add_parser("run")
    proof_run.add_argument("--json", action="store_true", dest="json_output")
    proof_smoke = proof_subcommands.add_parser("transcript-smoke")
    proof_smoke.add_argument("--fixture", type=Path, required=True)
    proof_smoke.add_argument("transcript_command", nargs=argparse.REMAINDER)

    mcp = subcommands.add_parser("mcp")
    mcp.add_argument("--allowed-root", type=Path, default=Path.cwd())

    args = parser.parse_args(argv)
    if args.command == "demo":
        return _demo_verify(args.fixture, args.revised_fixture, args.video_fixture)
    if args.command == "proof":
        if args.proof_command == "run":
            return _proof_run(json_output=args.json_output)
        return _proof_transcript_smoke(args.fixture, args.transcript_command)
    if args.command == "mcp":
        return run_mcp_server(db_path=args.db, allowed_root=args.allowed_root)

    engine = KnowledgeEngine(args.db)
    try:
        if args.command == "ingest":
            return _ingest(engine, args.file)
        if args.command == "search":
            return _search(engine, " ".join(args.query))
        if args.command == "ask":
            return _ask(engine, " ".join(args.question))
        return _run_get(engine, args.run_id)
    finally:
        engine.close()


def console_main() -> int:
    """Console script entrypoint."""
    argv = sys.argv[1:]
    return main(argv if argv else None)


def _ingest(engine: KnowledgeEngine, path: Path) -> int:
    try:
        if path.suffix.lower() == ".mp4":
            result = engine.ingest_video(path)
        else:
            result = engine.ingest_pdf(path)
    except PdfIngestError as error:
        _print_error_contract(str(error))
        return 1
    except VideoIngestError as error:
        _print_error_contract(str(error), problem="video_ingest_failed")
        return 1
    report = (
        f" {_format_pdf_intake_report(result.intake_report)}"
        if result.intake_report is not None
        else ""
    )
    print(
        f"run_id={result.run_id} run_state={result.run_state.value} "
        f"evidence_count={result.evidence_count}{report}"
    )
    return 0


def _search(engine: KnowledgeEngine, query: str) -> int:
    _print_evidence_matches(engine.search(query))
    return 0


def _ask(engine: KnowledgeEngine, question: str) -> int:
    try:
        result = engine.ask(question)
    except AskValidationError as error:
        _print_error_contract(error.cause, problem=error.problem, next_step=error.next_step)
        return 1
    print(
        f"answer_status={result.answer_status} evidence_count={len(result.evidence)} "
        f"summary=\"{result.summary}\""
    )
    _print_evidence_matches(result.evidence)
    return 0


def _print_evidence_matches(matches: Iterable[SearchResult]) -> None:
    for match in matches:
        if match.locator_kind == "page":
            locator = f"page={match.page_number}"
        else:
            locator = f"{match.locator_kind}={match.locator_start}..{match.locator_end}"
        print(f"{locator} evidence_id={match.evidence_id} text={match.text}")


def _run_get(engine: KnowledgeEngine, run_id: str) -> int:
    try:
        run = engine.get_run(run_id)
    except KeyError:
        _print_error_contract(f"unknown run: {run_id}")
        return 1
    retry = f" retry_of_run_id={run.retry_of_run_id}" if run.retry_of_run_id else ""
    print(
        f"run_id={run.run_id} state={run.state.value} "
        f"source_generation={run.source_generation}{retry}"
    )
    report = engine.get_pdf_intake_report(run_id)
    if report is not None:
        print(_format_pdf_intake_report(report))
    for event in engine.get_run_events(run_id):
        print(f"event_index={event.event_index} event={event.event_type}")
    return 0


def _demo_verify(fixture: Path, revised_fixture: Path, video_fixture: Path) -> int:
    started = time.monotonic()
    print("mke demo --verify")
    if not fixture.exists() or not revised_fixture.exists():
        _print_error_contract("demo fixture is missing")
        return 1
    if not video_fixture.exists():
        _print_error_contract("demo video fixture is missing", problem="video_ingest_failed")
        return 1

    with tempfile.TemporaryDirectory(prefix="mke-demo-") as temp_dir:
        db_path = Path(temp_dir) / "demo.sqlite"
        engine: KnowledgeEngine | None = None
        try:
            engine = KnowledgeEngine(db_path)
            initial = engine.ingest_pdf(fixture)
            initial_results = engine.search("trustworthy")
            if not initial_results:
                raise RuntimeError("initial search returned no Evidence")
            print(
                f"phase=ingest_initial status=ok run_id={initial.run_id} "
                f"evidence_count={initial.evidence_count}"
            )

            try:
                engine.reprocess_pdf(
                    revised_fixture,
                    failure_point=FailurePoint.BEFORE_VALIDATION,
                )
            except PdfIngestError:
                pass
            else:
                raise RuntimeError("failure injection did not fail")
            if [match.text for match in engine.search("trustworthy")] != [
                match.text for match in initial_results
            ]:
                raise RuntimeError("active Publication changed after failed reprocess")
            print("phase=failed_reprocess status=ok active_publication_impact=unchanged")

            try:
                engine.reprocess_pdf(
                    revised_fixture,
                    failure_point=FailurePoint.AFTER_PUBLICATION_INSERT,
                )
            except PdfIngestError as activation_failure:
                retry_run_id = activation_failure.run_id or ""
                retry = engine.activate_publication(retry_run_id)
            else:
                raise RuntimeError("activation failure injection did not fail")
            if not retry.published or not engine.search("revised"):
                raise RuntimeError("retry publication did not replace active Search")
            print(f"phase=retry_publish status=ok run_id={retry.run_id}")

            video = engine.ingest_video(video_fixture)
            video_results = engine.search("timestamp proof")
            if not video_results:
                raise RuntimeError("video search returned no timestamp Evidence")
            print(
                f"phase=ingest_video status=ok run_id={video.run_id} "
                f"video_evidence_count={video.evidence_count}"
            )
        except Exception as error:
            if isinstance(error, VideoIngestError):
                problem = "video_ingest_failed"
            else:
                problem = "pdf_ingest_failed"
            _print_error_contract(str(error), problem=problem)
            return 1
        finally:
            if engine is not None:
                engine.close()

    duration_ms = int((time.monotonic() - started) * 1000)
    print("phase=cleanup status=ok")
    print(f"result=passed duration_ms={duration_ms}")
    return 0


def _proof_run(*, json_output: bool) -> int:
    report = run_product_proof()
    if json_output:
        print(render_json_report(report))
    else:
        print(render_human_report(report))
    return 0 if report.status == "passed" else 1


def _proof_transcript_smoke(fixture: Path, command: Sequence[str]) -> int:
    print("mke proof transcript-smoke")
    normalized_command = _normalize_remainder_command(command)
    if not normalized_command:
        _print_error_contract(
            "transcript command is required",
            problem="video_ingest_failed",
        )
        return 1
    try:
        provider = LocalCommandTranscriptProvider(
            LocalCommandTranscriptConfig(argv=normalized_command)
        )
        with tempfile.TemporaryDirectory(prefix="mke-transcript-smoke-") as temp_dir:
            engine = KnowledgeEngine(
                Path(temp_dir) / "transcript-smoke.sqlite",
                transcript_provider=provider,
            )
            try:
                result = engine.ingest_video(fixture)
            finally:
                engine.close()
    except (TypeError, ValueError, VideoIngestError) as error:
        _print_error_contract(str(error), problem="video_ingest_failed")
        return 1
    print(
        "proof=transcript_smoke status=passed "
        f"provider=local_command evidence_count={result.evidence_count}"
    )
    return 0


def _normalize_remainder_command(command: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(command)
    if normalized and normalized[0] == "--":
        return normalized[1:]
    return normalized


def _print_error_contract(
    cause: str,
    problem: str = "pdf_ingest_failed",
    next_step: str = "fix_input_or_retry",
) -> None:
    public_cause = _public_error_cause(cause)
    print(
        f"problem={problem} "
        f"cause={public_cause} "
        "active_publication_impact=unchanged "
        f"next_step={next_step}"
    )


def _public_error_cause(cause: str) -> str:
    if cause.startswith("unknown run:"):
        return _UNKNOWN_RUN_ERROR_CAUSE
    return _PUBLIC_ERROR_CAUSES.get(cause, _REDACTED_ERROR_CAUSE)


def _format_pdf_intake_report(report: PdfIntakeReport) -> str:
    return (
        f"pdf_pages={report.total_pages} "
        f"extracted_pages={report.extracted_pages} "
        f"empty_pages={report.empty_pages} "
        f"extracted_chars={report.total_extracted_chars} "
        f"suspected_scanned_pages={report.suspected_scanned_pages}"
    )
