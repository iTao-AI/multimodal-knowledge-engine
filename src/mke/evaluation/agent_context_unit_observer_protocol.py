from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from mke.evaluation.agent_context_unit_protocol import (
    load_agent_context_unit_protocol_metadata,
)


@dataclass(frozen=True)
class AgentContextSourceReceipt:
    source_id: str
    path: str
    content_fingerprint: str
    bytes: int
    pages: int
    nonempty_text_pages: int
    extracted_text_utf8_bytes: int
    pymupdf_version: str


@dataclass(frozen=True)
class AgentContextObserverCase:
    query_id: str
    query_text: str
    source_content_fingerprints: tuple[str, ...]
    runtime_route_profile: str
    observation_ids: tuple[str, ...]


@dataclass(frozen=True)
class AgentContextObserverContract:
    sources: tuple[AgentContextSourceReceipt, ...]
    cases: tuple[AgentContextObserverCase, ...]


def _repository_root(protocol_path: Path) -> Path:
    resolved = protocol_path.resolve(strict=True)
    for parent in resolved.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src/mke").is_dir():
            return parent
    raise ValueError("protocol repository root is invalid")


def load_agent_context_unit_observer_contract(
    protocol_path: Path,
) -> AgentContextObserverContract:
    metadata = load_agent_context_unit_protocol_metadata(protocol_path)
    root = _repository_root(protocol_path)
    partition = metadata.partitions["development"]
    receipts = json.loads((root / partition.source_receipts_path).read_bytes())
    cases = json.loads((root / partition.observer_cases_path).read_bytes())
    if set(receipts) != {"schema_version", "sources"} or receipts[
        "schema_version"
    ] != "mke.agent_context_unit_source_receipts.v2":
        raise ValueError("source receipt contract is invalid")
    if set(cases) != {"schema_version", "cases"} or cases[
        "schema_version"
    ] != "mke.agent_context_unit_observer_cases.v2":
        raise ValueError("observer case contract is invalid")
    source_records = tuple(
        AgentContextSourceReceipt(
            source_id=item["source_id"],
            path=item["path"],
            content_fingerprint=item["content_fingerprint"],
            bytes=item["bytes"],
            pages=item["pages"],
            nonempty_text_pages=item["nonempty_text_pages"],
            extracted_text_utf8_bytes=item["extracted_text_utf8_bytes"],
            pymupdf_version=item["pymupdf_version"],
        )
        for item in receipts["sources"]
    )
    case_records = tuple(
        AgentContextObserverCase(
            query_id=item["query_id"],
            query_text=item["query_text"],
            source_content_fingerprints=tuple(item["source_content_fingerprints"]),
            runtime_route_profile=item["runtime_route_profile"],
            observation_ids=tuple(item["observation_ids"]),
        )
        for item in cases["cases"]
    )
    if tuple(item.source_id for item in source_records) != partition.source_ids:
        raise ValueError("observer source inventory is invalid")
    if tuple(item.query_id for item in case_records) != partition.query_ids:
        raise ValueError("observer query inventory is invalid")
    return AgentContextObserverContract(sources=source_records, cases=case_records)
