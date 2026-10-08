#!/usr/bin/env python3
"""Generate the separately named, repository-authored synthetic installation pack."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pymupdf


def build_assets(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=False)
    sources: list[dict[str, str | int]] = []
    for role, count, text in [
        ("selected", 3, "needle café selected"),
        ("other", 5, "needle outsideonly"),
    ]:
        path = root / f"{role}.pdf"
        document = pymupdf.open()
        for number in range(count):
            page = document.new_page()
            page.insert_text((72, 72), f"{text} page {number + 1}")  # pyright: ignore[reportUnknownMemberType]
        document.save(path, no_new_id=True)  # pyright: ignore[reportUnknownMemberType]
        document.close()
        content = path.read_bytes()
        sources.append(
            {
                "role": role,
                "filename": path.name,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "pages": count,
            }
        )
    (root / "manifest.json").write_text(
        json.dumps(
            {"schema_version": "mke.source_evidence_installed_manifest.v1", "sources": sources},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    build_assets(parser.parse_args().output_dir)


if __name__ == "__main__":
    main()
