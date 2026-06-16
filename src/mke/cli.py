"""Command-line entrypoint for the local-first Evidence engine."""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path

from mke.application import KnowledgeEngine, PdfIngestError, VideoIngestError
from mke.domain import FailurePoint

_DEFAULT_PDF_FIXTURE = Path("tests/fixtures/pdf/text-layer.pdf")
_DEFAULT_REVISED_PDF_FIXTURE = Path("tests/fixtures/pdf/text-layer-revised.pdf")
_DEFAULT_VIDEO_FIXTURE = Path("tests/fixtures/video/short-audio.mp4")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the narrow PR 2 CLI path."""
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

    run = subcommands.add_parser("run")
    run_subcommands = run.add_subparsers(dest="run_command", required=True)
    run_get = run_subcommands.add_parser("get")
    run_get.add_argument("run_id")

    demo = subcommands.add_parser("demo")
    demo.add_argument("--verify", action="store_true", required=True)
    demo.add_argument("--fixture", type=Path, default=_DEFAULT_PDF_FIXTURE)
    demo.add_argument("--revised-fixture", type=Path, default=_DEFAULT_REVISED_PDF_FIXTURE)
    demo.add_argument("--video-fixture", type=Path, default=_DEFAULT_VIDEO_FIXTURE)

    args = parser.parse_args(argv)
    if args.command == "demo":
        return _demo_verify(args.fixture, args.revised_fixture, args.video_fixture)

    engine = KnowledgeEngine(args.db)
    try:
        if args.command == "ingest":
            return _ingest(engine, args.file)
        if args.command == "search":
            return _search(engine, " ".join(args.query))
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
    print(
        f"run_id={result.run_id} run_state={result.run_state.value} "
        f"evidence_count={result.evidence_count}"
    )
    return 0


def _search(engine: KnowledgeEngine, query: str) -> int:
    for match in engine.search(query):
        if match.locator_kind == "page":
            locator = f"page={match.page_number}"
        else:
            locator = f"{match.locator_kind}={match.locator_start}..{match.locator_end}"
        print(f"{locator} evidence_id={match.evidence_id} text={match.text}")
    return 0


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


def _print_error_contract(cause: str, problem: str = "pdf_ingest_failed") -> None:
    print(
        f"problem={problem} "
        f"cause={cause} "
        "active_publication_impact=unchanged "
        "next_step=fix_input_or_retry"
    )
