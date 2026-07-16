# Compiled Library Export v1 Implementation Plan

Status: mechanically landed and authority-reviewed; the live code-authority preflight amendment
was accepted on 2026-07-16 and must land mechanically before core implementation resumes.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one deterministic, read-only `mke library export` contract that exports every active
Publication as portable Markdown plus exact `mke.evidence_ref.v1` sidecars and proves the result
from an installed wheel. A separate follow-up plan owns the isolated LLM Wiki compatibility proof
after this core PR is merged.

**Architecture:** A command-specific read-only `KnowledgeEngine` composition opens the existing
SQLite database with `mode=ro` and `PRAGMA query_only=ON`, obtains one bounded immutable snapshot,
and closes the transaction before rendering. Project-owned domain DTOs carry that snapshot into a
canonical renderer and a descriptor-bound filesystem publisher; `export-manifest.json` is the
final fallible artifact operation and the commit marker. CLI presentation is a thin interface
adapter, while the installed-wheel consumer remains an independent downstream validator rather
than a new MKE runtime dependency.

**Tech Stack:** Python 3.12/3.13, stdlib `sqlite3`, PEP 249 transaction control, stdlib
`dataclasses`, `json`, `hashlib`, descriptor-relative `os` filesystem operations, Pydantic v2 for
closed public response validation, Pytest, Ruff, Pyright, Hatch/uv, and GitHub Actions.

## Approved Inputs

- Approved design source:
  `docs/superpowers/specs/2026-07-15-compiled-library-export-design.md` after the mechanically
  landed spec commit.
- Planning-time repository baseline:
  `a03c2308106ef499c6bd64b0efb1c123d5059f47` (`proof(ocr): establish PDF OCR phase zero viability (#71)`).
- At execution start, re-fetch and require `main == origin/main` with a clean primary worktree.
  If `main` moved, inspect the intervening diff before mechanically landing this plan; do not
  silently apply stale line numbers or overwrite a newer contract.
- The approved public spec must land as
  `docs/superpowers/specs/2026-07-15-compiled-library-export-design.md` and this plan as
  `docs/superpowers/plans/2026-07-15-compiled-library-export-implementation.md` in the isolated
  implementation worktree before Task 1 begins. The follow-up plan lands as
  `docs/superpowers/plans/2026-07-15-compiled-library-export-llm-wiki-compatibility-implementation.md`.

## Global Constraints

- Core PR only: Compiled Library Export v1, generic installed-wheel proof, CI, documentation, and
  core review closure. LLM Wiki compatibility and its bounded claim belong to the separate
  follow-up plan after this PR is merged and reverified.
- No production OCR, OCR provider promotion, rich document IR, assets, layout reconstruction,
  table/formula/chart claims, MCP changes, HTTP service, watcher, plugin, or bidirectional sync.
- No new runtime dependency, model, hosted API, LLM call, network requirement, tenant, RBAC, or
  decision authority.
- Public command is exactly:
  `mke --db <database> library export --output <new-directory> [--json]`.
- `--db` is the only accepted global runtime option for this command. Explicitly reject
  `--retrieval-query-policy` and `--retrieval-strategy`, including `--option=value` forms, before
  any runtime composition.
- `--output` accepts one child-directory component under the bound process working directory.
  Reject empty, `.`, `..`, absolute, slash-containing, backslash-containing, NUL-containing, nested,
  traversal, and symbolic-link-parent forms. Never merge into or replace an existing target.
- Export only the implicit `local` Library and every active Publication in one coherent snapshot.
- Open an existing SQLite database through URI `mode=ro`, set `PRAGMA query_only=ON`, and do not
  create a database, migrate schema, probe FTS, rebuild retrieval, or recover unfinished Runs.
- Preserve current normal CLI/MCP owner startup unchanged; the read-only path is command-specific.
- Exact v1 budgets are 4,096 active Publications, 65,536 active Evidence records, 128 MiB aggregate
  Evidence UTF-8 bytes, and 64 MiB per emitted Markdown or JSONL file. Equality passes; greater
  values fail before a committed export.
- Process one Source at a time during rendering. Do not duplicate the complete export in memory.
- Exact tree is `export-manifest.json`, `sources/<sha256>.md`, and
  `evidence/<sha256>.jsonl`; no other committed entry is allowed.
- `export-manifest.json` publication is the final production operation and the only commit marker.
  All fallible close, digest, inventory, temporary-manifest, and ownership checks complete first.
- JSON is strict UTF-8, sorted-key, compact-separator canonical JSON with one trailing LF.
- Evidence sidecars contain exact closed `mke.evidence_ref.v1` objects; Markdown is a derivative,
  not provenance authority.
- The six non-redacted export causes are a closed command-local set in
  `mke.interfaces.library_export`. Do not add them to shared `_ALLOWLISTED_CAUSES`; shared
  `PublicError.payload()`, MCP schemas, the frozen consumer source-pack fixture, existing CLI/MCP
  responses, Search/Ask, ingest, retrieval, evaluation artifacts, OCR evidence, and release
  identity remain compatible.
- All public text and repository records are public-neutral. Never include private paths, local hub
  identities, private workflow or motivation, hostnames, timestamps, tokens, raw diagnostics, or
  operator data.
- Implementation is TDD. Every task stops on unexpected baseline failure or scope expansion and
  reports the exact blocker rather than modifying an unapproved surface.

## Planned File Structure

### Product code

- Create `src/mke/domain/library_export.py`: immutable snapshot DTOs, strict value validation,
  budgets, and typed data-error reasons.
- Modify `src/mke/domain/__init__.py`: re-export only the approved snapshot types/constants.
- Modify `src/mke/adapters/sqlite/__init__.py`: command-specific read-only construction, required
  schema validation, common active-Publication graph validation, and bounded set-oriented snapshot.
- Modify `src/mke/application/__init__.py`: read-only `KnowledgeEngine` composition and snapshot use
  case; no renderer or filesystem logic.
- Create `src/mke/application/library_export.py`: canonical EvidenceRef/Markdown/manifest rendering
  and small immutable rendered-entry/result DTOs.
- Create `src/mke/adapters/filesystem/__init__.py` and
  `src/mke/adapters/filesystem/library_export.py`: descriptor-bound target creation, file writes,
  manifest-last publication, revalidation, and ownership-safe cleanup.
- Create `src/mke/interfaces/library_export.py`: closed success/error response models, exception to
  stable public-error mapping, and human/JSON rendering.
- Modify `src/mke/cli.py`: parser and thin command-specific composition before normal runtime
  construction.
- Regression only, no planned edit: `src/mke/interfaces/public_errors.py`,
  `src/mke/interfaces/mcp_schemas.py`, and
  `tests/fixtures/consumer-source-pack-v1/mcp-tool-schemas.json`.

### Tests and proof

- Create `tests/domain/test_library_export.py`.
- Create `tests/adapters/test_sqlite_library_export.py`.
- Create `tests/application/test_library_export.py`.
- Create `tests/adapters/test_library_export_filesystem.py`.
- Create `tests/interfaces/test_cli_library_export.py`.
- Regression only, no planned edit:
  `tests/interfaces/test_consumer_source_pack_contract_fixture.py`.
- Create `scripts/compiled_library_export_consumer.py` and
  `scripts/compiled_library_export_proof.py`.
- Create `tests/scripts/test_compiled_library_export_consumer.py` and
  `tests/scripts/test_compiled_library_export_proof.py`.
- Create `.github/workflows/compiled-library-export-proof.yml` as one bounded non-matrix job.

### Documentation

