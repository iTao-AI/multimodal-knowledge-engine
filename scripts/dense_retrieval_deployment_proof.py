#!/usr/bin/env python3
"""Run the dense compatibility proof from an installed wheel with no network."""

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

from mke.evaluation.dense_compatibility import (
    CompatibilityValidationError,
    load_dense_corpus_lock,
    validate_dense_compatibility_report,
)

_STEP_TIMEOUT_SECONDS = 600.0
_TOTAL_TIMEOUT_SECONDS = 600.0
_OUTPUT_LIMIT = 512 * 1024


@dataclass(frozen=True)
class DeploymentProofConfig:
    wheel: Path
    corpus_lock: Path
    model_cache: Path
    python_version: str
    repository: Path = Path.cwd()

    def __post_init__(self) -> None:
        if self.python_version not in {"3.12", "3.13"}:
            raise ValueError("python version is unsupported")
        if not self.wheel.is_file() or self.wheel.suffix != ".whl":
            raise ValueError("wheel is missing")
        if not self.corpus_lock.is_file() or self.corpus_lock.suffix != ".json":
            raise ValueError("corpus lock is missing")
        if not self.model_cache.is_dir():
            raise ValueError("model cache is missing")
        repository = self.repository.resolve()
        cache = self.model_cache.resolve()
        if cache == repository or cache.is_relative_to(repository):
            raise ValueError("model cache must be outside the repository")


def isolated_runtime_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        environment.pop(name, None)
    environment.update(
        {
            "UV_OFFLINE": "1",
            "PIP_NO_INDEX": "1",
            "HF_HUB_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "TOKENIZERS_PARALLELISM": "false",
        }
    )
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
        str(wheel) + "[embedding]",
    )


def query_smoke_command(
    python: Path,
    corpus_lock: Path,
    model_cache: Path,
    repository: Path,
) -> tuple[str, ...]:
    return (
        str(python),
        "-m",
        "mke.evaluation.dense_compatibility",
        "--single-query-smoke",
        "--corpus-lock",
        str(corpus_lock),
        "--model-cache",
        str(model_cache),
        "--repository",
        str(repository),
        "--json",
    )


def validate_query_smoke_evidence(
    evidence: Mapping[str, object],
    *,
    expected_model_fingerprint: str,
) -> None:
    expected = {
        "status",
        "python",
        "interpreter",
        "cache_only",
        "network",
        "source_tree_import",
        "model_fingerprint",
        "query_vector_digest",
        "peak_rss_bytes",
        "model_load_ms",
        "query_embedding_ms",
    }
    if set(evidence) != expected:
        raise ValueError("single-query smoke evidence is invalid")
    if (
        evidence["status"] != "passed"
        or evidence["model_fingerprint"] != expected_model_fingerprint
        or evidence["cache_only"] is not True
        or evidence["network"] is not False
        or evidence["source_tree_import"] is not False
        or not _fingerprint(evidence["query_vector_digest"])
    ):
        raise ValueError("single-query smoke evidence is invalid")
    for key in ("python", "interpreter"):
        if type(evidence[key]) is not str or not evidence[key]:
            raise ValueError("single-query smoke evidence is invalid")
    for key in ("peak_rss_bytes", "model_load_ms", "query_embedding_ms"):
        value = evidence[key]
        if type(value) is not int or value < 0:
            raise ValueError("single-query smoke evidence is invalid")


def validate_installed_identity(
    identity: Mapping[str, object],
    *,
    environment: Path,
    repository: Path,
) -> None:
    module_value = identity.get("mke_file")
    executable_value = identity.get("sys_executable")
    if type(module_value) is not str or type(executable_value) is not str:
        raise ValueError("installed package identity verification failed")
    module = Path(module_value).resolve()
    executable = Path(executable_value).absolute()
    runtime = environment.resolve()
    source = repository.resolve()
    expected_executable = (runtime / "bin/python").absolute()
    if (
        not module.is_relative_to(runtime)
        or module.is_relative_to(source)
        or "site-packages" not in module.parts
        or executable != expected_executable
    ):
        raise ValueError("installed package identity verification failed")


