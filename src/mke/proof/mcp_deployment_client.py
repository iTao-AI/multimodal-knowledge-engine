"""Installed-package stdio MCP SDK deployment proof client."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import stat
import threading
from collections.abc import Iterable, Mapping, Sequence
from datetime import timedelta
from pathlib import Path
from typing import Literal, TextIO, cast

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from pydantic import TypeAdapter

from mke.interfaces.mcp_schemas import (
    AskLibraryResponseV1,
    AskLibrarySuccessV1,
    SearchLibraryResponseV1,
    SearchLibrarySuccessV1,
)

_EXPECTED_TOOL_FIELDS: dict[str, frozenset[str]] = {
    "list_libraries": frozenset(),
    "ingest_file": frozenset({"path"}),
    "get_run": frozenset({"run_id"}),
    "search_library": frozenset({"query", "limit"}),
    "ask_library": frozenset({"question", "limit"}),
}
_EXPECTED_PORTABLE_TOOL_FIELDS = {
    "search_library_v1": frozenset({"query", "limit"}),
    "ask_library_v1": frozenset({"question", "limit"}),
}
_FORBIDDEN_SCHEMA_TERMS = (
    "provider",
    "model",
    "revision",
    "cache",
    "argv",
    "endpoint",
    "credential",
    "download",
)
_SAFE_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.!_+()-]{0,255}\Z")
_MODEL_PART_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}\Z")
_COMMIT_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
_REPORT_IDENTITY_FIELDS = (
    "provider",
    "model",
    "model_revision",
    "library_version",
    "device",
    "compute_type",
    "language",
    "detected_language",
    "model_source",
)
_MAX_SERVER_STDERR_BYTES = 256 * 1024
_MCP_FAILURE_STAGES = frozenset(
    {
        "startup",
        "schema",
        "ingest",
        "get_run",
        "search",
        "ask",
        "portable_search",
        "portable_ask",
        "shutdown",
        "flow_validation",
        "portable_validation",
        "stderr",
    }
)
McpFailureStage = Literal[
    "startup",
    "schema",
    "ingest",
    "get_run",
    "search",
    "ask",
    "portable_search",
    "portable_ask",
    "shutdown",
    "flow_validation",
    "portable_validation",
    "stderr",
]


class McpDeploymentFailure(RuntimeError):
    """Closed installed-MCP failure with stable stage and stderr metadata."""

    def __init__(
        self,
        stage: McpFailureStage,
        stderr: Mapping[str, object] | None = None,
    ) -> None:
        if stage not in _MCP_FAILURE_STAGES:
            raise ValueError("invalid MCP deployment failure stage")
        super().__init__("mcp_deployment_failed")
        candidate = dict(stderr or _empty_stderr_metadata())
        if not _mcp_failure_semantics_valid(stage, candidate):
            stage = "stderr"
            candidate = _empty_stderr_metadata(capture_failed=True)
        self.stage = stage
        self.stderr = candidate


class McpDiagnosticWriteError(RuntimeError):
    """Closed failure writing the operator-only MCP diagnostic."""


def _empty_stderr_metadata(*, capture_failed: bool = False) -> dict[str, object]:
    return {
        "bytes": 0,
        "sha256": hashlib.sha256(b"").hexdigest(),
        "overflow": False,
        "capture_failed": capture_failed,
    }


def _mcp_failure_semantics_valid(
    stage: object,
    stderr: Mapping[str, object],
) -> bool:
    if not isinstance(stage, str) or stage not in _MCP_FAILURE_STAGES:
        return False
    stderr_bytes = stderr.get("bytes")
    stderr_sha = stderr.get("sha256")
    overflow = stderr.get("overflow")
    capture_failed = stderr.get("capture_failed")
    if (
        set(stderr) != {"bytes", "sha256", "overflow", "capture_failed"}
        or type(stderr_bytes) is not int
        or stderr_bytes < 0
        or not isinstance(stderr_sha, str)
        or re.fullmatch(r"[0-9a-f]{64}", stderr_sha) is None
        or type(overflow) is not bool
        or type(capture_failed) is not bool
    ):
        return False
    if overflow is not (stderr_bytes > _MAX_SERVER_STDERR_BYTES):
        return False
    return (stage == "stderr") is (overflow or capture_failed)


class _BoundedStderrCapture:
    """Drain child stderr while retaining only closed bounded metadata."""

    def __init__(self) -> None:
        self._read_descriptor, write_descriptor = os.pipe()
        self.stream: TextIO = os.fdopen(
            write_descriptor,
            "w",
            encoding="utf-8",
            errors="replace",
            buffering=1,
        )
        self._bytes = 0
        self._digest = hashlib.sha256()
        self._capture_failed = False
        self._thread = threading.Thread(
            target=self._drain,
            name="mke-mcp-stderr-capture",
            daemon=True,
        )
        self._thread.start()

    def _drain(self) -> None:
        try:
            while True:
                chunk = os.read(self._read_descriptor, 64 * 1024)
                if not chunk:
                    return
                self._bytes += len(chunk)
                self._digest.update(chunk)
        except OSError:
            self._capture_failed = True
        finally:
            try:
                os.close(self._read_descriptor)
            except OSError:
                self._capture_failed = True

    def finish(self) -> dict[str, object]:
        try:
            self.stream.close()
        except OSError:
            self._capture_failed = True
        self._thread.join(timeout=5.0)
        if self._thread.is_alive():
            self._capture_failed = True
            try:
                os.close(self._read_descriptor)
            except OSError:
                pass
            self._thread.join(timeout=1.0)
        return {
            "bytes": self._bytes,
            "sha256": self._digest.hexdigest(),
            "overflow": self._bytes > _MAX_SERVER_STDERR_BYTES,
            "capture_failed": self._capture_failed or self._thread.is_alive(),
        }


async def run_mcp_flow(
    server: StdioServerParameters,
    fixture_name: str,
    *,
    provider_timeout_seconds: float,
    search_query: str = "evidence",
    ask_question: str = "evidence publication",
    expected_keyword: str = "evidence",
    expected_content_fingerprint: str | None = None,
    portable_evidence: bool = False,
) -> dict[str, object]:
    """Run the installed stdio MCP flow through the official Python SDK."""
    if provider_timeout_seconds <= 0:
        raise ValueError("provider timeout must be positive")
    timeout = timedelta(seconds=provider_timeout_seconds)
    try:
        capture = _BoundedStderrCapture()
    except OSError as error:
        raise McpDeploymentFailure(
            "stderr", _empty_stderr_metadata(capture_failed=True)
        ) from error
    stage: McpFailureStage = "startup"
    failure: Exception | None = None
    ingest: dict[str, object] = {}
    inspected: dict[str, object] = {}
    searched: dict[str, object] = {}
    asked: dict[str, object] = {}
    portable_searched: dict[str, object] | None = None
    portable_asked: dict[str, object] | None = None
    try:
        async with stdio_client(server, errlog=capture.stream) as (read, write):
            async with ClientSession(
                read,
                write,
                read_timeout_seconds=timeout,
            ) as session:
                await session.initialize()
                stage = "schema"
                listed = await session.list_tools()
                assert_public_tool_schemas(
                    listed.tools, require_portable=portable_evidence
                )

                stage = "ingest"
                ingest = tool_payload(
                    await session.call_tool("ingest_file", {"path": fixture_name})
                )
                run_id = _required_string(ingest, "run_id")
                stage = "get_run"
                inspected = tool_payload(
                    await session.call_tool("get_run", {"run_id": run_id})
                )
                stage = "search"
                searched = tool_payload(
                    await session.call_tool(
                        "search_library",
                        {"query": search_query, "limit": 5},
                    )
                )
                stage = "ask"
                asked = tool_payload(
                    await session.call_tool(
                        "ask_library",
                        {"question": ask_question, "limit": 5},
                    )
                )
                if portable_evidence:
                    stage = "portable_search"
                    portable_searched = tool_payload(
                        await session.call_tool(
                            "search_library_v1",
                            {"query": search_query, "limit": 5},
                        )
                    )
                    stage = "portable_ask"
                    portable_asked = tool_payload(
                        await session.call_tool(
                            "ask_library_v1",
                            {"question": ask_question, "limit": 5},
                        )
                    )
                stage = "shutdown"
    except Exception as error:
        failure = error
    stderr = capture.finish()
    if stderr["overflow"] is True or stderr["capture_failed"] is True:
        raise McpDeploymentFailure("stderr", stderr) from failure
    if failure is not None:
        raise McpDeploymentFailure(stage, stderr) from failure
    try:
        result = validate_mcp_flow(
            ingest,
            inspected,
            searched,
            asked,
            expected_keyword=expected_keyword,
        )
    except Exception as error:
        raise McpDeploymentFailure("flow_validation", stderr) from error
    if portable_evidence:
        try:
            if expected_content_fingerprint is None:
                raise ValueError(
                    "portable MCP proof requires the expected Source fingerprint"
                )
            portable = validate_portable_evidence(
                cast(dict[str, object], portable_searched),
                cast(dict[str, object], portable_asked),
                run_id=_required_string(ingest, "run_id"),
                content_fingerprint=expected_content_fingerprint,
                keyword=expected_keyword,
                media_duration_ms=cast(
                    int,
                    cast(dict[str, object], result["transcript_intake_report"])[
                        "media_duration_ms"
                    ],
                ),
            )
        except Exception as error:
            raise McpDeploymentFailure("portable_validation", stderr) from error
        result["evidence_ref"] = portable
        result["source_sha256"] = expected_content_fingerprint.removeprefix("sha256:")
        result["run_id"] = _required_string(ingest, "run_id")
        result["fixture"] = Path(fixture_name).suffix.removeprefix(".")
    return result


def run_mcp_flow_sync(
    server: StdioServerParameters,
    fixture_name: str,
    *,
    provider_timeout_seconds: float,
    search_query: str = "evidence",
    ask_question: str = "evidence publication",
    expected_keyword: str = "evidence",
    expected_content_fingerprint: str | None = None,
    portable_evidence: bool = False,
) -> dict[str, object]:
    return asyncio.run(
        run_mcp_flow(
            server,
            fixture_name,
            provider_timeout_seconds=provider_timeout_seconds,
            search_query=search_query,
            ask_question=ask_question,
            expected_keyword=expected_keyword,
            expected_content_fingerprint=expected_content_fingerprint,
            portable_evidence=portable_evidence,
        )
    )


def assert_public_tool_schemas(
    tools: Iterable[object], *, require_portable: bool = False
) -> None:
    """Require the stable public tool fields and reject owner runtime controls."""
    observed: dict[str, frozenset[str]] = {}
    for tool in tools:
        name = getattr(tool, "name", None)
        raw_schema = getattr(tool, "inputSchema", None)
        if not isinstance(name, str) or not isinstance(raw_schema, dict):
            raise ValueError("MCP tool schema is invalid")
        schema = cast(Mapping[str, object], raw_schema)
        rendered = json.dumps(schema, sort_keys=True).casefold()
        if any(term in rendered for term in _FORBIDDEN_SCHEMA_TERMS):
            raise ValueError("MCP tool schema exposes owner runtime controls")
        raw_properties = schema.get("properties", {})
        if not isinstance(raw_properties, dict):
            raise ValueError("MCP tool schema properties are invalid")
        properties = cast(Mapping[str, object], raw_properties)
        observed[name] = frozenset(str(field) for field in properties)

    for name, expected in _EXPECTED_TOOL_FIELDS.items():
        if observed.get(name) != expected:
            raise ValueError("MCP public tool schema mismatch")
    if require_portable:
        for name, expected in _EXPECTED_PORTABLE_TOOL_FIELDS.items():
            if observed.get(name) != expected:
                raise ValueError("MCP portable tool schema mismatch")


def validate_portable_evidence(
    searched: Mapping[str, object],
    asked: Mapping[str, object],
    *,
    run_id: str,
    content_fingerprint: str,
    keyword: str,
    media_duration_ms: int,
) -> dict[str, object]:
    search_root = TypeAdapter(SearchLibraryResponseV1).validate_python(searched).root
    ask_root = TypeAdapter(AskLibraryResponseV1).validate_python(asked).root
    if not isinstance(search_root, SearchLibrarySuccessV1) or not isinstance(
        ask_root, AskLibrarySuccessV1
    ):
        raise ValueError("MCP portable Evidence response failed")
    if not search_root.results or tuple(search_root.results) != tuple(ask_root.evidence):
        raise ValueError("MCP portable Search and Ask Evidence mismatch")
    matches = [
        item
        for item in search_root.results
        if item.content_fingerprint == content_fingerprint and item.run_id == run_id
    ]
    if len(matches) != 1:
        raise ValueError("MCP portable Source or Run identity mismatch")
    evidence = matches[0]
    locator = evidence.locator
    if (
        locator.kind != "timestamp_ms"
        or locator.end > media_duration_ms
        or keyword not in evidence.text.casefold()
    ):
        raise ValueError("MCP portable timestamp Evidence mismatch")
    return evidence.model_dump(mode="json")


def tool_payload(result: object) -> dict[str, object]:
    """Extract one object from structuredContent or a TextContent JSON fallback."""
    if bool(getattr(result, "isError", False)):
        raise ValueError("MCP tool call failed")
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return cast(dict[str, object], structured)

    raw_content = getattr(result, "content", None)
    if not isinstance(raw_content, list):
        raise ValueError("MCP tool result is missing content")
    content = cast(list[object], raw_content)
    for item in content:
        if isinstance(item, types.TextContent):
            try:
                payload = json.loads(item.text)
            except json.JSONDecodeError as error:
                raise ValueError("MCP tool result is not valid JSON") from error
            if isinstance(payload, dict):
                return cast(dict[str, object], payload)
    raise ValueError("MCP tool result is missing an object payload")


def validate_mcp_flow(
    ingest: dict[str, object],
    inspected: dict[str, object],
    searched: dict[str, object],
    asked: dict[str, object],
    *,
    expected_keyword: str = "evidence",
) -> dict[str, object]:
    if ingest.get("ok") is not True or ingest.get("run_state") != "published":
        raise ValueError("MCP ingest did not publish")
    run_id = _required_string(ingest, "run_id")
    raw_run = inspected.get("run")
    if (
        inspected.get("ok") is not True
        or not isinstance(raw_run, dict)
    ):
        raise ValueError("MCP Run inspection mismatch")
    run = cast(Mapping[str, object], raw_run)
    if run.get("run_id") != run_id or run.get("state") != "published":
        raise ValueError("MCP Run inspection mismatch")

    ingest_report = _required_report(ingest)
    inspected_report = _required_report(inspected)
    if ingest_report != inspected_report or not _is_public_transcript_report(ingest_report):
        raise ValueError("MCP transcript report mismatch")

    raw_results = searched.get("results")
    if (
        searched.get("ok") is not True
        or not isinstance(raw_results, list)
        or not raw_results
    ):
        raise ValueError("MCP Search returned no Evidence")
    results = cast(list[object], raw_results)
    if not all(
        _is_timestamp_evidence(item, keyword=expected_keyword) for item in results
    ):
        raise ValueError("MCP Search Evidence is invalid")

    raw_answer_evidence = asked.get("evidence")
    if (
        asked.get("ok") is not True
        or asked.get("answer_status") != "evidence_found"
        or not isinstance(raw_answer_evidence, list)
        or not raw_answer_evidence
    ):
        raise ValueError("MCP Ask did not return timestamp Evidence")
    answer_evidence = cast(list[object], raw_answer_evidence)
    if not all(_is_timestamp_evidence(item) for item in answer_evidence):
        raise ValueError("MCP Ask did not return timestamp Evidence")

    evidence_count = ingest.get("evidence_count")
    if type(evidence_count) is not int or evidence_count <= 0:
        raise ValueError("MCP ingest Evidence count is invalid")
    return {
        "status": "passed",
        "run_state": "published",
        "evidence_count": evidence_count,
        "search_keyword_matched": True,
        "ask_status": "evidence_found",
        "transcript_intake_report": ingest_report,
    }


def _is_timestamp_evidence(value: object, *, keyword: str | None = None) -> bool:
    if not isinstance(value, dict):
        return False
    evidence = cast(Mapping[str, object], value)
    raw_locator = evidence.get("locator")
    text = evidence.get("text")
    if not isinstance(raw_locator, dict) or not isinstance(text, str):
        return False
    locator = cast(Mapping[str, object], raw_locator)
    start = locator.get("start")
    end = locator.get("end")
    return (
        locator.get("kind") == "timestamp_ms"
        and type(start) is int
        and type(end) is int
        and start >= 0
        and end > start
        and (keyword is None or keyword in text.casefold())
    )


def _required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError("MCP result is missing a required identifier")
    return value


def _required_report(payload: dict[str, object]) -> dict[str, object]:
    report = payload.get("transcript_intake_report")
    if not isinstance(report, dict):
        raise ValueError("MCP result is missing the transcript report")
    return cast(dict[str, object], report)


def _is_public_transcript_report(report: Mapping[str, object]) -> bool:
    if report.get("provider") != "faster-whisper" or report.get("model_source") != "cache":
        return False
    if not _is_safe_model(report.get("model")):
        return False
    revision = report.get("model_revision")
    if not isinstance(revision, str) or _COMMIT_SHA_RE.fullmatch(revision) is None:
        return False
    for field in _REPORT_IDENTITY_FIELDS:
        if field in {"model", "model_revision"}:
            continue
        value = report.get(field)
        if not isinstance(value, str) or _SAFE_TOKEN_RE.fullmatch(value) is None:
            return False
    for field in ("media_duration_ms", "segment_count"):
        value = report.get(field)
        if type(value) is not int or value <= 0:
            return False
    duration = report.get("transcription_duration_ms")
    return type(duration) is int and duration >= 0


def _is_safe_model(value: object) -> bool:
    if not isinstance(value, str):
        return False
    if _SAFE_TOKEN_RE.fullmatch(value) is not None:
        return True
    parts = value.split("/")
    return len(parts) == 2 and all(_MODEL_PART_RE.fullmatch(part) for part in parts)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m mke.proof.mcp_deployment_client")
    parser.add_argument("--mke-command", required=True)
    parser.add_argument("--fixture-name", required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--allowed-root", type=Path, required=True)
    parser.add_argument("--child-cwd", type=Path, required=True)
    parser.add_argument("--diagnostic", type=Path, required=True)
    parser.add_argument("--model", default="small")
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--language", default="auto")
    parser.add_argument("--model-cache", type=Path)
    parser.add_argument("--transcription-timeout-seconds", type=float, default=900.0)
    parser.add_argument("--direct-audio-footprint-bytes", type=_positive_int)
    parser.add_argument(
        "--direct-audio-footprint-budget-mode",
        choices=("baseline_plus",),
    )
    parser.add_argument("--search-query", default="evidence")
    parser.add_argument("--ask-question", default="evidence publication")
    parser.add_argument("--expected-keyword", default="evidence")
    parser.add_argument("--expected-content-fingerprint")
    parser.add_argument("--portable-evidence", action="store_true")
    return parser


def _approved_child_environment(cwd: Path) -> dict[str, str]:
    try:
        resolved = cwd.resolve(strict=True)
        process_cwd = Path.cwd().resolve(strict=True)
    except OSError as error:
        raise McpDeploymentFailure("startup") from error
    if (
        not cwd.is_absolute()
        or cwd != Path(os.path.normpath(os.fspath(cwd)))
        or cwd != resolved
        or resolved != process_cwd
        or not resolved.is_dir()
    ):
        raise McpDeploymentFailure("startup")
    required = {
        "HOME": str(cwd / "home"),
        "TMPDIR": str(cwd / "tmp"),
        "XDG_CACHE_HOME": str(cwd / "cache"),
        "PIP_CONFIG_FILE": os.devnull,
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "UV_OFFLINE": "1",
    }
    for key, expected in required.items():
        if os.environ.get(key) != expected:
            raise McpDeploymentFailure("startup")
    for key in ("HOME", "TMPDIR", "XDG_CACHE_HOME"):
        path = Path(required[key])
        try:
            if path.resolve(strict=True) != path or not path.is_dir():
                raise McpDeploymentFailure("startup")
        except OSError as error:
            raise McpDeploymentFailure("startup") from error
    return {
        **required,
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "C",
        "LC_ALL": "C",
        "LOGNAME": "",
        "SHELL": "",
        "TERM": "dumb",
        "USER": "",
    }


def write_mcp_diagnostic(path: Path, failure: McpDeploymentFailure) -> None:
    payload = {
        "schema_version": "mke.mcp_deployment_diagnostic.v1",
        "status": "failed",
        "failure": "mcp_deployment_failed",
        "stage": failure.stage,
        "stderr": failure.stderr,
    }
    value = (
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
        + b"\n"
    )
    parent_descriptor: int | None = None
    descriptor: int | None = None
    identity: tuple[int, int] | None = None
    write_failure: BaseException | None = None
    try:
        if not path.is_absolute() or path != Path(os.path.normpath(os.fspath(path))):
            raise OSError("diagnostic path is not absolute and normalized")
        parent = path.parent.resolve(strict=True)
        if path != parent / path.name:
            raise OSError("diagnostic path is not canonical")
        parent_descriptor = os.open(
            parent,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        descriptor = os.open(
            path.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_descriptor,
        )
        observed = os.fstat(descriptor)
        if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
            raise OSError("diagnostic target is not an owned regular file")
        identity = (observed.st_dev, observed.st_ino)
        os.fchmod(descriptor, 0o600)
        remaining = memoryview(value)
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise OSError("diagnostic write made no progress")
            remaining = remaining[written:]
        os.fsync(descriptor)
    except (OSError, RuntimeError) as error:
        write_failure = error
    if descriptor is not None:
        try:
            os.close(descriptor)
        except OSError as error:
            if write_failure is None:
                write_failure = error
    if write_failure is not None and parent_descriptor is not None and identity is not None:
        try:
            current = os.stat(
                path.name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
            if stat.S_ISREG(current.st_mode) and (current.st_dev, current.st_ino) == identity:
                os.unlink(path.name, dir_fd=parent_descriptor)
        except OSError:
            pass
    if parent_descriptor is not None:
        try:
            os.close(parent_descriptor)
        except OSError as error:
            if write_failure is None:
                write_failure = error
    if write_failure is not None:
        raise McpDiagnosticWriteError("mcp_diagnostic_write_failed") from write_failure


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("value must be a positive integer") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if (args.direct_audio_footprint_bytes is None) != (
        args.direct_audio_footprint_budget_mode is None
    ):
        parser.error("direct audio supervision controls must be configured together")
    server_args = [
        "--db",
        str(args.db),
        "mcp",
        "--allowed-root",
        str(args.allowed_root),
        "--transcript-provider",
        "faster-whisper",
        "--model",
        args.model,
        "--model-revision",
        args.model_revision,
        "--device",
        args.device,
        "--compute-type",
        args.compute_type,
        "--language",
        args.language,
        "--transcription-timeout-seconds",
        str(args.transcription_timeout_seconds),
    ]
    if args.model_cache is not None:
        server_args.extend(("--model-cache", str(args.model_cache)))
    if args.direct_audio_footprint_bytes is not None:
        server_args.extend(
            (
                "--direct-audio-footprint-bytes",
                str(args.direct_audio_footprint_bytes),
                "--direct-audio-footprint-budget-mode",
                args.direct_audio_footprint_budget_mode,
            )
        )
    try:
        child_environment = _approved_child_environment(args.child_cwd)
        report = run_mcp_flow_sync(
            StdioServerParameters(
                command=args.mke_command,
                args=server_args,
                cwd=args.child_cwd,
                env=child_environment,
            ),
            args.fixture_name,
            provider_timeout_seconds=args.transcription_timeout_seconds,
            search_query=args.search_query,
            ask_question=args.ask_question,
            expected_keyword=args.expected_keyword,
            expected_content_fingerprint=args.expected_content_fingerprint,
            portable_evidence=args.portable_evidence,
        )
    except McpDeploymentFailure as failure:
        try:
            write_mcp_diagnostic(args.diagnostic, failure)
        except McpDiagnosticWriteError:
            pass
        print(json.dumps({"status": "failed", "reason": "mcp_deployment_failed"}))
        return 1
    except Exception:
        try:
            write_mcp_diagnostic(args.diagnostic, McpDeploymentFailure("startup"))
        except McpDiagnosticWriteError:
            pass
        print(json.dumps({"status": "failed", "reason": "mcp_deployment_failed"}))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
