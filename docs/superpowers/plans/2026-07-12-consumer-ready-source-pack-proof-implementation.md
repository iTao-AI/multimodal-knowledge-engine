# Consumer-Ready Source-Pack Proof Implementation Plan

Status: implemented and verified at commit `44fa5b3571173b09400c76f3b326633c63d08f31`.

Final neutral detached-worktree gate: `UV_OFFLINE=1 uv run pytest -q` completed with
`1584 passed, 5 skipped, 5 warnings in 117.75s` and exit code `0`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Use `superpowers:test-driven-development` for every
> behavior change and `superpowers:verification-before-completion` before the final handoff.

**Goal:** Add one source-built, installed-wheel proof showing that a standalone external MCP SDK
consumer can ingest the frozen synthetic source pack, validate the strict v1 Evidence contract,
and map source-byte fingerprints to consumer-owned source keys on Python 3.12 and 3.13.

**Architecture:** Keep producer code and schemas unchanged. A standalone client owns strict
manifest/schema/payload validation and the real stdio MCP flow, while a separate controller builds
one wheel, exports core constraints from `uv.lock`, creates two fresh external environments, checks
installed identity, invokes the copied client with bounded subprocesses, and emits a redacted
aggregate report.

**Tech Stack:** Python 3.12/3.13, Python standard library, official MCP Python SDK, uv, pytest,
Ruff, Pyright, GitHub Actions.

## Global Constraints

- Planning base is `main@73d5f01885b60fbffeba8820e8f2f2151f8b9c39`; implementation starts
  from the reviewed planning commit that contains this plan and its approved design.
- The standalone client may import only the Python standard library, the official MCP SDK, and
  dependencies installed with that SDK. It must not import `mke`, `mke.*`, Pydantic, `sqlite3`,
  test helpers, or source-checkout code.
- The controller may read repository inputs only to build the wheel, export `uv.lock` constraints,
  and copy the explicit consumer assets plus the two frozen PDFs into external workspaces. It must
  never supply a repository path to the standalone client.
- Build exactly one current-source wheel. Run that same wheel in fresh Python 3.12 and 3.13
  environments; an unavailable interpreter fails explicitly and is never silently substituted.
- CI separates online cache provisioning from the proof. The provisioning step prepares the
  controller environment, build backend, and core locked dependencies for both explicit
  interpreter paths; the later controller invocation runs with `UV_OFFLINE=1` and must never
  enable network access or recover silently from a cache miss.
- Clear `PYTHONPATH`, `PYTHONHOME`, and `VIRTUAL_ENV` from every child environment. Every
  subprocess uses an argv sequence, `shell=False`, an explicit external `cwd`, a fixed timeout,
  hard-bounded controller stdout/stderr, and deterministic child termination. The MCP server
  stderr pipe is independently hard bounded.
- Reuse `tests/fixtures/local-knowledge-v1/operations-guide.pdf` and
  `tests/fixtures/local-knowledge-v1/incident-guide.pdf` without changing their bytes, existing
  manifest, README, or generator. The new manifest/schema fixtures are independently
  consumer-owned.
- Public output is closed. Success contains only approved aggregate fields; failure is exactly
  `{"status":"failed","code":"stable_machine_code"}`. Never render paths, opaque IDs,
  Evidence text or text hashes, filenames, commands, environment values, stderr, tracebacks, or
  exception details.
- This is a source-built proof for the current checkout. Documentation must not present it as a
  tagged `v0.1.1` Release capability or release gate.
- Stop immediately if implementation appears to require any change under `src/mke/**`, canonical
  MCP schemas, domain/application/SQLite/retrieval/Publication behavior, frozen PDF bytes,
  version/tag/Release/PyPI/deployment surfaces, evaluation artifacts or semantics, `CHANGELOG`, or
  release verification documentation. Report the required design change instead of expanding the
  PR.
- Do not modify corpus bytes, qrels, queries, observations, metrics, gates, candidates, profiles,
  or verdicts. If a validator reports source/scope/dependency identity drift, stop before writing
  any artifact and re-evaluate the identity closure.
- Do not push, create a PR, merge, tag, release, publish, or deploy during implementation unless a
  later explicit authorization changes that boundary.

## Exact File Map

### Create

- `scripts/consumer_source_pack_client.py`: copied standalone client; independent manifest,
  discovered-schema, payload, receipt, mapping, real stdio, deadline, and public-report logic.
- `scripts/consumer_source_pack_proof.py`: repository-side build/export/install/identity/external
  workspace controller and closed public entry point.
- `tests/fixtures/consumer-source-pack-v1/manifest.json`: strict consumer-owned source/query
  identity manifest with schema `mke.consumer_source_pack_manifest.v1`.
- `tests/fixtures/consumer-source-pack-v1/mcp-tool-schemas.json`: closed consumer-owned
  expectations for all five frozen legacy tools and three current strict v1 read tools.
- `tests/scripts/test_consumer_source_pack_client.py`: standalone parser, schema, payload, mapping,
  report, deadline, transport, termination, and static-independence tests.
- `tests/interfaces/test_consumer_source_pack_contract_fixture.py`: producer-side development
  regression proving current MCP discovery and current public safe causes structurally equal the
  consumer-owned expectation fixture.
- `tests/scripts/test_consumer_source_pack_proof.py`: controller command-plan, wheel reuse,
  constraints, interpreter, identity, bounds, redaction, cleanup, and real external proof tests.
- `tests/evaluation/test_consumer_source_pack_documentation.py`: dedicated documentation and
  forbidden-release-claim regression tests.
- `docs/how-to/run-consumer-source-pack-proof.md`: source-built command, isolation boundary,
  mapping, output contract, and explicit proves/does-not-prove sections.
- `.github/workflows/consumer-source-pack-proof.yml`: dedicated non-matrix workflow that obtains
  explicit 3.12/3.13 interpreter paths and passes both paths to one controller invocation.
- `docs/superpowers/reviews/2026-07-13-consumer-ready-source-pack-proof-task7-blocker-review.md`:
  public-neutral Task 7 identity-drift resolution and verification-boundary record.
- `docs/superpowers/reviews/2026-07-13-consumer-ready-source-pack-proof-implementation-review.md`:
  public-neutral implementation review resolution for client failure propagation, exact output
  ownership, and recursive source-root membership.

### Modify

- `README.md`: add one current-source proof sentence/link without changing release claims.
- `docs/README.md`: add one navigation link and one current-source positioning sentence.

### Read Only / Forbidden

- `src/mke/**` and all canonical MCP schema snapshots except the new consumer-owned fixture.
- `tests/fixtures/local-knowledge-v1/**`, especially both PDF bytes and its existing manifest.
- `.github/workflows/ci.yml`, because dense evaluation source identity declares its exact bytes;
  the dedicated consumer workflow must leave this file byte-identical to `HEAD`.
- `benchmarks/**`, retrieval/evaluation protocol locks, qrels, reports, and artifacts.
- `pyproject.toml`, `uv.lock`, `src/mke/__init__.py`, `CHANGELOG*`, tags, Release metadata,
  deployment files, and `docs/how-to/verify-release.md`.

---

