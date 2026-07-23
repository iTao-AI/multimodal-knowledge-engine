#!/usr/bin/env python3
"""Validate a portable compiled Library export without producer code."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any, cast

_MAX_FILE_BYTES = 64 * 1024 * 1024
_READ_BYTES = 64 * 1024
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER = {
    "source_id": re.compile(r"src_[0-9a-f]{32}\Z"),
    "publication_id": re.compile(r"pub_[0-9a-f]{32}\Z"),
    "run_id": re.compile(r"run_[0-9a-f]{32}\Z"),
    "evidence_id": re.compile(r"ev_[0-9a-f]{32}\Z"),
}
_MANIFEST_KEYS = {
    "schema_version",
    "evidence_schema",
    "markdown_format",
    "observation",
    "sources",
}
_OBSERVATION_KEYS = {
    "schema_version",
    "library_id",
    "state",
    "source_count",
    "active_publication_count",
    "active_evidence_count",
}
_SOURCE_KEYS = {
    "source_id",
    "display_name",
    "content_fingerprint",
    "media_type",
    "publication_id",
    "publication_revision",
    "run_id",
    "extractor_fingerprint",
    "required_stages",
    "evidence_count",
    "evidence_path",
    "evidence_sha256",
    "markdown_path",
    "markdown_sha256",
}
_EVIDENCE_KEYS = {
    "schema_version",
    "evidence_id",
    "source_id",
    "content_fingerprint",
    "publication_id",
    "publication_revision",
    "run_id",
    "locator",
    "text",
}
_LOCATOR_KEYS = {"kind", "start", "end"}
_DISPLAY_NAME_MAX_CHARS = 1024
_EVIDENCE_TEXT_MAX_CHARS = 1_000_000
_PDF_TEXT_EXTRACTORS = {"builtin-pdf-text-v1", "pymupdf-text-v1"}
_VIDEO_EXTRACTORS = {
    "builtin-video-transcript-v1",
    "local-command-video-transcript-v1",
}
_FINGERPRINTED_EXTRACTOR = re.compile(
    r"(?P<name>faster-whisper-v1|faster-whisper-audio-v1|pdf-ocr-eval-v1):"
    r"[0-9a-f]{64}\Z"
)


class ValidationError(Exception):
    """Closed validation failure."""


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError
        result[key] = value
    return result


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8", errors="strict")


def _read_descriptor(fd: int, maximum: int = _MAX_FILE_BYTES) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(fd, min(_READ_BYTES, maximum + 1 - total))
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > maximum:
            raise ValidationError
        chunks.append(chunk)


def _read_regular(path: Path) -> bytes:
    before = os.lstat(path)
    if not stat.S_ISREG(before.st_mode):
        raise ValidationError
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        opened = os.fstat(fd)
        if (
            not stat.S_ISREG(opened.st_mode)
            or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
            or opened.st_size < 0
            or opened.st_size > _MAX_FILE_BYTES
        ):
            raise ValidationError
        data = _read_descriptor(fd)
        after = os.fstat(fd)
        if (
            len(data) != opened.st_size
            or (opened.st_dev, opened.st_ino, opened.st_size)
            != (after.st_dev, after.st_ino, after.st_size)
        ):
            raise ValidationError
        return data
    finally:
        os.close(fd)


def _object(value: object, keys: set[str]) -> dict[str, object]:
    if type(value) is not dict:
        raise ValidationError
    normalized = cast(dict[object, object], value)
    if not all(type(key) is str for key in normalized) or set(normalized) != keys:
        raise ValidationError
    return cast(dict[str, object], normalized)


def _text(value: object, pattern: re.Pattern[str] | None = None) -> str:
    if type(value) is not str or not value or "\x00" in value:
        raise ValidationError
    if pattern is not None and pattern.fullmatch(value) is None:
        raise ValidationError
    return value


def _positive_int(value: object, *, allow_zero: bool = False) -> int:
    if type(value) is not int or value < (0 if allow_zero else 1):
        raise ValidationError
    return value


def _display_name(value: object) -> str:
    name = _text(value)
    if len(name) > _DISPLAY_NAME_MAX_CHARS or any(
        character in {"\u2028", "\u2029"}
        or unicodedata.category(character).startswith("C")
        for character in name
    ):
        raise ValidationError
    return name


def _evidence_text(value: object) -> str:
    if type(value) is not str or not value.strip() or len(value) > _EVIDENCE_TEXT_MAX_CHARS:
        raise ValidationError
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ValidationError from exc
    return value


def _source_semantics(
    media_type: object, extractor_fingerprint: object, required_stages: object
) -> str:
    media = _text(media_type)
    extractor = _text(extractor_fingerprint)
    match = _FINGERPRINTED_EXTRACTOR.fullmatch(extractor)
    if media == "application/pdf" and extractor in _PDF_TEXT_EXTRACTORS:
        expected = ["candidate_evidence", "pdf_text_extraction"]
        locator_kind = "page"
    elif media == "application/pdf" and match and match.group("name") == "pdf-ocr-eval-v1":
        expected = ["candidate_evidence", "pdf_ocr_extraction"]
        locator_kind = "page"
    elif media == "video/mp4" and (
        extractor in _VIDEO_EXTRACTORS
        or (match and match.group("name") == "faster-whisper-v1")
    ):
        expected = ["candidate_evidence", "video_transcription"]
        locator_kind = "timestamp_ms"
    elif media in {"audio/mpeg", "audio/wav", "audio/mp4"} and (
        match and match.group("name") == "faster-whisper-audio-v1"
    ):
        expected = ["audio_transcription", "candidate_evidence"]
        locator_kind = "timestamp_ms"
    else:
        raise ValidationError
    if type(required_stages) is not list or required_stages != expected:
        raise ValidationError
    return locator_kind


def _json(data: bytes) -> object:
    try:
        text = data.decode("utf-8", errors="strict")
        value: object = json.loads(
            text,
            object_pairs_hook=_reject_duplicates,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValidationError()),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValidationError from exc
    if _canonical(value) != data:
        raise ValidationError
    return value


def _relative_file(value: object, directory: str, suffix: str, digest: str) -> str:
    path = _text(value)
    pure = PurePosixPath(path)
    if (
        pure.is_absolute()
        or pure.parts != (directory, f"{digest}{suffix}")
        or "\\" in path
    ):
        raise ValidationError
    return path


def _inventory(root: Path) -> set[str]:
    before = os.lstat(root)
    if not stat.S_ISDIR(before.st_mode):
        raise ValidationError
    result: set[str] = set()
    for directory, names, files in os.walk(root, topdown=True, followlinks=False):
        relative = Path(directory).relative_to(root)
        for name in names:
            path = Path(directory) / name
            if not stat.S_ISDIR(os.lstat(path).st_mode):
                raise ValidationError
            entry = (relative / name).as_posix()
            result.add(entry)
        for name in files:
            path = Path(directory) / name
            if not stat.S_ISREG(os.lstat(path).st_mode):
                raise ValidationError
            result.add((relative / name).as_posix())
    after = os.lstat(root)
    if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
        raise ValidationError
    return result


def _validate_locator(value: object) -> dict[str, object]:
    locator = _object(value, _LOCATOR_KEYS)
    kind = locator["kind"]
    start = _positive_int(locator["start"], allow_zero=True)
    end = _positive_int(locator["end"], allow_zero=True)
    if kind == "page":
        if start < 1 or end != start:
            raise ValidationError
    elif kind == "timestamp_ms":
        if end <= start:
            raise ValidationError
    else:
        raise ValidationError
    return locator


def _markdown(entry: Mapping[str, object], rows: Sequence[Mapping[str, object]]) -> bytes:
    frontmatter = (
        "---\n"
        'mke_format: "mke.compiled_markdown.v2"\n'
        f"source_id: {json.dumps(entry['source_id'], ensure_ascii=False)}\n"
        f"display_name: {json.dumps(entry['display_name'], ensure_ascii=False)}\n"
        f"content_fingerprint: {json.dumps(entry['content_fingerprint'])}\n"
        f"media_type: {json.dumps(entry['media_type'])}\n"
        f"publication_id: {json.dumps(entry['publication_id'])}\n"
        f"publication_revision: {entry['publication_revision']}\n"
        f"run_id: {json.dumps(entry['run_id'])}\n"
        f"extractor_fingerprint: {json.dumps(entry['extractor_fingerprint'], ensure_ascii=False)}\n"
        'evidence_schema: "mke.evidence_ref.v1"\n'
        f"evidence_count: {entry['evidence_count']}\n"
        "---\n\n"
        f"# Compiled source `{entry['content_fingerprint']}`\n"
    )
    body = ""
    for row in rows:
        locator = row["locator"]
        assert isinstance(locator, dict)
        if locator["kind"] == "page":
            heading = f"## Page {locator['start']}"
        else:
            heading = f"## Timestamp {locator['start']}-{locator['end']} ms"
        body += (
            f"\n<a id=\"mke-evidence-{row['evidence_id']}\"></a>\n"
            f"{heading}\n\n{row['text']}\n"
        )
    return (frontmatter + body).encode("utf-8", errors="strict")


def validate(export: Path) -> dict[str, object]:
    manifest_data = _read_regular(export / "export-manifest.json")
    manifest = _object(_json(manifest_data), _MANIFEST_KEYS)
    if (
        manifest["schema_version"] != "mke.compiled_library_export.v2"
        or manifest["evidence_schema"] != "mke.evidence_ref.v1"
        or manifest["markdown_format"] != "mke.compiled_markdown.v2"
    ):
        raise ValidationError
    observation = _object(manifest["observation"], _OBSERVATION_KEYS)
    if (
        observation["schema_version"] != "mke.active_publication_observation.v1"
        or observation["state"] != "active"
        or observation["library_id"] != "local"
    ):
        raise ValidationError
    sources_value = manifest["sources"]
    if type(sources_value) is not list:
        raise ValidationError
    sources = cast(list[object], sources_value)
    if not sources:
        raise ValidationError
    expected_inventory = {"sources", "evidence", "export-manifest.json"}
    seen_fingerprints: set[str] = set()
    source_sort_keys: list[tuple[str, str]] = []
    seen_evidence_ids: set[str] = set()
    evidence_total = 0
    for raw_entry in sources:
        entry = _object(raw_entry, _SOURCE_KEYS)
        for key in ("source_id", "publication_id", "run_id"):
            _text(entry[key], _IDENTIFIER[key])
        _display_name(entry["display_name"])
        locator_kind = _source_semantics(
            entry["media_type"], entry["extractor_fingerprint"], entry["required_stages"]
        )
        revision = _positive_int(entry["publication_revision"])
        count = _positive_int(entry["evidence_count"])
        fingerprint = _text(entry["content_fingerprint"])
        if not fingerprint.startswith("sha256:"):
            raise ValidationError
        digest = fingerprint.removeprefix("sha256:")
        if _SHA256.fullmatch(digest) is None:
            raise ValidationError
        if fingerprint in seen_fingerprints:
            raise ValidationError
        seen_fingerprints.add(fingerprint)
        source_sort_keys.append((fingerprint, cast(str, entry["source_id"])))
        evidence_path = _relative_file(entry["evidence_path"], "evidence", ".jsonl", digest)
        markdown_path = _relative_file(entry["markdown_path"], "sources", ".md", digest)
        expected_inventory.update({evidence_path, markdown_path})
        evidence_data = _read_regular(export / evidence_path)
        markdown_data = _read_regular(export / markdown_path)
        if (
            _text(entry["evidence_sha256"], _SHA256)
            != hashlib.sha256(evidence_data).hexdigest()
            or _text(entry["markdown_sha256"], _SHA256)
            != hashlib.sha256(markdown_data).hexdigest()
        ):
            raise ValidationError
        lines = evidence_data.splitlines(keepends=True)
        if len(lines) != count or any(not line.endswith(b"\n") for line in lines):
            raise ValidationError
        rows: list[dict[str, object]] = []
        row_sort_keys: list[tuple[str, int, int, str]] = []
        for line in lines:
            row = _object(_json(line), _EVIDENCE_KEYS)
            locator = _validate_locator(row["locator"])
            if (
                row["schema_version"] != "mke.evidence_ref.v1"
                or row["source_id"] != entry["source_id"]
                or row["content_fingerprint"] != fingerprint
                or row["publication_id"] != entry["publication_id"]
                or row["publication_revision"] != revision
                or row["run_id"] != entry["run_id"]
            ):
                raise ValidationError
            evidence_id = _text(row["evidence_id"], _IDENTIFIER["evidence_id"])
            if evidence_id in seen_evidence_ids or locator["kind"] != locator_kind:
                raise ValidationError
            seen_evidence_ids.add(evidence_id)
            _evidence_text(row["text"])
            row["locator"] = locator
            rows.append(row)
            row_sort_keys.append(
                (
                    cast(str, locator["kind"]),
                    cast(int, locator["start"]),
                    cast(int, locator["end"]),
                    evidence_id,
                )
            )
        if row_sort_keys != sorted(row_sort_keys):
            raise ValidationError
        if markdown_data != _markdown(entry, rows):
            raise ValidationError
        evidence_total += count
    if (
        source_sort_keys != sorted(source_sort_keys)
        or _inventory(export) != expected_inventory
    ):
        raise ValidationError
    source_count = _positive_int(observation["source_count"])
    active_publication_count = _positive_int(observation["active_publication_count"])
    active_evidence_count = _positive_int(observation["active_evidence_count"])
    if (
        source_count < active_publication_count
        or active_publication_count != len(sources)
        or active_evidence_count != evidence_total
    ):
        raise ValidationError
    return {
        "schema_version": "mke.compiled_library_export_consumer.v2",
        "status": "passed",
        "export_schema": "mke.compiled_library_export.v2",
        "markdown_format": "mke.compiled_markdown.v2",
        "evidence_schema": "mke.evidence_ref.v1",
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
