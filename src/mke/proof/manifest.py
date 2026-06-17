"""Built-in product proof manifest."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProofFixtures:
    text_layer_pdf: Path
    revised_pdf: Path
    video: Path
    video_transcript: Path


@dataclass(frozen=True)
class ProofManifest:
    name: str
    cases: tuple[str, ...]
    fixtures: ProofFixtures


PRODUCT_PROOF_MANIFEST = ProofManifest(
    name="product",
    cases=(
        "cli_pdf_ingest",
        "cli_pdf_search",
        "cli_failed_reprocess",
        "cli_video_ingest_search",
        "cli_ask",
        "mcp_ingest_file",
        "mcp_get_run",
        "mcp_search_and_ask",
    ),
    fixtures=ProofFixtures(
        text_layer_pdf=Path("tests/fixtures/pdf/text-layer.pdf"),
        revised_pdf=Path("tests/fixtures/pdf/text-layer-revised.pdf"),
        video=Path("tests/fixtures/video/short-audio.mp4"),
        video_transcript=Path("tests/fixtures/video/short-audio.mp4.mke-transcript.json"),
    ),
)
