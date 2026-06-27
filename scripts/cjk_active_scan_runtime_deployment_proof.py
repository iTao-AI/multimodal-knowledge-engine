#!/usr/bin/env python3
"""Prove CJK active-scan runtime behavior from an isolated installed wheel."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

_TIMEOUT_SECONDS = 180.0
_PYTHON_ENVIRONMENT_VARIABLES = ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")
_ACTIVE_STRATEGY = "cjk-active-scan-overlap-v1"
_ROLLBACK_STRATEGY = "numeric-grouping-v1"
_QUERY = "蓝湖缓存服务 不完整索引"
_EXPECTED_PAGE = 5
_FIXTURE = Path(
    "tests/fixtures/retrieval-chinese-v1/development/adversarial.pdf"
)

_MCP_CLIENT_SOURCE = r'''
import argparse
import asyncio
import json
from datetime import timedelta

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client


def payload(result):
    if result.isError:
        raise RuntimeError("tool call failed")
    if isinstance(result.structuredContent, dict):
        return result.structuredContent
    for item in result.content:
        if isinstance(item, types.TextContent):
            value = json.loads(item.text)
            if isinstance(value, dict):
                return value
    raise RuntimeError("tool payload missing")


def page_starts(items):
    return [item["locator"]["start"] for item in items]


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mke", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--ingest", action="store_true")
    parser.add_argument("--strategy")
    parser.add_argument("--mode", choices=("active", "rollback", "default"), required=True)
    parser.add_argument("--fixture", required=True)
    args = parser.parse_args()

    server_args = ["--db", args.db]
    if args.strategy is not None:
        server_args.extend(["--retrieval-strategy", args.strategy])
    server_args.extend(["mcp", "--allowed-root", args.root])

    async with stdio_client(
        StdioServerParameters(command=args.mke, args=server_args)
    ) as (read, write):
        async with ClientSession(
            read, write, read_timeout_seconds=timedelta(seconds=60)
        ) as session:
            await session.initialize()
            tools = await session.list_tools()
            by_name = {tool.name: tool for tool in tools.tools}
            required = {
                "list_libraries",
                "ingest_file",
                "get_run",
                "search_library",
                "ask_library",
            }
            if not required.issubset(by_name):
                raise RuntimeError("required MCP tools missing")
            for name, expected in {
                "search_library": {"query", "limit"},
                "ask_library": {"question", "limit"},
            }.items():
                properties = set(by_name[name].inputSchema.get("properties", {}))
                if properties != expected or "retrieval_strategy" in properties:
                    raise RuntimeError("request schema exposes owner strategy")

            libraries = payload(await session.call_tool("list_libraries", {}))
            if libraries.get("libraries", [{}])[0].get("library_id") != "local":
                raise RuntimeError("list_libraries proof failed")

            if args.ingest:
                ingested = payload(
                    await session.call_tool("ingest_file", {"path": args.fixture})
                )
                if ingested.get("run_state") != "published":
                    raise RuntimeError("MCP ingest failed")
                inspected = payload(
                    await session.call_tool(
                        "get_run", {"run_id": ingested.get("run_id")}
                    )
                )
                if inspected.get("run", {}).get("state") != "published":
                    raise RuntimeError("MCP get_run failed")

            search = payload(
                await session.call_tool(
                    "search_library", {"query": "蓝湖缓存服务 不完整索引", "limit": 5}
                )
            )
            ask = payload(
                await session.call_tool(
                    "ask_library", {"question": "蓝湖缓存服务 不完整索引", "limit": 5}
                )
            )
            if args.mode in {"active", "default"}:
                if page_starts(search.get("results", []))[:1] != [5]:
                    raise RuntimeError("MCP CJK search proof failed")
                if ask.get("answer_status") != "evidence_found":
                    raise RuntimeError("MCP CJK ask proof failed")
                if page_starts(ask.get("evidence", []))[:1] != [5]:
                    raise RuntimeError("MCP CJK citation proof failed")
            else:
                if search.get("results") != []:
                    raise RuntimeError("rollback CJK search changed")
                if ask.get("ok") is not False or ask.get("problem") != "invalid_question":
                    raise RuntimeError("rollback CJK ask changed")

    strategy = args.strategy or "cjk-active-scan-overlap-v1"
    print(json.dumps({
        "status": "passed",
        "strategy": strategy,
        "mode": args.mode,
        "request_override_exposed": False,
    }, sort_keys=True))


asyncio.run(main())
'''

_BUDGET_SEED_SOURCE = r'''
from pathlib import Path
import sys

from mke.application import KnowledgeEngine
from mke.domain import (
    CandidateEvidence,
    PDF_EXTRACTOR_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    RunManifest,
)
from mke.retrieval.cjk_active_scan import CJK_ACTIVE_SCAN_PARAMETERS

db = Path(sys.argv[1])
engine = KnowledgeEngine(db, retrieval_strategy="cjk-active-scan-overlap-v1")
try:
    source = engine.ensure_source("budget-proof", "f" * 64, media_type="application/pdf")
    run = engine.create_run(source.source_id)
    count = CJK_ACTIVE_SCAN_PARAMETERS.max_active_evidence_rows + 1
    evidence = [
        CandidateEvidence(
            evidence_id=f"budget_{index:05d}",
            locator_kind="page",
            locator_start=index,
            locator_end=index,
            text="普通证据页面",
        )
        for index in range(1, count + 1)
    ]
    engine.persist_validated_candidate(
        run.run_id,
        evidence,
        RunManifest(
            run_id=run.run_id,
            evidence_count=count,
            required_stages=tuple(sorted(REQUIRED_PDF_STAGES)),
            extractor_fingerprint=PDF_EXTRACTOR_FINGERPRINT,
            asset_sha256="f" * 64,
        ),
    )
    engine.activate_publication(run.run_id)
finally:
    engine.close()
'''


@dataclass(frozen=True)
class DeploymentProofConfig:
    wheel: Path
    python_version: str
    verify_default: bool = True

    def __post_init__(self) -> None:
        if self.python_version not in {"3.12", "3.13"}:
            raise ValueError("python version must be 3.12 or 3.13")
        if not self.wheel.is_file() or self.wheel.suffix != ".whl":
            raise ValueError("wheel must be an existing .whl file")
        if type(self.verify_default) is not bool:
            raise TypeError("verify_default must be a boolean")


def isolated_runtime_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for name in _PYTHON_ENVIRONMENT_VARIABLES:
        environment.pop(name, None)
    environment.update(
        {
            "HF_HUB_OFFLINE": "1",
            "PYTHONNOUSERSITE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "UV_OFFLINE": "1",
        }
    )
    return environment


def wheel_install_command(python: Path, wheel: Path) -> tuple[str, ...]:
    return (
        "uv",
        "pip",
        "install",
        "--offline",
        "--python",
        str(python),
        str(wheel),
    )


def owner_cli_command(
    mke: Path,
    db: Path,
    *,
    strategy: str | None,
    command: Sequence[str],
) -> tuple[str, ...]:
    result = [str(mke), "--db", str(db)]
    if strategy is not None:
        result.extend(("--retrieval-strategy", strategy))
    result.extend(command)
    return tuple(result)


def mcp_client_command(
    *,
    python: Path,
    client: Path,
    mke: Path,
    db: Path,
    root: Path,
    fixture: str,
    strategy: str | None,
    mode: str,
    ingest: bool,
) -> tuple[str, ...]:
    result = [
        str(python),
        "-I",
        str(client),
        "--mke",
        str(mke),
        "--db",
        str(db),
        "--root",
        str(root),
    ]
    if ingest:
        result.append("--ingest")
    if strategy is not None:
        result.extend(("--strategy", strategy))
    result.extend(("--mode", mode, "--fixture", fixture))
    return tuple(result)


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
    executable_path = Path(executable).resolve()
    if (
        not module_path.is_relative_to(environment.resolve())
        or module_path.is_relative_to(repository.resolve())
        or executable_path != (environment / "bin" / "python").resolve()
    ):
        raise ValueError("installed package identity verification failed")


def validate_runtime_reports(
    *,
    explicit: Mapping[str, object],
    rollback: Mapping[str, object],
    default: Mapping[str, object] | None,
    verify_default: bool,
) -> str:
    if explicit.get("status") != "passed" or explicit.get("strategy") != _ACTIVE_STRATEGY:
        raise RuntimeError("explicit retrieval strategy proof failed")
    if rollback.get("status") != "passed" or rollback.get("strategy") != _ROLLBACK_STRATEGY:
        raise RuntimeError("rollback retrieval strategy proof failed")
    if not verify_default:
        return "explicit_only"
    if (
        default is None
        or default.get("status") != "passed"
        or default.get("strategy") != _ACTIVE_STRATEGY
    ):
        raise RuntimeError("default retrieval strategy proof failed")
    return _ACTIVE_STRATEGY


def validate_budget_error(
    result: subprocess.CompletedProcess[str], *, forbidden_root: Path
) -> None:
    required = (
        "problem=cjk_scan_budget_exceeded",
        "cause=CJK active Evidence scan would exceed configured local budget",
        "active_publication_impact=unchanged",
        "next_step=narrow_query_or_use_projection_strategy",
    )
    combined = result.stdout + result.stderr
    if (
        result.returncode != 1
        or any(item not in result.stdout for item in required)
        or str(forbidden_root) in combined
        or "traceback" in combined.casefold()
    ):
        raise RuntimeError("budget error proof failed")


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    accepted_returncodes: frozenset[int] = frozenset({0}),
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            list(command),
            cwd=cwd,
            env=dict(environment),
            text=True,
            capture_output=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError("deployment proof command failed") from error
    if result.returncode not in accepted_returncodes:
        raise RuntimeError("deployment proof command failed")
    return result


def _json_command(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
) -> dict[str, object]:
    result = _run(command, cwd=cwd, environment=environment)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("deployment proof JSON was invalid") from error
    if not isinstance(payload, dict):
        raise RuntimeError("deployment proof JSON was invalid")
    return cast(dict[str, object], payload)


def _assert_cli_active(
    mke: Path,
    db: Path,
    strategy: str | None,
    *,
    cwd: Path,
    environment: Mapping[str, str],
) -> None:
    for command in (("search", _QUERY), ("ask", _QUERY)):
        result = _run(
            owner_cli_command(mke, db, strategy=strategy, command=command),
            cwd=cwd,
            environment=environment,
        )
        if f"page={_EXPECTED_PAGE}" not in result.stdout:
            raise RuntimeError("installed CLI CJK retrieval proof failed")
    doctor = _json_command(
        owner_cli_command(
            mke,
            db,
            strategy=None,
            command=("retrieval", "doctor", "--strategy", _ACTIVE_STRATEGY, "--json"),
        ),
        cwd=cwd,
        environment=environment,
    )
    if doctor.get("status") != "ready":
        raise RuntimeError("installed CLI retrieval doctor proof failed")
    rebuild = _json_command(
        owner_cli_command(
            mke,
            db,
            strategy=None,
            command=("retrieval", "rebuild", "--strategy", _ACTIVE_STRATEGY, "--json"),
        ),
        cwd=cwd,
        environment=environment,
    )
    if rebuild.get("action") != "noop" or rebuild.get("projection") != "none":
        raise RuntimeError("installed CLI retrieval rebuild proof failed")


def _assert_cli_rollback(
    mke: Path,
    db: Path,
    *,
    cwd: Path,
    environment: Mapping[str, str],
) -> None:
    search = _run(
        owner_cli_command(
            mke,
            db,
            strategy=_ROLLBACK_STRATEGY,
            command=("search", _QUERY),
        ),
        cwd=cwd,
        environment=environment,
    )
    if search.stdout:
        raise RuntimeError("installed CLI rollback search changed")
    ask = _run(
        owner_cli_command(
            mke,
            db,
            strategy=_ROLLBACK_STRATEGY,
            command=("ask", _QUERY),
        ),
        cwd=cwd,
        environment=environment,
        accepted_returncodes=frozenset({1}),
    )
    if "problem=invalid_question" not in ask.stdout:
        raise RuntimeError("installed CLI rollback ask changed")


def run_deployment_proof(config: DeploymentProofConfig) -> dict[str, object]:
    repository = Path(__file__).resolve().parents[1]
    wheel = config.wheel.resolve(strict=True)
    source_fixture = repository / _FIXTURE
    if not source_fixture.is_file():
        raise RuntimeError("deployment proof fixture is missing")
    environment_variables = isolated_runtime_environment()
    with tempfile.TemporaryDirectory(prefix="mke-cjk-active-scan-") as temp:
        runtime_root = Path(temp).resolve()
        environment = runtime_root / "venv"
        installed_python = environment / "bin" / "python"
        installed_mke = environment / "bin" / "mke"
        allowed_root = runtime_root / "allowed"
        allowed_root.mkdir()
        fixture = allowed_root / "adversarial.pdf"
        shutil.copyfile(source_fixture, fixture)
        client = runtime_root / "mcp_client.py"
        client.write_text(_MCP_CLIENT_SOURCE, encoding="utf-8")

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
        )
        _run(
            wheel_install_command(installed_python, wheel),
            cwd=runtime_root,
            environment=environment_variables,
        )
        identity = _json_command(
            (
                str(installed_python),
                "-I",
                "-c",
                (
                    "import json,mke,sys;"
                    "print(json.dumps({'mke_file':mke.__file__,"
                    "'sys_executable':sys.executable}))"
                ),
            ),
            cwd=runtime_root,
            environment=environment_variables,
        )
        validate_installed_identity(
            identity,
            environment=environment,
            repository=repository,
        )

        cli_db = runtime_root / "cli.sqlite"
        _run(
            owner_cli_command(
                installed_mke,
                cli_db,
                strategy=_ACTIVE_STRATEGY,
                command=("ingest", str(fixture), "--json"),
            ),
            cwd=runtime_root,
            environment=environment_variables,
        )
        _assert_cli_active(
            installed_mke,
            cli_db,
            _ACTIVE_STRATEGY,
            cwd=runtime_root,
            environment=environment_variables,
        )
        _assert_cli_rollback(
            installed_mke,
            cli_db,
            cwd=runtime_root,
            environment=environment_variables,
        )
        if config.verify_default:
            _assert_cli_active(
                installed_mke,
                cli_db,
                None,
                cwd=runtime_root,
                environment=environment_variables,
            )

        mcp_db = runtime_root / "mcp.sqlite"
        explicit = _json_command(
            mcp_client_command(
                python=installed_python,
                client=client,
                mke=installed_mke,
                db=mcp_db,
                root=allowed_root,
                fixture=fixture.name,
                strategy=_ACTIVE_STRATEGY,
                mode="active",
                ingest=True,
            ),
            cwd=runtime_root,
            environment=environment_variables,
        )
        rollback = _json_command(
            mcp_client_command(
                python=installed_python,
                client=client,
                mke=installed_mke,
                db=mcp_db,
                root=allowed_root,
                fixture=fixture.name,
                strategy=_ROLLBACK_STRATEGY,
                mode="rollback",
                ingest=False,
            ),
            cwd=runtime_root,
            environment=environment_variables,
        )
        default = (
            _json_command(
                mcp_client_command(
                    python=installed_python,
                    client=client,
                    mke=installed_mke,
                    db=mcp_db,
                    root=allowed_root,
                    fixture=fixture.name,
                    strategy=None,
                    mode="default",
                    ingest=False,
                ),
                cwd=runtime_root,
                environment=environment_variables,
            )
            if config.verify_default
            else None
        )
        default_status = validate_runtime_reports(
            explicit=explicit,
            rollback=rollback,
            default=default,
            verify_default=config.verify_default,
        )

        budget_db = runtime_root / "budget.sqlite"
        _run(
            (str(installed_python), "-I", "-c", _BUDGET_SEED_SOURCE, str(budget_db)),
            cwd=runtime_root,
            environment=environment_variables,
        )
        budget = _run(
            owner_cli_command(
                installed_mke,
                budget_db,
                strategy=_ACTIVE_STRATEGY,
                command=("search", _QUERY),
            ),
            cwd=runtime_root,
            environment=environment_variables,
            accepted_returncodes=frozenset({1}),
        )
        validate_budget_error(budget, forbidden_root=runtime_root)

    return {
        "status": "passed",
        "python": config.python_version,
        "installed_identity": "wheel",
        "network": "offline",
        "cli": {
            "explicit_strategy": _ACTIVE_STRATEGY,
            "default_strategy": default_status,
            "rollback_strategy": _ROLLBACK_STRATEGY,
            "doctor": "ready",
            "rebuild": "noop",
            "budget_error": "stable",
        },
        "mcp": {
            "explicit_strategy": _ACTIVE_STRATEGY,
            "default_strategy": default_status,
            "rollback_strategy": _ROLLBACK_STRATEGY,
            "tool_calls": [
                "list_libraries",
                "ingest_file",
                "get_run",
                "search_library",
                "ask_library",
            ],
            "request_override_exposed": False,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cjk_active_scan_runtime_deployment_proof.py"
    )
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--python", choices=("3.12", "3.13"), required=True)
    parser.add_argument("--explicit-only", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = run_deployment_proof(
            DeploymentProofConfig(
                wheel=args.wheel,
                python_version=args.python,
                verify_default=not args.explicit_only,
            )
        )
    except Exception:
        print(json.dumps({"status": "failed", "reason": "deployment_proof_failed"}))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
