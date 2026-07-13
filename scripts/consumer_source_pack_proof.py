#!/usr/bin/env python3
"""Build and run the consumer source-pack proof in isolated environments."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, cast

_DIRTY_ENV = frozenset({"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"})
_DISTRIBUTION = "multimodal-knowledge-engine"
_READ_SIZE = 4096
_TERMINATION_GRACE_SECONDS = 0.5
_STABLE_FAILURE_CODES = frozenset(
    {
        "source_pack_manifest_invalid",
        "source_pack_identity_mismatch",
        "wheel_build_failed",
        "environment_create_failed",
        "install_failed",
        "installed_identity_failed",
        "external_isolation_failed",
        "consumer_schema_invalid",
        "consumer_payload_invalid",
        "manifest_mapping_missing",
        "manifest_mapping_ambiguous",
        "manifest_locator_mismatch",
        "observation_state_mismatch",
        "mcp_startup_timeout",
        "mcp_tool_timeout",
        "mcp_transport_failed",
        "server_exit_nonzero",
        "command_output_exceeded",
        "cleanup_failed",
        "proof_failed",
    }
)
_CLIENT_FAILURE_CODES = frozenset(
    {
        "source_pack_manifest_invalid",
        "source_pack_identity_mismatch",
        "consumer_schema_invalid",
        "consumer_payload_invalid",
        "manifest_mapping_missing",
        "manifest_mapping_ambiguous",
        "manifest_locator_mismatch",
        "observation_state_mismatch",
        "mcp_startup_timeout",
        "mcp_tool_timeout",
        "mcp_transport_failed",
        "command_output_exceeded",
        "cleanup_failed",
        "proof_failed",
    }
)
_CLIENT_FILES = (
    Path("scripts/consumer_source_pack_client.py"),
    Path("tests/fixtures/consumer-source-pack-v1/manifest.json"),
    Path("tests/fixtures/consumer-source-pack-v1/mcp-tool-schemas.json"),
    Path("tests/fixtures/local-knowledge-v1/operations-guide.pdf"),
    Path("tests/fixtures/local-knowledge-v1/incident-guide.pdf"),
)
_CLIENT_KEYS = frozenset(
    {
        "status",
        "manifest_schema",
        "evidence_schema",
        "pack_id",
        "source_count",
        "published_run_count",
        "active_publication_count",
        "active_evidence_count",
        "observed_states",
        "receipts",
        "strict_schema_validation",
        "search_ask_projection_equal",
        "exact_manifest_mapping",
        "fresh_store_mapping",
        "redaction",
        "server_cleanup",
    }
)
_EXPECTED_RECEIPTS = (
    {
        "schema_version": "mke.consumer_source_pack_receipt.v1",
        "manifest_schema": "mke.consumer_source_pack_manifest.v1",
        "pack_id": "local-knowledge-v1",
        "evidence_schema": "mke.evidence_ref.v1",
        "match_status": "matched",
        "query_role": "operations_guide",
        "source_key": "operations_guide",
        "content_fingerprint": (
            "sha256:0ac3e96efc89ee91e48bb3efc8611de88b2698e5aa26c1f8e0e8f78ad2d60ddd"
        ),
        "locator": {"kind": "page", "start": 1, "end": 1},
    },
    {
        "schema_version": "mke.consumer_source_pack_receipt.v1",
        "manifest_schema": "mke.consumer_source_pack_manifest.v1",
        "pack_id": "local-knowledge-v1",
        "evidence_schema": "mke.evidence_ref.v1",
        "match_status": "matched",
        "query_role": "incident_guide",
        "source_key": "incident_guide",
        "content_fingerprint": (
            "sha256:ed55cfbe9bdbf4404eb9ff55ab7e51fac14006ae0584a14d50704f68a02ff699"
        ),
        "locator": {"kind": "page", "start": 1, "end": 1},
    },
)


class ControllerError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: bytes
    stderr: bytes


@dataclass(frozen=True)
class ProofConfig:
    repository: Path
    python_interpreters: tuple[Path, Path]
    command_timeout_seconds: float
    max_stdout_bytes: int
    max_stderr_bytes: int


def isolated_environment(base: Mapping[str, str]) -> dict[str, str]:
    return {key: value for key, value in base.items() if key not in _DIRTY_ENV}


def _group_exists(pgid: int) -> bool:
    if os.name != "posix":
        return False
    try:
        os.killpg(pgid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _terminate(process: subprocess.Popen[bytes], pgid: int | None) -> None:
    try:
        if pgid is not None:
            os.killpg(pgid, signal.SIGTERM)
        elif process.poll() is None:
            process.terminate()
    except ProcessLookupError:
        pass
    except PermissionError:
        if process.poll() is None:
            process.terminate()
    deadline = time.monotonic() + _TERMINATION_GRACE_SECONDS
    while time.monotonic() < deadline:
        parent_done = process.poll() is not None
        group_done = pgid is None or not _group_exists(pgid)
        if parent_done and group_done:
            break
        time.sleep(0.01)
    if pgid is not None and _group_exists(pgid):
        try:
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    elif process.poll() is None:
        process.kill()
    try:
        process.wait(timeout=_TERMINATION_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=_TERMINATION_GRACE_SECONDS)


def run_bounded(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    timeout_seconds: float,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
) -> CommandResult:
    if timeout_seconds <= 0 or max_stdout_bytes < 0 or max_stderr_bytes < 0:
        raise ControllerError("proof_failed")
    try:
        process = subprocess.Popen(
            list(command),
            shell=False,
            cwd=cwd,
            env=dict(env),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=os.name == "posix",
        )
    except OSError as exc:
        raise ControllerError("command_could_not_start") from exc
    assert process.stdout is not None and process.stderr is not None
    pgid: int | None = process.pid if os.name == "posix" else None
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    limits = {"stdout": max_stdout_bytes, "stderr": max_stderr_bytes}
    terminal: list[tuple[str, float]] = []
    condition = threading.Condition()

    def drain(name: str, pipe: BinaryIO) -> None:
        while True:
            chunk = pipe.read(_READ_SIZE)
            if not chunk:
                return
            with condition:
                remaining = max(0, limits[name] - len(buffers[name]))
                buffers[name].extend(chunk[:remaining])
                if len(chunk) > remaining and not terminal:
                    terminal.append(("overflow", time.monotonic()))
                    condition.notify_all()

    readers = [
        threading.Thread(target=drain, args=("stdout", process.stdout), daemon=True),
        threading.Thread(target=drain, args=("stderr", process.stderr), daemon=True),
    ]
    for reader in readers:
        reader.start()
    deadline = time.monotonic() + timeout_seconds
    event: str | None = None
    while process.poll() is None:
        with condition:
            if terminal:
                event = terminal[0][0]
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                terminal.append(("timeout", time.monotonic()))
                event = "timeout"
                break
            condition.wait(timeout=min(remaining, 0.02))
    if event is not None:
        _terminate(process, pgid)
    else:
        process.wait()
    for reader in readers:
        reader.join(timeout=1)
    group_alive = _group_exists(process.pid) if os.name == "posix" else False
    if any(reader.is_alive() for reader in readers) or group_alive:
        _terminate(process, pgid)
        for reader in readers:
            reader.join(timeout=1)
    process.stdout.close()
    process.stderr.close()
    if process.poll() is None:
        _terminate(process, pgid)
        raise ControllerError("proof_failed")
    group_alive = _group_exists(process.pid) if os.name == "posix" else False
    if any(reader.is_alive() for reader in readers) or group_alive:
        raise ControllerError("proof_failed")
    if terminal and terminal[0][0] == "overflow":
        raise ControllerError("command_output_exceeded")
    if event == "overflow":
        raise ControllerError("command_output_exceeded")
    if event == "timeout":
        raise ControllerError("command_timed_out")
    return CommandResult(process.returncode, bytes(buffers["stdout"]), bytes(buffers["stderr"]))


def _within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _within_text(value: str, repository: Path) -> bool:
    return str(repository) in value or str(repository.resolve()) in value


def _command(
    code: str,
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    config: ProofConfig,
) -> CommandResult:
    try:
        result = run_bounded(
            command,
            cwd=cwd,
            env=env,
            timeout_seconds=config.command_timeout_seconds,
            max_stdout_bytes=config.max_stdout_bytes,
            max_stderr_bytes=config.max_stderr_bytes,
        )
    except ControllerError as exc:
        if exc.code == "command_output_exceeded":
            raise
        raise ControllerError(code) from exc
    if result.returncode != 0:
        raise ControllerError(code)
    return result


def _copy_inputs(repository: Path, workspace: Path) -> tuple[Path, Path, Path, Path]:
    copied: dict[Path, Path] = {}
    try:
        for relative in _CLIENT_FILES:
            source = repository / relative
            target = workspace / relative.name
            shutil.copyfile(source, target)
            copied[relative] = target
    except OSError as exc:
        raise ControllerError("external_isolation_failed") from exc
    source_root = workspace / "source-pack"
    source_root.mkdir()
    for relative in _CLIENT_FILES[-2:]:
        copied[relative].replace(source_root / relative.name)
    return (
        copied[_CLIENT_FILES[0]],
        copied[_CLIENT_FILES[1]],
        copied[_CLIENT_FILES[2]],
        source_root,
    )


def _validate_identity(payload: object, environment: Path, repository: Path) -> None:
    if not isinstance(payload, dict):
        raise ControllerError("installed_identity_failed")
    normalized = cast(dict[object, object], payload)
    expected_keys = (
        "mke_file",
        "metadata_path",
        "metadata_version",
        "module_version",
        "sys_executable",
        "mke_executable",
    )
    if set(normalized) != set(expected_keys) or not all(
        isinstance(value, str) for value in normalized.values()
    ):
        raise ControllerError("installed_identity_failed")
    path_keys = ("mke_file", "metadata_path", "sys_executable", "mke_executable")
    paths = [Path(cast(str, normalized[key])) for key in path_keys]
    if any(not path.is_absolute() for path in paths):
        raise ControllerError("installed_identity_failed")
    expected_python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    expected_mke = environment / ("Scripts/mke.exe" if os.name == "nt" else "bin/mke")
    if paths[2] != expected_python or paths[3] != expected_mke:
        raise ControllerError("installed_identity_failed")
    installed_paths = (paths[0], paths[1], paths[3])
    if any(
        not _within(path, environment) or _within(path, repository) for path in installed_paths
    ):
        raise ControllerError("installed_identity_failed")
    if "site-packages" not in paths[0].parts or ".dist-info" not in paths[1].name:
        raise ControllerError("installed_identity_failed")
    if (
        paths[2].resolve() != expected_python.resolve()
        or paths[3].resolve() != expected_mke.resolve()
    ):
        raise ControllerError("installed_identity_failed")
    metadata_version = cast(str, normalized["metadata_version"])
    module_version = cast(str, normalized["module_version"])
    if not metadata_version or metadata_version != module_version:
        raise ControllerError("installed_identity_failed")


def _validate_client(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ControllerError("proof_failed")
    normalized = cast(dict[object, object], payload)
    if not all(isinstance(key, str) for key in normalized):
        raise ControllerError("proof_failed")
    string_keys = cast(set[str], set(normalized))
    if string_keys != set(_CLIENT_KEYS):
        raise ControllerError("proof_failed")
    client = cast(dict[str, object], normalized)
    expected = {
        "status": "passed",
        "manifest_schema": "mke.consumer_source_pack_manifest.v1",
        "evidence_schema": "mke.evidence_ref.v1",
        "pack_id": "local-knowledge-v1",
        "source_count": 2,
        "published_run_count": 2,
        "active_publication_count": 2,
        "active_evidence_count": 2,
        "observed_states": ["empty", "active"],
        "strict_schema_validation": True,
        "search_ask_projection_equal": True,
        "exact_manifest_mapping": True,
        "fresh_store_mapping": True,
        "redaction": True,
        "server_cleanup": True,
    }
    if any(client.get(key) != value for key, value in expected.items()):
        raise ControllerError("proof_failed")
    receipts = client.get("receipts")
    if not isinstance(receipts, list) or receipts != list(_EXPECTED_RECEIPTS):
        raise ControllerError("proof_failed")
    return client


def _client_failure_code(stdout: bytes) -> str | None:
    try:
        payload_object: object = json.loads(stdout)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload_object, dict):
        return None
    payload = cast(dict[object, object], payload_object)
    if set(payload) != {"status", "code"}:
        return None
    if payload.get("status") != "failed":
        return None
    code = payload.get("code")
    if not isinstance(code, str) or code not in _CLIENT_FAILURE_CODES:
        return None
    return code


def run_proof(config: ProofConfig) -> dict[str, object]:
    repository = config.repository.resolve()
    if len(config.python_interpreters) != 2:
        raise ControllerError("proof_failed")
    root = Path(tempfile.mkdtemp(prefix="mke-consumer-source-pack-"))
    owned: list[Path] = [root]
    functional: dict[str, object] | None = None
    error: BaseException | None = None
    try:
        if _within(root, repository):
            raise ControllerError("external_isolation_failed")
        env = isolated_environment(os.environ)
        client_env = {
            key: value for key, value in env.items() if not _within_text(value, repository)
        }
        client_env["PWD"] = str(root)
        build_dir = root / "build"
        build_dir.mkdir()
        constraints = root / "constraints.txt"
        _command(
            "wheel_build_failed",
            ["uv", "build", "--wheel", "--out-dir", str(build_dir), str(repository)],
            cwd=root,
            env=env,
            config=config,
        )
        wheels = tuple(build_dir.glob("*.whl"))
        if len(wheels) != 1:
            raise ControllerError("wheel_build_failed")
        wheel = wheels[0]
        _command(
            "proof_failed",
            [
                "uv",
                "export",
                "--project",
                str(repository),
                "--locked",
                "--no-dev",
                "--no-emit-project",
                "--output-file",
                str(constraints),
            ],
            cwd=root,
            env=env,
            config=config,
        )
        results: list[dict[str, object]] = []
        for index, interpreter in enumerate(config.python_interpreters):
            environment = root / f"venv-{index}"
            workspace = root / f"workspace-{index}"
            workspace.mkdir()
            installed_python = environment / (
                "Scripts/python.exe" if os.name == "nt" else "bin/python"
            )
            installed_mke = environment / ("Scripts/mke.exe" if os.name == "nt" else "bin/mke")
            _command(
                "environment_create_failed",
                [
                    "uv",
                    "venv",
                    str(environment),
                    "--python",
                    str(interpreter),
                    "--no-python-downloads",
                ],
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
                    str(installed_python),
                    "--constraint",
                    str(constraints),
                    str(wheel),
                ],
                cwd=root,
                env=env,
                config=config,
            )
            probe = (
                "import importlib.metadata as m,json,mke,sys;"
                f"d=m.distribution('{_DISTRIBUTION}');"
                "print(json.dumps({'mke_file':mke.__file__,'metadata_path':str(d._path),"
                "'metadata_version':d.version,'module_version':mke.__version__,"
                "'sys_executable':sys.executable,"
                "'mke_executable':str(__import__('pathlib').Path(sys.executable).with_name('mke'))}))"
            )
            identity_result = _command(
                "installed_identity_failed",
                [str(installed_python), "-c", probe],
                cwd=root,
                env=env,
                config=config,
            )
            try:
                identity = json.loads(identity_result.stdout)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ControllerError("installed_identity_failed") from exc
            _validate_identity(identity, environment, repository)
            client, manifest, schemas, source_root = _copy_inputs(repository, workspace)
            if any(
                _within(path, repository)
                for path in (workspace, client, manifest, schemas, source_root)
            ):
                raise ControllerError("external_isolation_failed")
            try:
                client_result = run_bounded(
                    [
                        str(installed_python),
                        str(client),
                        "--manifest",
                        str(manifest),
                        "--schemas",
                        str(schemas),
                        "--source-root",
                        str(source_root),
                        "--mke",
                        str(installed_mke),
                        "--workspace",
                        str(workspace),
                        "--startup-timeout",
                        str(config.command_timeout_seconds),
                        "--tool-timeout",
                        str(config.command_timeout_seconds),
                        "--max-server-stderr-bytes",
                        str(config.max_stderr_bytes),
                    ],
                    cwd=workspace,
                    env=client_env,
                    timeout_seconds=config.command_timeout_seconds,
                    max_stdout_bytes=config.max_stdout_bytes,
                    max_stderr_bytes=config.max_stderr_bytes,
                )
            except ControllerError as exc:
                if exc.code == "command_output_exceeded":
                    raise
                raise ControllerError("proof_failed") from exc
            if client_result.returncode != 0:
                client_code = _client_failure_code(client_result.stdout)
                if client_code is not None:
                    raise ControllerError(client_code)
                raise ControllerError("server_exit_nonzero")
            try:
                client_payload = json.loads(client_result.stdout)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ControllerError("proof_failed") from exc
            results.append(_validate_client(client_payload))
        if results[0] != results[1]:
            raise ControllerError("proof_failed")
        functional = results[0]
    except BaseException as exc:
        error = exc
    finally:
        try:
            shutil.rmtree(root)
        except OSError:
            error = ControllerError("cleanup_failed")
        if any(path.exists() for path in owned):
            error = ControllerError("cleanup_failed")
    if error is not None:
        if isinstance(error, ControllerError):
            raise error
        raise ControllerError("proof_failed") from error
    assert functional is not None
    return {
        "proof": "consumer_source_pack",
        "status": "passed",
        **{
            key: functional[key]
            for key in (
                "manifest_schema",
                "evidence_schema",
                "pack_id",
                "source_count",
                "published_run_count",
                "active_publication_count",
                "active_evidence_count",
                "observed_states",
            )
        },
        "installed_identity": True,
        "external_isolation": True,
        **{
            key: functional[key]
            for key in (
                "strict_schema_validation",
                "search_ask_projection_equal",
                "exact_manifest_mapping",
                "fresh_store_mapping",
                "redaction",
            )
        },
        "cleanup": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", action="append", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--command-timeout", type=float, default=600.0)
    parser.add_argument("--max-stdout-bytes", type=int, default=2 * 1024 * 1024)
    parser.add_argument("--max-stderr-bytes", type=int, default=512 * 1024)
    args = parser.parse_args(argv)
    try:
        if len(args.python) != 2:
            raise ControllerError("proof_failed")
        result = run_proof(
            ProofConfig(
                Path(__file__).resolve().parents[1],
                tuple(args.python),
                args.command_timeout,
                args.max_stdout_bytes,
                args.max_stderr_bytes,
            )
        )
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except ControllerError as exc:
        code = exc.code if exc.code in _STABLE_FAILURE_CODES else "proof_failed"
        print(
            json.dumps(
                {"status": "failed", "code": code}, sort_keys=True, separators=(",", ":")
            )
        )
        return 1
    except Exception:
        print(
            json.dumps(
                {"status": "failed", "code": "proof_failed"}, sort_keys=True, separators=(",", ":")
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