- Modify `README.md`, `README_CN.md`, `docs/README.md`, `docs/explanation/architecture.md`,
  `docs/reference/cli.md`, and `docs/reference/contracts.md`.
- Create `docs/how-to/export-compiled-library.md` and
  `docs/how-to/run-compiled-library-export-proof.md`.
- Create `tests/evaluation/test_compiled_library_export_documentation.py`.
- Modify `scripts/release_presentation_audit.py` and
  `tests/scripts/test_release_presentation_audit.py` only to accept the bounded verified claim and
  reject OCR/production/LLM-Wiki-authority overclaims.
- Create the public-neutral core implementation review under `docs/superpowers/reviews/` at its
  actual review gate. The compatibility review belongs to the follow-up PR.

## Execution And Review Gates

1. The approved spec, core plan, compatibility follow-up plan, and plan-review document were
   mechanically landed at `10bbee5b2aea5fd0fd4c9631e31b786606a9b00a`. Before implementation,
   mechanically land the accepted 2026-07-16 preflight amendment to the design, core plan, and
   plan review as a separate docs-only commit and pass exact authority review.
2. Complete Tasks 1–7 sequentially with one local commit per task and near-field review after each.
3. Complete Task 8 core documentation and preliminary final verification, then hard stop for the
   authoritative pre-PR diff review.
4. Findings return to the implementation window for evidence-backed repair and targeted re-review.
   After the accepted review closure commit, rerun the generic installed-wheel proof and full gates
   on the final committed candidate with no later tracked write.
5. Push/PR/merge remain separately authorized. Only after the core PR is merged and post-merge
   checks pass may the follow-up LLM Wiki compatibility plan begin.
6. Version bump, tag, GitHub Release, registry publication, and deployment remain separate
   authorization gates after both PRs.

---

### Task 1: Define immutable Compiled Library snapshot contracts

**Files:**
- Create: `src/mke/domain/library_export.py`
- Modify: `src/mke/domain/__init__.py`
- Test: `tests/domain/test_library_export.py`

**Interfaces:**
- Consumes: existing `ActivePublicationObservation`, `CandidateEvidence`, `RunManifest`,
  `ManifestValidationError`, and `validate_manifest()`.
- Produces:
  - `ExportLimits(max_active_publications: int, max_active_evidence: int,
    max_evidence_utf8_bytes: int, max_rendered_file_bytes: int)`
  - `DEFAULT_EXPORT_LIMITS = ExportLimits(4096, 65536, 128 * 1024 * 1024,
    64 * 1024 * 1024)`
  - `LibraryExportDataError(reason: Literal["empty", "provenance", "too_large"])`
  - `CompiledEvidenceSnapshot`
  - `CompiledSourceSnapshot`
  - `CompiledLibrarySnapshot`

- [ ] **Step 1: Write RED tests for the accepted snapshot and budgets**

Create helpers with repository-valid 32-hex IDs and assert one page Source plus one timestamp
Source forms an immutable, sorted `CompiledLibrarySnapshot`. Assert the exact four default limits,
Evidence UTF-8 byte accounting, source/evidence counts, and `dataclasses.FrozenInstanceError` on
mutation.

```python
def test_compiled_library_snapshot_accepts_page_and_timestamp_sources() -> None:
    page = source_snapshot(kind="page", start=1, end=1, digest="a" * 64)
    timestamp = source_snapshot(kind="timestamp_ms", start=0, end=1200, digest="b" * 64)
    observation = ActivePublicationObservation("local", "active", 2, 2, 2)

    snapshot = CompiledLibrarySnapshot(observation, (page, timestamp))

    assert tuple(item.content_fingerprint for item in snapshot.sources) == (
        "sha256:" + "a" * 64,
        "sha256:" + "b" * 64,
    )
    assert snapshot.evidence_utf8_bytes == len("page text".encode()) + len(
        "timestamp text".encode()
    )
    assert DEFAULT_EXPORT_LIMITS == ExportLimits(4096, 65536, 134217728, 67108864)
```

- [ ] **Step 2: Write RED rejection matrices**

Parameterize exact failures for invalid ID prefixes/length/case, non-lowercase fingerprint,
display name length/control/U+2028/U+2029, unsupported media type, non-positive revision, blank or
over-1,000,000-character Evidence text, invalid page/timestamp locator, extractor/stage mismatch,
duplicate stage, unsorted Evidence, cross-Source identity drift, duplicate fingerprint, unsorted
Sources, observation count drift, empty/no-active observation, and each over-limit value. Assert
`LibraryExportDataError.reason` is exactly `empty`, `provenance`, or `too_large`.

- [ ] **Step 3: Run the domain tests to verify RED**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q tests/domain/test_library_export.py
```

Expected: collection fails because `mke.domain.library_export` does not exist.

- [ ] **Step 4: Implement the strict DTOs and reuse manifest authority**

Use frozen dataclasses and these exact field shapes:

```python
@dataclass(frozen=True)
class CompiledEvidenceSnapshot:
    evidence_id: str
    source_id: str
    content_fingerprint: str
    publication_id: str
    publication_revision: int
    run_id: str
    locator_kind: Literal["page", "timestamp_ms"]
    locator_start: int
    locator_end: int
    text: str

@dataclass(frozen=True)
class CompiledSourceSnapshot:
    source_id: str
    display_name: str
    content_fingerprint: str
    media_type: Literal["application/pdf", "video/mp4"]
    publication_id: str
    publication_revision: int
    run_id: str
    extractor_fingerprint: str
    required_stages: tuple[str, ...]
    evidence: tuple[CompiledEvidenceSnapshot, ...]

@dataclass(frozen=True)
class CompiledLibrarySnapshot:
    observation: ActivePublicationObservation
    sources: tuple[CompiledSourceSnapshot, ...]

    @property
    def evidence_utf8_bytes(self) -> int:
        return sum(len(item.text.encode("utf-8")) for source in self.sources for item in source.evidence)
```

Validate IDs with the existing public prefix convention (`src_`, `pub_`, `run_`, `ev_` plus 32
lowercase hex), validate the exact content fingerprint, and reconstruct a `RunManifest` plus
`CandidateEvidence` list for `validate_manifest()`. Add the stricter export rule that page
`start == end`. Sort requirements are assertions, not auto-sorting: callers that supply drift must
fail closed. Translate internal validation failures to `LibraryExportDataError("provenance")` while
retaining no Source text in the exception message.

- [ ] **Step 5: Run domain GREEN and adjacent provenance tests**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/domain/test_library_export.py \
  tests/domain/test_manifest.py \
  tests/domain/test_provenance_domain.py
UV_OFFLINE=1 uv run pyright src/mke/domain tests/domain/test_library_export.py
```

Expected: all selected tests pass and Pyright reports 0 errors.

- [ ] **Step 6: Commit Task 1**

```bash
git add src/mke/domain/library_export.py src/mke/domain/__init__.py \
  tests/domain/test_library_export.py
git diff --cached --check
git commit -m "feat(export): define compiled library snapshot"
```

### Task 2: Add non-mutating SQLite export startup

**Files:**
- Modify: `src/mke/adapters/sqlite/__init__.py`
- Modify: `src/mke/application/__init__.py`
- Test: `tests/adapters/test_sqlite_library_export.py`
- Test: `tests/runtime/test_runtime_composition.py`

**Interfaces:**
- Consumes: `SQLiteStore`, `KnowledgeEngine`, and Task 1 `LibraryExportDataError`.
- Produces:
  - `SQLiteStore.open_read_only_export(db_path: Path) -> SQLiteStore`
  - `KnowledgeEngine.open_read_only_export(db_path: Path) -> KnowledgeEngine`
  - the existing normal constructors remain byte-for-behavior compatible.

