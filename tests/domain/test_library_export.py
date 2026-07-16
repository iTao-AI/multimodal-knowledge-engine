from dataclasses import FrozenInstanceError, replace

import pytest

import mke.domain.library_export as library_export
from mke.domain import ActivePublicationObservation
from mke.domain.library_export import (
    DEFAULT_EXPORT_LIMITS,
    CompiledEvidenceSnapshot,
    CompiledLibrarySnapshot,
    CompiledSourceSnapshot,
    ExportLimits,
    LibraryExportDataError,
)


def evidence_snapshot(
    *,
    suffix: str = "1",
    source_suffix: str = "a",
    publication_suffix: str = "b",
    run_suffix: str = "c",
    digest: str = "a" * 64,
    kind: str = "page",
    start: int = 1,
    end: int = 1,
    text: str = "page text",
) -> CompiledEvidenceSnapshot:
    return CompiledEvidenceSnapshot(
        evidence_id="ev_" + suffix * 32,
        source_id="src_" + source_suffix * 32,
        content_fingerprint="sha256:" + digest,
        publication_id="pub_" + publication_suffix * 32,
        publication_revision=1,
        run_id="run_" + run_suffix * 32,
        locator_kind=kind,  # type: ignore[arg-type]
        locator_start=start,
        locator_end=end,
        text=text,
    )


def source_snapshot(
    *,
    source_suffix: str = "a",
    publication_suffix: str = "b",
    run_suffix: str = "c",
    digest: str = "a" * 64,
    kind: str = "page",
    start: int = 1,
    end: int = 1,
    text: str | None = None,
    evidence: tuple[CompiledEvidenceSnapshot, ...] | None = None,
) -> CompiledSourceSnapshot:
    media_type = "application/pdf" if kind == "page" else "video/mp4"
    extractor = "pymupdf-text-v1" if kind == "page" else "builtin-video-transcript-v1"
    stages = (
        ("candidate_evidence", "pdf_text_extraction")
        if kind == "page"
        else ("candidate_evidence", "video_transcription")
    )
    if evidence is None:
        evidence = (
            evidence_snapshot(
                source_suffix=source_suffix,
                publication_suffix=publication_suffix,
                run_suffix=run_suffix,
                digest=digest,
                kind=kind,
                start=start,
                end=end,
                text=text or ("page text" if kind == "page" else "timestamp text"),
            ),
        )
    return CompiledSourceSnapshot(
        source_id="src_" + source_suffix * 32,
        display_name="fixture.pdf" if kind == "page" else "fixture.mp4",
        content_fingerprint="sha256:" + digest,
        media_type=media_type,  # type: ignore[arg-type]
        publication_id="pub_" + publication_suffix * 32,
        publication_revision=1,
        run_id="run_" + run_suffix * 32,
        extractor_fingerprint=extractor,
        required_stages=stages,
        evidence=evidence,
    )


def active_snapshot(*sources: CompiledSourceSnapshot) -> CompiledLibrarySnapshot:
    observation = ActivePublicationObservation(
        "local",
        "active",
        len(sources),
        len(sources),
        sum(len(source.evidence) for source in sources),
    )
    return CompiledLibrarySnapshot(observation, sources)


def assert_reason(reason: str, factory: object) -> None:
    with pytest.raises(LibraryExportDataError) as exc_info:
        factory()  # type: ignore[operator]
    assert exc_info.value.reason == reason


def test_compiled_library_snapshot_accepts_page_and_timestamp_sources() -> None:
    page = source_snapshot(kind="page", start=1, end=1, digest="a" * 64)
    timestamp = source_snapshot(
        source_suffix="d",
        publication_suffix="e",
        run_suffix="f",
        kind="timestamp_ms",
        start=0,
        end=1200,
        digest="b" * 64,
    )
    observation = ActivePublicationObservation("local", "active", 2, 2, 2)

    snapshot = CompiledLibrarySnapshot(observation, (page, timestamp))

    assert tuple(item.content_fingerprint for item in snapshot.sources) == (
        "sha256:" + "a" * 64,
        "sha256:" + "b" * 64,
    )
    assert snapshot.evidence_utf8_bytes == len(b"page text") + len(b"timestamp text")
    assert len(snapshot.sources) == snapshot.observation.active_publication_count
    assert sum(len(source.evidence) for source in snapshot.sources) == 2
    assert DEFAULT_EXPORT_LIMITS == ExportLimits(4096, 65536, 134217728, 67108864)

    with pytest.raises(FrozenInstanceError):
        snapshot.sources = ()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        page.display_name = "changed"  # type: ignore[misc]


