import hashlib
import sqlite3
from pathlib import Path
from typing import Literal

import pytest

from mke.adapters.sqlite import EvidenceNotFoundError
from mke.application import KnowledgeEngine
from mke.domain import (
    PDF_EXTRACTOR_FINGERPRINT,
    REQUIRED_PDF_STAGES,
    ActiveAuthoritySnapshot,
    CandidateEvidence,
    RunManifest,
)


def publish(
    engine: KnowledgeEngine,
    *,
    fingerprint: str = "a",
    name: str = "fixture.pdf",
    texts: tuple[str, ...] = ("one", "two", "三🙂" * 1000),
) -> tuple[str, str, str]:
    source = engine.ensure_source(name, fingerprint * 64)
    run = engine.create_run(source.source_id)
    engine.persist_validated_candidate(
        run.run_id,
        [
            CandidateEvidence(
                evidence_id=f"ev_{fingerprint}{index:031x}",
                locator_kind="page",
                locator_start=index,
                locator_end=index,
                text=text,
            )
            for index, text in enumerate(texts, 1)
        ],
        RunManifest(
            run_id=run.run_id,
            evidence_count=len(texts),
            required_stages=tuple(sorted(REQUIRED_PDF_STAGES)),
            extractor_fingerprint=PDF_EXTRACTOR_FINGERPRINT,
            asset_sha256=fingerprint * 64,
        ),
    )
    engine.activate_publication(run.run_id)
    catalog = engine.list_sources_page(position=0, page_size=20, authority_validator=lambda _: None)
    selected = next(item for item in catalog.sources if item.source_id == source.source_id)
    return source.source_id, selected.publication_id, run.run_id


