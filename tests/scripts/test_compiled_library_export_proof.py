# pyright: reportUnknownArgumentType=false, reportUnknownLambdaType=false
# pyright: reportUnknownMemberType=false

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/compiled_library_export_proof.py"
WORKFLOW = ROOT / ".github/workflows/compiled-library-export-proof.yml"
CI_WORKFLOW = ROOT / ".github/workflows/ci.yml"
SOURCE_PACK_WORKFLOW = ROOT / ".github/workflows/consumer-source-pack-proof.yml"


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("compiled_library_export_proof", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _job(workflow: str | None = None) -> str:
    if workflow is None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
    sections = workflow.split("\njobs:\n", maxsplit=1)
    assert len(sections) == 2
    names = re.findall(r"(?m)^  ([a-zA-Z0-9_-]+):\n", sections[1])
    assert names == ["compiled-library-export-proof"]
    return sections[1]


def _primary_ci_python_job() -> str:
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    sections = workflow.split("\njobs:\n", maxsplit=1)
    assert len(sections) == 2
    names = re.findall(r"(?m)^  ([a-zA-Z0-9_-]+):\n", sections[1])
    assert names == ["embedding-extra", "python"]
    matches = list(
        re.finditer(
            r"(?ms)^  python:\n(?P<body>.*?)(?=^  [a-zA-Z0-9_-]+:\n|\Z)",
            sections[1],
        )
    )
    assert len(matches) == 1
    return matches[0].group(0)


def test_controller_reuses_reviewed_process_helpers_without_copying_controller() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "from consumer_source_pack_proof import" in source
    assert "_clean_sha1_source_commit" in source
    assert "_candidate_source_snapshot" in source
    assert "run_bounded" in source
    assert "isolated_environment" in source
    assert "def _git_value" not in source
    assert "def _clean_candidate_snapshot" not in source
    assert "subprocess.Popen(" not in source
    assert ".communicate(" not in source


def _git_repository(path: Path) -> Path:
    path.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "proof@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Proof Test"], cwd=path, check=True)
    (path / "pyproject.toml").write_text(
        '[project]\nname="multimodal-knowledge-engine"\nversion="0.1.2"\n'
    )
    subprocess.run(["git", "add", "pyproject.toml"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=path, check=True)
    return path


def test_candidate_source_rejects_real_dirty_repository(tmp_path: Path) -> None:
    proof = _load()
    repository = _git_repository(tmp_path / "repository")
    (repository / "untracked.txt").write_text("dirty")
    config = proof.ProofConfig(repository, (Path("/312"), Path("/313")), 10, 100, 100)
    root = tmp_path / "owned"
    root.mkdir()
    with pytest.raises(proof.ControllerError, match="candidate_artifact_invalid"):
        proof._candidate_source(config, root)
    assert not (root / "source").exists()


def test_candidate_source_rejects_head_change_during_real_authority_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    proof = _load()
    repository = _git_repository(tmp_path / "repository")
    authority = sys.modules["consumer_source_pack_proof"]
    original_run = authority.subprocess.run
    advanced = False

    def moving_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[Any]:
        nonlocal advanced
        result = original_run(*args, **kwargs)
        command = args[0]
        if command == ["git", "status", "--porcelain=v1", "--untracked-files=all"] and not advanced:
            advanced = True
            original_run(
                ["git", "commit", "--allow-empty", "-qm", "move head"],
                cwd=repository,
                check=True,
            )
        return result

    monkeypatch.setattr(authority.subprocess, "run", moving_run)
    config = proof.ProofConfig(repository, (Path("/312"), Path("/313")), 10, 100, 100)
    root = tmp_path / "owned"
    root.mkdir()
    with pytest.raises(proof.ControllerError, match="candidate_artifact_invalid"):
        proof._candidate_source(config, root)
    assert advanced is True
    assert not (root / "source").exists()


def test_aggregate_is_closed_and_requires_one_digest_for_two_interpreters() -> None:
    proof = _load()
    digest = hashlib.sha256(b"same wheel").hexdigest()
    result = proof.aggregate_results(
        [
            proof.InterpreterResult("3.12", digest, 2, 3),
            proof.InterpreterResult("3.13", digest, 2, 3),
        ]
    )
    assert result == {
        "evidence_schema": "mke.evidence_ref.v1",
        "export_schema": "mke.compiled_library_export.v1",
        "interpreter_count": 2,
        "markdown_format": "mke.compiled_markdown.v1",
        "proof_input_wheel_sha256": digest,
        "schema_version": "mke.compiled_library_export_proof.v1",
        "status": "passed",
    }
    for results in (
        [proof.InterpreterResult("3.12", digest, 2, 3)],
        [
            proof.InterpreterResult("3.12", digest, 2, 3),
            proof.InterpreterResult("3.12", digest, 2, 3),
        ],
        [
            proof.InterpreterResult("3.12", digest, 2, 3),
            proof.InterpreterResult("3.13", "f" * 64, 2, 3),
        ],
    ):
        with pytest.raises(proof.ControllerError, match="proof_failed"):
            proof.aggregate_results(results)


@pytest.mark.parametrize(
    ("expected_failure", "stdout"),
    [
        ("target_exists", b""),
        ("target_exists", b"Traceback: crashed\n"),
        ("target_exists", b'{"ok":false}\n'),
        (
            "target_exists",
            b'{"active_publication_impact":"unchanged","cause":"output directory must not '
            b'already exist","next_step":"choose_new_output_directory","ok":false,'
            b'"problem":"wrong_problem","schema_version":'
            b'"mke.compiled_library_export_response.v1"}\n',
        ),
        (
            "provenance",
            b'{"active_publication_impact":"unchanged","cause":"active Publication provenance '
            b'graph is invalid","extra":true,"next_step":"repair_local_library","ok":false,'
            b'"problem":"library_export_invalid","schema_version":'
            b'"mke.compiled_library_export_response.v1"}\n',
        ),
    ],
)
def test_producer_negative_requires_exact_closed_public_payload(
    expected_failure: str, stdout: bytes
) -> None:
    proof = _load()
    with pytest.raises(proof.ControllerError, match="producer_failed"):
        proof._producer_export_payload(stdout, expected_failure=expected_failure)


@pytest.mark.parametrize(
    "stdout",
    [
        b"",
        b"Traceback: crashed\n",
        b'{"code":"export_invalid","status":"passed"}\n',
        b'{"code":"wrong","status":"failed"}\n',
        b'{"code":"export_invalid","extra":true,"status":"failed"}\n',
    ],
)
def test_consumer_negative_requires_exact_closed_failure_payload(stdout: bytes) -> None:
    proof = _load()
    with pytest.raises(proof.ControllerError, match="consumer_failed"):
        proof._consumer_payload(stdout, success=False)


@pytest.mark.parametrize("offline", [None, "0", "true"])
def test_run_proof_requires_explicit_offline_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    offline: str | None,
) -> None:
    proof = _load()
    if offline is None:
        monkeypatch.delenv("UV_OFFLINE", raising=False)
    else:
        monkeypatch.setenv("UV_OFFLINE", offline)
    monkeypatch.setattr(
        proof.tempfile,
        "mkdtemp",
        lambda **_kwargs: pytest.fail("proof allocated state before offline validation"),
    )
    config = proof.ProofConfig(
        tmp_path, (Path("/python3.12"), Path("/python3.13")), 10, 100, 100
    )
    with pytest.raises(proof.ControllerError, match="proof_failed"):
        proof.run_proof(config)


