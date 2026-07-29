from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, cast

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


@dataclass(frozen=True)
class AgentContextPartitionMetadata:
    source_ids: tuple[str, ...]
    query_ids: tuple[str, ...]
    source_receipts_path: str
    observer_cases_path: str


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


def _file_reference(value: object, name: str) -> str:
    record = _closed_mapping(value, {"bytes", "path", "sha256"}, name)
    if (
        type(record["bytes"]) is not int
        or record["bytes"] < 0
        or not isinstance(record["sha256"], str)
        or len(record["sha256"]) != 64
    ):
        raise ValueError(f"{name} identity is invalid")
    return _relative_path(record["path"])


def load_agent_context_unit_protocol_metadata(
    protocol_path: Path,
) -> AgentContextProtocolMetadata:
    payload = json.loads(protocol_path.read_bytes())
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
            source_receipts_path=_file_reference(
                partition["source_receipts"], f"{name} source receipts"
            ),
            observer_cases_path=_file_reference(
                partition["observer_cases"], f"{name} observer cases"
            ),
        )
    if not isinstance(record["candidate_profile"], dict) or not isinstance(
        record["projection_bounds"], dict
    ):
        raise ValueError("protocol profile is invalid")
    return AgentContextProtocolMetadata(
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
    )
