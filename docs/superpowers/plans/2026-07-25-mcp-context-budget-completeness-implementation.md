# MCP Context Budget and Completeness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two additive read-only MCP tools that make Search selection loss and per-Evidence
content completeness explicit, provide bounded continuation and exact active-Evidence reads, and
preserve every existing Python, CLI, legacy MCP, strict-v1, Publication, Evidence, and Export
contract.

**Architecture:** The existing `KnowledgeEngine` remains the shared application façade. SQLite
validates the active Run/Publication/Evidence graph and derives an active-set fingerprint in the
same read transaction as paged selection or active-Evidence read; pure application helpers build
UTF-8-safe excerpts/chunks and enforce response budgets; `OwnerRuntimeState` signs process-bound
cursors; strict Pydantic unions project the result through FastMCP structured output. No database
migration, persistent cursor state, second authority, retrieval promotion, network service, or
Agent loop is added.

**Tech Stack:** Python 3.12/3.13, SQLite, Pydantic 2.13.4, MCP Python SDK/FastMCP 1.28.1, HMAC-SHA256,
pytest, Ruff, Pyright, uv, GitHub Actions.

---

Execution branch: `codex/mcp-context-budget-spec`.

Baseline before the spec and plan documentation commits:
`main@d0b3b8e3f73005851570cf8fcf546030a9e2ceb5`.

Design:
[MCP Context Budget and Completeness Contract](../specs/2026-07-25-mcp-context-budget-completeness.md).

## Execution Mode and Gates

- Continue in the existing isolated worktree and branch containing the reviewed spec and this
  plan. Do not create a second implementation worktree.
- Execute sequentially with `superpowers:executing-plans`. The domain, cursor, adapter,
  application, and wire tasks share contract types and are not independent parallel lanes.
- Use `superpowers:test-driven-development` for every behavior change and
  `superpowers:verification-before-completion` before any READY handoff.
- Do not modify production code until Task 0 has produced the three targeted REDs.
- Stop and return to design review if the locked MCP SDK cannot expose typed structured output plus
  compatibility text or if the exact ten-tool inventory cannot be represented without weakening
  unknown-tool rejection.
- Stop if implementation needs a database migration, persistent cursors, a second Evidence store,
  a new dependency, retrieval ranking changes, an HTTP/remote transport, or a third new MCP tool.
- Do not push, create a PR, merge, tag, release, deploy, publish, or clean up the worktree without a
  later explicit authorization.

## Fixed Public Constants

```python
SEARCH_RESPONSE_SCHEMA = "mke.search_library_response.v2"
READ_RESPONSE_SCHEMA = "mke.read_evidence_response.v1"
AUTHORITY_SCHEMA = "mke.active_authority_snapshot.v1"
SELECTION_SCHEMA = "mke.search_selection.v2"
OUTPUT_BUDGET_SCHEMA = "mke.search_output_budget.v1"
CURSOR_SCHEMA = "mke.mcp_cursor.v1"
ACTIVE_SET_FINGERPRINT_SCHEMA = "mke.active_set_fingerprint.v1"
QUERY_POLICY_REVISION = 1

MAX_QUERY_BYTES = 512
MAX_CURSOR_BYTES = 4096
MAX_EXCERPT_BYTES = 2048
MAX_EXCERPT_CONTENT_BYTES = 16384
MAX_READ_CHUNK_BYTES = 16384
MAX_CANONICAL_MODEL_BYTES = 32768
MAX_SDK_RESULT_BYTES = 96 * 1024
MAX_READABLE_EVIDENCE_BYTES = 16 * 1024 * 1024
MAX_SEARCH_PAGE_TEXT_BYTES = 16 * 1024 * 1024

INVALID_CURSOR_CAUSE = "cursor is malformed, unauthenticated, or for another tool"
OWNER_RESTARTED_CAUSE = "cursor owner has restarted"
ACTIVE_SET_CHANGED_CAUSE = "active Publication set changed"
RETRIEVAL_POLICY_CHANGED_CAUSE = "retrieval policy changed"
EVIDENCE_CHANGED_CAUSE = "active Evidence descriptor changed"
EVIDENCE_NOT_FOUND_CAUSE = "active Evidence is not available"
RESPONSE_TOO_LARGE_CAUSE = "mandatory response metadata exceeds the response limit"
EVIDENCE_TOO_LARGE_CAUSE = "active Evidence exceeds the readable size limit"
INVALID_REQUEST_CAUSE = "request must use exactly one supported input branch"
QUERY_TOO_LARGE_CAUSE = "query exceeds 512 UTF-8 bytes"
CURSOR_TOO_LARGE_CAUSE = "cursor exceeds 4096 UTF-8 bytes"
INVALID_MAX_BYTES_CAUSE = "max_bytes must be between 4 and 16384"
V1_TEXT_TOO_LARGE_CAUSE = "complete Evidence text exceeds the v1 response limit"
```

The shipped readable-Evidence ceiling is deliberately 16 MiB, below the design's provisional
128 MiB ceiling. It is large enough to cover the deterministic oversized-v1 RED while keeping the
initial O(total Evidence bytes) hash bounded and practical to test. FTS page assembly separately
caps simultaneously loaded candidate text at 16 MiB; a single admissible candidate always makes
progress, and later candidates remain behind the cursor. These are implementation ceilings, not
performance claims.

## Native FastMCP Input Envelope

FastMCP 1.28.1 models every Python function parameter as a top-level MCP argument. Optional flat
parameters expose JSON `null` and erase the distinction between omitted and explicit `null`.
Therefore both additive tools use one required `request` parameter whose value is the strict
initial/continuation union:

```json
{"request":{"query":"publication authority","limit":10}}
```

```json
{"request":{"cursor":"<opaque-token>"}}
```

and:

```json
{"request":{"evidence_id":"ev_<opaque-id>","max_bytes":16384}}
```

```json
{"request":{"cursor":"<opaque-token>"}}
```

This keeps FastMCP structured output and Pydantic validation on public APIs. It avoids SDK-private
tool-manager mutation. A missing top-level `request` is rejected by FastMCP. With the envelope
present, a request-capture model preserves null, scalar, empty, mixed, and valid branches so the
contract can return its typed strict error without repository access.

## What already exists

- `KnowledgeEngine` is the shared Python/CLI/MCP application façade; this plan adds methods to it
  rather than creating an MCP-only authority path.
- `SQLiteStore._read_and_validate_active_publication_rows()` already validates the active
  Run/Publication/Evidence graph inside explicit PEP 249 transactions; the new fingerprint and
  selection/read methods extend that path.
- `SearchResultProvenance` and `ActivePublicationObservation` already carry the source,
  Publication, Run, locator, media, and content identities needed by the new descriptor.
- FTS5 query compilation and CJK active-scan ranking are already frozen retrieval strategies; the
  plan exposes paging/cap observations without replacing their ranking.
- `OwnerRuntimeState` already centralizes MCP process lifetime and cleanup; the cursor key and epoch
  join that owner rather than creating persistent cursor storage.
- `mcp_schemas.py`, `mcp_contract.py`, `public_errors.py`, and FastMCP structured-output tests
  already establish strict Pydantic and redacted-error patterns.
- The immutable eight-tool schema fixture, installed-wheel fixture producer, standalone official
  SDK consumer, and proof controller patterns already demonstrate release and source-isolation
  boundaries; this pack adds a new ten-tool fixture without rewriting the historical evidence.

## NOT in scope

- Changing any existing tool name, flat v1 input schema, valid bounded success payload, Python
  method, CLI command, Export schema, or Publication/Evidence authority.
- Persistent cursors, a cursor table, cache, queue, second Evidence store, or second authority.
- Agent loops, generated-answer authority, HTTP/remote MCP, cloud service, SaaS, RBAC, billing, or
  deployment.
- OCR runtime, arbitrary/long audio or video, new provider/model/account/download, or new
  dependency.
- Segmentation/contextual-retrieval comparison, corpus expansion, GraphRAG, dense/RRF/reranker
  promotion, or any comparison-only result promotion.
- Version bump, tag, Release, registry publication, push, PR, merge, deployment, or worktree
  cleanup.
- A new `TODOS.md`: the repository has none, and the excluded candidates do not block this bounded
  pack or gain value from a speculative backlog entry.

## Failure Modes and Planned Coverage

```text
MCP call
├── missing top-level request
│   └── FastMCP input validation; tool body and repository are not called
├── present request: null / scalar / empty / mixed / over-byte-limit
│   └── typed invalid_request; zero engine builds and repository calls
├── initial Search
│   ├── active graph invalid -> redacted internal_error
│   ├── FTS/CJK selection -> authority-bound selected pool
│   ├── page text budget stops before next candidate -> more_available, same next position
│   └── output metadata cannot fit -> response_too_large
├── Search continuation
│   ├── malformed/oversized cursor -> invalid_cursor; zero repository calls
│   ├── owner/authority/policy drift -> cursor_expired
│   ├── same-epoch bad MAC -> authority snapshot only; no selection
│   └── selected-pool end with CJK discard -> terminal capped
├── initial Read
│   ├── inactive/unknown/superseded ID -> evidence_not_found
│   ├── Evidence >16 MiB -> response_too_large
│   └── hash once -> bounded exact UTF-8 chunk + descriptor
├── Read continuation
│   ├── descriptor/byte-count/authority drift -> cursor_expired
│   ├── bounded BLOB range -> code-point-safe exact bytes
│   └── final reconstructed SHA mismatch -> proof failure
└── installed real-stdio proof
    ├── source-checkout import -> identity failure
    ├── schema/payload/text mismatch -> closed consumer failure
    └── timeout/oversized output/non-zero exit -> closed proof failure + cleanup
```

Every leaf above has a named unit, adapter, interface, or installed-consumer assertion in Tasks
0-8. No listed failure is allowed to degrade to a silent partial success.

## Test Coverage Map

