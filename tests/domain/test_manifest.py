import pytest

from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    REQUIRED_VIDEO_STAGES,
    VIDEO_TRANSCRIPT_FINGERPRINT,
    CandidateEvidence,
    ManifestValidationError,
    RunManifest,
    validate_manifest,
)


def _make_evidence(
    evidence_id: str = "ev_1",
    locator_kind: str = "page",
    locator_start: int = 1,
    locator_end: int = 1,
    text: str = "Test evidence.",
) -> CandidateEvidence:
    return CandidateEvidence(
        evidence_id=evidence_id,
        locator_kind=locator_kind,
        locator_start=locator_start,
        locator_end=locator_end,
        text=text,
    )


def _make_manifest(
    run_id: str = "run_1",
    evidence_count: int = 1,
    required_stages: tuple[str, ...] | None = None,
    extractor_fingerprint: str | None = None,
    asset_sha256: str = "a" * 64,
) -> RunManifest:
    return RunManifest(
        run_id=run_id,
        evidence_count=evidence_count,
        required_stages=(
            tuple(sorted(REQUIRED_PDF_STAGES))
            if required_stages is None
            else required_stages
        ),
        extractor_fingerprint=(
            PDF_EXTRACTOR_FINGERPRINT if extractor_fingerprint is None else extractor_fingerprint
        ),
        asset_sha256=asset_sha256,
    )


def test_manifest_validation_accepts_complete_page_evidence() -> None:
    validate_manifest(_make_manifest(), [_make_evidence()])


def test_manifest_validation_accepts_timestamp_evidence() -> None:
    manifest = _make_manifest(
        required_stages=tuple(sorted(REQUIRED_VIDEO_STAGES)),
        extractor_fingerprint=VIDEO_TRANSCRIPT_FINGERPRINT,
    )
    evidence = [
        _make_evidence(
            locator_kind="timestamp_ms",
            locator_start=0,
            locator_end=1200,
            text="Video evidence has timestamp locators.",
        )
    ]

    validate_manifest(manifest, evidence)


def test_manifest_validation_rejects_count_mismatch() -> None:
    manifest = _make_manifest(evidence_count=2)
    with pytest.raises(ManifestValidationError, match="evidence count"):
        validate_manifest(manifest, [])


class TestRejectsInvalidManifest:
    def test_stages_incomplete(self) -> None:
        manifest = _make_manifest(required_stages=("pdf_text_extraction",))
        with pytest.raises(ManifestValidationError, match="required stages"):
            validate_manifest(manifest, [_make_evidence()])

    def test_fingerprint_unrecognized(self) -> None:
        manifest = _make_manifest(extractor_fingerprint="bad")
        with pytest.raises(ManifestValidationError, match="fingerprint"):
            validate_manifest(manifest, [_make_evidence()])

    def test_sha256_too_short(self) -> None:
        manifest = _make_manifest(asset_sha256="short")
        with pytest.raises(ManifestValidationError, match="sha256"):
            validate_manifest(manifest, [_make_evidence()])


class TestRejectsInvalidEvidence:
    def test_locator_kind_not_page(self) -> None:
        evidence = [_make_evidence(locator_kind="paragraph")]
        with pytest.raises(ManifestValidationError, match="locator kind"):
            validate_manifest(_make_manifest(), evidence)

    def test_locator_start_below_one(self) -> None:
        evidence = [_make_evidence(locator_start=0, locator_end=0)]
        with pytest.raises(ManifestValidationError, match="page locator"):
            validate_manifest(_make_manifest(), evidence)

    def test_locator_end_before_start(self) -> None:
        evidence = [_make_evidence(locator_start=3, locator_end=2)]
        with pytest.raises(ManifestValidationError, match="page locator"):
            validate_manifest(_make_manifest(), evidence)

    def test_text_empty(self) -> None:
        evidence = [_make_evidence(text="  ")]
        with pytest.raises(ManifestValidationError, match="must not be empty"):
            validate_manifest(_make_manifest(), evidence)

    def test_timestamp_end_must_be_after_start(self) -> None:
        manifest = _make_manifest(
            required_stages=tuple(sorted(REQUIRED_VIDEO_STAGES)),
            extractor_fingerprint=VIDEO_TRANSCRIPT_FINGERPRINT,
        )
        evidence = [
            _make_evidence(locator_kind="timestamp_ms", locator_start=1000, locator_end=1000)
        ]

        with pytest.raises(ManifestValidationError, match="timestamp locator"):
            validate_manifest(manifest, evidence)


def test_search_result_page_number_raises_for_timestamp_result() -> None:
    from mke.domain import SearchResult

    result = SearchResult(
        evidence_id="ev_t",
        publication_id="pub_t",
        source_id="src_t",
        locator_kind="timestamp_ms",
        locator_start=0,
        locator_end=1200,
        text="Test",
    )

    with pytest.raises(ValueError, match="does not contain page Evidence"):
        _ = result.page_number


def test_locator_label_fallback_for_unknown_kind() -> None:
    from mke.adapters.sqlite import _locator_label  # pyright: ignore[reportPrivateUsage]

    assert _locator_label("paragraph", 3, 5) == "paragraph:3..5"