@pytest.mark.parametrize("cleanup_behavior", ["raises", "leaves_root"])
def test_run_proof_reports_root_cleanup_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cleanup_behavior: str,
) -> None:
    proof = _load()
    root = tmp_path / "owned"
    root.mkdir()
    monkeypatch.setenv("UV_OFFLINE", "1")
    monkeypatch.setattr(proof.tempfile, "mkdtemp", lambda **_kwargs: str(root))

    def fail_build(*_args: object) -> tuple[Path, str]:
        raise proof.ControllerError("proof_failed")

    monkeypatch.setattr(proof, "_build_candidate", fail_build)
    if cleanup_behavior == "raises":

        def fail_cleanup(_path: Path) -> None:
            raise OSError("simulated cleanup failure")

        monkeypatch.setattr(proof.shutil, "rmtree", fail_cleanup)
    else:
        monkeypatch.setattr(proof.shutil, "rmtree", lambda _path: None)

    config = proof.ProofConfig(
        tmp_path, (Path("/python3.12"), Path("/python3.13")), 10, 100, 100
    )
    with pytest.raises(proof.ControllerError, match="cleanup_failed"):
        proof.run_proof(config)


@pytest.mark.parametrize(
    "drift_target", [None, "state-after-existing", "state-after-corrupt"]
)
def test_run_proof_builds_one_candidate_and_checks_identity_invariants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drift_target: str | None
) -> None:
    proof = _load()
    authority = sys.modules["consumer_source_pack_proof"]
    owned = tmp_path / "owned"
    events: list[str] = []

    def clean_commit(_repository: Path) -> str:
        events.append("candidate-clean")
        return "a" * 40

    def snapshot(
        _repository: Path, _commit: str, root: Path, _timeout: float
    ) -> Path:
        events.append("candidate-snapshot")
        source = root / "source"
        source.mkdir()
        (source / "pyproject.toml").write_text(
            '[project]\nname="multimodal-knowledge-engine"\nversion="0.1.2"\n'
        )
        return source

    def export_tree(target: Path) -> None:
        (target / "sources").mkdir(parents=True)
        (target / "evidence").mkdir()
        (target / "sources/source.md").write_bytes(b"stable markdown\n")
        (target / "evidence/source.jsonl").write_bytes(b'{"stable":true}\n')
        (target / "export-manifest.json").write_text(
            json.dumps(
                {
                    "observation": {"library_id": "local", "state": "active"},
                    "sources": [
                        {
                            "source_id": "src_"
                            + ("b" if target.name == drift_target else "a") * 32
                        }
                    ],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )

    def fake_run(
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
        timeout_seconds: float,
        max_stdout_bytes: int,
        max_stderr_bytes: int,
    ) -> object:
        del timeout_seconds, max_stdout_bytes, max_stderr_bytes
        argv = list(command)
        assert env.get("UV_OFFLINE") == "1"
        stdout = b""
        returncode = 0
        if argv[:2] == ["uv", "build"]:
            events.append("build-wheel")
            output = Path(argv[argv.index("--out-dir") + 1])
            wheel = output / "multimodal_knowledge_engine-0.1.2-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr(
                    "multimodal_knowledge_engine-0.1.2.dist-info/METADATA",
                    "Name: multimodal-knowledge-engine\nVersion: 0.1.2\n",
                )
        elif argv[:2] == ["uv", "export"]:
            events.append("export-constraints")
            Path(argv[argv.index("--output-file") + 1]).write_text("# locked\n")
        elif argv[:2] == ["uv", "venv"]:
            index = int(Path(argv[2]).name.rsplit("-", 1)[1])
            events.append(f"{index}:venv")
            binary = Path(argv[2]) / "bin"
            binary.mkdir(parents=True)
            for name in ("python", "mke"):
                path = binary / name
                path.write_text("#!/bin/sh\n")
                path.chmod(0o755)
        elif argv[:3] == ["uv", "pip", "install"]:
            index = int(Path(argv[argv.index("--python") + 1]).parents[1].name.rsplit("-", 1)[1])
            events.append(f"{index}:install-offline")
        elif argv[:3] == ["uv", "pip", "check"]:
            index = int(Path(argv[argv.index("--python") + 1]).parents[1].name.rsplit("-", 1)[1])
            events.append(f"{index}:pip-check")
        elif len(argv) >= 3 and argv[1] == "-c":
            index = int(Path(argv[0]).parents[1].name.rsplit("-", 1)[1])
            if "distribution(" in argv[2]:
                events.append(f"{index}:doctor")
                environment = Path(argv[0]).parents[1].resolve()
                module = environment / "lib/python/site-packages/mke/__init__.py"
                metadata = environment / "lib/python/site-packages/mke.dist-info"
                module.parent.mkdir(parents=True)
                metadata.mkdir(parents=True)
                module.write_text("")
                stdout = json.dumps(
                    {
                        "module": str(module),
                        "metadata": str(metadata),
                        "version": "0.1.2",
                        "python": str(Path(argv[0]).resolve()),
                    }
                ).encode()
            else:
                events.append(f"{index}:minor")
                stdout = f"3.{12 + index}\n".encode()
        elif Path(argv[0]).name == "mke" and "ingest" in argv:
            index = int(Path(argv[0]).parents[1].name.rsplit("-", 1)[1])
            source = Path(argv[argv.index("ingest") + 1]).name
            events.append(f"{index}:ingest:{source}")
            database = Path(argv[argv.index("--db") + 1])
            connection = sqlite3.connect(database)
            try:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS publications "
                    "(publication_id TEXT, source_id TEXT, run_id TEXT)"
                )
                if connection.execute("SELECT COUNT(*) FROM publications").fetchone()[0] == 0:
                    connection.execute(
                        "INSERT INTO publications VALUES (?, ?, ?)",
                        ("pub_" + "a" * 32, "src_" + "a" * 32, "run_" + "a" * 32),
                    )
                connection.commit()
            finally:
                connection.close()
        elif Path(argv[0]).name == "mke" and "export" in argv:
            index = int(Path(argv[0]).parents[1].name.rsplit("-", 1)[1])
            name = argv[argv.index("--output") + 1]
            events.append(f"{index}:export:{name}")
            target = cwd / name
            if target.exists() or name == "corrupted-output":
                returncode = 1
                failure = (
                    proof._PRODUCER_FAILURES["provenance"]
                    if name == "corrupted-output"
                    else proof._PRODUCER_FAILURES["target_exists"]
                )
                stdout = proof.canonical_json(failure)
            else:
                export_tree(target)
                stdout = proof.canonical_json(
                    {
                        "schema_version": "mke.compiled_library_export_response.v1",
                        "ok": True,
                        "library_id": "local",
                        "source_count": 2,
                        "evidence_count": 3,
                        "manifest_sha256": "a" * 64,
                    }
                )
        elif Path(argv[1]).name == "compiled_library_export_consumer.py":
            index = int(Path(argv[0]).parents[1].name.rsplit("-", 1)[1])
            target = Path(argv[argv.index("--export") + 1])
            events.append(f"{index}:consumer:{target.name}")
            if target.name in {"digest-drift", "unexpected-file", "manifest-less"}:
                returncode = 1
                stdout = b'{"code":"export_invalid","status":"failed"}\n'
            else:
                stdout = proof.canonical_json(proof._CONSUMER_SUCCESS)
        else:
            raise AssertionError(argv)
        return authority.CommandResult(returncode, stdout, b"")

    monkeypatch.setattr(proof, "_clean_sha1_source_commit", clean_commit)
    monkeypatch.setattr(proof, "_candidate_source_snapshot", snapshot)
    monkeypatch.setattr(proof, "run_bounded", fake_run)
    monkeypatch.setattr(proof.tempfile, "mkdtemp", lambda **_kwargs: str(owned))
    monkeypatch.setenv("UV_OFFLINE", "1")
    python312 = tmp_path / "python3.12"
    python313 = tmp_path / "python3.13"
    for interpreter in (python312, python313):
        interpreter.write_text("#!/bin/sh\n")
        interpreter.chmod(0o755)
    config = proof.ProofConfig(
        ROOT, (python312, python313), 10, 1024 * 1024, 1024 * 1024
    )
    if drift_target is not None:
        with pytest.raises(proof.ControllerError, match="producer_failed"):
            proof.run_proof(config)
        assert f"0:export:{drift_target}" in events
        assert not any(event.startswith("1:") for event in events)
        assert not owned.exists()
        return
    result = proof.run_proof(config)
    digest = result["proof_input_wheel_sha256"]
    assert isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)
    assert result["proof_input_wheel_sha256"] == digest
    assert events[:4] == [
        "candidate-clean",
        "candidate-snapshot",
        "build-wheel",
        "export-constraints",
    ]
    per_interpreter = [
        "venv",
        "install-offline",
        "pip-check",
        "doctor",
        "minor",
        "ingest:operations-guide.pdf",
        "ingest:spoken-evidence.mp4",
        "export:export-first",
        "export:export-second",
        "consumer:export-first",
        "consumer:portable-copy",
        "export:export-first",
        "export:state-after-existing",
        "export:corrupted-output",
        "export:state-after-corrupt",
        "consumer:digest-drift",
        "consumer:unexpected-file",
        "consumer:manifest-less",
    ]
    assert events[4:22] == [f"0:{event}" for event in per_interpreter]
    assert events[22:] == [f"1:{event}" for event in per_interpreter]
    assert not owned.exists()