def run_deployment_proof(config: DeploymentProofConfig) -> dict[str, object]:
    started = time.monotonic()
    environment = isolated_runtime_environment()
    repository = config.repository.resolve()
    with tempfile.TemporaryDirectory(prefix="mke-dense-wheel-proof-") as temp:
        root = Path(temp).resolve()
        if root.is_relative_to(repository):
            raise RuntimeError("deployment proof external cwd is invalid")
        runtime = root / "venv"
        constraints = root / "constraints.txt"
        _run(
            (
                "uv",
                "export",
                "--locked",
                "--extra",
                "embedding",
                "--no-dev",
                "--no-emit-project",
                "--output-file",
                str(constraints),
            ),
            cwd=repository,
            environment=environment,
            timeout=_remaining(started),
        )
        _run(
            (
                "uv",
                "venv",
                "--clear",
                str(runtime),
                "--python",
                config.python_version,
                "--no-python-downloads",
            ),
            cwd=root,
            environment=environment,
            timeout=_remaining(started),
        )
        _run(
            wheel_install_command(runtime / "bin/python", config.wheel, constraints),
            cwd=root,
            environment=environment,
            timeout=_remaining(started),
        )
        python = runtime / "bin/python"
        mke = runtime / "bin/mke"
        identity = _json_command(
            (
                str(python),
                "-I",
                "-c",
                "import json,mke,sys;"
                "print(json.dumps({'mke_file':mke.__file__,"
                "'sys_executable':sys.executable}))",
            ),
            cwd=root,
            environment=environment,
            timeout=_remaining(started),
        )
        validate_installed_identity(identity, environment=runtime, repository=repository)
        doctor = _json_command(
            (
                str(mke),
                "embedding",
                "doctor",
                "--model-cache",
                str(config.model_cache),
                "--json",
            ),
            cwd=root,
            environment=environment,
            timeout=_remaining(started),
        )
        if doctor.get("status") != "ready":
            raise RuntimeError("installed embedding doctor failed")
        expected_fingerprint = doctor.get("snapshot_fingerprint")
        if type(expected_fingerprint) is not str:
            raise RuntimeError("installed embedding doctor failed")
        query_smoke = _json_command(
            query_smoke_command(
                python,
                config.corpus_lock,
                config.model_cache,
                repository,
            ),
            cwd=root,
            environment=environment,
            timeout=_remaining(started),
        )
        validate_query_smoke_evidence(
            query_smoke,
            expected_model_fingerprint=expected_fingerprint,
        )
        query_smoke_path = root / "single-query-smoke.json"
        query_smoke_path.write_text(
            json.dumps(query_smoke, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        report = _json_command(
            (
                str(python),
                "-m",
                "mke.evaluation.dense_compatibility",
                "--corpus-lock",
                str(config.corpus_lock),
                "--model-cache",
                str(config.model_cache),
                "--repository",
                str(repository),
                "--single-query-smoke-report",
                str(query_smoke_path),
                "--json",
            ),
            cwd=root,
            environment=environment,
            timeout=_remaining(started),
        )
        try:
            corpus = load_dense_corpus_lock(
                config.corpus_lock,
                repository_root=repository,
            )
            validate_dense_compatibility_report(report, corpus)
        except CompatibilityValidationError as error:
            raise RuntimeError("installed dense compatibility proof failed") from error
        if report["compatibility_status"] != "passed":
            raise RuntimeError("installed dense compatibility proof failed")
        return {
            "schema_version": "mke.dense_deployment_proof.v1",
            "status": "passed",
            "python": config.python_version,
            "offline": True,
            "external_cwd": True,
            "hostile_environment_cleared": True,
            "installed_identity": "passed",
            "doctor": "ready",
            "single_query_smoke": query_smoke,
            "compatibility": report,
        }


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
    if len(result.stdout.encode()) + len(result.stderr.encode()) > _OUTPUT_LIMIT:
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
        raise RuntimeError("deployment proof returned invalid JSON") from error
    if not isinstance(payload, dict):
        raise RuntimeError("deployment proof returned invalid JSON")
    return cast(dict[str, object], payload)


def _remaining(started: float) -> float:
    remaining = _TOTAL_TIMEOUT_SECONDS - (time.monotonic() - started)
    if remaining <= 0:
        raise RuntimeError("deployment proof command failed")
    return min(_STEP_TIMEOUT_SECONDS, remaining)


def _fingerprint(value: object) -> bool:
    if type(value) is not str or not value.startswith("sha256:"):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(
        character in "0123456789abcdef" for character in digest
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dense_retrieval_deployment_proof.py")
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--corpus-lock", type=Path, required=True)
    parser.add_argument("--model-cache", type=Path, required=True)
    parser.add_argument("--python", choices=("3.12", "3.13"), required=True)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = run_deployment_proof(
            DeploymentProofConfig(
                wheel=args.wheel.resolve(),
                corpus_lock=args.corpus_lock.resolve(),
                model_cache=args.model_cache.resolve(),
                python_version=args.python,
                repository=args.repository.resolve(),
            )
        )
    except Exception:
        print(json.dumps({"schema_version": "mke.dense_deployment_proof.v1", "status": "failed"}))
        return 1
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
