import pytest

from mke.domain import (
    CandidateEvidence,
    ManifestValidationError,
    RunManifest,
    validate_manifest,
)


def test_manifest_validation_accepts_complete_page_evidence() -> None:
    evidence = [
        CandidateEvidence(
            evidence_id="ev_1",
            locator_kind="page",
            locator_start=1,
            locator_end=1,
            text="Trustworthy evidence starts on page one.",
        )
    ]
    manifest = RunManifest(
        run_id="run_1",
        evidence_count=1,
        required_stages=("pdf_text_extraction", "candidate_evidence"),
        extractor_fingerprint="builtin-pdf-text-v1",
        asset_sha256="a" * 64,
    )

    validate_manifest(manifest, evidence)


def test_manifest_validation_rejects_count_mismatch() -> None:
    manifest = RunManifest(
        run_id="run_1",
        evidence_count=2,
        required_stages=("pdf_text_extraction", "candidate_evidence"),
        extractor_fingerprint="builtin-pdf-text-v1",
        asset_sha256="a" * 64,
    )

    with pytest.raises(ManifestValidationError, match="evidence count"):
        validate_manifest(manifest, [])


def test_manifest_validation_rejects_invalid_page_locator() -> None:
    evidence = [
        CandidateEvidence(
            evidence_id="ev_1",
            locator_kind="page",
            locator_start=0,
            locator_end=0,
            text="invalid locator",
        )
    ]
    manifest = RunManifest(
        run_id="run_1",
        evidence_count=1,
        required_stages=("pdf_text_extraction", "candidate_evidence"),
        extractor_fingerprint="builtin-pdf-text-v1",
        asset_sha256="a" * 64,
    )

    with pytest.raises(ManifestValidationError, match="page locator"):
        validate_manifest(manifest, evidence)
