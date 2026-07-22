"""Immutable domain contracts for a compiled local Library snapshot."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from . import (
    PDF_EXTRACTOR_FINGERPRINT,
    PYMUPDF_TEXT_FINGERPRINT,
    ActivePublicationObservation,
    CandidateEvidence,
    ManifestValidationError,
    RunManifest,
    is_recognized_audio_fingerprint,
    is_recognized_video_fingerprint,
    validate_manifest,
)

ExportFormatVersion = Literal["v1", "v2"]

_CONTENT_FINGERPRINT_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ID_PATTERNS = {
    "evidence": re.compile(r"ev_[0-9a-f]{32}\Z"),
    "source": re.compile(r"src_[0-9a-f]{32}\Z"),
    "publication": re.compile(r"pub_[0-9a-f]{32}\Z"),
    "run": re.compile(r"run_[0-9a-f]{32}\Z"),
}


@dataclass(frozen=True)
class ExportLimits:
    max_active_publications: int
    max_active_evidence: int
    max_evidence_utf8_bytes: int
    max_rendered_file_bytes: int

    def __post_init__(self) -> None:
        if any(type(value) is not int or value <= 0 for value in self.__dict__.values()):
            raise ValueError("export limits must be positive integers")


DEFAULT_EXPORT_LIMITS = ExportLimits(4096, 65536, 128 * 1024 * 1024, 64 * 1024 * 1024)


class LibraryExportDataError(ValueError):
    """Raised when domain truth cannot form a safe compiled Library snapshot."""

    def __init__(
        self,
        reason: Literal["empty", "provenance", "too_large", "unsupported_active_media_type"],
    ) -> None:
        super().__init__(f"compiled Library snapshot rejected: {reason}")
        self.reason = reason


def _reject_provenance() -> None:
    raise LibraryExportDataError("provenance")


def _valid_id(kind: str, value: object) -> bool:
    return type(value) is str and _ID_PATTERNS[kind].fullmatch(value) is not None


def _valid_content_fingerprint(value: object) -> bool:
    return type(value) is str and _CONTENT_FINGERPRINT_RE.fullmatch(value) is not None


@dataclass(frozen=True)
class CompiledEvidenceSnapshot:
    evidence_id: str
    source_id: str
    content_fingerprint: str
    publication_id: str
    publication_revision: int
    run_id: str
    locator_kind: Literal["page", "timestamp_ms"]
    locator_start: int
    locator_end: int
    text: str

    def __post_init__(self) -> None:
        valid_utf8 = False
        if type(self.text) is str:
            try:
                self.text.encode("utf-8", errors="strict")
            except UnicodeEncodeError:
                pass
            else:
                valid_utf8 = True
        identities = (
            _valid_id("evidence", self.evidence_id),
            _valid_id("source", self.source_id),
            _valid_id("publication", self.publication_id),
            _valid_id("run", self.run_id),
        )
        valid_text = (
            type(self.text) is str
            and bool(self.text.strip())
            and len(self.text) <= 1_000_000
            and valid_utf8
        )
        valid_revision = (
            type(self.publication_revision) is int and self.publication_revision > 0
        )
        if self.locator_kind == "page":
            valid_locator = (
                type(self.locator_start) is int
                and type(self.locator_end) is int
                and self.locator_start > 0
                and self.locator_end == self.locator_start
            )
        elif self.locator_kind == "timestamp_ms":
            valid_locator = (
                type(self.locator_start) is int
                and type(self.locator_end) is int
                and self.locator_start >= 0
                and self.locator_end > self.locator_start
            )
        else:
            valid_locator = False
        if not (
            all(identities)
            and _valid_content_fingerprint(self.content_fingerprint)
            and valid_revision
            and valid_locator
            and valid_text
        ):
            _reject_provenance()


def _evidence_sort_key(item: CompiledEvidenceSnapshot) -> tuple[str, int, int, str]:
    return (
        item.locator_kind,
        item.locator_start,
        item.locator_end,
        item.evidence_id,
    )


def _valid_display_name(value: object) -> bool:
    if type(value) is not str or not 1 <= len(value) <= 1024:
        return False
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        return False
    return not any(
        unicodedata.category(character).startswith("C")
        or character in {"\u2028", "\u2029"}
        for character in value
    )


@dataclass(frozen=True)
class CompiledSourceSnapshot:
    source_id: str
    display_name: str
    content_fingerprint: str
    media_type: Literal["application/pdf", "video/mp4"]
    publication_id: str
    publication_revision: int
    run_id: str
    extractor_fingerprint: str
    required_stages: tuple[str, ...]
    evidence: tuple[CompiledEvidenceSnapshot, ...]

    def __post_init__(self) -> None:
        valid_shape = (
            _valid_id("source", self.source_id)
            and _valid_display_name(self.display_name)
            and _valid_content_fingerprint(self.content_fingerprint)
            and self.media_type in {"application/pdf", "video/mp4"}
            and _valid_id("publication", self.publication_id)
            and type(self.publication_revision) is int
            and self.publication_revision > 0
            and _valid_id("run", self.run_id)
            and type(self.extractor_fingerprint) is str
            and bool(self.extractor_fingerprint)
            and type(self.required_stages) is tuple
            and all(type(stage) is str for stage in self.required_stages)
            and type(self.evidence) is tuple
            and bool(self.evidence)
            and all(type(item) is CompiledEvidenceSnapshot for item in self.evidence)
        )
        if not valid_shape:
            _reject_provenance()
        if self.required_stages != tuple(sorted(self.required_stages)):
            _reject_provenance()
        if self.evidence != tuple(sorted(self.evidence, key=_evidence_sort_key)):
            _reject_provenance()
        for item in self.evidence:
            if (
                item.source_id != self.source_id
                or item.content_fingerprint != self.content_fingerprint
                or item.publication_id != self.publication_id
                or item.publication_revision != self.publication_revision
                or item.run_id != self.run_id
            ):
                _reject_provenance()
        manifest = RunManifest(
            run_id=self.run_id,
            evidence_count=len(self.evidence),
            required_stages=self.required_stages,
            extractor_fingerprint=self.extractor_fingerprint,
            asset_sha256=self.content_fingerprint.removeprefix("sha256:"),
        )
        candidates = [
            CandidateEvidence(
                evidence_id=item.evidence_id,
                locator_kind=item.locator_kind,
                locator_start=item.locator_start,
                locator_end=item.locator_end,
                text=item.text,
            )
            for item in self.evidence
        ]
        try:
            validate_manifest(manifest, candidates)
        except ManifestValidationError as exc:
            raise LibraryExportDataError("provenance") from exc


@dataclass(frozen=True)
class CompiledSourceSnapshotV2:
    source_id: str
    display_name: str
    content_fingerprint: str
    media_type: Literal[
        "application/pdf",
        "video/mp4",
        "audio/mpeg",
        "audio/wav",
        "audio/mp4",
    ]
    publication_id: str
    publication_revision: int
    run_id: str
    extractor_fingerprint: str
    required_stages: tuple[str, ...]
    evidence: tuple[CompiledEvidenceSnapshot, ...]

    def __post_init__(self) -> None:
        valid_shape = (
            _valid_id("source", self.source_id)
            and _valid_display_name(self.display_name)
            and _valid_content_fingerprint(self.content_fingerprint)
            and self.media_type
            in {"application/pdf", "video/mp4", "audio/mpeg", "audio/wav", "audio/mp4"}
            and _valid_id("publication", self.publication_id)
            and type(self.publication_revision) is int
            and self.publication_revision > 0
            and _valid_id("run", self.run_id)
            and type(self.extractor_fingerprint) is str
            and bool(self.extractor_fingerprint)
            and type(self.required_stages) is tuple
            and all(type(stage) is str for stage in self.required_stages)
            and type(self.evidence) is tuple
            and bool(self.evidence)
            and all(type(item) is CompiledEvidenceSnapshot for item in self.evidence)
        )
        if not valid_shape:
            _reject_provenance()
        if self.required_stages != tuple(sorted(self.required_stages)):
            _reject_provenance()
        if self.evidence != tuple(sorted(self.evidence, key=_evidence_sort_key)):
            _reject_provenance()
        for item in self.evidence:
            if (
                item.source_id != self.source_id
                or item.content_fingerprint != self.content_fingerprint
                or item.publication_id != self.publication_id
                or item.publication_revision != self.publication_revision
                or item.run_id != self.run_id
            ):
                _reject_provenance()
        manifest = RunManifest(
            run_id=self.run_id,
            evidence_count=len(self.evidence),
            required_stages=self.required_stages,
            extractor_fingerprint=self.extractor_fingerprint,
            asset_sha256=self.content_fingerprint.removeprefix("sha256:"),
        )
        candidates = [
            CandidateEvidence(
                evidence_id=item.evidence_id,
                locator_kind=item.locator_kind,
                locator_start=item.locator_start,
                locator_end=item.locator_end,
                text=item.text,
            )
            for item in self.evidence
        ]
        try:
            validate_manifest(manifest, candidates)
        except ManifestValidationError as exc:
            raise LibraryExportDataError("provenance") from exc
        locator_kinds = {item.locator_kind for item in self.evidence}
        if self.media_type == "application/pdf":
            valid_authority = locator_kinds == {"page"} and (
                self.extractor_fingerprint
                in {PDF_EXTRACTOR_FINGERPRINT, PYMUPDF_TEXT_FINGERPRINT}
                or self.extractor_fingerprint.startswith("pdf-ocr-eval-v1:")
            )
        elif self.media_type == "video/mp4":
            valid_authority = locator_kinds == {"timestamp_ms"} and (
                is_recognized_video_fingerprint(self.extractor_fingerprint)
            )
        else:
            valid_authority = locator_kinds == {"timestamp_ms"} and (
                is_recognized_audio_fingerprint(self.extractor_fingerprint)
            )
        if not valid_authority:
            _reject_provenance()


@dataclass(frozen=True)
class CompiledLibrarySnapshot:
    observation: ActivePublicationObservation
    sources: tuple[CompiledSourceSnapshot, ...]

    def __post_init__(self) -> None:
        if type(self.observation) is not ActivePublicationObservation:
            _reject_provenance()
        if self.observation.state != "active":
            raise LibraryExportDataError("empty")
        if type(self.sources) is not tuple or not all(
            type(source) is CompiledSourceSnapshot for source in self.sources
        ):
            _reject_provenance()
        if self.sources != tuple(
            sorted(self.sources, key=lambda source: (source.content_fingerprint, source.source_id))
        ):
            _reject_provenance()
        fingerprints = tuple(source.content_fingerprint for source in self.sources)
        if len(fingerprints) != len(set(fingerprints)):
            _reject_provenance()
        evidence_count = sum(len(source.evidence) for source in self.sources)
        if (
            len(self.sources) != self.observation.active_publication_count
            or evidence_count != self.observation.active_evidence_count
        ):
            _reject_provenance()
        limits = DEFAULT_EXPORT_LIMITS
        if (
            len(self.sources) > limits.max_active_publications
            or evidence_count > limits.max_active_evidence
            or self.evidence_utf8_bytes > limits.max_evidence_utf8_bytes
        ):
            raise LibraryExportDataError("too_large")

    @property
    def evidence_utf8_bytes(self) -> int:
        return sum(
            len(item.text.encode("utf-8"))
            for source in self.sources
            for item in source.evidence
        )


@dataclass(frozen=True)
class CompiledLibrarySnapshotV2:
    observation: ActivePublicationObservation
    sources: tuple[CompiledSourceSnapshotV2, ...]

    def __post_init__(self) -> None:
        if type(self.observation) is not ActivePublicationObservation:
            _reject_provenance()
        if self.observation.state != "active":
            raise LibraryExportDataError("empty")
        if type(self.sources) is not tuple or not all(
            type(source) is CompiledSourceSnapshotV2 for source in self.sources
        ):
            _reject_provenance()
        if self.sources != tuple(
            sorted(self.sources, key=lambda source: (source.content_fingerprint, source.source_id))
        ):
            _reject_provenance()
        fingerprints = tuple(source.content_fingerprint for source in self.sources)
        if len(fingerprints) != len(set(fingerprints)):
            _reject_provenance()
        evidence_count = sum(len(source.evidence) for source in self.sources)
        if (
            len(self.sources) != self.observation.active_publication_count
            or evidence_count != self.observation.active_evidence_count
        ):
            _reject_provenance()
        limits = DEFAULT_EXPORT_LIMITS
        if (
            len(self.sources) > limits.max_active_publications
            or evidence_count > limits.max_active_evidence
            or self.evidence_utf8_bytes > limits.max_evidence_utf8_bytes
        ):
            raise LibraryExportDataError("too_large")

    @property
    def evidence_utf8_bytes(self) -> int:
        return sum(
            len(item.text.encode("utf-8"))
            for source in self.sources
            for item in source.evidence
        )
