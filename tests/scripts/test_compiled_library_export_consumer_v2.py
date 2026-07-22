from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from mke.adapters.filesystem import publish_compiled_library
from mke.domain import (
    ActivePublicationObservation,
    CompiledEvidenceSnapshot,
    CompiledLibrarySnapshotV2,
    CompiledSourceSnapshotV2,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/compiled_library_export_consumer_v2.py"
V1_SCRIPT = ROOT / "scripts/compiled_library_export_consumer.py"


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def _source(
    tmp_path: Path, digit: str, media_type: str
) -> tuple[Path, CompiledSourceSnapshotV2]:
    suffix = {"application/pdf": "pdf", "video/mp4": "mp4", "audio/mpeg": "mp3"}[
        media_type
    ]
    raw = tmp_path / f"source-{digit}.{suffix}"
    raw.write_bytes(f"independent v2 source {digit}\n".encode())
    fingerprint = f"sha256:{hashlib.sha256(raw.read_bytes()).hexdigest()}"
    source_id = f"src_{digit * 32}"
    publication_id = f"pub_{digit * 32}"
    run_id = f"run_{digit * 32}"
    timestamp = media_type != "application/pdf"
    evidence = CompiledEvidenceSnapshot(
        evidence_id=f"ev_{digit * 32}",
        source_id=source_id,
        content_fingerprint=fingerprint,
        publication_id=publication_id,
        publication_revision=1,
        run_id=run_id,
        locator_kind="timestamp_ms" if timestamp else "page",
        locator_start=0 if timestamp else 1,
        locator_end=1200 if timestamp else 1,
        text=f"portable Evidence {digit}",
    )
    if media_type == "application/pdf":
        extractor = "pymupdf-text-v1"
        stages = ("candidate_evidence", "pdf_text_extraction")
    elif media_type == "video/mp4":
        extractor = "builtin-video-transcript-v1"
        stages = ("candidate_evidence", "video_transcription")
    else:
        extractor = f"faster-whisper-audio-v1:{digit * 64}"
        stages = ("audio_transcription", "candidate_evidence")
    return raw, CompiledSourceSnapshotV2(
        source_id=source_id,
        display_name=raw.name,
        content_fingerprint=fingerprint,
        media_type=media_type,  # type: ignore[arg-type]
        publication_id=publication_id,
        publication_revision=1,
        run_id=run_id,
        extractor_fingerprint=extractor,
        required_stages=stages,
        evidence=(evidence,),
    )


def _tree(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    pairs = [
        _source(tmp_path, "1", "application/pdf"),
        _source(tmp_path, "2", "video/mp4"),
        _source(tmp_path, "3", "audio/mpeg"),
    ]
    sources = tuple(
        sorted((source for _, source in pairs), key=lambda item: item.content_fingerprint)
    )
    snapshot = CompiledLibrarySnapshotV2(
        observation=ActivePublicationObservation("local", "active", 3, 3, 3),
        sources=sources,
    )
    publish_compiled_library(
        snapshot, format_version="v2", output_name="export", parent=tmp_path
    )
    return tmp_path / "export", {
        f"source-{index}": raw for index, (raw, _) in enumerate(pairs, start=1)
    }


def _run(script: Path, export: Path) -> subprocess.CompletedProcess[str]:
    arguments = [sys.executable, str(script), "--export", str(export)]
    arguments.append("--json")
    return subprocess.run(
        arguments,
        cwd=export.parent,
        text=True,
        capture_output=True,
        check=False,
    )


def _assert_failure(result: subprocess.CompletedProcess[str], tmp_path: Path) -> None:
    assert result.returncode == 1
    assert json.loads(result.stdout) == {"status": "failed", "code": "export_invalid"}
    assert result.stderr == ""
    assert str(tmp_path) not in result.stdout


def test_v2_consumer_accepts_complete_portable_pdf_video_audio_tree(
    tmp_path: Path,
) -> None:
    export, _sources = _tree(tmp_path)
    portable = tmp_path / "portable"
    shutil.copytree(export, portable)

    result = _run(SCRIPT, portable)

    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "schema_version": "mke.compiled_library_export_consumer.v2",
        "status": "passed",
        "export_schema": "mke.compiled_library_export.v2",
        "markdown_format": "mke.compiled_markdown.v2",
        "evidence_schema": "mke.evidence_ref.v1",
    }
    assert result.stderr == ""


def test_v1_and_v2_consumers_do_not_cross_consume(tmp_path: Path) -> None:
    export, _sources = _tree(tmp_path)
    assert _run(V1_SCRIPT, export).returncode == 1

    manifest_path = export / "export-manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["schema_version"] = "mke.compiled_library_export.v1"
    manifest_path.write_bytes(_canonical(manifest))
    assert _run(SCRIPT, export).returncode == 1


def test_v2_consumer_independently_rejects_audio_authority_mismatch(
    tmp_path: Path,
) -> None:
    export, _sources = _tree(tmp_path)
    manifest_path = export / "export-manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    audio = next(item for item in manifest["sources"] if item["media_type"] == "audio/mpeg")
    audio["media_type"] = "video/mp4"
    markdown_path = export / audio["markdown_path"]
    markdown = markdown_path.read_bytes().replace(b'"audio/mpeg"', b'"video/mp4"')
    markdown_path.write_bytes(markdown)
    audio["markdown_sha256"] = hashlib.sha256(markdown).hexdigest()
    manifest_path.write_bytes(_canonical(manifest))

    result = _run(SCRIPT, export)

    _assert_failure(result, tmp_path)


def test_v2_consumer_rejects_missing_source_and_stale_inventory(tmp_path: Path) -> None:
    export, _sources = _tree(tmp_path)
    manifest_path = export / "export-manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["sources"].pop()
    manifest_path.write_bytes(_canonical(manifest))

    _assert_failure(_run(SCRIPT, export), tmp_path)


def test_v2_consumer_rejects_extra_or_unsupported_source(tmp_path: Path) -> None:
    export, _sources = _tree(tmp_path)
    manifest_path = export / "export-manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["sources"].append(dict(manifest["sources"][0]))
    manifest_path.write_bytes(_canonical(manifest))
    _assert_failure(_run(SCRIPT, export), tmp_path)

    export, _sources = _tree(tmp_path / "second")
    manifest_path = export / "export-manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["sources"][0]["media_type"] = "audio/flac"
    manifest_path.write_bytes(_canonical(manifest))
    _assert_failure(_run(SCRIPT, export), tmp_path)


@pytest.mark.parametrize("field", ["source_id", "publication_id", "run_id"])
def test_v2_consumer_rejects_evidence_graph_mismatch(
    tmp_path: Path, field: str
) -> None:
    export, _sources = _tree(tmp_path)
    manifest_path = export / "export-manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    entry = manifest["sources"][0]
    evidence_path = export / entry["evidence_path"]
    row = json.loads(evidence_path.read_bytes())
    prefix = {"source_id": "src_", "publication_id": "pub_", "run_id": "run_"}[field]
    row[field] = prefix + "f" * 32
    evidence = _canonical(row)
    evidence_path.write_bytes(evidence)
    entry["evidence_sha256"] = hashlib.sha256(evidence).hexdigest()
    manifest_path.write_bytes(_canonical(manifest))

    _assert_failure(_run(SCRIPT, export), tmp_path)


def test_v2_consumer_rejects_tampered_jsonl_and_manifest(tmp_path: Path) -> None:
    export, _sources = _tree(tmp_path)
    evidence_path = next((export / "evidence").iterdir())
    evidence_path.write_bytes(evidence_path.read_bytes() + b"x")
    _assert_failure(_run(SCRIPT, export), tmp_path)

    export, _sources = _tree(tmp_path / "second")
    manifest_path = export / "export-manifest.json"
    manifest_path.write_bytes(manifest_path.read_bytes() + b"\n")
    _assert_failure(_run(SCRIPT, export), tmp_path)

    export, _sources = _tree(tmp_path / "third")
    markdown_path = next((export / "sources").iterdir())
    markdown_path.write_bytes(markdown_path.read_bytes() + b"tampered")
    _assert_failure(_run(SCRIPT, export), tmp_path)


def test_v2_consumer_rejects_extra_file_and_symlink(tmp_path: Path) -> None:
    export, _sources = _tree(tmp_path)
    (export / "unexpected").write_bytes(b"unexpected")
    _assert_failure(_run(SCRIPT, export), tmp_path)

    export, _sources = _tree(tmp_path / "second")
    markdown_path = next((export / "sources").iterdir())
    markdown_path.unlink()
    markdown_path.symlink_to(export / "export-manifest.json")
    _assert_failure(_run(SCRIPT, export), tmp_path)


def test_v2_consumer_is_stdlib_only() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "import mke" not in source
    assert "from mke" not in source
    assert "pydantic" not in source.casefold()
