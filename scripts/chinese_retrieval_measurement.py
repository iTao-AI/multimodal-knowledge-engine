#!/usr/bin/env python3
"""Measure bounded local E3-A evaluation and installed-wheel proof costs."""

from __future__ import annotations

import argparse
import json
import os
import resource
import subprocess
import tempfile
import threading
import time
from collections.abc import Mapping, MutableMapping, Sequence
from pathlib import Path
from typing import cast

_OUTPUT_LIMIT_BYTES = 64 * 1024
_STEP_TIMEOUT_SECONDS = 180.0
_GIB = 1024 * 1024 * 1024
_MIB = 1024 * 1024


def evaluate_budgets(
    *,
    warm_cache_sync_ms: int,
    evaluator_ms: int,
    installed_wheel_proof_ms: int,
    peak_rss_bytes: int,
    max_sqlite_bytes: int,
) -> dict[str, bool]:
    return {
        "checkout_to_first_report": warm_cache_sync_ms + evaluator_ms <= 300_000,
        "source_tree_evaluation": evaluator_ms <= 180_000,
        "installed_wheel_proof": installed_wheel_proof_ms <= 180_000,
        "peak_rss": peak_rss_bytes <= int(1.5 * _GIB),
        "temporary_sqlite": max_sqlite_bytes <= 64 * _MIB,
    }


def build_summary(
    *,
    python_version: str,
    warm_cache_sync_ms: int,
    evaluator_ms: int,
    installed_wheel_proof_ms: int,
    peak_rss_bytes: int,
    max_sqlite_bytes: int,
) -> dict[str, object]:
    return {
        "schema_version": "mke.retrieval_chinese_measurement.v1",
        "python": python_version,
        "telemetry": False,
        "network": False,
        "warm_cache_sync_ms": warm_cache_sync_ms,
        "evaluator_ms": evaluator_ms,
        "checkout_to_first_report_ms": warm_cache_sync_ms + evaluator_ms,
        "installed_wheel_proof_ms": installed_wheel_proof_ms,
        "peak_rss_bytes": peak_rss_bytes,
        "max_temporary_sqlite_bytes": max_sqlite_bytes,
        "budgets": evaluate_budgets(
            warm_cache_sync_ms=warm_cache_sync_ms,
            evaluator_ms=evaluator_ms,
            installed_wheel_proof_ms=installed_wheel_proof_ms,
            peak_rss_bytes=peak_rss_bytes,
            max_sqlite_bytes=max_sqlite_bytes,
        ),
    }


def run_timed_command(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    timeout: float = _STEP_TIMEOUT_SECONDS,
    resource_sample: MutableMapping[str, int] | None = None,
) -> tuple[int, subprocess.CompletedProcess[str]]:
    started = time.monotonic()
    stop_sampling = threading.Event()
    sampler: threading.Thread | None = None
    temporary_root = environment.get("TMPDIR")
    if resource_sample is not None and temporary_root is not None:
        sampler = threading.Thread(
            target=_sample_sqlite_sizes,
            args=(
                Path(temporary_root),
                stop_sampling,
                resource_sample,
            ),
            daemon=True,
        )
        sampler.start()
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
        raise RuntimeError("measurement command failed") from error
    finally:
        stop_sampling.set()
        if sampler is not None:
            sampler.join(timeout=1.0)
    elapsed_ms = round((time.monotonic() - started) * 1000)
    output_size = len(result.stdout.encode()) + len(result.stderr.encode())
    if output_size > _OUTPUT_LIMIT_BYTES:
        raise RuntimeError("measurement output limit exceeded")
    if result.returncode != 0:
        raise RuntimeError("measurement command failed")
    return elapsed_ms, result


def _peak_child_rss_bytes() -> int:
    maximum = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    if os.uname().sysname == "Darwin":
        return int(maximum)
    return int(maximum * 1024)


def _maximum_sqlite_bytes(root: Path) -> int:
    sizes = (
        path.stat().st_size
        for path in root.rglob("*")
        if path.is_file()
        and (
            path.suffix in {".sqlite", ".sqlite3", ".db"}
            or "-wal" in path.name
        )
    )
    return max(sizes, default=0)


def _sample_sqlite_sizes(
    root: Path,
    stop: threading.Event,
    sample: MutableMapping[str, int],
) -> None:
    while not stop.wait(0.005):
        sample["max_sqlite_bytes"] = max(
            sample.get("max_sqlite_bytes", 0),
            _maximum_sqlite_bytes(root),
        )
    sample["max_sqlite_bytes"] = max(
        sample.get("max_sqlite_bytes", 0),
        _maximum_sqlite_bytes(root),
    )


def run_measurement(
    *,
    repository: Path,
    protocol: Path,
    wheel: Path,
    python_version: str,
    installed_environment: Path | None = None,
) -> dict[str, object]:
    environment = dict(os.environ)
    environment["UV_OFFLINE"] = "1"
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        environment.pop(name, None)
    with tempfile.TemporaryDirectory(prefix="mke-chinese-measurement-") as temp:
        temp_root = Path(temp)
        environment["TMPDIR"] = str(temp_root)
        resource_sample = {"max_sqlite_bytes": 0}
        warm_cache_sync_ms, _ = run_timed_command(
            ("uv", "sync", "--locked", "--offline"),
            cwd=repository,
            environment=environment,
            resource_sample=resource_sample,
        )
        evaluator_ms, evaluator = run_timed_command(
            (
                "uv",
                "run",
                "mke",
                "eval",
                "retrieval-chinese",
                "--protocol",
                str(protocol),
            ),
            cwd=repository,
            environment=environment,
            resource_sample=resource_sample,
        )
        if not evaluator.stdout.startswith("mke eval retrieval-chinese\n"):
            raise RuntimeError("measurement command failed")
        proof_command = [
                "uv",
                "run",
                "python",
                "scripts/chinese_retrieval_deployment_proof.py",
                "--wheel",
                str(wheel),
                "--protocol",
                str(protocol),
                "--python",
                python_version,
        ]
        if installed_environment is not None:
            proof_command.extend(
                ("--installed-environment", str(installed_environment))
            )
        proof_ms, proof = run_timed_command(
            tuple(proof_command),
            cwd=repository,
            environment=environment,
            resource_sample=resource_sample,
        )
        if json.loads(proof.stdout).get("status") != "passed":
            raise RuntimeError("measurement command failed")
        summary = build_summary(
            python_version=python_version,
            warm_cache_sync_ms=warm_cache_sync_ms,
            evaluator_ms=evaluator_ms,
            installed_wheel_proof_ms=proof_ms,
            peak_rss_bytes=_peak_child_rss_bytes(),
            max_sqlite_bytes=resource_sample["max_sqlite_bytes"],
        )
    budgets = cast(dict[str, bool], summary["budgets"])
    if not all(budgets.values()):
        raise RuntimeError("measurement budget exceeded")
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chinese_retrieval_measurement.py")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--python", choices=("3.12", "3.13"), required=True)
    parser.add_argument("--installed-environment", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = run_measurement(
            repository=args.repository.resolve(),
            protocol=args.protocol.resolve(),
            wheel=args.wheel.resolve(),
            python_version=args.python,
            installed_environment=(
                args.installed_environment.resolve()
                if args.installed_environment is not None
                else None
            ),
        )
    except Exception:
        print(
            json.dumps(
                {
                    "schema_version": "mke.retrieval_chinese_measurement.v1",
                    "status": "failed",
                    "reason": "measurement_failed",
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 1
    report["status"] = "passed"
    print(json.dumps(report, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
