#!/usr/bin/env python3
"""Build and prove an isolated wheel-installed CLI and stdio MCP deployment."""

from __future__ import annotations

import argparse
import json
import os
import re
import select
import shutil
import subprocess
import tempfile
import time
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from mke.runtime import DEFAULT_MODEL_REVISION

_COMMAND_TIMEOUT_SECONDS = 180.0
_PROVIDER_TIMEOUT_SECONDS = 900.0
_MAX_STDOUT_BYTES = 2 * 1024 * 1024
_MAX_STDERR_BYTES = 512 * 1024
_CAPTURE_CHUNK_BYTES = 8192
_POLL_INTERVAL_SECONDS = 0.05
_REPORT_IDENTITY_FIELDS = (
    "provider",
    "model",
    "model_revision",
    "library_version",
    "device",
    "compute_type",
    "language",
    "model_source",
)
_SAFE_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.!_+()-]{0,255}\Z")
_MODEL_PART_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}\Z")
_COMMIT_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
_PYTHON_ENVIRONMENT_VARIABLES = ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")


class DeploymentProofError(RuntimeError):
    """Stable internal failure used by the redacted deployment report."""


@dataclass(frozen=True)
class DeploymentProofConfig:
    fixture: Path
    model_cache: Path | None
    python_version: str
    allow_model_download: bool = False
    provider_timeout_seconds: float = _PROVIDER_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if self.python_version not in {"3.12", "3.13"}:
            raise ValueError("python version must be 3.12 or 3.13")
        if self.provider_timeout_seconds <= 0:
            raise ValueError("provider timeout must be positive")


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: bytes
    stderr: bytes


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def select_built_wheel(root: Path) -> Path:
    wheels = sorted((root / "dist").glob("multimodal_knowledge_engine-*.whl"))
    if len(wheels) != 1:
        raise DeploymentProofError("built wheel selection failed")
    return wheels[0]