```text
CODE PATHS                                      CONSUMER FLOWS
[PLANNED] domain fingerprints/descriptors       [PLANNED] discover exact ten-tool inventory
  ├── deterministic canonical hash                ├── reject unknown/missing tool
  ├── field sensitivity/corruption                └── validate exact schemas/descriptions
  └── strict selection/read states              [PLANNED] loss-aware Search
[PLANNED] cursor codec                            ├── initial -> more_available -> complete
  ├── encode/decode/tamper/wrong-tool             ├── initial -> capped
  ├── owner/authority/policy expiry               └── excerpt incomplete -> Read affordance
  └── UTF-8 and envelope bounds                 [PLANNED] exact Evidence Read
[PLANNED] SQLite authority + paging               ├── chunk loop without gaps/duplicates
  ├── validation-before-selection                 ├── stable descriptor and byte count
  ├── activation race rollback                    └── final SHA-256 equality
  ├── FTS lightweight lookahead/text budget     [PLANNED] compatibility
  └── CJK 9/10/11 cap boundary                    ├── frozen legacy eight-tool fixture
[PLANNED] strict wire contracts                    ├── unchanged bounded v1 successes
  ├── schema/runtime branch parity                └── typed oversized v1 error
  ├── structuredContent/text parity             [PLANNED] installed wheel, external cwd
  └── public-safe error recovery                   ├── Python 3.12 / 3.13
                                                   └── network denied, bounded subprocesses
```

## Parallelization Strategy

Sequential implementation, no parallelization opportunity. Domain values feed cursor payloads;
both feed adapter and application projections; those feed wire schemas, server registration,
installed proof, and documentation. The same contract files and exact ten-tool fixture are shared
integration points, so multiple write worktrees would add merge and authority risk without
shortening the critical path.

## Performance Bounds

- Active-set fingerprint derivation is `O(active Sources)` and runs once per tool call; it reuses
  validated rows and adds no persistent index or cache.
- FTS lookahead returns at most `page_size + 1 <= 21` metadata rows. Full candidate text loaded for
  one Search response is capped at 16 MiB, and at least the first individually admissible result
  progresses the cursor.
- CJK retrieval keeps the existing 10,000-row, 16 MiB active-text, 1,000-candidate, and top-10
  strategy caps; this pack exposes cap state but does not increase scan work.
- Initial Read hashes at most one 16 MiB Evidence exactly once. Continuations select at most
  `max_bytes + 3 <= 16,387` BLOB bytes and never rehash or load complete text.
- Search prospective-response serialization may run once per candidate, but both candidate count
  (`<=20`) and canonical bytes (`<=32 KiB`) are fixed; no unbounded quadratic path exists.
- The installed proof measures canonical model bytes and complete SDK result bytes. It makes no
  latency, throughput, RSS, production-capacity, or cross-platform claim.

## Exact File Map

### Create

- `src/mke/domain/evidence_access.py`: immutable authority records, fingerprint derivation,
  Evidence descriptors, selected-result pages, and active-Evidence read snapshots.
- `src/mke/application/evidence_access.py`: UTF-8 byte validation, query-centered excerpt
  construction, exact chunks, selection state, and canonical response-budget assembly.
- `src/mke/application/mcp_cursor.py`: strict canonical cursor payloads, base64url envelope,
  HMAC authentication, and stable cursor failures.
- `src/mke/interfaces/mcp_completeness_contract.py`: validate additive-tool request branches, use
  the shared application façade, and translate cursor/completeness errors without enlarging the
  existing legacy/v1 contract module.
- `tests/domain/test_evidence_access.py`: fingerprint, descriptor, selection, and authority
  invariants.
- `tests/application/test_evidence_access.py`: excerpt, chunk, page, cap, and response-budget tests.
- `tests/application/test_mcp_cursor.py`: canonical cursor, epoch, tamper, wrong-tool, and bound
  validation.
- `tests/adapters/test_sqlite_evidence_access.py`: same-transaction authority fingerprint,
  FTS/CJK paging, active-only exact reads, corruption, and read-range behavior.
- `tests/interfaces/test_mcp_context_completeness.py`: strict input/output unions, targeted
  RED/GREEN, SDK structured/compatibility output, descriptions, annotations, and recovery.
- `tests/fixtures/mcp-context-completeness-v1/mcp-tool-schemas.json`: exact current ten-tool
  input/output schema, description, annotation, and safe-cause expectation.
- `scripts/mcp_context_completeness_fixture.py`: deterministic installed-wheel fixture producer;
  it imports only the installed MKE package and standard library.
- `scripts/mcp_context_completeness_consumer.py`: standalone official-SDK consumer; it never imports
  MKE, SQLite, Pydantic, repository helpers, or source-checkout modules.
- `scripts/mcp_context_completeness_proof.py`: one-wheel, external-environment, arbitrary-cwd,
  real-stdio proof controller with bounded subprocesses and closed receipts.
- `tests/scripts/test_mcp_context_completeness_fixture.py`: installed fixture construction and
  active-set mutation tests.
- `tests/scripts/test_mcp_context_completeness_consumer.py`: schema, payload, continuation,
  reconstruction, transport, timeout, and static-independence tests.
- `tests/scripts/test_mcp_context_completeness_proof.py`: wheel identity, external cwd, absolute
  arguments, environment clearing, byte measurements, failure closure, and cleanup tests.
- `tests/evaluation/test_mcp_context_completeness_documentation.py`: canonical-reference,
  navigation, compatibility, non-claim, and safe-issue-report regressions.
- `docs/how-to/run-mcp-context-completeness-proof.md`: reproducible installed-wheel proof command,
  receipt, proves/does-not-prove boundary, and troubleshooting.
- `.github/workflows/mcp-context-completeness-proof.yml`: same-wheel Python 3.12/3.13 offline proof.

### Modify

- `src/mke/domain/__init__.py`: re-export only the new domain values used by existing layers.
- `src/mke/application/__init__.py`: add façade methods for paged Search and active Evidence reads;
  keep existing methods unchanged.
- `src/mke/runtime_owner.py`: own one ephemeral cursor key and non-secret owner epoch.
- `src/mke/retrieval/query_policy.py`: expose the frozen query-policy revision.
- `src/mke/retrieval/cjk_active_scan.py`: expose selected-pool/cap metadata while preserving the
  existing ranking function and its top-10 results.
- `src/mke/adapters/sqlite/__init__.py`: derive the active-set fingerprint and implement bounded
  FTS/CJK page and active-Evidence read snapshots in existing PEP 249 transactions.
- `src/mke/interfaces/mcp_schemas.py`: add strict v2 Search and v1 Read input/output models.
- `src/mke/interfaces/mcp_contract.py`: add only explicit strict-v1 size preflights; keep the
  existing legacy/v1 responsibilities otherwise unchanged.
- `src/mke/interfaces/mcp_server.py`: register exactly two tools, structured output, normative
  descriptions, and accurate annotations; improve all eight existing descriptions/annotations.
- `src/mke/interfaces/public_errors.py`: add only approved stable causes.
- `tests/retrieval/test_cjk_active_scan.py`: preserve ranking and assert 9/10/11 eligible cap
  metadata.
- `tests/runtime/test_owner_runtime.py`: one-owner material reuse and restart invalidation.
- `tests/interfaces/test_mcp_v1_schemas.py`: typed oversized Search/Ask errors and unchanged bounded
  successes.
- `tests/interfaces/test_mcp_legacy_schema_snapshot.py`: prove the frozen legacy subset remains
  byte-for-byte unchanged; do not rewrite its fixture.
- `tests/interfaces/test_consumer_source_pack_contract_fixture.py`: continue validating the
  immutable v0.1.4 eight-tool fixture against its release scope.
- `README.md`, `README_CN.md`, `docs/README.md`: capability summary and canonical links only.
- `docs/reference/mcp-contract.md`: canonical ten-tool inventory and full contract.
- `docs/how-to/use-mke-mcp.md`: tool chooser, absolute-path quickstart, continuation, exact read,
  recovery, trust, and compatibility.
- `docs/explanation/architecture.md`: one shared application path and derived authority snapshot.
- `CHANGELOG.md`: add an `[Unreleased]` entry without assigning a release version.

### Read Only

- `tests/fixtures/mcp/legacy-tool-schemas.json`.
- `tests/fixtures/consumer-source-pack-v1/**`.
- `tests/fixtures/pdf/text-layer.pdf`; the proof controller copies it byte-for-byte into the
  external allowed root for the active-set mutation step.
- `docs/releases/v0.1.4.md` and all previous release records.
- Export schemas, fixtures, proof scripts, and compiled-library limits.
- Retrieval benchmark corpora, qrels, protocol locks, reports, gates, and promotion decisions.
- `pyproject.toml` and `uv.lock`; this capability adds no dependency or version bump.

## Target Data Flow

```text
FastMCP typed tool
  -> mcp_completeness_contract branch validation
  -> OwnerRuntimeState cursor material
  -> KnowledgeEngine shared façade
  -> SQLite one read transaction
       -> validate active Run/Publication/Evidence graph
       -> derive active_set_fingerprint
       -> lightweight FTS lookahead + bounded text load, CJK page, or active Evidence range
  -> pure excerpt/chunk + canonical budget assembly
  -> strict frozen success/error RootModel
  -> structuredContent + compatibility text
```

## Task 0: Freeze baseline and prove the targeted REDs

**Files:**

- Read: `AGENTS.md`
- Read: `docs/superpowers/specs/2026-07-25-mcp-context-budget-completeness.md`
- Read: this plan
- Create: `tests/interfaces/test_mcp_context_completeness.py`
- Modify later, not in this task: production files

- [ ] **Step 1: Verify the exact execution base and clean ownership**

Run:

```bash
git status --short --branch
git rev-parse HEAD
git rev-list --count d0b3b8e3f73005851570cf8fcf546030a9e2ceb5..HEAD
git diff --name-status d0b3b8e3f73005851570cf8fcf546030a9e2ceb5..HEAD
```

Expected: the existing isolated branch is clean; HEAD contains the approved spec and this plan;
there are exactly those two task-owned documentation commits/paths before implementation.

- [ ] **Step 2: Run the frozen baseline regressions**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/interfaces/test_mcp_legacy_schema_snapshot.py \
  tests/interfaces/test_mcp_v1_schemas.py \
  tests/interfaces/test_mcp_contract.py \
  tests/interfaces/test_mcp_server.py \
  tests/interfaces/test_consumer_source_pack_contract_fixture.py \
  tests/adapters/test_sqlite_fts.py \
  tests/adapters/test_sqlite_cjk_active_scan.py
