"""Closed protocol for the disposable PDF OCR Phase 0 evaluation."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal, NoReturn, cast

import fitz  # pyright: ignore[reportMissingTypeStubs]

PageRoute = Literal[
    "text_layer_accepted",
    "ocr_required",
    "blank_nontext",
    "ambiguous_unsupported",
]

_ROUTES = frozenset(
    {
        "text_layer_accepted",
        "ocr_required",
        "blank_nontext",
        "ambiguous_unsupported",
    }
)
_PROVIDERS = (
    "apple-vision-local-v1",
    "paddleocr-vl-1.6-cpu-spike-v1",
    "ppocrv6-medium-cpu-spike-v1",
)
_ID_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_PRIVATE_RE = re.compile(
    r"(?:/Users/|[A-Za-z]:\\|Traceback|API[_-]?KEY|TOKEN=|SECRET=|PASSWORD=|"
    r"BEGIN [A-Z ]*PRIVATE KEY)",
    flags=re.IGNORECASE,
)


class PdfOcrProtocolError(ValueError):
    """A stable, path-free Phase 0 corpus validation failure."""

    def __init__(
        self,
        *,
        problem: str = "pdf_ocr_protocol_invalid",
        cause: str,
        next_step: str = "regenerate_pdf_ocr_protocol",
        subject_id: str | None = None,
    ) -> None:
        super().__init__(f"{problem}: {cause}")
        self.problem = problem
        self.cause = cause
        self.next_step = next_step
        self.subject_id = subject_id


@dataclass(frozen=True)
class FixtureIdentity:
    path: PurePosixPath
    bytes: int
    sha256: str


@dataclass(frozen=True)
class ExpectedPage:
    page_number: int
    expected_route: PageRoute
    expected_text_layer_text: str | None
    expected_ocr_text: str | None


@dataclass(frozen=True)
class ExpectedQuery:
    query_id: str
    text: str
    expected_document_id: str
    expected_page: int


@dataclass(frozen=True)
class EvaluationDocument:
    document_id: str
    fixture: FixtureIdentity
    pages: tuple[ExpectedPage, ...]


@dataclass(frozen=True)
class PdfOcrEvaluationProtocol:
    schema: Literal["mke.pdf_ocr_eval_protocol.v1"]
    protocol_id: str
    root: Path
    providers: tuple[str, ...]
    documents: tuple[EvaluationDocument, ...]
    queries: tuple[ExpectedQuery, ...]

    def resolve(self, fixture: FixtureIdentity) -> Path:
        return self.root.joinpath(*fixture.path.parts)


def load_pdf_ocr_evaluation_protocol(path: Path) -> PdfOcrEvaluationProtocol:
    payload = _load_json(path)
    _require_keys(
        payload,
        {"schema", "protocol_id", "providers", "documents", "queries"},
        "protocol",
    )
    if payload["schema"] != "mke.pdf_ocr_eval_protocol.v1":
        _fail("protocol schema is unsupported")
    protocol_id = _identifier(payload["protocol_id"], "protocol identifier is invalid")
    if protocol_id != "pdf-ocr-phase0-v1":
        _fail("protocol identifier is invalid")
    providers = tuple(_provider(item) for item in _list(payload["providers"], "providers"))
    if providers != _PROVIDERS:
        _fail("provider inventory is invalid")
    documents = tuple(_document(item) for item in _list(payload["documents"], "documents"))
    queries = tuple(_query(item) for item in _list(payload["queries"], "queries"))
    _require_unique((item.document_id for item in documents), "document identifiers must be unique")
    _require_unique((item.query_id for item in queries), "query identifiers must be unique")
    _require_unique((str(item.fixture.path) for item in documents), "fixture paths must be unique")
    root = path.resolve().parent
    protocol = PdfOcrEvaluationProtocol(
        schema="mke.pdf_ocr_eval_protocol.v1",
        protocol_id=protocol_id,
        root=root,
        providers=providers,
        documents=documents,
        queries=queries,
    )
    page_inventory = _validate_fixtures(protocol)
    for query in queries:
        pages = page_inventory.get(query.expected_document_id)
        if pages is None:
            _fail("query document identifier is unknown", subject_id=query.query_id)
        if query.expected_page not in pages:
            _fail("query page locator is unknown", subject_id=query.query_id)
        page = documents_by_id(protocol)[query.expected_document_id].pages[query.expected_page - 1]
        if page.expected_route in {"blank_nontext", "ambiguous_unsupported"}:
            _fail("query page is not publishable", subject_id=query.query_id)
    return protocol


def documents_by_id(protocol: PdfOcrEvaluationProtocol) -> dict[str, EvaluationDocument]:
    return {item.document_id: item for item in protocol.documents}


def _load_json(path: Path) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise PdfOcrProtocolError(cause="protocol file is missing") from error
    except OSError as error:
        raise PdfOcrProtocolError(cause="protocol file is not readable") from error
    except (UnicodeError, json.JSONDecodeError) as error:
        raise PdfOcrProtocolError(cause="protocol is not valid JSON") from error
    if not isinstance(raw, dict):
        _fail("protocol must be an object")
    payload = cast(dict[str, object], raw)
    _reject_private(payload)
    return payload


def _document(value: object) -> EvaluationDocument:
    payload = _object(value, "document")
    _require_keys(payload, {"document_id", "fixture", "pages"}, "document")
    document_id = _identifier(payload["document_id"], "document identifier is invalid")
    fixture = _fixture(payload["fixture"])
    pages = tuple(_page(item, document_id) for item in _list(payload["pages"], "pages"))
    if not pages or tuple(item.page_number for item in pages) != tuple(range(1, len(pages) + 1)):
        _fail("document page numbers must be contiguous", subject_id=document_id)
    return EvaluationDocument(document_id=document_id, fixture=fixture, pages=pages)


def _fixture(value: object) -> FixtureIdentity:
    payload = _object(value, "fixture")
    _require_keys(payload, {"path", "bytes", "sha256"}, "fixture")
    raw_path = payload["path"]
    if not isinstance(raw_path, str):
        _fail("fixture path is invalid")
    relative = PurePosixPath(raw_path)
    if (
        not raw_path
        or relative.is_absolute()
        or "\\" in raw_path
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        _fail("fixture path is invalid")
    byte_size = payload["bytes"]
    if isinstance(byte_size, bool) or not isinstance(byte_size, int) or byte_size <= 0:
        _fail("fixture byte size is invalid")
    digest = payload["sha256"]
    if not isinstance(digest, str) or _SHA256_RE.fullmatch(digest) is None:
        _fail("fixture checksum is invalid")
    return FixtureIdentity(path=relative, bytes=byte_size, sha256=digest)


def _page(value: object, document_id: str) -> ExpectedPage:
    payload = _object(value, "page")
    _require_keys(
        payload,
        {"page_number", "expected_route", "expected_text_layer_text", "expected_ocr_text"},
        "page",
    )
    page_number = payload["page_number"]
    if isinstance(page_number, bool) or not isinstance(page_number, int) or page_number <= 0:
        _fail("page number is invalid", subject_id=document_id)
    raw_route = payload["expected_route"]
    if raw_route not in _ROUTES:
        _fail("page route is invalid", subject_id=document_id)
    route = cast(PageRoute, raw_route)
    text_layer = _optional_text(payload["expected_text_layer_text"], "text-layer truth")
    ocr_text = _optional_text(payload["expected_ocr_text"], "OCR truth")
    if route == "text_layer_accepted" and (text_layer is None or ocr_text is not None):
        _fail("text-layer page truth is invalid", subject_id=document_id)
    if route == "ocr_required" and (ocr_text is None or text_layer is not None):
        _fail("OCR page truth is invalid", subject_id=document_id)
    if route in {"blank_nontext", "ambiguous_unsupported"} and (
        text_layer is not None or ocr_text is not None
    ):
        _fail("non-publishable page truth is invalid", subject_id=document_id)
    return ExpectedPage(page_number, route, text_layer, ocr_text)


def _query(value: object) -> ExpectedQuery:
    payload = _object(value, "query")
    _require_keys(
        payload,
        {"query_id", "text", "expected_document_id", "expected_evidence_ref"},
        "query",
    )
    query_id = _identifier(payload["query_id"], "query identifier is invalid")
    text = _text(payload["text"], "query text is invalid")
    document_id = _identifier(
        payload["expected_document_id"], "query document identifier is invalid"
    )
    evidence_ref = _object(payload["expected_evidence_ref"], "expected EvidenceRef")
    _require_keys(evidence_ref, {"schema_version", "locator"}, "expected EvidenceRef")
    if evidence_ref["schema_version"] != "mke.evidence_ref.v1":
        _fail("query EvidenceRef schema is invalid", subject_id=query_id)
    locator = _object(evidence_ref["locator"], "query locator")
    _require_keys(locator, {"kind", "start", "end"}, "query locator")
    start = locator["start"]
    end = locator["end"]
    if (
        locator["kind"] != "page"
        or isinstance(start, bool)
        or not isinstance(start, int)
        or start <= 0
        or end != start
    ):
        _fail("query page locator is invalid", subject_id=query_id)
    return ExpectedQuery(query_id, text, document_id, start)


def _validate_fixtures(protocol: PdfOcrEvaluationProtocol) -> dict[str, frozenset[int]]:
    inventory: dict[str, frozenset[int]] = {}
    for document in protocol.documents:
        path = protocol.resolve(document.fixture)
        try:
            if path.is_symlink() or not path.is_file():
                _fail("fixture file is not a regular file", subject_id=document.document_id)
            data = path.read_bytes()
        except OSError as error:
            raise PdfOcrProtocolError(
                cause="fixture file is not readable", subject_id=document.document_id
            ) from error
        if len(data) != document.fixture.bytes:
            _fail("fixture byte size does not match", subject_id=document.document_id)
        if hashlib.sha256(data).hexdigest() != document.fixture.sha256:
            _fail("fixture checksum does not match", subject_id=document.document_id)
        try:
            pdf: Any = fitz.open(stream=data, filetype="pdf")
        except Exception as error:
            raise PdfOcrProtocolError(
                cause="fixture PDF is invalid", subject_id=document.document_id
            ) from error
        try:
            if pdf.needs_pass:
                _fail("fixture PDF is encrypted", subject_id=document.document_id)
            if pdf.page_count != len(document.pages):
                _fail("fixture page count does not match", subject_id=document.document_id)
        finally:
            pdf.close()
        inventory[document.document_id] = frozenset(
            page.page_number for page in document.pages
        )
    return inventory


def _reject_private(value: object) -> None:
    if isinstance(value, str):
        if _PRIVATE_RE.search(value):
            _fail("protocol contains private data")
        return
    if isinstance(value, list):
        for item in cast(list[object], value):
            _reject_private(item)
    elif isinstance(value, dict):
        for key, item in cast(dict[object, object], value).items():
            _reject_private(key)
            _reject_private(item)


def _require_keys(payload: dict[str, object], expected: set[str], subject: str) -> None:
    actual = set(payload)
    if actual - expected:
        _fail(f"{subject} contains unknown fields")
    if expected - actual:
        _fail(f"{subject} is missing required fields")


def _object(value: object, subject: str) -> dict[str, object]:
    if not isinstance(value, dict):
        _fail(f"{subject} must be an object")
    return cast(dict[str, object], value)


def _list(value: object, subject: str) -> list[object]:
    if not isinstance(value, list):
        _fail(f"{subject} must be a list")
    return cast(list[object], value)


def _identifier(value: object, cause: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 128 or _ID_RE.fullmatch(value) is None:
        _fail(cause)
    return value


def _provider(value: object) -> str:
    if not isinstance(value, str) or value not in _PROVIDERS:
        _fail("provider identifier is invalid")
    return value


def _text(value: object, cause: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 10_000:
        _fail(cause)
    return value


def _optional_text(value: object, subject: str) -> str | None:
    if value is None:
        return None
    return _text(value, f"{subject} is invalid")


def _require_unique(values: Iterable[str], cause: str) -> None:
    materialized = tuple(values)
    if len(materialized) != len(set(materialized)):
        _fail(cause)


def _fail(cause: str, *, subject_id: str | None = None) -> NoReturn:
    raise PdfOcrProtocolError(cause=cause, subject_id=subject_id)
