import pytest
from pydantic import ValidationError

from mke.interfaces import source_schemas as schemas


def test_requests_are_strict_initial_or_continuation() -> None:
    initial = schemas.LIST_SOURCES_INPUT_V1.validate_python({})
    assert isinstance(initial, schemas.ListSourcesInitialV1)
    assert initial.page_size == 10
    for value in [{"page_size": True}, {"page_size": 21}, {"cursor": "abc", "page_size": 1}]:
        with pytest.raises(ValidationError):
            schemas.LIST_SOURCES_INPUT_V1.validate_python(value)
    for value in [
        {
            "source_id": "src",
            "publication_id": "pub",
            "locator_range": {"kind": "page", "start": 0, "end": 2},
        },
        {"cursor": "abc", "source_id": "src"},
    ]:
        with pytest.raises(ValidationError):
            schemas.BROWSE_SOURCE_INPUT_V1.validate_python(value)


def test_additive_responses_are_closed() -> None:
    for value in [
        {"status": "complete", "returned": 1, "next_cursor": "x"},
        {"status": "more_available", "returned": 0, "next_cursor": "x"},
        {"status": "more_available", "returned": 1},
    ]:
        with pytest.raises(ValidationError):
            schemas.SOURCE_SELECTION_V1.validate_python(value)
    with pytest.raises(ValidationError):
        schemas.SourceMetadataV1.model_validate({"source_id": "src"})


def browse_response() -> dict[str, object]:
    return {
        "ok": True,
        "authority_snapshot": {
            "observation": {
                "state": "active",
                "source_count": 1,
                "active_publication_count": 1,
                "active_evidence_count": 1,
            },
            "active_set_fingerprint": "sha256:" + "a" * 64,
        },
        "source": {
            "source_id": "src",
            "display_name": "example.pdf",
            "media_type": "application/pdf",
            "content_fingerprint": "sha256:" + "b" * 64,
            "publication_id": "pub",
            "publication_revision": 1,
            "run_id": "run",
            "extractor_fingerprint": "extractor",
            "required_stages": ["extract"],
            "evidence_count": 1,
            "coverage": {
                "kind": "pdf",
                "report_status": "not_observed",
                "extraction_mode": None,
                "total_pages": None,
                "extracted_pages": None,
                "empty_pages": None,
                "suspected_scanned_pages": None,
                "total_extracted_chars": None,
                "page_char_counts": [],
                "page_char_counts_total": None,
                "page_char_counts_omitted": False,
            },
        },
        "entries": [
            {
                "evidence": {
                    "evidence_id": "ev",
                    "source_id": "src",
                    "content_fingerprint": "sha256:" + "b" * 64,
                    "publication_id": "pub",
                    "publication_revision": 1,
                    "run_id": "run",
                    "locator": {"kind": "page", "start": 1, "end": 1},
                    "evidence_text_sha256": "sha256:" + "c" * 64,
                    "original_utf8_bytes": 3,
                },
                "excerpt": {
                    "kind": "prefix_fallback",
                    "text": "one",
                    "start_utf8_byte": 0,
                    "end_utf8_byte": 3,
                    "prefix_omitted": False,
                    "suffix_omitted": False,
                    "complete": True,
                    "returned_utf8_bytes": 3,
                    "content_trust": "untrusted_evidence",
                },
                "read": {"tool": "read_evidence_v1", "evidence_id": "ev"},
            }
        ],
        "selection": {"status": "complete", "returned": 1},
        "output": {"incomplete_excerpt_count": 0},
    }


@pytest.mark.parametrize(
    "field",
    ["source_id", "publication_id", "run_id", "content_fingerprint", "publication_revision"],
)
def test_browse_response_rejects_descriptor_outside_selected_source(field: str) -> None:
    from typing import Any, cast

    from mke.interfaces.source_schemas import BrowseSourceEvidenceResponseV1

    value = cast(dict[str, Any], browse_response())
    value["entries"][0]["evidence"][field] = (
        2
        if field == "publication_revision"
        else "sha256:" + "d" * 64
        if field == "content_fingerprint"
        else "foreign"
    )
    with pytest.raises(ValidationError):
        BrowseSourceEvidenceResponseV1.model_validate(value)


def test_browse_response_rejects_incorrect_read_affordance() -> None:
    from typing import Any, cast

    from mke.interfaces.source_schemas import BrowseSourceEvidenceResponseV1

    value = cast(dict[str, Any], browse_response())
    value["entries"][0]["read"]["evidence_id"] = "foreign"
    with pytest.raises(ValidationError):
        BrowseSourceEvidenceResponseV1.model_validate(value)


def test_browse_response_rejects_missing_or_extra_provenance() -> None:
    from typing import Any, cast

    from mke.interfaces.source_schemas import BrowseSourceEvidenceResponseV1

    value = cast(dict[str, Any], browse_response())
    BrowseSourceEvidenceResponseV1.model_validate(value)
    del value["entries"][0]["evidence"]["run_id"]
    with pytest.raises(ValidationError):
        BrowseSourceEvidenceResponseV1.model_validate(value)
    value = cast(dict[str, Any], browse_response())
    value["entries"][0]["evidence"]["host_path"] = "/private/example"
    with pytest.raises(ValidationError):
        BrowseSourceEvidenceResponseV1.model_validate(value)