```

Expected: PASS with no fixture rewrite.

- [ ] **Step 3: Write the three public-contract REDs**

Create focused tests with these exact observable assertions:

```python
async def test_red_search_has_no_selection_completeness(current_server):
    tools = {tool.name: tool for tool in await current_server.list_tools()}
    assert "search_library_v2" in tools


def test_red_oversized_v1_has_no_typed_exact_read(oversized_config):
    search = search_library_v1(oversized_config, "late marker", limit=1)
    assert search.root.problem == "response_too_large"
    assert search.root.next_step == "use_search_library_v2"


def test_red_cjk_cap_is_not_observable(cjk_eleven_match_config):
    response = search_library_v2(
        cjk_eleven_match_config,
        SearchLibraryV2Request(
            root={"query": "完整性上下文预算", "limit": 5}
        ),
    )
    terminal = follow_all_search_pages(cjk_eleven_match_config, response)
    assert terminal.root.selection.status == "capped"
    assert terminal.root.selection.limit_reason == "retrieval_strategy_cap"
```

The helpers belong in the test file and must use public MCP contract functions, not adapter
internals. Create deterministic state through existing test builders.

- [ ] **Step 4: Run RED and retain the exact failure evidence**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/interfaces/test_mcp_context_completeness.py \
  -k 'red_search or red_oversized or red_cjk'
```

Expected: all three tests FAIL because `search_library_v2` and `read_evidence_v1` do not exist and
strict-v1 oversized output has no typed preflight. If any test passes against the baseline, stop
and narrow or cancel the corresponding contract change.

Do not commit a RED-only production branch state. Keep the failing tests for Task 5 GREEN.

## Task 1: Define authority, descriptor, and UTF-8 completeness primitives

**Files:**

- Create: `src/mke/domain/evidence_access.py`
- Create: `src/mke/application/evidence_access.py`
- Create: `tests/domain/test_evidence_access.py`
- Create: `tests/application/test_evidence_access.py`
- Modify: `src/mke/domain/__init__.py`

- [ ] **Step 1: Write RED domain and byte-boundary tests**

Cover:

- active fingerprint row-order independence and sensitivity to every authority field;
- display name and media type exclusion;
- lowercase `sha256:` validation and complete descriptor invariants;
- FTS and CJK match hints with stable order;
- ASCII, CJK, emoji, and combining-mark byte boundaries;
- beginning/middle/end query windows and explicit prefix fallback;
- exact chunk partition with positive progress at `max_bytes=4`;
- 16 MiB readable ceiling and non-empty active Evidence;

Use assertions such as:

```python
def test_query_window_finds_a_match_after_the_prefix() -> None:
    text = "前缀" * 1500 + "publication authority" + "后缀" * 1500
    excerpt = build_excerpt(text, (MatchHint("publication authority", 0, 0),))
    assert excerpt.kind == "query_window"
    assert "publication authority" in excerpt.text
    assert excerpt.returned_utf8_bytes <= 2048
    assert excerpt.complete is False


def test_utf8_chunks_reconstruct_exact_bytes() -> None:
    text = "A中🙂e\u0301" * 100
    chunks = list(iter_utf8_chunks(text, max_bytes=4))
    assert b"".join(chunk.text.encode("utf-8") for chunk in chunks) == text.encode("utf-8")
    assert all(chunk.returned_utf8_bytes > 0 for chunk in chunks)
```

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/domain/test_evidence_access.py \
  tests/application/test_evidence_access.py
```

Expected: FAIL during collection because the new modules do not exist.

- [ ] **Step 2: Implement immutable domain contracts**

Implement and re-export these exact interfaces:

```python
@dataclass(frozen=True)
class ActiveAuthorityRecord:
    source_id: str
    content_fingerprint: str
    active_publication_id: str
    active_revision: int
    run_id: str
    manifest_evidence_count: int
    manifest_sha256: str
    required_stages: tuple[str, ...]
    extractor_fingerprint: str


@dataclass(frozen=True)
class ActiveAuthoritySnapshot:
    observation: ActivePublicationObservation
    active_set_fingerprint: str


@dataclass(frozen=True)
class EvidenceDescriptor:
    evidence_id: str
    source_id: str
    content_fingerprint: str
    publication_id: str
    publication_revision: int
    run_id: str
    locator_kind: Literal["page", "timestamp_ms"]
    locator_start: int
    locator_end: int
    evidence_text_sha256: str
    original_utf8_bytes: int


@dataclass(frozen=True)
class ActiveEvidenceRecord:
    evidence_id: str
    source_id: str
    content_fingerprint: str
    publication_id: str
    publication_revision: int
    run_id: str
    locator_kind: Literal["page", "timestamp_ms"]
    locator_start: int
    locator_end: int
    original_utf8_bytes: int


@dataclass(frozen=True)
class MatchHint:
    text: str
    clause_order: int
    term_order: int


@dataclass(frozen=True)
class EvidenceExcerpt:
    kind: Literal["query_window", "prefix_fallback"]
    text: str
    start_utf8_byte: int
    end_utf8_byte: int
    prefix_omitted: bool
    suffix_omitted: bool
    complete: bool
    returned_utf8_bytes: int
    content_trust: Literal["untrusted_evidence"] = "untrusted_evidence"


@dataclass(frozen=True)
class Utf8Chunk:
    text: str
    offset_bytes: int
    returned_utf8_bytes: int
    next_offset_bytes: int


@dataclass(frozen=True)
class SelectedEvidence:
    provenance: SearchResultProvenance
    hints: tuple[MatchHint, ...]


@dataclass(frozen=True)
class EvidenceSearchPage:
    authority: ActiveAuthoritySnapshot
    normalized_query: str
    strategy_id: str
    strategy_revision: int
    query_policy: str
    query_policy_revision: int
    position: int
    results: tuple[SelectedEvidence, ...]
    more_in_selected_pool: bool
    eligible_discarded_by_cap: bool


@dataclass(frozen=True)
class EvidenceReadSnapshot:
    authority: ActiveAuthoritySnapshot
    record: ActiveEvidenceRecord
    text: str | None
    range_bytes: bytes
    offset_bytes: int
```

`derive_active_set_fingerprint(records)` must canonicalize this exact shape with
`sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, UTF-8 encoding, records sorted by
`source_id`, and a domain separator:

```python
payload = {
    "domain": "mke.active_set_fingerprint",
    "schema_version": "mke.active_set_fingerprint.v1",
    "library_id": "local",
    "records": [record_payload(record) for record in sorted_records],
}
return f"sha256:{sha256(canonical_json(payload)).hexdigest()}"
```

- [ ] **Step 3: Implement pure excerpt and chunk helpers**

Implement:

```python
def utf8_size(value: str) -> int:
    return len(value.encode("utf-8"))


def build_excerpt(
    text: str,
    hints: tuple[MatchHint, ...],
    *,
    max_bytes: int = MAX_EXCERPT_BYTES,
) -> EvidenceExcerpt:
    """Return the earliest stable query window or an explicit prefix fallback."""


def read_utf8_chunk(data: bytes, *, offset: int, max_bytes: int) -> Utf8Chunk:
    """Return one positive-progress code-point-safe half-open byte range."""


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
```

Normalize only for match discovery. Maintain an index map back to the original string, select the
earliest UTF-8 byte match followed by clause and term order, balance the remaining byte budget
around that span, and move both boundaries inward to code-point boundaries. Do not claim grapheme
cluster safety.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/domain/test_evidence_access.py \
  tests/application/test_evidence_access.py
uv run ruff check \
  src/mke/domain/evidence_access.py \
  src/mke/application/evidence_access.py \
  tests/domain/test_evidence_access.py \
  tests/application/test_evidence_access.py
git diff --check
git add \
  src/mke/domain/__init__.py \
  src/mke/domain/evidence_access.py \
  src/mke/application/evidence_access.py \
  tests/domain/test_evidence_access.py \
  tests/application/test_evidence_access.py
git commit -m "feat(mcp): define Evidence completeness primitives"
```

Expected: focused tests and Ruff PASS; commit contains only Task 1 paths.

## Task 2: Add ephemeral owner cursor material and strict cursor codec

**Files:**

- Create: `src/mke/application/mcp_cursor.py`
- Create: `tests/application/test_mcp_cursor.py`
- Modify: `src/mke/runtime_owner.py`
- Modify: `tests/runtime/test_owner_runtime.py`

- [ ] **Step 1: Write RED cursor and owner-lifecycle tests**

Cover canonical round-trip, no base64 padding, exact allowed fields, duplicate/unknown JSON fields,
oversized tokens, malformed UTF-8/JSON/base64, Search/Read wrong-tool use, position and size bounds,
same-epoch bad MAC, old epoch, active fingerprint drift, retrieval strategy revision drift, query
policy revision drift, restart invalidation, and absence of Evidence text/path/key in decoded
payloads.

Use deterministic key/epoch injection only in tests:

```python
def test_owner_restart_expires_cursor() -> None:
    first = OwnerRuntimeState(cursor_key=b"k" * 32, owner_epoch="epoch-a")
    token = encode_search_cursor(first.cursor_material(), search_payload(position=1))
    second = OwnerRuntimeState(cursor_key=b"z" * 32, owner_epoch="epoch-b")
    with pytest.raises(CursorExpiredError):
        decode_search_cursor(token, second.cursor_material())


def test_same_epoch_bad_mac_is_invalid() -> None:
    owner = OwnerRuntimeState(cursor_key=b"k" * 32, owner_epoch="epoch-a")
    token = tamper_mac(encode_search_cursor(owner.cursor_material(), search_payload()))
    with pytest.raises(InvalidCursorError):
        decode_search_cursor(token, owner.cursor_material())
```

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/application/test_mcp_cursor.py \
  tests/runtime/test_owner_runtime.py
```

Expected: new tests FAIL because cursor material and codec do not exist; existing owner tests remain
GREEN.

- [ ] **Step 2: Extend `OwnerRuntimeState` without changing recovery behavior**

Add:

