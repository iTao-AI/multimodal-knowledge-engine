from __future__ import annotations

import json
import re
import shutil
import sqlite3
from pathlib import Path

import pytest
from pytest import CaptureFixture, MonkeyPatch

import mke.application.library_export as library_renderer
import mke.cli
import mke.interfaces.library_export as library_export
from mke.adapters.filesystem import OutputPublicationError
from mke.application import KnowledgeEngine
from mke.cli import main
from mke.domain import LibraryExportDataError
from tests.application.test_audio_publication import FakeAudioProvider
from tests.conftest import PDF_FIXTURES, VIDEO_FIXTURES

AUDIO_FIXTURES = Path(__file__).parents[1] / "fixtures" / "audio"


def _ingest_library(db_path: Path, capsys: CaptureFixture[str]) -> None:
    assert main(["--db", str(db_path), "ingest", str(PDF_FIXTURES / "text-layer.pdf")]) == 0
    capsys.readouterr()
    video = db_path.with_name("one-segment.mp4")
    shutil.copyfile(VIDEO_FIXTURES / "short-audio.mp4", video)
    sidecar = json.loads(
        (VIDEO_FIXTURES / "short-audio.mp4.mke-transcript.json").read_text(encoding="utf-8")
    )
    sidecar["segments"] = sidecar["segments"][:1]
    video.with_suffix(".mp4.mke-transcript.json").write_text(json.dumps(sidecar), encoding="utf-8")
    assert main(["--db", str(db_path), "ingest", str(video)]) == 0
    capsys.readouterr()


def _active_state_rows(db_path: Path) -> tuple[tuple[object, ...], ...]:
    connection = sqlite3.connect(db_path)
    try:
        return tuple(
            connection.execute(
                "SELECT source_id, active_publication_id FROM sources ORDER BY source_id"
            ).fetchall()
        )
    finally:
        connection.close()


def _initialize_empty_library(db_path: Path) -> None:
    engine = KnowledgeEngine(db_path)
    engine.close()


def _ingest_audio(db_path: Path) -> None:
    engine = KnowledgeEngine(
        db_path,
        audio_provider=FakeAudioProvider(),
        audio_transcription_config=object(),
        audio_preflight=lambda: None,
    )
    try:
        engine.ingest_file(AUDIO_FIXTURES / "direct-audio.mp3")
    finally:
        engine.close()


def _assert_closed_error(
    output: str,
    expected: tuple[str, str, str],
    *,
    forbidden: tuple[str, ...] = (),
) -> None:
    assert output.count("\n") == 1
    payload = json.loads(output)
    assert (payload["problem"], payload["cause"], payload["next_step"]) == expected
    assert set(payload) == {
        "schema_version",
        "ok",
        "problem",
        "cause",
        "active_publication_impact",
        "next_step",
    }
    for value in forbidden:
        assert value not in output


