from __future__ import annotations

import json
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, cast

from mke.evaluation.source_identity import DirectFileRead, read_no_follow_regular_file

_PROTOCOL_FIELDS = {
    "candidate_profile",
    "development_evaluator_paths",
    "mechanism_verdict_revision",
    "o0_evaluator_paths",
    "partitions",
    "projection_bounds",
    "protocol_id",
    "runtime_profile_fields",
    "schema_version",
    "scientific_input_lock",
    "stage_verdict_revision",
}
_PARTITION_FIELDS = {
    "labels",
    "observer_cases",
    "query_ids",
    "source_ids",
    "source_receipts",
}
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class AgentContextFileReference:
    path: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class AgentContextPartitionMetadata:
    source_ids: tuple[str, ...]
    query_ids: tuple[str, ...]
    source_receipts: AgentContextFileReference
    observer_cases: AgentContextFileReference
    labels: AgentContextFileReference

    @property
    def source_receipts_path(self) -> str:
        return self.source_receipts.path

    @property
    def observer_cases_path(self) -> str:
        return self.observer_cases.path


@dataclass(frozen=True)
class AgentContextProtocolMetadata:
    schema_version: str
    protocol_id: str
    candidate_profile: Mapping[str, Any]
    projection_bounds: Mapping[str, Any]
    runtime_profile_fields: tuple[str, ...]
    mechanism_verdict_revision: str
    stage_verdict_revision: str
    o0_evaluator_paths: tuple[str, ...]
    development_evaluator_paths: tuple[str, ...]
    partitions: Mapping[str, AgentContextPartitionMetadata]
    scientific_input_lock: AgentContextFileReference


@dataclass(frozen=True)
class AgentContextProtocolAuthority:
    repository_root: Path
    protocol_read: DirectFileRead
    scientific_lock_read: DirectFileRead
    metadata: AgentContextProtocolMetadata
    development_source_projection_sha256: str
    development_case_projection_sha256: str
    development_span_projection_sha256: str


@dataclass(frozen=True)
class AgentContextObserverAuthority:
    repository_root: Path
    source_ids: tuple[str, ...]
    query_ids: tuple[str, ...]
    source_receipts: AgentContextFileReference
    observer_cases: AgentContextFileReference
    source_projection_sha256: str
    case_projection_sha256: str


def build_agent_context_unit_observer_authority(
    authority: AgentContextProtocolAuthority,
) -> AgentContextObserverAuthority:
    development = authority.metadata.partitions["development"]
    return AgentContextObserverAuthority(
        repository_root=authority.repository_root,
        source_ids=development.source_ids,
        query_ids=development.query_ids,
        source_receipts=development.source_receipts,
        observer_cases=development.observer_cases,
        source_projection_sha256=authority.development_source_projection_sha256,
        case_projection_sha256=authority.development_case_projection_sha256,
    )


def _closed_mapping(value: object, fields: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} field set is invalid")
    mapping = cast(dict[object, object], value)
    if set(mapping) != fields:
        raise ValueError(f"{name} field set is invalid")
    return cast(dict[str, Any], value)


