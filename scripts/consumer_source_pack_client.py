"""Standalone consumer for the installed source-pack proof.

This file intentionally uses only Python's standard library for source-pack
manifest parsing and preflight identity verification.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from io import TextIOWrapper
from pathlib import Path, PurePosixPath
from typing import Any, Protocol, TextIO, cast

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

_MANIFEST_SCHEMA = "mke.consumer_source_pack_manifest.v1"
_PACK_ID = "local-knowledge-v1"
_SCHEMA_EXPECTATIONS_VERSION = "mke.consumer_mcp_tool_expectations.v1"
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_MANIFEST_KEYS = {"schema_version", "pack_id", "sources", "queries"}
_SOURCE_KEYS = {
    "source_key",
    "relative_filename",
    "media_type",
    "bytes",
    "sha256",
    "redistribution_class",
    "generator",
}
_POSITIVE_QUERY_KEYS = {
    "role",
    "query",
    "expected_source_key",
    "locator_kind",
    "allowed_locator_range",
}
_UNSUPPORTED_QUERY_KEYS = {
    "role",
    "query",
    "expected_search_status",
    "expected_ask_status",
}
_MACHINE_TOKEN_RE = re.compile(r"[a-z][a-z0-9_]{0,127}\Z")
_ID_RES = {
    prefix: re.compile(prefix + r"[0-9a-f]{32}\Z") for prefix in ("src_", "run_", "pub_", "ev_")
}
_FINGERPRINT_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SAFE_CAUSES = frozenset(
    {
        "embedding output dtype must be float32",
        "video transcript format is unsupported",
        "configured embedding model revision is unavailable",
        "transcript command timed out",
        "unsupported codec for local video proof",
        "CJK candidate pool exceeded the configured cap",
        "PDF has no extractable text",
        "transcript command failed",
        "configured embedding model snapshot is incomplete",
        "video transcript segment exceeds media duration",
        "transcript command produced too much stderr",
        "video transcript sidecar is not valid JSON",
        "video transcript sidecar must be a JSON object",
        "question must not be empty",
        "PDF cannot be opened",
        "limit must be between 1 and 20",
        "timestamp locators must be integer milliseconds",
        "video transcript exceeds segment limit",
        "demo fixture is missing",
        "vector projection replace failed",
        "video transcript sidecar missing media",
        "vector projection distance is invalid",
        "embedding tokenizer output is invalid",
        "transcript command is required",
        "PDF input exceeds 100 MB limit",
        "embedding model download failed",
        "vector extension is unavailable or incompatible",
        "vector projection inventory is incomplete",
        "transcription optional dependency is not installed",
        "embedding optional dependency is not installed",
        "file path cannot be resolved",
        "configured embedding model is not cached",
        "input path must be a file",
        "question must contain at least one searchable ASCII token",
        "input file does not exist",
        "video transcript missing media",
        "embedding output contains non-finite values",
        "embedding cancelled",
        "embedding model cache is not readable",
        "unknown run",
        "stable timestamp locator generation requires sorted ranges",
        "vector projection identity mismatch",
        "transcription device or compute profile is unsupported",
        "CJK active Evidence scan would exceed configured local budget",
        "input video must be an MP4 file",
        "supported suffixes are .pdf and .mp4",
        "video transcript segment must be an object",
        "embedding adapter failed",
        "video must contain an audio track",
        "video input exceeds 100 MiB limit",
        "transcription failed",
        "transcript command executable is missing",
        "video transcript sidecar format is unsupported",
        "transcript command stdout is not valid UTF-8",
        "configured embedding model snapshot exceeds size limit",
        "configured language is not supported by the model",
        "transcript schema validation failed",
        "transcription model download failed",
        "video transcript must be a JSON object",
        "configured transcription model revision is unavailable",
        "vector projection search inventory is incomplete",
        "stable timestamp locator generation requires increasing ranges",
        "operation failed; details were redacted",
        "demo video fixture is missing",
        "video transcript is not valid JSON",
        "input path must not be empty",
        "input video is missing",
        "configured transcription model is not cached",
        "Requested retrieval strategy is not supported by this runtime",
        "transcription model cache is not readable",
        "video transcript text must not be empty",
        "video media exceeds duration limit",
        "input video could not be read",
        "argv must contain exactly one {input} placeholder",
        "embedding output is not normalized",
        "input video is empty",
        "embedding output count is invalid",
        "embedding output dimension is invalid",
        "input path must be under allowed root",
        "embedding input would be truncated",
        "encrypted PDF is not supported",
        "query must not be empty",
        "transcription model resolution failed",
        "video transcript sidecar is missing",
        "transcript command produced too much stdout",
        "question must be 1000 characters or fewer",
        "video transcript must contain at least one segment",
        "Query does not contain enough eligible CJK terms",
        "video ingest initialization failed",
    }
)
_STABLE_FAILURE_CODES = frozenset(
    {
        "source_pack_manifest_invalid",
        "source_pack_identity_mismatch",
        "consumer_schema_invalid",
        "consumer_payload_invalid",
        "manifest_mapping_missing",
        "manifest_mapping_ambiguous",
        "manifest_locator_mismatch",
        "observation_state_mismatch",
        "mcp_startup_timeout",
        "mcp_tool_timeout",
        "mcp_transport_failed",
        "command_output_exceeded",
        "cleanup_failed",
        "proof_failed",
    }
)
_PUBLIC_ERROR_CONTRACT_KEYS = {
    "machine_token_pattern",
    "active_publication_impact",
    "safe_causes",
}
_MACHINE_TOKEN_PATTERN = "^[a-z][a-z0-9_]{0,127}$"


class DiscoveredTool(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def inputSchema(self) -> Mapping[str, object]: ...
    @property
    def outputSchema(self) -> Mapping[str, object] | None: ...


@dataclass(frozen=True)
class _ProofErrorData:
    code: str


class ProofError(_ProofErrorData, Exception):
    """Frozen proof failure with mutable BaseException bookkeeping."""


@dataclass(frozen=True)
class SourceEntry:
    source_key: str
    relative_filename: str
    media_type: str
    bytes: int
    sha256: str
    redistribution_class: str
    generator: str


@dataclass(frozen=True)
class QueryExpectation:
    role: str
    query: str
    expected_source_key: str | None
    locator_kind: str | None
    allowed_locator_range: tuple[int, int] | None
    expected_search_status: str | None
    expected_ask_status: str | None


@dataclass(frozen=True)
class SourcePack:
    schema_version: str
    pack_id: str
    sources: tuple[SourceEntry, ...]
    queries: tuple[QueryExpectation, ...]


@dataclass(frozen=True)
class ConsumerConfig:
    manifest: Path
    schemas: Path
    source_root: Path
    mke_executable: Path
    workspace: Path
    child_environment: dict[str, str]
    startup_timeout_seconds: float
    tool_timeout_seconds: float
    max_server_stderr_bytes: int


@dataclass(frozen=True)
class StoreResult:
    source_count: int
    published_run_count: int
    active_publication_count: int
    active_evidence_count: int
    observed_states: tuple[str, ...]
    receipts: tuple[dict[str, object], ...]
    strict_schema_validation: bool
    search_ask_projection_equal: bool
    exact_manifest_mapping: bool
    redaction: bool
    server_cleanup: bool


@dataclass(frozen=True)
class ConsumerResult:
    manifest_schema: str
    evidence_schema: str
    pack_id: str
    source_count: int
    published_run_count: int
    active_publication_count: int
    active_evidence_count: int
    observed_states: tuple[str, ...]
    receipts: tuple[dict[str, object], ...]
    strict_schema_validation: bool
    search_ask_projection_equal: bool
    exact_manifest_mapping: bool
    fresh_store_mapping: bool
    redaction: bool
    server_cleanup: bool


_APPROVED_SOURCES = (
    SourceEntry(
        source_key="operations_guide",
        relative_filename="operations-guide.pdf",
        media_type="application/pdf",
        bytes=1000,
        sha256="0ac3e96efc89ee91e48bb3efc8611de88b2698e5aa26c1f8e0e8f78ad2d60ddd",
        redistribution_class="repository_authored_synthetic",
        generator="scripts/generate_local_knowledge_fixtures.py",
    ),
    SourceEntry(
        source_key="incident_guide",
        relative_filename="incident-guide.pdf",
        media_type="application/pdf",
        bytes=990,
        sha256="ed55cfbe9bdbf4404eb9ff55ab7e51fac14006ae0584a14d50704f68a02ff699",
        redistribution_class="repository_authored_synthetic",
        generator="scripts/generate_local_knowledge_fixtures.py",
    ),
)
_APPROVED_QUERIES = (
    QueryExpectation(
        role="operations_guide",
        query="Cedar Relay maintenance window",
        expected_source_key="operations_guide",
        locator_kind="page",
        allowed_locator_range=(1, 1),
        expected_search_status=None,
        expected_ask_status=None,
    ),
    QueryExpectation(
        role="incident_guide",
        query="Cedar Relay telemetry amber",
        expected_source_key="incident_guide",
        locator_kind="page",
        allowed_locator_range=(1, 1),
        expected_search_status=None,
        expected_ask_status=None,
    ),
    QueryExpectation(
        role="unsupported",
        query="lunar payroll retention policy",
        expected_source_key=None,
        locator_kind=None,
        allowed_locator_range=None,
        expected_search_status="no_match",
        expected_ask_status="insufficient_evidence",
    ),
)


def _manifest_error() -> ProofError:
    return ProofError("source_pack_manifest_invalid")


def _require_object(value: object, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict):
        raise _manifest_error()
    mapping = cast(dict[object, object], value)
    if set(mapping) != keys:
        raise _manifest_error()
    return cast(dict[str, object], value)


def _require_string(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise _manifest_error()
    return value


def _parse_source(value: object) -> SourceEntry:
    source = _require_object(value, _SOURCE_KEYS)
    source_key = _require_string(source["source_key"])
    relative_filename = _require_string(source["relative_filename"])
    relative_path = PurePosixPath(relative_filename)
    if (
        relative_path.is_absolute()
        or ".." in relative_path.parts
        or str(relative_path) != relative_filename
        or relative_filename in {".", ""}
    ):
        raise _manifest_error()
    byte_count = source["bytes"]
    if isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count < 1:
        raise _manifest_error()
    digest = _require_string(source["sha256"])
    if _SHA256_RE.fullmatch(digest) is None:
        raise _manifest_error()
    media_type = _require_string(source["media_type"])
    redistribution_class = _require_string(source["redistribution_class"])
    generator = _require_string(source["generator"])
    if media_type != "application/pdf":
        raise _manifest_error()
    if redistribution_class != "repository_authored_synthetic":
        raise _manifest_error()
    if generator != "scripts/generate_local_knowledge_fixtures.py":
        raise _manifest_error()
    return SourceEntry(
        source_key=source_key,
        relative_filename=relative_filename,
        media_type=media_type,
        bytes=byte_count,
        sha256=digest,
        redistribution_class=redistribution_class,
        generator=generator,
    )


def _parse_query(value: object, source_keys: set[str]) -> QueryExpectation:
    if not isinstance(value, dict):
        raise _manifest_error()
    value = cast(dict[str, object], value)
    keys = set(value)
    role = _require_string(value.get("role"))
    query = _require_string(value.get("query"))
    if keys == _POSITIVE_QUERY_KEYS:
        expected_source_key = _require_string(value["expected_source_key"])
        if expected_source_key not in source_keys or value["locator_kind"] != "page":
            raise _manifest_error()
        locator_range = value["allowed_locator_range"]
        if not isinstance(locator_range, list):
            raise _manifest_error()
        locator_values = cast(list[object], locator_range)
        if len(locator_values) != 2:
            raise _manifest_error()
        locator_start, locator_end = locator_values
        if (
            isinstance(locator_start, bool)
            or not isinstance(locator_start, int)
            or isinstance(locator_end, bool)
            or not isinstance(locator_end, int)
            or locator_start < 1
            or locator_start > locator_end
        ):
            raise _manifest_error()
        return QueryExpectation(
            role=role,
            query=query,
            expected_source_key=expected_source_key,
            locator_kind="page",
            allowed_locator_range=(locator_start, locator_end),
            expected_search_status=None,
            expected_ask_status=None,
        )
    if keys == _UNSUPPORTED_QUERY_KEYS:
        if (
            value["expected_search_status"] != "no_match"
            or value["expected_ask_status"] != "insufficient_evidence"
        ):
            raise _manifest_error()
        return QueryExpectation(
            role=role,
            query=query,
            expected_source_key=None,
            locator_kind=None,
            allowed_locator_range=None,
            expected_search_status="no_match",
            expected_ask_status="insufficient_evidence",
        )
    raise _manifest_error()


def load_source_pack(manifest_path: Path) -> SourcePack:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = _require_object(payload, _MANIFEST_KEYS)
        if manifest["schema_version"] != _MANIFEST_SCHEMA or manifest["pack_id"] != _PACK_ID:
            raise _manifest_error()
        raw_sources = manifest["sources"]
        if not isinstance(raw_sources, list) or not raw_sources:
            raise _manifest_error()
        sources = tuple(_parse_source(value) for value in cast(list[object], raw_sources))
        source_keys = [source.source_key for source in sources]
        filenames = [source.relative_filename for source in sources]
        if len(set(source_keys)) != len(source_keys) or len(set(filenames)) != len(filenames):
            raise _manifest_error()
        raw_queries = manifest["queries"]
        if not isinstance(raw_queries, list) or not raw_queries:
            raise _manifest_error()
        queries = tuple(
            _parse_query(value, set(source_keys)) for value in cast(list[object], raw_queries)
        )
        roles = [query.role for query in queries]
        if len(set(roles)) != len(roles):
            raise _manifest_error()
        if sources != _APPROVED_SOURCES or queries != _APPROVED_QUERIES:
            raise _manifest_error()
    except ProofError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise _manifest_error() from exc
    return SourcePack(
        schema_version=_MANIFEST_SCHEMA,
        pack_id=_PACK_ID,
        sources=sources,
        queries=queries,
    )


def verify_source_files(pack: SourcePack, source_root: Path) -> dict[str, Path]:
    expected_filenames = {source.relative_filename for source in pack.sources}
    try:
        actual_filenames = {
            path.relative_to(source_root).as_posix()
            for path in source_root.rglob("*")
            if path.is_file()
        }
        if actual_filenames != expected_filenames:
            raise ProofError("source_pack_identity_mismatch")
        resolved: dict[str, Path] = {}
        for source in pack.sources:
            path = source_root / Path(*PurePosixPath(source.relative_filename).parts)
            data = path.read_bytes()
            if len(data) != source.bytes or hashlib.sha256(data).hexdigest() != source.sha256:
                raise ProofError("source_pack_identity_mismatch")
            resolved[source.source_key] = path
    except ProofError:
        raise
    except OSError as exc:
        raise ProofError("source_pack_identity_mismatch") from exc
    return resolved


def load_schema_expectations(path: Path) -> dict[str, object]:
    try:
        payload_object: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProofError("consumer_schema_invalid") from exc
    if not isinstance(payload_object, dict):
        raise ProofError("consumer_schema_invalid")
    payload = cast(dict[str, object], payload_object)
    if (
        set(payload) != {"schema_version", "public_error_contract", "tools"}
        or payload.get("schema_version") != _SCHEMA_EXPECTATIONS_VERSION
        or not isinstance(payload.get("public_error_contract"), dict)
        or not isinstance(payload.get("tools"), dict)
    ):
        raise ProofError("consumer_schema_invalid")
    contract = cast(dict[str, object], payload["public_error_contract"])
    causes_value = contract.get("safe_causes")
    if (
        set(contract) != _PUBLIC_ERROR_CONTRACT_KEYS
        or contract.get("machine_token_pattern") != _MACHINE_TOKEN_PATTERN
        or contract.get("active_publication_impact") != "unchanged"
        or not isinstance(causes_value, list)
    ):
        raise ProofError("consumer_schema_invalid")
    causes = cast(list[object], causes_value)
    if (
        any(not isinstance(item, str) for item in causes)
        or frozenset(cast(list[str], causes)) != _SAFE_CAUSES
        or len(causes) != len(_SAFE_CAUSES)
    ):
        raise ProofError("consumer_schema_invalid")
    return payload


def _contract_error() -> ProofError:
    return ProofError("consumer_payload_invalid")


def _schema_error() -> ProofError:
    return ProofError("consumer_schema_invalid")


def _runtime_value(value: object) -> object:
    return value


def normalize_discovered_tools(tools: Sequence[DiscoveredTool]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    try:
        for tool in tools:
            name = _runtime_value(tool.name)
            input_value = _runtime_value(tool.inputSchema)
            output_value = _runtime_value(tool.outputSchema)
            if not isinstance(name, str) or not name or not isinstance(input_value, Mapping):
                raise _schema_error()
            if output_value is not None and not isinstance(output_value, Mapping):
                raise _schema_error()
            input_schema = cast(Mapping[str, object], input_value)
            output_schema = cast(Mapping[str, object] | None, output_value)
            if name in normalized:
                raise _schema_error()
            normalized[name] = json.loads(
                json.dumps(
                    {
                        "inputSchema": dict(input_schema),
                        "outputSchema": None if output_schema is None else dict(output_schema),
                    }
                )
            )
    except ProofError:
        raise
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise _schema_error() from exc
    return normalized


def validate_tool_schemas(tools: Sequence[DiscoveredTool], expected: Mapping[str, object]) -> None:
    actual = normalize_discovered_tools(tools)
    expected_tools = expected.get("tools")
    if not isinstance(expected_tools, dict) or actual != cast(dict[str, object], expected_tools):
        raise _schema_error()


def _object(value: object, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict):
        raise _contract_error()
    mapping = cast(dict[object, object], value)
    if set(mapping) != keys:
        raise _contract_error()
    return cast(dict[str, object], value)


def _integer(value: object, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise _contract_error()
    return value


def _text(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 1_000_000:
        raise _contract_error()
    return value


def _observation(value: object) -> None:
    item = _object(
        value,
        {
            "schema_version",
            "library_id",
            "state",
            "source_count",
            "active_publication_count",
            "active_evidence_count",
        },
    )
    if (
        item["schema_version"] != "mke.active_publication_observation.v1"
        or item["library_id"] != "local"
    ):
        raise _contract_error()
    source = _integer(item["source_count"])
    publications = _integer(item["active_publication_count"])
    evidence = _integer(item["active_evidence_count"])
    state = item["state"]
    valid = (
        (state == "empty" and source == publications == evidence == 0)
        or (state == "no_active_publication" and source > 0 and publications == evidence == 0)
        or (state == "active" and source > 0 and publications > 0 and evidence > 0)
    )
    if not valid:
        raise ProofError("observation_state_mismatch")


def _evidence(value: object) -> tuple[object, ...]:
    item = _object(
        value,
        {
            "schema_version",
            "evidence_id",
            "source_id",
            "content_fingerprint",
            "publication_id",
            "publication_revision",
            "run_id",
            "locator",
            "text",
        },
    )
    if item["schema_version"] != "mke.evidence_ref.v1":
        raise _contract_error()
    for field, prefix in (
        ("evidence_id", "ev_"),
        ("source_id", "src_"),
        ("publication_id", "pub_"),
        ("run_id", "run_"),
    ):
        if (
            not isinstance(item[field], str)
            or _ID_RES[prefix].fullmatch(cast(str, item[field])) is None
        ):
            raise _contract_error()
    if (
        not isinstance(item["content_fingerprint"], str)
        or _FINGERPRINT_RE.fullmatch(item["content_fingerprint"]) is None
    ):
        raise _contract_error()
    _integer(item["publication_revision"], 1)
    _text(item["text"])
    locator = item["locator"]
    if not isinstance(locator, dict):
        raise _contract_error()
    loc = cast(dict[str, object], locator)
    if set(loc) != {"kind", "start", "end"}:
        raise _contract_error()
    start = _integer(loc["start"], 0)
    end = _integer(loc["end"], 0)
    if loc["kind"] == "page":
        if start < 1 or end != start:
            raise _contract_error()
    elif loc["kind"] == "timestamp_ms":
        if end <= start:
            raise _contract_error()
    else:
        raise _contract_error()
    return tuple(
        item[key] if key != "locator" else (loc["kind"], start, end) for key in sorted(item)
    )


def _error(payload: dict[str, object], version: str) -> None:
    if (
        set(payload)
        != {"schema_version", "ok", "problem", "cause", "active_publication_impact", "next_step"}
        or payload["schema_version"] != version
        or payload["ok"] is not False
    ):
        raise _contract_error()
    for field in ("problem", "next_step"):
        if (
            not isinstance(payload[field], str)
            or _MACHINE_TOKEN_RE.fullmatch(cast(str, payload[field])) is None
        ):
            raise _contract_error()
    cause = payload["cause"]
    if (
        not isinstance(cause, str)
        or cause not in _SAFE_CAUSES
        or payload["active_publication_impact"] != "unchanged"
    ):
        raise _contract_error()


def _payload(payload: object, version: str, success_keys: set[str]) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise _contract_error()
    result = cast(dict[str, object], payload)
    if result.get("ok") is False:
        _error(result, version)
        return dict(result)
    if (
        result.get("ok") is not True
        or set(result) != success_keys
        or result.get("schema_version") != version
    ):
        raise _contract_error()
    return result


def validate_list_response(payload: object) -> dict[str, object]:
    result = _payload(
        payload, "mke.list_libraries_response.v1", {"schema_version", "ok", "observation"}
    )
    if result["ok"] is True:
        _observation(result["observation"])
    return dict(result)


def validate_search_response(payload: object) -> dict[str, object]:
    result = _payload(
        payload,
        "mke.search_library_response.v1",
        {"schema_version", "ok", "query", "observation", "results"},
    )
    if result["ok"] is True:
        _text(result["query"])
        _observation(result["observation"])
        values_object = result["results"]
        if not isinstance(values_object, list):
            raise _contract_error()
        values = cast(list[object], values_object)
        if len(values) > 20:
            raise _contract_error()
        for value in values:
            _evidence(value)
        observation = cast(dict[str, object], result["observation"])
        if len(values) > cast(int, observation["active_evidence_count"]):
            raise _contract_error()
    return dict(result)


def validate_ask_response(payload: object) -> dict[str, object]:
    result = _payload(
        payload,
        "mke.ask_library_response.v1",
        {
            "schema_version",
            "ok",
            "question",
            "answer_status",
            "summary",
            "observation",
            "evidence",
            "limitations",
        },
    )
    if result["ok"] is True:
        _text(result["question"])
        _text(result["summary"])
        _observation(result["observation"])
        evidence_object = result["evidence"]
        limitations_object = result["limitations"]
        if not isinstance(evidence_object, list) or not isinstance(limitations_object, list):
            raise _contract_error()
        evidence = cast(list[object], evidence_object)
        limitations = cast(list[object], limitations_object)
        if len(evidence) > 20 or len(limitations) > 20:
            raise _contract_error()
        for value in evidence:
            _evidence(value)
        for value in limitations:
            _text(value)
        if (
            (result["answer_status"] == "evidence_found" and not evidence)
            or (result["answer_status"] == "insufficient_evidence" and evidence)
            or result["answer_status"] not in {"evidence_found", "insufficient_evidence"}
        ):
            raise _contract_error()
    return dict(result)


def evidence_projection(payload: Mapping[str, object]) -> tuple[object, ...]:
    values_object = payload.get("results", payload.get("evidence"))
    if not isinstance(values_object, list):
        raise _contract_error()
    values = cast(list[object], values_object)
    if len(values) > 20:
        raise _contract_error()
    return tuple(_evidence(value) for value in values)


def build_receipt(
    evidence: Mapping[str, object], pack: SourcePack, query: QueryExpectation
) -> dict[str, object]:
    fingerprint = evidence.get("content_fingerprint")
    matches = [source for source in pack.sources if fingerprint == "sha256:" + source.sha256]
    if not matches:
        raise ProofError("manifest_mapping_missing")
    if len(matches) != 1:
        raise ProofError("manifest_mapping_ambiguous")
    source = matches[0]
    if source.source_key != query.expected_source_key or source.source_key != query.role:
        raise ProofError("manifest_mapping_missing")
    locator = evidence.get("locator")
    if not isinstance(locator, dict) or query.allowed_locator_range is None:
        raise ProofError("manifest_locator_mismatch")
    loc = cast(dict[str, object], locator)
    if (
        set(loc) != {"kind", "start", "end"}
        or loc["kind"] != query.locator_kind
        or (loc["start"], loc["end"]) != query.allowed_locator_range
    ):
        raise ProofError("manifest_locator_mismatch")
    return {
        "schema_version": "mke.consumer_source_pack_receipt.v1",
        "manifest_schema": pack.schema_version,
        "pack_id": pack.pack_id,
        "evidence_schema": cast(str, evidence["schema_version"]),
        "match_status": "matched",
        "query_role": query.role,
        "source_key": source.source_key,
        "content_fingerprint": fingerprint,
        "locator": {"kind": loc["kind"], "start": loc["start"], "end": loc["end"]},
    }


class BoundedStderrCapture:
    """An incrementally drained OS pipe with a hard byte cap."""

    def __init__(self, max_bytes: int) -> None:
        if max_bytes < 1:
            raise ValueError("max_bytes must be positive")
        self.max_bytes = max_bytes
        self.overflow = asyncio.Event()
        self.overflow_observed_at: float | None = None
        self.terminal_code: str | None = None
        self.bytes_seen = 0
        self.errlog: TextIO | None = None
        self._read_fd: int | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def write_end(self) -> TextIO:
        if self.errlog is None:
            raise RuntimeError("capture is not entered")
        return self.errlog

    async def __aenter__(self) -> BoundedStderrCapture:
        read_fd, write_fd = os.pipe()
        self._read_fd = read_fd
        self.errlog = TextIOWrapper(os.fdopen(write_fd, "wb", closefd=True), write_through=True)
        self._task = asyncio.create_task(self._drain())
        return self

    async def _drain(self) -> None:
        assert self._read_fd is not None
        try:
            while True:
                chunk = await asyncio.to_thread(os.read, self._read_fd, 4096)
                if not chunk:
                    return
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

    async def __aexit__(self, *args: object) -> None:
        if self.errlog is not None and not self.errlog.closed:
            self.errlog.close()
        if self._read_fd is not None:
            os.close(self._read_fd)
            self._read_fd = None
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)


def _tool_payload(result: object) -> dict[str, object]:
    if getattr(result, "isError", False):
        raise _contract_error()
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return cast(dict[str, object], structured)
    for item in cast(list[object], getattr(result, "content", [])):
        if isinstance(item, types.TextContent):
            try:
                value = json.loads(item.text)
            except json.JSONDecodeError as exc:
                raise _contract_error() from exc
            if isinstance(value, dict):
                return cast(dict[str, object], value)
    raise _contract_error()


async def _deadline(
    awaitable: Any,
    seconds: float,
    code: str,
    capture: BoundedStderrCapture,
) -> Any:
    deadline_at = time.monotonic() + seconds
    operation = asyncio.ensure_future(awaitable)
    overflow = asyncio.create_task(capture.overflow.wait())
    try:
        done, _ = await asyncio.wait(
            {operation, overflow}, timeout=seconds, return_when=asyncio.FIRST_COMPLETED
        )
        overflow_at = capture.overflow_observed_at
        if overflow_at is not None and overflow_at <= deadline_at:
            if capture.terminal_code is None:
                capture.terminal_code = "command_output_exceeded"
            operation.cancel()
            await asyncio.gather(operation, return_exceptions=True)
            raise ProofError("command_output_exceeded")
        if operation in done:
            return await operation
        operation.cancel()
        await asyncio.gather(operation, return_exceptions=True)
        if capture.terminal_code is None:
            capture.terminal_code = code
        raise ProofError(code)
    finally:
        overflow.cancel()
        await asyncio.gather(overflow, return_exceptions=True)


def _validate_run(payload: Mapping[str, object], run_id: str) -> None:
    run = payload.get("run")
    events = payload.get("events")
    if payload.get("ok") is not True or not isinstance(run, dict) or not isinstance(events, list):
        raise _contract_error()
    typed_run = cast(dict[str, object], run)
    if typed_run.get("run_id") != run_id or typed_run.get("state") != "published":
        raise _contract_error()
    event_values = cast(list[object], events)
    if not all(isinstance(item, dict) for item in event_values):
        raise _contract_error()
    typed = cast(list[dict[str, object]], event_values)
    indices = [item.get("event_index") for item in typed]
    names = [item.get("event") for item in typed]
    required = ["run_created", "run_started", "candidate_validated", "publication_activated"]
    positions = [names.index(name) if name in names else -1 for name in required]
    if (
        indices != list(range(1, len(typed) + 1))
        or positions != sorted(positions)
        or -1 in positions
        or names[-1] != "publication_activated"
    ):
        raise _contract_error()


async def _call(
    session: ClientSession,
    name: str,
    arguments: dict[str, object],
    timeout: float,
    capture: BoundedStderrCapture,
) -> dict[str, object]:
    result = await _deadline(
        session.call_tool(name, arguments), timeout, "mcp_tool_timeout", capture
    )
    return _tool_payload(result)


async def run_store_session(config: ConsumerConfig, database: Path) -> StoreResult:
    pack = load_source_pack(config.manifest)
    verify_source_files(pack, config.source_root)
    schemas = load_schema_expectations(config.schemas)
    server = StdioServerParameters(
        command=str(config.mke_executable),
        args=["--db", str(database), "mcp", "--allowed-root", str(config.source_root)],
        cwd=str(config.workspace),
        env=dict(config.child_environment),
    )
    capture = BoundedStderrCapture(config.max_server_stderr_bytes)
    async with capture:
        try:
            async with stdio_client(server, errlog=capture.write_end) as (read, write):
                async with ClientSession(
                    read,
                    write,
                    read_timeout_seconds=timedelta(seconds=config.tool_timeout_seconds),
                ) as session:
                    await _deadline(
                        session.initialize(),
                        config.startup_timeout_seconds,
                        "mcp_startup_timeout",
                        capture,
                    )
                    listed = await _deadline(
                        session.list_tools(),
                        config.tool_timeout_seconds,
                        "mcp_tool_timeout",
                        capture,
                    )
                    validate_tool_schemas(listed.tools, schemas)
                    initial = validate_list_response(
                        await _call(
                            session,
                            "list_libraries_v1",
                            {},
                            config.tool_timeout_seconds,
                            capture,
                        )
                    )
                    initial_obs = cast(dict[str, object], initial["observation"])
                    if initial_obs != {
                        "schema_version": "mke.active_publication_observation.v1",
                        "library_id": "local",
                        "state": "empty",
                        "source_count": 0,
                        "active_publication_count": 0,
                        "active_evidence_count": 0,
                    }:
                        raise ProofError("observation_state_mismatch")
                    published = 0
                    for source in pack.sources:
                        ingested = await _call(
                            session,
                            "ingest_file",
                            {"path": source.relative_filename},
                            config.tool_timeout_seconds,
                            capture,
                        )
                        run_id = ingested.get("run_id")
                        evidence_count = ingested.get("evidence_count")
                        if (
                            not isinstance(run_id, str)
                            or isinstance(evidence_count, bool)
                            or not isinstance(evidence_count, int)
                            or evidence_count < 1
                        ):
                            raise _contract_error()
                        _validate_run(
                            await _call(
                                session,
                                "get_run",
                                {"run_id": run_id},
                                config.tool_timeout_seconds,
                                capture,
                            ),
                            run_id,
                        )
                        published += 1
                    active = validate_list_response(
                        await _call(
                            session,
                            "list_libraries_v1",
                            {},
                            config.tool_timeout_seconds,
                            capture,
                        )
                    )
                    observation = cast(dict[str, object], active["observation"])
                    if tuple(
                        observation.get(k)
                        for k in (
                            "state",
                            "source_count",
                            "active_publication_count",
                            "active_evidence_count",
                        )
                    ) != ("active", 2, 2, 2):
                        raise ProofError("observation_state_mismatch")
                    receipts: list[dict[str, object]] = []
                    projections_equal = True
                    for query in (
                        item for item in pack.queries if item.expected_source_key is not None
                    ):
                        searched = validate_search_response(
                            await _call(
                                session,
                                "search_library_v1",
                                {"query": query.query, "limit": 5},
                                config.tool_timeout_seconds,
                                capture,
                            )
                        )
                        asked = validate_ask_response(
                            await _call(
                                session,
                                "ask_library_v1",
                                {"question": query.query, "limit": 5},
                                config.tool_timeout_seconds,
                                capture,
                            )
                        )
                        if searched["query"] != query.query or asked["question"] != query.query:
                            raise _contract_error()
                        projections_equal &= evidence_projection(searched) == evidence_projection(
                            asked
                        )
                        results = cast(list[dict[str, object]], searched["results"])
                        if len(results) != 1 or not projections_equal:
                            raise _contract_error()
                        receipts.append(build_receipt(results[0], pack, query))
                    unsupported = next(
                        item for item in pack.queries if item.expected_source_key is None
                    )
                    searched = validate_search_response(
                        await _call(
                            session,
                            "search_library_v1",
                            {"query": unsupported.query, "limit": 5},
                            config.tool_timeout_seconds,
                            capture,
                        )
                    )
                    asked = validate_ask_response(
                        await _call(
                            session,
                            "ask_library_v1",
                            {"question": unsupported.query, "limit": 5},
                            config.tool_timeout_seconds,
                            capture,
                        )
                    )
                    if (
                        searched["query"] != unsupported.query
                        or asked["question"] != unsupported.query
                        or cast(dict[str, object], searched["observation"])["state"] != "active"
                        or searched["results"] != []
                        or asked["answer_status"] != unsupported.expected_ask_status
                        or asked["evidence"] != []
                    ):
                        if cast(dict[str, object], searched["observation"])["state"] != "active":
                            raise ProofError("observation_state_mismatch")
                        raise _contract_error()
                    return StoreResult(
                        2,
                        published,
                        2,
                        2,
                        ("empty", "active"),
                        tuple(receipts),
                        True,
                        projections_equal,
                        True,
                        True,
                        True,
                    )
        except ProofError:
            raise
        except Exception as exc:
            if capture.overflow.is_set():
                raise ProofError("command_output_exceeded") from exc
            raise ProofError("mcp_transport_failed") from exc
        finally:
            if capture.overflow.is_set() and capture.terminal_code in {
                None,
                "command_output_exceeded",
            }:
                raise ProofError("command_output_exceeded")


async def run_consumer(config: ConsumerConfig) -> ConsumerResult:
    first = await run_store_session(config, config.workspace / "store-1.sqlite")
    second = await run_store_session(config, config.workspace / "store-2.sqlite")

    def identity(item: dict[str, object]) -> tuple[object, ...]:
        locator = cast(dict[str, object], item["locator"])
        return (
            item["query_role"],
            item["source_key"],
            item["content_fingerprint"],
            (locator["kind"], locator["start"], locator["end"]),
        )

    fresh = tuple(map(identity, first.receipts)) == tuple(map(identity, second.receipts))
    if not fresh:
        raise ProofError("proof_failed")
    return ConsumerResult(
        _MANIFEST_SCHEMA,
        "mke.evidence_ref.v1",
        pack_id=_PACK_ID,
        source_count=first.source_count,
        published_run_count=first.published_run_count,
        active_publication_count=first.active_publication_count,
        active_evidence_count=first.active_evidence_count,
        observed_states=first.observed_states,
        receipts=first.receipts,
        strict_schema_validation=True,
        search_ask_projection_equal=True,
        exact_manifest_mapping=True,
        fresh_store_mapping=True,
        redaction=True,
        server_cleanup=True,
    )


def render_controller_result(result: ConsumerResult) -> str:
    payload = {
        "status": "passed",
        **{field: getattr(result, field) for field in result.__dataclass_fields__},
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--schemas", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--mke", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--startup-timeout", type=float, default=60.0)
    parser.add_argument("--tool-timeout", type=float, default=60.0)
    parser.add_argument("--max-server-stderr-bytes", type=int, default=65536)
    args = parser.parse_args(argv)
    config = ConsumerConfig(
        args.manifest,
        args.schemas,
        args.source_root,
        args.mke,
        args.workspace,
        dict(os.environ),
        args.startup_timeout,
        args.tool_timeout,
        args.max_server_stderr_bytes,
    )
    try:
        print(render_controller_result(asyncio.run(run_consumer(config))))
        return 0
    except ProofError as exc:
        code = exc.code if exc.code in _STABLE_FAILURE_CODES else "proof_failed"
        print(
            json.dumps(
                {"status": "failed", "code": code}, sort_keys=True, separators=(",", ":")
            )
        )
        return 1
    except Exception:
        print(
            json.dumps(
                {"status": "failed", "code": "proof_failed"},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
