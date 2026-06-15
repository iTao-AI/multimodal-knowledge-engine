"""Application service for the narrow PR 2 PDF ingest and Search path."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from mke.adapters.pdf import PdfExtractionError, extract_text_pages
from mke.adapters.sqlite import SQLiteStore
from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    ActivationResult,
    CandidateEvidence,
    IngestResult,
    RunManifest,
    RunRecord,
    SearchResult,
    SourceRecord,
)


class PdfIngestError(ValueError):
    """Raised when the PDF happy path cannot produce publishable Evidence."""


class KnowledgeEngine:
    """Project-owned application facade shared by CLI and future interfaces."""

    def __init__(self, db_path: Path) -> None:
        self._store = SQLiteStore(db_path)

    def close(self) -> None:
        self._store.close()

    def ensure_source(self, display_name: str, asset_sha256: str) -> SourceRecord:
        return self._store.ensure_source(display_name, asset_sha256)

    def create_run(self, source_id: str) -> RunRecord:
        return self._store.create_run(source_id)

    def get_run(self, run_id: str) -> RunRecord:
        return self._store.get_run(run_id)

    def persist_validated_candidate(
        self, run_id: str, evidence: list[CandidateEvidence], manifest: RunManifest
    ) -> None:
        self._store.persist_validated_candidate(run_id, evidence, manifest)

    def activate_publication(self, run_id: str) -> ActivationResult:
        return self._store.activate_publication(run_id)

    def search(self, query: str) -> list[SearchResult]:
        return self._store.search(query)

    def ingest_pdf(self, path: Path) -> IngestResult:
        asset_sha256 = _sha256_file(path)
        source = self.ensure_source(display_name=path.name, asset_sha256=asset_sha256)
        run = self.create_run(source.source_id)
        try:
            pages = extract_text_pages(path)
            evidence = [
                CandidateEvidence(
                    evidence_id=f"ev_{uuid4().hex}",
                    locator_kind="page",
                    locator_start=page.page_number,
                    locator_end=page.page_number,
                    text=page.text,
                )
                for page in pages
            ]
            manifest = RunManifest(
                run_id=run.run_id,
                evidence_count=len(evidence),
                required_stages=tuple(sorted(REQUIRED_PDF_STAGES)),
                extractor_fingerprint=PDF_EXTRACTOR_FINGERPRINT,
                asset_sha256=asset_sha256,
            )
            self.persist_validated_candidate(run.run_id, evidence, manifest)
            activation = self.activate_publication(run.run_id)
            return IngestResult(
                run_id=run.run_id,
                run_state=activation.run_state,
                evidence_count=len(evidence) if activation.published else 0,
            )
        except PdfExtractionError as error:
            self._store.mark_run_failed(run.run_id)
            raise PdfIngestError(str(error)) from error


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
