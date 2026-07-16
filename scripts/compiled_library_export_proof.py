#!/usr/bin/env python3
"""Prove installed-wheel compiled Library export portability."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import sys
import tempfile
import tomllib
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

_SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(_SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIRECTORY))

from consumer_source_pack_proof import (  # noqa: E402, I001
    ControllerError as ProcessControllerError,
    _candidate_source_snapshot,  # pyright: ignore[reportPrivateUsage]
    _clean_sha1_source_commit,  # pyright: ignore[reportPrivateUsage]
    isolated_environment,
    run_bounded,
)

_DISTRIBUTION = "multimodal-knowledge-engine"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_FAILURE_CODES = frozenset(
    {
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
)
_CONSUMER_SUCCESS = {
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


class ControllerError(RuntimeError):
    def __init__(self, code: str) -> None:
        if code not in _FAILURE_CODES:
            code = "proof_failed"
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ProofConfig:
    repository: Path
    python_interpreters: tuple[Path, Path]
    command_timeout_seconds: float
    max_stdout_bytes: int
    max_stderr_bytes: int
    retained_export: Path | None = None


@dataclass(frozen=True)
class InterpreterResult:
    interpreter: str
    proof_input_wheel_sha256: str
    source_count: int
    evidence_count: int


def canonical_json(value: Mapping[str, object]) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def retained_receipt(
    wheel_sha256: str, *, source_count: int, evidence_count: int
) -> dict[str, object]:
    if (
        _SHA256.fullmatch(wheel_sha256) is None
        or source_count != 2
        or evidence_count != 3
    ):
        raise ControllerError("proof_failed")
    return {
        "schema_version": "mke.compiled_library_export_proof_receipt.v1",
        "export_schema": "mke.compiled_library_export.v1",
        "evidence_schema": "mke.evidence_ref.v1",
        "markdown_format": "mke.compiled_markdown.v1",
        "source_count": source_count,
        "evidence_count": evidence_count,
        "proof_input_wheel_sha256": wheel_sha256,
    }


def aggregate_results(results: Sequence[InterpreterResult]) -> dict[str, object]:
    if (
        len(results) != 2
        or {item.interpreter for item in results} != {"3.12", "3.13"}
        or len({item.proof_input_wheel_sha256 for item in results}) != 1
        or any(
            _SHA256.fullmatch(item.proof_input_wheel_sha256) is None
            or item.source_count != 2
            or item.evidence_count != 3
            for item in results
        )
    ):
        raise ControllerError("proof_failed")
    return {
        "evidence_schema": "mke.evidence_ref.v1",
        "export_schema": "mke.compiled_library_export.v1",
        "interpreter_count": 2,
        "markdown_format": "mke.compiled_markdown.v1",
        "proof_input_wheel_sha256": results[0].proof_input_wheel_sha256,
        "schema_version": "mke.compiled_library_export_proof.v1",
        "status": "passed",
    }


def _command(
    code: str,
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    config: ProofConfig,
    success: bool = True,
) -> tuple[bytes, bytes]:
    try:
        result = run_bounded(
            command,
            cwd=cwd,
            env=env,
            timeout_seconds=config.command_timeout_seconds,
            max_stdout_bytes=config.max_stdout_bytes,
            max_stderr_bytes=config.max_stderr_bytes,
        )
    except ProcessControllerError as exc:
        raise ControllerError(code) from exc
    if (result.returncode == 0) is not success:
        raise ControllerError(code)
    return result.stdout, result.stderr


def _candidate_source(config: ProofConfig, root: Path) -> Path:
    repository = config.repository.resolve()
    try:
        commit = _clean_sha1_source_commit(repository)
        return _candidate_source_snapshot(
            repository, commit, root, config.command_timeout_seconds
        )
    except ProcessControllerError as exc:
        raise ControllerError("candidate_artifact_invalid") from exc


def _wheel_metadata(wheel: Path) -> tuple[str, str]:
    try:
        with zipfile.ZipFile(wheel) as archive:
            names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
            if len(names) != 1:
                raise ControllerError("candidate_artifact_invalid")
            metadata = archive.read(names[0]).decode("utf-8", errors="strict")
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile, KeyError) as exc:
        raise ControllerError("candidate_artifact_invalid") from exc
    fields: dict[str, str] = {}
    for line in metadata.splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            fields.setdefault(key, value)
    name = fields.get("Name", "")
    version = fields.get("Version", "")
    if name != _DISTRIBUTION or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", version):
        raise ControllerError("candidate_artifact_invalid")
    expected = re.compile(
        rf"multimodal_knowledge_engine-{re.escape(version)}-[A-Za-z0-9_.-]+\.whl\Z"
    )
    if expected.fullmatch(wheel.name) is None:
        raise ControllerError("candidate_artifact_invalid")
    return name, version


def _build_candidate(config: ProofConfig, root: Path) -> tuple[Path, str]:
    source = _candidate_source(config, root)
    build = root / "wheel"
    build.mkdir()
    env = isolated_environment(os.environ)
    _command(
        "wheel_build_failed",
        ["uv", "build", "--wheel", "--out-dir", str(build), str(source)],
        cwd=root,
        env=env,
        config=config,
    )
    wheels = tuple(build.glob("*.whl"))
    if len(wheels) != 1 or wheels[0].is_symlink():
        raise ControllerError("wheel_build_failed")
    wheel = wheels[0]
    try:
        project = tomllib.loads((source / "pyproject.toml").read_text(encoding="utf-8"))[
            "project"
        ]
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        raise ControllerError("candidate_artifact_invalid") from exc
    metadata_name, metadata_version = _wheel_metadata(wheel)
    if project.get("name") != metadata_name or project.get("version") != metadata_version:
        raise ControllerError("candidate_artifact_invalid")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    if _SHA256.fullmatch(digest) is None:
        raise ControllerError("candidate_artifact_invalid")
    _command(
        "wheel_build_failed",
        [
            "uv",
            "export",
            "--project",
            str(source),
            "--locked",
            "--no-dev",
            "--no-emit-project",
            "--output-file",
            str(root / "constraints.txt"),
        ],
        cwd=root,
        env=env,
        config=config,
    )
    return wheel, digest


def tree_digest(root: Path) -> str:
    entries: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        value = os.lstat(path)
        relative = path.relative_to(root).as_posix()
        if stat.S_ISDIR(value.st_mode):
            entries.append((relative + "/", "directory"))
        elif stat.S_ISREG(value.st_mode):
            entries.append((relative, hashlib.sha256(path.read_bytes()).hexdigest()))
        else:
            raise ControllerError("consumer_failed")
    return hashlib.sha256(canonical_json({"entries": entries})).hexdigest()


def _payload(stdout: bytes, code: str) -> dict[str, object]:
    try:
        value: object = json.loads(stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ControllerError(code) from exc
    if type(value) is not dict:
        raise ControllerError(code)
    return cast(dict[str, object], value)


def _consumer_command(
    config: ProofConfig,
    python: Path,
    consumer: Path,
    export: Path,
    pdf: Path,
    video: Path,
    env: Mapping[str, str],
    *,
    success: bool,
) -> dict[str, object]:
    stdout, _ = _command(
        "consumer_failed",
        [
            str(python),
            str(consumer),
            "--export",
            str(export),
            "--source",
            f"operations-guide={pdf}",
            "--source",
            f"spoken-evidence={video}",
            "--json",
        ],
        cwd=export.parent,
        env=env,
        config=config,
        success=success,
    )
    payload = _payload(stdout, "consumer_failed")
    if success and payload != _CONSUMER_SUCCESS:
        raise ControllerError("consumer_failed")
    if not success and set(payload) != {"status", "code"}:
        raise ControllerError("consumer_failed")
    return payload


def _copy_fixture(source: Path, target: Path) -> None:
    if source.is_symlink() or not source.is_file() or target.exists():
        raise ControllerError("proof_failed")
    shutil.copyfile(source, target)


def _manifest_identity(export: Path) -> tuple[object, object]:
    value = _payload((export / "export-manifest.json").read_bytes(), "producer_failed")
    return value.get("observation"), value.get("sources")


def _corrupt_database_provenance(database: Path) -> None:
    try:
        connection = sqlite3.connect(database)
        try:
            cursor = connection.execute(
                "UPDATE publications SET source_id = ? "
                "WHERE publication_id = ("
                "SELECT publication_id FROM publications ORDER BY publication_id LIMIT 1)",
                ("src_" + "f" * 32,),
            )
            connection.commit()
            if cursor.rowcount != 1:
                raise ControllerError("proof_failed")
        finally:
            connection.close()
    except (OSError, sqlite3.Error) as exc:
        raise ControllerError("proof_failed") from exc


def _prove_interpreter(
    config: ProofConfig,
    root: Path,
    wheel: Path,
    interpreter: Path,
    index: int,
) -> InterpreterResult:
    if not interpreter.is_file() or interpreter.is_symlink() or not os.access(interpreter, os.X_OK):
        raise ControllerError("environment_create_failed")
    environment = root / f"venv-{index}"
    workspace = root / f"workspace-{index}"
    workspace.mkdir()
    env = isolated_environment(os.environ)
    env["PWD"] = str(workspace)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    mke = environment / ("Scripts/mke.exe" if os.name == "nt" else "bin/mke")
    _command(
        "environment_create_failed",
        ["uv", "venv", str(environment), "--python", str(interpreter), "--no-python-downloads"],
        cwd=root,
        env=env,
        config=config,
    )
    _command(
        "install_failed",
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python),
            "--constraint",
            str(root / "constraints.txt"),
            str(wheel),
        ],
        cwd=root,
        env=env,
        config=config,
    )
    _command(
        "install_failed",
        ["uv", "pip", "check", "--python", str(python)],
        cwd=root,
        env=env,
        config=config,
    )
    doctor = (
        "import importlib.metadata as d,json,mke,sys;"
        "x=d.distribution('multimodal-knowledge-engine');"
        "print(json.dumps({'module':mke.__file__,'metadata':str(x._path),"
        "'version':x.version,'python':sys.executable}))"
    )
    stdout, _ = _command(
        "installed_identity_failed",
        [str(python), "-c", doctor],
        cwd=workspace,
        env=env,
        config=config,
    )
    identity = _payload(stdout, "installed_identity_failed")
    if set(identity) != {"module", "metadata", "version", "python"}:
        raise ControllerError("installed_identity_failed")
    for key in ("module", "metadata", "python"):
        value = identity[key]
        if type(value) is not str or not Path(value).is_absolute():
            raise ControllerError("installed_identity_failed")
        if key != "python" and environment.resolve() not in Path(value).resolve().parents:
            raise ControllerError("installed_identity_failed")
    if Path(cast(str, identity["python"])).resolve() != python.resolve():
        raise ControllerError("installed_identity_failed")
    version_stdout, _ = _command(
        "installed_identity_failed",
        [
            str(python),
            "-c",
            "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')",
        ],
        cwd=workspace,
        env=env,
        config=config,
    )
    try:
        minor = version_stdout.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise ControllerError("installed_identity_failed") from exc
    if minor not in {"3.12", "3.13"}:
        raise ControllerError("installed_identity_failed")

    pdf = workspace / "operations-guide.pdf"
    video = workspace / "spoken-evidence.mp4"
    sidecar = workspace / "spoken-evidence.mp4.mke-transcript.json"
    consumer = workspace / "compiled_library_export_consumer.py"
    _copy_fixture(config.repository / "tests/fixtures/local-knowledge-v1/operations-guide.pdf", pdf)
    _copy_fixture(config.repository / "tests/fixtures/video/spoken-evidence.mp4", video)
    _copy_fixture(
        config.repository / "tests/fixtures/video/short-audio.mp4.mke-transcript.json", sidecar
    )
    _copy_fixture(config.repository / "scripts/compiled_library_export_consumer.py", consumer)
    database = workspace / "library.sqlite"
    for source in (pdf, video):
        _command(
            "producer_failed",
            [str(mke), "--db", str(database), "ingest", str(source), "--json"],
            cwd=workspace,
            env=env,
            config=config,
        )
    exports: list[Path] = []

    def export(name: str, database_path: Path = database, *, success: bool = True) -> Path:
        target = workspace / name
        _command(
            "producer_failed",
            [str(mke), "--db", str(database_path), "library", "export", "--output", name, "--json"],
            cwd=workspace,
            env=env,
            config=config,
            success=success,
        )
        if success:
            exports.append(target)
        return target

    first = export("export-first")
    second = export("export-second")
    if tree_digest(first) != tree_digest(second):
        raise ControllerError("producer_failed")
    _consumer_command(config, python, consumer, first, pdf, video, env, success=True)
    portable = workspace / "portable-copy"
    shutil.copytree(first, portable)
    _consumer_command(config, python, consumer, portable, pdf, video, env, success=True)

    before = _manifest_identity(first)
    export("export-first", success=False)
    after_existing = export("state-after-existing")
    if _manifest_identity(after_existing) != before:
        raise ControllerError("producer_failed")
    corrupted = workspace / "corrupted.sqlite"
    shutil.copyfile(database, corrupted)
    _corrupt_database_provenance(corrupted)
    export("corrupted-output", corrupted, success=False)
    after_corrupt = export("state-after-corrupt")
    if _manifest_identity(after_corrupt) != before:
        raise ControllerError("producer_failed")

    digest_drift = workspace / "digest-drift"
    shutil.copytree(first, digest_drift)
    evidence_file = next((digest_drift / "evidence").iterdir())
    evidence_file.write_bytes(evidence_file.read_bytes() + b"x")
    _consumer_command(config, python, consumer, digest_drift, pdf, video, env, success=False)
    unexpected = workspace / "unexpected-file"
    shutil.copytree(first, unexpected)
    (unexpected / "unexpected").write_bytes(b"x")
    _consumer_command(config, python, consumer, unexpected, pdf, video, env, success=False)
    partial = workspace / "manifest-less"
    shutil.copytree(first, partial)
    (partial / "export-manifest.json").unlink()
    _consumer_command(config, python, consumer, partial, pdf, video, env, success=False)

    if index == 0:
        shutil.copytree(first, root / "retained-source")
    return InterpreterResult(
        minor,
        hashlib.sha256(wheel.read_bytes()).hexdigest(),
        source_count=2,
        evidence_count=3,
    )


def _copy_tree_regular(source: Path, target: Path) -> None:
    if target.exists() or target.is_symlink():
        raise ControllerError("proof_failed")
    target.mkdir()
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        value = os.lstat(path)
        destination = target / relative
        if stat.S_ISDIR(value.st_mode):
            destination.mkdir()
        elif stat.S_ISREG(value.st_mode):
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            source_fd = os.open(path, flags)
            try:
                opened = os.fstat(source_fd)
                if (opened.st_dev, opened.st_ino) != (value.st_dev, value.st_ino):
                    raise ControllerError("proof_failed")
                data = bytearray()
                while True:
                    chunk = os.read(source_fd, 64 * 1024)
                    if not chunk:
                        break
                    data.extend(chunk)
            finally:
                os.close(source_fd)
            destination_fd = os.open(
                destination,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            try:
                view = memoryview(data)
                offset = 0
                while offset < len(view):
                    written = os.write(destination_fd, view[offset:])
                    if written <= 0:
                        raise ControllerError("proof_failed")
                    offset += written
            finally:
                os.close(destination_fd)
        else:
            raise ControllerError("proof_failed")


def _remove_retained_target(target: Path) -> None:
    try:
        shutil.rmtree(target)
    except OSError as exc:
        raise ControllerError("cleanup_failed") from exc
    if target.exists() or target.is_symlink():
        raise ControllerError("cleanup_failed")


def _publish_retained(config: ProofConfig, root: Path, aggregate: Mapping[str, object]) -> None:
    target = config.retained_export
    if target is None:
        return
    if target.exists() or target.is_symlink() or target.name in {"", ".", ".."}:
        raise ControllerError("proof_failed")
    source = root / "retained-source"
    created = False
    try:
        target.mkdir()
        created = True
        _copy_tree_regular(source, target / "compiled-library")
        if tree_digest(source) != tree_digest(target / "compiled-library"):
            raise ControllerError("proof_failed")
        workspace = root / "workspace-0"
        environment = root / "venv-0"
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        validation_env = isolated_environment(os.environ)
        validation_env["PWD"] = str(target)
        _consumer_command(
            config,
            python,
            workspace / "compiled_library_export_consumer.py",
            target / "compiled-library",
            workspace / "operations-guide.pdf",
            workspace / "spoken-evidence.mp4",
            validation_env,
            success=True,
        )
        receipt = retained_receipt(
            cast(str, aggregate["proof_input_wheel_sha256"]), source_count=2, evidence_count=3
        )
        (target / "proof-receipt.json").write_bytes(canonical_json(receipt))
    except BaseException as exc:
        if created:
            try:
                _remove_retained_target(target)
            except ControllerError as cleanup_error:
                raise cleanup_error from exc
        if isinstance(exc, ControllerError):
            raise
        raise ControllerError("proof_failed") from exc


def run_proof(config: ProofConfig) -> dict[str, object]:
    if len(config.python_interpreters) != 2:
        raise ControllerError("proof_failed")
    paths = tuple(path.resolve() for path in config.python_interpreters)
    if paths[0] == paths[1]:
        raise ControllerError("proof_failed")
    root = Path(tempfile.mkdtemp(prefix="mke-compiled-library-export-"))
    root.mkdir(parents=True, exist_ok=True)
    error: BaseException | None = None
    aggregate: dict[str, object] | None = None
    try:
        wheel, _digest = _build_candidate(config, root)
        results = [
            _prove_interpreter(config, root, wheel, interpreter, index)
            for index, interpreter in enumerate(config.python_interpreters)
        ]
        aggregate = aggregate_results(results)
        _publish_retained(config, root, aggregate)
    except BaseException as exc:
        error = exc
    finally:
        try:
            shutil.rmtree(root)
        except OSError:
            error = ControllerError("cleanup_failed")
        if root.exists():
            error = ControllerError("cleanup_failed")
    if error is not None:
        if isinstance(error, ControllerError):
            raise error
        raise ControllerError("proof_failed") from error
    assert aggregate is not None
    return aggregate


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", action="append", type=Path, required=True)
    parser.add_argument("--retained-export", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    args = parser.parse_args(argv)
    try:
        if len(args.python) != 2:
            raise ControllerError("proof_failed")
        result = run_proof(
            ProofConfig(
                Path(__file__).resolve().parents[1],
                tuple(args.python),
                args.timeout_seconds,
                1024 * 1024,
                1024 * 1024,
                args.retained_export,
            )
        )
        exit_code = 0
    except ControllerError as exc:
        result = {"status": "failed", "code": exc.code}
        exit_code = 1
    except BaseException:
        result = {"status": "failed", "code": "proof_failed"}
        exit_code = 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
