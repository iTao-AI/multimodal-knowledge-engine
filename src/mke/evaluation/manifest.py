from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Literal, cast

QueryCategory = Literal["answerable", "lexical_confuser", "out_of_corpus"]
LocatorKind = Literal["page", "timestamp_ms"]
MediaType = Literal["application/pdf", "video/mp4"]
_ID_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_SEARCHABLE_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
_MAX_DECLARED_FIXTURE_BYTES = 100 * 1024 * 1024


class ManifestValidationError(ValueError):
    def __init__(self, cause: str, *, subject_id: str | None = None) -> None:
        super().__init__(cause)
        self.cause = cause
        self.subject_id = subject_id


class FixtureValidationError(ManifestValidationError):
    """A valid manifest references missing, unreadable, or mismatched fixture bytes."""


@dataclass(frozen=True)
class FixtureFile:
    path: PurePosixPath
    sha256: str
    bytes: int
    role: str | None = None


@dataclass(frozen=True)
class EvaluationDocument:
    document_id: str
    media_type: MediaType
    primary_file: FixtureFile
    supporting_files: tuple[FixtureFile, ...]


@dataclass(frozen=True, order=True)
class StableLocator:
    document_id: str
    locator_kind: LocatorKind
    locator_start: int
    locator_end: int


@dataclass(frozen=True)
class EvaluationQuery:
    query_id: str
    text: str
    category: QueryCategory
    relevant_locators: tuple[StableLocator, ...]


@dataclass(frozen=True)
class RetrievalEvaluationManifest:
    schema_version: str
    manifest_id: str
    root: Path
    documents: tuple[EvaluationDocument, ...]
    queries: tuple[EvaluationQuery, ...]

    def resolve(self, fixture: FixtureFile) -> Path:
        resolved = (self.root / Path(*fixture.path.parts)).resolve()
        if not resolved.is_relative_to(self.root):
            raise ManifestValidationError("fixture path is invalid")
        return resolved


def load_retrieval_manifest(path: Path) -> RetrievalEvaluationManifest:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ManifestValidationError("manifest file is missing") from error
    except OSError as error:
        raise ManifestValidationError("manifest file is not readable") from error
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ManifestValidationError("manifest is not valid JSON") from error
    if not isinstance(raw, dict):
        raise ManifestValidationError("manifest must be a JSON object")
    payload = cast(dict[str, object], raw)
    _require_keys(payload, {"schema_version", "manifest_id", "documents", "queries"}, "manifest")
    if payload["schema_version"] != "mke.retrieval_eval.v1":
        raise ManifestValidationError("manifest schema version is unsupported")
    manifest_id = _identifier(payload["manifest_id"], "manifest identifier is invalid")
    documents = tuple(_document(item) for item in _list(payload["documents"], "documents"))
    queries = tuple(_query(item) for item in _list(payload["queries"], "queries"))
    _require_manifest_bounds(documents, queries)
    _unique((item.document_id for item in documents), "document identifiers must be unique")
    _unique((item.query_id for item in queries), "query identifiers must be unique")
    _unique(
        (str(item.primary_file.path) for item in documents),
        "primary fixture paths must be unique",
    )
    _unique(
        (item.primary_file.sha256 for item in documents),
        "primary fixture checksums must be unique",
    )
    document_ids = {item.document_id for item in documents}
    for query in queries:
        for locator in query.relevant_locators:
            if locator.document_id not in document_ids:
                raise ManifestValidationError(
                    "qrel document identifier is unknown", subject_id=query.query_id
                )
    manifest = RetrievalEvaluationManifest(
        schema_version="mke.retrieval_eval.v1",
        manifest_id=manifest_id,
        root=path.resolve().parent,
        documents=documents,
        queries=queries,
    )
    _validate_fixture_files(manifest)
    return manifest


