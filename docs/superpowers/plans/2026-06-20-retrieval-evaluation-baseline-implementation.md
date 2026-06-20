# Retrieval Evaluation Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic offline `mke eval retrieval` command that records the current FTS5
page/timestamp retrieval baseline without changing retrieval behavior.

**Architecture:** A strict JSON manifest identifies versioned fixtures, queries, and binary locator
qrels. A project-owned evaluation package validates assets, ingests them through `KnowledgeEngine`,
enumerates active Evidence through a new read-only application method, evaluates Search and Ask in
two fresh SQLite workspaces, calculates pure metrics, and emits public-safe human/JSON reports.
Only evaluation integrity is gated; observed quality scores are recorded without minimum
thresholds.

**Tech Stack:** Python 3.12/3.13, stdlib dataclasses/JSON/hashlib/tempfile, SQLite FTS5,
PyMuPDF through the existing adapter, pytest, argparse, GitHub Actions.

**Approved design:**
`docs/superpowers/specs/2026-06-20-retrieval-evaluation-baseline-design.md`

**Implementation boundary:** Do not change `SQLiteStore.search`, `_to_fts_query`, Search ordering,
Ask validation/statuses, Publication semantics, or transcription behavior. Do not add embeddings,
`sqlite-vec`, RRF, reranking, network access at evaluation runtime, or exact-score CI assertions.

---

## File Map

### New product files

- `src/mke/evaluation/__init__.py`: package exports for the CLI.
- `src/mke/evaluation/manifest.py`: immutable manifest DTOs, strict JSON parsing, path and fixture
  validation.
- `src/mke/evaluation/metrics.py`: pure binary-qrel metric calculations.
- `src/mke/evaluation/report.py`: result/report DTOs and public-safe human/JSON rendering.
- `src/mke/evaluation/runner.py`: two-workspace orchestration, normal ingest/Search/Ask calls,
  qrel validation, and determinism checks.

### Existing product files

- `src/mke/domain/__init__.py`: add the narrow project-owned `ActiveEvidenceRef` DTO.
- `src/mke/adapters/sqlite/__init__.py`: add a read-only active-Evidence enumeration query; do not
  modify Search SQL.
- `src/mke/application/__init__.py`: expose enumeration through `KnowledgeEngine`.
- `src/mke/cli.py`: add `mke eval retrieval --manifest ... [--json]`.

### Fixtures

- `tests/fixtures/retrieval-eval-v1.json`: exact 24-query manifest.
- `tests/fixtures/eval/retrieval/README.md`: USGS provenance, public-domain policy, checksums, and
  retrieval date.
- `tests/fixtures/eval/retrieval/usgs-volcano-hazards.pdf`: approved exact USGS bytes.
- `tests/fixtures/eval/retrieval/usgs-water-use-2005.pdf`: approved exact USGS bytes.

### Tests

- `tests/evaluation/__init__.py`
- `tests/evaluation/test_fixture_corpus.py`
- `tests/evaluation/test_manifest.py`
- `tests/evaluation/test_metrics.py`
- `tests/evaluation/test_report.py`
- `tests/evaluation/test_runner.py`
- `tests/adapters/test_sqlite_fts.py`
- `tests/interfaces/test_cli_evaluation.py`

### Documentation and CI

- `.github/workflows/ci.yml`
- `README.md`
- `README_CN.md`
- `docs/README.md`
- `docs/reference/cli.md`
- `docs/how-to/run-retrieval-evaluation.md`
- `benchmarks/retrieval/retrieval-eval-v1-baseline.json`
- `docs/superpowers/reviews/2026-06-20-retrieval-evaluation-baseline-plan-review.md`
- `docs/superpowers/reviews/2026-06-20-retrieval-evaluation-baseline-review.md`
- `docs/superpowers/plans/2026-06-20-retrieval-evaluation-baseline-implementation.md`
- `docs/superpowers/specs/2026-06-20-retrieval-evaluation-baseline-design.md`

---

### Task 1: Add The Approved Offline Corpus And Frozen Manifest

**Files:**
- Create: `tests/evaluation/__init__.py`
- Create: `tests/evaluation/test_fixture_corpus.py`
- Create: `tests/fixtures/retrieval-eval-v1.json`
- Create: `tests/fixtures/eval/retrieval/README.md`
- Create: `tests/fixtures/eval/retrieval/usgs-volcano-hazards.pdf`
- Create: `tests/fixtures/eval/retrieval/usgs-water-use-2005.pdf`

- [x] **Step 1: Write the failing fixture-integrity test**

Create `tests/evaluation/__init__.py` as an empty file.

Create `tests/evaluation/test_fixture_corpus.py`:

```python
import hashlib
import json
from pathlib import Path

import fitz

FIXTURES = Path(__file__).parents[1] / "fixtures"
MANIFEST = FIXTURES / "retrieval-eval-v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_retrieval_eval_corpus_matches_approved_bytes_and_text_layers() -> None:
    expected = {
        "eval/retrieval/usgs-volcano-hazards.pdf": (
            563382,
            "bdb8a5b6c648194e0fcc6f932b70976350bdc864c8187632c47f0cb64a21da4e",
            (5842, 8626),
        ),
        "eval/retrieval/usgs-water-use-2005.pdf": (
            400168,
            "ef27346a9f2eab19d438a0740d43c606a9b739147e09d89d1121df294ed3c585",
            (6755, 9716),
        ),
    }

    for relative_path, (expected_bytes, expected_sha256, expected_chars) in expected.items():
        path = FIXTURES / relative_path
        assert path.stat().st_size == expected_bytes
        assert _sha256(path) == expected_sha256
        with fitz.open(path) as document:
            assert len(document) == 2
            assert tuple(len(page.get_text("text", sort=True)) for page in document) == (
                expected_chars
            )


def test_retrieval_eval_reuses_exact_video_fixture_bytes() -> None:
    expected = {
        "video/short-audio.mp4": (
            13025,
            "4e3c9feffa503e193165ddf27c40c0e0edf9f256c2e8e1e2d863bd7ba3e1fe49",
        ),
        "video/short-audio.mp4.mke-transcript.json": (
            506,
            "5688603821b9262f85592912ef957d852ea34448e7292c927ea5071a0668e995",
        ),
    }

    for relative_path, (expected_bytes, expected_sha256) in expected.items():
        path = FIXTURES / relative_path
        assert path.stat().st_size == expected_bytes
        assert _sha256(path) == expected_sha256


def test_retrieval_eval_manifest_freezes_approved_inventory() -> None:
    payload = json.loads(MANIFEST.read_text())

    assert payload["schema_version"] == "mke.retrieval_eval.v1"
    assert payload["manifest_id"] == "retrieval-eval-v1"
    assert len(payload["documents"]) == 3
    assert len(payload["queries"]) == 24
    assert sum(query["category"] == "answerable" for query in payload["queries"]) == 16
    assert sum(query["category"] == "lexical_confuser" for query in payload["queries"]) == 4
    assert sum(query["category"] == "out_of_corpus" for query in payload["queries"]) == 4
```

- [x] **Step 2: Run the fixture test to verify RED**

Run:

```bash
uv run pytest tests/evaluation/test_fixture_corpus.py -q
```

Expected: FAIL because the E1 PDF fixtures and manifest do not exist.

- [x] **Step 3: Download the exact approved PDF bytes outside the repository**

Run:

```bash
mkdir -p /tmp/mke-retrieval-eval
curl --proto '=https' --tlsv1.2 --location --fail --silent --show-error \
  https://pubs.usgs.gov/fs/fs002-97/fs00297.pdf \
  --output /tmp/mke-retrieval-eval/usgs-volcano-hazards.pdf
curl --proto '=https' --tlsv1.2 --location --fail --silent --show-error \
  https://pubs.usgs.gov/fs/2009/3098/pdf/2009-3098.pdf \
  --output /tmp/mke-retrieval-eval/usgs-water-use-2005.pdf
shasum -a 256 /tmp/mke-retrieval-eval/*.pdf
wc -c /tmp/mke-retrieval-eval/*.pdf
```

Expected exact results:

```text
bdb8a5b6c648194e0fcc6f932b70976350bdc864c8187632c47f0cb64a21da4e  .../usgs-volcano-hazards.pdf
ef27346a9f2eab19d438a0740d43c606a9b739147e09d89d1121df294ed3c585  .../usgs-water-use-2005.pdf
563382 .../usgs-volcano-hazards.pdf
400168 .../usgs-water-use-2005.pdf
```

Stop without copying either file if any byte size or checksum differs.

- [x] **Step 4: Copy only the verified PDFs into the fixture directory**

Run:

```bash
mkdir -p tests/fixtures/eval/retrieval
cp /tmp/mke-retrieval-eval/usgs-volcano-hazards.pdf \
  tests/fixtures/eval/retrieval/usgs-volcano-hazards.pdf
cp /tmp/mke-retrieval-eval/usgs-water-use-2005.pdf \
  tests/fixtures/eval/retrieval/usgs-water-use-2005.pdf
```

- [x] **Step 5: Add the exact provenance README**

Create `tests/fixtures/eval/retrieval/README.md` with:

```markdown
# Retrieval Evaluation Fixtures

These fixed text-layer PDFs are committed only for deterministic offline retrieval evaluation.

## `usgs-volcano-hazards.pdf`

- Title: `What are Volcano Hazards?`
- Publisher: U.S. Geological Survey
- Source: https://pubs.usgs.gov/fs/fs002-97/fs00297.pdf
- Retrieved: 2026-06-20
- Pages: 2
- Bytes: 563382
- SHA-256: `bdb8a5b6c648194e0fcc6f932b70976350bdc864c8187632c47f0cb64a21da4e`

## `usgs-water-use-2005.pdf`

- Title: `Summary of Estimated Water Use in the United States in 2005`
- Publisher: U.S. Geological Survey
- Publication page: https://pubs.usgs.gov/fs/2009/3098/
- Source: https://pubs.usgs.gov/fs/2009/3098/pdf/2009-3098.pdf
- Retrieved: 2026-06-20
- Pages: 2
- Bytes: 400168
- SHA-256: `ef27346a9f2eab19d438a0740d43c606a9b739147e09d89d1121df294ed3c585`

## Redistribution

USGS states that reports authored or produced by USGS are in the U.S. public domain:
https://www.usgs.gov/faqs/are-usgs-reportspublications-copyrighted

USGS asks users to acknowledge it as the information source:
https://www.usgs.gov/information-policies-and-instructions/acknowledging-or-crediting-usgs

The exact committed bytes were inspected for extractable third-party copyright labels before
inclusion. Preserve the checksums above; do not silently replace the files with newer upstream
bytes.
```

