from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterator
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from mke.application import KnowledgeEngine
from mke.application.library_export import (
    RenderedSourceEntry,
    render_compiled_markdown,
    render_evidence_jsonl,
    render_export_manifest,
)
from mke.domain import (
    DEFAULT_EXPORT_LIMITS,
    ActivePublicationObservation,
    CompiledEvidenceSnapshot,
    CompiledLibrarySnapshot,
    CompiledSourceSnapshot,
    LibraryExportDataError,
)
from mke.interfaces.mcp_schemas import (
    ActivePublicationObservationV1,
    EvidenceRefV1,
)
from tests.conftest import PDF_FIXTURES


def _active_state(connection: sqlite3.Connection) -> tuple[tuple[object, ...], ...]:
    return tuple(
        tuple(row)
        for row in connection.execute(
            """
            SELECT sources.source_id, sources.active_publication_id, sources.active_revision,
                   publications.run_id, publications.revision, runs.state,
                   run_manifests.evidence_count, run_manifests.asset_sha256
            FROM sources
            LEFT JOIN publications
              ON publications.publication_id = sources.active_publication_id
            LEFT JOIN runs ON runs.run_id = publications.run_id
            LEFT JOIN run_manifests ON run_manifests.run_id = runs.run_id
            ORDER BY sources.source_id
            """
        ).fetchall()
    )


