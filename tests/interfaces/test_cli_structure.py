from __future__ import annotations

import argparse
from pathlib import Path
from typing import cast

import pytest

from mke.interfaces.cli_parser import build_cli_parser

TOP_LEVEL_COMMANDS = (
    "ingest",
    "search",
    "ask",
    "library",
    "retrieval",
    "run",
    "demo",
    "proof",
    "eval",
    "mcp",
    "transcription",
    "embedding",
)


def _subparser_choices(
    parser: argparse.ArgumentParser, dest: str
) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if getattr(action, "dest", None) == dest:
            choices = getattr(action, "choices", None)
            if isinstance(choices, dict):
                return cast(dict[str, argparse.ArgumentParser], choices)
    raise AssertionError(f"missing subparser action: {dest}")


def test_build_cli_parser_preserves_public_command_order_and_dest_identities() -> None:
    parser = build_cli_parser()

    top_level = _subparser_choices(parser, "command")
    assert tuple(top_level) == TOP_LEVEL_COMMANDS
    assert tuple(_subparser_choices(top_level["library"], "library_command")) == ("export",)
    assert tuple(_subparser_choices(top_level["retrieval"], "retrieval_command")) == (
        "doctor",
        "rebuild",
    )
    assert tuple(_subparser_choices(top_level["run"], "run_command")) == ("get",)
    assert tuple(_subparser_choices(top_level["proof"], "proof_command")) == (
        "run",
        "direct-audio",
        "transcription-run",
        "transcript-smoke",
    )
    assert tuple(_subparser_choices(top_level["eval"], "evaluation_command")) == (
        "retrieval",
        "retrieval-numeric",
        "retrieval-chinese",
        "retrieval-cjk-lexical",
        "retrieval-dense",
        "retrieval-hybrid-rrf",
        "retrieval-relevance-gate",
    )
    assert tuple(_subparser_choices(top_level["transcription"], "transcription_command")) == (
        "prepare",
        "doctor",
    )
    assert tuple(_subparser_choices(top_level["embedding"], "embedding_command")) == (
        "prepare",
        "doctor",
    )


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (
            ["ingest", "document.pdf"],
            {
                "command": "ingest",
                "file": Path("document.pdf"),
                "json_output": False,
                "transcript_provider": "sidecar",
                "model": "small",
                "model_revision": "536b0662742c02347bc0e980a01041f333bce120",
                "device": "cpu",
                "compute_type": "int8",
                "language": "auto",
                "model_cache": None,
                "transcription_timeout_seconds": 900.0,
                "direct_audio_footprint_bytes": None,
                "direct_audio_footprint_budget_mode": None,
            },
        ),
        (["search", "two", "words"], {"command": "search", "query": ["two", "words"]}),
        (["ask", "one", "question"], {"command": "ask", "question": ["one", "question"]}),
        (
            ["library", "export", "--output", "out"],
            {
                "command": "library",
                "library_command": "export",
                "output": "out",
                "format_version": "v1",
                "json_output": False,
            },
        ),
        (
            ["retrieval", "doctor", "--strategy", "current"],
            {
                "command": "retrieval",
                "retrieval_command": "doctor",
                "strategy": "current",
                "json_output": False,
            },
        ),
        (
            ["run", "get", "run-123"],
            {
                "command": "run",
                "run_command": "get",
                "run_id": "run-123",
                "json_output": False,
            },
        ),
        (
            ["demo", "--verify"],
            {
                "command": "demo",
                "verify": True,
                "fixture": Path("tests/fixtures/pdf/text-layer.pdf"),
                "revised_fixture": Path("tests/fixtures/pdf/text-layer-revised.pdf"),
                "video_fixture": Path("tests/fixtures/video/short-audio.mp4"),
            },
        ),
        (
            ["proof", "run"],
            {"command": "proof", "proof_command": "run", "json_output": False},
        ),
        (
            ["eval", "retrieval", "--manifest", "manifest.json"],
            {
                "command": "eval",
                "evaluation_command": "retrieval",
                "manifest": Path("manifest.json"),
                "json_output": False,
            },
        ),
        (
            ["eval", "retrieval-dense", "--protocol", "protocol.json", "--candidate",
             "qwen3-embedding-0.6b-exact-v1", "--model-cache", "cache", "--development-only",
             "--record-development-freeze", "freeze.json"],
            {
                "command": "eval",
                "evaluation_command": "retrieval-dense",
                "protocol": Path("protocol.json"),
                "candidate": "qwen3-embedding-0.6b-exact-v1",
                "model_cache": Path("cache"),
                "development_only": True,
                "record_development_freeze": Path("freeze.json"),
                "development_freeze": None,
                "record": None,
                "record_holdout_receipt": None,
                "json_output": False,
            },
        ),
        (
            ["mcp"],
            {
                "command": "mcp",
                "allowed_root": Path.cwd(),
                "transcript_provider": "sidecar",
                "model": "small",
                "model_revision": "536b0662742c02347bc0e980a01041f333bce120",
                "device": "cpu",
                "compute_type": "int8",
                "language": "auto",
                "model_cache": None,
                "transcription_timeout_seconds": 900.0,
                "direct_audio_footprint_bytes": None,
                "direct_audio_footprint_budget_mode": None,
            },
        ),
        (
            ["transcription", "prepare", "--allow-model-download"],
            {
                "command": "transcription",
                "transcription_command": "prepare",
                "allow_model_download": True,
                "json_output": False,
                "transcript_provider": "faster-whisper",
                "model": "small",
                "model_revision": "536b0662742c02347bc0e980a01041f333bce120",
                "device": "cpu",
                "compute_type": "int8",
                "language": "auto",
                "model_cache": None,
                "transcription_timeout_seconds": 900.0,
            },
        ),
        (
            ["embedding", "doctor"],
            {
                "command": "embedding",
                "embedding_command": "doctor",
                "json_output": False,
                "model": "qwen3-embedding-0.6b",
                "model_revision": "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
                "model_cache": None,
            },
        ),
    ],
)
def test_build_cli_parser_preserves_leaf_destinations_and_defaults(
    argv: list[str], expected: dict[str, object]
) -> None:
    args = build_cli_parser().parse_args(argv)

    assert args.db == Path("mke.sqlite")
    assert args.retrieval_query_policy is None
    assert args.retrieval_strategy is None
    for name, value in expected.items():
        assert getattr(args, name) == value


@pytest.mark.parametrize(
    "argv",
    [
        ["eval", "retrieval-numeric", "--protocol", "protocol.json"],
        ["eval", "retrieval-chinese", "--protocol", "protocol.json"],
        [
            "eval",
            "retrieval-cjk-lexical",
            "--protocol",
            "protocol.json",
            "--candidate",
            "cjk-trigram-overlap-v1",
        ],
        [
            "eval",
            "retrieval-hybrid-rrf",
            "--protocol",
            "protocol.json",
            "--candidate",
            "cjk-active-scan-qwen3-rrf-v1",
            "--dense-artifact",
            "dense.json",
            "--development-only",
            "--record-development-freeze",
            "freeze.json",
        ],
        [
            "eval",
            "retrieval-relevance-gate",
            "--protocol",
            "protocol.json",
            "--candidate",
            "cjk-relevance-gate-reranker-v1",
            "--development-only",
            "--record-development-freeze",
            "freeze.json",
        ],
    ],
)
def test_build_cli_parser_keeps_comparison_candidate_leafs_parseable(
    argv: list[str],
) -> None:
    args = build_cli_parser().parse_args(argv)

    assert args.command == "eval"
    assert args.evaluation_command.startswith("retrieval-")
    assert args.json_output is False
