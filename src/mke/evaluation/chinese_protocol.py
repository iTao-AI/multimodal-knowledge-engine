from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Literal, cast

import fitz  # pyright: ignore[reportMissingTypeStubs]

from mke.evaluation.manifest import FixtureFile, StableLocator

ChineseSplit = Literal["development", "holdout"]
ChineseQueryCategory = Literal[
    "chinese_exact_lexical",
    "chinese_word_boundary",
    "proper_noun_mixed",
    "number_date_unit",
    "semantic_paraphrase",
    "multi_condition",
    "ranking_hard_negative",
    "unanswerable",
]
QrelGrade = Literal[0, 1, 2]

EXPECTED_SPLIT_COUNTS: Mapping[ChineseSplit, int] = {
    "development": 24,
    "holdout": 24,
}
EXPECTED_CATEGORY_COUNTS: Mapping[ChineseQueryCategory, int] = {
    "chinese_exact_lexical": 8,
    "chinese_word_boundary": 6,
    "proper_noun_mixed": 6,
    "number_date_unit": 6,
    "semantic_paraphrase": 8,
    "multi_condition": 6,
    "ranking_hard_negative": 4,
    "unanswerable": 4,
}

_ID_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_DECISION_UNSAFE_RE = re.compile(
    r"(?:/Users/|[A-Za-z]:\\|Traceback|Exception|API[_-]?KEY|TOKEN=|SECRET=|"
    r"PASSWORD=|BEGIN [A-Z ]*PRIVATE KEY)",
    flags=re.IGNORECASE,
)
_CATEGORIES = frozenset(EXPECTED_CATEGORY_COUNTS)
_SPLITS = frozenset(EXPECTED_SPLIT_COUNTS)


class ChineseProtocolValidationError(ValueError):
    def __init__(self, cause: str, *, subject_id: str | None = None) -> None:
        super().__init__(cause)
        self.cause = cause
        self.subject_id = subject_id


@dataclass(frozen=True)
class ChineseEvaluationDocument:
    document_id: str
    split: ChineseSplit
    media_type: Literal["application/pdf"]
    primary_file: FixtureFile


@dataclass(frozen=True, order=True)
class GradedQrel:
    locator: StableLocator
    grade: QrelGrade


@dataclass(frozen=True)
class ChineseEvaluationQuery:
    query_id: str
    split: ChineseSplit
    category: ChineseQueryCategory
    text: str
    qrels: tuple[GradedQrel, ...]


@dataclass(frozen=True)
class QrelAdjudication:
    path: Path
    sha256: str
    review_status: Literal["complete"]
    reviewed_query_count: int
    query_page_judgment_count: int


@dataclass(frozen=True)
class ChineseRetrievalProtocol:
    schema_version: str
    protocol_id: str
    rank_probe_query_id: str
    root: Path
    documents: tuple[ChineseEvaluationDocument, ...]
    queries: tuple[ChineseEvaluationQuery, ...]
    qrel_adjudication: QrelAdjudication

    def resolve(self, fixture: FixtureFile) -> Path:
        return _resolve_relative_file(self.root, fixture.path)


def load_chinese_retrieval_protocol(path: Path) -> ChineseRetrievalProtocol:
    payload = _load_json(path, "protocol")
    _require_keys(
        payload,
        {
            "schema_version",
            "protocol_id",
            "rank_probe_query_id",
            "qrel_adjudication",
            "documents",
            "queries",
        },
        "protocol",
    )
    if payload["schema_version"] != "mke.retrieval_chinese_protocol.v1":
        raise ChineseProtocolValidationError("protocol schema version is unsupported")
    protocol_id = _identifier(
        payload["protocol_id"], "protocol identifier is invalid"
    )
    if protocol_id != "retrieval-chinese-v1":
        raise ChineseProtocolValidationError("protocol identifier is invalid")
    root = path.resolve().parent
    documents = tuple(_document(item) for item in _list(payload["documents"], "documents"))
    queries = tuple(_query(item) for item in _list(payload["queries"], "queries"))
    rank_probe_query_id = _identifier(
        payload["rank_probe_query_id"], "rank probe query identifier is invalid"
    )
    _validate_protocol_inventory(documents, queries, rank_probe_query_id)
    protocol = ChineseRetrievalProtocol(
        schema_version="mke.retrieval_chinese_protocol.v1",
        protocol_id=protocol_id,
        rank_probe_query_id=rank_probe_query_id,
        root=root,
        documents=documents,
        queries=queries,
        qrel_adjudication=_adjudication_record(root, payload["qrel_adjudication"]),
    )
    page_counts = _validate_fixture_files(protocol)
    _validate_qrel_locators(protocol, page_counts)
    adjudication = _validate_adjudication(protocol, page_counts)
    return replace(protocol, qrel_adjudication=adjudication)


