# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/compiled_library_export_consumer.py"


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def _render_markdown(
    entry: dict[str, object], rows: list[dict[str, object]]
) -> bytes:
    frontmatter = (
        "---\n"
        'mke_format: "mke.compiled_markdown.v1"\n'
        f'source_id: {json.dumps(entry["source_id"], ensure_ascii=False)}\n'
        f'display_name: {json.dumps(entry["display_name"], ensure_ascii=False)}\n'
        f'content_fingerprint: {json.dumps(entry["content_fingerprint"], ensure_ascii=False)}\n'
        f'media_type: {json.dumps(entry["media_type"], ensure_ascii=False)}\n'
        f'publication_id: {json.dumps(entry["publication_id"], ensure_ascii=False)}\n'
        f'publication_revision: {entry["publication_revision"]}\n'
        f'run_id: {json.dumps(entry["run_id"], ensure_ascii=False)}\n'
        f'extractor_fingerprint: {json.dumps(entry["extractor_fingerprint"], ensure_ascii=False)}\n'
        'evidence_schema: "mke.evidence_ref.v1"\n'
        f'evidence_count: {entry["evidence_count"]}\n'
        "---\n\n"
        f'# Compiled source `{entry["content_fingerprint"]}`\n'
    )
    body = ""
    for item in rows:
        locator = item["locator"]
        assert isinstance(locator, dict)
        if locator["kind"] == "page":
            heading = f"## Page {locator['start']}"
        else:
            heading = f"## Timestamp {locator['start']}-{locator['end']} ms"
        body += (
            f"\n<a id=\"mke-evidence-{item['evidence_id']}\"></a>\n"
            f"{heading}\n\n{item['text']}\n"
        )
    return (frontmatter + body).encode()


def _source(
    root: Path,
    key: str,
    suffix: str,
    evidence: list[dict[str, object]],
) -> tuple[Path, dict[str, object]]:
    source = root / f"{key}.{suffix}"
    source.write_bytes(f"independent source bytes: {key}\n".encode())
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    fingerprint = f"sha256:{digest}"
    source_id = f"src_{digest[:32]}"
    publication_id = f"pub_{digest[:32]}"
    run_id = f"run_{digest[:32]}"
    normalized: list[dict[str, object]] = []
    for index, item in enumerate(evidence):
        normalized.append(
            {
                "schema_version": "mke.evidence_ref.v1",
                "evidence_id": f"ev_{digest[index:index + 32]}",
                "source_id": source_id,
                "content_fingerprint": fingerprint,
                "publication_id": publication_id,
                "publication_revision": 1,
                "run_id": run_id,
                "locator": item["locator"],
                "text": item["text"],
            }
        )
    evidence_bytes = b"".join(_canonical(item) for item in normalized)
    evidence_path = root / "export/evidence" / f"{digest}.jsonl"
    evidence_path.write_bytes(evidence_bytes)
    media_type = "application/pdf" if suffix == "pdf" else "video/mp4"
    extractor = "pymupdf-text-v1" if suffix == "pdf" else "builtin-video-transcript-v1"
    stages = (
        ["candidate_evidence", "pdf_text_extraction"]
        if suffix == "pdf"
        else ["candidate_evidence", "video_transcription"]
    )
    entry: dict[str, object] = {
        "source_id": source_id,
        "display_name": source.name,
        "content_fingerprint": fingerprint,
        "media_type": media_type,
        "publication_id": publication_id,
        "publication_revision": 1,
        "run_id": run_id,
        "extractor_fingerprint": extractor,
        "required_stages": stages,
        "evidence_count": len(normalized),
        "evidence_path": f"evidence/{digest}.jsonl",
        "evidence_sha256": hashlib.sha256(evidence_bytes).hexdigest(),
        "markdown_path": f"sources/{digest}.md",
    }
    markdown_bytes = _render_markdown(entry, normalized)
    markdown_path = root / "export/sources" / f"{digest}.md"
    markdown_path.write_bytes(markdown_bytes)
    entry["markdown_sha256"] = hashlib.sha256(markdown_bytes).hexdigest()
    return source, entry


