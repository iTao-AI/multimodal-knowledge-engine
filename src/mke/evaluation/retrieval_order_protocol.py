from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, cast

_SCHEMA = "mke.retrieval_order_protocol.v1"
_PROTOCOL_ID = "retrieval-order-v1"
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_FINGERPRINT_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_FTS_KEY = (
    "rank",
    "locator_start",
    "locator_kind",
    "locator_end",
    "assets.sha256",
)
_CJK_KEY = (
    "-overlap_count",
    "-overlap_ratio",
    "content_fingerprint",
    "locator_kind",
    "locator_start",
    "locator_end",
)
_RUNTIME_FIELDS = (
    "python",
    "sqlite",
    "sqlite_source_id",
    "sqlite_compile_options",
    "fts5_rank_configuration",
    "strategy_revision",
    "query_policy_revision",
)


class RetrievalOrderProtocolError(ValueError):
    """The deterministic retrieval-order protocol is malformed."""


@dataclass(frozen=True)
class RetrievalOrderKeyContract:
    fts: tuple[str, ...]
    cjk: tuple[str, ...]


@dataclass(frozen=True)
class PartitionContract:
    name: Literal["development", "holdout"]
    path: Path
    bytes: int
    sha256: str
    case_ids: frozenset[str]
    source_ids: frozenset[str]
    query_ids: frozenset[str]
    coverage: frozenset[str]
    expected_stable_projections: tuple[tuple[str, str, int, int], ...]


@dataclass(frozen=True)
class RetrievalOrderProtocol:
    schema_version: Literal["mke.retrieval_order_protocol.v1"]
    protocol_id: Literal["retrieval-order-v1"]
    key_contract: RetrievalOrderKeyContract
    development: PartitionContract
    holdout: PartitionContract
    runtime_profile_fields: tuple[str, ...]


def load_retrieval_order_protocol(
    path: Path, *, repository_root: Path
) -> RetrievalOrderProtocol:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        root = repository_root.resolve()
        payload = _object(value)
        if set(payload) != {
            "schema_version",
            "protocol_id",
            "key_contract",
            "runtime_profile_fields",
            "partition_rules",
            "partitions",
        }:
            raise RetrievalOrderProtocolError
        if (
            payload["schema_version"] != _SCHEMA
            or payload["protocol_id"] != _PROTOCOL_ID
        ):
            raise RetrievalOrderProtocolError
        key_contract = _object(payload["key_contract"])
        if tuple(_strings(key_contract.get("fts"))) != _FTS_KEY or tuple(
            _strings(key_contract.get("cjk"))
        ) != _CJK_KEY:
            raise RetrievalOrderProtocolError
        runtime_fields = tuple(_strings(payload["runtime_profile_fields"]))
        if runtime_fields != _RUNTIME_FIELDS:
            raise RetrievalOrderProtocolError
        if _object(payload["partition_rules"]) != {
            "public_nonblind": True,
            "mechanism_only": True,
            "holdout_execution_limit": 1,
            "after_publication_status": "development_material",
            "promotion_status": "not_evaluated",
        }:
            raise RetrievalOrderProtocolError
        partitions = _object(payload["partitions"])
        if set(partitions) != {"development", "holdout"}:
            raise RetrievalOrderProtocolError
        development = _load_partition(
            "development", partitions["development"], root=root
        )
        holdout = _load_partition("holdout", partitions["holdout"], root=root)
        if (
            development.sha256 == holdout.sha256
            or not development.source_ids.isdisjoint(holdout.source_ids)
            or not development.query_ids.isdisjoint(holdout.query_ids)
            or not development.case_ids.isdisjoint(holdout.case_ids)
        ):
            raise RetrievalOrderProtocolError
        return RetrievalOrderProtocol(
            schema_version=_SCHEMA,
            protocol_id=_PROTOCOL_ID,
            key_contract=RetrievalOrderKeyContract(_FTS_KEY, _CJK_KEY),
            development=development,
            holdout=holdout,
            runtime_profile_fields=runtime_fields,
        )
    except RetrievalOrderProtocolError:
        raise
    except Exception as error:
        raise RetrievalOrderProtocolError(
            "retrieval order protocol is invalid"
        ) from error


