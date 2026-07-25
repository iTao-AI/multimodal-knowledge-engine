from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Literal

from mke.domain import ActivePublicationObservation, SearchResultProvenance

_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class ActiveAuthorityRecord:
    source_id: str
    content_fingerprint: str
    active_publication_id: str
    active_revision: int
    run_id: str
    manifest_evidence_count: int
    manifest_sha256: str
    required_stages: tuple[str, ...]
    extractor_fingerprint: str

    def __post_init__(self) -> None:
        if not self.source_id or not self.active_publication_id or not self.run_id:
            raise ValueError("active authority identity must not be blank")
        if _SHA256.fullmatch(self.content_fingerprint) is None:
            raise ValueError("content fingerprint must be a lowercase sha256 digest")
        if re.fullmatch(r"[0-9a-f]{64}", self.manifest_sha256) is None:
            raise ValueError("manifest sha256 must be a lowercase digest")
        if self.active_revision < 1 or self.manifest_evidence_count < 1:
            raise ValueError("active authority counts must be positive")
        if self.required_stages != tuple(sorted(set(self.required_stages))):
            raise ValueError("required stages must be sorted and unique")


@dataclass(frozen=True)
class ActiveAuthoritySnapshot:
    observation: ActivePublicationObservation
    active_set_fingerprint: str

    def __post_init__(self) -> None:
        if _SHA256.fullmatch(self.active_set_fingerprint) is None:
            raise ValueError("active set fingerprint must be a lowercase sha256 digest")


@dataclass(frozen=True)
class EvidenceDescriptor:
    evidence_id: str
    source_id: str
    content_fingerprint: str
    publication_id: str
    publication_revision: int
    run_id: str
    locator_kind: Literal["page", "timestamp_ms"]
    locator_start: int
    locator_end: int
    evidence_text_sha256: str
    original_utf8_bytes: int

    def __post_init__(self) -> None:
        if not all((self.evidence_id, self.source_id, self.publication_id, self.run_id)):
            raise ValueError("Evidence descriptor identities must not be blank")
        if _SHA256.fullmatch(self.content_fingerprint) is None or _SHA256.fullmatch(
            self.evidence_text_sha256
        ) is None:
            raise ValueError("Evidence descriptor digests must be lowercase sha256 values")
        if self.publication_revision < 1 or self.original_utf8_bytes < 1:
            raise ValueError("Evidence descriptor counts must be positive")
        valid = (
            self.locator_kind == "page"
            and self.locator_start > 0
            and self.locator_end == self.locator_start
            or self.locator_kind == "timestamp_ms"
            and self.locator_start >= 0
            and self.locator_end > self.locator_start
        )
        if not valid:
            raise ValueError("Evidence descriptor locator is invalid")


@dataclass(frozen=True)
class ActiveEvidenceRecord:
    evidence_id: str
    source_id: str
    content_fingerprint: str
    publication_id: str
    publication_revision: int
    run_id: str
    locator_kind: Literal["page", "timestamp_ms"]
    locator_start: int
    locator_end: int
    original_utf8_bytes: int


@dataclass(frozen=True)
class MatchHint:
    text: str
    clause_order: int
    term_order: int


@dataclass(frozen=True)
class EvidenceExcerpt:
    kind: Literal["query_window", "prefix_fallback"]
    text: str
    start_utf8_byte: int
    end_utf8_byte: int
    prefix_omitted: bool
    suffix_omitted: bool
    complete: bool
    returned_utf8_bytes: int
    content_trust: Literal["untrusted_evidence"] = "untrusted_evidence"


@dataclass(frozen=True)
class Utf8Chunk:
    text: str
    offset_bytes: int
    returned_utf8_bytes: int
    next_offset_bytes: int


@dataclass(frozen=True)
class SelectedEvidence:
    provenance: SearchResultProvenance
    hints: tuple[MatchHint, ...]


@dataclass(frozen=True)
class EvidenceSearchPage:
    authority: ActiveAuthoritySnapshot
    normalized_query: str
    strategy_id: str
    strategy_revision: int
    query_policy: str
    query_policy_revision: int
    position: int
    results: tuple[SelectedEvidence, ...]
    more_in_selected_pool: bool
    eligible_discarded_by_cap: bool


@dataclass(frozen=True)
class EvidenceReadSnapshot:
    authority: ActiveAuthoritySnapshot
    record: ActiveEvidenceRecord
    text: str | None
    range_bytes: bytes
    offset_bytes: int


def derive_active_set_fingerprint(
    records: tuple[ActiveAuthorityRecord, ...],
) -> str:
    payload = {
        "domain": "mke.active_set_fingerprint",
        "schema_version": "mke.active_set_fingerprint.v1",
        "library_id": "local",
        "records": [
            asdict(record) | {"required_stages": list(record.required_stages)}
            for record in sorted(records, key=lambda value: value.source_id.encode())
        ],
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    return f"sha256:{sha256(encoded).hexdigest()}"
