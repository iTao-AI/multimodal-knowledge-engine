#!/usr/bin/env python3
"""External installed-wheel Source consumer; controlled negative cases exit 1."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import sys
import time
import traceback
import uuid
from collections.abc import AsyncGenerator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent

from mke.interfaces.source_ask_schemas import SourceAskResponseV1, SourceAskSuccessV1

SCHEMA = "mke.source_evidence_installed_consumer.v1"
CASE_CODES = {
    "mismatch": "identity_mismatch_detected",
    "stale": "stale_publication_detected",
    "read_failure": "read_replacement_detected",
    "citation_failure": "citation_corruption_detected",
}
SCOPE_KEYS = (
    "source_id",
    "publication_id",
    "publication_revision",
    "run_id",
    "content_fingerprint",
)


def adjacent(name: str) -> Any:
    path = Path(__file__).with_name(name + ".py")
    spec = importlib.util.spec_from_file_location("m3_" + name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("consumer asset missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pack = adjacent("consumer_source_pack_client")
processes = adjacent("consumer_source_pack_proof")
example = adjacent("source_evidence_consumer")

if TYPE_CHECKING:
    from scripts.consumer_source_pack_client import BoundedStderrCapture
else:
    BoundedStderrCapture = pack.BoundedStderrCapture


class CaseFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def require(value: bool, code: str) -> None:
    if not value:
        raise CaseFailure(code)


def encoded(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


@dataclass(frozen=True)
class Config:
    work_dir: Path
    assets: Path
    schemas: Path
    mke: Path
    environment: Mapping[str, str]


def load_assets(root: Path) -> dict[str, dict[str, Any]]:
    try:
        manifest = json.loads((root / "manifest.json").read_bytes())
        require(
            set(manifest) == {"schema_version", "sources"}
            and manifest["schema_version"] == "mke.source_evidence_installed_manifest.v1",
            "asset_identity_invalid",
        )
        require(
            isinstance(manifest["sources"], list) and len(manifest["sources"]) == 2,
            "asset_identity_invalid",
        )
        result: dict[str, dict[str, Any]] = {}
        for entry in manifest["sources"]:
            require(
                set(entry) == {"role", "filename", "bytes", "sha256", "pages"},
                "asset_identity_invalid",
            )
            role = entry["role"]
            require(
                role in {"selected", "other"}
                and role not in result
                and entry["filename"] == role + ".pdf",
                "asset_identity_invalid",
            )
            content = (root / entry["filename"]).read_bytes()
            require(
                type(entry["bytes"]) is int
                and len(content) == entry["bytes"]
                and hashlib.sha256(content).hexdigest() == entry["sha256"],
                "asset_identity_invalid",
            )
            require(
                type(entry["pages"]) is int and entry["pages"] == (3 if role == "selected" else 5),
                "asset_identity_invalid",
            )
            result[role] = entry
        return result
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise CaseFailure("asset_identity_invalid") from error


def diagnostics_root(cfg: Config) -> Path:
    path = cfg.work_dir / "diagnostics"
    path.mkdir(exist_ok=True)
    return path


def record_exception(cfg: Config, phase: str, error: Exception) -> None:
    text = "".join(traceback.format_exception(error)).encode()[:65536].decode(errors="replace")
    (diagnostics_root(cfg) / "failure.json").write_bytes(
        encoded({"phase": phase, "error_type": type(error).__name__, "traceback": text})
    )


def cli(cfg: Config, *args: str) -> Any:
    command = [
        str(cfg.mke),
        "--db",
        str(cfg.work_dir / "library.sqlite"),
        "--retrieval-strategy",
        "current",
        *args,
    ]
    try:
        result = processes.run_bounded(
            command,
            cwd=cfg.work_dir,
            env=cfg.environment,
            timeout_seconds=15,
            max_stdout_bytes=2 * 1024 * 1024,
            max_stderr_bytes=65536,
        )
    except processes.ControllerError as error:
        diagnostic = {
            "argv": command,
            "code": error.code,
            "stdout": error.stdout.decode(errors="replace"),
            "stderr": error.stderr.decode(errors="replace"),
        }
        with (diagnostics_root(cfg) / "cli.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(encoded(diagnostic).decode() + "\n")
        raise
    with (diagnostics_root(cfg) / "cli.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(
            encoded(
                {
                    "argv": command,
                    "returncode": result.returncode,
                    "stdout": result.stdout.decode(errors="replace"),
                    "stderr": result.stderr.decode(errors="replace"),
                }
            ).decode()
            + "\n"
        )
    return result


class DiagnosticStderrCapture(BoundedStderrCapture):
    """Keep M3 stderr bytes while reusing the bounded pipe's lifecycle/deadlines."""

    def __init__(self, destination: Path, max_bytes: int) -> None:
        super().__init__(max_bytes)
        self.destination = destination

    async def _drain(self) -> None:
        assert self._read_fd is not None
        retained = 0
        with self.destination.open("xb") as stream:
            try:
                while True:
                    chunk = await asyncio.to_thread(os.read, self._read_fd, 4096)
                    if not chunk:
                        return
                    prefix = chunk[: max(0, self.max_bytes - retained)]
                    stream.write(prefix)
                    stream.flush()
                    retained += len(prefix)
                    self.bytes_seen += len(chunk)
                    if self.bytes_seen > self.max_bytes:
                        self.overflow_observed_at = time.monotonic()
                        self.overflow.set()
                        if self.errlog is not None:
                            self.errlog.close()
                        os.close(self._read_fd)
                        self._read_fd = None
                        return
            except (OSError, asyncio.CancelledError):
                return