def snapshot_retrieval_fixtures(
    manifest: RetrievalEvaluationManifest,
    destination: Path,
) -> RetrievalEvaluationManifest:
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    staged = replace(manifest, root=destination)
    for document in manifest.documents:
        for fixture in (document.primary_file, *document.supporting_files):
            source = manifest.resolve(fixture)
            target = staged.resolve(fixture)
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            copied_bytes = 0
            try:
                with source.open("rb") as source_file, target.open("xb") as target_file:
                    while chunk := source_file.read(1024 * 1024):
                        target_file.write(chunk)
                        digest.update(chunk)
                        copied_bytes += len(chunk)
            except OSError as error:
                raise FixtureValidationError(
                    "fixture file is not readable", subject_id=document.document_id
                ) from error
            if copied_bytes != fixture.bytes:
                raise FixtureValidationError(
                    "fixture byte size does not match", subject_id=document.document_id
                )
            if digest.hexdigest() != fixture.sha256:
                raise FixtureValidationError(
                    "fixture checksum does not match", subject_id=document.document_id
                )
    _validate_fixture_files(staged)
    return staged


def _require_keys(payload: dict[str, object], expected: set[str], subject: str) -> None:
    actual = set(payload)
    if actual - expected:
        raise ManifestValidationError(f"{subject} contains unknown fields")
    if expected - actual:
        raise ManifestValidationError(f"{subject} is missing required fields")


def _list(value: object, subject: str) -> list[object]:
    if not isinstance(value, list):
        raise ManifestValidationError(f"{subject} must be a list")
    return cast(list[object], value)


