from __future__ import annotations

import json
from dataclasses import dataclass

from mke.evaluation.agent_context_unit_protocol import (
    AgentContextObserverAuthority,
    validate_agent_context_unit_file_read,
)
from mke.evaluation.source_identity import read_no_follow_regular_file


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


def load_agent_context_unit_observer_contract(
    authority: AgentContextObserverAuthority,
) -> AgentContextObserverContract:
    root = authority.repository_root
    receipt_read = read_no_follow_regular_file(root, authority.source_receipts.path)
    case_read = read_no_follow_regular_file(root, authority.observer_cases.path)
    if receipt_read.physical_identity == case_read.physical_identity:
        raise ValueError("observer fixture physical aliases are invalid")
    validate_agent_context_unit_file_read(
        authority.source_receipts,
        receipt_read,
        name="development source receipts",
    )
    validate_agent_context_unit_file_read(
        authority.observer_cases,
        case_read,
        name="development observer cases",
    )
    receipts = json.loads(receipt_read.content)
    cases = json.loads(case_read.content)
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
    if tuple(item.source_id for item in source_records) != authority.source_ids:
        raise ValueError("observer source inventory is invalid")
    if tuple(item.query_id for item in case_records) != authority.query_ids:
        raise ValueError("observer query inventory is invalid")
    source_projection = [
        {
            "source_id": item.source_id,
            "content_fingerprint": item.content_fingerprint,
            "bytes": item.bytes,
            "pages": item.pages,
            "nonempty_text_pages": item.nonempty_text_pages,
            "extracted_text_utf8_bytes": item.extracted_text_utf8_bytes,
            "pymupdf_version": item.pymupdf_version,
        }
        for item in source_records
    ]
    case_projection = [
        {
            "query_id": item.query_id,
            "query_text": item.query_text,
            "source_content_fingerprints": list(item.source_content_fingerprints),
            "runtime_route_profile": item.runtime_route_profile,
            "observation_ids": list(item.observation_ids),
        }
        for item in case_records
    ]
    if (
        _canonical_sha256(source_projection)
        != authority.source_projection_sha256
        or _canonical_sha256(case_projection)
        != authority.case_projection_sha256
    ):
        raise ValueError("observer scientific projection is invalid")
    return AgentContextObserverContract(sources=source_records, cases=case_records)


def _canonical_sha256(value: object) -> str:
    from hashlib import sha256

    return sha256(
        json.dumps(
            value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode()
    ).hexdigest()
