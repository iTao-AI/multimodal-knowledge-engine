"""Canonical renderers for a compiled local Library snapshot."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass

from mke.domain import (
    DEFAULT_EXPORT_LIMITS,
    CompiledEvidenceSnapshot,
    CompiledLibrarySnapshot,
    CompiledSourceSnapshot,
    LibraryExportDataError,
)

_MAX_RENDERED_FILE_BYTES = DEFAULT_EXPORT_LIMITS.max_rendered_file_bytes
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


def canonical_json_line(value: Mapping[str, object]) -> bytes:
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


@dataclass(frozen=True)
class RenderedSourceEntry:
    source_id: str
    display_name: str
    content_fingerprint: str
    media_type: str
    publication_id: str
    publication_revision: int
    run_id: str
    extractor_fingerprint: str
    required_stages: tuple[str, ...]
    evidence_count: int
    evidence_path: str
    evidence_sha256: str
    markdown_path: str
    markdown_sha256: str


@dataclass(frozen=True)
class LibraryExportResult:
    library_id: str
    source_count: int
    evidence_count: int
    manifest_sha256: str


def _validate_source(source: CompiledSourceSnapshot) -> None:
    if type(source) is not CompiledSourceSnapshot:
        raise LibraryExportDataError("provenance")
    for item in source.evidence:
        if type(item) is not CompiledEvidenceSnapshot:
            raise LibraryExportDataError("provenance")
        item.__post_init__()
    source.__post_init__()


def _evidence_payload(item: CompiledEvidenceSnapshot) -> dict[str, object]:
    return {
        "schema_version": "mke.evidence_ref.v1",
        "evidence_id": item.evidence_id,
        "source_id": item.source_id,
        "content_fingerprint": item.content_fingerprint,
        "publication_id": item.publication_id,
        "publication_revision": item.publication_revision,
        "run_id": item.run_id,
        "locator": {
            "kind": item.locator_kind,
            "start": item.locator_start,
            "end": item.locator_end,
        },
        "text": item.text,
    }


def _bounded_render(parts: Iterable[bytes]) -> bytes:
    rendered = bytearray()
    for part in parts:
        if len(part) > _MAX_RENDERED_FILE_BYTES - len(rendered):
            raise LibraryExportDataError("too_large")
        rendered.extend(part)
    return bytes(rendered)


def render_evidence_jsonl(source: CompiledSourceSnapshot) -> bytes:
    """Render one Source's active Evidence as canonical JSONL."""

    _validate_source(source)
    return _bounded_render(
        canonical_json_line(_evidence_payload(item)) for item in source.evidence
    )


def _json_scalar(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_compiled_markdown(source: CompiledSourceSnapshot) -> bytes:
    """Render one Source as deterministic provenance-preserving Markdown."""

    _validate_source(source)
    frontmatter = (
        "---\n"
        f"mke_format: {_json_scalar('mke.compiled_markdown.v1')}\n"
        f"source_id: {_json_scalar(source.source_id)}\n"
        f"display_name: {_json_scalar(source.display_name)}\n"
        f"content_fingerprint: {_json_scalar(source.content_fingerprint)}\n"
        f"media_type: {_json_scalar(source.media_type)}\n"
        f"publication_id: {_json_scalar(source.publication_id)}\n"
        f"publication_revision: {source.publication_revision}\n"
        f"run_id: {_json_scalar(source.run_id)}\n"
        f"extractor_fingerprint: {_json_scalar(source.extractor_fingerprint)}\n"
        f"evidence_schema: {_json_scalar('mke.evidence_ref.v1')}\n"
        f"evidence_count: {len(source.evidence)}\n"
        "---\n\n"
        f"# Compiled source `{source.content_fingerprint}`\n"
    ).encode("utf-8", errors="strict")

    def parts() -> Iterator[bytes]:
        yield frontmatter
        for item in source.evidence:
            if item.locator_kind == "page":
                heading = f"## Page {item.locator_start}"
            else:
                heading = f"## Timestamp {item.locator_start}-{item.locator_end} ms"
            yield (
                f'\n<a id="mke-evidence-{item.evidence_id}"></a>\n'
                f"{heading}\n\n"
            ).encode("utf-8", errors="strict")
            yield item.text.encode("utf-8", errors="strict")
            yield b"\n"

    return _bounded_render(parts())


def _validate_entry(
    source: CompiledSourceSnapshot, entry: RenderedSourceEntry
) -> None:
    digest = source.content_fingerprint.removeprefix("sha256:")
    expected = (
        source.source_id,
        source.display_name,
        source.content_fingerprint,
        source.media_type,
        source.publication_id,
        source.publication_revision,
        source.run_id,
        source.extractor_fingerprint,
        source.required_stages,
        len(source.evidence),
        f"evidence/{digest}.jsonl",
        f"sources/{digest}.md",
    )
    actual = (
        entry.source_id,
        entry.display_name,
        entry.content_fingerprint,
        entry.media_type,
        entry.publication_id,
        entry.publication_revision,
        entry.run_id,
        entry.extractor_fingerprint,
        entry.required_stages,
        entry.evidence_count,
        entry.evidence_path,
        entry.markdown_path,
    )
    if (
        type(entry.publication_revision) is not int
        or type(entry.evidence_count) is not int
        or actual != expected
        or type(entry.evidence_sha256) is not str
        or type(entry.markdown_sha256) is not str
        or _SHA256_RE.fullmatch(entry.evidence_sha256) is None
        or _SHA256_RE.fullmatch(entry.markdown_sha256) is None
    ):
        raise LibraryExportDataError("provenance")


def _entry_payload(entry: RenderedSourceEntry) -> dict[str, object]:
    return {
        "source_id": entry.source_id,
        "display_name": entry.display_name,
        "content_fingerprint": entry.content_fingerprint,
        "media_type": entry.media_type,
        "publication_id": entry.publication_id,
        "publication_revision": entry.publication_revision,
        "run_id": entry.run_id,
        "extractor_fingerprint": entry.extractor_fingerprint,
        "required_stages": list(entry.required_stages),
        "evidence_count": entry.evidence_count,
        "evidence_path": entry.evidence_path,
        "evidence_sha256": entry.evidence_sha256,
        "markdown_path": entry.markdown_path,
        "markdown_sha256": entry.markdown_sha256,
    }


def render_export_manifest(
    snapshot: CompiledLibrarySnapshot,
    entries: Sequence[RenderedSourceEntry],
) -> bytes:
    """Render the closed canonical manifest for a validated snapshot."""

    if type(snapshot) is not CompiledLibrarySnapshot:
        raise LibraryExportDataError("provenance")
    snapshot.__post_init__()
    if len(entries) != len(snapshot.sources) or any(
        type(entry) is not RenderedSourceEntry for entry in entries
    ):
        raise LibraryExportDataError("provenance")
    for source, entry in zip(snapshot.sources, entries, strict=True):
        _validate_source(source)
        _validate_entry(source, entry)
    observation = snapshot.observation
    return canonical_json_line(
        {
            "schema_version": "mke.compiled_library_export.v1",
            "evidence_schema": "mke.evidence_ref.v1",
            "markdown_format": "mke.compiled_markdown.v1",
            "observation": {
                "schema_version": "mke.active_publication_observation.v1",
                "library_id": observation.library_id,
                "state": observation.state,
                "source_count": observation.source_count,
                "active_publication_count": observation.active_publication_count,
                "active_evidence_count": observation.active_evidence_count,
            },
            "sources": [_entry_payload(entry) for entry in entries],
        }
    )
