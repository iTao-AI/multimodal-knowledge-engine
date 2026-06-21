"""Command-line entrypoint for the local-first Evidence engine."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from collections.abc import Iterable, Sequence
from pathlib import Path

from mke.adapters.video import LocalCommandTranscriptConfig, LocalCommandTranscriptProvider
from mke.adapters.video.contracts import VideoTranscriptionLimits
from mke.adapters.video.faster_whisper import (
    ModelResolutionError,
    TranscriptionReadiness,
    doctor_transcription,
    prepare_model,
)
from mke.application import AskValidationError, KnowledgeEngine, PdfIngestError, VideoIngestError
from mke.domain import FailurePoint, PdfIntakeReport, SearchResult, TranscriptIntakeReport
from mke.evaluation import (
    render_numeric_comparison_human,
    render_numeric_comparison_json,
    render_retrieval_human_report,
    render_retrieval_json_report,
    run_numeric_comparison,
    run_retrieval_evaluation,
)
from mke.evaluation.numeric_comparison import NumericComparisonReport
from mke.evaluation.report import RetrievalEvaluationReport
from mke.interfaces.mcp_contract import McpRuntimeConfig, transcript_intake_report_payload
from mke.interfaces.mcp_server import run_mcp_server
from mke.interfaces.public_errors import public_error_from_cause, render_public_error_line
from mke.proof import (
    render_human_report,
    render_json_report,
    render_transcription_proof_human,
    render_transcription_proof_json,
    run_product_proof,
    run_transcription_proof,
)
from mke.runtime import (
    DEFAULT_MODEL_REVISION,
    FasterWhisperTranscriptionConfig,
    ModelPreparationConfig,
    RuntimeConfig,
    SidecarTranscriptionConfig,
    build_engine,
)

_DEFAULT_PDF_FIXTURE = Path("tests/fixtures/pdf/text-layer.pdf")
_DEFAULT_REVISED_PDF_FIXTURE = Path("tests/fixtures/pdf/text-layer-revised.pdf")
_DEFAULT_VIDEO_FIXTURE = Path("tests/fixtures/video/short-audio.mp4")
_DEFAULT_TRANSCRIPTION_PROOF_FIXTURE = Path("tests/fixtures/video/spoken-evidence.mp4")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the narrow local Evidence ingest, Search, and Ask CLI path."""
    if argv is None:
        print("multimodal-knowledge-engine: bootstrap stage")
        return 0

    raw_argv = tuple(argv)
    parser = argparse.ArgumentParser(prog="mke")
    parser.add_argument("--db", type=Path, default=Path("mke.sqlite"))
    subcommands = parser.add_subparsers(dest="command", required=True)

    ingest = subcommands.add_parser("ingest")
    ingest.add_argument("file", type=Path)
    ingest.add_argument("--json", action="store_true", dest="json_output")
    add_transcription_runtime_arguments(ingest, default_provider="sidecar")

    search = subcommands.add_parser("search")
    search.add_argument("query", nargs="+")

    ask = subcommands.add_parser("ask")
    ask.add_argument("question", nargs="+")

    run = subcommands.add_parser("run")
    run_subcommands = run.add_subparsers(dest="run_command", required=True)
    run_get = run_subcommands.add_parser("get")
    run_get.add_argument("run_id")
    run_get.add_argument("--json", action="store_true", dest="json_output")

    demo = subcommands.add_parser("demo")
    demo.add_argument("--verify", action="store_true", required=True)
    demo.add_argument("--fixture", type=Path, default=_DEFAULT_PDF_FIXTURE)
    demo.add_argument("--revised-fixture", type=Path, default=_DEFAULT_REVISED_PDF_FIXTURE)
    demo.add_argument("--video-fixture", type=Path, default=_DEFAULT_VIDEO_FIXTURE)

    proof = subcommands.add_parser("proof")
    proof_subcommands = proof.add_subparsers(dest="proof_command", required=True)
    proof_run = proof_subcommands.add_parser("run")
    proof_run.add_argument("--json", action="store_true", dest="json_output")
    proof_transcription = proof_subcommands.add_parser("transcription-run")
    proof_transcription.add_argument(
        "--fixture",
        type=Path,
        default=_DEFAULT_TRANSCRIPTION_PROOF_FIXTURE,
    )
    proof_transcription.add_argument("--json", action="store_true", dest="json_output")
    add_faster_whisper_runtime_arguments(proof_transcription)
    proof_smoke = proof_subcommands.add_parser("transcript-smoke")
    proof_smoke.add_argument("--fixture", type=Path, required=True)
    proof_smoke.add_argument("transcript_command", nargs=argparse.REMAINDER)

    evaluation = subcommands.add_parser("eval")
    evaluation_subcommands = evaluation.add_subparsers(
        dest="evaluation_command", required=True
    )
    retrieval = evaluation_subcommands.add_parser(
        "retrieval",
        description=(
            "Record the current baseline on a small English page/timestamp corpus; "
            "no retrieval-quality threshold is applied."
        ),
    )
    retrieval.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="external retrieval-evaluation manifest",
    )
    retrieval.add_argument("--json", action="store_true", dest="json_output")
    numeric_retrieval = evaluation_subcommands.add_parser(
        "retrieval-numeric",
        description=(
            "Run the comparison-only public-holdout numeric protocol. "
            "The runtime default remains current, the holdout is public rather than blind, "
            "and promotion is conditional."
        ),
    )
    numeric_retrieval.add_argument(
        "--protocol",
        type=Path,
        required=True,
        help="locked numeric retrieval comparison protocol",
    )
    numeric_retrieval.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
    )

    mcp = subcommands.add_parser("mcp")
    mcp.add_argument("--allowed-root", type=Path, default=Path.cwd())
    add_transcription_runtime_arguments(mcp, default_provider="sidecar")

    transcription = subcommands.add_parser("transcription")
    transcription_subcommands = transcription.add_subparsers(
        dest="transcription_command", required=True
    )
    prepare = transcription_subcommands.add_parser("prepare")
    prepare.add_argument("--allow-model-download", action="store_true", required=True)
    prepare.add_argument("--json", action="store_true", dest="json_output")
    add_transcription_runtime_arguments(prepare, default_provider="faster-whisper")
    doctor = transcription_subcommands.add_parser("doctor")
    doctor.add_argument("--json", action="store_true", dest="json_output")
    add_transcription_runtime_arguments(doctor, default_provider="faster-whisper")

    args = parser.parse_args(argv)
    if args.command == "eval" and any(
        item == "--db" or item.startswith("--db=") for item in raw_argv
    ):
        parser.error("eval uses two temporary workspaces; --db is not supported")
    if args.command == "eval":
        if args.evaluation_command == "retrieval":
            report = run_retrieval_evaluation(args.manifest)
            rendered, rendering_failed = _render_retrieval_report_safely(
                report,
                json_output=args.json_output,
            )
            print(rendered)
            return 0 if report.status == "passed" and not rendering_failed else 1
        if args.evaluation_command == "retrieval-numeric":
            report = run_numeric_comparison(args.protocol)
            rendered, rendering_failed = _render_numeric_comparison_safely(
                report,
                json_output=args.json_output,
            )
            print(rendered)
            return (
                0
                if report.integrity_status == "passed"
                and report.candidate_status == "passed"
                and not rendering_failed
                else 1
            )
        parser.error("unsupported evaluation command")
    if args.command == "demo":
        return _demo_verify(args.fixture, args.revised_fixture, args.video_fixture)
    if args.command == "proof":
        if args.proof_command == "run":
            return _proof_run(json_output=args.json_output)
        if args.proof_command == "transcription-run":
            try:
                config = _faster_whisper_config_from_args(args)
            except (TypeError, ValueError) as error:
                parser.error(str(error))
            return _proof_transcription_run(
                args.fixture,
                config,
                json_output=args.json_output,
            )
        if args.proof_command == "transcript-smoke":
            return _proof_transcript_smoke(args.fixture, args.transcript_command)
        parser.error("unsupported proof command")
    if args.command == "mcp":
        try:
            runtime = runtime_config_from_args(args)
        except (TypeError, ValueError) as error:
            parser.error(str(error))
        return run_mcp_server(
            McpRuntimeConfig(
                runtime=runtime,
                allowed_root=args.allowed_root,
            )
        )
    if args.command == "transcription":
        try:
            config = _faster_whisper_config_from_args(args)
        except (TypeError, ValueError) as error:
            parser.error(str(error))
        if args.transcription_command == "prepare":
            return _transcription_prepare(config, json_output=args.json_output)
        return _transcription_doctor(config, json_output=args.json_output)

    try:
        runtime = runtime_config_from_args(args)
    except (TypeError, ValueError) as error:
        parser.error(str(error))
    if (
        args.command == "ingest"
        and args.file.suffix.lower() == ".mp4"
        and isinstance(runtime.transcription, FasterWhisperTranscriptionConfig)
    ):
        readiness = doctor_transcription(runtime.transcription)
        if readiness.status != "ready":
            _print_error_contract(
                readiness.cause or "transcription readiness check failed",
                problem="transcription_not_ready",
                next_step=readiness.next_step or "run_transcription_doctor",
                json_output=args.json_output,
            )
            return 1
    engine = build_engine(runtime)
    try:
        if args.command == "ingest":
            return _ingest(engine, args.file, json_output=args.json_output)
        if args.command == "search":
            return _search(engine, " ".join(args.query))
        if args.command == "ask":
            return _ask(engine, " ".join(args.question))
        return _run_get(engine, args.run_id, json_output=args.json_output)
    finally:
        engine.close()