```python
@dataclass(frozen=True)
class CursorOwnerMaterial:
    key: bytes
    epoch: str


class OwnerRuntimeState:
    def __init__(
        self,
        *,
        cursor_key: bytes | None = None,
        owner_epoch: str | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._recovered_databases: set[Path] = set()
        self._cursor_material = CursorOwnerMaterial(
            key=cursor_key if cursor_key is not None else secrets.token_bytes(32),
            epoch=owner_epoch if owner_epoch is not None else secrets.token_hex(16),
        )

    def cursor_material(self) -> CursorOwnerMaterial:
        return self._cursor_material
```

Validate injected keys as exactly 32 bytes and injected epochs as lowercase 32-hex tokens. The
default material is created once per owner runtime and is never persisted or logged.

- [ ] **Step 3: Implement strict cursor payloads and validation phases**

Define separate frozen dataclasses with these exact bindings:

```python
class InvalidCursorError(ValueError):
    """Cursor syntax, authentication, tool, or bound-field validation failed."""


class CursorExpiredError(ValueError):
    def __init__(
        self,
        reason: Literal[
            "owner_restarted",
            "active_set_changed",
            "retrieval_policy_changed",
            "evidence_changed",
        ],
    ) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class SearchCursorPayload:
    schema_version: Literal["mke.mcp_cursor.v1"]
    tool: Literal["search_library_v2"]
    owner_epoch: str
    active_set_fingerprint: str
    normalized_query: str
    query_fingerprint: str
    strategy_id: str
    strategy_revision: int
    query_policy: str
    query_policy_revision: int
    position: int
    page_size: int
    response_schema: Literal["mke.search_library_response.v2"]


@dataclass(frozen=True)
class ReadCursorPayload:
    schema_version: Literal["mke.mcp_cursor.v1"]
    tool: Literal["read_evidence_v1"]
    owner_epoch: str
    active_set_fingerprint: str
    evidence_id: str
    source_id: str
    content_fingerprint: str
    publication_id: str
    publication_revision: int
    run_id: str
    locator_kind: Literal["page", "timestamp_ms"]
    locator_start: int
    locator_end: int
    evidence_text_sha256: str
    original_utf8_bytes: int
    position: int
    max_bytes: int
    response_schema: Literal["mke.read_evidence_response.v1"]
```

Encode:

```python
payload_bytes = canonical_json(payload)
mac = hmac.new(material.key, payload_bytes, sha256).digest()
envelope = {"payload": base64url(payload_bytes), "mac": base64url(mac)}
token = base64url(canonical_json(envelope))
```

Decode in explicit pure phases. The cursor module never opens the repository:

```python
parsed = parse_cursor_untrusted(token, expected_tool="search_library_v2")
validate_owner_epoch(parsed, material.epoch)
authenticate_cursor(parsed, material)
validate_search_bindings(parsed, current_authority, current_policy)
```

`parse_cursor_untrusted` performs token byte-size, base64, UTF-8, duplicate-key, exact-field,
integer, and range checks without repository access. The interface contract obtains
`current_authority` from the adapter's same-transaction validator callback, then calls the three
pure validation functions in the approved epoch -> HMAC -> binding order. Authentication uses
`hmac.compare_digest`. The public layer never renders parsed payloads.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/application/test_mcp_cursor.py \
  tests/runtime/test_owner_runtime.py \
  tests/runtime/test_runtime_composition.py
uv run ruff check \
  src/mke/application/mcp_cursor.py \
  src/mke/runtime_owner.py \
  tests/application/test_mcp_cursor.py \
  tests/runtime/test_owner_runtime.py
git diff --check
git add \
  src/mke/application/mcp_cursor.py \
  src/mke/runtime_owner.py \
  tests/application/test_mcp_cursor.py \
  tests/runtime/test_owner_runtime.py
git commit -m "feat(mcp): add process-bound completeness cursors"
```

Expected: focused tests and existing runtime composition PASS.

## Task 3: Add same-transaction active authority, paged selection, and exact reads

**Files:**

- Modify: `src/mke/retrieval/query_policy.py`
- Modify: `src/mke/retrieval/cjk_active_scan.py`
- Modify: `src/mke/adapters/sqlite/__init__.py`
- Modify: `src/mke/application/__init__.py`
- Create: `tests/adapters/test_sqlite_evidence_access.py`
- Modify: `tests/retrieval/test_cjk_active_scan.py`
- Modify: `tests/adapters/test_sqlite_cjk_active_scan.py`
- Modify: `tests/adapters/test_sqlite_fts.py`

- [ ] **Step 1: Write RED selection and authority tests**

Require:

- fingerprint and selected/read rows come from one transaction;
- the adapter invokes an injected authority validator after deriving the fingerprint but before
  any FTS/CJK selection or Evidence range query;
- validator failure rolls back and performs no selection/Evidence lookup;
- active graph corruption fails closed before result projection;
- FTS pages preserve exact existing order and return `limit + 1` only for continuation detection;
- FTS lookahead loads metadata only, loads at most 16 MiB of candidate text per call, and always
  admits one individually admissible candidate so a cursor cannot stall;
- positions 0/1/N have no duplicate or skipped Evidence;
- CJK eligible counts 9, 10, and 11 preserve existing top-10 ranking while exposing only the
  11-case cap;
- CJK page sizes 5 and 10 report `more_in_selected_pool` before terminal `capped`;
- Read rejects unknown, inactive, superseded, cross-Publication, empty, and >16 MiB Evidence
  uniformly;
- initial Read returns complete text for one-time hashing; continuation returns only
  `max_bytes + 3` bytes from the requested byte position;
- descriptor/byte-count/authority drift fails closed;
- commit on success and rollback on every error.

Inject an activation from a second SQLite connection between hypothetical separate reads and assert
the public snapshot remains internally consistent.

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/adapters/test_sqlite_evidence_access.py \
  tests/retrieval/test_cjk_active_scan.py \
  tests/adapters/test_sqlite_cjk_active_scan.py \
  tests/adapters/test_sqlite_fts.py
```

Expected: new tests FAIL; legacy retrieval tests PASS.

- [ ] **Step 2: Expose CJK selected-pool metadata without changing legacy ranking**

Add:

```python
@dataclass(frozen=True)
class CjkActiveScanSelection:
    results: tuple[CjkActiveScanResult, ...]
    eligible_count: int
    discarded_by_strategy_cap: bool


def select_cjk_active_scan_candidates(
    candidates: tuple[CjkActiveScanCandidate, ...],
    terms: tuple[str, ...],
    *,
    parameters: CjkActiveScanParameters = CJK_ACTIVE_SCAN_PARAMETERS,
) -> CjkActiveScanSelection:
    ranked = rank_all_eligible_candidates(candidates, terms, parameters=parameters)
    return CjkActiveScanSelection(
        results=ranked[: parameters.max_results],
        eligible_count=len(ranked),
        discarded_by_strategy_cap=len(ranked) > parameters.max_results,
    )
```

Keep `rank_cjk_active_scan_candidates(...)` as a compatibility wrapper returning
`select_cjk_active_scan_candidates(...).results`. Preserve the 1,000-candidate failure, sort key,
scores, matched terms, and top-10 output exactly.

Set `QUERY_POLICY_REVISION = 1` in `query_policy.py`; do not change either policy's compilation.

- [ ] **Step 3: Derive active authority from existing validated rows**

After `_read_and_validate_active_publication_rows()`, map each row to
`ActiveAuthorityRecord`. Required stages are parsed as a sorted, unique tuple. Derive the
fingerprint before selection/read and return `ActiveAuthoritySnapshot`.

Do not persist the fingerprint and do not add a table or column.

- [ ] **Step 4: Implement bounded FTS/CJK pages**

Add:

```python
def search_evidence_page(
    self,
    query: str,
    *,
    position: int,
    page_size: int,
    authority_validator: Callable[[ActiveAuthoritySnapshot], None],
) -> EvidenceSearchPage:
    """Return one active-authority-bound page and one continuation lookahead."""


def _search_fts_page(
    self,
    match_query: str,
    *,
    position: int,
    fetch_count: int,
) -> list[_EvidenceSearchCandidate]:
    """Use the existing ORDER BY with LIMIT/OFFSET and omit full text."""
```

FTS fetches at most `page_size + 1` lightweight candidates containing identity, locator, score,
match hints, and `length(CAST(text AS BLOB))`, but not full text. Load full text only for the
ordered first-page candidates whose cumulative text bytes fit `MAX_SEARCH_PAGE_TEXT_BYTES`.
Because each admissible Evidence is at most the same 16 MiB ceiling, admit the first candidate even
when it exactly consumes the budget; leave every later budget-dropped candidate at the next cursor
position. CJK continues to rank under its existing 16 MiB aggregate scan and candidate budgets,
slices the selected top-10 pool, and carries `discarded_by_strategy_cap`. Flatten FTS diagnostic
alternatives into ordered `MatchHint` values and preserve per-result CJK `matched_terms`.
Set `more_in_selected_pool=True` whenever either metadata lookahead or the text budget leaves an
unemitted selected candidate. The next position advances by `len(results)` only.

Define `_EvidenceSearchCandidate` as a private frozen adapter record. It is not re-exported and
never crosses the `SQLiteStore` boundary; after the bounded text load, the adapter returns the
existing project-owned `SearchResultProvenance` inside `SelectedEvidence`.

Inside the existing transaction, derive `ActiveAuthoritySnapshot`, call `authority_validator` once,
then execute selection. The initial-call validator is a no-op; continuation passes the cursor
validation closure. The closure must be pure and non-reentrant: it may compare authority, owner
epoch, policy, and HMAC state, but may not call the store or start another transaction. A raised
cursor error rolls back before selection.

The existing `search()`, `_search_fts()`, and `search_cjk_active_scan()` outputs and query shapes
must remain unchanged.

- [ ] **Step 5: Implement active Evidence initial/range reads**

Add:

```python
class EvidenceNotFoundError(LookupError):
    """The requested ID is not current admissible active Evidence."""


class EvidenceResponseTooLargeError(ValueError):
    """The active Evidence exceeds the bounded exact-read contract."""


def read_active_evidence(
    self,
    evidence_id: str,
    *,
    offset_bytes: int = 0,
    range_bytes: int | None = None,
    authority_validator: Callable[[ActiveAuthoritySnapshot], None],
) -> EvidenceReadSnapshot:
    """Validate active authority and return full initial text or one bounded BLOB range."""
```