def _tree(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    (tmp_path / "export/evidence").mkdir(parents=True)
    (tmp_path / "export/sources").mkdir()
    pdf, pdf_entry = _source(
        tmp_path,
        "operations-guide",
        "pdf",
        [
            {"locator": {"kind": "page", "start": 1, "end": 1}, "text": "Page one."},
            {"locator": {"kind": "page", "start": 2, "end": 2}, "text": "Page two."},
        ],
    )
    video, video_entry = _source(
        tmp_path,
        "spoken-evidence",
        "mp4",
        [
            {
                "locator": {"kind": "timestamp_ms", "start": 0, "end": 1200},
                "text": "Timestamp evidence.",
            }
        ],
    )
    manifest = {
        "schema_version": "mke.compiled_library_export.v1",
        "evidence_schema": "mke.evidence_ref.v1",
        "markdown_format": "mke.compiled_markdown.v1",
        "observation": {
            "schema_version": "mke.active_publication_observation.v1",
            "library_id": "local",
            "state": "active",
            "source_count": 2,
            "active_publication_count": 2,
            "active_evidence_count": 3,
        },
        "sources": sorted(
            [pdf_entry, video_entry],
            key=lambda entry: (entry["content_fingerprint"], entry["source_id"]),
        ),
    }
    (tmp_path / "export/export-manifest.json").write_bytes(_canonical(manifest))
    return tmp_path / "export", {"operations-guide": pdf, "spoken-evidence": video}


def _run(export: Path, sources: dict[str, Path]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--export",
            str(export),
            "--source",
            f"operations-guide={sources['operations-guide']}",
            "--source",
            f"spoken-evidence={sources['spoken-evidence']}",
            "--json",
        ],
        cwd=export.parent,
        text=True,
        capture_output=True,
        check=False,
    )


def _manifest(export: Path) -> dict[str, object]:
    return json.loads((export / "export-manifest.json").read_text())


def _write_manifest(export: Path, manifest: dict[str, object]) -> None:
    (export / "export-manifest.json").write_bytes(_canonical(manifest))


def _entry_for_media(manifest: dict[str, object], media_type: str) -> dict[str, object]:
    sources = manifest["sources"]
    assert isinstance(sources, list)
    return next(entry for entry in sources if entry["media_type"] == media_type)


def _rewrite_entry_markdown(export: Path, entry: dict[str, object]) -> None:
    evidence_path = export / str(entry["evidence_path"])
    rows = [json.loads(line) for line in evidence_path.read_text().splitlines()]
    markdown = _render_markdown(entry, rows)
    (export / str(entry["markdown_path"])).write_bytes(markdown)
    entry["markdown_sha256"] = hashlib.sha256(markdown).hexdigest()


def _rewrite_evidence(
    export: Path,
    entry: dict[str, object],
    mutate: Callable[[list[dict[str, object]]], None],
) -> None:
    path = export / str(entry["evidence_path"])
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    mutate(rows)
    evidence = b"".join(_canonical(row) for row in rows)
    path.write_bytes(evidence)
    entry["evidence_sha256"] = hashlib.sha256(evidence).hexdigest()
    entry["evidence_count"] = len(rows)
    _rewrite_entry_markdown(export, entry)