def test_prove_interpreter_accepts_executable_symlink_and_passes_resolved_target_to_uv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    proof = _load()
    authority = sys.modules["consumer_source_pack_proof"]
    root = tmp_path / "owned"
    root.mkdir()
    target = tmp_path / "python-real"
    target.write_text("#!/bin/sh\n")
    target.chmod(0o755)
    interpreter = tmp_path / "python"
    interpreter.symlink_to(target)
    commands: list[list[str]] = []

    def fake_run(
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
        timeout_seconds: float,
        max_stdout_bytes: int,
        max_stderr_bytes: int,
    ) -> object:
        del cwd, env, timeout_seconds, max_stdout_bytes, max_stderr_bytes
        argv = list(command)
        commands.append(argv)
        return authority.CommandResult(0 if argv[:2] == ["uv", "venv"] else 1, b"", b"")

    monkeypatch.setattr(proof, "run_bounded", fake_run)
    config = proof.ProofConfig(ROOT, (interpreter, interpreter), 10, 1024, 1024)
    with pytest.raises(proof.ControllerError, match="install_failed"):
        proof._prove_interpreter(config, root, tmp_path / "candidate.whl", interpreter, 0)
    assert commands[0] == [
        "uv",
        "venv",
        str(root / "venv-0"),
        "--python",
        str(target.resolve(strict=True)),
        "--no-python-downloads",
    ]