class BoundedSession:
    def __init__(self, native: ClientSession, capture: Any, diagnostic: Path) -> None:
        self.native, self.capture, self.diagnostic = native, capture, diagnostic

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        result = cast(
            CallToolResult,
            await pack._deadline(
                self.native.call_tool(name, arguments), 15, "mcp_tool_timeout", self.capture
            ),
        )
        if result.isError:
            payload = encoded({"tool": name, "response": result.model_dump(mode="json")})
            if len(payload) <= 98304:
                self.diagnostic.write_bytes(payload)
        return result


class SearchCapture:
    """Retain the native first-page matches which the example fully verifies."""

    def __init__(self, client: BoundedSession) -> None:
        self.client = client
        self.matches: list[dict[str, Any]] | None = None

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        result = await self.client.call_tool(name, arguments)
        if name == "search_source_evidence_v1" and result.structuredContent is not None:
            self.matches = copy.deepcopy(result.structuredContent.get("matches"))
        return result


@asynccontextmanager
async def session(cfg: Config) -> AsyncGenerator[BoundedSession, None]:
    params = StdioServerParameters(
        command=str(cfg.mke),
        args=[
            "--db",
            str(cfg.work_dir / "library.sqlite"),
            "--retrieval-strategy",
            "current",
            "mcp",
            "--allowed-root",
            str(cfg.assets),
        ],
        cwd=str(cfg.work_dir),
        env=dict(cfg.environment),
    )
    destination = diagnostics_root(cfg) / ("sdk-" + uuid.uuid4().hex + ".stderr.log")
    async with DiagnosticStderrCapture(destination, 65536) as capture:
        async with stdio_client(params, errlog=capture.write_end) as (read, write):
            async with ClientSession(
                read, write, read_timeout_seconds=timedelta(seconds=15)
            ) as native:
                await pack._deadline(native.initialize(), 15, "mcp_startup_timeout", capture)
                tools = await pack._deadline(native.list_tools(), 15, "mcp_tool_timeout", capture)
                expected = pack.load_current_schema_expectations(cfg.schemas)
                pack.validate_tool_schemas(tools.tools, expected)
                require(len(tools.tools) == 15, "tool_inventory_invalid")
                yield BoundedSession(native, capture, cfg.work_dir / "sdk-error.json")
        require(not capture.overflow.is_set(), "command_output_exceeded")


