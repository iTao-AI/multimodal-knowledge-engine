#!/usr/bin/env python3
"""Independently validate v3 files and local PDF observations using only stdlib."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast

_SCRIPT_DIRECTORY = str(Path(__file__).resolve().parent)
if _SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, _SCRIPT_DIRECTORY)

from compiled_library_export_consumer_v2 import (  # noqa: E402
    ValidatedExport,
    ValidationError,
    _load_validated_export,  # pyright: ignore[reportPrivateUsage]
    _object,  # pyright: ignore[reportPrivateUsage]
    _positive_int,  # pyright: ignore[reportPrivateUsage]
)

_COUNTS = (
    "text_only_pages",
    "mixed_text_raster_pages",
    "raster_only_pages",
    "neither_text_nor_raster_pages",
)
_KEYS = {
    "schema_version",
    "status",
    "method",
    "extraction_scope",
    "total_pages",
    *_COUNTS,
    "pages",
    "returned_page_range",
    "omitted_page_ranges",
}


def _range(value: object, total: int) -> dict[str, object]:
    value = _object(value, {"start", "end"})
    start, end = _positive_int(value["start"]), _positive_int(value["end"])
    if start > end or end > total:
        raise ValidationError
    return value


def _validate_observation(entry: dict[str, object], rows: Sequence[dict[str, object]]) -> None:
    raw = entry["pdf_extraction_observation"]
    if entry["media_type"] != "application/pdf":
        if raw is not None:
            raise ValidationError
        return
    value = _object(raw, _KEYS)
    if value["schema_version"] != "mke.pdf_extraction_observation.v1":
        raise ValidationError
    if value["status"] == "not_observed":
        if (
            any(
                value[key] is not None
                for key in ("total_pages", "method", "extraction_scope", *_COUNTS)
            )
            or value["pages"] != []
            or value["returned_page_range"] is not None
            or value["omitted_page_ranges"] != []
        ):
            raise ValidationError
        return
    if (
        value["status"] != "observed"
        or value["method"] != "pymupdf-displayed-raster-v1"
        or value["extraction_scope"] != "text_layer_only"
    ):
        raise ValidationError
    total = _positive_int(value["total_pages"])
    counts = [_positive_int(value[key], allow_zero=True) for key in _COUNTS]
    if sum(counts) != total or counts[0] + counts[1] != len(rows):
        raise ValidationError
    if type(value["pages"]) is not list or type(value["omitted_page_ranges"]) is not list:
        raise ValidationError
    pages = cast(list[object], value["pages"])
    if len(pages) > 256:
        raise ValidationError
    known: dict[int, int] = {}
    categories = [0, 0, 0, 0]
    for raw_page in pages:
        page = _object(raw_page, {"page_number", "text_layer_chars", "has_raster_images"})
        number = _positive_int(page["page_number"])
        chars = _positive_int(page["text_layer_chars"], allow_zero=True)
        raster = page["has_raster_images"]
        if type(raster) is not bool or number > total or number in known:
            raise ValidationError
        known[number] = chars
        category = (1 if raster else 0) if chars else (2 if raster else 3)
        categories[category] += 1
    returned = value["returned_page_range"]
    omitted: list[dict[str, object]]
    if known:
        bounds = _range(returned, total)
        start, end = cast(int, bounds["start"]), cast(int, bounds["end"])
        if list(known) != list(range(start, end + 1)):
            raise ValidationError
        omitted = [
            {"start": start, "end": end}
            for start, end in ((1, start - 1), (end + 1, total))
            if start <= end
        ]
    else:
        if returned is not None:
            raise ValidationError
        omitted = [{"start": 1, "end": total}]
    actual_omitted = [
        _range(item, total) for item in cast(list[object], value["omitted_page_ranges"])
    ]
    if actual_omitted != omitted or any(
        part > count for part, count in zip(categories, counts, strict=True)
    ):
        raise ValidationError
    by_page = {cast(int, cast(dict[str, object], row["locator"])["start"]): row for row in rows}
    if len(by_page) != len(rows) or any(number > total for number in by_page):
        raise ValidationError
    for number, chars in known.items():
        row = by_page.get(number)
        if chars != (0 if row is None else len(cast(str, row["text"]))):
            raise ValidationError


def load_validated_export(export: Path) -> ValidatedExport:
    return _load_validated_export(
        export,
        format_version="v3",
        observation_validator=_validate_observation,
    )


def validate(export: Path) -> dict[str, object]:
    snapshot = load_validated_export(export)
    observations = [source.descriptor["pdf_extraction_observation"] for source in snapshot.sources]
    return {
        "schema_version": "mke.compiled_library_export_consumer.v3",
        "status": "passed",
        "export_schema": "mke.compiled_library_export.v3",
        "markdown_format": "mke.compiled_markdown.v3",
        "evidence_schema": "mke.evidence_ref.v1",
        "observed_pdf_sources": sum(
            isinstance(item, dict) and cast(dict[str, object], item)["status"] == "observed"
            for item in observations
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = validate(args.export)
    except (OSError, ValueError, TypeError, ValidationError):
        result = {"status": "failed", "code": "export_invalid"}
        exit_code = 1
    else:
        exit_code = 0
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
