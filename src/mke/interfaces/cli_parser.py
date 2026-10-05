"""Argparse declarations for the local-first Evidence engine CLI."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Protocol, cast

from mke.embeddings.contracts import CANDIDATE_ID as DENSE_CANDIDATE_ID
from mke.embeddings.contracts import MODEL_REVISION as EMBEDDING_MODEL_REVISION
from mke.embeddings.readiness import MODEL_CLI_ID as EMBEDDING_MODEL_CLI_ID
from mke.evaluation.cjk_lexical_candidate import CJK_LEXICAL_CANDIDATE
from mke.evaluation.hybrid_rrf_protocol import (
    CANDIDATE_ID as HYBRID_RRF_CANDIDATE_ID,
)
from mke.evaluation.relevance_gate_protocol import (
    CANDIDATE_ID as RELEVANCE_GATE_CANDIDATE_ID,
)
from mke.retrieval import (
    SUPPORTED_RETRIEVAL_QUERY_POLICIES,
    SUPPORTED_RETRIEVAL_STRATEGIES,
)
from mke.runtime import DEFAULT_MODEL_REVISION


class _SubcommandRegistrar(Protocol):
    def add_parser(self, name: str, **kwargs: Any) -> argparse.ArgumentParser: ...


_DEFAULT_PDF_FIXTURE = Path("tests/fixtures/pdf/text-layer.pdf")
_DEFAULT_REVISED_PDF_FIXTURE = Path("tests/fixtures/pdf/text-layer-revised.pdf")
_DEFAULT_VIDEO_FIXTURE = Path("tests/fixtures/video/short-audio.mp4")
_DEFAULT_TRANSCRIPTION_PROOF_FIXTURE = Path("tests/fixtures/video/spoken-evidence.mp4")


def build_cli_parser() -> argparse.ArgumentParser:
    """Build the complete parser while preserving the CLI declaration order."""
    parser = argparse.ArgumentParser(prog="mke")
    parser.add_argument("--db", type=Path, default=Path("mke.sqlite"))
    parser.add_argument(
        "--retrieval-query-policy",
        choices=SUPPORTED_RETRIEVAL_QUERY_POLICIES,
    )
    parser.add_argument(
        "--retrieval-strategy",
        choices=SUPPORTED_RETRIEVAL_STRATEGIES,
    )
    subcommands = cast(
        _SubcommandRegistrar,
        parser.add_subparsers(dest="command", required=True),
    )

    _register_ingest_search_ask(subcommands)
    _register_source_discovery(subcommands)
    _register_library_export(subcommands)
    _register_retrieval_admin(subcommands)
    _register_run(subcommands)
    _register_demo_and_proof(subcommands)
    _register_evaluation(subcommands)
    _register_mcp(subcommands)
    _register_transcription(subcommands)
    _register_embedding(subcommands)
    return parser


def _register_ingest_search_ask(subcommands: _SubcommandRegistrar) -> None:
    ingest = subcommands.add_parser("ingest")
    ingest.add_argument("file", type=Path)
    ingest.add_argument("--json", action="store_true", dest="json_output")
    add_transcription_runtime_arguments(ingest, default_provider="sidecar")
    add_direct_audio_supervision_arguments(ingest)

    search = subcommands.add_parser("search")
    search.add_argument("query", nargs="+")

    ask = subcommands.add_parser("ask")
    ask.add_argument("question", nargs="+")


def _register_library_export(subcommands: _SubcommandRegistrar) -> None:
    library = subcommands.add_parser("library")
    library_commands = cast(
        _SubcommandRegistrar,
        library.add_subparsers(dest="library_command", required=True),
    )
    library_export = library_commands.add_parser("export")
    library_export.add_argument("--output", required=True)
    library_export.add_argument(
        "--format-version", choices=("v1", "v2"), default="v1"
    )
    library_export.add_argument("--json", action="store_true", dest="json_output")


def _register_retrieval_admin(subcommands: _SubcommandRegistrar) -> None:
    retrieval_admin = subcommands.add_parser("retrieval")
    retrieval_subcommands = cast(
        _SubcommandRegistrar,
        retrieval_admin.add_subparsers(
            dest="retrieval_command", required=True
        ),
    )
    retrieval_doctor = retrieval_subcommands.add_parser("doctor")
    retrieval_doctor.add_argument(
        "--strategy", choices=SUPPORTED_RETRIEVAL_STRATEGIES, required=True
    )
    retrieval_doctor.add_argument("--json", action="store_true", dest="json_output")
    retrieval_rebuild = retrieval_subcommands.add_parser("rebuild")
    retrieval_rebuild.add_argument(
        "--strategy", choices=SUPPORTED_RETRIEVAL_STRATEGIES, required=True
    )
    retrieval_rebuild.add_argument("--json", action="store_true", dest="json_output")


def _register_run(subcommands: _SubcommandRegistrar) -> None:
    run = subcommands.add_parser("run")
    run_subcommands = cast(
        _SubcommandRegistrar,
        run.add_subparsers(dest="run_command", required=True),
    )
    run_get = run_subcommands.add_parser("get")
    run_get.add_argument("run_id")
    run_get.add_argument("--json", action="store_true", dest="json_output")


def _register_demo_and_proof(subcommands: _SubcommandRegistrar) -> None:
    demo = subcommands.add_parser("demo")
    demo.add_argument("--verify", action="store_true", required=True)
    demo.add_argument("--fixture", type=Path, default=_DEFAULT_PDF_FIXTURE)
    demo.add_argument("--revised-fixture", type=Path, default=_DEFAULT_REVISED_PDF_FIXTURE)
    demo.add_argument("--video-fixture", type=Path, default=_DEFAULT_VIDEO_FIXTURE)

    proof = subcommands.add_parser("proof")
    proof_subcommands = cast(
        _SubcommandRegistrar,
        proof.add_subparsers(dest="proof_command", required=True),
    )
    proof_run = proof_subcommands.add_parser("run")
    proof_run.add_argument("--json", action="store_true", dest="json_output")
    proof_direct_audio = proof_subcommands.add_parser("direct-audio")
    proof_direct_audio.add_argument("--json", action="store_true", dest="json_output")
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


def _register_evaluation(subcommands: _SubcommandRegistrar) -> None:
    evaluation = subcommands.add_parser("eval")
    evaluation_subcommands = cast(
        _SubcommandRegistrar,
        evaluation.add_subparsers(
            dest="evaluation_command", required=True
        ),
    )
    _register_retrieval_baseline(evaluation_subcommands)
    _register_numeric_comparison(evaluation_subcommands)
    _register_chinese_baseline(evaluation_subcommands)
    _register_cjk_lexical_comparison(evaluation_subcommands)
    _register_dense_comparison(evaluation_subcommands)
    _register_hybrid_rrf_comparison(evaluation_subcommands)
    _register_relevance_gate_comparison(evaluation_subcommands)


def _register_retrieval_baseline(
    evaluation_subcommands: _SubcommandRegistrar,
) -> None:
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


def _register_numeric_comparison(
    evaluation_subcommands: _SubcommandRegistrar,
) -> None:
    numeric_retrieval = evaluation_subcommands.add_parser(
        "retrieval-numeric",
        description=(
            "Run the historical comparison-only public-holdout numeric protocol. "
            "The holdout is public rather than blind, policy is protocol-owned, "
            "and this command does not select the runtime strategy."
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


def _register_chinese_baseline(
    evaluation_subcommands: _SubcommandRegistrar,
) -> None:
    chinese_retrieval = evaluation_subcommands.add_parser(
        "retrieval-chinese",
        description=(
            "Record the current FTS5 lexical baseline on a small public Chinese "
            "development/holdout corpus; no retrieval-quality threshold is applied "
            "and no dense, hybrid, or reranker claim is made."
        ),
    )
    chinese_retrieval.add_argument(
        "--protocol",
        type=Path,
        required=True,
        help="locked Chinese retrieval evaluation protocol",
    )
    chinese_retrieval.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
    )


def _register_cjk_lexical_comparison(
    evaluation_subcommands: _SubcommandRegistrar,
) -> None:
    cjk_lexical_retrieval = evaluation_subcommands.add_parser(
        "retrieval-cjk-lexical",
        description=(
            "Run the historical E3-B comparison-only CJK trigram-overlap candidate; "
            "candidate and policy are protocol-owned. This command does not select "
            "the runtime strategy or add embedding, vector, hybrid, RRF, reranker, "
            "or query rewrite behavior."
        ),
    )
    cjk_lexical_retrieval.add_argument(
        "--protocol",
        type=Path,
        required=True,
        help="locked Chinese retrieval evaluation protocol",
    )
    cjk_lexical_retrieval.add_argument(
        "--candidate",
        choices=(CJK_LEXICAL_CANDIDATE.candidate_id,),
        required=True,
        help="allowlisted CJK lexical candidate identifier",
    )
    cjk_lexical_retrieval.add_argument(
        "--record",
        type=Path,
        help="write the canonical CJK lexical comparison artifact",
    )
    cjk_lexical_retrieval.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
    )


def _register_dense_comparison(
    evaluation_subcommands: _SubcommandRegistrar,
) -> None:
    dense_retrieval = evaluation_subcommands.add_parser(
        "retrieval-dense",
        description=(
            "Run the E3-C cache-only dense comparison-only protocol. The two phases "
            "record a development freeze before one holdout observation and this "
            "command does not change Search, Ask, MCP, or runtime defaults."
        ),
    )
    dense_retrieval.add_argument("--protocol", type=Path, required=True)
    dense_retrieval.add_argument(
        "--candidate", choices=(DENSE_CANDIDATE_ID,), required=True
    )
    dense_retrieval.add_argument("--model-cache", type=Path, required=True)
    dense_retrieval.add_argument("--development-only", action="store_true")
    dense_retrieval.add_argument("--record-development-freeze", type=Path)
    dense_retrieval.add_argument("--development-freeze", type=Path)
    dense_retrieval.add_argument("--record", type=Path)
    dense_retrieval.add_argument("--record-holdout-receipt", type=Path)
    dense_retrieval.add_argument("--json", action="store_true", dest="json_output")


def _register_hybrid_rrf_comparison(
    evaluation_subcommands: _SubcommandRegistrar,
) -> None:
    hybrid_rrf_retrieval = evaluation_subcommands.add_parser(
        "retrieval-hybrid-rrf",
        description=(
            "Run the E3-D comparison-only rank-only RRF candidate over frozen "
            "lexical and dense observations. This command does not promote or "
            "change the runtime default, Search, Ask, MCP, or Publication behavior."
        ),
    )
    hybrid_rrf_retrieval.add_argument("--protocol", type=Path, required=True)
    hybrid_rrf_retrieval.add_argument(
        "--candidate", choices=(HYBRID_RRF_CANDIDATE_ID,), required=True
    )
    hybrid_rrf_retrieval.add_argument("--dense-artifact", type=Path, required=True)
    hybrid_rrf_retrieval.add_argument("--development-only", action="store_true")
    hybrid_rrf_retrieval.add_argument("--record-development-freeze", type=Path)
    hybrid_rrf_retrieval.add_argument("--development-freeze", type=Path)
    hybrid_rrf_retrieval.add_argument("--record", type=Path)
    hybrid_rrf_retrieval.add_argument("--record-holdout-receipt", type=Path)
    hybrid_rrf_retrieval.add_argument(
        "--json", action="store_true", dest="json_output"
    )


def _register_relevance_gate_comparison(
    evaluation_subcommands: _SubcommandRegistrar,
) -> None:
    relevance_gate_retrieval = evaluation_subcommands.add_parser(
        "retrieval-relevance-gate",
        description=(
            "Run the E3-E comparison-only deterministic relevance gate and "
            "reranker protocol. This command does not promote or change the "
            "runtime default, Search, Ask, MCP, owner startup, Publication, "
            "or ingestion behavior."
        ),
    )
    relevance_gate_retrieval.add_argument("--protocol", type=Path, required=True)
    relevance_gate_retrieval.add_argument(
        "--candidate", choices=(RELEVANCE_GATE_CANDIDATE_ID,), required=True
    )
    relevance_gate_retrieval.add_argument("--development-only", action="store_true")
    relevance_gate_retrieval.add_argument("--record-development-freeze", type=Path)
    relevance_gate_retrieval.add_argument("--development-freeze", type=Path)
    relevance_gate_retrieval.add_argument("--record", type=Path)
    relevance_gate_retrieval.add_argument("--record-holdout-receipt", type=Path)
    relevance_gate_retrieval.add_argument(
        "--json", action="store_true", dest="json_output"
    )


def _register_mcp(subcommands: _SubcommandRegistrar) -> None:
    mcp = subcommands.add_parser("mcp")
    mcp.add_argument("--allowed-root", type=Path, default=Path.cwd())
    add_transcription_runtime_arguments(mcp, default_provider="sidecar")
    add_direct_audio_supervision_arguments(mcp)


def _register_transcription(subcommands: _SubcommandRegistrar) -> None:
    transcription = subcommands.add_parser("transcription")
    transcription_subcommands = cast(
        _SubcommandRegistrar,
        transcription.add_subparsers(
            dest="transcription_command", required=True
        ),
    )
    prepare = transcription_subcommands.add_parser("prepare")
    prepare.add_argument("--allow-model-download", action="store_true", required=True)
    prepare.add_argument("--json", action="store_true", dest="json_output")
    add_transcription_runtime_arguments(prepare, default_provider="faster-whisper")
    doctor = transcription_subcommands.add_parser("doctor")
    doctor.add_argument("--json", action="store_true", dest="json_output")
    add_transcription_runtime_arguments(doctor, default_provider="faster-whisper")


def _register_embedding(subcommands: _SubcommandRegistrar) -> None:
    embedding = subcommands.add_parser("embedding")
    embedding_subcommands = cast(
        _SubcommandRegistrar,
        embedding.add_subparsers(
            dest="embedding_command", required=True
        ),
    )
    embedding_prepare = embedding_subcommands.add_parser("prepare")
    embedding_prepare.add_argument(
        "--allow-model-download", action="store_true", required=True
    )
    embedding_prepare.add_argument("--json", action="store_true", dest="json_output")
    add_embedding_runtime_arguments(embedding_prepare)
    embedding_doctor = embedding_subcommands.add_parser("doctor")
    embedding_doctor.add_argument("--json", action="store_true", dest="json_output")
    add_embedding_runtime_arguments(embedding_doctor)


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


def add_direct_audio_supervision_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--direct-audio-footprint-bytes",
        type=_positive_int,
    )
    parser.add_argument(
        "--direct-audio-footprint-budget-mode",
        choices=("baseline_plus",),
    )


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("value must be a positive integer") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def add_embedding_runtime_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--model",
        choices=(EMBEDDING_MODEL_CLI_ID,),
        default=EMBEDDING_MODEL_CLI_ID,
    )
    parser.add_argument(
        "--model-revision",
        choices=(EMBEDDING_MODEL_REVISION,),
        default=EMBEDDING_MODEL_REVISION,
    )
    parser.add_argument("--model-cache", type=Path)


def _register_source_discovery(subcommands: _SubcommandRegistrar) -> None:
    sources = subcommands.add_parser("sources")
    catalog = sources.add_subparsers(dest="sources_command", required=True).add_parser("list")
    catalog.add_argument("--page-size", type=int, default=10)
    catalog.add_argument("--contract-version", choices=("v1", "v2"), default="v1")
    catalog.add_argument("--json", action="store_true", dest="json_output")

    source = subcommands.add_parser("source")
    browse = source.add_subparsers(dest="source_command", required=True).add_parser("browse")
    browse.add_argument("source_id")
    browse.add_argument("--publication-id", required=True)
    browse.add_argument("--page-size", type=int, default=10)
    browse.add_argument("--contract-version", choices=("v1", "v2"), default="v1")
    browse.add_argument("--page-start", type=int)
    browse.add_argument("--page-end", type=int)
    browse.add_argument("--start-ms", type=int)
    browse.add_argument("--end-ms", type=int)
    browse.add_argument("--json", action="store_true", dest="json_output")

    evidence = subcommands.add_parser("evidence")
    read = evidence.add_subparsers(dest="evidence_command", required=True).add_parser("read")
    read.add_argument("evidence_id")
    read.add_argument("--max-bytes", type=int, default=16384)
    read.add_argument("--json", action="store_true", dest="json_output")