async def selected_pairs(
    client: BoundedSession, assets: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    packet = example.validated(
        example.ListSourcesResponseV1,
        await example.checked_call(client, "list_sources_v1", {"page_size": 20}),
    ).root
    require(
        isinstance(packet, example.ListSourcesSuccessV1)
        and packet.selection.status == "complete"
        and len(packet.sources) == 2,
        "source_identity_invalid",
    )
    result: dict[str, dict[str, Any]] = {}
    for role, entry in assets.items():
        rows = [
            row for row in packet.sources if row.content_fingerprint == "sha256:" + entry["sha256"]
        ]
        require(len(rows) == 1, "source_identity_invalid")
        source, _ = await example.discover_source(client, rows[0].source_id, rows[0].publication_id)
        result[role] = example.SourceSearchScopeV1(
            **{key: getattr(source, key) for key in SCOPE_KEYS}
        ).model_dump(mode="json")
    require(
        result["selected"]["source_id"] != result["other"]["source_id"], "source_identity_invalid"
    )
    return result


def validate_ask(value: Any, scope: dict[str, Any], question: str) -> dict[str, Any]:
    try:
        require(len(encoded(value)) <= 32768, "cli_packet_invalid")
        packet = SourceAskResponseV1.model_validate(value).root
        require(isinstance(packet, SourceAskSuccessV1), "cli_packet_invalid")
        packet = cast(SourceAskSuccessV1, packet)
        require(
            packet.scope.model_dump(mode="json") == scope and packet.question == question,
            "cli_packet_invalid",
        )
        for match in packet.evidence:
            require(
                all(getattr(match.evidence, key) == scope[key] for key in SCOPE_KEYS)
                and match.read.evidence_id == match.evidence.evidence_id,
                "cli_packet_invalid",
            )
        return packet.model_dump(mode="json")
    except (ValueError, KeyError, TypeError) as error:
        raise CaseFailure("cli_packet_invalid") from error


async def run_flow(cfg: Config) -> dict[str, Any]:
    assets = load_assets(cfg.assets)
    require(not cfg.work_dir.exists(), "work_directory_exists")
    cfg.work_dir.mkdir()
    for role in ("selected", "other"):
        result = await asyncio.to_thread(
            cli, cfg, "ingest", str(cfg.assets / assets[role]["filename"]), "--json"
        )
        require(
            result.returncode == 0,
            "ingest_failed",
        )
    async with asyncio.timeout(90):
        async with session(cfg) as client:
            pairs = await selected_pairs(client, assets)
    target = pairs["selected"]
    results: list[dict[str, Any]] = []
    for label, question, limit in [
        ("first-page", "needle", 1),
        ("complete", "needle", 3),
        ("empty", "outsideonly", 3),
    ]:
        command = await asyncio.to_thread(
            cli,
            cfg,
            "ask",
            question,
            "--source-id",
            target["source_id"],
            "--publication-id",
            target["publication_id"],
            "--limit",
            str(limit),
            "--json",
        )
        require(command.returncode == 0, "cli_ask_failed")
        packet = validate_ask(json.loads(command.stdout), target, question)
        (cfg.work_dir / f"cli-{label}.json").write_bytes(encoded(packet))
        async with asyncio.timeout(90):
            async with session(cfg) as client:
                captured = SearchCapture(client)
                receipt = await example.consume_source_evidence(
                    captured,
                    target["source_id"],
                    target["publication_id"],
                    question,
                    limit=limit,
                    max_read_bytes=4,
                )
        require(
            receipt["scope"] == packet["scope"]
            and receipt["authority_snapshot"] == packet["authority_snapshot"]
            and receipt["selection"] == packet["selection"]
            and receipt["limitations"] == packet["limitations"],
            "cli_sdk_mismatch",
        )
        require(
            captured.matches == packet["evidence"],
            "cli_sdk_mismatch",
        )
        results.append(receipt)
    unrelated = await asyncio.to_thread(cli, cfg, "ask", "outsideonly")
    require(
        unrelated.returncode == 0 and b"outsideonly" in unrelated.stdout, "unrelated_match_missing"
    )
    require(
        results[0]["selection"]["status"] == "more_available"
        and len(results[0]["references"]) == 1,
        "selection_invalid",
    )
    require(
        results[1]["selection"]["status"] == "complete" and len(results[1]["references"]) == 3,
        "selection_invalid",
    )
    require(
        results[2]["answer_status"] == "insufficient_evidence"
        and results[2]["selection"]["status"] == "complete"
        and results[2]["references"] == [],
        "selected_empty_invalid",
    )
    (cfg.work_dir / "selected-pairs.json").write_bytes(encoded(pairs))
    return {
        "schema_version": SCHEMA,
        "status": "passed",
        "tool_count": 15,
        "source_count": 2,
        "scope": target,
        "authority_snapshot": results[1]["authority_snapshot"],
        "references": results[1]["references"],
        "asset_sha256": {role: entry["sha256"] for role, entry in assets.items()},
        "cases": {
            "first_page": "more_available",
            "complete": "complete",
            "selected_empty": "insufficient_evidence",
            "unrelated_match": True,
            "cli_sdk_equal": True,
            "utf8_digest_and_excerpt_verified": True,
        },
    }


async def replace_source(client: BoundedSession) -> None:
    # The legacy tool uses top-level arguments; versioned tools use request DTOs.
    payload = pack._tool_payload(await client.call_tool("ingest_file", {"path": "selected.pdf"}))
    require(payload.get("ok") is True, "replacement_failed")


class ReadFault:
    def __init__(self, client: BoundedSession, case: str) -> None:
        self.client, self.case = client, case
        self.first_id: str | None = None
        self.first_complete = False
        self.exercised = False

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        args = (arguments or {}).get("request", {})
        if name == "read_evidence_v1" and "evidence_id" in args:
            if self.first_id is None:
                self.first_id = args["evidence_id"]
            elif args["evidence_id"] != self.first_id and self.case == "read_failure":
                await replace_source(self.client)
                self.exercised = True
        result = await self.client.call_tool(name, arguments)
        payload = result.structuredContent
        if name == "read_evidence_v1" and payload and payload.get("ok") is True:
            if payload["evidence"]["evidence_id"] == self.first_id and payload["complete"]:
                self.first_complete = True
            if (
                payload["evidence"]["evidence_id"] != self.first_id
                and self.case == "citation_failure"
                and not self.exercised
            ):
                damaged = copy.deepcopy(payload)
                text = damaged["content"]["text"]
                damaged["content"]["text"] = ("X" if text[0] != "X" else "Y") + text[1:]
                result = CallToolResult(
                    structuredContent=damaged,
                    content=[TextContent(type="text", text=encoded(damaged).decode())],
                )
                self.exercised = True
        return result


async def run_negative(cfg: Config, case: str) -> None:
    assets = load_assets(cfg.assets)
    require((cfg.work_dir / "library.sqlite").is_file(), "library_missing")
    require(case in CASE_CODES, "case_invalid")
    fault: ReadFault | None = None
    async with asyncio.timeout(90):
        async with session(cfg) as client:
            pairs = await selected_pairs(client, assets)
            target = pairs["selected"]
            publication = target["publication_id"]
            if case == "mismatch":
                publication = pairs["other"]["publication_id"]
            elif case == "stale":
                await replace_source(client)
            if case in {"read_failure", "citation_failure"}:
                fault = ReadFault(client, case)
            try:
                await example.consume_source_evidence(
                    fault or client,
                    target["source_id"],
                    publication,
                    "needle",
                    limit=3,
                    max_read_bytes=4,
                )
            except example.ConsumerFailure:
                if fault is not None:
                    require(
                        fault.first_complete and fault.exercised, "negative_boundary_not_exercised"
                    )
                    (cfg.work_dir / f"{case}-boundary.json").write_bytes(
                        encoded(
                            {
                                "first_reference_complete": True,
                                "native_boundary_exercised": True,
                                "successful_receipt_emitted": False,
                            }
                        )
                    )
            else:
                raise CaseFailure("negative_boundary_not_exercised")
    if case in {"mismatch", "stale"}:
        failure = await asyncio.to_thread(
            cli,
            cfg,
            "ask",
            "needle",
            "--source-id",
            target["source_id"],
            "--publication-id",
            publication,
            "--json",
        )
        payload = json.loads(failure.stdout)
        require(
            failure.returncode == 1
            and payload.get("ok") is False
            and payload.get("schema_version") == "mke.source_ask_response.v1"
            and "evidence" not in payload,
            "negative_boundary_not_exercised",
        )
    raise CaseFailure(CASE_CODES[case])


async def run_case(cfg: Config, case: str) -> dict[str, Any]:
    owned = (
        not cfg.work_dir.exists()
        if case == "flow"
        else (cfg.work_dir / "selected-pairs.json").is_file()
    )
    try:
        async with asyncio.timeout(90):
            if case == "flow":
                return await run_flow(cfg)
            await run_negative(cfg, case)
            raise CaseFailure("negative_boundary_not_exercised")
    except Exception as error:
        expected = isinstance(error, CaseFailure) and error.code in CASE_CODES.values()
        if owned and not expected and (cfg.work_dir / "diagnostics").is_dir():
            record_exception(cfg, case, error)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mke", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--schemas", type=Path, required=True)
    parser.add_argument("--case", choices=["flow", *CASE_CODES], default="flow")
    args = parser.parse_args(argv)
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}
    }
    cfg = Config(
        args.work_dir.resolve(),
        args.assets.resolve(),
        args.schemas.resolve(),
        args.mke.absolute(),
        environment,
    )
    try:
        import mke

        require(
            bool(sys.flags.isolated)
            and Path(mke.__file__).resolve().parent.parent.name == "site-packages"
            and cfg.mke.parent.resolve() == Path(sys.executable).parent.resolve(),
            "installed_identity_failed",
        )

        result = asyncio.run(run_case(cfg, args.case))
        require(len(encoded(result)) <= 32768, "consumer_output_exceeded")
    except CaseFailure as error:
        result = {"schema_version": SCHEMA, "status": "failed", "code": error.code}
    except Exception:
        result = {"schema_version": SCHEMA, "status": "failed", "code": "consumer_failed"}
    print(encoded(result).decode())
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