@pytest.mark.parametrize(
    "invalid_kind", ["missing", "dangling", "directory", "non-executable"]
)
def test_prove_interpreter_rejects_invalid_resolved_targets_before_uv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid_kind: str
) -> None:
    proof = _load()
    interpreter = tmp_path / "python"
    if invalid_kind == "dangling":
        interpreter.symlink_to(tmp_path / "missing-target")
    elif invalid_kind == "directory":
        target = tmp_path / "python-directory"
        target.mkdir()
        interpreter.symlink_to(target)
    elif invalid_kind == "non-executable":
        target = tmp_path / "python-non-executable"
        target.write_text("#!/bin/sh\n")
        target.chmod(0o644)
        interpreter.symlink_to(target)

    def unexpected_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("uv must not run for an invalid interpreter target")

    monkeypatch.setattr(proof, "run_bounded", unexpected_run)
    root = tmp_path / "owned"
    root.mkdir()
    config = proof.ProofConfig(ROOT, (interpreter, interpreter), 10, 1024, 1024)
    with pytest.raises(proof.ControllerError, match="environment_create_failed"):
        proof._prove_interpreter(config, root, tmp_path / "candidate.whl", interpreter, 0)


def test_tree_digest_real_slice_is_copy_stable_and_drift_sensitive(tmp_path: Path) -> None:
    proof = _load()
    first = tmp_path / "first"
    (first / "sources").mkdir(parents=True)
    (first / "evidence").mkdir()
    (first / "sources/a.md").write_bytes(b"markdown\n")
    (first / "evidence/a.jsonl").write_bytes(b'{"a":1}\n')
    (first / "export-manifest.json").write_bytes(b'{"manifest":true}\n')
    copied = tmp_path / "copied"
    shutil.copytree(first, copied)
    assert proof.tree_digest(first) == proof.tree_digest(copied)
    (copied / "sources/a.md").write_bytes(b"drift\n")
    assert proof.tree_digest(first) != proof.tree_digest(copied)


