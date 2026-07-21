import pytest

from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    PYMUPDF_TEXT_FINGERPRINT,
    REQUIRED_AUDIO_STAGES,
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
            tuple(sorted(REQUIRED_PDF_STAGES)) if required_stages is None else required_stages
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


def test_manifest_validation_accepts_exact_faster_whisper_fingerprint() -> None:
    manifest = _make_manifest(
        required_stages=tuple(sorted(REQUIRED_VIDEO_STAGES)),
        extractor_fingerprint="faster-whisper-v1:" + ("a" * 64),
    )
    evidence = [
        _make_evidence(
            locator_kind="timestamp_ms",
            locator_start=0,
            locator_end=1200,
        )
    ]

    validate_manifest(manifest, evidence)


def test_manifest_validation_accepts_exact_audio_fingerprint() -> None:
    manifest = _make_manifest(
        required_stages=tuple(sorted(REQUIRED_AUDIO_STAGES)),
        extractor_fingerprint="faster-whisper-audio-v1:" + ("a" * 64),
    )
    evidence = [_make_evidence(locator_kind="timestamp_ms", locator_start=0, locator_end=1_200)]

    validate_manifest(manifest, evidence)


@pytest.mark.parametrize(
    "fingerprint",
    [
        "faster-whisper-audio-v1:abc",
        "faster-whisper-audio-v1:" + ("A" * 64),
        "faster-whisper-audio-v2:" + ("a" * 64),
        "faster-whisper-v1:" + ("a" * 64),
    ],
)
def test_manifest_validation_rejects_wrong_audio_fingerprint(fingerprint: str) -> None:
    manifest = _make_manifest(
        required_stages=tuple(sorted(REQUIRED_AUDIO_STAGES)),
        extractor_fingerprint=fingerprint,
    )
    evidence = [_make_evidence(locator_kind="timestamp_ms", locator_start=0, locator_end=1)]

    with pytest.raises(ManifestValidationError):
        validate_manifest(manifest, evidence)


def test_manifest_validation_rejects_audio_fingerprint_with_video_stages() -> None:
    manifest = _make_manifest(
        required_stages=tuple(sorted(REQUIRED_VIDEO_STAGES)),
        extractor_fingerprint="faster-whisper-audio-v1:" + ("a" * 64),
    )
    evidence = [_make_evidence(locator_kind="timestamp_ms", locator_start=0, locator_end=1)]

    with pytest.raises(ManifestValidationError, match="required stages"):
        validate_manifest(manifest, evidence)


def test_manifest_validation_accepts_exact_pdf_ocr_evaluation_fingerprint() -> None:
    manifest = _make_manifest(
        required_stages=("candidate_evidence", "pdf_ocr_extraction"),
        extractor_fingerprint="pdf-ocr-eval-v1:" + ("a" * 64),
    )

    validate_manifest(manifest, [_make_evidence()])


@pytest.mark.parametrize(
    "fingerprint",
    [
        "pdf-ocr-eval-v1:",
        "pdf-ocr-eval-v1:" + ("a" * 63),
        "pdf-ocr-eval-v1:" + ("a" * 65),
        "pdf-ocr-eval-v1:" + ("A" * 64),
        "pdf-ocr-eval-v2:" + ("a" * 64),
    ],
)
def test_manifest_validation_rejects_invalid_pdf_ocr_evaluation_fingerprint(
    fingerprint: str,
) -> None:
    manifest = _make_manifest(
        required_stages=("candidate_evidence", "pdf_ocr_extraction"),
        extractor_fingerprint=fingerprint,
    )

    with pytest.raises(ManifestValidationError, match="fingerprint"):
        validate_manifest(manifest, [_make_evidence()])


@pytest.mark.parametrize(
    "required_stages",
    [tuple(sorted(REQUIRED_PDF_STAGES)), tuple(sorted(REQUIRED_VIDEO_STAGES))],
)
def test_manifest_validation_rejects_pdf_ocr_fingerprint_with_non_ocr_stages(
    required_stages: tuple[str, ...],
) -> None:
    manifest = _make_manifest(
        required_stages=required_stages,
        extractor_fingerprint="pdf-ocr-eval-v1:" + ("a" * 64),
    )

    with pytest.raises(ManifestValidationError, match="required stages"):
        validate_manifest(manifest, [_make_evidence()])


@pytest.mark.parametrize(
    "fingerprint",
    [
        PDF_EXTRACTOR_FINGERPRINT,
        PYMUPDF_TEXT_FINGERPRINT,
        VIDEO_TRANSCRIPT_FINGERPRINT,
    ],
)
def test_manifest_validation_rejects_non_ocr_fingerprint_with_ocr_stages(
    fingerprint: str,
) -> None:
    manifest = _make_manifest(
        required_stages=("candidate_evidence", "pdf_ocr_extraction"),
        extractor_fingerprint=fingerprint,
    )

    with pytest.raises(ManifestValidationError, match="required stages"):
        validate_manifest(manifest, [_make_evidence()])


def test_manifest_validation_rejects_duplicate_pdf_ocr_stages() -> None:
    manifest = _make_manifest(
        required_stages=(
            "candidate_evidence",
            "pdf_ocr_extraction",
            "candidate_evidence",
        ),
        extractor_fingerprint="pdf-ocr-eval-v1:" + ("a" * 64),
    )

    with pytest.raises(ManifestValidationError, match="required stages"):
        validate_manifest(manifest, [_make_evidence()])


def test_manifest_validation_rejects_non_page_pdf_ocr_locator() -> None:
    manifest = _make_manifest(
        required_stages=("candidate_evidence", "pdf_ocr_extraction"),
        extractor_fingerprint="pdf-ocr-eval-v1:" + ("a" * 64),
    )

    with pytest.raises(ManifestValidationError, match="locator kind"):
        validate_manifest(
            manifest,
            [_make_evidence(locator_kind="timestamp_ms", locator_start=0, locator_end=1)],
        )


@pytest.mark.parametrize(("start", "end"), [(0, 1), (2, 1)])
def test_manifest_validation_rejects_invalid_pdf_ocr_page_locator(
    start: int,
    end: int,
) -> None:
    manifest = _make_manifest(
        required_stages=("candidate_evidence", "pdf_ocr_extraction"),
        extractor_fingerprint="pdf-ocr-eval-v1:" + ("a" * 64),
    )

    with pytest.raises(ManifestValidationError, match="page locator"):
        validate_manifest(
            manifest,
            [_make_evidence(locator_start=start, locator_end=end)],
        )


def test_manifest_validation_rejects_faster_whisper_prefix_only() -> None:
    manifest = _make_manifest(
        required_stages=tuple(sorted(REQUIRED_VIDEO_STAGES)),
        extractor_fingerprint="faster-whisper-v1:",
    )
    evidence = [
        _make_evidence(
            locator_kind="timestamp_ms",
            locator_start=0,
            locator_end=1200,
        )
    ]

    with pytest.raises(ManifestValidationError, match="fingerprint"):
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