def console_main() -> int:
    """Console script entrypoint."""
    argv = sys.argv[1:]
    return main(argv if argv else None)


def _render_retrieval_report_safely(
    report: RetrievalEvaluationReport,
    *,
    json_output: bool,
) -> tuple[str, bool]:
    try:
        rendered = (
            render_retrieval_json_report(report)
            if json_output
            else render_retrieval_human_report(report)
        )
        return rendered, False
    except Exception:
        if json_output:
            return (
                json.dumps(
                    {
                        "evaluation": "retrieval",
                        "schema_version": "mke.retrieval_eval_report.v1",
                        "manifest_id": "unknown",
                        "benchmark_scope": "small_english_page_timestamp_corpus",
                        "quality_gate": "none",
                        "status": "failed",
                        "quality_status": "not_recorded",
                        "documents": 0,
                        "queries": 0,
                        "answerable": 0,
                        "unanswerable": 0,
                        "metrics": None,
                        "category_counts": {
                            "answerable": 0,
                            "lexical_confuser": 0,
                            "out_of_corpus": 0,
                        },
                        "results": [],
                        "integrity_failures": [
                            {
                                "problem": "retrieval_eval_incomplete",
                                "cause": (
                                    "retrieval evaluation report could not be rendered"
                                ),
                                "next_step": "inspect_retrieval_eval_inputs",
                                "subject_id": None,
                            }
                        ],
                        "duration_ms": 0,
                    }
                ),
                True,
            )
        return (
            "mke eval retrieval\n"
            "scope=small_english_page_timestamp_corpus quality_gate=none\n"
            "evaluation=retrieval manifest=unknown status=failed "
            "quality_status=not_recorded documents=0 queries=0 answerable=0 "
            "unanswerable=0\n"
            "problem=retrieval_eval_incomplete "
            "cause=retrieval evaluation report could not be rendered "
            "next_step=inspect_retrieval_eval_inputs",
            True,
        )


