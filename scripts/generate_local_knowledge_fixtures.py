#!/usr/bin/env python3
"""Generate the repository-owned synthetic local knowledge fixture pack."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import fitz

_PAGES = {
    "operations-guide.pdf": (
        "Cedar Relay maintenance window begins Tuesday at 14:00 UTC. "
        "Operators complete checklist KITE-17 before restart."
    ),
    "incident-guide.pdf": (
        "When Cedar Relay telemetry turns amber, pause intake and review the Evidence log "
        "before restarting the relay."
    ),
}

_QUERIES = {
    "search": "Cedar Relay maintenance window",
    "answer": "Cedar Relay telemetry amber",
    "refusal": "lunar payroll retention policy",
}


def generate_fixture_pack(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, object]] = []
    for name, text in _PAGES.items():
        path = output_dir / name
        _write_pdf(path, name=name, text=text)
        content = path.read_bytes()
        files.append(
            {
                "name": name,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )

    manifest: dict[str, object] = {
        "format": "mke.local_knowledge_fixture.v1",
        "files": files,
        "queries": _QUERIES,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def _write_pdf(path: Path, *, name: str, text: str) -> None:
    document: Any = fitz.open()
    try:
        page: Any = document.new_page(width=612, height=792)
        written: float = page.insert_textbox(
            fitz.Rect(72, 72, 540, 720),
            text,
            fontsize=12,
            fontname="helv",
        )
        if written < 0:
            raise RuntimeError("fixture text did not fit")
        document.set_metadata(
            {
                "title": f"MKE local knowledge fixture: {name}",
                "author": "Multimodal Knowledge Engine",
                "subject": "Repository-authored synthetic local knowledge proof",
            }
        )
        document.save(
            path,
            garbage=4,
            clean=True,
            deflate=True,
            no_new_id=True,
        )
    finally:
        document.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    generate_fixture_pack(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

