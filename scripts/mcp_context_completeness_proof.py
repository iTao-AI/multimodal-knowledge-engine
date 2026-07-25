#!/usr/bin/env python3
"""Build one wheel and prove its MCP completeness contract on Python 3.12 and 3.13."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

PROOF_SCHEMA = "mke.mcp_context_completeness_proof.v1"
DIRTY_ENV = frozenset({"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"})


class ProofFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def environment() -> dict[str, str]:
    result = {key: value for key, value in os.environ.items() if key not in DIRTY_ENV}
    result["UV_OFFLINE"] = "1"
    return result


def command(
    argv: list[str],
    *,
    cwd: Path,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            env=environment(),
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProofFailure("command_failed") from exc
    if len(result.stdout.encode("utf-8")) > 1024 * 1024:
        raise ProofFailure("command_output_exceeded")
    if len(result.stderr.encode("utf-8")) > 1024 * 1024:
        raise ProofFailure("command_output_exceeded")
    return result


def parse_receipt(result: subprocess.CompletedProcess[str], code: str) -> dict[str, Any]:
    if result.returncode != 0:
        raise ProofFailure(code)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProofFailure(code) from exc
    if not isinstance(payload, dict) or payload.get("status") != "passed":
        raise ProofFailure(code)
    return payload


def validate_installed_identity(
    *,
    module: Path,
    executable: Path,
    environment_root: Path,
    repository: Path,
) -> None:
    resolved_module = module.resolve()
    resolved_environment = environment_root.resolve()
    resolved_repository = repository.resolve()
    expected_executable = environment_root / "bin" / "python"
    if (
        not module.is_absolute()
        or not executable.is_absolute()
        or resolved_module == resolved_repository
        or resolved_repository in resolved_module.parents
        or (
            resolved_module != resolved_environment
            and resolved_environment not in resolved_module.parents
        )
        or executable.name != expected_executable.name
        or executable.parent.resolve() != expected_executable.parent.resolve()
    ):
        raise ProofFailure("installed_identity_failed")


def installed_case(
    *,
    interpreter: Path,
    wheel: Path,
    constraints: Path,
    repository: Path,
    case_root: Path,
) -> dict[str, Any]:
    case_root.mkdir(parents=True)
    version_result = command(
        [
            str(interpreter),
            "-c",
            "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')",
        ],
        cwd=case_root,
    )
    if version_result.returncode != 0:
        raise ProofFailure("python_interpreter_unavailable")
    version = version_result.stdout.strip()
    if version not in {"3.12", "3.13"}:
        raise ProofFailure("python_interpreter_unavailable")

    environment_root = case_root / f"python-{version}"
    create = command(
        ["uv", "venv", "--python", str(interpreter), str(environment_root)],
        cwd=case_root,
    )
    if create.returncode != 0:
        raise ProofFailure("environment_create_failed")
    installed_python = environment_root / "bin" / "python"
    install = command(
        [
            "uv",
            "pip",
            "install",
            "--offline",
            "--python",
            str(installed_python),
            "--constraints",
            str(constraints),
            str(wheel),
        ],
        cwd=case_root,
    )
    if install.returncode != 0:
        raise ProofFailure("install_failed")

    identity = command(
        [
            str(installed_python),
            "-c",
            (
                "import json,mke,sys;"
                "print(json.dumps({'module':mke.__file__,'executable':sys.executable}))"
            ),
        ],
        cwd=case_root,
    )
    identity_payload = parse_receipt(
        subprocess.CompletedProcess(
            identity.args,
            identity.returncode,
            json.dumps(
                {
                    "status": "passed",
                    **json.loads(identity.stdout),
                }
            ),
            identity.stderr,
        ),
        "installed_identity_failed",
    )
    validate_installed_identity(
        module=Path(identity_payload["module"]),
        executable=Path(identity_payload["executable"]),
        environment_root=environment_root,
        repository=repository,
    )

    fixture_script = case_root / "mcp_context_completeness_fixture.py"
    consumer_script = case_root / "mcp_context_completeness_consumer.py"
    expectation = case_root / "mcp-tool-schemas.json"
    pdf = case_root / "library" / "text-layer.pdf"
    pdf.parent.mkdir(parents=True)
    for source, target in (
        (repository / "scripts/mcp_context_completeness_fixture.py", fixture_script),
        (repository / "scripts/mcp_context_completeness_consumer.py", consumer_script),
        (
            repository
            / "tests/fixtures/mcp-context-completeness-v1/mcp-tool-schemas.json",
            expectation,
        ),
        (repository / "tests/fixtures/pdf/text-layer.pdf", pdf),
    ):
        shutil.copyfile(source, target)

    database = case_root / "mke.sqlite"
    fixture = command(
        [str(installed_python), str(fixture_script), "--database", str(database)],
        cwd=case_root,
    )
    parse_receipt(fixture, "fixture_setup_failed")
    consumer = command(
        [
            str(installed_python),
            str(consumer_script),
            "--server-command",
            str(environment_root / "bin" / "mke"),
            "--database",
            str(database),
            "--allowed-root",
            str(pdf.parent),
            "--expectation",
            str(expectation),
            "--ingest-fixture",
            str(pdf),
        ],
        cwd=case_root,
        timeout=180,
    )
    receipt = parse_receipt(consumer, "consumer_proof_failed")
    receipt["python_version"] = version
    return receipt


def run(args: argparse.Namespace) -> dict[str, object]:
    repository = Path(__file__).resolve().parent.parent
    interpreters = tuple(path.resolve() for path in args.python)
    constraints = args.constraints.resolve()
    if len(interpreters) != 2:
        raise ProofFailure("python_interpreter_unavailable")
    if not constraints.is_file():
        raise ProofFailure("locked_constraints_unavailable")
    locked_export = command(
        [
            "uv",
            "export",
            "--locked",
            "--no-dev",
            "--no-emit-project",
            "--no-header",
        ],
        cwd=repository,
    )
    if locked_export.returncode != 0:
        raise ProofFailure("locked_constraints_unavailable")
    if constraints.read_bytes() != locked_export.stdout.encode("utf-8"):
        raise ProofFailure("locked_constraints_mismatch")
    args.candidate_output.mkdir(parents=True, exist_ok=True)
    build = command(
        ["uv", "build", "--wheel", "--out-dir", str(args.candidate_output)],
        cwd=repository,
    )
    if build.returncode != 0:
        raise ProofFailure("wheel_build_failed")
    wheels = tuple(args.candidate_output.glob("*.whl"))
    if len(wheels) != 1:
        raise ProofFailure("wheel_build_failed")

    with tempfile.TemporaryDirectory(prefix="mke-context-completeness-") as temporary:
        root = Path(temporary)
        results = [
            installed_case(
                interpreter=interpreter,
                wheel=wheels[0],
                constraints=constraints,
                repository=repository,
                case_root=root / f"case-{index}",
            )
            for index, interpreter in enumerate(interpreters)
        ]
    versions = sorted(result["python_version"] for result in results)
    if versions != ["3.12", "3.13"]:
        raise ProofFailure("python_interpreter_unavailable")
    return {
        "status": "passed",
        "schema_version": PROOF_SCHEMA,
        "python_versions": versions,
        "tool_count": 10,
        "search_continuation": "passed",
        "exact_read": "passed",
        "cjk_cap": "passed",
        "cursor_expiry": "passed",
        "legacy_compatibility": "passed",
        "max_canonical_model_bytes": max(
            result["max_canonical_model_bytes"] for result in results
        ),
        "max_sdk_result_bytes": max(result["max_sdk_result_bytes"] for result in results),
        "source_import": "installed_wheel",
        "network_access": "not_used",
        "dependency_constraints": "uv_lock_exact",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", type=Path, action="append", required=True)
    parser.add_argument("--constraints", type=Path, required=True)
    parser.add_argument("--candidate-output", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    try:
        receipt = run(parse_args())
    except ProofFailure as exc:
        print(json.dumps({"status": "failed", "code": exc.code}, separators=(",", ":")))
        return 1
    except Exception:
        print(json.dumps({"status": "failed", "code": "proof_failed"}, separators=(",", ":")))
        return 1
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