def run_deployment_proof(config: DeploymentProofConfig) -> dict[str, object]:
    root = repository_root().resolve()
    try:
        fixture = config.fixture.resolve(strict=True)
    except OSError as error:
        raise DeploymentProofError("deployment fixture is unavailable") from error
    if not fixture.is_file():
        raise DeploymentProofError("deployment fixture is unavailable")
    if config.model_cache is not None:
        model_cache = config.model_cache.resolve()
        if _is_within(model_cache, root):
            raise DeploymentProofError("model cache must be outside the repository")
    else:
        model_cache = None

    with tempfile.TemporaryDirectory(prefix="mke-transcription-deployment-") as temp_dir:
        runtime_root = Path(temp_dir).resolve()
        if _is_within(runtime_root, root):
            raise DeploymentProofError("temporary runtime must be outside the repository")
        environment = runtime_root / "venv"
        constraints = runtime_root / "constraints.txt"
        allowed_root = runtime_root / "allowed"
        allowed_root.mkdir()
        deployed_fixture = allowed_root / fixture.name
        shutil.copy2(fixture, deployed_fixture)

        run_command(
            ["uv", "build"],
            timeout_seconds=_COMMAND_TIMEOUT_SECONDS,
            max_stdout_bytes=_MAX_STDOUT_BYTES,
            max_stderr_bytes=_MAX_STDERR_BYTES,
            cwd=root,
        )
        run_command(
            [
                "uv",
                "export",
                "--locked",
                "--extra",
                "transcription",
                "--no-dev",
                "--no-emit-project",
                "--output-file",
                str(constraints),
            ],
            timeout_seconds=_COMMAND_TIMEOUT_SECONDS,
            max_stdout_bytes=_MAX_STDOUT_BYTES,
            max_stderr_bytes=_MAX_STDERR_BYTES,
            cwd=root,
        )
        run_command(
            [
                "uv",
                "venv",
                str(environment),
                "--python",
                config.python_version,
                "--no-python-downloads",
            ],
            timeout_seconds=_COMMAND_TIMEOUT_SECONDS,
            max_stdout_bytes=_MAX_STDOUT_BYTES,
            max_stderr_bytes=_MAX_STDERR_BYTES,
            cwd=root,
        )

        wheel = select_built_wheel(root)
        installed_python = environment / "bin" / "python"
        installed_mke = environment / "bin" / "mke"
        run_command(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(installed_python),
                "--constraint",
                str(constraints),
                f"{wheel}[transcription]",
            ],
            timeout_seconds=_COMMAND_TIMEOUT_SECONDS,
            max_stdout_bytes=_MAX_STDOUT_BYTES,
            max_stderr_bytes=_MAX_STDERR_BYTES,
            cwd=root,
        )

        runtime_environment = _isolated_runtime_environment()
        identity = _json_command(
            [
                str(installed_python),
                "-c",
                (
                    "import json, mke, sys; "
                    "print(json.dumps({'mke_file': mke.__file__, "
                    "'sys_executable': sys.executable}))"
                ),
            ],
            timeout_seconds=_COMMAND_TIMEOUT_SECONDS,
            cwd=runtime_root,
            env=runtime_environment,
        )
        validate_installed_identity(
            identity,
            environment=environment,
            repository=root,
        )

        runtime_args = _runtime_args(config, model_cache)
        doctor = _json_command(
            [
                str(installed_mke),
                "transcription",
                "doctor",
                *runtime_args,
                "--json",
            ],
            accepted_returncodes=frozenset({0, 1}),
            timeout_seconds=_COMMAND_TIMEOUT_SECONDS,
            cwd=runtime_root,
            env=runtime_environment,
        )
        if config.allow_model_download:
            if doctor.get("status") != "ready":
                _json_command(
                    [
                        str(installed_mke),
                        "transcription",
                        "prepare",
                        "--allow-model-download",
                        *runtime_args,
                        "--json",
                    ],
                    timeout_seconds=config.provider_timeout_seconds,
                    cwd=runtime_root,
                    env=runtime_environment,
                )
                doctor = _json_command(
                    [
                        str(installed_mke),
                        "transcription",
                        "doctor",
                        *runtime_args,
                        "--json",
                    ],
                    timeout_seconds=_COMMAND_TIMEOUT_SECONDS,
                    cwd=runtime_root,
                    env=runtime_environment,
                )
        if doctor.get("status") != "ready":
            raise DeploymentProofError("installed transcription runtime is not ready")

        cli_db = runtime_root / "cli.sqlite"
        cli_ingest = _json_command(
            [
                str(installed_mke),
                "--db",
                str(cli_db),
                "ingest",
                str(deployed_fixture),
                "--transcript-provider",
                "faster-whisper",
                *runtime_args,
                "--json",
            ],
            timeout_seconds=config.provider_timeout_seconds,
            cwd=runtime_root,
            env=runtime_environment,
        )
        run_id = _required_string(cli_ingest, "run_id")
        cli_run = _json_command(
            [
                str(installed_mke),
                "--db",
                str(cli_db),
                "run",
                "get",
                run_id,
                "--json",
            ],
            timeout_seconds=_COMMAND_TIMEOUT_SECONDS,
            cwd=runtime_root,
            env=runtime_environment,
        )
        search = run_command(
            [str(installed_mke), "--db", str(cli_db), "search", "evidence"],
            timeout_seconds=_COMMAND_TIMEOUT_SECONDS,
            max_stdout_bytes=_MAX_STDOUT_BYTES,
            max_stderr_bytes=_MAX_STDERR_BYTES,
            cwd=runtime_root,
            env=runtime_environment,
        )
        ask = run_command(
            [
                str(installed_mke),
                "--db",
                str(cli_db),
                "ask",
                "evidence",
                "publication",
            ],
            timeout_seconds=_COMMAND_TIMEOUT_SECONDS,
            max_stdout_bytes=_MAX_STDOUT_BYTES,
            max_stderr_bytes=_MAX_STDERR_BYTES,
            cwd=runtime_root,
            env=runtime_environment,
        )
        if b"timestamp_ms=" not in search.stdout or b"evidence" not in search.stdout.lower():
            raise DeploymentProofError("installed CLI Search proof failed")
        if b"answer_status=evidence_found" not in ask.stdout:
            raise DeploymentProofError("installed CLI Ask proof failed")

        cli_report = _required_report(cli_ingest)
        if cli_report != _required_report(cli_run):
            raise DeploymentProofError("installed CLI transcript report mismatch")

        mcp_db = runtime_root / "mcp.sqlite"
        client_command = [
            str(installed_python),
            "-m",
            "mke.proof.mcp_deployment_client",
            "--mke-command",
            str(installed_mke),
            "--fixture-name",
            deployed_fixture.name,
            "--db",
            str(mcp_db),
            "--allowed-root",
            str(allowed_root),
            *runtime_args,
        ]
        mcp = _json_command(
            client_command,
            timeout_seconds=config.provider_timeout_seconds + 60.0,
            cwd=runtime_root,
            env=runtime_environment,
        )
        if mcp.get("status") != "passed":
            raise DeploymentProofError("installed MCP proof failed")
        mcp_report = _required_report(mcp)
        identity = compare_report_identity(cli_report, mcp_report)

        evidence_count = cli_ingest.get("evidence_count")
        if (
            cli_ingest.get("ok") is not True
            or cli_ingest.get("run_state") != "published"
            or type(evidence_count) is not int
            or evidence_count <= 0
        ):
            raise DeploymentProofError("installed CLI ingest proof failed")
        return {
            "status": "passed",
            "python": config.python_version,
            "cli": {
                "run_state": "published",
                "evidence_count": evidence_count,
                "search_keyword_matched": True,
                "ask_status": "evidence_found",
            },
            "mcp": {
                "run_state": mcp.get("run_state"),
                "evidence_count": mcp.get("evidence_count"),
                "search_keyword_matched": mcp.get("search_keyword_matched"),
                "ask_status": mcp.get("ask_status"),
            },
            "report_identity": identity,
        }


