# Consumer-Ready Source-Pack Proof Plan Review

Review target: `docs/superpowers/plans/2026-07-12-consumer-ready-source-pack-proof-implementation.md`
at planning commit `83634ff38f0099c79ba0d1da1d272847dbf7e34a`.

Review status: targeted engineering re-review completed; all four amendments accepted.

## Scope Challenge And Accepted One-PR Rationale

The design composes several boundaries—consumer-owned fixtures, independent protocol validation,
installed-wheel orchestration, real stdio MCP, two supported Python minors, CI, and documentation.
Splitting them across PRs would leave intermediate states that either cannot prove the approved
consumer flow or can drift between fixture/schema ownership and the installed proof. One focused
PR remains the smallest independently useful unit because all changes are proof-only scripts,
consumer-owned fixtures, focused tests, one CI job, and discoverability documentation.

The scope is accepted only while producer runtime and contracts remain untouched. Any need to
modify `src/mke/**`, canonical MCP schemas, domain/application/SQLite/retrieval/Publication
semantics, frozen PDFs, evaluation semantics, version/release/publication surfaces, deployment, or
release verification is a stop condition requiring a separate decision.

## Existing Surfaces And Reuse

- `scripts/release_consumer_smoke.py` supplies installed-module identity, hostile-environment
  clearing, external cwd, redacted failures, and bounded-command patterns to improve rather than
  extend in place.
- `src/mke/proof/local_knowledge.py` and `tests/fixtures/local-knowledge-v1/**` supply the real stdio
  flow and two frozen repository-authored synthetic PDFs. Their bytes and existing contract remain
  unchanged.
- `src/mke/proof/evidence_provenance.py` and strict v1 interface tests define the current Search/Ask
  Evidence projection, observation states, locator behavior, cross-store fingerprint identity, and
  redaction expectations. The external consumer revalidates them independently.
- `tests/fixtures/mcp/legacy-tool-schemas.json` protects the five legacy tools. The new consumer
  fixture freezes all eight discovered tools plus the exact current public-error validation data.
- `.github/workflows/ci.yml` already pins checkout, uv, and setup-python actions. The new job reuses
  those pins while separating online cache provisioning from the offline proof.

## Findings And Resolutions

### Finding 1 — CI Cold-Cache Provisioning

The initial plan placed both environment setup and proof execution under `UV_OFFLINE=1`. A fresh
runner cannot assume build and dependency caches exist, and provisioning only the controller's
active Python would not prepare minor-specific locked wheels for both 3.12 and 3.13.

Resolution: the amended CI task has two explicit phases. An online provisioning step runs the
locked controller sync, exports core locked requirements, creates prewarm environments from the two
setup-python output paths, and installs those requirements for both minors. A later distinct step
runs only the controller with `UV_OFFLINE=1`. Workflow tests require ordering, both interpreter
caches, and offline scope. The controller may not retry online. Documentation states that a
prepared cache is required and makes no empty-machine air-gap claim.

### Finding 2 — Enforceable Output Bounds

The initial `Popen.communicate()` design could detect oversize output only after buffering it and
could not guarantee termination at the configured cap. A temporary stderr file for the MCP server
would likewise be a post-hoc size check rather than a hard bound.

Resolution: controller subprocesses incrementally drain stdout and stderr in fixed-size chunks,
track per-stream counters, record the first terminal event against a monotonic deadline, and run a
process-group terminate/grace/kill/wait sequence on overflow or timeout. Live noisy-child tests
require termination at the cap. The standalone client passes an OS-pipe write end to
`stdio_client(errlog=...)`, drains the read end asynchronously, cancels the MCP context on overflow,
and verifies server termination. Overflow wins only when its cap event was observed before the
deadline; otherwise timeout wins. Client server cleanup and controller outer cleanup remain
separate owners.

### Finding 3 — Exact Independent Error And Schema Contract

The initial plan described closed `problem` and `next_step` allowlists, which did not match the
producer contract. The current contract accepts both through the MachineToken pattern, requires
impact `unchanged`, and restricts only `cause` to the public-safe cause set including the redacted
cause.

Resolution: the consumer expectation fixture now owns the exact MachineToken regex, literal impact,
and sorted safe-cause set beside all eight exact discovered tool schemas. The plan includes an exact
development-time freeze command and a producer-side structural-equality regression test. Runtime
consumer code reads only its copied fixture. Standalone validator tests cover invalid and multiple
valid machine tokens, impact drift, safe-cause membership, schema mutations, and projection drift.
`validate_tool_schemas` consumes a consumer-owned Protocol and normalizes immediately to mappings.