- [x] **Step 6: Add the frozen manifest**

Create `tests/fixtures/retrieval-eval-v1.json` using the exact document records, query text,
categories, and qrels in the approved spec section `Approved Query And Qrel Inventory`.

Use these exact video file identities:

```json
{
  "primary_file": {
    "path": "video/short-audio.mp4",
    "sha256": "4e3c9feffa503e193165ddf27c40c0e0edf9f256c2e8e1e2d863bd7ba3e1fe49",
    "bytes": 13025
  },
  "supporting_files": [
    {
      "role": "transcript_sidecar",
      "path": "video/short-audio.mp4.mke-transcript.json",
      "sha256": "5688603821b9262f85592912ef957d852ea34448e7292c927ea5071a0668e995",
      "bytes": 506
    }
  ]
}
```

Use no source URL or license fields in the runtime manifest. Provenance belongs in the fixture
README so the runtime schema stays limited to evaluation execution data.

- [x] **Step 7: Run the fixture test to verify GREEN**

Run:

```bash
uv run pytest tests/evaluation/test_fixture_corpus.py -q
git diff --check
```

Expected: `3 passed`; no whitespace errors.

- [x] **Step 8: Commit the fixture task**

Stage only:

```bash
git add \
  tests/evaluation/__init__.py \
  tests/evaluation/test_fixture_corpus.py \
  tests/fixtures/retrieval-eval-v1.json \
  tests/fixtures/eval/retrieval/README.md \
  tests/fixtures/eval/retrieval/usgs-volcano-hazards.pdf \
  tests/fixtures/eval/retrieval/usgs-water-use-2005.pdf
git commit -m "test(eval): add retrieval baseline corpus"
```

---

### Task 2: Implement Strict Manifest Parsing And Fixture Validation

**Files:**
- Create: `src/mke/evaluation/__init__.py`
- Create: `src/mke/evaluation/manifest.py`
- Create: `tests/evaluation/test_manifest.py`

- [x] **Step 1: Write failing parser tests**

Create `tests/evaluation/test_manifest.py` covering:

```python
import json
from pathlib import Path
from collections.abc import Callable

import pytest

from mke.evaluation.manifest import (
    FixtureValidationError,
    ManifestValidationError,
    load_retrieval_manifest,
)


def test_load_checked_in_manifest_has_frozen_shape() -> None:
    manifest = load_retrieval_manifest(Path("tests/fixtures/retrieval-eval-v1.json"))

    assert manifest.schema_version == "mke.retrieval_eval.v1"
    assert manifest.manifest_id == "retrieval-eval-v1"
    assert len(manifest.documents) == 3
    assert len(manifest.queries) == 24
    assert manifest.queries[0].query_id == "volcano-answerable-01"


@pytest.mark.parametrize(
    ("mutation", "cause"),
    [
        (lambda payload: payload.update({"unexpected": True}), "manifest contains unknown fields"),
        (
            lambda payload: payload["queries"].append(payload["queries"][0]),
            "query identifiers must be unique",
        ),
        (
            lambda payload: payload["documents"][0]["primary_file"].update(
                {"path": "../outside.pdf"}
            ),
            "fixture path is invalid",
        ),
        (
            lambda payload: payload["queries"][0].update({"category": "unknown"}),
            "query category is invalid",
        ),
        (
            lambda payload: payload["queries"][0].update({"relevant_locators": []}),
            "answerable query requires relevant locators",
        ),
    ],
)
def test_manifest_rejects_invalid_shapes(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], None],
    cause: str,
) -> None:
    source = Path("tests/fixtures/retrieval-eval-v1.json")
    payload = json.loads(source.read_text())
    mutation(payload)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(ManifestValidationError, match=cause):
        load_retrieval_manifest(path)


def test_manifest_rejects_checksum_mismatch_before_ingest(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.pdf"
    fixture.write_bytes(b"not the approved bytes")
    payload = {
        "schema_version": "mke.retrieval_eval.v1",
        "manifest_id": "test-manifest",
        "documents": [
            {
                "document_id": "document-one",
                "media_type": "application/pdf",
                "primary_file": {
                    "path": "fixture.pdf",
                    "sha256": "0" * 64,
                    "bytes": 22
                },
                "supporting_files": []
            }
        ],
        "queries": [
            {
                "query_id": "answerable-one",
                "text": "searchable token",
                "category": "answerable",
                "relevant_locators": [
                    {
                        "document_id": "document-one",
                        "locator_kind": "page",
                        "locator_start": 1,
                        "locator_end": 1
                    }
                ]
            },
            {
                "query_id": "unanswerable-one",
                "text": "absent token",
                "category": "out_of_corpus",
                "relevant_locators": []
            }
        ]
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(FixtureValidationError, match="fixture checksum does not match"):
        load_retrieval_manifest(path)
```

Also add parameterized tests for malformed IDs, absolute paths, non-lowercase SHA-256, duplicate
document IDs, unknown document/media/file/query/qrel fields, invalid page/timestamp ranges,
unanswerable queries with qrels, missing supporting sidecars, a sidecar path that is not exactly
`<primary path>.mke-transcript.json`, duplicate primary paths or hashes, empty query groups,
manifest count/size bounds, and missing manifest versus invalid JSON errors.

- [x] **Step 2: Run parser tests to verify RED**

Run:

```bash
uv run pytest tests/evaluation/test_manifest.py -q
```

Expected: collection FAIL because `mke.evaluation.manifest` does not exist.

- [x] **Step 3: Implement immutable DTOs and strict parser**

Create `src/mke/evaluation/manifest.py` with:

```python
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

QueryCategory = Literal["answerable", "lexical_confuser", "out_of_corpus"]
LocatorKind = Literal["page", "timestamp_ms"]
_ID_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class ManifestValidationError(ValueError):
    def __init__(self, cause: str, *, subject_id: str | None = None) -> None:
        super().__init__(cause)
        self.cause = cause
        self.subject_id = subject_id


class FixtureValidationError(ManifestValidationError):
    """A valid manifest references missing, unreadable, or mismatched fixture bytes."""


@dataclass(frozen=True)
class FixtureFile:
    path: PurePosixPath
    sha256: str
    bytes: int
    role: str | None = None


@dataclass(frozen=True)
class EvaluationDocument:
    document_id: str
    media_type: Literal["application/pdf", "video/mp4"]
    primary_file: FixtureFile
    supporting_files: tuple[FixtureFile, ...]


@dataclass(frozen=True, order=True)
class StableLocator:
    document_id: str
    locator_kind: LocatorKind
    locator_start: int
    locator_end: int


@dataclass(frozen=True)
class EvaluationQuery:
    query_id: str
    text: str
    category: QueryCategory
    relevant_locators: tuple[StableLocator, ...]


@dataclass(frozen=True)
class RetrievalEvaluationManifest:
    schema_version: str
    manifest_id: str
    root: Path
    documents: tuple[EvaluationDocument, ...]
    queries: tuple[EvaluationQuery, ...]

    def resolve(self, fixture: FixtureFile) -> Path:
        resolved = (self.root / Path(*fixture.path.parts)).resolve()
        if not resolved.is_relative_to(self.root):
            raise ManifestValidationError("fixture path is invalid")
        return resolved


def load_retrieval_manifest(path: Path) -> RetrievalEvaluationManifest:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ManifestValidationError("manifest file is missing") from error
    except OSError as error:
        raise ManifestValidationError("manifest file is not readable") from error
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ManifestValidationError("manifest is not valid JSON") from error
    if not isinstance(raw, dict):
        raise ManifestValidationError("manifest must be a JSON object")
    _require_keys(raw, {"schema_version", "manifest_id", "documents", "queries"}, "manifest")
    if raw["schema_version"] != "mke.retrieval_eval.v1":
        raise ManifestValidationError("manifest schema version is unsupported")
    manifest_id = _identifier(raw["manifest_id"], "manifest identifier is invalid")
    documents = tuple(_document(item) for item in _list(raw["documents"], "documents"))
    queries = tuple(_query(item) for item in _list(raw["queries"], "queries"))
    _require_manifest_bounds(documents, queries)
    _unique((item.document_id for item in documents), "document identifiers must be unique")
    _unique((item.query_id for item in queries), "query identifiers must be unique")
    _unique(
        (str(item.primary_file.path) for item in documents),
        "primary fixture paths must be unique",
    )
    _unique(
        (item.primary_file.sha256 for item in documents),
        "primary fixture checksums must be unique",
    )
    document_ids = {item.document_id for item in documents}
    for query in queries:
        for locator in query.relevant_locators:
            if locator.document_id not in document_ids:
                raise ManifestValidationError(
                    "qrel document identifier is unknown", subject_id=query.query_id
                )
    manifest = RetrievalEvaluationManifest(
        schema_version="mke.retrieval_eval.v1",
        manifest_id=manifest_id,
        root=path.resolve().parent,
        documents=documents,
        queries=queries,
    )
    _validate_fixture_files(manifest)
    return manifest
```

Implement the private helpers in the same file with these exact responsibilities:

- `_require_keys`: require the exact expected key set; reject missing and unknown fields.
- `_list`: require a JSON list.
- `_identifier`: require a bounded string of 1–128 characters matching `_ID_RE`.
- `_fixture_file`: validate role presence by context, relative `PurePosixPath`, SHA-256, and positive
  non-boolean integer byte size.
- `_document`: support only `application/pdf` and `video/mp4`; PDF has no supporting files; video
  has exactly one `transcript_sidecar` whose path is exactly
  `<primary path>.mke-transcript.json`.
- `_query`: validate text type, stripped length 1–1000, current ASCII searchable token,
  category/qrel cardinality, and unique qrels.