def compare_report_identity(
    cli_report: Mapping[str, object],
    mcp_report: Mapping[str, object],
) -> dict[str, object]:
    cli_identity = {
        field: cli_report.get(field) for field in _REPORT_IDENTITY_FIELDS
    }
    mcp_identity = {
        field: mcp_report.get(field) for field in _REPORT_IDENTITY_FIELDS
    }
    if (
        any(value is None for value in cli_identity.values())
        or cli_identity != mcp_identity
        or not _is_public_report_identity(cli_identity)
    ):
        raise ValueError("CLI and MCP report identity mismatch")
    return cli_identity


def validate_installed_identity(
    identity: Mapping[str, object],
    *,
    environment: Path,
    repository: Path,
) -> None:
    module_value = identity.get("mke_file")
    executable_value = identity.get("sys_executable")
    if not isinstance(module_value, str) or not isinstance(executable_value, str):
        raise ValueError("installed package identity verification failed")
    module_path = Path(module_value)
    executable_path = Path(executable_value)
    if not module_path.is_absolute() or not executable_path.is_absolute():
        raise ValueError("installed package identity verification failed")
    resolved_environment = environment.resolve()
    resolved_repository = repository.resolve()
    resolved_module = module_path.resolve()
    normalized_executable = Path(os.path.abspath(executable_path))
    if (
        not _is_within(resolved_module, resolved_environment)
        or _is_within(resolved_module, resolved_repository)
        or not _is_within(normalized_executable, resolved_environment)
        or _is_within(normalized_executable, resolved_repository)
    ):
        raise ValueError("installed package identity verification failed")


def _isolated_runtime_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for variable in _PYTHON_ENVIRONMENT_VARIABLES:
        environment.pop(variable, None)
    return environment


def run_command(
    command: list[str],
    *,
    timeout_seconds: float,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    accepted_returncodes: frozenset[int] = frozenset({0}),
) -> CommandResult:
    """Run argv-only with timeout and hard stdout/stderr capture limits."""
    try:
        process = subprocess.Popen(
            command,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=env,
        )
    except OSError as error:
        raise DeploymentProofError("deployment command could not start") from error
    try:
        result = _read_bounded_output(
            process,
            timeout_seconds=timeout_seconds,
            max_stdout_bytes=max_stdout_bytes,
            max_stderr_bytes=max_stderr_bytes,
        )
    except BaseException:
        _kill_process(process)
        raise
    finally:
        if process.stdout is not None:
            with suppress(OSError):
                process.stdout.close()
        if process.stderr is not None:
            with suppress(OSError):
                process.stderr.close()
    if result.returncode not in accepted_returncodes:
        raise DeploymentProofError("deployment command failed")
    return result


