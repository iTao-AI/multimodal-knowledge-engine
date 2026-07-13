# Consumer-Ready Source-Pack Proof Design

Status: implemented and verified at commit `44fa5b3571173b09400c76f3b326633c63d08f31`.

Planning base: `main@73d5f01885b60fbffeba8820e8f2f2151f8b9c39`.

Repository verification: the final neutral detached-worktree command
`UV_OFFLINE=1 uv run pytest -q` completed with
`1584 passed, 5 skipped, 5 warnings in 117.75s` and exit code `0`.

## Goal

Prove that a generic external Agent consumer can use an installed wheel built from the current
source checkout, outside the source tree and after hostile Python environment variables are
cleared, to consume MKE through the official MCP SDK and the real stdio MCP server.

The proof covers one public-safe synthetic source pack through this complete flow:

```text
consumer-owned source-pack manifest
  -> installed-wheel legacy ingest_file
  -> observable published Run through get_run
  -> active Publication observation
  -> strict v1 Search and Ask
  -> mke.evidence_ref.v1
  -> exact source-byte fingerprint mapping back to the source pack
  -> public-safe aggregate report
```

This is a provider-readiness and product-consumption proof. It does not add a runtime capability,
change an MKE contract, or claim that the source-built wheel is a published Release artifact. The
Evidence provenance contract was merged after the `v0.1.1` tag, so this proof must not describe the
contract as a capability of the tagged `v0.1.1` Release even if the package metadata in the current
checkout has not changed.

## Current Evidence And Exact Gap

The repository already has three strong but deliberately separate proof surfaces:

- `local_knowledge` uses a source-pack-like manifest and the real stdio MCP transport, but it runs
  from the source environment and consumes the five legacy tools.
- `evidence_provenance` proves the three strict v1 read tools, real stdio transport, active-state
  distinctions, Search/Ask projection equality, cross-store fingerprint identity, malformed
  payload rejection, bounded failure, redaction, and cleanup. Its harness lives inside the MKE
  package/source tree and validates payloads with MKE-owned schema types.
- `release_consumer_smoke` proves installed-wheel identity, an external working directory, hostile
  environment clearing, and isolated CLI/MCP execution. Its MCP flow imports and calls the legacy
  `mcp_contract` directly instead of behaving as an independent stdio v1 consumer.

No current proof combines all of the following in one bounded, reproducible flow:

1. a versioned source pack with repository-owned synthetic source bytes;
2. a wheel built from the exact current source checkout;
3. a fresh environment and working directory outside the repository;
4. a standalone consumer that does not import MKE implementation or schema modules;
5. the official MCP SDK and real stdio MCP server;
6. strict `mke.evidence_ref.v1` Search/Ask consumption; and
7. a portable, exact mapping from source-byte fingerprint to a consumer-owned source key.

The approved work closes only this composition gap. It must reuse, not reimplement, the merged
Evidence provenance contract.

## Approaches Considered

### A. Dedicated standalone installed-consumer source-pack proof

Build a wheel from the current checkout, create a fresh external environment, copy a standalone
consumer and a versioned synthetic source pack into that environment, then use the official MCP SDK
against the installed `mke` stdio executable. The consumer validates strict schemas and payloads
independently, maps content fingerprints to its own manifest, and emits only an aggregate report.

This is the selected approach. It keeps product-consumer readiness separate from contract
integrity and release verification while exercising their real boundaries together.

### B. Extend `release_consumer_smoke`

Rejected. That script is a release identity and version gate with existing proof/demo/CLI/legacy
MCP responsibilities. Adding source-pack semantics and strict external v1 validation would mix a
current-main product proof with the tagged Release scope and make future release-gate changes
harder to review.

### C. Extend `evidence_provenance`

Rejected. That proof protects contract integrity and currently relies on MKE-owned schema types.
Turning it into an external installed consumer would mix two distinct trust boundaries and make it
too easy for the consumer to continue accepting payloads because producer and validator share the
same implementation.

### D. Defer to maintenance

Rejected for this stage. The individual proofs are correct, but deferral leaves the explicit
consumer-readiness composition gap untested.

## Selected Architecture

