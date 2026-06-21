import hashlib
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
        "Non-adjacent ledger values: 410 units were accepted; after review, 000 units were rejected.",
        "Identifiers: postal district 02139; equipment model ZX410000; reporting year 2005.",
    ),
    "holdout.pdf": (
        "Grouped reserve capacity: 57,600 cubic meters.",
        "Compact shipment count: 880000 sealed packages.",
        "Non-adjacent audit values: 57 samples passed; later, 600 samples failed.",
        "Identifiers: postal district 00701; sensor model AB57600; reporting year 1997.",
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