def snapshot_chinese_retrieval_fixtures(
    protocol: ChineseRetrievalProtocol,
    destination: Path,
) -> ChineseRetrievalProtocol:
    destination = destination.resolve()
    try:
        destination.mkdir(parents=True, exist_ok=False)
    except FileExistsError as error:
        raise ChineseProtocolValidationError("snapshot target exists") from error
    except OSError as error:
        raise ChineseProtocolValidationError("snapshot target is not writable") from error
    staged = replace(protocol, root=destination)
    try:
        for document in protocol.documents:
            source = protocol.resolve(document.primary_file)
            target = staged.resolve(document.primary_file)
            target.parent.mkdir(parents=True, exist_ok=True)
            before = source.stat()
            digest = hashlib.sha256()
            copied_bytes = 0
            try:
                with source.open("rb") as source_file, target.open("xb") as target_file:
                    while chunk := source_file.read(1024 * 1024):
                        target_file.write(chunk)
                        digest.update(chunk)
                        copied_bytes += len(chunk)
                    target_file.flush()
            except FileExistsError as error:
                raise ChineseProtocolValidationError("snapshot target exists") from error
            except OSError as error:
                raise ChineseProtocolValidationError(
                    "fixture file is not readable", subject_id=document.document_id
                ) from error
            after = source.stat()
            if (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
            ) != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
            ):
                raise ChineseProtocolValidationError(
                    "fixture changed during snapshot", subject_id=document.document_id
                )
            if copied_bytes != document.primary_file.bytes:
                raise ChineseProtocolValidationError(
                    "fixture byte size does not match", subject_id=document.document_id
                )
            if digest.hexdigest() != document.primary_file.sha256:
                raise ChineseProtocolValidationError(
                    "fixture checksum does not match", subject_id=document.document_id
                )
        _validate_fixture_files(staged)
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return staged