```text
repository-authored synthetic PDF bytes
        |
        v
consumer-owned versioned source-pack manifest
        |
        +------------------------------+
        | validate bytes before startup|
        +------------------------------+
        |
current source checkout -> build wheel |
        |                               |
        v                               v
fresh external temp venv/cwd + copied standalone consumer
        |
        | lock-derived, offline-capable install
        v
official MCP SDK -> installed `mke` stdio server
        |
        +--> legacy ingest_file / get_run
        |
        +--> list_libraries_v1
        |
        +--> search_library_v1 / ask_library_v1
        v
independent strict validator
        |
        v
content_fingerprint -> exact consumer manifest source key
        |
        v
in-memory consumer receipt -> public-safe aggregate report
```

The proof builds one wheel from the planning-base descendant under test. Installation occurs in a
new virtual environment using repository-lock-derived constraints and an offline-capable command.
The implementation plan must lock exact build, constraint-generation, install, and Python 3.12/3.13
commands. A missing cached locked dependency is a failed or blocked proof, not permission to access
the network or weaken isolation.

The source pack, standalone consumer, server database, and subprocess error sink are copied or
created under an external temporary workspace. The server's allowed root points only at the copied
source pack. The real server process is the installed `mke` executable, not `uv run`, a source-tree
module, or a direct application call.

## Independence Boundary

The standalone consumer is an external protocol client, not an MKE test helper. At execution time:

- its file and working directory are under the external temporary workspace;
- it may import only the Python standard library, the official MCP SDK, and dependencies installed
  with that SDK;
- it must not import `mke`, any `mke.*` module, Pydantic models exported by MKE, test helpers, or
  source-checkout code;
- it must not read SQLite, inspect repository source files, or derive schemas/models from the source
  checkout;
- it learns producer tool schemas only through MCP tool discovery and learns MKE observations and
  Evidence only through MCP calls; reading its own manifest, schema expectation fixture, and copied
  source bytes for preflight and mapping does not cross this boundary.

A separate launcher-owned identity probe may import top-level `mke` solely to return
`mke.__file__`, distribution metadata, and `sys.executable` for isolation verification. The probe
does not validate contract payloads or participate in the consumer flow. The launcher must prove
that the imported module, distribution metadata, Python executable, and installed `mke` executable
belong to the fresh external environment and that none resolves within the repository.

Before any child process starts, the launcher removes `PYTHONPATH`, `PYTHONHOME`, and `VIRTUAL_ENV`
from the inherited environment. Every controller-owned subprocess invocation uses an argv sequence
with `shell=False`, a fixed timeout, hard-bounded stdout/stderr capture, an explicit external `cwd`,
and a minimal allowlisted success-code policy. Server startup, MCP initialization, tool discovery,
and every tool call also have explicit deadlines.

The MCP server stderr stream uses a consumer-owned hard-bounded pipe and is never copied into the
public result. Raw MCP stdout framing is owned by the official MCP SDK and is not claimed to be
hard-capped before SDK parsing. Structured Search and Ask payloads are bounded by the independent
validator after parsing. Timeout, cancellation, nonzero exit, validation failure, or cleanup
failure must terminate the relevant child and fail closed.

## Source-Pack Design

The proof reuses the exact two frozen repository-authored PDFs under
`tests/fixtures/local-knowledge-v1`:

- `operations-guide.pdf`;
- `incident-guide.pdf`.

Their existing bytes, `manifest.json`, README, generator, and local-knowledge proof contract remain
unchanged. The implementation adds a separate, independently versioned consumer-owned manifest
layer. The implementation plan selects its exact file location. Its literal schema version is
`mke.consumer_source_pack_manifest.v1`, its pack ID is `local-knowledge-v1`, and it contains:

- a literal pack schema version and stable pack ID;
- a bounded consumer-owned `source_key` for each entry;
- the relative filename and media type;
- exact byte count and lowercase SHA-256;
- redistribution class identifying the material as repository-authored synthetic content;
- generator identity sufficient to point to the repository-owned generator without embedding an
  absolute path;
- fixed expected query roles and their expected source key;
- expected locator kind and allowed range for each positive query.