def _render_numeric_comparison_safely(
    report: NumericComparisonReport,
    *,
    json_output: bool,
) -> tuple[str, bool]:
    try:
        rendered = (
            render_numeric_comparison_json(report)
            if json_output
            else render_numeric_comparison_human(report)
        )
        return rendered, False
    except Exception:
        if json_output:
            return (
                json.dumps(
                    {
                        "schema_version": "mke.retrieval_numeric_comparison.v1",
                        "protocol_id": "unknown",
                        "candidate_id": "numeric-grouping-v1",
                        "candidate_revision": 1,
                        "integrity_status": "failed",
                        "candidate_status": "not_recorded",
                        "development": {},
                        "holdout": {},
                        "e1": {},
                        "compiled_queries": [],
                        "gates": [],
                        "integrity_failures": [
                            {
                                "problem": "retrieval_numeric_comparison_incomplete",
                                "cause": (
                                    "numeric comparison report could not be rendered"
                                ),
                                "next_step": "inspect_numeric_comparison_inputs",
                                "subject_id": None,
                            }
                        ],
                        "duration_ms": 0,
                        "limitations": [
                            "public_holdout_not_blind",
                            "small_engineering_challenge_set",
                            "ascii_compact_integers_only",
                            "tokenizer_adjacent_separator_equivalence",
                            "no_general_retrieval_quality_claim",
                        ],
                    }
                ),
                True,
            )
        return (
            "mke eval retrieval-numeric\n"
            "protocol=unknown candidate=numeric-grouping-v1 revision=1\n"
            "integrity_status=failed candidate_status=not_recorded\n"
            "problem=retrieval_numeric_comparison_incomplete "
            "cause=numeric comparison report could not be rendered "
            "next_step=inspect_numeric_comparison_inputs",
            True,
        )