The active join must bind Evidence -> Run -> Publication -> Source active pointer -> manifest ->
asset. Initial mode loads the bounded complete text, computes byte count in Python, and lets the
application create the complete descriptor and hash once. Continuation mode selects metadata,
`length(CAST(text AS BLOB))`, and
`substr(CAST(text AS BLOB), offset + 1, range_bytes + 3)` without loading the complete text.

As with Search, derive authority and invoke `authority_validator` in the same transaction before
the Evidence join/range query.

Map all absence/inactivity cases to one internal `EvidenceNotFoundError`; map empty/corrupt graph
to a redacted internal failure; map the 16 MiB ceiling to `EvidenceResponseTooLargeError`.

- [ ] **Step 6: Add façade methods and verify GREEN**

`KnowledgeEngine` forwards:

```python
def search_evidence_page(
    self,
    query: str,
    *,
    position: int,
    page_size: int,
    authority_validator: Callable[[ActiveAuthoritySnapshot], None],
) -> EvidenceSearchPage:
    return self._store.search_evidence_page(
        query,
        position=position,
        page_size=page_size,
        authority_validator=authority_validator,
    )


def read_active_evidence(
    self,
    evidence_id: str,
    *,
    offset_bytes: int = 0,
    range_bytes: int | None = None,
    authority_validator: Callable[[ActiveAuthoritySnapshot], None],
) -> EvidenceReadSnapshot:
    return self._store.read_active_evidence(
        evidence_id,
        offset_bytes=offset_bytes,
        range_bytes=range_bytes,
        authority_validator=authority_validator,
    )
```

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/adapters/test_sqlite_evidence_access.py \
  tests/retrieval/test_cjk_active_scan.py \
  tests/adapters/test_sqlite_cjk_active_scan.py \
  tests/adapters/test_sqlite_fts.py \
  tests/application/test_cjk_active_scan_runtime.py
uv run ruff check \
  src/mke/retrieval/query_policy.py \
  src/mke/retrieval/cjk_active_scan.py \
  src/mke/adapters/sqlite/__init__.py \
  src/mke/application/__init__.py \
  tests/adapters/test_sqlite_evidence_access.py \
  tests/retrieval/test_cjk_active_scan.py
git diff --check
git add \
  src/mke/retrieval/query_policy.py \
  src/mke/retrieval/cjk_active_scan.py \
  src/mke/adapters/sqlite/__init__.py \
  src/mke/application/__init__.py \
  tests/adapters/test_sqlite_evidence_access.py \
  tests/retrieval/test_cjk_active_scan.py \
  tests/adapters/test_sqlite_cjk_active_scan.py \
  tests/adapters/test_sqlite_fts.py
git commit -m "feat(mcp): add active Evidence page and read snapshots"
```

Expected: all focused adapter/retrieval tests PASS with unchanged legacy ranking.

## Task 4: Assemble bounded Search/Read projections and strict-v1 size preflights

**Files:**

- Modify: `src/mke/application/evidence_access.py`
- Modify: `src/mke/interfaces/mcp_contract.py`
- Modify: `src/mke/interfaces/public_errors.py`
- Modify: `tests/application/test_evidence_access.py`
- Modify: `tests/interfaces/test_mcp_v1_schemas.py`
- Modify: `tests/interfaces/test_mcp_contract.py`

- [ ] **Step 1: Write RED budget, continuation, and v1 preflight tests**

Cover:

- two FTS matches with `limit=1` -> `more_available`, then terminal `complete`;
- aggregate excerpt budget drops an un-emitted item and cursor position does not advance past it;
- one metadata-heavy item, many tiny items, and mandatory-metadata overflow;
- exact 32,768 canonical-byte boundary;
- `incomplete_excerpt_count` is diagnostic only;
- illegal `complete`/`more_available`/`capped` projection combinations;
- Read exact reconstruction, final digest equality, stable descriptor, terminal no-cursor;
- initial hash called once; continuation never hashes full text;
- strict-v1 Search and Ask >1,000,000 characters return typed `response_too_large`;
- arbitrary `ValidationError` and graph corruption remain redacted internal failures.

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/application/test_evidence_access.py \
  tests/interfaces/test_mcp_v1_schemas.py \
  tests/interfaces/test_mcp_contract.py
```

Expected: new tests FAIL; existing bounded v1 tests PASS.

- [ ] **Step 2: Implement deterministic page assembly**

Add frozen application projections:

```python
class ResponseTooLargeError(ValueError):
    """Mandatory strict response metadata cannot fit the canonical budget."""


@dataclass(frozen=True)
class SearchMatchProjection:
    descriptor: EvidenceDescriptor
    excerpt: EvidenceExcerpt
    read_evidence_id: str


@dataclass(frozen=True)
class SearchSelectionProjection:
    status: Literal["complete", "more_available", "capped"]
    returned: int
    next_cursor: str | None = None
    limit_reason: Literal["retrieval_strategy_cap"] | None = None


@dataclass(frozen=True)
class SearchPageProjection:
    authority: ActiveAuthoritySnapshot
    query: str
    matches: tuple[SearchMatchProjection, ...]
    selection: SearchSelectionProjection
    incomplete_excerpt_count: int
    content_budget_bytes: int = MAX_EXCERPT_CONTENT_BYTES
    envelope_budget_bytes: int = MAX_CANONICAL_MODEL_BYTES


@dataclass(frozen=True)
class ReadChunkProjection:
    authority: ActiveAuthoritySnapshot
    descriptor: EvidenceDescriptor
    chunk: Utf8Chunk
    complete: bool
    next_cursor: str | None
```

Add application functions:

```python
def assemble_search_page(
    snapshot: EvidenceSearchPage,
    *,
    page_size: int,
    cursor_factory: Callable[[int], str],
) -> SearchPageProjection:
    """Add items only while excerpt and canonical model budgets remain satisfied."""


def assemble_read_chunk(
    snapshot: EvidenceReadSnapshot,
    *,
    max_bytes: int,
    cursor_factory: Callable[[int, str], str],
    bound_text_sha256: str | None = None,
) -> ReadChunkProjection:
    """Return one exact chunk and a cursor only when bytes remain."""
```

For each candidate, build the complete prospective response including selection state and cursor,
serialize canonically, and accept the item only when per-item, aggregate-content, and 32 KiB limits
all pass. If an item is rejected, leave it at the next cursor position. If mandatory metadata
cannot fit, raise `ResponseTooLargeError`.

Initial Read requires `snapshot.text` and `bound_text_sha256 is None`; it hashes the complete
bounded text once and constructs `EvidenceDescriptor`. Continuation requires
`snapshot.text is None` and the cursor-bound `bound_text_sha256`; it validates the stable
`ActiveEvidenceRecord` and byte count without rehashing the full text.

Selection priority is:

```python
if more_in_selected_pool or emitted_count < len(snapshot.results):
    status = "more_available"
elif snapshot.eligible_discarded_by_cap:
    status = "capped"
else:
    status = "complete"
```

- [ ] **Step 3: Add explicit strict-v1 size preflight**

Before constructing `EvidenceRefV1`, check every complete Evidence text with:

```python
if len(result.result.text) > 1_000_000:
    return SearchLibraryResponseV1(
        root=SearchLibraryErrorV1(
            ok=False,
            problem="response_too_large",
            cause="complete Evidence text exceeds the v1 response limit",
            next_step="use_search_library_v2",
        )
    )
```

Ask uses its own frozen response schema with the same cause and next step. Add exactly that cause to
`_ALLOWLISTED_CAUSES`. Do not catch or relabel general Pydantic `ValidationError`.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/application/test_evidence_access.py \
  tests/application/test_mcp_cursor.py \
  tests/interfaces/test_mcp_v1_schemas.py \
  tests/interfaces/test_mcp_contract.py \
  tests/interfaces/test_mcp_legacy_schema_snapshot.py
uv run ruff check \
  src/mke/application/evidence_access.py \
  src/mke/interfaces/mcp_contract.py \
  src/mke/interfaces/public_errors.py \
  tests/application/test_evidence_access.py \
  tests/interfaces/test_mcp_v1_schemas.py \
  tests/interfaces/test_mcp_contract.py
git diff --check
git add \
  src/mke/application/evidence_access.py \
  src/mke/interfaces/mcp_contract.py \
  src/mke/interfaces/public_errors.py \
  tests/application/test_evidence_access.py \
  tests/interfaces/test_mcp_v1_schemas.py \
  tests/interfaces/test_mcp_contract.py
git commit -m "feat(mcp): assemble bounded completeness responses"
```

Expected: focused application/contract tests PASS; frozen legacy schema remains unchanged.

## Task 5: Add strict wire models and register the exact ten-tool surface

**Files:**

- Modify: `src/mke/interfaces/mcp_schemas.py`
- Create: `src/mke/interfaces/mcp_completeness_contract.py`
- Modify: `src/mke/interfaces/mcp_server.py`
- Modify: `src/mke/interfaces/public_errors.py`
- Modify: `tests/interfaces/test_mcp_context_completeness.py`
- Modify: `tests/interfaces/test_mcp_server.py`
- Modify: `tests/interfaces/test_mcp_legacy_schema_snapshot.py`

- [ ] **Step 1: Write RED strict-schema and SDK-output tests**

Require:

- exactly ten tool names;
- each new input schema requires exactly one top-level `request` property whose value is the closed
  initial/cursor-only `oneOf`;
- valid examples accepted by the discovered schema produce the same branch chosen by the runtime
  `TypeAdapter`;
- a missing top-level `request` is rejected by FastMCP before the tool body; a present `request`
  whose value is null, scalar, empty, mixed, or has a null/wrong-scalar field returns the typed
  invalid-request response with zero engine builds/repository calls;
- output schemas are closed `oneOf` success/error unions discriminated by `ok`;
- byte-overflow strings fail even when character length is within bounds;
- terminal Search and Read variants forbid cursors;
- `more_available` requires a cursor; `capped` requires only
  `limit_reason="retrieval_strategy_cap"`;
- `complete=true` forbids `next_cursor`; `complete=false` requires it;
- `outputSchema`, `structuredContent`, and JSON compatibility text agree;
- descriptions include use, do-not-use, mutation/network, Evidence-only, active authority,
  untrusted content, and recovery/read affordance;
- read-only tools have `readOnlyHint=True`, `openWorldHint=False`, and no `idempotentHint`;
- `ingest_file` has `readOnlyHint=False`, `idempotentHint=False`, `openWorldHint=False`;
- `destructiveHint=False` on ingest only after its preservation regression passes.

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/interfaces/test_mcp_context_completeness.py \
  tests/interfaces/test_mcp_server.py \
  tests/interfaces/test_mcp_legacy_schema_snapshot.py
```

