from dataclasses import replace

import pytest

from mke.application import source_cursor as module
from mke.application.mcp_cursor import (
    CursorExpiredError,
    InvalidCursorError,
    parse_cursor_untrusted,
)
from mke.domain import ActivePublicationObservation
from mke.domain.evidence_access import ActiveAuthoritySnapshot
from mke.runtime_owner import CursorOwnerMaterial


def test_source_cursors_authenticate_every_binding() -> None:
    owner = CursorOwnerMaterial(key=b"k" * 32, epoch="epoch")
    authority = ActiveAuthoritySnapshot(
        ActivePublicationObservation("local", "empty", 0, 0, 0), "sha256:" + "a" * 64
    )
    binding = module.library_binding(owner, "/configured/library.sqlite")
    payload = module.SourceCursorPayload(
        schema_version="mke.mcp_cursor.v1",
        tool="list_sources_v1",
        owner_epoch="epoch",
        active_set_fingerprint=authority.active_set_fingerprint,
        library_binding=binding,
        position=1,
        page_size=10,
        response_schema="mke.list_sources_response.v1",
        source_id="",
        publication_id="",
        locator_kind="",
        locator_start=0,
        locator_end=0,
        ordering_version="content-fingerprint-source-id-v1",
    )
    token = module.encode_source_cursor(owner, payload)
    parsed = parse_cursor_untrusted(token)
    assert (
        module.validate_source_cursor(
            parsed, owner, authority, tool="list_sources_v1", library_binding=binding
        )
        == payload
    )
    for tool, selected_binding in [
        ("browse_source_evidence_v1", binding),
        ("list_sources_v1", module.library_binding(owner, "/other.sqlite")),
    ]:
        with pytest.raises(InvalidCursorError):
            module.validate_source_cursor(
                parsed, owner, authority, tool=tool, library_binding=selected_binding
            )
    with pytest.raises(CursorExpiredError):
        module.validate_source_cursor(
            parsed,
            replace(owner, epoch="new"),
            authority,
            tool="list_sources_v1",
            library_binding=binding,
        )
    with pytest.raises(CursorExpiredError):
        module.validate_source_cursor(
            parsed,
            owner,
            replace(authority, active_set_fingerprint="sha256:" + "b" * 64),
            tool="list_sources_v1",
            library_binding=binding,
        )
    forged = replace(parsed, supplied_mac=b"x" * 32)
    with pytest.raises(InvalidCursorError):
        module.validate_source_cursor(
            forged, owner, authority, tool="list_sources_v1", library_binding=binding
        )