### Finding 4 — Final Dual-Interpreter Evidence

The initial final-gate prose claimed the real dual-interpreter proof passed even though the listed
commands did not invoke it after documentation and CI changes.

Resolution: the amended final task discovers explicit 3.12/3.13 interpreter paths, runs the
controller with `UV_OFFLINE=1` after every code/docs/CI edit, and compares the emitted JSON to the
complete approved aggregate object. The changed-text scan now covers fixtures, CI, README/docs
index, spec/plan/review history, scripts, and tests.

## Data And Test Flow

```text
current checkout
      |
      +--> development-only discovery --> consumer schema/safe-cause fixture
      |                                      |
      |                                      +--> producer structural regression
      |
      +--> one wheel build -------------------------------+
      |                                                   |
locked export --> online CI prewarm (3.12 + 3.13)         |
                         |                                 |
                         v                                 v
                  offline controller --> fresh env 3.12 / fresh env 3.13
                                              |             |
frozen PDFs + consumer manifest/schema ------+-------------+
                                              |
                                              v
                               copied standalone MCP client
                                              |
                           real installed mke stdio server x two stores
                                              |
                         strict schemas/payloads + exact fingerprint map
                                              |
                                              v
                               redacted exact aggregate JSON

RED unit/mutation tests -> bounded live-child tests -> real stdio integration
      -> same-wheel dual-minor proof -> docs/CI checks -> full repository gates
```

## Failure-Mode And Test Coverage

- Manifest structure, path normalization, membership, byte count, and SHA-256 fail before startup.
- Exact schema discovery, MachineToken handling, literal impact, safe causes, strict payload shapes,
  bool-as-int, IDs, fingerprints, revisions, state/count relationships, locators, error unions, and
  Search/Ask projection equality are mutation-tested independently.
- Missing/ambiguous fingerprint joins and query/source/locator mismatches fail without receipts.
- Fresh, active, and normal no-match observations are distinct and fail closed on state drift.
- Startup/tool deadlines, transport close, nonzero exit, stdout/stderr overflow, cleanup, and
  unexpected failures map to the closed stable-code set with redacted two-key output.
- Live noisy children prove early cap enforcement and process-group termination; MCP stderr uses an
  incrementally drained pipe rather than post-exit inspection.
- Installed identity, external cwd/assets, hostile environment clearing, same-wheel reuse, both
  supported minors, second-store mapping, and outer cleanup are covered by controller tests and the
  final real proof.

## Performance And CI Conclusion

The proof is bounded by explicit job, command, startup, and tool deadlines; fixed stdout/stderr
caps; two one-page PDFs; two stores; and a fixed query set. One non-matrix job avoids building two
different wheels and makes same-wheel reuse directly reviewable. Online provisioning may download
locked artifacts once, while the proof phase is offline and fails rather than changing network
policy. This adds a deliberate installed-consumer job without expanding the existing Python matrix
or product runtime.

## NOT In Scope

- Producer runtime, MCP request/response schemas, persistence, retrieval, ranking, ingestion,
  Publication activation, or Ask semantics.
- Changes to frozen PDFs, their existing manifest/generator, or any retrieval/evaluation artifact,
  protocol, query, qrel, observation, metric, gate, profile, candidate, or verdict.
- Version, tag, Release, PyPI, changelog, deployment, release verification, or publication work.
- OCR, HTTP, UI, crawler, hosted/multi-tenant behavior, external providers, model downloads, or
  downstream workflow/business metadata.
- A claim of OS-level filesystem isolation or air-gapped installation from an empty machine.

## Sequential Execution Recommendation

Execute Tasks 1 through 5 sequentially because they share and progressively freeze the two proof
scripts and consumer fixtures. Task 1 freezes manifest/schema inputs; Task 2 freezes validator
interfaces; Task 3 freezes the stdio/client result contract; Task 4 freezes controller/process
ownership; Task 5 closes integration and failure coverage. Documentation may proceed only after
those interfaces are frozen. CI and final verification remain last so they validate the complete
code, fixture, and documentation surface.

## Verdict

**CLEARED FOR IMPLEMENTATION.** The one-PR scope, focused file map, stop conditions, and all four
amendments are accepted. Implementation may begin only after the plan and review changes are
committed and explicitly dispatched. Push, PR creation, merge, release, and publication remain
unauthorized.