def _load_partition(
    name: Literal["development", "holdout"],
    value: object,
    *,
    root: Path,
) -> PartitionContract:
    record = _object(value)
    if set(record) != {"path", "bytes", "sha256", "cases"}:
        raise RetrievalOrderProtocolError
    relative_path = _relative_path(record["path"])
    fixture_path = (root / relative_path).resolve()
    if not fixture_path.is_relative_to(root) or not fixture_path.is_file():
        raise RetrievalOrderProtocolError
    data = fixture_path.read_bytes()
    byte_count = record["bytes"]
    sha256 = record["sha256"]
    if (
        isinstance(byte_count, bool)
        or not isinstance(byte_count, int)
        or byte_count <= 0
        or byte_count != len(data)
        or not isinstance(sha256, str)
        or _SHA256_RE.fullmatch(sha256) is None
        or hashlib.sha256(data).hexdigest() != sha256
    ):
        raise RetrievalOrderProtocolError
    fixture = _object(json.loads(data))
    (
        case_ids,
        source_ids,
        query_ids,
        coverage,
        projections,
    ) = _validate_cases_fixture(fixture, name=name)
    metadata = _object(record["cases"])
    if set(metadata) != {
        "case_ids",
        "source_ids",
        "query_ids",
        "coverage",
        "expected_stable_projections",
    }:
        raise RetrievalOrderProtocolError
    if (
        frozenset(_unique_strings(metadata["case_ids"])) != case_ids
        or frozenset(_unique_strings(metadata["source_ids"])) != source_ids
        or frozenset(_unique_strings(metadata["query_ids"])) != query_ids
        or frozenset(_unique_strings(metadata["coverage"])) != coverage
        or sorted(_projections(metadata["expected_stable_projections"]))
        != sorted(projections)
    ):
        raise RetrievalOrderProtocolError
    return PartitionContract(
        name=name,
        path=fixture_path,
        bytes=byte_count,
        sha256=sha256,
        case_ids=case_ids,
        source_ids=source_ids,
        query_ids=query_ids,
        coverage=coverage,
        expected_stable_projections=tuple(projections),
    )


