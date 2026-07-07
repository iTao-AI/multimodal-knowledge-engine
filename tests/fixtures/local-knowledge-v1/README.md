# Local Knowledge V1 Fixtures

This pack is repository-authored synthetic material created only for the MKE local knowledge proof.
It contains no copied documents, personal data, private operational details, customer information,
or external source material. The fictional subject is a `Cedar Relay`; one document describes a
maintenance procedure and the other describes an incident response procedure. Exact page content
is owned by the generator source and is not repeated in proof output or documentation.

## Generation

- Generator: `scripts/generate_local_knowledge_fixtures.py`.
- Command:

  ```bash
  UV_OFFLINE=1 uv run python scripts/generate_local_knowledge_fixtures.py \
    --output tests/fixtures/local-knowledge-v1
  ```

- PyMuPDF: `1.27.2.3`.
- PDF structure: one text-layer page per file, 612 by 792 points.
- Text: built-in Helvetica (`helv`), 12 points, within a fixed page rectangle.
- Metadata: stable repository-owned title, author, and subject only.
- Save options: `garbage=4`, `clean=True`, `deflate=True`, `no_new_id=True`.
- Network, model, external fixture, and system-font access: none.

## File Identities

| File | Bytes | SHA-256 |
|---|---:|---|
| `operations-guide.pdf` | 1000 | `0ac3e96efc89ee91e48bb3efc8611de88b2698e5aa26c1f8e0e8f78ad2d60ddd` |
| `incident-guide.pdf` | 990 | `ed55cfbe9bdbf4404eb9ff55ab7e51fac14006ae0584a14d50704f68a02ff699` |

`manifest.json` records the same identities and the three fixed proof queries. Tests regenerate the
pack in an isolated directory and require byte-for-byte equality with the committed PDFs and
manifest.