Expected: strict wire tests FAIL because the new tools/models are not registered; frozen legacy
schema test remains GREEN.

- [ ] **Step 2: Implement strict frozen Pydantic models**

Reuse:

```python
class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
```

Add encoded-byte validators with `AfterValidator`, not character-count constraints:

```python
def _max_utf8_bytes(limit: int) -> Callable[[str], str]:
    def validate(value: str) -> str:
        if len(value.encode("utf-8")) > limit:
            raise ValueError(f"value exceeds {limit} UTF-8 bytes")
        return value
    return validate
```

Define:

- `SearchInitialV2`, `SearchContinuationV2`, their strict union adapter, and
  `SearchLibraryV2Request`;
- `ReadInitialV1`, `ReadContinuationV1`, their strict union adapter, and
  `ReadEvidenceV1Request`;
- `ActiveAuthoritySnapshotV1`;
- `EvidenceDescriptorV1`;
- `EvidenceExcerptV1`;
- `EvidenceReadAffordanceV1`;
- `SearchMatchV2`;
- `SearchSelectionCompleteV2`, `SearchSelectionMoreV2`, `SearchSelectionCappedV2`;
- `SearchOutputBudgetV1`;
- `SearchLibrarySuccessV2`, `SearchLibraryErrorV2`, `SearchLibraryResponseV2`;
- `EvidenceContentV1`;
- terminal and non-terminal Read success variants;
- `ReadEvidenceErrorV1`, `ReadEvidenceResponseV1`.

Each success/error RootModel uses `Annotated[Success | Error, Field(discriminator="ok")]`.
Selection uses `status`; Read terminality uses `complete`.

- [ ] **Step 3: Implement contract branch validation and cursor recovery**

Use strict branch models plus a request-capture RootModel:

```python
class SearchInitialV2(_StrictModel):
    query: Utf8BoundedQuery
    limit: StrictInt = Field(default=DEFAULT_ASK_LIMIT, ge=1, le=20)


class SearchContinuationV2(_StrictModel):
    cursor: Utf8BoundedCursor


SearchInputV2 = SearchInitialV2 | SearchContinuationV2
SEARCH_INPUT_V2 = TypeAdapter(SearchInputV2)


class SearchLibraryV2Request(RootModel[object]):
    model_config = ConfigDict(frozen=True, strict=True)

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        del core_schema, handler
        return {
            "title": "SearchLibraryV2Request",
            "oneOf": [
                SearchInitialV2.model_json_schema(),
                SearchContinuationV2.model_json_schema(),
            ],
        }
```

`SearchLibraryV2Request` captures any present raw request value so the contract can return the
strict error union for null, scalar, empty, mixed, or wrong-scalar branches. Its public JSON schema is
derived from the two strict branch models through Pydantic's supported schema hook; do not
hand-maintain a second field list. The contract calls
`SEARCH_INPUT_V2.validate_python(request.root)` before building an engine. Read uses the identical
pattern for `evidence_id`/`max_bytes` versus cursor-only continuation. The function parameter itself
has no default, so an omitted outer `request` remains a native FastMCP input-validation failure and
never reaches the tool body.

Classify only failures from these two explicit branch-adapter calls. Never catch a
`ValidationError` raised later by response construction, repository values, or another model:

| Raw branch failure | `problem` | fixed `cause` | `next_step` |
|---|---|---|---|
| null/scalar/empty/extra/mixed/wrong scalar | `invalid_request` | `INVALID_REQUEST_CAUSE` | `use_exactly_one_supported_request_branch` |
| query string above 512 UTF-8 bytes | `invalid_request` | `QUERY_TOO_LARGE_CAUSE` | `narrow_query_to_512_utf8_bytes` |
| cursor string above 4096 UTF-8 bytes | `invalid_cursor` | `CURSOR_TOO_LARGE_CAUSE` | `restart_from_initial_call` |
| `max_bytes` outside the strict integer range | `invalid_request` | `INVALID_MAX_BYTES_CAUSE` | `choose_max_bytes_between_4_and_16384` |

Implement the classifier against the raw captured value before `TypeAdapter.validate_python`; do
not read or render `ValidationError.errors()` inputs, because they may contain Evidence IDs,
queries, or cursor material. All classified failures return before engine construction.

Malformed or oversized cursors must perform zero engine builds/repository calls. For a syntactically
valid token, follow the approved order: resolve the active authority snapshot, compare owner epoch,
authenticate with the current key, then perform any Search page or Evidence range lookup. A
same-epoch bad MAC may observe only the authority snapshot and must never reach selection or
Evidence lookup. Map errors exactly:

```python
ERROR_RECOVERY = {
    "invalid_cursor": (
        INVALID_CURSOR_CAUSE,
        "restart_from_initial_call",
    ),
    "owner_restarted": (
        OWNER_RESTARTED_CAUSE,
        "repeat_initial_call",
    ),
    "active_set_changed": (
        ACTIVE_SET_CHANGED_CAUSE,
        "repeat_search_on_current_publications",
    ),
    "retrieval_policy_changed": (
        RETRIEVAL_POLICY_CHANGED_CAUSE,
        "repeat_search_under_current_strategy",
    ),
    "evidence_changed": (
        EVIDENCE_CHANGED_CAUSE,
        "repeat_initial_call",
    ),
    "evidence_not_found": (
        EVIDENCE_NOT_FOUND_CAUSE,
        "search_current_active_evidence",
    ),
    "response_too_large": (
        RESPONSE_TOO_LARGE_CAUSE,
        "reduce_query_scope_or_report_contract_limit",
    ),
    "evidence_too_large": (
        EVIDENCE_TOO_LARGE_CAUSE,
        "reduce_query_scope_or_report_contract_limit",
    ),
}
```

`InvalidCursorError` maps to `invalid_cursor`; the four `CursorExpiredError` reasons map to
`cursor_expired`; `EvidenceNotFoundError` maps to `evidence_not_found`; both response-size
exceptions map to `response_too_large`.
Causes are fixed public-safe literals. Never render IDs, token payloads, query/Evidence text, paths,
tracebacks, or exception details.

Add the fixed Task 5 causes (`INVALID_CURSOR_CAUSE` through `INVALID_MAX_BYTES_CAUSE`) to the
public-error allowlist. Keep `V1_TEXT_TOO_LARGE_CAUSE` from Task 4. No dynamic exception message is
allowlisted.

- [ ] **Step 4: Register exactly two structured tools with locked SDK syntax**

Import `mcp_completeness_contract` beside the existing `mcp_contract`; do not move or rename any
legacy/v1 contract function. Use the installed MCP 1.28.1 constructor fields exactly:

```python
from mcp.types import ToolAnnotations

READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)

@mcp.tool(
    structured_output=True,
    annotations=READ_ONLY,
)
def search_library_v2(
    request: SearchLibraryV2Request,
) -> SearchLibraryResponseV2:
    """Use for loss-aware active Evidence Search with explicit collection and excerpt completeness.

    Do not use as generated-answer authority or corpus-exhaustive proof. This local read-only tool
    has no network or mutation side effect, returns only active-Publication Evidence, and treats all
    Evidence text as untrusted. Follow next_cursor for more selected results and
    read_evidence_v1 when an excerpt is incomplete.
    """
    return mcp_completeness_contract.search_library_v2(config, request)


@mcp.tool(
    structured_output=True,
    annotations=READ_ONLY,
)
def read_evidence_v1(
    request: ReadEvidenceV1Request,
) -> ReadEvidenceResponseV1:
    """Use to read exact active Evidence when Search marks an excerpt incomplete.

    Do not use for inactive, superseded, or arbitrary storage reads. This local read-only tool has
    no network or mutation side effect, preserves active-Publication authority, returns untrusted
    Evidence content, and uses an opaque process-bound cursor for continuation.
    """
    return mcp_completeness_contract.read_evidence_v1(config, request)
```

Upgrade all eight existing tool descriptions and add accurate annotations without changing their
names, function parameters, return annotations, input schemas, or output schemas.

- [ ] **Step 5: Run the original targeted REDs as GREEN**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/interfaces/test_mcp_context_completeness.py \
  -k 'red_search or red_oversized or red_cjk'
```

Expected: the same three tests now PASS. Rename them by removing the `red_` prefix only after this
GREEN evidence is captured.

- [ ] **Step 6: Verify the complete wire and legacy boundary**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/interfaces/test_mcp_context_completeness.py \
  tests/interfaces/test_mcp_server.py \
  tests/interfaces/test_mcp_v1_schemas.py \
  tests/interfaces/test_mcp_legacy_schema_snapshot.py \
  tests/interfaces/test_consumer_source_pack_contract_fixture.py
uv run ruff check \
  src/mke/interfaces/mcp_schemas.py \
  src/mke/interfaces/mcp_completeness_contract.py \
  src/mke/interfaces/mcp_server.py \
  src/mke/interfaces/public_errors.py \
  tests/interfaces/test_mcp_context_completeness.py \
  tests/interfaces/test_mcp_server.py
git diff --check
git add \
  src/mke/interfaces/mcp_schemas.py \
  src/mke/interfaces/mcp_completeness_contract.py \
  src/mke/interfaces/mcp_server.py \
  src/mke/interfaces/public_errors.py \
  tests/interfaces/test_mcp_context_completeness.py \
  tests/interfaces/test_mcp_server.py \
  tests/interfaces/test_mcp_legacy_schema_snapshot.py
git commit -m "feat(mcp): expose completeness-aware Evidence tools"
```

Expected: exact ten-tool surface PASS; immutable eight-tool release fixture remains unchanged.

## Task 6: Prove exact-inventory migration through an installed standalone consumer

**Files:**