The manifest locks these source and query identities:

| Source key | Relative file | Media type | Bytes | SHA-256 | Paired Search/Ask query role | Locator |
|---|---|---|---:|---|---|---|
| `operations_guide` | `operations-guide.pdf` | `application/pdf` | 1000 | `0ac3e96efc89ee91e48bb3efc8611de88b2698e5aa26c1f8e0e8f78ad2d60ddd` | `Cedar Relay maintenance window` through both tools | page 1 |
| `incident_guide` | `incident-guide.pdf` | `application/pdf` | 990 | `ed55cfbe9bdbf4404eb9ff55ab7e51fac14006ae0584a14d50704f68a02ff699` | `Cedar Relay telemetry amber` through both tools | page 1 |

The unsupported query role is `lunar payroll retention policy`; it has no source key or locator and
expects active Search no-match plus Ask `insufficient_evidence`.

The manifest parser is strict: required fields only, literal schema versions, no duplicates, no
absolute paths, no parent traversal, normalized relative filenames, and no unknown fields. Before
building a server command, the launcher reads each copied fixture, verifies the exact byte count and
SHA-256, and requires a one-to-one relationship between manifest entries and copied source files.
A mismatch fails before server startup.

Filenames and paths are transport locations, never portable identity. The only portable join from
MKE Evidence to a source-pack entry is:

```text
mke.evidence_ref.v1.content_fingerprint
  == "sha256:" + manifest.sources[].sha256
```

The join must produce exactly one source key. Missing and ambiguous mappings fail closed. The pack
contains no copied third-party document, personal data, customer data, or operator-local material.

## Independent Schema And Payload Validation

The standalone consumer implements its own bounded validator with the standard library. It must
not generate validators from MKE models or source files. Tool discovery must prove:

- all five legacy tools are present with their frozen schemas unchanged;
- `list_libraries_v1`, `search_library_v1`, and `ask_library_v1` are present;
- each v1 output schema is a top-level success/error union discriminated by literal `ok`;
- all object shapes are closed and all schema-version fields are literal constants; and
- Search and Ask expose the same exact `mke.evidence_ref.v1` definition.

Exact legacy and v1 schema expectations are committed as a consumer-owned, closed JSON expectation
fixture beside the standalone client and copied into the external workspace before execution. The
client validates discovered schemas against that file. It does not copy, import, or parse producer
models or schema snapshots at runtime.

Payload validation must reject missing fields, extra fields, unknown schema versions, bool-as-int,
invalid count/state relationships, malformed identifiers, malformed fingerprints, invalid
Publication revisions, invalid page/timestamp locators, mixed success/error fields, unallowlisted
public error values, and Search/Ask projection drift. The consumer validates the public contract;
it does not try to reproduce MKE domain or persistence integrity checks.

## Consumer-Owned Receipt And Public Report

For every positive result, the consumer forms an in-memory receipt containing at least:

- consumer receipt schema version `mke.consumer_source_pack_receipt.v1`;
- pack schema version and pack ID;
- consumer source key;
- MKE Evidence schema version;
- content fingerprint;
- locator kind, start, and end;
- expected-query role; and
- the literal manifest match status `matched`.

No receipt is created for a missing, ambiguous, or invalid mapping.

Store-local `source_id`, `run_id`, `publication_id`, `publication_revision`, and `evidence_id` may be
held in memory only for same-response, same-store, and cross-store consistency checks. They must not
enter the public proof report. Evidence text may be validated in memory through bounded query and
projection rules but must not be rendered or hashed into the public report.

The receipt is proof-owned and consumer-owned. It is not an MKE public DTO, schema, persistence
model, or promise to downstream consumers.

The closed success report contains only `proof="consumer_source_pack"`, `status="passed"`, the
manifest and Evidence schema names, pack ID, source/published-Run/active-Publication/active-Evidence
counts, observed state names, and booleans for installed identity, external isolation, strict-schema
validation, Search/Ask projection equality, exact manifest mapping, fresh-store mapping, redaction,
and cleanup. The success report must not claim failure-path checks that the proof command did not
execute; focused tests carry the complete failure-path matrix. A failure report contains only:

