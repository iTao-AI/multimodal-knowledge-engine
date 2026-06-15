"""Command-line entrypoint for the local-first Evidence engine."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from mke.application import KnowledgeEngine, PdfIngestError


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

    args = parser.parse_args(argv)
    engine = KnowledgeEngine(args.db)
    try:
        if args.command == "ingest":
            return _ingest(engine, args.file)
        return _search(engine, " ".join(args.query))
    finally:
        engine.close()


def console_main() -> int:
    """Console script entrypoint."""
    argv = sys.argv[1:]
    return main(argv if argv else None)


def _ingest(engine: KnowledgeEngine, path: Path) -> int:
    try:
        result = engine.ingest_pdf(path)
    except PdfIngestError as error:
        print(f"error={error}")
        return 1
    print(
        f"run_id={result.run_id} run_state={result.run_state.value} "
        f"evidence_count={result.evidence_count}"
    )
    return 0


def _search(engine: KnowledgeEngine, query: str) -> int:
    for match in engine.search(query):
        print(f"page={match.page_number} evidence_id={match.evidence_id} text={match.text}")
    return 0
