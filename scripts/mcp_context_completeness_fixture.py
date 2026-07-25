#!/usr/bin/env python3
"""Create the deterministic database used by the installed MCP completeness proof."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from mke.application import KnowledgeEngine
from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    CandidateEvidence,
    RunManifest,
)

FIXTURE_SCHEMA = "mke.mcp_context_fixture.v1"


def _opaque_id(prefix: str, value: str) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:32]}"


def _publish(engine: KnowledgeEngine, name: str, texts: list[str]) -> None:
    fingerprint = hashlib.sha256(name.encode("utf-8")).hexdigest()
    source = engine.ensure_source(name, fingerprint)
    run = engine.create_run(source.source_id)
    evidence = [
        CandidateEvidence(
            evidence_id=_opaque_id("ev", f"{name}:{index}"),
            locator_kind="page",
            locator_start=index,
            locator_end=index,
            text=text,
        )
        for index, text in enumerate(texts, start=1)
    ]
    engine.persist_validated_candidate(
        run.run_id,
        evidence,
        RunManifest(
            run_id=run.run_id,
            evidence_count=len(evidence),
            required_stages=tuple(sorted(REQUIRED_PDF_STAGES)),
            extractor_fingerprint=PDF_EXTRACTOR_FINGERPRINT,
            asset_sha256=fingerprint,
        ),
    )
    engine.activate_publication(run.run_id)


def create_fixture(database: Path) -> None:
    engine = KnowledgeEngine(database)
    try:
        _publish(
            engine,
            "continuation.pdf",
            [
                "publication authority continuation alpha",
                "publication authority continuation beta",
            ],
        )
        large_text = (
            ("bounded prefix material " * 160)
            + "late completeness marker "
            + ("authoritative evidence payload " * 40000)
        )
        _publish(engine, "large.pdf", [large_text])
        _publish(
            engine,
            "cjk.pdf",
            [f"知识完整性证据 第{index}项" for index in range(1, 12)],
        )
    finally:
        engine.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    try:
        create_fixture(args.database.resolve())
    except Exception:
        print(json.dumps({"status": "failed", "code": "fixture_setup_failed"}))
        return 1
    print(
        json.dumps(
            {"status": "passed", "fixture_schema": FIXTURE_SCHEMA},
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
