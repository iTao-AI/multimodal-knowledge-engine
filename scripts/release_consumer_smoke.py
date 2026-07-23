#!/usr/bin/env python3
"""Run the v0.1.4 installed-wheel consumer smoke outside the source checkout."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

EXPECTED_VERSION = "0.1.4"
_DISTRIBUTION_NAME = "multimodal-knowledge-engine"
_COMMAND_TIMEOUT_SECONDS = 600.0
_MAX_STDOUT_BYTES = 2 * 1024 * 1024
_MAX_STDERR_BYTES = 512 * 1024
_PYTHON_ENVIRONMENT_VARIABLES = ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")
_PUBLIC_FIXTURES = (
    Path("tests/fixtures/pdf/text-layer.pdf"),
    Path("tests/fixtures/pdf/text-layer-revised.pdf"),
    Path("tests/fixtures/video/short-audio.mp4"),
    Path("tests/fixtures/video/short-audio.mp4.mke-transcript.json"),
)
_PDF_FIXTURE = Path("tests/fixtures/pdf/text-layer.pdf")

_MCP_CONTRACT_CODE = r"""
import json
import sys
from pathlib import Path

from mke.interfaces.mcp_contract import (
    McpRuntimeConfig,
    ask_library,
    get_run,
    ingest_file,
    search_library,
)
from mke.runtime import RuntimeConfig

db = Path(sys.argv[1])
allowed_root = Path(sys.argv[2])
fixture = sys.argv[3]
config = McpRuntimeConfig(runtime=RuntimeConfig(db), allowed_root=allowed_root)
ingest = ingest_file(config, fixture)
if ingest.get("ok") is not True or ingest.get("run_state") != "published":
    raise SystemExit(1)
run_id = ingest.get("run_id")
if not isinstance(run_id, str) or not run_id:
    raise SystemExit(1)
run = get_run(config, run_id)
if run.get("ok") is not True or run.get("run", {}).get("state") != "published":
    raise SystemExit(1)
search = search_library(config, "publication active", 5)
if search.get("ok") is not True or not search.get("results"):
    raise SystemExit(1)
ask = ask_library(config, "publication active", 5)
if ask.get("ok") is not True or ask.get("answer_status") != "evidence_found":
    raise SystemExit(1)
print(json.dumps({
    "status": "passed",
    "run_state": "published",
    "evidence_count": ingest.get("evidence_count"),
    "search_keyword_matched": True,
    "ask_status": "evidence_found",
}, sort_keys=True))
"""


class ConsumerSmokeError(RuntimeError):
    """Stable internal failure used by the redacted consumer-smoke report."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ConsumerSmokeConfig:
    wheel: Path
    python: str = sys.executable


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: bytes
    stderr: bytes


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def run_consumer_smoke(config: ConsumerSmokeConfig) -> dict[str, object]:
    root = repository_root().resolve()
    wheel = _validate_wheel(config.wheel)

    with tempfile.TemporaryDirectory(prefix="mke-release-consumer-smoke-") as temp_dir:
        runtime_root = Path(temp_dir).resolve()
        if _is_within(runtime_root, root):
            raise ConsumerSmokeError("runtime_root_inside_repository")
        _copy_public_fixtures(root, runtime_root)

        environment = runtime_root / "venv"
        bin_dir = _venv_bin(environment)
        installed_python = bin_dir / "python"
        installed_mke = bin_dir / "mke"
        runtime_environment = _isolated_runtime_environment()

        _run_step(
            "venv_failed",
            [
                "uv",
                "venv",
                str(environment),
                "--python",
                config.python,
                "--no-python-downloads",
            ],
            cwd=runtime_root,
            env=runtime_environment,
        )
        _run_step(
            "install_failed",
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(installed_python),
                str(wheel),
            ],
            cwd=runtime_root,
            env=runtime_environment,
        )

        identity = _json_step(
            "installed_identity_failed",
            [
                str(installed_python),
                "-c",
                (
                    "import importlib.metadata as metadata, json, mke, sys; "
                    "print(json.dumps({'mke_file': mke.__file__, "
                    "'mke_version': mke.__version__, "
                    f"'metadata_version': metadata.version(\"{_DISTRIBUTION_NAME}\"), "
                    "'sys_executable': sys.executable}))"
                ),
            ],
            cwd=runtime_root,
            env=runtime_environment,
        )
        installed_version = validate_installed_identity(
            identity,
            environment=environment,
            repository=root,
        )

        proof = _run_step(
            "proof_failed",
            [str(installed_mke), "proof", "run"],
            cwd=runtime_root,
            env=runtime_environment,
        )
        if b"status=passed" not in proof.stdout:
            raise ConsumerSmokeError("proof_failed")

        demo = _run_step(
            "demo_failed",
            [str(installed_mke), "demo", "--verify"],
            cwd=runtime_root,
            env=runtime_environment,
        )
        if b"result=passed" not in demo.stdout:
            raise ConsumerSmokeError("demo_failed")

        cli = _run_cli_smoke(
            installed_mke,
            runtime_root=runtime_root,
            env=runtime_environment,
        )
        mcp = _run_mcp_contract_smoke(
            installed_python,
            runtime_root=runtime_root,
            env=runtime_environment,
        )

    return {
        "status": "passed",
        "version": installed_version,
        "identity": {
            "installed_site_packages": True,
            "venv_executable": True,
        },
        "steps": {
            "install": "passed",
            "identity": "passed",
            "proof": "passed",
            "demo": "passed",
            "cli": cli,
            "mcp": mcp,
        },
    }