def test_library_export_success_close_failure_replaces_success_before_print(
    tmp_path: Path, monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"
    _ingest_library(db_path, capsys)
    original_close = KnowledgeEngine.close

    def close_then_fail(engine: KnowledgeEngine) -> None:
        original_close(engine)
        raise RuntimeError(f"CloseError Traceback {tmp_path}/mke.sqlite")

    monkeypatch.setattr(KnowledgeEngine, "close", close_then_fail)
    assert (
        library_export.run_library_export(
            db_path, "close-failed", json_output=True, parent=tmp_path
        )
        == 1
    )
    _assert_closed_error(
        capsys.readouterr().out,
        (
            "library_export_failed",
            "operation failed; details were redacted",
            "retry_library_export",
        ),
        forbidden=(str(tmp_path), "CloseError", "Traceback", "RuntimeError", '"ok":true'),
    )
    assert not (tmp_path / "close-failed").exists()


def test_library_export_real_render_limit_uses_too_large_contract_and_cleans_target(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    db_path = tmp_path / "mke.sqlite"
    _ingest_library(db_path, capsys)
    monkeypatch.setattr(library_renderer, "_MAX_RENDERED_FILE_BYTES", 1)

    assert (
        library_export.run_library_export(
            db_path, "render-too-large", json_output=True, parent=tmp_path
        )
        == 1
    )
    _assert_closed_error(
        capsys.readouterr().out,
        (
            "library_export_too_large",
            "active Library exceeds v1 export limits",
            "reduce_active_library_or_use_later_export_version",
        ),
    )
    assert not (tmp_path / "render-too-large").exists()


def test_library_export_typed_failure_close_failure_is_one_redacted_output(
    tmp_path: Path, monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"
    _initialize_empty_library(db_path)
    original_close = KnowledgeEngine.close

    def close_then_fail(engine: KnowledgeEngine) -> None:
        original_close(engine)
        raise RuntimeError(f"CloseError Traceback {tmp_path}/mke.sqlite")

    monkeypatch.setattr(KnowledgeEngine, "close", close_then_fail)
    assert (
        library_export.run_library_export(
            db_path, "unused", json_output=True, parent=tmp_path
        )
        == 1
    )
    _assert_closed_error(
        capsys.readouterr().out,
        (
            "library_export_failed",
            "operation failed; details were redacted",
            "retry_library_export",
        ),
        forbidden=(str(tmp_path), "CloseError", "Traceback", "RuntimeError"),
    )


def test_library_export_json_and_human_success_are_closed(
    tmp_path: Path, monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"
    _ingest_library(db_path, capsys)
    before = _active_state_rows(db_path)

    def fail_build(_config: object) -> object:
        pytest.fail("build_engine called")

    def fail_recovery(_engine: KnowledgeEngine) -> None:
        pytest.fail("owner recovery called")

    monkeypatch.setattr(mke.cli, "build_engine", fail_build)
    monkeypatch.setattr(
        KnowledgeEngine,
        "recover_unfinished_runs",
        fail_recovery,
    )
    monkeypatch.chdir(tmp_path)

    assert (
        main(["--db", str(db_path), "library", "export", "--output", "json-export", "--json"]) == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert set(payload) == {
        "evidence_count",
        "library_id",
        "manifest_sha256",
        "ok",
        "schema_version",
        "source_count",
    }
    assert payload == {
        "evidence_count": 3,
        "library_id": "local",
        "manifest_sha256": payload["manifest_sha256"],
        "ok": True,
        "schema_version": "mke.compiled_library_export_response.v1",
        "source_count": 2,
    }
    assert re.fullmatch(r"[0-9a-f]{64}", payload["manifest_sha256"])
    manifest = (tmp_path / "json-export" / "export-manifest.json").read_bytes()
    from hashlib import sha256

    assert payload["manifest_sha256"] == sha256(manifest).hexdigest()

    assert main(["--db", str(db_path), "library", "export", "--output", "human-export"]) == 0
    human_manifest = tmp_path / "human-export" / "export-manifest.json"
    assert capsys.readouterr().out == (
        "library_export=passed library_id=local source_count=2 evidence_count=3 "
        f"manifest_sha256={sha256(human_manifest.read_bytes()).hexdigest()}\n"
    )
    assert _active_state_rows(db_path) == before


def test_default_and_explicit_v1_cli_outputs_are_exactly_equal(
    tmp_path: Path, monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"
    _ingest_library(db_path, capsys)
    monkeypatch.chdir(tmp_path)

    assert main(
        ["--db", str(db_path), "library", "export", "--output", "default", "--json"]
    ) == 0
    default_response = capsys.readouterr().out
    assert main(
        [
            "--db",
            str(db_path),
            "library",
            "export",
            "--format-version",
            "v1",
            "--output",
            "explicit",
            "--json",
        ]
    ) == 0
    explicit_response = capsys.readouterr().out

    def tree(root: Path) -> dict[str, bytes]:
        return {
            str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        }

    assert default_response == explicit_response
    assert tree(tmp_path / "default") == tree(tmp_path / "explicit")


def test_v2_cli_response_and_tree_are_version_matched(
    tmp_path: Path, monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"
    _ingest_library(db_path, capsys)
    monkeypatch.chdir(tmp_path)

    assert main(
        [
            "--db",
            str(db_path),
            "library",
            "export",
            "--format-version",
            "v2",
            "--output",
            "v2-export",
            "--json",
        ]
    ) == 0
    response = json.loads(capsys.readouterr().out)
    manifest = json.loads((tmp_path / "v2-export/export-manifest.json").read_bytes())
    assert response["schema_version"] == "mke.compiled_library_export_response.v2"
    assert set(response) == {
        "schema_version",
        "ok",
        "library_id",
        "source_count",
        "evidence_count",
        "manifest_sha256",
    }
    assert manifest["schema_version"] == "mke.compiled_library_export.v2"
    assert manifest["markdown_format"] == "mke.compiled_markdown.v2"
    assert manifest["evidence_schema"] == "mke.evidence_ref.v1"


def test_v1_mixed_audio_failure_is_exact_and_v2_exports_complete_library(
    tmp_path: Path, monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"
    owner = KnowledgeEngine(db_path)
    try:
        owner.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
    finally:
        owner.close()
    _ingest_audio(db_path)
    monkeypatch.chdir(tmp_path)

    for version_args in ([], ["--format-version", "v1"]):
        assert main(
            [
                "--db",
                str(db_path),
                "library",
                "export",
                *version_args,
                "--output",
                f"v1-failed-{len(version_args)}",
                "--json",
            ]
        ) == 1
        _assert_closed_error(
            capsys.readouterr().out,
            (
                "unsupported_active_media_type",
                "active Library contains media unsupported by export v1",
                "rerun_library_export_with_format_version_v2",
            ),
        )

    assert main(
        [
            "--db",
            str(db_path),
            "library",
            "export",
            "--format-version",
            "v2",
            "--output",
            "complete-v2",
            "--json",
        ]
    ) == 0
    response = json.loads(capsys.readouterr().out)
    assert response["source_count"] == 2
    manifest = json.loads((tmp_path / "complete-v2/export-manifest.json").read_bytes())
    assert {source["media_type"] for source in manifest["sources"]} == {
        "application/pdf",
        "audio/mpeg",
    }



def test_library_export_help_is_closed(capsys: CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["library", "export", "--help"])
    assert raised.value.code == 0
    help_text = capsys.readouterr().out
    assert "--output" in help_text and "--json" in help_text
    assert "--format-version" in help_text and "{v1,v2}" in help_text
    for forbidden in ("library-id", "source", "extractor", "provider", "mcp", "parent"):
        assert forbidden not in help_text.casefold()


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        (
            "--retrieval-query-policy",
            "current",
            "library export does not support --retrieval-query-policy",
        ),
        ("--retrieval-strategy", "current", "library export does not support --retrieval-strategy"),
    ],
)
@pytest.mark.parametrize("equals", [False, True])
def test_library_export_rejects_retrieval_options_before_runtime(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    option: str,
    value: str,
    message: str,
    equals: bool,
) -> None:
    def fail_build(_config: object) -> object:
        pytest.fail("build_engine called")

    def fail_open(_db_path: Path) -> object:
        pytest.fail("read-only engine called")

    monkeypatch.setattr(mke.cli, "build_engine", fail_build)
    monkeypatch.setattr(
        KnowledgeEngine,
        "open_read_only_export",
        fail_open,
    )
    raw_option = [f"{option}={value}"] if equals else [option, value]
    with pytest.raises(SystemExit) as raised:
        main(
            [
                "--db",
                str(tmp_path / "mke.sqlite"),
                *raw_option,
                "library",
                "export",
                "--output",
                "out",
            ]
        )
    assert raised.value.code == 2
    assert message in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv",
    [
        ["search", "query", "--format-version", "v2"],
        ["ingest", "missing.pdf", "--format-version", "v2"],
    ],
)
def test_format_version_is_rejected_outside_library_export(
    argv: list[str], monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    def fail_build(_config: object) -> object:
        pytest.fail("runtime must not be built")

    monkeypatch.setattr(mke.cli, "build_engine", fail_build)
    with pytest.raises(SystemExit) as raised:
        main(argv)
    assert raised.value.code == 2
    assert "--format-version" in capsys.readouterr().err


class _FakeEngine:
    def __init__(self, snapshot: object = object(), error: Exception | None = None) -> None:
        self.snapshot = snapshot
        self.error = error
        self.closed = False
        self.format_versions: list[str] = []

    def compiled_library_snapshot(self, *, format_version: str = "v1") -> object:
        self.format_versions.append(format_version)
        if self.error is not None:
            raise self.error
        return self.snapshot

    def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize("interrupt_phase", ["snapshot", "publisher"])
def test_library_export_base_exception_unwind_closes_and_propagates(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    interrupt_phase: str,
) -> None:
    class InterruptEngine(_FakeEngine):
        def compiled_library_snapshot(self, *, format_version: str = "v1") -> object:
            if interrupt_phase == "snapshot":
                raise KeyboardInterrupt(f"SECRET Traceback {tmp_path}/mke.sqlite")
            return super().compiled_library_snapshot(format_version=format_version)

    engine = InterruptEngine()

    def open_fake(_db_path: Path) -> InterruptEngine:
        return engine

    def interrupt_publish(*args: object, **kwargs: object) -> object:
        raise KeyboardInterrupt(f"SECRET Traceback {tmp_path}/output")

    monkeypatch.setattr(KnowledgeEngine, "open_read_only_export", open_fake)
    if interrupt_phase == "publisher":
        monkeypatch.setattr(library_export, "publish_compiled_library", interrupt_publish)

    with pytest.raises(KeyboardInterrupt):
        library_export.run_library_export(
            tmp_path / "mke.sqlite", "output", json_output=True, parent=tmp_path
        )

    assert engine.closed
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            LibraryExportDataError("empty"),
            (
                "library_export_invalid",
                "local Library has no active Publications",
                "ingest_and_publish_source",
            ),
        ),
        (
            LibraryExportDataError("provenance"),
            (
                "library_export_invalid",
                "active Publication provenance graph is invalid",
                "repair_local_library",
            ),
        ),
        (
            LibraryExportDataError("too_large"),
            (
                "library_export_too_large",
                "active Library exceeds v1 export limits",
                "reduce_active_library_or_use_later_export_version",
            ),
        ),
        (
            RuntimeError("SECRET Traceback /private/source"),
            (
                "library_export_failed",
                "operation failed; details were redacted",
                "retry_library_export",
            ),
        ),
    ],
)
def test_library_export_snapshot_failures_are_closed_and_close_engine(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    error: Exception,
    expected: tuple[str, str, str],
) -> None:
    engine = _FakeEngine(error=error)

    def open_fake(_db_path: Path) -> _FakeEngine:
        return engine

    monkeypatch.setattr(KnowledgeEngine, "open_read_only_export", open_fake)
    assert (
        library_export.run_library_export(
            tmp_path / "SECRET.sqlite", "SECRET-output", json_output=True, parent=tmp_path
        )
        == 1
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "active_publication_impact": "unchanged",
        "cause": expected[1],
        "next_step": expected[2],
        "ok": False,
        "problem": expected[0],
        "schema_version": "mke.compiled_library_export_response.v1",
    }
    assert engine.closed
    rendered = json.dumps(payload)
    for forbidden in (
        str(tmp_path),
        "SECRET",
        "Traceback",
        "RuntimeError",
        "SECRET.sqlite",
        "SECRET-output",
    ):
        assert forbidden not in rendered


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        (
            "target_exists",
            (
                "output_path_invalid",
                "output directory must not already exist",
                "choose_new_output_directory",
            ),
        ),
        (
            "parent_invalid",
            ("output_path_invalid", "output parent is invalid", "choose_valid_output_parent"),
        ),
        (
            "write_failed",
            (
                "library_export_failed",
                "operation failed; details were redacted",
                "retry_library_export",
            ),
        ),
        (
            "cleanup_failed",
            ("cleanup_failed", "operation failed; details were redacted", "inspect_output_parent"),
        ),
    ],
)
def test_library_export_publication_failures_are_closed_and_close_engine(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    reason: str,
    expected: tuple[str, str, str],
) -> None:
    engine = _FakeEngine()

    def open_fake(_db_path: Path) -> _FakeEngine:
        return engine

    monkeypatch.setattr(KnowledgeEngine, "open_read_only_export", open_fake)

    def fail_publish(*args: object, **kwargs: object) -> object:
        raise OutputPublicationError(reason)  # type: ignore[arg-type]

    monkeypatch.setattr(library_export, "publish_compiled_library", fail_publish)
    assert (
        library_export.run_library_export(
            tmp_path / "db", "output", json_output=True, parent=tmp_path
        )
        == 1
    )
    payload = json.loads(capsys.readouterr().out)
    assert (payload["problem"], payload["cause"], payload["next_step"]) == expected
    assert set(payload) == {
        "schema_version",
        "ok",
        "problem",
        "cause",
        "active_publication_impact",
        "next_step",
    }
    assert engine.closed


def test_library_export_missing_database_is_stable_and_runtime_is_not_built(
    tmp_path: Path, monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    def fail_build(_config: object) -> object:
        pytest.fail("build_engine called")

    monkeypatch.setattr(mke.cli, "build_engine", fail_build)
    monkeypatch.chdir(tmp_path)
    assert (
        main(
            [
                "--db",
                str(tmp_path / "missing.sqlite"),
                "library",
                "export",
                "--output",
                "out",
                "--json",
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out) == {
        "active_publication_impact": "unchanged",
        "cause": "local Library database is unavailable or incompatible",
        "next_step": "open_current_library_database",
        "ok": False,
        "problem": "library_export_invalid",
        "schema_version": "mke.compiled_library_export_response.v1",
    }
    assert not (tmp_path / "missing.sqlite").exists()
    assert not (Path.cwd() / "out").exists()


def test_v2_error_response_reuses_exact_v1_error_fields(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    assert main(
        [
            "--db",
            str(tmp_path / "missing.sqlite"),
            "library",
            "export",
            "--format-version",
            "v2",
            "--output",
            "out",
            "--json",
        ]
    ) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "active_publication_impact": "unchanged",
        "cause": "local Library database is unavailable or incompatible",
        "next_step": "open_current_library_database",
        "ok": False,
        "problem": "library_export_invalid",
        "schema_version": "mke.compiled_library_export_response.v2",
    }


def test_library_export_schema_missing_library_name_is_database_incompatible(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"
    _ingest_library(db_path, capsys)
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        PRAGMA foreign_keys = OFF;
        CREATE TABLE libraries_replacement (library_id TEXT PRIMARY KEY);
        INSERT INTO libraries_replacement SELECT library_id FROM libraries;
        DROP TABLE libraries;
        ALTER TABLE libraries_replacement RENAME TO libraries;
        """
    )
    connection.close()

    assert (
        library_export.run_library_export(
            db_path, "out", json_output=True, parent=tmp_path
        )
        == 1
    )
    _assert_closed_error(
        capsys.readouterr().out,
        (
            "library_export_invalid",
            "local Library database is unavailable or incompatible",
            "open_current_library_database",
        ),
    )
    assert not (tmp_path / "out").exists()


def test_library_export_real_no_active_failure_preserves_active_state(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"
    _initialize_empty_library(db_path)
    before = _active_state_rows(db_path)

    assert (
        library_export.run_library_export(
            db_path, "unused", json_output=True, parent=tmp_path
        )
        == 1
    )

    _assert_closed_error(
        capsys.readouterr().out,
        (
            "library_export_invalid",
            "local Library has no active Publications",
            "ingest_and_publish_source",
        ),
    )
    assert _active_state_rows(db_path) == before
    assert not (tmp_path / "unused").exists()


def test_library_export_real_graph_drift_preserves_active_state(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"
    _ingest_library(db_path, capsys)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            UPDATE runs SET state = 'failed'
            WHERE run_id = (
              SELECT publications.run_id
              FROM sources
              JOIN publications
                ON publications.publication_id = sources.active_publication_id
              ORDER BY sources.source_id
              LIMIT 1
            )
            """
        )
        connection.commit()
    finally:
        connection.close()
    before = _active_state_rows(db_path)

    assert (
        library_export.run_library_export(
            db_path, "unused", json_output=True, parent=tmp_path
        )
        == 1
    )

    _assert_closed_error(
        capsys.readouterr().out,
        (
            "library_export_invalid",
            "active Publication provenance graph is invalid",
            "repair_local_library",
        ),
    )
    assert _active_state_rows(db_path) == before
    assert not (tmp_path / "unused").exists()


@pytest.mark.parametrize(
    ("output_name", "prepare_target", "expected"),
    [
        (
            "existing",
            True,
            (
                "output_path_invalid",
                "output directory must not already exist",
                "choose_new_output_directory",
            ),
        ),
        (
            "../invalid",
            False,
            (
                "output_path_invalid",
                "output parent is invalid",
                "choose_valid_output_parent",
            ),
        ),
    ],
)
def test_library_export_real_output_failures_preserve_active_state(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    output_name: str,
    prepare_target: bool,
    expected: tuple[str, str, str],
) -> None:
    db_path = tmp_path / "mke.sqlite"
    _ingest_library(db_path, capsys)
    if prepare_target:
        (tmp_path / output_name).mkdir()
    before = _active_state_rows(db_path)

    assert (
        library_export.run_library_export(
            db_path, output_name, json_output=True, parent=tmp_path
        )
        == 1
    )

    _assert_closed_error(capsys.readouterr().out, expected)
    assert _active_state_rows(db_path) == before


def test_library_export_real_read_only_over_limit_preserves_active_state(
    tmp_path: Path, monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    db_path = tmp_path / "mke.sqlite"
    _ingest_library(db_path, capsys)
    before = _active_state_rows(db_path)

    def reject_over_limit(
        _engine: KnowledgeEngine, *, format_version: str = "v1"
    ) -> object:
        raise LibraryExportDataError("too_large")

    monkeypatch.setattr(KnowledgeEngine, "compiled_library_snapshot", reject_over_limit)
    assert (
        library_export.run_library_export(
            db_path, "unused", json_output=True, parent=tmp_path
        )
        == 1
    )

    _assert_closed_error(
        capsys.readouterr().out,
        (
            "library_export_too_large",
            "active Library exceeds v1 export limits",
            "reduce_active_library_or_use_later_export_version",
        ),
    )
    assert _active_state_rows(db_path) == before
    assert not (tmp_path / "unused").exists()


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        (
            "write_failed",
            (
                "library_export_failed",
                "operation failed; details were redacted",
                "retry_library_export",
            ),
        ),
        (
            "cleanup_failed",
            (
                "cleanup_failed",
                "operation failed; details were redacted",
                "inspect_output_parent",
            ),
        ),
    ],
)
def test_library_export_injected_publisher_failure_uses_real_read_only_engine(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    reason: str,
    expected: tuple[str, str, str],
) -> None:
    db_path = tmp_path / "mke.sqlite"
    _ingest_library(db_path, capsys)
    before = _active_state_rows(db_path)
    original_close = KnowledgeEngine.close
    closed: list[bool] = []

    def observe_close(engine: KnowledgeEngine) -> None:
        original_close(engine)
        closed.append(True)

    def fail_publish(*args: object, **kwargs: object) -> object:
        raise OutputPublicationError(reason)  # type: ignore[arg-type]

    monkeypatch.setattr(KnowledgeEngine, "close", observe_close)
    monkeypatch.setattr(library_export, "publish_compiled_library", fail_publish)
    assert (
        library_export.run_library_export(
            db_path, "unused", json_output=True, parent=tmp_path
        )
        == 1
    )

    _assert_closed_error(capsys.readouterr().out, expected)
    assert closed == [True]
    assert _active_state_rows(db_path) == before
