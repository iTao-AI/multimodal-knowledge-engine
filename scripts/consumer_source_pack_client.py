"""Standalone consumer for the installed source-pack proof.

This file intentionally uses only Python's standard library for source-pack
manifest parsing and preflight identity verification.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import cast

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
            if path.is_file() and path.suffix == ".pdf"
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
        raise ProofError("tool_schema_expectations_invalid") from exc
    if not isinstance(payload_object, dict):
        raise ProofError("tool_schema_expectations_invalid")
    payload = cast(dict[str, object], payload_object)
    if (
        set(payload) != {"schema_version", "public_error_contract", "tools"}
        or payload.get("schema_version") != _SCHEMA_EXPECTATIONS_VERSION
        or not isinstance(payload.get("public_error_contract"), dict)
        or not isinstance(payload.get("tools"), dict)
    ):
        raise ProofError("tool_schema_expectations_invalid")
    return payload