- Create: `tests/fixtures/mcp-context-completeness-v1/mcp-tool-schemas.json`
- Create: `scripts/mcp_context_completeness_fixture.py`
- Create: `scripts/mcp_context_completeness_consumer.py`
- Create: `scripts/mcp_context_completeness_proof.py`
- Create: `tests/scripts/test_mcp_context_completeness_fixture.py`
- Create: `tests/scripts/test_mcp_context_completeness_consumer.py`
- Create: `tests/scripts/test_mcp_context_completeness_proof.py`
- Create: `.github/workflows/mcp-context-completeness-proof.yml`

- [ ] **Step 1: Freeze the exact current ten-tool expectation**

Generate the fixture once from `build_mcp_server(...).list_tools()` in the repository environment.
Store a closed sorted mapping containing each tool's exact `inputSchema`, `outputSchema`,
description, and annotations plus the sorted public safe-cause set. Require:

```python
assert set(expectation["tools"]) == {
    "list_libraries",
    "ingest_file",
    "get_run",
    "search_library",
    "ask_library",
    "list_libraries_v1",
    "search_library_v1",
    "ask_library_v1",
    "search_library_v2",
    "read_evidence_v1",
}
```

Do not copy, edit, or supersede `tests/fixtures/consumer-source-pack-v1/**`. The new consumer must
reject missing and unknown discovered tools.

- [ ] **Step 2: Write RED fixture, standalone client, and controller tests**

Static client restrictions:

```python
FORBIDDEN_IMPORTS = {
    "mke",
    "pydantic",
    "sqlite3",
    "tests",
}
```

Require the consumer to use only standard library plus:

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
```

Test exact discovery, structured/text equality, FTS continuation without gaps, incomplete
query-window excerpt, exact Read reconstruction/digest, terminal CJK cap, active-set expiry, owner
restart expiry and reconnect, same-epoch tamper rejection, bounded legacy/v1 calls, typed oversized
v1 failures, raw canonical/result byte ceilings, stdout protocol isolation, deadlines, child
termination, and closed failure receipts.

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/scripts/test_mcp_context_completeness_fixture.py \
  tests/scripts/test_mcp_context_completeness_consumer.py \
  tests/scripts/test_mcp_context_completeness_proof.py
```

Expected: FAIL because scripts and fixture do not exist.

- [ ] **Step 3: Implement the installed-package fixture producer**

The copied fixture producer runs under the installed wheel's Python from an external cwd. It
creates one database using `KnowledgeEngine`, `CandidateEvidence`, and `RunManifest`:

- two ordered ASCII matches for the Search continuation case;
- one active Evidence text above 1,000,000 characters with the match after byte 2,048;
- eleven eligible CJK Evidence rows for terminal strategy cap;
- the controller-provided `text-layer.pdf` path that the consumer can ingest to change the active
  set.

Use deterministic source-byte SHA-256 values and recognized PDF manifest constants. IDs may be
opaque and are never emitted in the public proof receipt.

The producer has a closed success:

```json
{"status":"passed","fixture_schema":"mke.mcp_context_fixture.v1"}
```

and a closed failure:

```json
{"status":"failed","code":"fixture_setup_failed"}
```

- [ ] **Step 4: Implement the standalone consumer**

The client accepts absolute `--server-command`, `--database`, `--allowed-root`, and expectation
paths. It uses one real stdio session for discovery and normal continuation, invokes
`ingest_file` to change the active set, restarts the server for epoch expiry, reconnects, and
verifies all fifteen design proof points.

Every additive call uses the native request envelope:

```python
first = await session.call_tool(
    "search_library_v2",
    {"request": {"query": query, "limit": 1}},
)
continued = await session.call_tool(
    "search_library_v2",
    {"request": {"cursor": next_cursor}},
)
chunk = await session.call_tool(
    "read_evidence_v1",
    {"request": {"evidence_id": evidence_id, "max_bytes": 16384}},
)
```

Compatibility text equality is:

```python
assert result.structuredContent == expected
assert len(result.content) == 1
assert result.content[0].type == "text"
assert json.loads(result.content[0].text) == expected
```

Measure:

```python
canonical_bytes = len(canonical_json(result.structuredContent))
sdk_result_bytes = len(
    result.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8")
)
assert canonical_bytes <= 32768
assert sdk_result_bytes < 96 * 1024
```

The client never prints cursor, Evidence/query text, IDs, paths, stderr, stack traces, or
environment values.

- [ ] **Step 5: Implement the one-wheel proof controller**

The controller:

1. builds exactly one wheel from the current committed source;
2. exports lock-derived core constraints;
3. creates external Python 3.12 and 3.13 environments;
4. installs the same wheel offline into both;
5. verifies `mke.__file__` and `sys.executable` are inside the external environment and outside the
   repository;
6. copies only the fixture producer, standalone client, ten-tool expectation, and the frozen
   `tests/fixtures/pdf/text-layer.pdf`;
7. runs fixture setup and the consumer from an arbitrary external cwd;
8. clears `PYTHONPATH`, `PYTHONHOME`, and `VIRTUAL_ENV`;
9. uses argv arrays, `shell=False`, explicit timeouts, bounded stdout/stderr, and deterministic
   child termination;
10. emits a closed aggregate receipt and removes temporary state.

Success is assembled from measured interpreter results and contains only:

```python
receipt = {
  "status": "passed",
  "schema_version": "mke.mcp_context_completeness_proof.v1",
  "python_versions": ["3.12", "3.13"],
  "tool_count": 10,
  "search_continuation": "passed",
  "exact_read": "passed",
  "cjk_cap": "passed",
  "cursor_expiry": "passed",
  "legacy_compatibility": "passed",
  "max_canonical_model_bytes": max(
      result.max_canonical_model_bytes for result in interpreter_results
  ),
  "max_sdk_result_bytes": max(
      result.max_sdk_result_bytes for result in interpreter_results
  ),
  "source_import": "installed_wheel",
  "network_access": "not_used"
}
```

The two byte values are the greatest actually observed values across both interpreter runs, not
configured limits; tests require them to be positive and at or below the applicable gate. Failure
is exactly:

```json
{"status":"failed","code":"stable_machine_code"}
```

- [ ] **Step 6: Add a dedicated same-wheel workflow**

Model `.github/workflows/mcp-context-completeness-proof.yml` on the existing consumer-source-pack
proof workflow. Pin the same action SHAs, provision both explicit Python paths and locked caches in
an online step, then run one controller invocation with `UV_OFFLINE=1`. Use one job, not a matrix,
so both interpreters are bound to the same wheel. Set `contents: read`, concurrency cancellation,
and a 15-minute timeout.

- [ ] **Step 7: Verify proof code and run one local installed proof**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/scripts/test_mcp_context_completeness_fixture.py \
  tests/scripts/test_mcp_context_completeness_consumer.py \
  tests/scripts/test_mcp_context_completeness_proof.py
uv run ruff check \
  scripts/mcp_context_completeness_fixture.py \
  scripts/mcp_context_completeness_consumer.py \
  scripts/mcp_context_completeness_proof.py \
  tests/scripts/test_mcp_context_completeness_fixture.py \
  tests/scripts/test_mcp_context_completeness_consumer.py \
  tests/scripts/test_mcp_context_completeness_proof.py
UV_OFFLINE=1 uv run python scripts/mcp_context_completeness_proof.py \
  --python "$(command -v python3.12)" \
  --python "$(command -v python3.13)" \
  --candidate-output /tmp/mke-context-completeness-candidate \
  --json
```

Expected: tests/Ruff PASS and the proof emits only the closed success receipt. If either interpreter
is unavailable, stop and report `python_interpreter_unavailable`; do not substitute another
version.

- [ ] **Step 8: Commit the proof pack**

Run:

```bash
git diff --check
git add \
  tests/fixtures/mcp-context-completeness-v1/mcp-tool-schemas.json \
  scripts/mcp_context_completeness_fixture.py \
  scripts/mcp_context_completeness_consumer.py \
  scripts/mcp_context_completeness_proof.py \
  tests/scripts/test_mcp_context_completeness_fixture.py \
  tests/scripts/test_mcp_context_completeness_consumer.py \
  tests/scripts/test_mcp_context_completeness_proof.py \
  .github/workflows/mcp-context-completeness-proof.yml
git commit -m "test(mcp): prove installed completeness contract"
```

Expected: one bounded proof-pack commit; no generated wheel, database, venv, or proof receipt is
tracked.

## Task 7: Publish canonical docs and compatibility boundaries

**Files:**

- Create: `docs/how-to/run-mcp-context-completeness-proof.md`
- Create: `tests/evaluation/test_mcp_context_completeness_documentation.py`
- Modify: `docs/reference/mcp-contract.md`
- Modify: `docs/how-to/use-mke-mcp.md`
- Modify: `docs/explanation/architecture.md`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `docs/README.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Write RED documentation regressions**

Require one canonical complete inventory in `docs/reference/mcp-contract.md`; README files link to
it without duplicating schemas. Require all of:

- v2 is an MKE tool-contract suffix, not MCP protocol/SDK 2.x;
- two-dimensional selection/item completeness;
- `capped` terminal but not exhaustive;
- exact active Evidence through `read_evidence_v1`;
- opaque process/authority-bound cursors;
- active-only Publication authority and untrusted content;
- Ask is deterministic Evidence convenience, not generated/exhaustive authority;
- Export remains a separate bounded delivery contract;
- exact-inventory migration from immutable eight-tool release evidence to current ten-tool
  expectation;
