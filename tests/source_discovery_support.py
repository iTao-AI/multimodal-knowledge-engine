"""Public synthetic inputs for Source discovery integration."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pymupdf

from mke.application import KnowledgeEngine

CLI = Path.cwd() / ".venv/bin/mke"


def native_cli(database: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI), "--db", str(database), *arguments],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def create_inputs(root: Path) -> tuple[Path, Path]:
    pdf = root / "navigation.pdf"
    document = pymupdf.open()
    for text in (
        "lexicalneedle only on page one",
        "navigation target page two",
        "final page three",
    ):
        page = document.new_page()
        page.insert_text((72, 72), text)  # pyright: ignore[reportUnknownMemberType]
    document.save(pdf)  # pyright: ignore[reportUnknownMemberType]
    document.close()
    video = root / "transcript.mp4"
    video.write_bytes(b"declared public synthetic sidecar fixture; no ASR execution")
    video.with_suffix(".mp4.mke-transcript.json").write_text(
        json.dumps(
            {
                "format": "mke.video_transcript.v1",
                "media": {
                    "container": "mp4",
                    "video_codec": "h264",
                    "audio_codec": "aac",
                    "has_audio": True,
                    "duration_ms": 3000,
                },
                "segments": [
                    {"start_ms": 0, "end_ms": 1000, "text": "First stored transcript."},
                    {"start_ms": 1000, "end_ms": 2000, "text": "Second stored transcript."},
                    {"start_ms": 2000, "end_ms": 3000, "text": "Third stored transcript."},
                ],
            }
        ),
        encoding="utf-8",
    )
    return pdf, video


def create_library(root: Path) -> Path:
    pdf, video = create_inputs(root)
    database = root / "mke.sqlite"
    for path in (pdf, video):
        result = native_cli(database, "ingest", str(path), "--json")
        assert result.returncode == 0, result.stdout + result.stderr
    return database


def publish_pages(
    database: Path, texts: tuple[str, ...], name: str = "large.pdf", fingerprint: str = "a",
    *, evidence_prefix: str | None = None,
) -> tuple[str, str]:
    from mke.domain import (
        PDF_EXTRACTOR_FINGERPRINT,
        REQUIRED_PDF_STAGES,
        CandidateEvidence,
        RunManifest,
    )

    engine = KnowledgeEngine(database)
    try:
        prefix = fingerprint if evidence_prefix is None else evidence_prefix
        source = engine.ensure_source(name, fingerprint * 64)
        run = engine.create_run(source.source_id)
        engine.persist_validated_candidate(
            run.run_id,
            [
                CandidateEvidence(f"ev_{prefix}{index:031x}", "page", index, index, text)
                for index, text in enumerate(texts, 1)
            ],
            RunManifest(
                run.run_id,
                len(texts),
                tuple(sorted(REQUIRED_PDF_STAGES)),
                PDF_EXTRACTOR_FINGERPRINT,
                fingerprint * 64,
            ),
        )
        engine.activate_publication(run.run_id)
        selected = engine.ensure_source(name, fingerprint * 64)
        assert selected.active_publication_id is not None
        return source.source_id, selected.active_publication_id
    finally:
        engine.close()


def cli_payloads(result: subprocess.CompletedProcess[str]) -> list[dict[str, Any]]:
    assert result.returncode == 0, result.stdout + result.stderr
    return [json.loads(line) for line in result.stdout.splitlines()]