def _load_json(path: Path, subject: str) -> dict[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ChineseProtocolValidationError(f"{subject} file is missing") from error
    except OSError as error:
        raise ChineseProtocolValidationError(f"{subject} file is not readable") from error
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ChineseProtocolValidationError(f"{subject} is not valid JSON") from error
    if not isinstance(raw, dict):
        raise ChineseProtocolValidationError(f"{subject} must be a JSON object")
    return cast(dict[str, object], raw)


def _require_keys(
    payload: dict[str, object], expected: set[str], subject: str
) -> None:
    actual = set(payload)
    if actual - expected:
        raise ChineseProtocolValidationError(f"{subject} contains unknown fields")
    if expected - actual:
        raise ChineseProtocolValidationError(f"{subject} is missing required fields")


def _object(value: object, subject: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ChineseProtocolValidationError(f"{subject} must be an object")
    return cast(dict[str, object], value)


def _list(value: object, subject: str) -> list[object]:
    if not isinstance(value, list):
        raise ChineseProtocolValidationError(f"{subject} must be a list")
    return cast(list[object], value)


def _identifier(value: object, cause: str) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 128
        or not _ID_RE.fullmatch(value)
    ):
        raise ChineseProtocolValidationError(cause)
    return value


def _split(value: object, subject: str) -> ChineseSplit:
    if value not in _SPLITS:
        raise ChineseProtocolValidationError(f"{subject} split is invalid")
    return value


def _fixture_file(value: object) -> FixtureFile:
    payload = _object(value, "fixture file")
    _require_keys(payload, {"path", "sha256", "bytes"}, "fixture file")
    raw_path = payload["path"]
    if not isinstance(raw_path, str):
        raise ChineseProtocolValidationError("fixture path is invalid")
    path = PurePosixPath(raw_path)
    if (
        not raw_path
        or path.is_absolute()
        or "\\" in raw_path
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ChineseProtocolValidationError("fixture path is invalid")
    sha256 = payload["sha256"]
    if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
        raise ChineseProtocolValidationError("fixture checksum is invalid")
    byte_size = payload["bytes"]
    if (
        isinstance(byte_size, bool)
        or not isinstance(byte_size, int)
        or byte_size <= 0
    ):
        raise ChineseProtocolValidationError("fixture byte size is invalid")
    return FixtureFile(path=path, sha256=sha256, bytes=byte_size)


def _document(value: object) -> ChineseEvaluationDocument:
    payload = _object(value, "document")
    _require_keys(
        payload,
        {
            "document_id",
            "split",
            "media_type",
            "primary_file",
            "supporting_files",
        },
        "document",
    )
    document_id = _identifier(
        payload["document_id"], "document identifier is invalid"
    )
    split = _split(payload["split"], "document")
    if payload["media_type"] != "application/pdf":
        raise ChineseProtocolValidationError(
            "document media type is invalid", subject_id=document_id
        )
    if _list(payload["supporting_files"], "supporting files"):
        raise ChineseProtocolValidationError(
            "Chinese evaluation documents must not have supporting files",
            subject_id=document_id,
        )
    return ChineseEvaluationDocument(
        document_id=document_id,
        split=split,
        media_type="application/pdf",
        primary_file=_fixture_file(payload["primary_file"]),
    )


def _query(value: object) -> ChineseEvaluationQuery:
    payload = _object(value, "query")
    _require_keys(
        payload, {"query_id", "split", "category", "text", "qrels"}, "query"
    )
    query_id = _identifier(payload["query_id"], "query identifier is invalid")
    split = _split(payload["split"], "query")
    raw_category = payload["category"]
    if raw_category not in _CATEGORIES:
        raise ChineseProtocolValidationError(
            "query category is invalid", subject_id=query_id
        )
    category = raw_category
    text = payload["text"]
    if (
        not isinstance(text, str)
        or not 1 <= len(text.strip()) <= 1000
        or not any(character.isalnum() for character in text)
    ):
        raise ChineseProtocolValidationError(
            "query text is invalid", subject_id=query_id
        )
    qrels = tuple(_qrel(item) for item in _list(payload["qrels"], "qrels"))
    _unique(
        (item.locator for item in qrels),
        "query qrel locators must be unique",
        subject_id=query_id,
    )
    if category == "unanswerable":
        if qrels:
            raise ChineseProtocolValidationError(
                "unanswerable query must not have qrels", subject_id=query_id
            )
    elif not any(item.grade == 2 for item in qrels):
        raise ChineseProtocolValidationError(
            "answerable query requires grade 2", subject_id=query_id
        )
    if category == "ranking_hard_negative" and not any(
        item.grade == 0 for item in qrels
    ):
        raise ChineseProtocolValidationError(
            "hard-negative query requires grade 0", subject_id=query_id
        )
    return ChineseEvaluationQuery(
        query_id=query_id,
        split=split,
        category=category,
        text=text.strip(),
        qrels=qrels,
    )


def _qrel(value: object) -> GradedQrel:
    payload = _object(value, "qrel")
    _require_keys(
        payload,
        {
            "document_id",
            "locator_kind",
            "locator_start",
            "locator_end",
            "grade",
        },
        "qrel",
    )
    document_id = _identifier(
        payload["document_id"], "qrel document identifier is invalid"
    )
    if payload["locator_kind"] != "page":
        raise ChineseProtocolValidationError("qrel locator kind is invalid")
    start = payload["locator_start"]
    end = payload["locator_end"]
    if (
        isinstance(start, bool)
        or isinstance(end, bool)
        or not isinstance(start, int)
        or not isinstance(end, int)
        or start <= 0
        or end != start
    ):
        raise ChineseProtocolValidationError("qrel page locator is invalid")
    grade = payload["grade"]
    if (
        isinstance(grade, bool)
        or not isinstance(grade, int)
        or grade not in {0, 1, 2}
    ):
        raise ChineseProtocolValidationError("qrel grade is invalid")
    return GradedQrel(
        locator=StableLocator(document_id, "page", start, end),
        grade=cast(QrelGrade, grade),
    )


def _adjudication_record(root: Path, value: object) -> QrelAdjudication:
    payload = _object(value, "qrel adjudication")
    _require_keys(payload, {"path", "sha256"}, "qrel adjudication")
    raw_path = payload["path"]
    if not isinstance(raw_path, str):
        raise ChineseProtocolValidationError("qrel adjudication path is invalid")
    relative = PurePosixPath(raw_path)
    if (
        not raw_path
        or relative.is_absolute()
        or "\\" in raw_path
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise ChineseProtocolValidationError("qrel adjudication path is invalid")
    sha256 = payload["sha256"]
    if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
        raise ChineseProtocolValidationError("qrel adjudication checksum is invalid")
    adjudication_path = _resolve_relative_file(root, relative)
    try:
        observed = _sha256(adjudication_path)
    except FileNotFoundError as error:
        raise ChineseProtocolValidationError(
            "qrel adjudication file is missing"
        ) from error
    except OSError as error:
        raise ChineseProtocolValidationError(
            "qrel adjudication file is not readable"
        ) from error
    if observed != sha256:
        raise ChineseProtocolValidationError(
            "qrel adjudication checksum does not match"
        )
    return QrelAdjudication(
        path=adjudication_path,
        sha256=sha256,
        review_status="complete",
        reviewed_query_count=0,
        query_page_judgment_count=0,
    )


def _validate_protocol_inventory(
    documents: tuple[ChineseEvaluationDocument, ...],
    queries: tuple[ChineseEvaluationQuery, ...],
    rank_probe_query_id: str,
) -> None:
    if len(documents) != 5:
        raise ChineseProtocolValidationError("document count is invalid")
    if len(queries) != 48:
        raise ChineseProtocolValidationError("query count is invalid")
    _unique(
        (item.document_id for item in documents),
        "document identifiers must be unique",
    )
    _unique((item.query_id for item in queries), "query identifiers must be unique")
    _unique(
        (item.text for item in queries),
        "query text must be unique",
    )
    _unique(
        (str(item.primary_file.path) for item in documents),
        "fixture paths must be unique",
    )
    _unique(
        (item.primary_file.sha256 for item in documents),
        "fixture checksums must be unique",
    )
    if Counter(item.split for item in queries) != Counter(EXPECTED_SPLIT_COUNTS):
        raise ChineseProtocolValidationError("query split counts are invalid")
    if Counter(item.category for item in queries) != Counter(EXPECTED_CATEGORY_COUNTS):
        raise ChineseProtocolValidationError("query category counts are invalid")
    documents_by_id = {item.document_id: item for item in documents}
    for query in queries:
        for qrel in query.qrels:
            document = documents_by_id.get(qrel.locator.document_id)
            if document is None:
                raise ChineseProtocolValidationError(
                    "qrel document identifier is unknown", subject_id=query.query_id
                )
            if document.split != query.split:
                raise ChineseProtocolValidationError(
                    "qrel split does not match query", subject_id=query.query_id
                )
    rank_probe = next(
        (item for item in queries if item.query_id == rank_probe_query_id), None
    )
    if rank_probe is None or rank_probe.split != "development":
        raise ChineseProtocolValidationError("rank probe query is invalid")


def _validate_fixture_files(
    protocol: ChineseRetrievalProtocol,
) -> dict[str, int]:
    page_counts: dict[str, int] = {}
    for document in protocol.documents:
        path = protocol.resolve(document.primary_file)
        try:
            stat = path.stat()
        except FileNotFoundError as error:
            raise ChineseProtocolValidationError(
                "fixture file is missing", subject_id=document.document_id
            ) from error
        except OSError as error:
            raise ChineseProtocolValidationError(
                "fixture file is not readable", subject_id=document.document_id
            ) from error
        if not path.is_file() or path.is_symlink():
            raise ChineseProtocolValidationError(
                "fixture path is invalid", subject_id=document.document_id
            )
        if stat.st_size != document.primary_file.bytes:
            raise ChineseProtocolValidationError(
                "fixture byte size does not match", subject_id=document.document_id
            )
        try:
            observed_sha256 = _sha256(path)
        except OSError as error:
            raise ChineseProtocolValidationError(
                "fixture file is not readable", subject_id=document.document_id
            ) from error
        if observed_sha256 != document.primary_file.sha256:
            raise ChineseProtocolValidationError(
                "fixture checksum does not match", subject_id=document.document_id
            )
        try:
            with fitz.open(path) as pdf:
                count = len(pdf)
        except Exception as error:
            raise ChineseProtocolValidationError(
                "fixture PDF is invalid", subject_id=document.document_id
            ) from error
        if count <= 0:
            raise ChineseProtocolValidationError(
                "fixture PDF is invalid", subject_id=document.document_id
            )
        page_counts[document.document_id] = count
    return page_counts


def _validate_qrel_locators(
    protocol: ChineseRetrievalProtocol, page_counts: Mapping[str, int]
) -> None:
    for query in protocol.queries:
        for qrel in query.qrels:
            if qrel.locator.locator_start > page_counts[qrel.locator.document_id]:
                raise ChineseProtocolValidationError(
                    "qrel page locator is invalid", subject_id=query.query_id
                )


def _validate_adjudication(
    protocol: ChineseRetrievalProtocol,
    page_counts: Mapping[str, int],
) -> QrelAdjudication:
    payload = _load_json(protocol.qrel_adjudication.path, "qrel adjudication")
    _require_keys(
        payload,
        {
            "schema_version",
            "protocol_id",
            "method",
            "review_date",
            "review_status",
            "document_page_counts",
            "query_page_judgment_count",
            "queries",
        },
        "qrel adjudication",
    )
    if (
        payload["schema_version"]
        != "mke.retrieval_chinese_qrel_adjudication.v1"
        or payload["protocol_id"] != protocol.protocol_id
        or payload["method"] != "complete_partition_page_review"
    ):
        raise ChineseProtocolValidationError("qrel adjudication identity is invalid")
    if payload["review_status"] != "complete":
        raise ChineseProtocolValidationError("qrel review status is invalid")
    declared_counts = _object(
        payload["document_page_counts"], "document page counts"
    )
    if set(declared_counts) != set(page_counts):
        raise ChineseProtocolValidationError("qrel review page coverage is invalid")
    for document_id, count in page_counts.items():
        declared = declared_counts[document_id]
        if (
            isinstance(declared, bool)
            or not isinstance(declared, int)
            or declared != count
        ):
            raise ChineseProtocolValidationError(
                "qrel review page coverage is invalid"
            )
    reviewed = _list(payload["queries"], "reviewed queries")
    if len(reviewed) != len(protocol.queries):
        raise ChineseProtocolValidationError("qrel review query coverage is invalid")
    total = 0
    documents_by_split = {
        split: tuple(
            item.document_id for item in protocol.documents if item.split == split
        )
        for split in cast(tuple[ChineseSplit, ChineseSplit], ("development", "holdout"))
    }
    for query, raw_review in zip(protocol.queries, reviewed, strict=True):
        review = _object(raw_review, "reviewed query")
        _require_keys(
            review, {"query_id", "split", "decision_basis", "judgments"}, "reviewed query"
        )
        if review["query_id"] != query.query_id or review["split"] != query.split:
            raise ChineseProtocolValidationError(
                "qrel review query coverage is invalid", subject_id=query.query_id
            )
        _validate_decision_basis(review["decision_basis"], query.query_id)
        expected_inventory = tuple(
            (document_id, page)
            for document_id in documents_by_split[query.split]
            for page in range(1, page_counts[document_id] + 1)
        )
        raw_judgments = _list(review["judgments"], "judgments")
        if len(raw_judgments) != len(expected_inventory):
            raise ChineseProtocolValidationError(
                "qrel review page coverage is invalid", subject_id=query.query_id
            )
        observed_inventory: list[tuple[str, int]] = []
        derived_qrels: list[GradedQrel] = []
        for raw_judgment in raw_judgments:
            judgment = _object(raw_judgment, "judgment")
            _require_keys(
                judgment,
                {
                    "document_id",
                    "locator_kind",
                    "locator_start",
                    "locator_end",
                    "grade",
                },
                "judgment",
            )
            document_id = _identifier(
                judgment["document_id"], "judgment document identifier is invalid"
            )
            start = judgment["locator_start"]
            end = judgment["locator_end"]
            if (
                judgment["locator_kind"] != "page"
                or isinstance(start, bool)
                or isinstance(end, bool)
                or not isinstance(start, int)
                or not isinstance(end, int)
                or start <= 0
                or end != start
            ):
                raise ChineseProtocolValidationError(
                    "qrel review page coverage is invalid", subject_id=query.query_id
                )
            observed_inventory.append((document_id, start))
            grade = judgment["grade"]
            if grade == "non_relevant":
                continue
            if (
                isinstance(grade, bool)
                or not isinstance(grade, int)
                or grade not in {0, 1, 2}
            ):
                raise ChineseProtocolValidationError(
                    "qrel review grade is invalid", subject_id=query.query_id
                )
            derived_qrels.append(
                GradedQrel(
                    locator=StableLocator(document_id, "page", start, end),
                    grade=cast(QrelGrade, grade),
                )
            )
        if tuple(observed_inventory) != expected_inventory:
            if set(observed_inventory) == set(expected_inventory):
                cause = "qrel review page order is invalid"
            else:
                cause = "qrel review page coverage is invalid"
            raise ChineseProtocolValidationError(cause, subject_id=query.query_id)
        if tuple(derived_qrels) != query.qrels:
            raise ChineseProtocolValidationError(
                "qrel review does not match protocol qrels", subject_id=query.query_id
            )
        total += len(raw_judgments)
    declared_total = payload["query_page_judgment_count"]
    if (
        isinstance(declared_total, bool)
        or not isinstance(declared_total, int)
        or declared_total != total
        or total != 1680
    ):
        raise ChineseProtocolValidationError("qrel review judgment count is invalid")
    return replace(
        protocol.qrel_adjudication,
        review_status="complete",
        reviewed_query_count=len(reviewed),
        query_page_judgment_count=total,
    )


def _validate_decision_basis(value: object, query_id: str) -> None:
    if not isinstance(value, str) or not 1 <= len(value) <= 500:
        raise ChineseProtocolValidationError(
            "decision basis is invalid", subject_id=query_id
        )
    if (
        any(ord(character) < 32 and character not in {"\t"} for character in value)
        or _DECISION_UNSAFE_RE.search(value)
    ):
        raise ChineseProtocolValidationError(
            "decision basis is not public-safe", subject_id=query_id
        )


def _resolve_relative_file(root: Path, relative: PurePosixPath) -> Path:
    candidate = root / Path(*relative.parts)
    try:
        for parent in (root, *candidate.parents):
            if parent == root.parent:
                break
            if parent.exists() and parent.is_symlink():
                raise ChineseProtocolValidationError("fixture path is invalid")
        resolved = candidate.resolve(strict=False)
    except OSError as error:
        raise ChineseProtocolValidationError("fixture path is invalid") from error
    if not resolved.is_relative_to(root.resolve()):
        raise ChineseProtocolValidationError("fixture path is invalid")
    return resolved


def _unique(
    values: Iterable[object], cause: str, *, subject_id: str | None = None
) -> None:
    seen: set[object] = set()
    for value in values:
        if value in seen:
            raise ChineseProtocolValidationError(cause, subject_id=subject_id)
        seen.add(value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