### Task 1: Freeze the consumer-owned source-pack and schema expectations

**Files:**

- Create: `tests/fixtures/consumer-source-pack-v1/manifest.json`
- Create: `tests/fixtures/consumer-source-pack-v1/mcp-tool-schemas.json`
- Create: `tests/scripts/test_consumer_source_pack_client.py`
- Create: `scripts/consumer_source_pack_client.py`
- Read only: `tests/fixtures/local-knowledge-v1/operations-guide.pdf`
- Read only: `tests/fixtures/local-knowledge-v1/incident-guide.pdf`
- Read only: `tests/fixtures/mcp/legacy-tool-schemas.json`

**Interfaces:**

- Produces `ProofError(code: str)`, `SourceEntry`, `QueryExpectation`, and `SourcePack` frozen
  dataclasses in the standalone client.
- Produces `load_source_pack(manifest_path: Path) -> SourcePack` and
  `verify_source_files(pack: SourcePack, source_root: Path) -> dict[str, Path]`.
- Produces `load_schema_expectations(path: Path) -> dict[str, object]`.
- The manifest literal values are `mke.consumer_source_pack_manifest.v1`, pack ID
  `local-knowledge-v1`, source keys `operations_guide` / `incident_guide`, and the exact byte,
  SHA-256, query, and page-1 identities in the approved design.

- [x] **Step 1: Write RED fixture and parser tests**

Add tests that import the standalone script by file path and require:

```python
pack = client.load_source_pack(MANIFEST)
assert pack.schema_version == "mke.consumer_source_pack_manifest.v1"
assert pack.pack_id == "local-knowledge-v1"
assert {source.source_key for source in pack.sources} == {
    "operations_guide",
    "incident_guide",
}
assert client.verify_source_files(pack, LOCAL_FIXTURE_ROOT).keys() == {
    "operations_guide",
    "incident_guide",
}
```

Parameterize malformed copies to reject missing/extra fields, unknown schema versions, duplicate
source keys, duplicate filenames, bool byte counts, uppercase/malformed digests, absolute paths,
`..` traversal, non-normalized relative paths, duplicate query roles, invalid locator ranges, and
positive/unsupported query shape mismatches. Require `source_pack_manifest_invalid` for structure
failures and `source_pack_identity_mismatch` for membership, byte-count, or SHA-256 failures.

Run:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/scripts/test_consumer_source_pack_client.py -k 'manifest or source_files'
```

Expected: FAIL during collection because `scripts/consumer_source_pack_client.py` and the new
consumer fixtures do not exist.

- [x] **Step 2: Freeze the exact closed fixtures from current producer discovery**

Write `manifest.json` with required-fields-only objects. Each source includes `source_key`,
`relative_filename`, `media_type`, `bytes`, lowercase `sha256`, redistribution class
`repository_authored_synthetic`, and generator identity
`scripts/generate_local_knowledge_fixtures.py`. Each positive query records its role, literal query,
expected source key, locator kind `page`, and allowed range `[1, 1]`; the unsupported query records
no source or locator and requires active Search no-match plus Ask `insufficient_evidence`.

Write `mcp-tool-schemas.json` as a closed object with its own consumer expectation schema version,
the exact five legacy `inputSchema`/`outputSchema` objects from the frozen legacy fixture, the exact
discovered current input/output schemas for `list_libraries_v1`, `search_library_v1`, and
`ask_library_v1`, and consumer-owned `public_error_contract` metadata containing the literal
MachineToken pattern `^[a-z][a-z0-9_]{0,127}$`, literal impact `unchanged`, and the sorted exact safe
cause list including `operation failed; details were redacted`. Do not reference a producer fixture
path at runtime.

Use this development-time freeze procedure from the repository environment; it is not copied into
or invoked by the runtime consumer:

```bash
UV_OFFLINE=1 uv run python - <<'PY'
import asyncio
import json
import tempfile
from pathlib import Path

from mke.interfaces.mcp_contract import McpRuntimeConfig
from mke.interfaces.mcp_server import build_mcp_server
from mke.interfaces.public_errors import _ALLOWLISTED_CAUSES, _REDACTED_CAUSE
from mke.runtime import RuntimeConfig

async def discover(root: Path) -> dict[str, object]:
    server = build_mcp_server(
        McpRuntimeConfig(RuntimeConfig(root / "mke.sqlite"), root)
    )
    tools = await server.list_tools()
    names = {
        "list_libraries", "ingest_file", "get_run", "search_library", "ask_library",
        "list_libraries_v1", "search_library_v1", "ask_library_v1",
    }
    selected = {
        tool.name: {"inputSchema": tool.inputSchema, "outputSchema": tool.outputSchema}
        for tool in tools if tool.name in names
    }
    assert set(selected) == names
    return selected

with tempfile.TemporaryDirectory(prefix="mke-consumer-schema-freeze-") as directory:
    tools = asyncio.run(discover(Path(directory)))