- absolute installed executable/database/allowed-root quickstart;
- stable problem/cause/next-step recovery table;
- safe issue checklist with versions, public problem code, proof step, and restart result;
- explicit exclusions for Evidence/query text, cursor, database path, username, local filename,
  private configuration, production/deployment/adoption/performance claims.

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/evaluation/test_mcp_context_completeness_documentation.py
```

Expected: FAIL because the new how-to and links do not exist.

- [ ] **Step 2: Update the canonical reference and how-to**

Document exact inputs, strict success/error shapes, status tables, byte budgets, cursor lifecycle,
recovery operations, descriptions, annotations, and all ten tool names only in
`docs/reference/mcp-contract.md`.

`docs/how-to/use-mke-mcp.md` contains the tool chooser and this absolute-path pattern:

```json
{
  "command": "/ABSOLUTE/PATH/TO/INSTALLED/mke",
  "args": [
    "--db",
    "/ABSOLUTE/PATH/TO/mke.sqlite",
    "mcp",
    "--allowed-root",
    "/ABSOLUTE/PATH/TO/library"
  ]
}
```

Add continuation examples with opaque placeholder tokens only; never include a real token.

- [ ] **Step 3: Document proof, architecture, navigation, and unreleased change**

The proof how-to states the exact command, interpreter/cache prerequisites, arbitrary-cwd and
installed-identity checks, closed receipt, cleanup, proves/does-not-prove boundary, and safe
troubleshooting.

Architecture shows the one shared application path and labels `active_set_fingerprint` as a derived
continuation observation, never a Publication. README files and `docs/README.md` add short links.
Add an `[Unreleased]` CHANGELOG entry without a version/date and without claiming release,
production deployment, adoption, or performance.

- [ ] **Step 4: Verify docs and commit**

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/evaluation/test_mcp_context_completeness_documentation.py \
  tests/evaluation/test_repository_governance_documentation.py \
  tests/evaluation/test_consumer_source_pack_documentation.py
uv run ruff check tests/evaluation/test_mcp_context_completeness_documentation.py
git diff --check
git add \
  docs/how-to/run-mcp-context-completeness-proof.md \
  tests/evaluation/test_mcp_context_completeness_documentation.py \
  docs/reference/mcp-contract.md \
  docs/how-to/use-mke-mcp.md \
  docs/explanation/architecture.md \
  README.md \
  README_CN.md \
  docs/README.md \
  CHANGELOG.md
git commit -m "docs(mcp): document completeness and exact reads"
```

Expected: documentation tests and governance regressions PASS.

## Task 8: Run full verification and prepare authority review

**Files:**

- Modify only when a failing gate demonstrates a task-owned defect.
- Do not create a public implementation review before the independent authority review is
  complete.

- [ ] **Step 1: Run focused contract and proof gates**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/domain/test_evidence_access.py \
  tests/application/test_evidence_access.py \
  tests/application/test_mcp_cursor.py \
  tests/adapters/test_sqlite_evidence_access.py \
  tests/retrieval/test_cjk_active_scan.py \
  tests/interfaces/test_mcp_context_completeness.py \
  tests/interfaces/test_mcp_v1_schemas.py \
  tests/interfaces/test_mcp_legacy_schema_snapshot.py \
  tests/interfaces/test_consumer_source_pack_contract_fixture.py \
  tests/scripts/test_mcp_context_completeness_fixture.py \
  tests/scripts/test_mcp_context_completeness_consumer.py \
  tests/scripts/test_mcp_context_completeness_proof.py \
  tests/evaluation/test_mcp_context_completeness_documentation.py
```

Expected: PASS.

- [ ] **Step 2: Run compatibility suites**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/application \
  tests/adapters \
  tests/retrieval \
  tests/interfaces \
  tests/proof \
  tests/scripts/test_consumer_source_pack_client.py \
  tests/scripts/test_consumer_source_pack_proof.py \
  tests/scripts/test_compiled_library_export_consumer.py \
  tests/scripts/test_compiled_library_export_proof.py
```

Expected: PASS; Python, CLI, legacy/v1 MCP, current installed consumer, Publication, Evidence,
retrieval, Ask, and Export regressions remain GREEN.

- [ ] **Step 3: Run full project quality gates**

```bash
UV_OFFLINE=1 uv run pytest -q
uv run ruff check .
uv run pyright
UV_OFFLINE=1 uv build
git diff --check
```

Expected: full pytest PASS with only pre-existing documented skips/warnings; Ruff PASS; Pyright
reports zero errors; sdist and wheel build.

- [ ] **Step 4: Rebuild and rerun the terminal installed proof on committed HEAD**

Remove only the task-owned temporary candidate directory, then run:

```bash
UV_OFFLINE=1 uv run python scripts/mcp_context_completeness_proof.py \
  --python "$(command -v python3.12)" \
  --python "$(command -v python3.13)" \
  --candidate-output /tmp/mke-context-completeness-final \
  --json
```

Expected: closed PASS receipt from the exact committed HEAD. Verify the proof imports the installed
wheel, not the source tree.

- [ ] **Step 5: Run boundary scans and inspect the complete diff**

```bash
git status --short --branch
git log --oneline --decorate \
  d0b3b8e3f73005851570cf8fcf546030a9e2ceb5..HEAD
git diff --stat \
  d0b3b8e3f73005851570cf8fcf546030a9e2ceb5..HEAD
git diff --check \
  d0b3b8e3f73005851570cf8fcf546030a9e2ceb5..HEAD
rg -n \
  'BEGIN [A-Z ]*PRIVATE KEY|api[_-]?key[[:space:]]*[:=]|authorization:[[:space:]]*bearer|password[[:space:]]*[:=]|/(Users|home)/[^/[:space:]]+/' \
  README.md README_CN.md CHANGELOG.md docs src tests scripts .github
```

Inspect every match; allow only existing public technical uses after manual review. Expected: no
credential, personal local-path, or non-project workflow disclosure.

- [ ] **Step 6: Self-review against the approved spec**

Create an authority-review checklist outside the implementation diff mapping every section:

- Public Tool Inventory -> Task 5/6;
- Strict Wire Rules -> Task 5;
- Active Authority Snapshot -> Task 1/3;
- Evidence Descriptor -> Task 1/3/5;
- Search v2 and selection/item completeness -> Task 3/4/5;
- Read v1 -> Task 3/4/5;
- Cursor Contract -> Task 2/4;
- Output Budgets -> Task 1/4/6;
- Stable Errors -> Task 4/5;
- Legacy/v1 and exact-inventory compatibility -> Task 4/5/6;
- Descriptions/annotations/security -> Task 5;
- deterministic tests/proof -> Task 0 through 6;
- docs/rollback/non-claims -> Task 7.

Expected: no uncovered requirement and no implementation beyond the approved exclusions.

- [ ] **Step 7: Handoff for one independent pre-PR authority review**

Return:

- branch and exact HEAD;
- baseline and commit list;
- full diff stat and task-owned paths;
- targeted RED failure and GREEN evidence;
- focused, compatibility, full pytest, Ruff, Pyright, build, and installed-proof results;
- exact ten-tool fixture identity;
- remaining non-claims and rollback;
- clean worktree status.

Do not run a duplicate full review in the execution window. The independent authority window owns
the single pre-PR review and returns findings for targeted repair.

### Task 8R: Close evaluation identity compatibility

The Task 8 compatibility suite reached the numeric evaluation integrity gate because this feature
adds application and SQLite source bytes covered by the existing whole-file E1-E3-E provenance
graph. Retrieval observations, results, metrics, thresholds, gates, diagnostics, selected
candidate/profile, status, and verdict did not change.

The compatibility closure reused the repository's supported atomic and recoverable identity
refresh procedure:

1. freeze the committed feature HEAD and generate fresh E1, refreshed-scope E2, E3-A, and E3-B
   observations in call-owned paths;
2. prove the checked-in failures are source, scope, or dependency identity drift only;
3. run `python -m mke.evaluation.artifact_refresh` for its five canonical E1-E3-B targets;
4. generate E3-C, E3-D, and E3-E identity candidates without a model or holdout re-observation;
5. overlay the complete proposed graph into a detached validation mirror and require exact
   candidate/mirror bytes, normalized semantic equality, and all seven canonical validators;
6. apply and commit exactly the validator-proven 21-path identity allowlist used by the existing
   compiled-export compatibility procedure.

Validation requires the complete artifact regression suite, all seven canonical validators,
Task 8 full tests, Ruff, Pyright, build, and the dual-version same-wheel installed proof. The
identity closure does not change a corpus, fixture, query, qrel, observation, result, metric,
threshold, gate, diagnostic, selected candidate/profile, status, verdict, or retrieval promotion.
It makes no model, quality, performance, production, deployment, or adoption claim.

### Task 8S: Close reviewed contract-boundary findings

The independent full-diff review identified bounded implementation gaps in SQLite page/range
reads, retrieval match-hint preservation, normalized excerpt offsets, exact CJK cap reporting,
blank-query validation, frozen release-error regression coverage, staged cursor validation, and
lock-bound dual-interpreter proof provisioning. Each repair begins with a targeted failing
regression and preserves the approved public schemas, ranking, active-Publication authority,
ten-tool inventory, immutable v0.1.4 fixture, and one-wheel offline proof boundary.

Completion requires bounded SQLite metadata preflight and range queries, FTS `LIMIT`/`OFFSET`
lookahead, retrieval-owned hints, exact normalized-to-original byte mapping, strategy-reported cap
state, zero-access malformed input rejection, authority-first authenticated continuation
validation, producer-derived frozen error checks, lock-derived install constraints, Python
3.12/3.13 cache prewarming, the complete Task 8 verification set, and supported identity closure
when source-bound artifact validators require it. These repairs do not change ranking, add a tool
or dependency, run a model, re-observe holdout data, alter an evaluation metric or verdict, or make
performance, deployment, production, or adoption claims.

## Final Acceptance

The implementation is READY for independent review only when:

1. both new tools exist and no third tool was added;
2. Search collection status and per-item excerpt completeness are independent and explicit;
3. exact active Evidence can be reconstructed without gaps and verified by SHA-256;
4. every continuation is owner-, authority-, strategy-, policy-, and contract-bound;
5. strict-v1 oversized Search/Ask fail with the typed frozen error shape;
6. existing Python, CLI, legacy/v1 MCP, Ask, Publication, Evidence, retrieval, and Export contracts
   pass unchanged;
7. immutable v0.1.4 eight-tool evidence remains untouched and current discovery validates exactly
   ten tools;
8. installed-wheel real-stdio proof passes on Python 3.12 and 3.13 from external cwd with no source
   import;
9. canonical response <=32 KiB and complete SDK result <96 KiB are measured;
10. full tests, Ruff, Pyright, build, documentation, and boundary scans pass;
11. the worktree is clean and all task-owned phases are committed;
12. no claim extends to exhaustive retrieval, semantic summarization, arbitrary-size Export,
    production deployment, performance, adoption, remote MCP, OCR, GraphRAG, or Agent
    orchestration.

At that point stop. Do not continue into segmentation comparison, corpus expansion, OCR, remote
services, additional tools, retrieval promotion, version bump, Release, or deployment.