- `_locator`: validate exact keys and page/timestamp integer range rules.
- `_unique`: reject duplicate values.
- `_require_manifest_bounds`: require 1–32 documents, 2–1,000 queries, at least one answerable and
  one unanswerable query, and at most 100 MiB of declared primary plus supporting fixture bytes.
- `_validate_fixture_files`: require readable files, exact byte sizes, and streaming SHA-256
  matches. Raise `FixtureValidationError` for these fixture-state failures, while schema, identity,
  path, and qrel-shape failures remain `ManifestValidationError`.
- `snapshot_retrieval_fixtures`: copy each validated file into an evaluator-owned destination while
  hashing, preserve manifest-relative paths and video/sidecar adjacency, revalidate the copied
  bytes, and return an equivalent manifest rooted at the immutable snapshot. If source bytes change
  during the copy, raise `FixtureValidationError`.

Create `src/mke/evaluation/__init__.py` exporting only:

```python
from mke.evaluation.manifest import (
    FixtureValidationError,
    ManifestValidationError,
    RetrievalEvaluationManifest,
    load_retrieval_manifest,
    snapshot_retrieval_fixtures,
)

__all__ = [
    "FixtureValidationError",
    "ManifestValidationError",
    "RetrievalEvaluationManifest",
    "load_retrieval_manifest",
    "snapshot_retrieval_fixtures",
]
```

- [x] **Step 4: Run parser tests to verify GREEN**

Run:

```bash
uv run pytest tests/evaluation/test_fixture_corpus.py tests/evaluation/test_manifest.py -q
uv run pyright
```

Expected: all targeted tests pass; Pyright reports `0 errors`.

- [x] **Step 5: Commit the parser task**

```bash
git add \
  src/mke/evaluation/__init__.py \
  src/mke/evaluation/manifest.py \
  tests/evaluation/test_manifest.py
git commit -m "feat(eval): validate retrieval manifests"
```

---

### Task 3: Add Read-Only Active Evidence Enumeration

**Files:**
- Modify: `src/mke/domain/__init__.py`
- Modify: `src/mke/adapters/sqlite/__init__.py`
- Modify: `src/mke/application/__init__.py`
- Modify: `tests/adapters/test_sqlite_fts.py`

- [x] **Step 1: Write the failing active-Evidence test**

Append to `tests/adapters/test_sqlite_fts.py`:

```python
from pathlib import Path

from mke.application import KnowledgeEngine
from mke.domain import ActiveEvidenceRef
from tests.conftest import PDF_FIXTURES


def test_list_active_evidence_returns_only_current_publication(tmp_path: Path) -> None:
    engine = KnowledgeEngine(tmp_path / "mke.sqlite")
    try:
        initial = engine.ingest_pdf(PDF_FIXTURES / "text-layer.pdf")
        source_id = engine.get_run(initial.run_id).source_id
        engine.reprocess_pdf(PDF_FIXTURES / "text-layer-revised.pdf")

        active = engine.list_active_evidence()

        assert active
        assert {item.source_id for item in active} == {source_id}
        assert active == [
            ActiveEvidenceRef(source_id, "page", 1, 1),
            ActiveEvidenceRef(source_id, "page", 2, 2),
        ]
    finally:
        engine.close()
```

- [x] **Step 2: Run the test to verify RED**

Run:

```bash
uv run pytest tests/adapters/test_sqlite_fts.py::test_list_active_evidence_returns_only_current_publication -q
```

Expected: FAIL because `KnowledgeEngine.list_active_evidence` does not exist.

- [x] **Step 3: Add the store query without modifying Search**

Add the project-owned DTO in `src/mke/domain/__init__.py`:

```python
@dataclass(frozen=True)
class ActiveEvidenceRef:
    source_id: str
    locator_kind: str
    locator_start: int
    locator_end: int
```

Add this method immediately before `SQLiteStore.search`:

```python
def list_active_evidence(self) -> list[ActiveEvidenceRef]:
    rows = self._connection.execute(
        """
        SELECT evidence.source_id, evidence.locator_kind,
               evidence.locator_start, evidence.locator_end
        FROM sources
        JOIN publications
          ON publications.publication_id = sources.active_publication_id
        JOIN evidence
          ON evidence.run_id = publications.run_id
         AND evidence.source_id = sources.source_id
        ORDER BY evidence.source_id, evidence.locator_kind,
                 evidence.locator_start, evidence.locator_end
        """
    ).fetchall()
    return [
        ActiveEvidenceRef(
            source_id=str(row["source_id"]),
            locator_kind=str(row["locator_kind"]),
            locator_start=int(row["locator_start"]),
            locator_end=int(row["locator_end"]),
        )
        for row in rows
    ]
```

Import `ActiveEvidenceRef` from the domain module. Do not refactor or change existing Search
SQL, conversion, or ordering.

- [x] **Step 4: Expose the read-only method through the application facade**

Add immediately before `KnowledgeEngine.search`:

```python
def list_active_evidence(self) -> list[ActiveEvidenceRef]:
    """Return active Evidence for internal diagnostics and evaluation."""
    return self._store.list_active_evidence()
```

Do not expose this method through CLI, MCP, or public reference contracts.

- [x] **Step 5: Run targeted lifecycle and FTS tests**

Run:

```bash
uv run pytest \
  tests/adapters/test_sqlite_fts.py \
  tests/application/test_pdf_publication.py \
  tests/application/test_video_publication.py -q
uv run pyright
```

Expected: all pass; Pyright reports `0 errors`.

- [x] **Step 6: Commit the enumeration task**

```bash
git add \
  src/mke/domain/__init__.py \
  src/mke/adapters/sqlite/__init__.py \
  src/mke/application/__init__.py \
  tests/adapters/test_sqlite_fts.py
git commit -m "feat(eval): expose active evidence for evaluation"
```

---

### Task 4: Implement Pure Retrieval Metrics

**Files:**
- Create: `src/mke/evaluation/metrics.py`
- Create: `tests/evaluation/test_metrics.py`

- [x] **Step 1: Write failing metric tests**

Create `tests/evaluation/test_metrics.py`:

```python
from mke.evaluation.manifest import StableLocator
from mke.evaluation.metrics import QueryMetricInput, calculate_metrics


def _page(document_id: str, page: int) -> StableLocator:
    return StableLocator(document_id, "page", page, page)


def test_metrics_use_macro_recall_and_first_relevant_rank() -> None:
    metrics = calculate_metrics(
        (
            QueryMetricInput(
                category="answerable",
                relevant=(_page("doc", 1), _page("doc", 2)),
                retrieved=(_page("doc", 1), _page("other", 1), _page("doc", 2)),
                ask_status="evidence_found",
            ),
            QueryMetricInput(
                category="answerable",
                relevant=(_page("doc", 3),),
                retrieved=(),
                ask_status="insufficient_evidence",
            ),
            QueryMetricInput(
                category="out_of_corpus",
                relevant=(),
                retrieved=(),
                ask_status="insufficient_evidence",
            ),
        )
    )

    assert metrics.locator_recall_at_1.value == 0.25
    assert metrics.locator_recall_at_3.value == 0.5
    assert metrics.locator_recall_at_5.value == 0.5
    assert metrics.mrr_at_5.value == 0.5
    assert metrics.answerable_zero_hit_rate.value == 0.5
    assert metrics.unanswerable_no_hit_rate.value == 1.0
    assert metrics.ask_refusal_rate.value == 1.0


def test_metrics_round_values_to_six_decimal_places() -> None:
    metrics = calculate_metrics(
        (
            QueryMetricInput(
                category="answerable",
                relevant=(_page("doc", 1), _page("doc", 2), _page("doc", 3)),
                retrieved=(_page("doc", 1),),
                ask_status="evidence_found",
            ),
        )
    )

    assert metrics.locator_recall_at_1.value == 0.333333
    assert metrics.locator_recall_at_1.sum == 0.3333333333333333
    assert metrics.locator_recall_at_1.count == 1
```

Add tests for multiple unanswerable categories, first relevant rank after a non-relevant result,
Search/Ask consistency, and empty answerable/unanswerable group rejection. Under the current
application contract, a non-empty Search result with a refused Ask is impossible and must not be
used as a metric fixture.

- [x] **Step 2: Run metric tests to verify RED**

Run:

```bash
uv run pytest tests/evaluation/test_metrics.py -q
```

Expected: collection FAIL because `mke.evaluation.metrics` does not exist.

- [x] **Step 3: Implement pure metric DTOs and calculation**

Create `src/mke/evaluation/metrics.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mke.evaluation.manifest import QueryCategory, StableLocator

AskStatus = Literal["evidence_found", "insufficient_evidence"]


@dataclass(frozen=True)
class QueryMetricInput:
    category: QueryCategory
    relevant: tuple[StableLocator, ...]
    retrieved: tuple[StableLocator, ...]
    ask_status: AskStatus


@dataclass(frozen=True)
class MetricValue:
    value: float
    sum: float
    count: int


@dataclass(frozen=True)
class RetrievalMetrics:
    locator_recall_at_1: MetricValue
    locator_recall_at_3: MetricValue
    locator_recall_at_5: MetricValue
    mrr_at_5: MetricValue
    answerable_zero_hit_rate: MetricValue
    unanswerable_no_hit_rate: MetricValue
    ask_refusal_rate: MetricValue


def calculate_metrics(inputs: tuple[QueryMetricInput, ...]) -> RetrievalMetrics:
    answerable = tuple(item for item in inputs if item.category == "answerable")
    unanswerable = tuple(item for item in inputs if item.category != "answerable")
    if not answerable or not unanswerable:
        raise ValueError("metrics require answerable and unanswerable queries")

    return RetrievalMetrics(
        locator_recall_at_1=_mean(tuple(_recall(item, 1) for item in answerable)),
        locator_recall_at_3=_mean(tuple(_recall(item, 3) for item in answerable)),
        locator_recall_at_5=_mean(tuple(_recall(item, 5) for item in answerable)),
        mrr_at_5=_mean(tuple(_reciprocal_rank(item) for item in answerable)),
        answerable_zero_hit_rate=_mean(
            tuple(float(not item.retrieved) for item in answerable)
        ),
        unanswerable_no_hit_rate=_mean(
            tuple(float(not item.retrieved) for item in unanswerable)
        ),
        ask_refusal_rate=_mean(
            tuple(float(item.ask_status == "insufficient_evidence") for item in unanswerable)
        ),
    )


def _recall(item: QueryMetricInput, limit: int) -> float:
    relevant = set(item.relevant)
    return len(relevant.intersection(item.retrieved[:limit])) / len(relevant)


def _reciprocal_rank(item: QueryMetricInput) -> float:
    relevant = set(item.relevant)
    for index, locator in enumerate(item.retrieved[:5], start=1):
        if locator in relevant:
            return 1.0 / index
    return 0.0


def _mean(values: tuple[float, ...]) -> MetricValue:
    total = sum(values)
    return MetricValue(value=round(total / len(values), 6), sum=total, count=len(values))
```