def test_application_delegates_compiled_snapshot_on_query_only_connection(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mke.sqlite"
    owner = KnowledgeEngine(db_path)
    try:
        owner.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
    finally:
        owner.close()

    engine = KnowledgeEngine.open_read_only_export(db_path)
    connection = engine._store._connection  # pyright: ignore[reportPrivateUsage]
    before = _active_state(connection)
    try:
        snapshot = engine.compiled_library_snapshot()
        assert snapshot.observation.active_publication_count == 1
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        assert _active_state(connection) == before
    finally:
        engine.close()


def test_application_failure_rolls_back_and_preserves_query_only_state(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mke.sqlite"
    owner = KnowledgeEngine(db_path)
    try:
        result = owner.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
        connection = owner._store._connection  # pyright: ignore[reportPrivateUsage]
        connection.execute(
            "UPDATE run_manifests SET evidence_count = evidence_count + 1 WHERE run_id = ?",
            (result.run_id,),
        )
        connection.commit()
    finally:
        owner.close()

    engine = KnowledgeEngine.open_read_only_export(db_path)
    connection = engine._store._connection  # pyright: ignore[reportPrivateUsage]
    before = _active_state(connection)
    statements: list[str] = []
    connection.set_trace_callback(statements.append)
    try:
        with pytest.raises(LibraryExportDataError) as exc_info:
            engine.compiled_library_snapshot()
        assert exc_info.value.reason == "provenance"
        assert any(statement == "ROLLBACK" for statement in statements)
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        assert _active_state(connection) == before
    finally:
        connection.set_trace_callback(None)
        engine.close()


def _compiled_source(*, timestamp: bool = False) -> CompiledSourceSnapshot:
    digit = "b" if timestamp else "a"
    evidence_digit = "5" if timestamp else "1"
    publication_digit = "6" if timestamp else "2"
    run_digit = "7" if timestamp else "3"
    source_digit = "8" if timestamp else "4"
    source_id = f"src_{source_digit * 32}"
    content_fingerprint = f"sha256:{digit * 64}"
    evidence = CompiledEvidenceSnapshot(
        evidence_id=f"ev_{evidence_digit * 32}",
        source_id=source_id,
        content_fingerprint=content_fingerprint,
        publication_id=f"pub_{publication_digit * 32}",
        publication_revision=1,
        run_id=f"run_{run_digit * 32}",
        locator_kind="timestamp_ms" if timestamp else "page",
        locator_start=1000 if timestamp else 1,
        locator_end=2500 if timestamp else 1,
        text="timestamp text" if timestamp else "page text",
    )
    return CompiledSourceSnapshot(
        source_id=source_id,
        display_name="clip.mp4" if timestamp else "page.pdf",
        content_fingerprint=content_fingerprint,
        media_type="video/mp4" if timestamp else "application/pdf",
        publication_id=evidence.publication_id,
        publication_revision=evidence.publication_revision,
        run_id=evidence.run_id,
        extractor_fingerprint=(
            "builtin-video-transcript-v1" if timestamp else "pymupdf-text-v1"
        ),
        required_stages=(
            ("candidate_evidence", "video_transcription")
            if timestamp
            else ("candidate_evidence", "pdf_text_extraction")
        ),
        evidence=(evidence,),
    )


def _compiled_snapshot() -> CompiledLibrarySnapshot:
    return CompiledLibrarySnapshot(
        observation=ActivePublicationObservation(
            library_id="local",
            state="active",
            source_count=2,
            active_publication_count=2,
            active_evidence_count=2,
        ),
        sources=(_compiled_source(), _compiled_source(timestamp=True)),
    )


def _expected_page_jsonl() -> bytes:
    return (
        b'{"content_fingerprint":"sha256:'
        + b"a" * 64
        + b'","evidence_id":"ev_'
        + b"1" * 32
        + b'","locator":{"end":1,"kind":"page","start":1},'
        + b'"publication_id":"pub_'
        + b"2" * 32
        + b'","publication_revision":1,"run_id":"run_'
        + b"3" * 32
        + b'","schema_version":"mke.evidence_ref.v1","source_id":"src_'
        + b"4" * 32
        + b'","text":"page text"}\n'
    )


def _expected_timestamp_jsonl() -> bytes:
    return (
        b'{"content_fingerprint":"sha256:'
        + b"b" * 64
        + b'","evidence_id":"ev_'
        + b"5" * 32
        + b'","locator":{"end":2500,"kind":"timestamp_ms","start":1000},'
        + b'"publication_id":"pub_'
        + b"6" * 32
        + b'","publication_revision":1,"run_id":"run_'
        + b"7" * 32
        + b'","schema_version":"mke.evidence_ref.v1","source_id":"src_'
        + b"8" * 32
        + b'","text":"timestamp text"}\n'
    )


def _expected_page_markdown() -> bytes:
    return (
        b'---\nmke_format: "mke.compiled_markdown.v1"\nsource_id: "src_'
        + b"4" * 32
        + b'"\ndisplay_name: "page.pdf"\ncontent_fingerprint: "sha256:'
        + b"a" * 64
        + b'"\nmedia_type: "application/pdf"\npublication_id: "pub_'
        + b"2" * 32
        + b'"\npublication_revision: 1\nrun_id: "run_'
        + b"3" * 32
        + b'"\nextractor_fingerprint: "pymupdf-text-v1"'
        + b'\nevidence_schema: "mke.evidence_ref.v1"\nevidence_count: 1\n---\n\n'
        + b"# Compiled source `sha256:"
        + b"a" * 64
        + b"`\n\n<a id=\"mke-evidence-ev_"
        + b"1" * 32
        + b'\"></a>\n## Page 1\n\npage text\n'
    )


def _expected_timestamp_markdown() -> bytes:
    return (
        b'---\nmke_format: "mke.compiled_markdown.v1"\nsource_id: "src_'
        + b"8" * 32
        + b'"\ndisplay_name: "clip.mp4"\ncontent_fingerprint: "sha256:'
        + b"b" * 64
        + b'"\nmedia_type: "video/mp4"\npublication_id: "pub_'
        + b"6" * 32
        + b'"\npublication_revision: 1\nrun_id: "run_'
        + b"7" * 32
        + b'"\nextractor_fingerprint: "builtin-video-transcript-v1"'
        + b'\nevidence_schema: "mke.evidence_ref.v1"\nevidence_count: 1\n---\n\n'
        + b"# Compiled source `sha256:"
        + b"b" * 64
        + b"`\n\n<a id=\"mke-evidence-ev_"
        + b"5" * 32
        + b'\"></a>\n## Timestamp 1000-2500 ms\n\ntimestamp text\n'
    )


def _rendered_entry(
    source: CompiledSourceSnapshot, jsonl: bytes, markdown: bytes
) -> RenderedSourceEntry:
    digest = source.content_fingerprint.removeprefix("sha256:")
    return RenderedSourceEntry(
        source_id=source.source_id,
        display_name=source.display_name,
        content_fingerprint=source.content_fingerprint,
        media_type=source.media_type,
        publication_id=source.publication_id,
        publication_revision=source.publication_revision,
        run_id=source.run_id,
        extractor_fingerprint=source.extractor_fingerprint,
        required_stages=source.required_stages,
        evidence_count=len(source.evidence),
        evidence_path=f"evidence/{digest}.jsonl",
        evidence_sha256=sha256(jsonl).hexdigest(),
        markdown_path=f"sources/{digest}.md",
        markdown_sha256=sha256(markdown).hexdigest(),
    )


def test_render_exact_page_and_timestamp_artifact_bytes() -> None:
    page = _compiled_source()
    timestamp = _compiled_source(timestamp=True)

    page_jsonl = render_evidence_jsonl(page)
    timestamp_jsonl = render_evidence_jsonl(timestamp)
    page_markdown = render_compiled_markdown(page)
    timestamp_markdown = render_compiled_markdown(timestamp)

    assert page_jsonl == _expected_page_jsonl()
    assert timestamp_jsonl == _expected_timestamp_jsonl()
    assert page_markdown == _expected_page_markdown()
    assert timestamp_markdown == _expected_timestamp_markdown()
    for rendered in (page_jsonl, timestamp_jsonl, page_markdown, timestamp_markdown):
        assert rendered.endswith(b"\n")
        assert not rendered.endswith(b"\n\n")
        assert b"\r" not in rendered
    for jsonl in (page_jsonl, timestamp_jsonl):
        for line in jsonl.splitlines():
            EvidenceRefV1.model_validate_json(line)
    assert sha256(page_jsonl).hexdigest() == (
        "c9ed655d4ed31a86ecf090a5d1221f50403e1343446125013999cf62ea23939d"
    )
    assert sha256(page_markdown).hexdigest() == (
        "79192ec102e1b611a035dc13d54c5512478622078e27e027aad12e54f1519987"
    )
    assert sha256(timestamp_jsonl).hexdigest() == (
        "6930270f50ab396480b50a6bc181309838530c36eb015c26069b0c092270b662"
    )
    assert sha256(timestamp_markdown).hexdigest() == (
        "9859cf444a9dd4ae748c4a777f554e647f0c3ea50722e0ffda0cb53e2d05492c"
    )


def test_render_manifest_has_exact_fields_and_golden_bytes() -> None:
    snapshot = _compiled_snapshot()
    page_jsonl = _expected_page_jsonl()
    timestamp_jsonl = _expected_timestamp_jsonl()
    page_markdown = _expected_page_markdown()
    timestamp_markdown = _expected_timestamp_markdown()
    entries = (
        _rendered_entry(snapshot.sources[0], page_jsonl, page_markdown),
        _rendered_entry(snapshot.sources[1], timestamp_jsonl, timestamp_markdown),
    )

    manifest = render_export_manifest(snapshot, entries)
    expected = (
        '{"evidence_schema":"mke.evidence_ref.v1",'
        '"markdown_format":"mke.compiled_markdown.v1",'
        '"observation":{"active_evidence_count":2,"active_publication_count":2,'
        '"library_id":"local","schema_version":'
        '"mke.active_publication_observation.v1","source_count":2,'
        '"state":"active"},"schema_version":"mke.compiled_library_export.v1",'
        '"sources":['
        + _expected_manifest_source(entries[0])
        + ","
        + _expected_manifest_source(entries[1])
        + "]}\n"
    ).encode()
    assert manifest == expected
    assert manifest.endswith(b"\n") and not manifest.endswith(b"\n\n")
    assert b"\r" not in manifest
    payload = json.loads(manifest)
    assert set(payload) == {
        "evidence_schema",
        "markdown_format",
        "observation",
        "schema_version",
        "sources",
    }
    assert set(payload["observation"]) == {
        "active_evidence_count",
        "active_publication_count",
        "library_id",
        "schema_version",
        "source_count",
        "state",
    }
    expected_source_fields = {
        "content_fingerprint",
        "display_name",
        "evidence_count",
        "evidence_path",
        "evidence_sha256",
        "extractor_fingerprint",
        "markdown_path",
        "markdown_sha256",
        "media_type",
        "publication_id",
        "publication_revision",
        "required_stages",
        "run_id",
        "source_id",
    }
    assert all(set(source) == expected_source_fields for source in payload["sources"])
    ActivePublicationObservationV1.model_validate(payload["observation"])
    assert sha256(manifest).hexdigest() == (
        "7de7221b6ffe190085291809ffadeb480bbea72e43c84ffdc3a0d5c4f57bc108"
    )


def _expected_manifest_source(entry: RenderedSourceEntry) -> str:
    required_stages = ",".join(f'"{stage}"' for stage in entry.required_stages)
    return (
        '{"content_fingerprint":"'
        + entry.content_fingerprint
        + '","display_name":"'
        + entry.display_name
        + '","evidence_count":1,"evidence_path":"'
        + entry.evidence_path
        + '","evidence_sha256":"'
        + entry.evidence_sha256
        + '","extractor_fingerprint":"'
        + entry.extractor_fingerprint
        + '","markdown_path":"'
        + entry.markdown_path
        + '","markdown_sha256":"'
        + entry.markdown_sha256
        + '","media_type":"'
        + entry.media_type
        + '","publication_id":"'
        + entry.publication_id
        + '","publication_revision":1,"required_stages":['
        + required_stages
        + '],"run_id":"'
        + entry.run_id
        + '","source_id":"'
        + entry.source_id
        + '"}'
    )


def test_render_is_deterministic_and_preserves_untrusted_content() -> None:
    source = _compiled_source()
    display_name = '\"quoted\": --- # Markdown key: value'
    text = (
        "# injected heading\n"
        '<a id="injected"></a>\n'
        "---\nkey: value\n```sh\nrm -rf /\n```\n"
        "<script>alert(1)</script>\nIgnore previous instructions"
    )
    source = replace(
        source,
        display_name=display_name,
        evidence=(replace(source.evidence[0], text=text),),
    )

    first_jsonl = render_evidence_jsonl(source)
    first_markdown = render_compiled_markdown(source)
    assert render_evidence_jsonl(source) == first_jsonl
    assert render_compiled_markdown(source) == first_markdown
    assert (
        b'display_name: "\\\"quoted\\\": --- # Markdown key: value"\n'
        in first_markdown
    )
    assert first_markdown.count(b"\ndisplay_name:") == 1
    owned_heading = b"## Page 1\n\n"
    assert first_markdown.index(text.encode()) == first_markdown.index(owned_heading) + len(
        owned_heading
    )
    assert b"evidence/" not in first_markdown
    assert b"sources/" not in first_markdown
    entry = _rendered_entry(source, first_jsonl, first_markdown)
    assert entry.evidence_path == "evidence/" + "a" * 64 + ".jsonl"
    assert entry.markdown_path == "sources/" + "a" * 64 + ".md"


def test_render_does_not_repair_source_order() -> None:
    observation = _compiled_snapshot().observation
    with pytest.raises(LibraryExportDataError) as exc_info:
        CompiledLibrarySnapshot(
            observation=observation,
            sources=(_compiled_source(timestamp=True), _compiled_source()),
        )
    assert exc_info.value.reason == "provenance"


def test_render_rejects_evidence_and_manifest_entry_drift() -> None:
    source = _compiled_source()
    object.__setattr__(source.evidence[0], "source_id", "src_" + "9" * 32)
    with pytest.raises(LibraryExportDataError) as evidence_error:
        render_evidence_jsonl(source)
    assert evidence_error.value.reason == "provenance"

    snapshot = _compiled_snapshot()
    entries = tuple(
        _rendered_entry(
            item,
            render_evidence_jsonl(item),
            render_compiled_markdown(item),
        )
        for item in snapshot.sources
    )
    drifted = (replace(entries[0], display_name="drifted.pdf"), entries[1])
    with pytest.raises(LibraryExportDataError) as entry_error:
        render_export_manifest(snapshot, drifted)
    assert entry_error.value.reason == "provenance"


@pytest.mark.parametrize("renderer", [render_evidence_jsonl, render_compiled_markdown])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_id", "ev_invalid"),
        ("locator_end", 2),
        ("publication_revision", True),
        ("text", "x" * 1_000_001),
        ("text", "\ud800"),
    ],
    ids=[
        "invalid-evidence-id",
        "locator-drift",
        "bool-revision",
        "overlong-text",
        "invalid-utf8",
    ],
)
def test_render_recursively_revalidates_each_evidence_field(
    renderer: Callable[[CompiledSourceSnapshot], bytes],
    field: str,
    value: object,
) -> None:
    source = _compiled_source()
    object.__setattr__(source.evidence[0], field, value)

    with pytest.raises(LibraryExportDataError) as exc_info:
        renderer(source)
    assert exc_info.value.reason == "provenance"


