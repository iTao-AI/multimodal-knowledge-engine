"""Development-label authority opened only after the O0 observation seal."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import cast

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SPAN_FIELDS = {
    "byte_range",
    "control",
    "hypothesis",
    "locator",
    "query_id",
    "role",
    "source_content_fingerprint",
    "span_id",
    "text_sha256",
}


@dataclass(frozen=True)
class AgentContextRequiredSpan:
    span_id: str
    query_id: str
    source_content_fingerprint: str
    locator_kind: str
    locator_start: int
    locator_end: int
    start_utf8_byte: int
    end_utf8_byte: int
    text_sha256: str
    role: str
    hypothesis: str
    control: str

    def __post_init__(self) -> None:
        if (
            not all(
                (
                    self.span_id,
                    self.query_id,
                    self.role,
                    self.hypothesis,
                    self.control,
                )
            )
            or not self.source_content_fingerprint.startswith("sha256:")
            or _SHA256.fullmatch(
                self.source_content_fingerprint.removeprefix("sha256:")
            )
            is None
            or _SHA256.fullmatch(self.text_sha256) is None
            or self.start_utf8_byte < 0
            or self.end_utf8_byte <= self.start_utf8_byte
        ):
            raise ValueError("required span is invalid")


@dataclass(frozen=True)
class AgentContextBaselineGradingPayload:
    required_spans: tuple[AgentContextRequiredSpan, ...]

    def __post_init__(self) -> None:
        identities = tuple(item.span_id for item in self.required_spans)
        if not identities or len(set(identities)) != len(identities):
            raise ValueError("grading span inventory is invalid")


def load_agent_context_unit_baseline_grading_payload(
    protocol_path: Path,
) -> AgentContextBaselineGradingPayload:
    if protocol_path.name != "protocol.json":
        raise ValueError("baseline grading authority must be development protocol")
    protocol_value: object = json.loads(protocol_path.read_bytes())
    if not isinstance(protocol_value, dict):
        raise ValueError("protocol is invalid")
    protocol = cast(dict[str, object], protocol_value)
    partitions = protocol.get("partitions")
    if not isinstance(partitions, dict):
        raise ValueError("protocol is invalid")
    partitions = cast(dict[str, object], partitions)
    development = partitions.get("development")
    if not isinstance(development, dict):
        raise ValueError("development grading authority is invalid")
    development = cast(dict[str, object], development)
    labels = development.get("labels")
    if not isinstance(labels, dict):
        raise ValueError("development grading authority is invalid")
    labels = cast(dict[str, object], labels)
    if set(labels) != {"bytes", "path", "sha256"}:
        raise ValueError("development grading authority is invalid")
    relative = labels["path"]
    if not isinstance(relative, str):
        raise ValueError("development grading authority is invalid")
    pure = PurePosixPath(relative)
    if (
        pure.is_absolute()
        or ".." in pure.parts
        or "development" not in pure.parts
        or "holdout" in pure.parts
    ):
        raise ValueError("development grading authority is invalid")
    root = _repository_root(protocol_path)
    label_path = root / relative
    content = label_path.read_bytes()
    if (
        type(labels["bytes"]) is not int
        or len(content) != labels["bytes"]
        or not isinstance(labels["sha256"], str)
        or _digest(content) != labels["sha256"]
    ):
        raise ValueError("development grading identity is invalid")
    payload_value: object = json.loads(content)
    if not isinstance(payload_value, dict):
        raise ValueError("development grading payload is invalid")
    payload = cast(dict[str, object], payload_value)
    if set(payload) != {"required_spans", "schema_version"}:
        raise ValueError("development grading payload is invalid")
    if (
        payload["schema_version"] != "mke.agent_context_unit_labels.v2"
        or not isinstance(payload["required_spans"], list)
    ):
        raise ValueError("development grading payload is invalid")
    spans: list[AgentContextRequiredSpan] = []
    for value in cast(list[object], payload["required_spans"]):
        if not isinstance(value, dict):
            raise ValueError("development grading payload is invalid")
        item = cast(dict[str, object], value)
        if set(item) != _SPAN_FIELDS:
            raise ValueError("development grading payload is invalid")
        locator = item["locator"]
        byte_range = item["byte_range"]
        if not isinstance(locator, dict) or not isinstance(byte_range, dict):
            raise ValueError("development grading payload is invalid")
        locator = cast(dict[str, object], locator)
        byte_range = cast(dict[str, object], byte_range)
        if set(locator) != {"end", "kind", "start"} or set(byte_range) != {
            "end",
            "start",
        }:
            raise ValueError("development grading payload is invalid")
        spans.append(
            AgentContextRequiredSpan(
                span_id=_string(item["span_id"]),
                query_id=_string(item["query_id"]),
                source_content_fingerprint=_string(
                    item["source_content_fingerprint"]
                ),
                locator_kind=_string(locator["kind"]),
                locator_start=_integer(locator["start"]),
                locator_end=_integer(locator["end"]),
                start_utf8_byte=_integer(byte_range["start"]),
                end_utf8_byte=_integer(byte_range["end"]),
                text_sha256=_string(item["text_sha256"]),
                role=_string(item["role"]),
                hypothesis=_string(item["hypothesis"]),
                control=_string(item["control"]),
            )
        )
    return AgentContextBaselineGradingPayload(tuple(spans))


def _repository_root(path: Path) -> Path:
    resolved = path.resolve(strict=True)
    for parent in resolved.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src/mke").is_dir():
            return parent
    raise ValueError("protocol repository root is invalid")


def _string(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("development grading payload is invalid")
    return value


def _integer(value: object) -> int:
    if type(value) is not int:
        raise ValueError("development grading payload is invalid")
    return value


def _digest(content: bytes) -> str:
    from hashlib import sha256

    return sha256(content).hexdigest()