- [x] **Step 4: Run metric tests to verify GREEN**

Run:

```bash
uv run pytest tests/evaluation/test_metrics.py -q
uv run pyright
```

Expected: all pass; Pyright reports `0 errors`.

- [x] **Step 5: Commit the metric task**

```bash
git add src/mke/evaluation/metrics.py tests/evaluation/test_metrics.py
git commit -m "feat(eval): calculate retrieval baseline metrics"
```

---

### Task 5: Implement Public-Safe Evaluation Reports

**Files:**
- Create: `src/mke/evaluation/report.py`
- Create: `tests/evaluation/test_report.py`

- [x] **Step 1: Write failing report tests**

Create `tests/evaluation/test_report.py` with a report fixture and assertions that:

```python
import json

from mke.evaluation.manifest import StableLocator
from mke.evaluation.metrics import MetricValue, RetrievalMetrics
from mke.evaluation.report import (
    QueryEvaluationResult,
    RetrievalEvaluationReport,
    render_retrieval_human_report,
    render_retrieval_json_report,
)


def _metrics() -> RetrievalMetrics:
    value = MetricValue(value=0.5, sum=1.0, count=2)
    return RetrievalMetrics(value, value, value, value, value, value, value)


def test_json_report_is_public_safe_and_complete() -> None:
    report = RetrievalEvaluationReport(
        manifest_id="retrieval-eval-v1",
        benchmark_scope="small_english_page_timestamp_corpus",
        quality_gate="none",
        status="passed",
        quality_status="baseline_recorded",
        document_count=3,
        results=(
            QueryEvaluationResult(
                query_id="volcano-answerable-01",
                category="answerable",
                relevant_locator_count=1,
                retrieved_locators=(
                    StableLocator("usgs-volcano-hazards", "page", 1, 1),
                ),
                relevant_retrieved_at_1=1,
                relevant_retrieved_at_3=1,
                relevant_retrieved_at_5=1,
                first_relevant_rank=1,
                ask_status="evidence_found",
            ),
        ),
        metrics=_metrics(),
        integrity_failures=(),
        duration_ms=10,
    )

    rendered = render_retrieval_json_report(report)
    payload = json.loads(rendered)

    assert payload["schema_version"] == "mke.retrieval_eval_report.v1"
    assert payload["quality_status"] == "baseline_recorded"
    assert payload["results"][0]["query_id"] == "volcano-answerable-01"
    assert "query" not in payload["results"][0]
    assert "/Users/" not in rendered
    assert "eruption clouds aviation" not in rendered
```

Also assert:

- the human aggregate line contains every aggregate field from the approved spec;
- human output includes `scope=small_english_page_timestamp_corpus quality_gate=none`;
- one result line per query uses only query ID, category, counts, rank, Ask status, and stable
  locators;
- failed reports include stable `problem`, `cause`, `next_step`, `subject_id`;
- renderers never include Evidence text, random IDs, absolute paths, or traceback strings.

- [x] **Step 2: Run report tests to verify RED**

Run:

```bash
uv run pytest tests/evaluation/test_report.py -q
```

Expected: collection FAIL because `mke.evaluation.report` does not exist.

- [x] **Step 3: Implement immutable report DTOs and renderers**

Create `src/mke/evaluation/report.py` with:

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Literal

from mke.evaluation.manifest import QueryCategory, StableLocator
from mke.evaluation.metrics import AskStatus, RetrievalMetrics

EvaluationStatus = Literal["passed", "failed"]
QualityStatus = Literal["baseline_recorded", "not_recorded"]


@dataclass(frozen=True)
class IntegrityFailure:
    problem: str
    cause: str
    next_step: str
    subject_id: str | None = None


@dataclass(frozen=True)
class QueryEvaluationResult:
    query_id: str
    category: QueryCategory
    relevant_locator_count: int
    retrieved_locators: tuple[StableLocator, ...]
    relevant_retrieved_at_1: int
    relevant_retrieved_at_3: int
    relevant_retrieved_at_5: int
    first_relevant_rank: int | None
    ask_status: AskStatus


@dataclass(frozen=True)
class RetrievalEvaluationReport:
    manifest_id: str
    benchmark_scope: str
    quality_gate: Literal["none"]
    status: EvaluationStatus
    quality_status: QualityStatus
    document_count: int
    results: tuple[QueryEvaluationResult, ...]
    metrics: RetrievalMetrics | None
    integrity_failures: tuple[IntegrityFailure, ...]
    duration_ms: int

    @property
    def query_count(self) -> int:
        return len(self.results)

    @property
    def answerable_count(self) -> int:
        return sum(item.category == "answerable" for item in self.results)

    @property
    def unanswerable_count(self) -> int:
        return self.query_count - self.answerable_count


def render_retrieval_json_report(report: RetrievalEvaluationReport) -> str:
    return json.dumps(_payload(report), indent=2, sort_keys=False)
```

Implement `_payload` explicitly rather than using unrestricted recursive serialization. Serialize
only the approved fields, include `"evaluation": "retrieval"`, and convert `StableLocator` to
`document_id/locator_kind/locator_start/locator_end`.

Implement `render_retrieval_human_report` with:

1. `mke eval retrieval`
2. the approved corpus-scope and quality-gate line,
3. the approved aggregate line with all seven metrics,
4. one bounded line per query result,
5. one bounded line per integrity failure.

When `report.metrics is None`, omit metric fields and use
`quality_status=not_recorded`.

- [x] **Step 4: Run report tests to verify GREEN**

Run:

```bash
uv run pytest tests/evaluation/test_report.py -q
uv run pyright
```

Expected: all pass; Pyright reports `0 errors`.

- [x] **Step 5: Commit the report task**

```bash
git add src/mke/evaluation/report.py tests/evaluation/test_report.py
git commit -m "feat(eval): add retrieval evaluation reports"
```

---

### Task 6: Implement Two-Workspace Evaluation Orchestration

**Files:**
- Create: `src/mke/evaluation/runner.py`
- Create: `tests/evaluation/test_runner.py`
- Modify: `src/mke/evaluation/__init__.py`

- [x] **Step 1: Write failing runner tests**

Create `tests/evaluation/test_runner.py` covering:

```python
from dataclasses import replace
from pathlib import Path

import pytest

from mke.evaluation.manifest import StableLocator, load_retrieval_manifest
from mke.evaluation.runner import run_retrieval_evaluation


def test_checked_in_evaluation_records_complete_deterministic_baseline() -> None:
    report = run_retrieval_evaluation(
        Path("tests/fixtures/retrieval-eval-v1.json")
    )

    assert report.status == "passed"
    assert report.quality_status == "baseline_recorded"
    assert report.document_count == 3
    assert report.query_count == 24
    assert report.answerable_count == 16
    assert report.unanswerable_count == 8
    assert report.metrics is not None
    assert report.integrity_failures == ()
    assert [item.query_id for item in report.results] == [
        query.query_id
        for query in load_retrieval_manifest(
            Path("tests/fixtures/retrieval-eval-v1.json")
        ).queries
    ]


def test_low_quality_is_not_an_integrity_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mke.evaluation.runner._search_locators",
        lambda *args, **kwargs: (),
    )
    monkeypatch.setattr(
        "mke.evaluation.runner._ask_status",
        lambda *args, **kwargs: "insufficient_evidence",
    )

    report = run_retrieval_evaluation(
        Path("tests/fixtures/retrieval-eval-v1.json")
    )

    assert report.status == "passed"
    assert report.quality_status == "baseline_recorded"
    assert report.metrics is not None
    assert report.metrics.locator_recall_at_5.value == 0.0


def test_nondeterministic_order_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def unstable(*args: object, **kwargs: object) -> tuple[StableLocator, ...]:
        nonlocal calls
        calls += 1
        page = 1 if calls < 25 else 2
        return (StableLocator("usgs-volcano-hazards", "page", page, page),)

    monkeypatch.setattr("mke.evaluation.runner._search_locators", unstable)
    monkeypatch.setattr(
        "mke.evaluation.runner._ask_status",
        lambda *args, **kwargs: "evidence_found",
    )

    report = run_retrieval_evaluation(
        Path("tests/fixtures/retrieval-eval-v1.json")
    )

    assert report.status == "failed"
    assert report.quality_status == "not_recorded"
    assert report.integrity_failures[0].problem == "retrieval_eval_nondeterministic"
```

Also add tests for:

- corrupt fixture returns a stable failed report before engine construction;
- unknown qrel locator returns `retrieval_eval_qrel_invalid`;
- failed ingest returns `retrieval_eval_ingest_failed`;
- skipped query returns `retrieval_eval_incomplete`;
- random Run/Source/Evidence IDs do not appear in report results;
- duplicate active Evidence rows for one stable locator return `retrieval_eval_qrel_invalid`;
- Search emptiness and Ask status disagreement returns `retrieval_eval_incomplete`;
- the same immutable fixture snapshot feeds both workspaces;
- temporary directories are removed after success and failure.

- [x] **Step 2: Run runner tests to verify RED**

Run:

```bash
uv run pytest tests/evaluation/test_runner.py -q
```

Expected: collection FAIL because `mke.evaluation.runner` does not exist.

- [x] **Step 3: Implement runner errors and one-workspace execution**

Create `src/mke/evaluation/runner.py` with:

```python
from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from mke.application import KnowledgeEngine
from mke.domain import ActiveEvidenceRef, RunState, SearchResult
from mke.evaluation.manifest import (
    EvaluationDocument,
    EvaluationQuery,
    FixtureValidationError,
    ManifestValidationError,
    RetrievalEvaluationManifest,
    StableLocator,
    load_retrieval_manifest,
    snapshot_retrieval_fixtures,
)
from mke.evaluation.metrics import QueryMetricInput, RetrievalMetrics, calculate_metrics
from mke.evaluation.report import (
    IntegrityFailure,
    QueryEvaluationResult,
    RetrievalEvaluationReport,
)