def _ingest(engine: KnowledgeEngine, path: Path, *, json_output: bool = False) -> int:
    try:
        if path.suffix.lower() == ".mp4":
            result = engine.ingest_video(path)
        else:
            result = engine.ingest_pdf(path)
    except PdfIngestError as error:
        _print_error_contract(str(error), json_output=json_output)
        return 1
    except VideoIngestError as error:
        _print_error_contract(
            str(error),
            problem=error.problem,
            next_step=error.next_step,
            json_output=json_output,
        )
        return 1
    if json_output:
        payload: dict[str, object] = {
            "ok": True,
            "run_id": result.run_id,
            "run_state": result.run_state.value,
            "evidence_count": result.evidence_count,
        }
        if result.intake_report is not None:
            payload["intake_report"] = _pdf_intake_report_payload(result.intake_report)
        if result.transcript_intake_report is not None:
            payload["transcript_intake_report"] = transcript_intake_report_payload(
                result.transcript_intake_report
            )
        print(json.dumps(payload))
        return 0
    report = (
        f" {_format_pdf_intake_report(result.intake_report)}"
        if result.intake_report is not None
        else ""
    )
    transcript_report = (
        f" {_format_transcript_intake_report(result.transcript_intake_report)}"
        if result.transcript_intake_report is not None
        else ""
    )
    print(
        f"run_id={result.run_id} run_state={result.run_state.value} "
        f"evidence_count={result.evidence_count}{report}{transcript_report}"
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
        f'summary="{result.summary}"'
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


def _run_get(engine: KnowledgeEngine, run_id: str, *, json_output: bool = False) -> int:
    try:
        run = engine.get_run(run_id)
    except KeyError:
        _print_error_contract(f"unknown run: {run_id}", json_output=json_output)
        return 1
    if json_output:
        payload: dict[str, object] = {
            "ok": True,
            "run": {
                "run_id": run.run_id,
                "state": run.state.value,
                "source_generation": run.source_generation,
                "retry_of_run_id": run.retry_of_run_id,
            },
            "events": [
                {"event_index": event.event_index, "event": event.event_type}
                for event in engine.get_run_events(run_id)
            ],
        }
        report = engine.get_pdf_intake_report(run_id)
        if report is not None:
            payload["intake_report"] = _pdf_intake_report_payload(report)
        transcript_report = engine.get_transcript_intake_report(run_id)
        if transcript_report is not None:
            payload["transcript_intake_report"] = transcript_intake_report_payload(
                transcript_report
            )
        print(json.dumps(payload))
        return 0
    retry = f" retry_of_run_id={run.retry_of_run_id}" if run.retry_of_run_id else ""
    print(
        f"run_id={run.run_id} state={run.state.value} "
        f"source_generation={run.source_generation}{retry}"
    )
    report = engine.get_pdf_intake_report(run_id)
    if report is not None:
        print(_format_pdf_intake_report(report))
    transcript_report = engine.get_transcript_intake_report(run_id)
    if transcript_report is not None:
        print(_format_transcript_intake_report(transcript_report))
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


def _proof_transcription_run(
    fixture: Path,
    config: FasterWhisperTranscriptionConfig,
    *,
    json_output: bool,
) -> int:
    report = run_transcription_proof(fixture, config)
    if json_output:
        print(render_transcription_proof_json(report))
    else:
        print(render_transcription_proof_human(report))
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
    json_output: bool = False,
) -> None:
    error = public_error_from_cause(
        cause,
        problem=problem,
        next_step=next_step,
    )
    if json_output:
        print(json.dumps(error.payload()))
    else:
        print(render_public_error_line(error))


