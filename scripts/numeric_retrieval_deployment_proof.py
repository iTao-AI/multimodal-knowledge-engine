#!/usr/bin/env python3
"""Prove promoted and rollback retrieval policies from an isolated installed wheel."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

_TIMEOUT_SECONDS = 180.0
_PYTHON_ENVIRONMENT_VARIABLES = ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")

_FIXTURE_SOURCE = """
from pathlib import Path
import fitz

pages = (
    "Grouped comma control: 410,000 units.",
    "Grouped space control: 410 000 units.",
    "Grouped hyphen control: 410-000 units.",
    "Grouped slash control: 410/000 units.",
    "Compact control: 410000 units.",
    "Non-adjacent control: 410 accepted units and 000 rejected units.",
)
document = fitz.open()
for text in pages:
    page = document.new_page()
    written = page.insert_textbox(
        fitz.Rect(72, 72, 540, 720),
        text,
        fontsize=12,
        fontname="helv",
    )
    if written < 0:
        raise RuntimeError("fixture text did not fit")
document.save(Path(__import__("sys").argv[1]))
document.close()
"""

_MCP_CLIENT_SOURCE = """
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

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mke", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--policy", choices=("current", "numeric-grouping-v1"), required=True)
    parser.add_argument("--ingest", action="store_true")
    args = parser.parse_args()
    server_args = [
        "--db", args.db,
        "--retrieval-query-policy", args.policy,
        "mcp", "--allowed-root", args.root,
    ]
    async with stdio_client(
        StdioServerParameters(command=args.mke, args=server_args)
    ) as (read, write):
        async with ClientSession(
            read, write, read_timeout_seconds=timedelta(seconds=60)
        ) as session:
            await session.initialize()
            tools = await session.list_tools()
            schemas = json.dumps(
                [tool.inputSchema for tool in tools.tools], sort_keys=True
            ).casefold()
            if "retrieval_query_policy" in schemas or "retrieval-query-policy" in schemas:
                raise RuntimeError("request schema exposes owner policy")
            if args.ingest:
                ingested = payload(
                    await session.call_tool("ingest_file", {"path": args.fixture})
                )
                if ingested.get("run_state") != "published":
                    raise RuntimeError("MCP ingest failed")
            async def search(query):
                return payload(
                    await session.call_tool(
                        "search_library", {"query": query, "limit": 5}
                    )
                ).get("results", [])
            comma = await search("410000 grouped comma control")
            compact = await search("410000 compact control")
            non_adjacent = await search("410000 non adjacent control")
            slash = await search("410000 grouped slash control")
            if args.policy == "numeric-grouping-v1":
                if [item["locator"]["start"] for item in comma] != [1]:
                    raise RuntimeError("promoted comma search failed")
                if [item["locator"]["start"] for item in slash] != [4]:
                    raise RuntimeError("promoted punctuation search failed")
            elif comma or slash:
                raise RuntimeError("current rollback changed grouped search")
            if [item["locator"]["start"] for item in compact] != [5]:
                raise RuntimeError("compact preservation failed")
            if non_adjacent:
                raise RuntimeError("non-adjacent control matched")
    print(json.dumps({"status": "passed", "policy": args.policy}, sort_keys=True))