class EvaluationIntegrityError(RuntimeError):
    def __init__(
        self,
        problem: str,
        cause: str,
        next_step: str,
        *,
        subject_id: str | None = None,
    ) -> None:
        super().__init__(cause)
        self.problem = problem
        self.cause = cause
        self.next_step = next_step
        self.subject_id = subject_id


@dataclass(frozen=True)
class _WorkspaceResult:
    results: tuple[QueryEvaluationResult, ...]
    metrics: RetrievalMetrics


def run_retrieval_evaluation(manifest_path: Path) -> RetrievalEvaluationReport:
    started = time.monotonic()
    manifest_id = "unknown"
    try:
        manifest = load_retrieval_manifest(manifest_path)
        manifest_id = manifest.manifest_id
        with tempfile.TemporaryDirectory(prefix="mke-retrieval-eval-snapshot-") as snapshot:
            staged = snapshot_retrieval_fixtures(manifest, Path(snapshot))
            first = _run_workspace(staged)
            second = _run_workspace(staged)
            _require_deterministic(first, second)
            return RetrievalEvaluationReport(
                manifest_id=manifest.manifest_id,
                benchmark_scope="small_english_page_timestamp_corpus",
                quality_gate="none",
                status="passed",
                quality_status="baseline_recorded",
                document_count=len(manifest.documents),
                results=first.results,
                metrics=first.metrics,
                integrity_failures=(),
                duration_ms=_elapsed_ms(started),
            )
    except FixtureValidationError as error:
        return _failed_report(
            manifest_id=manifest_id,
            problem="retrieval_eval_fixture_invalid",
            cause=error.cause,
            next_step="restore_retrieval_eval_fixture",
            subject_id=error.subject_id,
            started=started,
        )
    except ManifestValidationError as error:
        return _failed_report(
            manifest_id=manifest_id,
            problem="retrieval_eval_manifest_invalid",
            cause=error.cause,
            next_step="fix_retrieval_eval_manifest",
            subject_id=error.subject_id,
            started=started,
        )
    except EvaluationIntegrityError as error:
        return _failed_report(
            manifest_id=manifest_id,
            problem=error.problem,
            cause=error.cause,
            next_step=error.next_step,
            subject_id=error.subject_id,
            started=started,
        )
    except Exception:
        return _failed_report(
            manifest_id=manifest_id,
            problem="retrieval_eval_incomplete",
            cause="retrieval evaluation failed",
            next_step="inspect_retrieval_eval_inputs",
            subject_id=None,
            started=started,
        )
```

Use a properly typed `RetrievalMetrics` field instead of `object` in `_WorkspaceResult`.

Implement `_run_workspace`:

1. Create `TemporaryDirectory(prefix="mke-retrieval-eval-")`.
2. Construct `KnowledgeEngine(temp_root / "mke.sqlite")`.
3. Ingest documents in manifest order.
4. Require `RunState.PUBLISHED`.
5. Record `source_id -> document_id` from `engine.get_run(result.run_id)`.
6. Build the complete active locator multiset from `engine.list_active_evidence()`.
7. Require exactly one active Evidence row per stable locator and every approved qrel in that set.
8. Evaluate every query in manifest order with Search limit `5` and Ask limit `5`.
9. Close the engine in `finally`.
10. Require exactly one result per manifest query.

Use:

```python
def _stable_locator(
    match: SearchResult,
    source_documents: dict[str, str],
) -> StableLocator:
    try:
        document_id = source_documents[match.source_id]
    except KeyError as error:
        raise EvaluationIntegrityError(
            "retrieval_eval_incomplete",
            "retrieved Evidence belongs to an unknown document",
            "inspect_retrieval_eval_inputs",
        ) from error
    return StableLocator(
        document_id=document_id,
        locator_kind=match.locator_kind,  # validate/assert page or timestamp_ms
        locator_start=match.locator_start,
        locator_end=match.locator_end,
    )
```

`_search_locators` must call only `engine.search(query.text, limit=5)`.
`_ask_status` must call only `engine.ask(query.text, limit=5)` and return its status.

For each query, calculate counts at 1/3/5 and first relevant rank from stable locators. Feed the
same stable locators and Ask status to `calculate_metrics`. Require
`ask.status == "insufficient_evidence"` exactly when Search returns no rows; disagreement is
`retrieval_eval_incomplete`.

- [x] **Step 4: Implement deterministic comparison and failed report helpers**

Compare only:

- ordered `QueryEvaluationResult` fields,
- stable locators,
- non-duration metrics.

Do not compare random IDs or duration.

Use stable failure causes:

```text
fixture checksum does not match
fixture byte size does not match
document ingest did not publish
qrel does not resolve to active Evidence
active Evidence locator is not unique
Search and Ask results disagree
retrieval evaluation did not execute every query
retrieval evaluation results are nondeterministic
retrieval evaluation failed
```

`_failed_report` must create a report with:

- `benchmark_scope="small_english_page_timestamp_corpus"`
- `quality_gate="none"`
- `status="failed"`
- `quality_status="not_recorded"`
- no metrics,
- no query results,
- one `IntegrityFailure`.

- [x] **Step 5: Export runner/report functions**

Update `src/mke/evaluation/__init__.py` to export:

```python
from mke.evaluation.report import (
    render_retrieval_human_report,
    render_retrieval_json_report,
)
from mke.evaluation.runner import run_retrieval_evaluation
```

Add those names to `__all__`.

- [x] **Step 6: Run runner and full evaluation tests**

Run:

```bash
uv run pytest tests/evaluation -q
uv run pyright
```

Expected: all pass; Pyright reports `0 errors`.

- [x] **Step 7: Commit the runner task**

```bash
git add \
  src/mke/evaluation/__init__.py \
  src/mke/evaluation/runner.py \
  tests/evaluation/test_runner.py
git commit -m "feat(eval): run deterministic retrieval baseline"
```

---

### Task 7: Add The CLI Contract And Required CI Gate

**Files:**
- Modify: `src/mke/cli.py`
- Create: `tests/interfaces/test_cli_evaluation.py`
- Modify: `.github/workflows/ci.yml`

- [x] **Step 1: Write failing CLI tests**

Create `tests/interfaces/test_cli_evaluation.py`:

```python
import json
from pathlib import Path

import pytest
from pytest import CaptureFixture

from mke.cli import main

MANIFEST = Path("tests/fixtures/retrieval-eval-v1.json")


def test_cli_eval_retrieval_outputs_human_baseline(
    capsys: CaptureFixture[str],
) -> None:
    assert main(["eval", "retrieval", "--manifest", str(MANIFEST)]) == 0

    output = capsys.readouterr()
    assert output.err == ""
    assert "mke eval retrieval" in output.out
    assert "scope=small_english_page_timestamp_corpus quality_gate=none" in output.out
    assert "status=passed quality_status=baseline_recorded" in output.out
    assert "documents=3 queries=24 answerable=16 unanswerable=8" in output.out
    assert "query_id=volcano-answerable-01 category=answerable" in output.out
    assert "/Users/" not in output.out
    assert "eruption clouds aviation" not in output.out


def test_cli_eval_retrieval_outputs_one_json_object(
    capsys: CaptureFixture[str],
) -> None:
    assert main(["eval", "retrieval", "--manifest", str(MANIFEST), "--json"]) == 0

    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert output.err == ""
    assert payload["evaluation"] == "retrieval"
    assert payload["benchmark_scope"] == "small_english_page_timestamp_corpus"
    assert payload["quality_gate"] == "none"
    assert payload["status"] == "passed"
    assert payload["quality_status"] == "baseline_recorded"
    assert payload["queries"] == 24
    assert payload["integrity_failures"] == []