```json
{"status": "failed", "code": "stable_machine_code"}
```

Neither success nor failure output may contain paths, MKE opaque IDs, Evidence text, text hashes,
source filenames, commands, environment values, stderr, tracebacks, or exception details.

## Required Success Flows

One proof run must establish all of the following:

1. **Installed identity and isolation.** The wheel is built from the current checkout, installed in
   a fresh external environment, and executed from an external working directory. Module,
   distribution, Python, and `mke` executable identities resolve inside that environment and outside
   the repository. Hostile Python environment variables are absent in child processes.
2. **Fresh Library.** The first real stdio session starts on a fresh store and
   `list_libraries_v1` returns the strict `empty` observation with all counts zero.
3. **Two published Runs.** The consumer ingests both source-pack PDFs through the unchanged legacy
   `ingest_file` tool and inspects both Runs through the unchanged legacy `get_run` tool. Both Runs
   are `published`, have positive Evidence counts, and expose the required ordered lifecycle
   events.
4. **Exact active observation.** After both ingests, `list_libraries_v1` returns `active` with
   `source_count=2`, `active_publication_count=2`, and `active_evidence_count=2` for the frozen
   one-page source pack.
5. **Strict positive Search and Ask.** Each fixed positive manifest query is sent separately to both
   `search_library_v1` and `ask_library_v1` and selects its expected source entry. The returned
   `results[]` and `evidence[]` validate as strict v1 payloads and contain an exact equal
   `mke.evidence_ref.v1` projection for each shared Evidence item.
6. **Portable mapping.** Each positive Evidence fingerprint maps to exactly one manifest source
   key, and each locator is a valid page locator inside the manifest's expected range.
7. **Business no-match distinction.** The unsupported manifest query returns an `active`
   observation with zero Search results. Ask returns `insufficient_evidence` with zero Evidence. It
   must not be interpreted as `empty` or `no_active_publication`.
8. **Fresh-store portability.** A second fresh store ingests the same source bytes through another
   real installed stdio session. It produces the same fingerprint-to-source-key mapping while
   store-local opaque IDs may differ and are never compared across stores as portable identity.
9. **Cleanup.** All server and helper processes terminate, every temporary store/workspace is
   removed, and cleanup is verified after the owning context exits.

## Failure And Fail-Closed Design

The implementation must exercise these failures directly or through focused unit/integration
tests:

| Failure | Required result |
|---|---|
| Manifest byte count or SHA-256 mismatch | Fail before server startup with a stable manifest identity code. |
| Missing, extra, or unknown manifest field/version | Reject through the independent manifest validator. |
| Missing, extra, or unknown MCP field/version | Reject through the independent protocol validator. |
| Fingerprint absent from the manifest | Fail closed; do not create a receipt. |
| Fingerprint maps to multiple source keys | Fail closed as an ambiguous mapping. |
| Locator kind/range contradicts the expected source/query mapping | Fail closed as a mapping violation. |
| `empty` or `no_active_publication` observed for a normal no-match | Fail closed; do not report a business no-match. |
| Server startup, MCP initialization, or tool call exceeds its deadline | Terminate the child and return a stable timeout code. |
| Child exits nonzero or transport closes unexpectedly | Return a stable transport/server-exit code. |
| Module, metadata, executable, or cwd resolves into the source tree | Fail closed as installed-identity contamination. |
| Controller subprocess stdout/stderr or MCP server stderr exceeds its configured hard bound | Terminate or reject and return a stable output-bound code. |
| Parsed Search/Ask payload exceeds the independent validator's structural bounds | Reject with a stable payload-validation code. |
| Process, store, or workspace cleanup cannot be verified | Return a stable cleanup code even if functional assertions passed. |

All launcher and standalone-consumer exceptions are caught at the public script boundary. Public
output uses this closed allowlist of stable machine codes:

- `source_pack_manifest_invalid`;
- `source_pack_identity_mismatch`;
- `wheel_build_failed`;
- `environment_create_failed`;
- `install_failed`;
- `installed_identity_failed`;
- `external_isolation_failed`;
- `consumer_schema_invalid`;
- `consumer_payload_invalid`;
- `manifest_mapping_missing`;
- `manifest_mapping_ambiguous`;
- `manifest_locator_mismatch`;
- `observation_state_mismatch`;
- `mcp_startup_timeout`;
- `mcp_tool_timeout`;
- `mcp_transport_failed`;
- `server_exit_nonzero`;
- `command_output_exceeded`;
- `cleanup_failed`; and
- `proof_failed` for an unexpected error that cannot safely map to a narrower code.

Paths, identifiers, Evidence text, filenames, stderr, tracebacks, environment data, and exception
messages are never interpolated into those codes or rendered alongside them.

## Compatibility And Runtime Boundaries

- The five legacy tools remain exactly schema-compatible with the frozen consumer expectations
  under structural JSON equality.
- The three existing v1 read tools and their strict schemas remain unchanged.
- The current domain, application, SQLite, retrieval, ranking, active-Publication, Ask-refusal, and
  error semantics remain unchanged.
- The proof adds no database migration, persistence model, runtime dependency family, public
  request field, or MKE-owned business metadata.
- The source-pack manifest and receipt remain outside MKE domain and application contracts.
- No version, tag, Release, PyPI, CHANGELOG, deployment, or publication action is included.
- The proof consumes the exact current-main contract. It must not describe that contract as part of
  the tagged `v0.1.1` Release.

The intended implementation is one independently reviewable proof/docs/tests PR. Any discovered
need to modify `src/mke`, canonical MCP schemas, SQLite, retrieval behavior, or Publication
semantics is a stop condition requiring a new design decision rather than scope expansion inside
that PR.

## Testing And Verification Design

### Unit coverage

Focused tests cover:

- strict source-pack manifest parsing and path normalization;
- byte-count/SHA-256 preflight and one-to-one file membership;
- independent MCP tool-schema and response validation;
- in-memory receipt construction and exact/absent/ambiguous fingerprint mapping;
- locator/source/query consistency;
- observation-state interpretation;
- stable failure-code mapping;
- public report redaction and output bounds; and
- identity, subprocess, timeout, termination, and cleanup helpers.

### Integration coverage

Real stdio integration uses the copied standalone consumer against the installed `mke` executable
and covers every required success flow. Tests must also prove that the consumer file and cwd are
external, hostile Python environment variables are cleared, only the explicit consumer assets and
source pack are copied, and no repository path is supplied to the consumer. Focused tests and a
static audit of the standalone consumer must reject `mke` or `sqlite3` imports and any direct
repository or database read, proving that the successful consumer path neither reads nor depends on
the source checkout or SQLite directly. These are verifiable dependency and behavior assertions
under a shared OS principal, not a claim that an OS sandbox removes filesystem access.

### Installed-wheel matrix

The external proof runs at least once with each currently supported Python minor, 3.12 and 3.13,
using fresh environments and the same built wheel. The implementation plan records exact interpreter
identities, commands, constraints, cache/offline settings, timeouts, and expected aggregate output.
Unsupported or unavailable interpreters are reported explicitly; they are not silently replaced by
the controller's Python.

### Repository gates

The implementation plan must include these gates, using the exact commands supported at execution
time:

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

The implementation adds focused unit, real stdio, external installed-wheel, documentation, and
redaction tests and runs them before the full gates.

If implementation does not modify `src/mke` or canonical evaluation inputs, it does not trigger an
E1 through E3 artifact identity refresh. If actual implementation changes a validator-declared
source/scope/dependency identity, execution stops and re-evaluates the identity closure before any
artifact write. Corpus bytes, qrels, queries, observations, metrics, gates, candidates, profiles,
and verdicts must never drift as a side effect of this proof.

## Documentation Design

Implementation adds one dedicated how-to that explains:

- the source-built installed-consumer command;
- the exact external and offline isolation boundary;
- the source-pack fingerprint mapping;
- stable success/failure output; and
- explicit "proves" and "does not prove" sections.

README and the documentation index receive only the minimum link and one-sentence positioning
needed to discover the how-to. The MCP reference is updated only if the implementation needs to
point existing schemas to this new proof; it must not restate or modify the contract.