def test_snapshot_counts_utf8_bytes_and_allows_inactive_source_rows() -> None:
    source = source_snapshot(text="证据")
    observation = ActivePublicationObservation("local", "active", 2, 1, 1)

    snapshot = CompiledLibrarySnapshot(observation, (source,))

    assert snapshot.evidence_utf8_bytes == len("证据".encode())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_id", "source_" + "a" * 32),
        ("source_id", "src_" + "a" * 31),
        ("source_id", "src_" + "A" * 32),
        ("publication_id", "publication_" + "b" * 32),
        ("publication_id", "pub_" + "b" * 33),
        ("publication_id", "pub_" + "B" * 32),
        ("run_id", "job_" + "c" * 32),
        ("run_id", "run_" + "c" * 31),
        ("run_id", "run_" + "C" * 32),
    ],
)
def test_source_rejects_invalid_identity(field: str, value: str) -> None:
    source = source_snapshot()
    assert_reason("provenance", lambda: replace(source, **{field: value}))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_id", "evidence_" + "1" * 32),
        ("evidence_id", "ev_" + "1" * 31),
        ("evidence_id", "ev_" + "A" * 32),
        ("source_id", "src_" + "a" * 31),
        ("publication_id", "pub_" + "B" * 32),
        ("run_id", "run_" + "c" * 33),
    ],
)
def test_evidence_rejects_invalid_identity(field: str, value: str) -> None:
    evidence = evidence_snapshot()
    assert_reason("provenance", lambda: replace(evidence, **{field: value}))


@pytest.mark.parametrize(
    "fingerprint",
    ["sha256:" + "A" * 64, "sha256:" + "a" * 63, "md5:" + "a" * 64],
)
def test_snapshots_reject_invalid_content_fingerprint(fingerprint: str) -> None:
    assert_reason(
        "provenance",
        lambda: replace(source_snapshot(), content_fingerprint=fingerprint),
    )
    assert_reason(
        "provenance",
        lambda: replace(evidence_snapshot(), content_fingerprint=fingerprint),
    )


@pytest.mark.parametrize(
    "display_name",
    ["", "x" * 1025, "line\nbreak", "delete\x7f", "line\u2028break", "para\u2029break"],
)
def test_source_rejects_invalid_display_name_without_echoing_it(display_name: str) -> None:
    with pytest.raises(LibraryExportDataError) as exc_info:
        replace(source_snapshot(), display_name=display_name)
    assert exc_info.value.reason == "provenance"
    if display_name:
        assert display_name not in str(exc_info.value)


def test_source_rejects_unsupported_media_type_and_revision() -> None:
    source = source_snapshot()
    assert_reason(
        "provenance",
        lambda: replace(source, media_type="text/plain"),  # type: ignore[arg-type]
    )
    for revision in (0, -1, True):
        assert_reason(
            "provenance", lambda revision=revision: replace(source, publication_revision=revision)
        )


@pytest.mark.parametrize("text", ["", " \t\n", "x" * 1_000_001])
def test_evidence_rejects_blank_or_overlong_text(text: str) -> None:
    assert_reason("provenance", lambda: replace(evidence_snapshot(), text=text))


def test_evidence_rejects_text_that_is_not_strict_utf8_without_echoing_it() -> None:
    text = "\ud800"

    with pytest.raises(LibraryExportDataError) as exc_info:
        evidence_snapshot(text=text)

    assert exc_info.value.reason == "provenance"
    assert text not in str(exc_info.value)


@pytest.mark.parametrize(
    ("kind", "start", "end"),
    [
        ("page", 0, 0),
        ("page", 1, 2),
        ("timestamp_ms", -1, 1),
        ("timestamp_ms", 1, 1),
        ("other", 1, 2),
    ],
)
def test_evidence_rejects_invalid_locator(kind: str, start: int, end: int) -> None:
    assert_reason(
        "provenance",
        lambda: replace(
            evidence_snapshot(),
            locator_kind=kind,  # type: ignore[arg-type]
            locator_start=start,
            locator_end=end,
        ),
    )


def test_source_reuses_manifest_authority_for_extractor_stages_and_duplicates() -> None:
    source = source_snapshot()
    assert_reason(
        "provenance",
        lambda: replace(source, extractor_fingerprint="builtin-video-transcript-v1"),
    )
    assert_reason(
        "provenance",
        lambda: replace(source, required_stages=("candidate_evidence",)),
    )
    assert_reason(
        "provenance",
        lambda: replace(
            source,
            required_stages=(
                "candidate_evidence",
                "pdf_text_extraction",
                "candidate_evidence",
            ),
        ),
    )