@pytest.mark.parametrize("field", ["publication_revision", "evidence_count"])
def test_render_manifest_rejects_bool_entry_integers(field: str) -> None:
    snapshot = _compiled_snapshot()
    entries = tuple(
        _rendered_entry(
            source,
            render_evidence_jsonl(source),
            render_compiled_markdown(source),
        )
        for source in snapshot.sources
    )
    drifted = (replace(entries[0], **{field: True}), entries[1])

    with pytest.raises(LibraryExportDataError) as exc_info:
        render_export_manifest(snapshot, drifted)
    assert exc_info.value.reason == "provenance"


@pytest.mark.parametrize(
    ("field", "value"),
    [("evidence_sha256", b"0" * 64), ("markdown_sha256", 1)],
)
def test_render_manifest_normalizes_non_string_digest_drift(
    field: str, value: object
) -> None:
    snapshot = _compiled_snapshot()
    entries = tuple(
        _rendered_entry(
            source,
            render_evidence_jsonl(source),
            render_compiled_markdown(source),
        )
        for source in snapshot.sources
    )
    drifted = (replace(entries[0], **{field: value}), entries[1])

    with pytest.raises(LibraryExportDataError) as exc_info:
        render_export_manifest(snapshot, drifted)
    assert exc_info.value.reason == "provenance"