def test_corrupted_database_negative_changes_only_copied_provenance(tmp_path: Path) -> None:
    proof = _load()
    database = tmp_path / "copied.sqlite"
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "CREATE TABLE publications (publication_id TEXT, source_id TEXT, run_id TEXT)"
        )
        connection.execute(
            "INSERT INTO publications VALUES ('pub_aaaaaaaa', 'src_aaaaaaaa', 'run_aaaaaaaa')"
        )
        connection.commit()
    finally:
        connection.close()
    proof._corrupt_database_provenance(database)
    connection = sqlite3.connect(database)
    try:
        row = connection.execute(
            "SELECT publication_id, source_id, run_id FROM publications"
        ).fetchone()
    finally:
        connection.close()
    assert row == ("pub_aaaaaaaa", "src_" + "f" * 32, "run_aaaaaaaa")


def test_retained_receipt_is_canonical_closed_and_contains_no_local_path() -> None:
    proof = _load()
    digest = "a" * 64
    receipt = proof.retained_receipt(digest, source_count=2, evidence_count=3)
    assert set(receipt) == {
        "schema_version",
        "export_schema",
        "evidence_schema",
        "markdown_format",
        "source_count",
        "evidence_count",
        "proof_input_wheel_sha256",
    }
    assert receipt["schema_version"] == "mke.compiled_library_export_proof_receipt.v1"
    rendered = proof.canonical_json(receipt)
    assert json.loads(rendered) == receipt
    assert b"/Users/" not in rendered and b"/tmp/" not in rendered