def _read_bounded_output(
    process: subprocess.Popen[bytes],
    *,
    timeout_seconds: float,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
) -> CommandResult:
    if process.stdout is None or process.stderr is None:
        raise DeploymentProofError("deployment command capture failed")
    stdout = bytearray()
    stderr = bytearray()
    streams: dict[int, tuple[bytearray, int]] = {
        process.stdout.fileno(): (stdout, max_stdout_bytes),
        process.stderr.fileno(): (stderr, max_stderr_bytes),
    }
    for descriptor in streams:
        os.set_blocking(descriptor, False)
    deadline = time.monotonic() + timeout_seconds
    while streams:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise DeploymentProofError("deployment command timed out")
        ready, _, _ = select.select(
            list(streams),
            [],
            [],
            min(remaining, _POLL_INTERVAL_SECONDS),
        )
        for descriptor in ready:
            buffer, limit = streams[descriptor]
            read_size = min(_CAPTURE_CHUNK_BYTES, limit - len(buffer) + 1)
            if read_size <= 0:
                raise DeploymentProofError("deployment command output exceeded limit")
            try:
                chunk = os.read(descriptor, read_size)
            except BlockingIOError:
                continue
            if not chunk:
                del streams[descriptor]
                continue
            buffer.extend(chunk)
            if len(buffer) > limit:
                raise DeploymentProofError("deployment command output exceeded limit")
    return CommandResult(process.wait(), bytes(stdout), bytes(stderr))


def _kill_process(process: subprocess.Popen[bytes]) -> None:
    with suppress(OSError):
        if process.poll() is None:
            process.kill()
    with suppress(OSError, subprocess.TimeoutExpired):
        process.wait(timeout=1)


def _json_command(
    command: list[str],
    *,
    timeout_seconds: float,
    accepted_returncodes: frozenset[int] = frozenset({0}),
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, object]:
    result = run_command(
        command,
        timeout_seconds=timeout_seconds,
        max_stdout_bytes=_MAX_STDOUT_BYTES,
        max_stderr_bytes=_MAX_STDERR_BYTES,
        accepted_returncodes=accepted_returncodes,
        cwd=cwd,
        env=env,
    )
    try:
        payload = json.loads(result.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DeploymentProofError("deployment command returned invalid JSON") from error
    if not isinstance(payload, dict):
        raise DeploymentProofError("deployment command returned invalid JSON")
    return cast(dict[str, object], payload)


def _runtime_args(
    config: DeploymentProofConfig,
    model_cache: Path | None,
) -> list[str]:
    args = [
        "--model",
        "small",
        "--model-revision",
        DEFAULT_MODEL_REVISION,
        "--device",
        "cpu",
        "--compute-type",
        "int8",
        "--language",
        "auto",
        "--transcription-timeout-seconds",
        str(config.provider_timeout_seconds),
    ]
    if model_cache is not None:
        args.extend(("--model-cache", str(model_cache)))
    return args


def _required_string(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise DeploymentProofError("deployment result is missing an identifier")
    return value


def _required_report(payload: Mapping[str, object]) -> dict[str, object]:
    report = payload.get("transcript_intake_report")
    if not isinstance(report, dict):
        raise DeploymentProofError("deployment result is missing transcript report")
    return cast(dict[str, object], report)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _is_public_report_identity(identity: Mapping[str, object]) -> bool:
    if (
        identity.get("provider") != "faster-whisper"
        or identity.get("model_source") != "cache"
    ):
        return False
    model = identity.get("model")
    if not isinstance(model, str):
        return False
    if _SAFE_TOKEN_RE.fullmatch(model) is None:
        parts = model.split("/")
        if len(parts) != 2 or not all(
            _MODEL_PART_RE.fullmatch(part) for part in parts
        ):
            return False
    revision = identity.get("model_revision")
    if not isinstance(revision, str) or _COMMIT_SHA_RE.fullmatch(revision) is None:
        return False
    return all(
        isinstance(identity.get(field), str)
        and _SAFE_TOKEN_RE.fullmatch(cast(str, identity[field])) is not None
        for field in _REPORT_IDENTITY_FIELDS
        if field not in {"model", "model_revision"}
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="transcription_deployment_proof.py")
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--model-cache", type=Path)
    parser.add_argument("--python", choices=("3.12", "3.13"), default="3.12")
    parser.add_argument("--allow-model-download", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = run_deployment_proof(
            DeploymentProofConfig(
                fixture=args.fixture,
                model_cache=args.model_cache,
                python_version=args.python,
                allow_model_download=args.allow_model_download,
            )
        )
    except Exception:
        report = {"status": "failed", "reason": "deployment_proof_failed"}
        print(
            json.dumps(report, sort_keys=True)
            if args.json_output
            else "status=failed reason=deployment_proof_failed"
        )
        return 1
    print(
        json.dumps(report, sort_keys=True)
        if args.json_output
        else " ".join(f"{key}={value}" for key, value in report.items())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