def test_page_assembly_obeys_bytes_and_progresses() -> None:
    from mke.application.evidence_access import ResponseTooLargeError
    from mke.application.source_discovery import assemble_source_page
    from mke.domain.source_discovery import PdfSourceCoverage, SourceCatalogPage, SourceMetadata

    authority = ActiveAuthoritySnapshot(
        ActivePublicationObservation("local", "active", 3, 3, 3), "sha256:" + "a" * 64
    )
    sources = tuple(
        SourceMetadata(
            f"src_{i}",
            "x" * 14000,
            "application/pdf",
            "sha256:" + "a" * 64,
            f"pub_{i}",
            1,
            "run",
            "extractor",
            ("extract",),
            1,
            PdfSourceCoverage("not_observed"),
        )
        for i in range(3)
    )
    page = SourceCatalogPage(authority, 0, sources, False)

    def serialize(selected: SourceCatalogPage, cursor: str | None) -> object:
        return {"sources": [item.display_name for item in selected.sources], "cursor": cursor}

    first = assemble_source_page(
        page, cursor_factory=lambda position: f"cursor-{position}", serialize_response=serialize
    )
    assert len(first.page.sources) == 2
    assert first.next_cursor == "cursor-2"
    assert first.page.more_available is True

    def oversized(selected: SourceCatalogPage, cursor: str | None) -> object:
        return {"mandatory": "x" * 40000}

    with pytest.raises(ResponseTooLargeError):
        assemble_source_page(
            page, cursor_factory=lambda position: f"cursor-{position}", serialize_response=oversized
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"page_size": True},
        {"page_size": 21},
        {"position": 0},
        {"response_schema": "mke.read_evidence_response.v1"},
        {"ordering_version": "new-order"},
        {"locator_kind": "page", "locator_start": 0, "locator_end": 1},
        {"source_id": "foreign"},
        {"publication_id": "foreign"},
    ],
)
def test_authenticated_altered_catalog_bindings_are_rejected(changes: dict[str, object]) -> None:
    from typing import Any, cast

    from mke.application.source_cursor import (
        SourceCursorPayload,
        encode_source_cursor,
        library_binding,
        validate_source_cursor,
    )

    owner = CursorOwnerMaterial(key=b"k" * 32, epoch="epoch")
    authority = ActiveAuthoritySnapshot(
        ActivePublicationObservation("local", "empty", 0, 0, 0), "sha256:" + "a" * 64
    )
    binding = library_binding(owner, "/configured/library.sqlite")
    payload = SourceCursorPayload(
        "mke.mcp_cursor.v1",
        "list_sources_v1",
        "epoch",
        authority.active_set_fingerprint,
        binding,
        1,
        10,
        "mke.list_sources_response.v1",
        "",
        "",
        "",
        0,
        0,
        "content-fingerprint-source-id-v1",
    )
    token = encode_source_cursor(owner, replace(payload, **cast(Any, changes)))
    with pytest.raises(InvalidCursorError):
        validate_source_cursor(
            parse_cursor_untrusted(token),
            owner,
            authority,
            tool="list_sources_v1",
            library_binding=binding,
        )


@pytest.mark.parametrize("token", ["", "not base64!", "a" * 4097, "e30", "W10"])
def test_source_cursor_parser_rejects_malformed_envelopes(token: str) -> None:
    with pytest.raises(InvalidCursorError):
        parse_cursor_untrusted(token)


def test_browse_cursor_routes_authenticated_locator_and_source() -> None:
    owner = CursorOwnerMaterial(key=b"k" * 32, epoch="epoch")
    authority = ActiveAuthoritySnapshot(
        ActivePublicationObservation("local", "empty", 0, 0, 0), "sha256:" + "a" * 64
    )
    binding = module.library_binding(owner, "/configured/library.sqlite")
    payload = module.SourceCursorPayload(
        "mke.mcp_cursor.v1",
        "browse_source_evidence_v1",
        owner.epoch,
        authority.active_set_fingerprint,
        binding,
        4,
        10,
        "mke.browse_source_evidence_response.v1",
        "src",
        "pub",
        "timestamp_ms",
        0,
        1200,
        "locator-start-end-evidence-id-v1",
    )
    parsed = parse_cursor_untrusted(module.encode_source_cursor(owner, payload))
    validated = module.validate_source_cursor(
        parsed, owner, authority, tool="browse_source_evidence_v1", library_binding=binding
    )
    source, publication, locator, position, size = module.untrusted_source_route(parsed)
    assert validated == payload
    assert (source, publication, position, size) == ("src", "pub", 4, 10)
    assert locator is not None and (locator.kind, locator.start, locator.end) == (
        "timestamp_ms",
        0,
        1200,
    )
    for changes in [
        {"locator_kind": "page", "locator_start": 0},
        {"locator_kind": "", "locator_end": 1200},
        {"response_schema": "mke.list_sources_response.v1"},
        {"ordering_version": "new-order"},
        {"source_id": ""},
        {"publication_id": ""},
    ]:
        from typing import Any, cast

        altered = parse_cursor_untrusted(
            module.encode_source_cursor(owner, replace(payload, **cast(Any, changes)))
        )
        with pytest.raises(InvalidCursorError):
            module.validate_source_cursor(
                altered, owner, authority, tool="browse_source_evidence_v1", library_binding=binding
            )