payload = {
    "schema_version": "mke.consumer_mcp_tool_expectations.v1",
    "public_error_contract": {
        "machine_token_pattern": "^[a-z][a-z0-9_]{0,127}$",
        "active_publication_impact": "unchanged",
        "safe_causes": sorted({_REDACTED_CAUSE, *_ALLOWLISTED_CAUSES}),
    },
    "tools": dict(sorted(tools.items())),
}
Path("tests/fixtures/consumer-source-pack-v1/mcp-tool-schemas.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY
```

The implementation review must inspect the generated diff. Runtime code reads only the copied
consumer fixture and never imports these producer modules.

- [x] **Step 3: Implement the strict manifest preflight**

Use standard-library dataclasses, `json`, `hashlib`, and `pathlib`. Enforce exact key sets before
constructing typed values, reject `bool` where an integer is required, normalize with
`PurePosixPath`, and compare the manifest filename set exactly with the copied source-root file set.
The byte/hash loop must run before any `StdioServerParameters` is constructed.

- [x] **Step 4: Verify GREEN and freeze source bytes**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/scripts/test_consumer_source_pack_client.py -k 'manifest or source_files'
python - <<'PY'
from hashlib import sha256
from pathlib import Path
expected = {
    "operations-guide.pdf": (1000, "0ac3e96efc89ee91e48bb3efc8611de88b2698e5aa26c1f8e0e8f78ad2d60ddd"),
    "incident-guide.pdf": (990, "ed55cfbe9bdbf4404eb9ff55ab7e51fac14006ae0584a14d50704f68a02ff699"),
}
root = Path("tests/fixtures/local-knowledge-v1")
for name, identity in expected.items():
    data = (root / name).read_bytes()
    assert (len(data), sha256(data).hexdigest()) == identity
PY
git diff --check
```

Expected: focused tests pass and both committed PDFs retain their exact approved identities.

- [x] **Step 5: Commit the consumer fixtures and parser**

```bash
git add scripts/consumer_source_pack_client.py \
  tests/fixtures/consumer-source-pack-v1/manifest.json \
  tests/fixtures/consumer-source-pack-v1/mcp-tool-schemas.json \
  tests/scripts/test_consumer_source_pack_client.py
git commit -m "test(proof): freeze consumer source-pack contract"
```

### Task 2: Implement independent discovered-schema and payload validation

**Files:**

- Modify: `scripts/consumer_source_pack_client.py`
- Modify: `tests/scripts/test_consumer_source_pack_client.py`
- Create: `tests/interfaces/test_consumer_source_pack_contract_fixture.py`
- Read only: `tests/fixtures/consumer-source-pack-v1/mcp-tool-schemas.json`

**Interfaces:**

- Consumes `load_schema_expectations(path) -> dict[str, object]` from Task 1.
- Produces consumer-owned `DiscoveredTool(Protocol)` with read-only `name: str`,
  `inputSchema: Mapping[str, object]`, and `outputSchema: Mapping[str, object] | None` attributes,
  plus `normalize_discovered_tools(tools: Sequence[DiscoveredTool]) -> dict[str, object]`.
- Produces `validate_tool_schemas(tools: Sequence[DiscoveredTool],
  expected: Mapping[str, object]) -> None`; validation begins by normalizing Protocol values into
  plain closed mappings and performs no later attribute access.
- Produces `validate_list_response(payload: object) -> dict[str, object]`,
  `validate_search_response(payload: object) -> dict[str, object]`, and
  `validate_ask_response(payload: object) -> dict[str, object]`.
- Produces `evidence_projection(payload: Mapping[str, object]) -> tuple[object, ...]` for structural
  Search/Ask equality without importing producer models.

- [x] **Step 1: Write RED schema-discovery tests**

Use small fake tool objects and the committed expectation fixture. Require exact structural JSON
equality for all five legacy tools, presence of all three v1 tools, no duplicate/unknown required
tool substitution, top-level `ok` success/error discrimination, closed object shapes, literal
schema versions, and exact equality of the Search/Ask `mke.evidence_ref.v1` definitions. Type-check
fake tools against the consumer-owned Protocol and test normalization rejection for missing,
non-mapping, and duplicate attributes.

Add `tests/interfaces/test_consumer_source_pack_contract_fixture.py` as a producer-side regression:
it may import `build_mcp_server`, `McpRuntimeConfig`, `RuntimeConfig`, `_ALLOWLISTED_CAUSES`, and
`_REDACTED_CAUSE` to reproduce the Step 2 freeze payload, then require exact structural equality
with `mcp-tool-schemas.json`. This test protects development-time fixture freshness; the copied
standalone client remains producer-independent.

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/scripts/test_consumer_source_pack_client.py -k 'tool_schema or normalize_discovered' \
  tests/interfaces/test_consumer_source_pack_contract_fixture.py
```

Expected: FAIL because `validate_tool_schemas` is absent.

- [x] **Step 2: Write RED payload mutation tests**

Build valid local payload factories for list/search/ask and parameterize mutations covering every
required case: missing/extra fields; unknown schema versions; bool-as-int; malformed IDs and
fingerprints; zero/negative Publication revisions; invalid page and timestamp locators; impossible
state/count relationships; result count beyond the requested limit; mixed success/error fields;
`problem` / `next_step` values outside `^[a-z][a-z0-9_]{0,127}$`; impact other than literal
`unchanged`; `cause` values absent from the consumer-owned exact safe-cause list; Ask
status/evidence mismatch; and unequal Search/Ask Evidence projections. Include acceptance cases for
multiple valid machine tokens so the independent validator does not invent narrower problem or
next-step enums.

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/scripts/test_consumer_source_pack_client.py -k 'payload or projection'
```

Expected: FAIL because the three response validators and projection helper are absent.

- [x] **Step 3: Implement bounded standard-library validators**

Implement exact-key helpers and regexes for `src_`, `run_`, `pub_`, `ev_`, lowercase
`sha256:<64 hex>`, literal schema versions, and positive revisions. Validate `problem` and
`next_step` only with the consumer fixture's exact MachineToken regex, require
`active_publication_impact == "unchanged"`, and require `cause` membership in the fixture's exact
safe-cause set; do not define problem/next-step enums. Validate locator unions and nested
collections before indexing them and reject payloads above explicit item/text/depth bounds.
`validate_*_response` returns a shallow typed-as-mapping copy only after all cross-field invariants
pass; it never returns a producer DTO.

- [x] **Step 4: Verify GREEN, static independence, and commit**

```bash
UV_OFFLINE=1 uv run pytest -q tests/scripts/test_consumer_source_pack_client.py
UV_OFFLINE=1 uv run pytest -q tests/interfaces/test_consumer_source_pack_contract_fixture.py
UV_OFFLINE=1 uv run ruff check scripts/consumer_source_pack_client.py \
  tests/scripts/test_consumer_source_pack_client.py
UV_OFFLINE=1 uv run pyright scripts/consumer_source_pack_client.py \
  tests/scripts/test_consumer_source_pack_client.py
python - <<'PY'
import ast
from pathlib import Path
tree = ast.parse(Path("scripts/consumer_source_pack_client.py").read_text())
roots = {node.names[0].name.split(".")[0] for node in ast.walk(tree)
         if isinstance(node, ast.Import)}
roots |= {node.module.split(".")[0] for node in ast.walk(tree)
          if isinstance(node, ast.ImportFrom) and node.module}
assert "mke" not in roots and "pydantic" not in roots and "sqlite3" not in roots
PY
git diff --check
git add scripts/consumer_source_pack_client.py \
  tests/scripts/test_consumer_source_pack_client.py \
  tests/interfaces/test_consumer_source_pack_contract_fixture.py
git commit -m "feat(proof): validate consumer MCP contract independently"
```

Expected: tests, Ruff, Pyright, and the AST import audit pass.

### Task 3: Execute the real installed stdio success flow and portable mapping

**Files:**

- Modify: `scripts/consumer_source_pack_client.py`
- Modify: `tests/scripts/test_consumer_source_pack_client.py`

**Interfaces:**

- Produces frozen `ConsumerConfig(manifest: Path, schemas: Path, source_root: Path,
  mke_executable: Path, workspace: Path, child_environment: dict[str, str],
  startup_timeout_seconds: float, tool_timeout_seconds: float,
  max_server_stderr_bytes: int)`.
- Produces `build_receipt(evidence: Mapping[str, object], pack: SourcePack,
  query: QueryExpectation) -> dict[str, object]` with schema
  `mke.consumer_source_pack_receipt.v1` and literal `match_status="matched"`.
- Produces frozen `StoreResult` and `ConsumerResult` aggregates containing only counts, states,
  schema names, receipt projections, and booleans; no opaque ID, Evidence text, or path survives
  validation.
- Produces `async run_store_session(config: ConsumerConfig, database: Path) -> StoreResult` and
  `async run_consumer(config: ConsumerConfig) -> ConsumerResult`.
- Produces `BoundedStderrCapture(max_bytes: int)` as an async context manager exposing the pipe
  write end accepted by `stdio_client(errlog=...)`, an incrementally drained read end, and an
  overflow event that cancels the MCP context at the hard cap.
- Raw MCP stdout framing remains owned by the official MCP SDK and is not claimed to be hard-capped
  before SDK parsing. The independent validator bounds structured Search/Ask payloads after parsing.
- Produces `render_controller_result(result: ConsumerResult) -> str` and `main(argv) -> int`; this
  bounded redacted JSON is private controller input, while Task 4 owns the final public report.

- [x] **Step 1: Write RED mapping and receipt tests**

Require the only join to be
`evidence["content_fingerprint"] == "sha256:" + source.sha256`. Assert exact-one mapping,
query/source role agreement, page locator `[1, 1]`, receipt field closure, and absence of all
store-local IDs and Evidence text. Cover missing mapping, two source keys sharing a digest, and
locator contradiction with `manifest_mapping_missing`, `manifest_mapping_ambiguous`, and
`manifest_locator_mismatch`; no failure case may return a receipt.

- [x] **Step 2: Write RED async MCP flow tests**

Use an injected/fake session boundary to require this exact order per fresh store:

1. initialize with startup deadline;
2. list tools and validate all eight schemas;
3. `list_libraries_v1` -> strict `empty` with `0/0/0`;
4. ingest both relative filenames through legacy `ingest_file`;
5. inspect each returned Run through legacy `get_run` and require `published`, positive Evidence,
   contiguous event indices, ordered `run_created`, `run_started`, `candidate_validated`,
   `publication_activated`, and final `publication_activated`;
6. `list_libraries_v1` -> strict `active` with exact `2/2/2`;
7. issue each positive query separately to `search_library_v1` and `ask_library_v1`, validate both
   payloads, require exact shared Evidence projection, and build the expected receipt;
8. issue the unsupported query, require active Search with zero results and Ask
   `insufficient_evidence` with zero Evidence;
9. close the session and server.

Run the full sequence on a second fresh database and compare only
`(query_role, source_key, content_fingerprint, locator)` tuples across stores. Explicitly assert
that opaque IDs are not used as cross-store identity.

Add a live noisy-server test whose child continuously writes beyond the configured stderr cap and
remains alive. Require the pipe reader to observe the cap incrementally, close/cancel the MCP
context, terminate the child, verify the PID is gone, and return `command_output_exceeded` without
waiting for normal child exit. Add timeout/output race tests: the first observed terminal event
wins; output overflow wins when the cap event is recorded before the monotonic deadline, otherwise
the applicable startup/tool timeout code wins.

- [x] **Step 3: Implement the MCP SDK flow with independent deadlines**

Import `ClientSession`, `StdioServerParameters`, and `stdio_client` only from the official MCP SDK.
Set server argv to `mke --db <external-db> mcp --allowed-root <copied-source-root>`, external cwd,
and the already-cleared environment. Wrap server startup/initialize, discovery, and every tool call
in explicit monotonic deadlines. For server stderr, create an OS pipe, pass only its write end to
`stdio_client(errlog=...)`, and asynchronously drain the read end in fixed-size chunks while
tracking bytes. Once the configured cap is crossed, set the overflow event, close the read/write
ends, cancel/exit the MCP context, and verify the SDK-owned server child terminates before mapping
to `command_output_exceeded`. Do not use `TemporaryFile` or `SpooledTemporaryFile` as the bound.
Convert startup, tool, transport, and nonzero-exit conditions to their approved stable codes. Keep
server cleanup owned by the client MCP context and outer client-process/workspace cleanup owned by
the controller.

- [x] **Step 4: Implement the closed client-to-controller boundary**

The client subprocess success object contains only `status="passed"`, schema names, pack ID,
approved counts/states, receipt projections stripped to source key/fingerprint/locator/query role,
and consumer-verifiable booleans for strict schemas, projection equality, exact mapping, fresh-store
mapping, redaction, and server/store cleanup. The controller validates that exact closed shape and
uses it to form this final public object only after installed identity, external isolation, and
outer-workspace cleanup have passed:

```python
{
    "proof": "consumer_source_pack",
    "status": "passed",
    "manifest_schema": "mke.consumer_source_pack_manifest.v1",
    "evidence_schema": "mke.evidence_ref.v1",
    "pack_id": "local-knowledge-v1",
    "source_count": 2,
    "published_run_count": 2,
    "active_publication_count": 2,
    "active_evidence_count": 2,
    "observed_states": ["empty", "active"],
    "installed_identity": True,  # controller-owned
    "external_isolation": True,  # controller-owned
    "strict_schema_validation": True,
    "search_ask_projection_equal": True,
    "exact_manifest_mapping": True,
    "fresh_store_mapping": True,
    "redaction": True,
    "cleanup": True,  # controller-owned after every owning context exits
}
```

Both client and controller failure output is exactly the two-key closed object. The client never
accepts identity or cleanup attestations from argv; the controller derives those claims from its
own checks.

- [x] **Step 5: Verify focused GREEN and commit**

```bash
UV_OFFLINE=1 uv run pytest -q tests/scripts/test_consumer_source_pack_client.py
UV_OFFLINE=1 uv run ruff check scripts/consumer_source_pack_client.py \
  tests/scripts/test_consumer_source_pack_client.py
UV_OFFLINE=1 uv run pyright scripts/consumer_source_pack_client.py \
  tests/scripts/test_consumer_source_pack_client.py
git diff --check
git add scripts/consumer_source_pack_client.py \
  tests/scripts/test_consumer_source_pack_client.py
git commit -m "feat(proof): consume source pack through real stdio MCP"
```

Expected: all client unit/async tests pass with no repository or private value in rendered output.

### Task 4: Build once and orchestrate two isolated installed environments

**Files:**

- Create: `scripts/consumer_source_pack_proof.py`
- Create: `tests/scripts/test_consumer_source_pack_proof.py`
- Read only: `uv.lock`
- Read only: `scripts/release_consumer_smoke.py`

**Interfaces:**

- Produces `ControllerError(code: str)`, frozen `CommandResult(returncode: int, stdout: bytes,
  stderr: bytes)`, and frozen `ProofConfig(repository: Path,
  python_interpreters: tuple[Path, Path], command_timeout_seconds: float,
  max_stdout_bytes: int, max_stderr_bytes: int)`.
- Produces `isolated_environment(base: Mapping[str, str]) -> dict[str, str]`.
- Produces `run_bounded(command: Sequence[str], *, cwd: Path, env: Mapping[str, str],
  timeout_seconds: float, max_stdout_bytes: int, max_stderr_bytes: int) -> CommandResult`.
- Produces `run_proof(config: ProofConfig) -> dict[str, object]` and `main(argv) -> int`.

- [x] **Step 1: Write RED command-plan and same-wheel tests**

Mock `run_bounded` and temporary directories. Require this exact controller sequence:

```text
uv build --wheel --out-dir <external-build-dir> <repository>
uv export --project <repository> --locked --no-dev --no-emit-project --output-file <external-constraints>
for explicit interpreter in (python_3_12, python_3_13):
  uv venv <fresh-env> --python <explicit-path> --no-python-downloads
  uv pip install --python <fresh-python> --constraint <same-constraints> <same-wheel>
  <fresh-python> -c <identity probe>
  <fresh-python> <copied-client> <copied manifest/schema/source-root> <installed-mke>
```

Run both repository-input commands with an external controller cwd. Assert `uv build` and
`uv export` each occur once, both installs receive the byte-identical same
wheel path, each interpreter path is the explicit caller value, both environment/workspace paths
are distinct and outside the repository, and no client argv/env value contains the repository.

- [x] **Step 2: Write RED environment, identity, bound, and termination tests**

Cover hostile environment removal; module/distribution/Python/`mke` executable inside the matching
fresh environment and outside the repository; consumer file and cwd inside the external workspace;
timeout; stdout/stderr overflow; nonzero child; process-group termination; partial environment
creation; install failure; invalid/multiple wheel outputs; and cleanup failure after an otherwise
successful flow. Require the approved codes `wheel_build_failed`, `environment_create_failed`,
`install_failed`, `installed_identity_failed`, `external_isolation_failed`,
`command_output_exceeded`, `server_exit_nonzero`, `cleanup_failed`, or `proof_failed` as applicable.

Use live children for the hard-bound cases: one continuously writes stdout and sleeps, one
continuously writes stderr and sleeps, and neither exits voluntarily. Assert termination happens
when the configured stream counter crosses its cap, the child PID/process group is gone, captured
bytes never grow without bound, and the test does not wait for the child's natural lifetime. Add a
race test that records monotonic event order and requires overflow when its cap event is first, or
timeout when the deadline event is first.

- [x] **Step 3: Implement bounded subprocess ownership**

Use `subprocess.Popen` with `shell=False`, `start_new_session=True` on POSIX, and byte pipes. Drain
stdout and stderr concurrently in fixed-size chunks with one reader thread per stream (or one
selector loop where supported), increment per-stream byte counters under synchronized state, and
record the first terminal event against `time.monotonic()`. An overflow reader signals the owner
immediately; the owner terminates the process group, waits for a fixed grace interval, kills if
still alive, joins readers, closes pipes, calls `wait()`, and verifies the PID/process group is
gone. A deadline follows the same terminate-to-kill sequence. Output overflow maps to
`command_output_exceeded` only when its cap event was observed first; otherwise timeout maps to the
calling step's stable timeout/failure code. Never call `communicate()` for bounded commands. Keep at
most the configured bytes from either stream for private diagnosis and never include command or
exception text in the public error object.

- [x] **Step 4: Implement build/export/copy/install/identity orchestration**

Resolve the repository only in the controller. From an external controller cwd, pass the repository
as the explicit `uv build` source, build into an external temporary directory, and require exactly
one wheel. Export core constraints with
`uv export --project <repository> --locked --no-dev --no-emit-project`. Copy only the standalone client, the two new
consumer fixtures, and the two approved PDFs to each external workspace. The identity probe may
import top-level `mke` only to return module file, distribution metadata location/version,
`sys.executable`, and installed `mke` executable; validate every path against the fresh environment
and repository before launching the client.

- [x] **Step 5: Aggregate two interpreter results and verify cleanup**

Require both closed client results to contain the same approved counts/states/schema names and both
to use the same manifest/fingerprint mapping. Exit the owning temporary-directory contexts, then
verify each workspace/environment/store path no longer exists before building the final public
success object and setting `installed_identity`, `external_isolation`, and `cleanup` true. A cleanup
failure overrides functional success with `cleanup_failed`.

- [x] **Step 6: Verify GREEN and commit**

```bash
UV_OFFLINE=1 uv run pytest -q tests/scripts/test_consumer_source_pack_proof.py
UV_OFFLINE=1 uv run ruff check scripts/consumer_source_pack_proof.py \
  tests/scripts/test_consumer_source_pack_proof.py
UV_OFFLINE=1 uv run pyright scripts/consumer_source_pack_proof.py \
  tests/scripts/test_consumer_source_pack_proof.py
git diff --check
git add scripts/consumer_source_pack_proof.py \
  tests/scripts/test_consumer_source_pack_proof.py
git commit -m "feat(proof): orchestrate isolated source-built consumers"
```

Expected: controller unit tests pass and public failures contain only `status` and stable `code`.

### Task 5: Close the failure matrix and run the real external proof

**Files:**

- Modify: `tests/scripts/test_consumer_source_pack_client.py`
- Modify: `tests/scripts/test_consumer_source_pack_proof.py`
- Modify only if a focused defect is exposed: `scripts/consumer_source_pack_client.py`
- Modify only if a focused defect is exposed: `scripts/consumer_source_pack_proof.py`

**Interfaces:**

- Consumes the client/controller public and helper interfaces from Tasks 1-4.
- Produces one parametrized failure-code matrix and one real two-interpreter external integration
  test/command with a single aggregate success JSON object.

- [x] **Step 1: Add the complete stable-code matrix**

Create one table-driven test that triggers every closed allowlist code:

```text
source_pack_manifest_invalid, source_pack_identity_mismatch, wheel_build_failed,
environment_create_failed, install_failed, installed_identity_failed,
external_isolation_failed, consumer_schema_invalid, consumer_payload_invalid,
manifest_mapping_missing, manifest_mapping_ambiguous, manifest_locator_mismatch,
observation_state_mismatch, mcp_startup_timeout, mcp_tool_timeout,
mcp_transport_failed, server_exit_nonzero, command_output_exceeded, cleanup_failed,
proof_failed
```

For each case assert exact two-key JSON, exit code `1`, no traceback, and no injected secret, path,
opaque ID, filename, command, environment value, stderr, Evidence text, or exception detail.

- [x] **Step 2: Add static and behavioral independence assertions**

AST-audit the standalone client imports and calls. Reject `mke`, `pydantic`, `sqlite3`, repository
fixture/model imports, database reads, and absolute repository literals. Instrument the success
path to prove the client opens only its own copied manifest, schema fixture, and source bytes and
obtains all MKE observations through official MCP SDK discovery/calls. Phrase the assertion as a
shared-principal dependency/behavior check, not an OS filesystem sandbox claim.

- [x] **Step 3: Run focused tests and a real local two-interpreter proof**

Resolve exact local interpreters without fallback:

```bash
python312=$(command -v python3.12)
python313=$(command -v python3.13)
test -n "$python312" && test -n "$python313"
UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py \
  --python "$python312" \
  --python "$python313" \
  --json
```

Expected: one success JSON object with `proof="consumer_source_pack"`, `status="passed"`, exact
`2/2/2` aggregate counts, states `empty` and `active`, and all approved booleans true. If either
interpreter or a locked cached dependency is unavailable, report the exact environmental blocker;
do not substitute an interpreter or use the network.

- [x] **Step 4: Verify the complete focused suite and commit**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/scripts/test_consumer_source_pack_client.py \
  tests/scripts/test_consumer_source_pack_proof.py \
  tests/scripts/test_local_knowledge_fixtures.py \
  tests/interfaces/test_consumer_source_pack_contract_fixture.py \
  tests/interfaces/test_mcp_legacy_schema_snapshot.py \
  tests/interfaces/test_mcp_v1_schemas.py
UV_OFFLINE=1 uv run ruff check scripts/consumer_source_pack_client.py \
  scripts/consumer_source_pack_proof.py tests/scripts/test_consumer_source_pack_client.py \
  tests/scripts/test_consumer_source_pack_proof.py
UV_OFFLINE=1 uv run pyright scripts/consumer_source_pack_client.py \
  scripts/consumer_source_pack_proof.py tests/scripts/test_consumer_source_pack_client.py \
  tests/scripts/test_consumer_source_pack_proof.py
git diff --check
git add scripts/consumer_source_pack_client.py scripts/consumer_source_pack_proof.py \
  tests/scripts/test_consumer_source_pack_client.py \
  tests/scripts/test_consumer_source_pack_proof.py
git commit -m "test(proof): close consumer source-pack failure matrix"
```

Expected: all focused contract, failure, independence, and external-flow tests pass.

### Task 6: Document the source-built proof without changing release claims

**Files:**

- Create: `docs/how-to/run-consumer-source-pack-proof.md`
- Create: `tests/evaluation/test_consumer_source_pack_documentation.py`
- Modify: `README.md`
- Modify: `docs/README.md`
- Read only: `docs/how-to/verify-release.md`
- Read only: `docs/releases/v0.1.1.md`
- Read only: `README_CN.md`

**Interfaces:**

- Consumes the exact controller command and closed output contract from Tasks 4-5.
- Produces one discoverable public-neutral how-to that labels the proof current-source/source-built,
  explains offline/external boundaries and fingerprint mapping, and separates “proves” from “does
  not prove”.

- [x] **Step 1: Write RED documentation assertions**

Require the how-to and minimal navigation surfaces to contain:

```text
scripts/consumer_source_pack_proof.py
mke.consumer_source_pack_manifest.v1
mke.evidence_ref.v1
content_fingerprint
Python 3.12
Python 3.13
source-built
current source checkout
What This Proves
What This Does Not Prove
```

Require the dedicated how-to to state that the proof uses the official MCP SDK, the same wheel in
two fresh environments, lock-derived offline-capable constraints, external cwd/consumer assets,
stable redacted failures, exact source fingerprint mapping, and no OS-sandbox claim. Require a
prerequisite section explaining that dependencies and build tooling must already be available in
the uv cache; CI performs a distinct online provisioning/prewarm step before the offline proof.
Explicitly reject any claim that an empty machine can install air-gapped without a prepared cache.
Assert that
the new text does not call this a `v0.1.1` capability, Release artifact, release gate, PyPI proof,
deployment, production-readiness proof, or release verification step.

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/evaluation/test_consumer_source_pack_documentation.py
```

Expected: FAIL because the how-to and links do not exist.

- [x] **Step 2: Write the dedicated how-to and minimal links**

Document this command shape with explicit interpreter paths:

```bash
UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py \
  --python "$(command -v python3.12)" \
  --python "$(command -v python3.13)" \
  --json
```

Explain that the controller builds the current checkout once; the result is not the tagged
`v0.1.1` Release wheel. Describe only the approved success/failure output fields. In README and
`docs/README.md`, add one sentence and one link; do not revise the “Verified in v0.1.1” table or
release verification surfaces. State that `UV_OFFLINE=1` proves reuse of provisioned locked cache
content, not installation from an empty or never-provisioned machine.

- [x] **Step 3: Verify docs GREEN and commit**

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/evaluation/test_consumer_source_pack_documentation.py \
  tests/evaluation/test_evidence_provenance_documentation.py
uv run python scripts/release_presentation_audit.py --root .
git diff --check
git add docs/how-to/run-consumer-source-pack-proof.md docs/README.md README.md \
  tests/evaluation/test_consumer_source_pack_documentation.py
git commit -m "docs(proof): explain source-built consumer verification"
```

Expected: documentation tests and release presentation audit pass with release claims unchanged.

### Task 7: Add one dedicated same-wheel workflow and run final verification

**Files:**

- Create: `.github/workflows/consumer-source-pack-proof.yml`
- Create: `docs/superpowers/reviews/2026-07-13-consumer-ready-source-pack-proof-task7-blocker-review.md`
- Create: `docs/superpowers/reviews/2026-07-13-consumer-ready-source-pack-proof-implementation-review.md`
- Modify: `scripts/consumer_source_pack_client.py`
- Modify: `scripts/consumer_source_pack_proof.py`
- Modify: `tests/scripts/test_consumer_source_pack_client.py`
- Modify: `tests/scripts/test_consumer_source_pack_proof.py`
- Modify: `tests/evaluation/test_consumer_source_pack_documentation.py`
- Modify: `docs/how-to/run-consumer-source-pack-proof.md`
- Modify: `docs/superpowers/specs/2026-07-12-consumer-ready-source-pack-proof-design.md`
- Modify: `docs/superpowers/plans/2026-07-12-consumer-ready-source-pack-proof-implementation.md`
- Modify: `docs/superpowers/reviews/2026-07-12-consumer-ready-source-pack-proof-plan-review.md`
- Read only: `.github/workflows/ci.yml`
- Read only: every forbidden path in the Exact File Map

**Interfaces:**

- Consumes `scripts/consumer_source_pack_proof.py --python PATH --python PATH --json`.
- Produces one `consumer-source-pack-proof` job, not a Python matrix, so both interpreters consume
  one wheel built by one controller invocation.

- [x] **Step 1: Write RED workflow-shape assertions**

Parse `.github/workflows/consumer-source-pack-proof.yml` as text and require exactly one job with:

- `runs-on: ubuntu-latest` and a bounded job timeout;
- checkout and `astral-sh/setup-uv` at the repository's existing pinned action SHAs;
- two separately identified pinned `actions/setup-python` steps for literal `3.12` and `3.13`;
- controller arguments `${{ steps.python312.outputs.python-path }}` and
  `${{ steps.python313.outputs.python-path }}`;
- one controller invocation and no matrix for this job;
- a named online provisioning step that runs `uv sync --locked`, exports core locked requirements,
  creates separate 3.12 and 3.13 prewarm environments from the two setup-python outputs, and
  installs the exported requirements into both;
- a later, separately named proof step with `UV_OFFLINE: "1"` and no network-enabling flags;
- workflow-shape assertions that the provisioning step precedes the proof, both explicit
  interpreter caches are populated, and `UV_OFFLINE` is scoped only to the proof step; and
- no duplicate `uv build` or per-interpreter wheel build command in YAML; and
- a regression assertion that `.github/workflows/ci.yml` remains byte-identical to `HEAD` so the
  declared dense evaluation source identity cannot drift as a side effect of this proof.

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/scripts/test_consumer_source_pack_proof.py -k workflow
```

Expected: FAIL because the dedicated job is absent.

- [x] **Step 2: Add the dedicated single-job CI proof**

Create the dedicated workflow with `pull_request` and `push` to `main` triggers, `contents: read`,
bounded concurrency, and this single-job shape, retaining the exact action SHAs already present in
the primary CI workflow:

```yaml
consumer-source-pack-proof:
  name: consumer source-pack proof (3.12 + 3.13, same wheel)
  runs-on: ubuntu-latest
  timeout-minutes: 15
  steps:
    - uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0
    - uses: astral-sh/setup-uv@11f9893b081a58869d3b5fccaea48c9e9e46f990
    - id: python312
      uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1
      with:
        python-version: "3.12"
    - id: python313
      uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1
      with:
        python-version: "3.13"
    - name: Provision locked cache for controller and both interpreters
      run: |
        uv sync --locked
        uv export --locked --no-dev --no-emit-project \
          --output-file "$RUNNER_TEMP/mke-core-requirements.txt"
        uv venv "$RUNNER_TEMP/mke-prewarm-312" \
          --python "${{ steps.python312.outputs.python-path }}" \
          --no-python-downloads
        uv pip install \
          --python "$RUNNER_TEMP/mke-prewarm-312/bin/python" \
          --requirement "$RUNNER_TEMP/mke-core-requirements.txt"
        uv venv "$RUNNER_TEMP/mke-prewarm-313" \
          --python "${{ steps.python313.outputs.python-path }}" \
          --no-python-downloads
        uv pip install \
          --python "$RUNNER_TEMP/mke-prewarm-313/bin/python" \
          --requirement "$RUNNER_TEMP/mke-core-requirements.txt"
    - name: Run offline same-wheel consumer proof
      env:
        UV_OFFLINE: "1"
      run: |
        uv run python scripts/consumer_source_pack_proof.py \
          --python "${{ steps.python312.outputs.python-path }}" \
          --python "${{ steps.python313.outputs.python-path }}" \
          --json
```

The online step provisions caches only; it does not run the proof or build the proof wheel. The
controller, not YAML, owns the single wheel build and same-wheel assertion. Once invoked under
`UV_OFFLINE=1`, the controller must propagate offline mode and fail on any cache miss without
retrying online. Keeping this job in a dedicated workflow is required because the dense evaluation
artifact declares `.github/workflows/ci.yml` as source identity; modifying that primary workflow
would invalidate the committed artifact even though evaluation behavior did not change.

- [x] **Step 3: Run focused and full repository gates**

Run focused gates first:

```bash
UV_OFFLINE=1 uv run pytest -q \
  tests/scripts/test_consumer_source_pack_client.py \
  tests/scripts/test_consumer_source_pack_proof.py \
  tests/evaluation/test_consumer_source_pack_documentation.py \
  tests/scripts/test_local_knowledge_fixtures.py \
  tests/interfaces/test_consumer_source_pack_contract_fixture.py \
  tests/interfaces/test_mcp_legacy_schema_snapshot.py \
  tests/interfaces/test_mcp_v1_schemas.py
```

Then run every approved repository gate exactly:

```bash
UV_OFFLINE=1 uv run pytest -q
UV_OFFLINE=1 uv run ruff check .
UV_OFFLINE=1 uv run pyright
UV_OFFLINE=1 uv build
UV_OFFLINE=1 uv run mke proof run
UV_OFFLINE=1 uv run mke demo --verify
UV_OFFLINE=1 uv run python scripts/local_knowledge_proof.py
UV_OFFLINE=1 uv run python scripts/evidence_provenance_proof.py
uv run python scripts/release_presentation_audit.py --root .
git diff --check
```

Expected: focused gates and every non-pytest repository command exit `0`; the representative
dense/hybrid tests that previously reported source-identity drift pass after the primary CI file is
restored. In the named feature worktree, the only acceptable full-pytest residual is the unchanged,
path-sensitive release consumer-smoke `proof-proof_failed` case. Record it without marking the full
pytest gate complete. Final completion requires the configured authority to run the bare full suite
from a neutral-named detached temporary worktree at the committed Task 7 `HEAD`. The
dual-interpreter consumer claim is gated separately by Step 4 and must not be inferred from these
commands.

- [x] **Step 4: Re-run the final real dual-interpreter proof and assert exact JSON**

Run this only after every code, documentation, and CI edit is complete:

```bash
python312=$(command -v python3.12)
python313=$(command -v python3.13)
test -n "$python312" && test -n "$python313"
UV_OFFLINE=1 uv run python scripts/consumer_source_pack_proof.py \
  --python "$python312" \
  --python "$python313" \
  --json > /tmp/mke-consumer-source-pack-final.json
python - <<'PY'
import json
from pathlib import Path

observed = json.loads(
    Path("/tmp/mke-consumer-source-pack-final.json").read_text(encoding="utf-8")
)
expected = {
    "proof": "consumer_source_pack",
    "status": "passed",
    "manifest_schema": "mke.consumer_source_pack_manifest.v1",
    "evidence_schema": "mke.evidence_ref.v1",
    "pack_id": "local-knowledge-v1",
    "source_count": 2,
    "published_run_count": 2,
    "active_publication_count": 2,
    "active_evidence_count": 2,
    "observed_states": ["empty", "active"],
    "installed_identity": True,
    "external_isolation": True,
    "strict_schema_validation": True,
    "search_ask_projection_equal": True,
    "exact_manifest_mapping": True,
    "fresh_store_mapping": True,
    "redaction": True,
    "cleanup": True,
}
assert observed == expected, observed
PY
```

Expected: both explicit interpreters run the same controller-built wheel offline and the aggregate
JSON is structurally equal to the approved public report.

- [x] **Step 5: Audit immutable and forbidden surfaces**

```bash
git diff --exit-code 73d5f01885b60fbffeba8820e8f2f2151f8b9c39 -- \
  src/mke tests/fixtures/local-knowledge-v1 benchmarks pyproject.toml uv.lock \
  CHANGELOG.md docs/how-to/verify-release.md docs/releases
git diff --name-only 73d5f01885b60fbffeba8820e8f2f2151f8b9c39...HEAD
```

Expected: the first command has no output; the second lists only the focused client/controller,
consumer fixtures/tests, CI, how-to, README, docs index, approved spec/plan/review history, and no
forbidden surface.

- [x] **Step 6: Perform the required plan/spec self-review against the final diff**

Check every approved design section and acceptance criterion against a concrete test or command in
Tasks 1-7. Scan every changed text file, including JSON fixtures, CI, README/docs index, approved
spec/plan/review history, scripts, and tests, for incomplete-marker language and
workflow-specific/private terms.
Verify that every signature, dataclass field, stable code, report field, schema literal, fixture
identity, and interpreter argument is consistent across client, controller, tests, docs, and CI.
Confirm the diff forms one independently reviewable proof/docs/tests PR and contains no release,
runtime, evaluation-semantic, or unrelated change.

```bash
python - <<'PY'
import subprocess
from pathlib import Path

markers = (
    "T" + "BD",
    "T" + "ODO",
    "place" + "holder",
    "similar " + "to above",
    "Car" + "eer",
    "Night " + "Voyager",
    "job" + "-search",
    "/Us" + "ers/",
)
allowed_lines = {
    (
        Path("scripts/consumer_source_pack_client.py"),
        "place" + "holder",
    ): {'"argv must contain exactly one {input} place' + 'holder",'},
    (
        Path("tests/fixtures/consumer-source-pack-v1/mcp-tool-schemas.json"),
        "place" + "holder",
    ): {'"argv must contain exactly one {input} place' + 'holder",'},
    (
        Path("tests/scripts/test_consumer_source_pack_client.py"),
        "/Us" + "ers/",
    ): {'assert "/Us' + 'ers/" not in CLIENT_PATH.read_text(encoding="utf-8")'},
}
commands = (
    [
        "git", "diff", "--name-only", "--diff-filter=ACMR",
        "73d5f01885b60fbffeba8820e8f2f2151f8b9c39...HEAD",
    ],
    ["git", "diff", "--name-only", "--diff-filter=ACMR"],
    ["git", "ls-files", "--others", "--exclude-standard"],
)
changed = sorted(
    {
        name
        for command in commands
        for name in subprocess.run(
            command, check=True, capture_output=True, text=True
        ).stdout.splitlines()
    }
)
hits: list[tuple[Path, int, str]] = []
for name in changed:
    path = Path(name)
    data = path.read_bytes()
    if b"\0" in data:
        continue
    text = data.decode("utf-8")
    for line_number, line in enumerate(text.splitlines(), start=1):
        for marker in markers:
            if marker not in line:
                continue
            if line.strip() in allowed_lines.get((path, marker), set()):
                continue
            hits.append((path, line_number, marker))
assert not hits, hits
PY
git diff --exit-code HEAD -- .github/workflows/ci.yml
git diff --check
git status --short
```

Expected: the scan permits only the exact public safe-cause line in the standalone client and its
consumer schema fixture plus the exact negative local-path assertion in its test. Any other
incomplete marker, actual private absolute path, or workflow-specific/private term fails. The
primary CI file is byte-identical to `HEAD`, `git diff --check` passes, and status contains only the
intended Task 7 changes before commit.

- [x] **Step 7: Hand off the uncommitted Task 7 closure for authoritative commit and detached verification**

This execution window leaves the following expanded Task 7 and implementation-review fix set
uncommitted and reports the complete verification evidence:

```bash
git status --short
git diff --check
git diff -- scripts/consumer_source_pack_client.py \
  scripts/consumer_source_pack_proof.py \
  tests/scripts/test_consumer_source_pack_client.py \
  tests/scripts/test_consumer_source_pack_proof.py \
  tests/evaluation/test_consumer_source_pack_documentation.py \
  docs/how-to/run-consumer-source-pack-proof.md \
  docs/superpowers/specs/2026-07-12-consumer-ready-source-pack-proof-design.md \
  docs/superpowers/plans/2026-07-12-consumer-ready-source-pack-proof-implementation.md \
  docs/superpowers/reviews/2026-07-12-consumer-ready-source-pack-proof-plan-review.md
git diff --no-index /dev/null .github/workflows/consumer-source-pack-proof.yml || test $? -eq 1
git diff --no-index /dev/null \
  docs/superpowers/reviews/2026-07-13-consumer-ready-source-pack-proof-task7-blocker-review.md \
  || test $? -eq 1
git diff --no-index /dev/null \
  docs/superpowers/reviews/2026-07-13-consumer-ready-source-pack-proof-implementation-review.md \
  || test $? -eq 1
```

After reviewing that handoff, the configured authority, not this execution window, stages and
commits only the expanded reviewed set:

```bash
git add .github/workflows/consumer-source-pack-proof.yml \
  scripts/consumer_source_pack_client.py \
  scripts/consumer_source_pack_proof.py \
  tests/scripts/test_consumer_source_pack_client.py \
  tests/scripts/test_consumer_source_pack_proof.py \
  tests/evaluation/test_consumer_source_pack_documentation.py \
  docs/how-to/run-consumer-source-pack-proof.md \
  docs/superpowers/specs/2026-07-12-consumer-ready-source-pack-proof-design.md \
  docs/superpowers/plans/2026-07-12-consumer-ready-source-pack-proof-implementation.md \
  docs/superpowers/reviews/2026-07-12-consumer-ready-source-pack-proof-plan-review.md \
  docs/superpowers/reviews/2026-07-13-consumer-ready-source-pack-proof-task7-blocker-review.md \
  docs/superpowers/reviews/2026-07-13-consumer-ready-source-pack-proof-implementation-review.md
git commit -m "ci(proof): verify same wheel on supported Python minors"
git status --short --branch
```

The configured authority then creates a neutral-named detached temporary worktree at the committed
Task 7 `HEAD` and runs the exact bare gate:

```bash
UV_OFFLINE=1 uv run pytest -q
```

Expected: this execution window stops with the named expanded set uncommitted and a complete
handoff report. The configured authority reviews and commits that exact set, then the detached
worktree full suite exits `0` before Task 7 or the implementation plan may be marked complete. Push,
PR, merge, release, publication, and deployment remain unauthorized.

## Spec Coverage Self-Review

- Success flow: Tasks 3 and 5 cover installed identity, fresh `empty`, two published Runs, exact
  active `2/2/2`, separate positive Search/Ask calls, exact projection/mapping, active business
  no-match, second fresh store, and cleanup.
- Failure matrix: Tasks 1-5 cover strict manifest/schema/payload rejection, missing/ambiguous
  mapping, locator/state mismatch, startup/tool timeout, transport/nonzero exit, identity
  contamination, controller subprocess stdout/stderr and MCP server stderr bounds, termination,
  cleanup, and the complete stable-code allowlist. Raw MCP stdout framing is SDK-owned; structured
  Search/Ask payloads are bounded after parsing.
- Independent contract: Tasks 1-2 freeze all eight discovered schemas plus the exact MachineToken,
  literal impact, and safe-cause contract; a producer-side structural regression protects fixture
  freshness while the copied client remains independent.
- Isolation/build: Task 4 builds one wheel, exports core `uv.lock` constraints, clears hostile
  variables, uses external workspaces/venvs and incrementally bounded `shell=False` subprocesses,
  and verifies module/distribution/Python/CLI/client/cwd identities. Tasks 3-4 use live noisy-child
  tests to prove output-cap termination and deterministic timeout/overflow precedence.
- Supported minors: Tasks 4, 5, and 7 require explicit Python 3.12/3.13 paths and the same wheel;
  the dedicated CI workflow is intentionally non-matrix, provisions both locked interpreter caches
  online, then runs the distinct proof step offline.
- Frozen inputs and compatibility: Tasks 1, 5, and 7 reuse but never modify the two PDFs, own
  independent manifest/schema fixtures, and re-run legacy/v1 schema regressions.
- Documentation: Task 6 labels the proof source-built/current-checkout, explains exact boundaries,
  requires prior cache provisioning, rejects empty-machine air-gap claims, and prevents any
  `v0.1.1` Release or release-gate claim.
- Forbidden surfaces and verification: Global Constraints and Task 7 turn every prohibited area
  into an explicit stop condition, run every approved focused/full gate, re-run the final real
  dual-interpreter proof, and compare its complete aggregate JSON exactly.
- Completeness/type/coherence review: Task 7 requires incomplete-marker scan, cross-file signature/type
  consistency, public-neutral scan, and one-PR diff audit before completion.

Implementation and verification complete. The reviewed implementation was committed as
`44fa5b3571173b09400c76f3b326633c63d08f31`; the final neutral detached-worktree gate ran
`UV_OFFLINE=1 uv run pytest -q` with `1584 passed, 5 skipped, 5 warnings in 117.75s` and exit code
`0`. This plan is retained as completed implementation history and must not be treated as active
work.
