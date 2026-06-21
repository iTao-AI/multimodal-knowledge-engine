# Numeric Retrieval V1 Fixtures

These two text-layer PDFs were created for this repository to test one narrow claim:
whether a compact ASCII integer query can match the same right-grouped tokenizer-adjacent tokens
without changing unrelated retrieval results.

The development and holdout documents use different numbers, units, vocabulary, and exact page
text. The holdout is locked and independently authored, but public rather than secret or
statistically blind. These fixtures do not support a general retrieval-quality claim.

## Provenance

- Generator: `/tmp/mke-retrieval-numeric-v1/generate.py`, shown below.
- Command: `UV_OFFLINE=1 uv run python /tmp/mke-retrieval-numeric-v1/generate.py`.
- PyMuPDF: `1.27.2.3`.
- Page size: 612 by 792 points.
- Font: built-in Helvetica (`helv`), 12 points.
- Save options: `garbage=4`, `deflate=True`, `clean=True`.
- Both generated files were inspected before being copied into this directory.

| File | Bytes | SHA-256 |
|---|---:|---|
| `development.pdf` | 2091 | `721890756c2bbf9f53e391755dc507ae9cadc0de80f54e7e9b23c8a00667ee51` |
| `holdout.pdf` | 2045 | `769ae9e6bb2a57f1cea5c23bc72d9fa6135d9c41783f04b9e5eb7cac8a6a9931` |

Each PDF has exactly four pages.

## Exact Page Text

`development.pdf`:

1. `Grouped daily withdrawal total: 410,000 million gallons.`
2. `Compact inventory total: 730000 storage units.`
3. `Non-adjacent ledger values: 410 units were accepted; after review, 000 units were rejected.`
4. `Identifiers: postal district 02139; equipment model ZX410000; reporting year 2005.`

`holdout.pdf`:

1. `Grouped reserve capacity: 57,600 cubic meters.`
2. `Compact shipment count: 880000 sealed packages.`
3. `Non-adjacent audit values: 57 samples passed; later, 600 samples failed.`
4. `Identifiers: postal district 00701; sensor model AB57600; reporting year 1997.`

## Generator

```python
from pathlib import Path

import fitz

PAGES = {
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

root = Path("/tmp/mke-retrieval-numeric-v1")
root.mkdir(parents=True, exist_ok=True)
for name, pages in PAGES.items():
    document = fitz.open()
    for text in pages:
        page = document.new_page(width=612, height=792)
        written = page.insert_textbox(
            fitz.Rect(72, 72, 540, 720),
            text,
            fontsize=12,
            fontname="helv",
        )
        if written < 0:
            raise RuntimeError(f"page text did not fit: {name}")
    document.set_metadata(
        {
            "title": f"MKE numeric retrieval fixture: {name}",
            "author": "Multimodal Knowledge Engine",
            "subject": "Deterministic numeric retrieval evaluation",
        }
    )
    document.save(root / name, garbage=4, deflate=True, clean=True)
    document.close()
```