def add_transcription_runtime_arguments(
    parser: argparse.ArgumentParser,
    *,
    default_provider: str,
) -> None:
    parser.add_argument(
        "--transcript-provider",
        choices=("sidecar", "faster-whisper"),
        default=default_provider,
    )
    add_faster_whisper_runtime_arguments(parser)


def add_faster_whisper_runtime_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", default="small")
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--language", default="auto")
    parser.add_argument("--model-cache", type=Path)
    parser.add_argument("--transcription-timeout-seconds", type=float, default=900.0)


def runtime_config_from_args(args: argparse.Namespace) -> RuntimeConfig:
    provider = getattr(args, "transcript_provider", "sidecar")
    transcription = (
        _faster_whisper_config_from_args(args)
        if provider == "faster-whisper"
        else SidecarTranscriptionConfig()
    )
    return RuntimeConfig(db_path=args.db, transcription=transcription)


def _faster_whisper_config_from_args(
    args: argparse.Namespace,
) -> FasterWhisperTranscriptionConfig:
    return FasterWhisperTranscriptionConfig(
        model=args.model,
        model_revision=args.model_revision,
        device=args.device,
        compute_type=args.compute_type,
        language=args.language,
        cache_dir=args.model_cache,
        limits=VideoTranscriptionLimits(timeout_seconds=args.transcription_timeout_seconds),
    )


def _transcription_prepare(
    config: FasterWhisperTranscriptionConfig,
    *,
    json_output: bool,
) -> int:
    try:
        result = prepare_model(ModelPreparationConfig(config, allow_model_download=True))
    except ModelResolutionError as error:
        _print_error_contract(
            error.cause,
            problem="transcription_not_ready",
            next_step=error.next_step,
            json_output=json_output,
        )
        return 1
    payload = {
        "status": result.status,
        "provider": result.provider,
        "model": result.model,
        "model_revision": result.model_revision,
    }
    print(json.dumps(payload) if json_output else " ".join(f"{k}={v}" for k, v in payload.items()))
    return 0


def _transcription_doctor(
    config: FasterWhisperTranscriptionConfig,
    *,
    json_output: bool,
) -> int:
    readiness = doctor_transcription(config)
    payload = _readiness_payload(readiness)
    if json_output:
        print(json.dumps(payload))
    else:
        print(" ".join(f"{key}={value}" for key, value in payload.items() if key != "checks"))
        for check in readiness.checks:
            print(f"check={check.name} status={check.status} message={check.message}")
    return 0 if readiness.status == "ready" else 1


def _readiness_payload(readiness: TranscriptionReadiness) -> dict[str, object]:
    return {
        "status": readiness.status,
        "checks": [
            {"name": check.name, "status": check.status, "message": check.message}
            for check in readiness.checks
        ],
        "cause": readiness.cause,
        "next_step": readiness.next_step,
    }


def _pdf_intake_report_payload(report: PdfIntakeReport) -> dict[str, object]:
    return {
        "total_pages": report.total_pages,
        "extracted_pages": report.extracted_pages,
        "empty_pages": report.empty_pages,
        "total_extracted_chars": report.total_extracted_chars,
        "page_char_counts": list(report.page_char_counts),
        "suspected_scanned_pages": report.suspected_scanned_pages,
        "extraction_mode": report.extraction_mode,
        "failure_reason": report.failure_reason,
    }


def _format_pdf_intake_report(report: PdfIntakeReport) -> str:
    return (
        f"pdf_pages={report.total_pages} "
        f"extracted_pages={report.extracted_pages} "
        f"empty_pages={report.empty_pages} "
        f"extracted_chars={report.total_extracted_chars} "
        f"suspected_scanned_pages={report.suspected_scanned_pages}"
    )


def _format_transcript_intake_report(report: TranscriptIntakeReport) -> str:
    payload = transcript_intake_report_payload(report)
    fields = " ".join(f"{key}={value}" for key, value in payload.items())
    return f"transcript_intake_report {fields}"