- [ ] **Step 1: Write RED startup tests against missing, stale, and live databases**

Cover all of these assertions:

```python
def test_read_only_export_does_not_create_missing_database(tmp_path: Path) -> None:
    db_path = tmp_path / "missing.sqlite"
    with pytest.raises(sqlite3.OperationalError):
        SQLiteStore.open_read_only_export(db_path)
    assert not db_path.exists()

def test_read_only_export_sets_query_only_without_migration(tmp_path: Path) -> None:
    db_path = populated_database(tmp_path)
    before = db_path.read_bytes()
    store = SQLiteStore.open_read_only_export(db_path)
    try:
        assert store._connection.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            store._connection.execute("UPDATE runs SET state = 'failed'")
    finally:
        store.close()
    assert db_path.read_bytes() == before
```

Also create an incompatible database missing one required export column and an unfinished Run in a
valid database. Prove startup fails on the former, leaves both database files byte-identical, and
does not recover or change the unfinished Run. Monkeypatch `migrate()`, `_probe_fts5()`, and normal
owner recovery to raise if called.

- [ ] **Step 2: Run startup tests to verify RED**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/adapters/test_sqlite_library_export.py -k 'read_only or missing or incompatible or recovery' \
  tests/runtime/test_runtime_composition.py
```

Expected: RED because both `open_read_only_export()` entry points are absent.

- [ ] **Step 3: Implement the command-specific connection path**

Keep the normal constructor path unchanged. Add a private construction mode called only by the
classmethod. The read-only path must execute this sequence and no owner-startup work:

```python
uri = db_path.absolute().as_uri() + "?mode=ro"
connection = sqlite3.connect(uri, uri=True, autocommit=False)
connection.row_factory = sqlite3.Row
connection.execute("PRAGMA foreign_keys = ON")
connection.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
connection.execute("PRAGMA query_only = ON")
```

Validate `PRAGMA query_only == 1`, `PRAGMA encoding == "UTF-8"`, and the required columns for only
these authority tables: `libraries`, `assets`, `sources`, `runs`, `run_manifests`, `evidence`, and
`publications`. Use `PRAGMA table_xinfo` and require the current column names/types/not-null/primary
key properties used by export; allow unrelated additional tables and future additive columns.
Never execute `PRAGMA journal_mode`, `_configure()`, `_probe_fts5()`, or `migrate()` on this path.

Construct the application facade without creating a second store:

```python
@classmethod
def open_read_only_export(cls, db_path: Path) -> KnowledgeEngine:
    return cls(
        db_path,
        _store=SQLiteStore.open_read_only_export(db_path),
        recover_unfinished_runs=False,
    )
```

The `_store` parameter is keyword-only and private by name; when absent, existing construction is
identical. It is not added to CLI, MCP, or runtime configuration.

- [ ] **Step 4: Add compatibility guards for normal owner startup**

Assert normal `KnowledgeEngine(tmp_path / "new.sqlite")` still creates/migrates the database and
normal `build_engine()` still performs owner-scoped recovery once. Assert the read-only classmethod
does neither. The MCP contract fixture and current parser surface must remain unchanged at this
task.

- [ ] **Step 5: Run Task 2 GREEN**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/adapters/test_sqlite_library_export.py \
  tests/adapters/test_sqlite_migration.py \
  tests/runtime/test_runtime_composition.py \
  tests/runtime/test_owner_runtime.py
UV_OFFLINE=1 uv run ruff check src/mke/adapters/sqlite/__init__.py \
  src/mke/application/__init__.py tests/adapters/test_sqlite_library_export.py
UV_OFFLINE=1 uv run pyright src/mke/adapters/sqlite src/mke/application \
  tests/adapters/test_sqlite_library_export.py
```

Expected: all selected tests pass; Ruff and Pyright report no errors.

- [ ] **Step 6: Commit Task 2**

```bash
git add src/mke/adapters/sqlite/__init__.py src/mke/application/__init__.py \
  tests/adapters/test_sqlite_library_export.py tests/runtime/test_runtime_composition.py
git diff --cached --check
git commit -m "feat(export): open library database read only"
```

### Task 3: Read one bounded active-Publication snapshot

**Files:**
- Modify: `src/mke/adapters/sqlite/__init__.py`
- Modify: `src/mke/application/__init__.py`
- Test: `tests/adapters/test_sqlite_library_export.py`
- Test: `tests/application/test_library_export.py`

**Interfaces:**
- Consumes: Task 1 DTOs and Task 2 read-only composition.
- Produces:
  - `SQLiteStore.compiled_library_snapshot(
    *, limits: ExportLimits = DEFAULT_EXPORT_LIMITS
    ) -> CompiledLibrarySnapshot`
  - `KnowledgeEngine.compiled_library_snapshot() -> CompiledLibrarySnapshot`
- The `limits` seam exists for bounded unit tests only; the public application method always uses
  `DEFAULT_EXPORT_LIMITS`.

- [ ] **Step 1: Write RED tests for complete page/timestamp snapshot content**

Create one normal PDF Publication, one sidecar-video Publication, and one inactive Source through
the current application lifecycle. Reopen through `KnowledgeEngine.open_read_only_export()` and
assert:

- `observation.source_count == 3`, active Publication count is 2, and only two Sources export;
- PDF and video display name/media type/asset digest/Publication revision/Run/manifest identities
  match database authority;
- page and timestamp Evidence are complete and sorted by
  `(locator_kind, locator_start, locator_end, evidence_id)`; and
- the original Source bytes are never opened by the export reader (rename the fixture copy after
  ingest, then read successfully from SQLite).

- [ ] **Step 2: Write RED graph-corruption and limit matrices**

Mutate a copied database one case at a time for library ownership, active pointer, Publication
Source, Run Source/state, revision, manifest asset/count/stages/extractor, Evidence Source/Run,
locator, duplicate content fingerprint, and unsupported media type. Every case must raise
`LibraryExportDataError(reason="provenance")`, roll back, and leave all active rows unchanged.

Use small injected `ExportLimits` values to prove exact equality passes and one-above fails for:

```python
ExportLimits(
    max_active_publications=2,
    max_active_evidence=4,
    max_evidence_utf8_bytes=len(expected_utf8),
    max_rendered_file_bytes=1024,
)
```

The aggregate byte assertion must use non-ASCII text so character count cannot masquerade as UTF-8
byte count. The committed default-limit assertion remains in Task 1.

- [ ] **Step 3: Write RED fixed-query and concurrent-snapshot tests**

Capture SQLite trace statements for one Source and several Sources. Ignore `PRAGMA` and transaction
statements; require exactly five data `SELECT`s in both cases:

1. Library inventory;
2. total Source count;
3. active Source/Publication/Run/manifest graph rows;
4. aggregate active Evidence count plus `SUM(length(CAST(text AS BLOB)))` preflight; and
5. all active Evidence rows.

Monkeypatch the private Evidence-row read helper to let a second WAL connection publish or corrupt
after preflight but before the fifth query. Assert the returned snapshot is entirely before-change
or entirely after-change, never mixed. Do not add a production observer/callback parameter.

- [ ] **Step 4: Run Task 3 tests to verify RED**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/adapters/test_sqlite_library_export.py \
  tests/application/test_library_export.py