def test_source_rejects_unsorted_evidence_and_cross_source_identity_drift() -> None:
    second = evidence_snapshot(suffix="2", start=2, end=2, text="second")
    first = evidence_snapshot(suffix="1", start=1, end=1, text="first")
    assert_reason(
        "provenance",
        lambda: source_snapshot(evidence=(second, first)),
    )
    for field, value in (
        ("source_id", "src_" + "d" * 32),
        ("content_fingerprint", "sha256:" + "d" * 64),
        ("publication_id", "pub_" + "d" * 32),
        ("publication_revision", 2),
        ("run_id", "run_" + "d" * 32),
    ):
        drift = replace(first, **{field: value})
        assert_reason("provenance", lambda drift=drift: source_snapshot(evidence=(drift,)))


def test_library_rejects_duplicate_fingerprint_and_unsorted_sources() -> None:
    first = source_snapshot(digest="a" * 64)
    duplicate = source_snapshot(
        source_suffix="d", publication_suffix="e", run_suffix="f", digest="a" * 64
    )
    second = source_snapshot(
        source_suffix="d", publication_suffix="e", run_suffix="f", digest="b" * 64
    )
    assert_reason("provenance", lambda: active_snapshot(first, duplicate))
    assert_reason("provenance", lambda: active_snapshot(second, first))


def test_library_rejects_observation_count_drift() -> None:
    source = source_snapshot()
    observations = (
        ActivePublicationObservation("local", "active", 2, 1, 2),
        ActivePublicationObservation("local", "active", 2, 2, 2),
    )
    for observation in observations:
        assert_reason(
            "provenance",
            lambda observation=observation: CompiledLibrarySnapshot(observation, (source,)),
        )


@pytest.mark.parametrize(
    "observation",
    [
        ActivePublicationObservation("local", "empty", 0, 0, 0),
        ActivePublicationObservation("local", "no_active_publication", 1, 0, 0),
    ],
)
def test_library_rejects_without_active_publications(
    observation: ActivePublicationObservation,
) -> None:
    assert_reason("empty", lambda: CompiledLibrarySnapshot(observation, ()))


def test_library_rejects_each_snapshot_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    first = source_snapshot()
    second = source_snapshot(
        source_suffix="d", publication_suffix="e", run_suffix="f", digest="b" * 64
    )
    monkeypatch.setattr(
        library_export,
        "DEFAULT_EXPORT_LIMITS",
        ExportLimits(1, 2, 100, 100),
    )
    assert_reason("too_large", lambda: active_snapshot(first, second))

    two_evidence = source_snapshot(
        evidence=(
            evidence_snapshot(suffix="1", start=1, end=1, text="first"),
            evidence_snapshot(suffix="2", start=2, end=2, text="second"),
        )
    )
    monkeypatch.setattr(
        library_export,
        "DEFAULT_EXPORT_LIMITS",
        ExportLimits(1, 1, 100, 100),
    )
    assert_reason("too_large", lambda: active_snapshot(two_evidence))

    monkeypatch.setattr(
        library_export,
        "DEFAULT_EXPORT_LIMITS",
        ExportLimits(1, 2, len(b"page text") - 1, 100),
    )
    assert_reason("too_large", lambda: active_snapshot(first))


def test_library_accepts_active_publication_budget_at_equality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        library_export,
        "DEFAULT_EXPORT_LIMITS",
        ExportLimits(1, 2, 100, 1),
    )

    snapshot = active_snapshot(source_snapshot())

    assert len(snapshot.sources) == 1


def test_library_accepts_active_evidence_budget_at_equality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = source_snapshot(
        evidence=(
            evidence_snapshot(suffix="1", start=1, end=1, text="first"),
            evidence_snapshot(suffix="2", start=2, end=2, text="second"),
        )
    )
    monkeypatch.setattr(
        library_export,
        "DEFAULT_EXPORT_LIMITS",
        ExportLimits(1, 2, 100, 1),
    )

    snapshot = active_snapshot(source)

    assert sum(len(item.evidence) for item in snapshot.sources) == 2


def test_library_accepts_utf8_byte_budget_at_equality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = "证据"
    monkeypatch.setattr(
        library_export,
        "DEFAULT_EXPORT_LIMITS",
        ExportLimits(1, 1, len(text.encode()), 1),
    )

    snapshot = active_snapshot(source_snapshot(text=text))

    assert snapshot.evidence_utf8_bytes == len(text.encode())