def test_cli_eval_integrity_failure_is_exit_one_and_redacted(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    missing = tmp_path / "private" / "missing.json"

    assert main(["eval", "retrieval", "--manifest", str(missing), "--json"]) == 1

    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert output.err == ""
    assert payload["status"] == "failed"
    assert payload["integrity_failures"][0]["problem"] == (
        "retrieval_eval_manifest_invalid"
    )
    assert str(tmp_path) not in output.out
    assert "Traceback" not in output.out


def test_cli_eval_requires_manifest_as_usage_error(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["eval", "retrieval"])

    assert error.value.code == 2
    assert "required" in capsys.readouterr().err


def test_cli_eval_retrieval_help_documents_required_manifest(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        main(["eval", "retrieval", "--help"])

    assert error.value.code == 0
    output = capsys.readouterr()
    assert "--manifest" in output.out
    assert "--json" in output.out
    assert "small English" in output.out
```

Also add contract tests that:

- explicit global `--db` with `eval` exits `2` instead of being silently ignored;
- evaluation creates no current-directory `mke.sqlite`;
- monkeypatched human and JSON renderers that raise return exit `1` with a fixed redacted failed
  report, no traceback, and no absolute path;
- missing manifest and invalid JSON return distinct stable causes.

- [x] **Step 2: Run CLI tests to verify RED**

Run:

```bash
uv run pytest tests/interfaces/test_cli_evaluation.py -q
```

Expected: FAIL because `eval` is not a recognized subcommand.

- [x] **Step 3: Add the CLI parser and dispatch**

Import the evaluation exports in `src/mke/cli.py`, then add:

```python
evaluation = subcommands.add_parser("eval")
evaluation_subcommands = evaluation.add_subparsers(
    dest="evaluation_command", required=True
)
retrieval = evaluation_subcommands.add_parser(
    "retrieval",
    description=(
        "Record the current baseline on a small English page/timestamp corpus; "
        "no retrieval-quality threshold is applied."
    ),
)
retrieval.add_argument(
    "--manifest",
    type=Path,
    required=True,
    help="external retrieval-evaluation manifest",
)
retrieval.add_argument("--json", action="store_true", dest="json_output")
```

Capture the raw argv before parsing. If the parsed command is `eval` and raw argv contains `--db`
or `--db=...`, call `parser.error("eval uses two temporary workspaces; --db is not supported")`.
This keeps the E1 change local instead of moving the existing global option for every command.

Dispatch before runtime configuration:

```python
if args.command == "eval":
    if args.evaluation_command == "retrieval":
        report = run_retrieval_evaluation(args.manifest)
        rendered, rendering_failed = _render_retrieval_report_safely(
            report,
            json_output=args.json_output,
        )
        print(rendered)
        return 0 if report.status == "passed" and not rendering_failed else 1
    parser.error("unsupported evaluation command")
```

Import the retrieval-specific renderer names directly; do not create generic renderer aliases.
`_render_retrieval_report_safely` catches any renderer exception and returns one fixed failed
human line or one fixed JSON object with:

```text
problem=retrieval_eval_incomplete
cause=retrieval evaluation report could not be rendered
next_step=inspect_retrieval_eval_inputs
```

The fallback contains no exception text, path, query, Evidence, or host detail.

- [x] **Step 4: Keep evaluation failures inside the evaluation report contract**

The evaluation runner already renders stable `problem`, `cause`, `next_step`, and optional
`subject_id` fields. Do not route those failures through `interfaces/public_errors.py`: doing so
would couple a self-contained report to the CLI/MCP operation-error allowlist and would discard
the evaluation-specific problem classification. Keep dynamic IDs in `subject_id`; do not
concatenate IDs or paths into `cause`.

- [x] **Step 5: Run CLI tests to verify GREEN**

Run:

```bash
uv run pytest \
  tests/interfaces/test_cli_evaluation.py \
  tests/interfaces/test_cli_error_contract.py \
  tests/evaluation -q
uv run pyright
```

Expected: all pass; Pyright reports `0 errors`.

- [x] **Step 6: Add required source-tree and wheel-installed CI evaluation**

After `uv run pyright`, add:

```yaml
      - name: Run retrieval evaluation baseline
        run: |
          uv run mke eval retrieval \
            --manifest tests/fixtures/retrieval-eval-v1.json \
            --json > /tmp/mke-retrieval-eval.json
          python - <<'PY'
          import json
          payload = json.load(open("/tmp/mke-retrieval-eval.json"))
          assert payload["status"] == "passed"
          assert payload["quality_status"] == "baseline_recorded"
          assert payload["documents"] == 3
          assert payload["queries"] == 24
          assert payload["answerable"] == 16
          assert payload["unanswerable"] == 8
          assert payload["integrity_failures"] == []
          print(json.dumps(payload["metrics"], sort_keys=True))
          PY
```

After the core wheel install and `mke demo --verify`, add:

```yaml
          (
            cd "$RUNNER_TEMP"
            /tmp/mke-wheel-env/bin/mke eval retrieval \
              --manifest "$GITHUB_WORKSPACE/tests/fixtures/retrieval-eval-v1.json" \
              --json > /tmp/mke-wheel-retrieval-eval.json
          )
          python - <<'PY'
          import json
          payload = json.load(open("/tmp/mke-wheel-retrieval-eval.json"))
          assert payload["status"] == "passed"
          assert payload["quality_status"] == "baseline_recorded"
          assert payload["queries"] == 24
          PY
```

Validate `benchmarks/retrieval/retrieval-eval-v1-baseline.json` as JSON and require the expected
baseline schema, manifest ID, manifest checksum, fixture checksums, environment fields, metrics,
per-query results, and no duration. Do not compare current scores to the canonical artifact and do
not assert exact metric values.

- [x] **Step 7: Run the complete local verification set**

Run:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke eval retrieval --manifest tests/fixtures/retrieval-eval-v1.json
uv run mke eval retrieval --manifest tests/fixtures/retrieval-eval-v1.json --json \
  > /tmp/mke-retrieval-eval.json
python -m json.tool /tmp/mke-retrieval-eval.json >/dev/null
uv run mke proof run
uv run mke demo --verify
git diff --check
```

Expected: all commands pass. Record the actual test count and observed metrics; do not invent them
in advance.

- [x] **Step 8: Commit the CLI and CI task**

```bash
git add \
  src/mke/cli.py \
  tests/interfaces/test_cli_evaluation.py \
  .github/workflows/ci.yml
git commit -m "feat(cli): add retrieval evaluation baseline"
```

---

### Task 8: Record The Baseline, Complete Documentation, And Prepare Review

**Files:**
- Create: `benchmarks/retrieval/retrieval-eval-v1-baseline.json`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `docs/README.md`
- Modify: `docs/reference/cli.md`
- Create: `docs/how-to/run-retrieval-evaluation.md`
- Create: `docs/superpowers/reviews/2026-06-20-retrieval-evaluation-baseline-review.md`
- Modify: `docs/superpowers/specs/2026-06-20-retrieval-evaluation-baseline-design.md`
- Modify: `docs/superpowers/plans/2026-06-20-retrieval-evaluation-baseline-implementation.md`

- [x] **Step 1: Run the final baseline and capture only public-safe values**

Run:

```bash
uv run mke eval retrieval \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --json > /tmp/mke-retrieval-eval-final.json
python - <<'PY'
import json
payload = json.load(open("/tmp/mke-retrieval-eval-final.json"))
print(json.dumps({
    "manifest_id": payload["manifest_id"],
    "documents": payload["documents"],
    "queries": payload["queries"],
    "answerable": payload["answerable"],
    "unanswerable": payload["unanswerable"],
    "metrics": payload["metrics"],
    "integrity_failures": payload["integrity_failures"],
}, indent=2))
PY
```

Use these actual values in documentation. Do not record `duration_ms` as a product performance
claim.

- [x] **Step 2: Write the canonical machine-readable baseline artifact**

Create `benchmarks/retrieval/retrieval-eval-v1-baseline.json` from the successful final report.
Use schema `mke.retrieval_eval_baseline.v1` and include only public-safe deterministic fields:

- baseline schema and `retrieval-eval-v1` manifest ID;
- manifest SHA-256 and all primary/supporting fixture SHA-256 values;
- `main` base SHA and the Task 7 evaluation-code commit;
- Python, SQLite, and PyMuPDF versions from the verified run;
- report schema, corpus scope, quality gate, document/query counts, category counts, metrics, and
  per-query outcomes;
- known answerable queries with no relevant locator at rank 5 and unanswerable false positives.

Omit duration, absolute paths, query text, Evidence text, random IDs, environment variables, and
host identity. Validate the JSON and verify it contains none of those fields. This artifact is a
reviewed observation for later comparison; CI validates shape and provenance but does not require
future scores to match it.

- [x] **Step 3: Write the operator how-to**

Create `docs/how-to/run-retrieval-evaluation.md` covering:

- prerequisite `uv sync --locked`;
- human and JSON commands;
- `status` versus `quality_status`;
- corpus scope and `quality_gate=none`;
- metric definitions;
- integrity exit codes `0/1/2`;
- offline/checksum behavior;
- how to read answerable misses, lexical confusers, and refusal rate;
- that `ask_refusal_rate` is derived from Search no-hit behavior in E1;
- why low baseline scores do not fail E1;
- explicit non-scope: algorithm improvement, private corpus, CJK, OCR, latency benchmark;
- source-tree and wheel-installed commands with an explicit external manifest;
- how to capture JSON before and after a retrieval change and compare only matching manifest/report
  versions;
- the canonical baseline artifact path and why it is not a quality gate.

Include copy-paste commands:

```bash
uv run mke eval retrieval \
  --manifest tests/fixtures/retrieval-eval-v1.json

uv run mke eval retrieval \
  --manifest tests/fixtures/retrieval-eval-v1.json \
  --json | python -m json.tool
```

Do not add a built-in default manifest, `--output`, or `--compare` command in E1.

- [x] **Step 4: Update public navigation and CLI reference**

Update:

- README current status: distinguish lifecycle proof from retrieval baseline.
- README_CN with equivalent claims and boundaries.
- `docs/README.md`: link the how-to, spec, plan, and durable review.
- `docs/reference/cli.md`: exact syntax, output fields, errors, and exit codes.

Do not claim hybrid retrieval, semantic retrieval, stable product quality, private-corpus quality,
or CJK support.

- [x] **Step 5: Record the observed baseline and known misses**

Add a section to the how-to or a dedicated subsection in the durable review with:

- `main` base SHA and E1 branch HEAD;
- manifest ID and three document identities;
- actual metrics;
- every answerable query ID with no relevant locator in the first five results;
- every unanswerable false-positive query ID;
- whether Ask refused each unanswerable query;
- explicit statement that scores apply only to `retrieval-eval-v1`.

Do not include query text in normal command output. Documentation may link to the committed manifest
as the source of query text.

- [x] **Step 6: Run `gstack-document-release` audit**

Use the document-release skill against the complete branch diff. Apply only changes within E1
scope. Do not let the audit create a PR, push, version bump, or release.

- [x] **Step 7: Run the requested lightweight self-check instead of full gstack-review**

Execution window stops with a clean local branch after implementation and full verification.
Planning window runs one authoritative `gstack-review` against:

- approved spec,
- this plan,
- actual branch diff,
- fixture provenance/checksums,
- command evidence.

Persist public-neutral findings in:

`docs/superpowers/reviews/2026-06-20-retrieval-evaluation-baseline-review.md`

If findings exist, return them to the execution window for
`superpowers:receiving-code-review`, targeted fixes, full verification, and targeted re-review.

- [x] **Step 8: Run final verification after all review fixes**

Run:

```bash
uv run pytest -q
uv run ruff check .
uv run pyright
uv build
uv run mke eval retrieval --manifest tests/fixtures/retrieval-eval-v1.json
uv run mke eval retrieval --manifest tests/fixtures/retrieval-eval-v1.json --json \
  > /tmp/mke-retrieval-eval-final.json
python -m json.tool /tmp/mke-retrieval-eval-final.json >/dev/null
python -m json.tool benchmarks/retrieval/retrieval-eval-v1-baseline.json >/dev/null
uv run mke proof run
uv run mke demo --verify
git diff --check main...HEAD
git status --short
```

Expected:

- all checks pass;
- evaluation integrity passes for 3 documents and 24 queries;
- worktree is clean after the final commit;
- no model download or network access occurs during evaluation;
- no exact metric threshold is required.

- [x] **Step 9: Mark the spec and plan complete**

Update the design status to the actual merged PR and date only after merge.

Before PR creation, update this plan with:

- completed checkboxes,
- actual verification results,
- actual baseline metrics,
- durable review result,
- remaining risks.

- [x] **Step 10: Commit documentation and completion records**

```bash
git add \
  benchmarks/retrieval/retrieval-eval-v1-baseline.json \
  README.md \
  README_CN.md \
  docs/README.md \
  docs/reference/cli.md \
  docs/how-to/run-retrieval-evaluation.md \
  docs/superpowers/specs/2026-06-20-retrieval-evaluation-baseline-design.md \
  docs/superpowers/plans/2026-06-20-retrieval-evaluation-baseline-implementation.md \
  docs/superpowers/reviews/2026-06-20-retrieval-evaluation-baseline-review.md
git commit -m "docs(eval): document retrieval baseline"
```

---

## Required Handoff From Execution To Planning Window

Return:

- branch name and worktree path;
- base SHA and HEAD;
- atomic commit list;
- clean `git status`;
- complete branch diff stat;
- fixture byte sizes and SHA-256 values;
- actual metric report;
- test, Ruff, Pyright, build, eval, proof, demo, and diff-check results;
- document-release result;
- explicit confirmation that Search/Ask/Publication behavior was not changed;
- explicit confirmation that evaluation runtime made no network call;
- remaining risks and known baseline misses;
- no push and no PR until the planning-window review is clean and the user authorizes publication.

## Implementation Results

- Branch: `codex/retrieval-eval-baseline`.
- Main merge base: `721784eabcb9fbb737166578010c9e1a46a25fef`.
- Implementation start: `3992b0e9371d1a8c9e019d3bbe2b32aac9665914`.
- Evaluation-code commit: `79bafb07ac592b684e6ceab15dc389dc33702978`.
- Corpus: 3 documents and 24 queries (`16` answerable, `8` unanswerable).
- Metrics: Recall@1 `0.875000`; Recall@3/5 `0.937500`; MRR@5 `0.937500`;
  answerable zero-hit `0.062500`; unanswerable no-hit and Ask refusal `1.000000`.
- Answerable miss at rank 5: `water-answerable-01`.
- Unanswerable false positives: none.
- Verification: `527 passed, 1 skipped`; Ruff passed; Pyright `0 errors`; build, human/JSON
  evaluation, product proof, demo, canonical artifact validation, CI YAML parse, and diff check
  passed.
- Documentation audit: reference, how-to, README, docs navigation, architecture, fixture
  provenance, and canonical artifact coverage present; no broken links or unresolved doc debt.
- Review: lightweight execution self-check completed; full `gstack-review` intentionally not run
  per user instruction.
- Remaining risks: small English corpus, coarse macro resolution, page/timestamp segmentation
  dependency, and environment-specific SQLite determinism.
- Authoritative review remediation: corrected canonical code provenance; added a project-owned
  artifact validator that derives manifest/fixture identity and validates code, environment,
  metrics, results, and query identity without score gating; added fixture mutation regression
  coverage for the validation-to-snapshot interval.
- Targeted re-review remediation: replaced runtime Git ancestry requirements with fixed historical
  audit metadata plus a durable content identity derived from the exact evaluation/retrieval files,
  allowing validation after squash landing in a shallow fresh clone with deleted feature history;
  converted malformed locator integer parsing into a redacted `BaselineValidationError` at the
  module CLI boundary.

## Autoplan Review Record

### Premise Challenge And Scope Decision

The premise “measure before improving retrieval” holds. The stronger premise “this E1 corpus can
select among CJK tokenization, semantic retrieval, fusion, and reranking” does not. The corrected
claim is:

> E1 is a coarse, deterministic observation and regression baseline for the current English
> page/timestamp retrieval contract. It is not an algorithm-selection benchmark.

The stage remains the smallest useful step because no repository-visible query/qrel baseline
currently exists. Expanding it into a large benchmark would delay evidence capture and blur the
causal baseline.

### What Already Exists

- active-Publication-only FTS5 Search and evidence-only Ask;
- page and timestamp Evidence through normal PDF/video ingest;
- deterministic sidecar video fixture and completed real-transcription proof;
- product proof with human/JSON reporting and redaction tests;
- source-tree and isolated-wheel CI patterns;
- strict Run/Publication failure isolation.

E1 reuses these contracts. It does not duplicate FTS SQL, create a retrieval adapter, or depend on
proof runner/report DTOs.

### Dream State Delta

```text
today
  product proof says lifecycle/contracts work
  retrieval quality is anecdotal

E1
  fixed public corpus + qrels
  deterministic current-behavior report
  reviewed canonical baseline artifact

later decision-specific evaluation
  expanded development/holdout slices
  candidate quality + local resource costs
  explicit improvement/regression gates
```

E1 closes the first delta only.

### CEO Review Coverage

| Area | Result |
|---|---|
| User problem | Confirmed: contributors lack reproducible retrieval evidence. |
| Scope | Held to baseline; algorithm implementation remains excluded. |
| Evidence strength | Narrowed: small English corpus, coarse macro signal, no statistical inference. |
| Existing leverage | Reuses normal ingest, Search, Ask, fixtures, proof/CI patterns. |
| Alternatives | Proof integration, runtime downloads, private corpus, and large benchmark rejected or deferred. |
| Temporal sequencing | Baseline first; expanded candidate protocol before tuning later algorithms. |
| Reversibility | Additive package/CLI/docs; rollback removes the evaluator without migration. |
| Public claims | Scores apply only to `retrieval-eval-v1`; no CJK/private-corpus/product-quality claim. |
| Failure value | Low scores are useful observations; only integrity failures block completion. |
| Six-month regret | Canonical artifact and versioned contracts preserve evidence without freezing quality. |

### CEO Voice Consensus

| Topic | Codex | Claude | Decision |
|---|---|---|---|
| Baseline before retrieval change | Agree | Agree | Keep E1. |
| Broad algorithm-selection claim | Reject | Reject | Narrow the claim. |
| Ask refusal independence | Derived | Derived | Keep only as contract observation. |
| Small corpus limitation | Must be explicit | Must be explicit | Add coarse-signal boundary. |
| Large benchmark expansion now | Recommend expansion or narrower claim | Prefer targeted corrections | Hold scope; defer expanded protocol. |
| Public/private boundary | Remove local restore path | Verify all fixture provenance | Sanitize public docs and preserve local-only artifacts. |

### Engineering Scope Challenge

The original plan reused `SearchResult` for active-Evidence enumeration, validated source fixtures
before reopening them for ingest, allowed ambiguous duplicate locators after future chunking, and
listed renderer failure as a gate without a safe rendering boundary. Those are real contract gaps,
not reasons to expand retrieval scope.

The engineering correction adds only the seams required to make the approved baseline trustworthy:
a narrow DTO, immutable fixture snapshot, locator uniqueness, Search/Ask consistency, safe renderer
fallback, bounded manifests, and a canonical reviewed artifact.

### Architecture And Data Flow

```text
external JSON manifest + checksummed fixtures
                      |
                      v
 strict schema / limits / path / Asset validation
                      |
                      v
      immutable revalidated fixture snapshot
                      |
            +---------+---------+
            |                   |
            v                   v
    fresh workspace A   fresh workspace B
            |                   |
 normal ingest -> active Publication/Evidence
            |                   |
 ActiveEvidenceRef qrel/uniqueness validation
            |                   |
 current Search + current evidence-only Ask
            +---------+---------+
                      |
 ordered stable-locator + non-duration comparison
                      |
 public-safe report + canonical baseline artifact
```

`mke.proof` stays separate because its cases, sequencing, and lifecycle assertions differ from
external-manifest qrels and retrieval metrics.

### Test Coverage Flow

```text
exact PDF/video bytes and provenance
  -> strict manifest, bounds, adjacency, duplicate Asset tests
  -> immutable snapshot / mutation tests
  -> active-Publication narrow DTO and stale exclusion
  -> qrel existence / stable-locator uniqueness
  -> pure metrics / derived Ask consistency
  -> report completeness / redaction / renderer fallback
  -> two-workspace determinism / cleanup
  -> CLI human / JSON / help / exit / explicit --db rejection
  -> source-tree CI / external-manifest isolated wheel CI
  -> canonical artifact schema and provenance
  -> full suite / Ruff / Pyright / build / proof / demo
```

A detailed local engineering test-plan artifact was also produced outside the repository; the
public plan above is the durable execution source.

### Failure Modes And Recovery

| Failure mode | Detection | Public result | Recovery |
|---|---|---|---|
| Invalid manifest schema, limits, or qrel shape | Strict parser before snapshot | `retrieval_eval_manifest_invalid` | Fix the manifest and rerun |
| Missing, mismatched, or mutating fixture bytes | Snapshot size/SHA-256 verification | `retrieval_eval_fixture_invalid` | Restore exact bytes |
| Duplicate manifest Asset identity | Path/SHA uniqueness validation | `retrieval_eval_manifest_invalid` | Use distinct documents |
| Ingest does not publish | Run-state check | `retrieval_eval_ingest_failed` | Inspect the named document |
| Qrel missing or active locator duplicated | `ActiveEvidenceRef` multiset | `retrieval_eval_qrel_invalid` | Correct qrel/segmentation |
| Search and Ask disagree | Per-query consistency gate | `retrieval_eval_incomplete` | Inspect current application contract |
| Query execution is partial | Result count and ID order | `retrieval_eval_incomplete` | Inspect evaluator execution |
| Fresh workspaces disagree | Ordered result/metric comparison | `retrieval_eval_nondeterministic` | Investigate ordering/state leakage |
| Renderer raises | CLI safe-render boundary | Fixed redacted failed report | Inspect renderer locally |
| Unexpected exception | Final redacted fallback | `retrieval_eval_incomplete` | Inspect local diagnostics |
| Low retrieval quality | Metrics only | `status=passed`, `quality_status=baseline_recorded` | Use misses to design later evaluation |

### Error And Rescue Contract

| Layer | Error boundary | Rescue behavior |
|---|---|---|
| argparse | Missing manifest, unsupported command, explicit `--db` | Exit `2` with usage |
| manifest | JSON, schema, identity, bounds, paths, qrels | Stable failed report; no engine |
| fixture snapshot | Readability, size, checksum, mutation | Stable fixture-invalid report; no ingest |
| runner | Ingest, qrel, completeness, consistency, determinism | Stable failed report; cleanup |
| renderer | Human/JSON serialization | Fixed redacted fallback and exit `1` |
| unknown | Unclassified exception | Fixed redacted cause and exit `1` |

### Engineering Parallelization

After the fixture task, manifest/snapshot parsing, the active-Evidence DTO/query, and pure
metrics/report DTOs can be implemented independently. Runner integration must follow those seams.
CLI/CI and documentation/artifact work can then proceed in parallel before final verification and
authoritative pre-landing review.

### Engineering Voice Consensus

| Topic | Codex | Claude | Decision |
|---|---|---|---|
| Active-Evidence type | Narrow DTO required | `SearchResult` acceptable but narrow DTO cleaner | Use narrow DTO. |
| Renderer names | Retrieval-specific | Retrieval-specific | Rename. |
| Canonical JSON artifact | Required | Required | Add reviewed artifact without score gate. |
| Ask refusal | Derived and consistency-gated | Derived and document it | Add consistency gate. |
| Exact locators after chunking | New contract required | New manifest version required | Limit E1 comparability. |
| Proof/evaluation reuse | Keep separate | Keep separate | No shared base. |
| Fixture mutation interval | Snapshot required | No blocker identified | Add snapshot as defense-in-depth. |

### Developer Empathy Narrative

A repository contributor wants one honest answer before editing retrieval. The expected path is
`uv sync --locked` followed by one documented command with an explicit manifest. The result must
make three facts immediate: integrity passed, no quality gate exists, and the corpus is a small
English page/timestamp slice. The contributor can then capture JSON, inspect miss IDs without
leaking content, and compare a later run only when manifest/report versions match.

### Developer Journey

| Stage | Required experience |
|---|---|
| Discover | README, docs index, and `mke --help` distinguish proof from evaluation. |
| Install | Core dependencies only; no model or fixture download at runtime. |
| Understand fixtures | Provenance, checksums, manifest identity, and narrow corpus are explicit. |
| Run | Copy-paste source-tree and wheel commands use an explicit external manifest. |
| Interpret | Scope line, all seven metrics, `quality_gate=none`, and exit semantics are visible. |
| Debug | Stable query IDs, locator summaries, and `problem/cause/next_step`; no raw content. |
| CI integrate | JSON integrity is validated and metrics are printed; exact scores are not gated. |
| Compare | Canonical artifact and documented before/after JSON flow require matching versions. |
| Upgrade | Manifest, report, environment, and Evidence-segmentation boundaries are explicit. |

### DX Scores

| Dimension | Before corrections | After plan corrections |
|---|---:|---:|
| Discoverability | 6/10 | 8/10 |
| Time to first success | 7/10 | 8/10 |
| Mental model | 6/10 | 9/10 |
| Errors and recovery | 7/10 | 9/10 |
| Output contract | 8/10 | 9/10 |
| Documentation | 7/10 | 9/10 |
| CI usability | 8/10 | 9/10 |
| Upgrade comparability | 4/10 | 8/10 |

Target time to first trustworthy baseline: one documented command after `uv sync --locked`.

### DX Implementation Checklist

- [x] `--help` states the small English corpus and absence of a quality threshold.
- [x] Explicit manifest is required and documented for source-tree and wheel flows.
- [x] Explicit global `--db` with evaluation exits `2`.
- [x] Human output contains scope, quality gate, all metrics, query IDs, and stable locators.
- [x] JSON is one versioned object with no raw query/Evidence text or private paths.
- [x] Missing manifest and invalid JSON produce distinct stable causes.
- [x] Renderer failure produces a fixed redacted report and exit `1`.
- [x] Canonical baseline JSON is public-safe, deterministic, and duration-free.
- [x] How-to documents before/after comparison and version matching.
- [x] README and docs do not generalize scores to CJK, private corpora, OCR, or semantic retrieval.

### DX Voice Consensus

| Topic | Codex | Claude | Decision |
|---|---|---|---|
| Corpus limitations | Put in help/output/docs | Put in output/docs | Add across public surfaces. |
| `--db` | Reject for eval | Do not silently ignore | Reject explicitly. |
| Missing-manifest error | Distinguish it | Distinguish it | Add stable cause. |
| Canonical artifact | Required | Useful and warranted | Add it. |
| Default manifest | Prefer built-in | Keep explicit required path | Keep explicit path; avoid packaging expansion. |
| Wheel corpus | Prefer self-contained | External path is acceptable | Wheel verifies installed code with external manifest. |
| Default query detail | Prefer misses by default | Per-query lines acceptable | Keep approved per-query output. |

### NOT In Scope

- retrieval algorithm changes, embeddings, `sqlite-vec`, fusion, RRF, or reranking;
- Unicode/CJK evaluation or claims;
- Passage chunking, graded qrels, nDCG, large ranking corpora, or statistical significance;
- built-in wheel corpus, default manifest discovery, `--output`, or `--compare`;
- private corpus, OCR, real-ASR quality, latency/throughput benchmarking;
- HTTP, UI, hosted evaluation, or external telemetry.

### Cross-Phase Themes

- **Claim discipline:** CEO and DX independently required the small-English/no-quality-gate
  boundary to be visible.
- **Comparability:** CEO, engineering, and DX independently required versioned limits and a durable
  machine-readable baseline.
- **Contract minimization:** engineering and DX independently favored narrow DTOs, specific
  renderer names, explicit manifest input, and no hidden `--db` behavior.
- **Future segmentation:** CEO and engineering independently found that exact locator qrels cannot
  survive Passage chunking without a new protocol.

### Completion Summary

- CEO: scope held; broad algorithm-selection claim removed.
- Design: skipped; no UI scope.
- Engineering: data flow, contracts, failure modes, tests, performance, rollback, and execution
  order reviewed against actual code.
- DX: contributor journey, output semantics, errors, documentation, CI, and upgrade comparability
  reviewed.
- Independent voices: Codex and Claude completed for all applicable phases.
- Remaining taste decisions: none; explicit-manifest source-checkout benchmark remains the approved
  E1 product boundary.

### Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---:|---|---|---|---|---|---|
| 1 | CEO | Keep E1 baseline-only | Auto | Preserve causal evidence | Measure current FTS5 before changing it | Implement algorithm now |
| 2 | CEO | Narrow follow-up claims | Auto | Claims follow evidence | Small English corpus cannot select broad algorithms | Treat E1 as universal benchmark |
| 3 | CEO | Defer expanded dev/holdout sets | Auto | Smallest useful stage | Needed for later tuning, not current observation | Expand E1 immediately |
| 4 | Eng | Add `ActiveEvidenceRef` | Auto | Least data exposure | Qrel validation needs locators, not text/random IDs | Reuse `SearchResult` |
| 5 | Eng | Snapshot fixture bytes | Auto | Validate what is executed | Removes validation-to-ingest mutation interval | Reopen source files directly |
| 6 | Eng | Require stable-locator uniqueness | Auto | Metrics must be unambiguous | Current qrels assume one Evidence per locator | Ignore future chunking ambiguity |
| 7 | Eng | Treat Ask refusal as derived | Auto | Avoid duplicate claims | Ask delegates to Search at the same limit | Present as independent quality |
| 8 | Eng | Add safe renderer fallback | Auto | Fail closed publicly | Serialization is an integrity boundary | Allow traceback/uncaught error |
| 9 | Eng | Keep proof/eval separate | Auto | Avoid premature abstraction | Different sequencing and semantics | Shared report/runner base |
| 10 | Eng/DX | Add canonical baseline JSON | Auto | Durable comparability | Prose and `/tmp` output are not sufficient | Exact-score CI gate |
| 11 | DX | Keep explicit `--manifest` | Auto | Explicit provenance | Supports repo/private manifests without packaging corpus | Built-in default |
| 12 | DX | Reject explicit `--db` | Auto | No silent configuration | Eval owns two fresh workspaces | Ignore global option |
| 13 | DX | Surface corpus scope/no gate | Auto | Correct first-read mental model | `status=passed` is integrity, not quality | Rely only on deep docs |
| 14 | DX | Keep per-query human rows | Auto | Approved diagnostic contract | 24 rows remain bounded and useful | Add `--verbose` now |
| 15 | Cross-phase | No new ADR | Auto | ADRs record long-lived product architecture | E1 adds an internal evaluation seam without changing accepted runtime architecture | Create redundant ADR |

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | CLEAR AFTER FIXES | HOLD SCOPE; narrow algorithm-selection claim |
| CEO Voices | Codex + Claude | Independent premise challenge | 2 | CONSENSUS | Baseline valid; small corpus limits must be explicit |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR AFTER FIXES | DTO, snapshot, locator, renderer, artifact, and bounds corrected |
| Eng Voices | Codex + Claude | Independent engineering review | 2 | CONSENSUS | Core contracts aligned; non-shared findings adjudicated |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | SKIPPED | No UI scope |
| DX Review | `/plan-devex-review` | Developer experience gaps | 1 | CLEAR AFTER FIXES | Scope/gate language, `--db`, errors, comparison flow corrected |
| DX Voices | Codex + Claude | Independent developer-experience review | 2 | CONSENSUS | Explicit manifest retained; packaging expansion rejected |

**VERDICT:** CEO + ENG + DX CLEARED AFTER PLAN CORRECTIONS — ready for final approval

NO UNRESOLVED DECISIONS
