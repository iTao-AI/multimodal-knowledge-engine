from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.source_discovery_support import cli_payloads, native_cli, publish_pages


def test_actual_cli_scope_pages_and_legacy_output(tmp_path: Path) -> None:
    database = tmp_path / "mke.sqlite"
    source, publication = publish_pages(database, ("needle scoped",) * 13, fingerprint="f")
    publish_pages(database, ("needle outside",) * 20, fingerprint="a")
    legacy = native_cli(database, "search", "needle")
    assert legacy.returncode == 0 and len(legacy.stdout.splitlines()) == 33
    assert "text=needle scoped" in legacy.stdout and "text=needle outside" in legacy.stdout
    pages = cli_payloads(
        native_cli(
            database,
            "search",
            "needle",
            "--source-id",
            source,
            "--publication-id",
            publication,
            "--limit",
            "3",
            "--json",
        )
    )
    assert len(pages) == 5 and pages[-1]["selection"]["status"] == "complete"
    assert [
        item["evidence"]["locator"]["start"] for page in pages for item in page["matches"]
    ] == list(range(1, 14))
    assert all(page["scope"]["source_id"] == source for page in pages)
    wrong = native_cli(
        database,
        "search",
        "needle",
        "--source-id",
        source,
        "--publication-id",
        "pub_wrong",
        "--json",
    )
    assert wrong.returncode == 1 and json.loads(wrong.stdout)["problem"] == "evidence_not_found"
    empty = cli_payloads(
        native_cli(
            database,
            "search",
            "missing",
            "--source-id",
            source,
            "--publication-id",
            publication,
            "--json",
        )
    )
    assert len(empty) == 1 and empty[0]["matches"] == []


@pytest.mark.parametrize(
    "options",
    [
        ("--source-id", "src_only"),
        ("--publication-id", "pub_only"),
        ("--json",),
        ("--limit", "3"),
    ],
)
def test_cli_scope_options_require_explicit_pair(tmp_path: Path, options: tuple[str, ...]) -> None:
    result = native_cli(tmp_path / "mke.sqlite", "search", "needle", *options)
    assert result.returncode == 2 and "Traceback" not in result.stderr


def test_cli_stops_on_changed_publication_between_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import builtins

    from mke.cli import main

    database = tmp_path / "mke.sqlite"
    source, publication = publish_pages(database, ("needle",) * 3)
    outputs: list[dict[str, object]] = []

    def intercept(text: str, **kwargs: object) -> None:
        del kwargs
        outputs.append(json.loads(text))
        if len(outputs) == 1:
            publish_pages(database, ("new source",), fingerprint="b")

    monkeypatch.setattr(builtins, "print", intercept)
    assert (
        main(
            [
                "--db",
                str(database),
                "search",
                "needle",
                "--source-id",
                source,
                "--publication-id",
                publication,
                "--limit",
                "1",
                "--json",
            ]
        )
        == 1
    )
    assert outputs[0]["ok"] is True and outputs[1]["problem"] == "cursor_expired"