def validate_installed_identity(
    identity: Mapping[str, object],
    *,
    environment: Path,
    repository: Path,
) -> str:
    module_value = identity.get("mke_file")
    module_version_value = identity.get("mke_version")
    metadata_version_value = identity.get("metadata_version")
    executable_value = identity.get("sys_executable")
    if (
        not isinstance(module_value, str)
        or not isinstance(module_version_value, str)
        or not isinstance(metadata_version_value, str)
        or not isinstance(executable_value, str)
    ):
        raise ConsumerSmokeError("installed_identity_failed")
    if module_version_value != EXPECTED_VERSION or metadata_version_value != EXPECTED_VERSION:
        raise ConsumerSmokeError("installed_identity_failed")
    module_path = Path(module_value)
    executable_path = Path(executable_value)
    if not module_path.is_absolute() or not executable_path.is_absolute():
        raise ConsumerSmokeError("installed_identity_failed")
    resolved_environment = environment.resolve()
    resolved_repository = repository.resolve()
    resolved_module = module_path.resolve()
    resolved_executable = Path(os.path.abspath(executable_path))
    if (
        not _is_within(resolved_module, resolved_environment)
        or not _is_within(resolved_executable, resolved_environment)
        or _is_within(resolved_module, resolved_repository)
        or _is_within(resolved_executable, resolved_repository)
        or "site-packages" not in resolved_module.parts
    ):
        raise ConsumerSmokeError("installed_identity_failed")
    return module_version_value


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
    try:
        result = subprocess.run(
            command,
            shell=False,
            cwd=cwd,
            env=env,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ConsumerSmokeError("command_timed_out") from error
    except OSError as error:
        raise ConsumerSmokeError("command_could_not_start") from error
    stdout = result.stdout
    stderr = result.stderr
    if len(stdout) > max_stdout_bytes or len(stderr) > max_stderr_bytes:
        raise ConsumerSmokeError("command_output_exceeded")
    if result.returncode not in accepted_returncodes:
        raise ConsumerSmokeError("command_failed")
    return CommandResult(result.returncode, stdout, stderr)


def _run_cli_smoke(
    installed_mke: Path,
    *,
    runtime_root: Path,
    env: dict[str, str],
) -> str:
    db = runtime_root / "consumer-cli.sqlite"
    fixture = runtime_root / _PDF_FIXTURE
    ingest = _json_step(
        "cli_ingest_failed",
        [
            str(installed_mke),
            "--db",
            str(db),
            "ingest",
            str(fixture),
            "--json",
        ],
        cwd=runtime_root,
        env=env,
    )
    if (
        ingest.get("ok") is not True
        or ingest.get("run_state") != "published"
        or type(ingest.get("evidence_count")) is not int
        or cast(int, ingest["evidence_count"]) <= 0
    ):
        raise ConsumerSmokeError("cli_ingest_failed")
    search = _run_step(
        "cli_search_failed",
        [str(installed_mke), "--db", str(db), "search", "publication", "active"],
        cwd=runtime_root,
        env=env,
    )
    if b"page=2" not in search.stdout:
        raise ConsumerSmokeError("cli_search_failed")
    ask = _run_step(
        "cli_ask_failed",
        [str(installed_mke), "--db", str(db), "ask", "publication", "active"],
        cwd=runtime_root,
        env=env,
    )
    if b"answer_status=evidence_found" not in ask.stdout:
        raise ConsumerSmokeError("cli_ask_failed")
    return "passed"


def _run_mcp_contract_smoke(
    installed_python: Path,
    *,
    runtime_root: Path,
    env: dict[str, str],
) -> str:
    payload = _json_step(
        "mcp_contract_failed",
        [
            str(installed_python),
            "-c",
            _MCP_CONTRACT_CODE,
            str(runtime_root / "consumer-mcp.sqlite"),
            str(runtime_root),
            str(_PDF_FIXTURE),
        ],
        cwd=runtime_root,
        env=env,
    )
    if payload.get("status") != "passed" or payload.get("ask_status") != "evidence_found":
        raise ConsumerSmokeError("mcp_contract_failed")
    return "passed"


def _run_step(
    code: str,
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> CommandResult:
    try:
        return run_command(
            command,
            timeout_seconds=_COMMAND_TIMEOUT_SECONDS,
            max_stdout_bytes=_MAX_STDOUT_BYTES,
            max_stderr_bytes=_MAX_STDERR_BYTES,
            cwd=cwd,
            env=env,
        )
    except ConsumerSmokeError as error:
        raise ConsumerSmokeError(code, error.code) from error


def _json_step(
    code: str,
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> dict[str, object]:
    result = _run_step(code, command, cwd=cwd, env=env)
    try:
        payload = json.loads(result.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConsumerSmokeError(code) from error
    if not isinstance(payload, dict):
        raise ConsumerSmokeError(code)
    return cast(dict[str, object], payload)


def _validate_wheel(wheel: Path) -> Path:
    try:
        resolved = wheel.resolve(strict=True)
    except OSError as error:
        raise ConsumerSmokeError("wheel_unavailable") from error
    if not resolved.is_file():
        raise ConsumerSmokeError("wheel_unavailable")
    if resolved.suffix != ".whl":
        raise ConsumerSmokeError("wheel_invalid")
    return resolved


def _copy_public_fixtures(root: Path, runtime_root: Path) -> None:
    for relative in _PUBLIC_FIXTURES:
        source = root / relative
        if not source.is_file():
            raise ConsumerSmokeError("fixture_unavailable")
        target = runtime_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _isolated_runtime_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for variable in _PYTHON_ENVIRONMENT_VARIABLES:
        environment.pop(variable, None)
    return environment


def _venv_bin(environment: Path) -> Path:
    return environment / ("Scripts" if os.name == "nt" else "bin")


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="release_consumer_smoke.py")
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = run_consumer_smoke(
            ConsumerSmokeConfig(wheel=args.wheel, python=args.python)
        )
    except ConsumerSmokeError as error:
        report = {"status": "failed", "code": error.code}
        print(
            json.dumps(report, sort_keys=True)
            if args.json_output
            else f"status=failed code={error.code}"
        )
        return 1
    except Exception:
        report = {"status": "failed", "code": "consumer_smoke_failed"}
        print(
            json.dumps(report, sort_keys=True)
            if args.json_output
            else "status=failed code=consumer_smoke_failed"
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