asyncio.run(main())
"""


@dataclass(frozen=True)
class DeploymentProofConfig:
    wheel: Path
    python_version: str

    def __post_init__(self) -> None:
        if self.python_version not in {"3.12", "3.13"}:
            raise ValueError("python version must be 3.12 or 3.13")
        if not self.wheel.is_file() or self.wheel.suffix != ".whl":
            raise ValueError("wheel must be an existing .whl file")


def isolated_runtime_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for name in _PYTHON_ENVIRONMENT_VARIABLES:
        environment.pop(name, None)
    return environment


def wheel_install_command(python: Path, wheel: Path) -> tuple[str, ...]:
    return (
        "uv",
        "pip",
        "install",
        "--python",
        str(python),
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
    executable_path = Path(executable).resolve()
    if (
        not module_path.is_relative_to(environment.resolve())
        or module_path.is_relative_to(repository.resolve())
        or executable_path != (environment / "bin" / "python").resolve()
    ):
        raise ValueError("installed package identity verification failed")


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


def _assert_cli_page(
    mke: Path,
    db: Path,
    policy: str,
    query: str,
    expected_page: int | None,
    *,
    cwd: Path,
    environment: Mapping[str, str],
) -> None:
    result = _run(
        [
            str(mke),
            "--db",
            str(db),
            "--retrieval-query-policy",
            policy,
            "search",
            query,
        ],
        cwd=cwd,
        environment=environment,
    )
    if expected_page is None:
        if result.stdout:
            raise RuntimeError("installed CLI rollback proof failed")
        return
    if f"page={expected_page}" not in result.stdout:
        raise RuntimeError("installed CLI retrieval proof failed")


def run_deployment_proof(config: DeploymentProofConfig) -> dict[str, object]:
    repository = Path(__file__).resolve().parents[1]
    wheel = config.wheel.resolve(strict=True)
    environment_variables = isolated_runtime_environment()
    with tempfile.TemporaryDirectory(prefix="mke-numeric-retrieval-") as temp:
        runtime_root = Path(temp).resolve()
        environment = runtime_root / "venv"
        installed_python = environment / "bin" / "python"
        installed_mke = environment / "bin" / "mke"
        allowed_root = runtime_root / "allowed"
        allowed_root.mkdir()
        fixture = allowed_root / "numeric-policy-proof.pdf"
        client = runtime_root / "mcp_client.py"
        client.write_text(_MCP_CLIENT_SOURCE)

        _run(
            [
                "uv",
                "venv",
                str(environment),
                "--python",
                config.python_version,
                "--no-python-downloads",
            ],
            cwd=runtime_root,
            environment=environment_variables,
        )
        _run(
            wheel_install_command(installed_python, wheel),
            cwd=runtime_root,
            environment=environment_variables,
        )
        identity = _json_command(
            [
                str(installed_python),
                "-c",
                (
                    "import json,mke,sys;"
                    "print(json.dumps({'mke_file':mke.__file__,"
                    "'sys_executable':sys.executable}))"
                ),
            ],
            cwd=runtime_root,
            environment=environment_variables,
        )
        validate_installed_identity(
            identity,
            environment=environment,
            repository=repository,
        )
        _run(
            [str(installed_python), "-c", _FIXTURE_SOURCE, str(fixture)],
            cwd=runtime_root,
            environment=environment_variables,
        )

        cli_db = runtime_root / "cli.sqlite"
        _run(
            [str(installed_mke), "--db", str(cli_db), "ingest", str(fixture)],
            cwd=runtime_root,
            environment=environment_variables,
        )
        for query, page in (
            ("410000 grouped comma control", 1),
            ("410000 grouped space control", 2),
            ("410000 grouped hyphen control", 3),
            ("410000 grouped slash control", 4),
            ("410000 compact control", 5),
            ("410000 non adjacent control", None),
        ):
            _assert_cli_page(
                installed_mke,
                cli_db,
                "numeric-grouping-v1",
                query,
                page,
                cwd=runtime_root,
                environment=environment_variables,
            )
        _assert_cli_page(
            installed_mke,
            cli_db,
            "current",
            "410000 grouped comma control",
            None,
            cwd=runtime_root,
            environment=environment_variables,
        )
        _assert_cli_page(
            installed_mke,
            cli_db,
            "current",
            "410000 compact control",
            5,
            cwd=runtime_root,
            environment=environment_variables,
        )

        mcp_db = runtime_root / "mcp.sqlite"
        common = [
            str(installed_python),
            str(client),
            "--mke",
            str(installed_mke),
            "--db",
            str(mcp_db),
            "--root",
            str(allowed_root),
            "--fixture",
            fixture.name,
        ]
        promoted = _json_command(
            [*common, "--policy", "numeric-grouping-v1", "--ingest"],
            cwd=runtime_root,
            environment=environment_variables,
        )
        rollback = _json_command(
            [*common, "--policy", "current"],
            cwd=runtime_root,
            environment=environment_variables,
        )
        if promoted.get("status") != "passed" or rollback.get("status") != "passed":
            raise RuntimeError("installed MCP retrieval proof failed")

    return {
        "status": "passed",
        "python": config.python_version,
        "cli": {
            "default_policy": "numeric-grouping-v1",
            "rollback_policy": "current",
            "grouped_variants": 4,
            "compact_preserved": True,
            "non_adjacent_rejected": True,
        },
        "mcp": {
            "default_policy": "numeric-grouping-v1",
            "rollback_policy": "current",
            "request_override_exposed": False,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="numeric_retrieval_deployment_proof.py")
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--python", choices=("3.12", "3.13"), required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = run_deployment_proof(
            DeploymentProofConfig(wheel=args.wheel, python_version=args.python)
        )
    except Exception:
        print(json.dumps({"status": "failed", "reason": "deployment_proof_failed"}))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