def _validate_cases_fixture(
    fixture: dict[str, object],
    *,
    name: Literal["development", "holdout"],
) -> tuple[
    frozenset[str],
    frozenset[str],
    frozenset[str],
    frozenset[str],
    list[tuple[str, str, int, int]],
]:
    if set(fixture) != {
        "schema_version",
        "partition",
        "workspace_schedules",
        "page_sizes",
        "cases",
    } or fixture.get("schema_version") != "mke.retrieval_order_cases.v1":
        raise RetrievalOrderProtocolError
    if fixture.get("partition") != name:
        raise RetrievalOrderProtocolError
    if _strings(fixture["workspace_schedules"]) != [
        "forward_ids",
        "reverse_ids",
    ] or fixture["page_sizes"] != [1, 2, "full"]:
        raise RetrievalOrderProtocolError
    cases_raw = fixture["cases"]
    if not isinstance(cases_raw, list) or not cases_raw:
        raise RetrievalOrderProtocolError
    cases_value = cast(list[object], cases_raw)
    case_ids: list[str] = []
    source_ids: set[str] = set()
    query_ids: list[str] = []
    coverage: set[str] = set()
    projections: list[tuple[str, str, int, int]] = []
    for raw_case in cases_value:
        case = _object(raw_case)
        if set(case) != {
            "case_id",
            "strategy",
            "query_id",
            "query",
            "candidates",
            "expected_stable_projections",
        }:
            raise RetrievalOrderProtocolError
        case_id = _nonempty(case["case_id"])
        query_id = _nonempty(case["query_id"])
        _nonempty(case["query"])
        strategy = case["strategy"]
        if strategy not in {"fts", "cjk"}:
            raise RetrievalOrderProtocolError
        candidates_raw = case["candidates"]
        if not isinstance(candidates_raw, list):
            raise RetrievalOrderProtocolError
        candidates = cast(list[object], candidates_raw)
        if len(candidates) < 2:
            raise RetrievalOrderProtocolError
        expected = _projections(case["expected_stable_projections"])
        observed: list[tuple[str, str, int, int]] = []
        for raw_candidate in candidates:
            candidate = _object(raw_candidate)
            if set(candidate) != {
                "source_id",
                "content_fingerprint",
                "asset_sha256",
                "locator_kind",
                "locator_start",
                "locator_end",
                "text",
            }:
                raise RetrievalOrderProtocolError
            source_ids.add(_nonempty(candidate["source_id"]))
            fingerprint = _nonempty(candidate["content_fingerprint"])
            asset_sha256 = _nonempty(candidate["asset_sha256"])
            locator_kind = candidate["locator_kind"]
            start = candidate["locator_start"]
            end = candidate["locator_end"]
            if (
                _FINGERPRINT_RE.fullmatch(fingerprint) is None
                or _SHA256_RE.fullmatch(asset_sha256) is None
                or fingerprint != f"sha256:{asset_sha256}"
                or locator_kind not in {"page", "timestamp_ms"}
                or isinstance(start, bool)
                or not isinstance(start, int)
                or isinstance(end, bool)
                or not isinstance(end, int)
                or start < 0
                or end < start
            ):
                raise RetrievalOrderProtocolError
            _nonempty(candidate["text"])
            observed.append((fingerprint, cast(str, locator_kind), start, end))
            coverage.add(
                "timestamp"
                if locator_kind == "timestamp_ms"
                else cast(str, locator_kind)
            )
        if expected != observed:
            raise RetrievalOrderProtocolError
        case_ids.append(case_id)
        query_ids.append(query_id)
        coverage.add(cast(str, strategy))
        projections.extend(expected)
    if (
        len(case_ids) != len(set(case_ids))
        or len(query_ids) != len(set(query_ids))
        or not {"fts", "cjk", "page"}.issubset(coverage)
        or (name == "development" and "timestamp" not in coverage)
    ):
        raise RetrievalOrderProtocolError
    return (
        frozenset(case_ids),
        frozenset(source_ids),
        frozenset(query_ids),
        frozenset(coverage),
        projections,
    )


def _projections(value: object) -> list[tuple[str, str, int, int]]:
    if not isinstance(value, list) or not value:
        raise RetrievalOrderProtocolError
    result: list[tuple[str, str, int, int]] = []
    for raw in cast(list[object], value):
        if not isinstance(raw, list):
            raise RetrievalOrderProtocolError
        projection = cast(list[object], raw)
        if len(projection) != 4:
            raise RetrievalOrderProtocolError
        fingerprint, kind, start, end = projection
        if (
            not isinstance(fingerprint, str)
            or _FINGERPRINT_RE.fullmatch(fingerprint) is None
            or kind not in {"page", "timestamp_ms"}
            or isinstance(start, bool)
            or not isinstance(start, int)
            or isinstance(end, bool)
            or not isinstance(end, int)
        ):
            raise RetrievalOrderProtocolError
        result.append((fingerprint, cast(str, kind), start, end))
    return result


def _relative_path(value: object) -> str:
    path = _nonempty(value)
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or ".." in parsed.parts or path != parsed.as_posix():
        raise RetrievalOrderProtocolError
    return path


def _unique_strings(value: object) -> list[str]:
    result = _strings(value)
    if len(result) != len(set(result)):
        raise RetrievalOrderProtocolError
    return result


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        raise RetrievalOrderProtocolError
    items = cast(list[object], value)
    if not all(isinstance(item, str) and item for item in items):
        raise RetrievalOrderProtocolError
    return cast(list[str], items)


def _nonempty(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise RetrievalOrderProtocolError
    return value


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RetrievalOrderProtocolError
    return cast(dict[str, object], value)
