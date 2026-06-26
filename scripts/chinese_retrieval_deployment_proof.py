#!/usr/bin/env python3
"""Prove the Chinese retrieval evaluator from an isolated offline wheel."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

_STEP_TIMEOUT_SECONDS = 120.0
_TOTAL_TIMEOUT_SECONDS = 180.0
_OUTPUT_LIMIT_BYTES = 64 * 1024
_PYTHON_ENVIRONMENT_VARIABLES = ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")


@dataclass(frozen=True)
class DeploymentProofConfig:
    wheel: Path
    protocol: Path
    python_version: str
    installed_environment: Path | None = None

    def __post_init__(self) -> None:
        if self.python_version not in {"3.12", "3.13"}:
            raise ValueError("python version must be 3.12 or 3.13")
        if not self.wheel.is_file() or self.wheel.suffix != ".whl":
            raise ValueError("wheel must be an existing .whl file")
        if not self.protocol.is_file() or self.protocol.suffix != ".json":
            raise ValueError("protocol must be an existing JSON file")
        if self.installed_environment is not None:
            environment = self.installed_environment
            if not environment.is_dir():
                raise ValueError("installed environment must be an existing venv")
            if not (environment / "bin" / "python").is_file() or not (
                environment / "bin" / "mke"
            ).is_file():
                raise ValueError("installed environment must contain python and mke")


def isolated_runtime_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for name in _PYTHON_ENVIRONMENT_VARIABLES:
        environment.pop(name, None)
    environment["UV_OFFLINE"] = "1"
    return environment


def wheel_install_command(
    python: Path,
    wheel: Path,
    constraints: Path,
) -> tuple[str, ...]:
    return (
        "uv",
        "pip",
        "install",
        "--offline",
        "--python",
        str(python),
        "--constraint",
        str(constraints),
        str(wheel),
    )


def validate_installed_identity(
    identity: Mapping[str, object],
    *,
    environment: Path,
    repository: Path,
) -> None:
    module_file = identity.get("mke_file")
    executable = identity.get("sys_executable")
    if not isinstance(module_file, str) or not isinstance(executable, str):
        raise ValueError("installed package identity verification failed")
    module_path = Path(module_file).resolve()
    environment_path = environment.resolve()
    executable_path = Path(executable).absolute()
    expected_executable = (environment / "bin" / "python").absolute()
    if (
        not module_path.is_relative_to(environment_path)
        or module_path.is_relative_to(repository.resolve())
        or "site-packages" not in module_path.parts
        or executable_path != expected_executable
    ):
        raise ValueError("installed package identity verification failed")


def validate_evaluation(payload: Mapping[str, object]) -> None:
    if (
        payload.get("integrity_status") != "passed"
        or payload.get("quality_status") != "baseline_recorded"
        or payload.get("documents") != 5
        or payload.get("queries") != 48
        or payload.get("split_counts")
        != {"development": 24, "holdout": 24}
        or payload.get("integrity_failures") != []
        or payload.get("fts5_rank_profile") != "sqlite_fts5_default_bm25"
    ):
        raise RuntimeError("installed evaluation proof failed")


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    timeout: float = _STEP_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            list(command),
            cwd=cwd,
            env=dict(environment),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError("deployment proof command failed") from error
    output_size = len(result.stdout.encode()) + len(result.stderr.encode())
    if output_size > _OUTPUT_LIMIT_BYTES:
        raise RuntimeError("deployment proof output limit exceeded")
    if result.returncode != 0:
        raise RuntimeError("deployment proof command failed")
    return result


def _json_command(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    timeout: float,
) -> dict[str, object]:
    result = _run(
        command,
        cwd=cwd,
        environment=environment,
        timeout=timeout,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("deployment proof JSON was invalid") from error
    if not isinstance(payload, dict):
        raise RuntimeError("deployment proof JSON was invalid")
    return cast(dict[str, object], payload)


def run_deployment_proof(config: DeploymentProofConfig) -> dict[str, object]:
    started = time.monotonic()
    repository = Path(__file__).resolve().parents[1]
    protocol = config.protocol.resolve(strict=True)
    environment_variables = isolated_runtime_environment()
    with tempfile.TemporaryDirectory(prefix="mke-chinese-retrieval-proof-") as temp:
        runtime_root = Path(temp).resolve()
        if config.installed_environment is None:
            wheel = config.wheel.resolve(strict=True)
            environment = runtime_root / "venv"
            python = environment / "bin" / "python"
            mke = environment / "bin" / "mke"
            constraints = runtime_root / "constraints.txt"

            _run(
                (
                    "uv",
                    "export",
                    "--locked",
                    "--no-dev",
                    "--no-emit-project",
                    "--output-file",
                    str(constraints),
                ),
                cwd=repository,
                environment=environment_variables,
                timeout=_remaining(started),
            )
            _run(
                (
                    "uv",
                    "venv",
                    str(environment),
                    "--python",
                    config.python_version,
                    "--no-python-downloads",
                ),
                cwd=runtime_root,
                environment=environment_variables,
                timeout=_remaining(started),
            )
            _run(
                wheel_install_command(python, wheel, constraints),
                cwd=runtime_root,
                environment=environment_variables,
                timeout=_remaining(started),
            )
        else:
            environment = config.installed_environment.resolve(strict=True)
            python = environment / "bin" / "python"
            mke = environment / "bin" / "mke"

        identity = _json_command(
            (
                str(python),
                "-c",
                (
                    "import json,mke,sys;"
                    "print(json.dumps({'mke_file':mke.__file__,"
                    "'sys_executable':sys.executable}))"
                ),
            ),
            cwd=runtime_root,
            environment=environment_variables,
            timeout=_remaining(started),
        )
        validate_installed_identity(
            identity,
            environment=environment,
            repository=repository,
        )
        payload = _json_command(
            (
                str(mke),
                "eval",
                "retrieval-chinese",
                "--protocol",
                str(protocol),
                "--json",
            ),
            cwd=runtime_root,
            environment=environment_variables,
            timeout=_remaining(started),
        )
        validate_evaluation(payload)
    return {
        "status": "passed",
        "python": config.python_version,
        "offline": True,
        "installed_identity": "passed",
        "evaluation_status": "passed",
        "duration_ms": round((time.monotonic() - started) * 1000),
        "failure_reason": None,
    }


def _remaining(started: float) -> float:
    remaining = _TOTAL_TIMEOUT_SECONDS - (time.monotonic() - started)
    if remaining <= 0:
        raise RuntimeError("deployment proof command failed")
    return min(_STEP_TIMEOUT_SECONDS, remaining)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chinese_retrieval_deployment_proof.py"
    )
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--python", choices=("3.12", "3.13"), required=True)
    parser.add_argument("--installed-environment", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = run_deployment_proof(
            DeploymentProofConfig(
                wheel=args.wheel,
                protocol=args.protocol,
                python_version=args.python,
                installed_environment=args.installed_environment,
            )
        )
    except Exception:
        report = {
            "status": "failed",
            "python": args.python,
            "offline": True,
            "installed_identity": "not_verified",
            "evaluation_status": "not_verified",
            "duration_ms": 0,
            "failure_reason": "deployment_proof_failed",
        }
        print(json.dumps(report, separators=(",", ":"), sort_keys=True))
        return 1
    print(json.dumps(report, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