def _object(value: object, subject: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ManifestValidationError(f"{subject} must be an object")
    return cast(dict[str, object], value)


def _identifier(value: object, cause: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 128 or not _ID_RE.fullmatch(value):
        raise ManifestValidationError(cause)
    return value


def _fixture_file(value: object, *, supporting: bool) -> FixtureFile:
    payload = _object(value, "fixture file")
    expected = (
        {"path", "sha256", "bytes", "role"}
        if supporting
        else {"path", "sha256", "bytes"}
    )
    _require_keys(payload, expected, "fixture file")
    raw_path = payload["path"]
    if not isinstance(raw_path, str):
        raise ManifestValidationError("fixture path is invalid")
    path = PurePosixPath(raw_path)
    if (
        not raw_path
        or path.is_absolute()
        or "\\" in raw_path
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ManifestValidationError("fixture path is invalid")
    sha256 = payload["sha256"]
    if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
        raise ManifestValidationError("fixture checksum is invalid")
    byte_size = payload["bytes"]
    if isinstance(byte_size, bool) or not isinstance(byte_size, int) or byte_size <= 0:
        raise ManifestValidationError("fixture byte size is invalid")
    role = None
    if supporting:
        role = _identifier(payload["role"], "supporting-file role is invalid")
    return FixtureFile(path=path, sha256=sha256, bytes=byte_size, role=role)


def _document(value: object) -> EvaluationDocument:
    payload = _object(value, "document")
    _require_keys(
        payload,
        {"document_id", "media_type", "primary_file", "supporting_files"},
        "document",
    )
    document_id = _identifier(payload["document_id"], "document identifier is invalid")
    raw_media_type = payload["media_type"]
    if raw_media_type not in {"application/pdf", "video/mp4"}:
        raise ManifestValidationError("document media type is invalid", subject_id=document_id)
    media_type = cast(MediaType, raw_media_type)
    primary = _fixture_file(payload["primary_file"], supporting=False)
    supporting = tuple(
        _fixture_file(item, supporting=True)
        for item in _list(payload["supporting_files"], "supporting files")
    )
    if media_type == "application/pdf" and supporting:
        raise ManifestValidationError(
            "PDF documents must not have supporting files", subject_id=document_id
        )
    if media_type == "video/mp4":
        if len(supporting) != 1 or supporting[0].role != "transcript_sidecar":
            raise ManifestValidationError(
                "video document requires one transcript sidecar", subject_id=document_id
            )
        expected_sidecar = PurePosixPath(f"{primary.path}.mke-transcript.json")
        if supporting[0].path != expected_sidecar:
            raise ManifestValidationError(
                "video transcript sidecar path is invalid", subject_id=document_id
            )
    return EvaluationDocument(document_id, media_type, primary, supporting)


def _query(value: object) -> EvaluationQuery:
    payload = _object(value, "query")
    _require_keys(payload, {"query_id", "text", "category", "relevant_locators"}, "query")
    query_id = _identifier(payload["query_id"], "query identifier is invalid")
    text = payload["text"]
    if (
        not isinstance(text, str)
        or not 1 <= len(text.strip()) <= 1000
        or not _SEARCHABLE_TOKEN_RE.search(text)
    ):
        raise ManifestValidationError("query text is invalid", subject_id=query_id)
    raw_category = payload["category"]
    if raw_category not in {"answerable", "lexical_confuser", "out_of_corpus"}:
        raise ManifestValidationError("query category is invalid", subject_id=query_id)
    category = cast(QueryCategory, raw_category)
    locators = tuple(
        _locator(item) for item in _list(payload["relevant_locators"], "relevant locators")
    )
    _unique(locators, "query relevant locators must be unique")
    if category == "answerable" and not locators:
        raise ManifestValidationError(
            "answerable query requires relevant locators", subject_id=query_id
        )
    if category != "answerable" and locators:
        raise ManifestValidationError(
            "unanswerable query must not have relevant locators", subject_id=query_id
        )
    return EvaluationQuery(query_id, text.strip(), category, locators)


def _locator(value: object) -> StableLocator:
    payload = _object(value, "qrel")
    _require_keys(
        payload,
        {"document_id", "locator_kind", "locator_start", "locator_end"},
        "qrel",
    )
    document_id = _identifier(payload["document_id"], "qrel document identifier is invalid")
    raw_kind = payload["locator_kind"]
    if raw_kind not in {"page", "timestamp_ms"}:
        raise ManifestValidationError("locator kind is invalid")
    kind = cast(LocatorKind, raw_kind)
    start = payload["locator_start"]
    end = payload["locator_end"]
    if (
        isinstance(start, bool)
        or isinstance(end, bool)
        or not isinstance(start, int)
        or not isinstance(end, int)
    ):
        label = "page" if kind == "page" else "timestamp"
        raise ManifestValidationError(f"{label} locator is invalid")
    if kind == "page" and (start <= 0 or end != start):
        raise ManifestValidationError("page locator is invalid")
    if kind == "timestamp_ms" and (start < 0 or end <= start):
        raise ManifestValidationError("timestamp locator is invalid")
    return StableLocator(document_id, kind, start, end)


def _unique(values: Iterable[object], cause: str) -> None:
    seen: set[object] = set()
    for value in values:
        if value in seen:
            raise ManifestValidationError(cause)
        seen.add(value)


def _require_manifest_bounds(
    documents: tuple[EvaluationDocument, ...],
    queries: tuple[EvaluationQuery, ...],
) -> None:
    if not 1 <= len(documents) <= 32:
        raise ManifestValidationError("manifest document count is invalid")
    if not 2 <= len(queries) <= 1000:
        raise ManifestValidationError("manifest query count is invalid")
    if not any(item.category == "answerable" for item in queries) or not any(
        item.category != "answerable" for item in queries
    ):
        raise ManifestValidationError("manifest requires answerable and unanswerable queries")
    declared_bytes = sum(
        fixture.bytes
        for document in documents
        for fixture in (document.primary_file, *document.supporting_files)
    )
    if declared_bytes > _MAX_DECLARED_FIXTURE_BYTES:
        raise ManifestValidationError("manifest declared fixture size is invalid")


def _validate_fixture_files(manifest: RetrievalEvaluationManifest) -> None:
    for document in manifest.documents:
        for fixture in (document.primary_file, *document.supporting_files):
            try:
                path = manifest.resolve(fixture)
                stat = path.stat()
            except ManifestValidationError:
                raise
            except FileNotFoundError as error:
                raise FixtureValidationError(
                    "fixture file is missing", subject_id=document.document_id
                ) from error
            except OSError as error:
                raise FixtureValidationError(
                    "fixture file is not readable", subject_id=document.document_id
                ) from error
            if not path.is_file():
                raise FixtureValidationError(
                    "fixture file is not readable", subject_id=document.document_id
                )
            if stat.st_size != fixture.bytes:
                raise FixtureValidationError(
                    "fixture byte size does not match", subject_id=document.document_id
                )
            try:
                digest = _sha256(path)
            except OSError as error:
                raise FixtureValidationError(
                    "fixture file is not readable", subject_id=document.document_id
                ) from error
            if digest != fixture.sha256:
                raise FixtureValidationError(
                    "fixture checksum does not match", subject_id=document.document_id
                )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