def _real_cli_tree(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    pdf = tmp_path / "operations-guide.pdf"
    video = tmp_path / "spoken-evidence.mp4"
    sidecar = tmp_path / "spoken-evidence.mp4.mke-transcript.json"
    shutil.copyfile(ROOT / "tests/fixtures/local-knowledge-v1/operations-guide.pdf", pdf)
    shutil.copyfile(ROOT / "tests/fixtures/video/spoken-evidence.mp4", video)
    shutil.copyfile(ROOT / "tests/fixtures/video/short-audio.mp4.mke-transcript.json", sidecar)
    database = tmp_path / "library.sqlite"
    mke = Path(sys.executable).with_name("mke")
    env = dict(os.environ, UV_OFFLINE="1")
    for source in (pdf, video):
        result = subprocess.run(
            [str(mke), "--db", str(database), "ingest", str(source), "--json"],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
    result = subprocess.run(
        [str(mke), "--db", str(database), "library", "export", "--output", "export", "--json"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return tmp_path / "export", {"operations-guide": pdf, "spoken-evidence": video}


def _assert_closed_failure(result: subprocess.CompletedProcess[str], tmp_path: Path) -> None:
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert set(payload) == {"status", "code"}
    assert payload["status"] == "failed"
    assert payload["code"] in {"export_invalid", "source_invalid", "cleanup_failed"}
    assert result.stderr == ""
    assert str(tmp_path) not in result.stdout
    assert "Traceback" not in result.stdout


def test_consumer_accepts_exact_portable_export(tmp_path: Path) -> None:
    export, sources = _tree(tmp_path)
    result = _run(export, sources)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "schema_version": "mke.compiled_library_export_consumer.v1",
        "evidence_count": 3,
        "evidence_schema": "mke.evidence_ref.v1",
        "export_schema": "mke.compiled_library_export.v1",
        "fingerprint_mapping": "exact",
        "markdown_format": "mke.compiled_markdown.v1",
        "portable_copy": True,
        "source_count": 2,
        "status": "passed",
    }
    assert result.stderr == ""


def test_consumer_accepts_total_source_count_with_inactive_source(tmp_path: Path) -> None:
    export, sources = _tree(tmp_path)
    manifest = _manifest(export)
    observation = manifest["observation"]
    assert isinstance(observation, dict)
    observation["source_count"] = 3
    _write_manifest(export, manifest)
    result = _run(export, sources)
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize("source_count", [1, True])
def test_consumer_rejects_total_source_count_below_active_or_bool(
    tmp_path: Path, source_count: object
) -> None:
    export, sources = _tree(tmp_path)
    manifest = _manifest(export)
    observation = manifest["observation"]
    assert isinstance(observation, dict)
    observation["source_count"] = source_count
    _write_manifest(export, manifest)
    _assert_closed_failure(_run(export, sources), tmp_path)


@pytest.mark.parametrize(
    "mutation",
    ["not-local", "blank-text", "text-plain", "unsorted-stages"],
)
def test_consumer_rejects_reviewer_real_cli_mutations(
    tmp_path: Path, mutation: str
) -> None:
    export, sources = _real_cli_tree(tmp_path)
    manifest = _manifest(export)
    pdf_entry = _entry_for_media(manifest, "application/pdf")
    if mutation == "not-local":
        observation = manifest["observation"]
        assert isinstance(observation, dict)
        observation["library_id"] = "not-local"
    elif mutation == "blank-text":
        _rewrite_evidence(
            export,
            pdf_entry,
            lambda rows: rows[0].__setitem__("text", " \t\n"),
        )
    elif mutation == "text-plain":
        pdf_entry["media_type"] = "text/plain"
        _rewrite_entry_markdown(export, pdf_entry)
    else:
        stages = pdf_entry["required_stages"]
        assert isinstance(stages, list)
        pdf_entry["required_stages"] = list(reversed(stages))
    _write_manifest(export, manifest)
    _assert_closed_failure(_run(export, sources), tmp_path)


def test_consumer_rejects_unsorted_source_and_evidence_snapshots(tmp_path: Path) -> None:
    export, sources = _tree(tmp_path / "sources")
    manifest = _manifest(export)
    entries = manifest["sources"]
    assert isinstance(entries, list)
    entries.reverse()
    _write_manifest(export, manifest)
    _assert_closed_failure(_run(export, sources), tmp_path)

    export, sources = _tree(tmp_path / "evidence")
    manifest = _manifest(export)
    pdf_entry = _entry_for_media(manifest, "application/pdf")
    _rewrite_evidence(export, pdf_entry, lambda rows: rows.reverse())
    _write_manifest(export, manifest)
    _assert_closed_failure(_run(export, sources), tmp_path)


@pytest.mark.parametrize(
    "display_name",
    ["", "x" * 1025, "line\nbreak", "delete\x7f", "line\u2028break", "para\u2029break"],
)
def test_consumer_rejects_display_name_domain_bounds(
    tmp_path: Path, display_name: str
) -> None:
    export, sources = _tree(tmp_path)
    manifest = _manifest(export)
    entry = _entry_for_media(manifest, "application/pdf")
    entry["display_name"] = display_name
    _rewrite_entry_markdown(export, entry)
    _write_manifest(export, manifest)
    _assert_closed_failure(_run(export, sources), tmp_path)


@pytest.mark.parametrize("text", ["", " \t\n", "x" * 1_000_001])
def test_consumer_rejects_evidence_text_domain_bounds(tmp_path: Path, text: str) -> None:
    export, sources = _tree(tmp_path)
    manifest = _manifest(export)
    entry = _entry_for_media(manifest, "application/pdf")
    _rewrite_evidence(
        export,
        entry,
        lambda rows: rows[0].__setitem__("text", text),
    )
    _write_manifest(export, manifest)
    _assert_closed_failure(_run(export, sources), tmp_path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("extractor_fingerprint", "builtin-video-transcript-v1"),
        ("required_stages", []),
        ("required_stages", ["candidate_evidence"]),
        (
            "required_stages",
            ["candidate_evidence", "pdf_text_extraction", "pdf_text_extraction"],
        ),
        ("publication_revision", True),
    ],
)
def test_consumer_rejects_source_semantic_and_typed_scalar_drift(
    tmp_path: Path, field: str, value: object
) -> None:
    export, sources = _tree(tmp_path)
    manifest = _manifest(export)
    entry = _entry_for_media(manifest, "application/pdf")
    entry[field] = value
    _rewrite_entry_markdown(export, entry)
    _write_manifest(export, manifest)
    _assert_closed_failure(_run(export, sources), tmp_path)


def test_consumer_accepts_exact_display_and_text_upper_bounds(tmp_path: Path) -> None:
    export, sources = _tree(tmp_path)
    manifest = _manifest(export)
    entry = _entry_for_media(manifest, "application/pdf")
    entry["display_name"] = "x" * 1024
    _rewrite_evidence(
        export,
        entry,
        lambda rows: rows[0].__setitem__("text", "x" * 1_000_000),
    )
    _write_manifest(export, manifest)
    result = _run(export, sources)
    assert result.returncode == 0, result.stdout


def test_consumer_is_stdlib_only_and_has_no_product_or_query_authority() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "import mke" not in source
    assert "from mke" not in source
    assert "sqlite" not in source.lower()
    assert "search" not in source.lower()
    assert "ask" not in source.lower()
    assert "os.open(" in source
    assert "os.lstat(" in source or "follow_symlinks=False" in source
    assert "os.fstat(" in source


def _extra_manifest_field(export: Path) -> None:
    value = _manifest(export)
    value["extra"] = True
    _write_manifest(export, value)


def _missing_source_field(export: Path) -> None:
    value = _manifest(export)
    del value["sources"][0]["run_id"]  # type: ignore[index]
    _write_manifest(export, value)


def _unknown_version(export: Path) -> None:
    value = _manifest(export)
    value["schema_version"] = "mke.compiled_library_export.v2"
    _write_manifest(export, value)


def _noncanonical_manifest(export: Path) -> None:
    value = _manifest(export)
    (export / "export-manifest.json").write_text(json.dumps(value, indent=2) + "\n")


def _digest_drift(export: Path) -> None:
    value = _manifest(export)
    value["sources"][0]["evidence_sha256"] = "f" * 64  # type: ignore[index]
    _write_manifest(export, value)


def _truncated_content(export: Path) -> None:
    value = _manifest(export)
    path = export / value["sources"][0]["markdown_path"]  # type: ignore[index,operator]
    path.write_bytes(path.read_bytes()[:-1])


def _unexpected_file(export: Path) -> None:
    (export / "unexpected.txt").write_text("unexpected")


def _nested_file(export: Path) -> None:
    (export / "sources/nested").mkdir()
    (export / "sources/nested/file").write_text("unexpected")


def _missing_manifest(export: Path) -> None:
    (export / "export-manifest.json").unlink()


def _fake_manifest(export: Path) -> None:
    (export / "export-manifest.json").unlink()
    (export / "export-manifest.json").mkdir()


def _markdown_disagreement(export: Path) -> None:
    value = _manifest(export)
    entry = value["sources"][0]  # type: ignore[index]
    path = export / entry["markdown_path"]  # type: ignore[index]
    data = path.read_bytes().replace(b"Page one.", b"Page drift")
    path.write_bytes(data)
    entry["markdown_sha256"] = hashlib.sha256(data).hexdigest()  # type: ignore[index]
    _write_manifest(export, value)


@pytest.mark.parametrize(
    "mutate",
    [
        _extra_manifest_field,
        _missing_source_field,
        _unknown_version,
        _noncanonical_manifest,
        _digest_drift,
        _truncated_content,
        _unexpected_file,
        _nested_file,
        _missing_manifest,
        _fake_manifest,
        _markdown_disagreement,
    ],
)
def test_consumer_rejects_export_schema_inventory_and_content_drift(
    tmp_path: Path, mutate: Callable[[Path], None]
) -> None:
    export, sources = _tree(tmp_path)
    mutate(export)
    _assert_closed_failure(_run(export, sources), tmp_path)


def test_consumer_rejects_symlink_inventory(tmp_path: Path) -> None:
    export, sources = _tree(tmp_path)
    os.symlink(export / "export-manifest.json", export / "unexpected-link")
    _assert_closed_failure(_run(export, sources), tmp_path)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("schema_version", "mke.evidence_ref.v2"),
        ("evidence_id", "ev_" + "F" * 32),
        ("source_id", "src_" + "f" * 32),
        ("content_fingerprint", "sha256:" + "f" * 64),
        ("publication_id", "pub_" + "f" * 32),
        ("publication_revision", 2),
        ("run_id", "run_" + "f" * 32),
        ("locator", {"kind": "page", "start": 1, "end": 2}),
        ("text", " \t\n"),
    ],
)
def test_consumer_rejects_every_evidence_identity_locator_and_text_drift(
    tmp_path: Path, field: str, replacement: object
) -> None:
    export, sources = _tree(tmp_path)
    manifest = _manifest(export)
    entry = _entry_for_media(manifest, "application/pdf")
    _rewrite_evidence(
        export,
        entry,
        lambda rows: rows[0].__setitem__(field, replacement),
    )
    _write_manifest(export, manifest)
    _assert_closed_failure(_run(export, sources), tmp_path)


def test_consumer_rejects_noncanonical_jsonl_and_source_mapping(tmp_path: Path) -> None:
    export, sources = _tree(tmp_path)
    manifest = _manifest(export)
    entry = manifest["sources"][0]  # type: ignore[index]
    path = export / entry["evidence_path"]  # type: ignore[index]
    row = json.loads(path.read_text().splitlines()[0])
    data = (json.dumps(row, indent=2) + "\n").encode()
    path.write_bytes(data)
    entry["evidence_count"] = 1  # type: ignore[index]
    entry["evidence_sha256"] = hashlib.sha256(data).hexdigest()  # type: ignore[index]
    _write_manifest(export, manifest)
    _assert_closed_failure(_run(export, sources), tmp_path)

    export, sources = _tree(tmp_path / "mapping")
    sources["operations-guide"].write_bytes(b"different bytes")
    _assert_closed_failure(_run(export, sources), tmp_path)