def test_catalog_and_browse_preserve_identity_without_loading_catalog_text(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        source, publication, _ = publish(engine, name="/private/secret/fixture.pdf")
        engine.ensure_source("unpublished.pdf", "b" * 64)
        connection = engine._store._connection  # pyright: ignore[reportPrivateUsage]
        statements: list[str] = []
        connection.set_trace_callback(statements.append)
        catalog = engine.list_sources_page(
            position=0, page_size=10, authority_validator=lambda _: None
        )
        connection.set_trace_callback(None)
        assert len(catalog.sources) == 1
        assert catalog.sources[0].display_name == "fixture.pdf"
        assert catalog.sources[0].coverage.report_status == "not_observed"
        assert not any("evidence.text" in statement for statement in statements)
        from mke.domain.source_discovery import SourceLocatorRange

        browse = engine.browse_source_evidence_page(
            source,
            publication,
            locator_range=SourceLocatorRange("page", 2, 3),
            position=0,
            page_size=10,
            authority_validator=lambda _: None,
        )
        assert [entry.descriptor.locator_start for entry in browse.entries] == [2, 3]
        assert browse.entries[1].descriptor.evidence_text_sha256 == (
            "sha256:" + hashlib.sha256(("三🙂" * 1000).encode()).hexdigest()
        )
        assert browse.entries[1].preview.complete is False
        assert len(browse.entries[1].preview.text.encode()) <= 2048
        zero = engine.browse_source_evidence_page(
            source,
            publication,
            locator_range=SourceLocatorRange("page", 20, 30),
            position=0,
            page_size=10,
            authority_validator=lambda _: None,
        )
        assert zero.entries == () and not zero.more_available
        with pytest.raises(EvidenceNotFoundError):
            engine.browse_source_evidence_page(
                source,
                "pub_wrong",
                locator_range=None,
                position=0,
                page_size=10,
                authority_validator=lambda _: None,
            )
    finally:
        engine.close()


def test_snapshot_survives_concurrent_publication_replacement(tmp_path: Path) -> None:
    from mke.application.mcp_cursor import CursorExpiredError, parse_cursor_untrusted
    from mke.application.source_cursor import (
        SourceCursorPayload,
        encode_source_cursor,
        library_binding,
        validate_source_cursor,
    )
    from mke.domain import PdfIntakeReport
    from mke.domain.source_discovery import PdfSourceCoverage
    from mke.runtime_owner import CursorOwnerMaterial

    path = tmp_path / "mke.sqlite"
    engine = KnowledgeEngine(path)
    writer = KnowledgeEngine(path, recover_unfinished_runs=False)
    try:
        source, publication, run = publish(engine, texts=("old",))
        original_report = PdfIntakeReport(1, 1, 0, 3, (3,), 0, "text_layer")
        engine._store.persist_pdf_intake_report(run, original_report)  # pyright: ignore[reportPrivateUsage]
        newer = engine.create_run(source)
        engine.persist_validated_candidate(
            newer.run_id,
            [CandidateEvidence("ev_" + "f" * 32, "page", 1, 1, "newer")],
            RunManifest(
                newer.run_id,
                1,
                tuple(sorted(REQUIRED_PDF_STAGES)),
                PDF_EXTRACTOR_FINGERPRINT,
                "a" * 64,
            ),
        )
        newer_report = PdfIntakeReport(1, 1, 0, 5, (5,), 0, "text_layer")
        material = CursorOwnerMaterial(key=b"k" * 32, epoch="snapshot-owner")
        binding = library_binding(material, path)
        cursors: list[str] = []

        def replace_publication(authority: ActiveAuthoritySnapshot) -> None:
            cursors.append(
                encode_source_cursor(
                    material,
                    SourceCursorPayload(
                        "mke.mcp_cursor.v1",
                        "browse_source_evidence_v1",
                        material.epoch,
                        authority.active_set_fingerprint,
                        binding,
                        1,
                        1,
                        "mke.browse_source_evidence_response.v1",
                        source,
                        publication,
                        "",
                        0,
                        0,
                        "locator-start-end-evidence-id-v1",
                    ),
                )
            )
            writer._store.activate_publication(  # pyright: ignore[reportPrivateUsage]
                newer.run_id, pdf_intake_report=newer_report
            )

        page = engine.browse_source_evidence_page(
            source,
            publication,
            locator_range=None,
            position=0,
            page_size=1,
            authority_validator=replace_publication,
        )
        assert page.source.run_id == run
        assert page.entries[0].descriptor.publication_id == publication
        assert page.entries[0].preview.text == "old"
        coverage = page.source.coverage
        assert isinstance(coverage, PdfSourceCoverage)
        assert coverage.total_extracted_chars == 3 and coverage.page_char_counts == (3,)
        current = engine.list_sources_page(
            position=0, page_size=10, authority_validator=lambda _: None
        ).sources[0]
        assert current.run_id == newer.run_id
        with pytest.raises(EvidenceNotFoundError):
            engine.browse_source_evidence_page(
                source,
                publication,
                locator_range=None,
                position=0,
                page_size=1,
                authority_validator=lambda _: None,
            )
        parsed = parse_cursor_untrusted(cursors[0])

        def validate_continuation(authority: ActiveAuthoritySnapshot) -> None:
            validate_source_cursor(
                parsed,
                material,
                authority,
                tool="browse_source_evidence_v1",
                library_binding=binding,
            )

        with pytest.raises(CursorExpiredError, match="active_set_changed"):
            engine.browse_source_evidence_page(
                source,
                publication,
                locator_range=None,
                position=1,
                page_size=1,
                authority_validator=validate_continuation,
            )
    finally:
        writer.close()
        engine.close()


def test_pdf_coverage_projects_only_producing_run_and_bounds_arrays(tmp_path: Path) -> None:
    from mke.domain import PdfIntakeReport
    from mke.domain.source_discovery import PdfSourceCoverage

    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        source, publication, run = publish(engine)
        engine._store.persist_pdf_intake_report(  # pyright: ignore[reportPrivateUsage]
            run,
            PdfIntakeReport(
                total_pages=1000,
                extracted_pages=3,
                empty_pages=997,
                total_extracted_chars=300,
                page_char_counts=(100,) * 1000,
                suspected_scanned_pages=996,
                extraction_mode="text_layer",
            ),
        )
        future = engine.create_run(source)
        engine._store.persist_pdf_intake_report(  # pyright: ignore[reportPrivateUsage]
            future.run_id, PdfIntakeReport(1, 1, 0, 7, (7,), 0, "future_mode")
        )
        catalog = engine.list_sources_page(
            position=0, page_size=1, authority_validator=lambda _: None
        )
        coverage = catalog.sources[0].coverage
        assert isinstance(coverage, PdfSourceCoverage)
        assert coverage.extraction_mode == "text_layer"
        assert coverage.page_char_counts == ()
        assert coverage.page_char_counts_total == 1000
        assert coverage.page_char_counts_omitted is True
        browse = engine.browse_source_evidence_page(
            source,
            publication,
            locator_range=None,
            position=0,
            page_size=1,
            authority_validator=lambda _: None,
        )
        coverage = browse.source.coverage
        assert isinstance(coverage, PdfSourceCoverage)
        assert len(coverage.page_char_counts) == 256
        assert coverage.page_char_counts_omitted is True
        assert coverage.empty_pages == 997 and coverage.suspected_scanned_pages == 996
    finally:
        engine.close()


def test_catalog_pagination_no_omissions_and_oversized_metadata_rejected(tmp_path: Path) -> None:
    from mke.adapters.sqlite import EvidenceResponseTooLargeError

    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        for fingerprint in "abcde":
            publish(engine, fingerprint=fingerprint, texts=("one",))
        actual: list[str] = []
        position = 0
        while True:
            page = engine.list_sources_page(
                position=position, page_size=2, authority_validator=lambda _: None
            )
            actual.extend(source.content_fingerprint for source in page.sources)
            position += len(page.sources)
            if not page.more_available:
                break
        assert actual == ["sha256:" + character * 64 for character in "abcde"]
        connection = engine._store._connection  # pyright: ignore[reportPrivateUsage]
        connection.execute("UPDATE sources SET display_name = ?", ("x" * 32769,))
        connection.commit()
        with pytest.raises(EvidenceResponseTooLargeError):
            engine.list_sources_page(position=0, page_size=2, authority_validator=lambda _: None)
    finally:
        engine.close()


def test_timestamp_overlap_and_wrong_locator_kind(tmp_path: Path) -> None:
    from mke.domain.source_discovery import SourceLocatorRange, TranscriptSourceCoverage
    from tests.conftest import VIDEO_FIXTURES

    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        engine.ingest_video(VIDEO_FIXTURES / "short-audio.mp4")
        catalog = engine.list_sources_page(
            position=0, page_size=10, authority_validator=lambda _: None
        )
        source = catalog.sources[0]
        assert isinstance(source.coverage, TranscriptSourceCoverage)
        assert source.coverage.evidence_kind == "stored_transcript"
        page = engine.browse_source_evidence_page(
            source.source_id,
            source.publication_id,
            locator_range=SourceLocatorRange("timestamp_ms", 1199, 1200),
            position=0,
            page_size=10,
            authority_validator=lambda _: None,
        )
        assert [
            (entry.descriptor.locator_start, entry.descriptor.locator_end) for entry in page.entries
        ] == [(0, 1200)]
        with pytest.raises(ValueError, match="kind"):
            engine.browse_source_evidence_page(
                source.source_id,
                source.publication_id,
                locator_range=SourceLocatorRange("page", 1, 2),
                position=0,
                page_size=10,
                authority_validator=lambda _: None,
            )
    finally:
        engine.close()


@pytest.mark.parametrize(
    "corruption",
    [
        "UPDATE runs SET state = 'failed'",
        "UPDATE sources SET library_id = 'foreign'",
        "UPDATE publications SET source_id = 'foreign'",
    ],
)
def test_discovery_rejects_invalid_authority_graph(tmp_path: Path, corruption: str) -> None:
    from mke.domain import ManifestValidationError

    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        publish(engine)
        connection = engine._store._connection  # pyright: ignore[reportPrivateUsage]
        # Disable foreign-key checks only on this corrupt-fixture writer.
        writer = sqlite3.connect(tmp_path / "mke.sqlite")
        try:
            writer.execute(corruption)
            writer.commit()
        finally:
            writer.close()
        connection.commit()
        with pytest.raises(ManifestValidationError):
            engine.list_sources_page(position=0, page_size=1, authority_validator=lambda _: None)
    finally:
        engine.close()


def test_browse_budget_pagination_keeps_all_descriptors_and_unicode(tmp_path: Path) -> None:
    from dataclasses import asdict

    from mke.application.source_discovery import assemble_source_page
    from mke.domain.source_discovery import SourceBrowsePage

    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        source, publication, _ = publish(engine, texts=tuple("🙂三" * 800 for _ in range(20)))
        position = 0
        locators: list[int] = []

        def serialize(page: SourceBrowsePage, cursor: str | None) -> object:
            return {"page": asdict(page), "next_cursor": cursor}

        while True:
            page = engine.browse_source_evidence_page(
                source,
                publication,
                locator_range=None,
                position=position,
                page_size=20,
                authority_validator=lambda _: None,
            )
            assembled = assemble_source_page(
                page, cursor_factory=lambda value: str(value), serialize_response=serialize
            )
            assert (
                sum(entry.preview.returned_utf8_bytes for entry in assembled.page.entries) <= 16384
            )
            locators.extend(entry.descriptor.locator_start for entry in assembled.page.entries)
            position += len(assembled.page.entries)
            if assembled.next_cursor is None:
                break
            assert int(assembled.next_cursor) == position
        assert locators == list(range(1, 21))
    finally:
        engine.close()


def test_browse_oversized_evidence_preflights_before_text(tmp_path: Path) -> None:
    from mke.adapters.sqlite import EvidenceResponseTooLargeError

    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        source, publication, _ = publish(engine, texts=("one",))
        connection = engine._store._connection  # pyright: ignore[reportPrivateUsage]
        connection.execute("UPDATE evidence SET text = ?", ("x" * (16 * 1024 * 1024 + 1),))
        connection.commit()
        statements: list[str] = []
        connection.set_trace_callback(statements.append)
        with pytest.raises(EvidenceResponseTooLargeError):
            engine.browse_source_evidence_page(
                source,
                publication,
                locator_range=None,
                position=0,
                page_size=1,
                authority_validator=lambda _: None,
            )
        connection.set_trace_callback(None)
        assert not any("SELECT text FROM evidence" in statement for statement in statements)
    finally:
        engine.close()


def test_discovery_excludes_failed_candidates_and_wrong_source_publication_pair(
    tmp_path: Path,
) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        source, publication, _ = publish(engine)
        other, other_publication, _ = publish(engine, fingerprint="b", texts=("other",))
        failed = engine.ensure_source("failed.pdf", "c" * 64)
        run = engine.create_run(failed.source_id)
        engine._store.mark_run_failed(run.run_id)  # pyright: ignore[reportPrivateUsage]
        candidate = engine.ensure_source("candidate.pdf", "d" * 64)
        run = engine.create_run(candidate.source_id)
        engine.persist_validated_candidate(
            run.run_id,
            [CandidateEvidence("ev_" + "d" * 32, "page", 1, 1, "unpublished")],
            RunManifest(
                run.run_id,
                1,
                tuple(sorted(REQUIRED_PDF_STAGES)),
                PDF_EXTRACTOR_FINGERPRINT,
                "d" * 64,
            ),
        )
        assert (
            len(
                engine.list_sources_page(
                    position=0, page_size=20, authority_validator=lambda _: None
                ).sources
            )
            == 2
        )
        for selected, pub in [(source, other_publication), (other, publication)]:
            with pytest.raises(EvidenceNotFoundError):
                engine.browse_source_evidence_page(
                    selected,
                    pub,
                    locator_range=None,
                    position=0,
                    page_size=10,
                    authority_validator=lambda _: None,
                )
    finally:
        engine.close()


def test_transcript_coverage_returns_persisted_producing_report(tmp_path: Path) -> None:
    from mke.domain.source_discovery import TranscriptSourceCoverage
    from tests.application.test_video_provider_injection import FakeFasterWhisperProvider

    video = tmp_path / "synthetic.mp4"
    video.write_bytes(b"public synthetic media fixture")
    engine = KnowledgeEngine(
        tmp_path / "mke.sqlite", transcript_provider=FakeFasterWhisperProvider()
    )
    try:
        engine.ingest_video(video)
        source = engine.list_sources_page(
            position=0, page_size=1, authority_validator=lambda _: None
        ).sources[0]
        coverage = source.coverage
        assert isinstance(coverage, TranscriptSourceCoverage)
        assert coverage.report_status == "observed"
        assert coverage.provenance is not None
        assert coverage.provenance.model == "small"
        assert coverage.provenance.detected_language == "en"
        assert coverage.provenance.segment_count == 1
    finally:
        engine.close()


def test_copied_library_with_same_active_ids_rejects_catalog_cursor(tmp_path: Path) -> None:
    import shutil

    from mke.application.mcp_cursor import InvalidCursorError, parse_cursor_untrusted
    from mke.application.source_cursor import (
        SourceCursorPayload,
        encode_source_cursor,
        library_binding,
        validate_source_cursor,
    )
    from mke.runtime_owner import CursorOwnerMaterial

    original_path = tmp_path / "original.sqlite"
    copied_path = tmp_path / "copy.sqlite"
    material = CursorOwnerMaterial(key=b"k" * 32, epoch="same-owner")
    engine = KnowledgeEngine(original_path)
    publish(engine)
    original = engine.list_sources_page(position=0, page_size=1, authority_validator=lambda _: None)
    engine.close()
    shutil.copyfile(original_path, copied_path)
    token = encode_source_cursor(
        material,
        SourceCursorPayload(
            "mke.mcp_cursor.v1",
            "list_sources_v1",
            material.epoch,
            original.authority.active_set_fingerprint,
            library_binding(material, original_path),
            1,
            1,
            "mke.list_sources_response.v1",
            "",
            "",
            "",
            0,
            0,
            "content-fingerprint-source-id-v1",
        ),
    )
    parsed = parse_cursor_untrusted(token)
    assert str(original_path) not in str(parsed.raw)
    copied = KnowledgeEngine(copied_path)
    try:
        page = copied.list_sources_page(position=0, page_size=1, authority_validator=lambda _: None)
        assert page.authority == original.authority
        with pytest.raises(InvalidCursorError):
            validate_source_cursor(
                parsed,
                material,
                page.authority,
                tool="list_sources_v1",
                library_binding=library_binding(material, copied_path),
            )
    finally:
        copied.close()


@pytest.mark.parametrize("operation", ["catalog", "browse"])
def test_discovery_rejects_sources_without_library(tmp_path: Path, operation: str) -> None:
    from mke.domain import ManifestValidationError

    path = tmp_path / "mke.sqlite"
    engine = KnowledgeEngine(path)
    try:
        source, publication, _ = publish(engine)
        # A separate corrupt-fixture writer has foreign-key enforcement disabled.
        with sqlite3.connect(path) as writer:
            writer.execute("DELETE FROM libraries")
        with pytest.raises(ManifestValidationError, match="Library ownership"):
            if operation == "catalog":
                engine.list_sources_page(
                    position=0, page_size=10, authority_validator=lambda _: None
                )
            else:
                engine.browse_source_evidence_page(
                    source,
                    publication,
                    locator_range=None,
                    position=0,
                    page_size=10,
                    authority_validator=lambda _: None,
                )
    finally:
        engine.close()


def test_discovery_accepts_an_empty_uninitialized_library(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        page = engine.list_sources_page(
            position=0, page_size=10, authority_validator=lambda _: None
        )
        assert page.authority.observation.state == "empty"
        assert page.sources == ()
        assert page.more_available is False
    finally:
        engine.close()


def publish_boundary_locators(
    engine: KnowledgeEngine,
    kind: Literal["page", "timestamp_ms"],
) -> tuple[str, str]:
    """Declared candidate fixture at the actual SQLite integer locator boundary."""
    from mke.domain import REQUIRED_VIDEO_STAGES, VIDEO_TRANSCRIPT_FINGERPRINT

    maximum = 2**63 - 1
    fingerprint = ("a" if kind == "page" else "b") * 64
    source = engine.ensure_source(
        "boundary.pdf" if kind == "page" else "boundary.mp4",
        fingerprint,
        media_type="application/pdf" if kind == "page" else "video/mp4",
    )
    locators = (
        ((1, 1), (maximum - 1, maximum - 1), (maximum, maximum))
        if kind == "page"
        else ((0, 1), (maximum - 2, maximum - 1), (maximum - 1, maximum))
    )
    run = engine.create_run(source.source_id)
    engine.persist_validated_candidate(
        run.run_id,
        [
            CandidateEvidence(
                f"ev_{fingerprint[0]}{index:031x}",
                kind,
                start,
                end,
                f"boundary text {index}",
            )
            for index, (start, end) in enumerate(locators, 1)
        ],
        RunManifest(
            run.run_id,
            len(locators),
            tuple(sorted(REQUIRED_PDF_STAGES if kind == "page" else REQUIRED_VIDEO_STAGES)),
            PDF_EXTRACTOR_FINGERPRINT if kind == "page" else VIDEO_TRANSCRIPT_FINGERPRINT,
            fingerprint,
        ),
    )
    engine.activate_publication(run.run_id)
    selected = engine.ensure_source(
        "boundary",
        fingerprint,
        media_type="application/pdf" if kind == "page" else "video/mp4",
    )
    assert selected.active_publication_id is not None
    return source.source_id, selected.active_publication_id


@pytest.mark.parametrize("kind", ["page", "timestamp_ms"])
@pytest.mark.parametrize("scenario", ["exact_end", "overflow_end", "huge_end", "overflow_start"])
def test_source_ranges_above_sqlite_domain_keep_locator_semantics(
    tmp_path: Path,
    kind: Literal["page", "timestamp_ms"],
    scenario: str,
) -> None:
    from mke.domain.source_discovery import SourceLocatorRange

    maximum = 2**63 - 1
    end = {
        "exact_end": maximum,
        "overflow_end": maximum + 1,
        "huge_end": 10**100,
        "overflow_start": maximum + 2,
    }[scenario]
    start = maximum + 1 if scenario == "overflow_start" else (1 if kind == "page" else 0)
    locator_range = SourceLocatorRange(kind, start, end)
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        source, publication = publish_boundary_locators(engine, kind)
        actual: list[int] = []
        for position in range(3):
            page = engine.browse_source_evidence_page(
                source,
                publication,
                locator_range=locator_range,
                position=position,
                page_size=1,
                authority_validator=lambda _: None,
            )
            actual.extend(entry.descriptor.locator_start for entry in page.entries)
            assert page.more_available == (scenario != "overflow_start" and position < 2)
            if not page.more_available:
                break
        assert actual == (
            []
            if scenario == "overflow_start"
            else ([1, maximum - 1, maximum] if kind == "page" else [0, maximum - 2, maximum - 1])
        )
        assert locator_range.start == start and locator_range.end == end
    finally:
        engine.close()


@pytest.mark.parametrize("kind", ["page", "timestamp_ms"])
def test_source_range_exact_sqlite_boundaries_keep_inclusive_and_overlap_rules(
    tmp_path: Path,
    kind: Literal["page", "timestamp_ms"],
) -> None:
    from mke.domain.source_discovery import SourceLocatorRange

    maximum = 2**63 - 1
    ranges: list[tuple[int, int, list[int]]] = (
        [
            (maximum, maximum, [maximum]),
            (maximum - 1, maximum, [maximum - 1, maximum]),
            (maximum, maximum + 1, [maximum]),
        ]
        if kind == "page"
        else [
            (maximum - 1, maximum, [maximum - 1]),
            (maximum - 2, maximum - 1, [maximum - 2]),
            (maximum, maximum + 1, []),
        ]
    )
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        source, publication = publish_boundary_locators(engine, kind)
        for start, end, expected in ranges:
            page = engine.browse_source_evidence_page(
                source,
                publication,
                locator_range=SourceLocatorRange(kind, start, end),
                position=0,
                page_size=10,
                authority_validator=lambda _: None,
            )
            assert [entry.descriptor.locator_start for entry in page.entries] == expected
            assert not page.more_available
    finally:
        engine.close()