def test_render_manifest_recursively_revalidates_synchronized_source_entry_drift(
) -> None:
    snapshot = _compiled_snapshot()
    entries = tuple(
        _rendered_entry(
            source,
            render_evidence_jsonl(source),
            render_compiled_markdown(source),
        )
        for source in snapshot.sources
    )
    source = snapshot.sources[0]
    object.__setattr__(source, "publication_revision", True)
    object.__setattr__(source.evidence[0], "publication_revision", True)
    drifted = (replace(entries[0], publication_revision=True), entries[1])

    with pytest.raises(LibraryExportDataError) as exc_info:
        render_export_manifest(snapshot, drifted)
    assert exc_info.value.reason == "provenance"


class _FailOnSecondEvidence(tuple[CompiledEvidenceSnapshot, ...]):
    def __iter__(self) -> Iterator[CompiledEvidenceSnapshot]:
        yield self[0]
        raise AssertionError("renderer consumed Evidence after crossing byte limit")


@pytest.mark.parametrize("renderer", [render_evidence_jsonl, render_compiled_markdown])
def test_render_stops_consuming_parts_immediately_after_crossing_limit(
    monkeypatch: pytest.MonkeyPatch,
    renderer: Callable[[CompiledSourceSnapshot], bytes],
) -> None:
    from mke.application import library_export

    source = _compiled_source()
    evidence = source.evidence[0]
    guarded = _FailOnSecondEvidence((evidence, evidence))
    object.__setattr__(source, "evidence", guarded)

    def skip_validation(_source: CompiledSourceSnapshot) -> None:
        return None

    monkeypatch.setattr(library_export, "_validate_source", skip_validation)
    monkeypatch.setattr(library_export, "_MAX_RENDERED_FILE_BYTES", 1)

    with pytest.raises(LibraryExportDataError) as exc_info:
        renderer(source)
    assert exc_info.value.reason == "too_large"


@pytest.mark.parametrize("renderer", [render_evidence_jsonl, render_compiled_markdown])
def test_render_accepts_exact_file_limit_and_rejects_one_byte_above(
    monkeypatch: pytest.MonkeyPatch,
    renderer: Callable[[CompiledSourceSnapshot], bytes],
) -> None:
    from mke.application import library_export

    source = _compiled_source()
    rendered = renderer(source)
    monkeypatch.setattr(library_export, "_MAX_RENDERED_FILE_BYTES", len(rendered))
    assert renderer(source) == rendered
    monkeypatch.setattr(library_export, "_MAX_RENDERED_FILE_BYTES", len(rendered) - 1)
    with pytest.raises(LibraryExportDataError) as exc_info:
        renderer(source)
    assert exc_info.value.reason == "too_large"


def test_render_production_file_limit_is_64_mib() -> None:
    from mke.application import library_export

    assert DEFAULT_EXPORT_LIMITS.max_rendered_file_bytes == 64 * 1024 * 1024
    assert (
        library_export._MAX_RENDERED_FILE_BYTES  # pyright: ignore[reportPrivateUsage]
        == DEFAULT_EXPORT_LIMITS.max_rendered_file_bytes
    )