```

Expected: failures because `compiled_library_snapshot()` is absent.

- [ ] **Step 5: Extract common active-graph validation and implement the five-query reader**

Refactor the current `_observe_active_publications()` only enough to share the same metadata query
and row validator with export. Preserve existing observation results and error text. The export
reader must:

```python
def compiled_library_snapshot(
    self, *, limits: ExportLimits = DEFAULT_EXPORT_LIMITS
) -> CompiledLibrarySnapshot:
    try:
        observation, active_rows = self._read_and_validate_active_publication_rows()
        if observation.state != "active":
            raise LibraryExportDataError("empty")
        if len(active_rows) > limits.max_active_publications:
            raise LibraryExportDataError("too_large")
        evidence_count, evidence_utf8_bytes = self._preflight_export_evidence()
        if evidence_count > limits.max_active_evidence or (
            evidence_utf8_bytes > limits.max_evidence_utf8_bytes
        ):
            raise LibraryExportDataError("too_large")
        evidence_rows = self._read_export_evidence_rows()
        snapshot = self._build_compiled_library_snapshot(
            observation, active_rows, evidence_rows
        )
        self._connection.commit()
        return snapshot
    except Exception:
        self._connection.rollback()
        raise
```

Do not issue `BEGIN`; use the connection's existing PEP 249 transaction. The metadata rows include
`display_name`, `media_type`, required stages, extractor fingerprint, and exact graph ownership.
Parse `required_stages` as strict JSON list-of-strings and reject malformed, duplicate, or unsorted
values through the Task 1 DTO. Build all Evidence only after preflight succeeds.

- [ ] **Step 6: Add the application delegation and prove read-only state**

Add only:

```python
def compiled_library_snapshot(self) -> CompiledLibrarySnapshot:
    return self._store.compiled_library_snapshot()
```

In the application test, hash or query the active graph immediately before and after success and
each failure. Assert exact equality and `PRAGMA query_only == 1` through the private test handle.

- [ ] **Step 7: Run Task 3 GREEN and adjacent provenance regression**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/adapters/test_sqlite_library_export.py \
  tests/adapters/test_sqlite_evidence_provenance.py \
  tests/application/test_library_export.py \
  tests/application/test_evidence_provenance.py
UV_OFFLINE=1 uv run ruff check src/mke/adapters/sqlite/__init__.py \
  src/mke/application/__init__.py tests/adapters/test_sqlite_library_export.py \
  tests/application/test_library_export.py
UV_OFFLINE=1 uv run pyright src/mke/adapters/sqlite src/mke/application \
  tests/adapters/test_sqlite_library_export.py tests/application/test_library_export.py
```

Expected: all tests pass, fixed-query assertions hold, Ruff/Pyright report no errors.

- [ ] **Step 8: Commit Task 3**

```bash
git add src/mke/adapters/sqlite/__init__.py src/mke/application/__init__.py \
  tests/adapters/test_sqlite_library_export.py tests/application/test_library_export.py
git diff --cached --check
git commit -m "feat(export): snapshot active publications"
```

### Task 4: Render canonical Evidence sidecars, Markdown, and manifest

**Files:**
- Create: `src/mke/application/library_export.py`
- Modify: `src/mke/application/__init__.py`
- Test: `tests/application/test_library_export.py`
- Regression only, no planned edit: `tests/interfaces/test_mcp_v1_schemas.py`

**Interfaces:**
- Consumes: `CompiledLibrarySnapshot`, `CompiledSourceSnapshot`, existing `EvidenceRefV1`, and
  `ActivePublicationObservationV1` as validation oracles in tests.
- Produces:
  - `canonical_json_line(value: Mapping[str, object]) -> bytes`
  - `render_evidence_jsonl(source: CompiledSourceSnapshot) -> bytes`
  - `render_compiled_markdown(source: CompiledSourceSnapshot) -> bytes`
  - `RenderedSourceEntry` with exact manifest fields and two byte digests
  - `render_export_manifest(snapshot, entries) -> bytes`
  - `LibraryExportResult(library_id, source_count, evidence_count, manifest_sha256)`

- [ ] **Step 1: Write RED exact-byte golden tests**

For one page and one timestamp Source, freeze the complete expected UTF-8 bytes for JSONL,
Markdown, and manifest. Validate every JSONL line through `EvidenceRefV1.model_validate_json()`,
the observation through `ActivePublicationObservationV1`, and the manifest field set with explicit
key equality. Assert one trailing LF, no CR, and exact SHA-256 over emitted bytes.

```python
assert jsonl == (
    b'{"content_fingerprint":"sha256:' + b"a" * 64
    + b'","evidence_id":"ev_' + b"1" * 32
    + b'","locator":{"end":1,"kind":"page","start":1},'
      b'"publication_id":"pub_' + b"2" * 32
    + b'","publication_revision":1,"run_id":"run_' + b"3" * 32
    + b'","schema_version":"mke.evidence_ref.v1","source_id":"src_'
    + b"4" * 32 + b'","text":"page text"}\n'
)
```

Use a readable assembled literal if Ruff rejects one long expression; the expected bytes must stay
independent of the production serializer.

- [ ] **Step 2: Write RED determinism and untrusted-content tests**

Assert:

- repeated rendering is byte-identical;
- Source order is not repaired silently (Task 1 rejects it);
- display name containing quotes, colon, `---`, Markdown, and YAML-like content remains one
  JSON-escaped frontmatter scalar;
- Evidence text containing headings, anchors, frontmatter markers, code fences, HTML, and prompt-like
  strings is emitted verbatim after the renderer-owned heading and never affects file paths;
- page heading is `## Page N`, timestamp heading is `## Timestamp START-END ms`, and anchor is
  `<a id="mke-evidence-EVIDENCE_ID"></a>`; and
- any EvidenceRef or source-entry field drift fails before bytes are returned.

- [ ] **Step 3: Write RED per-file boundary tests**

Monkeypatch only the module's private rendered-byte limit to a small value. Assert a Markdown and
JSONL byte sequence exactly equal to the limit passes and one byte above raises
`LibraryExportDataError(reason="too_large")`. Assert the production constant imported from
`DEFAULT_EXPORT_LIMITS` remains exactly 64 MiB.