def test_retained_publish_revalidates_copy_before_writing_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    proof = _load()
    root = tmp_path / "owned"
    (root / "retained-source/sources").mkdir(parents=True)
    (root / "retained-source/sources/a.md").write_bytes(b"a")
    (root / "workspace-0").mkdir()
    target = tmp_path / "retained"
    calls: list[Path] = []

    def validate(
        _config: object,
        _python: Path,
        _consumer: Path,
        export: Path,
        _pdf: Path,
        _video: Path,
        _env: object,
        *,
        success: bool,
    ) -> dict[str, object]:
        assert success is True
        assert not (target / "proof-receipt.json").exists()
        calls.append(export)
        return {}

    monkeypatch.setattr(proof, "_consumer_command", validate)
    config = proof.ProofConfig(ROOT, (Path("/312"), Path("/313")), 1, 100, 100, target)
    proof._publish_retained(
        config,
        root,
        {"proof_input_wheel_sha256": "a" * 64},
    )
    assert calls == [target / "compiled-library"]
    assert (target / "proof-receipt.json").is_file()


@pytest.mark.parametrize("cleanup_behavior", ["normal", "noop", "raise"])
def test_retained_publish_failure_removes_target_or_reports_cleanup_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cleanup_behavior: str,
) -> None:
    proof = _load()
    root = tmp_path / "owned"
    (root / "retained-source/sources").mkdir(parents=True)
    (root / "retained-source/sources/a.md").write_bytes(b"a")
    (root / "workspace-0").mkdir()
    target = tmp_path / "retained"

    def fail_validation(*_args: object, **_kwargs: object) -> object:
        raise proof.ControllerError("consumer_failed")

    monkeypatch.setattr(proof, "_consumer_command", fail_validation)
    if cleanup_behavior == "noop":
        monkeypatch.setattr(proof.shutil, "rmtree", lambda _path: None)
    elif cleanup_behavior == "raise":
        def fail_remove(_path: Path) -> None:
            raise OSError("cannot remove")

        monkeypatch.setattr(proof.shutil, "rmtree", fail_remove)
    config = proof.ProofConfig(ROOT, (Path("/312"), Path("/313")), 1, 100, 100, target)
    expected = "consumer_failed" if cleanup_behavior == "normal" else "cleanup_failed"
    with pytest.raises(proof.ControllerError, match=expected):
        proof._publish_retained(
            config,
            root,
            {"proof_input_wheel_sha256": "a" * 64},
        )
    if cleanup_behavior == "normal":
        assert not target.exists()
    else:
        assert target.exists()


