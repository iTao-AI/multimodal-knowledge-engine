from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tests.source_discovery_support import cli_payloads, create_library, native_cli


def test_subprocess_catalog_browse_exact_read_workflow(tmp_path: Path) -> None:
    database = create_library(tmp_path)
    catalog = cli_payloads(native_cli(database, "sources", "list", "--page-size", "1", "--json"))
    assert len(catalog) == 2
    sources = [source for page in catalog for source in page["sources"]]
    assert len({source["source_id"] for source in sources}) == 2
    selected = next(source for source in sources if source["display_name"] == "navigation.pdf")
    browse = cli_payloads(
        native_cli(
            database,
            "source",
            "browse",
            selected["source_id"],
            "--publication-id",
            selected["publication_id"],
            "--page-start",
            "2",
            "--page-end",
            "3",
            "--page-size",
            "1",
            "--json",
        )
    )
    assert len(browse) == 2
    entries = [entry for page in browse for entry in page["entries"]]
    assert [entry["evidence"]["locator"]["start"] for entry in entries] == [2, 3]
    query = native_cli(database, "search", "lexicalneedle")
    assert query.returncode == 0 and "navigation target" not in query.stdout
    descriptor = entries[0]["evidence"]
    read = cli_payloads(
        native_cli(
            database,
            "evidence",
            "read",
            descriptor["evidence_id"],
            "--max-bytes",
            "8",
            "--json",
        )
    )
    assert len(read) > 1 and read[-1]["complete"]
    text = "".join(page["content"]["text"] for page in read)
    assert text == "navigation target page two"
    assert (
        "sha256:" + hashlib.sha256(text.encode()).hexdigest() == descriptor["evidence_text_sha256"]
    )
    assert all(page["evidence"] == descriptor for page in read)
    transcript = next(source for source in sources if source["media_type"] == "video/mp4")
    times = cli_payloads(
        native_cli(
            database,
            "source",
            "browse",
            transcript["source_id"],
            "--publication-id",
            transcript["publication_id"],
            "--start-ms",
            "500",
            "--end-ms",
            "1500",
            "--page-size",
            "1",
            "--json",
        )
    )
    assert [
        entry["evidence"]["locator"]["start"] for page in times for entry in page["entries"]
    ] == [0, 1000]
    assert times[0]["source"]["coverage"]["evidence_kind"] == "stored_transcript"


@pytest.mark.parametrize(
    "arguments",
    [
        ("sources", "list", "--page-size", "0", "--json"),
        ("source", "browse", "src_wrong", "--publication-id", "pub_wrong", "--json"),
        ("source", "browse", "src", "--publication-id", "pub", "--page-start", "1", "--json"),
        (
            "source",
            "browse",
            "src",
            "--publication-id",
            "pub",
            "--page-start",
            "1",
            "--page-end",
            "2",
            "--start-ms",
            "0",
            "--end-ms",
            "3",
            "--json",
        ),
        ("evidence", "read", "ev_wrong", "--max-bytes", "3", "--json"),
    ],
)
def test_subprocess_invalid_commands_exit_nonzero(
    tmp_path: Path, arguments: tuple[str, ...]
) -> None:
    result = native_cli(tmp_path / "mke.sqlite", *arguments)
    assert result.returncode != 0
    assert "Traceback" not in result.stdout + result.stderr


def test_cli_stops_when_publication_changes_between_streamed_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import builtins
    import json

    from mke.cli import main
    from tests.source_discovery_support import publish_pages

    database = tmp_path / "mke.sqlite"
    source, _ = publish_pages(database, ("one",), fingerprint="a")
    publish_pages(database, ("two",), fingerprint="b")
    outputs: list[dict[str, object]] = []

    def intercept(text: str, **kwargs: object) -> None:
        del kwargs
        outputs.append(json.loads(text))
        if len(outputs) == 1:
            from mke.application import KnowledgeEngine
            from mke.domain import (
                PDF_EXTRACTOR_FINGERPRINT,
                REQUIRED_PDF_STAGES,
                CandidateEvidence,
                RunManifest,
            )

            writer = KnowledgeEngine(database)
            try:
                run = writer.create_run(source)
                writer.persist_validated_candidate(
                    run.run_id,
                    [
                        CandidateEvidence("ev_" + "f" * 32, "page", 1, 1, "replacement"),
                    ],
                    RunManifest(
                        run.run_id,
                        1,
                        tuple(sorted(REQUIRED_PDF_STAGES)),
                        PDF_EXTRACTOR_FINGERPRINT,
                        "a" * 64,
                    ),
                )
                writer.activate_publication(run.run_id)
            finally:
                writer.close()

    monkeypatch.setattr(builtins, "print", intercept)
    assert main(["--db", str(database), "sources", "list", "--page-size", "1", "--json"]) == 1
    assert outputs[0]["ok"] is True
    assert outputs[1]["problem"] == "cursor_expired"