Release verification documentation remains unchanged because this is not a release gate. A future
separate decision that promotes the proof to a release gate must define its own release-document
change; this design does not do so.

## Non-Goals

- No consumer-specific workflow, authority, review, freshness, tenant, decision, or other business
  fields.
- No named downstream-product or orchestrator integration.
- No OCR, HTML, crawler, HTTP, UI, service adapter, hosted process, or multi-tenant surface.
- No dense, hybrid, RRF, reranker, query rewrite, HyDE, segmentation, or retrieval promotion.
- No real third-party material, operator-local private material, production user, SLA, ROI, or
  production-readiness claim.
- No generative Ask behavior; Ask remains evidence-only with `insufficient_evidence`.
- No change to ingestion, Run, Publication, retrieval, provenance, or error semantics.
- No new version, tag, Release, PyPI upload, deployment, or other publication behavior.

## Acceptance Criteria

- [ ] One command builds the current checkout, installs it under lock-derived offline-capable
      constraints, and runs the proof from a fresh workspace outside the repository.
- [ ] The proof passes on supported Python 3.12 and 3.13 interpreters using the same wheel and fresh
      environments.
- [ ] Module, distribution metadata, Python, `mke` executable, consumer file, and cwd identities
      prove installed/external isolation; hostile Python environment variables are cleared.
- [ ] Only explicit consumer assets and source-pack files enter the external workspace; no
      repository path is supplied to the standalone consumer. Focused tests and static audit reject
      `mke`/`sqlite3` imports and direct repository/database reads, and the successful consumer path
      derives no schema from the source checkout and obtains MKE data only through official MCP SDK
      stdio calls, without claiming OS-level filesystem isolation.
- [ ] Existing frozen synthetic PDF bytes and `local-knowledge-v1` assets remain unchanged; a
      separate strict manifest owns pack identity and consumer source keys.
- [ ] Manifest bytes and hashes validate before server startup, and fingerprint mapping is exact,
      unique, and based only on `sha256:<digest>`.
- [ ] A fresh store reports strict `empty`; two legacy ingests produce two observable published
      Runs; the active observation reports exact `2/2/2` counts.
- [ ] Strict v1 Search and Ask return the same Evidence projection for positive queries, map to the
      expected manifest source keys, and carry valid page locators.
- [ ] The unsupported query returns active no-match and `insufficient_evidence`, never empty or
      no-active semantics.
- [ ] A second fresh store preserves fingerprint-to-source-key mapping while making no cross-store
      promise about opaque IDs.
- [ ] Independent validators reject every required malformed manifest/schema/payload, mapping,
      observation, locator, identity, transport, timeout, output-bound, child-exit, and cleanup
      case with stable failure codes.
- [ ] Public success/failure output contains no path, opaque ID, Evidence text or hash, filename,
      command, environment value, stderr, traceback, or exception detail.
- [ ] All five legacy schemas and all three existing v1 schemas remain unchanged; there is no MKE
      runtime semantic, request, persistence, dependency-family, or business-metadata change.
- [ ] Focused tests, real stdio integration, both installed-wheel interpreter proofs, full pytest,
      Ruff, Pyright, build, product proof, demo, local-knowledge proof, Evidence-provenance proof,
      release presentation audit, documentation checks, and `git diff --check` pass.
- [ ] A dedicated how-to plus minimal README/docs-index links state exactly what the proof proves and
      does not prove; release verification remains unchanged unless separately approved.
- [ ] The final diff is one coherent proof/docs/tests PR with no version, release, deployment,
      evaluation-semantic, fixture-byte, or unrelated change.

## Future Consumer Handoff

A future consumer may pin either an exact MKE commit that contains the strict provenance contract
or a later Release that explicitly includes it. The consumer can discover and validate the public
MCP schemas, maintain its own source-pack manifest, map `content_fingerprint` to its own source key,
and project the resulting Evidence into its own adapter and authority model.

This proof does not own downstream workflow state, business eligibility, review, decision, or
delivery authority. It proves only that the provider contract can be consumed independently and
mapped to portable consumer-owned source identity without crossing MKE's application boundary.