def test_failure_envelope_is_closed_and_allowlisted(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--python",
            "/missing/312",
            "--python",
            "/missing/313",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    result = completed.stdout
    payload = json.loads(result)
    assert set(payload) == {"status", "code"}
    assert payload["status"] == "failed"
    assert payload["code"] in {
        "candidate_artifact_invalid",
        "wheel_build_failed",
        "environment_create_failed",
        "install_failed",
        "installed_identity_failed",
        "producer_failed",
        "consumer_failed",
        "cleanup_failed",
        "proof_failed",
    }
    assert str(tmp_path) not in result and "Traceback" not in result


def test_main_success_returns_zero_and_one_closed_aggregate(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    proof = _load()
    digest = "a" * 64
    aggregate = {
        "evidence_schema": "mke.evidence_ref.v1",
        "export_schema": "mke.compiled_library_export.v1",
        "interpreter_count": 2,
        "markdown_format": "mke.compiled_markdown.v1",
        "proof_input_wheel_sha256": digest,
        "schema_version": "mke.compiled_library_export_proof.v1",
        "status": "passed",
    }
    monkeypatch.setattr(proof, "run_proof", lambda _config: aggregate)
    assert proof.main(["--python", "/python312", "--python", "/python313", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == aggregate


def test_workflow_has_repository_scope_and_one_bounded_non_matrix_job() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    job = _job(workflow)
    assert "pull_request:" in workflow
    assert "push:\n    branches: [main]" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "concurrency:" in workflow and "cancel-in-progress: true" in workflow
    assert "runs-on: ubuntu-latest" in job
    assert "timeout-minutes: 15" in job
    assert "matrix:" not in job
    assert "upload-artifact" not in workflow
    assert "write" not in workflow
    assert "--retained-export" not in workflow


def test_primary_ci_python_job_has_twenty_minute_verification_budget() -> None:
    job = _primary_ci_python_job()
    assert re.findall(r"(?m)^    timeout-minutes: ([0-9]+)$", job) == ["20"]


def test_workflow_uses_only_pinned_actions_and_both_explicit_interpreters() -> None:
    job = _job()
    checkout = "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"
    setup_uv = "astral-sh/setup-uv@11f9893b081a58869d3b5fccaea48c9e9e46f990"
    setup_python = "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"
    assert job.count(checkout) == 1
    assert job.count(setup_uv) == 1
    assert job.count(setup_python) == 2
    assert 'python-version: "3.12"' in job
    assert 'python-version: "3.13"' in job
    assert job.count('${{ steps.python312.outputs.python-path }}') >= 2
    assert job.count('${{ steps.python313.outputs.python-path }}') >= 2
    uses = re.findall(r"(?m)^\s+- (?:id: [^\n]+\n\s+)?uses: ([^\s]+)", job)
    assert uses and all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", value) for value in uses)


def test_workflow_prewarms_online_then_runs_one_offline_proof() -> None:
    job = _job()
    prewarm = job.index("name: Provision locked cache for controller and both interpreters")
    execution = job.index("name: Run offline compiled Library export proof")
    assert prewarm < execution
    online = job[prewarm:execution]
    offline = job[execution:]
    assert "uv sync --locked" in online
    assert "uv export --locked --no-dev --no-emit-project" in online
    assert online.count("uv pip install") == 2
    assert "UV_OFFLINE" not in online
    assert 'UV_OFFLINE: "1"' in offline
    assert offline.count("scripts/compiled_library_export_proof.py") == 1
    assert "uv sync" not in offline
    assert "uv pip install" not in offline


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value + "\n  sibling:\n    runs-on: ubuntu-latest\n",
        lambda value: value.replace('python-version: "3.13"', 'python-version: "3.12"'),
        lambda value: value.replace(
            "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0",
            "actions/checkout@main",
        ),
        lambda value: value.replace('UV_OFFLINE: "1"', 'UV_OFFLINE: "0"'),
        lambda value: value + "\n      - uses: actions/upload-artifact@" + "a" * 40 + "\n",
        lambda value: value.replace("contents: read", "contents: write"),
    ],
)
def test_workflow_contract_detects_forbidden_mutations(mutate: Any) -> None:
    workflow = mutate(WORKFLOW.read_text(encoding="utf-8"))
    with pytest.raises(AssertionError):
        job = _job(workflow)
        assert "contents: read" in workflow and "contents: write" not in workflow
        assert "upload-artifact" not in workflow
        assert "actions/checkout@main" not in workflow
        assert job.count('python-version: "3.12"') == 1
        assert job.count('python-version: "3.13"') == 1
        assert 'UV_OFFLINE: "1"' in job


def test_unrelated_workflows_remain_byte_identical_to_head() -> None:
    for path in (CI_WORKFLOW, SOURCE_PACK_WORKFLOW):
        committed = subprocess_run_git_show(path)
        assert path.read_bytes() == committed


def subprocess_run_git_show(path: Path) -> bytes:
    return subprocess.run(
        ["git", "show", f"HEAD:{path.relative_to(ROOT)}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
