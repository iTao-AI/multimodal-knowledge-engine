from __future__ import annotations

import hashlib
import json
import os
import re
import stat
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
class PartitionMetadata:
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
class PartitionContract(PartitionMetadata):
    fixture: dict[str, object]


@dataclass(frozen=True)
class RetrievalOrderProtocolMetadata:
    schema_version: Literal["mke.retrieval_order_protocol.v1"]
    protocol_id: Literal["retrieval-order-v1"]
    protocol_path: Path
    protocol_sha256: str
    key_contract: RetrievalOrderKeyContract
    development: PartitionMetadata
    holdout: PartitionMetadata
    runtime_profile_fields: tuple[str, ...]


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
    metadata = load_retrieval_order_protocol_metadata(
        path,
        repository_root=repository_root,
    )
    return RetrievalOrderProtocol(
        schema_version=_SCHEMA,
        protocol_id=_PROTOCOL_ID,
        key_contract=metadata.key_contract,
        development=load_retrieval_order_protocol_partition(
            metadata,
            "development",
        ),
        holdout=load_retrieval_order_protocol_partition(
            metadata,
            "holdout",
        ),
        runtime_profile_fields=metadata.runtime_profile_fields,
    )


def load_retrieval_order_protocol_metadata(
    path: Path,
    *,
    repository_root: Path,
) -> RetrievalOrderProtocolMetadata:
    try:
        root = _preflight_repository_root(repository_root)
        protocol_path = _preflight_repository_regular_file(
            path,
            repository_root=root,
        )
        protocol_bytes = protocol_path.read_bytes()
        payload = _object(json.loads(protocol_bytes))
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
        development = _load_partition_metadata(
            "development", partitions["development"], root=root
        )
        holdout = _load_partition_metadata(
            "holdout",
            partitions["holdout"],
            root=root,
        )
        if (
            development.sha256 == holdout.sha256
            or not development.source_ids.isdisjoint(holdout.source_ids)
            or not development.query_ids.isdisjoint(holdout.query_ids)
            or not development.case_ids.isdisjoint(holdout.case_ids)
        ):
            raise RetrievalOrderProtocolError
        return RetrievalOrderProtocolMetadata(
            schema_version=_SCHEMA,
            protocol_id=_PROTOCOL_ID,
            protocol_path=protocol_path,
            protocol_sha256=hashlib.sha256(protocol_bytes).hexdigest(),
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


def _load_partition_metadata(
    name: Literal["development", "holdout"],
    value: object,
    *,
    root: Path,
) -> PartitionMetadata:
    record = _object(value)
    if set(record) != {"path", "bytes", "sha256", "cases"}:
        raise RetrievalOrderProtocolError
    relative_path = _relative_path(record["path"])
    fixture_path = _preflight_repository_regular_file(
        root / relative_path,
        repository_root=root,
    )
    byte_count = record["bytes"]
    sha256 = record["sha256"]
    if (
        isinstance(byte_count, bool)
        or not isinstance(byte_count, int)
        or byte_count <= 0
        or not isinstance(sha256, str)
        or _SHA256_RE.fullmatch(sha256) is None
    ):
        raise RetrievalOrderProtocolError
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
        not (case_ids := frozenset(_unique_strings(metadata["case_ids"])))
        or not (
            source_ids := frozenset(
                _unique_strings(metadata["source_ids"])
            )
        )
        or not (
            query_ids := frozenset(_unique_strings(metadata["query_ids"]))
        )
        or not (coverage := frozenset(_unique_strings(metadata["coverage"])))
        or not (
            projections := _projections(
                metadata["expected_stable_projections"]
            )
        )
        or not {"fts", "cjk", "page"}.issubset(coverage)
        or (name == "development" and "timestamp" not in coverage)
    ):
        raise RetrievalOrderProtocolError
    return PartitionMetadata(
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


def load_retrieval_order_protocol_partition(
    metadata: RetrievalOrderProtocolMetadata,
    partition: Literal["development", "holdout"],
) -> PartitionContract:
    try:
        record = (
            metadata.development
            if partition == "development"
            else metadata.holdout
        )
        _preflight_absolute_regular_file(record.path)
        data = record.path.read_bytes()
        if (
            len(data) != record.bytes
            or hashlib.sha256(data).hexdigest() != record.sha256
        ):
            raise RetrievalOrderProtocolError
        fixture = _object(json.loads(data))
        (
            case_ids,
            source_ids,
            query_ids,
            coverage,
            projections,
        ) = _validate_cases_fixture(fixture, name=partition)
        if (
            case_ids != record.case_ids
            or source_ids != record.source_ids
            or query_ids != record.query_ids
            or coverage != record.coverage
            or sorted(projections)
            != sorted(record.expected_stable_projections)
        ):
            raise RetrievalOrderProtocolError
        return PartitionContract(**record.__dict__, fixture=fixture)
    except RetrievalOrderProtocolError:
        raise
    except Exception as error:
        raise RetrievalOrderProtocolError(
            "retrieval order partition is invalid"
        ) from error


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


def _preflight_repository_root(repository_root: Path) -> Path:
    root = (
        repository_root
        if repository_root.is_absolute()
        else Path.cwd() / repository_root
    )
    if ".." in root.parts:
        raise RetrievalOrderProtocolError
    if _lexical_path_state(root, expected="directory") != "directory":
        raise RetrievalOrderProtocolError
    return root


def _lexical_repository_path(
    path: Path,
    *,
    repository_root: Path,
) -> Path:
    root = _preflight_repository_root(repository_root)
    candidate = path if path.is_absolute() else root / path
    if ".." in candidate.parts or not candidate.is_relative_to(root):
        raise RetrievalOrderProtocolError
    return candidate


def _preflight_repository_regular_file(
    path: Path,
    *,
    repository_root: Path,
) -> Path:
    candidate = _lexical_repository_path(
        path,
        repository_root=repository_root,
    )
    _preflight_absolute_regular_file(candidate)
    return candidate


def _preflight_repository_output(  # pyright: ignore[reportUnusedFunction]
    path: Path,
    *,
    repository_root: Path,
) -> tuple[Path, Literal["absent", "regular", "invalid"]]:
    try:
        candidate = _lexical_repository_path(
            path,
            repository_root=repository_root,
        )
    except RetrievalOrderProtocolError:
        return path, "invalid"
    state = _lexical_path_state(candidate, expected="output")
    if state == "absent":
        return candidate, "absent"
    if state == "regular":
        return candidate, "regular"
    return candidate, "invalid"


def _is_exact_repository_path(  # pyright: ignore[reportUnusedFunction]
    path: Path,
    *,
    repository_root: Path,
    relative_path: Path,
) -> bool:
    try:
        root = _preflight_repository_root(repository_root)
        candidate = _lexical_repository_path(
            path,
            repository_root=root,
        )
    except RetrievalOrderProtocolError:
        return False
    return (
        candidate == root / relative_path
        and _lexical_path_state(candidate, expected="output") != "invalid"
    )


def _preflight_absolute_regular_file(path: Path) -> None:
    if _lexical_path_state(path, expected="regular") != "regular":
        raise RetrievalOrderProtocolError


def _lexical_path_state(
    path: Path,
    *,
    expected: Literal["directory", "regular", "output"],
) -> Literal["absent", "directory", "regular", "invalid"]:
    if not path.is_absolute() or ".." in path.parts:
        return "invalid"
    current = Path(path.anchor)
    parts = path.parts[1:]
    for index, part in enumerate(parts):
        final = index == len(parts) - 1
        candidate = current / part
        try:
            with os.scandir(current) as entries:
                exact_name = any(entry.name == part for entry in entries)
        except OSError:
            return "invalid"
        if not exact_name:
            try:
                candidate.lstat()
            except FileNotFoundError:
                return "absent" if expected == "output" else "invalid"
            except OSError:
                return "invalid"
            return "invalid"
        try:
            metadata = candidate.lstat()
        except OSError:
            return "invalid"
        if stat.S_ISLNK(metadata.st_mode):
            return "invalid"
        if not final:
            if not stat.S_ISDIR(metadata.st_mode):
                return "invalid"
            current = candidate
            continue
        if expected == "directory":
            return "directory" if stat.S_ISDIR(metadata.st_mode) else "invalid"
        if expected == "regular":
            return "regular" if stat.S_ISREG(metadata.st_mode) else "invalid"
        return "regular" if stat.S_ISREG(metadata.st_mode) else "invalid"
    return "directory" if expected == "directory" else "invalid"


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
