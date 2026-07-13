from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from mke.evaluation.pdf_ocr_protocol import (
    PdfOcrProtocolError,
    load_pdf_ocr_evaluation_protocol,
)
from scripts.generate_pdf_ocr_phase0_fixtures import generate_fixture_tree

PROTOCOL = Path("tests/fixtures/pdf-ocr-phase0-v1/protocol.json")


def _snapshot_tree(root: Path) -> dict[str, tuple[int, str]]:
    return {
        path.relative_to(root).as_posix(): (
            path.stat().st_size,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _copy_corpus(tmp_path: Path) -> Path:
    target = tmp_path / "corpus"
    shutil.copytree(PROTOCOL.parent, target)
    return target / "protocol.json"


def _payload(path: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def _write_payload(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_protocol_has_exact_public_corpus_inventory() -> None:
    protocol = load_pdf_ocr_evaluation_protocol(PROTOCOL)

    assert protocol.schema == "mke.pdf_ocr_eval_protocol.v1"
    assert protocol.protocol_id == "pdf-ocr-phase0-v1"
    assert [item.document_id for item in protocol.documents] == [
        "english-scan",
        "chinese-scan",
        "mixed-prose",
        "routing-adversarial",
    ]
    assert protocol.providers == (
        "apple-vision-local-v1",
        "paddleocr-vl-1.6-cpu-spike-v1",
        "ppocrv6-medium-cpu-spike-v1",
    )
    assert [(item.query_id, item.expected_page) for item in protocol.queries] == [
        ("amber-seals", 1),
        ("haiyan-42", 1),
        ("orbit-731", 2),
    ]


def test_generator_is_byte_deterministic(tmp_path: Path) -> None:
    first = generate_fixture_tree(tmp_path / "first")
    second = generate_fixture_tree(tmp_path / "second")

    assert _snapshot_tree(first) == _snapshot_tree(second)
    assert _snapshot_tree(first) == _snapshot_tree(PROTOCOL.parent)


def test_protocol_truth_covers_expected_routes_and_text() -> None:
    protocol = load_pdf_ocr_evaluation_protocol(PROTOCOL)

    truth = {
        document.document_id: tuple(
            (page.page_number, page.expected_route, page.expected_ocr_text)
            for page in document.pages
        )
        for document in protocol.documents
    }
    assert truth["english-scan"] == (
        (1, "ocr_required", "Aurora station uses amber seals for verified cargo."),
    )
    assert truth["chinese-scan"] == ((1, "ocr_required", "巡检编号为海燕四十二号。"),)
    assert truth["mixed-prose"] == (
        (1, "text_layer_accepted", None),
        (2, "ocr_required", "Scanned appendix code is ORBIT-731."),
    )
    assert [route for _, route, _ in truth["routing-adversarial"]] == [
        "blank_nontext",
        "ambiguous_unsupported",
        "ambiguous_unsupported",
        "ambiguous_unsupported",
        "ocr_required",
    ]


def test_protocol_rejects_unknown_fields_and_checksum_drift(tmp_path: Path) -> None:
    protocol_path = _copy_corpus(tmp_path)
    payload = _payload(protocol_path)
    payload["unexpected"] = True
    _write_payload(protocol_path, payload)
    with pytest.raises(PdfOcrProtocolError) as unknown:
        load_pdf_ocr_evaluation_protocol(protocol_path)
    assert unknown.value.problem == "pdf_ocr_protocol_invalid"
    assert unknown.value.cause == "protocol contains unknown fields"
    assert unknown.value.next_step == "regenerate_pdf_ocr_protocol"
    assert str(tmp_path) not in str(unknown.value)

    protocol_path = _copy_corpus(tmp_path / "checksum")
    payload = _payload(protocol_path)
    documents = cast(list[dict[str, object]], payload["documents"])
    fixture = cast(dict[str, object], documents[0]["fixture"])
    fixture_path = protocol_path.parent / cast(str, fixture["path"])
    fixture_path.write_bytes(fixture_path.read_bytes() + b"\x00")
    with pytest.raises(PdfOcrProtocolError) as drift:
        load_pdf_ocr_evaluation_protocol(protocol_path)
    assert drift.value.cause == "fixture byte size does not match"
    assert drift.value.subject_id == "english-scan"


def _document_unknown(payload: dict[str, object]) -> None:
    cast(list[dict[str, object]], payload["documents"])[0]["unexpected"] = True


def _traversal_path(payload: dict[str, object]) -> None:
    document = cast(list[dict[str, object]], payload["documents"])[0]
    cast(dict[str, object], document["fixture"])["path"] = "../outside.pdf"


def _private_identifier(payload: dict[str, object]) -> None:
    cast(list[dict[str, object]], payload["documents"])[0]["document_id"] = (
        "/Users/private/document"
    )


def _noncontiguous_page(payload: dict[str, object]) -> None:
    document = cast(list[dict[str, object]], payload["documents"])[0]
    cast(list[dict[str, object]], document["pages"])[0]["page_number"] = 2


def _unknown_query_page(payload: dict[str, object]) -> None:
    query = cast(list[dict[str, object]], payload["queries"])[0]
    evidence_ref = cast(dict[str, object], query["expected_evidence_ref"])
    locator = cast(dict[str, object], evidence_ref["locator"])
    locator.update({"start": 99, "end": 99})


@pytest.mark.parametrize(
    ("mutation", "cause"),
    [
        (_document_unknown, "document contains unknown fields"),
        (_traversal_path, "fixture path is invalid"),
        (_private_identifier, "protocol contains private data"),
        (_noncontiguous_page, "document page numbers must be contiguous"),
        (_unknown_query_page, "query page locator is unknown"),
    ],
)
def test_protocol_rejects_closed_contract_violations(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], None],
    cause: str,
) -> None:
    protocol_path = _copy_corpus(tmp_path)
    payload = _payload(protocol_path)
    mutation(payload)
    _write_payload(protocol_path, payload)

    with pytest.raises(PdfOcrProtocolError) as error:
        load_pdf_ocr_evaluation_protocol(protocol_path)
    assert error.value.cause == cause


def test_protocol_rejects_symlink_fixture(tmp_path: Path) -> None:
    protocol_path = _copy_corpus(tmp_path)
    payload = _payload(protocol_path)
    documents = cast(list[dict[str, object]], payload["documents"])
    fixture = cast(dict[str, object], documents[0]["fixture"])
    fixture_path = protocol_path.parent / cast(str, fixture["path"])
    original = fixture_path.with_suffix(".original")
    fixture_path.rename(original)
    fixture_path.symlink_to(original.name)

    with pytest.raises(PdfOcrProtocolError) as error:
        load_pdf_ocr_evaluation_protocol(protocol_path)
    assert error.value.cause == "fixture file is not a regular file"