- [ ] **Step 4: Run renderer tests to verify RED**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q tests/application/test_library_export.py -k 'render or manifest'
```

Expected: RED because `mke.application.library_export` does not exist.

- [ ] **Step 5: Implement canonical one-Source-at-a-time renderers**

Use this exact canonical helper:

```python
def canonical_json_line(value: Mapping[str, object]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8", errors="strict")
```

Build the EvidenceRef payload with exactly:

```python
{
    "schema_version": "mke.evidence_ref.v1",
    "evidence_id": item.evidence_id,
    "source_id": item.source_id,
    "content_fingerprint": item.content_fingerprint,
    "publication_id": item.publication_id,
    "publication_revision": item.publication_revision,
    "run_id": item.run_id,
    "locator": {
        "kind": item.locator_kind,
        "start": item.locator_start,
        "end": item.locator_end,
    },
    "text": item.text,
}
```

Frontmatter uses the approved fixed key order and `json.dumps(value, ensure_ascii=False)` for every
string scalar. `required_stages` is present only in the manifest source entry. Manifest `sources`
uses the already-validated snapshot order and the exact relative POSIX paths derived from the
lowercase digest. Store only `RenderedSourceEntry` metadata after each Source render; do not retain
all Source file bytes.

- [ ] **Step 6: Run Task 4 GREEN and schema compatibility**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/application/test_library_export.py \
  tests/interfaces/test_mcp_v1_schemas.py \
  tests/domain/test_provenance_domain.py
UV_OFFLINE=1 uv run ruff check src/mke/application/library_export.py \
  tests/application/test_library_export.py
UV_OFFLINE=1 uv run pyright src/mke/application/library_export.py \
  tests/application/test_library_export.py
```

Expected: exact bytes and schema oracle tests pass; no existing EvidenceRef behavior changes.

- [ ] **Step 7: Commit Task 4**

```bash
git add src/mke/application/library_export.py src/mke/application/__init__.py \
  tests/application/test_library_export.py
git diff --cached --check
git commit -m "feat(export): render compiled library artifacts"
```

### Task 5: Publish the export tree transactionally and clean up by identity

**Files:**
- Create: `src/mke/adapters/filesystem/__init__.py`
- Create: `src/mke/adapters/filesystem/library_export.py`
- Test: `tests/adapters/test_library_export_filesystem.py`

**Interfaces:**
- Consumes: Task 3 snapshot and Task 4 per-Source renderers.
- Produces:
  - `OutputPublicationError(reason: Literal[
    "target_exists", "parent_invalid", "write_failed", "cleanup_failed"
    ])`
  - `publish_compiled_library(
    snapshot: CompiledLibrarySnapshot,
    *, output_name: str,
    parent: Path = Path("."),
    ) -> LibraryExportResult`
  - Module-private helpers isolate bounded descriptor operations for focused monkeypatching in
    unit tests; no filesystem test seam is exposed through the product or installed proof.

- [ ] **Step 1: Write RED output-name and collision tests**

Accept one ordinary child name such as `compiled-library`. Reject `""`, `.`, `..`, absolute POSIX
and Windows forms, `/`, `\\`, nested, traversal, NUL, and names whose parent resolution involves a
symbolic link. Test pre-existing regular file, directory, and symlink targets. Assert every
rejection preserves the existing entry byte/inode/metadata identity and creates no sibling file.

- [ ] **Step 2: Write RED exact-tree and manifest-last tests**

For a two-Source snapshot assert the only committed paths are:

```text
export-manifest.json
evidence/<digest-a>.jsonl
evidence/<digest-b>.jsonl
sources/<digest-a>.md
sources/<digest-b>.md
```

Use focused spies on module-private write/revalidation helpers to assert all content files close
and revalidate, then exact inventory validation runs, then the temporary manifest is written,
closed, and re-read. Only after every fallible check and descriptor close succeeds may the final
rename publish `export-manifest.json`; the rename is the last production operation. The test then
independently reopens every file, compares byte count/SHA with the manifest, and rejects any
temporary or unexpected entry.

- [ ] **Step 3: Write RED ownership, replacement, and cleanup failure tests**

Inject these real local-operation failures one at a time:

- short write, disk/write `OSError`, close failure, file digest mismatch, nested/unexpected entry,
  temporary-manifest write/revalidation failure, and final rename failure;
- target or recorded child replacement before cleanup; and
- cleanup unlink/rmdir failure.

For catchable failures before manifest publication, assert the call-owned tree disappears only
when every recorded `(st_dev, st_ino, file_type)` still matches. If the target or a recorded child
is replaced before cleanup, assert operator-owned replacement bytes survive and the result is
`OutputPublicationError("cleanup_failed")`. No test may use recursive path-based
`shutil.rmtree()`. Exhaustive same-account inode replacement at every internal micro-step is not a
core-PR blocker.

- [ ] **Step 4: Run filesystem tests to verify RED**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q tests/adapters/test_library_export_filesystem.py
```

Expected: collection fails because the filesystem publisher is absent.

- [ ] **Step 5: Implement bound-directory operations**

The publisher uses small module-private helpers around descriptor-relative operations and
`follow_symlinks=False`/`O_NOFOLLOW` where available:

```python
parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
os.mkdir(output_name, mode=0o700, dir_fd=parent_fd)
target_stat = os.stat(output_name, dir_fd=parent_fd, follow_symlinks=False)
target_fd = os.open(
    output_name,
    os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    dir_fd=parent_fd,
)
if (os.fstat(target_fd).st_dev, os.fstat(target_fd).st_ino) != (
    target_stat.st_dev,
    target_stat.st_ino,
):
    raise OutputPublicationError("parent_invalid")
```

Create every file with `O_RDWR | O_CREAT | O_EXCL | O_NOFOLLOW`, bounded write loops, `lseek(0)`,
bounded re-read, and descriptor `fstat` identity checks. Record identity at creation. Create
`sources/` and `evidence/` with mode `0o700`, files with `0o600`. Use fixed internal temporary name
`.export-manifest.json.tmp` because the target is a new call-owned directory; it must not remain in
the success inventory.

- [ ] **Step 6: Implement identity-bound reverse cleanup**

Cleanup walks only the recorded expected inventory in reverse order. Before each unlink/rmdir,
compare `lstat` identity and file type to the recorded value; never follow a symlink and never
discover additional paths to delete. After child removal, verify the target identity again before
`rmdir(output_name, dir_fd=parent_fd)`. Any mismatch or removal error becomes `cleanup_failed`; do
not mask it with the originating write error and do not delete ambiguous state.

- [ ] **Step 7: Run Task 5 GREEN and repeat the race slice**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q tests/adapters/test_library_export_filesystem.py
UV_OFFLINE=1 uv run ruff check src/mke/adapters/filesystem \
  tests/adapters/test_library_export_filesystem.py
UV_OFFLINE=1 uv run pyright src/mke/adapters/filesystem \
  tests/adapters/test_library_export_filesystem.py
```

Expected: all tests pass; committed output has no post-manifest fallible operation and cleanup is
limited to the identity-bound owned tree.

- [ ] **Step 8: Commit Task 5**

```bash
git add src/mke/adapters/filesystem/__init__.py \
  src/mke/adapters/filesystem/library_export.py \
  tests/adapters/test_library_export_filesystem.py
git diff --cached --check
git commit -m "feat(export): publish compiled library safely"
```

### Task 6: Expose the closed CLI and stable failure contract

**Files:**
- Create: `src/mke/interfaces/library_export.py`
- Modify: `src/mke/cli.py`
- Create: `tests/interfaces/test_cli_library_export.py`
- Modify: `tests/interfaces/test_cli_error_contract.py`
- Modify: `tests/interfaces/test_mcp_contract.py`
- Regression only, no planned edit: `src/mke/interfaces/public_errors.py`
- Regression only, no planned edit:
  `tests/interfaces/test_consumer_source_pack_contract_fixture.py`

**Interfaces:**
- Consumes: Task 2 read-only engine, Task 3 snapshot, Task 5 publisher/result, and existing
  `PublicError`.
- Produces:
  - response schema literal `mke.compiled_library_export_response.v1`
  - strict Pydantic `LibraryExportSuccessV1` and `LibraryExportErrorV1`
  - `run_library_export(db_path, output_name, *, json_output, parent=Path(".")) -> int`
  - exact public parser `library export --output NAME [--json]`.

- [ ] **Step 1: Write RED parser and success response tests**

Ingest the normal PDF and sidecar video through existing commands, then run:

```python
exit_code = main([
    "--db", str(db_path),
    "library", "export",
    "--output", "compiled-library",
    "--json",
])
```

Assert exit 0 and exact closed JSON keys/value types:

```json
{"evidence_count":3,"library_id":"local","manifest_sha256":"<64-lowercase-hex>","ok":true,"schema_version":"mke.compiled_library_export_response.v1","source_count":2}
```

The test computes the real digest rather than freezing a placeholder. The human form is one line
with these exact tokens in order:

```text
library_export=passed library_id=local source_count=2 evidence_count=3 manifest_sha256=<digest>
```

Assert parser help contains the new nested command and accepts no library ID, Source selector,
format, extractor, provider, MCP, or arbitrary parent option. Parameterize both separated and
`--option=value` forms of `--retrieval-query-policy` and `--retrieval-strategy`; all four must exit
through `argparse` with code 2 before runtime construction. `--db` remains accepted.

- [ ] **Step 2: Write RED exact failure matrix and redaction tests**

Parameterize the design table and require closed response keys:

| Trigger | problem | cause | next_step |
|---|---|---|---|
| no active Publication | `library_export_invalid` | `local Library has no active Publications` | `ingest_and_publish_source` |
| graph drift | `library_export_invalid` | `active Publication provenance graph is invalid` | `repair_local_library` |
| missing/stale DB | `library_export_invalid` | `local Library database is unavailable or incompatible` | `open_current_library_database` |
| existing target | `output_path_invalid` | `output directory must not already exist` | `choose_new_output_directory` |
| invalid parent/name | `output_path_invalid` | `output parent is invalid` | `choose_valid_output_parent` |
| over limit | `library_export_too_large` | `active Library exceeds v1 export limits` | `reduce_active_library_or_use_later_export_version` |
| other write failure | `library_export_failed` | `operation failed; details were redacted` | `retry_library_export` |
| ambiguous cleanup | `cleanup_failed` | `operation failed; details were redacted` | `inspect_output_parent` |

Every failure has `schema_version`, `ok=false`, and
`active_publication_impact="unchanged"`. Assert no absolute path, database/output name, Source text,
hostname, timestamp, temporary name, exception class, or stack trace appears.

- [ ] **Step 3: Write RED read-only composition and compatibility tests**

Monkeypatch `build_engine()` and owner recovery to fail if the `library export` branch reaches them.
Assert the command uses `KnowledgeEngine.open_read_only_export()` and closes it on success/failure.
Snapshot active-state rows before and after every case. Assert the MCP tool inventory and generated
schemas remain byte-identical and contain no `library_export` tool. Assert existing
`PublicError.payload()` tests retain the old field set without `schema_version`. Assert all six
export causes remain absent from shared `_ALLOWLISTED_CAUSES`, and the committed consumer
source-pack fixture remains exactly equal to the live MCP producer.

- [ ] **Step 4: Run CLI tests to verify RED**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/interfaces/test_cli_library_export.py \
  tests/interfaces/test_cli_error_contract.py \
  tests/interfaces/test_mcp_contract.py \
  tests/interfaces/test_consumer_source_pack_contract_fixture.py
```

Expected: RED because the parser and command-local interface models are absent. Existing shared
MCP/consumer contract tests remain GREEN and must not be changed to manufacture RED.

- [ ] **Step 5: Implement the interface serializer and error mapping**

Define strict frozen models with `ConfigDict(extra="forbid", frozen=True, strict=True)`. Define a
private command-local frozenset containing exactly the six non-redacted causes from the table plus
a local constant holding the exact redacted literal. `LibraryExportErrorV1` rejects every cause
outside those seven values; it does not call `is_public_error_cause()` and does not import or
modify `_ALLOWLISTED_CAUSES`. Construct `PublicError` directly for typed export failures so its
payload shape is reused, and use the exact redacted cause for unknown/cleanup failures. Build the
command-specific failure payload without changing the shared model:

```python
def library_export_error_payload(error: PublicError) -> dict[str, object]:
    return {
        "schema_version": "mke.compiled_library_export_response.v1",
        **error.payload(),
    }
```

Validate that payload through `LibraryExportErrorV1` before rendering. Map only typed exceptions
and approved reasons; unknown exceptions use `library_export_failed` plus the redacted cause. Add
a regression proving an unrelated shared cause is rejected by the export response model.

- [ ] **Step 6: Add the thin CLI branch before normal runtime construction**

Add nested parsers after `ask` and handle `args.command == "library"` before
`runtime_config_from_args()`/`build_engine()`:

```python
library = subcommands.add_parser("library")
library_commands = library.add_subparsers(dest="library_command", required=True)
library_export = library_commands.add_parser("export")
library_export.add_argument("--output", required=True)
library_export.add_argument("--json", action="store_true", dest="json_output")
```

Immediately after parsing and before the existing retrieval option conflict/runtime logic, reject
both raw global retrieval options when `args.command == "library"` and
`args.library_command == "export"`. Reuse `_raw_option_present()` so separated and equals forms are
covered. Use these stable parser errors:

```text
library export does not support --retrieval-query-policy
library export does not support --retrieval-strategy
```

The execution function opens the read-only engine, obtains the snapshot before target creation,
publishes under `Path(".")`, validates the response, prints once, and closes the engine in `finally`.
No normal retrieval/runtime configuration is consulted.

- [ ] **Step 7: Run Task 6 GREEN and CLI/MCP regressions**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/interfaces/test_cli_library_export.py \
  tests/interfaces/test_cli_error_contract.py \
  tests/interfaces/test_cli_pdf.py \
  tests/interfaces/test_cli_video.py \
  tests/interfaces/test_cli_ask.py \
  tests/interfaces/test_cli_retrieval.py \
  tests/interfaces/test_mcp_contract.py \
  tests/interfaces/test_mcp_legacy_schema_snapshot.py \
  tests/interfaces/test_consumer_source_pack_contract_fixture.py
UV_OFFLINE=1 uv run ruff check src/mke/interfaces/library_export.py \
  src/mke/cli.py tests/interfaces/test_cli_library_export.py
UV_OFFLINE=1 uv run pyright src/mke/interfaces src/mke/cli.py \
  tests/interfaces/test_cli_library_export.py
```

Expected: all selected tests pass; MCP snapshots and shared errors are unchanged.

- [ ] **Step 8: Commit Task 6**

```bash
git add src/mke/interfaces/library_export.py src/mke/cli.py \
  tests/interfaces/test_cli_library_export.py \
  tests/interfaces/test_cli_error_contract.py tests/interfaces/test_mcp_contract.py
git diff --cached --check
git commit -m "feat(cli): export compiled library"
```

### Task 7: Prove installed-wheel portability with an independent consumer

**Files:**
- Create: `scripts/compiled_library_export_consumer.py`
- Create: `scripts/compiled_library_export_proof.py`
- Create: `tests/scripts/test_compiled_library_export_consumer.py`
- Create: `tests/scripts/test_compiled_library_export_proof.py`
- Create: `.github/workflows/compiled-library-export-proof.yml`

**Interfaces:**
- Consumes: the public installed `mke` executable and emitted files only.
- Produces:
  - consumer result schema `mke.compiled_library_export_consumer.v1`
  - proof result schema `mke.compiled_library_export_proof.v1`
  - optional controller-only `--retained-export <new-directory>` reserved for the later
    compatibility plan; it retains only a validated export plus `proof-receipt.json`, never a
    database, venv, wheelhouse, or local path in the receipt.
- `compiled_library_export_consumer.py` uses only the Python standard library, never imports `mke`,
  never reads SQLite, and never invokes Search/Ask.

- [ ] **Step 1: Write RED standalone-consumer schema and drift tests**

Build a synthetic export tree directly in the test and require the consumer to validate:

- exact inventory and one final manifest;
- closed manifest/source/observation/EvidenceRef shapes and known schema versions;
- normalized relative paths and lowercase content-digest filenames;
- file byte counts/digests, canonical JSON/JSONL, fixed Markdown frontmatter/anchors/headings;
- cross-file Source/Publication/revision/Run/fingerprint/Evidence count equality;
- page/timestamp locator rules; and
- mapping every content fingerprint to a consumer-owned source key computed from supplied Source
  bytes.

Mutation tests must reject unknown/extra/missing fields, unknown versions, reordered/non-canonical
JSON, digest drift, truncated file, unexpected/nested/symlink file, missing/fake manifest,
Markdown/JSONL disagreement, and every EvidenceRef identity/locator/text field drift.

The consumer success object has these exact keys:

```json
{
  "evidence_count": 3,
  "evidence_schema": "mke.evidence_ref.v1",
  "export_schema": "mke.compiled_library_export.v1",
  "fingerprint_mapping": "exact",
  "markdown_format": "mke.compiled_markdown.v1",
  "portable_copy": true,
  "source_count": 2,
  "status": "passed"
}
```

The script envelope adds only
`schema_version="mke.compiled_library_export_consumer.v1"`. Failures emit exact
`{"status":"failed","code":<allowlisted-token>}` with no raw exception or path.

- [ ] **Step 2: Run consumer tests to verify RED**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q tests/scripts/test_compiled_library_export_consumer.py
```

Expected: RED because the consumer script is absent.

- [ ] **Step 3: Implement the standard-library consumer**

Use bounded descriptor reads, `lstat`/`fstat` identity checks, strict UTF-8, stdlib JSON with
duplicate-key rejection, regex/typed scalar validation, and explicit key-set equality. Never use
producer Pydantic models or helper imports. Re-encode every parsed JSON object with the canonical
encoder and require byte equality to detect non-canonical producer drift.

CLI shape:

```bash
python scripts/compiled_library_export_consumer.py \
  --export compiled-library \
  --source operations-guide=operations-guide.pdf \
  --source spoken-evidence=spoken-evidence.mp4 \
  --json
```

The `--source` values are controller-owned proof inputs, not MKE product arguments. Bound each
input by regular-file descriptor and hash it independently.

- [ ] **Step 4: Write RED controller tests for one wheel, two interpreters, and real commands**

Test the controller's exact sequence with bounded fake command results first, then one local real
slice:

1. require a clean SHA-1 Git candidate and build one wheel once;
2. verify wheel filename/METADATA/project version and SHA-256;
3. create fresh isolated environments for explicit Python 3.12 and 3.13 paths;
4. offline-install the same exact wheel and run `pip check` plus installed-origin doctor;
5. copy repository-authored PDF, MP4, and sidecar transcript fixtures into a consumer-owned root;
6. run installed `mke ingest` for page and timestamp Sources;
7. run installed `mke library export` twice to distinct new targets on the unchanged database and
   require byte-identical trees;
8. run the standalone consumer on the first tree and on a copied portable tree;
9. prove existing target, corrupted copied database provenance, digest drift, unexpected file, and
   manifest-less partial output fail closed through public commands or the independent consumer;
10. verify active Publication rows before/after every producer-side negative case; and
11. clean venv/database/workspace/process state, or return stable `cleanup_failed`.

Installed proof does not import or invoke the publisher's private fault-injection helpers. Cleanup
failure injection remains fully covered in Task 5 at the adapter boundary.

Assert the two interpreter results share one `proof_input_wheel_sha256`. Do not require
cross-database export bytes to match because lifecycle IDs are independently generated.

- [ ] **Step 5: Run controller tests to verify RED**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q tests/scripts/test_compiled_library_export_proof.py
```

Expected: RED because the proof controller is absent.

- [ ] **Step 6: Implement bounded controller orchestration**

Reuse the already-reviewed process/environment/candidate helpers from
`scripts/consumer_source_pack_proof.py` by importing them from the repository script path; do not
copy another process-group controller. The proof's closed aggregate is:

```json
{
  "evidence_schema": "mke.evidence_ref.v1",
  "export_schema": "mke.compiled_library_export.v1",
  "interpreter_count": 2,
  "markdown_format": "mke.compiled_markdown.v1",
  "proof_input_wheel_sha256": "<computed-64-lowercase-hex>",
  "schema_version": "mke.compiled_library_export_proof.v1",
  "status": "passed"
}
```

Compute the digest at runtime; do not freeze a sample literal. `--retained-export` must be absent
in CI. When present locally, require a new target, descriptor-copy only the already validated first
export plus a canonical receipt with schemas/counts/wheel digest, and transfer cleanup ownership to
the caller only after full revalidation.

- [ ] **Step 7: Add one bounded non-matrix GitHub workflow**

Mirror the existing consumer proof's pinned actions and online-prewarm/offline-proof split:

- `actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0`
- `astral-sh/setup-uv@11f9893b081a58869d3b5fccaea48c9e9e46f990`
- two explicit `actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1`
  steps for 3.12 and 3.13;
- `contents: read`, repository/ref concurrency, `cancel-in-progress: true`;
- one `ubuntu-latest` job, no matrix, 15-minute timeout, no artifact upload, no write permission;
- online `uv sync --locked`/locked core prewarm, followed by a distinct `UV_OFFLINE=1` proof step.

Add workflow structure tests that reject a sibling job, missing interpreter, unpinned action,
online proof, upload, or write permission. Do not modify `.github/workflows/ci.yml` or the existing
consumer source-pack workflow.

- [ ] **Step 8: Run Task 7 GREEN locally**

Resolve real Python 3.12 and 3.13 interpreter paths already installed on the host, then run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/scripts/test_compiled_library_export_consumer.py \
  tests/scripts/test_compiled_library_export_proof.py
UV_OFFLINE=1 uv run python scripts/compiled_library_export_proof.py \
  --python "$PYTHON312" \
  --python "$PYTHON313" \
  --json
UV_OFFLINE=1 uv run ruff check scripts/compiled_library_export_consumer.py \
  scripts/compiled_library_export_proof.py tests/scripts/test_compiled_library_export_consumer.py \
  tests/scripts/test_compiled_library_export_proof.py
UV_OFFLINE=1 uv run pyright scripts/compiled_library_export_consumer.py \
  scripts/compiled_library_export_proof.py tests/scripts/test_compiled_library_export_consumer.py \
  tests/scripts/test_compiled_library_export_proof.py
```

Before the real proof, record the exact interpreter commands in the execution report. If either
interpreter or the offline locked cache is unavailable, stop as an environment blocker; do not
download, relax offline mode, substitute the same interpreter twice, or claim the proof passed.

- [ ] **Step 9: Commit Task 7**

```bash
git add scripts/compiled_library_export_consumer.py \
  scripts/compiled_library_export_proof.py \
  tests/scripts/test_compiled_library_export_consumer.py \
  tests/scripts/test_compiled_library_export_proof.py \
  .github/workflows/compiled-library-export-proof.yml
git diff --cached --check
git commit -m "proof(export): verify installed library portability"
```

### Task 8: Document the core contract and close verification

**Files:**
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `docs/README.md`
- Modify: `docs/explanation/architecture.md`
- Modify: `docs/reference/cli.md`
- Modify: `docs/reference/contracts.md`
- Create: `docs/how-to/export-compiled-library.md`
- Create: `docs/how-to/run-compiled-library-export-proof.md`
- Create: `tests/evaluation/test_compiled_library_export_documentation.py`
- Modify: `scripts/release_presentation_audit.py`
- Modify: `tests/scripts/test_release_presentation_audit.py`
- Modify: `docs/superpowers/plans/2026-07-15-compiled-library-export-implementation.md`
- Create after actual review:
  `docs/superpowers/reviews/2026-07-15-compiled-library-export-implementation-review.md`

**Interfaces:**
- Consumes: final public CLI, schemas, and generic installed-wheel proof.
- Produces:
  - user documentation and the bounded generic export claim;
  - no LLM Wiki compatibility claim before the follow-up PR;
  - no release identity, dependency, workflow, or runtime expansion.

- [ ] **Step 1: Write RED documentation and overclaim tests**

Require English/Chinese README discoverability, CLI/reference exact schemas, how-to commands,
Markdown-versus-EvidenceRef authority, count/byte budgets, read-only DB behavior, manifest-last
semantics, original-Source exclusion, and the explicitly deferred LLM Wiki compatibility boundary.
Extend release presentation tests so they reject claims of production OCR, reconstructed layout,
verified LLM Wiki compatibility, hosted integration, real-user adoption, or released v0.1.3 before
the separate compatibility and release operations.

- [ ] **Step 2: Run documentation tests to verify RED**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/evaluation/test_compiled_library_export_documentation.py \
  tests/scripts/test_release_presentation_audit.py
```

Expected: RED because the documents and bounded audit rules are absent.

- [ ] **Step 3: Write the public documentation without changing release identity**

Document the feature as verified on the current main candidate and intended for a later release
decision; keep package version and `docs/releases/v0.1.2.md` unchanged. Include these exact claim
boundaries:

> MKE can deterministically export active Publications as portable Markdown with exact page or
> timestamp Evidence provenance, validated through an installed-wheel external consumer proof.

State separately that OCR Phase 0 is bounded local viability evidence on a fixed synthetic corpus
and is not production OCR. Do not create v0.1.3 release notes, bump versions, tag, or publish.

- [ ] **Step 4: Commit the core documentation before authority review**

Commit the documentation before running acceptance:

```bash
git add README.md README_CN.md docs/README.md docs/explanation/architecture.md \
  docs/reference/cli.md docs/reference/contracts.md \
  docs/how-to/export-compiled-library.md \
  docs/how-to/run-compiled-library-export-proof.md \
  tests/evaluation/test_compiled_library_export_documentation.py \
  scripts/release_presentation_audit.py tests/scripts/test_release_presentation_audit.py
git diff --cached --check
git commit -m "docs(export): document compiled library contract"
```

Run the focused documentation tests and presentation audit again after the commit. This commit must
not change package version or any Task 1–7 product/proof file.

- [ ] **Step 5: Run preliminary final-candidate verification**

Run the full command set from Step 8, including the generic same-wheel Python 3.12/3.13 proof, on
the committed implementation/docs candidate. Record full counts, wheel digest, proof aggregate,
changed-file audit, and clean worktree. Do not use `--retained-export`; retained output belongs to
the follow-up compatibility PR.

- [ ] **Step 6: Hard stop for authoritative pre-PR review**

The planning/review authority reviews the actual branch diff against the public spec, this core
plan, ADRs, and command
evidence. The implementation worker does not run a second broad review. Findings return for
evidence-backed repair and targeted re-review; low-impact theoretical hardening outside the bounded
local threat model is recorded as a follow-up rather than becoming an unbounded blocker.

- [ ] **Step 7: Commit accepted core review closure**

After findings are closed, update only checkboxes for completed steps and persist actual diff
range, verification commands, wheel digest, generic proof aggregate, and claim boundary. Do not
record LLM Wiki compatibility before its separate proof.

```bash
git add docs/superpowers/plans/2026-07-15-compiled-library-export-implementation.md \
  docs/superpowers/reviews/2026-07-15-compiled-library-export-implementation-review.md
git diff --cached --check
git commit -m "docs(export): record compiled library verification"
```

- [ ] **Step 8: Run final verification on the final committed candidate**

After the review commit, make no further tracked write. Rebuild and rerun the generic proof against
the final `HEAD`, then run:

```bash
UV_OFFLINE=1 uv run pytest -q
UV_OFFLINE=1 uv run ruff check .
UV_OFFLINE=1 uv run pyright
UV_OFFLINE=1 uv build
UV_OFFLINE=1 uv run mke proof run
UV_OFFLINE=1 uv run mke demo --verify
UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py
UV_OFFLINE=1 uv run python scripts/evidence_provenance_proof.py
UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py \
  --python "$PYTHON312" --python "$PYTHON313" --json
UV_OFFLINE=1 uv run python scripts/compiled_library_export_proof.py \
  --python "$PYTHON312" --python "$PYTHON313" --json
UV_OFFLINE=1 uv run python scripts/release_presentation_audit.py --root .
git diff --check
git status --short
```

Use the repository's actual local-knowledge proof filename if live inspection shows the current
entrypoint is named differently; report the exact command rather than silently skipping it. The
final report must include full counts/results, exact wheel digest, generic proof aggregate, clean
worktree, changed-file audit, and remaining bounded limitations.

- [ ] **Step 9: External-action and follow-up gate**

Stop with a clean, reviewed local branch/worktree. Do not push, create or ready a PR, merge, begin
the LLM Wiki compatibility plan, bump to v0.1.3, tag, publish a GitHub Release, upload an artifact,
deploy, or start Selective OCR Intake without the corresponding separate authorization and gate.

## Self-Review Checklist

- Spec coverage: every core public CLI, schema, snapshot, budget, cleanup, proof, and documentation
  requirement maps to Tasks 1–8; the separate compatibility plan owns LLM Wiki acceptance.
- Scope: one core product PR plus one later docs/evidence compatibility PR; OCR/runtime promotion,
  rich IR, MCP, HTTP, sync, and provider work remain excluded.
- Type consistency: `CompiledLibrarySnapshot` flows SQLite -> KnowledgeEngine -> renderer ->
  filesystem; `LibraryExportResult` flows filesystem -> interface -> CLI; no reversed ownership.
- Authority consistency: SQLite owns active Publication facts; JSONL owns portable provenance;
  Markdown remains derivative, and the later LLM Wiki proof cannot change that authority.
- Memory bound: preflight occurs before Evidence materialization; renderer keeps only one Source's
  file bytes plus small manifest-entry metadata.
- Mutation boundary: normal owner startup is unchanged; export uses a separate read-only
  composition and creates only a new child output directory.
- Proof boundary: standalone consumer has no MKE import/SQLite read or private publisher probe;
  LLM Wiki remains a later local acceptance check, never a CI/runtime dependency.
- Claim boundary: implementation does not itself release v0.1.3 or claim production OCR, layout
  recovery, hosted use, adoption, or business impact.
- Contract isolation: export causes remain command-local, the consumer source-pack/MCP safe-cause
  fixture stays byte-identical, and retrieval runtime overrides are rejected by the export parser.
- Placeholder scan: this plan contains no unfinished design decision; angle-bracket strings in
  examples denote runtime-computed values, not missing implementation content.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|---|---|---|---:|---|---|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | not run | Product direction was approved through the preceding brainstorming/spec process. |
| Codex Review | `/codex review` | Independent second opinion | 0 | not run | No unresolved architecture disagreement required an outside voice. |
| Eng Review | `/plan-eng-review` | Architecture & tests | 1 | CLEAR | 6 issues found, 0 critical gaps, all folded into the two plans. |
| Live Code Preflight | authority review | Shared error/parser authority | 1 | CLEAR | 2 contradictions found and folded into the design and core plan before Task 1. |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | not applicable | No UI surface. |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | not run | CLI flow is covered by the engineering review and exact contract tests. |

**VERDICT:** ENG + PRODUCT APPROVAL CLEARED — ready for the mechanical preflight amendment landing;
implementation remains behind the amended-doc review gate.

NO UNRESOLVED DECISIONS
