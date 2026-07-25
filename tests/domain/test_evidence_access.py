from dataclasses import replace

from mke.domain import ActivePublicationObservation
from mke.domain.evidence_access import (
    ActiveAuthorityRecord,
    ActiveAuthoritySnapshot,
    EvidenceDescriptor,
    derive_active_set_fingerprint,
)


def _record() -> ActiveAuthorityRecord:
    return ActiveAuthorityRecord(
        source_id="src_a",
        content_fingerprint="sha256:" + "a" * 64,
        active_publication_id="pub_a",
        active_revision=1,
        run_id="run_a",
        manifest_evidence_count=1,
        manifest_sha256="b" * 64,
        required_stages=("candidate_persisted",),
        extractor_fingerprint="extractor-v1",
    )


def test_active_fingerprint_is_order_independent_and_field_sensitive() -> None:
    first = _record()
    second = replace(first, source_id="src_b", active_publication_id="pub_b")
    expected = derive_active_set_fingerprint((first, second))
    assert derive_active_set_fingerprint((second, first)) == expected
    assert derive_active_set_fingerprint((replace(first, active_revision=2), second)) != expected


def test_authority_and_descriptor_validate_public_invariants() -> None:
    observation = ActivePublicationObservation("local", "active", 1, 1, 1)
    authority = ActiveAuthoritySnapshot(observation, derive_active_set_fingerprint((_record(),)))
    descriptor = EvidenceDescriptor(
        evidence_id="ev_a",
        source_id="src_a",
        content_fingerprint="sha256:" + "a" * 64,
        publication_id="pub_a",
        publication_revision=1,
        run_id="run_a",
        locator_kind="page",
        locator_start=1,
        locator_end=1,
        evidence_text_sha256="sha256:" + "c" * 64,
        original_utf8_bytes=1,
    )
    assert authority.active_set_fingerprint.startswith("sha256:")
    assert descriptor.original_utf8_bytes == 1
