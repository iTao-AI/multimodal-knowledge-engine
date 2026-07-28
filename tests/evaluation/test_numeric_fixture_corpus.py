import hashlib
import json
import re
from pathlib import Path
from typing import cast

import fitz  # pyright: ignore[reportMissingTypeStubs]

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "retrieval-numeric-v1"
README = FIXTURE_ROOT / "README.md"

EXPECTED_PAGES = {
    "development.pdf": (
        "Grouped daily withdrawal total: 410,000 million gallons.",
        "Compact inventory total: 730000 storage units.",
        (
            "Non-adjacent ledger values: 410 units were accepted; "
            "after review, 000 units were rejected."
        ),
        "Identifiers: postal district 02139; equipment model ZX410000; reporting year 2005.",
    ),
    "holdout.pdf": (
        "Grouped reserve capacity: 57,600 cubic meters.",
        "Compact shipment count: 880000 sealed packages.",
        "Non-adjacent audit values: 57 samples passed; later, 600 samples failed.",
        "Identifiers: postal district 00701; sensor model AB57600; reporting year 1997.",
    ),
}

EXPECTED_QUERY_IDS = {
    "development": (
        "numeric-dev-grouped-01",
        "numeric-dev-compact-01",
        "numeric-dev-non-adjacent-01",
        "numeric-dev-leading-zero-01",
        "numeric-dev-identifier-01",
        "numeric-dev-short-01",
        "numeric-dev-outside-01",
    ),
    "holdout": (
        "numeric-holdout-grouped-01",
        "numeric-holdout-compact-01",
        "numeric-holdout-non-adjacent-01",
        "numeric-holdout-leading-zero-01",
        "numeric-holdout-identifier-01",
        "numeric-holdout-short-01",
        "numeric-holdout-outside-01",
    ),
}


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _readme_identity(name: str) -> tuple[int, str]:
    readme = README.read_text(encoding="utf-8")
    match = re.search(
        rf"^\| `{re.escape(name)}` \| (?P<bytes>[0-9]+) \| "
        rf"`(?P<sha256>[0-9a-f]{{64}})` \|$",
        readme,
        flags=re.MULTILINE,
    )
    assert match is not None
    return int(match.group("bytes")), match.group("sha256")


def test_numeric_retrieval_pdfs_match_frozen_text_and_identity() -> None:
    observed_bytes: list[bytes] = []
    observed_pages: list[set[str]] = []

    for name, expected_pages in EXPECTED_PAGES.items():
        path = FIXTURE_ROOT / name
        data = path.read_bytes()
        expected_bytes, expected_sha256 = _readme_identity(name)
        assert len(data) == expected_bytes
        assert hashlib.sha256(data).hexdigest() == expected_sha256

        with fitz.open(path) as document:
            assert len(document) == 4
            pages = tuple(
                _normalize(
                    cast(
                        str,
                        page.get_text(  # pyright: ignore[reportUnknownMemberType]
                            "text", sort=True
                        ),
                    )
                )
                for page in document
            )
        assert pages == expected_pages
        observed_bytes.append(data)
        observed_pages.append(set(pages))

    assert observed_bytes[0] != observed_bytes[1]
    assert observed_pages[0].isdisjoint(observed_pages[1])


def test_numeric_manifests_freeze_inventory_and_disjoint_holdout() -> None:
    development = cast(
        dict[str, object],
        json.loads((FIXTURE_ROOT / "development.json").read_text(encoding="utf-8")),
    )
    holdout = cast(
        dict[str, object],
        json.loads((FIXTURE_ROOT / "holdout.json").read_text(encoding="utf-8")),
    )
    development_queries = cast(list[dict[str, object]], development["queries"])
    holdout_queries = cast(list[dict[str, object]], holdout["queries"])

    assert development["manifest_id"] == "retrieval-numeric-v1-development"
    assert holdout["manifest_id"] == "retrieval-numeric-v1-holdout"
    assert tuple(query["query_id"] for query in development_queries) == EXPECTED_QUERY_IDS[
        "development"
    ]
    assert tuple(query["query_id"] for query in holdout_queries) == EXPECTED_QUERY_IDS[
        "holdout"
    ]
    assert {query["query_id"] for query in development_queries}.isdisjoint(
        query["query_id"] for query in holdout_queries
    )
    assert {query["text"] for query in development_queries}.isdisjoint(
        query["text"] for query in holdout_queries
    )
    assert sum(query["category"] == "answerable" for query in development_queries) == 5
    assert sum(query["category"] == "answerable" for query in holdout_queries) == 5
    assert all(
        len(cast(list[object], query["relevant_locators"])) == 1
        for queries in (development_queries, holdout_queries)
        for query in queries
        if query["category"] == "answerable"
    )