def _relative_path(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("fixture path is invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise ValueError("fixture path is invalid")
    return value


def _string_tuple(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{name} is invalid")
    items = cast(list[object], value)
    if not items or not all(isinstance(item, str) and item for item in items):
        raise ValueError(f"{name} is invalid")
    result = tuple(cast(str, item) for item in items)
    if len(set(result)) != len(result):
        raise ValueError(f"{name} is invalid")
    return result


def _source_paths(value: object, name: str) -> tuple[str, ...]:
    result = _string_tuple(value, name)
    if result != tuple(sorted(result)):
        raise ValueError(f"{name} is invalid")
    for item in result:
        _relative_path(item)
    return result


def _file_reference(value: object, name: str) -> AgentContextFileReference:
    record = _closed_mapping(value, {"bytes", "path", "sha256"}, name)
    if (
        type(record["bytes"]) is not int
        or record["bytes"] < 0
        or not isinstance(record["sha256"], str)
        or _SHA256.fullmatch(record["sha256"]) is None
    ):
        raise ValueError(f"{name} identity is invalid")
    return AgentContextFileReference(
        path=_relative_path(record["path"]),
        bytes=record["bytes"],
        sha256=record["sha256"],
    )


def validate_agent_context_unit_file_read(
    reference: AgentContextFileReference,
    read: DirectFileRead,
    *,
    name: str,
) -> None:
    if read.identity != {
        "path": reference.path,
        "bytes": reference.bytes,
        "sha256": reference.sha256,
    }:
        raise ValueError(f"{name} identity is invalid")


def _is_plain_file(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return stat.S_ISREG(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode)


def _is_plain_directory(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode)


def _repository_root(path: Path) -> Path:
    absolute = path.absolute()
    for parent in absolute.parents:
        if _is_plain_file(parent / "pyproject.toml") and _is_plain_directory(
            parent / "src/mke"
        ):
            return parent
    raise ValueError("protocol repository root is invalid")


def _canonical_sha256(value: object) -> str:
    from hashlib import sha256

    content = json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    return sha256(content).hexdigest()


def _scientific_projection(
    record: dict[str, Any],
    partitions: Mapping[str, AgentContextPartitionMetadata],
    lock_content: bytes,
) -> tuple[str, str, str]:
    lock_value: object = json.loads(lock_content)
    if not isinstance(lock_value, dict):
        raise ValueError("scientific projection is invalid")
    lock = cast(dict[str, object], lock_value)
    if lock.get("schema_version") != "mke.agent_context_unit_scientific_input_lock.v1":
        raise ValueError("scientific projection is invalid")
    for field in (
        "candidate_profile",
        "projection_bounds",
        "runtime_profile_fields",
        "mechanism_verdict_revision",
        "stage_verdict_revision",
    ):
        if record[field] != lock.get(field):
            raise ValueError("scientific projection is invalid")
    lock_partitions = lock.get("partitions")
    if not isinstance(lock_partitions, dict):
        raise ValueError("scientific projection is invalid")
    lock_partitions = cast(dict[str, object], lock_partitions)
    for name in ("development", "holdout"):
        value = lock_partitions.get(name)
        if not isinstance(value, dict):
            raise ValueError("scientific projection is invalid")
        partition = cast(dict[str, object], value)
        if list(partitions[name].source_ids) != partition.get("source_ids"):
            raise ValueError("scientific projection is invalid")
        if list(partitions[name].query_ids) != partition.get("query_ids"):
            raise ValueError("scientific projection is invalid")
    development = cast(dict[str, object], lock_partitions["development"])
    sources = development.get("sources")
    cases = development.get("observer_cases")
    spans = development.get("required_spans")
    if (
        not isinstance(sources, list)
        or not isinstance(cases, list)
        or not isinstance(spans, list)
    ):
        raise ValueError("scientific projection is invalid")
    sources = cast(list[object], sources)
    cases = cast(list[object], cases)
    spans = cast(list[object], spans)
    return (
        _canonical_sha256(sources),
        _canonical_sha256(cases),
        _canonical_sha256(spans),
    )


def load_agent_context_unit_protocol_authority(
    protocol_path: Path,
) -> AgentContextProtocolAuthority:
    repository_root = _repository_root(protocol_path)
    try:
        relative_protocol_path = protocol_path.absolute().relative_to(repository_root)
    except ValueError:
        raise ValueError("protocol repository root is invalid") from None
    protocol_read = read_no_follow_regular_file(
        repository_root,
        PurePosixPath(relative_protocol_path).as_posix(),
    )
    payload = json.loads(protocol_read.content)
    record = _closed_mapping(payload, _PROTOCOL_FIELDS, "protocol")
    if record["schema_version"] != "mke.agent_context_unit_protocol.v2":
        raise ValueError("protocol schema is invalid")
    partitions_record = _closed_mapping(
        record["partitions"], {"development", "holdout"}, "partitions"
    )
    partitions: dict[str, AgentContextPartitionMetadata] = {}
    for name in ("development", "holdout"):
        partition = _closed_mapping(
            partitions_record[name], _PARTITION_FIELDS, f"{name} partition"
        )
        partitions[name] = AgentContextPartitionMetadata(
            source_ids=_string_tuple(partition["source_ids"], f"{name} source ids"),
            query_ids=_string_tuple(partition["query_ids"], f"{name} query ids"),
            source_receipts=_file_reference(
                partition["source_receipts"], f"{name} source receipts"
            ),
            observer_cases=_file_reference(
                partition["observer_cases"], f"{name} observer cases"
            ),
            labels=_file_reference(partition["labels"], f"{name} labels"),
        )
    if not isinstance(record["candidate_profile"], dict) or not isinstance(
        record["projection_bounds"], dict
    ):
        raise ValueError("protocol profile is invalid")
    scientific_input_lock = _file_reference(
        record["scientific_input_lock"], "scientific input lock"
    )
    lock_read = read_no_follow_regular_file(
        repository_root, scientific_input_lock.path
    )
    validate_agent_context_unit_file_read(
        scientific_input_lock,
        lock_read,
        name="scientific input lock",
    )
    metadata = AgentContextProtocolMetadata(
        schema_version=record["schema_version"],
        protocol_id=record["protocol_id"],
        candidate_profile=MappingProxyType(
            cast(dict[str, Any], record["candidate_profile"])
        ),
        projection_bounds=MappingProxyType(
            cast(dict[str, Any], record["projection_bounds"])
        ),
        runtime_profile_fields=_string_tuple(
            record["runtime_profile_fields"], "runtime profile fields"
        ),
        mechanism_verdict_revision=record["mechanism_verdict_revision"],
        stage_verdict_revision=record["stage_verdict_revision"],
        o0_evaluator_paths=_source_paths(
            record["o0_evaluator_paths"], "O0 evaluator paths"
        ),
        development_evaluator_paths=_source_paths(
            record["development_evaluator_paths"], "development evaluator paths"
        ),
        partitions=MappingProxyType(partitions),
        scientific_input_lock=scientific_input_lock,
    )
    source_projection, case_projection, span_projection = _scientific_projection(
        record,
        metadata.partitions,
        lock_read.content,
    )
    return AgentContextProtocolAuthority(
        repository_root=repository_root,
        protocol_read=protocol_read,
        scientific_lock_read=lock_read,
        metadata=metadata,
        development_source_projection_sha256=source_projection,
        development_case_projection_sha256=case_projection,
        development_span_projection_sha256=span_projection,
    )


def load_agent_context_unit_protocol_metadata(
    protocol_path: Path,
) -> AgentContextProtocolMetadata:
    return load_agent_context_unit_protocol_authority(protocol_path).metadata
